# Import required modules
from dpongpy.remote.centralised import DEFAULT_PORT
from dpongpy.remote.centralised.ipong_terminal import SyncPongTerminal
from dpongpy.remote.centralised.ipong_coordinator import (
    SyncPongCoordinator,
)

class ZmqPongCoordinator(SyncPongCoordinator):
    def initialize(self):
        from dpongpy.remote.comm.zmq.zmq_server import Server as ZMQServer
        self.server = ZMQServer(self.settings.port or DEFAULT_PORT)

class ZmqPongTerminal(SyncPongTerminal):
    def initialize(self):
        from dpongpy.remote.comm.zmq.zmq_client import Client as ZMQClient
        super().initialize(ZMQClient)