import threading
import time
import uuid
from abc import ABC

import etcd3

from dpongpy import EtcdSettings
from dpongpy.log import logger


class ClusterTerminal(ABC):
    def __init__(self, settings: EtcdSettings = None):
        self.settings = settings or EtcdSettings()
        # Generate player_id if not provided
        if not self.settings.player_id:
            self.settings.player_id = str(uuid.uuid4())
        self.client = etcd3.client(
            host=self.settings.etcd_host, port=self.settings.etcd_port
        )
        self.lease = self.client.lease(ttl=5)
        self.leader_thread = threading.Thread(target=self.campaign_for_leadership)
        self.leader_thread.daemon = True  # Ensure thread exits with main program
        self.leader_thread.start()

    def become_leader(self):
        return self.client.put_if_not_exists(
            "election/leader", self.settings.player_id, self.lease
        )

    def is_leader(self) -> bool:
        current_leader = self.client.get("election/leader")
        if current_leader:
            if current_leader[0]:
                return current_leader[0].decode("utf-8") == self.settings.player_id
            else:
                self.client.delete("election/leader")
                self.client.put("election/leader", self.settings.player_id, self.lease)
                logger.info("This client is the leader.")
                return True
        else:
            return False

    def resign_leadership(self):
        """Resign from leadership by deleting the leadership key."""
        if self.is_leader() and self.lease:
            try:
                self.client.delete("election/leader")
                self.lease.revoke()
                logger.info("Resigned from leadership.")
            except Exception as e:
                logger.error(f"Failed to resign from leadership: {e}")

    def campaign_for_leadership(self):
        """Attempt to become the leader using etcd's election mechanism."""
        while True:
            try:
                # Setting a lease to be fault-tolerant in case the leader crashes
                is_leader = self.is_leader() or self.become_leader()
                while self.lease and is_leader:
                    logger.debug("This client is the leader.")
                    # Update distributed state using events from other terminals
                    self.process_events()
                    # Keep the lease alive to maintain leadership
                    self.lease.refresh()
                    logger.debug("Lease refreshed; still the leader.")
                if not is_leader:
                    logger.info("This client is a follower; observing the leader.")
                    self.observe_leader()
            except Exception as e:
                logger.error(f"Error during leadership campaign: {e}")
                if self.lease:
                    self.lease.revoke()
                time.sleep(5)  # Wait before retrying

    def observe_leader(self):
        """Watch the leadership key to detect leader changes."""
        events_iterator, cancel = self.client.watch("election/leader")
        for event in events_iterator:
            if isinstance(event, etcd3.events.DeleteEvent):
                logger.info("Leader key deleted; attempting to become the leader.")
                cancel()
                break
            elif isinstance(event, etcd3.events.PutEvent):
                logger.info(f"New leader elected: {event.value.decode()}")
        # After detecting leader key deletion, retry leadership campaign
        self.campaign_for_leadership()

    def process_events(self):
        """Process events present in the etcd database."""
        pass
