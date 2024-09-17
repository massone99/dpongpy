from typing import Optional
from dpongpy.model import Pong, Config, Direction
from dpongpy.controller.local import ActionMap
import pygame
from dataclasses import dataclass, field


@dataclass
class Settings:
    config: Config = field(default_factory=Config)
    debug: bool = False
    size: tuple = (800, 600)
    fps: int = 60
    host: Optional[str] = None
    port: Optional[int] = None
    initial_paddles: tuple[Direction, Direction] = (Direction.LEFT, Direction.RIGHT)
    comm_technology: str = "web_sockets"

class PongGame:
    def __init__(self, settings: Settings = None):
        self.settings = settings or Settings()
        self.pong = Pong(
            size=self.settings.size,
            config=self.settings.config,
            paddles=self.settings.initial_paddles
        )
        self.dt = None
        self.view = self.create_view()
        self.clock = pygame.time.Clock()
        self.running = True
        self.controller = self.create_controller(settings.initial_paddles)

    def create_view(self):
        '''
        Creates
        '''
        from dpongpy.view import ScreenPongView
        return ScreenPongView(self.pong, debug=self.settings.debug)

    def create_controller(game, paddle_commands: dict[Direction, ActionMap]):
        from dpongpy.controller.local import PongLocalController

        class Controller(PongLocalController):
            def __init__(self, paddle_commands):
                super().__init__(game.pong, paddle_commands)

            def on_game_over(this, _):
                game.stop()

        return Controller(paddle_commands)

    def before_run(self):
        pygame.init()

    def after_run(self):
        pygame.quit()

    def at_each_run(self):
        pygame.display.flip()

    def run(self):
        try:
            self.dt = 0
            self.before_run()
            while self.running:
                self.controller.handle_inputs(self.dt)
                self.controller.handle_events()
                self.view.render()
                self.at_each_run()
                self.dt = self.clock.tick(self.settings.fps) / 1000
        finally:
            self.after_run()

    def stop(self):
        self.running = False


def main(settings = None):
    if settings is None:
        settings = Settings()
    PongGame(settings).run()
