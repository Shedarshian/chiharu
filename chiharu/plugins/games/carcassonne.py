from typing import Literal, Any, Generator, Type, TypeVar, Iterable, Callable
import random, itertools, more_itertools, json
from enum import Enum, auto
from abc import ABC, abstractmethod
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

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
class Dir(Enum):
    UP = 0
    RIGHT = 1
    DOWN = 2
    LEFT = 3
    def corr(self) -> tuple[int, int]:
        return ((0, -1), (1, 0), (0, 1), (-1, 0))[self.value]
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
class DragonType(Enum):
    No = auto()
    Volcano = auto()
    Dragon = auto()
    Portal = auto()
class TradeCounter(Enum):
    Wine = auto()
    Grain = auto()
    Cloth = auto()
all_extensions = {1: 'abcd', 2: 'abcd', 3: 'abcde', 4: 'ab', 5: 'abcde'}
T = TypeVar('T')
TAsync = Generator[dict[str, Any], dict[str, Any], T]

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
    def __init__(self, packs_options: dict[int, str], player_names: list[str], start_tile_pack: int=0) -> None:
        all_packs = open_pack()["packs"]
        packs: list[dict[str, Any]] = [all_packs[0]] + [all_packs[i] for i, item in sorted(packs_options.items()) if item != ""]
        self.packs_options = packs_options
        self.tiles: dict[tuple[int, int], Tile] = {}
        self.riverDeck: list[Tile] = []
        self.deck: list[Tile] = []
        self.tokens: list[Token] = []
        self.players: list[Player] = [Player(self, i, name) for i, name in enumerate(player_names)]
        self.tileimgs: dict[int, Image.Image] = {}
        self.tokenimgs: dict[int, Image.Image] = {}
        self.allTileimgs: dict[int, dict[int, Image.Image]] = {}
        for pack in packs:
            pack_id = pack["id"]
            self.tileimgs[pack_id] = open_img(str(pack_id))
            self.tokenimgs[pack_id] = open_img("token" + str(pack_id))
            self.allTileimgs[pack_id] = {}
            if pack_id == 5 and self.checkPack(5, "b"):
                self.abbeyImg = self.tileimgs[pack_id].crop((2 * 64, 2 * 64, 3 * 64, 3 * 64))
            for key, lt in pack["tiles"].items():
                if pack_id != 0 and key not in packs_options[pack_id]:
                    continue
                for t in lt:
                    img = self.tileimgs[pack_id].crop(((t["id"] % 5) * 64, (t["id"] // 5) * 64, (t["id"] % 5 + 1) * 64, (t["id"] // 5 + 1) * 64))
                    self.allTileimgs[pack_id][t["id"]] = img
                    if pack_id == 7 and key == "a":
                        self.riverDeck.extend(Tile(self, t, img, pack_id) for i in range(t["num"]))
                    else:
                        self.deck.extend(Tile(self, t, img, pack_id) for i in range(t["num"]))
            for t in pack["tokens"]:
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
        for player in self.players:
            player.allTokens = [t for t in player.tokens]
        self.allTokens = [t for t in self.tokens]
        start_id = packs[start_tile_pack]["starting_tile"]
        start_tile = [t for t in self.deck if t.packid == start_tile_pack and t.id == start_id][0]
        if start_tile_pack == 7:
            self.popTile(start_tile)
        else:
            self.popRiverTile(start_tile)
        self.tiles[0, 0] = start_tile
        self.current_player_id = 0
        self.current_turn_player_id = 0
        random.shuffle(self.deck)
        if self.checkPack(7, "a"):
            random.shuffle(self.riverDeck)
            fork = [tile for tile in self.riverDeck if tile.id == 1][0]
            self.riverDeck.remove(fork)
            self.riverDeck = [fork] + self.riverDeck
            end = [tile for tile in self.riverDeck if tile.id == 3][0]
            self.riverDeck.remove(end)
            self.riverDeck.append(end)
        self.players[0].tokens.sort(key=Token.key)
        self.token_pos: dict[Type[Token], int] = {}
        xpos = 0
        last_key: tuple[int, int] = (-1, -2)
        for t in self.players[0].tokens:
            if t.key() != last_key:
                self.token_pos[type(t)] = xpos
                last_key = t.key()
                if len([1 for tk in self.players[0].tokens if tk.key() == last_key]) >= 3:
                    xpos += t.image().size[0] + 24 + 4
                else:
                    xpos += t.image().size[0] + 4
        self.token_length = xpos
        self.dragonMoved: list[Tile] = []
        self.font_name = ImageFont.truetype("msyhbd.ttc", 16)
        self.font_score = ImageFont.truetype("msyhbd.ttc", 24)
        self.state: State = State.End
        self.stateGen = self.process()
        self.log: list[dict[str, Any]] = []
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
    @property
    def dragon(self) -> 'Dragon':
        return more_itertools.only(t for t in self.allTokens if isinstance(t, Dragon)) # type: ignore
    @property
    def fairy(self) -> 'Fairy':
        return more_itertools.only(t for t in self.allTokens if isinstance(t, Fairy)) # type: ignore

    def popTile(self, tile: 'Tile'):
        self.deck.remove(tile)
    def popRiverTile(self, tile: 'Tile'):
        self.riverDeck.remove(tile)
    def drawTile(self):
        tile = self.deck[0]
        self.popTile(tile)
        return tile
    def drawRiverTile(self):
        tile = self.riverDeck[0]
        self.popRiverTile(tile)
        return tile
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
                max_token: int = 0
                max_players: list[Player] = []
                for player in self.players:
                    if player.tradeCounter[i] > max_token:
                        max_token = player.tradeCounter[i]
                        max_players = [player]
                    elif player.tradeCounter[i] == max_token:
                        max_players.append(player)
                for player in max_players:
                    player.addScoreFinal(10)
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
    def checkTileCanPut(self, tile: 'Tile'):
        if self.checkPack(3, "b") and self.dragon.tile is None and tile.dragon == DragonType.Dragon:
            return False
        leftmost, rightmost = self.lrborder
        uppermost, lowermost = self.udborder
        for i in range(leftmost - 1, rightmost + 2):
            for j in range(uppermost - 1, lowermost + 2):
                for orient in Dir:
                    if self.canPutTile(tile, (i, j), orient) == 1:
                        return True
        return False
    def findTilePos(self, tile: 'Tile'):
        l = [pos for pos, t in self.tiles.items() if t is tile]
        return l[0] if len(l) != 0 else None
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

    def tileImages(self, draw_tile_seg: tuple[int, int] | list[tuple[int, int]] | None=None, /,
                   debug: bool=False,
                   draw_fairy_follower: tuple[int, int] | None=None,
                   princess: 'Object | None'=None,
                   tower_pos: tuple[int, int] | None=None):
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
                i = ord('a')
                for feature in tile.features:
                    if isinstance(feature, CanScore):
                        tpos = turn(feature.token_pos, tile.orient)
                        draw(c, tpos, i)
                    i += 1
                for seg in tile.segments:
                    if len(seg.tokens) == 0:
                        tpos = turn(seg.token_pos, tile.orient)
                        draw(c, tpos, i)
                    i += 1
                if self.checkPack(5, "e") and len(choose_follower2) == 1:
                    for tpos in ((0, 0), (64, 0), (0, 64), (64, 64)):
                        draw(c, tpos, i)
                        i += 1
        if draw_fairy_follower is not None and draw_fairy_follower in self.tiles and self.checkPack(3, 'c'):
            tile = self.tiles[draw_fairy_follower]
            i = ord('a')
            for follower in tile.iterAllTokens():
                if isinstance(follower, Follower) and follower.parent is self.current_turn_player and self.fairy.canMove(follower):
                    draw(c, tile.findTokenDrawPos(follower), i)
                    i += 1
        if princess is not None:
            i = ord('a')
            for follower in princess.iterTokens():
                if isinstance(follower, Follower) and isinstance(follower.parent, Segment):
                    draw(c, follower.parent.tile.findTokenDrawPos(follower), i)
                    i += 1
        if tower_pos is not None:
            tower = [feature for feature in self.tiles[tower_pos].features if isinstance(feature, Tower)][0]
            followers = [token for token in self.tiles[tower_pos].iterAllTokens() if isinstance(token, Follower)] + [token for dr in Dir for i in range(tower.height) if (tower_pos[0] + dr.corr()[0] * (i + 1), tower_pos[1] + dr.corr()[1] * (i + 1)) in self.tiles for token in self.tiles[tower_pos[0] + dr.corr()[0] * (i + 1), tower_pos[1] + dr.corr()[1] * (i + 1)].iterAllTokens() if isinstance(token, Follower)]
            i = ord('a')
            for follower in followers:
                if isinstance(follower.parent, Segment):
                    draw(c, follower.parent.tile.findTokenDrawPos(follower), i)
                    i += 1
        # token
        def checkFairy(token: Token, p1: tuple[int, int], next: int):
            tf = self.fairy.image()
            self.fairy.drawpos = p1
            self.fairy.drawpos = self.fairy.drawpos[0] + next * 4, self.fairy.drawpos[1] + next * 4 + 8
            img.alpha_composite(t, posshift(i, j, self.fairy.drawpos, (-tf.size[0] // 2, -tf.size[1] // 2)))
        for (i, j), tile in self.tiles.items():
            for seg in tile.segments:
                next = 0
                for token in seg.tokens:
                    t = token.image()
                    if isinstance(token, Barn):
                        img.alpha_composite(t, posshift(i, j, (64, 64), (-t.size[0] // 2, -t.size[1] // 2)))
                    else:
                        img.alpha_composite(t, posshift(i, j, turn(seg.token_pos, tile.orient), (-t.size[0] // 2, -t.size[1] // 2), (next * 4, next * 4)))
                        next += 1
                        if self.checkPack(3, "c") and self.fairy.follower is token:
                            checkFairy(token, turn(seg.token_pos, tile.orient), next)
            next = 0
            for token in tile.tokens:
                t = token.image()
                img.alpha_composite(t, posshift(i, j, turn(tile.token_pos, tile.orient), (-t.size[0] // 2, -t.size[1] // 2), (next * 4, next * 4)))
                next += 1
                if self.checkPack(3, "c") and self.fairy.follower is token:
                    checkFairy(token, turn(tile.token_pos, tile.orient), next)
            for feature in tile.features:
                next = 0
                for token in feature.tokens:
                    t = token.image()
                    img.alpha_composite(t, posshift(i, j, turn(feature.token_pos, tile.orient), (-t.size[0] // 2, -t.size[1] // 2), (next * 4, next * 4)))
                    next += 1
                    if self.checkPack(3, "c") and self.fairy.follower is token:
                        checkFairy(token, turn(feature.token_pos, tile.orient), next)
        # tiles dragon has moved
        for tile in self.dragonMoved:
            p = self.findTilePos(tile)
            if p is not None:
                tileimg = img.crop(pos(*p) + pos(*p, (64, 64)))
                enhancer = ImageEnhance.Brightness(tileimg)
                img.paste(enhancer.enhance(0.7), pos(*p))
        # remain tiles
        dr.text((0, 0), str(len(self.deck)), "black", self.font_name, "lt")
        return img
    def playerImage(self, no_final_score: bool=False):
        imgs = [p.image(no_final_score=no_final_score) for p in self.players]
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
        if remove_zero:
            height: int = 0
            for packid, dct in self.allTileimgs.items():
                x2: int = 0
                for tileid, timg in dct.items():
                    num = sum(1 for tile in self.deck if tile.packid == packid and tile.id == tileid)
                    if num != 0:
                        x2 += 1
                height += (x2 - 1) // 5 + 1
        else:
            height = sum((len(dct) - 1) // 5 + 1 for packid, dct in self.allTileimgs.items())
        img = Image.new("RGBA", pos(5, height), "LightCyan")
        dr = ImageDraw.Draw(img)
        y: int = 0
        for packid, dct in self.allTileimgs.items():
            x: int = 0
            for tileid, timg in dct.items():
                num = sum(1 for tile in self.deck if tile.packid == packid and tile.id == tileid)
                if num != 0 or not remove_zero:
                    img.paste(timg, pos(x % 5, y + x // 5))
                    dr.text(pos(x % 5, y + x // 5, (32, 65)), str(num), "black", self.font_name, "mt")
                    x += 1
            y += (x - 1) // 5 + 1
        return img

    def image(self, /, draw_tile_seg: tuple[int, int] | list[tuple[int, int]] | None=None,
              debug: bool=False, no_final_score: bool=False,
              draw_fairy_follower: tuple[int, int] | None=None,
              princess: 'Object | None'=None,
              tower_pos: tuple[int, int] | None=None):
        player_img = self.playerImage(no_final_score=no_final_score)
        handtile_img = self.handTileImage()
        tile_img = self.tileImages(draw_tile_seg, debug=debug, draw_fairy_follower=draw_fairy_follower, princess=princess, tower_pos=tower_pos)
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
    def saveImg(self, /, draw_tile_seg: tuple[int, int] | list[tuple[int, int]] | None=None,
                debug: bool=False, no_final_score: bool=False,
                draw_fairy_follower: tuple[int, int] | None=None,
                princess: 'Object | None'=None,
                tower_pos: tuple[int, int] | None=None):
        from .. import config
        name = 'ccs' + str(random.randint(0, 9) + self.current_player_id * 10) + '.png'
        self.image(draw_tile_seg, debug=debug, no_final_score=no_final_score, draw_fairy_follower=draw_fairy_follower, princess=princess, tower_pos=tower_pos).save(config.img(name))
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
            _, isAbbey, pos = yield from player.turnAskAbbey(True, True)
            if isAbbey:
                assert player.handTile is not None
                yield from player.turnScoring(player.handTile, pos)
                player.handTile = None
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
        yield from self.endGameAskAbbey()
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
    @abstractmethod
    def iterTokens(self) -> 'Iterable[Token]':
        pass
    @abstractmethod
    def checkScore(self, players: 'list[Player]', mid_game: bool, putBarn: bool) -> 'list[tuple[Player, int]]':
        pass
    def removeAllFollowers(self, criteria: 'Callable[[Token], bool] | None'=None):
        if criteria is None:
            criteria = lambda token: isinstance(token.player, Player) and not isinstance(token, Barn)
        to_remove: list[Token] = [token for token in self.iterTokens() if criteria(token)]
        for token in to_remove:
            token.putBackToHand()
    def checkPlayerAndScore(self, mid_game: bool, putBarn: bool=True) -> 'list[tuple[Player, int]]':
        strengths: list[int] = [0 for i in range(len(self.board.players))]
        fairy_player: Player | None = None
        for token in self.iterTokens():
            if isinstance(token, Follower) and isinstance(token.player, Player):
                strengths[token.player.id] += token.strength
            if self.board.checkPack(3, "c") and self.board.fairy.follower is token and isinstance(token.player, Player):
                fairy_player = token.player
        max_strength: tuple[list[int], int] = ([], 0)
        for i, strength in enumerate(strengths):
            if strength == max_strength[1]:
                max_strength[0].append(i)
            elif strength > max_strength[1]:
                max_strength = [i], strength
        if max_strength[1] == 0:
            return []
        players = self.checkScore([self.board.players[i] for i in max_strength[0]], mid_game, putBarn)
        if fairy_player is not None:
            for i, (player, score) in enumerate(players):
                if player is fairy_player:
                    players[i] = (player, score + 3)
                    break
            else:
                players.append((fairy_player, 3))
        return players
    def score(self, putBarn: bool) -> TAsync[None]:
        players = self.checkPlayerAndScore(True, putBarn=putBarn)
        for player, score in players:
            if score != 0:
                self.board.addLog(id="score", player=player, source="complete", num=score)
                yield from player.addScore(score)
        # move wagon
        if self.board.checkPack(5, "d"):
            self.board.state = State.WagonAsking
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
                        ret = yield {"id": 4, "pos": pos, "player_id": wagon.player.id, "last_err": pass_err}
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
                        if 0 <= ret["seg"] < len(tile.features):
                            seg_put: Segment | Feature = tile.features[ret["seg"]]
                        elif len(tile.features) <= ret["seg"] < len(tile.segments) + len(tile.features):
                            seg_put = tile.segments[ret["seg"] - len(tile.features)]
                        else:
                            pass_err = -3
                            continue
                        if (isinstance(seg_put, Segment) and seg_put.object.closed() or isinstance(seg_put, CanScore) and seg_put.closed()) or not wagon.canPut(seg_put):
                            pass_err = -3
                            continue
                        wagon.parent.tokens.remove(wagon)
                        yield from wagon.putOn(seg_put)
                        break
                self.board.current_player_id = self.board.current_turn_player_id
            self.board.state = State.InturnScoring
        self.removeAllFollowers()
    def scoreFinal(self):
        players = self.checkPlayerAndScore(False)
        for player, score in players:
            if score != 0:
                self.board.addLog(id="score", player=player, source="final", num=score)
                player.addScoreFinal(score)
        self.removeAllFollowers()

class Tile:
    def __init__(self, board: Board, data: dict[str, Any], img: Image.Image, packid: int, isAbbey: bool=False) -> None:
        super().__init__()
        self.id: int = data["id"]
        self.tokens: list[Token] = []
        self.packid = packid
        self.board = board
        self.isAbbey = isAbbey
        self.sides: tuple[Connectable,...] = tuple(Connectable.fromChar(s) for s in data["sides"])
        self.segments: list[Segment] = [Segment.make(s["type"])(self, s) for s in data["segments"]] # type: ignore
        for seg in self.segments:
            if isinstance(seg, FieldSegment):
                seg.makeAdjacentCity(self.segments)
        self.features: list[Feature] = [f(self, s) for s in data.get("features", []) if (f := Feature.make(s["type"])) is not None]
        self.connectTile: list[Tile | None] = [None] * 4
        self.orient: Dir = Dir.UP
        self.token_pos: tuple[int, int] = (data.get("posx", 32), data.get("posy", 32))
        fs: list[str] = [s["type"] for s in data.get("features", [])]
        self.dragon: DragonType = DragonType.Volcano if "Volcano" in fs else DragonType.Dragon if "Dragon" in fs else DragonType.Portal if "Portal" in fs else DragonType.No
        self.img = img
    def iterAllTokens(self):
        yield from (token for seg in self.segments for token in seg.tokens)
        yield from (token for feature in self.features for token in feature.tokens)
        yield from (token for token in self.tokens)
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
    def closeSideAbbey(self, dir: Dir):
        if (s1 := self.sidesToSegment(dir)) is not None:
            s1.closeAbbey(dir)
        if (s1 := self.sidesToSegmentF(dir, False)) is not None:
            s1.closeAbbeyF(dir, False)
        if (s1 := self.sidesToSegmentF(dir, True)) is not None:
            s1.closeAbbeyF(dir, True)
    def getSideSeg(self, dir: Dir):
        segs: list[Segment] = []
        if (s1 := self.sidesToSegment(dir)) is not None:
            segs.append(s1)
        if (s1 := self.sidesToSegmentF(dir, False)) is not None:
            segs.append(s1)
        if (s1 := self.sidesToSegmentF(dir, True)) is not None:
            segs.append(s1)
        return segs
    def getBarnSeg(self):
        seg = more_itertools.only(s for s in self.segments if s.inSideF(Dir.RIGHT, False) and s.inSideF(Dir.DOWN, True))
        return seg
    def findTokenDrawPos(self, token: 'Token'):
        for seg in self.segments:
            if token in seg.tokens:
                id = seg.tokens.index(token)
                return seg.token_pos[0] + 4 * id, seg.token_pos[1] + 4 * id
        for feature in self.features:
            if token in feature.tokens:
                id = feature.tokens.index(token)
                return feature.token_pos[0] + 4 * id, feature.token_pos[1] + 4 * id
        if token in self.tokens:
            id = self.tokens.index(token)
            return self.token_pos[0] + 4 * id, self.token_pos[1] + 4 * id
        return self.token_pos

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

class Segment:
    def __init__(self, typ: Connectable, tile: Tile, data: dict[str, Any]) -> None:
        self.type = typ
        self.tokens: list[Token] = []
        self.tile = tile
        self.features: list[Feature] = [f(self, s) for s in data.get("features", []) if (f := Feature.make(s["type"])) is not None]
        self.object = Object(self)
        self.token_pos: tuple[int, int] = (data.get("posx", 32), data.get("posy", 32))
        self.isCathedral: bool = False
        self.isInn: bool = False
        self.tradeCounter: TradeCounter | None = None
        self.princess: bool = False
        self.pigherd: bool = False
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
    def turn(self, dir: Dir):
        self.side = {d + dir: value for d, value in self.side.items()}
    def inSide(self, dir: Dir):
        return dir in self.side
    def combine(self, other: 'NonFieldSegment', dir: Dir):
        other.object = self.object.eat(other.object)
        self.side[dir] = other
        other.side[-dir] = self
    def closeAbbey(self, dir: Dir):
        self.side[dir] = self
    def closed(self):
        return all(value is not None for value in self.side.values())
class CitySegment(NonFieldSegment):
    def __init__(self, tile: Tile, data: dict[str, Any]) -> None:
        super().__init__(Connectable.City, tile, data)
        self.pennant: int = data.get("pennant", 0)
        for feature in data.get("features", []):
            if feature["type"] == "Cathedral":
                self.isCathedral = True
            if feature["type"] == "TradeCounter":
                self.tradeCounter = TradeCounter[feature["counter"]]
            if feature["type"] == "Princess":
                self.princess = True
    @property
    def color(self):
        return "brown"
class RoadSegment(NonFieldSegment):
    def __init__(self, tile: Tile, data: dict[str, Any]) -> None:
        super().__init__(Connectable.Road, tile, data)
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
        for feature in data.get("features", []):
            if feature["type"] == "Pigherd":
                self.pigherd = True
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
    def closeAbbeyF(self, dir: Dir, up: bool):
        self.side[dir, up] = self
    def closed(self):
        return all(value is not None for value in self.side.values())
    @property
    def color(self):
        return "green"

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
        return self.type != Connectable.Field and all(seg.closed() for seg in self.segments)
    def iterTokens(self) -> 'Iterable[Token]':
        for seg in self.segments:
            yield from seg.tokens
        yield from self.tokens
    def checkTile(self):
        tiles: list[Tile] = []
        for seg in self.segments:
            if seg.tile not in tiles:
                tiles.append(seg.tile)
        return len(tiles)
    def checkPennant(self):
        return sum(seg.pennant for seg in self.segments if isinstance(seg, CitySegment))
    def checkBarnAndScore(self) -> 'list[tuple[Player, int]]':
        ps: list[Player] = []
        for seg in self.segments:
            for token in seg.tokens:
                if isinstance(token, Barn) and isinstance(token.player, Player):
                    ps.append(token.player)
                complete_city: list[Object] = []
        for seg in self.segments:
            if isinstance(seg, FieldSegment):
                for segc in seg.adjacentCity:
                    if segc.object not in complete_city and segc.object.closed():
                        complete_city.append(segc.object)
        base = 4
        players = [(p, base * len(complete_city)) for p in ps]
        return players
    def checkBarn(self):
        return self.board.checkPack(5, 'e') and self.type == Connectable.Field and any(isinstance(token, Barn) for seg in self.segments for token in seg.tokens)
    def checkScore(self, players: 'list[Player]', mid_game: bool, putBarn: bool) -> 'list[tuple[Player, int]]':
        match self.type:
            case Connectable.City:
                base = 2 if mid_game else 1
                if self.board.checkPack(1, "d") and any(seg.isCathedral for seg in self.segments):
                    if mid_game:
                        base += 1
                    else:
                        base = 0
                score = base * (self.checkTile() + self.checkPennant())
                new_players: list[tuple[Player, int]] = [(player, score) for player in players]
            case Connectable.Road:
                base = 1
                if self.board.checkPack(1, "c") and any(seg.isInn for seg in self.segments):
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
                            if segc.object not in complete_city and segc.object.closed():
                                complete_city.append(segc.object)
                if self.board.checkPack(2, "c"):
                    new_players = []
                    for player in players:
                        base = 3 if putBarn else 1
                        if any(isinstance(token, Pig) and token.player is player for seg in self.segments for token in seg.tokens):
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
            if not any(token.player is t.player for seg in self.segments for token in seg.tokens):
                self.board.addLog(id="putbackBuilder", builder=t)
                t.putBackToHand()
    def score(self, putBarn: bool) -> TAsync[None]:
        if self.type == Connectable.Field:
            if self.checkBarn():
                yield from super().score(putBarn)
            else:
                return
        yield from super().score(putBarn)
    def scoreFinal(self):
        super().scoreFinal()
        # barn
        if any(isinstance(token, Barn) for seg in self.segments for token in seg.tokens):
            players = self.checkBarnAndScore()
            for player, score in players:
                if score != 0:
                    player.addScoreFinal(score)
            self.removeAllFollowers(lambda token: isinstance(token, Barn))

class Feature:
    def __init__(self, parent: Tile | Segment, data: dict[str, Any]) -> None:
        self.parent = parent
        self.tokens: list[Token] = []
        self.token_pos: tuple[int, int] = (data.get("posx", 32), data.get("posy", 32))
    @classmethod
    def make(cls, typ: str) -> Type["Feature"] | None:
        return {"cloister": Cloister, "garden": Garden, "shrine": Shrine}.get(typ.lower(), None)
class BaseCloister(Feature, CanScore):
    def __init__(self, parent: Tile | Segment, data: dict[str, Any]) -> None:
        Feature.__init__(self, parent, data)
        CanScore.__init__(self, parent.board if isinstance(parent, Tile) else parent.tile.board)
    def iterTokens(self) -> 'Iterable[Token]':
        yield from self.tokens
    def closed(self) -> bool:
        assert isinstance(self.parent, Tile)
        pos = more_itertools.only(key for key, value in self.parent.board.tiles.items() if value is self.parent)
        if pos is None:
            return False
        return all((pos[0] + i, pos[1] + j) in self.parent.board.tiles for i in (-1, 0, 1) for j in (-1, 0, 1))
    def checkScore(self, players: 'list[Player]', mid_game: bool, putBarn: bool) -> 'list[tuple[Player, int]]':
        assert isinstance(self.parent, Tile)
        pos = self.parent.board.findTilePos(self.parent)
        score = sum(1 if (pos[0] + i, pos[1] + j) in self.parent.board.tiles else 0 for i in (-1, 0, 1) for j in (-1, 0, 1))
        return [(player, score) for player in players]
class Cloister(BaseCloister):
    pass
class Garden(BaseCloister):
    pass
class Shrine(BaseCloister):
    pass
class Tower(Feature):
    def __init__(self, parent: Tile | Segment, data: dict[str, Any]) -> None:
        super().__init__(parent, data)
        self.height: int = 0

class Token(ABC):
    def __init__(self, parent: 'Player | Board', data: dict[str, Any], img: Image.Image) -> None:
        self.parent: Tile | Segment | Object | Feature | Player | Board = parent
        self.player = parent
        self.board = parent if isinstance(parent, Board) else parent.board
        self.img = img
        self.canEatByDragon: bool = True
    def checkPack(self, packid: int, thingid: str):
        if isinstance(self.player, Player):
            return self.player.board.checkPack(packid, thingid)
        return self.player.checkPack(packid, thingid)
    @classmethod
    def make(cls, typ: str) -> Type['Token']:
        return {"follower": BaseFollower, "big follower": BigFollower, "大跟随者": BigFollower, "builder": Builder, "建筑师": Builder, "pig": Pig, "猪": Pig, "mayor": Mayor, "市长": Mayor, "wagon": Wagon, "马车": Wagon, "barn": Barn, "谷仓": Barn, "dragon": Dragon, "龙": Dragon, "fairy": Fairy, "仙子": Fairy}[typ.lower()]
    def canPut(self, seg: Segment | Feature | Tile):
        if isinstance(seg, Tile):
            return False
        if isinstance(seg, Segment):
            if any(isinstance(token, Dragon) for token in seg.tile.tokens):
                return False
            return all(len(s.tokens) == 0 for s in seg.object.segments)
        return len(seg.tokens) == 0 and not isinstance(seg, Garden)
    def putOn(self, seg: Segment | Feature | Tile) -> TAsync[None]:
        seg.tokens.append(self)
        self.parent = seg
        return
        yield {}
    def image(self):
        if isinstance(self.player, Board):
            return self.img.copy()
        if isinstance(self, (BaseFollower, BigFollower)) and isinstance(self.parent, FieldSegment):
            mask = open_img("token0").crop((16, 0, 32, 16))
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
    @abstractmethod
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
    def canPut(self, seg: Segment | Feature | Tile):
        if isinstance(seg, Segment):
            if any(isinstance(token, Dragon) for token in seg.tile.tokens):
                return False
            return seg.type in (Connectable.City, Connectable.Road) and any(t.player is self.player for s in seg.object.segments for t in s.tokens if isinstance(t, Follower))
        return False
    def key(self) -> tuple[int, int]:
        return (2, 0)
class Pig(Figure):
    def canPut(self, seg: Segment | Feature | Tile):
        if isinstance(seg, FieldSegment):
            if any(isinstance(token, Dragon) for token in seg.tile.tokens):
                return False
            return any(t.player is self.player for s in seg.object.segments for t in s.tokens if isinstance(t, Follower))
        return False
    def key(self) -> tuple[int, int]:
        return (2, 1)
class Mayor(Follower):
    def canPut(self, seg: Segment | Feature | Tile):
        return isinstance(seg, CitySegment) and super().canPut(seg)
    @property
    def strength(self) -> int:
        if not isinstance(self.parent, Segment):
            return 0
        return self.parent.object.checkPennant()
    def key(self) -> tuple[int, int]:
        return (5, 0)
class Wagon(Follower):
    def canPut(self, seg: Segment | Feature | Tile):
        return isinstance(seg, (CitySegment, RoadSegment, Cloister, Shrine)) and super().canPut(seg)
    def key(self) -> tuple[int, int]:
        return (3, 1)
class Barn(Figure):
    def __init__(self, parent: 'Player | Board', data: dict[str, Any], img: Image) -> None:
        super().__init__(parent, data, img)
        self.canEatByDragon = False
    def canPut(self, seg: Segment | Feature | Tile):
        return isinstance(seg, Tile) and (pos := self.board.findTilePos(seg)) and \
            all((pos[0] + i, pos[1] + j) in self.board.tiles and not self.board.tiles[pos[0] + i, pos[1] + j].isAbbey for i in (0, 1) for j in (0, 1)) and \
            seg.getBarnSeg() is not None
    def putOn(self, seg: Segment | Feature | Tile) -> TAsync[None]:
        if isinstance(seg, Tile):
            if s := seg.getBarnSeg():
                s.tokens.append(self)
                self.parent = s
                yield from s.object.score(putBarn=True)
    def key(self) -> tuple[int, int]:
        return (5, 2)
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
    def key(self) -> tuple[int, int]:
        return (3, 0)
class Fairy(Figure):
    def __init__(self, parent: 'Player | Board', data: dict[str, Any], img: Image) -> None:
        super().__init__(parent, data, img)
        self.follower: Follower | None = None
        self.tile: Tile | None = None
        self.drawpos: tuple[int, int] = 32, 32
        self.canEatByDragon = False
    def canMove(self, follower: Follower):
        return True
    def moveTo(self, follower: Follower, tile: Tile):
        self.tile = tile
        self.follower = follower
    def key(self) -> tuple[int, int]:
        return (3, 1)

AbbeyData = {"id": -1, "sides": "FFFF", "segments": [], "features": [{"type": "Cloister", "posx": 32, "posy": 36}]}
class State(Enum):
    End = auto()
    PuttingRiver = auto()
    AbbeyAsking = auto()
    PuttingTile = auto()
    PrincessAsking = auto()
    PuttingFollower = auto()
    CaptureTower = auto()
    ExchangingPrisoner = auto()
    ChoosingFairy = auto()
    MovingDragon = auto()
    InturnScoring = auto()
    WagonAsking = auto()
    FinalAbbeyAsking = auto()
    Error = auto()
class Player:
    def __init__(self, board: Board, id: int, name: str) -> None:
        self.board = board
        self.id = id
        self.name = name[:20]
        self.tokens: list[Token] = []
        self.allTokens: list[Token] = []
        self.score: int = 0
        self.handTile: Tile | None = None
        self.tradeCounter = [0, 0, 0]
        self.hasAbbey = self.board.checkPack(5, 'b')
        self.towerPieces: int = 0
        self.prisoners: list[Follower] = []
    @property
    def tokenColor(self):
        return ["green", "yellow", "gray", "purple", "blue", "black"][self.id]
    @property
    def show_name(self):
        show_name = self.name
        if self.board.font_name.getlength(self.name) > 80:
            while self.board.font_name.getlength(show_name + "...") > 80:
                show_name = show_name[:-1]
            show_name += "..."
        return show_name
    def addScore(self, score: int, canMessage: bool=True) -> TAsync[None]:
        self.score += score
        return
        yield {}
    def addScoreFinal(self, score: int):
        self.score += score
    def checkMeepleScoreCurrent(self):
        all_objects: list[Object | BaseCloister] = []
        all_barns: list[Object] = []
        score: int = 0
        for token in self.allTokens:
            if isinstance(token, Barn) and isinstance(token.parent, Segment):
                all_barns.append(token.parent.object)
            elif isinstance(token.parent, Segment) and token.parent.object not in all_objects:
                all_objects.append(token.parent.object)
            elif isinstance(token.parent, BaseCloister) and token.parent not in all_objects:
                all_objects.append(token.parent)
        for obj in all_objects:
            for player, scorec in obj.checkPlayerAndScore(False):
                if self is player:
                    score += scorec
        for barn in all_barns:
            for player, scorec in barn.checkBarnAndScore():
                if self is player:
                    score += scorec
        return self.score + score

    def turnDrawRiver(self, isBegin: bool) -> TAsync[bool]:
        self.handTile = self.board.drawRiverTile()
        return isBegin
        yield {}
    def turnAskAbbey(self, isBegin: bool, endGame: bool) -> TAsync[tuple[bool, bool, tuple[int, int]]]:
        isAbbey: bool = False
        tile: Tile | None = None
        pos: tuple[int, int] = (-1, -1)
        if self.hasAbbey and self.board.checkHole():
            pass_err: Literal[0, -1] = 0
            self.board.state = State.FinalAbbeyAsking if endGame else State.AbbeyAsking
            while 1:
                ret = yield {"id": 5, "last_err": pass_err, "begin": isBegin, "endGame": endGame}
                isBegin = False
                if not ret.get("put"):
                    break
                isAbbey = True
                self.hasAbbey = False
                pos = ret["pos"]
                if pos in self.board.tiles or any(pos + dr not in self.board.tiles for dr in Dir):
                    pass_err = -1
                    continue
                tile = Tile(self.board, AbbeyData, self.board.abbeyImg, 5, True)
                self.handTile = tile
                self.board.tiles[pos] = tile
                for dr in Dir:
                    self.board.tiles[pos + dr].closeSideAbbey(-dr)
                break
        return isBegin, isAbbey, pos
    def turnDrawTile(self, isBegin: bool) -> TAsync[bool]:
        self.handTile = self.board.drawTile()
        checked: int = 0
        while self.handTile is not None and not self.board.checkTileCanPut(self.handTile):
            self.board.addLog(id="redraw", tile=self.handTile)
            checked += 1
            self.board.deck.append(self.handTile)
            self.handTile = self.board.drawTile()
            if checked >= len(self.board.deck):
                raise CantPutError
        if checked >= 1:
            random.shuffle(self.board.deck)
        return isBegin
        yield {}
    def turnPutTile(self, turn: int, isBegin: bool) -> TAsync[tuple[bool, tuple[int, int], bool]]:
        self.board.state = State.PuttingTile
        pass_err: Literal[0, -1, -2, -3, -4, -5] = 0
        prisonered: bool = False
        while 1:
            ret = yield {"id": 0, "second_turn": turn == 1, "last_err": pass_err, "begin": isBegin}
            isBegin = False
            if turn == 0 and not prisonered and ret.get("special") == "prisoner":
                if self.score < 3:
                    pass_err = -5
                    continue
                player_id: int = ret["player_id"]
                if player_id < 0 or player_id >= len(self.board.players):
                    pass_err = -4
                    continue
                player: Player = self.board.players[player_id]
                try:
                    tokens = [token for token in player.prisoners if isinstance(token, Token.make(ret.get("which", "follower")))]
                except KeyError:
                    pass_err = -4
                    continue
                if len(tokens) == 0:
                    pass_err = -4
                    continue
                token = tokens[0]
                yield from self.addScore(-3, False)
                player.prisoners.remove(token)
                self.tokens.append(token)
                prisonered = True
                continue
            pos: tuple[int, int] = ret["pos"]
            orient: Dir = ret["orient"]
            tile = self.handTile
            assert tile is not None
            if pos in self.board.tiles:
                pass_err = -1
                continue
            if all(pos + dr not in self.board.tiles for dr in Dir):
                pass_err = -3
                continue
            for dr in Dir:
                side = pos + dr
                if side in self.board.tiles:
                    ret0 = self.board.tiles[side].checkConnect(tile, -dr, orient)
                    if ret0 < 0:
                        pass_err = ret0
                        if pass_err < 0:
                            continue
            # TODO check river
            break
        tile.turn(orient)
        self.board.tiles[pos] = tile
        for dr in Dir:
            if pos + dr in self.board.tiles:
                self.board.tiles[pos + dr].addConnect(tile, -dr)
        princessed: bool = False
        if self.board.checkPack(3, "e") and (seg := more_itertools.only(seg for seg in tile.segments if seg.princess)):
            followers = [token for token in seg.object.iterTokens() if isinstance(token, Follower) and isinstance(token.parent, Segment)]
            if len(followers) != 0:
                pass_err = 0
                self.board.state = State.PrincessAsking
                while 1:
                    ret = yield {"id": 8, "object": seg.object}
                    id: int = ret["id"]
                    if id >= 0 and id < len(followers):
                        followers[id].putBackToHand()
                        seg.object.checkRemoveBuilderAndPig()
                        princessed = True
                        break
                    elif id != -1:
                        pass_err = -1
                        continue
                    break
        return isBegin, pos, princessed
    def turnCheckBuilder(self) -> TAsync[bool]:
        assert self.handTile is not None
        if not self.board.checkPack(2, 'b'):
            return False
        for seg in self.handTile.segments:
            for seg2 in seg.object.segments:
                for token in seg2.tokens:
                    if token.player is self and isinstance(token, Builder):
                        return True
        return False
        yield {}
    def turnPutFollower(self, tile: Tile, pos: tuple[int, int]) -> TAsync[bool]:
        pass_err: Literal[0, -1, -2, -3, -4, -5, -6, -7] = 0
        if_portal: bool = False
        pos_put = pos
        tile_put = tile
        while 1:
            self.board.state = State.PuttingFollower
            ret = yield {"id": 2, "last_err": pass_err, "last_put": pos_put, "if_portal": if_portal}
            if self.board.checkPack(3, "c") and ret.get("special") == "fairy":
                pos_fairy: tuple[int, int] = ret["pos"]
                if pos_fairy not in self.board.tiles:
                    pass_err = -3
                    continue
                tile_fairy = self.board.tiles[pos_fairy]
                followers = [token for token in tile_fairy.iterAllTokens() if isinstance(token, Follower) and token.player is self and self.board.fairy.canMove(token)]
                if len(followers) == 0:
                    pass_err = -3
                    continue
                if len(followers) == 1:
                    follower = followers[0]
                else:
                    pass_err = 0
                    while 1:
                        self.board.state = State.ChoosingFairy
                        ret = yield {"id": 7, "last_err": pass_err, "last_put": pos_fairy}
                        if ret["id"] < 0 or ret["id"] >= len(followers):
                            pass_err = -1
                            continue
                        follower = followers[ret["id"]]
                self.board.fairy.moveTo(follower, tile_fairy)
                break
            if self.board.checkPack(3, "d") and not if_portal and ret.get("special") == "portal":
                pos_portal: tuple[int, int] = ret["pos"]
                if pos_portal not in self.board.tiles or tile.dragon != DragonType.Portal:
                    pass_err = -4
                    continue
                pos_put = pos_portal
                tile_put = self.board.tiles[pos_portal]
                if_portal = True
                continue
            if if_portal and ret["id"] == -1:
                pos_put = pos
                tile_put = tile
                if_portal = False
                continue
            if self.board.checkPack(4, "b") and ret.get("special") == "tower":
                pos_tower: tuple[int, int] = ret["pos"]
                if pos_tower not in self.board.tiles:
                    pass_err = -5
                    continue
                tile_tower = self.board.tiles[pos_tower]
                tower = more_itertools.only(feature for feature in tile_tower.features if isinstance(feature, Tower))
                if tower is None:
                    pass_err = -5
                    continue
                if len(tower.tokens) != 0:
                    pass_err = -6
                    continue
                if not ret.get("which"):
                    if self.towerPieces == 0:
                        pass_err = -7
                        continue
                    yield from self.turnCaptureTower(tower, pos_tower)
                    break
                try:
                    tokens = [token for token in self.tokens if isinstance(token, Token.make(ret["which"]))]
                except KeyError:
                    pass_err = -1
                    continue
                if len(tokens) == 0:
                    pass_err = -1
                    continue
                token = tokens[0]
                if not isinstance(token, (Follower, BigFollower)):
                    pass_err = -2
                    continue
                self.tokens.remove(token)
                yield from token.putOn(tower)
                break
            if ret["id"] == -1:
                break
            if 0 <= ret["id"] < len(tile_put.features):
                seg_put: Segment | Feature | Tile = tile_put.features[ret["id"]]
            elif len(tile_put.features) <= ret["id"] < (ll := len(tile_put.segments) + len(tile_put.features)):
                seg_put = tile_put.segments[ret["id"] - len(tile_put.features)]
            elif self.board.checkPack(5, "e") and not tile_put.isAbbey and ll <= ret["id"] < ll + 4 and (pos := self.board.findTilePos(tile_put)):
                # for barn
                offset = [(-1, -1), (0, -1), (-1, 0), (0, 0)][ret["id"] - ll]
                if (tile2 := self.board.tiles.get((pos_put[0] + offset[0], pos_put[1] + offset[1]))) is not None:
                    seg_put = tile2
                else:
                    pass_err = -2
                    continue
            else:
                pass_err = -2
                continue
            try:
                tokens = [token for token in self.tokens if isinstance(token, Token.make(ret.get("which", "follower")))]
            except KeyError:
                pass_err = -1
                continue
            if len(tokens) == 0:
                pass_err = -1
                continue
            token = tokens[0]
            if not token.canPut(seg_put) or if_portal and (isinstance(seg_put, Segment) and seg_put.object.closed() or isinstance(seg_put, CanScore) and seg_put.closed()):
                pass_err = -2
                continue
            self.tokens.remove(token)
            yield from token.putOn(seg_put)
            break
        return if_portal
    def turnCaptureTower(self, tower: Tower, pos: tuple[int, int]) -> TAsync[None]:
        followers = [token for token in self.board.tiles[pos].iterAllTokens() if isinstance(token, Follower)] + [token for dr in Dir for i in range(tower.height) if (pos[0] + dr.corr()[0] * (i + 1), pos[1] + dr.corr()[1] * (i + 1)) in self.board.tiles for token in self.board.tiles[pos[0] + dr.corr()[0] * (i + 1), pos[1] + dr.corr()[1] * (i + 1)].iterAllTokens() if isinstance(token, Follower)]
        if len(followers) == 0:
            return
        self.board.state = State.CaptureTower
        pass_err: Literal[0, -1] = 0
        while 1:
            ret = yield {"id": 9, "pos": pos, "last_err": pass_err}
            id: int = ret["id"]
            if id == -1:
                break
            if id < 0 or id >= len(followers):
                pass_err = -1
                continue
            follower = followers[id]
            if follower.player is self:
                follower.putBackToHand()
            else:
                follower.remove()
                self.prisoners.append(follower)
                yield from self.checkReturnPrisoner()
            break
    def checkReturnPrisoner(self) -> TAsync[None]:
        for player in self.board.players:
            if player is self:
                continue
            p = [[token for token in self.prisoners if token.player is player], [token for token in player.prisoners if token.player is self]]
            if len(p[0]) == 0 or len(p[1]) == 0:
                continue
            t = [p[0][0], p[1][0]]
            self.board.state = State.ExchangingPrisoner
            pass_err: Literal[0, -1] = 0
            c = [False, False]
            for i in range(2):
                if len(set(c.key() for c in p[i])) == 1:
                    c[i] = True
                    continue
                if i == 1:
                    self.board.current_player_id = player.id
                while 1:
                    ret = yield {"id": 10, "last_err": pass_err}
                    try:
                        tokens = [token for token in p[i] if isinstance(token, Token.make(ret["which"]))]
                    except KeyError:
                        pass_err = -1
                        continue
                    if len(tokens) == 0:
                        pass_err = -1
                        continue
                    t[i] = tokens[0]
                    break
                if i == 1:
                    self.board.current_player_id = self.board.current_turn_player_id
            if c[0] and c[1]:
                self.board.addLog(id="exchangePrisoner", p1=t[0], p2=t[1])
            self.prisoners.remove(t[0])
            player.tokens.append(t[0])
            player.prisoners.remove(t[1])
            self.tokens.append(t[1])
    def turnMoveDragon(self) -> TAsync[None]:
        self.board.state = State.MovingDragon
        dragon = self.board.dragon
        assert dragon.tile is not None
        pass_err: Literal[0, -1] = 0
        for i in range(6):
            pos = self.board.findTilePos(dragon.tile)
            if not any(pos + dr in self.board.tiles and dragon.canMove(self.board.tiles[pos + dr]) for dr in Dir):
                break
            while 1:
                ret = yield {"id": 6, "last_err": pass_err, "moved_num": i}
                dr: Dir = ret["direction"]
                if pos + dr not in self.board.tiles or not dragon.canMove(self.board.tiles[pos + dr]):
                    pass_err = -1
                    continue
                break
            dragon.moveTo(self.board.tiles[pos + dr])
            self.board.dragonMoved.append(dragon.tile)
            self.board.nextAskingPlayer()
        self.board.current_player_id = self.board.current_turn_player_id
        self.board.dragonMoved = []
    def turnScoring(self, tile: Tile, pos: tuple[int, int]) -> TAsync[None]:
        self.board.state = State.InturnScoring
        objects: list[Object] = []
        for seg in tile.segments:
            if seg.object.closed() and seg.object not in objects:
                objects.append(seg.object)
        if tile.isAbbey:
            for dir in Dir:
                for seg in self.board.tiles[pos + dir].getSideSeg(-dir):
                    if seg.object.closed() and seg.object not in objects:
                        objects.append(seg.object)
        for obj in objects:
            tc: list[int] = [0, 0, 0]
            if self.board.checkPack(2, 'd') and obj.type == Connectable.City:
                for seg2 in obj.segments:
                    if seg2.tradeCounter == TradeCounter.Wine:
                        tc[0] += 1
                    elif seg2.tradeCounter == TradeCounter.Grain:
                        tc[1] += 1
                    elif seg2.tradeCounter == TradeCounter.Cloth:
                        tc[2] += 1
                if tc != [0, 0, 0]:
                    for i in range(3):
                        self.tradeCounter[i] += tc[i]
                    self.board.addLog(id="tradeCounter", tradeCounter=tc)
            yield from obj.score(putBarn=False)
        for i in (-1, 0, 1):
            for j in (-1, 0, 1):
                npos = (pos[0] + i, pos[1] + j)
                if npos in self.board.tiles:
                    for feature in self.board.tiles[npos].features:
                        if isinstance(feature, CanScore) and feature.closed():
                            yield from feature.score(False)
    def turn(self) -> TAsync[None]:
        """id0：放图块（-1：已有连接, -2：无法连接，-3：没有挨着，-4：未找到可赎回的囚犯，-5：余分不足）
        2：放跟随者（-1不放，返回-1：没有跟随者，-2：无法放置，-3：无法移动仙子，-4：无法使用传送门，-5：找不到高塔
        -6：高塔有人，-7：手里没有高塔片段），4：选马车（-1：没有图块，-2：图块过远，-3：无法放置）
        5：询问僧院板块（-1：无法放置），6：询问龙（-1：无法移动），7：询问仙子细化（-1：无法移动）
        8：询问公主（-1：未找到跟随者），9：询问高塔抓人（-1：未找到跟随者），10：询问交换俘虏（-1：未找到跟随者）"""
        isBegin: bool = True
        nextTurn: bool = False
        princessed: bool = False
        # check fairy
        if self.board.checkPack(3, "c") and self.board.fairy.follower is not None and self.board.fairy.follower.player is self:
            self.board.addLog(id="score", player=self, num=1, source="fairy")
            yield from self.addScore(1)

        for turn in range(2):
            # draw river
            if len(self.board.riverDeck) != 0:
                isBegin = yield from self.turnDrawRiver(isBegin)
                nextTurn = len(self.board.riverDeck) == 0

                # put tile
                isBegin, pos, princessed = yield from self.turnPutTile(turn, isBegin)
            else:
                # ask abbey
                isBegin, isAbbey, pos = yield from self.turnAskAbbey(isBegin, False)

                if not isAbbey:
                    # draw tile normally
                    isBegin = yield from self.turnDrawTile(isBegin)

                    # put tile
                    isBegin, pos, princessed = yield from self.turnPutTile(turn, isBegin)

                    # builder generate a second turn
                    if turn == 0:
                        nextTurn = yield from self.turnCheckBuilder()
            tile = self.handTile
            assert tile is not None
            self.handTile = None

            # check dragon
            if self.board.checkPack(3, "b") and tile.dragon == DragonType.Volcano:
                self.board.dragon.moveTo(tile)

            if_portal: bool = False
            if not princessed:
                # put a follower
                if_portal = yield from self.turnPutFollower(tile, pos)

            # move a dragon
            if self.board.checkPack(3, "b") and tile.dragon == DragonType.Dragon:
                yield from self.turnMoveDragon()

            # score
            yield from self.turnScoring(tile, pos)

            self.board.state = State.End
            if nextTurn:
                continue
            break

    def image(self, no_final_score: bool=False):
        score_str = str(self.score)
        if not no_final_score:
            score_str += " (" + str(self.checkMeepleScoreCurrent()) + ")"
        if self.board.checkPack(2, 'd') and not no_final_score:
            trade_score = 0
            for i in range(3):
                if all(self.tradeCounter[i] >= player.tradeCounter[i] for player in self.board.players):
                    trade_score += 10
            score_str = score_str[:-1] + "+" + str(trade_score) + score_str[-1]
        score_length = 120 + (45 if self.board.checkPack(2, 'd') else 0)
        length = 80 + score_length + self.board.token_length
        if self.board.checkPack(5, "b"):
            abbey_xpos = length
            length += 28
        if self.board.checkPack(2, "d"):
            trade_counter_xpos = length
            length += 120
        img = Image.new("RGBA", (length, 24))
        dr = ImageDraw.Draw(img)
        dr.text((0, 12), self.show_name, "black", self.board.font_name, "lm")
        dr.text((80 + score_length // 2, 12), score_str, "black", self.board.font_score, "mm")
        # tokens
        self.tokens.sort(key=Token.key)
        last_key: tuple[int, int] = (-1, -2)
        for token in self.tokens:
            if token.key() != last_key:
                last_key = token.key()
                timg = token.image()
                this_num = len([1 for tk in self.tokens if tk.key() == last_key])
                xbegin = self.board.token_pos[type(token)] + 80 + score_length
                if this_num >= 3:
                    img.alpha_composite(timg, (xbegin, 12 - timg.size[1] // 2))
                    dr.text((xbegin + timg.size[0], 12), "x " + str(this_num), "black", self.board.font_name, "lm")
                elif this_num == 2:
                    img.alpha_composite(timg, (xbegin, 12 - timg.size[1] // 2))
                    img.alpha_composite(timg, (xbegin + timg.size[0] + 4, 12 - timg.size[1] // 2))
                elif this_num == 1:
                    img.alpha_composite(timg, (xbegin, 12 - timg.size[1] // 2))
        # abbey
        if self.board.checkPack(5, "b"):
            if self.hasAbbey:
                dr.rectangle((abbey_xpos + 4, 4, abbey_xpos + 20, 20), "red")
        # trade counter count
        if self.board.checkPack(2, "d"):
            dr.text((trade_counter_xpos, 12), f"酒{self.tradeCounter[0]}", "black", self.board.font_name, "lm")
            dr.text((trade_counter_xpos + 40, 12), f"麦{self.tradeCounter[1]}", "black", self.board.font_name, "lm")
            dr.text((trade_counter_xpos + 80, 12), f"布{self.tradeCounter[2]}", "black", self.board.font_name, "lm")
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
    b = Board({1: "abcd", 2: "abcd", 5: "abcde"}, ["任意哈斯塔", "哈斯塔网络整体意识", "当且仅当哈斯塔", "到底几个哈斯塔", "普通的哈斯塔"])
    d = {
            "name": "follower",
            "distribute": True,
            "num": 7,
            "image": [0, 0, 16, 16]
        }
    b.players[0].tokens.pop(0)
    def _(i: int, packid: int, yshift: int):
        t = b.tiles[i % 5, i // 5 + yshift] = [s for s in b.deck if s.id == i and s.packid == packid][0]
        for seg in t.segments:
            b.players[0].tokens.append(BaseFollower(b.players[0], d, open_img("token0").crop((0, 0, 16, 16))))
            for _ in b.players[0].tokens[-1].putOn(seg):
                pass
        for feature in t.features:
            if isinstance(feature, BaseCloister):
                b.players[0].tokens.append(BaseFollower(b.players[0], d, open_img("token0").crop((0, 0, 16, 16))))
                for _ in b.players[0].tokens[-1].putOn(feature):
                    pass
    for i in range(1, 25):
        _(i - 1, 0, 0)
    for i in range(17):
        _(i, 1, 5)
    for i in range(24):
        _(i, 2, 9)
    for i in range(12):
        _(i, 5, 14)
    b.dragonMoved.extend([b.tiles[0, 0], b.tiles[1, 0], b.tiles[2, 0], b.tiles[2, 1]])
    b.image().show()
