import asyncio
import json

from dpongpy.remote.web_sockets.session import WebSocketSession


if __name__ == "__main__":
    
    async def main():
        from dpongpy.remote.lobby.lobby_client import LobbyManagerClient

        client = LobbyManagerClient()
        response = client.join_lobby("user1")
        if response:
            # session = WebSocketSession((response.lobby.address, response.lobby.port))
            # await session.connect()
            print("Got response:", response)
            
            
    asyncio.run(main())
    