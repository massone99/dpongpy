import socket
import threading
import sys
import zmq


class ZeroMQClient:
    def __init__(self, server_address):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.DEALER)
        self.identity = f"{socket.gethostbyname(socket.gethostname())}:{self.socket.bind_to_random_port('tcp://*')}"
        self.socket.setsockopt(zmq.IDENTITY, self.identity.encode("utf-8"))
        self.socket.connect(server_address)
        self.stop_event = threading.Event()
        self.receive_thread = threading.Thread(
            target=self._receive_loop, daemon=True)
        self.receive_thread.start()

    def stop(self):
        self.stop_event.set()
        self.receive_thread.join()
        self.socket.close()
        self.context.term()

    def send(self, message):
        self.socket.send_multipart([b"", message.encode("utf-8")])

    def _receive_loop(self):
        while not self.stop_event.is_set():
            try:
                multiparts = self.socket.recv_multipart(flags=zmq.NOBLOCK)
                if len(multiparts) == 3:
                    _, server_id, payload = multiparts
                    message = payload.decode("utf-8")
                    if message.lower() == "quit":
                        print("Received quit message. Exiting.")
                        self.stop_event.set()
                        print("stop event: ", self.stop_event.is_set())
                    else:
                        print(
                            f"[{server_id.decode('utf-8')}] Received: {message}")
            except zmq.Again:
                self.stop_event.wait(0.1)
            except Exception as e:
                print(f"Error in receive loop: {e}")


# Usage
client = ZeroMQClient("tcp://localhost:5555")
try:
    print("Enter message to send (or 'quit' to exit):")
    while not client.stop_event.is_set():
        print(f"client stop event: {client.stop_event.is_set()} ")
        message = input("Message: ")
        client.send(message)
    sys.exit()
except Exception:
    print("Exception incurred")
except KeyboardInterrupt:
    print("Interrupted by user")

# List active threads to ensure graceful shutdown
print("Active threads after shutdown:")
for thread in threading.enumerate():
    print(f"- {thread.name}")
