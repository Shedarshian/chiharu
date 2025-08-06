import random, itertools, more_itertools
from enum import Enum, auto, IntEnum, IntFlag
from typing import TypeVar, Generic, TYPE_CHECKING, Iterable, Any, NewType, Sequence
from copy import deepcopy
from dataclasses import dataclass
from collections import Counter
from functools import total_ordering, cache
from .helper import Send, Recieve, TAsync, Config

class Color(Enum):
    z = auto() # 只有字牌不能形成顺子
    m = auto()
    p = auto()
    s = auto()
    h = auto() # 花牌
class MianziType(IntFlag):
    shun = 0
    ke = 1
    gang = 2
    quetou = 3
    an = 0
    ming = 4
    rong = 8
    jiagang = 12
    anshun = an | shun
    anke = an | ke
    angang = an | gang
    anquetou = an | quetou
    mingshun = ming | shun
    mingke = ming | ke
    minggang = ming | gang
    rongshun = rong | shun
    rongke = rong | ke
    rongquetou = rong | quetou
    babei = 16
    buhua = 32
    def isKezi(self):
        return self & 3 in (1, 2)
    def isShunzi(self):
        return self & 3 == 0
    def isQuetou(self):
        return self & 3 == 3
    def isExtra(self):
        return self & -16 != 0
    def isShunziOrExtra(self):
        return self.isShunzi() or self.isExtra()
    def isKeziOrExtra(self):
        return self.isKezi() or self.isExtra()
    def isShunziOrQuetouOrExtra(self):
        return self.isShunzi() or self.isQuetou() or self.isExtra()
    def isKeziOrQuetouOrExtra(self):
        return self.isKezi() or self.isQuetou() or self.isExtra()
    def isRong(self):
        return self & 12 == 8
    def menqianqing(self):
        return self & 12 in (0, 8)
    def isFulu(self):
        return self.menqianqing() and self != MianziType.angang
    def isGang(self):
        return self & 3 == 2
