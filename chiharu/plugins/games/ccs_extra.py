from abc import abstractmethod
from datalite import datalite
from enum import IntEnum
from dataclasses import dataclass
from enum import Enum, auto
from typing import Type, Literal, Sequence
import more_itertools

class Gift:
    __slots__ = ()
    name = ""
    id = -1
    @classmethod
    def make(cls, id: int) -> 'Type[Gift]':
        return [GiftSynod, GiftRoadSweeper, GiftCashOut, GiftChangePosition, GiftTake2][id]
    @abstractmethod
    def use(self, user: 'Player') -> 'TAsync[int]':
        return 1
        yield {}
class GiftSynod(Gift):
    __slots__ = ()
    name = "教会会议"
    id = 0
    def use(self, user: 'Player') -> 'TAsync[int]':
        pass_err: Literal[0, -1, -2, -3, -4] = 0
        for t in user.board.tiles.values():
            cloister = more_itertools.only(feature for feature in t.features if isinstance(feature, Monastry))
            if cloister and not cloister.closed():
                break
        else:
            return -1
        while 1:
            user.board.state = State.AskingSynod
            from .ccs_helper import RecievePosWhich
            ret = yield Send(pass_err)
            assert isinstance(ret, RecievePosWhich)
            if ret.pos not in user.board.tiles:
                pass_err = -1
                continue
            tile: Tile = user.board.tiles[ret.pos]
            cloister = more_itertools.only(feature for feature in tile.features if isinstance(feature, Monastry))
            if cloister is None:
                pass_err = -2
                continue
            token = user.findToken(ret.which)
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
    __slots__ = ()
    name = "马路清扫者"
    id = 1
    def use(self, user: 'Player') -> 'TAsync[int]':
        pass_err: Literal[0, -1, -2, -3, -4] = 0
        for t in user.board.tiles.values():
            roads = [segment for segment in t.segments if isinstance(segment, RoadSegment) and not segment.closed()]
            if len(roads) > 0:
                break
        else:
            return -1
        while 1:
            user.board.state = State.ChoosingPos
            from .ccs_helper import SendChoosingPos
            ret = yield SendChoosingPos(pass_err, "road_sweeper")
            assert isinstance(ret, RecievePos)
            if ret.pos not in user.board.tiles:
                pass_err = -1
                continue
            tile = user.board.tiles[ret.pos]
            roads = [segment for segment in tile.segments if isinstance(segment, RoadSegment) and not segment.closed()]
            if len(roads) == 0:
                pass_err = -2
                continue
            road: RoadSegment = roads[0]
            if len(roads) >= 2:
                pass_err = 0
                while 1:
                    user.board.state = State.ChoosingSegment
                    from .ccs_helper import SendPosSpecial
                    ret2 = yield SendPosSpecial(pass_err, ret.pos, "road_sweeper")
                    assert isinstance(ret2, RecieveId)
                    s = tile.getSeg(ret2.id)
                    if not isinstance(s, RoadSegment):
                        pass_err = -1
                        continue
                    if s not in roads:
                        pass_err = -2
                        continue
                    road = s
                    break
            road.object.scoreFinal()
            road.object.removeAllFollowers(HomeReason.RoadSweeper)
            break
        return 1
class GiftCashOut(Gift):
    __slots__ = ()
    name = "兑现"
    id = 2
    def use(self, user: 'Player') -> 'TAsync[int]':
        follower = yield from user.utilityChoosingFollower('cash_out', lambda t: isinstance(t.parent, (Segment, BaseCloister)))
        if follower is None:
            return -1
        assert isinstance(follower.parent, (Segment, BaseCloister))
        assert isinstance(follower.player, Player)
        obj = follower.parent.object if isinstance(follower.parent, Segment) else follower.parent
        score = sum(2 for token in obj.iterTokens() if isinstance(token, Follower))
        from .ccs_helper import LogScore
        user.board.addLog(LogScore(user.long_name, "cash_out", score))
        yield from follower.player.addScore(score, type=ScoreReason.Gift)
        follower.putBackToHand(HomeReason.CashOut)
        return 1
