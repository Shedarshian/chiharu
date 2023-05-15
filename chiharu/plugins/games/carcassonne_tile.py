from enum import Enum, auto
from abc import ABC, abstractmethod
from PIL import Image, ImageDraw

class Dir(Enum):
    UP = 0
    RIGHT = 1
    DOWN = 2
    LEFT = 3
    def corr(self) -> tuple[int, int]:
        return ((0, -1), (1, 0), (0, 1), (-1, 0))[self.value]
    def tilepos(self) -> tuple[int, int]:
        return [(32, 0), (32, 64), (0, 32), (64, 32)][self.value]
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

class SegmentPic(ABC):
    def __init__(self) -> None:
        pass
    def inDirArea(self, dir: Dir) -> bool:
        return False
class RoadSegmentPic(SegmentPic):
    def __init__(self, nodes: list[tuple[int, int]]) -> None:
        super().__init__()
        self.nodes = nodes
class AreaSegmentPic(SegmentPic):
    pass
class OneSideSegmentPic(AreaSegmentPic):
    def __init__(self, dir: Dir, width: int) -> None:
        super().__init__()
        self.dir = dir
        self.width = width
        self.limited: tuple[bool, bool] = (False, False) # counter-clockwise, clockwise
    def inDirArea(self, dir: Dir) -> bool:
        return dir == self.dir
class DoubleSideSegmentPic(AreaSegmentPic):
    def __init__(self, dirs: tuple[Dir, Dir], width: int) -> None:
        super().__init__()
        self.dirs: tuple[Dir, Dir] = tuple(Dir(x) for x in sorted(dir.value for dir in dirs)) # type: ignore
        if dirs == (Dir.UP, Dir.LEFT):
            self.dirs = (Dir.LEFT, Dir.UP)
        self.width = width
        self.limited: tuple[bool, bool] = (False, False)
    def inDirArea(self, dir: Dir) -> bool:
        return dir in self.dirs
class AllSideSegmentPic(AreaSegmentPic):
    def __init__(self, removed: list[SegmentPic] | None=None, roads: list[RoadSegmentPic] | None=None) -> None:
        super().__init__()
        self.removed = removed or []
        self.roads = roads or []

def readTileData(packData: dict[int, str]):
    from pathlib import Path
    tiles: list[TileData] = []
    with open(Path(__file__).parent / "carcassonne_asset" / "tiledata.txt", encoding="utf-8") as f:
        pic: str = ""
        currentTile: TileData | None = None
        elsed: bool = False
        def endTile():
            nonlocal currentTile, elsed
            if currentTile is None:
                raise ValueError
            currentTile.CheckLimited()
            currentTile.MakeField(elsed)
            tiles.append(currentTile)
            currentTile = None
            elsed = False
        for line in f.readlines():
            words = line.strip().split(" ")
            if len(words) == 0:
                continue
            if words[0] == "Picture":
                if pic != "":
                    endTile()
                pic = words[1]
            elif words[0][0] in "0123456789":
                if pic != "":
                    endTile()
                id = int(words[0])
                sides = words[1]
                currentTile = TileData(id, sides)
            elif words[0].startswith("*"):
                pass
            else:
                if currentTile is None:
                    raise ValueError
                match words[0]:
                    case "City" | "Field":
                        if '-' in words[1]:
                            a, b = words[1].split('-')
                            p: AreaSegmentPic = DoubleSideSegmentPic((Dir[a.upper()], Dir[b.upper()]), int(words[2]))
                        elif words[1] in ("up", "down", "left", "right"):
                            p = OneSideSegmentPic(Dir[words[1].upper()], int(words[2]))
                        elif words[1] == "else":
                            p = AllSideSegmentPic([seg.type for seg in currentTile.segments if isinstance(seg, AreaSegmentData)])
                            elsed = True
                        else:
                            raise ValueError
                        currentTile.segments.append((CitySegmentData if words[0] == "City" else FieldSegmentData)(p))
                    case "Road":
                        if words[1] in ("up", "down", "left", "right"):
                            p2: list[RoadSegmentPic] | OneSideSegmentPic = OneSideSegmentPic(Dir[words[1].upper()], int(words[2]))
                        elif '-' in words[1]:
                            la = words[1].split('-')
                            n: list[tuple[int, int]] = []
                            for i in range(2):
                                if la[i].upper() in dir(Dir):
                                    ps: tuple[int, int] = Dir[la[i].upper()].tilepos()
                                    ex = (-Dir[la[i].upper()]).corr()
                                    if i == 0:
                                        n.append(ps)
                                    n.append((ps[0] + ex[0] * int(words[2]), ps[1] + ex[1] * int(words[2])))
                                    if i == 1:
                                        n.append(ps)
                                elif ',' in la[i]:
                                    n.append(tuple(int(x) for x in la[i].split(','))) # type: ignore
                                elif la[i][:-1] in ("junction", "cloister", "shrine"):
                                    num = int(la[i][8:])
                                    n.append([seg.pos for seg in currentTile.segments if isinstance(seg, FeatureSegmentData) and seg.type == la[i][:-1]][num])
                                else:
                                    raise ValueError
                            p2 = [RoadSegmentPic(n)]
                        else:
                            raise ValueError
                        currentTile.segments.append(RoadSegmentData(p2))
                    case "River":
                        pass
                    case "Junction" | "Garden" | "Cloister" | "Shrine":
                        ps = tuple(int(x) for x in words[1].split(',')) # type: ignore
                        p4 = FeatureSegmentData(ps, words[0])
                        currentTile.segments.append(p4)
                    case "Cut":
                        la = words[1].split('-')
                        n = []
                        for i in range(2):
                            if ',' in la[i]:
                                n.append(tuple(int(x) for x in la[i].split(','))) # type: ignore
                            elif la[i][:-1] in ("junction", "cloister", "shrine"):
                                num = int(la[i][8:])
                                n.append([seg.pos for seg in currentTile.segments if isinstance(seg, FeatureSegmentData) and seg.type == la[i][:-1]][num])
                            else:
                                raise ValueError
                        currentTile.segments.append(CutSegmentData(RoadSegmentPic(n)))

