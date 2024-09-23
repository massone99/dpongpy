import threading
import time
import uuid
import dpongpy.model
import dpongpy.controller
import argparse

from dpongpy.remote.lobby.lobby_server import LobbyServer


def run_lobby_server(host: str, api_port: int, ws_port: int):
    """
    Runs the LobbyServer in a separate thread.

    :param host: Host address to bind the server.
    :param port: Port number to bind the server.
    """
    server = LobbyServer(host=host, api_port=api_port, ws_port=ws_port)
    server.run()


def arg_parser():
    ap = argparse.ArgumentParser()
    ap.prog = "python -m " + dpongpy.__name__
    # ap.add_argument("--help", action="store_true", help="Show this help message and exit")
    mode = ap.add_argument_group("mode")
    mode.add_argument(
        "--mode",
        "-m",
        choices=["local", "centralised"],
        help="Run the game in local or centralised mode",
    )
    mode.add_argument(
        "--comm-type",
        "-c",
        choices=["udp", "zmq", "web_sockets"],
        # FIXME: remove
        default="web_sockets",
        required=False,
        help="Specify the communication type (UDP or ZeroMQ) for centralised mode",
    )
    mode.add_argument(
        "--role",
        "-r",
        required=False,
        choices=["coordinator", "terminal"],
        help="Run the game with a central coordinator, in either coordinator or terminal role",
    )
    networking = ap.add_argument_group("networking")
    networking.add_argument(
        "--host", "-H", help="Host to connect to", type=str, default="localhost"
    )
    networking.add_argument(
        "--port", "-p", help="Port to connect to", type=int, default=None
    )
    # Arguments added to manage the lobby via REST API before the game starts
    networking.add_argument(
        "--api-url",
        type=str,
        default="http://localhost",
        help="URL of the lobby management API",
    )
    networking.add_argument(
        "--api-port",
        type=int,
        default=8000,
        help="Port of the lobby management API",
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
    settings = dpongpy.Settings()
    settings.host = args.host
    settings.port = args.port
    settings.debug = args.debug
    settings.size = tuple(args.size)
    settings.fps = args.fps
    if args.keys is None:
        args.keys = list(dpongpy.controller.ActionMap.all_mappings().keys())[
            : len(args.sides)
        ]
    assert len(args.sides) == len(args.keys), "Number of sides and keymaps must match"
    settings.initial_paddles = {
        dpongpy.model.Direction[
            direction.upper()
        ]: dpongpy.controller.ActionMap.all_mappings()[keymap]
        for direction, keymap in zip(args.sides, args.keys)
    }
    return settings


parser = arg_parser()
args = parser.parse_args()
settings = args_to_settings(args)
# if args.help:
#     parser.print_help()
#     exit(0)
if args.mode == "local":
    if not settings.initial_paddles:
        settings.initial_paddles = (
            dpongpy.model.Direction.LEFT,
            dpongpy.model.Direction.RIGHT,
        )
    dpongpy.main(settings)
    exit(0)
if args.mode == "centralised":
    import dpongpy.remote.centralised

    # The coordinators models also the entity which manages the REST API
    # for managing the lobby, so it must be started without any precondition
    if args.role == "coordinator":
        # Check if the comm_type is web_sockets
        if args.comm_type == "web_sockets":
            # Start the server to manage the REST API
            api_server_thread = threading.Thread(
                target=run_lobby_server,
                args=(args.host, args.api_port, args.port),
                daemon=True,
            )
            api_server_thread.start()

            print("Starting web_sockets coordinator")

            dpongpy.remote.centralised.main_coordinator(settings)
            exit(0)
        else:
            dpongpy.remote.centralised.main_coordinator(settings)
            exit(0)
    if args.role == "terminal":
        # The PongTerminal on the other side can be created only if the lobby is full, to avoid the graphic rendering
        # of the game UI
        if args.comm_type == "web_sockets":
            # Prompt the server to join the lobby using the REST API
            print("Starting lobby management for client")

            from dpongpy.remote.lobby.lobby_client import LobbyManagerClient

            lobby_manager = LobbyManagerClient(
                base_url=args.api_url, api_port=args.api_port
            )
            print("Lobby API url: ", args.api_url)

            client_name = f"client_{uuid.uuid4().hex[:8]}_{int(time.time())}"
            print(f"Generated client name: {client_name}")

            print("Connecting to lobby...")
            response = lobby_manager.join_lobby(client_name)

            # Retrieve the websocket information from the response
            if response.lobby:
                settings.host = response.lobby.address
                settings.port = response.lobby.port
            else:
                raise ValueError("No lobby found")

            dpongpy.remote.centralised.main_terminal(settings)
            exit(0)
        else:
            print("NO WEB SOCKETS")

            dpongpy.remote.centralised.main_terminal(settings)
            exit(0)
    print(f"Invalid role: {args.role}. Must be either 'coordinator' or 'terminal'")

parser.print_help()
exit(1)
