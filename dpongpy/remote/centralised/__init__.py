import threading

import pygame
from pygame.event import Event
import asyncio
from dpongpy import PongGame, Settings
from dpongpy.controller import ControlEvent
from dpongpy.model import *
from dpongpy.remote.presentation import deserialize, serialize
from dpongpy.log import logger
from dpongpy.remote.web_sockets.session import WebSocketSession

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 12345


def _run_event_loop_in_thread(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()


class PongCoordinator(PongGame):
    """
    A PongGame that acts as the central server/coordinator for the game.
    It:
        - Initializes a server to handle communication with terminals.
        - Manages the game state and broadcasts updates to all connected terminals.
        - Handles incoming messages from terminals in a separate thread.
    """

    def __init__(self, settings: Settings = None):
        settings = settings or Settings()
        settings.initial_paddles = []
        super().__init__(settings)
        self.pong.reset_ball((0, 0))
        self.communication_technology = settings.comm_technology
        if (
            self.communication_technology == "zmq"
            or self.communication_technology == "udp"
        ):
            self.prepare_server_udp_or_zmq()
        elif self.communication_technology == "web_sockets":
            self.prepare_server_web_sockets()
        else:
            raise ValueError(
                f"Invalid communication technology: {self.communication_technology}"
            )

    async def _handle_ingoing_messages_async(self):
        assert self.running, "Server is not running"
        while self.running:
            logger.debug(
                f"[{self.__class__.__name__}] Waiting for incoming messages..."
            )
            sender, message = await self.server.receive()
            logger.debug(
                f"[{self.__class__.__name__}] Received message from {sender}: {message}"
            )
            if sender is not None:
                self.add_peer(sender)
                message = deserialize(message)
                assert isinstance(
                    message, pygame.event.Event
                ), f"Expected {pygame.event.Event}, got {type(message)}"
                pygame.event.post(message)
            elif self.running:
                raise RuntimeError(
                    f"[{self.__class__.__name__}] Receive operation returned None"
                )

    def prepare_server_udp_or_zmq(self):
        from dpongpy.remote.zmq_tcp import Server as ZMQServer
        from dpongpy.remote.udp import Server as UDPServer

        self.server = (
            ZMQServer(self.settings.port or DEFAULT_PORT)
            if self.communication_technology == "zmq"
            else UDPServer(self.settings.port or DEFAULT_PORT)
        )

        self._event_loop_thread = threading.Thread(
            target=self.__handle_ingoing_messages, daemon=True
        )
        self._event_loop_thread.start()
        self._peers = set()
        self._lock = threading.RLock()

    def prepare_server_web_sockets(self):
        print(
            f"[{self.__class__.__name__}] Using WebSockets as the communication technology"
        )
        from dpongpy.remote.web_sockets.server import Server

        self.server = Server(self.settings.port or DEFAULT_PORT, num_clients=self.settings.num_players)

        # Create a new event loop for the WebSocket server
        self.event_loop = asyncio.new_event_loop()

        # Start the server in a new thread
        self._event_loop_thread = threading.Thread(
            target=_run_event_loop_in_thread, args=(self.event_loop,), daemon=True
        )
        self._event_loop_thread.start()

        self._peers = set()
        self._lock = threading.RLock()

        # Start the server asynchronously in the event loop
        asyncio.run_coroutine_threadsafe(self.server.start(), self.event_loop)

        # Start handling incoming messages asynchronously
        asyncio.run_coroutine_threadsafe(
            self._handle_ingoing_messages_async(), self.event_loop
        )

    def create_view(coordinator):
        from dpongpy.controller.local import ControlEvent
        from dpongpy.view import ShowNothingPongView

        class SendToPeersPongView(ShowNothingPongView):
            def render(self):
                event = coordinator.controller.create_event(
                    ControlEvent.TIME_ELAPSED, dt=coordinator.dt, status=self._pong
                )
                coordinator._broadcast_to_all_peers(event)

        return SendToPeersPongView(coordinator.pong)

    def create_controller(coordinator, paddle_commands):
        from dpongpy.controller.local import InputHandler, PongEventHandler

        class Controller(PongEventHandler, InputHandler):
            def __init__(self, pong: Pong):
                PongEventHandler.__init__(self, pong)

            def on_player_join(self, pong: Pong, paddle_index: int | Direction):
                super().on_player_join(pong, paddle_index)
                pong.reset_ball()

            def on_player_leave(self, pong: Pong, paddle_index: Direction):
                if pong.has_paddle(paddle_index):
                    pong.remove_paddle(paddle_index)
                if len(pong.paddles) == 0:
                    self.on_game_over(pong)
                else:
                    pong.reset_ball()

            def on_game_over(self, pong: Pong):
                event = self.create_event(ControlEvent.GAME_OVER)
                coordinator._broadcast_to_all_peers(event)
                coordinator.stop()

            def handle_inputs(self, dt=None):
                self.time_elapsed(dt)

        return Controller(coordinator.pong)

    def before_run(self):
        logger.info("Coordinator starting")
        super().before_run()

    def at_each_run(self):
        pass

    def after_run(self):
        self.server.close()
        logger.info("Coordinator stopped gracefully")
        super().after_run()

    # def before_run(self):
    #     pass

    @property
    def peers(self):
        with self._lock:
            return set(self._peers)

    @peers.setter
    def peers(self, value):
        with self._lock:
            self._peers = set(value)

    def add_peer(self, peer):
        with self._lock:
            self._peers.add(peer)

    def _broadcast_to_all_peers(self, message):
        event = serialize(message)
        for peer in self.peers:
            if self.settings.comm_technology == "web_sockets":
                loop = asyncio.get_event_loop()
                loop.run_until_complete(
                    self.server.send(client_socket=peer, payload=event)
                )
            else:
                self.server.send(peer, event)

    def __handle_ingoing_messages(self):
        try:
            max_retries = 3
            while self.running:
                message, sender = self.server.receive()
                if sender is not None:
                    self.add_peer(sender)
                    message = deserialize(message)
                    assert isinstance(
                        message, pygame.event.Event
                    ), f"Expected {pygame.event.Event}, got {type(message)}"
                    pygame.event.post(message)
                elif self.running:
                    logger.warn(
                        "Receive operation returned None: the server may have been closed ahead of time"
                    )
                    max_retries -= 1
                    if max_retries == 0:
                        break
        except Exception as e:
            self.running = False
            raise e


class PongTerminal(PongGame):
    """
    A PongGame that runs in terminal mode, i.e. it is controlled by the user.
    It:
    - Connects to the coordinator as a client.
    - Handles local player input and sends it to the coordinator.
    - Receives game state updates from the coordinator and updates the local game state.
    """

    def __init__(self, settings: Settings = None):
        settings = settings or Settings()
        assert (
            len(settings.initial_paddles) == 1
        ), "Only one paddle is allowed in terminal mode"
        super().__init__(settings)
        self.pong.reset_ball((0, 0))
        self.communication_technology = settings.comm_technology
        if self.communication_technology != "web_sockets":
            self.prepare_client_zmq_or_udp()
        else:
            self.prepare_client_web_sockets()

    async def _handle_ingoing_messages_async(self):
        assert self.running, "Client is not running"
        while self.running:
            message = await self.client.receive()
            if message is not None:
                message = deserialize(message)
                assert isinstance(
                    message, pygame.event.Event
                ), f"Expected {pygame.event.Event}, got {type(message)}"
                pygame.event.post(message)
            elif self.running:
                raise RuntimeError(
                    f"[{self.__class__.__name__}] Receive operation returned None"
                )

    def prepare_client_zmq_or_udp(self):
        from dpongpy.remote.zmq_tcp import Client as ZMQClient
        from dpongpy.remote.udp import Client as UDPClient

        if self.communication_technology == "zmq":
            client_class = ZMQClient
        else:
            client_class = UDPClient

        host = self.settings.host or DEFAULT_HOST
        port = self.settings.port or DEFAULT_PORT

        self.client = client_class((host, port))

        self._event_loop_thread = threading.Thread(
            target=self.__handle_ingoing_messages, daemon=True
        )
        self._event_loop_thread.start()
        self._peers = set()
        self._lock = threading.RLock()

    def prepare_client_web_sockets(self):
        logger.info(
            f"[{self.__class__.__name__}] Using WebSockets as the communication technology"
        )
        from dpongpy.remote.web_sockets.session import WebSocketSession

        self.client = WebSocketSession(
            (self.settings.host or DEFAULT_HOST, self.settings.port or DEFAULT_PORT)
        )

        print("Connecting to server at", self.settings.host, self.settings.port)

        self.event_loop = asyncio.new_event_loop()

        self.event_loop.run_until_complete(self.client.connect())

        self._event_loop_thread = threading.Thread(
            target=_run_event_loop_in_thread, args=(self.event_loop,), daemon=True
        )

        self._event_loop_thread.start()
        self._peers = set()
        self._lock = threading.RLock()

        asyncio.run_coroutine_threadsafe(
            self._handle_ingoing_messages_async(), loop=self.event_loop
        )

    def create_controller(terminal, paddle_commands=None):
        from dpongpy.controller.local import EventHandler, PongInputHandler

        class Controller(PongInputHandler, EventHandler):
            def __init__(self, pong: Pong, paddle_commands):
                PongInputHandler.__init__(self, pong, paddle_commands)

            def post_event(self, event: Event | ControlEvent, **kwargs):
                event = super().post_event(event, **kwargs)
                if not ControlEvent.TIME_ELAPSED.matches(event):
                    if isinstance(terminal.client, WebSocketSession):
                        assert terminal.client.websocket.open, "Websocket is not open"

                        loop = asyncio.get_event_loop()
                        # Execute event on the event loop in a blocking way
                        loop.run_until_complete(terminal.client.send(serialize(event)))
                    else:
                        terminal.client.send(serialize(event))
                return event

            def handle_inputs(self, dt=None):
                return super().handle_inputs(dt)

            def on_time_elapsed(self, pong: Pong, dt: float, status: Pong = None):
                if status is None or pong is status:
                    pong.update(dt)
                else:
                    pong.override(status)

            def on_paddle_move(
                self, pong: Pong, paddle_index: int | Direction, direction: Direction
            ):
                pong.move_paddle(paddle_index, direction)

            def on_game_over(self, pong: Pong):
                terminal.stop()

        return Controller(terminal.pong, paddle_commands)

    def __handle_ingoing_messages(self):
        try:
            max_retries = 3
            while self.running:
                message = self.client.receive()
                if message is not None:
                    message = deserialize(message)
                    assert isinstance(
                        message, pygame.event.Event
                    ), f"Expected {pygame.event.Event}, got {type(message)}"
                    pygame.event.post(message)
                elif self.running:
                    logger.warn(
                        "Receive operation returned None: the client may have been closed ahead of time"
                    )
                    max_retries -= 1
                    if max_retries == 0:
                        break
        except Exception as e:
            self.running = False
            raise e

    def before_run(self):
        logger.info("Terminal starting")
        super().before_run()
        self.controller.post_event(
            ControlEvent.PLAYER_JOIN, paddle_index=self.pong.paddles[0].side
        )

    def after_run(self):
        self.client.close()
        logger.info("Terminal stopped gracefully")
        super().after_run()


def main_coordinator(settings=None):
    PongCoordinator(settings).run()


def main_terminal(settings=None):
    PongTerminal(settings).run()
