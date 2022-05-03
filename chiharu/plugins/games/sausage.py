from collections import defaultdict
from dataclasses import dataclass

import more_itertools
from .boxgame import Grid3D
UP, DOWN, FRONT, BACK, LEFT, RIGHT = Grid3D.Directions.UP, Grid3D.Directions.DOWN, Grid3D.Directions.FRONT, Grid3D.Directions.BACK, Grid3D.Directions.LEFT, Grid3D.Directions.RIGHT

@dataclass
class Box:
    pos: Grid3D
@dataclass
class HalfSausage(Box):
    otherFacing: Grid3D
    grill: Grid3D | None = None
    upBurned: bool = False
    downBurned: bool = False
    def otherHalf(self, game: 'SausageGame'):
        return game.get(self.pos + self.otherFacing)
@dataclass
class Player(Box):
    facing: Grid3D
    hasGrill: bool = True
    def grill(self, game: 'SausageGame'):
        return game.get(self.pos + self.facing)
@dataclass
class Grill(Box):
    pass
@dataclass
class DropGrill(Box):
    facing: Grid3D
@dataclass
class Block(Box):
    isStove: bool = False
    stationary: int = 0
    ladder: frozenset[Grid3D] = frozenset()
    # display: int = 0
class SausageGame:
    def __init__(self) -> None:
        # 玩家，烤架，肠（是否包含烤架，是否上面已烤，是否下面已烤），方块（是否是火炉，四面是否附着梯子，是否活动）
        # pylint: disable=no-member
        self.player = Player(Grid3D(0, 0, 0), BACK)
        grill = Grill(self.playerPos + self.player.facing)
        self.board: list[Box] = [self.player, grill]
        self.blocks: list[tuple[Block,...]] = []
        mx = max(0, 0, *(b.stationary for b in self.board if isinstance(b, Block)))
        if mx != 0:
            self.blocks = [tuple(b for b in self.board if isinstance(b, Block) and b.stationary == i) for i in range(1, mx + 1)]
    def get(self, pos: Grid3D):
        return more_itertools.only(b for b in self.board if b.pos == pos)
    def process(self, dir: Grid3D):
        if self.player.facing == dir: # 前进
            if not self.player.hasGrill and isinstance(block := self.get(self.playerPos + dir), Block) and -dir in block.ladder: # 无叉子，正面爬梯子
                pass
            self.push(self.player, dir)
        elif self.player.facing == -dir: # 后退
            self.push(self.player, dir)
        elif not self.player.hasGrill: # 没有叉子，直接转向
            self.player.facing = dir
        else:
            box = self.get(self.playerPos + dir)
            boxa = self.get(self.playerPos + self.player.facing + dir)
            boxg = self.get(self.playerPos + self.player.facing)
            if isinstance(box, Block) and -dir in box.ladder: # 爬梯子
                pass
            elif isinstance(boxg, HalfSausage): # 叉着肠，平行移动
                self.push(self.player, dir)
            elif self.push(boxa, dir):
                if self.push(box, -self.player.facing):
                    pass
                    # 转向
    def push(self, box: Box | None, dir: Grid3D) -> bool:
        if box is None:
            return True
        ifMove = isinstance(box, Player) # 真的时候考虑脚下肠反向，假的时候考虑玩家脚下方块划船
        if ifMove:
            foot = box.pos + DOWN
            
        # 有一些是必须被推，推不动则反作用的，有一些是option被推的比如向上传递
    @property
    def playerPos(self):
        return self.player.pos
    def checkLoad(self, box: Box) -> list[Box]:
        if isinstance(box, Block) and box.stationary:
            return []
        l = self.getObject(box)
        return [b for box in l if (b := self.get(box.pos + DOWN)) is not None and b not in l]
    def getObject(self, box: Box) -> list[Box]:
        if isinstance(box, HalfSausage):
            return [box, box.otherHalf(self)]
        elif isinstance(box, Block):
            if box.stationary == 0:
                return [box]
            return list(self.blocks[box.stationary])
        elif isinstance(box, Player):
            return [box, box.grill(self)] if box.hasGrill else [box]
        else:
            return [box]
