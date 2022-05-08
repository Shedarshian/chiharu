from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, TypeVar, List, Tuple
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
@dataclass(frozen=True, unsafe_hash=True)
class Grid2D(IPos):
    x: int
    y: int
    class Directions:
        pass
    def __add__(self: TGrid2D, other: TGrid2D):
        return self.__class__(self.x + other.x, self.y + other.y)
    def __iadd__(self: TGrid2D, other: TGrid2D):
        return self.__class__(self.x + other.x, self.y + other.y)
    def __sub__(self: TGrid2D, other: TGrid2D):
        return self.__class__(self.x - other.x, self.y - other.y)
    def __isub__(self: TGrid2D, other: TGrid2D):
        return self.__class__(self.x - other.x, self.y - other.y)
    def __mul__(self: TGrid2D, other):
        if isinstance(other, int):
            return self.__class__(other * self.x, other * self.y)
        return NotImplemented
    def __imul__(self: TGrid2D, other):
        if isinstance(other, int):
            return self.__class__(other * self.x, other * self.y)
        return NotImplemented
    def __neg__(self):
        return self.__class__(-self.x, -self.y)
    def __bool__(self):
        return self.x != 0 or self.y != 0
    def dot(self: TGrid2D, other: TGrid2D):
        return self.x * other.x + self.y * other.y

class Grid2DSquare(Grid2D):
    class Directions:
        UP: 'Grid2DSquare' = None
        RIGHT: 'Grid2DSquare' = None
        DOWN: 'Grid2DSquare' = None
        LEFT: 'Grid2DSquare' = None
Grid2DSquare.Directions.UP = Grid2DSquare(0, -1)
Grid2DSquare.Directions.RIGHT = Grid2DSquare(1, 0)
Grid2DSquare.Directions.DOWN = Grid2DSquare(0, 1)
Grid2DSquare.Directions.LEFT = Grid2DSquare(-1, 0)

class Grid2DHexagonH(Grid2D):
    class Directions:
        UPLEFT: 'Grid2DHexagonH' = None
        UPRIGHT: 'Grid2DHexagonH' = None
        RIGHT: 'Grid2DHexagonH' = None
        DOWNRIGHT: 'Grid2DHexagonH' = None
        DOWNLEFT: 'Grid2DHexagonH' = None
        LEFT: 'Grid2DHexagonH' = None
Grid2DHexagonH.Directions.UPLEFT = Grid2DHexagonH(0, -1)
Grid2DHexagonH.Directions.UPRIGHT = Grid2DHexagonH(1, -1)
Grid2DHexagonH.Directions.RIGHT = Grid2DHexagonH(1, 0)
Grid2DHexagonH.Directions.LEFT = Grid2DHexagonH(-1, 0)
Grid2DHexagonH.Directions.DOWNRIGHT = Grid2DHexagonH(0, -1)
Grid2DHexagonH.Directions.DOWNLEFT = Grid2DHexagonH(-1, 1)

class Grid2DHexagonV(Grid2D):
    class Directions:
        UP: 'Grid2DHexagonV' = None
        UPRIGHT: 'Grid2DHexagonV' = None
        DOWN: 'Grid2DHexagonV' = None
        DOWNRIGHT: 'Grid2DHexagonV' = None
        DOWNLEFT: 'Grid2DHexagonV' = None
        UPLEFT: 'Grid2DHexagonV' = None
Grid2DHexagonV.Directions.UP = Grid2DHexagonV(0, -1)
Grid2DHexagonV.Directions.UPRIGHT = Grid2DHexagonV(1, -1)
Grid2DHexagonV.Directions.DOWNRIGHT = Grid2DHexagonV(1, 0)
Grid2DHexagonV.Directions.DOWN = Grid2DHexagonV(0, 1)
Grid2DHexagonV.Directions.DOWNLEFT = Grid2DHexagonV(-1, 1)
Grid2DHexagonV.Directions.UPLEFT = Grid2DHexagonV(-1, 0)

TGrid3D = TypeVar("TGrid3D", bound='Grid3D')
@dataclass(frozen=True, unsafe_hash=True)
class Grid3D(IPos):
    x: int
    y: int
    z: int
    class Directions:
        UP: 'Grid3D' = None
        DOWN: 'Grid3D' = None
        FRONT: 'Grid3D' = None
        BACK: 'Grid3D' = None
        LEFT: 'Grid3D' = None
        RIGHT: 'Grid3D' = None
    def __add__(self: TGrid3D, other: TGrid3D):
        return self.__class__(self.x + other.x, self.y + other.y, self.z + other.z)
    def __iadd__(self: TGrid3D, other: TGrid3D):
        return self.__class__(self.x + other.x, self.y + other.y, self.z + other.z)
    def __sub__(self: TGrid3D, other: TGrid3D):
        return self.__class__(self.x - other.x, self.y - other.y, self.z - other.z)
    def __isub__(self: TGrid3D, other: TGrid3D):
        return self.__class__(self.x - other.x, self.y - other.y, self.z - other.z)
    def __mul__(self: TGrid3D, other):
        if isinstance(other, int):
            return self.__class__(other * self.x, other * self.y, other * self.z)
        return NotImplemented
    def __imul__(self: TGrid3D, other):
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

class IBox(ABC):
    pos_type = None
    def __init__(self, pos: TPos, space: 'TSpace', *args, **kwargs):
        assert(isinstance(pos, self.pos_type))
        self.pos = pos
        self.space = space
    def move(self, dir: TPos):
        self.space.move(self, dir)
    def canMove(self, dir: TPos):
        return self.space.canMoveIn(self, self.pos + dir)
TBox = TypeVar('TBox', bound=IBox)

class ISpace(ABC):
    box_type = None
    data = {}
    def __getitem__(self, index):
        return self.getObjs(index)
    @abstractmethod
    def _pop(self, box: TBox):
        pass
    @abstractmethod
    def _add(self, box: TBox):
        pass
    def move_bunch(self, boxes: Dict[TBox, TPos]):
        map(boxes.keys(), self._pop)
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

class ISpaceOverlap(ISpace):
    data: Dict[TPos, List[TBox]] = {}
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

class ISpaceNoOverlap(ISpace):
    data: Dict[TPos, TBox] = {}
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
        cls.space_cls = space_cls
    
