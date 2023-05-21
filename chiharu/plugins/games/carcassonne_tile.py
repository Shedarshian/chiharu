import re, more_itertools
from abc import ABC, abstractmethod
from PIL import Image, ImageDraw
from copy import deepcopy
from .carcassonne_asset.readTile import *

def open_img(name: str):
    from pathlib import Path
    return Image.open(Path(__file__).parent / "carcassonne_asset" / (name + ".png")).convert("RGBA")
def readTileData(packData: dict[int, str]):
    from pathlib import Path
    tiles: list[TileData] = []
    with open(Path(__file__).parent / "carcassonne_asset" / "tiledata.txt", encoding="utf-8") as f:
        data = parser.parse(f.read())
        for name, tilets in data:
            img = open_img(name)
            for tilet in tilets:
                tile = TileData(name, tilet.id, tilet.sides, tilet.segments)
                for i, (num, packname, extra_orders) in enumerate(tilet.nums):
                    match = re.match(r"(\d+)([a-z])", packname)
                    if match is None:
                        continue
                    if match.group(2) not in packData.get(int(match.group(1)), ""):
                        continue
                    tile_now = deepcopy(tile)
                    for order in extra_orders:
                        match order:
                            case StartExtraOrderData():
                                tile_now.start = True
                            case AddableExtraOrderData(feature, params, None):
                                tile.segments.append(AddableSegmentData(feature, params))
                            case AddableExtraOrderData(feature, params, pos):
                                tile.segments.append(FeatureSegmentData(feature, pos, params, tile)) # type: ignore
                            case FeatureExtraOrderData(type, id, feature, params):
                                seg = [seg for seg in tile.segments if seg.type == type][id]
                                seg.addables.append(AddableSegmentData(feature, params))
                            case HintExtraOrderData(type, id, hint):
                                seg = [seg for seg in tile.segments if seg.type == type][id]
                                assert isinstance(seg, AreaSegmentData)
                                seg.pic.makeHint(hint)
                    tile_now.sub_id = i
                    for _ in range(num - 1):
                        tiles.append(deepcopy(tile_now))
                    tiles.append(tile_now)
    return tiles

class TileData:
    def __init__(self, picname: str, id: int, sides: str, segments: list[SegmentPic]) -> None:
        self.picname = picname
        self.id = id
        self.sides = sides
        self.segments: list[SegmentData] = []
        self.start: bool = False
        self.points: list[PointSegmentPic] = []
        self.sub_id = 0
        self.elsed: bool = False
        self.all_sides: list[tuple[Dir, bool]] = [(dr, b) for dr in Dir for b in (True, False)]
        for segment in segments:
            match segment.type:
                case SegmentType.City:
                    if not isinstance(segment, AreaSegmentPic):
                        raise NotImplementedError
                    self.segments.append(CitySegmentData(segment, self))
                case SegmentType.Field:
                    if not isinstance(segment, AreaSegmentPic):
                        raise NotImplementedError
                    self.segments.append(FieldSegmentData(segment, self))
                case SegmentType.Road:
                    if isinstance(segment, LineSegmentPic):
                        self.segments.append(RoadSegmentData(segment, self))
                    elif isinstance(segment, OneSideSegmentPic):
                        self.segments.extend(RoadSegmentData.makeOneSide(segment, self))
                    else:
                        raise NotImplementedError
                case SegmentType.River | SegmentType.Cut:
                    if not isinstance(segment, LineSegmentPic):
                        raise NotImplementedError
                    self.segments.append(RiverSegmentData(segment, self))
                case SegmentType.Feature:
                    if not isinstance(segment, PointSegmentPic):
                        raise NotImplementedError
                    self.segments.append(EmptyFeatureSegmentData(segment, self))
                    self.points.append(segment)
                case SegmentType.Junction | SegmentType.Bridge | SegmentType.Roundabout:
                    if not isinstance(segment, PointSegmentPic):
                        raise NotImplementedError
                    self.points.append(segment)
                case SegmentType.Tunnel:
                    if not isinstance(segment, TunnelSegmentPic):
                        raise NotImplementedError
                    roads = [seg for seg in self.segments if isinstance(seg, RoadSegmentData)]
                    roads[segment.num1].eat(roads[segment.num2])
            if isinstance(segment, ElseSegmentPic):
                self.elsed = True
        for segdata in self.segments:
            if isinstance(segdata, LineSegmentData) and segdata.valid:
                segdata.makeLink(self)
        self.segments = [seg for seg in self.segments if not isinstance(seg, RoadSegmentData) or seg.valid]
        del self.elsed

