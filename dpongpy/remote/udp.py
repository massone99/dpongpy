import threading
from dpongpy.remote.centralised import DEFAULT_HOST, DEFAULT_PORT
from dpongpy.remote.centralised.ipong_coordinator import IRemotePongCoordinator, SyncPongCoordinator
from dpongpy.remote.centralised.ipong_terminal import SyncPongTerminal, IRemotePongTerminal


class UdpPongCoordinator(SyncPongCoordinator):
    def initialize(self):
        from dpongpy.remote.comm.udp.udp import Server as UDPServer
        self.server = UDPServer(self.settings.port or DEFAULT_PORT)


class UdpPongTerminal(SyncPongTerminal):
    def initialize(self):
        from dpongpy.remote.comm.udp.udp import Client as UDPClient
        super().initialize(UDPClient)