from jsonschema import validate, ValidationError

from dpongpy.log import logger

PONG_LOBBY_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Distributed Pong Game Schema",
    "type": "object",
    "properties": {
        "gameId": {
            "type": "string",
            "description": "Unique identifier for the game instance.",
        },
        "players": {
            "type": "array",
            "minItems": 2,
            "maxItems": 2,
            "items": {
                "type": "object",
                "properties": {
                    "playerId": {
                        "type": "string",
                        "description": "Unique identifier for the player.",
                    },
                    "x": {
                        "type": "number",
                        "description": "Horizontal position of the player's paddle.",
                    },
                    "y": {
                        "type": "number",
                        "description": "Vertical position of the player's paddle.",
                    },
                },
                "required": ["playerId", "x", "y"],
            },
            "description": "Array containing two player objects.",
        },
        "ball": {
            "type": "object",
            "properties": {
                "position": {
                    "type": "object",
                    "properties": {
                        "x": {
                            "type": "number",
                            "description": "Normalized horizontal position of the ball (0 = left, 1 = right).",
                        },
                        "y": {
                            "type": "number",
                            "description": "Normalized vertical position of the ball (0 = top, 1 = bottom).",
                        },
                    },
                    "required": ["x", "y"],
                },
                "velocity": {
                    "type": "object",
                    "properties": {
                        "x": {
                            "type": "number",
                            "description": "Horizontal velocity component of the ball.",
                        },
                        "y": {
                            "type": "number",
                            "description": "Vertical velocity component of the ball.",
                        },
                    },
                    "required": ["x", "y"],
                },
            },
            "required": ["position", "velocity"],
            "description": "Object representing the ball's state.",
        },
        "gameState": {
            "type": "string",
            "enum": ["waiting", "playing", "paused", "ended"],
            "description": "Current state of the game.",
        },
        "approved": {
            "type": "boolean",
            "description": "Whether the state has been evaluated by the leader.",
            "default": False
        },
    },
    "required": ["gameId", "players", "ball", "gameState"],
}

EMPTY_LOBBY = {
    "gameId": "default-game",
    "players": [
        {"playerId": "", "x": 0, "y": 0},
        {"playerId": "", "x": 0, "y": 0},
    ],
    "ball": {"position": {"x": 0, "y": 0}, "velocity": {"x": 0, "y": 0}},
    "gameState": "waiting",
    "approved": False
}


def validate_lobby_data(data: dict) -> bool:
    """Validate the lobby data against the schema."""
    try:
        validate(instance=data, schema=PONG_LOBBY_SCHEMA)
        return True
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        return False
