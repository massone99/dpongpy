from dpongpy.remote import Address, Session


class ZeroMQSession(Session):
    def __init__(
        self,
        socket: zmq.Socket,
        remote_address: Address,
        first_message: str | bytes = None,
    ):
        assert socket is not None, "Socket must not be None"
        self._socket = socket
        assert remote_address is not None, "Remote address must not be None"
        self._remote_address = remote_address
        self._received_messages = 0 if first_message is None else 1
        self._first_message = first_message

    @property
    def remote_address(self) -> Address:
        """
        Represents the address of the remote peer.
        """
        return self._remote_address

    @property
    def local_address(self) -> Address:
        return Address(*self._socket.getsockname())

    def send(self, payload: str | bytes) -> int:
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        return self._socket.send(payload)

    def receive(self, decode=True):
        if self._first_message is not None:
            payload = self._first_message
            if decode and isinstance(payload, bytes):
                payload = payload.decode()
            self._first_message = None
            return payload
        payload = self._socket.recv()
        return payload

    def close(self):
        self._socket.close(0)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        
class Client(ZeroMQSession):
    """
    A ZeroMQ client that connects to a server using the DEALER pattern.
    This class manages communication with the remote ZeroMQ server.
    Applies the DEALER pattern.
    """

    def __init__(self, remote_address: Address):
        socket = zmq.Context().socket(zmq.DEALER)
        super().__init__(socket, remote_address)
        self.connect()

    def connect(self):
        self._socket.connect(
            f"tcp://{self._remote_address[0]}:{self._remote_address[1]}"
        )