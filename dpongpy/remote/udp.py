from dpongpy.remote.centralised import DEFAULT_PORT
from dpongpy.remote.centralised.ipong_coordinator import ThreadedPongCoordinator
from dpongpy.remote.centralised.ipong_terminal import ThreadedPongTerminal


class UdpPongCoordinator(ThreadedPongCoordinator):
    def initialize(self):
        from dpongpy.remote.comm.udp.udp import Server as UDPServer
        self.server = UDPServer(self.settings.port or DEFAULT_PORT)


class UdpPongTerminal(ThreadedPongTerminal):
    def initialize(self):
        from dpongpy.remote.comm.udp.udp import Client as UDPClient
        super().initialize(UDPClient)