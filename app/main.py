from dependencies.mqtt_functions import *

from dependencies import loadConfig
from dependencies.sqlite_database_actions import SqliteDatabaseActions

import time
from logging import info
from json import loads, dumps
from threading import Event
from queue import Empty, Queue
from mqtt_client import MQTTClient, MQTTConfig
from sys import getsizeof
#
MQTT_BROKERS = loadConfig.return_config_value("broker_details")
TOPICS = loadConfig.return_config_value("topics")
DATABASE_DETAILS = loadConfig.return_config_value("database")
#: Names this service in anything it publishes. A module-level default rather
#: than only being set inside main(): `global service_id` at module scope does
#: nothing, so the name main() assigned was a LOCAL and invisible to anything
#: out here -- which made the error reporter raise NameError at the exact
#: moment it was needed. Replaced from config at startup.
service_id = "database-service"

#: How long a blocking wait allows a frame to arrive.
#:
#: Was 10s, against a colour camera whose own `capture_timeout` is 50s and
#: which measures ~5.3s per frame on a 1500-MTU link. Those two numbers
#: disagreed by 5x: the camera was permitted to still be working long after
#: the consumer had given up, so a slow-but-successful capture was recorded as
#: a failure. 30s sits above the observed capture time and still below the
#: camera's own limit, so a genuinely stuck camera is still bounded.
TRIGGER_TIMEOUT_S = 15


def report_status(client, severity: str, event: str, message: str, **extra) -> None:
    """Publish the outcome of a write, good or bad, for the HMI to act on.

    BOTH outcomes are published, not just failures. The HMI greys its buttons
    while a capture is in flight, so it needs to hear that a plate saved just
    as much as that one did not -- a success that says nothing leaves the
    operator looking at a disabled screen wondering whether to wait.

    And a plate that did not save has to reach whoever is standing at the
    line. Until now the only sign was a traceback in a console window behind
    the HMI, and the cell stopping -- which tells an operator that something
    is wrong but not what, and takes every other service down to say it.

    Logs as well as publishes: the log is the record afterwards, the topic is
    what somebody sees now. Neither replaces the other.
    """
    payload = {
        "service": service_id,
        "severity": severity,
        "event": event,
        "message": message,
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        **extra,
    }
    info(f"{severity.title()}: {message}")
    print(f"{severity.title()}: {message}")

    topic = next(
        (t.get("topic") for t in TOPICS if t.get("name") == "status_output"),
        None,
    )
    if not topic:
        # Not configured. The log line above still happens, so a deployment
        # that has not added the topic behaves exactly as it did before rather
        # than failing in the reporting path -- the worst place to fail.
        return
    try:
        client.publish(topic, dumps(payload))
    except Exception as exc:
        info(f"Error: could not publish the status report: {exc}")


def report_error(client, event: str, message: str, **extra) -> None:
    """Shorthand for the failure case."""
    report_status(client, "error", event, message, **extra)


def check_for_triggers(trigger:dict, is_blocking:bool=False, timeout:float = TRIGGER_TIMEOUT_S):
    '''Checks the queue for each of the trigger topics and returns the message when any of them have received one
    Args:
        triggers: a dictionary of topics
        is_blocking: a boolean value that controls the blocking functionality
        timout: a float that determines the timout in s
    Returns:
        message: the message received from the trigger as dictionary'''

    if not trigger:
        raise ValueError("Error : trigger cannot be empty")
    message = {"image": None}

    if is_blocking:
        message = loads(trigger["queue"].get(timeout=timeout))
        return message
    
    try:
        message = loads(trigger["queue"].get_nowait())
    except Exception as e:
        if e != KeyError: info(f"error occured when checking for trigger {e}")

    return message

def _check_for_triggers(triggers:dict):
    '''Checks the queue for each of the trigger topics and returns the message when any of them have received one
    Args:
        triggers: a dictionary of topics
    Returns:
        message: the message received from the trigger as dictionary'''
    message = {"command": None}

    for trigger in triggers:
        try:
            if not trigger["is_trigger"]:continue
        except:
            continue

        try:
            message = loads(trigger["queue"].get_nowait())
        except Exception as e:
            if e != KeyError: info(f"error occured when checking for trigger {e}")
            continue

    return message