class TileData:
    def __init__(self, id: int, sides: str) -> None:
        self.id = id
        self.sides = sides
        self.segments: list[SegmentData] = []
    def CheckLimited(self):
        for seg in self.segments:
            if isinstance(seg, OneSideSegmentPic):
                l = any(s.inDirArea(seg.dir + Dir.LEFT) for s in self.segments)
                r = any(s.inDirArea(seg.dir + Dir.RIGHT) for s in self.segments)
                seg.limited = (l, r)
            elif isinstance(seg, DoubleSideSegmentPic):
                l = any(s.inDirArea(seg.dirs[0] + Dir.LEFT) for s in self.segments)
                r = any(s.inDirArea(seg.dirs[1] + Dir.RIGHT) for s in self.segments)
                seg.limited = (l, r)
    def MakeField(self, elsed: bool):
        if elsed:
            to_add: list[SegmentData] = []
            for seg in self.segments:
                if (ret := seg.makeSide()) is not None:
                    to_add.extend(ret)
            self.segments.extend(to_add)
        pass

class SegmentData(ABC):
    def inDirArea(self, dir: Dir) -> bool:
        return False
    def makeSide(self) -> None:
        pass
class PointSegmentData(SegmentData):
    def __init__(self, pos: tuple[int, int]) -> None:
        super().__init__()
        self.pos = pos
class LineSegmentData(SegmentData):
    def __init__(self) -> None:
        super().__init__()
        self.side: list[Dir] = []
class AreaSegmentData(SegmentData):
    def __init__(self, type: AreaSegmentPic) -> None:
        super().__init__()
        self.type = type
        self.side: list[Dir] = []
    def inDirArea(self, dir: Dir) -> bool:
        return self.type.inDirArea(dir)
class RiverSegmentData(LineSegmentData):
    def __init__(self, type: list[RoadSegmentPic]) -> None:
        super().__init__()
        self.type = type
    def makeSide(self):
        for dir in Dir:
            for seg in self.type:
                if dir.tilepos() in seg.nodes:
                    self.side.append(dir)
                    break
class RoadSegmentData(LineSegmentData):
    def __init__(self, type: list[RoadSegmentPic] | OneSideSegmentPic) -> None:
        super().__init__()
        self.type = type
    def inDirArea(self, dir: Dir) -> bool:
        return self.type.inDirArea(dir) if isinstance(self.type, OneSideSegmentPic) else False
    def makeSide(self):
        if isinstance(self.type, OneSideSegmentPic):
            self.side = [self.type.dir]
        else:
            for dir in Dir:
                for seg in self.type:
                    if dir.tilepos() in seg.nodes:
                        self.side.append(dir)
                        break
class CitySegmentData(AreaSegmentData):
    def __init__(self, type: AreaSegmentPic) -> None:
        super().__init__(type)
        self.pennant: int = 0
    def makeSide(self):
        if isinstance(self.type, OneSideSegmentPic):
            self.side = [self.type.dir]
        elif isinstance(self.type, DoubleSideSegmentPic):
            self.side = list(self.type.dirs)
class FieldSegmentData(AreaSegmentData):
    pass
class FeatureSegmentData(PointSegmentData):
    def __init__(self, pos: tuple[int, int], type: str) -> None:
        super().__init__(pos)
        self.pos = pos
        self.type = type.lower()
class CutSegmentData(LineSegmentData):
    def __init__(self, type: RoadSegmentPic) -> None:
        super().__init__()
        self.type = type
