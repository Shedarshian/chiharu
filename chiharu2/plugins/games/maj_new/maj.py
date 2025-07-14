import random
from enum import Enum, auto
from typing import TypeVar, Generic, TYPE_CHECKING
from .helper import Send, Recieve, TAsync, Config

class Color(Enum):
    z = auto() # 只有字牌不能形成顺子
    m = auto()
    p = auto()
    s = auto()
    h = auto() # 花牌
class FuuroType(Enum):
    chi = auto()
    peng = auto()
    minggang = auto()
    angang = auto()
    jiagang = auto()
    babei = auto()
    buhua = auto()

class Pai:
    def __init__(self, color: Color, num: int):
        self.color = color
        self.num = num
    def __eq__(self, value: 'Pai') -> bool:
        return self.color == value.color and self.num == value.num
    def __lt__(self, value: 'Pai') -> bool:
        if self.color != value.color:
            return self.color.value < value.color.value
        return self.num < value.num
    def __hash__(self) -> int:
        return hash((self.color, self.num))

class Fulu:
    def __init__(self, type: FuuroType, hai: tuple[Pai], fromPlayerPos: int = -1):
        self.type = type
        self.hai = hai
        self.fromPlayerPos: int = fromPlayerPos

class Player:
    def __init__(self, board: 'Board', pos: int):
        self.board = board
        self.pos = pos
        self.point: int = 0
        self.shoupai: list[Pai] = []
        self.fulu: list[Fulu] = []
        self.paihe: list[Pai] = []
        self.active: bool = False
        self.noDraw: bool = False
    def prepareNewRound(self):
        self.shoupai.clear()
        self.fulu.clear()
        self.paihe.clear()
    def drawHai(self) -> None:
        hai = self.board.paishan.pop(0)
        self.shoupai.append(hai)
    def turn(self) -> TAsync[bool]:
        if not self.noDraw:
            self.drawHai()
        self.noDraw = False
        self.active = False
        return False
        yield

class Board:
    PLAYER_NUM = 4
    def __init__(self, config: Config):
        self.players: list[Player] = [self.createPlayer(i) for i in range(self.PLAYER_NUM)]
        self.allPai: list[Pai] = self.preparePai()
        self.paishan: list[Pai] = []
        self.wangpai: list[Pai] = []
        self.chang: int = 0
        self.ju: int = 0
        self.benchang: int = 0
        self.lianzhuang: bool = False
        self.activePlayerPos: int = 0
    def createPlayer(self, pos: int) -> Player:
        return Player(pos)
    def preparePai(self) -> list[Pai]:
        pai = []
        for color in Color:
            if color == Color.z:
                continue
            for num in range(1, 10):
                for _ in range(4):
                    pai.append(Pai(color, num))
        for num in range(1, 8):
            for _ in range(4):
                pai.append(Pai(Color.z, num))
        return pai
    def shufflePaishan(self):
        random.shuffle(self.paishan)
    @property
    def dongjiaPos(self) -> int:
        return self.ju
    @property
    def dongjia(self) -> Player:
        return self.players[self.dongjiaPos]
    @property
    def activePlayer(self) -> Player:
        return self.players[self.activePlayerPos]

    def Game(self) -> TAsync[None]:
        while self.chang < 4:
            yield from self.Round()
            if not self.lianzhuang:
                self.benchang = 0
                self.ju += 1
                if self.ju >= 4:
                    self.chang += 1
                    self.ju = 0
            else:
                self.benchang += 1
                self.lianzhuang = False
    def Round(self) -> TAsync[None]:
        self.RoundPrepareHaiyama()
        self.RoundPrepareWanpai()
        for player in self.players:
            player.prepareNewRound()
        self.RoundBeginHai()
        while True:
            if len(self.paishan) == 0:
                break
            ret = yield from self.activePlayer.turn()
            if ret:
                break
    def RoundPrepareHaiyama(self):
        self.paishan = self.allPai.copy()
        self.shufflePaishan()
    def RoundPrepareWanpai(self):
        self.wangpai = self.paishan[-14:]
        self.paishan = self.paishan[:-14]
    def RoundBeginHai(self):
        for _ in range(3):
            for player in self.players:
                for _ in range(4):
                    player.shoupai.append(self.paishan.pop(0))
        for player in self.players:
            player.shoupai.append(self.paishan.pop(0))
        self.dongjia.shoupai.append(self.paishan.pop(0))
        self.dongjia.active = True
        self.dongjia.noDraw = True
        self.activePlayerPos = self.dongjiaPos
