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
                print(name, tilet.id, tilet.sides)
                tile = TileData(name, tilet.id, tilet.sides, tilet.segments)
                for i0, (num, packname, extra_orders) in enumerate(tilet.nums):
                    match = re.match(r"(\d+)([a-z])", packname)
                    if match is None:
                        continue
                    i = int(match.group(1))
                    if match.group(2) not in packData.get(i, ""):
                        continue
                    tile_now = deepcopy(tile)
                    tile_now.packid = i
                    tile_now.img = img.crop((64 * i0, 64 * tilet.id, 64 * i0 + 64, 64 * tilet.id + 64))
                    for order in extra_orders:
                        match order:
                            case StartExtraOrderData():
                                tile_now.start = True
                            case AddableExtraOrderData(feature, params, None):
                                tile_now.segments.append(AddableSegmentData(feature, params))
                            case AddableExtraOrderData(feature, params, pos):
                                tile_now.segments.append(FeatureSegmentData(feature, pos, params, tile_now)) # type: ignore
                            case FeatureExtraOrderData(type, id, feature, params):
                                seg = [seg for seg in tile_now.segments if seg.type == type][id]
                                seg.addables.append(AddableSegmentData(feature, params))
                            case HintExtraOrderData(type, id, hint):
                                seg = [seg for seg in tile_now.segments if seg.type == type][id]
                                assert isinstance(seg, AreaSegmentData)
                                seg.pic.makeHint(hint)
                            case RoadWidthExtraOrderData(type, id, width):
                                seg = [seg for seg in tile_now.segments if seg.type == type][id]
                                assert isinstance(seg, LineSegmentData)
                                for line in seg.lines:
                                    line.width = width
                                    line.makeNodes(tile_now.points)
                    tile_now.sub_id = i0
                    for _ in range(num - 1):
                        tiles.append(deepcopy(tile_now))
                    tiles.append(tile_now)
    return tiles
def readPackData():
    from pathlib import Path
    import json
    with open(Path(__file__).parent / "carcassonne.json", encoding="utf-8") as f:
        return json.load(f)

class TileData:
    def __init__(self, picname: str, id: int, sides: str, segments: list[SegmentPic]) -> None:
        self.picname = picname
        self.packid: int = -1
        self.id = id
        self.sides = sides
        self.segments: list[SegmentData] = []
        self.start: bool = False
        self.points: list[PointSegmentPic] = []
        self.sub_id = 0
        self.elsed: bool = False
        self.all_sides: list[tuple[Dir, bool]] = [(dr, b) for dr in Dir for b in (True, False)]
        self.img: Image.Image = None # type: ignore
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
                case SegmentType.River:
                    if not isinstance(segment, LineSegmentPic):
                        raise NotImplementedError
                    self.segments.append(RiverSegmentData(segment, self))
                case SegmentType.Cut:
                    pass
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
        self.segments = [seg for seg in self.segments if not isinstance(seg, LineSegmentData) or seg.valid]
        del self.elsed
    @property
    def serialNumber(self):
        return self.packid, self.picname, self.id, self.sub_id

class SegmentData:
    type: SegmentType = SegmentType.City
    def __init__(self) -> None:
        self.addables: list[AddableSegmentData] = []
