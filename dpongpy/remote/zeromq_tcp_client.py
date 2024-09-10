import queue
import socket
import threading

import zmq


class ZeroMQClient:
    def __init__(self, server_address):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.DEALER)
        self.ip = socket.gethostbyname(socket.gethostname())
        self.port = self.socket.bind_to_random_port("tcp://*")
        self.identity = f"{self.ip}:{self.port}"
        self.socket.setsockopt(zmq.IDENTITY, self.identity.encode("utf-8"))
        self.socket.connect(server_address)

        self.running = False
        self.receive_thread = None
        self.message_queue = queue.Queue()

    def start(self):
        self.running = True
        self.receive_thread = threading.Thread(target=self._receive_loop)
        self.receive_thread.start()

    def stop(self):
        self.running = False
        if self.receive_thread:
            self.receive_thread.join()
        self.close()

    def send(self, message):
        self.socket.send_multipart([b"", message.encode("utf-8")])

    def handle_message(self, sender, message):
        self.message_queue.put(message)
        print(f"[{sender}] Received: {message}")

    def _receive_loop(self):
        while self.running:
            try:
                multiparts = self.socket.recv_multipart(flags=zmq.NOBLOCK)
                if len(multiparts) == 3:
                    _, server_id, payload = multiparts[0], multiparts[1], multiparts[2]
                    server_id = server_id.decode("utf-8")
                    message = payload.decode("utf-8")
                    if message == "_quit_":
                        print("Received quit message from server.")
                        self.running = False
                    else:
                        self.handle_message(server_id, message)
                else:
                    print(f"Unexpected message format: {multiparts}")
            except zmq.Again:
                pass  # No message available
            except Exception as e:
                print(f"Error in receive loop: {e}")

    def get_message(self, timeout=None):
        try:
            return self.message_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def close(self):
        self.socket.close()
        self.context.term()


client = ZeroMQClient("tcp://localhost:5555")
client.start()

try:
    print("Enter message to send (or 'quit' to exit):\n ")
    while client.running:
        message = input()
        if message.lower() == "quit":
            client.stop()
            break
        client.send(message)

except KeyboardInterrupt:
    print("Interrupted by user")
finally:
    client.stop()
