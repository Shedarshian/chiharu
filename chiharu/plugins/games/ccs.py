from typing import Literal, Any, Generator, Type, TypeVar, Iterable, Callable, Sequence, Awaitable
import random, itertools, more_itertools, json
from abc import ABC, abstractmethod
from PIL import Image, ImageDraw, ImageFont
from .ccs_tile import Dir, TileData, OneSideSegmentPic
from .ccs_tile import CitySegmentData, RoadSegmentData, RiverSegmentData, FieldSegmentData, FeatureSegmentData, AddableSegmentData
from .ccs_tile import AreaSegmentPic, LineSegmentPic, SegmentData
from .ccs_helper import Connectable, TileAddable, Addable, Shed
from .ccs_helper import findAllMax, turn, dist2, State, Log, Send, Recieve

T = TypeVar('T')
TAsync = Generator[Send, Recieve, T]
TToken = TypeVar("TToken", bound="Token")

class CanScore(ABC):
    def __init__(self, board: 'Board') -> None:
        super().__init__()
        self.board = board
    @abstractmethod
    def closed(self) -> bool:
        pass
    def canPut(self) -> bool:
        return not self.closed()
    @abstractmethod
    def scoreType(self) -> 'ScoreReason':
        pass
    def occupied(self):
        return any(isinstance(t.player, Player) for t in self.iterTokens())
    @abstractmethod
    def iterTokens(self) -> 'Iterable[Token]':
        pass
    @abstractmethod
    def checkScore(self, players: 'list[Player]', complete: bool, putBarn: bool) -> 'list[tuple[Player, int]]':
        pass
    @abstractmethod
    def getTile(self) -> 'list[Tile]':
        pass
    def addStat(self, complete: bool, putBarn: bool, score: 'list[tuple[Player, int]]', isBarn: bool):
        return
    def removeAllFollowers(self, reason: 'HomeReason', criteria: 'Callable[[Token], bool] | None'=None):
        if criteria is None:
            criteria = lambda token: isinstance(token.player, Player) and not isinstance(token, Barn)
        to_remove: list[Token] = [token for token in self.iterTokens() if criteria(token)]
        for token in to_remove:
            token.putBackToHand(reason)
    def checkPlayer(self, complete: bool) -> 'list[Player]':
        strengths: list[int] = [0 for i in range(len(self.board.players))]
        for token in self.iterTokens():
            if isinstance(token, Follower) and isinstance(token.player, Player):
                strengths[token.player.id] += token.strength
        players = findAllMax(self.board.players, lambda player: strengths[player.id], lambda player: strengths[player.id] != 0)[1]
        if self.board.checkPack(9, "d"):
            on_hills = [token.player for token in self.iterTokens() if token.player in players and isinstance(token, Follower) and (isinstance(token.parent, (Segment, Feature)) and token.parent.tile.addable == TileAddable.Hill or isinstance(token.parent, Tile) and token.parent.addable == TileAddable.Hill)]
            if len(on_hills) != 0:
                return on_hills # type: ignore
        return players
    def checkPlayerAndScore(self, complete: bool, putBarn: bool=True) -> 'list[tuple[Player, int]]':
        players = self.checkScore(self.checkPlayer(complete), complete, putBarn)
        return players
    def score(self, putBarn: bool, ifExtra: bool=True) -> TAsync[bool]:
        players = self.checkPlayerAndScore(True, putBarn=putBarn)
        for player, score in players:
            if score != 0:
                from .ccs_helper import LogScore
                self.board.addLog(LogScore(player.long_name, "complete", score))
                yield from player.addScore(score, type=self.scoreType())
        self.addStat(True, putBarn, players, False)
        if ifExtra:
            for token in self.iterTokens():
                yield from token.scoreExtra()
        gingered: bool = False
        if self.board.checkPack(14, "d"):
            ginger = more_itertools.only(token for token in self.iterTokens() if isinstance(token, Gingerbread))
            if ginger is not None:
                yield from ginger.score()
                gingered = True
        return gingered
    def scoreFinal(self, ifExtra: bool=True):
        players = self.checkPlayerAndScore(False)
        for player, score in players:
            if score != 0:
                from .ccs_helper import LogScore
                self.board.addLog(LogScore(player.long_name, "final", score))
                player.addScoreFinal(score, type=self.scoreType())
        self.addStat(False, False, players, False)
        if ifExtra:
            for token in self.iterTokens():
                token.scoreExtraFinal()

