import asyncio
import websockets
from typing import Tuple
from dpongpy.log import logger

class Server:
    def __init__(self, port: int, num_clients: int = 2):
        self.port = port
        self.num_clients = num_clients
        self.clients = set()  # Store client WebSocket connections
        self.message_queue = asyncio.Queue()
        self.server = None
        self.lobby_full_event = asyncio.Event()


    def is_lobby_full(self) -> bool:
        return len(self.clients) >= self.num_clients

    async def start(self):
        # Start the server and serve clients continuously without a loop
        self.server = await websockets.serve(self.handle_client, "localhost", self.port)
        print(f"Websocket listening on IP: localhost, Port: {self.port}")


    async def handle_client(self, websocket, path):
        self.clients.add(websocket)
        print(f"New client connected: {websocket.remote_address}")
        print(f"Waiting for {self.num_clients - len(self.clients)} more clients to join...")

        if self.is_lobby_full():
            self.lobby_full_event.set()
            print("\033[92mStarting game...\033[0m")

        try:
            await self.lobby_full_event.wait()
            async for message in websocket:
                await self.on_message(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            print(f"Client disconnected: {websocket.remote_address}")
        finally:
            self.clients.remove(websocket)
            if len(self.clients) < self.num_clients:
                self.lobby_full_event.clear()

    async def on_message(self, client_socket, message: str):
        await self.message_queue.put((client_socket, message))

    async def receive(self) -> Tuple[websockets.WebSocketServerProtocol, str]:
        try:
            # Try to get a message without waiting
            return self.message_queue.get_nowait()
        except asyncio.QueueEmpty:
            logger.debug("No messages in the queue, waiting for new message...")
            # Wait for the next message when the queue is empty
            return await self.message_queue.get()


    async def send(self, client_socket, payload: str):
        if client_socket in self.clients:
            await client_socket.send(payload)
        else:
            logger.debug(f"Client {client_socket.remote_address} not found in active clients")

    async def close(self):
        # Send shutdown message to all clients
        for client in self.clients:
            await client.send("_server_shutdown_")
            await client.close()
        if self.server:
            self.server.close()
            await self.server.wait_closed()

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
