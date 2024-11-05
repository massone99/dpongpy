import threading
import time
import uuid

import etcd3
from pygame.event import Event

from dpongpy import PongGame, EtcdSettings
from dpongpy.controller import ControlEvent
from dpongpy.etcd.schemas.event_schema import decode_event, encode_event, EVENTS_KEY_PREFIX
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

        # Initialize leadership variables
        self.leader = False
        self.lease = None
        self.leader_thread = threading.Thread(target=self.campaign_for_leadership)
        self.leader_thread.daemon = True  # Ensure thread exits with main program
        self.leader_thread.start()

    def campaign_for_leadership(self):
        """Attempt to become the leader using etcd's election mechanism."""

        def is_leader():
            current_leader = self.client.get('election/leader')
            # Checking if the player id of the leader is None
            if current_leader:
                if current_leader[0]:
                    return current_leader[0] == self.settings.player_id
                else:
                    self.client.delete('election/leader')
                    self.client.put('election/leader', self.settings.player_id, self.lease)
                    logger.info("This client is the leader.")
                    return True
            else:
                return self.client.put_if_not_exists('election/leader', self.settings.player_id, self.lease)

        while True:
            try:
                self.lease = self.client.lease(ttl=5)  # Create a lease with a TTL of 5 seconds
                is_leader = is_leader()
                while is_leader:
                    self.leader = True
                    logger.info("This client is the leader.")
                    # Start leadership responsibilities
                    self.update_game_state()
                    # Keep the lease alive to maintain leadership
                    time.sleep(2)
                    self.lease.refresh()
                    logger.debug("Lease refreshed; still the leader.")
                if not is_leader:
                    self.leader = False
                    logger.info("This client is a follower; observing the leader.")
                    self.observe_leader()
            except Exception as e:
                logger.error(f"Error during leadership campaign: {e}")
                if self.lease:
                    self.lease.revoke()
                time.sleep(5)  # Wait before retrying

    def observe_leader(self):
        """Watch the leadership key to detect leader changes."""
        events_iterator, cancel = self.client.watch('election/leader')
        for event in events_iterator:
            if isinstance(event, etcd3.events.DeleteEvent):
                logger.info("Leader key deleted; attempting to become the leader.")
                cancel()
                break
            elif isinstance(event, etcd3.events.PutEvent):
                logger.info(f"New leader elected: {event.value.decode()}")
        # After detecting leader key deletion, retry leadership campaign
        self.campaign_for_leadership()

    def update_game_state(self):
        """Handle actions to perform when becoming the leader."""
        logger.info("Retrieving events with prefix.")
        events = self.client.get_prefix(EVENTS_KEY_PREFIX)
        for value, metadata in events:
            event = decode_event(value)
            # Process the event as needed
            print(value)

    def resign_leadership(self):
        """Resign from leadership by deleting the leadership key."""
        if self.leader and self.lease:
            try:
                self.client.delete('election/leader')
                self.lease.revoke()
                self.leader = False
                logger.info("Resigned from leadership.")
            except Exception as e:
                logger.error(f"Failed to resign from leadership: {e}")

    def create_controller(terminal, paddle_commands=None):
        from dpongpy.controller.local import EventHandler, PongInputHandler
        import json

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
                    unique_id = str(uuid.uuid4())
                    key = f"{EVENTS_KEY_PREFIX}/{unique_id}"
                    result = terminal.client.put(
                        key,
                        encode_event(event),
                    )
                    if not result:
                        logger.error("Failed to put event to etcd: No result returned")
                    logger.info(f"Put event to etcd on key '{key}'")
                    logger.info(f"Data: {json.dumps(event, indent=4)}")
                except Exception as e:
                    logger.error(f"Failed to put event to etcd: {e}")
                    raise e

            def on_paddle_move(
                    self, pong: Pong, paddle_index: int | Direction, direction: Direction
            ):
                if terminal.leader:
                    # Only the leader can update the game state
                    event = {
                        "eventId": str(uuid.uuid4()),
                        "eventType": "PADDLE_MOVE",
                        "timestamp": int(time.time() * 1000),
                        "gameId": terminal.settings.game_id,
                        "playerId": terminal.settings.player_id,
                        "payload": {
                            "direction": direction.name,
                            "paddleIndex": {
                                "x": (
                                    paddle_index.value.x
                                    if isinstance(paddle_index, Direction)
                                    else 0
                                ),
                                "y": (
                                    paddle_index.value.y
                                    if isinstance(paddle_index, Direction)
                                    else 0
                                ),
                            },
                        },
                    }
                    self.put_event(event)
                else:
                    logger.debug("Ignored paddle move event as this client is not the leader.")

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
        # Resign leadership if currently the leader
        self.resign_leadership()
        super().after_run()

    def stop(self):
        """Override the stop method to include leadership resignation."""
        logger.info("Stopping terminal...")
        self.resign_leadership()
        super().stop()
