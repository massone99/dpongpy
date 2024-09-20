
from pydantic import BaseModel
from typing import List, Optional

class LobbyResponse(BaseModel):
    id: str
    name: str
    max_players: int
    current_players: int
    players: List[str]
    address: str
    port: int

class MessageResponse(BaseModel):
    message: str
    lobby: Optional[LobbyResponse] = None
