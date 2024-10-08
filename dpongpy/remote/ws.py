import threading
from dpongpy.controller import ControlEvent
from dpongpy.remote.centralised import (
    DEFAULT_HOST,
    DEFAULT_PORT,
)
from dpongpy.remote.centralised.ipong_coordinator import IRemotePongCoordinator
from dpongpy.remote.centralised.ipong_terminal import IRemotePongTerminal
from dpongpy.remote.presentation import deserialize, serialize
import asyncio
from dpongpy.log import logger
import pygame
from dpongpy.remote.comm.web_sockets.ws_server import Server


def _run_event_loop_in_thread(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()


class WebSocketPongCoordinator(IRemotePongCoordinator):
    def initialize(self):
        self.log("Using WebSockets as the communication technology")

        self.server = Server(
            self.settings.port or DEFAULT_PORT, num_clients=self.settings.num_players
        )

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
                self.error(
                    "Receive operation returned None: the server may have been closed ahead of time"
                )
                raise RuntimeError("Receive operation returned None")

    def _broadcast_to_all_peers(self, message):
        event = serialize(message)
        for peer in self.peers:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.server.send(client_socket=peer, payload=event))

    def create_event(self, event_type: ControlEvent, dt=None, status=None):
        return ControlEvent(event_type, dt, status, self._pong)

    async def stop(self):
        logger.info("Stopping WebSocket coordinator")
        self.running = False
        await asyncio.gather(
            self._server.close(),
            asyncio.sleep(1),  # wait for the server to close properly
        )


class WebSocketPongTerminal(IRemotePongTerminal):

    def initialize(self):
        self.log("Using WebSockets as the communication technology")
        from dpongpy.remote.comm.web_sockets.ws_client import WebSocketSession

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

    def send_event(self, event):
        loop = asyncio.get_event_loop()
        # Execute event on the event loop in a blocking way
        loop.run_until_complete(self.client.send(serialize(event)))

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
                self.error(
                    "Receive operation returned None: the client may have been closed ahead of time"
                )
                raise RuntimeError("Receive operation returned None")
