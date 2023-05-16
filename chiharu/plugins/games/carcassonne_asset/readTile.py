import re
from PIL import Image, ImageDraw
from enum import Enum, auto
from abc import ABC
from typing import NamedTuple, Any
from copy import deepcopy
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

addable = {"Cathedral", "Inn", "pennant", "Cloth", "Wine", "Grain", "Princess"}
tile_addable = {"Portal", "Volcano", "Dragon"}
tile_addable_pos = {"Garden", "Tower", "Cloister"}
segments = {"City", "Road", "Field", "River", "Feature", "Junction", "Cut"}
directions = ["up", "right", "down", "left"]
elses = ["else", "where", "ud", "lr", "start"]
tokens = ["DIRECTION", "NUMBER", "WORD", "PACKNAME", "SIDES", "ADDABLE", "TILE_ADDABLE", "TILE_ADDABLE_POS", "PICTURE"] + [s.upper() for s in segments] + [s.upper() for s in elses]
literals = '()[]/-;,*'

line_num = 0
def TileDataLexer():
    t_ignore = ' \t'
    def t_newline(t):
        r'\n'
        global line_num
        line_num += 1
    def t_PICTURE(t):
        r'Picture\d+'
        t.value = t.value[7:]
        return t
    def t_PACKNAME(t):
        r'\d+[a-zA-Z]+'
        return t
    def t_NUMBER(t):
        r'\d+'
        t.value = int(t.value)
        return t
    def t_WORD(t):
        r'[a-zA-Z]+'
        if t.value in segments or t.value in elses:
            t.type = t.value.upper()
        elif t.value in directions:
            t.type = "DIRECTION"
            t.value = Dir[t.value.upper()]
        elif t.value in addable:
            t.type = "ADDABLE"
        elif t.value in tile_addable:
            t.type = "TILE_ADDABLE"
        elif t.value in tile_addable_pos:
            t.type = "TILE_ADDABLE_POS"
        elif set(t.value) < set("CRFS"):
            t.type = "SIDES"
        else:
            raise ParserError('Unknown word ' + t.value)
        return t
    def t_error(t):
        raise ParserError('Illegal character ' + t.value)
    return lex.lex()
lexer = TileDataLexer()

class TileDataParser:
    tokens = tokens
    start = 'pictures'
    def p_Not(self, p):
        """pictures : 
           tiles :
           segments :
           nums :
           op_hint :
           road_side :
           op_dir :
           more_hints :
           more_road_sides :
           extras :
           more_extras :
           op_param :"""
        p[0] = []
    def p_Pictures(self, p):
        """pictures : PICTURE tiles pictures"""
        p[0] = [PictureDataTuple(p[1], p[2])] + p[3]
    def p_Tiles(self, p):
        """tiles : NUMBER SIDES segments nums tiles"""
        p[0] = [TileDataTuple(p[1], p[2], p[3], p[4])] + p[4]
    def p_Segments(self, p):
        """segments : segment segments"""
        p[0] = [p[1]] + p[2]
    def p_AnySegmentType(self, p):
        """any_segment : CITY
        | ROAD
        | FIELD
        | RIVER
        | JUNCTION
        | FEATURE
        | CUT"""
        p[0] = SegmentType[p[1]]
    def p_AnyAreaType(self, p):
        """any_area : CITY
        | FIELD"""
        p[0] = SegmentType[p[1]]
    def p_AnyPointType(self, p):
        """any_point : JUNCTION
        | FEATURE"""
        p[0] = SegmentType[p[1]]
    def p_pos(self, p):
        """pos : NUMBER ',' NUMBER"""
        p[0] = (p[1], p[3])
    def p_AnyPos0(self, p):
        """any_pos : pos
           op_hint : hint
           any_pos : DIRECTION"""
        p[0] = p[1]
    def p_AnyPos2(self, p):
        """any_pos : any_point NUMBER"""
        p[0] = p[1], p[2]
    def p_Hint(self, p):
        """hint : '[' hints ']'
           road_side : '(' road_sides ')'
           more_hints : '/' hints
           more_road_sides : ',' road_sides
           more_extras : ';' extras
           op_param : '(' params ')'"""
        p[0] = p[2]
    def p_Hints(self, p):
        """hints : pos more_hints
                 | UD more_hints
                 | LR more_hints"""
        p[0] = [p[1]] + p[2]
    def p_RoadSides(self, p):
        """road_sides : ROAD NUMBER '-' DIRECTION op_dir more_road_sides"""
        p[0] = [RoadSideTuple(p[2], [p[4]] + p[5])] + p[6]
    def p_OpDir(self, p):
        """op_dir : '-' DIRECTION"""
        p[0] = [p[2]]
    def p_PointSegment(self, p):
        """segment : any_point pos op_hint"""
        p[0] = PointSegmentData(p[1], p[2], hint=p[3])
    def p_OneSideSegment(self, p):
        """segment : any_area DIRECTION NUMBER op_hint
                   | ROAD DIRECTION NUMBER op_hint"""
        p[0] = OneSideSegmentData(p[1], p[2], p[3], hint=p[4])
    def p_DoubleSideSegment(self, p):
        """segment : any_area DIRECTION '-' DIRECTION NUMBER op_hint"""
        p[0] = DoubleSideSegmentData(p[1], (p[2], p[4]), p[5], hint=p[6])
    def p_LineSegment(self, p):
        """segment : ROAD any_pos '-' any_pos NUMBER
                   | RIVER any_pos '-' any_pos NUMBER"""
        p[0] = LineSegmentData(p[1], [p[2], p[4]], p[5], [])
    def p_CutSegment(self, p):
        """segment : CUT any_pos '-' any_pos"""
        p[0] = LineSegmentData(p[1], [p[2], p[4]], 0, [])
    def p_ElseSegment(self, p):
        """segment : any_area ELSE road_side hint"""
        p[0] = ElseSegmentData(p[1], p[3], p[4])
    def p_Nums(self, p):
        """nums : '*' NUMBER PACKNAME extras nums"""
        p[0] = [NumDataTuple(p[2], p[3], p[4])] + p[5]
    def p_Extras0(self, p):
        """extras : TILE_ADDABLE_POS op_param any_pos more_extras"""
        p[0] = [AddableExtraOrderData(p[1], p[2], p[3])] + p[4]
    def p_Extras1(self, p):
        """extras : TILE_ADDABLE op_param more_extras"""
        p[0] = [AddableExtraOrderData(p[1], p[2], None)] + p[3]
    def p_Extras2(self, p):
        """extras : START more_extras"""
        p[0] = [StartExtraOrderData()] + p[2]
    def p_Extras3(self, p):
        """extras : any_segment NUMBER ADDABLE more_extras"""
        p[0] = [FeatureExtraOrderData(p[1], p[2], p[3])] + p[4]
    def p_Extras4(self, p):
        """extras : WHERE any_segment NUMBER hint more_extras"""
        p[0] = [HintExtraOrderData(p[2], p[3], p[4])] + p[5]
    def p_Params0(self, p):
        """params : DIRECTION"""
        p[0] = [p[1]]
    def p_error(self, p):
        raise ParserError(line_num, p)
    def build(self, **kwargs):
        self.parser = yacc.yacc(module=self, **kwargs) # pylint: disable=attribute-defined-outside-init
    def parse(self, string, lexer=lexer):
        return self.parser.parse(string, lexer=lexer)
