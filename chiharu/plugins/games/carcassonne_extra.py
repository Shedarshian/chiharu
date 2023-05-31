
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

class LandCity(Enum):
    Wealth = auto()
    Poverty = auto()
    Siege = auto()
    BadNeighborhood = auto()
    CitizensJury = auto()
class LandRoad(Enum):
    Poverty = auto()
    StreetFair = auto()
    Highway = auto()
    PeasantUprising = auto()
class LandMonastry(Enum):
    Wealth = auto()
    HermitMonastery = auto()
    PilgrimageRoute = auto()

from .carcassonne import *
