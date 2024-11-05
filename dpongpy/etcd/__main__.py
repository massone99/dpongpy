import argparse
import json

import etcd3
import dpongpy
from dpongpy.etcd.schemas.lobby_schema import EMPTY_LOBBY, validate_lobby_data, LOBBY_KEY
from dpongpy.log import logger


# python -m dpongpy.etcd --host localhost --port 2379 --side left --keys arrows
# python -m dpongpy.etcd --side left --keys arrows


def arg_parser():
    ap = argparse.ArgumentParser()
    ap.prog = "python -m " + dpongpy.__name__
    mode = ap.add_argument_group("mode")
    mode.add_argument(
        "--num-players",
        "-n",
        type=int,
        default=2,
        help="Number of players in the game (only used in centralised mode)",
    )
    networking = ap.add_argument_group("networking")
    networking.add_argument(
        "--host",
        "-H",
        help="Etcd server host to connect to",
        type=str,
        default="localhost",
    )
    networking.add_argument(
        "--port", "-p", help="Port to connect to", type=int, default=2379
    )
    game = ap.add_argument_group("game")
    game.add_argument(
        "--side",
        "-s",
        choices=[dir.name.lower() for dir in dpongpy.model.Direction.values()],
        help="Side to play on",
        action="append",
        default=[],
        dest="sides",
    )
    game.add_argument(
        "--keys",
        "-k",
        choices=dpongpy.controller.ActionMap.all_mappings().keys(),
        help="Keymaps for sides",
        action="append",
        default=None,
    )
    game.add_argument("--debug", "-d", help="Enable debug mode", action="store_true")
    game.add_argument(
        "--size",
        "-S",
        help="Size of the game window",
        type=int,
        nargs=2,
        default=[900, 600],
    )
    game.add_argument("--fps", "-f", help="Frames per second", type=int, default=60)
    return ap


def args_to_settings(args):
    settings = dpongpy.EtcdSettings()
    settings.host = args.host
    settings.port = args.port
    settings.debug = args.debug
    settings.size = tuple(args.size)
    settings.num_players = args.num_players
    settings.fps = args.fps
    settings.initial_paddles = tuple(
        dpongpy.model.Direction[dir.upper()] for dir in args.sides
    )
    return settings


def retrieve_game_id() -> str:
    """
    Retrieve or create game ID from lobby data.
    Returns the game ID string.
    """
    client = etcd3.client(host="localhost", port=2379)
    lobby_data, metadata = client.get(LOBBY_KEY)
    try:
        if lobby_data:
            # Parse existing lobby data
            parsed_data = json.loads(lobby_data.decode("utf-8"))
            if validate_lobby_data(parsed_data):
                logger.info(f"Found valid lobby with game ID: {parsed_data['gameId']}")
                return parsed_data["gameId"]

        # Create new lobby if data invalid or missing
        logger.info("Creating new lobby with default game ID")
        client.put(LOBBY_KEY, json.dumps(EMPTY_LOBBY, indent=4))

        # Verify creation
        new_data = client.get(LOBBY_KEY)
        if not new_data:
            raise Exception(f"Failed to create LOBBY_KEY '{LOBBY_KEY}' in etcd")

        parsed_new_data = json.loads(new_data[0].decode("utf-8"))
        logger.info(f"Created new lobby with game ID: {parsed_new_data['gameId']}")
        return parsed_new_data["gameId"]

    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in lobby data, resetting to default")
        client.put(LOBBY_KEY, json.dumps(EMPTY_LOBBY, indent=4))
        return EMPTY_LOBBY["gameId"]
    except Exception as e:
        logger.error(f"Error retrieving game ID: {e}")
        raise


if __name__ == "__main__":
    parser = arg_parser()
    args = parser.parse_args()
    settings = args_to_settings(args)

    import dpongpy.remote.centralised

    game_id = retrieve_game_id()
    settings.game_id = game_id

    # Create the pong game
    dpongpy.remote.centralised.main_terminal(settings)
    exit(0)
