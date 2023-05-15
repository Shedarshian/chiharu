from abc import ABC, abstractmethod
from PIL import Image, ImageDraw
from .carcassonne_asset.readTile import Dir

def readTileData(packData: dict[int, str]):
    from pathlib import Path
    tiles: list[TileData] = []
    with open(Path(__file__).parent / "carcassonne_asset" / "tiledata.txt", encoding="utf-8") as f:
        pic: str = ""

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
