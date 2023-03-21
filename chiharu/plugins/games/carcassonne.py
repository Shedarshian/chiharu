from typing import Literal, Any, Callable, Generator
import random, itertools, more_itertools, json
from enum import Enum, auto
from abc import ABC, abstractmethod
from PIL import Image, ImageDraw, ImageFont

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
    def __radd__(self, other: tuple[int, int]):
        return other[0] + self.corr()[0], other[1] + self.corr()[1]
    def __neg__(self):
        return Dir((self.value + 2) % 4)
class TraderCounter(Enum):
    Wine = auto()
    Grain = auto()
    Cloth = auto()

def open_pack():
    with open("./carcassonne.json", encoding="utf-8") as f:
        return json.load(f)
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
        self.popTile(start_tile)
        self.tiles[0, 0] = start_tile
    def popTile(self, tile: 'Tile'):
        self.deck.remove(tile)
    def drawTile(self):
        tile = random.choice(self.deck)
        self.popTile(tile)
        return tile

class Tile:
    def __init__(self, data: dict[str, Any]) -> None:
        self.id: int = data["id"]
        self.sides: tuple[Connectable,...] = tuple(Connectable.fromChar(s) for s in data["sides"])
        self.segments: list[Segment] = [Segment.make(s["type"])(self, s) for s in data["segments"]]
        for seg in self.segments:
            if isinstance(seg, FieldSegment):
                seg.makeAdjacentCity(self.segments)
            elif isinstance(seg, NonFieldSegment):
                seg.makeAdjacentRoad(self.segments)
        self.features: list[Feature] = [f(self, s) for s in data.get("features", []) if (f := Feature.make(s["type"])) is not None]
        self.tokens: list[Token] = []
        self.connectTile: list[Tile | None] = [None] * 4
        self.orient: Dir = Dir.UP
    def sidesToSegment(self, dir: Dir):
        return more_itertools.only([seg for seg in self.segments if seg.inSide(dir) and isinstance(seg, NonFieldSegment)])
    def sidesToSegmentF(self, dir: Dir, up: bool):
        return more_itertools.only([seg for seg in self.segments if seg.inSideF(dir, up) and isinstance(seg, FieldSegment)])
    def turn(self, orient: Dir):
        self.orient = self.orient + orient
        self.sides = self.sides[4 - orient.value:] + self.sides[:4 - orient.value]
        self.connectTile = self.connectTile[4 - orient.value:] + self.connectTile[:4 - orient.value]
        for s in self.segments:
            s.turn(orient)
    def checkConnect(self, tile: 'Tile', dir: Dir, orient: Dir):
        """-1: 已有连接, -2: 无法连接"""
        if self.connectTile[dir.value] is not None:
            return -1
        sides = tile.sides[4 - orient.value:] + tile.sides[:4 - orient.value]
        if self.sides[dir.value] != sides[(-dir).value]:
            return -2
        return 1
    def addConnect(self, tile: 'Tile', dir: Dir):
        if (s1 := self.sidesToSegment(dir)) is not None and (s2 := tile.sidesToSegment(-dir)) is not None:
            s1.combine(s2)
        if (s1 := self.sidesToSegmentF(dir, False)) is not None and (s2 := tile.sidesToSegmentF(-dir, True)) is not None:
            s1.combineF(s2)
        if (s1 := self.sidesToSegmentF(dir, True)) is not None and (s2 := tile.sidesToSegmentF(-dir, False)) is not None:
            s1.combineF(s2)
        return 1
    def debugImage(self):
        img = Image.new("RGBA", (128, 128), "white")
        dr = ImageDraw.Draw(img)
        corr = (19, 19)
        ci = 1
        for i, c in zip(range(4), self.sides):
            dr.rectangle([(0, 0, 128, 2), (126, 0, 128, 128), (0, 126, 128, 128), (0, 0, 2, 128)][i], {Connectable.City: "brown", Connectable.Field: "green", Connectable.Road: "black", Connectable.River: "blue"}[c])
        citycorrs: list[tuple[int, int]] = []
        for seg in self.segments:
            if isinstance(seg, NonFieldSegment):
                for dir in seg.side.keys():
                    if dir == Dir.UP:
                        dr.line((corr[0], 0, corr[0], corr[1]), seg.color, 3)
                    elif dir == Dir.RIGHT:
                        dr.line((128, corr[1], corr[0], corr[1]), seg.color, 3)
                    elif dir == Dir.DOWN:
                        dr.line((corr[0], 128, corr[0], corr[1]), seg.color, 3)
                    elif dir == Dir.LEFT:
                        dr.line((0, corr[1], corr[0], corr[1]), seg.color, 3)
            elif isinstance(seg, FieldSegment):
                for du in seg.side.keys():
                    cr = {(Dir.UP, True): (32, 0), (Dir.UP, False): (96, 0), (Dir.RIGHT, True): (128, 32), (Dir.RIGHT, False): (128, 96), (Dir.DOWN, True): (96, 128), (Dir.DOWN, False): (32, 128), (Dir.LEFT, True): (0, 96), (Dir.LEFT, False): (0, 32)}[du]
                    dr.line(cr + corr, seg.color, 3)
                for city in seg.adjacentCity:
                    dr.line((citycorrs[self.segments.index(city)], corr), "gray", 3)
            citycorrs.append(corr)
            corr = (corr[0] + 10 * ci, corr[1] + 10)
            ci += 1
            if corr[0] >= 110:
                corr = (corr[0] - 110, corr[1])
        corr = (19, 19)
        ci = 1
        for seg in self.segments:
            if isinstance(seg, NonFieldSegment):
                for road in seg.adjacentRoad:
                    dr.line((citycorrs[self.segments.index(road)], corr), "gray", 3)
            corr = (corr[0] + 10 * ci, corr[1] + 10)
            ci += 1
            if corr[0] >= 110:
                corr = (corr[0] - 110, corr[1])
        corr = (19, 19)
        ci = 1
        for seg in self.segments:
            if isinstance(seg, CitySegment):
                dr.ellipse((corr[0] - 5, corr[1] - 5, corr[0] + 5, corr[1] + 5), seg.color)
                if seg.pennant != 0:
                    font = ImageFont.truetype("msyhbd.ttc", 10)
                    dr.text((corr[0] + 1, corr[1]), str(seg.pennant), "black", font, anchor="mm")
            elif isinstance(seg, RoadSegment):
                dr.ellipse((corr[0] - 5, corr[1] - 5, corr[0] + 5, corr[1] + 5), "white", outline="black", width=2)
            elif isinstance(seg, RiverSegment):
                dr.ellipse((corr[0] - 5, corr[1] - 5, corr[0] + 5, corr[1] + 5), seg.color)
            elif isinstance(seg, FieldSegment):
                dr.ellipse((corr[0] - 5, corr[1] - 5, corr[0] + 5, corr[1] + 5), seg.color)
                for city in seg.adjacentCity:
                    citycorrs[self.segments.index(city)]
            corr = (corr[0] + 10 * ci, corr[1] + 10)
            ci += 1
            if corr[0] >= 110:
                corr = (corr[0] - 110, corr[1])
        return img

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
    @property
    def color(self):
        return "black"
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
        self.adjacentRoad: list[Segment] = []
        self.adjacentRoadTemp: list[int] = data["adjacent_road"]
    def makeAdjacentRoad(self, segs: list[Segment]):
        self.adjacentRoad = [segs[i] for i in self.adjacentRoadTemp]
        del self.adjacentRoadTemp
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
        self.pennant: int = data.get("pennant", 0)
        self.isCathedral: bool = False
        self.trader: TraderCounter | None = None
        for feature in data.get("features", []):
            if feature["type"] == "Cathedral":
                self.isCathedral = True
            if feature["type"] == "TradeCounter":
                self.trader = TraderCounter[feature["counter"]]
    @property
    def color(self):
        return "brown"
