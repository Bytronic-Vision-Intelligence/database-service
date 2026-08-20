import json

def json_to_dict(json_string):
    '''converts a json string to a dictionary
    Args:
        json_string: the json string
    Returns:
        dictionary: the converted json string'''

    return json.loads(json_string)