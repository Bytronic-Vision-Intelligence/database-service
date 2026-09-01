"""Populate the store with sample inspections, for looking at the UI.

Publishes over MQTT through the normal save_frame / save_result path, so the
rows land exactly as the running system would write them - schema, links and
denormalised columns included. Nothing is inserted directly.

This is a development aid. The sample data is NOT part of database/seed.sql:
a fresh checkout should not ship fabricated inspection history.

    ./.venv/bin/python tools/generate_sample_results.py --count 40

Requires database-service to be running against the same broker.
"""

from __future__ import annotations

import argparse
import base64
import glob
import json
import random
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from mqtt_client import MQTTClient, MQTTConfig  # noqa: E402

SAVE_FRAME_TOPIC = "project/db/frame/save"
SAVE_RESULT_TOPIC = "project/db/result/save"

# Classes yolov8n actually knows, so the data looks like real output.
CLASSES = [
    ("person", 0), ("bottle", 39), ("cup", 41), ("chair", 56),
    ("laptop", 63), ("mouse", 64), ("keyboard", 66), ("book", 73),
]


def _detection(rng: random.Random) -> dict:
    name, cls = rng.choice(CLASSES)
    x1, y1 = rng.uniform(0, 900), rng.uniform(0, 500)
    return {
        "name": name,
        "class": cls,
        "confidence": round(rng.uniform(0.31, 0.98), 5),
        "box": {
            "x1": round(x1, 3),
            "y1": round(y1, 3),
            "x2": round(x1 + rng.uniform(60, 700), 3),
            "y2": round(y1 + rng.uniform(60, 500), 3),
        },
    }


def _detections(rng: random.Random) -> list:
    # Weighted so most inspections find something but empty results still occur -
    # "nothing detected" is a real outcome and should be visible in the table.
    n = rng.choices([0, 1, 2, 3, 4], weights=[8, 34, 30, 20, 8])[0]
    return [_detection(rng) for _ in range(n)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=40, help="inspections to create")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--camera-id", default="colour_1")
    parser.add_argument("--seed", type=int, default=7, help="for repeatable output")
    parser.add_argument(
        "--frame-ratio",
        type=float,
        default=0.55,
        help="fraction that also store an image (a Save frame rather than a Trigger)",
    )
    args = parser.parse_args()

    rng = random.Random(args.seed)

    images = sorted(
        glob.glob(
            str(Path(__file__).resolve().parents[1] / "database/images/**/*.jpg"),
            recursive=True,
        )
    )
    if not images:
        print("No captured image on disk to reuse; frames will not be created.")
    jpeg_b64 = (
        base64.b64encode(Path(images[0]).read_bytes()).decode("ascii")
        if images
        else None
    )

    client = MQTTClient(MQTTConfig(host=args.host, port=args.port))
    client.connect()

    # Spread backwards from now so the newest-first ordering is visible.
    now = datetime.now().replace(microsecond=0)
    stored = 0

    for i in range(args.count):
        ts = (now - timedelta(minutes=(args.count - i) * 7)).strftime("%Y-%m-%d %H:%M:%S")
        with_frame = jpeg_b64 is not None and rng.random() < args.frame_ratio

        if with_frame:
            client.publish(SAVE_FRAME_TOPIC, {
                "command": "save_frame",
                "camera_id": args.camera_id,
                "image": jpeg_b64,
                "date_time": ts,
            })
            stored += 1
            time.sleep(0.35)  # let the frame land so the result links to it

        client.publish(SAVE_RESULT_TOPIC, {
            "command": "save_result",
            "camera_id": args.camera_id,
            "date_time": ts,
            "model": "yolov8n.pt",
            "detections": _detections(rng),
        })
        time.sleep(0.12)

    time.sleep(1.5)
    client.disconnect()
    print(
        f"Published {args.count} inspections "
        f"({stored} with a stored frame, {args.count - stored} trigger-only)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
