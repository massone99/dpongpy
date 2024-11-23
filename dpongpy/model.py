from pygame.math import Vector2
from .log import logger
from dataclasses import dataclass, field
from random import Random
from enum import Enum


class Direction(Enum):
    NONE = Vector2(0, 0)
    LEFT = Vector2(-1, 0)
    UP = Vector2(0, -1)
    RIGHT = Vector2(1, 0)
    DOWN = Vector2(0, 1)

    def __repr__(self):
        return f'<{type(self).__name__}.{self.name}>'

    def __str__(self):
        return repr(self)[1:-1]

    @property
    def is_vertical(self) -> bool:
        return self.value.x == 0 and self.value.y != 0

    @property
    def is_horizontal(self) -> bool:
        return self.value.y == 0 and self.value.x != 0

    @classmethod
    def values(cls) -> list['Direction']:
        return list(cls.__members__.values())


# noinspection PyUnresolvedReferences
class Sized:

    @property
    def width(self) -> float:
        return self.size.x

    @property
    def height(self) -> float:
        return self.size.y


# noinspection PyUnresolvedReferences
class Positioned:

    @property
    def x(self) -> float:
        return self.position.x

    @property
    def y(self) -> float:
        return self.position.y


@dataclass
class Rectangle(Sized, Positioned):
    top_left: Vector2
    bottom_right: Vector2

    def __post_init__(self):
        fst, snd = Vector2(self.top_left), Vector2(self.bottom_right)
        self.top_left = Vector2(min(fst.x, snd.x), min(fst.y, snd.y))
        self.bottom_right = Vector2(max(fst.x, snd.x), max(fst.y, snd.y))

    @property
    def top(self) -> float:
        return self.top_left.y

    @property
    def bottom(self) -> float:
        return self.bottom_right.y

    @property
    def left(self) -> float:
        return self.top_left.x

    @property
    def right(self) -> float:
        return self.bottom_right.x

    @property
    def top_right(self) -> Vector2:
        return Vector2(self.right, self.top)

    @property
    def bottom_left(self) -> Vector2:
        return Vector2(self.left, self.bottom)

    @property
    def corners(self) -> list[Vector2]:
        return [self.top_left, self.top_right, self.bottom_right, self.bottom_left]

    @property
    def size(self) -> Vector2:
        return self.bottom_right - self.top_left

    @property
    def position(self) -> Vector2:
        return (self.top_left + self.bottom_right) / 2

    def overlaps(self, other: 'Rectangle') -> bool:
        return self.left <= other.right \
            and self.right >= other.left \
            and self.top <= other.bottom \
            and self.bottom >= other.top

    def is_inside(self, other) -> bool:
        return self in other

    def __contains__(self, other) -> bool:
        if isinstance(other, Rectangle):
            return other.top_left in self and other.bottom_right in self
        else:
            x, y = other
            return self.left <= x <= self.right and self.top <= y <= self.bottom

    def intersection_with(self, other: 'Rectangle') -> 'Rectangle':
        if self.overlaps(other):
            return Rectangle(
                Vector2(
                    max(self.left, other.left),
                    max(self.top, other.top)
                ),
                Vector2(
                    min(self.right, other.right),
                    min(self.bottom, other.bottom)
                )
            )
        return None

    def hits(self, other: 'Rectangle') -> dict[Direction, float]:
        result = dict()
        intersection = self.intersection_with(other)
        if intersection is not None:
            tl, tr, br, bl = tuple([corner in self for corner in other.corners])
            if br and not(tl or tr or bl):
                result[Direction.UP] = intersection.height
                result[Direction.LEFT] = intersection.width
            elif bl and not(tr or tl or br):
                result[Direction.UP] = intersection.height
                result[Direction.RIGHT] = intersection.width
            elif tr and not(bl or br or tl):
                result[Direction.DOWN] = intersection.height
                result[Direction.LEFT] = intersection.width
            elif tl and not(br or bl or tr):
                result[Direction.DOWN] = intersection.height
                result[Direction.RIGHT] = intersection.width
            elif (tl and tr and not (bl or br)) or (self.top <= other.top <= self.bottom < other.bottom):
                result[Direction.DOWN] = intersection.height
            elif (bl and br and not (tl or tr)) or (other.top < self.top <= other.bottom <= self.bottom):
                result[Direction.UP] = intersection.height
            elif (tl and bl and not (tr or br)) or (self.left <= other.left <= self.right < other.right):
                result[Direction.RIGHT] = intersection.width
            elif (tr and br and not (tl or bl)) or (other.left < self.left <= other.right <= self.right):
                result[Direction.LEFT] = intersection.width
            else:
                raise ValueError("Invalid collision, this is likely a bug")
        return result


