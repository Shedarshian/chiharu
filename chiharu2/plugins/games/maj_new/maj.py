import random
from enum import Enum, auto
from typing import TypeVar, Generic, TYPE_CHECKING
from .helper import Send, Recieve, TAsync

class Color(Enum):
    z = auto() # 只有字牌不能形成顺子
    m = auto()
    p = auto()
    s = auto()
class FuuroType(Enum):
    chi = auto()
    pon = auto()
    minkan = auto()
    ankan = auto()
    kakan = auto()
    pei = auto()

THai = TypeVar("THai", bound="BaseHai")
TPlayer = TypeVar("TPlayer", bound="BasePlayer")
TBoard = TypeVar('TTable', bound='BaseBoard')
class BaseHai:
    def __init__(self, color: Color, num: int):
        self.color = color
        self.num = num
    def __eq__(self, value: 'BaseHai') -> bool:
        return self.color == value.color and self.num == value.num
    def __lt__(self, value: 'BaseHai') -> bool:
        if self.color != value.color:
            return self.color.value < value.color.value
        return self.num < value.num
    def __hash__(self) -> int:
        return hash((self.color, self.num))

class Fuuro(Generic[THai]):
    def __init__(self, type: FuuroType, hai: tuple[THai], fromPlayerPos: int = -1):
        self.type = type
        self.hai = hai
        self.fromPlayerPos: int = fromPlayerPos

class BasePlayer(Generic[THai, TBoard]):
    def __init__(self, board: TBoard, pos: int):
        self.board = board
        self.pos = pos
        self.tensu: int = 0
        self.tehai: list[THai] = []
        self.fuuro: list[Fuuro[THai]] = []
        self.haiho: list[THai] = []
        self.active: bool = False
        self.noDraw: bool = False
    def prepareNewRound(self):
        self.tehai.clear()
        self.fuuro.clear()
        self.haiho.clear()
    def drawHai(self) -> None:
        self.tehai.append(hai)
    def turn(self) -> TAsync[bool]:
        if not self.noDraw:
            self.drawHai()
        self.noDraw = False
        self.active = False
        return False
        yield

class BaseBoard(Generic[TPlayer, THai]):
    PLAYER_NUM = 4
    def __init__(self):
        self.players: list[TPlayer] = [self.createPlayer(i) for i in range(self.PLAYER_NUM)]
        self.allHai: list[THai] = self.prepareHai()
        self.haiyama: list[THai] = []
        self.wanpai: list[THai] = []
        self.ba: int = 0
        self.kyoku: int = 0
        self.honba: int = 0
        self.renchan: bool = False
        self.activePlayerPos: int = 0
    def createPlayer(self, pos: int) -> TPlayer:
        return TPlayer(pos)
    def prepareHai(self) -> list[THai]:
        hai = []
        for color in Color:
            if color == Color.z:
                continue
            for num in range(1, 10):
                for _ in range(4):
                    hai.append(BaseHai(color, num))
        for num in range(1, 8):
            for _ in range(4):
                hai.append(BaseHai(Color.z, num))
        return hai
    def shuffleHaiyama(self):
        random.shuffle(self.haiyama)
    @property
    def toujyaPos(self) -> int:
        return self.kyoku
    @property
    def toujya(self) -> TPlayer:
        return self.players[self.toujyaPos]
    @property
    def activePlayer(self) -> TPlayer:
        return self.players[self.activePlayerPos]

    def Game(self) -> TAsync[None]:
        while self.ba < 4:
            yield from self.Round()
            if not self.renchan:
                self.honba = 0
                self.kyoku += 1
                if self.kyoku >= 4:
                    self.ba += 1
                    self.kyoku = 0
            else:
                self.honba += 1
                self.renchan = False
    def Round(self) -> TAsync[None]:
        self.RoundPrepareHaiyama()
        self.RoundPrepareWanpai()
        for player in self.players:
            player.prepareNewRound()
        self.RoundBeginHai()
        while True:
            ret = yield from self.activePlayer.turn()
            if ret:
                break
    def RoundPrepareHaiyama(self):
        self.haiyama = self.allHai.copy()
        self.shuffleHaiyama()
    def RoundPrepareWanpai(self):
        self.wanpai = self.haiyama[-14:]
        self.haiyama = self.haiyama[:-14]
    def RoundBeginHai(self):
        for _ in range(3):
            for player in self.players:
                for _ in range(4):
                    player.tehai.append(self.haiyama.pop(0))
        for player in self.players:
            player.tehai.append(self.haiyama.pop(0))
        self.toujya.tehai.append(self.haiyama.pop(0))
        self.toujya.active = True
        self.toujya.noDraw = True
        self.activePlayerPos = self.toujyaPos

class TestHai(BaseHai):
    pass
class TestPlayer(BasePlayer[TestHai, 'TestBoard']):
    pass
class TestBoard(BaseBoard[TestPlayer, TestHai]):
    pass