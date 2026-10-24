import json

def json_to_dict(json_string:str) -> dict:
    """
    Converts a JSON string to a Python dictionary.

    Args:
        jsonString (str): A string in JSON format.

    Returns:
        dict: A Python dictionary representation of the JSON string.
    """

    try:
        return json.loads(json_string)
    except json.JSONDecodeError as e:
        return None
