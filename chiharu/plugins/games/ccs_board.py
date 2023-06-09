from typing import Literal, Any, Type, Callable, Awaitable
from collections import Counter
import random, more_itertools, json, re
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from .ccs_tile import Dir, open_img, readTileData, readPackData
from .ccs_helper import CantPutError, NoDeckEnd, TileAddable
from .ccs_helper import findAllMax, State, Log, Send, Recieve

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
        if self.checkPack(10, 'b'):
            self.animals = [1, 3, 3, 3, 3, 4, 4, 4, 4, 4, 5, 5, 5, 6, 6, 7]
            random.shuffle(self.animals)
            self.bigtop = [token for token in self.tokens if isinstance(token, Bigtop)][0]
        if self.checkPack(14, 'a'):
            self.giftDeck = [Gift.make(i)() for i in range(5) for _ in range(5)]
            random.shuffle(self.giftDeck)
            self.giftDiscard: list[Gift] = []
        if self.checkPack(12, "c"):
            self.messengerDeck = [Messenger.make(i)() for i in range(1, 9)]
            random.shuffle(self.messengerDeck)
            self.messengerDiscard: list[Messenger] = []
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
    def drawMessenger(self):
        if not self.checkPack(12, 'c'):
            return None
        if len(self.messengerDeck) == 0:
            if len(self.messengerDiscard) == 0:
                return None
            self.messengerDeck = self.messengerDiscard
            random.shuffle(self.messengerDeck)
        return self.messengerDeck.pop(0)
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
        if self.checkPack(12, "c"):
            for player in self.players:
                player.score += player.score2
                player.score2 = 0
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
        extra = 0
        if self.checkPack(9, 'b'):
            sheep_begin = extra
            extra += 40
        if self.checkPack(10, 'b'):
            animals_begin = extra
            extra += 40
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
            dr.text((10, sheep_begin + 10), txt, "black", self.font_name, "lt")
        if self.checkPack(10, 'b'):
            txt = "，".join(f"{a}分x{num}" for a, num in sorted(Counter(self.animals).items()))
            dr.text((10, animals_begin + 10), txt, "black", self.font_name, "lt")
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

    def endGameAskAbbey(self) -> 'TAsync[None]':
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
    def process(self) -> 'TAsync[bool]':
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
                elif ret.last_err == -15:
                    await send("无法放置或计分杂技！")
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
                        if self.checkPack(10, "c"):
                            prompt += "，回复板块位置以及“杂技”放置杂技或计分杂技"
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
                from .ccs_helper import SendInt
                assert isinstance(ret, SendInt)
                if ret.last_err == -1:
                    await send("无法移动！")
                else:
                    self.setImageArgs()
                    await send([self.saveImg()])
                    await send(f'玩家{self.current_player.long_name}第{ret.num + 1}次移动龙，请输入URDL移动。')
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
            case State.ChoosingShepherd:
                await send("请选择扩张或是计分你的牧羊人。")
            case State.ChoosingScoreMove:
                from .ccs_helper import SendInt
                assert isinstance(ret, SendInt)
                await send(f"你增加了{ret.num}分，请选择记在第1个分还是第2个分上。")
            case State.ChoosingMessenger:
                from .ccs_helper import SendInt
                assert isinstance(ret, SendInt)
                await send(f"你抽到了圣旨{ret.num}，作用为{Messenger.make(ret.num).des}，请选择使用还是不用（换2分）。")

    async def parse_command(self, command: str, send: Callable[[Any], Awaitable], delete_func: Callable[[], Awaitable]):
        match self.state:
            case State.PuttingTile:
                if match := re.match(r"\s*([a-z])?\s*([A-Z]+)([0-9]+)\s*([URDL])$", command):
                    tilenum = ord(match.group(1)) - ord('a') if match.group(1) else -1
                    xs = match.group(2); ys = match.group(3); orients = match.group(4)
                    pos = self.tileNameToPos(xs, ys)
                    orient = {'U': Dir.UP, 'R': Dir.LEFT, 'D': Dir.DOWN, 'L': Dir.RIGHT}[orients]
                    from .ccs_helper import RecievePuttingTile
                    await self.advance(send, delete_func, RecievePuttingTile(pos, orient, tilenum))
                elif match := re.match(r"\s*赎回玩家(\d+)(.*)?$", command):
                    player_id = int(match.group(1)) - 1
                    name = match.group(2)
                    from .ccs_helper import RecieveBuyPrisoner
                    await self.advance(send, delete_func, RecieveBuyPrisoner(player_id, name or "follower"))
                elif match := re.match(r"\s*礼物([0-9]+)$", command):
                    ns = match.group(1)
                    await self.advance(send, delete_func, RecieveId(int(ns) - 1))
            case State.ChoosingOwnFollower | State.ChoosingSegment | State.ChoosingTileFigure:
                if match := re.match(r"\s*([a-z])$", command):
                    n = ord(match.group(1)) - ord('a')
                    await self.advance(send, delete_func, RecieveId(n))
            case State.PrincessAsking | State.CaptureTower:
                if command in ("不放", "返回"):
                    await self.advance(send, delete_func, RecieveReturn())
                elif match := re.match(r"\s*([a-z]+)$", command):
                    xs = match.group(1)
                    n = (ord(xs[0]) - ord('a') + 1) * 26 + ord(xs[1]) - ord('a') if len(xs) == 2 else ord(xs) - ord('a')
                    await self.advance(send, delete_func, RecieveId(n))
            case State.PuttingFollower:
                from .ccs_helper import RecievePuttingFollower
                if command in ("不放", "返回"):
                    await self.advance(send, delete_func, RecieveReturn())
                phantom: int = -1
                if self.checkPack(13, "k") and (match0 := re.match(r"(.*\S)\s*([a-z])\s*(幽灵|phantom)$", command)):
                    n = ord(match0.group(2)) - ord('a')
                    command = match0.group(1).strip()
                    phantom = n
                elif self.checkPack(13, "k") and (match0 := re.match(r"(.*\S)\s*放(幽灵|phantom)$", command)):
                    command = match0.group(1).strip()
                    phantom = -2
                if match := re.match(r"\s*([a-z])\s*(.*)?$", command):
                    n = ord(match.group(1)) - ord('a')
                    name = match.group(2)
                    await self.advance(send, delete_func, RecievePuttingFollower(n, name or "follower", phantom))
                elif match := re.match(r"\s*([A-Z]+)([0-9]+)\s*(仙子|fairy|传送门|portal|修道院长|abbot|护林员|ranger|节日|festival|杂技|acrobat)$", command):
                    xs = match.group(1); ys = match.group(2)
                    pos = self.tileNameToPos(xs, ys)
                    special = {"仙子": "fairy", "传送门": "portal", "修道院长": "abbot", "护林员": "ranger", "节日": "festival", "杂技": "acrobat"}.get(match.group(3), match.group(3))
                    await self.advance(send, delete_func, RecievePuttingFollower(-1, "follower", phantom, special, pos))
                elif self.checkPack(4, "b") and (match := re.match(r"\s*([A-Z]+)([0-9]+)\s*(高塔|tower)\s*(.*)?$", command)):
                    xs = match.group(1); ys = match.group(2); which = match.group(4)
                    pos = self.tileNameToPos(xs, ys)
                    await self.advance(send, delete_func, RecievePuttingFollower(-1, which, phantom, "tower", pos))
            case State.AskingSynod:
                if match := re.match(r"\s*([A-Z]+)([0-9]+)\s*(.*)?$", command):
                    xs = match.group(1); ys = match.group(2)
                    name = match.group(3)
                    pos = self.tileNameToPos(xs, ys)
                    from .ccs_helper import RecievePosWhich
                    await self.advance(send, delete_func, RecievePosWhich(pos, name or "follower"))
            case State.ExchangingPrisoner:
                if match := re.match(r"\s*(.*)$", command):
                    from .ccs_helper import RecieveWhich
                    await self.advance(send, delete_func, RecieveWhich(match.group(1)))
            case State.MovingDragon:
                if command in "URDL":
                    dr = {"U": Dir.UP, "R": Dir.RIGHT, "D": Dir.DOWN, "L": Dir.LEFT}[command]
                    from .ccs_helper import RecieveDir
                    await self.advance(send, delete_func, RecieveDir(dr))
            case State.WagonAsking:
                if command == "不放":
                    await self.advance(send, delete_func, RecieveReturn())
                elif match := re.match(r"\s*([A-Z]+)([0-9]+)\s*([a-z])$", command):
                    xs = match.group(1); ys = match.group(2); n = ord(match.group(3)) - ord('a')
                    pos = self.tileNameToPos(xs, ys)
                    from .ccs_helper import RecieveWagon
                    await self.advance(send, delete_func, RecieveWagon(pos, n))
            case State.AbbeyAsking | State.FinalAbbeyAsking:
                if command == "不放":
                    await self.advance(send, delete_func, RecieveReturn())
                elif match := re.match(r"\s*([A-Z]+)([0-9]+)$", command):
                    xs = match.group(1); ys = match.group(2)
                    pos = self.tileNameToPos(xs, ys)
                    await self.advance(send, delete_func, RecievePos(pos))
            case State.ChoosingPos:
                if match := re.match(r"\s*([A-Z]+)([0-9]+)$", command):
                    xs = match.group(1); ys = match.group(2)
                    pos = self.tileNameToPos(xs, ys)
                    await self.advance(send, delete_func, RecievePos(pos))
            case State.ChoosingShepherd:
                from .ccs_helper import RecieveChoose
                if command == "扩张":
                    await self.advance(send, delete_func, RecieveChoose(False))
                elif command == "计分":
                    await self.advance(send, delete_func, RecieveChoose(True))
            case State.ChoosingScoreMove:
                from .ccs_helper import RecieveChoose
                if command == "1":
                    await self.advance(send, delete_func, RecieveChoose(False))
                elif command == "2":
                    await self.advance(send, delete_func, RecieveChoose(True))
            case State.ChoosingMessenger:
                from .ccs_helper import RecieveChoose
                if command == "不用":
                    await self.advance(send, delete_func, RecieveChoose(False))
                elif command == "使用":
                    await self.advance(send, delete_func, RecieveChoose(True))
            case _:
                pass


from .ccs import Tile, Segment, Token, Gold, Dragon, Fairy, Robber, Ranger, Gingerbread, CanScore
from .ccs import Cloister, Shrine, BaseCloister, Object, Barn, Follower, Tower, TAsync, King, Bigtop
from .ccs_extra import Gift, LandCity, LandRoad, LandMonastry, ScoreReason, HomeReason, Messenger
from .ccs_extra import ccsCityStat, ccsGameStat, ccsRoadStat, ccsFieldStat, ccsMonastryStat, ccsMeepleStat, ccsTowerStat
from .ccs_player import Player
from .ccs_helper import RecieveId, RecieveReturn, RecievePos