#: How many candidates the HMI is offered. The prediction panel has four
#: slots; sending more would be data nobody can act on, and each one carries a
#: colour image.
MATCH_LIMIT = 4


def _similarity(target: dict, candidate: dict, fields) -> float:
    """How far a candidate is from the measured plate. Lower is closer.

    RELATIVE difference per field, averaged -- not raw distance. The fields are
    on wildly different scales (depth ~200, radius ~900, perimeter ~12000), so
    a raw distance is really a perimeter ranking with two fields along for the
    ride: being 100 out on perimeter is under 1%, while 100 out on depth is
    half the value.

    Each field contributes its own fractional error instead, so "5% out on
    everything" ranks the same whichever field it is, which is what a person
    means by similar.
    """
    scores = []
    for field in fields:
        try:
            want = float(target.get(field))
            got = float(candidate.get(field))
        except (TypeError, ValueError):
            continue
        scale = max(abs(want), 1.0)
        scores.append(abs(want - got) / scale)
    if not scores:
        return float("inf")
    return sum(scores) / len(scores)


def _fuzzy_search_database(
        client:MQTTClient, 
        message:dict, 
        db:SqliteDatabaseActions,
        headers,
        threshold:float=0
    ):
    '''performs a fuzzy search on the current database and publishes the results to a given MQTT broker
    Args:
        client: an MQTT client object
        message: a dict containing a search term
        db: a database actions object
    '''
    if client is None: raise ValueError("Error: client cannot be None")
    if message is None: raise ValueError("Error: message cannot be empty")
    if db is None: raise ValueError("Error: no database object detected")

    result_packet = dict()
    response = dict()

    database_name = message.get("database_name")
    if database_name == None: raise ValueError(f"Error : database name cannot be None")
    table_name = message.get("database_table")
    if table_name == None: raise ValueError(f"Error : table name cannot be None")

    # The fields the search actually compares on, so ranking uses the same
    # ones rather than a second list that can drift from it.
    headers_for_ranking = list(headers)
    search_results = db[database_name].search(table_name, message,headers, threshold)
    output_topic = next(
        topic["topic"]
        for topic in TOPICS
        if topic.get("name") == "database_output"
    )
    
    response["matches_found"]=len(search_results)
    client.publish(f"{output_topic}", dumps(response))
    
    if len(search_results) == 0:return

    # Ranked, then capped. The query is a box filter -- "within +/- threshold
    # on every field" -- with no ORDER BY and no LIMIT, so the rows arrive in
    # whatever order sqlite yields them. Presenting those as "closest first"
    # would be inventing a meaning the data does not carry.
    ranked = sorted(
        search_results.items(),
        key=lambda item: _similarity(message, item[1], headers_for_ranking),
    )[:MATCH_LIMIT]

    packet_list = []
    # Slots are numbered from 1, not 0: the number reaches an operator at the
    # panel, and the subtopic has to agree with what the HMI subscribes to.
    for position, (candidate, candidate_details) in enumerate(ranked, start=1):
        packet = dict()
        packet["topic"] = f"{output_topic}/{position}"
        packet["payload"] = {
            "packet_number": position,
            # Where it came in the ranking, so the HMI does not have to
            # re-derive an order from packets that may arrive out of sequence.
            "rank": position,
            "score": round(
                _similarity(message, candidate_details, headers_for_ranking), 4),
            "sku":candidate_details.get("sku", 0000),
            "id":candidate_details.get("id",0000),
            "depth": candidate_details.get("depth"),
            "perimeter": candidate_details.get("perimeter"),
            "radius": candidate_details.get("radius"),
            "colour_data": candidate_details.get("colour_data"),
        }
        packet_list.append(packet)
        print(f"Info : database-service Packet size = {getsizeof(candidate)*0.00000095367432} MB")
                

    client.publish_many(packet_list)

