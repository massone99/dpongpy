import asyncio
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional

import uvicorn
from dpongpy.remote.lobby.lobby_manager import LobbyManager
from dpongpy.remote.lobby.response_models import LobbyResponse, MessageResponse


class CreateLobbyRequest(BaseModel):
    name: str
    max_players: int = 2


class JoinLobbyRequest(BaseModel):
    player: str


class LeaveLobbyRequest(BaseModel):
    player: str


class LobbyServer:
    def __init__(
        self, host: str = "127.0.0.1", api_port: int = 8000, ws_port: int = 5000, num_players: int = 2
    ):
        """
        Initializes the LobbyServer to servfe on the specified host and port.

        :param host: Host address to bind the server.
        :param port: Port number to bind the server.
        """
        self.host = host
        self.port = api_port
        self.num_players = num_players
        self.app = FastAPI()
        self.lobby_manager = LobbyManager(address=host, port=ws_port)
        self.setup_routes()

    def setup_routes(self):
        """
        Sets up the RESTful API endpoints for the lobby management.
        """

        @self.app.post("/api/lobbies", response_model=LobbyResponse)
        async def create_lobby(request: CreateLobbyRequest):
            """
            Handles the creation of a new lobby.

            Args:
                request (CreateLobbyRequest): The request object containing the name and maximum number of players for the new lobby.

            Returns:
                dict: A dictionary representation of the created lobby, which will be automatically validated against the LobbyResponse schema, serialized to JSON, and returned with the correct Content-Type header.

            Raises:
                HTTPException: If an error occurs during lobby creation, an HTTP 400 error is raised with the error details.
            """
            try:
                lobby = await self.lobby_manager.create_lobby(
                    request.name, request.max_players
                )
                # FastAPI automatically:
                # Validates dict against LobbyResponse schema
                # Serializes to JSON
                # Sets correct Content-Type header
                return lobby.to_dict()
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.app.get("/api/lobbies", response_model=Optional[LobbyResponse])
        async def get_lobby():
            lobby = await self.lobby_manager.get_lobby()
            if lobby:
                return lobby.to_dict()
            return {"detail": "No active lobby"}

        @self.app.post("/api/lobbies/join", response_model=MessageResponse)
        async def join_lobby(
            request: JoinLobbyRequest, background_tasks: BackgroundTasks
        ):
            # Check if a lobby exists
            lobby = await self.lobby_manager.get_lobby()
            if not lobby:
                # No lobby exists; create a new one with default parameters
                default_lobby_name = "Auto-Created Lobby"
                try:
                    lobby = await self.lobby_manager.create_lobby(
                        default_lobby_name, self.num_players
                    )
                    print(f"Lobby '{default_lobby_name}' created automatically.")
                except Exception as e:
                    raise HTTPException(
                        status_code=400, detail=f"Unable to create lobby: {str(e)}"
                    )

            # Attempt to join the lobby
            success = await self.lobby_manager.join_lobby(request.player)
            if not success:
                raise HTTPException(
                    status_code=400,
                    detail="Unable to join lobby (it might be full or you are already in it).",
                )

            # Retrieve the updated lobby information
            lobby = await self.lobby_manager.get_lobby()

            response = MessageResponse(
                message=f"{request.player} joined the lobby.", lobby=lobby.to_dict()
            )

            # Check if the lobby is now full
            if lobby.is_full():
                print("Lobby is full. Scheduling application shutdown...")
                background_tasks.add_task(self.shutdown)

            return response

        @self.app.post("/api/lobbies/leave", response_model=MessageResponse)
        async def leave_lobby(request: LeaveLobbyRequest):
            success = await self.lobby_manager.leave_lobby(request.player)
            if not success:
                raise HTTPException(status_code=400, detail="Unable to leave lobby.")
            lobby = await self.lobby_manager.get_lobby()
            if lobby:
                return MessageResponse(
                    message=f"{request.player} left the lobby.", lobby=lobby.to_dict()
                )
            else:
                return MessageResponse(
                    message=f"{request.player} left the lobby. Lobby is now empty and closed.",
                    lobby=None,
                )

    async def shutdown(self):
        """
        Initiates a graceful shutdown of the server.
        """
        print("Initiating API server shutdown...")
        await asyncio.sleep(2)  # Give some time for the response to be sent
        # Access the server instance and set should_exit to True
        if hasattr(self.app.state, "server"):
            self.app.state.server.should_exit = True
            print("Shutdown signal sent to Uvicorn server.")
        else:
            print("Server instance not found in app.state.")

    def run(self):
        """
        Runs the Uvicorn server with the specified host and port.
        """
        config = uvicorn.Config(
            app=self.app, host=self.host, port=self.port, log_level="info"
        )
        server = uvicorn.Server(config)
        # Store the server instance in app.state for access within the FastAPI app
        self.app.state.server = server
        server.run()
