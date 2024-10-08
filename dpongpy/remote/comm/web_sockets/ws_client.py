import websockets
from dpongpy.remote import Address
from dpongpy.log import logger
from dpongpy.log import Loggable


class WebSocketSession(Loggable):
    def __init__(self, remote_address: Address):
        self.websocket = None
        self.remote_address = remote_address

        self.uri = f"ws://{remote_address[0]}:{remote_address[1]}"

    async def connect(self):
        self.websocket = await websockets.connect(self.uri)
        self.log(f"Connected to {self.remote_address}")

    async def send(self, payload: str) -> int:
        await self.websocket.send(payload)
        self.log(f"Sent: {payload}")
        return len(payload)

    async def receive(self) -> str | bytes:
        return await self.websocket.recv()

    async def close(self):
        await self.websocket.close()

    async def __aenter__(self):
        await self.connect()  # Connect when entering the context
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.log(f"Closing connection with {self.remote_address}")
        await self.close()