class SegmentData:
    type: SegmentType = SegmentType.City
    def __init__(self) -> None:
        self.addables: list[AddableSegmentData] = []
class AreaSegmentData(SegmentData):
    def __init__(self, segment: AreaSegmentPic, data: TileData) -> None:
        self.pic = segment
        self.side: list[tuple[Dir, bool]] = [] # counter-clockwise
        if isinstance(segment, OneSideSegmentPic):
            self.side = [(segment.dir, True), (segment.dir, False)]
            for side in self.side:
                data.all_sides.remove(side)
            if data.elsed:
                # data after "else" has eat effect
                for seg in data.segments:
                    if isinstance(seg, AreaSegmentData):
                        # eat
                        seg.side = [(dr, b) for dr, b in seg.side if dr != segment.dir]
        elif isinstance(segment, DoubleSideSegmentPic):
            self.side = [(dir, f) for dir in segment.dirs for f in (True, False)]
            for side in self.side:
                data.all_sides.remove(side)
        elif isinstance(segment, SmallSegmentPic):
            self.side = [segment.side]
            data.all_sides.remove(segment.side)
        elif isinstance(segment, ElseSegmentPic):
            if len(segment.road_sides) == 0:
                self.side = data.all_sides
                data.all_sides = []
                for seg in data.segments:
                    if isinstance(seg, AreaSegmentData) and isinstance(seg.pic, (OneSideSegmentPic, DoubleSideSegmentPic, SmallSegmentPic)):
                        self.addAdj(seg)
            else:
                roads = [road for road in data.segments if isinstance(road, (RoadSegmentData, RiverSegmentData))]
                checks: dict[tuple[Dir, bool], CitySegmentData | RoadSegmentData | RiverSegmentData] = {}
                for road_num, sides in segment.road_sides:
                    road = roads[road_num]
                    for rside in road.side:
                        for dir in sides:
                            if dir.orthogonal(rside):
                                sd = (rside, (rside - dir == Dir.RIGHT))
                                self.side.append(sd)
                                checks[sd] = road
                                data.all_sides.remove(sd)
                    t = road.lines[0].nodes_init[-1]
                    if isinstance(t, tuple) and isinstance(t[0], int):
                        for city in data.segments:
                            if isinstance(city, CitySegmentData) and city.pic.onSelfEdge(t):
                                checks[city.pic.begin()] = city
                                checks[city.pic.end()] = city
                self.sortSide()
                cl = list(checks.keys())
                begin = Dir.sideKey([(d, b) for d, b in reversed(sorted(list(checks.keys()), key=Dir.sideKey)) if not b][0])
                begined: bool = False
                for i in range(8):
                    d = Dir.fromSideKey(begin + i)
                    match begined, d in checks, d[1]:
                        case True, False, _:
                            self.side.append(d)
                        case True, True, True:
                            begined = False
                            if isinstance(c := checks[d], AreaSegmentData):
                                self.addAdj(c)
                        case True, True, False:
                            raise ValueError
                        case False, True, True:
                            raise ValueError
                        case False, True, False:
                            begined = True
                            if isinstance(c := checks[d], AreaSegmentData):
                                self.addAdj(c)
                        case False, False, _:
                            pass
        self.sortSide()
    def sortSide(self):
        self.side.sort(key=Dir.sideKey)
    def addAdj(self, other: "AreaSegmentData"):
        pass
    def drawPos(self, num: int):
        return self.pic.drawPos(num)
    def drawPosPut(self, num: int):
        return self.pic.drawPosPut(num)
