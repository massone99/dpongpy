import asyncio
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from dpongpy.remote.lobby.lobby_manager import LobbyManager  # Adjust based on your project structure
from dpongpy.remote.lobby.response_models import LobbyResponse, MessageResponse

app = FastAPI()
lobby_manager = LobbyManager()

# Data Models for Requests
class CreateLobbyRequest(BaseModel):
    name: str
    max_players: int = 2

class JoinLobbyRequest(BaseModel):
    player: str

class LeaveLobbyRequest(BaseModel):
    player: str

# RESTful API Endpoints

# To run the server, use the follow command when in the lobby directory:
# uvicorn lobby_server:app --reload --host 127.0.0.1 --port 8000

@app.post("/api/lobbies", response_model=LobbyResponse)
async def create_lobby(request: CreateLobbyRequest):
    try:
        lobby = await lobby_manager.create_lobby(request.name, request.max_players)
        return lobby.to_dict()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/lobbies", response_model=Optional[LobbyResponse])
async def get_lobby():
    lobby = await lobby_manager.get_lobby()
    if lobby:
        return lobby.to_dict()
    return {"detail": "No active lobby"}

@app.post("/api/lobbies/join", response_model=MessageResponse)
async def join_lobby(request: JoinLobbyRequest, background_tasks: BackgroundTasks):
    # Check if a lobby exists
    lobby = await lobby_manager.get_lobby()
    if not lobby:
        # No lobby exists; create a new one with default parameters
        default_lobby_name = "Auto-Created Lobby"
        default_max_players = 2  # You can adjust this as needed
        try:
            lobby = await lobby_manager.create_lobby(default_lobby_name, default_max_players)
            print(f"Lobby '{default_lobby_name}' created automatically.")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Unable to create lobby: {str(e)}")

    # Attempt to join the lobby
    success = await lobby_manager.join_lobby(request.player)
    if not success:
        raise HTTPException(status_code=400, detail="Unable to join lobby (it might be full or you are already in it).")

    # Retrieve the updated lobby information
    lobby = await lobby_manager.get_lobby()

    response = MessageResponse(message=f"{request.player} joined the lobby.", lobby=lobby.to_dict())

    # Check if the lobby is now full
    if lobby.is_full():
        print("Lobby is full. Scheduling application shutdown...")
        background_tasks.add_task(shutdown)

    return response

async def shutdown():
    print("Initiating graceful shutdown...")
    await asyncio.sleep(2)  # Give some time for the response to be sent
    # Access the server instance and set should_exit to True
    app.state.server.should_exit = True



@app.post("/api/lobbies/leave", response_model=MessageResponse)
async def leave_lobby(request: LeaveLobbyRequest):
    success = await lobby_manager.leave_lobby(request.player)
    if not success:
        raise HTTPException(status_code=400, detail="Unable to leave lobby.")
    lobby = await lobby_manager.get_lobby()
    if lobby:
        return MessageResponse(message=f"{request.player} left the lobby.", lobby=lobby.to_dict())
    else:
        return MessageResponse(message=f"{request.player} left the lobby. Lobby is now empty and closed.", lobby=None)

# TODO: REMOVE
# WebSocket Handling (if applicable)
# @app.websocket("/ws/lobby")
# async def websocket_endpoint(websocket: WebSocket):
#     lobby = await lobby_manager.get_lobby()
#     if not lobby:
#         await websocket.close(code=1008)  # Policy Violation
#         return
#     await lobby_manager.connect(websocket)  # Implement connect method in LobbyManager
#     try:
#         while True:
#             data = await websocket.receive_text()
#             # Handle incoming messages and broadcast to other players
#             await lobby_manager.broadcast(data)  # Implement broadcast method in LobbyManager
#     except WebSocketDisconnect:
#         await lobby_manager.disconnect(websocket)  # Implement disconnect method in LobbyManager
#         # Optionally, handle player disconnection logic