class GameObject(Sized, Positioned):
    def __init__(self, size, position=None, speed=None, name=None):
        self._size = Vector2(size)
        self._position = Vector2(position) if position is not None else Vector2()
        self._speed = Vector2(speed) if speed is not None else Vector2()
        self.name = name or self.__class__.__name__.lower()

    def __eq__(self, other):
        return isinstance(other, type(self)) and \
            self.name == other.name and \
            self.size == other.size and \
            self.position == other.position and \
            self.speed == other.speed

    def __hash__(self):
        return hash((type(self), self.name, self.size, self.position, self.speed))

    def __repr__(self):
        return f'<{type(self).__name__}(id={id(self)}, name={self.name}, size={self.size}, position={self.position}, speed={self.speed})>'

    def __str__(self):
        return f'{self.name}#{id(self)}'

    @property
    def size(self) -> Vector2:
        return self._size

    @size.setter
    def size(self, value: Vector2):
        old = self._size
        self._size = Vector2(value)
        if old is not None and old != self._size:
            logger.debug(f"{self} resized: {old} -> {self._size}")

    @property
    def position(self) -> Vector2:
        return self._position

    @position.setter
    def position(self, value: Vector2):
        old = self._position
        self._position = Vector2(value)
        if old is not None and old != self._position:
            logger.debug(f"{self} moves: {old} -> {self._position}")

    @property
    def speed(self) -> Vector2:
        return self._speed

    @speed.setter
    def speed(self, value: Vector2):
        old = self._speed
        self._speed = Vector2(value)
        if old is not None and old != self._speed:
            logger.debug(f"{self} accelerates: {old} -> {self._speed}")

    @property
    def bounding_box(self) -> Rectangle:
        half_size = self.size / 2
        return Rectangle(self.position - half_size, self.position + half_size)

    def update(self, delta_time: float):
        self.position = self.position + self.speed * delta_time

    def override(self, other: 'GameObject'):
        assert isinstance(other, type(self)) and other.name == self.name, f"Invalid override: {other} -> {self}"
        self.size = other.size
        self.position = other.position
        self.speed = other.speed


for method_name in ['overlaps', 'is_inside', '__contains__', 'intersection_with', 'hits']:
    def method(self: GameObject, other: GameObject | Rectangle):
        if isinstance(other, GameObject):
            other = other.bounding_box
        return getattr(Rectangle, method_name)(self.bounding_box, other)
    setattr(GameObject, method_name, method)


class Ball(GameObject):
    pass


class Paddle(GameObject):
    _admissible_directions = set(Direction.values()) - {Direction.NONE}

    def __init__(self, size, side: Direction, position=None, speed=None, name=None):
        assert isinstance(side, Direction) and side in self._admissible_directions, f"Invalid direction {side}"
        super().__init__(size, position, speed, name or "paddle_" + side.name.lower())
        self.side = side

    def __repr__(self):
        return super().__repr__().replace(')>', f", side={self.side})>")

    def __hash__(self):
        return hash((super().__hash__(), self.side))

    def __eq__(self, other):
        return super().__eq__(other) and self.side == other.side

    def override(self, other: GameObject):
        super().override(other)
        self.side = other.side