class AreaSegmentData(SegmentData):
    def __init__(self, segment: AreaSegmentPic, data: TileData) -> None:
        super().__init__()
        self.pic = segment
        self.side: list[tuple[Dir, bool]] = [] # counter-clockwise
        if isinstance(segment, OneSideSegmentPic):
            self.side = [(segment.dir, True), (segment.dir, False)]
            if not data.elsed:
                for side in self.side:
                    data.all_sides.remove(side)
            else:
                # data after "else" has eat effect
                for seg in data.segments:
                    if isinstance(seg, AreaSegmentData):
                        if any(dr == segment.dir for dr, b in seg.side):
                            self.addAdj(seg)
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
            elif isinstance(segment.road_sides[0], RoadSideTuple):
                roads = [road for road in data.segments if isinstance(road, (RoadSegmentData, RiverSegmentData))]
                checks: dict[tuple[Dir, bool], CitySegmentData | RoadSegmentData | RiverSegmentData] = {}
                for road_num, sides in segment.road_sides:
                    assert isinstance(road_num, int) and isinstance(sides, list)
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
                                break
                self.sortSide()
                begin = Dir.sideKey([(d, b) for d, b in reversed(sorted(list(checks.keys()), key=Dir.sideKey)) if not b][0])
                begined: bool = False
                for i in range(8):
                    d = Dir.fromSideKey(begin + i)
                    match begined, d in checks, d[1]:
                        case True, False, _:
                            if d in data.all_sides:
                                self.side.append(d)
                                data.all_sides.remove(d)
                            else:
                                e = [seg for seg in data.segments if isinstance(seg, AreaSegmentData) and d in seg.side][0]
                                self.addAdj(e)
                        case True, True, True:
                            begined = False
                            if isinstance(c := checks[d], AreaSegmentData):
                                self.addAdj(c)
                        case True, True, False:
                            raise ValueError
                        case False, True, True:
                            pass
                        case False, True, False:
                            begined = True
                            if isinstance(c := checks[d], AreaSegmentData):
                                self.addAdj(c)
                        case False, False, _:
                            pass
            else:
                for d1, d2 in segment.road_sides:
                    assert isinstance(d1, Dir) and isinstance(d2, Dir)
                    b = d2 == d1 + Dir.LEFT
                    self.side.append((d1, b))
                    data.all_sides.remove((d1, b))
            lc = [c for c in data.segments if isinstance(c, CitySegmentData)]
            for i in segment.adjCity:
                self.addAdj(lc[i])
        self.sortSide()
    def sortSide(self):
        self.side.sort(key=Dir.sideKey)
    def addAdj(self, other: "AreaSegmentData"):
        pass
    def drawPos(self, num: int):
        return self.pic.drawPos(num)
    def putPos(self, num: int):
        return self.pic.putPos(num)
class CitySegmentData(AreaSegmentData):
    def addAdj(self, other: "AreaSegmentData"):
        if isinstance(other, FieldSegmentData) and self not in other.adjCity:
            other.adjCity.append(self)
class FieldSegmentData(AreaSegmentData):
    type: SegmentType = SegmentType.Field
    def __init__(self, segment: AreaSegmentPic, data: TileData) -> None:
        self.adjCity: list[CitySegmentData] = []
        super().__init__(segment, data)
    def addAdj(self, other: AreaSegmentData):
        if isinstance(other, CitySegmentData) and other not in self.adjCity:
            self.adjCity.append(other)
class LineSegmentData(SegmentData):
    def __init__(self, line: LineSegmentPic, data: TileData) -> None:
        super().__init__()
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
                elif line.link[0] == SegmentType.Bridge:
                    if len(l) == 3:
                        l[0].eat(self)
                    elif len(l) == 4:
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
        super().__init__()
        self.pic = segment
class AddableSegmentData(SegmentData):
    type: SegmentType = SegmentType.Feature
    def __init__(self, type: str, params: list[Any]) -> None:
        super().__init__()
        self.feature = type
        self.params = params
class FeatureSegmentData(AddableSegmentData):
    def __init__(self, type: str, pos: tuple[int, int] | Dir | tuple[SegmentType, int], params: list[Any], data: TileData) -> None:
        AddableSegmentData.__init__(self, type, params)
        if isinstance(pos, tuple):
            if isinstance(pos[0], SegmentType):
                f = [seg for seg in data.segments if seg.type == pos[0]][pos[1]]
                assert isinstance(f, EmptyFeatureSegmentData)
                self.pos: tuple[int, int] = f.pic.pos
            else:
                self.pos = pos
        else:
            self.pos = pos.tilepos()
        self.pic = PointSegmentPic(SegmentType.Feature, self.pos, [])


