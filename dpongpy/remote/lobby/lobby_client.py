import asyncio
import sys
from typing import Optional

import requests
import websockets
from dpongpy.remote.lobby.response_models import LobbyResponse, MessageResponse


class LobbyManagerClient:
    """
    LobbyManagerClient class to manage the interaction with the lobby API server.
    """

    def __init__(self, base_url: str, api_port: int):
        self.api_base_url = f"{base_url}:{api_port}/api/lobbies"
        self.player_name: Optional[str] = None
        self.current_lobby: Optional[LobbyResponse] = None

    def create_lobby(self, name: str, max_players: int = 2) -> Optional[LobbyResponse]:
        """Creates a lobby my making a POST request to the API of the server

        Args:
            name (str): name of the lobby
            max_players (int, optional): maximum number of players allowed in the lobby. Defaults to 2.

        Returns:
            Optional[LobbyResponse]: LobbyResponse object with the details of the created lobby, or None if an error occurred.
        """
        payload = {"name": name, "max_players": max_players}
        try:
            response = requests.post(self.api_base_url, json=payload)
            response.raise_for_status()
            lobby_data = response.json()
            lobby = LobbyResponse(**lobby_data)
            self.current_lobby = lobby
            print("Lobby created successfully:")
            print(lobby)
            return lobby
        except requests.exceptions.HTTPError as http_err:
            error_detail = response.json().get("detail", "Unknown error")
            print(
                f"HTTP error occurred while creating lobby: {http_err} - {error_detail}"
            )
        except Exception as err:
            print(f"An error occurred while creating lobby: {err}")
        return None

    def join_lobby(self, player_name: str) -> Optional[MessageResponse]:
        """Joins a lobby by making a POST request to the API of the server

        Args:
            player_name (str): name of the player joining the lobby

        Returns:
            Optional[MessageResponse]: MessageResponse object with the response message and lobby details, or None if an error occurred.
        """
        payload = {"player": player_name}
        try:
            response = requests.post(f"{self.api_base_url}/join", json=payload)
            response.raise_for_status()
            message_data = response.json()
            message = MessageResponse(**message_data)
            self.player_name = player_name
            if message.lobby:
                self.current_lobby = message.lobby
            print("Join message:", message.message)
            if message.lobby:
                print("Lobby Info:")
                print(message.lobby)
            return message
        except requests.exceptions.HTTPError as http_err:
            try:
                error_detail = response.json().get("detail", "Unknown error")
            except ValueError:
                error_detail = "No detail provided."
            print(
                f"HTTP error occurred while joining lobby: {http_err} - {error_detail}"
            )
        except Exception as err:
            print(f"An error occurred while joining lobby: {err}")
        return None

    def get_lobby(self) -> Optional[LobbyResponse]:
        """Fetches the current active lobby by making a GET request to the API of the server

        Returns:
            Optional[LobbyResponse]: LobbyResponse object with the details of the current active lobby, or None if an error occurred.
        """
        try:
            response = requests.get(self.api_base_url)
            response.raise_for_status()
            lobby_data = response.json()
            if "detail" in lobby_data and lobby_data["detail"] == "No active lobby":
                print("No active lobby.")
                self.current_lobby = None
                return None
            lobby = LobbyResponse(**lobby_data)
            self.current_lobby = lobby
            print("Active Lobby:")
            print(lobby)
            return lobby
        except requests.exceptions.HTTPError as http_err:
            try:
                error_detail = response.json().get("detail", "Unknown error")
            except ValueError:
                error_detail = "No detail provided."
            print(
                f"HTTP error occurred while fetching lobby: {http_err} - {error_detail}"
            )
        except Exception as err:
            print(f"An error occurred while fetching lobby: {err}")
        return None

    async def connect_websocket(self):
        """
        Connects to the WebSocket server of the current active lobby.
        """
        if not self.current_lobby:
            print("No active lobby to connect to.")
            return
        websocket_url = f"ws://{self.current_lobby.address}:{self.current_lobby.port}"
        print(f"Connecting to WebSocket at {websocket_url}...")
        try:
            async with websockets.connect(websocket_url):
                print(f"Connected to WebSocket at {websocket_url}")
        except websockets.exceptions.ConnectionClosed as e:
            print(f"WebSocket connection closed: {e.code} - {e.reason}")
        except Exception as e:
            print(f"An error occurred with WebSocket connection: {e}")

    async def listen(self, websocket):
        try:
            async for message in websocket:
                print(f"\nReceived message: {message}")
        except websockets.exceptions.ConnectionClosed:
            print("WebSocket connection closed.")
