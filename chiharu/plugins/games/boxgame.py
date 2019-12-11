from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass
from typing import Dict, TypeVar, List, Tuple
import functools

__all__ = {'IPos', 'Grid2D', 'Grid2DSquare', 'Grid2DHexagonH', 'Grid2DHexagonV', 'Grid3D',
           'IBox',
           'ISpace', 'ISpaceOverlap', 'ISpaceNoOverlap',
           'IBoxGame'}

class IPos(ABC):
    '''Interface for position.'''
    class Directions(Enum):
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
TPos = TypeVar('TPos', bound=IPos)

@dataclass(frozen=True)
class Grid2D(IPos):
    x: int
    y: int
    class Directions:
        pass
    def __add__(self, other):
        return Grid2D(self.x + other.x, self.y + other.y)
    def __iadd__(self, other):
        return Grid2D(self.x + other.x, self.y + other.y)
    def __sub__(self, other):
        return Grid2D(self.x - other.x, self.y - other.y)
    def __isub__(self, other):
        return Grid2D(self.x - other.x, self.y - other.y)

class Grid2DSquare(Grid2D):
    pass
Grid2DSquare.Directions.UP = Grid2DSquare(0, -1)
Grid2DSquare.Directions.RIGHT = Grid2DSquare(1, 0)
Grid2DSquare.Directions.DOWN = Grid2DSquare(0, 1)
Grid2DSquare.Directions.LEFT = Grid2DSquare(-1, 0)

class Grid2DHexagonH(Grid2D):
    pass
Grid2DHexagonH.Directions.UPLEFT = Grid2DHexagonH(0, -1)
Grid2DHexagonH.Directions.UPRIGHT = Grid2DHexagonH(1, -1)
Grid2DHexagonH.Directions.RIGHT = Grid2DHexagonH(1, 0)
Grid2DHexagonH.Directions.LEFT = Grid2DHexagonH(-1, 0)
Grid2DHexagonH.Directions.DOWNRIGHT = Grid2DHexagonH(0, -1)
Grid2DHexagonH.Directions.DOWNLEFT = Grid2DHexagonH(-1, 1)

class Grid2DHexagonV(Grid2D):
    pass
Grid2DHexagonV.Directions.UP = Grid2DHexagonV(0, -1)
Grid2DHexagonV.Directions.UPRIGHT = Grid2DHexagonV(1, -1)
Grid2DHexagonV.Directions.DOWNRIGHT = Grid2DHexagonV(1, 0)
Grid2DHexagonV.Directions.DOWN = Grid2DHexagonV(0, 1)
Grid2DHexagonV.Directions.DOWNLEFT = Grid2DHexagonV(-1, 1)
Grid2DHexagonV.Directions.UPLEFT = Grid2DHexagonV(-1, 0)

@dataclass(frozen=True)
class Grid3D(IPos):
    x: int
    y: int
    z: int
    def __add__(self, other):
        return Grid3D(self.x + other.x, self.y + other.y, self.z + other.z)
    def __iadd__(self, other):
        return Grid3D(self.x + other.x, self.y + other.y, self.z + other.z)
    def __sub__(self, other):
        return Grid3D(self.x - other.x, self.y - other.y, self.z - other.z)
    def __isub__(self, other):
        return Grid3D(self.x - other.x, self.y - other.y, self.z - other.z)

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
    def move(self, box: TBox, dir: TPos):
        self._pop(box)
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
    pass