def main():
    config = loadConfig.get_config()
    global service_id
    service_id = config.get("service_id", "database_1")
    print(f"INFO : {service_id} starting \n\r")
    config = MQTTConfig(host=MQTT_BROKERS["mqtt_ip"], port=MQTT_BROKERS["mqtt_port"])
    for database in DATABASE_DETAILS:
        db = {database["database_name"]: SqliteDatabaseActions(
            database_location=database["file_location"]
        )}
        table_name = database["tables"][0]["database_table"]
        headers = database["tables"][0]["columns"]
        search_headers = database["tables"][0]["searchable_columns"]
        # What an admin is allowed to rewrite on a stored row. Absent means
        # none, so a deployment that has not opted in cannot be edited at all
        # rather than defaulting to something editable.
        editable_headers = database["tables"][0].get("editable_columns") or []
        print(headers)
        if not db[database["database_name"]].check_table_exists(table_name):
            raise ConnectionError(f"Error : Could not connect to table {table_name}")
        db[database["database_name"]].set_database_map(table_name)
        db["threshold"]=database["search_threshold"]

    client = MQTTClient(config)
    client.connect()

    stop_event = Event()
    for topic in TOPICS:
        if not topic["is_subscribe"]:
            continue
        topic["queue"] = Queue()
        
        topic["thread"] = start_subscribe_thread(
            MQTT_BROKERS["mqtt_ip"], 
            MQTT_BROKERS["mqtt_port"], 
            topic["topic"], 
            topic["queue"],
            stop_event
        )

    try:
        while True:
            time.sleep(0.1)
            message = _check_for_triggers(TOPICS)
            if message.get("database_instruction") == "search_database":
                # Checked BEFORE the blocking waits below, because those waits
                # CONSUME the camera frames. Validating afterwards -- as this
                # did -- meant a search request with no database_name drained
                # the colour and depth queues and then failed anyway, and the
                # write_database that followed found nothing and abandoned the
                # row. The frames are published once per capture: whichever
                # branch takes them first is the only one that gets them, so a
                # request that cannot succeed must not take them at all.
                if not message.get("database_name"):
                    # The whole message is logged because nothing configured on
                    # this machine sends this: both HMI buttons carry
                    # database_name, no retained message exists, and only the
                    # instruction topic is a trigger. So the sender is unknown,
                    # and the payload is the only thing that will identify it.
                    info(f"Error: {service_id} search ignored; no database_name. "
                         f"Message was: {message}")
                    print(f"Error: {service_id} search ignored; no database_name. "
                          f"Message was: {message}")
                    continue
                try:
                    colour_image = next((t for t in TOPICS if t.get("name") == "colour_data"), None)
                    depth_image = next((t for t in TOPICS if t.get("name") == "depth_data"), None)
                    depth_data = next((t for t in TOPICS if t.get("name") == "request_command"), None)

                    colour_image_out = check_for_triggers(colour_image, True)
                    depth_image_out = check_for_triggers(depth_image, True)
                    depth_data_out = check_for_triggers(depth_data, True)
                    search_data = {
                        **message,
                        **colour_image_out, 
                        **depth_image_out, 
                        **depth_data_out
                    }

                    _fuzzy_search_database(
                        client, 
                        search_data, 
                        db, 
                        search_headers,
                        db["threshold"]
                    )

                except Exception as e:
                    info(f"Error: {service_id} fuzzy search failed: {e}")
                    print(f"Error: {service_id} fuzzy search failed: {e}")

            elif message.get("database_instruction") == "write_database":
                write_data = message
                print(f"Info : write received, origional message = {write_data}")
                colour_image = next((t for t in TOPICS if t.get("name") == "colour_data"), None)
                depth_image = next((t for t in TOPICS if t.get("name") == "depth_data"), None)
                depth_data = next((t for t in TOPICS if t.get("name") == "request_command"), None)

                # A frame that did not arrive in time is a LOST ROW, not a
                # reason to stop the line. This used to be three bare blocking
                # waits: queue.Empty propagated out of main() and the process
                # exited 1, which took every other service down with it -- a
                # slow colour capture stopping the whole cell.
                #
                # The search branch above has always caught this. The write
                # branch did not, so the identical timeout was survivable on
                # one path and fatal on the other. It is caught here for the
                # same reason, and names which frame was missing so the cause
                # is in the log rather than inferred from a traceback.
                # Names the frame currently being waited on, so the log says
                # WHICH one was late. Set before each wait rather than
                # inferred afterwards: these locals survive into the next loop
                # iteration, so anything derived from their existence would
                # report the previous capture's state.
                pending = "colour_data"
                try:
                    colour_image_out = check_for_triggers(colour_image, True)
                    colour_image_out["colour_data"] = colour_image_out.pop("image")

                    pending = "depth_data"
                    depth_image_out = check_for_triggers(depth_image, True)
                    depth_image_out["depth_data"] = depth_image_out.pop("image")

                    pending = "request_command"
                    depth_data_out = check_for_triggers(depth_data, True)
                except Empty:
                    report_error(
                        client, "write_timeout",
                        f"Plate not saved: no {pending} arrived within "
                        f"{TRIGGER_TIMEOUT_S}s",
                        missing=pending, timeout_s=TRIGGER_TIMEOUT_S)
                    continue
                except Exception as e:
                    report_error(client, "write_failed", f"Plate not saved: {e}")
                    continue

                write_data = {
                    **write_data,
                    **colour_image_out, 
                    **depth_image_out, 
                    **depth_data_out
                }
                # The SKU the operator typed, when the request carried one.
                # "TBD" remains the fallback so a bare write_database -- the
                # old button, or anything else on the bus -- behaves exactly
                # as it did. A part named at capture time does not have to be
                # hunted down and renamed afterwards.
                write_data["sku"] = str(message.get("sku") or "").strip() or "TBD"
                try:
                    db[write_data["database_name"]].add_sku(
                        write_data["database_table"], 
                        write_data,
                        headers
                    )

                    print(f"Info : data added to database {write_data.get('database_name')}, {write_data.get('destination')}")
                    report_status(client, "info", "write_ok", "Plate saved",
                                  table=write_data.get("database_table"))
                except Exception as e:
                    report_error(client, "write_failed",
                                 f"Plate not saved: database write failed: {e}")
            elif message.get("database_instruction") == "update_database":
                # Takes nothing from the camera queues, and must not: an edit
                # corrects a row that already exists, so there is no capture to
                # wait for. A blocking wait here would consume the frames of a
                # capture running at the same time -- which is exactly how the
                # search branch used to strand writes.
                database_name = message.get("database_name")
                if not database_name or database_name not in db:
                    report_error(
                        client, "update_failed",
                        "Edit not saved: that database is not configured",
                        database_name=database_name)
                    continue

                row_id = str(message.get("id") or "").strip()
                if not row_id:
                    report_error(client, "update_failed",
                                 "Edit not saved: no part was identified")
                    continue

                # Only the configured columns are read out of the request. A
                # message naming anything else does not fail -- the extra key
                # is simply not a column anyone may change, and the request
                # carries routing keys (database_name, instruction) too.
                values = {
                    column: str(message[column]).strip()
                    for column in editable_headers
                    if message.get(column) is not None
                }
                if not values:
                    report_error(client, "update_failed",
                                 "Edit not saved: nothing was changed")
                    continue
                if any(value == "" for value in values.values()):
                    # A part with no name cannot be found again, and the search
                    # slots would show it as blank rather than as anything an
                    # operator could recognise.
                    report_error(client, "update_failed",
                                 "Edit not saved: a part needs a name")
                    continue

                try:
                    changed = db[database_name].update_sku(
                        message.get("database_table") or table_name,
                        row_id,
                        values,
                        editable_headers,
                    )
                except Exception as e:
                    report_error(client, "update_failed",
                                 f"Edit not saved: {e}", id=row_id)
                    continue

                if not changed:
                    report_error(
                        client, "update_missing",
                        "Edit not saved: that part is no longer in the database",
                        id=row_id)
                    continue

                report_status(
                    client, "info", "update_ok",
                    f"Saved as {values['sku']}" if "sku" in values
                    else "Part details saved",
                    id=row_id, changed=sorted(values))

            else:
                continue

    except KeyboardInterrupt:
        print(f"Info : {service_id} Shutting down subscribe listener and exiting.")

if __name__ == "__main__":
    main()