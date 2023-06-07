from typing import Literal, Any, Generator, Type, TypeVar, Iterable, Callable, Sequence, Awaitable
import random, itertools, more_itertools, json
from enum import Enum, auto
from collections import Counter
from abc import ABC, abstractmethod
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from .ccs_tile import Dir, open_img, readTileData, readPackData, TileData, OneSideSegmentPic
from .ccs_tile import CitySegmentData, RoadSegmentData, RiverSegmentData, FieldSegmentData, FeatureSegmentData, AddableSegmentData
from .ccs_tile import AreaSegmentPic, LineSegmentPic, SegmentData
from .ccs_helper import CantPutError, NoDeckEnd, Connectable, TileAddable, Addable, Shed
from .ccs_helper import all_extensions, findAllMax, turn, dist2, State, Log, Send, Recieve

T = TypeVar('T')
TAsync = Generator[Send, Recieve, T]
TToken = TypeVar("TToken", bound="Token")

class Board:
    def __init__(self, packs_options: dict[int, str], player_names: list[str],
                 start_tile_pack: int=0, group_id: int | None = None) -> None:
        all_packs = readTileData(packs_options)
        packs: list[dict[str, Any]] = readPackData()["packs"]
        self.group_id = group_id
        self.packs_options = packs_options
        self.tiles: dict[tuple[int, int], Tile] = {}
        self.riverDeck: list[Tile] = []
        self.deck: list[Tile] = []
        self.tokens: list[Token] = []
        self.players: list[Player] = [Player(self, i, name) for i, name in enumerate(player_names)]
        self.tokenimgs: dict[int, Image.Image] = {}
        self.allTileimgs: dict[tuple[int, str, int, int], Image.Image] = {}
        self.connected: list[tuple[tuple[int, int], Dir]] = []
        self.prompts: list[str] = []
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
        if self.checkPack(5, "b"):
            self.abbeyImg = open_img("abbey")
        for player in self.players:
            player.allTokens = [t for t in player.tokens]
        self.allTokens = [t for t in self.tokens]
        start_id = None
        if start_tile_pack == 7:
            if self.checkPack(7, "d"):
                start_id = (7, "0313", 0, 0)
            if self.checkPack(7, "a"):
                if start_id is not None:
                    self.popRiverTile([t for t in self.riverDeck if t.serialNumber == (7, "1223", 0, 0)][0])
                else:
                    start_id = (7, "1223", 0, 0)
            if self.checkPack(7, "c"):
                if start_id is not None:
                    self.popRiverTile([t for t in self.riverDeck if t.serialNumber == (7, "1213", 0, 0)][0])
                else:
                    start_id = (7, "1213", 0, 0)
            if self.checkPack(7, "b"):
                if start_id is not None:
                    self.popRiverTile([t for t in self.riverDeck if t.serialNumber == (7, "1113", 0, 0)][0])
                else:
                    start_id = (7, "1113", 0, 0)
            if start_id is None:
                raise NotImplementedError
            start_tile = [t for t in self.riverDeck if t.serialNumber == start_id][0]
            self.popRiverTile(start_tile)
            if not self.checkPack(7, "d"):
                start_tile.turn(Dir.LEFT)
            self.tiles[0, 0] = start_tile
            self.connected.append(((0, 0), Dir.RIGHT))
            if self.checkPack(7, "d"):
                start_tile2 = [t for t in self.riverDeck if t.serialNumber == (7, "1323", 1, 0)][0]
                self.popRiverTile(start_tile2)
                self.tiles[1, 0] = start_tile2
                self.tiles[0, 0].addConnect(self.tiles[1, 0], Dir.RIGHT)
        else:
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
            fork = [tile for tile in self.riverDeck if tile.serialNumber == (7, "1333", 0, 0)][0]
            self.popRiverTile(fork)
            self.riverDeck = [fork] + self.riverDeck
            volcano_end = [tile for tile in self.riverDeck if tile.serialNumber == (7, "1113", 0, 1)][0]
            self.popRiverTile(volcano_end)
            # city_end = [tile for tile in self.riverDeck if tile.serialNumber == (7, "0131", 0, 0)][0]
        if self.checkPack(7, "a"):
            cloister_end = [tile for tile in self.riverDeck if tile.serialNumber == (7, "1113", 0, 2)][0]
            self.popRiverTile(cloister_end)
        if self.checkPack(7, "d"):
            cloister_end = [tile for tile in self.riverDeck if tile.serialNumber == (7, "1113", 0, 3)][0]
            self.popRiverTile(cloister_end)
            both_end = [tile for tile in self.riverDeck if tile.serialNumber == (7, "0132", 0, 0)][0]
            self.popRiverTile(both_end)
        if len(self.riverDeck) > 0:
            fff_end = volcano_end if self.checkPack(3, "b") and self.checkPack(7, "b") or not self.checkPack(7, "a") and not self.checkPack(7, "d") else cloister_end
            if self.checkPack(7, "d"):
                sh = [both_end, fff_end]
                random.shuffle(sh)
                self.riverDeck.extend(sh)
            else:
                self.riverDeck.append(fff_end)
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
        if self.checkPack(13, 'd'): # gold
            self.token_pos[Gold] = xpos
            xpos += 14 + 24 + 4
        self.token_length = xpos
        self.font_name = ImageFont.truetype("msyhbd.ttc", 16)
        self.font_score = ImageFont.truetype("msyhbd.ttc", 24)
        self.state: State = State.End
        self.stateGen = self.process()
        self.log: list[Log] = []
        self.stats: tuple[list[ccsCityStat], list[ccsRoadStat], list[ccsFieldStat], list[ccsMonastryStat], list[ccsMeepleStat]] = ([], [], [], [], [])
        if self.checkPack(3, "b"):
            self.dragon = [token for token in self.tokens if isinstance(token, Dragon)][0]
            self.dragonMoved: list[Tile] = []
        if self.checkPack(3, "c"):
            self.fairy = [token for token in self.tokens if isinstance(token, Fairy)][0]
        if self.checkPack(6, "b"):
            self.king = [token for token in self.tokens if isinstance(token, King)][0]
        if self.checkPack(6, "c"):
            self.robber = [token for token in self.tokens if isinstance(token, Robber)][0]
        if self.checkPack(9, 'b'):
            self.sheeps = [1, 1, 1, 1, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 4, 4, -1, -1]
            random.shuffle(self.sheeps)
        if self.checkPack(9, 'c'):
            self.hill_tiles: list[Tile] = []
        if self.checkPack(14, 'a'):
            self.giftDeck = [Gift.make(i)() for i in range(5) for _ in range(5)]
            random.shuffle(self.giftDeck)
            self.giftDiscard: list[Gift] = []
        if self.checkPack(14, "b"):
            self.ranger = [token for token in self.tokens if isinstance(token, Ranger)][0]
        if self.checkPack(14, "d"):
            self.gingerbread = [token for token in self.tokens if isinstance(token, Gingerbread)][0]
        if self.checkPack(15, "a"):
            self.landCity = [x for x in LandCity]
            random.shuffle(self.landCity)
            self.landCityDiscard: list[LandCity] = []
            self.landRoad = [x for x in LandRoad]
            random.shuffle(self.landRoad)
            self.landRoadDiscard: list[LandRoad] = []
            self.landMonastry = [x for x in LandMonastry]
            random.shuffle(self.landMonastry)
            self.landMonastryDiscard: list[LandMonastry] = []
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
            from .ccs_helper import LogRedraw
            self.addLog(LogRedraw())
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
    def updateLand(self):
        self.landCityDiscard.append(self.landCity.pop(0))
        if len(self.landCity) == 0:
            self.landCity = self.landCityDiscard
            self.landCityDiscard = []
            random.shuffle(self.landCity)
        self.landRoadDiscard.append(self.landRoad.pop(0))
        if len(self.landRoad) == 0:
            self.landRoad = self.landRoadDiscard
            self.landRoadDiscard = []
            random.shuffle(self.landRoad)
        self.landMonastryDiscard.append(self.landMonastry.pop(0))
        if len(self.landMonastry) == 0:
            self.landMonastry = self.landMonastryDiscard
            self.landMonastryDiscard = []
            random.shuffle(self.landMonastry)
    def setGameStatId(self, id: int):
        for l in self.stats:
            for d in l: # type: ignore
                d.game = id

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
                    seg.object.removeAllFollowers(HomeReason.Score)
            for feature in tile.features:
                if isinstance(feature, CanScore) and len(feature.tokens) != 0:
                    feature.scoreFinal()
                    feature.removeAllFollowers(HomeReason.Score)
        if self.checkPack(2, "d"):
            for i in range(3):
                max_token, max_players = findAllMax(self.players, lambda player, i=i: player.tradeCounter[i]) # type: ignore
                for player in max_players:
                    player.addScoreFinal(10, type=ScoreReason.Trade)
        for player in self.players:
            if self.checkPack(6, "b") and player.king:
                player.addScoreFinal(len(self.king.complete_citys), type=ScoreReason.King)
            if self.checkPack(6, "c") and player.robber:
                player.addScoreFinal(len(self.robber.complete_roads), type=ScoreReason.Robber)
            if self.checkPack(14, 'a') and len(player.gifts) >= 0:
                player.addScoreFinal(2 * len(player.gifts), type=ScoreReason.Gift)
            if self.checkPack(13, 'd'):
                gold_num = sum(1 for token in player.tokens if isinstance(token, Gold))
                player.addScoreFinal(Gold.score(gold_num), type=ScoreReason.Gold)
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

    def addLog(self, log: Log):
        self.log.append(log)
    def addStats(self):
        pass

    def tileImages(self):
        draw_tile_seg: tuple[int, int] | list[tuple[int, int]] | None = self.imageArgs.get("draw_tile_seg")
        debug: bool = self.imageArgs.get("debug", False)
        draw_tile_follower: tuple[int, int] | None = self.imageArgs.get("draw_tile_follower")
        princess: Object | None = self.imageArgs.get("princess")
        tower_pos: tuple[int, int] | None = self.imageArgs.get("tower_pos")
        draw_occupied_seg: bool = self.imageArgs.get("draw_occupied_seg", False)
        tile_figure: tuple[int, int] | None = self.imageArgs.get("tile_figure")

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
        # last pos
        for player in self.players:
            if player.last_pos is not None:
                color = "white" if player.tokenColor == "gray" else player.tokenColor
                dr.rectangle(posshift(*player.last_pos, (0, 0)) + posshift(*player.last_pos, (63, 1)), color)
                dr.rectangle(posshift(*player.last_pos, (0, 0)) + posshift(*player.last_pos, (1, 63)), color)
                dr.rectangle(posshift(*player.last_pos, (62, 0)) + posshift(*player.last_pos, (63, 63)), color)
                dr.rectangle(posshift(*player.last_pos, (0, 62)) + posshift(*player.last_pos, (63, 63)), color)
        # hill
        if self.checkPack(9, 'c'):
            to_paste: list[tuple[tuple[int, int], Image.Image]] = []
            for p, tile in self.tiles.items():
                if tile.addable == TileAddable.Hill:
                    imgt = img.crop(posshift(*p) + posshift(*p, (64, 64)))
                    to_paste.append((p, imgt))
            to_paste.sort(key=lambda x: x[0])
            for p, imgt in to_paste:
                dr.rectangle(posshift(*p) + posshift(*p, (64, 64)), "gray")
                img.paste(imgt, posshift(*p, (-1, -3)))
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
        if tile_figure is not None:
            tile = self.tiles[tile_figure]
            i = ord('a')
            for token in list(tile.iterAllTokens()) + tile.tokens + [token for seg in tile.segments for token in seg.object.tokens]:
                draw(tile_figure, tile.findTokenDrawPos(token), i)
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
        for p in self.players:
            p.image_pre()
        score_length = max(p.score_length for p in self.players)
        imgs = [p.image(score_length) for p in self.players]
        img = Image.new("RGBA", (imgs[0].size[0], 24 * len(self.players)))
        for i, pimg in enumerate(imgs):
            img.alpha_composite(pimg, (0, i * 24))
        return img
    def handTileImage(self):
        return self.current_player.handTileImage()
    def remainTileImages(self):
        remove_zero = len(self.deck) <= len(self.tiles)
        extra = 40 if self.checkPack(9, 'b') else 0
        def pos(w: int, h: int, *offsets: tuple[int, int]):
            return w * (64 + 8) + sum(c[0] for c in offsets) + 8, h * (64 + 20) + sum(c[1] for c in offsets) + 20 + extra
        x2: dict[int, int] = {}
        if (river := len(self.riverDeck) != 0):
            to_check = self.riverDeck
        else:
            to_check = self.deck
            if self.checkPack(9, 'c'):
                to_check = self.deck + self.hill_tiles
        for ids in sorted(self.allTileimgs.keys()):
            if ("3" in ids[1]) != river:
                continue
            if not remove_zero or sum(1 for tile in to_check if tile.serialNumber == ids) != 0:
                x2[ids[0]] = x2.get(ids[0], 0) + 1
        height = sum((x - 1) // 5 + 1 for x in x2.values())
        img = Image.new("RGBA", pos(5, height), "LightCyan")
        dr = ImageDraw.Draw(img)
        if self.checkPack(9, 'b'):
            txt = "，".join(f"{s}羊：{self.sheeps.count(s)}" for s in (1, 2, 3, 4))
            txt += f"，狼：{self.sheeps.count(-1)}"
            dr.text((10, 10), txt, "black", self.font_name, "lt")
        y: int = 0
        x: int = 0
        last_pack: int = 0
        for ids in sorted(self.allTileimgs.keys()):
            if "3" in ids[1]:
                continue
            if ids[0] != last_pack:
                last_pack = ids[0]
                y += (x - 1) // 5 + 1
                x = 0
            timg = self.allTileimgs[ids]
            if (num := sum(1 for tile in to_check if tile.serialNumber == ids)) != 0 or not remove_zero:
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
        if self.group_id is not None:
            self.image().save(config.pag(f"ccs\\{self.group_id}.png"))
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
        except (CantPutError,):
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

    async def advance(self, send: Callable[[Any], Awaitable], delete_func: Callable[[], Awaitable],
            to_send: Recieve | None=None):
        try:
            if to_send is None:
                ret = next(self.stateGen)
            else:
                ret = self.stateGen.send(to_send)
        except StopIteration as e:
            if e.value:
                await send("所有剩余图块均无法放置，提前结束游戏！")
            self.setImageArgs(no_final_score=True)
            await send([self.saveImg()])
            score_win, players_win = self.winner()
            if len(players_win) == 1:
                await send(f'玩家{players_win[0].name}以{score_win}分获胜！')
            else:
                await send('玩家' + '，'.join(p.name for p in players_win) + f'以{score_win}分获胜！')
            # game log
            from .. import config
            import datetime
            config.userdata.execute("insert into ccs_gamelog (group_id, users, extensions, time, score, winner, winner_score) values (?, ?, ?, ?, ?, ?, ?)", (self.group_id or 0, ','.join(p.long_name for p in self.players), json.dumps(self.packs_options), datetime.datetime.now().isoformat(), ','.join(str(p.score) for p in self.players), ','.join(str(q) for q in players_win), score_win))
            await delete_func()
            return
        if len(self.log) != 0:
            outputs = []
            from .ccs_helper import LogScore, LogRedraw, LogPutBackBuilder, LogExchangePrisoner
            from .ccs_helper import LogTradeCounter, LogChallengeFailed, LogDrawGift, LogUseGift
            from .ccs_helper import LogTake2NoTile, LogDice, LogDragonMove, LogShepherd
            for d in self.log:
                match d:
                    case LogScore(player_name=name, source=source, num=num):
                        outputs.append(f"玩家{name}因" + {"fairy": "仙子", "complete": "已完成建筑", "final": "未完成建筑", "fairy_complete": "已完成建筑中的仙子", "ranger": "护林员", "cash_out": "兑现", "gingerbread": "姜饼人"}[source] + f"获得{num}分。")
                    case LogRedraw():
                        outputs.append("牌堆顶卡无法放置，故重抽一张。")
                    case LogPutBackBuilder(player_name=name, meeple_name=meeple_name):
                        outputs.append(f"玩家{name}的{'建筑师' if meeple_name == 'Builder' else '猪'}因所在区域没人而返回。")
                    case LogExchangePrisoner(player2_name=p2name, player1_name=p1name):
                        outputs.append(f"玩家{p2name}和玩家{p1name}的囚犯自动互换了。")
                    case LogTradeCounter(trade=trade):
                        outputs.append("你获得了" + '，'.join(f"{num}个" + ["酒", "小麦", "布"][i] for i, num in enumerate(trade) if num != 0) + '。')
                    case LogChallengeFailed(name=name):
                        outputs.append({"shrine": "神龛", "cloister": "修道院"}[name] + "的挑战失败！")
                    case LogDrawGift(gift_name=name, gifts_text=gifts):
                        outputs.append("你抽了一张礼物卡，已通过私聊发送。")
                        await send("你抽到了礼物卡：" + name + "\n你手中的礼物卡有：" + gifts, ensure_private=True) # type: ignore
                    case LogUseGift(gift_name=name, gifts_text=gifts):
                        outputs.append("你使用了礼物卡：" + name)
                        await send("你现在手中的礼物卡有：" + gifts, ensure_private=True) # type: ignore
                    case LogTake2NoTile():
                        outputs.append("并未找到第二张可以放置的板块！")
                    case LogDice(result=result):
                        outputs.append(f"骰子扔出了{result}点。")
                    case LogDragonMove(player_name=name, dir=dr):
                        outputs.append(f"玩家{name}自动向{dr.name[0]}方向动了一次龙。")
                    case LogShepherd(player_name=name, sheep=sheep):
                        outputs.append(f"玩家{name}抽到了{'狼' if sheep == -1 else str(sheep) + '只羊'}。")
            await send("\n".join(outputs))
            self.log = []
        match self.state:
            case State.PuttingTile:
                from .ccs_helper import SendPuttingTile
                assert isinstance(ret, SendPuttingTile)
                rete = ret.last_err
                if rete == -1:
                    await send("已有连接！")
                elif rete == -2:
                    await send("无法连接！")
                elif rete == -3:
                    await send("没有挨着！")
                elif rete == -4:
                    await send("未找到可赎回的囚犯！")
                elif rete == -5:
                    await send("余分不足以赎回！")
                elif rete == -6:
                    await send("河流不能回环！")
                elif rete == -7:
                    await send("河流不能拐弯180度！")
                elif rete == -8:
                    await send("修道院不能和多个神龛相连，反之亦然！")
                elif rete == -9:
                    await send("必须扩张河流！")
                elif rete == -10:
                    await send("河流分叉必须岔开！")
                elif rete == -11:
                    await send("未找到礼物卡！")
                elif rete == -12:
                    await send("请指定使用哪张手牌！")
                else:
                    if ret.begin and ret.second_turn:
                        await send("玩家继续第二回合")
                    self.setImageArgs()
                    await send([self.saveImg()])
                    await send((f'玩家{self.current_turn_player.long_name}开始行动，' if ret.begin else "") + '请选择放图块的坐标，以及用URDL将指定方向旋转至向上。' + ("此时可发送“赎回玩家nxxx”花3分赎回囚犯。" if not ret.second_turn and self.checkPack(4, "b") else "") + ('回复礼物+第几张使用礼物卡，“查询礼物”查询。' if self.checkPack(14, "a") and not ret.gifted else ""))
            case State.ChoosingPos:
                from .ccs_helper import SendChoosingPos
                assert isinstance(ret, SendChoosingPos)
                if ret.last_err == -1:
                    await send("板块不存在！")
                elif ret.last_err == -2:
                    await send("不符合要求！")
                elif ret.last_err == -3:
                    await send("这个金块不是你的！")
                else:
                    self.setImageArgs()
                    await send([self.saveImg()])
                    if ret.special == "synod":
                        await send("请选择修道院，输入图块坐标。")
                    elif ret.special == "road_sweeper":
                        await send("请选择未完成道路，输入图块坐标。")
                    elif ret.special == "cash_out":
                        await send("请选择跟随者兑现，输入图块坐标。")
                    elif ret.special == "ranger":
                        await send("请选择要将护林员移动到的图块坐标。")
                    elif ret.special == "change_position":
                        await send("请选择跟随者切换形态，输入图块坐标。")
                    elif ret.special == "gingerbread":
                        await send("请选择要移动到的城市，输入图块坐标。")
                    elif ret.special == "gold":
                        await send("请选择放置另一个金块的图块坐标。")
                    elif ret.special == "gold_take":
                        await send(f"请玩家{self.current_player.long_name}选择拿取金块的图块坐标。")
                    else:
                        await send("请选择坐标（通用）。")
            case State.PuttingFollower:
                from .ccs_helper import SendPuttingFollower
                assert isinstance(ret, SendPuttingFollower)
                if ret.last_err == -1:
                    await send("没有找到跟随者！")
                elif ret.last_err == -2:
                    await send("无法放置！")
                elif ret.last_err == -3:
                    await send("无法移动仙子！")
                elif ret.last_err == -4:
                    await send("无法使用传送门！")
                elif ret.last_err == -5:
                    await send("找不到高塔！")
                elif ret.last_err == -6:
                    await send("高塔有人！")
                elif ret.last_err == -7:
                    await send("手里没有高塔片段！")
                elif ret.last_err == -8:
                    await send("找不到修道院长！")
                elif ret.last_err == -9:
                    await send("无法移动护林员！")
                elif ret.last_err == -10:
                    await send("未找到幽灵！")
                elif ret.last_err == -11:
                    await send("幽灵无法放置！")
                elif ret.last_err == -12:
                    await send("在高塔/传送门/飞行器时不能使用幽灵，请仅仅申请“放幽灵”！")
                elif ret.last_err == -13:
                    await send("不能重复使用传送门/飞行器！")
                elif ret.last_err == -14:
                    await send("无法使用节日移除！")
                else:
                    self.setImageArgs(draw_tile_seg=ret.last_put)
                    await send([self.saveImg()])
                    if ret.special == "phantom":
                        prompt = "请选择放置幽灵的位置"
                    else:
                        prompt = "请选择放置跟随者的位置（小写字母）以及放置的特殊跟随者名称（如有需要）"
                        if self.checkPack(3, "c"):
                            prompt += "，回复跟随者所在板块位置以及“仙子”移动仙子"
                        if self.checkPack(4, "b"):
                            prompt += "，回复板块位置以及“高塔”以及跟随者名称（可选）放置高塔片段或跟随者"
                        if self.checkPack(12, "b"):
                            prompt += "，回复板块位置以及“修道院长”回收修道院长"
                        if self.checkPack(14, "b") and not ret.rangered:
                            prompt += "，回复板块位置以及“护林员”移动护林员"
                        if self.checkPack(13, "j") and self.tiles[ret.last_put].addable == TileAddable.Festival:
                            prompt += "，回复板块位置以及“节日”移除物体（移除谷仓请指定谷仓左上角的板块）"
                        if self.checkPack(13, "k"):
                            prompt += "，后加“放幽灵”申请放幽灵，或直接后加小写字母以及“幽灵”放置幽灵"
                    if not ret.portaled and self.checkPack(3, "d") and self.tiles[ret.last_put].addable == TileAddable.Portal:
                        prompt += "，回复板块位置以及“传送门”使用传送门"
                    if ret.portaled:
                        prompt += "，回复“返回”返回原板块" + ("并重新选择幽灵" if self.checkPack(13, "k") and ret.special != "phantom" else "")
                    else:
                        prompt += "，回复“不放”跳过"
                    prompt += "。"
                    await send(prompt)
            case State.WagonAsking:
                from .ccs_helper import SendMovingWagon
                assert isinstance(ret, SendMovingWagon)
                if ret.last_err == -1:
                    await send("没有该图块！")
                elif ret.last_err == -2:
                    await send("图块过远，只能放在本图块或是相邻的8块上！")
                elif ret.last_err == -3:
                    await send("无法放置！")
                else:
                    pos = ret.pos
                    self.setImageArgs(draw_tile_seg=[(pos[0] + i, pos[1] + j) for i in (-1, 0, 1) for j in (-1, 0, 1)])
                    await send([self.saveImg()])
                    await send("请选择马车要移动到的图块，以及该图块上的位置（小写字母），回复“不放”收回马车。")
            case State.AbbeyAsking | State.FinalAbbeyAsking:
                from .ccs_helper import SendAbbeyAsking
                assert isinstance(ret, SendAbbeyAsking)
                if ret.last_err == -1:
                    await send("无法放置！")
                elif ret.last_err == -8:
                    await send("修道院不能和多个神龛相连！")
                else:
                    if ret.begin and ret.second_turn:
                        await send("玩家继续第二回合")
                    if ret.begin:
                        self.setImageArgs()
                        await send([self.saveImg()])
                    await send((f'玩家{self.current_player.long_name}' if ret.begin or self.state == State.FinalAbbeyAsking else "") + ("开始行动，选择" if ret.begin else "选择最后" if self.state == State.FinalAbbeyAsking else "请选择") + "是否放置僧院板块，回复“不放”跳过。")
            case State.MovingDragon:
                from .ccs_helper import SendMovingDragon
                assert isinstance(ret, SendMovingDragon)
                if ret.last_err == -1:
                    await send("无法移动！")
                else:
                    self.setImageArgs()
                    await send([self.saveImg()])
                    await send(f'玩家{self.current_player.long_name}第{ret.moved_num + 1}次移动龙，请输入URDL移动。')
            case State.ChoosingOwnFollower:
                from .ccs_helper import SendPosSpecial
                assert isinstance(ret, SendPosSpecial)
                if ret.last_err == -1:
                    await send("无法移动！")
                if ret.last_err == -2:
                    await send("未找到跟随者！")
                if ret.last_err == -3:
                    await send("不符合要求！")
                else:
                    self.setImageArgs(draw_tile_follower=ret.pos)
                    await send([self.saveImg()])
                    if ret.special == "fairy":
                        await send('请额外指定要放置在哪个跟随者旁。')
                    elif ret.special == "cash_out":
                        await send('请额外指定要兑现哪个跟随者。')
                    elif ret.special == "change_position":
                        await send('请额外指定要切换哪个跟随者。')
                    else:
                        await send("请选择跟随者（通用）。")
            case State.PrincessAsking:
                from .ccs_helper import SendPrincess
                assert isinstance(ret, SendPrincess)
                if ret.last_err == -1:
                    await send("未找到跟随者！")
                else:
                    self.setImageArgs(princess=ret.object)
                    await send([self.saveImg()])
                    await send('你放置了公主，可以指定公主要移走哪名跟随者，回复“返回”跳过。')
            case State.CaptureTower:
                from .ccs_helper import SendPos
                assert isinstance(ret, SendPos)
                if ret.last_err == -1:
                    await send("未找到跟随者！")
                else:
                    self.setImageArgs(tower_pos=ret.pos)
                    await send([self.saveImg()])
                    await send('请选择要抓的跟随者，回复“不抓”跳过。')
            case State.ExchangingPrisoner:
                if ret.last_err == -1:
                    await send("未找到跟随者！")
                else:
                    self.setImageArgs()
                    await send([self.saveImg()])
                    await send(f'请玩家{self.current_player.long_name}选择换回的对方的跟随者。')
            case State.ChoosingSegment:
                from .ccs_helper import SendPosSpecial
                assert isinstance(ret, SendPosSpecial)
                if ret.last_err == -1:
                    await send("未找到片段号！")
                if ret.last_err == -2:
                    await send("不符合要求！")
                else:
                    self.setImageArgs(draw_tile_seg=ret.pos, draw_occupied_seg=True)
                    await send([self.saveImg()])
                    if ret.special == "road_sweeper":
                        await send('请选择道路片段。')
                    elif ret.special == "change_position":
                        await send('请选择切换形态的片段。')
                    elif ret.special == "flier":
                        await send('请选择放置跟随者的片段。')
                    elif ret.special == "gingerbread":
                        await send('请选择姜饼人移动到的片段。')
                    else:
                        await send("请选择片段（通用）。")
            case State.AskingSynod:
                if ret.last_err == -1:
                    await send("板块不存在！")
                elif ret.last_err == -2:
                    await send("不符合要求！")
                elif ret.last_err == -3:
                    await send("没有跟随者！")
                elif ret.last_err == -4:
                    await send("无法放置！")
                else:
                    self.setImageArgs()
                    await send([self.saveImg()])
                    await send('请选择放置的修道院板块坐标以及跟随者。')
            case State.ChoosingTileFigure:
                from .ccs_helper import SendPosSpecial
                assert isinstance(ret, SendPosSpecial)
                if ret.last_err == -1:
                    await send("未找到物体！")
                elif ret.last_err == -2:
                    await send("不符合要求！")
                else:
                    self.setImageArgs(tile_figure=ret.pos)
                    await send([self.saveImg()])
                    if ret.special == "festival":
                        await send('请选择板块上要移除的物体。')
                    else:
                        await send("请选择板块上的物体（通用）。")

class CanScore(ABC):
    def __init__(self, board: Board) -> None:
        super().__init__()
        self.board = board
    @abstractmethod
    def closed(self) -> bool:
        pass
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
                yield from token.scoreExtra()

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
        return {"cloister": Cloister, "garden": Garden, "shrine": Shrine, "tower": Tower, "flier": Flier}[typ.lower()]
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
        token.player.tokens.remove(token)
        yield from token.putOn(to_put)
        yield from super().putOnBy(token)

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

Token.all_name["follower"] = BaseFollower

AbbeyData = TileData("abbey", 0, "FFFF", [])
AbbeyData.segments.append(FeatureSegmentData("Cloister", (32, 32), [], AbbeyData))

from .ccs_extra import Gift, LandCity, LandRoad, LandMonastry, ScoreReason, HomeReason
from .ccs_extra import ccsCityStat, ccsGameStat, ccsRoadStat, ccsFieldStat, ccsMonastryStat, ccsMeepleStat, ccsTowerStat
from .ccs_player import Player
from .ccs_helper import RecieveId

if __name__ == "__main__":
    b = Board({0: "a", 1: "abcd", 2: "abcd", 3: "abcde", 4: "ab", 5: "abcde", 6: "abcdefgh", 7: "abcd", 9: "abc", 12: "ab", 13: "abcdijk"}, ["任意哈斯塔", "哈斯塔网络整体意识", "当且仅当哈斯塔", "到底几个哈斯塔", "普通的哈斯塔", "不是哈斯塔"])
    d = {
            "name": "follower",
            "distribute": True,
            "num": 7,
            "image": [0, 0, 16, 16]
        }
    b.players[0].tokens.pop(0)
    yshift = 0
    cri = lambda s: s.serialNumber[0] in (6, 9,)
    picnames = sorted(set(s.serialNumber[1] for s in b.deck + b.riverDeck if cri(s)))
    for pic in picnames:
        ss = sorted(set(s.serialNumber[1:] for s in b.deck + b.riverDeck if s.picname == pic if cri(s)))
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
    for p in b.players:
        p.last_pos = (0, p.id)
    # b.setImageArgs(debug=True)
    b.image().show()
