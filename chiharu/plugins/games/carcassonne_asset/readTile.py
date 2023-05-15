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
segments = {"City", "Road", "Field", "River", "Feature", "Junction", "Cut"}
directions = ["up", "right", "down", "left"]
elses = ["else", "where", "Picture", "ud", "lr"]
tokens = ["DIRECTION", "FEATURE", "NUMBER", "WORD", "PACKNAME", "SIDES"] + [s.upper() for s in segments] + [s.upper() for s in elses]
literals = r'()[]/-;,*'
def TileDataLexer():
    t_ignore = ' \t\n'
    def t_PACKNAME(t):
        r'\d+[a-zA-Z]+'
        return t
    def t_NUMBER(t):
        r'\d+'
        return int(t)
    def t_WORD(t):
        r'[a-zA-Z]+'
        if t.value in segments or t.value in elses:
            t.type = t.value.upper()
        elif t.value in features:
            t.type = "FEATURE"
        elif t.value in directions:
            t.type = "DIRECTION"
            t.value = Dir[t.value.upper()]
        elif set(t.value) < set("CRFS"):
            t.type = "SIDES"
        else:
            raise ParserError('Unknown word ' + t.value)
        return t
    def t_error(t):
        raise ParserError('Illegal character ' + t.value)
    return lex.lex()

class ExpressionParser:
    tokens = tokens
    start = 'pictures'
    def p_Not(self, p):
        """pictures : 
           tiles :
           segments :
           op_hint :
           hints :"""
        p[0] = []
    def p_Pictures(self, p):
        """pictures : PICTURE PACKNAME tiles pictures"""
        p[0] = [PictureDataTuple(p[2], p[3])] + p[4]
    def p_Tiles(self, p):
        """tiles : NUMBER SIDES segments nums tiles"""
        p[0] = TileDataTuple(p[1], p[2], p[3], p[4]) + p[4]
    def p_Segments(self, p):
        """segments : segment segments"""
        p[0] = [p[1]] + p[2]
    def p_AnySegmentType(self, p):
        """any_segment : CITY | ROAD | FIELD | RIVER | JUNCTION | FEATURE | CUT"""
        p[0] = SegmentType[p[1].upper()]
    def p_AnyAreaType(self, p):
        """any_area : CITY |FIELD"""
        p[0] = SegmentType[p[1].upper()]
    def p_AnyPointType(self, p):
        """any_point : JUNCTION | FEATURE"""
        p[0] = SegmentType[p[1].upper()]
    def p_pos(self, p):
        """pos : NUMBER , NUMBER"""
        p[0] = (p[1], p[3])
    def p_AnyPos0(self, p):
        """any_pos : pos
           op_hint : hint"""
        p[0] = p[1]
    def p_AnyPos1(self, p):
        """any_pos : DIRECTION"""
        p[0] = Dir[p[1].upper()]
    def p_AnyPos2(self, p):
        """any_pos : any_point NUMBER"""
        p[0] = p[1], p[2]
    def p_Hint(self, p):
        """hint : [ hints ]"""
        p[0] = p[2]
    def p_Hints(self, p):
        """hints : pos / hints
                 | UD / hints
                 | LR / hints"""
        p[0] = [p[1]] + p[3]
    def p_OneSideSegment(self, p):
        """segment : any_area DIRECTION NUMBER op_hint
                   | ROAD DIRECTION NUMBER op_hint"""
        p[0] = OneSideSegmentData(p[1], p[2], p[3], hint=p[4])
    def p_DoubleSideSegment(self, p):
        """segment : any_area DIRECTION - DIRECTION NUMBER op_hint"""
        p[0] = DoubleSideSegmentData(p[1], (p[2], p[4]), p[5], hint=p[6])
    def p_LineSegment(self, p):
        """segment : ROAD any_pos - any_pos NUMBER
                   | RIVER any_pos - any_pos NUMBER
                   | CUT any_pos - any_pos NUMBER"""
        # TODO
    def p_CutSegment(self, p):
        """segment : CUT any_pos - any_pos"""
        # TODO
    def p_ElseSegment(self, p):
        """segment : any_area ELSE road_side hint"""

class SegmentType(Enum):
    City = auto()
    Road = auto()
    Field = auto()
    River = auto()
    Feature = auto()
    Junction = auto()
    Cut = auto()
class SegmentData(ABC):
    def __init__(self, type: SegmentType, hint=None) -> None:
        self.type = type
        self.hint = hint
class PointSegmentData(SegmentData):
    def __init__(self, type: SegmentType, pos: tuple[int, int], hint=None) -> None:
        super().__init__(type, hint)
        self.pos = pos
class LineSegmentData(SegmentData):
    def __init__(self, type: SegmentType, nodes: list[tuple[int, int]], hint=None) -> None:
        super().__init__(type, hint)
        self.nodes = nodes
        self.side: list[Dir] = []
class AreaSegmentData(SegmentData):
    def __init__(self, type: SegmentType, hint=None) -> None:
        super().__init__(type, hint)
        self.side: list[Dir] = []
class OneSideSegmentData(AreaSegmentData):
    def __init__(self, type: SegmentType, dir: Dir, width: int, hint=None) -> None:
        super().__init__(type, hint)
        self.dir = dir
        self.width = width
        self.limited: tuple[bool, bool] = (False, False) # counter-clockwise, clockwise
    def inDirArea(self, dir: Dir) -> bool:
        return dir == self.dir
class DoubleSideSegmentData(AreaSegmentData):
    def __init__(self, type: SegmentType, dirs: tuple[Dir, Dir], width: int, hint=None) -> None:
        super().__init__(type, hint)
        self.dirs: tuple[Dir, Dir] = tuple(Dir(x) for x in sorted(dir.value for dir in dirs)) # type: ignore
        if dirs == (Dir.UP, Dir.LEFT):
            self.dirs = (Dir.LEFT, Dir.UP)
        self.width = width
        self.limited: tuple[bool, bool] = (False, False)
    def inDirArea(self, dir: Dir) -> bool:
        return dir in self.dirs
class ElseSegmentData(AreaSegmentData):
    def __init__(self, type: SegmentType, hint=None) -> None:
        super().__init__(type, hint)

class TileDataTuple(NamedTuple):
    id: int
    sides: str
    segments: list[SegmentData]
    nums: list[NumDataTuple]
class PictureDataTuple(NamedTuple):
    name: str
    tiles: list[TileDataTuple]

