import random
import string
import zmq

class ZeroMQClient:
    def __init__(self, server_address):
        # Create a ZeroMQ context
        self.context = zmq.Context()
        # Create a DEALER socket
        self.socket = self.context.socket(zmq.DEALER)
        # Set a random identity for this client
        self.identity = f"client-{''.join(random.choices(string.ascii_lowercase + string.digits, k=8))}"
        self.socket.setsockopt(zmq.IDENTITY, self.identity.encode('utf-8'))
        # Connect the socket to the server
        self.socket.connect(server_address)

    def send(self, message):
        # Send the message to the server
        self.socket.send_multipart([b'', message.encode('utf-8')])

    def receive(self):
        # Receive the server's reply
        _, reply = self.socket.recv_multipart()
        return reply.decode('utf-8')

    def close(self):
        self.socket.close()
        self.context.term()

# Example usage

client = ZeroMQClient("tcp://localhost:5555")

# Send a message to the server
print("Sending message to server...")
client.send("Hello, Server!")
print("Message sent.")

# Receive a reply from the server
reply = client.receive()
print(f"Received reply from server: {reply}")

# Clean up
client.close()