class GiftChangePosition(Gift):
    __slots__ = ()
    name = "切换形态"
    id = 3
    def use(self, user: 'Player') -> 'TAsync[int]':
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
            from .ccs_helper import SendChoosingPos
            ret = yield SendChoosingPos(pass_err, "change_position")
            assert isinstance(ret, RecievePos)
            if ret.pos not in user.board.tiles:
                pass_err = -1
                continue
            tile = user.board.tiles[ret.pos]
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
                    from .ccs_helper import SendPosSpecial
                    ret2 = yield SendPosSpecial(pass_err, ret.pos, "change_position")
                    assert isinstance(ret2, RecieveId)
                    if ret2.id < 0 or ret2.id >= len(followers):
                        pass_err = -2
                        continue
                    follower = followers[ret2.id]
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
                    from .ccs_helper import SendPosSpecial
                    ret3 = yield SendPosSpecial(pass_err, ret.pos, "change_position")
                    assert isinstance(ret3, RecieveId)
                    p = tile.getSeg(ret3.id)
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
            follower.remove(None)
            yield from follower.putOn(to_put)
            if to_check is not None:
                to_check.object.checkRemoveBuilderAndPig(HomeReason.ChangePosition)
            break
        return 1
        yield {}
class GiftTake2(Gift):
    __slots__ = ()
    name = "再来一张"
    id = 4
    def use(self, user: 'Player') -> 'TAsync[int]':
        if len(user.board.deck) == 0:
            return -1
        tile = user.board.drawTileCanPut()
        if tile is None:
            from .ccs_helper import LogTake2NoTile
            user.board.addLog(LogTake2NoTile())
        else:
            user.handTiles.append(tile)
        return 1
        yield {}

class LandCity(Enum):
    Wealth = auto()
    Poverty = auto()
    Siege = auto()
    BadNeighborhood = auto()
    CitizensJury = auto()
    def saveID(self):
        return {LandCity.CitizensJury: 0, LandCity.Poverty: 1, LandCity.Siege: 2, LandCity.Wealth: 3, LandCity.BadNeighborhood: 4}[self]
class LandRoad(Enum):
    Poverty = auto()
    StreetFair = auto()
    Highway = auto()
    PeasantUprising = auto()
    def saveID(self):
        return {LandRoad.Highway: 0, LandRoad.Poverty: 1, LandRoad.StreetFair: 2, LandRoad.PeasantUprising: 3}[self]
class LandMonastry(Enum):
    Wealth = auto()
    HermitMonastery = auto()
    PilgrimageRoute = auto()
    def saveID(self):
        return {LandMonastry.HermitMonastery: 0, LandMonastry.PilgrimageRoute: 1, LandMonastry.Wealth: 2}[self]

class Messenger:
    __slots__ = ()
    id = -1
    des = ""
    @classmethod
    def make(cls, id: int) -> 'Type[Messenger]':
        return [Messenger1, Messenger2, Messenger3, Messenger4, Messenger5, Messenger6, Messenger7, Messenger8][id - 1]
    def use(self, user: 'Player') -> 'TAsync[bool]':
        return False
        yield {}
class Messenger1(Messenger):
    __slots__ = ()
    id = 1
    des = "计分一个含你的最短路"
    def use(self, user: 'Player') -> 'TAsync[bool]':
        score = min(token.parent.object.checkScore([user], False, False)[0][1] for token in user.allTokens if isinstance(token.parent, RoadSegment))
        yield from user.addScore(score, ScoreReason.Messenger)
        return False
class Messenger2(Messenger):
    __slots__ = ()
    id = 2
    des = "计分一个含你的最小城"
    def use(self, user: 'Player') -> 'TAsync[bool]':
        score = min(token.parent.object.checkScore([user], False, False)[0][1] for token in user.allTokens if isinstance(token.parent, CitySegment))
        yield from user.addScore(score, ScoreReason.Messenger)
        return False
class Messenger3(Messenger):
    __slots__ = ()
    id = 3
    des = "计分一个含你的最小修道院"
    def use(self, user: 'Player') -> 'TAsync[bool]':
        score = min(token.parent.checkScore([user], False, False)[0][1] for token in user.allTokens if isinstance(token.parent, Monastry))
        yield from user.addScore(score, ScoreReason.Messenger)
        return False
class Messenger4(Messenger):
    __slots__ = ()
    id = 4
    des = "再进行一个回合"
    def use(self, user: 'Player') -> 'TAsync[bool]':
        return True
        yield {}
class Messenger5(Messenger):
    __slots__ = ()
    id = 5
    des = "每个含你的城的盾徽计2分"
    def use(self, user: 'Player') -> 'TAsync[bool]':
        all_cities: list[Object] = []
        for token in user.allTokens:
            if isinstance(token.parent, CitySegment) and token.parent.object not in all_cities:
                all_cities.append(token.parent.object)
        score = sum(2 * city.checkPennant() for city in all_cities)
        yield from user.addScore(score, ScoreReason.Messenger)
        return False
