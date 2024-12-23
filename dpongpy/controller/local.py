from typing import Iterable

from dpongpy.controller import *


def _normalize_commands(
        pong: Pong,
        paddles: dict[Direction, ActionMap] | Iterable[Direction] | None
) -> dict[Direction, ActionMap]:
    if paddles is dict:
        assert set(paddles.keys()) == {p.side for p in pong.paddles}, "All paddles must come with an ActionMap"
        return paddles
    if paddles is None:
        sides = [paddle.side for paddle in pong.paddles]
    else:
        assert set(paddles) == {p.side for p in pong.paddles}, "Paddles in pong must match paddles in commands"
        sides = list(paddles)
    sides.sort(key=lambda side: Direction.values().index(side))
    commands = ActionMap.all_mappings(list=True)
    return {side: command for side, command in zip(sides, commands)}


class PongInputHandler(InputHandler):
    def __init__(self, pong: Pong, paddles_commands: dict[Direction, ActionMap] = None):
        self._pong = pong
        self._paddles_commands = _normalize_commands(pong, paddles_commands)
        assert len(self._pong.paddles) == len(self._paddles_commands), "Number of paddles and commands must match"
        for side, keymap in self._paddles_commands.items():
            logger.info(f"Player {side.name} controls: {keymap.name}")

    def _get_paddle_actions(self, key: int) -> dict[Direction, PlayerAction]:
        result = dict()
        for side, paddle_commands in self._paddles_commands.items():
            key_map = paddle_commands.to_key_map()
            if key in key_map:
                result[side] = key_map[key]
        return result

    def key_pressed(self, key: int):
        for paddle_index, action in self._get_paddle_actions(key).items():
            if action in PlayerAction.all_moves():
                # Get the paddle's side and the action's direction
                paddle_side = paddle_index
                action_direction = action.to_direction()

                # Only post event if movement direction is valid for the paddle
                if (paddle_side.is_horizontal and action_direction.is_vertical) or \
                        (paddle_side.is_vertical and action_direction.is_horizontal):
                    self.post_event(ControlEvent.PADDLE_MOVE,
                                    paddle_index=paddle_index,
                                    direction=action_direction)
            elif action == PlayerAction.QUIT:
                self.post_event(ControlEvent.PLAYER_LEAVE, paddle_index=paddle_index)

    def key_released(self, key: int):
        for paddle_index, action in self._get_paddle_actions(key).items():
            if action in PlayerAction.all_moves():
                # Get the paddle's side and the action's direction
                paddle_side = paddle_index
                action_direction = action.to_direction()

                # Only post event if movement direction is valid for the paddle
                if (paddle_side.is_horizontal and action_direction.is_vertical) or \
                        (paddle_side.is_vertical and action_direction.is_horizontal):
                    self.post_event(ControlEvent.PADDLE_MOVE,
                                    paddle_index=paddle_index,
                                    direction=Direction.NONE)

    def handle_inputs(self, dt=None):
        # Handle one-time key press events
        for event in pygame.event.get(self.INPUT_EVENTS):
            if event.type == pygame.KEYDOWN:
                self.key_pressed(event.key)
            elif event.type == pygame.KEYUP:
                self.key_released(event.key)

        # Handle continuous key presses
        keys = pygame.key.get_pressed()
        for paddle in self._pong.paddles:
            paddle_commands = self._paddles_commands.get(paddle.side)
            if paddle_commands:
                # Check each movement key for this paddle
                if keys[paddle_commands.move_up]:
                    self.post_event(ControlEvent.PADDLE_MOVE,
                                  paddle_index=paddle.side,
                                  direction=Direction.UP)
                elif keys[paddle_commands.move_down]:
                    self.post_event(ControlEvent.PADDLE_MOVE,
                                  paddle_index=paddle.side,
                                  direction=Direction.DOWN)
                elif keys[paddle_commands.move_left]:
                    self.post_event(ControlEvent.PADDLE_MOVE,
                                  paddle_index=paddle.side,
                                  direction=Direction.LEFT)
                elif keys[paddle_commands.move_right]:
                    self.post_event(ControlEvent.PADDLE_MOVE,
                                  paddle_index=paddle.side,
                                  direction=Direction.RIGHT)

        if dt is not None:
            self.time_elapsed(dt)


class PongEventHandler(EventHandler):
    def on_player_join(self, pong: Pong, paddle_index: int | Direction):
        pong.add_paddle(paddle_index)

    def on_player_leave(self, pong: Pong, paddle_index: int):
        self.on_game_over(pong)

    def on_game_start(self, pong: Pong):
        pass

    def on_game_over(self, pong: Pong):
        pass

    def on_paddle_move(self, pong: Pong, paddle_index: int | Direction, direction: Direction):
        pong.move_paddle(paddle_index, direction)

    def on_time_elapsed(self, pong: Pong, dt: float):
        pong.update(dt)


class PongLocalController(PongInputHandler, PongEventHandler):
    def __init__(self, pong: Pong, paddles_commands: dict[Direction, ActionMap] = None):
        PongInputHandler.__init__(self, pong, paddles_commands)
        PongEventHandler.__init__(self, pong)