class ChangStatus(IntEnum):
    Dong = 0
    Nan = 1
    Xi = 2
    Bei = 3
    DongChang = 0
    NanChang = 4
    XiChang = 8
    BeiChang = 12
    def ZijiaToPai(self):
        return Pai(Color.z, self & 3)
    def ChangToPai(self):
        return Pai(Color.z, (self & 12) // 4)
class PaiStatus(IntFlag):
    none = 0
    Ronghe = 1
    Menqianqing = 1 << 1
    Ricchi = 1 << 2
    FirstPai = 1 << 3       # 是庄家打出/摸的第一张牌
    FirstXun = 1 << 4       # 开局直至自己打出第一张牌前且无人鸣牌
    Lingshang = 1 << 5
    Haidi = 1 << 6
    Qianggang = 1 << 7
    Qiangangang = 1 << 8
class Button(Enum):
    Pass = auto()
    Dapai = auto()
    Chi = auto()
    Peng = auto()
    Minggang = auto()
    Angang = auto()
    Jiagang = auto()
    Babei = auto()
    Buhua = auto()
    Lizhi = auto()
    Jiuzhongjiupai = auto()
class EndStatus(Enum):
    Dapai = auto()
    Hepai = auto()
    Huangpailiuju = auto()
    Jiuzhongjiupai = auto()
    Sifenglianda = auto()
    Sigangsanliao = auto()
    Sijializhi = auto()
    Sanjiaheliao = auto()

@dataclass(frozen=True, eq=True, order=True)
class Pai:
    color: Color
    num: int

@dataclass(eq=True, order=True)
class RealPai:
    pai: Pai

@dataclass
class Fulu:
    type: MianziType
    pai: tuple[RealPai,...]
    fromPlayerPos: int = -1 # 默认最后一张牌当作从别人那里拿来的牌
    def toMianzi(self):
        return Paili.Mianzi(self.type, self.pai[0].pai.color, tuple(n.pai.num for n in self.pai))

T = TypeVar("T")
class Paili:
    @dataclass(frozen=True, eq=True, order=True)
    class Mianzi:
        type: 'MianziType'
        color: Color
        pai: tuple[int,...]
        hepaiPos: int = -1
        def getHepai(self):
            if self.type.isRong():
                return (self.pai[self.hepaiPos],)
            return ()
        def withoutHepaiExtra(self):
            if self.type.isRong():
                return self.pai[:self.hepaiPos] + self.pai[self.hepaiPos + 1:]
            if self.type.isExtra():
                return ()
            return self.pai
    class MianziTuple(tuple[Mianzi,...]):
        def toPai(self) -> Iterable[Pai]:
            return itertools.chain(*((Pai(x.color, p) for p in x.pai) for x in self))
        def onlyExtra(self):
            return all(x.type.isExtra() for x in self)
        @cache
        def removeExtra(self):
            return Paili.MianziTuple(x for x in self if not x.type.isExtra())
        def menqianqing(self):
            return all(x.type.menqianqing() for x in self)
        def allShoupai(self):
            return sorted(Pai(m.color, p) for m in self for p in m.withoutHepaiExtra())
        def keziList(self) -> Iterable[Pai]:
            return (Pai(m.color, m.pai[0]) for m in self if m.type.isKezi())
        def quetou(self):
            return more_itertools.one(Pai(m.color, m.pai[0]) for m in self if m.type.isQuetou())
        def shunziMinList(self) -> Iterable[Pai]:
            return (Pai(m.color, min(m.pai)) for m in self if m.type.isShunzi())
        def __add__(self, other):
            return Paili.MianziTuple(self + other)
    SplitResult = tuple[MianziTuple,...]
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
    @classmethod
    def splitThree(cls, color: Color, paiCount: Counter[int],
            splitedPai: 'list[Paili.Mianzi]',
            hasQuetou: bool) \
            -> 'SplitResult':
        for key, val in paiCount.items():
            if val > 0:
                break
        else:
            return (Paili.MianziTuple(tuple(sorted(splitedPai))),)
        result: tuple[Paili.MianziTuple,...] = ()
        if paiCount[key + 1] > 0 and paiCount[key + 2] > 0:
            paiCount_temp = deepcopy(paiCount)
            splitedPai_temp = deepcopy(splitedPai)
            paiCount_temp[key] -= 1; paiCount_temp[key + 1] -= 1; paiCount_temp[key + 2] -= 1
            splitedPai_temp.append(Paili.Mianzi(MianziType.anshun, color, (key, key + 1, key + 2)))
            result += cls.splitThree(color, paiCount_temp, splitedPai_temp, hasQuetou)
        if val >= 2 and not hasQuetou:
            paiCount_temp = deepcopy(paiCount)
            splitedPai_temp = deepcopy(splitedPai)
            paiCount_temp[key] -= 2
            splitedPai_temp.append(Paili.Mianzi(MianziType.anquetou, color, (key, key)))
            result += cls.splitThree(color, paiCount_temp, splitedPai_temp, True)
        if val >= 3:
            paiCount_temp = deepcopy(paiCount)
            splitedPai_temp = deepcopy(splitedPai)
            paiCount_temp[key] -= 3
            splitedPai_temp.append(Paili.Mianzi(MianziType.anke, color, (key, key, key)))
            result += cls.splitThree(color, paiCount_temp, splitedPai_temp, hasQuetou)
        return result
    @classmethod
    def splitOneColor(cls, color: Color, pais: Iterable[int], hasQuetou: bool=True) -> 'SplitResult':
        barrel = Counter(pais)
        return cls.splitThree(color, barrel, [], not hasQuetou)
    @classmethod
    def getTingOneColor(cls, color: Color, pais: Iterable[int],
                        considerRange: Iterable[int]=range(9),
                        hasQuetou: bool=True):
        barrel = Counter(pais)
        results: dict[int, Paili.SplitResult] = {}
        for i in considerRange:
            barrel[i] += 1
            result = cls.splitThree(color, barrel, [], not hasQuetou)
            results[i] = result
            barrel[i] -= 1
        return results
    @classmethod
    def getTingAllColor(cls, pais: dict[Barrel, list[int]],
                        considerRange: Iterable[int]=range(9)) \
                        -> dict[Pai, list[MianziTuple]]:
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
                result: Paili.SplitResult = Paili.splitOneColor(key.color, val, hasQuetou=False)
                if len(result) == 0:
                    return {}
            else:
                #字牌
                def _(val: list[int]):
                    while len(val) >= 3:
                        yield Paili.Mianzi(MianziType.anke, key.color, (val[0], val[1], val[2]))
                        val = val[3:]
                result = (Paili.MianziTuple(_(val)),)
            resultAllInHand[key] = result
        if l == (1, 0): # 单骑
            key, val = list(mod1_barrel.items())[0]
            if key.color != Color.z:
                #数牌
                for tingpaiInt, splitResult in Paili.getTingOneColor(key.color, val, considerRange=considerRange).items():
                    if len(splitResult) == 0:
                        continue
                    pai = Pai(key.color, tingpaiInt)
                    resultsWithTen[pai] = {key: splitResult}
            else:
                #字牌单骑
                def _(val: list[int]):
                    while len(val) >= 3:
                        yield Paili.Mianzi(MianziType.anke, key.color, (val[0], val[1], val[2]))
                        val = val[3:]
                result4: Paili.SplitResult = (Paili.MianziTuple(tuple(_(val)) + (Paili.Mianzi(MianziType.anquetou, key.color, (val[0], val[0])),)),)
                pai = Pai(key.color, key.num)
                resultsWithTen[pai] = {key: result4}
        else: # 双碰
            (key1, val1), (key2, val2) = list(mod2_barrel.items())
            for k1, t1, k2, t2 in ((key1, val1, key2, val2), (key2, val2, key1, val1)):
                result5 = Paili.getTingOneColor(k1.color, t1, considerRange=considerRange, hasQuetou=False)
                result6 = Paili.splitOneColor(k2.color, t2)
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
        -> list[MianziTuple]:
        return [sum(x, start=Paili.MianziTuple(())) for x in itertools.product(*splitResult.values())]

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
    def drawPai(self, pai: RealPai):
        self.shoupai.append(pai)
    def findEqualRealPai(self, pai: RealPai):
        return more_itertools.first(c for c in self.shoupai if c == pai)
    def hasEqualRealPai(self, pai: RealPai):
        return any(True for c in self.shoupai if c == pai)
    def findPai(self, pai: Pai):
        return [c for c in self.shoupai if c.pai == pai]
    def hasPai(self, pai: Pai):
        return any(True for c in self.shoupai if c.pai == pai)
    def turn(self) -> TAsync[EndStatus]:
        if not self.noDraw:
            self.drawPai(self.board.drawPaishan())
        self.noDraw = False
        self.active = False
        while 1:
            # TODO 碰后不能杠
            canLingshang = self.board.canDrawLingshang()
            angang = self.checkAngang() if canLingshang else []
            jiagang = self.checkJiagang() if canLingshang else []
            babei = self.checkBei() if canLingshang else []
            buhua = self.checkHua() if self.board.canDrawPaishan() else []
            jzjp = bool(self.board.status & PaiStatus.FirstXun) and self.checkJiuzhongjiupai()
            from .helper import SendInTurn, RecieveInTurn
            last_err = -1
            while 1:
                choice: dict[Button, Sequence[tuple[RealPai, ...]] | bool] \
                    = {Button.Angang: angang, Button.Babei: babei, Button.Buhua: buhua, Button.Jiuzhongjiupai: jzjp, Button.Jiagang: jiagang}
                ret = yield SendInTurn(last_err, self.pos, choice)
                assert isinstance(ret, RecieveInTurn)
                if ret.button not in (Button.Angang, Button.Babei, Button.Buhua, Button.Jiuzhongjiupai, Button.Dapai, Button.Jiagang):
                    last_err = 1
                    continue
                if ret.button == Button.Jiuzhongjiupai:
                    return EndStatus.Jiuzhongjiupai
                if ret.choice is None or not any(True for c in choice[ret.button] if c == ret.choice): # type: ignore
                    last_err = 2
                    continue
                if ret.button == Button.Dapai:
                    if len(ret.choice) != 1 or self.hasEqualRealPai(ret.choice[0]):
                        last_err = 2
                        continue
                    pai = self.findEqualRealPai(ret.choice[0])
                    self.shoupai.remove(pai)
                    self.paihe.append(pai)
                    return EndStatus.Dapai
                elif ret.button == Button.Jiagang:
                    pass # TODO
                    break
                else:
                    self.makeFulu(ret.choice, MianziType[ret.button.name.lower()])
                    if ret.button == Button.Buhua:
                        pai = self.board.drawPaishan()
                    else:
                        pai = self.board.drawLingshang()
                    self.drawPai(pai)
                    break
        return EndStatus.Huangpailiuju
    def getPaiCombination(self, lpai: list[Counter[Pai]]):
        l: list[tuple[RealPai, ...]] = []
        for tpai in lpai:
            l += [sum(x, ()) for x in itertools.product(
                *(more_itertools.distinct_combinations(sorted(p for p in self.shoupai if p.pai == pai), num)
                for pai, num in tpai.items()))]
        return l
    def checkChi(self, pai: RealPai) -> list[tuple[RealPai, ...]]:
        if pai.pai.color == Color.z or pai.pai.color == Color.h:
            return []
        pais = {i: p for i in range(-2, 3) if self.hasPai(p := Pai(pai.pai.color, pai.pai.num + i))}
        l: list[Counter[Pai]] = []
        if -2 in pais and -1 in pais:
            l.append(Counter({pais[-2]: 1, pais[-1]: 1}))
        if -1 in pais and 1 in pais:
            l.append(Counter({pais[-1]: 1, pais[1]: 1}))
        if 1 in pais and 2 in pais:
            l.append(Counter({pais[1]: 1, pais[2]: 1}))
        return self.getPaiCombination(l)
    def checkPeng(self, pai: RealPai) -> list[tuple[RealPai, ...]]:
        if not self.hasPai(pai.pai):
            return []
        pais = self.findPai(pai.pai)
        if len(pais) < 2:
            return []
        return self.getPaiCombination([Counter({pai.pai: 2})])
    def checkMingGang(self, pai: RealPai) -> list[tuple[RealPai, ...]]:
        if not self.hasPai(pai.pai):
            return []
        pais = self.findPai(pai.pai)
        if len(pais) < 3:
            return []
        return self.getPaiCombination([Counter({pai.pai: 3})])
    def checkAngang(self):
        lpai = [Counter({key: 4}) for key, val in Counter(p.pai for p in self.shoupai).items() if val == 4]
        return self.getPaiCombination(lpai)
    def checkJiagang(self):
        return [(pai,) for pai in self.shoupai if any(fulu.type == MianziType.mingke and fulu.pai[0].pai == pai.pai for fulu in self.fulu)]
    def checkHua(self):
        return [(pai,) for pai in self.shoupai if pai.pai.color == Color.h]
    def checkBei(self):
        return [(pai,) for pai in self.shoupai if pai.pai == Pai(Color.z, 4)]
    def checkJiuzhongjiupai(self):
        return len(set(pai.pai for pai in self.shoupai if pai.pai.color == Color.z or pai.pai.num in (1, 9))) >= 9

    def makeFulu(self, findInShoupai: tuple[RealPai, ...], type: MianziType, fromPlayerPos: int = -1):
        pais: list[RealPai] = []
        for p in findInShoupai:
            pai = self.findEqualRealPai(p)
            self.shoupai.remove(pai)
            pais.append(pai)
        self.fulu.append(Fulu(type, tuple(pais), fromPlayerPos))

class Board:
    def __init__(self, config: Config):
        self.players: list[Player] = [self.createPlayer(i) for i in range(4)]
        self.allPai: list[RealPai] = self.preparePai()
        self.paishan: list[RealPai] = []
        self.wangpai: list[RealPai] = []
        self.lingshangDrawn: int = 0
        self.chang: int = 0
        self.ju: int = 0
        self.benchang: int = 0
        self.lianzhuang: bool = False
        self.activePlayerPos: int = 0
        self.config = config
        self.status = PaiStatus.none
    def createPlayer(self, pos: int) -> Player:
        return Player(self, pos)
    def preparePai(self) -> list[RealPai]:
        pai: list[RealPai] = []
        for color in Color:
            if color == Color.z:
                continue
            for num in range(1, 10):
                for _ in range(4):
                    pai.append(RealPai(Pai(color, num)))
        for num in range(1, 8):
            for _ in range(4):
                pai.append(RealPai(Pai(Color.z, num)))
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
    def canDrawPaishan(self):
        return len(self.paishan) > 0
    def drawPaishan(self):
        return self.paishan.pop(0)
    def canDrawLingshang(self):
        return self.lingshangDrawn < 4 and len(self.paishan) > 0
    def drawLingshang(self):
        pai = self.wangpai.pop(-1)
        self.wangpai.insert(0, self.paishan.pop(-1))
        return pai
    @classmethod
    def nextPos(cls, pos: int):
        return (pos + 1) % 4

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
        self.RoundPrepareWangpai()
        for player in self.players:
            player.prepareNewRound()
        self.RoundBeginPai()
        self.status = PaiStatus.FirstPai | PaiStatus.FirstXun
        ret = EndStatus.Dapai
        while True:
            if len(self.paishan) == 0:
                break
            ret = yield from self.activePlayer.turn()
            if ret != EndStatus.Dapai:
                break
            yield from self.RoundCheckMingpai()
    def RoundPrepareHaiyama(self):
        self.paishan = self.allPai.copy()
        self.shufflePaishan()
    def RoundPrepareWangpai(self):
        self.wangpai = self.paishan[-14:]
        self.paishan = self.paishan[:-14]
        self.lingshangDrawn = 0
    def RoundBeginPai(self):
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
    def RoundCheckMingpai(self) -> TAsync[None]:
        player = self.activePlayer
        pai = player.paihe[-1]
        if not self.canDrawPaishan():
            pass
            return
        choice: dict[int, dict[Button, list[tuple[RealPai, ...]]]] = {}
        for player_check in self.players:
            chi = player_check.checkChi(pai) if self.nextPos(self.activePlayerPos) == player_check.pos else []
            peng = player_check.checkPeng(pai)
            minggang = player_check.checkMingGang(pai)
            choice[player_check.pos] = {
                Button.Chi: chi,
                Button.Peng: peng,
                Button.Minggang: minggang,
            }
        passed_player = set()
        last_err = -1
        while 1:
            from .helper import SendFuluCheck, RecieveFulu
            ret = yield SendFuluCheck(last_err, choice)
            assert isinstance(ret, RecieveFulu)
            if ret.player_pos in passed_player:
                last_err = 4
                continue
            if ret.button == Button.Pass:
                passed_player.add(ret.player_pos)
                if len(passed_player) == 3:
                    break
                continue
            if ret.button not in (Button.Chi, Button.Peng, Button.Minggang):
                last_err = 1
                continue
            if not any(True for c in choice[ret.player_pos][ret.button] if c == ret.choice):
                last_err = 2
                continue
            if ret.button == Button.Chi and ret.player_pos != self.nextPos(self.activePlayerPos):
                last_err = 3
                continue
            player_do = self.players[ret.player_pos]
            player.paihe.remove(pai)
            player_do.makeFulu(ret.choice + (pai,), MianziType[ret.button.name.lower()]) # not done check priority
            self.activePlayerPos = ret.player_pos
            break