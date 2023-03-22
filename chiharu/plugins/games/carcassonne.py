from typing import Literal, Any, Generator, Type, Callable, Awaitable
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
    def __init__(self, packs: list[dict[str, Any]], players: list[Callable[[dict[str, Any]], Awaitable]]) -> None:
        self.tiles: dict[tuple[int, int], Tile] = {}
        self.deck: list[Tile] = []
        self.tokens: list[Token] = []
        self.players: list[Player] = [Player(self, i, p2) for i, p2 in enumerate(players)]
        for pack in packs:
            for t in pack["tiles"]:
                self.deck.extend(Tile(self, t) for i in range(t["num"]))
            for t in pack["tokens"]:
                if t["distribute"]:
                    for p in self.players:
                        p.tokens.extend(Token.make(t["name"])(p, p, t) for i in range(t["num"]))
                else:
                    self.tokens.extend(Token.make(t["name"])(self, None, t) for i in range(t["num"]))
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
    def __init__(self, board: Board, data: dict[str, Any]) -> None:
        self.id: int = data["id"]
        self.board = board
        self.sides: tuple[Connectable,...] = tuple(Connectable.fromChar(s) for s in data["sides"])
        self.segments: list[Segment] = [Segment.make(s["type"])(self, s) for s in data["segments"]] # type: ignore
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
    def make(cls, typ: str) -> Type['Segment']:
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
    def closed(self) -> bool:
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
    def checkTile(self):
        tiles: list[Tile] = []
        for seg in self.segments:
            if seg.tile not in tiles:
                tiles.append(seg.tile)
        return len(tiles)
    def checkPlayer(self) -> 'list[Player]':
        strengths: list[int] = [0 for i in range(len(self.segments[0].tile.board.players))]
        for token in self.tokens:
            if isinstance(token, Follower) and token.player is not None:
                strengths[token.player.id] += token.strength
        max_strength: tuple[list[int], int] = ([], 0)
        for i, strength in enumerate(strengths):
            if strength == max_strength[1]:
                max_strength[0].append(i)
            elif strength > max_strength[1]:
                max_strength = [i], strength
        if max_strength[1] == 0:
            return []
        return [self.segments[0].tile.board.players[i] for i in max_strength[0]]
    async def score(self, mid_game: bool):
        players = self.checkPlayer()
        if len(players) == 0:
            return
        score: int = 0
        match self.type:
            case Connectable.City:
                score = (2 if mid_game else 1) * self.checkTile()
            case Connectable.Road:
                score = self.checkTile()
            case Connectable.Field:
                complete_city: list[Object] = []
                for seg in self.segments:
                    if isinstance(seg, FieldSegment):
                        for segc in seg.adjacentCity:
                            if segc.object not in complete_city and segc.object.closed():
                                complete_city.append(segc.object)
                score = 3 * len(complete_city)
            case Connectable.River:
                pass
        if score != 0:
            for player in players:
                await player.addScore(score)

class Feature(ABC):
    def __init__(self, parent: Tile | Segment, data: dict[str, Any]) -> None:
        self.parent = parent
        self.tokens: list[Token] = []
    @classmethod
    def make(cls, typ: str) -> Type["Feature"] | None:
        return {"Cloister": Cloister}.get(typ, None)
    def canScore(self) -> bool:
        return False
    async def score(self, mid_game: bool):
        pass
class Cloister(Feature):
    def __init__(self, parent: Tile | Segment, data: dict[str, Any]) -> None:
        super().__init__(parent, data)
        assert isinstance(parent, Tile)
        self.adjacentRoad = [parent.segments[i] for i in data["adjacent_road"]]
    def canScore(self) -> bool:
        assert isinstance(self.parent, Tile)
        pos = more_itertools.only(key for key, value in self.parent.board.tiles.items() if value is self)
        if pos is None:
            return False
        return all((pos[0] + i, pos[0] + j) in self.parent.board.tiles for i in (-1, 0, 1) for j in (-1, 0, 1))
    async def score(self, mid_game: bool):
        assert isinstance(self.parent, Tile)
        pos = more_itertools.only(key for key, value in self.parent.board.tiles.items() if value is self)
        if pos is None:
            return
        token = more_itertools.only(self.tokens)
        if token is None or token.player is None:
            return
        await token.player.addScore(sum(1 if (pos[0] + i, pos[0] + j) in self.parent.board.tiles else 0 for i in (-1, 0, 1) for j in (-1, 0, 1)))