class Messenger6(Messenger):
    __slots__ = ()
    id = 6
    des = "每个你在城中的跟随者计2分"
    def use(self, user: 'Player') -> 'TAsync[bool]':
        score = sum(2 for token in user.allTokens if isinstance(token.parent, CitySegment) and isinstance(token, Follower))
        yield from user.addScore(score, ScoreReason.Messenger)
        return False
class Messenger7(Messenger):
    __slots__ = ()
    id = 7
    des = "每个你在草地上的跟随者计2分"
    def use(self, user: 'Player') -> 'TAsync[bool]':
        score = sum(2 for token in user.allTokens if isinstance(token.parent, FieldSegment) and isinstance(token, Follower))
        yield from user.addScore(score, ScoreReason.Messenger)
        return False
class Messenger8(Messenger):
    __slots__ = ()
    id = 8
    des = "将一个跟随者计分并收回"
    def use(self, user: 'Player') -> 'TAsync[bool]':
        follower = yield from user.utilityChoosingFollower('messenger8')
        if follower is None:
            return False
        if isinstance(follower.parent, Segment):
            scores = follower.parent.object.checkPlayerAndScore(False)
        elif isinstance(follower.parent, CanScore):
            scores = follower.parent.checkPlayerAndScore(False)
        else:
            return False
        lscore = [s for p, s in scores if p is user]
        if len(lscore) != 0:
            score = lscore[0]
            yield from user.addScore(score, ScoreReason.Messenger)
            yield from follower.scoreExtra()
        follower.putBackToHand(HomeReason.Messenger8)
        return False

@dataclass
class ccsGameStat:
    group_id: int
    players: str
    extensions: str
    time: str
    winner: int
    scores: str
    city_begin: int
    city_end: int
    road_begin: int
    road_end: int
    monastry_begin: int
    monastry_end: int
    field_begin: int
    field_end: int
    meeple_begin: int
    meeple_end: int
    tower_begin: int
    tower_end: int
@dataclass
class ccsCityStat:
    game: int
    players: str
    tiles: int
    complete: bool
    score: int
    scores: str = ''
    pennants: int = 0
    cathedral: int = 0
    mage_witch: int = 0
    land_surveyor: int = 0
@dataclass
class ccsRoadStat:
    game: int
    players: str
    tiles: int
    complete: bool
    score: int
    scores: str = ''
    inn: int = 0
    ferry: int = 0
    mage_witch: int = 0
    land_surveyor: int = 0
@dataclass
class ccsMonastryStat:
    game: int
    players: str
    type: str
    tiles: int
    complete: bool
    score: int
    scores: str = ''
    abbey: bool = False
    vineyard: int = 0
    challenge_complete: bool = False
    hermit_monastry: int = 0
    pilgrimage_route: int = 0
    wealth: bool = False
@dataclass
class ccsFieldStat:
    game: int
    players: str
    cities: int
    score: int
    scores: str = ''
    barn: int = 0 # 0: no, 1: putting barn, 2: connecting barn, 3: is barn
    pig: str = ''
    pigherd: int = 0
class HomeReason(IntEnum):
    Score = 0
    Dragon = 1
    Princess = 2
    Tower = 3
    Challenge = 4
    Wolf = 5
    Shepherd = 6
    Abbot = 7
    Messenger8 = 8
    CropCircle = 9
    Festival = 10
    RoadSweeper = 11
    CashOut = 12
    ChangePosition = 13
@dataclass
class ccsMeepleStat:
    game: int
    player: int
    type: str
    stay_turn: int
    home_reason: HomeReason
    ability: int = 0
    fairy_1: int = 0
    fairy_3: int = 0
@dataclass
class ccsTowerStat:
    game: int
    player: int
    capture: str
    exchange: str = ''
class ScoreReason(IntEnum):
    City = 0
    Road = 1
    Monastry = 2
    Field = 3
    Garden = 4
    Trade = 5
    Fairy = 6
    Prisoner = 7
    PayPrisoner = 8
    King = 9
    Robber = 10
    Shepherd = 11
    Messenger = 12
    Gold = 13
    ScoringRobber = 14
    Gift = 15
    Gingerbread = 16
    Ranger = 17

from .ccs import State, Tile, RoadSegment, Follower, Segment, BaseCloister, FieldSegment, CitySegment
from .ccs import TAsync, Monastry, Object, CanScore
from .ccs_player import Player
from .ccs_helper import RecievePos, RecieveId, Send
