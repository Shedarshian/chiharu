import random, itertools
from enum import Enum, auto, IntEnum, IntFlag
from typing import TypeVar, Generic, TYPE_CHECKING, Iterable, Any, NewType
from copy import deepcopy
from dataclasses import dataclass
from collections import Counter
from functools import total_ordering
from .helper import Send, Recieve, TAsync, Config

class Color(Enum):
    z = auto() # 只有字牌不能形成顺子
    m = auto()
    p = auto()
    s = auto()
    h = auto() # 花牌
class FuluType(Enum):
    chi = auto()
    peng = auto()
    minggang = auto()
    angang = auto()
    jiagang = auto()
    babei = auto()
    buhua = auto()
    def isKezi(self):
        return self in (FuluType.peng, FuluType.minggang, FuluType.angang, FuluType.jiagang)
    def isShunzi(self):
        return self == FuluType.chi
    def isExtra(self):
        return self in (FuluType.babei, FuluType.buhua)
    def isShunziOrExtra(self):
        return self.isShunzi() or self.isExtra()
    def isKeziOrExtra(self):
        return self.isKezi() or self.isExtra()
    def menqianqing(self):
        return self.isExtra() or self == FuluType.angang
class ChangStatus(IntEnum):
    Dong = 0
    Nan = 1
    Xi = 2
    Bei = 3
    DongChang = 0
    NanChang = 4
    XiChang = 8
    BeiChang = 12
class PaiStatus(IntFlag):
    none = 0
    Ronghe = 1
    Ricchi = 1 << 1
    FirstPai = 1 << 2       # 是庄家打出的第一张牌
    FirstXun = 1 << 3       # 开局直至自己打出第一张牌前且无人鸣牌
    Lingshang = 1 << 4
    Haidi = 1 << 5
    Qianggang = 1 << 6
    Qiangangang = 1 << 7

@dataclass(eq=True, order=True)
class Pai:
    color: Color
    num: int

@dataclass(eq=True, order=True)
class RealPai(Pai):
    pass

class Fulu:
    def __init__(self, type: FuluType, pai: tuple[RealPai], fromPlayerPos: int = -1):
        self.type = type
        self.pai = pai
        self.fromPlayerPos: int = fromPlayerPos

