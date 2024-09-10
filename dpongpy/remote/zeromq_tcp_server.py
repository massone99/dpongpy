from typing import Optional, Tuple
import zmq
import threading

class ZeroMQServer:
    def __init__(self, port: int):
        self.port = port
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.ROUTER)
        self.socket.bind(f"tcp://*:{self.port}")
        self.running = False
        self.receive_thread = None
        self.peers = set()

    def start(self):
        self.running = True
        self.receive_thread = threading.Thread(target=self._receive_loop)
        self.receive_thread.start()

    def stop(self):
        self.running = False
        if self.receive_thread:
            self.receive_thread.join()
        self.close()

    def send(self, message: str, client_id: str):
        self.socket.send_multipart([client_id.encode('utf-8'), b'', message.encode('utf-8')])

    def receive(self) -> Tuple[Optional[str], Optional[str]]:
        try:
            message_parts = self.socket.recv_multipart(flags=zmq.NOBLOCK)
            if len(message_parts) < 3:
                return None, None
            client_id, delimiter, payload = message_parts
            return payload.decode('utf-8'), client_id.decode('utf-8')
        except zmq.Again:
            return None, None
        except Exception as e:
            print(f"Error in receive: {e}")
            return None, None

    def _receive_loop(self):
        while self.running:
            message, client_id = self.receive()
            if message is not None:
                if client_id not in self.peers:
                    self.peers.add(client_id)
                    print(f"New client connected: {client_id}")
                print(f"Received message from ({client_id}): {message}")
                self.handle_message(message, client_id)

    def handle_message(self, message: str, client_id):
        # Example message handling
        response = f"Server received: {message}"
        self.send(response, client_id)

        # Check for quit message
        if message.lower() == 'quit':
            self.send("_quit_", client_id)
            self.peers.remove(client_id)
            print(f"Client disconnected: {client_id}")

    def close(self):
        self.socket.close()
        self.context.term()

    def broadcast(self, message: str):
        for client_id in self.peers:
            self.send(message, client_id)

# Example usage
server = ZeroMQServer(5555)
server.start()

try:
    while True:
        msg = input("Enter a message to broadcast (or 'quit' to stop the server): \n")
        if msg.lower() == 'quit':
            break
        server.broadcast(msg)
except KeyboardInterrupt:
    print("Server interrupted")
finally:
    server.stop()
    print("Server stopped")
