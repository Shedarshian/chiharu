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
        return [(32, 0), (64, 32), (32, 64), (0, 32)][self.value]
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
    def sideKey(t: 'tuple[Dir, bool]'):
        return (t[0].value * 2 + (7 if t[1] else 8)) % 8
    @staticmethod
    def fromSideKey(t: int) -> 'tuple[Dir, bool]':
        return Dir((t + 1) % 8 // 2), t % 2 == 1

class ParserError(Exception):
    pass

addable = {"Cathedral", "Inn", "pennant", "Cloth", "Wine", "Grain", "Princess", "Pigherd"}
tile_addable = {"Portal", "Volcano", "Dragon", "Gold"}
tile_addable_pos = {"Garden", "Tower", "Cloister", "Flier"}
segments = {"City", "Road", "Field", "River", "Feature", "Junction", "Cut", "Bridge", "Roundabout", "Tunnel"}
directions = ["u", "r", "d", "l"]
elses = ["else", "where", "ud", "lr", "start", "R"]
tokens = ["DIRECTION", "NUMBER", "WORD", "PACKNAME", "SIDES", "ADDABLE", "TILE_ADDABLE", "TILE_ADDABLE_POS", "PICTURE"] + [s.upper() for s in segments] + [s.upper() for s in elses]
literals = '()[]{}/-;,*'

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
        if t.value in segments:
            t.type = t.value.upper()
            t.value = SegmentType[t.value]
        elif t.value in elses:
            t.type = t.value.upper()
        elif t.value in directions:
            t.type = "DIRECTION"
            t.value = Dir(directions.index(t.value))
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
           op_param :
           more_manual_sides :
           adjcity :
           more_adjcitys :"""
        p[0] = []
    def p_Pictures(self, p):
        """pictures : PICTURE tiles pictures"""
        p[0] = [PictureDataTuple(p[1], p[2])] + p[3]
    def p_Tiles(self, p):
        """tiles : NUMBER SIDES segments nums tiles"""
        p[0] = [TileDataTuple(p[1], p[2], p[3], p[4])] + p[5]
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
        p[0] = p[1]
    def p_AnyAreaType(self, p):
        """any_area : CITY
        | FIELD"""
        p[0] = p[1]
    def p_AnyPointType(self, p):
        """any_point : JUNCTION
        | FEATURE
        | BRIDGE
        | ROUNDABOUT"""
        p[0] = p[1]
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
           road_side : '(' manual_sides ')'
           road_side : '(' road_sides ')'
           more_hints : '/' hints
           more_road_sides : ',' road_sides
           more_manual_sides : ',' manual_sides
           more_extras : ';' extras
           op_param : '(' params ')'
           adjcity : '{' adjcitys '}'
           more_adjcitys : ',' adjcitys"""
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
        """segment : any_area ELSE road_side adjcity hint"""
        p[0] = ElseSegmentPic(p[1], p[3], p[4], p[5])
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
        """extras : any_segment NUMBER ADDABLE op_param more_extras"""
        p[0] = [FeatureExtraOrderData(p[1], p[2], p[3], p[4])] + p[5]
    def p_Extras4(self, p):
        """extras : WHERE any_area NUMBER hint more_extras"""
        p[0] = [HintExtraOrderData(p[2], p[3], p[4])] + p[5]
    def p_Extras5(self, p):
        """extras : WHERE ROAD NUMBER NUMBER more_extras
                  | WHERE RIVER NUMBER NUMBER more_extras"""
        p[0] = [RoadWidthExtraOrderData(p[2], p[3], p[4])] + p[5]
    def p_Params0(self, p):
        """params : DIRECTION"""
        p[0] = [p[1]]
    def p_Params1(self, p):
        """params : NUMBER"""
        p[0] = [p[1]]
    def p_ManualSides(self, p):
        """manual_sides : DIRECTION - DIRECTION more_manual_sides"""
        p[0] = [(p[1], p[3])] + p[4]
    def p_AdjCities(self, p):
        """adjcitys : NUMBER more_adjcitys"""
        p[0] = [p[1]] + p[2]
    def p_error(self, p):
        raise ParserError(line_num, p)
    def build(self, **kwargs):
        self.parser = yacc.yacc(module=self, **kwargs) # pylint: disable=attribute-defined-outside-init
    def parse(self, string, lexer=lexer) -> 'list[PictureDataTuple]':
        return self.parser.parse(string, lexer=lexer)
parser = TileDataParser()
parser.build()

def disCir(pos: tuple[int, int], radius: float, r: int):
    ret: list[tuple[int, int]] = []
    ang = r % 2 * math.pi / 2
    d = math.pi * 2 / r
    for _ in range(r):
        ret.append((pos[0] + round(radius * math.cos(ang)), pos[1] - round(radius * math.sin(ang))))
        ang += d
    return ret
def disLine(line: str, pos: tuple[int, int], radius: float, r: int):
    ret: list[tuple[int, int]] = []
    if line == "ud":
        ang: float = -radius
        d = 2 * radius / (r - 1)
        for _ in range(r):
            ret.append((pos[0], pos[1] + round(ang)))
            ang += d
    elif line == "lr":
        ang = -radius
        d = 2 * radius / (r - 1)
        for _ in range(r):
            ret.append((pos[0] + round(ang), pos[1]))
            ang += d
    return ret
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
        self.hint_line: str | None = None
        self.hint: list[tuple[int, int]] = []
        self.makeHint(hint)
    def makeHint(self, hint: list[tuple[int, int] | str]):
        if "ud" in hint:
            self.hint_line = "ud"
            hint.remove("ud")
        elif "lr" in hint:
            self.hint_line = "lr"
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
    def drawPos(self, num: int) -> Sequence[tuple[int, int]]:
        if num == 1:
            return [self.pos]
        if num == 0:
            return []
        ret: list[tuple[int, int]] = disCir(self.pos, self.radius, num)
        return ret
    def putPos(self, num: int) -> tuple[int, int]:
        if num == 1:
            return self.pos[0] + self.radius, self.pos[1]
        return self.pos
class LineSegmentPic(SegmentPic):
    __slots__ = ("nodes", "sides", "nodes_init", "width", "link", "center")
    def __init__(self, type: SegmentType, nodes: list[tuple[int, int] | Dir | tuple[SegmentType, int]], width: int, hint) -> None:
        super().__init__(type, hint)
        self.nodes_init: list[tuple[int, int] | Dir | tuple[SegmentType, int]] = nodes
        self.sides: list[Dir] = [n for n in nodes if isinstance(n, Dir)]
        self.nodes: list[tuple[int, int]] = []
        self.width = width
        self.link: tuple[SegmentType, int] | None = None
        self.center: tuple[int, int] = 0, 0
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
        if len(self.nodes) == 2:
            self.center = (self.nodes[0][0] + self.nodes[1][0]) // 2, (self.nodes[0][1] + self.nodes[1][1]) // 2
        else:
            self.center = self.getPortion(0.5)
    def getPortion(self, f: float) -> tuple[int, int]:
        lens: list[float] = [((i[0] - j[0]) ** 2 + (i[1] - j[1]) ** 2) ** 0.5 for i, j in more_itertools.windowed(self.nodes, 2, fillvalue=(0, 0))]
        l = sum(lens) * f
        for i, le in enumerate(lens):
            if l < le:
                d2 = self.nodes[i + 1][0] - self.nodes[i][0], self.nodes[i + 1][1] - self.nodes[i][1]
                ds = l / (d2[0] ** 2 + d2[1] ** 2) ** 0.5
                return round(ds * d2[0] + self.nodes[i][0]), round(ds * d2[1] + self.nodes[i][1])
            l -= le
        return 0, 0
class AreaSegmentPic(SegmentPic):
    __slots__ = ("radius",)
    def __init__(self, type: SegmentType, hint) -> None:
        super().__init__(type, hint)
        self.radius = 6
    def onSelfEdge(self, pos: tuple[int, int]) -> bool:
        return False
    def begin(self) -> tuple[Dir, bool]:
        raise NotImplementedError
    def end(self) -> tuple[Dir, bool]:
        raise NotImplementedError
    def drawPos(self, num: int) -> Sequence[tuple[int, int]]:
        if num == 1:
            return [self.hint[0]]
        if num <= len(self.hint):
            return self.hint[:num]
        repeat = num // len(self.hint)
        p1 = num % len(self.hint)
        ret: list[tuple[int, int]] = []
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
            elif self.hint_line is not None:
                ret.extend(disLine(self.hint_line, p, 16, r))
            else:
                ret.extend(disCir(p, self.radius, r))
        return ret
    def putPos(self, num: int):
        if len(self.hint) > num:
            return self.hint[num]
        repeat = num // len(self.hint)
        p1 = num % len(self.hint)
        if self.hint_line is not None:
            if (self.hint_line == "ud") == (repeat == 1):
                return self.hint[p1][0], self.hint[p1][1] + self.radius
            return self.hint[p1][0] + self.radius, self.hint[p1][1]
        if repeat == 1:
            return self.hint[p1][0] + self.radius, self.hint[p1][1]
        return self.hint[p1]
class SmallSegmentPic(AreaSegmentPic):
    __slots__ = ("side", "width")
    def __init__(self, type: SegmentType, side: tuple[Dir, bool], width: int, hint) -> None:
        super().__init__(type, hint)
        self.radius = 4
        self.side = side
        self.width = width
        if self.hint == []:
            self.hint = [(32 + (32 - width // 2) * (cor := side[0].corr())[0] + 16 * (cor2 := (side[0] + (Dir.LEFT if side[1] else Dir.RIGHT)).corr())[0], 32 + (32 - width // 2) * cor[1] + 16 * cor2[1])]
class OneSideSegmentPic(AreaSegmentPic):
    __slots__ = ("dir", "width")
    def __init__(self, type: SegmentType, dir: Dir, width: int, hint) -> None:
        super().__init__(type, hint)
        self.dir = dir
        self.width = width
        if self.hint == []:
            self.hint = [(32 + (32 - width // 2) * (cor := dir.corr())[0], 32 + (32 - width // 2) * cor[1])]
            self.hint_line = "lr" if dir in (Dir.UP, Dir.DOWN) else "ud"
    def onSelfEdge(self, pos: tuple[int, int]):
        return self.dir == Dir.UP and pos[1] == self.width or self.dir == Dir.DOWN and pos[1] == 64 - self.width or self.dir == Dir.LEFT and pos[0] == self.width or self.dir == Dir.RIGHT and pos[0] == 64 - self.width
    def begin(self):
        return (self.dir, True)
    def end(self):
        return (self.dir, False)
class DoubleSideSegmentPic(AreaSegmentPic):
    __slots__ = ("dirs", "width")
    def __init__(self, type: SegmentType, dirs: tuple[Dir, Dir], width: int, hint) -> None:
        super().__init__(type, hint)
        self.dirs: tuple[Dir, Dir] = tuple(Dir(x) for x in sorted(dir.value for dir in dirs)) # type: ignore
        if dirs == (Dir.UP, Dir.LEFT):
            self.dirs = (Dir.LEFT, Dir.UP)
        if self.hint == []:
            self.hint = [(32 + (32 - width // 2) * (cor := dir.corr())[0], 32 + (32 - width // 2) * cor[1]) for dir in self.dirs]
            self.width = width
    def onSelfEdge(self, pos: tuple[int, int]):
        return Dir.UP in self.dirs and pos[1] == self.width or Dir.DOWN in self.dirs and pos[1] == 64 - self.width or Dir.LEFT in self.dirs and pos[0] == self.width or Dir.RIGHT in self.dirs and pos[0] == 64 - self.width
    def begin(self):
        return (self.dirs[0], True)
    def end(self):
        return (self.dirs[1], False)
    def drawPos(self, num: int) -> Sequence[tuple[int, int]]:
        if num == 1:
            return [self.hint[0]]
        if num <= 2:
            return self.hint[:num]
        repeat = num // 2
        p1 = num % 2
        ret: list[tuple[int, int]] = []
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
                ret.extend(disLine("lr", p, 16, r))
            else:
                ret.extend(disLine("ud", p, 16, r))
        return ret
    def putPos(self, num: int):
        if num < 2:
            return self.hint[num]
        repeat = num // 2
        p1 = num % 2
        if (self.dirs[p1] in (Dir.UP, Dir.DOWN)) == (repeat == 1):
            return self.hint[p1][0], self.hint[p1][1] + self.radius
        return self.hint[p1][0] + self.radius, self.hint[p1][1]
class ElseSegmentPic(AreaSegmentPic):
    __slots__ = ("road_sides", "adjCity")
    def __init__(self, type: SegmentType, road_sides: 'list[RoadSideTuple] | list[tuple[Dir, Dir]]', adjCity: list[int], hint) -> None:
        super().__init__(type, hint)
        self.road_sides = road_sides
        self.adjCity = adjCity
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
    params: list[Any]
class HintExtraOrderData(NamedTuple):
    type: SegmentType
    id: int
    hint: list[tuple[int, int] | str]
class RoadWidthExtraOrderData(NamedTuple):
    type: SegmentType
    id: int
    width: int

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