class Token(ABC):
    def __init__(self, parent: 'Tile | Segment | Object | Feature | Player | Board', player: 'Player | None', data: dict[str, Any]) -> None:
        self.parent = parent
        self.player = player
    @classmethod
    def make(cls, typ: str) -> Type['Token']:
        return {"follower": BaseFollower, "big follower": BigFollower, "builder": Builder, "pig": Pig}[typ]
    def canPut(self, seg: Segment | Feature):
        if isinstance(seg, Segment):
            return all(len(s.tokens) == 0 for s in seg.object.segments) and len(seg.tokens) == 0
        return len(seg.tokens) == 0
    def putOn(self, seg: Segment | Feature) -> bool:
        seg.tokens.append(self)
        return False
class Follower(Token):
    @property
    def strength(self) -> int:
        return 1
class Figure(Token):
    pass
class BaseFollower(Follower):
    pass
class BigFollower(Follower):
    @property
    def strength(self):
        return 2
class Builder(Figure):
    def canPut(self, seg: Segment | Feature):
        if isinstance(seg, Segment):
            return seg.type in (Connectable.City, Connectable.Road) and any(t.player is self.player for s in seg.object.segments for t in s.tokens)
        return False
    def putOn(self, seg: Segment | Feature):
        seg.tokens.append(self)
        return True
class Pig(Figure):
    pass

class Player:
    def __init__(self, board: Board, id: int, communication: Callable[[dict[str, Any]], Awaitable]) -> None:
        self.board = board
        self.id = id
        self.tokens: list[Token] = []
        self.score: int = 0
        self.handTile: Tile | None = None
        self.communication = communication
    async def addScore(self, score: int):
        self.score += score
    def drawTile(self):
        self.handTile = self.board.drawTile()
        return self.handTile
    async def putTile(self, tile: Tile, pos: tuple[int, int], orient: Dir) -> Literal[-1, -2, 1]:
        """-1：已有连接, -2：无法连接。2：放跟随者（-1不放，片段号/feature，which：跟随者名称，返回-1：没有跟随者，-2：无法放置），"""
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
        next_turn = False
        # put a follower
        pass_err: Literal[0, -1, -2] = 0
        while 1:
            ret_put: tuple[int, dict[str, Any]] = await self.communication({"id": 2, "last_err": pass_err})
            if ret_put[0] == -1:
                break
            if 0 <= ret_put[0] < len(tile.segments):
                seg: Segment | Feature = tile.segments[ret_put[0]]
            elif len(tile.segments) <= ret_put[0] < len(tile.segments) + len(tile.features):
                seg = tile.features[ret_put[0] - len(tile.segments)]
            else:
                pass_err = -2
                continue
            tokens = [token for token in self.tokens if isinstance(token, Token.make(ret_put[1].get("which", "follower")))]
            if len(tokens) == 0:
                pass_err = -1
                continue
            token = tokens[0]
            if not token.canPut(seg):
                pass_err = -2
                continue
            self.tokens.remove(token)
            next_turn = token.putOn(seg)
            break
        # score
        for seg in tile.segments:
            if seg.object.closed():
                await seg.object.score(True)
        for feature in tile.features:
            if feature.canScore():
                await feature.score(True)
        return 1

if __name__ == "__main__":
    b = Board(open_pack()["packs"][0:2], [])
    b.deck[2].debugImage().show()