class CitySegmentData(AreaSegmentData):
    def addAdj(self, other: "AreaSegmentData"):
        if isinstance(other, FieldSegmentData) and self not in other.adjCity:
            other.adjCity.append(self)
class FieldSegmentData(AreaSegmentData):
    type: SegmentType = SegmentType.Field
    def __init__(self, segment: AreaSegmentPic, data: TileData) -> None:
        super().__init__(segment, data)
        self.adjCity: list[CitySegmentData] = []
    def addAdj(self, other: AreaSegmentData):
        if isinstance(other, CitySegmentData) and other not in self.adjCity:
            self.adjCity.append(other)
class LineSegmentData(SegmentData):
    def __init__(self, line: LineSegmentPic, data: TileData) -> None:
        self.lines: list[LineSegmentPic] = [line]
        self.valid = True
        self.link: tuple[SegmentType, int] | None = None
        line.makeNodes(data.points)
        self.side: list[Dir] = [s for s in line.sides]
    def eat(self, other: 'LineSegmentData'):
        self.lines.extend(other.lines)
        other.lines = []
        self.side.extend(other.side)
        other.side = []
        other.valid = False
    def makeLink(self, data: TileData):
        line = self.lines[0]
        if line.link is not None:
            self.link = line.link
            l = [seg for seg in data.segments if isinstance(seg, LineSegmentData) and seg.link == line.link]
            if len(l) != 0:
                if line.link[0] == SegmentType.Roundabout:
                    l[0].eat(self)
                elif line.link[0] == SegmentType.Bridge and len(l) == 2:
                    if len(l[0].lines) == 1:
                        l[0].eat(self)
                    else:
                        l[1].eat(self)
class RoadSegmentData(LineSegmentData):
    type: SegmentType = SegmentType.Road
    def __init__(self, line: LineSegmentPic, data: TileData) -> None:
        super().__init__(line, data)
        pass
    @classmethod
    def makeOneSide(cls, segment: OneSideSegmentPic, data: TileData):
        ret: list[SegmentData] = []
        cor = segment.dir.corr()
        ret.append(RoadSegmentData(LineSegmentPic(SegmentType.Road,
                [segment.dir, (32 + (32 - segment.width) * cor[0], 32 + (32 - segment.width) * cor[1])], 0, []), data))
        ret.append(FieldSegmentData(SmallSegmentPic(SegmentType.Field, (segment.dir, True), segment.width, []), data))
        ret.append(FieldSegmentData(SmallSegmentPic(SegmentType.Field, (segment.dir, False), segment.width, []), data))
        return ret
class RiverSegmentData(LineSegmentData):
    pass
class EmptyFeatureSegmentData(SegmentData):
    type: SegmentType = SegmentType.Feature
    def __init__(self, segment: PointSegmentPic, data: TileData) -> None:
        self.pic = segment
class AddableSegmentData(SegmentData):
    type: SegmentType = SegmentType.Feature
    def __init__(self, type: str, params: list[Any]) -> None:
        super().__init__()
        self.feature = type
        self.params = params
class FeatureSegmentData(EmptyFeatureSegmentData, AddableSegmentData):
    def __init__(self, type: str, pos: tuple[int, int] | Dir | tuple[SegmentType, int], params: list[Any], data: TileData) -> None:
        AddableSegmentData.__init__(self, type, params)
        if isinstance(pos, tuple):
            if isinstance(pos[0], SegmentType):
                f = [seg for seg in data.segments if seg.type == pos[0]][pos[1]]
                assert isinstance(f, PointSegmentPic)
                self.pos: tuple[int, int] = f.pos
            else:
                self.pos = pos
        else:
            self.pos = pos.tilepos()
        segment = PointSegmentPic(SegmentType.Feature, self.pos, [])
        EmptyFeatureSegmentData.__init__(self, segment, data)


