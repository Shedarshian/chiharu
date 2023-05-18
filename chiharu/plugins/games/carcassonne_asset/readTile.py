import re, math, more_itertools
from PIL import Image, ImageDraw
from enum import Enum, auto
from abc import ABC, abstractmethod
from typing import NamedTuple, Any, Sequence
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
    def __sub__(self, other: 'Dir'):
        return Dir((self.value - other.value + 4) % 4)
    def __radd__(self, other: tuple[int, int]):
        return other[0] + self.corr()[0], other[1] + self.corr()[1]
    def __neg__(self):
        return Dir((self.value + 2) % 4)
    def transpose(self):
        return (None, Image.ROTATE_270, Image.ROTATE_180, Image.ROTATE_90)[self.value]
    def orthogonal(self, other: 'Dir'):
        return self.value % 2 != other.value % 2
    @staticmethod
    def sideKey(t: tuple[Dir, bool]):
        return (t[0].value * 2 + (7 if t[1] else 8)) % 8

class ParserError(Exception):
    pass

addable = {"Cathedral", "Inn", "pennant", "Cloth", "Wine", "Grain", "Princess", "Pigherd"}
tile_addable = {"Portal", "Volcano", "Dragon"}
tile_addable_pos = {"Garden", "Tower", "Cloister"}
segments = {"City", "Road", "Field", "River", "Feature", "Junction", "Cut", "Bridge", "Roundabout", "Tunnel"}
directions = ["up", "right", "down", "left"]
elses = ["else", "where", "ud", "lr", "start", "R"]
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
        | CUT
        | TUNNEL"""
        p[0] = SegmentType[p[1]]
    def p_AnyAreaType(self, p):
        """any_area : CITY
        | FIELD"""
        p[0] = SegmentType[p[1]]
    def p_AnyPointType(self, p):
        """any_point : JUNCTION
        | FEATURE
        | BRIDGE
        | ROUNDABOUT"""
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
        """road_sides : R NUMBER '-' DIRECTION op_dir more_road_sides"""
        p[0] = [RoadSideTuple(p[2], [p[4]] + p[5])] + p[6]
    def p_OpDir(self, p):
        """op_dir : '-' DIRECTION"""
        p[0] = [p[2]]
    def p_PointSegment(self, p):
        """segment : any_point pos op_hint"""
        p[0] = PointSegmentPic(p[1], p[2], hint=p[3])
    def p_OneSideSegment(self, p):
        """segment : any_area DIRECTION NUMBER op_hint
                   | ROAD DIRECTION NUMBER op_hint"""
        p[0] = OneSideSegmentPic(p[1], p[2], p[3], hint=p[4])
    def p_DoubleSideSegment(self, p):
        """segment : any_area DIRECTION '-' DIRECTION NUMBER op_hint"""
        p[0] = DoubleSideSegmentPic(p[1], (p[2], p[4]), p[5], hint=p[6])
    def p_LineSegment(self, p):
        """segment : ROAD any_pos '-' any_pos NUMBER
                   | RIVER any_pos '-' any_pos NUMBER"""
        p[0] = LineSegmentPic(p[1], [p[2], p[4]], p[5], [])
    def p_CutSegment(self, p):
        """segment : CUT any_pos '-' any_pos"""
        p[0] = LineSegmentPic(p[1], [p[2], p[4]], 0, [])
    def p_ElseSegment(self, p):
        """segment : any_area ELSE road_side hint"""
        p[0] = ElseSegmentPic(p[1], p[3], p[4])
    def p_TunnelSegment(self, p):
        """segment : TUNNEL ROAD NUMBER ROAD NUMBER"""
        p[0] = TunnelSegmentPic(p[1], p[3], p[5], [])
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
    def parse(self, string, lexer=lexer) -> 'list[PictureDataTuple]':
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
    Bridge = auto()
    Roundabout = auto()
    Tunnel = auto()
class SegmentPic(ABC):
    __slots__ = ("type", "hint", "hint_line")
    def __init__(self, type: SegmentType, hint: list[tuple[int, int] | str]) -> None:
        self.type = type
        self.hint_line: Dir | None = None
        if "ud" in hint:
            self.hint_line = Dir.UP
            hint.remove("ud")
        elif "lr" in hint:
            self.hint_line = Dir.LEFT
            hint.remove("lr")
        if not all(isinstance(s, tuple) for s in hint):
            raise ParserError("ud/lr not right")
        self.hint = [s for s in hint if isinstance(s, tuple)]
class TunnelSegmentPic(SegmentPic):
    def __init__(self, type: SegmentType, num1: int, num2: int, hint) -> None:
        super().__init__(type, hint)
        self.num1 = num1
        self.num2 = num2
class PointSegmentPic(SegmentPic):
    __slots__ = ("pos",)
    def __init__(self, type: SegmentType, pos: tuple[int, int], hint) -> None:
        super().__init__(type, hint)
        self.pos = pos
    @property
    def radius(self):
        return 8 if self.type == SegmentType.Feature else 0
class LineSegmentPic(SegmentPic):
    __slots__ = ("nodes", "sides", "nodes_init", "width", "link")
    def __init__(self, type: SegmentType, nodes: list[tuple[int, int] | Dir | tuple[SegmentType, int]], width: int, hint) -> None:
        super().__init__(type, hint)
        self.nodes_init: list[tuple[int, int] | Dir | tuple[SegmentType, int]] = nodes
        self.sides: list[Dir] = [n for n in nodes if isinstance(n, Dir)]
        self.nodes: list[tuple[int, int]] = []
        self.width = width
        self.link: tuple[SegmentType, int] | None = None
    def makeNodes(self, points: list[PointSegmentPic]):
        for i, node in enumerate(self.nodes_init):
            if isinstance(node, Dir):
                pos = node.tilepos()
                offset = (-node).corr()
                if self.width == 0:
                    self.nodes.append(pos)
                else:
                    if i == 0:
                        self.nodes.append(pos)
                    self.nodes.append((pos[0] + self.width * offset[0], pos[1] + self.width * offset[1]))
                    if i != 0:
                        self.nodes.append(pos)
            elif isinstance(node[0], SegmentType):
                point = [seg for seg in points if seg.type == node[0]][node[1]]
                pos = point.pos
                last_pos = self.nodes[-1]
                d: float = ((last_pos[0] - pos[0]) ** 2 + (last_pos[1] - pos[1]) ** 2) ** 0.5
                self.nodes.append((round(pos[0] + point.radius * (last_pos[0] - pos[0]) / d), round(pos[1] + point.radius * (last_pos[1] - pos[1]) / d)))
                if node[0] in (SegmentType.Bridge, SegmentType.Roundabout):
                    self.link = node
            else:
                self.nodes.append(node)
        del self.nodes_init
class AreaSegmentPic(SegmentPic):
    __slots__ = ("radius",)
    def __init__(self, type: SegmentType, hint) -> None:
        super().__init__(type, hint)
        self.radius = 6
    def drawPos(self, num: int) -> Sequence[tuple[float, float]]:
        if num == 1:
            return [self.hint[0]]
        if num <= len(self.hint):
            return self.hint[:num]
        repeat = num // len(self.hint)
        p1 = num % len(self.hint)
        ret: list[tuple[float, float]] = []
        for i, p in enumerate(self.hint):
            r = repeat + (1 if i < p1 else 0)
            if r == 1:
                ret.append(p)
            elif r == 2:
                if self.hint_line == "ud":
                    ret.append((p[0], p[1] - self.radius))
                    ret.append((p[0], p[1] + self.radius))
                else:
                    ret.append((p[0] - self.radius, p[1]))
                    ret.append((p[0] + self.radius, p[1]))
            elif self.hint_line == "ud":
                ang: float = -16
                d = 32 / (r - 1)
                for _ in range(r):
                    ret.append((p[0], p[1] + ang))
                    ang += d
            elif self.hint_line == "lr":
                ang = -16
                d = 32 / (r - 1)
                for _ in range(r):
                    ret.append((p[0] + ang, p[1]))
                    ang += d
            else:
                ang = r % 2 * math.pi / 2
                d = math.pi * 2 / r
                for _ in range(r):
                    ret.append((p[0] + self.radius * math.cos(ang), p[1] - self.radius * math.sin(ang)))
                    ang += d
        return ret
    def drawPosPut(self, num: int):
        if len(self.hint) >= num + 1:
            return self.hint[num]
        return []
class SmallSegmentPic(AreaSegmentPic):
    __slots__ = ("side", "width")
    def __init__(self, type: SegmentType, side: tuple[Dir,bool], width: int, hint) -> None:
        super().__init__(type, hint)
        self.radius = 4
        self.side = side
        self.width = width
        self.hint = [(32 + (32 - width // 2) * (cor := side[0].corr())[0] + 16 * (cor2 := (side[0] + Dir.LEFT).corr())[0], 32 + (32 - width // 2) * cor[1] + 16 * cor2[1])]
class OneSideSegmentPic(AreaSegmentPic):
    __slots__ = ("dir", "width")
    def __init__(self, type: SegmentType, dir: Dir, width: int, hint) -> None:
        super().__init__(type, hint)
        self.dir = dir
        self.width = width
        self.hint = [(32 + (32 - width // 2) * (cor := dir.corr())[0], 32 + (32 - width // 2) * cor[1])]
        self.hint_line = Dir.UP if dir == Dir.DOWN else Dir.LEFT if dir == Dir.RIGHT else dir
class DoubleSideSegmentPic(AreaSegmentPic):
    __slots__ = ("dirs", "width")
    def __init__(self, type: SegmentType, dirs: tuple[Dir, Dir], width: int, hint) -> None:
        super().__init__(type, hint)
        self.dirs: tuple[Dir, Dir] = tuple(Dir(x) for x in sorted(dir.value for dir in dirs)) # type: ignore
        if dirs == (Dir.UP, Dir.LEFT):
            self.dirs = (Dir.LEFT, Dir.UP)
        self.hint = [(32 + (32 - width // 2) * (cor := dir.corr())[0], 32 + (32 - width // 2) * cor[1]) for dir in self.dirs]
        self.width = width
    def drawPos(self, num: int) -> Sequence[tuple[float, float]]:
        if num == 1:
            return [self.hint[0]]
        if num <= 2:
            return self.hint[:num]
        repeat = num // 2
        p1 = num % 2
        ret: list[tuple[float, float]] = []
        for i, p in enumerate(self.hint):
            r = repeat + (1 if i < p1 else 0)
            if r == 1:
                ret.append(p)
            elif r == 2:
                if self.dirs[i] in (Dir.LEFT, Dir.RIGHT):
                    ret.append((p[0], p[1] - self.radius))
                    ret.append((p[0], p[1] + self.radius))
                else:
                    ret.append((p[0] - self.radius, p[1]))
                    ret.append((p[0] + self.radius, p[1]))
            elif self.dirs[i] in (Dir.LEFT, Dir.RIGHT):
                ang: float = -16
                d = 32 / (r - 1)
                for _ in range(r):
                    ret.append((p[0], p[1] + ang))
                    ang += d
            else:
                ang = -16
                d = 32 / (r - 1)
                for _ in range(r):
                    ret.append((p[0] + ang, p[1]))
                    ang += d
        return ret
class ElseSegmentPic(AreaSegmentPic):
    __slots__ = ("road_sides",)
    def __init__(self, type: SegmentType, road_sides: 'list[RoadSideTuple]', hint) -> None:
        super().__init__(type, hint)
        self.road_sides = road_sides
        if len(self.hint) == 0:
            raise ValueError

class StartExtraOrderData(NamedTuple):
    pass
class AddableExtraOrderData(NamedTuple):
    feature: str
    params: list[Any]
    pos: tuple[int, int] | Dir | tuple[SegmentType, int] | None
class FeatureExtraOrderData(NamedTuple):
    type: SegmentType
    id: int
    feature: str
class HintExtraOrderData(NamedTuple):
    type: SegmentType
    id: int
    hint: list[tuple[int, int] | str]

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
    segments: list[SegmentPic]
    nums: list[NumDataTuple]
class PictureDataTuple(NamedTuple):
    name: str
    tiles: list[TileDataTuple]
