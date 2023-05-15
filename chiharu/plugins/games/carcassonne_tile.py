from abc import ABC, abstractmethod
from PIL import Image, ImageDraw
from .carcassonne_asset.readTile import Dir, SegmentPic, OneSideSegmentPic, DoubleSideSegmentPic, RoadSegmentPic, AreaSegmentPic, AllSideSegmentPic

def readTileData(packData: dict[int, str]):
    from pathlib import Path
    tiles: list[TileData] = []
    with open(Path(__file__).parent / "carcassonne_asset" / "tiledata.txt", encoding="utf-8") as f:
        pic: str = ""
        currentTile: TileData | None = None
        def endTile():
            nonlocal currentTile
            if currentTile is None:
                raise ValueError
            currentTile.CheckLimited()
            currentTile.MakeElse()
            tiles.append(currentTile)
            currentTile = None
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
