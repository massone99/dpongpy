from jsonschema import validate, ValidationError

from dpongpy.log import logger

LOBBY_KEY = "pong_lobby"

PONG_LOBBY_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Distributed Pong Lobby Data Schema",
    "type": "object",
    "properties": {
        "gameId": {
            "type": "string",
            "description": "Unique identifier for the game instance.",
        },
        "players": {
            "type": "array",
            "minItems": 0,  # Allow for an empty list of players
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
                    "direction": {
                        "type": "string",
                        "enum": ["NONE", "LEFT", "UP", "RIGHT", "DOWN"],
                        "description": "Current direction of the player's paddle.",
                    },
                },
                "required": ["playerId", "x", "y", "direction"],
            },
            "description": "Array containing zero to two player objects.",
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
            "default": False,
        },
    },
    "required": ["gameId", "players", "ball", "gameState"],
}


def create_empty_lobby(size=(800, 600), padding_ratio=0.05):
    """Creates an empty lobby with properly positioned paddles and ball"""
    width, height = size
    padding = width * padding_ratio  # 5% of width for padding

    return {
        "gameId": "default-game",
        "players": [],  # No players initially
        # Ball - positioned at center
        "ball": {
            "position": {
                "x": width / 2,
                "y": height / 2
            },
            "velocity": {"x": 0, "y": 0}
        },
        "gameState": "waiting",
        "approved": False
    }


EMPTY_LOBBY = create_empty_lobby()


def validate_lobby_data(data: dict) -> bool:
    """Validate the lobby data against the schema."""
    try:
        validate(instance=data, schema=PONG_LOBBY_SCHEMA)
        return True
    except ValidationError as e:
        return False
