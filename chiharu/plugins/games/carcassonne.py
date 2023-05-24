from typing import Literal, Any, Generator, Type, TypeVar, Iterable, Callable, Sequence, TypedDict
import random, itertools, more_itertools, json
from enum import Enum, auto
from abc import ABC, abstractmethod
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from .carcassonne_tile import Dir, open_img, readTileData, readPackData, TileData, PointSegmentPic
from .carcassonne_tile import CitySegmentData, RoadSegmentData, RiverSegmentData, FieldSegmentData, FeatureSegmentData, AddableSegmentData
from .carcassonne_tile import AreaSegmentPic, LineSegmentPic, SegmentData

class CantPutError(Exception):
    pass
class NoDeckEnd(Exception):
    pass
class Connectable(Enum):
    City = auto()
    Field = auto()
    Road = auto()
    River = auto()
    @classmethod
    def fromChar(cls, char: str):
        return {"C": Connectable.City, "F": Connectable.Field, "R": Connectable.Road, "S": Connectable.River}[char]
class TileAddable(Enum):
    No = auto()
    Volcano = auto()
    Dragon = auto()
    Portal = auto()
    Gold = auto()
    Gingerbread = auto()
class Addable(Enum):
    No = auto()
    Cathedral = auto()
    Inn = auto()
    Wine = auto()
    Grain = auto()
    Cloth = auto()
    Princess = auto()
    Pigherd = auto()
all_extensions = {1: 'abcd', 2: 'abcd', 3: 'abcde', 4: 'ab', 5: 'abcde', 6: 'abcdefgh', 7: 'abcd', 12: 'abcdef', 13: 'abcdefghijk', 14: 'abcdefg'}
T = TypeVar('T')
TAsync = Generator[dict[str, Any], dict[str, Any], T]
def findAllMax(items: Sequence[T], key: Callable[[T], int], criteria=None) -> tuple[int, list[T]]:
    maxScore: int = -99
    maxPlayer: list[T] = []
    for player in items:
        if criteria is not None and not criteria(player):
            continue
        if (score := key(player)) > maxScore:
            maxScore = score
            maxPlayer = [player]
        elif score == maxScore:
            maxPlayer.append(player)
    return maxScore, maxPlayer

def turn(pos: tuple[int, int], dir: Dir):
    if dir == Dir.UP:
        return pos
    if dir == Dir.RIGHT:
        return 64 - pos[1], pos[0]
    if dir == Dir.DOWN:
        return 64 - pos[0], 64 - pos[1]
    return pos[1], 64 - pos[0]
def dist2(pos1: tuple[int, int], pos2: tuple[int, int]) -> float:
    return (pos1[0] - pos2[0]) ** 2 + (pos1[1] - pos2[1]) ** 2

TToken = TypeVar("TToken", bound="Token")

