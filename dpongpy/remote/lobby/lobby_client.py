import asyncio
import json
import sys
from typing import Optional

import requests
import websockets
from dpongpy.remote.lobby.response_models import LobbyResponse, MessageResponse


class LobbyManagerClient:
    def __init__(self, base_url: str, api_port: int):
        self.api_base_url = f"{base_url}:{api_port}/api/lobbies"
        self.player_name: Optional[str] = None
        self.current_lobby: Optional[LobbyResponse] = None

    def create_lobby(self, name: str, max_players: int = 2) -> Optional[LobbyResponse]:
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

    def leave_lobby(self) -> Optional[MessageResponse]:
        if not self.player_name:
            print("You are not currently in a lobby.")
            return None
        payload = {"player": self.player_name}
        try:
            response = requests.post(f"{self.api_base_url}/leave", json=payload)
            response.raise_for_status()
            message_data = response.json()
            message = MessageResponse(**message_data)
            print("Leave message:", message.message)
            if message.lobby:
                self.current_lobby = message.lobby
            else:
                self.current_lobby = None
            self.player_name = None
            return message
        except requests.exceptions.HTTPError as http_err:
            try:
                error_detail = response.json().get("detail", "Unknown error")
            except ValueError:
                error_detail = "No detail provided."
            print(
                f"HTTP error occurred while leaving lobby: {http_err} - {error_detail}"
            )
        except Exception as err:
            print(f"An error occurred while leaving lobby: {err}")
        return None

    def get_lobby(self) -> Optional[LobbyResponse]:
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
        if not self.current_lobby:
            print("No active lobby to connect to.")
            return
        websocket_url = f"ws://{self.current_lobby.address}:{self.current_lobby.port}"
        print(f"Connecting to WebSocket at {websocket_url}...")
        try:
            async with websockets.connect(websocket_url) as websocket:
                print(f"Connected to WebSocket at {websocket_url}")
                # Start listening and sending messages concurrently
                listener_task = asyncio.create_task(self.listen(websocket))
                sender_task = asyncio.create_task(self.send_messages(websocket))
                await asyncio.gather(listener_task, sender_task)
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

    async def send_messages(self, websocket):
        print("You can now start sending messages. Type 'exit' to disconnect.")
        while True:
            message = await asyncio.get_event_loop().run_in_executor(
                None, sys.stdin.readline
            )
            message = message.strip()
            if message.lower() == "exit":
                print("Disconnecting from WebSocket...")
                await websocket.close()
                break
            if message:
                try:
                    await websocket.send(message)
                    print(f"Sent message: {message}")
                except websockets.exceptions.ConnectionClosed:
                    print("WebSocket connection closed.")
                    break
