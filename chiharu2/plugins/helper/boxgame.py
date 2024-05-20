from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeVar, List, Tuple, Generic, Any, Generator
import functools
from typing_extensions import Self

__all__ = ('IPos', 'Grid2D', 'Grid2DSquare', 'Grid2DHexagonH', 'Grid2DHexagonV', 'Grid3D',
           'IBox',
           'ISpace', 'ISpaceOverlap', 'ISpaceNoOverlap',
           'IBoxGame')

class IPos(ABC):
    '''Interface for position.'''
    class Directions:
        pass
    @abstractmethod
    def __add__(self, other):
        pass
    @abstractmethod
    def __iadd__(self, other):
        pass
    @abstractmethod
    def __sub__(self, other):
        pass
    @abstractmethod
    def __isub__(self, other):
        pass
    @abstractmethod
    def __bool__(self):
        pass
TPos = TypeVar('TPos', bound=IPos)

TGrid2D = TypeVar('TGrid2D', bound='Grid2D')
@dataclass(frozen=True, unsafe_hash=True, order=True)
class Grid2D(IPos):
    x: int
    y: int
    class Directions:
        pass
    def __add__(self, other):
        if not isinstance(other, Grid2D):
            return NotImplemented
        return self.__class__(self.x + other.x, self.y + other.y)
    def __iadd__(self, other):
        if not isinstance(other, Grid2D):
            return NotImplemented
        return self.__class__(self.x + other.x, self.y + other.y)
    def __sub__(self, other):
        if not isinstance(other, Grid2D):
            return NotImplemented
        return self.__class__(self.x - other.x, self.y - other.y)
    def __isub__(self, other):
        if not isinstance(other, Grid2D):
            return NotImplemented
        return self.__class__(self.x - other.x, self.y - other.y)
    def __mul__(self, other):
        if isinstance(other, int):
            return self.__class__(other * self.x, other * self.y)
    def __rmul__(self, other):
        if isinstance(other, int):
            return self.__class__(other * self.x, other * self.y)
        return NotImplemented
    def __imul__(self, other):
        if isinstance(other, int):
            return self.__class__(other * self.x, other * self.y)
        return NotImplemented
    def __floordiv__(self, other):
        if isinstance(other, int):
            return self.__class__(self.x // other, self.y // other)
        return NotImplemented
    def __ifloordiv__(self, other):
        if isinstance(other, int):
            return self.__class__(self.x // other, self.y // other)
        return NotImplemented
    def __neg__(self):
        return self.__class__(-self.x, -self.y)
    def __bool__(self):
        return self.x != 0 or self.y != 0
    def mag2(self) -> int:
        return self.dot(self)
    def mag(self) -> float:
        return self.mag2() ** 0.5
    def dot(self, other: Self):
        return self.x * other.x + self.y * other.y
    def toTuple(self):
        return (self.x, self.y)

class Grid2DSquare(Grid2D):
    class Directions(Grid2D.Directions):
        UP: 'Grid2DSquare'
        RIGHT: 'Grid2DSquare'
        DOWN: 'Grid2DSquare'
        LEFT: 'Grid2DSquare'
    def around(self) -> Generator[Self, Any, None]:
        for p in (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (-1, 1):
            yield self + Grid2DSquare(*p)
    def isAround(self, other: Self):
        return self.x - other.x in (-1, 0, 1) and self.y - other.y in (-1, 0, 1)
Grid2DSquare.Directions.UP = Grid2DSquare(0, -1)
Grid2DSquare.Directions.RIGHT = Grid2DSquare(1, 0)
Grid2DSquare.Directions.DOWN = Grid2DSquare(0, 1)
Grid2DSquare.Directions.LEFT = Grid2DSquare(-1, 0)

class Grid2DHexagonH(Grid2D):
    class Directions(Grid2D.Directions):
        UPLEFT: 'Grid2DHexagonH'
        UPRIGHT: 'Grid2DHexagonH'
        RIGHT: 'Grid2DHexagonH'
        DOWNRIGHT: 'Grid2DHexagonH'
        DOWNLEFT: 'Grid2DHexagonH'
        LEFT: 'Grid2DHexagonH'
Grid2DHexagonH.Directions.UPLEFT = Grid2DHexagonH(0, -1)
Grid2DHexagonH.Directions.UPRIGHT = Grid2DHexagonH(1, -1)
Grid2DHexagonH.Directions.RIGHT = Grid2DHexagonH(1, 0)
Grid2DHexagonH.Directions.LEFT = Grid2DHexagonH(-1, 0)
Grid2DHexagonH.Directions.DOWNRIGHT = Grid2DHexagonH(0, -1)
Grid2DHexagonH.Directions.DOWNLEFT = Grid2DHexagonH(-1, 1)

class Grid2DHexagonV(Grid2D):
    class Directions(Grid2D.Directions):
        UP: 'Grid2DHexagonV'
        UPRIGHT: 'Grid2DHexagonV'
        DOWN: 'Grid2DHexagonV'
        DOWNRIGHT: 'Grid2DHexagonV'
        DOWNLEFT: 'Grid2DHexagonV'
        UPLEFT: 'Grid2DHexagonV'
Grid2DHexagonV.Directions.UP = Grid2DHexagonV(0, -1)
Grid2DHexagonV.Directions.UPRIGHT = Grid2DHexagonV(1, -1)
Grid2DHexagonV.Directions.DOWNRIGHT = Grid2DHexagonV(1, 0)
Grid2DHexagonV.Directions.DOWN = Grid2DHexagonV(0, 1)
Grid2DHexagonV.Directions.DOWNLEFT = Grid2DHexagonV(-1, 1)
Grid2DHexagonV.Directions.UPLEFT = Grid2DHexagonV(-1, 0)

TGrid3D = TypeVar("TGrid3D", bound='Grid3D')
@dataclass(frozen=True, unsafe_hash=True, order=True)
class Grid3D(IPos):
    x: int
    y: int
    z: int
    class Directions:
        UP: 'Grid3D'
        DOWN: 'Grid3D'
        FRONT: 'Grid3D'
        BACK: 'Grid3D'
        LEFT: 'Grid3D'
        RIGHT: 'Grid3D'
    def __add__(self: TGrid3D, other: TGrid3D):
        return self.__class__(self.x + other.x, self.y + other.y, self.z + other.z)
    def __iadd__(self: TGrid3D, other: TGrid3D):
        return self.__class__(self.x + other.x, self.y + other.y, self.z + other.z)
    def __sub__(self: TGrid3D, other: TGrid3D):
        return self.__class__(self.x - other.x, self.y - other.y, self.z - other.z)
    def __isub__(self: TGrid3D, other: TGrid3D):
        return self.__class__(self.x - other.x, self.y - other.y, self.z - other.z)
    def __mul__(self, other):
        if isinstance(other, int):
            return self.__class__(other * self.x, other * self.y, other * self.z)
        return NotImplemented
    def __imul__(self, other):
        if isinstance(other, int):
            return self.__class__(other * self.x, other * self.y, other * self.z)
        return NotImplemented
    def __neg__(self):
        return self.__class__(-self.x, -self.y, -self.z)
    def __bool__(self):
        return self.x != 0 or self.y != 0 or self.z != 0
    def dot(self: TGrid3D, other: TGrid3D):
        return self.x * other.x + self.y * other.y + self.z * other.z
Grid3D.Directions.UP = Grid3D(0, 0, -1)
Grid3D.Directions.DOWN = Grid3D(0, 0, 1)
Grid3D.Directions.FRONT = Grid3D(0, -1, 0)
Grid3D.Directions.BACK = Grid3D(0, 1, 0)
Grid3D.Directions.LEFT = Grid3D(-1, 0, 0)
Grid3D.Directions.RIGHT = Grid3D(1, 0, 0)

class IBox(ABC, Generic[TPos]):
    pos_type = None
    def __init__(self, pos: TPos, space: 'ISpace', *args, **kwargs):
        self.pos = pos
        self.space = space
    def move(self, dir: TPos):
        pass # self.space.move(self, dir)
    def canMove(self, dir: TPos):
        return self.space.canMoveIn(self.pos + dir)
TBox = TypeVar('TBox', bound=IBox)

class ISpace(ABC, Generic[TPos, TBox]):
    box_type = None
    data: dict[TPos, Any] = {}
    def __getitem__(self, index):
        return self.getObjs(index)
    @abstractmethod
    def _pop(self, box: TBox):
        pass
    @abstractmethod
    def _add(self, box: TBox):
        pass
    def move_bunch(self, boxes: dict[TBox, TPos]):
        # map(boxes.keys(), self._pop)
        for box, dir in boxes.items():
            box.pos += dir
            self._add(box)
    @abstractmethod
    def getObjs(self, pos: TPos) -> Tuple[TBox, ...]:
        pass
    @abstractmethod
    def canMoveIn(self, pos: TPos) -> bool:
        pass
    @abstractmethod
    def isPosValid(self, pos: TPos) -> bool:
        pass
TSpace = TypeVar('TSpace', bound=ISpace)

class ISpaceOverlap(ISpace[TPos, TBox]):
    data: dict[TPos, List[TBox]] = {}
    def _pop(self, box: TBox):
        if len(self.data[box.pos]) == 1:
            self.data.pop(box.pos)
        else:
            self.data[box.pos].remove(box)
        return box
    def _add(self, box: TBox):
        if box.pos not in self.data:
            self.data[box.pos] = [box]
        else:
            self.data[box.pos].append(box)
    def getObjs(self, pos: TPos) -> Tuple[TBox, ...]:
        if pos not in self.data:
            return ()
        else:
            return tuple(self.data[pos])
    def canMoveIn(self, pos: TPos) -> bool:
        return self.isPosValid(pos)

class ISpaceNoOverlap(ISpace[TPos, TBox]):
    data: dict[TPos, TBox] = {}
    def _pop(self, box: TBox):
        self.data.pop(box.pos)
    def _add(self, box: TBox):
        if box.pos in self.data:
            raise ValueError
        self.data[box.pos] = box
    def getObjs(self, pos: TPos):
        if pos not in self.data:
            return ()
        else:
            return (self.data[pos],)
    def canMoveIn(self, pos: TPos) -> bool:
        if not self.isPosValid(pos):
            return False
        return pos not in self.data

class IBoxGame(ABC):
    def __init_subclass__(cls, space_cls):
        cls.space_cls = space_cls # type: ignore

