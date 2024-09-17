import asyncio
import websockets
from typing import Tuple
from dpongpy.remote import Address
from dpongpy.log import logger


class WebSocketSession:
    def __init__(self, remote_address: Address):
        self.websocket = None
        self.remote_address = remote_address

        self.uri = f"ws://{remote_address[0]}:{remote_address[1]}"

    async def connect(self):
        self.websocket = await websockets.connect(self.uri)
        logger.debug(f"[{self.__class__.__name__}] Connected to {self.remote_address}")

    async def send(self, payload: str) -> int:
        await self.websocket.send(payload)
        logger.debug(f"[{self.__class__.__name__}] Sent: {payload}")
        return len(payload)

    async def receive(self) -> str | bytes:
        return await self.websocket.recv()

    async def close(self):
        await self.websocket.close()

    async def __aenter__(self):
        await self.connect()  # Connect when entering the context
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        logger.debug(
            f"[{self.__class__.__name__}] Closing connection with {self.remote_address}"
        )
        await self.close()


if __name__ == "__main__":

    async def run_client():
        session = WebSocketSession(("localhost", 1234))

        try:
            # Manually connect
            await session.connect()
            print("Connected to server")

            # Send exactly 5 simple messages
            for i in range(5):
                message = f"Simple message {i + 1}"
                await session.send(message)
                print(f"Sent: {message}")

                # Optionally, await a response if necessary
                try:
                    response = await asyncio.wait_for(
                        session.receive(), timeout=1
                    )  # Optional timeout
                    print(f"Received from server: {response}")
                except asyncio.TimeoutError:
                    print("No response from server, continuing to next message.")

                await asyncio.sleep(0.5)  # Small delay between sending messages
        except websockets.exceptions.ConnectionClosed as e:
            print(f"Connection closed: {e}")
        finally:
            # Ensure the connection is closed
            await session.close()
            print("Connection closed")

    asyncio.run(run_client())
