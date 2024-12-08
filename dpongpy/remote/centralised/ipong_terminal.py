import threading
import time
import uuid

import pygame
from pygame.event import Event

from dpongpy import PongGame, DistributedSettings
from dpongpy.controller import ControlEvent
from dpongpy.log import Loggable
from dpongpy.model import *
from dpongpy.remote.centralised import DEFAULT_HOST, DEFAULT_PORT
from dpongpy.remote.presentation import deserialize, serialize


class IRemotePongTerminal(PongGame, Loggable):
    """
    A terminal interface for a remote Pong game,
    which allows interaction through network communication protocols such as WebSockets, ZMQ, or UDP.

    Methods that must be overrriden:
    - __handle_ingoing_messages() -> None

        This method is responsible for handling incoming messages from the server.
        The default implementation is suitable only for communication protocols like ZMQ or UDP.

    Methods that must be implemented by subclasses:

    - initialize() -> None

        This method is responsible for initializing the remote Pong terminal and setting up any necessary configurations or connections to a server over the specified network protocol (WebSockets, ZMQ, etc.).

    - send_event(event: Event) -> None

        This method is used to transmit events from the local client (terminal) to a remote server or another client.
        Default implementation works for ZMQ and UDP. Websockets MUST override this method.
    """

    def __init__(self, settings: DistributedSettings = None):
        self.settings = settings or DistributedSettings()
        super().__init__(self.settings)
        assert (
            len(self.settings.initial_paddles) == 1
        ), "Only one paddle is allowed in terminal mode"
        super().__init__(self.settings)
        self.pong.reset_ball((0, 0))
        self.communication_technology = self.settings.comm_technology

        self.initialize()

    def initialize(self):
        raise NotImplementedError("Must be implemented by subclasses")

    def handle_ingoing_messages(self):
        self.__handle_ingoing_messages()

    def send_event(self, event):
        if isinstance(self, WebSocketPongTerminal):
            raise NotImplementedError(
                "WebSocketPongTerminal requires a different implementation of send_event"
            )
        self.client.send(serialize(event))

    def create_controller(terminal, paddle_commands=None):
        from dpongpy.controller.local import EventHandler, PongInputHandler

        class Controller(PongInputHandler, EventHandler):
            def __init__(self, pong: Pong, paddle_commands):
                PongInputHandler.__init__(self, pong, paddle_commands)

            def post_event(self, event: Event | ControlEvent, **kwargs):
                event = super().post_event(event, **kwargs)
                if not ControlEvent.TIME_ELAPSED.matches(event):
                    terminal.send_event(event)
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


class ThreadedPongTerminal(IRemotePongTerminal):
    def initialize(self, client_class):
        host = self.settings.host or DEFAULT_HOST
        port = self.settings.port or DEFAULT_PORT

        self.client = client_class((host, port))

        self.receiving_thread = threading.Thread(
            target=super().handle_ingoing_messages, daemon=True
        )
        self.receiving_thread.start()
        self._peers = set()
        self._lock = threading.RLock()

    def send_event(self, event):
        self.client.send(serialize(event))
