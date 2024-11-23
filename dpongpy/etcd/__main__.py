import argparse
import json
import os
import time

import backoff
import etcd3

import dpongpy
from dpongpy.etcd.schemas.lobby_schema import (
    validate_lobby_data,
    LOBBY_KEY,
    create_empty_lobby,
)
from dpongpy.log import logger


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
    networking = ap.add_argument_group("networking")
    networking.add_argument(
        "--host",
        help="etcd host",
        default="etcd",
    )
    networking.add_argument(
        "--port",
        help="etcd port",
        type=int,
        default=2379,
    )

    return ap


def args_to_settings(args):
    game_settings = dpongpy.EtcdSettings()

    # Set etcd host and port
    etcd_host = args.host or os.environ.get('ETCD_HOST')
    etcd_port = args.port or os.environ.get('ETCD_PORT')

    if not etcd_host or not etcd_port:
        raise ValueError("ETCD_HOST and ETCD_PORT environment variables must be set")

    game_settings.etcd_host = etcd_host
    game_settings.etcd_port = int(etcd_port)
    game_settings.debug = args.debug
    game_settings.size = tuple(args.size)
    game_settings.num_players = args.num_players
    game_settings.fps = args.fps
    game_settings.initial_paddles = tuple(
        dpongpy.model.Direction[dir.upper()] for dir in args.sides
    )
    return game_settings


@backoff.on_exception(backoff.expo,
                      etcd3.exceptions.ConnectionFailedError,
                      max_tries=5)
def retrieve_game_id(game_settings: dpongpy.EtcdSettings) -> str:
    logger.info(f"\033[91mRetrieving game ID from etcd at {game_settings.etcd_host}:{game_settings.etcd_port}\033[0m")
    client = etcd3.client(host=game_settings.etcd_host, port=game_settings.etcd_port)

    # Add a small delay to ensure etcd is ready
    time.sleep(5)

    lobby_data, metadata = client.get(LOBBY_KEY)
    try:
        if lobby_data:
            parsed_data = json.loads(lobby_data.decode("utf-8"))
            if validate_lobby_data(parsed_data):
                logger.info(f"Found valid lobby with game ID: {parsed_data['gameId']}")
                return parsed_data["gameId"]

        # Create new lobby with settings-based positions
        logger.info("Creating new lobby with default game ID")
        empty_lobby = create_empty_lobby(size=game_settings.size)  # Use settings size
        client.put(LOBBY_KEY, json.dumps(empty_lobby, indent=4))

        # Verify creation
        new_data = client.get(LOBBY_KEY)
        if not new_data:
            raise Exception(f"Failed to create LOBBY_KEY '{LOBBY_KEY}' in etcd")

        parsed_new_data = json.loads(new_data[0].decode("utf-8"))
        logger.info(f"Created new lobby with game ID: {parsed_new_data['gameId']}")
        return parsed_new_data["gameId"]

    except json.JSONDecodeError:
        logger.error("Invalid JSON in lobby data, resetting to default")
        empty_lobby = create_empty_lobby(size=game_settings.size)  # Use settings size
        client.put(LOBBY_KEY, json.dumps(empty_lobby, indent=4))
        return empty_lobby["gameId"]
    except Exception as e:
        logger.error(f"Error retrieving game ID: {e}")
        raise


if __name__ == "__main__":
    parser = arg_parser()
    args = parser.parse_args()
    settings = args_to_settings(args)

    import dpongpy.remote.centralised

    game_id = retrieve_game_id(settings)
    settings.game_id = game_id

    # Create the pong game
    dpongpy.remote.centralised.main_terminal(settings)
    exit(0)