class Board:
    def __init__(self, packs_options: dict[int, str], player_names: list[str], start_tile_pack: int=0) -> None:
        all_packs = readTileData(packs_options)
        packs: list[dict[str, Any]] = readPackData()["packs"]
        self.packs_options = packs_options
        self.tiles: dict[tuple[int, int], Tile] = {}
        self.riverDeck: list[Tile] = []
        self.deck: list[Tile] = []
        self.tokens: list[Token] = []
        self.players: list[Player] = [Player(self, i, name) for i, name in enumerate(player_names)]
        self.tokenimgs: dict[int, Image.Image] = {}
        self.allTileimgs: dict[tuple[int, str, int, int], Image.Image] = {}
        start_tile: Tile | None = None
        for tileData in all_packs:
            tile = Tile(self, tileData, False)
            if 'S' in tileData.sides:
                self.riverDeck.append(tile)
            else:
                self.deck.append(tile)
            if tileData.start and tileData.packid == start_tile_pack:
                start_tile = tile
            self.allTileimgs[tile.serialNumber] = tile.img
        for pack in packs:
            pack_id = pack["id"]
            if "tokens" in pack:
                self.tokenimgs[pack_id] = open_img("token" + str(pack_id))
            for t in pack.get("tokens", []):
                if pack_id not in packs_options:
                    continue
                if "thing_id" in t and t["thing_id"] not in packs_options[pack_id]:
                    continue
                num = t["num"] if "num" in t else t["numOfPlayers"][str(len(self.players))]
                if t["name"] == "tower":
                    for p in self.players:
                        p.towerPieces = num
                else:
                    img = self.tokenimgs[pack_id].crop(tuple(t["image"]))
                    if t["distribute"]:
                        for p in self.players:
                            p.tokens.extend(Token.make(t["name"])(p, t, img) for i in range(num))
                    else:
                        self.tokens.extend(Token.make(t["name"])(self, t, img) for i in range(num))
        if pack_id == 5 and self.checkPack(5, "b"):
            self.abbeyImg = open_img("abbey")
        for player in self.players:
            player.allTokens = [t for t in player.tokens]
        self.allTokens = [t for t in self.tokens]
            # if self.checkPack(7, "b"):
            #     if self.checkPack(7, "c"):
            #         start_id = 22
            #         self.popRiverTile([t for t in self.riverDeck if t.packid == 7 and t.id == 0][0])
            #     else:
            #         start_id = 0
            #     start_tile = [t for t in self.riverDeck if t.packid == start_tile_pack and t.id == start_id][0]
            #     self.popRiverTile(start_tile)
            #     start_tile.turn(Dir.LEFT) TODO
        if start_tile is None:
            raise NotImplementedError
        self.popTile(start_tile)
        self.tiles[0, 0] = start_tile
        self.current_player_id = 0
        self.current_turn_player_id = 0
        random.shuffle(self.deck)
        if not (self.checkPack(7, "a") or self.checkPack(7, "b") or self.checkPack(7, "d")):
            self.riverDeck = []
        if len(self.riverDeck) > 0:
            random.shuffle(self.riverDeck)
        if self.checkPack(7, "b"):
            fork = [tile for tile in self.riverDeck if tile.id == 1][0]
            self.riverDeck.remove(fork)
            self.riverDeck = [fork] + self.riverDeck
            end = [tile for tile in self.riverDeck if tile.id == 3][0]
            self.riverDeck.remove(end)
            self.riverDeck.append(end)
        self.players[0].tokens.sort(key=lambda x: x.key)
        self.token_pos: dict[Type[Token], int] = {}
        xpos = 0
        last_key: tuple[int, int] = (-1, -2)
        for t in self.players[0].tokens:
            if t.key != last_key:
                self.token_pos[type(t)] = xpos
                last_key = t.key
                if len([1 for tk in self.players[0].tokens if tk.key == last_key]) >= 3:
                    xpos += t.image().size[0] + 24 + 4
                else:
                    xpos += t.image().size[0] + 4
        self.token_length = xpos
        self.font_name = ImageFont.truetype("msyhbd.ttc", 16)
        self.font_score = ImageFont.truetype("msyhbd.ttc", 24)
        self.state: State = State.End
        self.stateGen = self.process()
        self.log: list[dict[str, Any]] = []
        if self.checkPack(3, "b"):
            self.dragon = [token for token in self.tokens if isinstance(token, Dragon)][0]
            self.dragonMoved: list[Tile] = []
        if self.checkPack(3, "c"):
            self.fairy = [token for token in self.tokens if isinstance(token, Fairy)][0]
        if self.checkPack(14, "b"):
            self.ranger = [token for token in self.tokens if isinstance(token, Ranger)][0]
        if self.checkPack(14, "d"):
            self.gingerbread = [token for token in self.tokens if isinstance(token, Gingerbread)][0]
        if self.checkPack(14, 'a'):
            self.giftDeck = [Gift.make(i)() for i in range(5) for _ in range(5)]
            random.shuffle(self.giftDeck)
            self.giftDiscard: list[Gift] = []
        self.imageArgs: dict[str, Any] = {}
    def checkPack(self, packid: int, thingid: str):
        return packid in self.packs_options and thingid in self.packs_options[packid]
    @property
    def current_player(self):
        return self.players[self.current_player_id]
    @property
    def current_turn_player(self):
        return self.players[self.current_turn_player_id]
    @property
    def lrborder(self):
        leftmost = min(i for i, j in self.tiles.keys())
        rightmost = max(i for i, j in self.tiles.keys())
        return leftmost, rightmost
    @property
    def udborder(self):
        uppermost = min(j for i, j in self.tiles.keys())
        lowermost = max(j for i, j in self.tiles.keys())
        return uppermost, lowermost

    def popTile(self, tile: 'Tile'):
        self.deck.remove(tile)
    def popRiverTile(self, tile: 'Tile'):
        self.riverDeck.remove(tile)
    def drawTile(self):
        if len(self.deck) == 0:
            raise NoDeckEnd
        tile = self.deck[0]
        self.popTile(tile)
        return tile
    def drawTileCanPut(self):
        tile = self.drawTile()
        checked: int = 0
        while tile is not None and not self.checkTileCanPut(tile):
            self.addLog(id="redraw", tile=tile)
            checked += 1
            self.deck.append(tile)
            tile = self.drawTile()
            if checked >= len(self.deck):
                return None
        if checked >= 1:
            random.shuffle(self.deck)
        return tile
    def drawRiverTile(self):
        tile = self.riverDeck[0]
        self.popRiverTile(tile)
        return tile
    def drawGift(self):
        if not self.checkPack(14, 'a'):
            return None
        if len(self.giftDeck) == 0:
            if len(self.giftDiscard) == 0:
                return None
            self.giftDeck = self.giftDiscard
            random.shuffle(self.giftDeck)
        return self.giftDeck.pop(0)
    def nextPlayer(self):
        self.current_turn_player_id += 1
        if self.current_turn_player_id >= len(self.players):
            self.current_turn_player_id -= len(self.players)
        self.current_player_id = self.current_turn_player_id
    def nextAskingPlayer(self):
        self.current_player_id += 1
        if self.current_player_id >= len(self.players):
            self.current_player_id -= len(self.players)
    def endGameScore(self):
        for tile in self.tiles.values():
            for seg in tile.segments:
                if len(seg.tokens) != 0 or len(seg.object.tokens) != 0:
                    seg.object.scoreFinal()
            for feature in tile.features:
                if isinstance(feature, CanScore) and len(feature.tokens) != 0:
                    feature.scoreFinal()
        if self.checkPack(2, "d"):
            for i in range(3):
                max_token, max_players = findAllMax(self.players, lambda player, i=i: player.tradeCounter[i]) # type: ignore
                for player in max_players:
                    player.addScoreFinal(10)
        if self.checkPack(14, 'a'):
            for player in self.players:
                if len(player.gifts) >= 0:
                    player.addScoreFinal(2 * len(player.gifts))
    def winner(self):
        return findAllMax(self.players, lambda player: player.score)
    def canPutTile(self, tile: 'Tile', pos: tuple[int, int], orient: Dir) -> Literal[-1, -2, -3, -8, 0]:
        """-1：已有连接, -2：无法连接，-3：没有挨着。"""
        if pos in self.tiles:
            return -1
        if all(pos + dr not in self.tiles for dr in Dir):
            return -3
        if not tile.isAbbey:
            for dr in Dir:
                side = pos + dr
                if side in self.tiles:
                    ret = self.tiles[side].checkConnect(tile, -dr, orient)
                    if ret < 0:
                        return ret
        if self.checkPack(6, "h"):
            cl = more_itertools.only(0 if isinstance(feature, Cloister) else 1 if isinstance(feature, Shrine) else -1 for feature in tile.features if isinstance(feature, BaseCloister))
            if cl in (0, 1):
                around = [(pos[0] + i, pos[1] + j) for i in (-1, 0, 1) for j in (-1, 0, 1) if (pos[0] + i, pos[1] + j) in self.tiles]
                l = [pos for pos in around for feature in self.tiles[pos].features if isinstance(feature, (Shrine, Cloister)[cl])]
                if len(l) >= 2:
                    return -8
                if len(l) == 1:
                    pos_new = l[0]
                    around = [(i, j) for i in (-1, 0, 1) for j in (-1, 0, 1) if (pos_new[0] + i, pos_new[1] + j) in self.tiles for feature in self.tiles[pos_new[0] + i, pos_new[1] + j].features if isinstance(feature, (Cloister, Shrine)[cl])]
                    if len(around) >= 1:
                        return -8
        return 0
    def checkTileCanPut(self, tile: 'Tile'):
        if self.checkPack(3, "b") and self.dragon.tile is None and tile.addable == TileAddable.Dragon:
            return False
        leftmost, rightmost = self.lrborder
        uppermost, lowermost = self.udborder
        for i in range(leftmost - 1, rightmost + 2):
            for j in range(uppermost - 1, lowermost + 2):
                for orient in Dir:
                    if self.canPutTile(tile, (i, j), orient) == 0:
                        return True
        return False
    def findTilePos(self, tile: 'Tile'):
        return more_itertools.only(pos for pos, t in self.tiles.items() if t is tile)
    def tileNameToPos(self, xs: str, ys: str):
        x = (ord(xs[0]) - ord('A') + 1) * 26 + ord(xs[1]) - ord('A') if len(xs) == 2 else ord(xs) - ord('A')
        y = int(ys)
        leftmost, rightmost = self.lrborder
        uppermost, lowermost = self.udborder
        return (x + leftmost - 1, y + uppermost - 1)
    def checkHole(self):
        leftmost, rightmost = self.lrborder
        uppermost, lowermost = self.udborder
        for i in range(leftmost + 1, rightmost):
            for j in range(uppermost + 1, lowermost):
                if (i, j) not in self.tiles and all((i, j) + dir in self.tiles for dir in Dir):
                    return True
        return False
    def addLog(self, /, **log):
        self.log.append(log)

    def tileImages(self):
        draw_tile_seg: tuple[int, int] | list[tuple[int, int]] | None = self.imageArgs.get("draw_tile_seg")
        debug: bool = self.imageArgs.get("debug", False)
        draw_tile_follower: tuple[int, int] | None = self.imageArgs.get("draw_tile_follower")
        princess: Object | None = self.imageArgs.get("princess")
        tower_pos: tuple[int, int] | None = self.imageArgs.get("tower_pos")
        draw_occupied_seg: bool = self.imageArgs.get("draw_occupied_seg", False)

        leftmost, rightmost = self.lrborder
        uppermost, lowermost = self.udborder
        img = Image.new("RGBA", ((rightmost - leftmost + 1) * 64 + 46, (lowermost - uppermost + 1) * 64 + 46))
        dr = ImageDraw.Draw(img)
        def pos(w: int, h: int, *offsets: tuple[int, int]):
            return w * 64 + sum(c[0] for c in offsets) + 32, h * 64 + sum(c[1] for c in offsets) + 32
        def posshift(w: int, h: int, *offsets: tuple[int, int]):
            return (w - leftmost) * 64 + sum(c[0] for c in offsets) + 32, (h - uppermost) * 64 + sum(c[1] for c in offsets) + 32
        for (i, j), tile in self.tiles.items():
            img.paste(tile.image(debug), posshift(i, j))
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
        font = ImageFont.truetype("msyhbd.ttc", 10)
        def alpha(n):
            if n <= 25: return chr(ord('A') + n)
            return chr(ord('A') + n // 26 - 1) + chr(ord('A') + n % 26)
        dr.text(pos(0, 0, (-5, -15)), 'A', "black", font, "mb")
        for i in range(0, width + 1):
            dr.text(pos(i, 0, (32, -15)), alpha(i + 1), "black", font, "mb")
        dr.text(pos(width + 1, 0, (5, -15)), alpha(width + 2), "black", font, "mb")
        dr.text(pos(0, 0, (-15, -5)), '0', "black", font, "rm")
        for j in range(0, height + 1):
            dr.text(pos(0, j, (-15, 32)), str(j + 1), "black", font, "rm")
        dr.text(pos(0, height + 1, (-15, 5)), str(height + 2), "black", font, "rm")
        # tokens
        for (i, j), tile in self.tiles.items():
            tile.drawToken(img, posshift(i, j))
        if self.checkPack(3, "c") and self.fairy.tile is not None and (p := self.findTilePos(self.fairy.tile)) is not None:
            tf = self.fairy.image()
            img.alpha_composite(tf, posshift(*p, self.fairy.drawpos, (-tf.size[0] // 2, -tf.size[1] // 2)))
        # choose follower
        def draw(c: tuple[int, int], tpos: tuple[int, int], i: int):
            dr.ellipse((posshift(*c, (tpos[0] - 6, tpos[1] - 6)), posshift(*c, (tpos[0] + 6, tpos[1] + 6))), "white", "black", 1)
            text = chr(i) if i <= ord('a') + 25 else chr((i - ord('a')) // 26) + chr((i - ord('a')) % 26)
            dr.text(posshift(*c, tpos), text, "black", font, "mm")
        if draw_tile_seg is not None:
            if isinstance(draw_tile_seg, tuple):
                choose_follower2 = [draw_tile_seg]
            else:
                choose_follower2 = draw_tile_seg
            for c in choose_follower2:
                if c not in self.tiles:
                    continue
                tile = self.tiles[c]
                tile.drawPutToken(img, posshift(*c), draw_occupied_seg, self.checkPack(5, "e") and len(choose_follower2) == 1 and any(isinstance(token, Barn) for token in self.current_turn_player.tokens))
        if draw_tile_follower is not None and draw_tile_follower in self.tiles:
            tile = self.tiles[draw_tile_follower]
            i = ord('a')
            for follower in tile.iterAllTokens():
                if isinstance(follower, Follower) and follower.player is self.current_turn_player:
                    draw(self.findTilePos(tile), tile.findTokenDrawPos(follower), i)
                    i += 1
        if princess is not None:
            i = ord('a')
            for follower in princess.iterTokens():
                if isinstance(follower, Follower) and isinstance(follower.parent, Segment):
                    draw(self.findTilePos(follower.parent.tile), follower.parent.tile.findTokenDrawPos(follower), i)
                    i += 1
        if tower_pos is not None:
            tower = [feature for feature in self.tiles[tower_pos].features if isinstance(feature, Tower)][0]
            followers = [token for token in self.tiles[tower_pos].iterAllTokens() if isinstance(token, Follower)] + [token for dr in Dir for i in range(tower.height) if (tower_pos[0] + dr.corr()[0] * (i + 1), tower_pos[1] + dr.corr()[1] * (i + 1)) in self.tiles for token in self.tiles[tower_pos[0] + dr.corr()[0] * (i + 1), tower_pos[1] + dr.corr()[1] * (i + 1)].iterAllTokens() if isinstance(token, Follower)]
            i = ord('a')
            for follower in followers:
                if isinstance(follower.parent, Segment):
                    draw(self.findTilePos(follower.parent.tile), follower.parent.tile.findTokenDrawPos(follower), i)
                    i += 1
        # tiles dragon has moved
        if self.checkPack(3, "b"):
            for tile in self.dragonMoved:
                p = self.findTilePos(tile)
                if p is not None:
                    tileimg = img.crop(posshift(*p) + posshift(*p, (64, 64)))
                    enhancer = ImageEnhance.Brightness(tileimg)
                    img.paste(enhancer.enhance(0.7), posshift(*p))
        # ranger
        if self.checkPack(14, "b") and (pos_ranger := self.ranger.pos) is not None and pos_ranger not in self.tiles:
            offset_edge = (32, 32)
            if pos_ranger[0] == leftmost - 1:
                offset_edge = (59, offset_edge[1])
            if pos_ranger[0] == rightmost + 1:
                offset_edge = (5, offset_edge[1])
            if pos_ranger[1] == uppermost - 1:
                offset_edge = (offset_edge[0], 59)
            if pos_ranger[1] == lowermost + 1:
                offset_edge = (offset_edge[0], 5)
            img.alpha_composite(self.ranger.image(), posshift(*pos_ranger, offset_edge, (-13, -8)))
        # remain tiles
        dr.text((0, 0), str(len(self.riverDeck) if len(self.riverDeck) != 0 else len(self.deck)), "black", self.font_name, "lt")
        # remain gift
        if self.checkPack(14, "a"):
            dr.rectangle((0, 32, 16, 48), "green")
            dr.text((0, 32), str(len(self.giftDeck)), "white", self.font_name, "lt")
        return img
    def playerImage(self):
        imgs = [p.image() for p in self.players]
        img = Image.new("RGBA", (imgs[0].size[0], 24 * len(self.players)))
        for i, pimg in enumerate(imgs):
            img.alpha_composite(pimg, (0, i * 24))
        return img
    def handTileImage(self):
        return self.current_player.handTileImage()
    def remainTileImages(self):
        remove_zero = len(self.deck) <= len(self.tiles)
        def pos(w: int, h: int, *offsets: tuple[int, int]):
            return w * (64 + 8) + sum(c[0] for c in offsets) + 8, h * (64 + 20) + sum(c[1] for c in offsets) + 20
        x2: dict[int, int] = {}
        for ids in sorted(self.allTileimgs.keys()):
            dct = self.allTileimgs[ids]
            if not remove_zero or sum(1 for tile in self.deck if tile.serialNumber == ids) != 0:
                x2[ids[0]] = x2.get(ids[0], 0) + 1
        height = sum((x - 1) // 5 + 1 for x in x2.values())
        img = Image.new("RGBA", pos(5, height), "LightCyan")
        dr = ImageDraw.Draw(img)
        y: int = 0
        x: int = 0
        last_pack: int = 0
        for ids in sorted(self.allTileimgs.keys()):
            if ids[0] != last_pack:
                last_pack = ids[0]
                y += (x - 1) // 5 + 1
                x = 0
            timg = self.allTileimgs[ids]
            if not remove_zero or (num := sum(1 for tile in self.deck if tile.serialNumber == ids)) != 0:
                p = (x % 5, y + x // 5)
                img.paste(timg, pos(*p))
                dr.text(pos(*p, (32, 65)), str(num), "black", self.font_name, "mt")
                if num == 0:
                    dr.line(pos(*p) + pos(*p, (64, 64)), "red", 2)
                    dr.line(pos(*p, (64, 0)) + pos(*p, (0, 64)), "red", 2)
                x += 1
        return img

    def setImageArgs(self, **kwargs):
        self.imageArgs = kwargs
    def image(self):
        player_img = self.playerImage()
        handtile_img = self.handTileImage()
        tile_img = self.tileImages()
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
    def saveImg(self):
        from .. import config
        name = 'ccs' + str(random.randint(0, 9) + self.current_player_id * 10) + '.png'
        self.image().save(config.img(name))
        return config.cq.img(name)
    def saveRemainTileImg(self):
        from .. import config
        name = 'ccsr' + str(random.randint(0, 9) + self.current_player_id * 10) + '.png'
        self.remainTileImages().save(config.img(name))
        return config.cq.img(name)

    def endGameAskAbbey(self) -> TAsync[None]:
        if not self.checkPack(5, "b") or not self.checkHole():
            return
        players = [player for player in self.players if player.hasAbbey]
        players.sort(key=lambda player: ((0, player.id) if player.id >= self.current_turn_player_id else (1, player.id)))
        for player in players:
            if not self.checkHole():
                return
            _, isAbbey, pos = yield from player.turnAskAbbey(0, True, True)
            if isAbbey:
                yield from player.turnScoring(player.handTiles[0], pos, False, False)
                player.handTiles.pop(0)
    def process(self) -> TAsync[bool]:
        try:
            while 1:
                yield from self.current_player.turn()
                self.nextPlayer()
        except CantPutError:
            midEnd = True
        except NoDeckEnd:
            midEnd = False
        except Exception:
            self.state = State.Error
            raise
        # yield from self.endGameAskAbbey()
        self.state = State.End
        self.endGameScore()
        return midEnd

class CanScore(ABC):
    def __init__(self, board: Board) -> None:
        super().__init__()
        self.board = board
    @abstractmethod
    def closed(self) -> bool:
        pass
    def occupied(self):
        return any(True for t in self.iterTokens())
    @abstractmethod
    def iterTokens(self) -> 'Iterable[Token]':
        pass
    @abstractmethod
    def checkScore(self, players: 'list[Player]', mid_game: bool, putBarn: bool) -> 'list[tuple[Player, int]]':
        pass
    @abstractmethod
    def getTile(self) -> 'list[Tile]':
        pass
    def removeAllFollowers(self, criteria: 'Callable[[Token], bool] | None'=None):
        if criteria is None:
            criteria = lambda token: isinstance(token.player, Player) and not isinstance(token, Barn)
        to_remove: list[Token] = [token for token in self.iterTokens() if criteria(token)]
        for token in to_remove:
            token.putBackToHand()
    def checkPlayer(self) -> 'list[Player]':
        strengths: list[int] = [0 for i in range(len(self.board.players))]
        for token in self.iterTokens():
            if isinstance(token, Follower) and isinstance(token.player, Player):
                strengths[token.player.id] += token.strength
        return findAllMax(self.board.players, lambda player: strengths[player.id], lambda player: strengths[player.id] != 0)[1]
    def checkPlayerAndScore(self, mid_game: bool, putBarn: bool=True) -> 'list[tuple[Player, int]]':
        players = self.checkScore(self.checkPlayer(), mid_game, putBarn)
        return players
    def moveWagon(self) -> TAsync[None]:
        # move wagon
        if not self.board.checkPack(5, "d"):
            return
        to_remove: list[Wagon] = [token for token in self.iterTokens() if isinstance(token, Wagon)]
        to_remove.sort(key=lambda token: ((0, token.player.id) if token.player.id >= self.board.current_player_id else (1, token.player.id)) if isinstance(token.player, Player) else (-1, -1))
        if len(to_remove) > 0:
            for wagon in to_remove:
                if not isinstance(wagon.parent, Segment) or (pos := self.board.findTilePos(wagon.parent.tile)) is None:
                    continue
                assert isinstance(wagon.player, Player)
                self.board.current_player_id = wagon.player.id
                pass_err: Literal[0, -1, -2, -3] = 0
                while 1:
                    self.board.state = State.WagonAsking
                    ret = yield {"pos": pos, "player_id": wagon.player.id, "last_err": pass_err}
                    if "pos" not in ret or ret["pos"] is None:
                        break
                    pos_put: tuple[int, int] = ret["pos"]
                    if pos_put not in self.board.tiles:
                        pass_err = -1
                        continue
                    if pos_put[0] - pos[0] not in (-1, 0, 1) or pos_put[1] - pos[1] not in (-1, 0, 1):
                        pass_err = -2
                        continue
                    tile = self.board.tiles[pos_put]
                    seg_put = tile.getSeg(ret["seg"])
                    if seg_put is None:
                        pass_err = -3
                        continue
                    if (isinstance(seg_put, Feature) and not isinstance(seg_put, Monastry)):
                        pass_err = -3
                        continue
                    if seg_put.closed() or seg_put.occupied() or not wagon.canPut(seg_put):
                        pass_err = -3
                        continue
                    wagon.parent.tokens.remove(wagon)
                    yield from wagon.putOn(seg_put)
                    break
            self.board.current_player_id = self.board.current_turn_player_id
    def score(self, scorer: 'Player', putBarn: bool, ifFairy: bool=True) -> TAsync[None]:
        players = self.checkPlayerAndScore(True, putBarn=putBarn)
        for player, score in players:
            if score != 0:
                self.board.addLog(id="score", player=player, source="complete", num=score)
                yield from player.addScore(score)
        if self.board.checkPack(3, "c") and ifFairy and self.board.fairy.follower is not None:
            for token in self.iterTokens():
                if self.board.fairy.follower is token and isinstance(token.player, Player):
                    self.board.addLog(id="score", player=token.player, source="fairy_complete", num=3)
                    yield from token.player.addScore(3)
        yield from self.moveWagon()
        if self.board.checkPack(14, "d"):
            ginger = more_itertools.only(token for token in self.iterTokens() if isinstance(token, Gingerbread))
            if ginger is not None:
                yield from scorer.turnMoveGingerbread(True)
        self.removeAllFollowers()
    def scoreFinal(self):
        players = self.checkPlayerAndScore(False)
        for player, score in players:
            if score != 0:
                self.board.addLog(id="score", player=player, source="final", num=score)
                player.addScoreFinal(score)
        self.removeAllFollowers()

class Tile:
    def __init__(self, board: Board, data: TileData, isAbbey: bool) -> None:
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
    def getBarnSeg(self):
        seg = more_itertools.only(s for s in self.segments if s.inSideA(Dir.RIGHT, False) and s.inSideA(Dir.DOWN, True))
        return seg
    def findTokenDrawPos(self, token: 'Token'):
        """turned"""
        for seg in self.segments:
            if token in seg.tokens:
                id = seg.tokens.index(token)
                return turn(seg.drawPos(len(seg.tokens))[id], self.orient)
        for feature in self.features:
            if token in feature.tokens:
                id = feature.tokens.index(token)
                return turn(feature.drawPos(len(feature.tokens))[id], self.orient)
        if token in self.tokens:
            drawn_poses: list[tuple[int, int]] = []
            for seg in self.segments:
                drawn_poses.extend(seg.drawPos(len(seg.tokens)))
            for feature in self.features:
                drawn_poses.extend(feature.drawPos(len(feature.tokens)))
            if token.last_pos == (0, 0):
                for _ in range(10):
                    post = (random.randint(8, 56), random.randint(8, 56))
                    if all(dist2(post, p) >= 16 for p in drawn_poses):
                        token.last_pos = post
                        break
                else:
                    post = (random.randint(8, 56), random.randint(8, 56))
            return turn(token.last_pos, self.orient)
        return (32, 32)
    def getSeg(self, i: int):
        if i < len(self.features):
            return self.features[i]
        if i < len(self.features) + len(self.segments):
            return self.segments[i - len(self.features)]
        return None

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
        drawn_poses: list[tuple[int, int]] = []
        for seg in self.segments:
            poses = seg.drawPos(len(seg.tokens))
            drawn_poses.extend(poses)
            for i, token in enumerate(seg.tokens):
                t = token.image()
                if isinstance(token, Barn):
                    img.alpha_composite(t, pos(64, 64, (-t.size[0] // 2, -t.size[1] // 2)))
                else:
                    img.alpha_composite(t, pos(*turn(poses[i], self.orient), (-t.size[0] // 2, -t.size[1] // 2)))
        for feature in self.features:
            poses = feature.drawPos(len(feature.tokens))
            drawn_poses.extend(poses)
            for i, token in enumerate(feature.tokens):
                t = token.image()
                img.alpha_composite(t, pos(*turn(poses[i], self.orient), (-t.size[0] // 2, -t.size[1] // 2)))
            if isinstance(feature, Tower):
                dr = ImageDraw.Draw(img)
                font_tower = ImageFont.truetype("calibrib.ttf", 10)
                dr.text(pos(*turn(feature.num_pos, self.orient)), str(feature.height), "black", font_tower, "mm")
        for token in self.tokens:
            if token.last_pos == (0, 0):
                for _ in range(10):
                    post = (random.randint(8, 56), random.randint(8, 56))
                    if all(dist2(post, p) >= 16 for p in drawn_poses):
                        token.last_pos = post
                        break
                else:
                    post = (32, 32)
            t = token.image()
            img.alpha_composite(t, pos(*turn(post, self.orient), (-t.size[0] // 2, -t.size[1] // 2)))
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
            if isinstance(feature, CanScore) and (draw_occupied_seg or len(feature.tokens) == 0):
                tpos = turn(feature.putPos(len(feature.tokens)), self.orient)
                draw(tpos, i)
            i += 1
        for seg in self.segments:
            if draw_occupied_seg or len(seg.tokens) == 0:
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
            if addable.feature == "pennant":
                self.pennant += 1
            if tile.board.checkPack(1, "d") and addable.feature == "Cathedral":
                self.addable = Addable.Cathedral
            if tile.board.checkPack(2, "d") and addable.feature in ("Cloth", "Wine", "Grain"):
                self.addable = Addable[addable.feature]
            if tile.board.checkPack(3, "e") and addable.feature == "Princess":
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
            if tile.board.checkPack(1, "c") and addable.feature == "Inn":
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
            if tile.board.checkPack(2, "c") and addable.feature == "Pigherd":
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
    def checkTile(self):
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
    def checkScore(self, players: 'list[Player]', mid_game: bool, putBarn: bool) -> 'list[tuple[Player, int]]':
        match self.type:
            case Connectable.City:
                base = 2 if mid_game else 1
                if self.board.checkPack(1, "d") and any(seg.addable == Addable.Cathedral for seg in self.segments):
                    if mid_game:
                        base += 1
                    else:
                        base = 0
                score = base * (self.checkTile() + self.checkPennant())
                new_players: list[tuple[Player, int]] = [(player, score) for player in players]
            case Connectable.Road:
                base = 1
                if self.board.checkPack(1, "c") and any(seg.addable == Addable.Inn for seg in self.segments):
                    if mid_game:
                        base += 1
                    else:
                        base = 0
                score = base * self.checkTile()
                new_players = [(player, score) for player in players]
            case Connectable.Field:
                complete_city: list[Object] = []
                for seg in self.segments:
                    if isinstance(seg, FieldSegment):
                        for segc in seg.adjacentCity:
                            if segc.closed() and segc.object not in complete_city:
                                complete_city.append(segc.object)
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
                new_players = [(player, 0) for player in players]
        return new_players
    def checkRemoveBuilderAndPig(self):
        if not self.board.checkPack(2, "b") and not self.board.checkPack(2, "c"):
            return
        ts = [token for seg in self.segments for token in seg.tokens if isinstance(token, (Builder, Pig))]
        for t in ts:
            if not any(token.player is t.player for seg in self.segments for token in seg.tokens if isinstance(token, Follower)):
                self.board.addLog(id="putbackBuilder", builder=t)
                t.putBackToHand()
    def scoreFinal(self):
        super().scoreFinal()
        # barn
        if self.type == Connectable.Field and any(isinstance(token, Barn) for seg in self.segments for token in seg.tokens):
            players = self.checkBarnAndScore()
            for player, score in players:
                if score != 0:
                    player.addScoreFinal(score)
            self.removeAllFollowers(lambda token: isinstance(token, Barn))

TCloister = TypeVar('TCloister', bound='BaseCloister')
class Feature:
    pack = (0, "a")
    def __init__(self, parent: Tile, segment: FeatureSegmentData, data: list[Any]) -> None:
        self.pic = segment.pic
        self.pos = segment.pos
        self.parent = parent
        self.tokens: list[Token] = []
    def occupied(self):
        return len(self.tokens) != 0
    @classmethod
    def make(cls, typ: str) -> Type["Feature"]:
        return {"cloister": Cloister, "garden": Garden, "shrine": Shrine, "tower": Tower, "flier": Flier}[typ.lower()]
    def putOnBy(self, token: 'Token') -> TAsync[None]:
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
    def iterTokens(self) -> 'Iterable[Token]':
        yield from self.tokens
    def closed(self) -> bool:
        return len(self.getTile()) == 9
    def getTile(self):
        pos = self.parent.board.findTilePos(self.parent)
        if pos is None:
            return [self]
        return [self.parent.board.tiles[pos[0] + i, pos[1] + j] for i in (-1, 0, 1) for j in (-1, 0, 1) if (pos[0] + i, pos[1] + j) in self.parent.board.tiles]
    def checkScore(self, players: 'list[Player]', mid_game: bool, putBarn: bool) -> 'list[tuple[Player, int]]':
        score = len(self.getTile())
        return [(player, score) for player in players]
    def getCloister(self, typ: Type[TCloister]) -> TCloister | None:
        assert isinstance(self.parent, Tile)
        pos = self.board.findTilePos(self.parent)
        if pos is None:
            return None
        return more_itertools.only(feature for i in (-1, 0, 1) for j in (-1, 0, 1)
                    if (pos[0] + i, pos[1] + j) in self.board.tiles
                    for feature in self.board.tiles[pos[0] + i, pos[1] + j].features
                    if isinstance(feature, typ))
class Monastry(BaseCloister):
    pass
class Cloister(Monastry):
    def getChallenge(self):
        return self.getCloister(Shrine)
    def score(self, scorer: 'Player', putBarn: bool, ifFairy: bool=True) -> TAsync[None]:
        hasmeeple: bool = len(self.tokens) != 0
        yield from super().score(scorer, putBarn, ifFairy)
        if self.board.checkPack(6, 'h') and (cloister := self.getChallenge()) and not cloister.closed() and hasmeeple and len(cloister.tokens) != 0:
            self.board.addLog(id="challengeFailed", type="shrine")
            cloister.removeAllFollowers()
class Garden(BaseCloister):
    pack = (12, "a")
class Shrine(Monastry):
    def getChallenge(self):
        return self.getCloister(Cloister)
    def score(self, scorer: 'Player', putBarn: bool, ifFairy: bool=True) -> TAsync[None]:
        hasmeeple: bool = len(self.tokens) != 0
        yield from super().score(scorer, putBarn, ifFairy)
        if self.board.checkPack(6, 'h') and (cloister := self.getChallenge()) and not cloister.closed() and hasmeeple and len(cloister.tokens) != 0:
            self.board.addLog(id="challengeFailed", type="cloister")
            cloister.removeAllFollowers()
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
    def iterTokens(self) -> 'Iterable[Token]':
        return []
    def checkScore(self, players: 'list[Player]', mid_game: bool, putBarn: bool) -> 'list[tuple[Player, int]]':
        return []
    def getTile(self) -> 'list[Tile]':
        return []
    def putOnBy(self, token: 'Token') -> TAsync[None]:
        token.putBackToHand()
        pos = self.board.findTilePos(self.parent)
        if pos is None:
            return
        dice = random.randint(1, 3)
        self.board.addLog(id="dice", result=dice)
        ps = {0: (0, -1), 1: (1, -1), 2: (1, 0), 3: (1, 1), 4: (0, 1), 5: (-1, 1), 6: (-1, 0), 7: (-1, -1)}[(self.direction + self.parent.orient.value * 2) % 8]
        pos_new = pos[0] + ps[0] * dice, pos[1] + ps[1] * dice
        if pos_new not in self.board.tiles:
            return
        tile = self.board.tiles[pos_new]
        put_list: Sequence[Segment | Feature] = [segment for segment in tile.segments if not isinstance(segment, FieldSegment) and not segment.object.closed() and token.canPut(segment)] + [feature for feature in tile.features if isinstance(feature, CanScore) and not feature.closed() and token.canPut(feature)]
        if len(put_list) == 0:
            return
        if len(put_list) == 1:
            to_put = put_list[0]
        else:
            pass_err: Literal[0, -1, -2] = 0
            while 1:
                self.board.state = State.ChoosingSegment
                ret = yield {"last_err": pass_err, "last_put": pos_new, "special": "flier"}
                p = tile.getSeg(ret["id"])
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
        self.last_pos: tuple[int, int] = 0, 0
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
        if isinstance(seg, Feature):
            yield from seg.putOnBy(self)
        return
        yield {}
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
    def remove(self):
        if isinstance(self.parent, (Tile, Segment, Feature, Object)):
            self.parent.tokens.remove(self)
        if self.board.checkPack(3, 'c') and self.board.fairy.follower is self:
            self.board.fairy.follower = None
    def putBackToHand(self):
        if isinstance(self.parent, (Tile, Segment, Feature, Object)):
            self.parent.tokens.remove(self)
        self.player.tokens.append(self)
        self.parent = self.player
        if self.board.checkPack(3, 'c') and self.board.fairy.follower is self:
            self.board.fairy.follower = None
    canEatByDragon: bool = True
    canPutTypes: 'tuple[Type[Segment] | Type[Feature] | Type[Tile],...]' = (Segment, Monastry, Flier, Tower)
    key: tuple[int, int] = (-1, -1)
class Follower(Token):
    @property
    def strength(self) -> int:
        return 1
class Figure(Token):
    pass
class BaseFollower(Follower):
    key = (0, 0)
    name = "跟随者"
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
            (barnseg := seg.getBarnSeg()) is not None and all(not isinstance(t, Barn) for s in barnseg.object.segments for t in s.tokens)
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
class Dragon(Figure):
    def __init__(self, parent: 'Player | Board', data: dict[str, Any], img: Image) -> None:
        super().__init__(parent, data, img)
        self.tile: Tile | None = None
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
                token.putBackToHand()
        for seg in tile.segments:
            seg.object.checkRemoveBuilderAndPig()
    def putBackToHand(self):
        self.tile = None
        return super().putBackToHand()
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
    def putBackToHand(self):
        self.follower = None
        self.tile = None
        return super().putBackToHand()
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
    def selfPutOn(self, seg: Segment | Feature | Tile) -> TAsync[None]:
        if not isinstance(self.parent, Board):
            assert isinstance(self.parent, CitySegment)
            players: list[Player] = []
            for token in self.parent.object.iterTokens():
                if isinstance(token.parent, Player) and token.parent not in players:
                    players.append(token.parent)
            score = self.parent.object.checkTile()
            for player in players:
                self.board.addLog(id="score", player=player, source="gingerbread", num=score)
                yield from player.addScore(score)
        yield from super().selfPutOn(seg)
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
Token.all_name["follower"] = BaseFollower

AbbeyData = TileData("abbey", 0, "FFFF", [])
AbbeyData.segments.append(FeatureSegmentData("Cloister", (32, 32), [], AbbeyData))
class State(Enum):
    End = auto()
    PuttingTile = auto()
    ChoosingPos = auto()
    PuttingFollower = auto()
    ChoosingSegment = auto()
    WagonAsking = auto()
    AbbeyAsking = auto()
    FinalAbbeyAsking = auto()
    MovingDragon = auto()
    ChoosingOwnFollower = auto()
    PrincessAsking = auto()
    CaptureTower = auto()
    ExchangingPrisoner = auto()
    AskingSynod = auto()
    Error = auto()

class Gift:
    __slots__ = ()
    name = ""
    id = -1
    @classmethod
    def make(cls, id: int) -> 'Type[Gift]':
        return [GiftSynod, GiftRoadSweeper, GiftCashOut, GiftChangePosition, GiftTake2][id]
    @abstractmethod
    def use(self, user: 'Player') -> TAsync[int]:
        return 1
        yield {}
class GiftSynod(Gift):
    name = "教会会议"
    id = 0
    def use(self, user: 'Player') -> TAsync[int]:
        pass_err: Literal[0, -1, -2, -3, -4] = 0
        for t in user.board.tiles.values():
            cloister = more_itertools.only(feature for feature in t.features if isinstance(feature, Monastry))
            if cloister and not cloister.closed():
                break
        else:
            return -1
        while 1:
            user.board.state = State.AskingSynod
            ret = yield {"last_err": pass_err}
            if ret["pos"] not in user.board.tiles:
                pass_err = -1
                continue
            tile: Tile = user.board.tiles[ret["pos"]]
            cloister = more_itertools.only(feature for feature in tile.features if isinstance(feature, Monastry))
            if cloister is None:
                pass_err = -2
                continue
            token = user.findToken(ret.get("which", "follower"))
            if token is None:
                pass_err = -3
                continue
            if not token.canPut(cloister) or cloister.closed():
                pass_err = -4
                continue
            user.tokens.remove(token)
            yield from token.putOn(cloister)
            break
        return 1
class GiftRoadSweeper(Gift):
    name = "马路清扫者"
    id = 1
    def use(self, user: 'Player') -> TAsync[int]:
        pass_err: Literal[0, -1, -2, -3, -4] = 0
        for t in user.board.tiles.values():
            roads = [segment for segment in t.segments if isinstance(segment, RoadSegment) and not segment.closed()]
            if len(roads) > 0:
                break
        else:
            return -1
        while 1:
            user.board.state = State.ChoosingPos
            ret = yield {"last_err": pass_err, "special": "road_sweeper"}
            if ret["pos"] not in user.board.tiles:
                pass_err = -1
                continue
            tile = user.board.tiles[ret["pos"]]
            roads = [segment for segment in tile.segments if isinstance(segment, RoadSegment) and not segment.closed()]
            if len(roads) == 0:
                pass_err = -2
                continue
            road: RoadSegment = roads[0]
            if len(roads) >= 2:
                pass_err = 0
                while 1:
                    user.board.state = State.ChoosingSegment
                    ret2 = yield {"last_err": pass_err, "last_put": ret["pos"], "special": "road_sweeper"}
                    s = tile.getSeg(ret2["id"])
                    if not isinstance(s, RoadSegment):
                        pass_err = -1
                        continue
                    if s not in roads:
                        pass_err = -2
                        continue
                    road = s
                    break
            road.object.scoreFinal()
            break
        return 1
class GiftCashOut(Gift):
    name = "兑现"
    id = 2
    def use(self, user: 'Player') -> TAsync[int]:
        pass_err: Literal[0, -1, -2, -3, -4] = 0
        for t in user.board.tiles.values():
            followers = [token for token in t.iterAllTokens() if isinstance(token, Follower) and token.player is user and isinstance(token.parent, (Segment, BaseCloister))]
            if len(followers) > 0:
                break
        else:
            return -1
        while 1:
            user.board.state = State.ChoosingPos
            ret = yield {"last_err": pass_err, "special": "cash_out"}
            if ret["pos"] not in user.board.tiles:
                pass_err = -1
                continue
            tile = user.board.tiles[ret["pos"]]
            followers = [token for token in tile.iterAllTokens() if isinstance(token, Follower) and token.player is user]
            can_choose = [token for token in followers if isinstance(token.parent, (Segment, BaseCloister))]
            if len(can_choose) == 0:
                pass_err = -2
                continue
            if len(can_choose) == 1:
                follower: Follower = can_choose[0]
            else:
                pass_err = 0
                while 1:
                    user.board.state = State.ChoosingOwnFollower
                    ret2 = yield {"last_err": pass_err, "last_put": ret["pos"], "special": "cash_out"}
                    if ret2["id"] < 0 or ret2["id"] >= len(followers):
                        pass_err = -2
                        continue
                    follower = followers[ret2["id"]]
                    if not isinstance(follower.parent, (Segment, BaseCloister)):
                        pass_err = -3
                        continue
                    break
            assert isinstance(follower.parent, (Segment, BaseCloister))
            assert isinstance(follower.player, Player)
            obj = follower.parent.object if isinstance(follower.parent, Segment) else follower.parent
            score = sum(2 for token in obj.iterTokens() if isinstance(token, Follower))
            user.board.addLog(id="score", player=user, num=score, source="cash_out")
            yield from follower.player.addScore(score)
            follower.putBackToHand()
            break
        return 1
class GiftChangePosition(Gift):
    name = "切换形态"
    id = 3
    def use(self, user: 'Player') -> TAsync[int]:
        pass_err: Literal[0, -1, -2, -3] = 0
        for t in user.board.tiles.values():
            followers = [token for token in t.iterAllTokens() if isinstance(token, Follower) and token.player is user]
            for token in followers:
                if isinstance(token.parent, FieldSegment):
                    if any(isinstance(segment, (CitySegment, RoadSegment)) and token.canPut(segment) for segment in t.segments) or any(isinstance(feature, Monastry) and token.canPut(feature) for feature in t.features):
                        break
                if isinstance(token.parent, (CitySegment, RoadSegment, Monastry)):
                    if any(isinstance(segment, FieldSegment) and token.canPut(segment) for segment in t.segments):
                        break
            else:
                continue
            break
        else:
            return -1
        while 1:
            user.board.state = State.ChoosingPos
            ret = yield {"last_err": pass_err, "special": "change_position"}
            if ret["pos"] not in user.board.tiles:
                pass_err = -1
                continue
            tile = user.board.tiles[ret["pos"]]
            followers = [token for token in tile.iterAllTokens() if isinstance(token, Follower) and token.player is user]
            can_choose: list[tuple[Follower, Sequence[Segment | Monastry]]] = []
            for token in followers:
                if isinstance(token.parent, FieldSegment):
                    can_put: Sequence[Monastry | Segment] = [segment for segment in tile.segments if isinstance(segment, (CitySegment, RoadSegment)) and token.canPut(segment)] + [feature for feature in tile.features if isinstance(feature, Monastry) and token.canPut(feature)]
                    if len(can_put) > 0:
                        can_choose.append((token, can_put))
                if isinstance(token.parent, (CitySegment, RoadSegment, Monastry)):
                    can_put = [segment for segment in tile.segments if isinstance(segment, FieldSegment) and token.canPut(segment)]
                    if len(can_put) > 0:
                        can_choose.append((token, can_put))
            if len(can_choose) == 0:
                pass_err = -2
                continue
            follower, put_list = can_choose[0]
            if len(can_choose) > 1:
                pass_err = 0
                while 1:
                    user.board.state = State.ChoosingOwnFollower
                    ret2 = yield {"last_err": pass_err, "last_put": ret["pos"], "special": "change_position"}
                    if ret2["id"] < 0 or ret2["id"] >= len(followers):
                        pass_err = -2
                        continue
                    follower = followers[ret2["id"]]
                    for f, l in can_choose:
                        if f is follower:
                            put_list = l
                            break
                    else:
                        pass_err = -3
                        continue
                    break
            if len(put_list) == 1:
                to_put = put_list[0]
            else:
                pass_err = 0
                while 1:
                    user.board.state = State.ChoosingSegment
                    ret3 = yield {"last_err": pass_err, "last_put": ret["pos"], "special": "change_position"}
                    p = tile.getSeg(ret2["id"])
                    if p is None:
                        pass_err = -1
                        continue
                    elif p not in put_list:
                        pass_err = -2
                        continue
                    else:
                        to_put = p
                    break
            to_check: Segment | None = None
            if isinstance(follower.parent, Segment):
                to_check = follower.parent
            follower.remove()
            yield from follower.putOn(to_put)
            if to_check is not None:
                to_check.object.checkRemoveBuilderAndPig()
            break
        return 1
        yield {}
class GiftTake2(Gift):
    name = "再来一张"
    id = 4
    def use(self, user: 'Player') -> TAsync[int]:
        if len(user.board.deck) == 0:
            return -1
        tile = user.board.drawTileCanPut()
        if tile is None:
            user.board.addLog(id="take2NoTile")
        else:
            user.handTiles.append(tile)
        return 1
        yield {}

from .carcassonne_player import Player

if __name__ == "__main__":
    b = Board({0: "a", 1: "abcd", 2: "abcd", 3: "abcde", 4: "ab", 5: "abcde", 6: "abcdefgh", 7: "c", 12: "ab", 13: "abcd"}, ["任意哈斯塔", "哈斯塔网络整体意识", "当且仅当哈斯塔", "到底几个哈斯塔", "普通的哈斯塔", "不是哈斯塔"])
    d = {
            "name": "follower",
            "distribute": True,
            "num": 7,
            "image": [0, 0, 16, 16]
        }
    b.players[0].tokens.pop(0)
    yshift = 0
    picnames = sorted(set(s.serialNumber[1] for s in b.deck + b.riverDeck))
    for pic in picnames:
        ss = sorted(set(s.serialNumber[1:] for s in b.deck + b.riverDeck if s.picname == pic))
        for i, s2 in enumerate(ss):
            t = b.tiles[i % 5, i // 5 + yshift] = [s for s in b.deck + b.riverDeck if s.picname == pic and s.serialNumber[1:] == s2][0]
            # t.turn(Dir.LEFT)
            # for seg in t.segments:
            #     b.players[0].tokens.append(BaseFollower(b.players[0], d, open_img("token0").crop((0, 0, 16, 16))))
            #     for _ in b.players[0].tokens[-1].putOn(seg):
            #         pass
            # for feature in t.features:
            #     if isinstance(feature, BaseCloister):
            #         b.players[0].tokens.append(BaseFollower(b.players[0], d, open_img("token0").crop((0, 0, 16, 16))))
            #         for _ in b.players[0].tokens[-1].putOn(feature):
            #             pass
            #     if isinstance(feature, Tower):
            #         b.players[1].tokens.append(BaseFollower(b.players[1], d, open_img("token0").crop((0, 0, 16, 16))))
            #         for _ in b.players[1].tokens[-1].putOn(feature):
            #             pass
            #         feature.height = random.randint(0, 9)
        yshift += (len(ss) + 4) // 5
    b.dragonMoved.extend([b.tiles[0, 0], b.tiles[1, 0], b.tiles[2, 0], b.tiles[2, 1]])
    b.setImageArgs(debug=True)
    b.image().show()
