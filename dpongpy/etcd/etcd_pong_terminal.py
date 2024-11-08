import json
import threading
import time
import uuid

import etcd3
from jsonschema import ValidationError
from pygame.event import Event

from dpongpy import PongGame, EtcdSettings
from dpongpy.controller import ControlEvent
from dpongpy.etcd.ClusterTerminal import ClusterTerminal
from dpongpy.etcd.schemas.event_schema import (decode_event, EVENTS_KEY_PREFIX, put_event, )
from dpongpy.etcd.schemas.lobby_schema import (LOBBY_KEY, validate_lobby_data, create_empty_lobby, )
from dpongpy.log import Loggable
from dpongpy.model import *


class EtcdPongTerminal(PongGame, Loggable, ClusterTerminal):
    def __init__(self, settings: EtcdSettings = None):
        self.settings = settings or EtcdSettings()
        ClusterTerminal.__init__(self, self.settings)
        super().__init__(self.settings)
        self.pong.reset_ball((0, 0))

    def process_events(self):
        """Handle actions to perform when becoming the leader."""
        logger.debug("Retrieving events with prefix.")
        events = self.client.get_prefix(EVENTS_KEY_PREFIX)
        for value, metadata in events:
            event = decode_event(value)
            self.update_lobby_data(event)
            # Delete the event after processing
            self.client.delete(metadata.key)
            logger.debug(f"Processed and deleted event: {event}")

    def watch_lobby_data(self):
        """Watch the lobby_data key to detect changes and update the game state."""
        events_iterator, cancel = self.client.watch(LOBBY_KEY, start_revision=0)
        for event in events_iterator:
            if isinstance(event, etcd3.events.PutEvent):
                lobby_data = json.loads(event.value.decode('utf-8'))
                self.update_local_state(lobby_data)

    def get_lobby_data(self):
        lobby_data, _ = self.client.get(LOBBY_KEY)
        if lobby_data:
            try:
                return json.loads(lobby_data.decode('utf-8'))
            except json.JSONDecodeError:
                logger.error("Invalid JSON in lobby data")
        return create_empty_lobby(size=self.pong.size)

    def update_local_state(self, lobby_data):
        # Update paddles
        for player in lobby_data['players']:
            paddle_position = Vector2(player['x'], player['y'])
            # Create paddle with proper size from config
            paddle_ratio = self.pong.config.paddle_ratio
            side = Direction[player['direction']]
            if side.is_vertical:
                paddle_ratio = (paddle_ratio.y, paddle_ratio.x)
            paddle_size = self.pong.size.elementwise() * paddle_ratio
            if not [p for p in self.pong.paddles if p.side == Direction[player['direction']]]:
                # Create paddle with proper size from config
                paddle_ratio = self.pong.config.paddle_ratio
                side = Direction[player['direction']]
                if side.is_vertical:
                    paddle_ratio = (paddle_ratio.y, paddle_ratio.x)
                paddle_size = self.pong.size.elementwise() * paddle_ratio
                new_paddle = Paddle(size=paddle_size, side=side, position=paddle_position)
                self.pong.add_paddle(side=side, paddle=new_paddle)
                logger.info(f"[LOCAL] Added new paddle on {side.name}")
            if [p for p in self.pong.paddles if p.side == Direction[player['direction']]]:
                updated_paddle = Paddle(size=paddle_size, side=side, position=paddle_position)
                current_paddle = [p for p in self.pong.paddles if p.side == updated_paddle.side]
                # assert len(current_paddle) == 1, f"Expected 1 paddle, got {len(current_paddle)}"
                if len(current_paddle) == 1:
                    old_paddle_pos = current_paddle[0].position
                    current_paddle[0].override(updated_paddle)
                    logger.debug(
                        f"[LOCAL] Updated {updated_paddle.side.name} paddle position from {old_paddle_pos} to {updated_paddle.position}")
        # Update ball position
        ball_position = lobby_data['ball']['position']
        self.pong.ball.position = Vector2(ball_position['x'], ball_position['y'])

    def update_lobby_data(self, event):
        lobby_data, metadata = self.client.get(LOBBY_KEY)
        if lobby_data:
            lobby = json.loads(lobby_data.decode("utf-8"))
        else:
            lobby = create_empty_lobby(size=self.pong.size)
            logger.error("Lobby data not found; initializing with empty lobby.")
        if event["eventType"] == "PLAYER_JOIN":
            # Check if player already exists
            player_id = event["playerId"]
            if not any(p["playerId"] == player_id for p in lobby["players"]):
                player_side = event["payload"].get("side")
                assert player_side is not None, "Player side must be provided in payload"
                player_join_payload = {"playerId": player_id, "direction": player_side,
                                       "x": event["payload"].get("x", 0), "y": event["payload"].get("y", 0), }
                lobby["players"].append(player_join_payload)
                logger.info(f"Player joined with payload: {player_join_payload}")
        elif event["eventType"] == "PLAYER_LEAVE":
            lobby["players"] = [player for player in lobby["players"] if player["playerId"] != event["playerId"]]
        elif event["eventType"] == "PADDLE_MOVE":
            for player in lobby["players"]:
                if player["playerId"] == event["playerId"]:
                    old_pos = Vector2(player["x"], player["y"])
                    # Update the paddle position using the amount in the payload
                    player["x"] += event["payload"]["paddleIndex"].get("x")
                    player["y"] += event["payload"]["paddleIndex"].get("y")
                    logger.debug(f"[ETCD] Updated paddle position from {old_pos} to {player['x'], player['y']}")
                    break

        # Validate and update etcd
        try:
            validate_lobby_data(lobby)
            self.client.put(LOBBY_KEY, json.dumps(lobby, indent=4), lease=self.client.lease(ttl=60))
        except ValidationError as ve:
            logger.error(f"Lobby data validation failed: {ve}")

    def resign_leadership(self):
        """Resign from leadership by deleting the leadership key."""
        if self.is_leader() and self.lease:
            try:
                self.client.delete("election/leader")
                self.lease.revoke()
                logger.info("Resigned from leadership.")
            except Exception as e:
                logger.error(f"Failed to resign from leadership: {e}")

    def player_join(self, player_id, side):
        # Get current lobby state
        lobby = self.get_lobby_data()

        # Calculate paddle position
        paddle_ratio = self.pong.config.paddle_ratio
        if side.is_vertical:
            paddle_ratio = (paddle_ratio.y, paddle_ratio.x)

        paddle_size = Vector2(self.pong.size).elementwise() * paddle_ratio
        padding = (
            self.pong.width * self.pong.config.paddle_padding + paddle_size.x / 2 if side.is_horizontal else self.pong.height * self.pong.config.paddle_padding + paddle_size.y / 2)

        # Calculate position based on side
        if side == Direction.UP:
            position = Vector2(self.pong.width / 2, padding)
        elif side == Direction.RIGHT:
            position = Vector2(self.pong.width - padding, self.pong.height / 2)
        elif side == Direction.DOWN:
            position = Vector2(self.pong.width / 2, self.pong.height - padding)
        else:  # LEFT
            position = Vector2(padding, self.pong.height / 2)

        # Create player data
        player_data = {"playerId": player_id, "direction": side.name, "x": position.x, "y": position.y, }

        # Remove player with same side if already exists
        # lobby["players"] = [player for player in lobby["players"] if player["direction"] != side.name]

        lobby["players"].append(player_data)

        # Update lobby in etcd
        try:
            validate_lobby_data(lobby)
            self.client.put(LOBBY_KEY, json.dumps(lobby, indent=4))
            logger.info(f"Added player to lobby: {player_data}")
        except ValidationError as ve:
            logger.error(f"Lobby validation failed: {ve}")

        # Also create the join event
        event = {"eventId": str(uuid.uuid4()), "eventType": "PLAYER_JOIN", "timestamp": int(time.time() * 1000),
                 "gameId": self.settings.game_id, "playerId": player_id,
                 "payload": {"side": side.name, "x": position.x, "y": position.y, }, }
        put_event(self.client, event)

    def create_controller(terminal, paddle_commands=None):
        from dpongpy.controller.local import EventHandler, PongInputHandler

        class EtcdController(PongInputHandler, EventHandler):
            def __init__(self, pong: Pong, paddle_commands):
                PongInputHandler.__init__(self, pong, paddle_commands)

            def post_event(self, event: Event | ControlEvent, **kwargs):
                event = super().post_event(event, **kwargs)
                return event

            def handle_inputs(self, dt=None):
                return super().handle_inputs(dt)

            def on_time_elapsed(self, pong: Pong, dt: float, status: Pong = None):
                if status is None or pong is status:
                    pong.update(dt)
                else:
                    pong.override(status)

            def on_paddle_move(self, pong: Pong, paddle_index: int | Direction, direction: Direction):
                if isinstance(paddle_index, Direction):
                    event = {"eventId": str(uuid.uuid4()), "eventType": "PADDLE_MOVE",
                             "timestamp": int(time.time() * 1000), "gameId": terminal.settings.game_id,
                             "playerId": terminal.settings.player_id,
                             "payload": {"direction": direction.name,
                                         "paddleIndex": {
                                             "x": direction.value.x,
                                             "y": direction.value.y, },
                                         },
                             }
                    put_event(terminal.client, event)

            def on_game_over(self, pong: Pong):
                terminal.stop()

        return EtcdController(terminal.pong, paddle_commands)

    def before_run(self):
        logger.info("Terminal starting")
        super().before_run()
        # Initialize game state from lobby data
        lobby_data = self.get_lobby_data()
        # Local event handler
        self.controller.post_event(ControlEvent.PLAYER_JOIN, paddle_index=self.pong.paddles[0].side)
        # Emit PLAYER_JOIN event on the etcd server
        self.player_join(self.settings.player_id, self.pong.paddles[0].side)

        self.update_local_state(lobby_data)
        # Start watching the lobby_data key
        threading.Thread(target=self.watch_lobby_data, daemon=True).start()

    def after_run(self):
        logger.info("Terminal stopped gracefully")
        # Resign leadership if currently the leader
        self.resign_leadership()
        super().after_run()

    def stop(self):
        """Override the stop method to include leadership resignation."""
        logger.info("Stopping terminal...")
        self.resign_leadership()
        super().stop()