class RoadSegment(NonFieldSegment):
    def __init__(self, tile: Tile, data: dict[str, Any]) -> None:
        super().__init__(Connectable.Road, tile, data)
        self.isInn: bool = False
        for feature in data.get("features", []):
            if feature["type"] == "Inn":
                self.isInn = True
    @property
    def color(self):
        return "black"
class RiverSegment(NonFieldSegment):
    def __init__(self, tile: Tile, data: dict[str, Any]) -> None:
        super().__init__(Connectable.River, tile, data)
    @property
    def color(self):
        return "blue"
class FieldSegment(Segment):
    def __init__(self, tile: Tile, data: dict[str, Any]) -> None:
        super().__init__(Connectable.Field, tile, data)
        self.side: dict[tuple[Dir, bool], Segment | None] = \
            {(Dir(((i + 1) % 8) // 2), i % 2 == 1): None for i in data["to"]}
        self.adjacentCity: list[Segment] = []
        self.adjacentCityTemp: list[int] = data["adjacent_city"]
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
    @property
    def color(self):
        return "green"

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

class Feature(ABC):
    def __init__(self, parent: Tile | Segment, data: dict[str, Any]) -> None:
        self.parent = parent
        self.tokens: list[Token] = []
    @classmethod
    def make(cls, typ: str) -> Callable[[Tile | Segment, dict[str, Any]], 'Feature'] | None:
        return {"Cloister": Cloister}.get(typ, None)
class Cloister(Feature):
    def __init__(self, parent: Tile | Segment, data: dict[str, Any]) -> None:
        super().__init__(parent, data)
        assert isinstance(parent, Tile)
        self.adjacentRoad = [parent.segments[i] for i in data["adjacent_road"]]

class Token(ABC):
    def __init__(self, parent: 'Tile | Segment | Object | Feature | Player | Board', data: dict[str, Any]) -> None:
        self.parent = parent
    @classmethod
    def make(cls, typ: str) -> Callable[['Tile | Segment | Object | Feature | Player | Board', dict[str, Any]], 'Token']:
        return {"follower": BaseFollower, "big follower": BigFollower, "builder": Builder, "pig": Pig}[typ]
class Follower(Token):
    def __init__(self, parent: 'Tile | Segment | Object | Feature | Player | Board', data: dict[str, Any]) -> None:
        super().__init__(parent, data)
        self.strength = 1
class Figure(Token):
    pass
class BaseFollower(Follower):
    pass
class BigFollower(Follower):
    def __init__(self, parent: 'Tile | Segment | Object | Feature | Player | Board', data: dict[str, Any]) -> None:
        super().__init__(parent, data)
        self.strength = 2
class Builder(Figure):
    pass
class Pig(Figure):
    pass

class Player:
    def __init__(self, board: Board) -> None:
        self.board = board
        self.tokens: list[Token] = []
        self.handTile: Tile | None = None
    def drawTile(self):
        self.handTile = self.board.drawTile()
        return self.handTile
    def putTile(self, tile: Tile, pos: tuple[int, int], orient: Dir) -> Generator[Literal[2], Any, Literal[-1, -2, 1]]:
        """-1：已有连接, -2：无法连接。2：放跟随者（-1不放），"""
        if pos in self.board.tiles:
            return -1
        for dr in Dir:
            side = pos + dr
            if side in self.board.tiles:
                ret = self.board.tiles[side].checkConnect(tile, -dr, orient)
                if ret < 0:
                    return ret
        tile.turn(orient)
        self.board.tiles[pos] = tile
        for dr in Dir:
            self.board.tiles[pos + dr].addConnect(tile, -dr)
        # put a follower
        while 1:
            ret_put: tuple[int, dict[str, Any]] = (yield 2)
            if ret_put[0] == -1:
                break
            pass
        return 1

if __name__ == "__main__":
    b = Board(open_pack()["packs"][0:2], 1)
    b.deck[2].debugImage().show()
