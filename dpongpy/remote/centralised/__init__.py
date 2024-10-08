from dpongpy import Settings
from dpongpy.model import *

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 12345

def main_coordinator(settings=None):
    comm_tech = settings.comm_technology
    match comm_tech:
        case "web_sockets":
            from dpongpy.remote.ws import WebSocketPongCoordinator

            WebSocketPongCoordinator(settings).run()
        case "zmq":
            from dpongpy.remote.zmq import ZmqPongCoordinator

            ZmqPongCoordinator(settings).run()
        case "udp":
            from dpongpy.remote.udp import UdpPongCoordinator

            UdpPongCoordinator(settings).run()
        case _:
            raise ValueError(f"Unknown comm_tech: {comm_tech}")


def main_terminal(settings=None):
    comm_tech = settings.comm_technology
    match comm_tech:
        case "web_sockets":
            from dpongpy.remote.ws import WebSocketPongTerminal

            WebSocketPongTerminal(settings).run()
        case "zmq":
            from dpongpy.remote.zmq import ZmqPongTerminal

            ZmqPongTerminal(settings).run()
        case "udp":
            from dpongpy.remote.udp import UdpPongTerminal

            UdpPongTerminal(settings).run()
        case _:
            raise ValueError(f"Unknown comm_tech: {comm_tech}")
