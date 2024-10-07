from dpongpy import Settings
from dpongpy.controller import ControlEvent
from dpongpy.model import Direction, Pong
from dpongpy.view import PongView


class IRemotePongCoordinator:
    def __init__(self, settings: Settings = None):
        pass

    def initialize(self):
        pass

    def start_server(self):
        raise NotImplementedError("Must be implemented by subclasses")

    def broadcast_to_all_peers(self, message):
        raise NotImplementedError("Must be implemented by subclasses")

    def create_view(coordinator):
        from dpongpy.controller.local import ControlEvent
        from dpongpy.view import ShowNothingPongView

        class SendToPeersPongView(ShowNothingPongView):
            def render(self):
                event = coordinator.controller.create_event(
                    ControlEvent.TIME_ELAPSED, dt=coordinator.dt, status=self._pong
                )
                coordinator._broadcast_to_all_peers(event)

        return SendToPeersPongView(coordinator.pong)

    def create_controller(coordinator, paddle_commands):
        from dpongpy.controller.local import InputHandler, PongEventHandler

        class Controller(PongEventHandler, InputHandler):
            def __init__(self, pong: Pong):
                PongEventHandler.__init__(self, pong)

            def on_player_join(self, pong: Pong, paddle_index: int | Direction):
                super().on_player_join(pong, paddle_index)
                pong.reset_ball()

            def on_player_leave(self, pong: Pong, paddle_index: Direction):
                if pong.has_paddle(paddle_index):
                    pong.remove_paddle(paddle_index)
                if len(pong.paddles) == 0:
                    self.on_game_over(pong)
                else:
                    pong.reset_ball()

            def on_game_over(self, pong: Pong):
                event = self.create_event(ControlEvent.GAME_OVER)
                coordinator._broadcast_to_all_peers(event)
                coordinator.stop()

            def handle_inputs(self, dt=None):
                self.time_elapsed(dt)

        return Controller(coordinator.pong)

    def before_run(self):
        pass

    def at_each_run(self):
        pass

    def after_run(self):
        pass

    @property
    def peers(self):
        raise NotImplementedError("Must be implemented by subclasses")

    @peers.setter
    def peers(self, value):
        raise NotImplementedError("Must be implemented by subclasses")

    def add_peer(self, peer: object):
        raise NotImplementedError("Must be implemented by subclasses")
