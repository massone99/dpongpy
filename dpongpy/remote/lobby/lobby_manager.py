from typing import List, Optional
import uuid
from asyncio import Lock


class Lobby:
    def __init__(
        self,
        name: str,
        max_players: int = 2,
        address: str = "127.0.0.1",
        port: int = 12345,
    ):
        self.id = str(uuid.uuid4())
        self.name = name
        self.max_players = max_players
        self.players: List[str] = []  # List of player IDs or names
        self.address = address  # WebSocket server address
        self.port = port  # WebSocket server port
        self.lock = Lock()

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "max_players": self.max_players,
            "current_players": len(self.players),
            "players": self.players,
            "address": self.address,
            "port": self.port,
        }
        
    def is_full(self):
        return len(self.players) >= self.max_players


class LobbyManager:
    def __init__(self, address: str = "127.0.0.1", port: int = 8000):
        self.lobby: Optional[Lobby] = None
        self.lock = Lock()
        self.address = address
        self.port = port

    async def create_lobby(self, name: str, max_players: int = 2) -> Lobby:
        async with self.lock:
            if self.lobby is not None:
                raise Exception("A lobby is already active.")
            lobby = Lobby(name, max_players, self.address, self.port)
            self.lobby = lobby
            return lobby

    async def get_lobby(self) -> Optional[Lobby]:
        async with self.lock:
            return self.lobby

    async def join_lobby(self, player: str) -> bool:
        print(f"Attempting to join lobby with player: {player}")
        async with self.lock:
            if self.lobby is None:
                print("Join failed: No lobby exists")
                return False
            async with self.lobby.lock:
                print(f"Current players in lobby: {self.lobby.players}")
                print(f"Max players allowed: {self.lobby.max_players}")
                if len(self.lobby.players) >= self.lobby.max_players:
                    print("Join failed: Lobby is full")
                    return False
                if player in self.lobby.players:
                    print(f"Join failed: Player {player} already in lobby")
                    return False
                self.lobby.players.append(player)
                print(f"Player {player} successfully joined the lobby")
                print(f"Updated players in lobby: {self.lobby.players}")
                return True
