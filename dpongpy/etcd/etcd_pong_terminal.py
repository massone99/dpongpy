import time
import uuid

import etcd3
from pygame.event import Event

from dpongpy import PongGame, EtcdSettings
from dpongpy.controller import ControlEvent
from dpongpy.etcd.schemas.event_schema import encode_event
from dpongpy.log import Loggable
from dpongpy.model import *


class EtcdPongTerminal(PongGame, Loggable):
    def __init__(self, settings: EtcdSettings = None):
        self.settings = settings or EtcdSettings()
        # Generate player_id if not provided
        if not self.settings.player_id:
            self.settings.player_id = str(uuid.uuid4())
        super().__init__(self.settings)
        self.pong.reset_ball((0, 0))
        self.client = etcd3.client(
            host=self.settings.etcd_host, port=self.settings.etcd_port
        )

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

            def put_event(self, event):
                try:
                    result = terminal.client.put(
                        f"pong_events",
                        encode_event(event),
                    )
                    if not result:
                        logger.error("Failed to put event to etcd: No result returned")
                    logger.info(f"Put event to etcd: {event}")
                except Exception as e:
                    logger.error(f"Failed to put event to etcd: {e}")
                    raise e

            def on_paddle_move(
                    self, pong: Pong, paddle_index: int | Direction, direction: Direction
            ):
                # We need to update the state only after it's been approved by the cluster leader
                # pong.move_paddle(paddle_index, direction)

                assert isinstance(paddle_index, Direction), "Invalid paddle index type provided"

                # Create event following schema
                event = {
                    "eventId": str(uuid.uuid4()),
                    "eventType": "PADDLE_MOVE",
                    "timestamp": int(time.time() * 1000),
                    "gameId": terminal.settings.game_id,
                    "playerId": terminal.settings.player_id,
                    "payload": {
                        "direction": direction.name,
                        "paddleIndex": {
                            # Convert Vector2/Direction to x,y coordinates
                            "x": paddle_index.value.x if isinstance(paddle_index, Direction) else 0,
                            "y": paddle_index.value.y if isinstance(paddle_index, Direction) else 0
                        }
                    }
                }
                self.put_event(event)

            def on_game_over(self, pong: Pong):
                terminal.stop()

        return EtcdController(terminal.pong, paddle_commands)

    def before_run(self):
        logger.info("Terminal starting")
        super().before_run()
        self.controller.post_event(
            ControlEvent.PLAYER_JOIN, paddle_index=self.pong.paddles[0].side
        )

    def after_run(self):
        logger.info("Terminal stopped gracefully")
        super().after_run()