T = TypeVar("T")
class Paili:
    class MianziType(Enum):
        Shunzi = auto()
        Kezi = auto()
        Quetou = auto()
        Rongke = auto()
        Rongshun = auto()
        def isShunziOrQuetou(self):
            return self in (Paili.MianziType.Shunzi, Paili.MianziType.Rongshun, Paili.MianziType.Quetou)
        def isKeziOrQuetou(self):
            return self in (Paili.MianziType.Kezi, Paili.MianziType.Rongke, Paili.MianziType.Quetou)
    @dataclass(frozen=True, eq=True, order=True)
    class Mianzi:
        type: 'Paili.MianziType'
        pai: tuple[int,...]
        hepaiPos: int = -1
        def getHepai(self):
            if self.type in (Paili.MianziType.Rongke, Paili.MianziType.Rongshun):
                return (self.pai[self.hepaiPos],)
            return ()
        def withoutHepai(self):
            if self.type in (Paili.MianziType.Rongke, Paili.MianziType.Rongshun):
                return self.pai[:self.hepaiPos] + self.pai[self.hepaiPos + 1:]
            return self.pai
    MianziSet = tuple[Mianzi,...]
    SplitResult = set[MianziSet]
    @dataclass(frozen=True, eq=True, order=True)
    class Barrel:
        color: Color
        num: int
    @classmethod
    def toBarrel(cls, pai: Pai) -> Barrel:
        if pai.color == Color.h or pai.color == Color.z:
            return Paili.Barrel(pai.color, pai.num)
        return Paili.Barrel(pai.color, 0)
    @classmethod
    def inBarrel(cls, pai: Pai, barrel: Barrel):
        if pai.color != barrel.color:
            return False
        if pai.color in (Color.h, Color.z) and pai.num != barrel.num:
            return False
        return True
    BarrelwiseSplitResult = dict[Barrel, SplitResult]
    class SplitResultWithBarrel(dict[Barrel, MianziSet]):
        def allPai(self):
            return sorted(Pai(v.color, p) for v, s in self.items() for m in s for p in m.pai)
        def allPaiWithFulu(self, f: list[Fulu]):
            return sorted(itertools.chain(self.allPai(), *(y.pai for y in f if not y.type.isExtra())))
        def allShoupai(self):
            return sorted(Pai(v.color, p) for v, s in self.items() for m in s for p in m.withoutHepai())
    @classmethod
    def splitThree(cls, paiCount: Counter[int],
            splitedPai: 'list[Paili.Mianzi]',
            hasQuetou: bool) \
            -> 'SplitResult':
        for key, val in paiCount.items():
            if val > 0:
                break
        else:
            return {tuple(sorted(splitedPai))}
        result: set[tuple[Paili.Mianzi,...]] = set()
        if paiCount[key + 1] > 0 and paiCount[key + 2] > 0:
            paiCount_temp = deepcopy(paiCount)
            splitedPai_temp = deepcopy(splitedPai)
            paiCount_temp[key] -= 1; paiCount_temp[key + 1] -= 1; paiCount_temp[key + 2] -= 1
            splitedPai_temp.append(Paili.Mianzi(Paili.MianziType.Shunzi, (key, key + 1, key + 2)))
            result |= cls.splitThree(paiCount_temp, splitedPai_temp, hasQuetou)
        if val >= 2 and not hasQuetou:
            paiCount_temp = deepcopy(paiCount)
            splitedPai_temp = deepcopy(splitedPai)
            paiCount_temp[key] -= 2
            splitedPai_temp.append(Paili.Mianzi(Paili.MianziType.Quetou, (key, key)))
            result |= cls.splitThree(paiCount_temp, splitedPai_temp, True)
        if val >= 3:
            paiCount_temp = deepcopy(paiCount)
            splitedPai_temp = deepcopy(splitedPai)
            paiCount_temp[key] -= 3
            splitedPai_temp.append(Paili.Mianzi(Paili.MianziType.Kezi, (key, key, key)))
            result |= cls.splitThree(paiCount_temp, splitedPai_temp, hasQuetou)
        return result
    @classmethod
    def splitOneColor(cls, pais: Iterable[int], hasQuetou: bool=True) -> 'SplitResult':
        barrel = Counter(pais)
        return cls.splitThree(barrel, [], not hasQuetou)
    @classmethod
    def getTingOneColor(cls, pais: Iterable[int],
                        considerRange: Iterable[int]=range(9),
                        hasQuetou: bool=True):
        barrel = Counter(pais)
        results: dict[int, Paili.SplitResult] = {}
        for i in considerRange:
            barrel[i] += 1
            result = cls.splitThree(barrel, [], not hasQuetou)
            results[i] = result
            barrel[i] -= 1
        return results
    @classmethod
    def getTingAllColor(cls, pais: dict[Barrel, list[int]],
                        considerRange: Iterable[int]=range(9)) \
                        -> dict[Pai, list[SplitResultWithBarrel]]:
        mod1_barrel: dict[Paili.Barrel, list[int]] = {}
        mod2_barrel: dict[Paili.Barrel, list[int]] = {}
        mod3_barrel: dict[Paili.Barrel, list[int]] = {}
        for key, val in pais.items():
            if len(val) % 3 == 1:
                mod1_barrel[key] = val
            elif len(val) % 3 == 2:
                mod2_barrel[key] = val
            elif len(val) != 0:
                mod3_barrel[key] = val
        l = (len(mod1_barrel), len(mod2_barrel))
        if not (l == (1, 0) or l == (0, 2)):
            return {}
        resultsWithTen: dict[Pai, Paili.BarrelwiseSplitResult] = {}
        resultAllInHand: Paili.BarrelwiseSplitResult = {}
        for key, val in mod3_barrel.items():
            if key.color != Color.z:
                #数牌
                result: Paili.SplitResult = Paili.splitOneColor(val, hasQuetou=False)
                if len(result) == 0:
                    return {}
            else:
                #字牌
                def _(val: list[int]):
                    while len(val) >= 3:
                        yield Paili.Mianzi(Paili.MianziType.Kezi, (val[0], val[1], val[2]))
                        val = val[3:]
                result = {tuple(_(val))}
            resultAllInHand[key] = result
        if l == (1, 0): # 单骑
            key, val = list(mod1_barrel.items())[0]
            if key.color != Color.z:
                #数牌
                for tingpaiInt, splitResult in Paili.getTingOneColor(val, considerRange=considerRange).items():
                    if len(splitResult) == 0:
                        continue
                    pai = Pai(key.color, tingpaiInt)
                    resultsWithTen[pai] = {key: splitResult}
            else:
                #字牌单骑
                def _(val: list[int]):
                    while len(val) >= 3:
                        yield Paili.Mianzi(Paili.MianziType.Kezi, (val[0], val[1], val[2]))
                        val = val[3:]
                result4: Paili.SplitResult = {tuple(_(val)) + (Paili.Mianzi(Paili.MianziType.Quetou, (val[0], val[0])),)}
                pai = Pai(key.color, key.num)
                resultsWithTen[pai] = {key: result4}
        else: # 双碰
            (key1, val1), (key2, val2) = list(mod2_barrel.items())
            for k1, t1, k2, t2 in ((key1, val1, key2, val2), (key2, val2, key1, val1)):
                result5 = Paili.getTingOneColor(t1, considerRange=considerRange, hasQuetou=False)
                result6 = Paili.splitOneColor(t2)
                if len(result6) == 0:
                    continue
                for tingpaiInt, splitResult in result5.items():
                    if len(splitResult) == 0:
                        continue
                    pai = Pai(k1.color, tingpaiInt)
                    resultsWithTen[pai] = {k1: splitResult, k2: result6}
        return {key: Paili.breakBarrelwiseSplitResult(val) for key, val in resultsWithTen.items()}
    @classmethod
    def breakBarrelwiseSplitResult(cls, splitResult: BarrelwiseSplitResult) \
        -> list[SplitResultWithBarrel]:
        return [SplitResultWithBarrel(x) for x in itertools.product(*([(barrel, s) for s in sr] for barrel, sr in splitResult.items()))]
SplitResultWithBarrel = Paili.SplitResultWithBarrel

class Player:
    def __init__(self, board: 'Board', pos: int):
        self.board = board
        self.pos = pos
        self.point: int = 0
        self.shoupai: list[RealPai] = []
        self.fulu: list[Fulu] = []
        self.paihe: list[RealPai] = []
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
    def __init__(self, config: Config):
        self.players: list[Player] = [self.createPlayer(i) for i in range(4)]
        self.allPai: list[RealPai] = self.preparePai()
        self.paishan: list[RealPai] = []
        self.wangpai: list[RealPai] = []
        self.chang: int = 0
        self.ju: int = 0
        self.benchang: int = 0
        self.lianzhuang: bool = False
        self.activePlayerPos: int = 0
        self.config = config
    def createPlayer(self, pos: int) -> Player:
        return Player(self, pos)
    def preparePai(self) -> list[RealPai]:
        pai: list[RealPai] = []
        for color in Color:
            if color == Color.z:
                continue
            for num in range(1, 10):
                for _ in range(4):
                    pai.append(RealPai(color, num))
        for num in range(1, 8):
            for _ in range(4):
                pai.append(RealPai(Color.z, num))
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