parser = TileDataParser()
parser.build()

class SegmentType(Enum):
    City = auto()
    Road = auto()
    Field = auto()
    River = auto()
    Feature = auto()
    Junction = auto()
    Cut = auto()
class SegmentData(ABC):
    def __init__(self, type: SegmentType, hint: list[tuple[int, int] | str | Dir]) -> None:
        self.type = type
        self.hint_line: str | None = None
        if "ud" in hint:
            self.hint_line = "ud"
            hint.remove("ud")
        elif "lr" in hint:
            self.hint_line = "lr"
            hint.remove("lr")
        if not all(isinstance(s, tuple) for s in hint):
            raise ParserError("ud/lr not right")
        self.hint = [s for s in hint if isinstance(s, tuple)] # TODO dir
class PointSegmentData(SegmentData):
    def __init__(self, type: SegmentType, pos: tuple[int, int], hint) -> None:
        super().__init__(type, hint)
        self.pos = pos
class LineSegmentData(SegmentData):
    def __init__(self, type: SegmentType, nodes: list[tuple[int, int]], width: int, hint) -> None:
        super().__init__(type, hint)
        self.nodes = nodes # TODO
        self.width = width
        self.side: list[Dir] = []
class AreaSegmentData(SegmentData):
    def __init__(self, type: SegmentType, hint) -> None:
        super().__init__(type, hint)
        self.side: list[Dir] = []
class OneSideSegmentData(AreaSegmentData):
    def __init__(self, type: SegmentType, dir: Dir, width: int, hint) -> None:
        super().__init__(type, hint)
        self.dir = dir
        self.width = width
        self.limited: tuple[bool, bool] = (False, False) # counter-clockwise, clockwise
    def inDirArea(self, dir: Dir) -> bool:
        return dir == self.dir
class DoubleSideSegmentData(AreaSegmentData):
    def __init__(self, type: SegmentType, dirs: tuple[Dir, Dir], width: int, hint) -> None:
        super().__init__(type, hint)
        self.dirs: tuple[Dir, Dir] = tuple(Dir(x) for x in sorted(dir.value for dir in dirs)) # type: ignore
        if dirs == (Dir.UP, Dir.LEFT):
            self.dirs = (Dir.LEFT, Dir.UP)
        self.width = width
        self.limited: tuple[bool, bool] = (False, False)
    def inDirArea(self, dir: Dir) -> bool:
        return dir in self.dirs
class ElseSegmentData(AreaSegmentData):
    def __init__(self, type: SegmentType, road_sides: 'list[RoadSideTuple]', hint) -> None:
        super().__init__(type, hint)
        self.road_sides = road_sides

class StartExtraOrderData(NamedTuple):
    pass
class AddableExtraOrderData(NamedTuple):
    feature: str
    params: list[Any]
    pos: tuple[int, int] | str | Dir | None
class FeatureExtraOrderData(NamedTuple):
    type: SegmentType
    id: int
    feature: str
class HintExtraOrderData(NamedTuple):
    type: SegmentType
    id: int
    hint: list[tuple[int, int] | str | Dir]

class RoadSideTuple(NamedTuple):
    road_num: int
    sides: list[Dir]
class NumDataTuple(NamedTuple):
    num: int
    pack_name: str
    extra_orders: list[StartExtraOrderData | AddableExtraOrderData | FeatureExtraOrderData | HintExtraOrderData]
class TileDataTuple(NamedTuple):
    id: int
    sides: str
    segments: list[SegmentData]
    nums: list[NumDataTuple]
class PictureDataTuple(NamedTuple):
    name: str
    tiles: list[TileDataTuple]

from pathlib import Path
with open(Path(__file__).parent / "tiledata.txt", encoding="utf-8") as f:
    parser.parse(f.read())