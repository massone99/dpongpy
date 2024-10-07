# Import required modules
import threading
from dpongpy.remote.presentation import deserialize
from dpongpy.remote.centralised.pong_coordinator_interface import (
    DEFAULT_PORT,
    IRemotePongCoordinator,
)
from dpongpy.log import logger
import pygame


class ZmqPongCoordinator(IRemotePongCoordinator):
    def initialize(self):
        print(f"[{self.__class__.__name__}] Using ZMQ as the communication technology")
        from dpongpy.remote.comm.zmq.zmq_server import Server as ZMQServer

        self.server = ZMQServer(self.settings.port or DEFAULT_PORT)

        self.receiving_thread = threading.Thread(
            target=self.__handle_ingoing_messages, daemon=True
        )
        self.receiving_thread.start()
        self._peers = set()
        self._lock = threading.RLock()


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
