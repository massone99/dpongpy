import threading
from typing import Optional, Tuple
import zmq
from dpongpy.remote import Address, Server, Session
import binascii
import threading


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
        '''
        Represents the address of the remote peer.
        '''
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
        print("Trying to receive from", self.remote_address)
        # payload, address = self._socket.recv()
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
    """

    def __init__(self, remote_address: Address):
        socket = zmq.Context().socket(zmq.DEALER)
        super().__init__(socket, remote_address)
        self.connect()

    def connect(self):
        self._socket.connect(f"tcp://{self._remote_address[0]}:{self._remote_address[1]}")

class Server(Server):
    """
    A simple ZeroMQ server that listens for incoming messages
    and manages sessions with clients.
    """
    def __init__(self, port: int):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.ROUTER)
        self.socket.bind(f"tcp://127.0.0.1:{port}")  # Bind to localhost
        endpoint = self.socket.getsockopt_string(zmq.LAST_ENDPOINT)
        ip = endpoint.split("://")[1].split(":")[0]
        print(f"Server listening on IP: {ip}, Port: {port}")
        self.sessions = {}  # Dictionary to store client sessions

    def listen(self) -> ZeroMQSession:
        """
        Listens for incoming messages and returns a session for the first client.
        """
        message_parts = self.socket.recv_multipart()
        if len(message_parts) < 3:
            return None

        client_id, delimiter, message = message_parts
        client_id = client_id.decode("utf-8")
        message = message.decode("utf-8")

        # Create or retrieve the session
        if client_id not in self.sessions:
            print(f"New client connected: {client_id}")
            session = ZeroMQSession(self.context, client_id, self.socket)
            self.sessions[client_id] = session
        else:
            session = self.sessions[client_id]

        session._first_message = message  # Store the first message
        return session

    def receive(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Receives a message from any client and manages sessions.
        """
        try:
            message_parts = self.socket.recv_multipart()
            if len(message_parts) < 2:
                return None, None

            client_id, message = message_parts
            client_id_hex = binascii.hexlify(client_id).decode('ascii')

            # Create a new session if this is a new client
            if client_id_hex not in self.sessions:
                print(f"New client connected: {client_id_hex}")
                session = ZeroMQSession(self.socket, Address("", 0), None)  # Placeholder address
                self.sessions[client_id_hex] = session

            return message.decode("utf-8"), client_id_hex
        except zmq.Again:
            return None, None

    def send(self, client_id: str, payload: str):
        """
        Sends a message to a specific client.
        """
        if client_id in self.sessions:
            client_id_bytes = binascii.unhexlify(client_id)
            self.socket.send_multipart([client_id_bytes, payload.encode("utf-8")])
        else:
            print(f"[Server] Client {client_id} not found in the list: {list(self.sessions.keys())}")

    def close(self):
        """
        Closes the ZeroMQ server and terminates all sessions.
        """
        for session in self.sessions.values():
            session.send("_server_shutdown_")
        self.socket.close()
        self.context.term()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Example usage with context management
# with ZeroMQServer(5555) as server:
#     try:
#         while True:
#             msg = input(
#                 "Enter a message to broadcast (or 'quit' to stop the server): \n"
#             )
#             server.broadcast(msg)
#             if msg.lower() == ZeroMQServer.shutdown_message:
#                 break
#     except KeyboardInterrupt:
#         print("Server interrupted")
#     finally:
#         print("Server stopped")