class Tile:
    def __init__(self, board: 'Board', data: TileData, isAbbey: bool) -> None:
        super().__init__()
        self.picname = data.picname
        self.packid = data.packid
        self.id = data.id
        self.sub_id = data.sub_id
        self.sides = tuple({"C": Connectable.City, "R": Connectable.Road, "F": Connectable.Field, "S": Connectable.River}[c] for c in data.sides)
        self.img: Image.Image = board.abbeyImg if isAbbey else data.img
        self.segments: list[Segment] = []
        self.features: list[Feature] = []
        self.tokens: list[Token] = []
        self.board = board
        self.isAbbey = isAbbey
        self.connectTile: list[Tile | None] = [None] * 4
        self.orient: Dir = Dir.UP
        self.addable: TileAddable = TileAddable.No

        for seg in data.segments:
            if isinstance(seg, CitySegmentData):
                self.segments.append(CitySegment(self, seg))
            elif isinstance(seg, RoadSegmentData):
                self.segments.append(RoadSegment(self, seg))
            elif isinstance(seg, FieldSegmentData):
                self.segments.append(FieldSegment(self, seg, data.segments))
            elif isinstance(seg, RiverSegmentData):
                self.segments.append(RiverSegment(self, seg))
            elif isinstance(seg, FeatureSegmentData):
                typ = Feature.make(seg.feature)
                if typ.pack[0] == 0 or self.board.checkPack(*typ.pack):
                    self.features.append(typ(self, seg, seg.params))
            elif isinstance(seg, AddableSegmentData):
                self.addable = TileAddable[seg.feature]
        for seg2 in self.segments:
            if isinstance(seg2, FieldSegment):
                seg2.makeAdjCity()
        self.segments.sort(key=lambda x: x.key())

    @property
    def serialNumber(self):
        return self.packid, self.picname, self.id, self.sub_id
    def iterAllTokens(self):
        yield from (token for seg in self.segments for token in seg.tokens)
        yield from (token for feature in self.features for token in feature.tokens)
        yield from (token for token in self.tokens)
    def sidesToSegment(self, dir: Dir):
        return more_itertools.only([seg for seg in self.segments if seg.inSide(dir) and isinstance(seg, LineSegment)])
    def sidesToSegmentA(self, dir: Dir, up: bool):
        return more_itertools.only([seg for seg in self.segments if seg.inSideA(dir, up) and isinstance(seg, AreaSegment)])
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
        if (s1 := self.sidesToSegmentA(dir, False)) is not None and (s2 := tile.sidesToSegmentA(-dir, True)) is not None:
            s1.combineA(s2, dir, False)
        if (s1 := self.sidesToSegmentA(dir, True)) is not None and (s2 := tile.sidesToSegmentA(-dir, False)) is not None:
            s1.combineA(s2, dir, True)
        return 1
    def closeSideAbbey(self, dir: Dir):
        if (s1 := self.sidesToSegment(dir)) is not None:
            s1.closeAbbey(dir)
        if (s1 := self.sidesToSegmentA(dir, False)) is not None:
            s1.closeAbbeyA(dir, False)
        if (s1 := self.sidesToSegmentA(dir, True)) is not None:
            s1.closeAbbeyA(dir, True)
    def getSideSeg(self, dir: Dir):
        segs: list[Segment] = []
        if (s1 := self.sidesToSegment(dir)) is not None:
            segs.append(s1)
        if (s1 := self.sidesToSegmentA(dir, False)) is not None:
            segs.append(s1)
        if (s1 := self.sidesToSegmentA(dir, True)) is not None:
            segs.append(s1)
        return segs
    def getBarnSeg(self, dir: tuple[Dir, Dir] = (Dir.RIGHT, Dir.DOWN)):
        seg = more_itertools.only(s for s in self.segments if s.inSideA(dir[0], False) and s.inSideA(dir[1], True) and s.type == Connectable.Field)
        return seg
    def findTokenDrawPos(self, token: 'Token'):
        """turned"""
        if self.addable == TileAddable.Hill:
            add = (-2, -4)
        else:
            add = (0, 0)
        if isinstance(token, Barn) and (seg := self.getBarnSeg()) and token in seg.tokens:
            return (64, 64)
        for seg in self.segments:
            if token in seg.tokens:
                id = seg.tokens.index(token)
                t = turn(seg.drawPos(len(seg.tokens))[id], self.orient)
                return t[0] + add[0], t[1] + add[1]
            if token in seg.object.tokens:
                pass # TODO for castle
        for feature in self.features:
            if token in feature.tokens:
                id = feature.tokens.index(token)
                t = turn(feature.drawPos(len(feature.tokens))[id], self.orient)
                return t[0] + add[0], t[1] + add[1]
        if token in self.tokens:
            assert isinstance(token, TileFigure)
            t = turn(token.findDrawPos(), self.orient)
            return t[0] + add[0], t[1] + add[1]
        return (32, 32)
    def getSeg(self, i: int):
        if i < len(self.features):
            return self.features[i]
        if i < len(self.features) + len(self.segments):
            return self.segments[i - len(self.features)]
        return None
    def putOnBy(self, token: 'Token') -> TAsync[None]:
        return
        yield {}

    def debugImage(self):
        img = Image.new("RGBA", (64, 64), "white")
        dr = ImageDraw.Draw(img)
        img.paste(self.img)
        ci = 1
        for i, c in zip(range(4), self.sides):
            dr.rectangle([(0, 0, 64, 2), (62, 0, 64, 64), (0, 62, 64, 64), (0, 0, 2, 64)][i], {Connectable.City: "brown", Connectable.Field: "green", Connectable.Road: "black", Connectable.River: "blue"}[c])
        citycorrs: list[tuple[float, float]] = []
        for seg in self.segments:
            corr = seg.drawPos(1)[0]
            if isinstance(seg, LineSegment):
                for dir in seg.side.keys():
                    if dir == Dir.UP:
                        dr.line((corr[0], 0, corr[0], corr[1]), seg.color, 2)
                    elif dir == Dir.RIGHT:
                        dr.line((64, corr[1], corr[0], corr[1]), seg.color, 2)
                    elif dir == Dir.DOWN:
                        dr.line((corr[0], 64, corr[0], corr[1]), seg.color, 2)
                    elif dir == Dir.LEFT:
                        dr.line((0, corr[1], corr[0], corr[1]), seg.color, 2)
            elif isinstance(seg, AreaSegment):
                for du in seg.side.keys():
                    cr = {(Dir.UP, True): (16, 0), (Dir.UP, False): (48, 0), (Dir.RIGHT, True): (64, 16), (Dir.RIGHT, False): (64, 48), (Dir.DOWN, True): (48, 64), (Dir.DOWN, False): (16, 64), (Dir.LEFT, True): (0, 48), (Dir.LEFT, False): (0, 16)}[du]
                    dr.line(cr + corr, seg.color, 2)
                if isinstance(seg, FieldSegment):
                    for city in seg.adjacentCity:
                        dr.line((citycorrs[self.segments.index(city)], corr), "gray", 2)
            citycorrs.append(corr)
            ci += 1
        ci = 1
        for seg in self.segments:
            corr = seg.drawPos(1)[0]
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
    def drawToken(self, img: Image.Image, beg_pos: tuple[int, int]):
        def pos(i, j, *offsets: tuple[int, int]):
            return beg_pos[0] + i + sum(x[0] for x in offsets), beg_pos[1] + j + sum(x[1] for x in offsets)
        if self.addable == TileAddable.Hill:
            add = (-2, -4)
        else:
            add = (0, 0)
        drawn_poses: list[tuple[int, int]] = []
        for seg in self.segments:
            poses = seg.drawPos(len(seg.tokens))
            drawn_poses.extend(poses)
            for i, token in enumerate(seg.tokens):
                t = token.image()
                if isinstance(token, Barn):
                    img.alpha_composite(t, pos(64, 64, (-t.size[0] // 2, -t.size[1] // 2)))
                else:
                    img.alpha_composite(t, pos(*turn(poses[i], self.orient), (-t.size[0] // 2, -t.size[1] // 2), add))
        for feature in self.features:
            poses = feature.drawPos(len(feature.tokens))
            drawn_poses.extend(poses)
            for i, token in enumerate(feature.tokens):
                t = token.image()
                img.alpha_composite(t, pos(*turn(poses[i], self.orient), (-t.size[0] // 2, -t.size[1] // 2), add))
            if isinstance(feature, Tower):
                dr = ImageDraw.Draw(img)
                font_tower = ImageFont.truetype("calibrib.ttf", 10)
                dr.text(pos(*turn(feature.num_pos, self.orient), add), str(feature.height), "black", font_tower, "mm")
        for token in self.tokens:
            assert isinstance(token, TileFigure)
            t = token.image()
            img.alpha_composite(t, pos(*turn(token.findDrawPos(drawn_poses), self.orient), (-t.size[0] // 2, -t.size[1] // 2), add))
    def drawPutToken(self, img: Image.Image, beg_pos: tuple[int, int], draw_occupied_seg: bool, drawBarn: bool):
        def pos(i, j, *offsets: tuple[int, int]):
            return beg_pos[0] + i + sum(x[0] for x in offsets), beg_pos[1] + j + sum(x[1] for x in offsets)
        dr = ImageDraw.Draw(img)
        font = ImageFont.truetype("msyhbd.ttc", 10)
        def draw(tpos: tuple[int, int], i: int):
            dr.ellipse((pos(tpos[0] - 6, tpos[1] - 6), pos(tpos[0] + 6, tpos[1] + 6)), "white", "black", 1)
            text = chr(i) if i <= ord('a') + 25 else chr((i - ord('a')) // 26) + chr((i - ord('a')) % 26)
            dr.text(pos(*tpos), text, "black", font, "mm")
        i = ord('a')
        for feature in self.features:
            if isinstance(feature, CanScore) and (draw_occupied_seg or len([token for token in feature.tokens if isinstance(token.player, Player)]) == 0):
                tpos = turn(feature.putPos(len(feature.tokens)), self.orient)
                draw(tpos, i)
            i += 1
        for seg in self.segments:
            if (draw_occupied_seg or len([token for token in seg.tokens if isinstance(token.player, Player)]) == 0) and not isinstance(seg, RiverSegment):
                tpos = turn(seg.putPos(len(seg.tokens)), self.orient)
                draw(tpos, i)
            i += 1
        if drawBarn:
            for tpos in ((0, 0), (64, 0), (0, 64), (64, 64)):
                draw(tpos, i)
                i += 1
    def image(self, debug: bool=False):
        if debug:
            return self.debugImage()
        if self.orient == Dir.UP:
            return self.img
        return self.img.transpose(self.orient.transpose())

class Segment(ABC):
    type = Connectable.City
    color = "black"
    def __init__(self, tile: Tile) -> None:
        self.tokens: list[Token] = []
        self.tile = tile
        self.object = Object(self)
        self.addable = Addable.No
        self.shed = Shed.No
    @classmethod
    def make(cls, typ: str) -> Type['Segment']:
        return {"City": CitySegment, "Field": FieldSegment, "Road": RoadSegment, "River": RiverSegment}[typ] # type: ignore
    @abstractmethod
    def turn(self, dir: Dir):
        pass
    def occupied(self):
        return self.object.occupied()
    def closed(self):
        return self.object.closed()
    def canPut(self):
        return self.object.canPut()
    def inSide(self, dir: Dir):
        return False
    def inSideA(self, dir: Dir, up: bool):
        return False
    def selfClosed(self) -> bool:
        return False
    @abstractmethod
    def drawPos(self, num: int) -> Sequence[tuple[int, int]]:
        pass
    @abstractmethod
    def putPos(self, num: int) -> tuple[int, int]:
        pass
    def key(self):
        return (-1,)
    def putOnBy(self, token: 'Token') -> TAsync[None]:
        for token in self.tile.tokens:
            if isinstance(token, TileFigure):
                token.draw_pos = None
        return
        yield {}
class AreaSegment(Segment):
    def __init__(self, tile: Tile, side: list[tuple[Dir, bool]], pic: AreaSegmentPic) -> None:
        super().__init__(tile)
        self.pic = pic
        self.side: dict[tuple[Dir, bool], Segment | None] = {s: None for s in side}
    def turn(self, dir: Dir):
        self.side = {(d + dir, d2): value for (d, d2), value in self.side.items()}
    def inSideA(self, dir: Dir, up: bool):
        return (dir, up) in self.side
    def combineA(self, other: 'AreaSegment', dir: Dir, up: bool):
        other.object = self.object.eat(other.object)
        self.side[dir, up] = other
        other.side[-dir, not up] = self
    def closeAbbeyA(self, dir: Dir, up: bool):
        self.side[dir, up] = self
    def selfClosed(self):
        return all(value is not None for value in self.side.values())
    def drawPos(self, num: int):
        return self.pic.drawPos(num)
    def putPos(self, num: int):
        return self.pic.putPos(num)
    def key(self):
        return tuple(sorted(Dir.sideKey(t) for t in self.side.keys()))
class LineSegment(Segment):
    def __init__(self, tile: Tile, side: list[Dir], pic: list[LineSegmentPic]) -> None:
        super().__init__(tile)
        if len(pic) == 0:
            raise ValueError
        self.pic = pic
        self.side: dict[Dir, Segment | None] = {s: None for s in side}
    def turn(self, dir: Dir):
        self.side = {d + dir: value for d, value in self.side.items()}
    def inSide(self, dir: Dir):
        return dir in self.side
    def combine(self, other: 'LineSegment', dir: Dir):
        other.object = self.object.eat(other.object)
        self.side[dir] = other
        other.side[-dir] = self
    def closeAbbey(self, dir: Dir):
        self.side[dir] = self
    def selfClosed(self):
        return all(value is not None for value in self.side.values())
    def drawPos(self, num: int):
        if num == 1:
            return [self.pic[0].center]
        if num <= len(self.pic):
            return [self.pic[i].center for i in range(num)]
        repeat = num // len(self.pic)
        p1 = num % len(self.pic)
        ret: list[tuple[int, int]] = []
        for i, p in enumerate(self.pic):
            r = repeat + (1 if i < p1 else 0)
            if r == 1:
                ret.append(p.center)
            else:
                for c in range(r):
                    ret.append(p.getPortion((c + 1) / (r + 1)))
        return ret
    def putPos(self, num: int):
        if num < len(self.pic):
            return self.pic[num].center
        r = num // len(self.pic)
        p1 = num % len(self.pic)
        p = self.pic[p1]
        if r == 1:
            return p.getPortion(0.75)
        elif r % 2 == 0:
            return p.center
        return p.getPortion(0.5 + 0.5 / (r + 1))
    def key(self):
        return tuple(sorted(t.value for t in self.side.keys()))
class CitySegment(AreaSegment):
    def __init__(self, tile: Tile, data: CitySegmentData) -> None:
        super().__init__(tile, data.side, data.pic)
        self.pennant: int = 0
        for addable in data.addables:
            if addable.feature in Shed.__members__:
                self.shed = Shed[addable.feature]
            elif addable.feature == "pennant":
                self.pennant += 1
            elif tile.board.checkPack(1, "d") and addable.feature == "Cathedral":
                self.addable = Addable.Cathedral
            elif tile.board.checkPack(2, "d") and addable.feature in ("Cloth", "Wine", "Grain"):
                self.addable = Addable[addable.feature]
            elif tile.board.checkPack(3, "e") and addable.feature == "Princess":
                self.addable = Addable.Princess
    def key(self):
        return (0, super().key())
class RoadSegment(LineSegment):
    type = Connectable.Road
    color = "black"
    def key(self):
        return (1, super().key())
    def __init__(self, tile: Tile, data: RoadSegmentData) -> None:
        super().__init__(tile, data.side, data.lines)
        for addable in data.addables:
            if addable.feature in Shed.__members__:
                self.shed = Shed[addable.feature]
            elif tile.board.checkPack(1, "c") and addable.feature == "Inn":
                self.addable = Addable.Inn
class RiverSegment(LineSegment):
    type = Connectable.River
    color = "blue"
    def __init__(self, tile: Tile, data: RiverSegmentData) -> None:
        super().__init__(tile, data.side, data.lines)
    def key(self):
        return (3, super().key())
class FieldSegment(AreaSegment):
    type = Connectable.Field
    color = "green"
    def __init__(self, tile: Tile, data: FieldSegmentData, segments: list[SegmentData]) -> None:
        super().__init__(tile, data.side, data.pic)
        self.adjacentCitytemp = data.adjCity
        self.adjacentSegtemp = segments
        self.adjacentCity: list[Segment] = []
        for addable in data.addables:
            if addable.feature in Shed.__members__:
                self.shed = Shed[addable.feature]
            elif tile.board.checkPack(2, "c") and addable.feature == "Pigherd":
                self.addable = Addable.Pigherd
    def makeAdjCity(self):
        self.adjacentCity = [self.tile.segments[self.adjacentSegtemp.index(seg)] for seg in self.adjacentCitytemp]
        del self.adjacentCitytemp
        del self.adjacentSegtemp
    def key(self):
        return (2, super().key())

class Object(CanScore):
    def __init__(self, seg: Segment) -> None:
        super().__init__(seg.tile.board)
        self.type = seg.type
        self.tokens: list[Token] = []
        self.segments: list[Segment] = [seg]
        self.board = seg.tile.board
    def scoreType(self) -> 'ScoreReason':
        return ScoreReason[self.type.name]
    def eat(self, other: 'Object'):
        if other is self:
            return self
        self.segments.extend(other.segments)
        self.tokens.extend(other.tokens)
        for seg in other.segments:
            seg.object = self
        return self
    def closed(self):
        if self.type == Connectable.Field:
            return self.checkBarn()
        return all(seg.selfClosed() for seg in self.segments)
    def iterTokens(self) -> 'Iterable[Token]':
        for seg in self.segments:
            yield from seg.tokens
    def getTile(self):
        tiles: list[Tile] = []
        for seg in self.segments:
            if seg.tile not in tiles:
                tiles.append(seg.tile)
        return tiles
    def checkTile(self, bad_neiborhood: bool=False):
        if bad_neiborhood:
            tiles: list[Tile] = []
            for seg in self.segments:
                if isinstance(seg, CitySegment):
                    if not isinstance(seg.pic, OneSideSegmentPic) and seg.tile not in tiles:
                        tiles.append(seg.tile)
                elif isinstance(seg, RoadSegment):
                    if not any(seg2.shed == Shed.Farmhouse for seg2 in seg.tile.segments) and seg.tile not in tiles:
                        tiles.append(seg.tile)
            return len(tiles)
        return len(self.getTile())
    def checkPennant(self):
        return sum(seg.pennant for seg in self.segments if isinstance(seg, CitySegment))
    def checkBarnAndScore(self) -> 'list[tuple[Player, int]]':
        ps: list[Player] = []
        for token in self.iterTokens():
            if isinstance(token, Barn) and isinstance(token.player, Player):
                ps.append(token.player)
        complete_city: list[Object] = []
        for seg in self.segments:
            if isinstance(seg, FieldSegment):
                for segc in seg.adjacentCity:
                    if segc.object not in complete_city and segc.closed():
                        complete_city.append(segc.object)
        base = 4
        score = base * len(complete_city)
        players = [(p, score) for p in ps]
        return players
    def checkBarn(self):
        return self.board.checkPack(5, 'e') and self.type == Connectable.Field and any(isinstance(token, Barn) for token in self.iterTokens())
    def checkPlayer(self, complete: bool) -> 'list[Player]':
        if self.board.checkPack(15, "a") and complete and self.type == Connectable.City and self.board.landCity[0] == LandCity.CitizensJury:
            players = []
            for token in self.iterTokens():
                if isinstance(token.player, Player) and token.player not in players:
                    players.append(token.player)
            return players
        return super().checkPlayer(complete)
    def checkScore(self, players: 'list[Player]', complete: bool, putBarn: bool) -> 'list[tuple[Player, int]]':
        match self.type:
            case Connectable.City:
                base = 2 if complete else 1
                if self.board.checkPack(1, "d") and any(seg.addable == Addable.Cathedral for seg in self.segments):
                    if complete:
                        base += 1
                    else:
                        base = 0
                base_pennant = base
                if self.board.checkPack(15, "a") and complete and self.board.landCity[0] == LandCity.Siege:
                    base_pennant += 1
                score = base * self.checkTile(self.board.checkPack(15, "a") and complete and self.board.landCity[0] == LandCity.BadNeighborhood) + base_pennant * self.checkPennant()
                if self.board.checkPack(15, "a") and complete:
                    if self.board.landCity[0] == LandCity.Wealth:
                        score += 3
                    elif self.board.landCity[0] == LandCity.Poverty:
                        score -= 3
                new_players: list[tuple[Player, int]] = [(player, score) for player in players]
            case Connectable.Road:
                base = 1
                if self.board.checkPack(1, "c") and any(seg.addable == Addable.Inn for seg in self.segments):
                    if complete:
                        base += 1
                    else:
                        base = 0
                if self.board.checkPack(15, "a") and complete and self.board.landRoad[0] == LandRoad.StreetFair:
                    base += 1
                score = base * self.checkTile(self.board.checkPack(15, "a") and complete and self.board.landRoad[0] == LandRoad.PeasantUprising)
                if self.board.checkPack(15, "a") and complete:
                    if self.board.landRoad[0] == LandRoad.Poverty:
                        score -= 3
                    elif self.board.landRoad[0] == LandRoad.Highway:
                        score = base * 5
                new_players = [(player, score) for player in players]
            case Connectable.Field:
                complete_city = self.checkCompleteCities()
                if self.board.checkPack(2, "c"):
                    new_players = []
                    for player in players:
                        base = 3 if putBarn else 1
                        if any(isinstance(token, Pig) and token.player is player for token in self.iterTokens()):
                            base += 1
                        elif any(seg.addable == Addable.Pigherd for seg in self.segments):
                            base += 1
                        new_players.append((player, base * len(complete_city)))
                else:
                    base = 3 if putBarn else 1
                    new_players = [(player, base * len(complete_city)) for player in players]
            case _:
                new_players = []
        if self.board.checkPack(15, "a") and len(new_players) != 0:
            self.board.updateLand()
        return new_players
    def checkRemoveBuilderAndPig(self, reason: 'HomeReason'):
        if not self.board.checkPack(2, "b") and not self.board.checkPack(2, "c"):
            return
        ts = [token for seg in self.segments for token in seg.tokens if isinstance(token, (Builder, Pig))]
        for t in ts:
            if not any(token.player is t.player for seg in self.segments for token in seg.tokens if isinstance(token, Follower)):
                from .ccs_helper import LogPutBackBuilder
                assert isinstance(t.player, Player)
                self.board.addLog(LogPutBackBuilder(t.player.long_name, t.__class__.__name__))
                t.putBackToHand(reason)
    def checkCompleteCities(self):
        complete_city: list[Object] = []
        for seg in self.segments:
            if isinstance(seg, FieldSegment):
                for segc in seg.adjacentCity:
                    if segc.closed() and segc.object not in complete_city:
                        complete_city.append(segc.object)
        return complete_city
    def scoreFinal(self, ifExtra: bool=True):
        super().scoreFinal(ifExtra)
        # barn
        if self.type == Connectable.Field and any(isinstance(token, Barn) for seg in self.segments for token in seg.tokens):
            players = self.checkBarnAndScore()
            for player, score in players:
                if score != 0:
                    player.addScoreFinal(score, type=ScoreReason.Field)
            self.removeAllFollowers(HomeReason.Score, lambda token: isinstance(token, Barn))
            self.addStat(False, False, players, True)
    def addStat(self, complete: bool, putBarn: bool, score: 'list[tuple[Player, int]]', isBarn: bool):
        if len(score) == 0:
            return
        players = json.dumps([p.id for p, s in score])
        scores = ''
        if not all(s == score[0][1] for p, s in score):
            scores = json.dumps([(p.id, s) for p, s in score])
        match self.type:
            case Connectable.City:
                stat = ccsCityStat(0, players, len(self.getTile()), complete, score[0][1], scores)
                stat.pennants = self.checkPennant()
                if self.board.checkPack(1, "d"):
                    stat.cathedral = sum(1 for seg in self.segments if seg.addable == Addable.Cathedral)
                if self.board.checkPack(15, "a") and complete:
                    if self.board.landCity[0] == LandCity.BadNeighborhood:
                        stat.land_surveyor = 4 + (stat.tiles - self.checkTile(True))
                    else:
                        stat.land_surveyor = self.board.landCity[0].saveID()
                if self.board.checkPack(13, "f"):
                    stat.mage_witch = sum(1 if isinstance(token, Mage) else 2 if isinstance(token, Witch) else 0 for token in self.iterTokens())
                self.board.stats[0].append(stat)
            case Connectable.Road:
                stat2 = ccsRoadStat(0, players, len(self.getTile()), complete, score[0][1], scores)
                if self.board.checkPack(1, "c"):
                    stat2.inn = sum(1 for seg in self.segments if seg.addable == Addable.Inn)
                if self.board.checkPack(13, "f"):
                    stat2.mage_witch = sum(1 if isinstance(token, Mage) else 2 if isinstance(token, Witch) else 0 for token in self.iterTokens())
                if self.board.checkPack(15, "a") and complete:
                    if self.board.landRoad[0] == LandRoad.PeasantUprising:
                        stat2.land_surveyor = 3 + (stat2.tiles - self.checkTile(True))
                    else:
                        stat2.land_surveyor = self.board.landRoad[0].saveID()
                self.board.stats[1].append(stat2)
            case Connectable.Field:
                barn = 3 if isBarn else 0 if not complete else 1 if putBarn else 2
                stat3 = ccsFieldStat(0, players, len(self.checkCompleteCities()), score[0][1], scores, barn)
                if self.board.checkPack(2, "c") and not isBarn:
                    stat3.pigherd = sum(1 for seg in self.segments if seg.addable == Addable.Pigherd)
                    stat3.pig = json.dumps([token.player.id for token in self.iterTokens() if isinstance(token, Pig) and isinstance(token.player, Player)])
                self.board.stats[2].append(stat3)

TCloister = TypeVar('TCloister', bound='BaseCloister')
class Feature:
    pack = (0, "a")
    def __init__(self, tile: Tile, segment: FeatureSegmentData, data: list[Any]) -> None:
        self.pic = segment.pic
        self.pos = segment.pos
        self.tile = tile
        self.tokens: list[Token] = []
    @classmethod
    def make(cls, typ: str) -> Type["Feature"]:
        return {"cloister": Cloister, "garden": Garden, "shrine": Shrine, "tower": Tower, "flier": Flier, "circus": Circus, "acrobat": Acrobat}[typ.lower()]
    def putOnBy(self, token: 'Token') -> TAsync[None]:
        for token in self.tile.tokens:
            if isinstance(token, TileFigure):
                token.draw_pos = None
        return
        yield {}
    def drawPos(self, num: int):
        return self.pic.drawPos(num)
    def putPos(self, num: int):
        return self.pic.putPos(num)
class BaseCloister(Feature, CanScore):
    def __init__(self, parent: Tile, pic: FeatureSegmentData, data: list[Any]) -> None:
        Feature.__init__(self, parent, pic, data)
        CanScore.__init__(self, parent.board)
    def scoreType(self) -> 'ScoreReason':
        return ScoreReason.Monastry
    def iterTokens(self) -> 'Iterable[Token]':
        yield from self.tokens
    def closed(self) -> bool:
        return len(self.getTile()) == 9
    def getTile(self):
        pos = self.tile.board.findTilePos(self.tile)
        if pos is None:
            return [self.tile]
        return [self.tile.board.tiles[pos[0] + i, pos[1] + j] for i in (-1, 0, 1) for j in (-1, 0, 1) if (pos[0] + i, pos[1] + j) in self.tile.board.tiles]
    def checkScore(self, players: 'list[Player]', complete: bool, putBarn: bool) -> 'list[tuple[Player, int]]':
        score = len(self.getTile())
        return [(player, score) for player in players]
    def getCloister(self, typ: Type[TCloister]) -> TCloister | None:
        assert isinstance(self.tile, Tile)
        pos = self.board.findTilePos(self.tile)
        if pos is None:
            return None
        return more_itertools.only(feature for i in (-1, 0, 1) for j in (-1, 0, 1)
                    if (pos[0] + i, pos[1] + j) in self.board.tiles
                    for feature in self.board.tiles[pos[0] + i, pos[1] + j].features
                    if isinstance(feature, typ))
    def addStat(self, complete: bool, putBarn: bool, score: 'list[tuple[Player, int]]', isBarn: bool):
        if len(score) == 0:
            return
        players = json.dumps([p.id for p, s in score])
        scores = ''
        if not all(s == score[0][1] for p, s in score):
            scores = json.dumps([(p.id, s) for p, s in score])
        stat = ccsMonastryStat(0, players, self.__class__.__name__.lower(), len(self.getTile()), complete, score[0][1], scores)
        stat.abbey = self.tile.isAbbey
        if self.board.checkPack(9, "e") and complete and isinstance(self, Monastry):
            stat.vineyard = sum(1 for tile in self.getTile() if tile.addable == TileAddable.Vineyard)
        if self.board.checkPack(15, "a") and complete and isinstance(self, Monastry):
            if self.board.landMonastry[0] == LandMonastry.Wealth:
                stat.wealth = True
            elif self.board.landMonastry[0] == LandMonastry.HermitMonastery:
                stat.hermit_monastry = sum(1 for tile in self.getTile() if any(isinstance(seg, CitySegment) for seg in tile.segments))
            else:
                stat.pilgrimage_route = sum(1 for tile in self.getTile() if any(isinstance(seg, RoadSegment) for seg in tile.segments))
        if self.board.checkPack(6, 'h') and isinstance(self, (Cloister, Shrine)) and (cloister := self.getChallenge()) and not cloister.closed() and len(self.tokens) != 0 and len(cloister.tokens) != 0: # pylint: disable=no-member
            stat.challenge_complete = True
        self.board.stats[3].append(stat)
class Monastry(BaseCloister):
    def checkScore(self, players: 'list[Player]', complete: bool, putBarn: bool) -> 'list[tuple[Player, int]]':
        score = len(self.getTile())
        if self.board.checkPack(9, "e") and complete:
            score += sum(3 for tile in self.getTile() if tile.addable == TileAddable.Vineyard)
        if self.board.checkPack(15, "a") and complete:
            if self.board.landMonastry[0] == LandMonastry.Wealth:
                score += 3
            elif self.board.landMonastry[0] == LandMonastry.HermitMonastery:
                score -= sum(1 for tile in self.getTile() if any(isinstance(seg, CitySegment) for seg in tile.segments))
            else:
                score += sum(1 for tile in self.getTile() if any(isinstance(seg, RoadSegment) for seg in tile.segments))
        return [(player, score) for player in players]
class Cloister(Monastry):
    def getChallenge(self):
        return self.getCloister(Shrine)
    def score(self, putBarn: bool, ifExtra: bool=True) -> TAsync[bool]:
        hasmeeple: bool = len(self.tokens) != 0
        gingered = yield from super().score(putBarn, ifExtra)
        if self.board.checkPack(6, 'h') and (cloister := self.getChallenge()) and not cloister.closed() and hasmeeple and len(cloister.tokens) != 0:
            from .ccs_helper import LogChallengeFailed
            self.board.addLog(LogChallengeFailed("shrine"))
            cloister.removeAllFollowers(HomeReason.Challenge)
        return gingered
class Garden(BaseCloister):
    pack = (12, "a")
    def scoreType(self) -> 'ScoreReason':
        return ScoreReason.Garden
class Shrine(Monastry):
    def getChallenge(self):
        return self.getCloister(Cloister)
    def score(self, putBarn: bool, ifExtra: bool=True) -> TAsync[bool]:
        hasmeeple: bool = len(self.tokens) != 0
        gingered = yield from super().score(putBarn, ifExtra)
        if self.board.checkPack(6, 'h') and (cloister := self.getChallenge()) and not cloister.closed() and hasmeeple and len(cloister.tokens) != 0:
            from .ccs_helper import LogChallengeFailed
            self.board.addLog(LogChallengeFailed("cloister"))
            cloister.removeAllFollowers(HomeReason.Challenge)
        return gingered
class Tower(Feature):
    pack = (4, "b")
    def __init__(self, parent: Tile, pic: FeatureSegmentData, data: list[Any]) -> None:
        super().__init__(parent, pic, data)
        self.height: int = 0
        self.num_dir: Dir = data[0]
    @property
    def num_pos(self):
        cor = self.num_dir.corr()
        return self.pic.pos[0] + 11 * cor[0], self.pic.pos[1] + 11 * cor[1]
class Flier(Feature, CanScore):
    pack = (13, "b")
    def __init__(self, parent: Tile, pic: FeatureSegmentData, data: list[Any]) -> None:
        Feature.__init__(self, parent, pic, data)
        CanScore.__init__(self, parent.board)
        self.direction: int = data[0]
    def closed(self) -> bool:
        return True
    def scoreType(self) -> 'ScoreReason':
        return ScoreReason.City
    def iterTokens(self) -> 'Iterable[Token]':
        return []
    def checkScore(self, players: 'list[Player]', complete: bool, putBarn: bool) -> 'list[tuple[Player, int]]':
        return []
    def getTile(self) -> 'list[Tile]':
        return []
    def putOnBy(self, token: 'Token') -> TAsync[None]:
        token.remove(None)
        pos = self.board.findTilePos(self.tile)
        if pos is None:
            return
        dice = random.randint(1, 3)
        from .ccs_helper import LogDice
        self.board.addLog(LogDice(dice))
        ps = {0: (0, -1), 1: (1, -1), 2: (1, 0), 3: (1, 1), 4: (0, 1), 5: (-1, 1), 6: (-1, 0), 7: (-1, -1)}[(self.direction + self.tile.orient.value * 2) % 8]
        pos_new = pos[0] + ps[0] * dice, pos[1] + ps[1] * dice
        if pos_new not in self.board.tiles:
            # token.putBackToHand(HomeReason.FlierInvalid)
            return
        tile = self.board.tiles[pos_new]
        put_list: Sequence[Segment | Feature] = [segment for segment in tile.segments if not isinstance(segment, FieldSegment) and segment.object.canPut() and token.canPut(segment)] + [feature for feature in tile.features if token.canPut(feature) and isinstance(feature, CanScore) and feature.canPut()]
        if len(put_list) == 0:
            return
        if len(put_list) == 1:
            to_put = put_list[0]
        else:
            pass_err: Literal[0, -1, -2] = 0
            while 1:
                self.board.state = State.ChoosingSegment
                from .ccs_helper import SendPosSpecial
                ret = yield SendPosSpecial(pass_err, pos_new, "flier")
                assert isinstance(ret, RecieveId)
                p = tile.getSeg(ret.id)
                if p is None:
                    pass_err = -1
                    continue
                if p in put_list:
                    to_put = p
                else:
                    pass_err = -2
                    continue
                break
        yield from token.putOn(to_put)
class Circus(Feature):
    pack = (12, "b")
class Acrobat(Feature, CanScore):
    pack = (12, "c")
    def closed(self) -> bool:
        return False
    def canPut(self) -> bool:
        return len(self.tokens) >= 3
    def scoreType(self) -> 'ScoreReason':
        return ScoreReason.Acrobat
    def occupied(self):
        return len(self.tokens) >= 3
    def iterTokens(self) -> 'Iterable[Token]':
        yield from self.tokens
    def getTile(self) -> 'list[Tile]':
        return []
    def checkPlayer(self, complete: bool) -> 'list[Player]':
        players: list[Player] = []
        for token in self.iterTokens():
            if token.player not in players and isinstance(token.player, Player):
                players.append(token.player)
        return players
    def checkScore(self, players: 'list[Player]', complete: bool, putBarn: bool) -> 'list[tuple[Player, int]]':
        return [(player, 5 * sum(1 for token in self.iterTokens() if token.player is player)) for player in players]

class TokenMeta(type):
    def __new__(cls, name: str, base, attr):
        ncls = super().__new__(cls, name, base, attr)
        if 'name' in attr:
            Token.all_name[name.lower()] = ncls # type: ignore
            Token.all_name[attr["name"]] = ncls # type: ignore
        return ncls
class Token(metaclass=TokenMeta):
    all_name: dict[str, 'Type[Token]'] = {}
    def __init__(self, parent: 'Player | Board', data: dict[str, Any], img: Image.Image) -> None:
        self.parent: Tile | Segment | Object | Feature | Player | Board = parent
        self.player = parent
        self.board = parent if isinstance(parent, Board) else parent.board
        self.img = img
        self.turns: int = 0
        self.ability: int = 0
        if self.board.checkPack(3, 'c'):
            self.fairy_1: int = 0
            self.fairy_3: int = 0
    def checkPack(self, packid: int, thingid: str):
        if isinstance(self.player, Player):
            return self.player.board.checkPack(packid, thingid)
        return self.player.checkPack(packid, thingid)
    @classmethod
    def make(cls, typ: str) -> Type['Token']:
        return cls.all_name[typ.lower()]
    def canPut(self, seg: Segment | Feature | Tile):
        if not isinstance(seg, self.canPutTypes):
            return False
        if isinstance(seg, Segment):
            return not any(isinstance(token, Dragon) for token in seg.tile.tokens)
        return True
    def putOn(self, seg: Segment | Feature | Tile) -> TAsync[None]:
        yield from self.selfPutOn(seg)
        yield from seg.putOnBy(self)
    def selfPutOn(self, seg: Segment | Feature | Tile) -> TAsync[None]:
        seg.tokens.append(self)
        self.parent = seg
        return
        yield {}
    def image(self):
        if isinstance(self.player, Board):
            return self.img.copy()
        if isinstance(self, (BaseFollower, BigFollower)) and isinstance(self.parent, FieldSegment):
            mask = self.board.tokenimgs[0].crop((16, 0, 32, 16))
        else:
            mask = self.img
        x = Image.new("RGBA", self.img.size)
        x.paste(Image.new("RGBA", self.img.size, self.player.tokenColor), (0, 0), mask)
        return x
    def remove(self, reason: 'HomeReason | None'):
        if isinstance(self.parent, (Tile, Segment, Feature, Object)):
            self.parent.tokens.remove(self)
        if self.board.checkPack(3, 'c') and self.board.fairy.follower is self:
            self.board.fairy.follower = None
        if reason is not None:
            self.addStat(reason)
            self.turns = 0
    def putBackToHand(self, reason: 'HomeReason'):
        if isinstance(self.parent, (Tile, Segment, Feature, Object)):
            self.parent.tokens.remove(self)
        self.player.tokens.append(self)
        self.parent = self.player
        if self.board.checkPack(3, 'c') and self.board.fairy.follower is self:
            self.board.fairy.follower = None
        self.addStat(reason)
        self.turns = 0
    def addStat(self, reason: 'HomeReason'):
        if not isinstance(self.player, Player):
            return
        stat = ccsMeepleStat(0, self.player.id, self.__class__.__name__.lower(), self.turns, reason, self.ability)
        if self.board.checkPack(3, 'c'):
            stat.fairy_1 = self.fairy_1
            stat.fairy_3 = self.fairy_3
        self.board.stats[4].append(stat)
    def scoreExtra(self) -> TAsync[None]:
        if self.board.checkPack(3, "c") and self.board.fairy.follower is self and isinstance(self.player, Player):
            self.fairy_3 += 1
            from .ccs_helper import LogScore
            self.board.addLog(LogScore(self.player.long_name, "fairy_complete", 3))
            yield from self.player.addScore(3, type=ScoreReason.Fairy)
    def scoreExtraFinal(self):
        if self.board.checkPack(3, "c") and self.board.fairy.follower is self and isinstance(self.player, Player):
            self.fairy_3 += 1
            from .ccs_helper import LogScore
            self.board.addLog(LogScore(self.player.long_name, "fairy_complete", 3))
            self.player.addScoreFinal(3, type=ScoreReason.Fairy)
    canEatByDragon: bool = True
    canPutTypes: 'tuple[Type[Segment] | Type[Feature] | Type[Tile],...]' = (FieldSegment, CitySegment, RoadSegment, Monastry, Flier, Tower)
    key: tuple[int, int] = (-1, -1)
class Follower(Token):
    @property
    def strength(self) -> int:
        return 1
class Figure(Token):
    pass
class TileFigure(Figure):
    def __init__(self, parent: 'Player | Board', data: dict[str, Any], img: Image) -> None:
        super().__init__(parent, data, img)
        self.draw_pos: tuple[int, int] | None = None
    def findDrawPos(self, drawn_poses: list[tuple[int, int]] | None=None):
        if not isinstance(self.parent, Tile):
            return (0, 0)
        if self.draw_pos is not None:
            return self.draw_pos
        if drawn_poses is None:
            drawn_poses = []
            for seg in self.parent.segments:
                drawn_poses.extend(seg.drawPos(len(seg.tokens)))
            for feature in self.parent.features:
                drawn_poses.extend(feature.drawPos(len(feature.tokens)))
        if self.draw_pos is None:
            for _ in range(10):
                post = (random.randint(8, 56), random.randint(8, 56))
                if all(dist2(post, p) >= 256 for p in drawn_poses):
                    self.draw_pos = post
                    break
            else:
                post = (random.randint(8, 56), random.randint(8, 56))
        return self.draw_pos
    canPutTypes = (Tile,)
class BaseFollower(Follower):
    key = (0, 0)
    name = "跟随者"
    canPutTypes = (FieldSegment, CitySegment, RoadSegment, Monastry, Flier, Tower, Acrobat)
class BigFollower(Follower):
    @property
    def strength(self):
        return 2
    def image(self):
        return super().image().resize((24, 24))
    key = (1, 0)
    name = "大跟随者"
class Builder(Figure):
    def canPut(self, seg: Segment | Feature | Tile):
        if not super().canPut(seg):
            return False
        if isinstance(seg, Segment):
            return any(t.player is self.player for s in seg.object.segments for t in s.tokens if isinstance(t, Follower))
        return False
    canPutTypes = (CitySegment, RoadSegment)
    key = (2, 0)
    name = "建筑师"
class Pig(Figure):
    def canPut(self, seg: Segment | Feature | Tile):
        if not super().canPut(seg):
            return False
        if isinstance(seg, FieldSegment):
            return any(t.player is self.player for s in seg.object.segments for t in s.tokens if isinstance(t, Follower))
        return False
    canPutTypes = (FieldSegment,)
    key = (2, 1)
    name = "猪"
class Mayor(Follower):
    @property
    def strength(self) -> int:
        if not isinstance(self.parent, Segment):
            return 0
        return self.parent.object.checkPennant()
    canPutTypes = (CitySegment, Flier)
    key = (5, 0)
    name = "市长"
class Wagon(Follower):
    canPutTypes = (CitySegment, RoadSegment, Monastry, Flier)
    key = (3, 1)
    name = "马车"
class Barn(Figure):
    def canPut(self, seg: Segment | Feature | Tile):
        return isinstance(seg, Tile) and (pos := self.board.findTilePos(seg)) and \
            all((pos[0] + i, pos[1] + j) in self.board.tiles and not self.board.tiles[pos[0] + i, pos[1] + j].isAbbey for i in (0, 1) for j in (0, 1)) and \
            (barnseg := seg.getBarnSeg()) is not None and \
            all(not isinstance(t, Barn) for s in barnseg.object.segments for t in s.tokens) and \
            self.board.tiles[pos[0] + 1, pos[1] + 1].getBarnSeg((Dir.LEFT, Dir.UP)) is not None and \
            self.board.tiles[pos[0] + 1, pos[1]].getBarnSeg((Dir.DOWN, Dir.LEFT)) is not None and \
            self.board.tiles[pos[0], pos[1] + 1].getBarnSeg((Dir.UP, Dir.RIGHT)) is not None
    def selfPutOn(self, seg: Segment | Feature | Tile) -> TAsync[None]:
        if isinstance(seg, Tile) and (s := seg.getBarnSeg()):
            s.tokens.append(self)
            self.parent = s
        return
        yield {}
    canEatByDragon = False
    canPutTypes = (Tile,)
    key = (5, 2)
    name = "谷仓"
class Dragon(TileFigure):
    def __init__(self, parent: 'Player | Board', data: dict[str, Any], img: Image) -> None:
        super().__init__(parent, data, img)
        self.tile: Tile | None = None
        self.draw_pos = (32, 32)
    def findDrawPos(self, drawn_poses: list[tuple[int, int]] | None=None):
        return (32, 32)
    def canMove(self, tile: Tile):
        if self.board.checkPack(3, "c") and self.board.fairy.tile is tile:
            return False
        return tile not in self.board.dragonMoved
    def moveTo(self, tile: Tile):
        if self.tile is not None:
            self.tile.tokens.remove(self)
        tile.tokens.append(self)
        self.parent = self.tile = tile
        to_remove = tile.tokens + [token for seg in tile.segments for token in seg.tokens] + [token for feature in tile.features for token in feature.tokens]
        for token in to_remove:
            if token.canEatByDragon:
                token.putBackToHand(HomeReason.Dragon)
        for seg in tile.segments:
            seg.object.checkRemoveBuilderAndPig(HomeReason.Dragon)
    def putBackToHand(self, reason: 'HomeReason'):
        self.tile = None
        return super().putBackToHand(reason)
    canEatByDragon = False
    key = (3, 0)
    name = "龙"
class Fairy(Figure):
    def __init__(self, parent: 'Player | Board', data: dict[str, Any], img: Image) -> None:
        super().__init__(parent, data, img)
        self.follower: Follower | None = None
        self.tile: Tile | None = None
        self.drawpos: tuple[int, int] = 32, 32
    def moveTo(self, follower: Follower, tile: Tile):
        self.tile = tile
        self.follower = follower
        pos = tile.findTokenDrawPos(follower)
        self.drawpos = pos[0], pos[1] + 8
    def putBackToHand(self, reason: 'HomeReason'):
        self.follower = None
        self.tile = None
        return super().putBackToHand(reason)
    canEatByDragon = False
    key = (3, 1)
    name = "仙子"
class Abbot(Follower):
    canPutTypes = (BaseCloister, Flier)
    key = (7, 0)
    name = "修道院长"
class Ranger(Figure):
    def __init__(self, parent: 'Player | Board', data: dict[str, Any], img: Image) -> None:
        super().__init__(parent, data, img)
        self.pos: tuple[int, int] | None = None
    def canMove(self, pos: tuple[int, int]):
        return pos not in self.board.tiles and any(pos + dr in self.board.tiles for dr in Dir)
    def moveTo(self, pos: tuple[int, int]):
        self.pos = pos
    key = (14, 0)
    name = "护林员"
class Gingerbread(Figure):
    def score(self) -> TAsync[None]:
        if not isinstance(self.parent, Board):
            assert isinstance(self.parent, CitySegment)
            players: list[Player] = []
            for token in self.parent.object.iterTokens():
                if isinstance(token.player, Player) and token.player not in players:
                    players.append(token.player)
            score = self.parent.object.checkTile()
            for player in players:
                from .ccs_helper import LogScore
                self.board.addLog(LogScore(player.long_name, "gingerbread", score))
                yield from player.addScore(score, type=ScoreReason.Gingerbread)
    canPutTypes = (CitySegment,)
    key = (14, 1)
    name = "姜饼人"
class Phantom(Follower):
    def image(self):
        assert isinstance(self.player, Player)
        id = (4, 2, 0, 1, 5, 3)[self.player.id]
        if isinstance(self.parent, FieldSegment):
            return self.board.tokenimgs[13].crop(((id % 3) * 17, 28 + (id // 3) * 14, (id % 3) * 17 + 16, 28 + (id // 3) * 14 + 13))
        return self.board.tokenimgs[13].crop(((id % 3) * 17, (id // 3) * 14, (id % 3 + 1) * 17, (id // 3 + 1) * 14))
    key = (13, 4)
    name = "幽灵"
class King(Figure):
    def __init__(self, parent: 'Player | Board', data: dict[str, Any], img: Image) -> None:
        super().__init__(parent, data, img)
        self.max: int = 0
        self.complete_citys: list[Object] = []
    key = (6, 0)
    name = "国王"
    canEatByDragon = False
class Robber(Figure):
    def __init__(self, parent: 'Player | Board', data: dict[str, Any], img: Image) -> None:
        super().__init__(parent, data, img)
        self.max: int = 0
        self.complete_roads: list[Object] = []
    key = (6, 1)
    name = "小偷"
    canEatByDragon = False
class Gold(TileFigure):
    key = (13, 0)
    name = "金块"
    canEatByDragon = False
    @classmethod
    def score(cls, num: int):
        return (num + 2) // 3 * num
class Shepherd(Figure):
    def __init__(self, parent: 'Player | Board', data: dict[str, Any], img: Image) -> None:
        super().__init__(parent, data, img)
        self.sheeps: list[int] = []
    def canPut(self, seg: Segment | Feature | Tile):
        if not super().canPut(seg):
            return False
        if isinstance(seg, FieldSegment) and any(isinstance(t, Shepherd) for t in seg.object.iterTokens()):
            return False
        return True
    def putBackToHand(self, reason: 'HomeReason'):
        super().putBackToHand(reason)
        self.board.sheeps.extend(self.sheeps)
        self.sheeps = []
    def grow(self):
        assert isinstance(self.parent, FieldSegment)
        assert isinstance(self.player, Player)
        i = random.choice(self.board.sheeps)
        from .ccs_helper import LogShepherd
        self.board.addLog(LogShepherd(self.player.long_name, i))
        if i == -1:
            self.putBackToHand(HomeReason.Wolf)
            for t in self.parent.object.iterTokens():
                if isinstance(t, Shepherd):
                    t.putBackToHand(HomeReason.Wolf)
        else:
            self.board.sheeps.remove(i)
            self.sheeps.append(i)
    def score(self):
        assert isinstance(self.parent, FieldSegment)
        to_score: list[Shepherd] = []
        score = 0
        for t in self.parent.object.iterTokens():
            if isinstance(t, Shepherd):
                to_score.append(t)
                score += sum(t.sheeps)
        for t in to_score:
            assert isinstance(t.player, Player)
            yield from t.player.addScore(score, type=ScoreReason.Shepherd)
        for t in to_score:
            t.putBackToHand(HomeReason.Shepherd)
    def image(self):
        img = super().image()
        dr = ImageDraw.Draw(img)
        font = ImageFont.truetype("msyhbd.ttc", 10)
        dr.ellipse(((12, 12), (24, 24)), "white", "black", 1)
        text = str(sum(self.sheeps))
        dr.text((18, 18), text, "black", font, "mm")
        return img
    key = (9, 0)
    name = "牧羊人"
    canPutTypes = (FieldSegment,)
class Mage(Figure):
    key = (13, 1)
    name = "法师"
class Witch(Figure):
    key = (13, 2)
    name = "女巫"
class Bigtop(Figure):
    key = (10, 0)
    name = "马戏帐篷"
    def score(self) -> TAsync[None]:
        if isinstance(self.parent, Circus) and (pos := self.board.findTilePos(self.parent.tile)) is not None:
            score = self.board.animals.pop(0)
            from .ccs_helper import LogCircus
            self.board.addLog(LogCircus(score))
            tiles = [self.board.tiles[p] for i in (-1, 0, 1) for j in (-1, 0, 1) if (p := (pos[0] + i, pos[0] + j)) in self.board.tiles]
            followers = [token for tile in tiles for token in tile.iterAllTokens() if isinstance(token, Follower)]
            players: dict[Player, int] = {}
            for follower in followers:
                if isinstance(follower.parent, Player):
                    players[follower.parent] = players.get(follower.parent, 0) + self.board.animals[0]
            for player, s in players.items():
                yield from player.addScore(s, ScoreReason.Bigtop)
class Ringmaster(Follower):
    key = (10, 1)
    name = "马戏指挥"
    def scoreExtra(self) -> TAsync[None]:
        yield from super().scoreExtra()
        tile: Tile | None = None
        if isinstance(self.parent, Segment):
            tile = self.parent.tile
        elif isinstance(self.parent, CanScore) and isinstance(self.parent, Feature):
            tile = self.parent.tile
        if isinstance(self.player, Player) and tile is not None and (pos := self.board.findTilePos(tile)) is not None:
            tiles = [self.board.tiles[p] for i in (-1, 0, 1) for j in (-1, 0, 1) if (p := (pos[0] + i, pos[0] + j)) in self.board.tiles]
            extra = sum(2 for t in tiles for feature in t.features if isinstance(t, (Circus, Acrobat)))
            yield from self.player.addScore(extra, ScoreReason.Ringmaster)
    def scoreExtraFinal(self):
        super().scoreExtraFinal()
        tile: Tile | None = None
        if isinstance(self.parent, Segment):
            tile = self.parent.tile
        elif isinstance(self.parent, CanScore) and isinstance(self.parent, Feature):
            tile = self.parent.tile
        if isinstance(self.player, Player) and tile is not None and (pos := self.board.findTilePos(tile)) is not None:
            tiles = [self.board.tiles[p] for i in (-1, 0, 1) for j in (-1, 0, 1) if (p := (pos[0] + i, pos[0] + j)) in self.board.tiles]
            extra = sum(2 for t in tiles for feature in t.features if isinstance(t, (Circus, Acrobat)))
            self.player.addScoreFinal(extra, ScoreReason.Ringmaster)

Token.all_name["follower"] = BaseFollower

AbbeyData = TileData("abbey", 0, "FFFF", [])
AbbeyData.segments.append(FeatureSegmentData("Cloister", (32, 32), [], AbbeyData))

from .ccs_extra import LandCity, LandRoad, LandMonastry, ScoreReason, HomeReason
from .ccs_extra import ccsCityStat, ccsGameStat, ccsRoadStat, ccsFieldStat, ccsMonastryStat, ccsMeepleStat, ccsTowerStat
from .ccs_player import Player
from .ccs_helper import RecieveId
from .ccs_board import Board

if __name__ == "__main__":
    from .ccs_tile import open_img
    b = Board({0: "a", 1: "abcd", 2: "abcd", 3: "abcde", 4: "ab", 5: "abcde", 6: "abcdefgh", 7: "abcd", 9: "abc", 10: "abcd", 12: "abe", 13: "abcdijk"}, ["任意哈斯塔", "哈斯塔网络整体意识", "当且仅当哈斯塔", "到底几个哈斯塔", "普通的哈斯塔", "不是哈斯塔"])
    d = {
            "name": "follower",
            "distribute": True,
            "num": 7,
            "image": [0, 0, 16, 16]
        }
    b.players[0].tokens.pop(0)
    yshift = 0
    cri = lambda s: s.serialNumber[0] in (10, 12)
    picnames = sorted(set(s.serialNumber[1] for s in b.deck + b.riverDeck if cri(s)))
    for pic in picnames:
        ss = sorted(set(s.serialNumber[1:] for s in b.deck + b.riverDeck if s.picname == pic if cri(s)))
        for i, s2 in enumerate(ss):
            t = b.tiles[i % 5, i // 5 + yshift] = [s for s in b.deck + b.riverDeck if s.picname == pic and s.serialNumber[1:] == s2][0]
            # t.turn(Dir.LEFT)
            for seg in t.segments:
                b.players[0].tokens.append(BaseFollower(b.players[0], d, open_img("token0").crop((0, 0, 16, 16))))
                for _ in b.players[0].tokens[-1].putOn(seg):
                    pass
            for feature in t.features:
                if isinstance(feature, BaseCloister):
                    b.players[0].tokens.append(BaseFollower(b.players[0], d, open_img("token0").crop((0, 0, 16, 16))))
                    for _ in b.players[0].tokens[-1].putOn(feature):
                        pass
                if isinstance(feature, Tower):
                    b.players[1].tokens.append(BaseFollower(b.players[1], d, open_img("token0").crop((0, 0, 16, 16))))
                    for _ in b.players[1].tokens[-1].putOn(feature):
                        pass
                    feature.height = random.randint(0, 9)
        yshift += (len(ss) + 4) // 5
    for p in b.players:
        p.last_pos = (0, p.id)
    # b.setImageArgs(debug=True)
    b.image().show()
