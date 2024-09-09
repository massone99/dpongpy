from dpongpy.log import logger
from dpongpy.remote import *
import os
import random


THRESHOLD_DGRAM_SIZE = 65536
UDP_DROP_RATE = float(os.environ.get("UDP_DROP_RATE", 0.0))
assert 0 <= UDP_DROP_RATE < 1, "Drop rate for outgoing UDP messages must be between 0 (included) and 1 (excluded)"
if UDP_DROP_RATE > 0:
    logger.warn(f"Drop rate for outgoing UDP messages is {UDP_DROP_RATE}")


def udp_socket(bind_to: Address | int = Address.any_local_port()) -> socket.socket:
    if isinstance(bind_to, int):
        bind_to = Address.localhost(bind_to)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if bind_to is not None:
        sock.bind(bind_to.as_tuple())
        logger.debug(f"Bind UDP socket to {sock.getsockname()}")
    return sock


def udp_send(sock: socket.socket, address:Address, payload: bytes | str) -> int:
    '''
    Sends a message to a remote peer over UDP.

    Args:
        - sock (socket.socket): The socket to use for sending.
        - address (Address): The address of the remote peer.
        - payload (bytes | str): The message to send.

    Returns:
        - int: The number of bytes sent.
    '''
    try:
        if sock._closed:
            raise OSError("Socket is closed")
        if isinstance(payload, str):
            payload = payload.encode()
        if len(payload) > THRESHOLD_DGRAM_SIZE:
            raise ValueError(f"Payload size must be less than {THRESHOLD_DGRAM_SIZE} bytes ({THRESHOLD_DGRAM_SIZE / 1024} KiB)")
        if random.uniform(0, 1) < UDP_DROP_RATE:
            result = len(payload)
            logger.warn(f"Pretend to send {result} bytes to {address}: {payload}")
        else:
            result = sock.sendto(payload, address.as_tuple())
            logger.debug(f"Sent {result} bytes to {address}: {payload}")
        return result
    except OSError as e:
        logger.error(e)
        raise e


def udp_receive(sock: socket.socket, decode=True) -> tuple[str | bytes, Address]:
    '''
    Receives a message from a remote peer over UDP.

    Args:
        - sock (socket.socket): The socket to use for receiving.
        - decode (bool): Whether to decode the payload from bytes to a string.

    Returns:
        - tuple[str | bytes, Address]: The payload and the address of the remote peer.
    '''
    try:
        if sock._closed:
            return None, None
        payload, address = sock.recvfrom(THRESHOLD_DGRAM_SIZE)
        address = Address(*address)
        logger.debug(f"Received {len(payload)} bytes from {address}: {payload}")
        if decode:
            payload = payload.decode()
        return payload, address
    except OSError as e:
        if sock._closed:
            return None, None
        logger.error(e)
        raise e


class Session(Session):
    """
    Represents a UDP session with a remote peer.

    This class manages communication over UDP with a specific remote address,
    handling sending and receiving of messages.

    Attributes:
        - remote_address (Address): The address of the remote peer.
        - local_address (Address): The local socket address.

    """
    def __init__(self,
                 socket: socket.socket,
                 remote_address: Address | tuple,
                 first_message: str | bytes = None):
        assert socket is not None, "Socket must not be None"
        self._socket = socket
        assert remote_address is not None, "Remote address must not be None"
        self._remote_address = Address(*remote_address) if isinstance(remote_address, tuple) else remote_address
        self._received_messages = 0 if first_message is None else 1
        self._first_message = first_message

    @property
    def remote_address(self):
        return self._remote_address

    @property
    def local_address(self):
        return Address(*self._socket.getsockname())

    def send(self, payload: bytes | str):
        '''
        Sends a message to the remote peer.

        Args:
            payload (bytes | str): The message to send.

        Returns:
            int: The number of bytes sent.
        '''
        return udp_send(self._socket, self.remote_address, payload)

    def receive(self, decode=True):
        if self._first_message is not None:
            payload = self._first_message
            if decode and isinstance(payload, bytes):
                payload = payload.decode()
            self._first_message = None
            return payload
        payload, address = udp_receive(self._socket, decode)
        if address is not None:
            if self._received_messages == 0:
                self._remote_address = address
            assert address.equivalent_to(self.remote_address), f"Received packet from unexpected party {address}"
            return payload
        return None

    def close(self):
        self._socket.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class Server(Server):
    def __init__(self, port: int):
        self._address = Address.local_port_on_any_interface(port)
        self._socket = udp_socket(self._address)

    def listen(self) -> Session:
        payload, address = udp_receive(self._socket, True)
        return Session(
            socket=udp_socket(),
            remote_address=address,
            first_message=payload
        )

    def receive(self, decode=True) -> tuple[str | bytes, Address]:
        return udp_receive(self._socket, decode)

    def send(self, address: Address, payload: bytes | str):
        return udp_send(self._socket, address, payload)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        self._socket.close()


class Client(Session):
    def __init__(self, remote_address: Address):
        super().__init__(udp_socket(), remote_address)

    def connect(self):
        pass
