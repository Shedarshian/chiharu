from typing import Literal, Any, Generator, Type, TypeVar, Iterable, Callable, Sequence, TypedDict
import more_itertools, random
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

class Player:
    def __init__(self, board: 'Board', id: int, name: str) -> None:
        self.board = board
        self.id = id
        self.name = name[:20]
        self.tokens: list[Token] = []
        self.allTokens: list[Token] = []
        self.score: int = 0
        self.handTiles: list[Tile] = []
        if self.board.checkPack(2, 'd'):
            self.tradeCounter = [0, 0, 0]
        if self.board.checkPack(5, 'b'):
            self.hasAbbey = True
        if self.board.checkPack(4, 'b'):
            self.towerPieces: int = 0
            self.prisoners: list[Follower] = []
        if self.board.checkPack(14, 'a'):
            self.gifts: list[Gift] = []
    @property
    def tokenColor(self):
        return ["green", "blue", "gray", "violet", "black", "yellow"][self.id]
    @property
    def show_name(self):
        show_name = self.name
        if self.board.font_name.getlength(self.name) > 80:
            while self.board.font_name.getlength(show_name + "...") > 80:
                show_name = show_name[:-1]
            show_name += "..."
        return show_name
    def addScore(self, score: int) -> 'TAsync[None]':
        self.score += score
        return
        yield {}
    def addScoreFinal(self, score: int):
        self.score += score
    def checkMeepleScoreCurrent(self):
        all_objects: list[CanScore] = []
        all_barns: list[Object] = []
        score: int = 0
        for token in self.allTokens:
            if isinstance(token, Barn) and isinstance(token.parent, Segment):
                all_barns.append(token.parent.object)
            elif isinstance(token.parent, Segment) and token.parent.object not in all_objects:
                all_objects.append(token.parent.object)
            elif isinstance(token.parent, CanScore) and token.parent not in all_objects:
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
    def findToken(self, key: str, where: 'Sequence[Token] | None'=None):
        try:
            typ = Token.make(key)
        except KeyError:
            return None
        tokens = [token for token in (where if where is not None else self.tokens) if isinstance(token, typ)]
        if len(tokens) == 0:
            return None
        return tokens[0]
    def giftsText(self):
        return "\n".join(str(i + 1) + "." + card.name for i, card in enumerate(self.gifts))

    def turnDrawRiver(self, isBegin: bool) -> 'TAsync[bool]':
        self.handTiles.append(self.board.drawRiverTile())
        return isBegin
        yield {}
    def turnAskAbbey(self, turn: int, isBegin: bool, endGame: bool) -> 'TAsync[tuple[bool, bool, tuple[int, int]]]':
        isAbbey: bool = False
        tile: Tile | None = None
        pos: tuple[int, int] = (-1, -1)
        if self.hasAbbey and self.board.checkHole():
            while 1:
                pass_err: Literal[0, -1, -8] = 0
                self.board.state = State.FinalAbbeyAsking if endGame else State.AbbeyAsking
                ret = yield {"second_turn": turn == 1, "last_err": pass_err, "begin": isBegin}
                isBegin = False
                if not ret.get("put"):
                    break
                isAbbey = True
                self.hasAbbey = False
                pos = ret["pos"]
                tile = Tile(self.board, AbbeyData, True)
                r = self.board.canPutTile(tile, pos, Dir.UP)
                if r < 0:
                    pass_err = -8 if r == -8 else -1
                    continue
                self.handTiles.append(tile)
                self.board.tiles[pos] = tile
                for dr in Dir:
                    self.board.tiles[pos + dr].closeSideAbbey(-dr)
                break
        return isBegin, isAbbey, pos
    def turnDrawTile(self, turn: int, isBegin: bool) -> 'TAsync[bool]':
        tile = self.board.drawTileCanPut()
        if tile is None:
            raise CantPutError
        self.handTiles.append(tile)
        return isBegin
        yield {}
    def turnPutTile(self, turn: int, isBegin: bool) -> 'TAsync[tuple[bool, tuple[int, int], bool, bool]]':
        pass_err: Literal[0, -1, -2, -3, -4, -5, -6, -7, -8, -9, -10, -11, -12] = 0
        prisonered: bool = False
        gifted: bool = False
        while 1:
            self.board.state = State.PuttingTile
            ret = yield {"second_turn": turn == 1, "last_err": pass_err, "begin": isBegin, "gifted": gifted}
            pass_err = 0
            isBegin = False
            if self.board.checkPack(4, "b") and turn == 0 and not prisonered and ret.get("special") == "prisoner":
                if self.score < 3:
                    pass_err = -5
                    continue
                player_id: int = ret["player_id"]
                if player_id < 0 or player_id >= len(self.board.players):
                    pass_err = -4
                    continue
                player: 'Player' = self.board.players[player_id]
                token = player.findToken(ret.get("which", "follower"))
                if token is None:
                    pass_err = -4
                    continue
                yield from self.addScore(-3)
                yield from player.addScore(3)
                player.prisoners.remove(token)
                self.tokens.append(token)
                prisonered = True
                continue
            if self.board.checkPack(14, "a") and not gifted and ret.get("special") == "gift":
                if ret["id"] >= len(self.gifts):
                    pass_err = -11
                    continue
                gift: Gift = self.gifts.pop(ret["id"])
                self.board.addLog(id="useGift", gift=gift, player=self)
                ret2 = yield from gift.use(self)
                self.board.giftDiscard.append(gift)
                gifted = True
                continue
            if ret["tilenum"] == -1 and len(self.handTiles) != 1:
                pass_err = -12
                continue
            pos: tuple[int, int] = ret["pos"]
            orient: Dir = ret["orient"]
            tilenum: int = ret["tilenum"]
            tile: Tile = self.handTiles[0]
            tile = self.handTiles[tilenum]
            pass_err = self.board.canPutTile(tile, pos, orient)
            if pass_err < 0:
                continue
            if tile.packid == 7 and Connectable.River in tile.sides:
                drs = [dr for dr in Dir if pos + dr in self.board.tiles]
                if len(drs) != 1:
                    pass_err = -6
                    continue
                sides = tile.sides[4 - orient.value:] + tile.sides[:4 - orient.value]
                rdrs = [i for i, s in enumerate(sides) if s == Connectable.River]
                if drs[0].value not in rdrs:
                    pass_err = -9
                    continue
                rdrs.remove(drs[0].value)
                if len(rdrs) == 2 and sides[Dir.DOWN.value] == Connectable.River:
                    pass_err = -10
                    continue
                if len(rdrs) == 1:
                    if pos[0] < 0 and rdrs[0] not in (Dir.LEFT.value, Dir.DOWN.value) or pos[0] > 0 and rdrs[0] not in (Dir.RIGHT.value, Dir.DOWN.value):
                        pass_err = -7
                        continue
            break
        tile.turn(orient)
        self.board.tiles[pos] = tile
        for dr in Dir:
            if pos + dr in self.board.tiles:
                self.board.tiles[pos + dr].addConnect(tile, -dr)
        rangered: bool = self.board.checkPack(14, "b") and self.board.ranger.pos == pos
        princessed: bool = False
        if self.board.checkPack(3, "e") and (seg := more_itertools.only(seg for seg in tile.segments if seg.addable == Addable.Princess)):
            followers = [token for token in seg.object.iterTokens() if isinstance(token, Follower) and isinstance(token.parent, Segment)]
            if len(followers) != 0:
                pass_err = 0
                while 1:
                    self.board.state = State.PrincessAsking
                    ret = yield {"object": seg.object, "last_err": pass_err}
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
        if self.board.checkPack(14, "a"):
            for segment in tile.segments:
                if isinstance(segment, (RoadSegment, CitySegment)) and len(l := segment.object.checkPlayer()) > 0 and self not in l:
                    if gift := self.board.drawGift():
                        self.board.addLog(id="drawGift", gift=gift, player=self)
                        self.gifts.append(gift)
                        self.gifts.sort(key=lambda g: g.id)
                    break
        if len(self.handTiles) > 1:
            for tile2 in self.handTiles:
                if tile2 is not tile:
                    self.board.deck.append(tile2)
            self.handTiles = [tile]
            random.shuffle(self.board.deck)
        return isBegin, pos, princessed, rangered
    def turnMoveGingerbread(self, complete: bool) -> 'TAsync[None]':
        ginger = self.board.gingerbread
        for t in self.board.tiles.values():
            citys = [segment for segment in t.segments if isinstance(segment, CitySegment) and not segment.closed() and ginger.canPut(segment)]
            if len(citys) > 0:
                break
        else:
            if complete:
                ginger.putBackToHand()
            return
        pass_err: Literal[0, -1, -2] = 0
        while 1:
            self.board.state = State.ChoosingPos
            ret = yield {"last_err": pass_err, "special": "gingerbread"}
            if ret["pos"] not in self.board.tiles:
                pass_err = -1
                continue
            tile = self.board.tiles[ret["pos"]]
            citys = [segment for segment in tile.segments if isinstance(segment, CitySegment) and not segment.closed() and ginger.canPut(segment)]
            if len(citys) == 0:
                pass_err = -2
                continue
            city = citys[0]
            if len(citys) >= 2:
                pass_err = 0
                while 1:
                    self.board.state = State.ChoosingSegment
                    ret2 = yield {"last_err": pass_err, "last_put": ret["pos"], "special": "gingerbread"}
                    s = tile.getSeg(ret2["id"])
                    if not isinstance(s, CitySegment):
                        pass_err = -1
                        continue
                    if s not in citys:
                        pass_err = -2
                        continue
                    city = s
                    break
            if not complete:
                yield from ginger.score()
            ginger.remove()
            yield from ginger.putOn(city)
            break
    def turnCheckBuilder(self) -> 'TAsync[bool]':
        if not self.board.checkPack(2, 'b'):
            return False
        for seg in self.handTiles[0].segments:
            for token in seg.object.iterTokens():
                if token.player is self and isinstance(token, Builder):
                    return True
        return False
        yield {}
    def turnPutFollower(self, tile: 'Tile', pos: tuple[int, int], rangered: bool) -> 'TAsync[bool]':
        pass_err: int = 0
        if_portal: bool = False
        if_flier: bool = False
        put_barn: bool = False
        pos_put = pos
        tile_put = tile
        ph_put: int = -1
        while 1:
            self.board.state = State.PuttingFollower
            ret = yield {"last_err": pass_err, "last_put": pos_put, "if_portal": if_portal, "rangered": rangered}
            if self.board.checkPack(13, "k") and not if_portal and (ph_put := ret.get("phantom", -1)) != -1:
                phantom = more_itertools.only(t for t in self.tokens if isinstance(t, Phantom))
                if phantom is None:
                    pass_err = -10
                    continue
                if ph_put == ret["id"] and ph_put != -2:
                    pass_err = -11
                    continue
                if ph_put != -2:
                    seg_ph = tile_put.getSeg(ph_put)
                    if seg_ph is None:
                        pass_err = -11
                        continue
                    if isinstance(seg_ph, Feature) and not isinstance(seg_ph, CanScore):
                        pass_err = -11
                        continue
                    if not phantom.canPut(seg_ph) or seg_ph.occupied() or if_portal and seg_ph.closed():
                        pass_err = -11
                        continue
            if self.board.checkPack(3, "c") and ret.get("special") == "fairy":
                pos_fairy: tuple[int, int] = ret["pos"]
                if pos_fairy not in self.board.tiles:
                    pass_err = -3
                    continue
                tile_fairy = self.board.tiles[pos_fairy]
                followers = [token for token in tile_fairy.iterAllTokens() if isinstance(token, Follower) and token.player is self]
                if len(followers) == 0:
                    pass_err = -3
                    continue
                if len(followers) == 1:
                    follower = followers[0]
                else:
                    pass_err = 0
                    while 1:
                        self.board.state = State.ChoosingOwnFollower
                        ret = yield {"last_err": pass_err, "last_put": pos_fairy, "special": "fairy"}
                        if ret["id"] < 0 or ret["id"] >= len(followers):
                            pass_err = -2
                            continue
                        follower = followers[ret["id"]]
                        break
                self.board.fairy.moveTo(follower, tile_fairy)
                break
            if self.board.checkPack(3, "d") and not if_portal and ret.get("special") == "portal":
                if ph_put >= 0:
                    pass_err = -12
                    continue
                pos_portal: tuple[int, int] = ret["pos"]
                if pos_portal not in self.board.tiles or tile.addable != TileAddable.Portal:
                    pass_err = -4
                    continue
                pos_put = pos_portal
                tile_put = self.board.tiles[pos_portal]
                if_portal = True
                pass_err = 0
                continue
            if if_portal and ret["id"] == -1:
                pos_put = pos
                tile_put = tile
                if_portal = False
                pass_err = 0
                continue
            if self.board.checkPack(4, "b") and ret.get("special") == "tower":
                if ph_put >= 0:
                    pass_err = -12
                    continue
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
                    self.towerPieces -= 1
                    tower.height += 1
                    yield from self.turnCaptureTower(tower, pos_tower)
                    break
                token = self.findToken(ret["which"])
                if token is None:
                    pass_err = -1
                    continue
                if not token.canPut(tower):
                    pass_err = -2
                    continue
                self.tokens.remove(token)
                yield from token.putOn(tower)
                break
            if self.board.checkPack(12, "b") and ret.get("special") == "abbot":
                pos_abbot: tuple[int, int] = ret["pos"]
                if pos_abbot not in self.board.tiles:
                    pass_err = -8
                    continue
                tile_abbot = self.board.tiles[pos_abbot]
                abbots = [token for feature in tile_abbot.features for token in feature.tokens if isinstance(token, Abbot) and token.player is self]
                if len(abbots) == 0:
                    pass_err = -8
                    continue
                abbot = abbots[0]
                assert isinstance(abbot.parent, BaseCloister)
                score = abbot.parent.checkScore([self], True, False)[0][1]
                yield from self.addScore(score)
                abbot.putBackToHand()
                break
            if self.board.checkPack(14, "b") and not rangered and ret.get("special") == "ranger":
                pos_ranger: tuple[int, int] = ret["pos"]
                if not self.board.ranger.canMove(pos_ranger):
                    pass_err = -9
                    continue
                self.board.ranger.moveTo(pos_ranger)
                break
            if ret["id"] == -1:
                break
            seg_put: Segment | Feature | Tile = tile_put
            if 0 <= ret["id"] < (ll := len(tile_put.segments) + len(tile_put.features)):
                seg_put = tile_put.getSeg(ret["id"])
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
            if isinstance(seg_put, Flier) and ph_put >= 0:
                pass_err = -12
                continue
            if isinstance(seg_put, Feature) and not isinstance(seg_put, CanScore):
                pass_err = -2
                continue
            token = self.findToken(ret.get("which", "follower"))
            if token is None:
                pass_err = -1
                continue
            if not token.canPut(seg_put) or not isinstance(seg_put, Tile) and (isinstance(token, Follower) and seg_put.occupied() or if_portal and seg_put.closed()):
                pass_err = -2
                continue
            self.tokens.remove(token)
            yield from token.putOn(seg_put)
            put_barn = isinstance(token, Barn)
            if_flier = isinstance(seg_put, Flier)
            break
        if ph_put != -1:
            ph_portal: bool = False
            pos_put = pos
            tile_put = tile
            pass_err = 0
            while 1:
                if ph_put == -2:
                    self.board.state = State.PuttingFollower
                    ret2 = yield {"last_err": pass_err, "last_put": pos, "if_portal": ph_portal, "rangered": rangered, "special": "phantom"}
                    if self.board.checkPack(3, "d") and not ph_portal and ret2.get("special") == "portal":
                        if if_portal:
                            pass_err = -13
                            continue
                        pos_portal = ret2["pos"]
                        if pos_portal not in self.board.tiles or tile.addable != TileAddable.Portal:
                            pass_err = -4
                            continue
                        pos_put = pos_portal
                        tile_put = self.board.tiles[pos_portal]
                        ph_portal = True
                        continue
                    if not if_portal and ph_portal and ret2["id"] == -1:
                        pos_put = pos
                        tile_put = tile
                        ph_portal = False
                        continue
                    ph_put = ret2["id"]
                    if ph_put == -1:
                        break
                    seg_ph = tile_put.getSeg(ph_put)
                    if seg_ph is None:
                        pass_err = -11
                        continue

                ph_put = -2
                if phantom is None:
                    pass_err = -10
                    continue
                if isinstance(seg_ph, Flier) and if_flier:
                    pass_err = -13
                    continue
                if isinstance(seg_ph, Feature) and not isinstance(seg_ph, CanScore):
                    pass_err = -11
                    continue
                if not phantom.canPut(seg_ph) or seg_ph.occupied() or ph_portal and seg_ph.closed():
                    pass_err = -11
                    continue
                self.tokens.remove(phantom)
                yield from phantom.putOn(seg_ph)
                break
        return put_barn
    def turnCaptureTower(self, tower: 'Tower', pos: tuple[int, int]) -> 'TAsync[None]':
        followers = [token for token in self.board.tiles[pos].iterAllTokens() if isinstance(token, Follower)] + [token for dr in Dir for i in range(tower.height) if (pos[0] + dr.corr()[0] * (i + 1), pos[1] + dr.corr()[1] * (i + 1)) in self.board.tiles for token in self.board.tiles[pos[0] + dr.corr()[0] * (i + 1), pos[1] + dr.corr()[1] * (i + 1)].iterAllTokens() if isinstance(token, Follower)]
        if len(followers) == 0:
            return
        pass_err: Literal[0, -1] = 0
        while 1:
            self.board.state = State.CaptureTower
            ret = yield {"pos": pos, "last_err": pass_err}
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
                follower.parent = self
                self.prisoners.append(follower)
                yield from self.checkReturnPrisoner()
            break
    def checkReturnPrisoner(self) -> 'TAsync[None]':
        for player in self.board.players:
            if player is self:
                continue
            p = [[token for token in self.prisoners if token.player is player], [token for token in player.prisoners if token.player is self]]
            if len(p[0]) == 0 or len(p[1]) == 0:
                continue
            t = [p[0][0], p[1][0]]
            pass_err: Literal[0, -1] = 0
            c = [False, False]
            for i in range(2):
                if len(set(c.key for c in p[i])) == 1:
                    c[i] = True
                    continue
                if i == 1:
                    self.board.current_player_id = player.id
                while 1:
                    self.board.state = State.ExchangingPrisoner
                    ret = yield {"last_err": pass_err}
                    token = self.findToken(ret["which"], p[i])
                    if token is None:
                        pass_err = -1
                        continue
                    t[i] = token
                    break
                if i == 1:
                    self.board.current_player_id = self.board.current_turn_player_id
            if c[0] and c[1]:
                self.board.addLog(id="exchangePrisoner", p1=t[0], p2=t[1])
            t[0].putBackToHand()
            t[1].putBackToHand()
    def turnMoveDragon(self) -> 'TAsync[None]':
        dragon = self.board.dragon
        assert dragon.tile is not None
        pass_err: Literal[0, -1] = 0
        self.board.dragonMoved.append(dragon.tile)
        for i in range(6):
            pass_err = 0
            pos = self.board.findTilePos(dragon.tile)
            if not any(pos + dr in self.board.tiles and dragon.canMove(self.board.tiles[pos + dr]) for dr in Dir):
                break
            while 1:
                self.board.state = State.MovingDragon
                ret = yield {"last_err": pass_err, "moved_num": i}
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
    def turnScoring(self, tile: 'Tile', pos: tuple[int, int], ifBarn: bool, rangered: bool) -> 'TAsync[bool]':
        objects: list[Object] = []
        gingered: bool = False
        for seg in tile.segments:
            if seg.closed() and seg.object not in objects:
                objects.append(seg.object)
        if tile.isAbbey:
            for dir in Dir:
                for seg in self.board.tiles[pos + dir].getSideSeg(-dir):
                    if seg.closed() and seg.object not in objects:
                        objects.append(seg.object)
        for obj in objects:
            tc: list[int] = [0, 0, 0]
            if self.board.checkPack(2, 'd') and obj.type == Connectable.City:
                for seg2 in obj.segments:
                    if seg2.addable == Addable.Wine:
                        tc[0] += 1
                    elif seg2.addable == Addable.Grain:
                        tc[1] += 1
                    elif seg2.addable == Addable.Cloth:
                        tc[2] += 1
                if tc != [0, 0, 0]:
                    for i in range(3):
                        self.tradeCounter[i] += tc[i]
                    self.board.addLog(id="tradeCounter", tradeCounter=tc)
            if (yield from obj.score(ifBarn)):
                gingered = True
        for i in (-1, 0, 1):
            for j in (-1, 0, 1):
                npos = (pos[0] + i, pos[1] + j)
                if npos in self.board.tiles:
                    for feature in self.board.tiles[npos].features:
                        if isinstance(feature, CanScore) and feature.closed():
                            if (yield from feature.score(ifBarn)):
                                gingered = True
        if rangered:
            self.board.addLog(id="score", player=self, source="ranger", num=3)
            yield from self.addScore(3)
            pass_err: Literal[0, -2] = 0
            while 1:
                self.board.state = State.ChoosingPos
                ret = yield {"last_err": pass_err, "special": "ranger"}
                pos_ranger: tuple[int, int] = ret["pos"]
                if not self.board.ranger.canMove(pos_ranger):
                    pass_err = -2
                    continue
                self.board.ranger.moveTo(pos_ranger)
                break
        return gingered
    def turn(self) -> 'TAsync[None]':
        """PuttingTile：坐标+方向（-1：已有连接, -2：无法连接，-3：没有挨着，-4：未找到可赎回的囚犯，-5：余分不足，-6：河流不能回环
        -7：河流不能180度，-8：修道院和神龛不能有多个相邻，-9：必须扩张河流，-10：河流分叉必须岔开，-11：未找到礼物卡，-12：请指定使用哪张）
        ChoosingPos：选择坐标（-1：板块不存在，-2：不符合要求）
        PuttingFollower：单个板块feature+跟随者（-1：没有跟随者，-2：无法放置，-3：无法移动仙子，-4：无法使用传送门，-5：找不到高塔
        -6：高塔有人，-7：手里没有高塔片段，-8：找不到修道院长，-9：无法移动护林员，-10：没有幽灵，-11：幽灵无法放置
        -12：在高塔/传送门/飞行器时使用幽灵，-13：不能重复使用传送门/飞行器）
        ChoosingSegment：选择单个板块feature（-1：未找到片段，-2：不符合要求）
        WagonAsking：选马车（-1：没有图块，-2：图块过远，-3：无法放置）
        AbbeyAsking/FinalAbbeyAsking：询问僧院板块（-1：无法放置，-8：修道院和神龛不能有多个相邻）
        MovingDragon：询问龙（-1：无法移动）
        ChoosingOwnFollower：同一格的自己的follower【询问仙子/Cash out细化】（-1：无法移动，-2：不符合要求）
        PrincessAsking：单个object上的follower【询问公主】（-1：未找到跟随者）
        CaptureTower：询问高塔抓人（-1：未找到跟随者），ExchangingPrisoner：询问交换俘虏（-1：未找到跟随者）
        ChoosingGiftCard：使用礼物卡（-1：未找到礼物卡）
        AskingSynod：坐标+跟随者（-1：板块不存在，-2：不符合要求，-3：没有跟随者，-4：无法放置）"""
        isBegin: bool = True
        nextTurn: bool = False
        princessed: bool = False
        rangered: bool = False
        ifBarn: bool = False
        isAbbey: bool = False
        gingered: bool = False
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
                isBegin, pos, princessed, rangered = yield from self.turnPutTile(turn, isBegin)
            else:
                # ask abbey
                if self.board.checkPack(5, 'b'):
                    isBegin, isAbbey, pos = yield from self.turnAskAbbey(turn, isBegin, False)

                if not isAbbey:
                    # draw tile normally
                    isBegin = yield from self.turnDrawTile(turn, isBegin)

                    # put tile
                    isBegin, pos, princessed, rangered = yield from self.turnPutTile(turn, isBegin)

                    # builder generate a second turn
                    if turn == 0:
                        nextTurn = yield from self.turnCheckBuilder()
            tile = self.handTiles.pop(0)

            # check dragon
            if self.board.checkPack(3, "b") and tile.addable == TileAddable.Volcano:
                self.board.dragon.moveTo(tile)

            if not princessed:
                # put a follower
                ifBarn = yield from self.turnPutFollower(tile, pos, rangered)

            # move a dragon
            if self.board.checkPack(3, "b") and tile.addable == TileAddable.Dragon:
                yield from self.turnMoveDragon()

            # score
            gingered = yield from self.turnScoring(tile, pos, ifBarn, rangered)

            # move Gingerbread man
            if self.board.checkPack(14, "d") and (gingered or tile.addable == TileAddable.Gingerbread):
                yield from self.turnMoveGingerbread(gingered)

            self.board.state = State.End
            if nextTurn:
                continue
            break

    def image(self):
        no_final_score: bool = self.board.imageArgs.get("no_final_score", False)
        score_str = str(self.score)
        if not no_final_score:
            score_str += " (" + str(self.checkMeepleScoreCurrent()) + ")"
        if self.board.checkPack(2, 'd') and not no_final_score:
            trade_score = 0
            for i in range(3):
                if all(self.tradeCounter[i] >= player.tradeCounter[i] for player in self.board.players):
                    trade_score += 10
            score_str = score_str[:-1] + "+" + str(trade_score) + score_str[-1]
        if self.board.checkPack(14, 'a') and not no_final_score:
            score_str = score_str[:-1] + "+" + str(2 * len(self.gifts)) + score_str[-1]
        score_length = 120 + (45 if self.board.checkPack(2, 'd') else 0) + (30 if self.board.checkPack(14, 'a') else 0)
        length = 100 + score_length + self.board.token_length
        if self.board.checkPack(5, "b"):
            abbey_xpos = length
            length += 28
        if self.board.checkPack(4, "b"):
            tower_piece_xpos = length
            length += 40
            prisoner_xpos = length
            length += max(20 * len(player.prisoners) + sum(8 for token in player.prisoners if isinstance(token, BigFollower)) for player in self.board.players)
        if self.board.checkPack(2, "d"):
            trade_counter_xpos = length
            length += 120
        if self.board.checkPack(14, "a"):
            gift_xpos = length
            length += 28
        img = Image.new("RGBA", (length, 24))
        dr = ImageDraw.Draw(img)
        dr.text((0, 12), str(self.id + 1) + "." + self.show_name, "black", self.board.font_name, "lm")
        dr.text((100 + score_length // 2, 12), score_str, "black", self.board.font_score, "mm")
        # tokens
        self.tokens.sort(key=lambda x: x.key)
        last_key: tuple[int, int] = (-1, -2)
        for token in self.tokens:
            if token.key != last_key:
                last_key = token.key
                timg = token.image()
                this_num = len([1 for tk in self.tokens if tk.key == last_key])
                xbegin = self.board.token_pos[type(token)] + 100 + score_length
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
        # tower piece
        if self.board.checkPack(4, "b"):
            dr.text((tower_piece_xpos, 12), f"塔{self.towerPieces}", "black", self.board.font_name, "lm")
        # prisoner
        if self.board.checkPack(4, "b"):
            for token in self.prisoners:
                timg = token.image()
                img.alpha_composite(timg, (prisoner_xpos, 12 - timg.size[1] // 2))
                prisoner_xpos += timg.size[0] + 4
        # trade counter count
        if self.board.checkPack(2, "d"):
            dr.text((trade_counter_xpos, 12), f"酒{self.tradeCounter[0]}", "black", self.board.font_name, "lm")
            dr.text((trade_counter_xpos + 40, 12), f"麦{self.tradeCounter[1]}", "black", self.board.font_name, "lm")
            dr.text((trade_counter_xpos + 80, 12), f"布{self.tradeCounter[2]}", "black", self.board.font_name, "lm")
        # gift card count
        if self.board.checkPack(14, "a"):
            dr.rectangle((gift_xpos + 4, 4, gift_xpos + 20, 20), "green")
            dr.text((gift_xpos + 12, 12), str(len(self.gifts)), "white", self.board.font_name, "mm")
        return img
    def handTileImage(self):
        img = Image.new("RGBA", (80 + 96 * max(1, len(self.handTiles)), 96))
        dr = ImageDraw.Draw(img)
        if len(self.handTiles) == 0:
            dr.text((0, 48), self.show_name + "  请选择", "black", self.board.font_name, "lm")
        else:
            dr.text((0, 48), self.show_name, "black", self.board.font_name, "lm")
            font = ImageFont.truetype("msyhbd.ttc", 10)
            for i, tile in enumerate(self.handTiles):
                dr.rectangle((92 + i * 96, 12, 164 + i * 96, 84), self.tokenColor, None)
                img.paste(tile.image(), (96 + i * 96, 16))
                # text
                if len(self.handTiles) > 1:
                    dr.text((100 + i * 96, 10), chr(ord('a') + i), "black", font, "mb")
                dr.text((128 + i * 96, 10), "U", "black", font, "mb")
                dr.text((128 + i * 96, 86), "D", "black", font, "mt")
                dr.text((90 + i * 96, 48), "L", "black", font, "rm")
                dr.text((166 + i * 96, 48), "R", "black", font, "lm")
        return img

from .carcassonne import Board, Tile, Segment, Object, Feature, Token, Follower
from .carcassonne import State, Connectable, Gift, Dir, CanScore, TAsync, CantPutError
from .carcassonne import Barn, Builder, Pig, TileAddable, CitySegment, RoadSegment, AbbeyData
from .carcassonne import Phantom, Tower, Abbot, BaseCloister, Flier, BigFollower, Addable