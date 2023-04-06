from typing import Literal, Any, Generator, Type, Callable, Awaitable, TypeVar
import random, itertools, more_itertools, json
from enum import Enum, auto
from abc import ABC, abstractmethod
from PIL import Image, ImageDraw, ImageFont

class CantPutError(Exception):
    pass
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
    def transpose(self):
        return (None, Image.ROTATE_270, Image.ROTATE_180, Image.ROTATE_90)[self.value]
class TraderCounter(Enum):
    Wine = auto()
    Grain = auto()
    Cloth = auto()
def turn(pos: tuple[int, int], dir: Dir):
    if dir == Dir.UP:
        return pos
    if dir == Dir.RIGHT:
        return 64 - pos[1], pos[0]
    if dir == Dir.DOWN:
        return 64 - pos[0], 64 - pos[1]
    return pos[1], 64 - pos[0]

TToken = TypeVar("TToken", bound="Token")

def open_pack():
    from pathlib import Path
    with open(Path(__file__).parent / "carcassonne.json", encoding="utf-8") as f:
        return json.load(f)
def open_img(name: str):
    from pathlib import Path
    return Image.open(Path(__file__).parent / "carcassonne_asset" / (name + ".png")).convert("RGBA")
class Board:
    def __init__(self, packs: list[dict[str, Any]], player_names: list[str]) -> None:
        self.tiles: dict[tuple[int, int], Tile] = {}
        self.deck: list[Tile] = []
        self.tokens: list[Token] = []
        self.players: list[Player] = [Player(self, i, name) for i, name in enumerate(player_names)]
        self.tileimgs: dict[int, Image.Image] = {}
        self.tokenimgs: dict[int, Image.Image] = {}
        current_pos: int = 0
        for pack in packs:
            self.tileimgs[pack["id"]] = open_img(str(pack["id"]))
            self.tokenimgs[pack["id"]] = open_img("token" + str(pack["id"]))
            for t in pack["tiles"]:
                img = self.tileimgs[pack["id"]].crop(((t["id"] % 5) * 64, (t["id"] // 5) * 64, (t["id"] % 5 + 1) * 64, (t["id"] // 5 + 1) * 64))
                self.deck.extend(Tile(self, t, img) for i in range(t["num"]))
            for t in pack["tokens"]:
                img = self.tokenimgs[pack["id"]].crop(tuple(t["image"]))
                if t["distribute"]:
                    for p in self.players:
                        p.tokens.extend(Token.make(t["name"])(p, p, t, img) for i in range(t["num"]))
                else:
                    self.tokens.extend(Token.make(t["name"])(self, None, t, img) for i in range(t["num"]))
        start_id = packs[0]["starting_tile"]
        start_tile = [t for t in self.deck if t.id == start_id][0]
        self.popTile(start_tile)
        self.tiles[0, 0] = start_tile
        self.current_player_id = 0
        random.shuffle(self.deck)
        self.players[0].tokens.sort(key=Token.key)
        self.token_pos: dict[Type[Token], int] = {}
        xpos = 0
        last_key: tuple[int, int] = (-1, -2)
        for t in self.players[0].tokens:
            if t.key() != last_key:
                self.token_pos[type(t)] = xpos
                last_key = t.key()
            xpos += t.image().size[0] + 4
        self.token_length = xpos
        self.font_name = ImageFont.truetype("msyhbd.ttc", 16)
        self.font_score = ImageFont.truetype("msyhbd.ttc", 24)
    @property
    def current_player(self):
        return self.players[self.current_player_id]
    def popTile(self, tile: 'Tile'):
        self.deck.remove(tile)
    def drawTile(self):
        tile = self.deck[0]
        self.popTile(tile)
        return tile
    def nextPlayer(self):
        self.current_player_id += 1
        if self.current_player_id >= len(self.players):
            self.current_player_id -= len(self.players)
        return 1
    def endGameScore(self):
        for tile in self.tiles.values():
            for seg in tile.segments:
                if len(seg.tokens) != 0:
                    seg.object.scoreFinal()
            for feature in tile.features:
                if len(feature.tokens) != 0:
                    feature.scoreFinal()
    def winner(self):
        maxScore: int = 0
        maxPlayer: list[Player] = []
        for player in self.players:
            if player.score > maxScore:
                maxScore = player.score
                maxPlayer = [player]
            elif player.score == maxScore:
                maxPlayer.append(player)
        return maxScore, maxPlayer
    def canPutTile(self, tile: 'Tile', pos: tuple[int, int], orient: Dir) -> Literal[-1, -2, -3, 1]:
        """-1：已有连接, -2：无法连接，-3：没有挨着。"""
        if pos in self.tiles:
            return -1
        if all(pos + dr not in self.tiles for dr in Dir):
            return -3
        for dr in Dir:
            side = pos + dr
            if side in self.tiles:
                ret = self.tiles[side].checkConnect(tile, -dr, orient)
                if ret < 0:
                    return ret
        return 1
    def checkTilePosition(self, tile: 'Tile'):
        leftmost = min(i for i, j in self.tiles.keys())
        rightmost = max(i for i, j in self.tiles.keys())
        uppermost = min(j for i, j in self.tiles.keys())
        lowermost = max(j for i, j in self.tiles.keys())
        for i in range(leftmost - 1, rightmost + 2):
            for j in range(uppermost - 1, lowermost + 2):
                for orient in Dir:
                    if self.canPutTile(tile, (i, j), orient) == 1:
                        return True
        return False

    def tileImages(self, choose_follower: tuple[int, int] | None = None, debug: bool=False):
        leftmost = min(i for i, j in self.tiles.keys())
        rightmost = max(i for i, j in self.tiles.keys())
        uppermost = min(j for i, j in self.tiles.keys())
        lowermost = max(j for i, j in self.tiles.keys())
        img = Image.new("RGBA", ((rightmost - leftmost + 1) * 64 + 46, (lowermost - uppermost + 1) * 64 + 46))
        dr = ImageDraw.Draw(img)
        def pos(w: int, h: int, *offsets: tuple[int, int]):
            return w * 64 + sum(c[0] for c in offsets) + 32, h * 64 + sum(c[1] for c in offsets) + 32
        def posshift(w: int, h: int, *offsets: tuple[int, int]):
            return (w - leftmost) * 64 + sum(c[0] for c in offsets) + 32, (h - uppermost) * 64 + sum(c[1] for c in offsets) + 32
        for (i, j), tile in self.tiles.items():
            img.paste(tile.image(debug), posshift(i, j))
        # choose follower
        font = ImageFont.truetype("msyhbd.ttc", 10)
        if choose_follower is not None:
            tile = self.tiles[choose_follower]
            i = ord('a')
            for seg in tile.segments:
                tpos = turn(seg.token_pos, tile.orient)
                dr.ellipse((posshift(*choose_follower, (tpos[0] - 6, tpos[1] - 6)), posshift(*choose_follower, (tpos[0] + 6, tpos[1] + 6))), "white", "black", 1)
                dr.text(posshift(*choose_follower, tpos), chr(i), "black", font, "mm")
                i += 1
            for feature in tile.features:
                if feature.canPlace():
                    tpos = turn(feature.token_pos, tile.orient)
                    dr.ellipse((posshift(*choose_follower, (tpos[0] - 6, tpos[1] - 6)), posshift(*choose_follower, (tpos[0] + 6, tpos[1] + 6))), "white", "black", 1)
                    dr.text(posshift(*choose_follower, tpos), chr(i), "black", font, "mm")
                i += 1
        # grid
        width = rightmost - leftmost
        height = lowermost - uppermost
        dr.line(pos(0, 0, (-10, -10)) + pos(0, height + 1, (-10, 10)), "gray")
        dr.line(pos(0, 0, (-1, -10)) + pos(0, height + 1, (-1, 10)), "gray")
        for i in range(0, width + 1):
            dr.line(pos(i, 0, (0, -10)) + pos(i, height + 1, (0, 10)), "gray")
            dr.line(pos(i, 0, (63, -10)) + pos(i, height + 1, (63, 10)), "gray")
        dr.line(pos(width + 1, 0, (0, -10)) + pos(width + 1, height + 1, (0, 10)), "gray")
        dr.line(pos(width + 1, 0, (10, -10)) + pos(width + 1, height + 1, (10, 10)), "gray")
        dr.line(pos(0, 0, (-10, -10)) + pos(width + 1, 0, (10, -10)), "gray")
        dr.line(pos(0, 0, (-10, -1)) + pos(width + 1, 0, (10, -1)), "gray")
        for j in range(0, height + 1):
            dr.line(pos(0, j, (-10, 0)) + pos(width + 1, j, (10, 0)), "gray")
            dr.line(pos(0, j, (-10, 63)) + pos(width + 1, j, (10, 63)), "gray")
        dr.line(pos(0, height + 1, (-10, 0)) + pos(width + 1, height + 1, (10, 0)), "gray")
        dr.line(pos(0, height + 1, (-10, 10)) + pos(width + 1, height + 1, (10, 10)), "gray")
        # text
        def alpha(n):
            if n <= 25: return chr(ord('A') + n)
            return chr(ord('A') + n % 26 - 1) + chr(ord('A') + n // 26)
        dr.text(pos(0, 0, (-5, -15)), 'A', "black", font, "mb")
        for i in range(0, width + 1):
            dr.text(pos(i, 0, (32, -15)), alpha(i + 1), "black", font, "mb")
        dr.text(pos(width + 1, 0, (5, -15)), alpha(width + 2), "black", font, "mb")
        dr.text(pos(0, 0, (-15, -5)), '0', "black", font, "rm")
        for j in range(0, height + 1):
            dr.text(pos(0, j, (-15, 32)), str(j + 1), "black", font, "rm")
        dr.text(pos(0, height + 1, (-15, 5)), str(height + 2), "black", font, "rm")
        # token
        for (i, j), tile in self.tiles.items():
            for seg in tile.segments:
                next = 0
                for token in seg.tokens:
                    t = token.image()
                    img.alpha_composite(t, posshift(i, j, turn(seg.token_pos, tile.orient), (-t.size[0] // 2, -t.size[1] // 2), (next * 4, next * 4)))
                    next += 1
            next = 0
            for token in tile.tokens:
                t = token.image()
                img.alpha_composite(t, posshift(i, j, turn(tile.token_pos, tile.orient), (-t.size[0] // 2, -t.size[1] // 2), (next * 4, next * 4)))
                next += 1
            for feature in tile.features:
                next = 0
                for token in feature.tokens:
                    t = token.image()
                    img.alpha_composite(t, posshift(i, j, turn(feature.token_pos, tile.orient), (-t.size[0] // 2, -t.size[1] // 2), (next * 4, next * 4)))
                    next += 1
        return img
    def playerImage(self):
        imgs = [p.image() for p in self.players]
        img = Image.new("RGBA", (imgs[0].size[0], 24 * len(self.players)))
        for i, pimg in enumerate(imgs):
            img.alpha_composite(pimg, (0, i * 24))
        return img
    def handTileImage(self):
        return self.current_player.handTileImage()

    def image(self, choose_follower: tuple[int, int] | None = None, debug: bool=False):
        player_img = self.playerImage()
        handtile_img = self.handTileImage()
        tile_img = self.tileImages(choose_follower, debug)
        p1, p2 = player_img.size
        h1, h2 = handtile_img.size
        t1, t2 = tile_img.size
        img = Image.new("RGBA", (max(p1 + h1, t1), max(p2, h2) + t2), "AntiqueWhite")
        dr = ImageDraw.Draw(img)
        px, py, hx, hy, tx, ty = (0,) * 6
        if p2 > h2:
            py = 0
            hy = (p2 - h2) // 2
        else:
            py = (h2 - p2) // 2
            hy = 0
        ty = max(p2, h2)
        if p1 + h1 > t1:
            px = 0
            hx = p1
            tx = (p1 + h1 - t1) // 2
        else:
            px = (t1 - p1 - h1) // 2
            hx = px + p1
            tx = 0
        dr.rectangle((0, max(p2, h2), max(p1 + h1, t1), max(p2, h2) + t2), "LightCyan")
        img.alpha_composite(player_img, (px, py))
        img.alpha_composite(handtile_img, (hx, hy))
        img.alpha_composite(tile_img, (tx, ty))
        return img
    def saveImg(self, choose_follower: tuple[int, int] | None = None, debug: bool=False):
        from .. import config
        name = 'ccs' + str(random.randint(0, 9) + self.current_player_id * 10) + '.png'
        self.image(choose_follower, debug).save(config.img(name))
        return config.cq.img(name)

class CanToken(ABC):
    def __init__(self) -> None:
        self.tokens: list[Token] = []
    def removeAllFollowers(self):
        for token in self.tokens:
            if token.player is not None:
                token.player.tokens.append(token)
                token.parent = token.player
        self.tokens = [token for token in self.tokens if token.player is None]

class Tile(CanToken):
    def __init__(self, board: Board, data: dict[str, Any], img: Image.Image) -> None:
        super().__init__()
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
        self.connectTile: list[Tile | None] = [None] * 4
        self.orient: Dir = Dir.UP
        self.token_pos: tuple[int, int] = (data.get("posx", 32), data.get("posy", 32))
        self.img = img
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
            s1.combine(s2, dir)
        if (s1 := self.sidesToSegmentF(dir, False)) is not None and (s2 := tile.sidesToSegmentF(-dir, True)) is not None:
            s1.combineF(s2, dir, False)
        if (s1 := self.sidesToSegmentF(dir, True)) is not None and (s2 := tile.sidesToSegmentF(-dir, False)) is not None:
            s1.combineF(s2, dir, True)
        return 1
    def debugImage(self):
        img = Image.new("RGBA", (64, 64), "white")
        dr = ImageDraw.Draw(img)
        img.paste(self.img)
        ci = 1
        for i, c in zip(range(4), self.sides):
            dr.rectangle([(0, 0, 64, 2), (62, 0, 64, 64), (0, 62, 64, 64), (0, 0, 2, 64)][i], {Connectable.City: "brown", Connectable.Field: "green", Connectable.Road: "black", Connectable.River: "blue"}[c])
        citycorrs: list[tuple[int, int]] = []
        for seg in self.segments:
            corr = seg.token_pos
            if isinstance(seg, NonFieldSegment):
                for dir in seg.side.keys():
                    if dir == Dir.UP:
                        dr.line((corr[0], 0, corr[0], corr[1]), seg.color, 2)
                    elif dir == Dir.RIGHT:
                        dr.line((64, corr[1], corr[0], corr[1]), seg.color, 2)
                    elif dir == Dir.DOWN:
                        dr.line((corr[0], 64, corr[0], corr[1]), seg.color, 2)
                    elif dir == Dir.LEFT:
                        dr.line((0, corr[1], corr[0], corr[1]), seg.color, 2)
            elif isinstance(seg, FieldSegment):
                for du in seg.side.keys():
                    cr = {(Dir.UP, True): (16, 0), (Dir.UP, False): (48, 0), (Dir.RIGHT, True): (64, 16), (Dir.RIGHT, False): (64, 48), (Dir.DOWN, True): (48, 64), (Dir.DOWN, False): (16, 64), (Dir.LEFT, True): (0, 48), (Dir.LEFT, False): (0, 16)}[du]
                    dr.line(cr + corr, seg.color, 2)
                for city in seg.adjacentCity:
                    dr.line((citycorrs[self.segments.index(city)], corr), "gray", 2)
            citycorrs.append(corr)
            ci += 1
        ci = 1
        for seg in self.segments:
            corr = seg.token_pos
            if isinstance(seg, NonFieldSegment):
                for road in seg.adjacentRoad:
                    dr.line((citycorrs[self.segments.index(road)], corr), "gray", 2)
            ci += 1
        ci = 1
        for seg in self.segments:
            corr = seg.token_pos
            if isinstance(seg, CitySegment):
                dr.ellipse((corr[0] - 3, corr[1] - 3, corr[0] + 3, corr[1] + 3), seg.color)
                if seg.pennant != 0:
                    font = ImageFont.truetype("msyhbd.ttc", 10)
                    dr.text((corr[0] + 1, corr[1]), str(seg.pennant), "black", font, anchor="mm")
            elif isinstance(seg, RoadSegment):
                dr.ellipse((corr[0] - 3, corr[1] - 3, corr[0] + 3, corr[1] + 3), "white", outline="black", width=2)
            elif isinstance(seg, RiverSegment):
                dr.ellipse((corr[0] - 3, corr[1] - 3, corr[0] + 3, corr[1] + 3), seg.color)
            elif isinstance(seg, FieldSegment):
                dr.ellipse((corr[0] - 3, corr[1] - 3, corr[0] + 3, corr[1] + 3), seg.color)
                for city in seg.adjacentCity:
                    citycorrs[self.segments.index(city)]
            ci += 1
        return img
    def image(self, debug: bool=False):
        if debug:
            return self.debugImage()
        if self.orient == Dir.UP:
            return self.img
        return self.img.transpose(self.orient.transpose())

class Segment(CanToken):
    def __init__(self, typ: Connectable, tile: Tile, data: dict[str, Any]) -> None:
        super().__init__()
        self.type = typ
        self.tile = tile
        self.features: list[Feature] = []
        self.object = Object(self)
        self.token_pos: tuple[int, int] = (data.get("posx", 32), data.get("posy", 32))
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

class Object(CanToken):
    def __init__(self, seg: Segment) -> None:
        super().__init__()
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
    def checkPennant(self):
        return sum(seg.pennant for seg in self.segments if isinstance(seg, CitySegment))
    def checkPlayer(self) -> 'list[Player]':
        strengths: list[int] = [0 for i in range(len(self.segments[0].tile.board.players))]
        for seg in self.segments:
            for token in seg.tokens:
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
    def checkScore(self, mid_game: bool):
        score: int = 0
        match self.type:
            case Connectable.City:
                score = (2 if mid_game else 1) * (self.checkTile() + self.checkPennant())
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
        return score
    def removeAllFollowers(self):
        super().removeAllFollowers()
        for seg in self.segments:
            seg.removeAllFollowers()
    def score(self) -> Generator[dict[str, Any], dict[str, Any], None]:
        players = self.checkPlayer()
        score = self.checkScore(True)
        if score != 0:
            for player in players:
                yield from player.addScore(score)
        self.removeAllFollowers()
    def scoreFinal(self):
        players = self.checkPlayer()
        score = self.checkScore(False)
        if score != 0:
            for player in players:
                player.addScoreFinal(score)
        self.removeAllFollowers()

class Feature(CanToken):
    def __init__(self, parent: Tile | Segment, data: dict[str, Any]) -> None:
        super().__init__()
        self.parent = parent
        self.token_pos: tuple[int, int] = (data.get("posx", 32), data.get("posy", 32))
    @classmethod
    def make(cls, typ: str) -> Type["Feature"] | None:
        return {"Cloister": Cloister}.get(typ, None)
    def canScore(self) -> bool:
        return False
    def score(self) -> Generator[dict[str, Any], dict[str, Any], None]:
        return
        yield {}
    def scoreFinal(self):
        return
    def canPlace(self) -> bool:
        return False
class Cloister(Feature):
    def __init__(self, parent: Tile | Segment, data: dict[str, Any]) -> None:
        super().__init__(parent, data)
        assert isinstance(parent, Tile)
        self.adjacentRoad = [parent.segments[i] for i in data["adjacent_road"]]
    def canScore(self) -> bool:
        assert isinstance(self.parent, Tile)
        pos = more_itertools.only(key for key, value in self.parent.board.tiles.items() if value is self.parent)
        if pos is None:
            return False
        return all((pos[0] + i, pos[0] + j) in self.parent.board.tiles for i in (-1, 0, 1) for j in (-1, 0, 1))
    def score(self) -> Generator[dict[str, Any], dict[str, Any], None]:
        assert isinstance(self.parent, Tile)
        pos = more_itertools.only(key for key, value in self.parent.board.tiles.items() if value is self.parent)
        if pos is None:
            return
        token = more_itertools.only(self.tokens)
        if token is None or token.player is None:
            return
        yield from token.player.addScore(sum(1 if (pos[0] + i, pos[1] + j) in self.parent.board.tiles else 0 for i in (-1, 0, 1) for j in (-1, 0, 1)))
        self.removeAllFollowers()
    def scoreFinal(self):
        assert isinstance(self.parent, Tile)
        pos = more_itertools.only(key for key, value in self.parent.board.tiles.items() if value is self.parent)
        if pos is None:
            return
        token = more_itertools.only(self.tokens)
        if token is None or token.player is None:
            return
        token.player.addScoreFinal(sum(1 if (pos[0] + i, pos[1] + j) in self.parent.board.tiles else 0 for i in (-1, 0, 1) for j in (-1, 0, 1)))
        self.removeAllFollowers()
    def canPlace(self) -> bool:
        return True

class Token(ABC):
    def __init__(self, parent: 'Tile | Segment | Object | Feature | Player | Board', player: 'Player | None', data: dict[str, Any], img: Image.Image) -> None:
        self.parent = parent
        self.player = player
        self.img = img
    @classmethod
    def make(cls, typ: str) -> Type['Token']:
        return {"follower": BaseFollower, "big follower": BigFollower, "builder": Builder, "pig": Pig}[typ]
    def canPut(self, seg: Segment | Feature):
        if isinstance(seg, Segment):
            return all(len(s.tokens) == 0 for s in seg.object.segments) and len(seg.tokens) == 0
        return len(seg.tokens) == 0
    def putOn(self, seg: Segment | Feature) -> bool:
        seg.tokens.append(self)
        self.parent = seg
        return False
    def image(self):
        if self.player is None:
            return self.img.copy()
        if isinstance(self.parent, FieldSegment):
            mask = open_img("token0").crop((16, 0, 32, 16))
        else:
            mask = self.img
        x = Image.new("RGBA", (16, 16))
        x.paste(Image.new("RGBA", (16, 16), self.player.tokenColor), (0, 0, 16, 16), mask)
        return x
    def key(self) -> tuple[int, int]:
        return (-1, -1)
class Follower(Token):
    @property
    def strength(self) -> int:
        return 1
class Figure(Token):
    pass
class BaseFollower(Follower):
    def key(self) -> tuple[int, int]:
        return (0, 0)
class BigFollower(Follower):
    @property
    def strength(self):
        return 2
    def image(self):
        return super().image().resize((24, 24))
    def key(self) -> tuple[int, int]:
        return (1, 0)
class Builder(Figure):
    def canPut(self, seg: Segment | Feature):
        if isinstance(seg, Segment):
            return seg.type in (Connectable.City, Connectable.Road) and any(t.player is self.player for s in seg.object.segments for t in s.tokens)
        return False
    def putOn(self, seg: Segment | Feature):
        seg.tokens.append(self)
        return True
    def key(self) -> tuple[int, int]:
        return (2, 0)
class Pig(Figure):
    def key(self) -> tuple[int, int]:
        return (2, 1)

class PlayerState(Enum):
    End = auto()
    TileDrawn = auto()
    PuttingFollower = auto()
    InturnScoring = auto()
class Player:
    def __init__(self, board: Board, id: int, name: str) -> None:
        self.board = board
        self.id = id
        self.name = name[:20]
        self.tokens: list[Token] = []
        self.score: int = 0
        self.handTile: Tile | None = None
        self.state: PlayerState = PlayerState.End
        self.stateGen: Generator[dict[str, Any], dict[str, Any], Literal[-1, -2, -3, 1]] | None = None
    def addScore(self, score: int) -> Generator[dict[str, Any], dict[str, Any], None]:
        self.score += score
        return
        yield {}
    def addScoreFinal(self, score: int):
        self.score += score
    def drawTile(self):
        self.handTile = self.board.drawTile()
        self.state = PlayerState.TileDrawn
        checked: int = 0
        while self.handTile is not None and not self.board.checkTilePosition(self.handTile):
            checked += 1
            self.board.deck.append(self.handTile)
            self.handTile = self.board.drawTile()
            if checked >= len(self.board.deck):
                raise CantPutError
        return self.handTile
    @property
    def tokenColor(self):
        return ["red", "blue", "gray", "green", "yellow", "black"][self.id]
    @property
    def show_name(self):
        show_name = self.name
        if self.board.font_name.getlength(self.name) > 80:
            while self.board.font_name.getlength(show_name + "...") > 80:
                show_name = show_name[:-1]
            show_name += "..."
        return show_name
    def putTile(self, pos: tuple[int, int], orient: Dir) -> Generator[dict[str, Any], dict[str, Any], Literal[-1, -2, -3, 1]]:
        """-1：已有连接, -2：无法连接，-3：没有挨着。2：放跟随者（-1不放，片段号/feature，which：跟随者名称，返回-1：没有跟随者，-2：无法放置），"""
        tile = self.handTile
        if tile is None:
            return -3
        if pos in self.board.tiles:
            return -1
        if all(pos + dr not in self.board.tiles for dr in Dir):
            return -3
        for dr in Dir:
            side = pos + dr
            if side in self.board.tiles:
                ret = self.board.tiles[side].checkConnect(tile, -dr, orient)
                if ret < 0:
                    return ret
        tile.turn(orient)
        self.board.tiles[pos] = tile
        for dr in Dir:
            if pos + dr in self.board.tiles:
                self.board.tiles[pos + dr].addConnect(tile, -dr)
        self.handTile = None
        self.state = PlayerState.PuttingFollower
        next_turn = False
        # put a follower
        pass_err: Literal[0, -1, -2] = 0
        while 1:
            ret_put = yield {"id": 2, "last_err": pass_err, "last_put": pos}
            if ret_put["id"] == -1:
                break
            if 0 <= ret_put["id"] < len(tile.segments):
                seg_put: Segment | Feature = tile.segments[ret_put["id"]]
            elif len(tile.segments) <= ret_put["id"] < len(tile.segments) + len(tile.features):
                seg_put = tile.features[ret_put["id"] - len(tile.segments)]
            else:
                pass_err = -2
                continue
            tokens = [token for token in self.tokens if isinstance(token, Token.make(ret_put.get("which", "follower")))]
            if len(tokens) == 0:
                pass_err = -1
                continue
            token = tokens[0]
            if not token.canPut(seg_put):
                pass_err = -2
                continue
            self.tokens.remove(token)
            next_turn = token.putOn(seg_put)
            break
        self.state = PlayerState.InturnScoring
        # score
        for seg in tile.segments:
            if seg.object.closed():
                yield from seg.object.score()
        for i in (-1, 0, 1):
            for j in (-1, 0, 1):
                npos = (pos[0] + i, pos[1] + j)
                if npos in self.board.tiles:
                    for feature in self.board.tiles[npos].features:
                        if feature.canScore():
                            yield from feature.score()
        self.state = PlayerState.End
        return 1
    def image(self):
        img = Image.new("RGBA", (125 + self.board.token_length, 24))
        dr = ImageDraw.Draw(img)
        dr.text((0, 12), self.show_name, "black", self.board.font_name, "lm")
        dr.text((102, 12), str(self.score), "black", self.board.font_score, "mm")
        # tokens
        self.tokens.sort(key=Token.key)
        token_xpos = {key: value for key, value in self.board.token_pos.items()}
        for token in self.tokens:
            timg = token.image()
            img.alpha_composite(timg, (token_xpos[type(token)] + 125, 12 - timg.size[1] // 2))
            token_xpos[type(token)] += timg.size[0] + 4
        return img
    def handTileImage(self):
        img = Image.new("RGBA", (176, 96))
        dr = ImageDraw.Draw(img)
        if self.handTile is None:
            dr.text((0, 48), self.show_name + "  请选择", "black", self.board.font_name, "lm")
        else:
            dr.text((0, 48), self.show_name, "black", self.board.font_name, "lm")
            dr.rectangle((92, 12, 164, 84), self.tokenColor, None)
            img.paste(self.handTile.image(), (96, 16))
            # text
            font = ImageFont.truetype("msyhbd.ttc", 10)
            dr.text((128, 10), "U", "black", font, "mb")
            dr.text((128, 86), "D", "black", font, "mt")
            dr.text((90, 48), "L", "black", font, "rm")
            dr.text((166, 48), "R", "black", font, "lm")
        return img


if __name__ == "__main__":
    b = Board(open_pack()["packs"][0:1], ["任意哈斯塔", "哈斯塔网络整体意识", "当且仅当哈斯塔", "到底几个哈斯塔", "普通的哈斯塔"])
    d = {
            "name": "follower",
            "distribute": True,
            "num": 7,
            "image": [0, 0, 16, 16]
        }
    b.players[0].tokens.pop(0)
    for i in range(1, 25):
        t = b.tiles[i % 5, i // 5] = [s for s in b.deck if s.id == i - 1][0]
        # t.turn(Dir.RIGHT)
        # for seg in t.segments:
        #     b.players[0].tokens.append(Follower(b.players[0], b.players[0], d, open_img("token0").crop((0, 0, 16, 16))))
        #     b.players[0].tokens[-1].putOn(seg)
        # for feature in t.features:
        #     if isinstance(feature, Cloister):
        #         b.players[0].tokens.append(Follower(b.players[0], b.players[0], d, open_img("token0").crop((0, 0, 16, 16))))
        #         b.players[0].tokens[-1].putOn(feature)
    b.players[0].drawTile()
    b.image(debug=True).show()
