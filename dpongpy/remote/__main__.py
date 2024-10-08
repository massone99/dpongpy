from dpongpy.remote.comm.udp.udp import Server, Client, Session
import argparse
import threading
import queue

def arg_parser():
    ap = argparse.ArgumentParser()
    mode = ap.add_argument_group("mode")
    mode.add_argument("--mode", choices=['server', 'client'], help="Run the game in local or centralised mode")
    networking = ap.add_argument_group("networking")
    networking.add_argument("--host", help="Host to connect to", type=str, default="localhost")
    networking.add_argument("--port", help="Port to connect to", type=int, default=12345)
    game = ap.add_argument_group("misc")
    game.add_argument("--debug", help="Enable debug mode", action="store_true")
    return ap


class Echoer:
    def __init__(self, remote: Session | Server):
        # self._ingoing = threading.Queue()
        self._outgoing = queue.Queue()
        self._running = True
        self.is_server = isinstance(remote, Server)
        self._session = remote.listen() if isinstance(remote, Server) else remote
        self._thread_stdin_consumer = threading.Thread(target=self._consume_stdin)
        self._thread_remote_consumer = threading.Thread(target=self._consume_remote)
        self._thread_outgoing_propagator = threading.Thread(target=self._propagate_outgoing)
        self._threads = set(getattr(self, name) for name in dir(self) if name.startswith('_thread_'))

    @property
    def is_client(self):
        return not self.is_server

    def __enter__(self):
        '''
        Used to permit the usage of the with statement.
        It starts the threads and returns the object itself.
        '''
        for thread in self._threads:
            thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._thread_stdin_consumer.join()
        self._thread_outgoing_propagator.join()
        self._running = False
        self._thread_remote_consumer.join()
        self._session.close()

    def _consume_stdin(self):
        '''
        Reads from stdin and puts the input in the queue.
        '''
        while self._running:
            try:
                # puts input in the queue
                self._outgoing.put(input() + "\n")
            except EOFError:
                self._outgoing.put(b'')
                break

    def _consume_remote(self):
        '''
        Reads from the remote peer and prints the message.
        '''
        while self._running:
            # reads the message from the remote peer
            msg = self._session.receive()
            if len(msg) > 0:
                print(msg, end='', flush=True)
            else:
                break

    def _propagate_outgoing(self):
        '''
        Sends the messages in the queue to the remote peer.

        '''
        while self._running:
            msg = self._outgoing.get()
            self._session.send(msg)
            if len(msg) == 0:
                break


parser = arg_parser()
args = parser.parse_args()

if args.mode == 'server':
    server = Server(args.port)
    with Echoer(server):
        pass
elif args.mode == 'client':
    client = Client((args.host, args.port))
    with Echoer(client):
        pass
