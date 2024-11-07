import json
import uuid

from jsonschema import validate, ValidationError
from dpongpy.log import logger


def encode_event(event_dict: dict) -> str:
    """
    Encode an event dictionary into a JSON string.
    Validates against PONG_EVENT_SCHEMA before encoding.

    Returns:
        str: JSON encoded event
    Raises:
        ValidationError: If event doesn't match schema
        JSONEncodeError: If event can't be encoded
    """
    if not validate_event(event_dict):
        raise ValidationError("Event validation failed")

    return json.dumps(event_dict, indent=2)


def decode_event(event_str: str) -> dict:
    """
    Decode a JSON string into an event dictionary.
    Validates against PONG_EVENT_SCHEMA after decoding.

    Returns:
        dict: Decoded event
    Raises:
        ValidationError: If event doesn't match schema
        JSONDecodeError: If event can't be decoded
    """
    event_dict = json.loads(event_str)
    if not validate_event(event_dict):
        raise ValidationError("Event validation failed")

    return event_dict

def put_event(client, event):
    try:
        unique_id = str(uuid.uuid4())
        key = f"{EVENTS_KEY_PREFIX}/{unique_id}"
        lease = client.lease(60)  # Create a lease with a 60-second TTL
        result = client.put(
            key,
            encode_event(event),
            lease=lease
        )
        if not result:
            logger.error("Failed to put event to etcd: No result returned")
        logger.debug(f"Put event to etcd on key '{key}' with lease ID {lease.id}")
        logger.debug(f"Data: {json.dumps(event, indent=4)}")
    except Exception as e:
        logger.error(f"Failed to put event to etcd: {e}")
        raise e

EVENTS_KEY_PREFIX = "pong_events"

PONG_EVENT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Pong Game Event Schema",
    "type": "object",
    "properties": {
        "eventId": {"type": "string", "description": "Unique identifier for the event"},
        "eventType": {
            "type": "string",
            "enum": [
                "PLAYER_JOIN",
                "PLAYER_LEAVE",
                "PADDLE_MOVE",
                "GAME_START",
                "GAME_OVER",
                "TIME_ELAPSED",
            ],
            "description": "Type of game event",
        },
        "timestamp": {
            "type": "number",
            "description": "Event timestamp in milliseconds",
        },
        "gameId": {
            "type": "string",
            "description": "ID of the game this event belongs to",
        },
        "playerId": {
            "type": "string",
            "description": "ID of the player who generated the event",
        },
        "payload": {
            "type": "object",
            # "oneOf" is used to specify that a value must validate against exactly one of the provided schemas.
            "oneOf": [
                # To manage events related to PLAYER_JOIN
                {
                    "properties": {
                        "side": {"type": "string", "enum": ["LEFT", "RIGHT"]}
                    },
                    "required": ["side"],
                    "if": {"properties": {"eventType": {"const": "PLAYER_JOIN"}}},
                },
                # To manage events related to PADDLE_MOVE
                {
                    "properties": {
                        "direction": {"type": "string", "enum": ["UP", "DOWN", "NONE"]},
                        "paddleIndex": {
                            "type": "object",
                            "properties": {
                                "x": {"type": "number", "enum": [-1, 0, 1]},
                                "y": {"type": "number", "enum": [-1, 0, 1]},
                            },
                            "required": ["x", "y"],
                        },
                    },
                    "required": ["direction", "paddleIndex"],
                    "if": {"properties": {"eventType": {"const": "PADDLE_MOVE"}}},
                },
                # To manage events related to TIME_ELAPSED
                {
                    "properties": {
                        "dt": {"type": "number"},
                        "gameState": {
                            "type": "object",
                            "properties": {
                                "ball": {
                                    "type": "object",
                                    "properties": {
                                        "x": {"type": "number"},
                                        "y": {"type": "number"},
                                        "vx": {"type": "number"},
                                        "vy": {"type": "number"},
                                    },
                                    "required": ["x", "y", "vx", "vy"],
                                }
                            },
                            "required": ["ball"],
                        },
                    },
                    "required": ["dt", "gameState"],
                    "if": {"properties": {"eventType": {"const": "TIME_ELAPSED"}}},
                },
            ],
        },
    },
    "required": ["eventId", "eventType", "timestamp", "gameId", "playerId"],
}

EMPTY_EVENT = {
    "eventId": "",
    "eventType": "GAME_START",
    "timestamp": 0,
    "gameId": "",
    "playerId": "",
    "payload": {},
}


def validate_event(data: dict) -> bool:
    """Validate the event data against the schema."""
    try:
        validate(instance=data, schema=PONG_EVENT_SCHEMA)
        return True
    except ValidationError as e:
        # logger.error(f"Event validation error: {e}")
        raise e