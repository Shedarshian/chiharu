from typing import Literal, Any, Callable
import random, itertools, more_itertools
from enum import Enum, auto
from abc import ABC, abstractmethod

class Connectable(Enum):
    City = auto()
    Field = auto()
    Road = auto()
    River = auto()
    @classmethod
    def fromChar(cls, char: str):
        return {"C": Connectable.City, "F": Connectable.Field, "R": Connectable.Road, "S": Connectable.River}[char]
class Dir(Enum):
    UP = 0
    RIGHT = 1
    DOWN = 2
    LEFT = 3
    def corr(self):
        return ((0, -1), (1, 0), (0, 1), (-1, 0))[self.value]
    @classmethod
    def fromCorr(cls, corr: tuple[int, int]):
        return ((0, -1), (1, 0), (0, 1), (-1, 0)).index(corr)
    def __add__(self, other: 'Dir'):
        return Dir((self.value + other.value) % 4)
    def __neg__(self):
        return Dir((self.value + 2) % 4)
class TraderCounter(Enum):
    Wine = auto()
    Grain = auto()
    Cloth = auto()

class Board:
    def __init__(self, packs: list[dict[str, Any]], player_num: int) -> None:
        self.tiles: dict[tuple[int, int], Tile] = {}
        self.deck: list[Tile] = []
        self.tokens: list[Token] = []
        self.players: list[Player] = [Player(self) for i in range(player_num)]
        for pack in packs:
            for t in pack["tiles"]:
                self.deck.extend(Tile(t) for i in range(t["num"]))
            for t in pack["tokens"]:
                if t["distribute"]:
                    for p in self.players:
                        p.tokens.extend(Token.make(t["name"])(p, t) for i in range(t["num"]))
                else:
                    self.tokens.extend(Token.make(t["name"])(self, t) for i in range(t["num"]))
        start_id = packs[0]["starting_tile"]
        start_tile = [t for t in self.deck if t.id == start_id][0]
        self.deck.remove(start_tile)
        self.tiles[0, 0] = start_tile

class Tile:
    def __init__(self, data: dict[str, Any]) -> None:
        self.id: int = data["id"]
        self.sides: tuple[Connectable,...] = tuple(Connectable.fromChar(s) for s in data["sides"])
        self.segments: list[Segment] = [Segment.make(s["type"])(self, s) for s in data["segments"]]
        for seg in self.segments:
            if isinstance(seg, FieldSegment):
                seg.makeAdjacentCity(self.segments)
        self.features: list[Feature] = [f(self, s) for s in data.get("features", []) if (f := Feature.make(s["type"])) is not None]
        self.tokens: list[Token] = []
        self.connectTile: list[Tile | None] = [None] * 4
        self.orient: Dir = Dir.UP
    def sidesToSegment(self, dir: Dir):
        return more_itertools.only([seg for seg in self.segments if seg.inSide(dir) and isinstance(seg, NonFieldSegment)])
    def sidesToSegmentF(self, dir: Dir, up: bool):
        return more_itertools.only([seg for seg in self.segments if seg.inSideF(dir, up) and isinstance(seg, FieldSegment)])
    def turn(self, dir: Dir):
        self.orient = self.orient + dir
        self.sides = self.sides[4 - dir.value:] + self.sides[:4 - dir.value]
        self.connectTile = self.connectTile[4 - dir.value:] + self.connectTile[:4 - dir.value]
        for s in self.segments:
            s.turn(dir)
    def addConnect(self, tile: 'Tile', dir: Dir):
        """-1: 已有连接, -2: 无法连接"""
        if self.connectTile[dir.value] is not None:
            return -1
        if self.sides[dir.value] != tile.sides[(-dir).value]:
            return -2
        if (s1 := self.sidesToSegment(dir)) is not None and (s2 := tile.sidesToSegment(-dir)) is not None:
            s1.combine(s2)
        if (s1 := self.sidesToSegmentF(dir, False)) is not None and (s2 := tile.sidesToSegmentF(-dir, True)) is not None:
            s1.combineF(s2)
        if (s1 := self.sidesToSegmentF(dir, True)) is not None and (s2 := tile.sidesToSegmentF(-dir, False)) is not None:
            s1.combineF(s2)
        return 1

