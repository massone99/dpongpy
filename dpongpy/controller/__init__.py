import pygame
from dpongpy.model import *
from dataclasses import dataclass
from enum import Enum


class ControlEvent(Enum):
    PLAYER_JOIN = pygame.event.custom_type()
    PLAYER_LEAVE = pygame.event.custom_type()
    GAME_START = pygame.event.custom_type()
    GAME_OVER = pygame.QUIT
    PADDLE_MOVE = pygame.event.custom_type()
    TIME_ELAPSED = pygame.event.custom_type()

    @classmethod
    def all(cls) -> set['ControlEvent']:
        return set(cls.__members__.values())

    @classmethod
    def all_types(cls) -> set['ControlEvent']:
        return {event.value for event in cls.all()}

    @classmethod
    def is_control_event(cls, event: pygame.event.Event) -> bool:
        return any(control_event.matches(event) for control_event in cls.all())

    @classmethod
    def by_value(cls, value: int) -> 'ControlEvent':
        for control_event in cls.all():
            if control_event.value == value:
                return control_event
        raise KeyError(f"{cls.__name__} with value {value} not found")

    def matches(self, event) -> bool:
        if isinstance(event, pygame.event.Event):
            return event.type == self.value
        elif isinstance(event, ControlEvent):
            return event == self
        elif isinstance(event, int):
            return event == self.value
        return False


class PlayerAction(Enum):
    MOVE_UP = 0
    MOVE_DOWN = 1
    MOVE_RIGHT = 2
    MOVE_LEFT = 3
    STOP = 4
    QUIT = 5

    @classmethod
    def all(cls) -> set['PlayerAction']:
        return set(cls.__members__.values())

    @classmethod
    def all_moves(cls) -> set['PlayerAction']:
        return {action for action in cls.all() if 'MOVE_' in action.name}

    def to_direction(self):
        if 'MOVE_' in self.name:
            return Direction[self.name.split('_')[1]]
        elif self == PlayerAction.STOP:
            return Direction.NONE
        return None


@dataclass(frozen=True)
class ActionMap:
    '''
    A mapping of keys to actions.
    '''
    move_up: int
    move_down: int
    move_left: int
    move_right: int
    quit: int = pygame.K_ESCAPE
    name: str = 'custom'

    def to_key_map(self):
        return {getattr(self, name): PlayerAction[name.upper()] for name in self.__annotations__ if name != 'name'}

    @classmethod
    def wasd(cls):
        return cls(pygame.K_w, pygame.K_s, pygame.K_a, pygame.K_d, name='wasd')

    @classmethod
    def ijkl(cls):
        return cls(pygame.K_i, pygame.K_k, pygame.K_j, pygame.K_l, name='ijkl')

    @classmethod
    def numpad(cls):
        return cls(pygame.K_KP8, pygame.K_KP2, pygame.K_KP4, pygame.K_KP6, name='numpad')

    @classmethod
    def arrows(cls):
        return cls(pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT, name='arrows')

    @classmethod
    def all_mappings(cls, list=False):
        mappings = [cls.wasd(), cls.arrows(), cls.ijkl(), cls.numpad()]
        if list:
            return mappings
        return {mapping.name: mapping for mapping in mappings}


def create_event(event: pygame.event.Event | ControlEvent, **kwargs):
    if isinstance(event, ControlEvent):
        event = pygame.event.Event(event.value, **kwargs)
    elif isinstance(event, pygame.event.Event) and event.dict != kwargs:
        data = event.dict
        data.update(kwargs)
        event = pygame.event.Event(event.type, data)
    return event


def post_event(event: pygame.event.Event | ControlEvent, **kwargs):
    event = create_event(event, **kwargs)
    pygame.event.post(event)
    return event


class InputHandler:
    INPUT_EVENTS = (pygame.KEYDOWN, pygame.KEYUP)

    def create_event(self, event: pygame.event.Event | ControlEvent, **kwargs):
        return create_event(event, **kwargs)

    def post_event(self, event: pygame.event.Event | ControlEvent, **kwargs):
        return post_event(event, **kwargs)

    def key_pressed(self, key: int):
        pass

    def key_released(self, key: int):
        pass

    def time_elapsed(self, dt: float):
        self.post_event(ControlEvent.TIME_ELAPSED, dt=dt)

    def handle_inputs(self, dt=None):
        pass


class EventHandler:
    GAME_EVENTS = tuple(ControlEvent.all_types())

    def __init__(self, pong: Pong):
        self._pong = pong

    def handle_events(self):
        for event in pygame.event.get(self.GAME_EVENTS):
            if ControlEvent.PLAYER_JOIN.matches(event):
                self.on_player_join(self._pong, **event.dict)
            elif ControlEvent.PLAYER_LEAVE.matches(event):
                self.on_player_leave(self._pong, **event.dict)
            elif ControlEvent.GAME_START.matches(event):
                self.on_game_start(self._pong)
            elif ControlEvent.GAME_OVER.matches(event):
                self.on_game_over(self._pong)
            elif ControlEvent.PADDLE_MOVE.matches(event):
                self.on_paddle_move(self._pong, **event.dict)
            elif ControlEvent.TIME_ELAPSED.matches(event):
                self.on_time_elapsed(self._pong, **event.dict)

    def on_player_join(self, pong: Pong, paddle_index: int | Direction):
        pass

    def on_player_leave(self, pong: Pong, paddle_index: int):
        pass

    def on_game_start(self, pong: Pong):
        pass

    def on_game_over(self, pong: Pong):
        pass

    def on_paddle_move(self, pong: Pong, paddle_index: int | Direction, direction: Direction):
        pass

    def on_time_elapsed(self, pong: Pong, dt: float):
        pass
