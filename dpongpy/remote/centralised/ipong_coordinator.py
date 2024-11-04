import threading
from dpongpy import PongGame, DistributedSettings
from dpongpy.controller import ControlEvent
from dpongpy.log import Loggable
from dpongpy.model import Direction, Pong
from dpongpy.remote.presentation import deserialize, serialize
from dpongpy.view import PongView
from dpongpy.log import logger
import pygame

class IRemotePongCoordinator(PongGame, Loggable):
    """
    This is the base class for all remote Pong coordinators.

    Methods that need to be implemented:
        - initialize(): 
            This method should implement the specific initialization
            linked to each technology (e.g. UDP, ZMQ, WebSockets).
        - start_server(): 
            This method should start the server for the chosen communication technology.
        - broadcast_to_all_peers(message): 
            This method should broadcast a message to all connected peers.
        - __handle_ingoing_messages(): 
            This method should handle incoming messages from peers.
        - _broadcast_to_all_peers(message): 
            This method should broadcast a message to all connected peers.
    """

    def __init__(self, settings: DistributedSettings = None):
        settings = settings or DistributedSettings()
        settings.initial_paddles = []
        PongGame.__init__(
            self, settings
        )  # cambia il modo in cui si chiama il super costruttore nel l'ereditarietà multipla
        self.pong.reset_ball((0, 0))
        self.communication_technology = settings.comm_technology
        self.initialize()

    def initialize(self):
        """
        This method should implement the specific initialization
        linked to each technology (e.g. UDP, ZMQ, WebSockets).
        """
        raise NotImplementedError("Must be implemented by subclasses")

    def start_server(self):
        raise NotImplementedError("Must be implemented by subclasses")

    def broadcast_to_all_peers(self, message):
        raise NotImplementedError("Must be implemented by subclasses")

    
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

    def handle_ingoing_messages(self):
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

    def before_run(self):
        logger.info("Coordinator starting")
        super().before_run()

    def at_each_run(self):
        pass

    def after_run(self):
        self.server.close()
        print("\033[32mCoordinator stopped gracefully\033[0m")
        super().after_run()

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
        """
        Default implementation. Suitable for sychronous communication like ZMQ or UDP.
        Not compatible with WebSockets implementation
        """
        event = serialize(message)
        for peer in self.peers:
            self.server.send(peer, event)

class SyncPongCoordinator(IRemotePongCoordinator):
    def __init__(self, settings: DistributedSettings = None):
        super().__init__(settings)
        self.receiving_thread = threading.Thread(
            target=self.handle_ingoing_messages, daemon=True
        )
        self.receiving_thread.start()
        self._peers = set()
        self._lock = threading.RLock()