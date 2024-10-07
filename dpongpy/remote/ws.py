import threading
from dpongpy.controller import ControlEvent
from dpongpy.remote.centralised.pong_coordinator_interface import (
    DEFAULT_PORT,
    IRemotePongCoordinator,
)
from dpongpy.remote.presentation import deserialize, serialize
import asyncio
from dpongpy.log import logger
from dpongpy.remote.web_sockets.server import Server
import pygame


class WebSocketPongCoordinator(IRemotePongCoordinator):
    def _run_event_loop_in_thread(self, loop):
        asyncio.set_event_loop(loop)
        loop.run_forever()

    def initialize(self):
        print(
            f"[{self.__class__.__name__}] Using WebSockets as the communication technology"
        )
        from dpongpy.remote.web_sockets.server import Server

        self.server = Server(
            self.settings.port or DEFAULT_PORT, num_clients=self.settings.num_players
        )

        # Create a new event loop for the WebSocket server
        self.event_loop = asyncio.new_event_loop()

        # Start the server in a new thread
        self._event_loop_thread = threading.Thread(
            target=self._run_event_loop_in_thread, args=(self.event_loop,), daemon=True
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

    async def start(self):
        logger.info("Starting WebSocket coordinator")
        self._server = Server(self.settings.port or DEFAULT_PORT)
        await self._server.start()
        asyncio.create_task(self._handle_ingoing_messages_async())
        await self._event_loop.wait()

    async def _handle_ingoing_messages_async(self):
        assert self.running, "Server is not running"
        while self.running:
            sender, message = await self.server.receive()
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

    def _broadcast_to_all_peers(self, message):
        event = serialize(message)
        for peer in self.peers:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(
                self.server.send(client_socket=peer, payload=event)
            )

    def create_event(self, event_type: ControlEvent, dt=None, status=None):
        return ControlEvent(event_type, dt, status, self._pong)

    async def stop(self):
        logger.info("Stopping WebSocket coordinator")
        self.running = False
        await asyncio.gather(
            self._server.close(),
            asyncio.sleep(1),  # wait for the server to close properly
        )