class Segment(ABC):
    def __init__(self, typ: Connectable, tile: Tile, data: dict[str, Any]) -> None:
        self.type = typ
        self.tile = tile
        self.features: list[Feature] = []
        self.object = Object(self)
        self.tokens: list[Token] = []
    @classmethod
    def make(cls, typ: str) -> Callable[[Tile, dict[str, Any]], 'Segment']:
        return {"City": CitySegment, "Field": FieldSegment, "Road": RoadSegment, "River": RiverSegment}[typ]
    @abstractmethod
    def turn(self, dir: Dir):
        pass
    def inSide(self, dir: Dir):
        return False
    def inSideF(self, dir: Dir, up: bool):
        return False
    def closed(self):
        return False
class NonFieldSegment(Segment):
    def __init__(self, typ: Connectable, tile: Tile, data: dict[str, Any]) -> None:
        super().__init__(typ, tile, data)
        self.side: dict[Dir, Segment | None] = {Dir(i): None for i in data["to"]}
    def turn(self, dir: Dir):
        self.side = {d + dir: value for d, value in self.side.items()}
    def inSide(self, dir: Dir):
        return dir in self.side
    def combine(self, other: 'NonFieldSegment', dir: Dir):
        other.object = self.object.eat(other.object)
        self.side[dir] = other
        other.side[-dir] = self
    def closed(self):
        return all(value is not None for value in self.side.values())
class CitySegment(NonFieldSegment):
    def __init__(self, tile: Tile, data: dict[str, Any]) -> None:
        super().__init__(Connectable.City, tile, data)
        self.isCathedral: bool = False
        self.trader: TraderCounter | None = None
        for feature in data.get("features", []):
            if feature["type"] == "Cathedral":
                self.isCathedral = True
            if feature["type"] == "TradeCounter":
                self.trader = TraderCounter[feature["counter"]]
class RoadSegment(NonFieldSegment):
    def __init__(self, tile: Tile, data: dict[str, Any]) -> None:
        super().__init__(Connectable.Road, tile, data)
        self.isInn: bool = False
        for feature in data.get("features", []):
            if feature["type"] == "Inn":
                self.isInn = True
class RiverSegment(NonFieldSegment):
    def __init__(self, tile: Tile, data: dict[str, Any]) -> None:
        super().__init__(Connectable.River, tile, data)
class FieldSegment(Segment):
    def __init__(self, tile: Tile, data: dict[str, Any]) -> None:
        super().__init__(Connectable.Field, tile, data)
        self.side: dict[tuple[Dir, bool], Segment | None] = \
            {(Dir(((i + 1) % 8) // 2), i % 2 == 1): None for i in data["to"]}
        self.adjacentCity: list[Segment] = []
        self.adjacentCityTemp: list[int] = data["adjacent_city"]
        self.pennant = data.get("pennant", 0)
    def makeAdjacentCity(self, segs: list[Segment]):
        self.adjacentCity = [segs[i] for i in self.adjacentCityTemp]
        del self.adjacentCityTemp
    def turn(self, dir: Dir):
        self.side = {(d + dir, d2): value for (d, d2), value in self.side.items()}
    def inSideF(self, dir: Dir, up: bool):
        return (dir, up) in self.side
    def combineF(self, other: 'FieldSegment', dir: Dir, up: bool):
        other.object = self.object.eat(other.object)
        self.side[dir, up] = other
        other.side[-dir, not up] = self
    def closed(self):
        return all(value is not None for value in self.side.values())

class Object:
    def __init__(self, seg: Segment) -> None:
        self.type = seg.type
        self.segments: list[Segment] = [seg]
        self.tokens: list[Token] = []
    def eat(self, other: 'Object'):
        if other is self:
            return self
        self.segments.extend(other.segments)
        self.tokens.extend(other.tokens)
        for seg in other.segments:
            seg.object = self
        return self
    def closed(self):
        return all(seg.closed() for seg in self.segments)

class Feature:
    def __init__(self, parent: Tile | Segment, data: dict[str, Any]) -> None:
        self.parent = parent
        self.tokens: list[Token] = []
    @classmethod
    def make(cls, typ: str) -> Callable[[Tile | Segment, dict[str, Any]], 'Feature'] | None:
        return {"Cloister": Cloister}.get(typ, None)
class Cloister(Feature):
    pass

class Token:
    def __init__(self, parent: Tile | Segment | Object | Feature | 'Player' | Board, data: dict[str, Any]) -> None:
        self.parent = parent
    @classmethod
    def make(cls, typ: str) -> Callable[[Tile | Segment | Object | Feature | 'Player' | Board, dict[str, Any]], 'Token']:
        return {"follower": BaseFollower}[typ]
class Follower(Token):
    pass
class BaseFollower(Follower):
    pass

class Player:
    def __init__(self, board: Board) -> None:
        self.board = board
        self.tokens: list[Token] = []



