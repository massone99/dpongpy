from typing import Optional
from dpongpy.model import Pong, Config, Direction
from dpongpy.controller.local import ActionMap, PongLocalController as PongController
import pygame
from dataclasses import dataclass, field
import logging
import traceback


@dataclass
class Settings:
    config: Config = field(default_factory=Config)
    debug: bool = False
    size: tuple = (800, 600)
    fps: int = 60
    host: Optional[str] = None
    port: Optional[int] = None
    # i guess they are the lines in which each of the paddles can move
    # LEFT refers to the left side of the screen and RIGHT to the right one
    initial_paddles: tuple[Direction, Direction] = (Direction.LEFT, Direction.RIGHT)


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

    # def before_run(self):
    #     pygame.init()

    def before_run(self):
        logging.info("Initializing Pygame...")
        try:
            pygame.init()
            logging.info("Pygame initialized successfully")
        except pygame.error as e:
            logging.error(f"Failed to initialize Pygame: {e}")
            self.running = False
        except Exception as e:
            logging.error(f"Unexpected error during Pygame initialization: {e}")
            self.running = False

        # Check if display module is working
        if self.running:
            try:
                pygame.display.init()
                logging.info("Pygame display module initialized")
            except pygame.error as e:
                logging.error(f"Failed to initialize Pygame display: {e}")
                self.running = False

        # Try to set the display mode
        if self.running:
            try:
                pygame.display.set_mode(self.settings.size)
                logging.info(f"Display mode set to {self.settings.size}")
            except pygame.error as e:
                logging.error(f"Failed to set display mode: {e}")
                self.running = False

    def after_run(self):
        pygame.quit()

    def at_each_run(self):
        pygame.display.flip()

    # def run(self):
    #     try:
    #         self.dt = 0
    #         self.before_run()
    #         while self.running:
    #             self.controller.handle_inputs(self.dt)
    #             self.controller.handle_events()
    #             self.view.render()
    #             self.at_each_run()
    #             self.dt = self.clock.tick(self.settings.fps) / 1000
    #     finally:
    #         self.after_run()

    def run(self):
        try:
            self.dt = 0
            self.before_run()
            if not self.running:
                logging.warning("Initialization failed, exiting...")
                return

            logging.info("Entering main game loop")
            while self.running:
                try:
                    logging.debug("Handling inputs")
                    self.controller.handle_inputs(self.dt)

                    logging.debug("Handling events")
                    self.controller.handle_events()

                    logging.debug("Rendering view")
                    self.view.render()

                    logging.debug("Executing at_each_run")
                    self.at_each_run()

                    self.dt = self.clock.tick(self.settings.fps) / 1000
                    logging.debug(f"Frame completed. dt: {self.dt}")
                except Exception as e:
                    logging.error(f"Error in game loop: {e}")
                    logging.error(traceback.format_exc())
                    self.running = False
        except Exception as e:
            logging.error(f"Unexpected error in run method: {e}")
            logging.error(traceback.format_exc())
        finally:
            logging.info("Exiting game loop")
            self.after_run()

    def stop(self):
        self.running = False


def main(settings = None):
    if settings is None:
        settings = Settings()
    PongGame(settings).run()
