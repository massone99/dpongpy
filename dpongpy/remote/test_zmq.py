import time
from threading import Thread
from dpongpy.remote.zmq_impl import Server, Client, Address

def run_server():
    with Server(5555) as server:
        print("Server started, waiting for messages...")
        while True:
            message, client_id = server.receive()
            if message:
                print(f"Server received: {message} from {client_id}")
                server.send(client_id, f"Server received: {message}")
            if message == "STOP":
                break
    print("Server stopped")

def run_client():
    client = Client(Address("127.0.0.1", 5555))
    client.connect()

    # Send a message
    message = "Hello, Server!"
    print(f"Client sending: {message}")
    client.send(message)

    # Receive the response
    response = client.receive()
    print(f"Client received: {response}")

    # Send stop message
    client.send("STOP")
    client.close()

def main():
    # Start the server in a separate thread
    server_thread = Thread(target=run_server)
    server_thread.start()

    # Give the server a moment to start
    time.sleep(1)

    # Run the client
    run_client()

    # Wait for the server to stop
    server_thread.join()

main()