@dataclass
class Config:
    paddle_ratio: Vector2 = field(default_factory=lambda: Vector2(0.01, 0.1))
    ball_ratio: float = 0.05
    ball_speed_ratio: float = 0.2
    paddle_speed_ratio: float = 0.2
    paddle_padding: float = 0.05


@dataclass
class Table(Sized):
    size: Vector2
    borders: dict[Direction, GameObject] = field(init=False)

    def __post_init__(self):
        borders = dict()
        borders[Direction.UP] = Rectangle((-self.width, 0), (self.width * 2, -self.height))
        borders[Direction.DOWN] = Rectangle((-self.width, self.height), (self.width * 2, self.height * 2))
        borders[Direction.LEFT] = Rectangle((0, -self.height), (-self.width, self.height * 2))
        borders[Direction.RIGHT] = Rectangle((self.width, -self.height), (self.width * 2, self.height * 2))
        self.borders = dict()
        for dir, rect in borders.items():
            self.borders[dir] = GameObject(
                size=rect.size,
                position=rect.position,
                name=f"border_{dir.name.lower()}"
            )

class Pong(Sized):
    def __init__(self, size, config=None, paddles=None, random=None):
        self.size = Vector2(size)
        self.config = config or Config()
        self.random = random or Random()
        self.ball = None
        self.reset_ball()
        self.table = Table(self.size)
        self.updates = 0
        self.time = 0
        if paddles is None or len(paddles) == 0:
            logger.info("paddles is None")
            paddles = (Direction.LEFT, Direction.RIGHT)
        else:
            logger.info("paddles not none")
            logger.info(paddles)
        self.paddles = [paddle for paddle in paddles if isinstance(paddle, Paddle)]
        self._init_paddles((side for side in paddles if isinstance(side, Direction)))

    @property
    def paddles(self) -> list[Paddle]:
        return list(self._paddles.values())

    def __repr__(self):
        return (f'<{type(self).__name__}('
                f'id={id(self)}, '
                f'size={self.size}, '
                f'time={self.time}, '
                f'updates={self.updates}, '
                f'config={self.config}'
                f'ball={repr(self.ball)}, '
                f'paddles={self.paddles}, '
                f')>')

    @paddles.setter
    def paddles(self, paddles):
        self._paddles = {}
        for paddle in paddles:
            assert isinstance(paddle, Paddle), f"Invalid paddle: {paddle}"
            self._paddles[paddle.side] = paddle

    @property
    def _hittable_objects(self) -> list[GameObject]:
        return self.paddles + list(self.table.borders.values())

    def reset_ball(self, speed: Vector2 = None):
        min_dimension = min(*self.size)
        ball_size = Vector2(min_dimension * self.config.ball_ratio)
        if self.ball is None:
            self.ball = Ball(size=ball_size, position=self.size / 2)
        else:
            self.ball.size = ball_size
            self.ball.position = self.size / 2
        if speed is None:
            polar_speed = (min_dimension * self.config.ball_speed_ratio, self.random.uniform(0, 360))
            self.ball.speed = Vector2.from_polar(polar_speed)
        else:
            self.ball.speed = Vector2(speed)

    def add_paddle(self, side: Direction, paddle: Paddle = None):
        assert side is not None and side != Direction.NONE, "Invalid side"
        if side in self._paddles:
            raise ValueError(f"Paddle one side {side} already exists")
        if paddle is None:
            paddle_ratio = self.config.paddle_ratio
            if side.is_vertical:
                paddle_ratio = (paddle_ratio.y, paddle_ratio.x)
            paddle_size = self.size.elementwise() * paddle_ratio
            padding = self.width * self.config.paddle_padding + paddle_size.x / 2 if side.is_horizontal \
                else self.height * self.config.paddle_padding + paddle_size.y / 2
            if side == Direction.UP:
                position = Vector2(self.width / 2, padding)
            elif side == Direction.RIGHT:
                position = Vector2(self.width - padding, self.height / 2)
            elif side == Direction.DOWN:
                position = Vector2(self.width / 2, self.height - padding)
            else:
                position = Vector2(padding, self.height / 2)
            paddle = Paddle(size=paddle_size, side=side, position=position)
        self._paddles[side] = paddle
        logger.debug(f"Added paddle {paddle} to {self} on side {paddle.side.name}")

    def paddle(self, side: Direction):
        if side in self._paddles:
            return self._paddles[side]
        else:
            raise KeyError(f"No such a paddle: {side}")

    def has_paddle(self, side: Direction):
        return side in self._paddles

    def remove_paddle(self, side: Direction):
        if side in self._paddles:
            del self._paddles[side]
            logger.debug(f"Removed paddle from {self} on side {side}")
        else:
            raise KeyError(f"No such a paddle: {side}")

    def _init_paddles(self, sides):
        sides = set(sides) if sides is not None else set()
        for side in sides:
            self.add_paddle(side)

    def update(self, delta_time: float):
        self.updates += 1
        self.time += delta_time
        logger.debug(f"Update {self.updates} (time: {self.time})")
        self.ball.update(delta_time)
        for paddle in self.paddles:
            paddle.update(delta_time)
        self._handle_collisions(self.ball, self._hittable_objects)
        for paddle in self.paddles:
            self._handle_collisions(paddle, self.table.borders.values())

    def _handle_collisions(self, subject, objects):
        for hittable in objects:
            hits = subject.hits(hittable)
            for direction, delta in hits.items():
                logger.debug(f"{subject} hits {hittable} in direction {direction.name}, overlap is {delta}")
                if delta > 0.0:
                    subject.position = subject.position + direction.value * -delta
                    if direction.is_horizontal:
                        subject.speed = Vector2(-subject.speed.x, subject.speed.y)
                    if direction.is_vertical:
                        subject.speed = Vector2(subject.speed.x, -subject.speed.y)

    def move_paddle(self, paddle: int | Direction, direction: Direction):
        if isinstance(paddle, Direction) and paddle in self._paddles:
            selected = self._paddles[paddle]
        elif isinstance(paddle, int) and paddle in range(len(self.paddles)):
            selected = self.paddles[0]
        else:
            raise KeyError("No such a paddle: " + str(paddle))
        if selected.side.is_horizontal and direction.is_vertical:
            selected.speed = direction.value * self.height * self.config.paddle_speed_ratio
        elif selected.side.is_vertical and direction.is_horizontal:
            selected.speed = direction.value * self.width * self.config.paddle_speed_ratio
        elif direction == Direction.NONE:
            selected.speed = direction.value
        else:
            logger.debug(f"Ignored attempt to move {paddle} in {direction}")

    def stop_paddle(self, paddle: int | Direction):
        self.move_paddle(paddle, Direction.NONE)

    def override(self, other: 'Pong'):
        if self is other:
            return
        logger.debug(f"Overriding Pong status")
        self.size = other.size
        self.config = other.config
        self.ball.override(other.ball)
        self.table = other.table
        self.updates = other.updates
        self.time = other.time
        my_paddles = set((paddle.side for paddle in self.paddles))
        other_paddles = set((paddle.side for paddle in other.paddles))
        added = other_paddles - my_paddles
        added = {p: other._paddles[p] for p in added}
        removed = my_paddles - other_paddles
        removed = {p: self._paddles[p] for p in removed}
        common = my_paddles & other_paddles
        common = {p: other._paddles[p] for p in common}
        for side, paddle in added.items():
            self.add_paddle(side, paddle)
        for side, paddle in removed.items():
            self.remove_paddle(side)
        for side, paddle in common.items():
            self.paddle(side).override(other.paddle(side))
        return added, removed
