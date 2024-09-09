from dpongpy.remote import Address, Server
import zmq

def zmq_receive(socket, decode=True) -> tuple[str | bytes, str]:
    try:
        if socket._closed:
            return None, None

        # Receive message parts using ROUTER socket
        message_parts = socket.recv_multipart()

        # ROUTER socket receives: [identity, empty delimiter, payload]
        if len(message_parts) < 3:
            return None, None

        client_id, delimiter, payload = message_parts

        # Decode the payload if requested
        if decode and isinstance(payload, bytes):
            payload = payload.decode('utf-8')

        # # Create Address object with client identity
        # address = Address(client_id.decode('utf-8'))


        return payload, client_id
    except Exception as e:
        print(f"Error: {e}")
        return None, None

class ZeroMQServer():
    def __init__(self, port):
        self.port = port
        # Create a ZeroMQ context
        self.context = zmq.Context()
        # Create a ROUTER socket
        self.socket = self.context.socket(zmq.ROUTER)
        # Bind the socket to the specified port
        self.socket.bind(f"tcp://*:{self.port}")

    def send(self, message, address):
        # ROUTER socket sends: [identity, empty delimiter, payload]
        client_id = address.encode('utf-8')
        self.socket.send_multipart([client_id, b'', message.encode('utf-8')])

    def receive(self):
        return zmq_receive(self.socket)

    def close(self):
        self.socket.close()
        self.context.term()



server = ZeroMQServer(5555)
while True:
    message, client_id = server.receive()
    client_id = client_id.decode('utf-8')
    if message is not None:
        # print(f"Received message from {client_id}: {message}")
        server.send(f"Received message from {client_id}: {message}", client_id)
    else:
        print("No message received")
