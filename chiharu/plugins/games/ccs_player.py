from typing import Literal, Any, Sequence, Callable, Type
import more_itertools, random
from PIL import Image, ImageDraw, ImageFont

class Player:
    def __init__(self, board: 'Board', id: int, name: str) -> None:
        self.board = board
        self.id = id
        self.long_name = name
        self.name = name[:20]
        self.tokens: list[Token] = []
        self.allTokens: list[Token] = []
        self.score: int = 0
        self.handTiles: list[Tile] = []
        self.score_str: str = ""
        self.score_length: int = 0
        self.score_stat: dict[ScoreReason, int] = {s: 0 for s in ScoreReason.__members__.values()}
        self.last_pos: tuple[int, int] | None = None
        self.score2: int = 0
        self.begin_score = self.score, self.score2
        if self.board.checkPack(2, 'd'):
            self.tradeCounter = [0, 0, 0]
        if self.board.checkPack(5, 'b'):
            self.hasAbbey = True
        if self.board.checkPack(4, 'b'):
            self.towerPieces: int = 0
            self.prisoners: list[Follower] = []
        if self.board.checkPack(6, "b"):
            self.king: bool = False
        if self.board.checkPack(6, "c"):
            self.robber: bool = False
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
    def addScore(self, score: int, type: 'ScoreReason') -> 'TAsync[None]':
        if self.board.checkPack(12, "c"):
            self.board.state = State.ChoosingScoreMove
            from .ccs_helper import RecieveChoose
            ret = yield Send(0)
            assert isinstance(ret, RecieveChoose)
            if ret.chosen:
                self.score2 += score
            else:
                self.score += score
        else:
            self.score += score
        self.score_stat[type] += score
        return
    def addScoreFinal(self, score: int, type: 'ScoreReason'):
        self.score += score
        self.score_stat[type] += score
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
        if self.board.checkPack(12, "c"):
            return self.score + self.score2 + score
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

    def utilityChoosingFollower(self, special: str, criteria: 'Callable[[Token], bool] | None'=None,
            pos_beg: tuple[int, int] | None=None) -> 'TAsync[Follower | None]':
        pass_err: Literal[0, -1, -2, -3, -4] = 0
        if criteria is None:
            criteria = lambda t: True
        if pos_beg is None:
            for t in self.board.tiles.values():
                followers = [token for token in t.iterAllTokens() if isinstance(token, Follower) and token.player is self and criteria(token)]
                if len(followers) > 0:
                    break
            else:
                return None
        else:
            t = self.board.tiles[pos_beg]
            followers = [token for token in t.iterAllTokens() if isinstance(token, Follower) and token.player is self and criteria(token)]
            if len(followers) == 0:
                return None
        while 1:
            if pos_beg is None:
                self.board.state = State.ChoosingPos
                from .ccs_helper import SendChoosingPos
                ret = yield SendChoosingPos(pass_err, special)
                assert isinstance(ret, RecievePos)
                if ret.pos not in self.board.tiles:
                    pass_err = -1
                    continue
                pos = ret.pos
            else:
                pos = pos_beg
            tile = self.board.tiles[pos]
            followers = [token for token in tile.iterAllTokens() if isinstance(token, Follower) and token.player is self]
            can_choose = [token for token in followers if criteria(token)]
            if len(can_choose) == 0:
                pass_err = -2
                if pos_beg is None:
                    continue
                else:
                    return None
            if len(can_choose) == 1:
                return can_choose[0]
            pass_err = 0
            while 1:
                self.board.state = State.ChoosingOwnFollower
                from .ccs_helper import SendPosSpecial
                ret2 = yield SendPosSpecial(pass_err, pos, special)
                assert isinstance(ret2, RecieveId)
                if ret2.id < 0 or ret2.id >= len(followers):
                    pass_err = -2
                    continue
                follower = followers[ret2.id]
                if follower not in can_choose:
                    pass_err = -3
                    continue
                break
            return follower

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
                from .ccs_helper import SendAbbeyAsking
                ret = yield SendAbbeyAsking(pass_err, isBegin, turn == 1)
                isBegin = False
                if isinstance(ret, RecievePos):
                    break
                assert isinstance(ret, RecievePos)
                isAbbey = True
                self.hasAbbey = False
                pos = ret.pos
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
            from .ccs_helper import SendPuttingTile, RecievePuttingTile, RecieveId, RecieveBuyPrisoner
            ret = yield SendPuttingTile(pass_err, isBegin, turn == 1, gifted)
            assert isinstance(ret, (RecievePuttingTile, RecieveBuyPrisoner, RecieveId))
            pass_err = 0
            isBegin = False
            if self.board.checkPack(4, "b") and turn == 0 and not prisonered and isinstance(ret, RecieveBuyPrisoner):
                r = yield from self.turnExchangePrisoner(ret)
                if r < 0:
                    pass_err = r
                    continue
                prisonered = True
                continue
            if self.board.checkPack(14, "a") and not gifted and isinstance(ret, RecieveId):
                if ret.id >= len(self.gifts):
                    pass_err = -11
                    continue
                gift: Gift = self.gifts.pop(ret.id)
                from .ccs_helper import LogUseGift
                self.board.addLog(LogUseGift(gift.name, self.giftsText()))
                ret2 = yield from gift.use(self)
                self.board.giftDiscard.append(gift)
                gifted = True
                continue
            assert isinstance(ret, RecievePuttingTile)
            if ret.tilenum == -1 and len(self.handTiles) != 1:
                pass_err = -12
                continue
            pos = ret.pos
            orient = ret.orient
            tile = self.handTiles[ret.tilenum]
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
                if len(rdrs) == 2 and sides[[dr.value for dr in Dir if dr.corr() == pos or dr == Dir.RIGHT and pos == (2, 0)][0]] == Connectable.River:
                    pass_err = -10
                    continue
                if len(rdrs) == 1:
                    t: list[int] = []
                    if pos[0] <= 0: t.append(Dir.LEFT.value)
                    if pos[0] >= 0: t.append(Dir.RIGHT.value)
                    if pos[1] <= 0: t.append(Dir.UP.value)
                    if pos[1] >= 0: t.append(Dir.DOWN.value)
                    if rdrs[0] not in t:
                        pass_err = -7
                        continue
            break
        tile.turn(orient)
        self.board.tiles[pos] = tile
        self.last_pos = pos
        for dr in Dir:
            if pos + dr in self.board.tiles:
                self.board.tiles[pos + dr].addConnect(tile, -dr)
        if tile.addable == TileAddable.Hill and self.board.checkPack(9, 'c') and len(self.board.deck) > 0:
            self.board.hill_tiles.append(self.board.drawTile())
        rangered: bool = self.board.checkPack(14, "b") and self.board.ranger.pos == pos
        princessed: bool = False
        if self.board.checkPack(3, "e") and (seg := more_itertools.only(seg for seg in tile.segments if seg.addable == Addable.Princess)):
            princessed = yield from self.turnAskPrincess(seg)
        if self.board.checkPack(13, 'd') and tile.addable == TileAddable.Gold:
            yield from self.turnPutGold(pos)
        if self.board.checkPack(14, "a"):
            for segment in tile.segments:
                if isinstance(segment, (RoadSegment, CitySegment)) and len(l := segment.object.checkPlayer(True)) > 0 and self not in l:
                    if gift := self.board.drawGift():
                        from .ccs_helper import LogDrawGift
                        self.board.addLog(LogDrawGift(gift.name, self.giftsText()))
                        self.gifts.append(gift)
                    break
        if len(self.handTiles) > 1:
            for tile2 in self.handTiles:
                if tile2 is not tile:
                    self.board.deck.append(tile2)
            self.handTiles = [tile]
            random.shuffle(self.board.deck)
        return isBegin, pos, princessed, rangered
    def turnExchangePrisoner(self, ret: 'RecieveBuyPrisoner') -> 'TAsync[Literal[0, -4, -5]]':
        if self.score < 3:
            return -5
        player_id: int = ret.player_id
        if player_id < 0 or player_id >= len(self.board.players):
            return -4
        player: 'Player' = self.board.players[player_id]
        token = player.findToken(ret.follower)
        if token is None:
            return -4
        yield from self.addScore(-3, ScoreReason.PayPrisoner)
        yield from player.addScore(3, ScoreReason.PayPrisoner)
        player.prisoners.remove(token)
        self.tokens.append(token)
        return 0
    def turnAskPrincess(self, seg: 'Segment') -> 'TAsync[bool]':
        followers = [token for token in seg.object.iterTokens() if isinstance(token, Follower) and isinstance(token.parent, Segment)]
        if len(followers) == 0:
            return False
        pass_err = 0
        while 1:
            self.board.state = State.PrincessAsking
            from .ccs_helper import SendPrincess
            ret = yield SendPrincess(pass_err, seg.object)
            if isinstance(ret, RecieveReturn):
                break
            assert isinstance(ret, RecieveId)
            id: int = ret.id
            if id >= 0 and id < len(followers):
                followers[id].putBackToHand(HomeReason.Princess)
                seg.object.checkRemoveBuilderAndPig(HomeReason.Princess)
                return True
            pass_err = -1
        return False
    def turnPutGold(self, pos: tuple[int, int]) -> 'TAsync[None]':
        tile = self.board.tiles[pos]
        golds = [token for token in self.board.tokens if isinstance(token, Gold)]
        yield from golds[0].putOn(tile)
        self.board.tokens.remove(golds[0])
        adj = [(pos[0] + i[0], pos[1] + i[1]) for i in ((0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (-1, 1)) if (pos[0] + i[0], pos[1] + i[1]) in self.board.tiles]
        if len(adj) == 1:
            yield from golds[1].putOn(self.board.tiles[adj[0]])
        else:
            pass_err: Literal[0, -1, -2] = 0
            while 1:
                self.board.state = State.ChoosingPos
                from .ccs_helper import SendChoosingPos
                ret = yield SendChoosingPos(pass_err, 'gold')
                assert isinstance(ret, RecievePos)
                if ret.pos not in self.board.tiles:
                    pass_err = -1
                    continue
                if ret.pos not in adj:
                    pass_err = -2
                    continue
                tile2 = self.board.tiles[ret.pos]
                yield from golds[1].putOn(tile2)
                break
        self.board.tokens.remove(golds[1])

    def turnCheckBuilder(self) -> 'TAsync[bool]':
        if not self.board.checkPack(2, 'b'):
            return False
        for seg in self.handTiles[0].segments:
            for token in seg.object.iterTokens():
                if token.player is self and isinstance(token, Builder):
                    token.ability += 1
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
            from .ccs_helper import SendPuttingFollower
            ret = yield SendPuttingFollower(pass_err, pos_put, if_portal, rangered)
            assert isinstance(ret, (RecieveReturn, RecievePuttingFollower))
            if isinstance(ret, RecieveReturn):
                if if_portal:
                    pos_put = pos
                    tile_put = tile
                    if_portal = False
                    pass_err = 0
                    continue
                break
            if self.board.checkPack(13, "k") and not if_portal and (ph_put := ret.phantom) != -1:
                r = yield from self.turnCheckPhantom(ret, ph_put, tile_put, if_portal)
                if pass_err < 0:
                    continue
            if self.board.checkPack(3, "c") and ret.special == "fairy":
                pass_err = yield from self.turnMovingFairy(ret)
                if pass_err < 0:
                    continue
                break
            if self.board.checkPack(3, "d") and not if_portal and ret.special == "portal":
                if ph_put >= 0:
                    pass_err = -12
                    continue
                pos_portal: tuple[int, int] = ret.pos
                if pos_portal not in self.board.tiles or tile.addable != TileAddable.Portal:
                    pass_err = -4
                    continue
                pos_put = pos_portal
                tile_put = self.board.tiles[pos_portal]
                if_portal = True
                pass_err = 0
                continue
            if self.board.checkPack(4, "b") and ret.special == "tower":
                if ph_put >= 0:
                    pass_err = -12
                    continue
                yield from self.turnCheckTower(ret)
                break
            if self.board.checkPack(10, "c") and ret.special == "acrobat":
                pass_err = yield from self.turnAcrobat(pos, ret)
                if pass_err < 0:
                    continue
                break
            if self.board.checkPack(12, "b") and ret.special == "abbot":
                pass_err = yield from self.turnMovingAbbot(ret)
                if pass_err < 0:
                    continue
                break
            if self.board.checkPack(13, "j") and tile.addable == TileAddable.Festival and ret.special == "festival":
                pass_err = yield from self.turnMovingFestival(ret)
                if pass_err < 0:
                    continue
                break
            if self.board.checkPack(14, "b") and not rangered and ret.special == "ranger":
                pos_ranger: tuple[int, int] = ret.pos
                if not self.board.ranger.canMove(pos_ranger):
                    pass_err = -9
                    continue
                self.board.ranger.moveTo(pos_ranger)
                break
            seg_put: Segment | Feature | Tile = tile_put
            if (ll := len(tile_put.segments) + len(tile_put.features)) > ret.id >= 0:
                seg_put = tile_put.getSeg(ret.id)
            elif self.board.checkPack(5, "e") and not tile_put.isAbbey and ll <= ret.id < ll + 4 and (pos := self.board.findTilePos(tile_put)):
                # for barn
                offset = [(-1, -1), (0, -1), (-1, 0), (0, 0)][ret.id - ll]
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
            token = self.findToken(ret.which)
            if token is None:
                pass_err = -1
                continue
            if not token.canPut(seg_put) or not isinstance(seg_put, Tile) and (isinstance(token, Follower) and seg_put.occupied() or if_portal and not seg_put.canPut()):
                pass_err = -2
                continue
            self.tokens.remove(token)
            yield from token.putOn(seg_put)
            if isinstance(token, Shepherd):
                token.grow()
                if isinstance(token.parent, FieldSegment) and all(seg.selfClosed() for seg in token.parent.object.segments):
                    yield from token.score()
            put_barn = isinstance(token, Barn)
            if_flier = isinstance(seg_put, Flier)
            break
        if ph_put != -1:
            yield from self.turnPuttingPhantom(pos, tile, if_portal, if_flier, rangered, ph_put)
        return put_barn
    def turnCheckPhantom(self, ret: 'RecievePuttingFollower', ph_put: int,
                         tile_put: 'Tile', if_portal: bool) -> 'TAsync[Literal[0, -10, -11]]':
        phantom = more_itertools.only(t for t in self.tokens if isinstance(t, Phantom))
        if phantom is None:
            return -10
        if isinstance(ret, RecievePuttingFollower) and ph_put == ret.id:
            return -11
        if ph_put != -2:
            seg_ph = tile_put.getSeg(ph_put)
            if seg_ph is None:
                return -11
            if isinstance(seg_ph, Feature) and not isinstance(seg_ph, CanScore):
                return -11
            if not phantom.canPut(seg_ph) or seg_ph.occupied() or if_portal and not seg_ph.canPut():
                return -11
        return 0
        yield {}
    def turnMovingFairy(self, ret: 'RecievePuttingFollower') -> 'TAsync[Literal[0, -3]]':
        pos_fairy: tuple[int, int] = ret.pos
        if pos_fairy not in self.board.tiles:
            return -3
        follower = yield from self.utilityChoosingFollower('fairy', None, pos_fairy)
        if follower is None:
            return -3
        tile_fairy = self.board.tiles[pos_fairy]
        self.board.fairy.moveTo(follower, tile_fairy)
        return 0
    def turnPuttingPhantom(self, pos: tuple[int, int], tile: 'Tile',
                           if_portal: bool, if_flier: bool, rangered: bool, ph_put: int) -> 'TAsync[None]':
        ph_portal: bool = False
        pos_put = pos
        tile_put = tile
        pass_err = 0
        while 1:
            if ph_put == -2:
                self.board.state = State.PuttingFollower
                from .ccs_helper import SendPuttingFollower
                ret = yield SendPuttingFollower(pass_err, pos_put, ph_portal, rangered, "phantom")
                assert isinstance(ret, (RecieveReturn, RecievePuttingFollower))
                if isinstance(ret, RecieveReturn):
                    if not if_portal and ph_portal:
                        pos_put = pos
                        tile_put = tile
                        ph_portal = False
                        continue
                    break
                if self.board.checkPack(3, "d") and not ph_portal and isinstance(ret, RecievePuttingFollower) and ret.special == "portal":
                    if if_portal:
                        pass_err = -13
                        continue
                    pos_portal = ret.pos
                    if pos_portal not in self.board.tiles or tile.addable != TileAddable.Portal:
                        pass_err = -4
                        continue
                    pos_put = pos_portal
                    tile_put = self.board.tiles[pos_portal]
                    ph_portal = True
                    continue
                ph_put = ret.id
            seg_ph = tile_put.getSeg(ph_put)
            if seg_ph is None:
                pass_err = -11
                continue

            ph_put = -2
            phantom = more_itertools.only(t for t in self.tokens if isinstance(t, Phantom))
            if phantom is None:
                pass_err = -10
                continue
            if isinstance(seg_ph, Flier) and if_flier:
                pass_err = -13
                continue
            if isinstance(seg_ph, Feature) and not isinstance(seg_ph, CanScore):
                pass_err = -11
                continue
            if not phantom.canPut(seg_ph) or seg_ph.occupied() or ph_portal and not seg_ph.canPut():
                pass_err = -11
                continue
            self.tokens.remove(phantom)
            yield from phantom.putOn(seg_ph)
            break
    def turnCheckTower(self, ret: 'RecievePuttingFollower') -> 'TAsync[Literal[0, -1, -2, -5, -6, -7, -12]]':
        pos_tower: tuple[int, int] = ret.pos
        if pos_tower not in self.board.tiles:
            return -5
        tile_tower = self.board.tiles[pos_tower]
        tower = more_itertools.only(feature for feature in tile_tower.features if isinstance(feature, Tower))
        if tower is None:
            return -5
        if len(tower.tokens) != 0:
            return -6
        if ret.which == '':
            if self.towerPieces == 0:
                return -7
            self.towerPieces -= 1
            tower.height += 1
            yield from self.turnCaptureTower(tower, pos_tower)
            return 0
        token = self.findToken(ret.which)
        if token is None:
            return -1
        if not token.canPut(tower):
            return -2
        self.tokens.remove(token)
        yield from token.putOn(tower)
        return 0
    def turnMovingAbbot(self, ret: 'RecievePuttingFollower') -> 'TAsync[Literal[0, -8]]':
        pos_abbot: tuple[int, int] = ret.pos
        if pos_abbot not in self.board.tiles:
            return -8
        tile_abbot = self.board.tiles[pos_abbot]
        abbots = [token for feature in tile_abbot.features for token in feature.tokens if isinstance(token, Abbot) and token.player is self]
        if len(abbots) == 0:
            return -8
        abbot = abbots[0]
        assert isinstance(abbot.parent, BaseCloister)
        scores = abbot.parent.checkPlayerAndScore(False, False)
        l = [s for p, s in scores if p is self]
        if len(l) != 0:
            yield from self.addScore(l[0], type=abbot.parent.scoreType())
        abbot.putBackToHand(HomeReason.Abbot)
        return 0
    def turnAcrobat(self, pos: tuple[int, int], ret: 'RecievePuttingFollower') -> 'TAsync[Literal[0, -1, -15]]':
        pos2: tuple[int, int] = ret.pos
        if pos2 not in self.board.tiles:
            return -15
        tile = self.board.tiles[pos2]
        acrobats = [feature for feature in tile.features if isinstance(feature, Acrobat)]
        if len(acrobats) == 0:
            return -15
        acrobat = acrobats[0]
        if len(acrobat.tokens) < 3:
            if pos2[0] - pos[0] not in (-1, 0, 1) or pos2[1] - pos[1] not in (-1, 0, 1):
                return -15
            token = self.findToken("follower")
            if token is None:
                return -1
            self.tokens.remove(token)
            yield from token.putOn(acrobat)
        else:
            yield from acrobat.score(True, False)
            for token in acrobat.tokens:
                token.putBackToHand()
        return 0
    def turnMovingFestival(self, ret: 'RecievePuttingFollower') -> 'TAsync[Literal[0, -14]]':
        pos: tuple[int, int] = ret.pos
        if pos not in self.board.tiles:
            return -14
        tile = self.board.tiles[pos]
        al = [token for token in tile.iterAllTokens()] + [token for token in tile.tokens] + [token for seg in tile.segments for token in seg.object.tokens]
        can_remove = [token for token in al if token.player is self]
        if len(can_remove) == 0:
            return -14
        if len(can_remove) == 1:
            to_remove = can_remove[0]
        else:
            pass_err: Literal[0, -1, -2] = 0
            while 1:
                self.board.state = State.ChoosingTileFigure
                from .ccs_helper import SendPosSpecial
                ret2 = yield SendPosSpecial(pass_err, pos, "festival")
                assert isinstance(ret2, RecieveId)
                if ret2.id < 0 or ret2.id >= len(al):
                    pass_err = -1
                    continue
                to_remove = al[ret2.id]
                if to_remove not in can_remove:
                    pass_err = -2
                    continue
                break
        to_remove.putBackToHand(HomeReason.Festival)
        return 0
    def turnCaptureTower(self, tower: 'Tower', pos: tuple[int, int]) -> 'TAsync[None]':
        followers = [token for token in self.board.tiles[pos].iterAllTokens() if isinstance(token, Follower)] + [token for dr in Dir for i in range(tower.height) if (pos[0] + dr.corr()[0] * (i + 1), pos[1] + dr.corr()[1] * (i + 1)) in self.board.tiles for token in self.board.tiles[pos[0] + dr.corr()[0] * (i + 1), pos[1] + dr.corr()[1] * (i + 1)].iterAllTokens() if isinstance(token, Follower)]
        if len(followers) == 0:
            return
        pass_err: Literal[0, -1] = 0
        while 1:
            self.board.state = State.CaptureTower
            from .ccs_helper import SendPos
            ret = yield SendPos(pass_err, pos)
            if isinstance(ret, RecieveReturn):
                break
            assert isinstance(ret, RecieveId)
            id: int = ret.id
            if id < 0 or id >= len(followers):
                pass_err = -1
                continue
            follower = followers[id]
            if follower.player is self:
                follower.putBackToHand(HomeReason.Tower)
            else:
                follower.remove(None)
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
                    from .ccs_helper import Send, RecieveWhich
                    ret = yield Send(pass_err)
                    assert isinstance(ret, RecieveWhich)
                    token = self.findToken(ret.which, p[i])
                    if token is None:
                        pass_err = -1
                        continue
                    t[i] = token
                    break
                if i == 1:
                    self.board.current_player_id = self.board.current_turn_player_id
            if c[0] and c[1]:
                from .ccs_helper import LogExchangePrisoner
                assert isinstance(t[0].player, Player)
                assert isinstance(t[1].player, Player)
                self.board.addLog(LogExchangePrisoner(t[1].player.long_name, t[0].player.long_name))
            t[0].putBackToHand(HomeReason.Tower)
            t[1].putBackToHand(HomeReason.Tower)

    def turnCheckShepherd(self, tile: 'Tile') -> 'TAsync[None]':
        shepherd: Shepherd | None = None
        for seg in tile.segments:
            for token in seg.object.iterTokens():
                if token.player is self and isinstance(token, Shepherd):
                    shepherd = token
                    break
            else:
                continue
            break
        if shepherd is None:
            return
        self.board.state = State.ChoosingShepherd
        from .ccs_helper import RecieveChoose
        ret = yield Send(0)
        assert isinstance(ret, RecieveChoose)
        if not ret.chosen:
            shepherd.grow()
        else:
            yield from shepherd.score()
        if isinstance(shepherd.parent, FieldSegment) and all(seg.selfClosed() for seg in shepherd.parent.object.segments):
            yield from shepherd.score()

    def turnMoveDragon(self) -> 'TAsync[None]':
        dragon = self.board.dragon
        assert dragon.tile is not None
        pass_err: Literal[0, -1] = 0
        self.board.dragonMoved.append(dragon.tile)
        for i in range(6):
            pass_err = 0
            pos = self.board.findTilePos(dragon.tile)
            adj = [dr for dr in Dir if pos + dr in self.board.tiles and dragon.canMove(self.board.tiles[pos + dr])]
            if len(adj) == 0:
                break
            elif len(adj) == 1:
                from .ccs_helper import LogDragonMove
                self.board.addLog(LogDragonMove(self.board.current_player.long_name, dr))
                dr: Dir = adj[0]
            else:
                while 1:
                    self.board.state = State.MovingDragon
                    from .ccs_helper import SendInt, RecieveDir
                    ret = yield SendInt(pass_err, i)
                    assert isinstance(ret, RecieveDir)
                    dr = ret.dir
                    if pos + dr not in self.board.tiles or not dragon.canMove(self.board.tiles[pos + dr]):
                        pass_err = -1
                        continue
                    break
            dragon.moveTo(self.board.tiles[pos + dr])
            self.board.dragonMoved.append(dragon.tile)
            self.board.nextAskingPlayer()
        self.board.current_player_id = self.board.current_turn_player_id
        self.board.dragonMoved = []
    def turnMoveWagon(self, objects: 'list[CanScore]') -> 'TAsync[None]':
        if not self.board.checkPack(5, "d"):
            return
        to_remove: list[Wagon] = [token for obj in objects for token in obj.iterTokens() if isinstance(token, Wagon)]
        to_remove.sort(key=lambda token: ((0, token.player.id) if token.player.id >= self.board.current_player_id else (1, token.player.id)) if isinstance(token.player, Player) else (-1, -1))
        for wagon in to_remove:
            if not isinstance(wagon.parent, (Segment, Monastry)) or (pos := self.board.findTilePos(wagon.parent.tile)) is None:
                continue
            assert isinstance(wagon.player, Player)
            self.board.current_player_id = wagon.player.id
            pass_err: Literal[0, -1, -2, -3] = 0
            while 1:
                self.board.state = State.WagonAsking
                from .ccs_helper import SendMovingWagon, RecieveWagon
                ret = yield SendMovingWagon(pass_err, pos, wagon.player.id)
                if isinstance(ret, RecieveReturn):
                    break
                assert isinstance(ret, RecieveWagon)
                pos_put: tuple[int, int] = ret.pos
                if pos_put not in self.board.tiles:
                    pass_err = -1
                    continue
                if pos_put[0] - pos[0] not in (-1, 0, 1) or pos_put[1] - pos[1] not in (-1, 0, 1):
                    pass_err = -2
                    continue
                tile = self.board.tiles[pos_put]
                seg_put = tile.getSeg(ret.seg)
                if seg_put is None:
                    pass_err = -3
                    continue
                if (isinstance(seg_put, Feature) and not isinstance(seg_put, Monastry)):
                    pass_err = -3
                    continue
                if not seg_put.canPut() or seg_put.occupied() or not wagon.canPut(seg_put):
                    pass_err = -3
                    continue
                wagon.remove(None)
                wagon.ability += 1
                yield from wagon.putOn(seg_put)
                break
        self.board.current_player_id = self.board.current_turn_player_id
    def turnChooseGold(self, objects: 'list[CanScore]') -> 'TAsync[None]':
        players: 'dict[Player, list[Gold]]' = {}
        all_golds: list[Gold] = []
        for obj in objects:
            golds: list[Gold] = []
            for tile in obj.getTile():
                for token in tile.tokens:
                    if isinstance(token, Gold):
                        golds.append(token)
            if len(golds) == 0:
                continue
            for player in (l := obj.checkPlayer(True)):
                if player not in players:
                    players[player] = []
                for gold in golds:
                    if gold not in players[player]:
                        players[player].append(gold)
            if len(l) > 0:
                for gold in golds:
                    if gold not in all_golds:
                        all_golds.append(gold)
        num = len(all_golds)
        if num == 0 or len(players) == 0:
            return
        if len(players) == 1:
            for player in players:
                for gold in players[player]:
                    gold.remove(None)
                    player.tokens.append(gold)
        else:
            for i in range(num):
                while self.board.current_player not in players or len(players[self.board.current_player]) == 0:
                    self.board.nextAskingPlayer()
                pass_err: Literal[0, -1, -2, -3] = 0
                while 1:
                    self.board.state = State.ChoosingPos
                    from .ccs_helper import SendChoosingPos
                    ret = yield SendChoosingPos(pass_err, "gold_take")
                    assert isinstance(ret, RecievePos)
                    if ret.pos not in self.board.tiles:
                        pass_err = -1
                        continue
                    tile = self.board.tiles[ret.pos]
                    golds = [token for token in tile.tokens if isinstance(token, Gold)]
                    if len(golds) == 0:
                        pass_err = -2
                        continue
                    gold = golds[0]
                    if gold not in players[self.board.current_player]:
                        pass_err = -3
                        continue
                    for l2 in players.values():
                        if gold in l2:
                            l2.remove(gold)
                    gold.remove(None)
                    self.board.current_player.tokens.append(gold)
                    break
                self.board.nextAskingPlayer()
            self.board.current_player_id = self.board.current_turn_player_id
    def turnScoring(self, tile: 'Tile', pos: tuple[int, int], ifBarn: bool, rangered: bool) -> 'TAsync[bool]':
        objects: list[CanScore] = []
        gingered: bool = False
        for seg in tile.segments:
            if seg.closed() and seg.object not in objects:
                objects.append(seg.object)
        if tile.isAbbey:
            for dir in Dir:
                for seg in self.board.tiles[pos + dir].getSideSeg(-dir):
                    if seg.closed() and seg.object not in objects:
                        objects.append(seg.object)
        for i in (-1, 0, 1):
            for j in (-1, 0, 1):
                npos = (pos[0] + i, pos[1] + j)
                if npos in self.board.tiles:
                    for feature in self.board.tiles[npos].features:
                        if isinstance(feature, CanScore) and feature.closed():
                            objects.append(feature)
        if self.board.checkPack(13, 'd'):
            yield from self.turnChooseGold(objects)
        for obj in objects:
            if isinstance(obj, Object):
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
                        from .ccs_helper import LogTradeCounter
                        self.board.addLog(LogTradeCounter(tc))
                if self.board.checkPack(6, 'b') and obj.type == Connectable.City:
                    count = obj.checkTile()
                    if count > self.board.king.max:
                        self.board.king.max = count
                        self.board.king.remove(None)
                        yield from self.board.king.putOn(obj.segments[0])
                        for player in self.board.players:
                            player.king = False
                        self.king = True
                    if obj not in self.board.king.complete_citys:
                        self.board.king.complete_citys.append(obj)
                if self.board.checkPack(6, 'c') and obj.type == Connectable.Road:
                    count = obj.checkTile()
                    if count > self.board.robber.max:
                        self.board.robber.max = count
                        self.board.robber.remove(None)
                        yield from self.board.robber.putOn(obj.segments[0])
                        for player in self.board.players:
                            player.robber = False
                        self.robber = True
                    if obj not in self.board.robber.complete_roads:
                        self.board.robber.complete_roads.append(obj)
            if (yield from obj.score(ifBarn)):
                gingered = True
        yield from self.turnMoveWagon(objects)
        for obj in objects:
            obj.removeAllFollowers(HomeReason.Score)
        if self.board.checkPack(10, 'b'):
            tops = [f for f in tile.features if isinstance(f, Circus)]
            if len(tops) > 0:
                top = tops[0]
                yield from self.board.bigtop.score()
                self.board.bigtop.remove(None)
                yield from self.board.bigtop.putOn(top)
        if rangered:
            from .ccs_helper import LogScore
            self.board.addLog(LogScore(self.long_name, "ranger", 3))
            yield from self.addScore(3, type=ScoreReason.Ranger)
            pass_err: Literal[0, -2] = 0
            while 1:
                self.board.state = State.ChoosingPos
                from .ccs_helper import SendChoosingPos
                ret = yield SendChoosingPos(pass_err, "ranger")
                assert isinstance(ret, RecievePos)
                if not self.board.ranger.canMove(ret.pos):
                    pass_err = -2
                    continue
                self.board.ranger.moveTo(ret.pos)
                break
        return gingered

    def turnMessenger(self) -> 'TAsync[bool]':
        extra: bool = False
        while 1:
            if not (self.score % 5 == 0 and self.score != self.begin_score[0] or self.score2 % 5 == 0 and self.score2 != self.begin_score[1]):
                return extra
            self.begin_score = self.score, self.score2
            mes = self.board.drawMessenger()
            if mes is None:
                return extra
            self.board.state = State.ChoosingMessenger
            from .ccs_helper import SendInt, RecieveChoose
            ret = yield SendInt(0, mes.id)
            assert isinstance(ret, RecieveChoose)
            if ret.chosen:
                extra = yield from mes.use()
            else:
                yield from self.addScore(2, ScoreReason.Messenger)
        return extra
    def turnMoveGingerbread(self, complete: bool) -> 'TAsync[None]':
        ginger = self.board.gingerbread
        for t in self.board.tiles.values():
            citys = [segment for segment in t.segments if isinstance(segment, CitySegment) and not segment.closed() and ginger.canPut(segment)]
            if len(citys) > 0:
                break
        else:
            if complete:
                ginger.putBackToHand(HomeReason.Score)
            return
        pass_err: Literal[0, -1, -2] = 0
        while 1:
            self.board.state = State.ChoosingPos
            from .ccs_helper import SendChoosingPos
            ret = yield SendChoosingPos(pass_err, "gingerbread")
            assert isinstance(ret, RecievePos)
            if ret.pos not in self.board.tiles:
                pass_err = -1
                continue
            tile = self.board.tiles[ret.pos]
            citys = [segment for segment in tile.segments if isinstance(segment, CitySegment) and not segment.closed() and ginger.canPut(segment)]
            if len(citys) == 0:
                pass_err = -2
                continue
            city = citys[0]
            if len(citys) >= 2:
                pass_err = 0
                while 1:
                    self.board.state = State.ChoosingSegment
                    from .ccs_helper import SendPosSpecial
                    ret2 = yield SendPosSpecial(pass_err, ret.pos, "gingerbread")
                    assert isinstance(ret2, RecieveId)
                    s = tile.getSeg(ret2.id)
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
            ginger.remove(None)
            yield from ginger.putOn(city)
            break
    def turnCropCircle(self, tile: 'Tile') -> 'TAsync[None]':
        if tile.addable == TileAddable.Rake:
            check: Type[Segment] = FieldSegment
        elif tile.addable == TileAddable.Club:
            check = RoadSegment
        elif tile.addable == TileAddable.Shield:
            check = CitySegment
        else:
            return
        
        self.board.state = State.ChoosingCropCircle
        from .ccs_helper import RecieveChoose
        ret = yield Send(0)
        assert isinstance(ret, RecieveChoose)
        for _ in range(len(self.board.players)):
            self.board.nextAskingPlayer()
            user = self.board.current_player
            if not ret.chosen:
                follower = yield from user.utilityChoosingFollower("cropremove", lambda t: isinstance(t.parent, check))
                if follower is not None:
                    follower.putBackToHand(HomeReason.CropCircle)
                continue

            pass_err: Literal[0, -1, -2, -3] = 0
            while 1:
                self.board.state = State.CropAddFollower
                from .ccs_helper import RecievePosWhich
                ret2 = yield Send(pass_err)
                if isinstance(ret2, RecieveReturn):
                    break
                assert isinstance(ret2, RecievePosWhich)
                if ret2.pos not in self.board.tiles:
                    pass_err = -1
                    continue
                token_put = user.findToken(ret2.which)
                if token_put is None or check not in token_put.canPutTypes:
                    pass_err = -3
                    continue
                tile = self.board.tiles[ret2.pos]
                followers = [token for token in tile.iterAllTokens() if isinstance(token, Follower) and token.player is user]
                can_choose = [token for token in followers if isinstance(token.parent, check)]
                if len(can_choose) == 0:
                    pass_err = -2
                    continue
                if len(can_choose) == 1:
                    follower = can_choose[0]
                else:
                    pass_err = 0
                    while 1:
                        self.board.state = State.ChoosingOwnFollower
                        from .ccs_helper import SendPosSpecial
                        ret3 = yield SendPosSpecial(pass_err, ret2.pos, "cropadd")
                        assert isinstance(ret3, RecieveId)
                        if ret3.id < 0 or ret3.id >= len(followers):
                            pass_err = -2
                            continue
                        follower = followers[ret3.id]
                        if follower not in can_choose:
                            pass_err = -3
                            continue
                        break
                assert isinstance(follower.parent, check)
                if not token_put.canPut(follower.parent):
                    break
                user.tokens.remove(token_put)
                yield from token_put.putOn(follower.parent)
                break

        self.board.current_player_id = self.board.current_turn_player_id

    def turn(self) -> 'TAsync[None]':
        """PuttingTile：坐标+方向（-1：已有连接, -2：无法连接，-3：没有挨着，-4：未找到可赎回的囚犯，-5：余分不足，-6：河流不能回环
        -7：河流不能180度，-8：修道院和神龛不能有多个相邻，-9：必须扩张河流，-10：河流分叉必须岔开，-11：未找到礼物卡，-12：请指定使用哪张）
        ChoosingPos：选择坐标（-1：板块不存在，-2：不符合要求，-3：不是你的金块）
        PuttingFollower：单个板块feature+跟随者（-1：没有跟随者，-2：无法放置，-3：无法移动仙子，-4：无法使用传送门，-5：找不到高塔
        -6：高塔有人，-7：手里没有高塔片段，-8：找不到修道院长，-9：无法移动护林员，-10：没有幽灵，-11：幽灵无法放置
        -12：在高塔/传送门/飞行器时使用幽灵，-13：不能重复使用传送门/飞行器，-14：无法移除（节日），-15：无法放置杂技）
        ChoosingSegment：选择单个板块feature（-1：未找到片段，-2：不符合要求）
        WagonAsking：选马车（-1：没有图块，-2：图块过远，-3：无法放置）
        AbbeyAsking/FinalAbbeyAsking：询问僧院板块（-1：无法放置，-8：修道院和神龛不能有多个相邻）
        MovingDragon：询问龙（-1：无法移动）
        ChoosingOwnFollower：同一格的自己的follower【询问仙子/Cash out细化】（-1：无法移动，-2：不符合要求）
        PrincessAsking：单个object上的follower【询问公主】（-1：未找到跟随者）
        CaptureTower：询问高塔抓人（-1：未找到跟随者），ExchangingPrisoner：询问交换俘虏（-1：未找到跟随者）
        ChoosingGiftCard：使用礼物卡（-1：未找到礼物卡）
        AskingSynod：坐标+跟随者（-1：板块不存在，-2：不符合要求，-3：没有跟随者，-4：无法放置）
        ChoosingTileFigure：选择图块上的任意figure（-1：未找到，-2：不符合要求）
        ChoosingShepherd：选择牧羊人动作
        ChoosingScoreMove：选择计分人走哪个
        ChoosingMessenger：选择圣旨是否使用"""
        isBegin: bool = True
        turn: int = 0
        remainTurns: int = 1
        buildered: bool = False
        messengered: bool = False
        princessed: bool = False
        rangered: bool = False
        ifBarn: bool = False
        isAbbey: bool = False
        gingered: bool = False
        self.begin_score = self.score, self.score2
        # check fairy
        if self.board.checkPack(3, "c") and self.board.fairy.follower is not None and self.board.fairy.follower.player is self:
            self.board.fairy.follower.fairy_1 += 1
            from .ccs_helper import LogScore
            self.board.addLog(LogScore(self.long_name, "fairy", 1))
            yield from self.addScore(1, type=ScoreReason.Fairy)

        while remainTurns > 0:
            # draw river
            if len(self.board.riverDeck) != 0:
                isBegin = yield from self.turnDrawRiver(isBegin)
                if len(self.board.riverDeck) == 0 and self.handTiles[0].addable == TileAddable.Volcano:
                    remainTurns += 1

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
                    if not buildered and (yield from self.turnCheckBuilder()):
                        remainTurns += 1
                        buildered = True
            tile = self.handTiles.pop(0)

            # check dragon
            if self.board.checkPack(3, "b") and tile.addable == TileAddable.Volcano:
                self.board.dragon.moveTo(tile)

            if not princessed:
                # put a follower
                ifBarn = yield from self.turnPutFollower(tile, pos, rangered)

            if self.board.checkPack(9, "b"):
                yield from self.turnCheckShepherd(tile)

            # move a dragon
            if self.board.checkPack(3, "b") and tile.addable == TileAddable.Dragon:
                yield from self.turnMoveDragon()

            # score
            gingered = yield from self.turnScoring(tile, pos, ifBarn, rangered)

            # messenger
            if self.board.checkPack(12, "c") and not messengered and (yield from self.turnMessenger()):
                remainTurns += 1
                messengered = True

            # move Gingerbread man
            if self.board.checkPack(14, "d") and (gingered or tile.addable == TileAddable.Gingerbread):
                yield from self.turnMoveGingerbread(gingered)

            # crop circle
            if self.board.checkPack(12, "f"):
                yield from self.turnCropCircle(tile)

            self.board.state = State.End
            remainTurns -= 1
            turn += 1

    def image_pre(self):
        no_final_score: bool = self.board.imageArgs.get("no_final_score", False)
        score_str = str(self.score)
        if self.board.checkPack(12, "c"):
            score_str += "+" + str(self.score2)
        if not no_final_score:
            score_str += " (" + str(self.checkMeepleScoreCurrent()) + ")"
            if self.board.checkPack(2, 'd'):
                trade_score = 0
                for i in range(3):
                    if all(self.tradeCounter[i] >= player.tradeCounter[i] for player in self.board.players):
                        trade_score += 10
                score_str = score_str[:-1] + "+" + str(trade_score) + score_str[-1]
            if self.board.checkPack(3, 'c'):
                score_str = score_str[:-1] + "+" + str(3 if self.board.fairy.follower is not None and self.board.fairy.follower.player is self else 0) + score_str[-1]
            if self.board.checkPack(6, 'b'):
                score_str = score_str[:-1] + "+" + str(len(self.board.king.complete_citys) if self.king else 0) + score_str[-1]
            if self.board.checkPack(6, 'c'):
                score_str = score_str[:-1] + "+" + str(len(self.board.robber.complete_roads) if self.robber else 0) + score_str[-1]
            if self.board.checkPack(13, 'd'):
                gold_num = sum(1 for token in self.tokens if isinstance(token, Gold))
                score_str = score_str[:-1] + "+" + str(Gold.score(gold_num)) + score_str[-1]
            if self.board.checkPack(14, 'a') and not no_final_score:
                score_str = score_str[:-1] + "+" + str(2 * len(self.gifts)) + score_str[-1]
        self.score_str = score_str
        self.score_length = int(self.board.font_score.getlength(score_str)) + 20
    def image(self, score_length: int):
        score_str = self.score_str
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
        if self.board.checkPack(6, 'b'):
            king_xpos = length
            length += 19
        if self.board.checkPack(6, 'c'):
            robber_xpos = length
            length += 19
        if self.board.checkPack(14, "a"):
            gift_xpos = length
            length += 28
        img = Image.new("RGBA", (length, 24))
        dr = ImageDraw.Draw(img)
        dr.text((0, 12), str(self.id + 1) + "." + self.show_name, "black", self.board.font_name, "lm")
        if self.board.checkPack(12, "c"):
            dr.text((100 + score_length // 2, 12), score_str, "black", self.board.font_score, "mm")
        else:
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
        # king
        if self.board.checkPack(6, "b") and self.king:
            timg = self.board.king.image()
            img.alpha_composite(timg, (king_xpos, 12 - timg.size[1] // 2))
        # robber
        if self.board.checkPack(6, "c") and self.robber:
            timg = self.board.robber.image()
            img.alpha_composite(timg, (robber_xpos, 12 - timg.size[1] // 2))
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

from .ccs import Tile, Segment, Object, Feature, Token, Follower, FieldSegment
from .ccs import State, Connectable, Dir, CanScore, TAsync, Acrobat, Circus
from .ccs import Barn, Builder, Pig, TileAddable, CitySegment, RoadSegment, AbbeyData, Wagon, Monastry
from .ccs import Phantom, Tower, Abbot, BaseCloister, Flier, BigFollower, Addable, Gold, Shepherd
from .ccs_extra import Gift, ScoreReason, HomeReason
from .ccs_helper import RecieveBuyPrisoner, RecievePos, RecieveReturn, RecievePuttingFollower, RecieveId
from .ccs_helper import Send, CantPutError
from .ccs_board import Board