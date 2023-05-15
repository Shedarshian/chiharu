import re
from PIL import Image, ImageDraw
from enum import Enum, auto
from abc import ABC
from typing import NamedTuple
import ply.lex as lex, ply.yacc as yacc

class Dir(Enum):
    UP = 0
    RIGHT = 1
    DOWN = 2
    LEFT = 3
    def corr(self) -> tuple[int, int]:
        return ((0, -1), (1, 0), (0, 1), (-1, 0))[self.value]
    def tilepos(self) -> tuple[int, int]:
        return [(32, 0), (32, 64), (0, 32), (64, 32)][self.value]
    @classmethod
    def fromCorr(cls, corr: tuple[int, int]):
        return Dir(((0, -1), (1, 0), (0, 1), (-1, 0)).index(corr))
    def __add__(self, other: 'Dir'):
        return Dir((self.value + other.value) % 4)
    def __radd__(self, other: tuple[int, int]):
        return other[0] + self.corr()[0], other[1] + self.corr()[1]
    def __neg__(self):
        return Dir((self.value + 2) % 4)
    def transpose(self):
        return (None, Image.ROTATE_270, Image.ROTATE_180, Image.ROTATE_90)[self.value]

class ParserError(Exception):
    pass

features = {"Cloister", "Cathedral", "Inn", "pennant", "Garden", "Cloth", "Wine", "Grain"}
segments = {"City", "Road", "Field", "Feature", "Junction", "Cut"}
directions = ["up", "right", "down", "left"]
elses = ["else", "where", "Picture"]
tokens = ["DIRECTION", "FEATURE", "NUMBER", "WORD", "PACKNAME", "SIDES"] + [s.upper() for s in segments] + [s.upper() for s in elses]
literals = r'()[]/-;,*'
def TileDataLexer():
    t_ignore = ' \t\n'
    def t_PACKNAME(t):
        r'\d+[a-zA-Z]+'
        return t
    def t_NUMBER(t):
        r'\d+'
    def t_WORD(t):
        r'[a-zA-Z]+'
        if t.value in segments or t.value in elses:
            t.type = t.value.upper()
        elif t.value in features:
            t.type = "FEATURE"
        elif t.value in directions:
            t.type = "DIRECTION"
        elif set(t.value) < set("CRFS"):
            t.type = "SIDES"
        else:
            raise ParserError('Unknown word ' + t.value)
        return t
    def t_error(t):
        raise ParserError('Illegal character ' + t.value)
    return lex.lex()

class SegmentPic(ABC):
    def __init__(self) -> None:
        pass
    def inDirArea(self, dir: Dir) -> bool:
        return False
class RoadSegmentPic(SegmentPic):
    def __init__(self, nodes: list[tuple[int, int]]) -> None:
        super().__init__()
        self.nodes = nodes
class AreaSegmentPic(SegmentPic):
    pass
class OneSideSegmentPic(AreaSegmentPic):
    def __init__(self, dir: Dir, width: int) -> None:
        super().__init__()
        self.dir = dir
        self.width = width
        self.limited: tuple[bool, bool] = (False, False) # counter-clockwise, clockwise
    def inDirArea(self, dir: Dir) -> bool:
        return dir == self.dir
class DoubleSideSegmentPic(AreaSegmentPic):
    def __init__(self, dirs: tuple[Dir, Dir], width: int) -> None:
        super().__init__()
        self.dirs: tuple[Dir, Dir] = tuple(Dir(x) for x in sorted(dir.value for dir in dirs)) # type: ignore
        if dirs == (Dir.UP, Dir.LEFT):
            self.dirs = (Dir.LEFT, Dir.UP)
        self.width = width
        self.limited: tuple[bool, bool] = (False, False)
    def inDirArea(self, dir: Dir) -> bool:
        return dir in self.dirs
class AllSideSegmentPic(AreaSegmentPic):
    def __init__(self, removed: list[SegmentPic] | None=None, roads: list[RoadSegmentPic] | None=None) -> None:
        super().__init__()
        self.removed = removed or []
        self.roads = roads or []
class PictureData(NamedTuple):
    name: str
    tiles: list[TileDataTuple]

class ExpressionParser:
    tokens = tokens
    start = 'pictures'
    def p_Not(self, p):
        """pictures : 
           tiles :
           segments :"""
        p[0] = []
    def p_Pictures(self, p):
        """pictures : PICTURE PACKNAME tiles pictures"""
        p[0] = [PictureDataTuple(p[2], p[3])] + p[4]
    def p_Tiles(self, p):
        """tiles : NUMBER SIDES segments nums tiles"""
        p[0] = TileDataTuple(p[1], p[2], p[3], p[4]) + p[4]
    def p_CitySegment(self, p):
        """segments : CITY"""
        p[0] = []

