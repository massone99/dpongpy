import threading

import pygame
from pygame.event import Event

from dpongpy import PongGame, Settings
from dpongpy.controller import ControlEvent
from dpongpy.log import logger
from dpongpy.model import *
from dpongpy.remote.presentation import deserialize, serialize
from dpongpy.remote.zmq_tcp import Server, Client

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 12345


class PongCoordinator(PongGame):
    '''
    A PongGame that acts as the central server/coordinator for the game.
    It:
        - Initializes a server to handle communication with terminals.
        - Manages the game state and broadcasts updates to all connected terminals.
        - Handles incoming messages from terminals in a separate thread.
    '''

    def __init__(self, settings: Settings = None):
        settings = settings or Settings()
        settings.initial_paddles = []
        super().__init__(settings)
        self.pong.reset_ball((0, 0))
        # TODO: this is where the usage of ZeroMQ should be introduced
        # since the Server implementation is where UDP is used
        print("self.settings.port or DEFAULT_PORT: ", self.settings.port or DEFAULT_PORT)
        self.server = Server(self.settings.port or DEFAULT_PORT)
        self._thread_receiver = threading.Thread(target=self.__handle_ingoing_messages, daemon=True)
        self._thread_receiver.start()
        self._peers = set()
        self._lock = threading.RLock()

    def create_view(coordinator):
        from dpongpy.controller.local import ControlEvent
        from dpongpy.view import ShowNothingPongView

        class SendToPeersPongView(ShowNothingPongView):
            def render(self):
                event = coordinator.controller.create_event(ControlEvent.TIME_ELAPSED, dt=coordinator.dt, status=self._pong)
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
            self.server.send(peer, event)

    def __handle_ingoing_messages(self):
        try:
            max_retries = 3
            while self.running:
                message, sender = self.server.receive()
                print("Message received by coordinator: ", message)
                if sender is not None:
                    self.add_peer(sender)
                    print(f"Added peer: {sender}")
                    message = deserialize(message)
                    assert isinstance(message, pygame.event.Event), f"Expected {pygame.event.Event}, got {type(message)}"
                    pygame.event.post(message)
                elif self.running:
                    logger.warn("Receive operation returned None: the server may have been closed ahead of time")
                    max_retries -= 1
                    if max_retries == 0: break
        except Exception as e:
            self.running = False
            raise e


class PongTerminal(PongGame):
    '''
    A PongGame that runs in terminal mode, i.e. it is controlled by the user.
    It:
    - Connects to the coordinator as a client.
    - Handles local player input and sends it to the coordinator.
    - Receives game state updates from the coordinator and updates the local game state.
    '''

    def __init__(self, settings: Settings = None):
        settings = settings or Settings()
        assert len(settings.initial_paddles) == 1, "Only one paddle is allowed in terminal mode"
        super().__init__(settings)
        self.pong.reset_ball((0, 0))
        self.client = Client((self.settings.host or DEFAULT_HOST, self.settings.port or DEFAULT_PORT))
        self._thread_receiver = threading.Thread(target=self.__handle_ingoing_messages, daemon=True)
        self._thread_receiver.start()

    def create_controller(terminal, paddle_commands = None):
        from dpongpy.controller.local import EventHandler, PongInputHandler

        class Controller(PongInputHandler, EventHandler):
            def __init__(self, pong: Pong, paddle_commands):
                PongInputHandler.__init__(self, pong, paddle_commands)

            def post_event(self, event: Event | ControlEvent, **kwargs):
                event = super().post_event(event, **kwargs)
                if not ControlEvent.TIME_ELAPSED.matches(event):
                    terminal.client.send(serialize(event))
                return event

            def handle_inputs(self, dt=None):
                return super().handle_inputs(dt)

            def on_time_elapsed(self, pong: Pong, dt: float, status: Pong = None):
                if status is None or pong is status:
                    pong.update(dt)
                else:
                    pong.override(status)

            def on_paddle_move(self, pong: Pong, paddle_index: int | Direction, direction: Direction):
                pong.move_paddle(paddle_index, direction)

            def on_game_over(self, pong: Pong):
                terminal.stop()

        return Controller(terminal.pong, paddle_commands)

    def __handle_ingoing_messages(self):
        try:
            max_retries = 3
            while self.running:
                message = self.client.receive()
                print("Msg received by terminal: ", message)
                if message is not None:
                    message = deserialize(message)
                    assert isinstance(message, pygame.event.Event), f"Expected {pygame.event.Event}, got {type(message)}"
                    pygame.event.post(message)
                elif self.running:
                    logger.warn("Receive operation returned None: the client may have been closed ahead of time")
                    max_retries -= 1
                    if max_retries == 0: break
        except Exception as e:
            self.running = False
            raise e

    def before_run(self):
        logger.info("Terminal starting")
        super().before_run()
        print("Joining the game")
        self.controller.post_event(ControlEvent.PLAYER_JOIN, paddle_index=self.pong.paddles[0].side)

    def after_run(self):
        self.client.close()
        logger.info("Terminal stopped gracefully")
        super().after_run()


def main_coordinator(settings = None):
    PongCoordinator(settings).run()

def main_terminal(settings = None):
    PongTerminal(settings).run()
