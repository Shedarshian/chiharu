import random
import functools
import itertools
import abc
import asyncio
import operator
from copy import copy, deepcopy
from enum import Enum, IntFlag, IntEnum, auto
from typing import Sequence, TypeVar, Generic, Iterable, Generator, Any, Callable, TypeAlias
from typing_extensions import Self
from collections import Counter

H = TypeVar('H', bound='MajHai')
class MajErr(Exception):
    def __init__(self, *args):
        self.args = args
    def __str__(self):
        return str(self.args)
class FuuRoNotValid(MajErr):
    def __init__(self, status: 'FuuRoStatus', hai: Sequence[H]):
        self.args = (status, hai)
    def __str__(self):
        pass
class MajIdError(MajErr):
    def __init__(self, id):
        self.args = (id,)
    def __str__(self):
        return 'Id %i out of bound' % self.args[0]
class NoPlayer(MajErr):
    def __str__(self):
        return 'No player'
class Not14(MajErr):
    def __str__(self):
        return '不是14张'
class Win(MajErr):
    def __init__(self, p, hai):
        self.player = p
        self.hai = hai

class PlayerStatus(IntFlag):
    DAHAI = 0
    NAKU = 1
    FIRST = 2 # 第一张牌，人和使用
    RINSHAN = 4
    HAIDI = 8
    QIANKAN = 16
    TIAN = 32 # 第一巡，地和与流局使用
    QIANANKAN = 64
class FuuRoStatus(IntFlag):
    KAMICHA = 0
    TOIMEN = 1
    SHIMOCHA = 2
    ANKAN = 0
    QI = 4
    PON = 8
    DAIMINKAN = 16
    KAKAN = 32
    @property
    def who(self):
        return FuuRoStatus(self.value & 3)
    @property
    def what(self):
        return FuuRoStatus(self.value & -4)
    @property
    def what_str(self):
        return {0: "暗杠", 4: "吃", 8: "碰", 16: "大明杠", 32: "加杠"}[self.value & -4]
    @property
    def who_str(self):
        return {0: "上家", 1: "对家", 2: "下家"}[self.value & 3]
class PlayerPos(IntEnum):
    TON = 0
    NAN = 1
    SHA = 2
    PE = 3
    def fuuro(self, other: 'PlayerPos'):
        v = other - self - 1
        if v < 0:
            v += 4
        return FuuRoStatus(v)
class PlayerOption(IntFlag):
    NOTHING = 0
    kiri = 1
    ankan = 2
    kakan = 4
    tsumo = 8
    richi = 16
    qi = 64
    pon = 128
    daiminkan = 256
    ron = 512
class HaiHoStatus(IntFlag):
    TEDASHI = 0
    TSUMOKIRI = 1
    NAKARERU = 2
    RICHI = 4
class FuuRo(Generic[H]):
    def __init__(self, status: FuuRoStatus, hai: tuple[H,...]):
        self.status = status
        self.hai = hai
        self.sorted = tuple(sorted(x.num for x in hai))
    def __str__(self):
        return '(%s %s %s)' % (self.status.what_str, self.status.who_str, ' '.join(map(str, self.hai)))
    @property
    def barrel(self):
        return self.hai[0].barrel
    @property
    def isValid(self):
        if self.status.what == FuuRoStatus.QI:
            return len(self.hai) == 3 \
                and all(x.barrel == self.hai[0].barrel for x in self.hai) \
                and self.sorted[2] == self.sorted[1] + 1 == self.sorted[0] + 2
        else:
            return all(x.hai == self.hai[0].hai for x in self.hai) \
                and (self.status.what == FuuRoStatus.PON and len(self.hai) == 3 \
                or self.status.what != FuuRoStatus.PON and len(self.hai) == 4)

@functools.total_ordering
class MajHai:
    class HeZhong:
        pass
    class Color(Enum):
        m = 0
        p = 1
        s = 2
        z = 3
    NUM_SHU = 9
    NUM_EACH_HAI = 4
    NUM_ZI = 7
    NUM_COLOR = 3
    def __init__(self, id: int | str, *args):
        if len(args) == 1 and isinstance(id, int) and isinstance((num := args[0]), int):
            self.color = id
            self.num = num
            self.hai = self.color * 9 + self.num
            self.barrel = self.color if self.color != 3 else self.num + self.color
            if not (self.hai < 136):
                raise MajIdError((id, args[0]))
            self.id = -1
        elif isinstance(id, int):
            if not (id >= 0 and id < self.NUM_EACH_HAI * (self.NUM_SHU * self.NUM_COLOR + self.NUM_ZI)):
                raise MajIdError(id)
            self.id = id
            self.hai = id // self.NUM_EACH_HAI
            self.num = self.hai % self.NUM_SHU
            self.color = self.hai // self.NUM_SHU # 0: m, 1: p, 2: s, 3: z
            self.barrel = self.color if self.color != self.NUM_COLOR else self.num + self.color
        else:
            assert(isinstance(id, str))
            if not (len(id) == 2 and id[0] in '0123456789' and id[1] in 'mpsz'):
                raise MajIdError(id)
            self.num = int(id[0]) - 1
            self.color = {'m': 0, 'p': 1, 's': 2, 'z': 3}[id[1]]
            self.hai = self.color * 9 + self.num
            self.barrel = self.color if self.color != 3 else self.num + self.color
            if not (self.hai < 136):
                raise MajIdError(id)
            self.id = -1
    @classmethod
    def get_random(cls):
        return random.randint(0, cls.NUM_SHU * cls.NUM_COLOR + cls.NUM_ZI - 1)
    @property
    def color_c(self):
        return MajHai.Color(self.color)
    def __str__(self):
        return '%i%s' % (self.num + 1, self.color_c)
    def __lt__(self, other):
        if not isinstance(other, MajHai):
            return NotImplemented
        return self.hai < other.hai
    def __eq__(self, other): # 赤ドラ same
        if not isinstance(other, MajHai):
            return NotImplemented
        return self.hai == other.hai
    def isAllSame(self, other: 'MajHai'): # 赤ドラ differs
        return self.hai == other.hai
    def isaddOne(self, other: 'MajHai'):
        return self.color == other.color and self.color != self.NUM_COLOR and self.num + 1 == other.num
    def addOneDora(self):
        if self.color == 3:
            if self.num == self.NUM_ZI - 1:
                return self.__class__(self.color, 4)
            elif self.num == 3:
                return self.__class__(self.color, 0)
            return self.__class__(self.color, self.num + 1)
        else:
            if self.num == self.NUM_SHU - 1:
                return self.__class__(self.color, 0)
            return self.__class__(self.color, self.num + 1)
    @property
    def isYaokyuu(self):
        return self.color == self.NUM_COLOR or self.num == 0 or self.num == self.NUM_SHU - 1
    @property
    def isDummy(self):
        return self.id == -1
    @classmethod
    def getHaiId(cls, num: int, barrel: int):
        if barrel < cls.NUM_COLOR:
            return barrel * cls.NUM_SHU + num
        else:
            return cls.NUM_COLOR + cls.NUM_SHU + num
    @classmethod
    def splitThree(cls, d: Counter[int],
            s: list[tuple[int,...]],
            hasQueTou: bool) \
            -> set[tuple[tuple[int,...],...]]: # s: [(pai's),(pai's)]
        for key, val in d.items():
            if val > 0:
                break
        else:
            return {tuple(sorted(s))}
        result: set[tuple[tuple[int,...],...]] = set()
        if d[key + 1] > 0 and d[key + 2] > 0:
            d_temp = deepcopy(d)
            s_temp = deepcopy(s)
            d_temp[key] -= 1; d_temp[key + 1] -= 1; d_temp[key + 2] -= 1
            s_temp.append((key, key + 1, key + 2))
            result |= cls.splitThree(d_temp, s_temp, hasQueTou)
        if val >= 2 and not hasQueTou:
            d_temp = deepcopy(d)
            s_temp = deepcopy(s)
            d_temp[key] -= 2
            s_temp.append((key, key))
            result |= cls.splitThree(d_temp, s_temp, True)
        if val >= 3:
            d_temp = deepcopy(d)
            s_temp = deepcopy(s)
            d_temp[key] -= 3
            s_temp.append((key, key, key))
            result |= cls.splitThree(d_temp, s_temp, hasQueTou)
        return result
    @classmethod
    def splitOneColor(cls, d: Iterable[int]) -> set[tuple[tuple[int,...],...]]:
        barrel = Counter(d)
        return cls.splitThree(barrel, [], False)
    @classmethod
    def getTenOneColor(cls, d: Iterable[int]):
        barrel = Counter(d)
        results: list[set[tuple[tuple[int,...], ...]]] = []
        for i in range(MajHai.NUM_SHU):
            barrel[i] += 1
            result = MajHai.splitThree(barrel, [], False)
            results.append(result)
            barrel[i] -= 1
        return results
    @classmethod
    def splitAllColor(cls, hai: dict[int, Iterable[int]]) -> list[list[int]]:
        d_c: list[list[int]] = [[] for _ in range(cls.NUM_COLOR + cls.NUM_ZI)]
        for key, val in hai.items():
            d_c[key] = list(val)
        return d_c
    @classmethod
    def getTenAllColor(cls, barrel_all: list[list[int]]) \
        -> dict[int, list[dict[int, tuple[tuple[int,...],...]]]]:
        mod1_barrel: dict[int, list[int]] = {}
        mod2_barrel: dict[int, list[int]] = {}
        mod3_barrel: dict[int, list[int]] = {}
        for key, val in enumerate(barrel_all):
            if len(val) % 3 == 1:
                mod1_barrel[key] = val
            elif len(val) % 3 == 2:
                mod2_barrel[key] = val
            elif len(val) != 0:
                mod3_barrel[key] = val
        l = (len(mod1_barrel), len(mod2_barrel))
        if not (l == (1, 0) or l == (0, 2)):
            return {}
        resultsWithTen: dict[int, list[dict[int, tuple[tuple[int,...],...]]]] = {}
        # {26: [[(0, ((1,1),(1,2,3),(4,4,4)))], [(0, ((1,1,1),(2,3,4),(4,4)))]]}
        resultAllInHand: list[dict[int, tuple[tuple[int,...],...]]] = []
        # [[(0, ((1,1,1),(2,2,2),(3,3,3)))], [(0, ((1,2,3),(1,2,3),(1,2,3)))]]
        for key, val in mod3_barrel.items():
            if key < cls.NUM_COLOR:
                #数牌
                result = MajHai.splitOneColor(val)
                if len(result) == 0:
                    return {}
                resultAllInHand = [{key: r2, **r} for r in resultAllInHand for r2 in result]
            else:
                #字牌
                def _(val: list[int]):
                    while len(val) >= 3:
                        yield val[0], val[1], val[2]
                        val = val[3:]
                result2 = tuple(_(val))
                resultAllInHand = [{key: result2, **r} for r in resultAllInHand]
        if l == (1, 0): # 单骑
            key, val = list(mod1_barrel.items())[0]
            if key <= 2:
                #数牌
                result3 = MajHai.getTenOneColor(val)
                for i, s in enumerate(result3):
                    if len(s) == 0:
                        continue
                    hai = MajHai.getHaiId(i, key)
                    resultsWithTen[hai] = [{key: r2, **r} for r in resultAllInHand for r2 in s]
            else:
                #字牌单骑
                def _(val: list[int]):
                    while len(val) >= 3:
                        yield val[0], val[1], val[2]
                        val = val[3:]
                result4 = tuple(_(val)) + ((val[0], val[0]),)
                resultsWithTen[val[0] + cls.NUM_COLOR * cls.NUM_SHU] = [{key: result4, **r} for r in resultAllInHand]
        else: # 双碰
            (key1, val1), (key2, val2) = list(mod2_barrel.items())
            for k1, t1, k2, t2 in ((key1, val1, key2, val2), (key2, val2, key1, val1)):
                result5 = MajHai.getTenOneColor(t1)
                result6 = MajHai.splitOneColor(t2)
                if len(result6) == 0:
                    continue
                for i, re in enumerate(result5):
                    if len(re) == 0:
                        continue
                    hai = MajHai.getHaiId(i, k1)
                    resultsWithTen[hai] = [{k1: r1, k2: r2, **r} for r in resultAllInHand for r1 in re for r2 in result6]
        return resultsWithTen
    @classmethod
    def ten(cls, tehai: Sequence[Self]) -> dict[int, list[dict[int, tuple[tuple[int,...], ...]]]]:
        if len(tehai) % 3 != 1:
            return {}
        # 标准型
        barrel_all: list[list[int]] = [[] for _ in range(cls.NUM_COLOR + cls.NUM_ZI)]
        for hai in tehai:
            barrel_all[hai.barrel].append(hai.num)
        ting = MajHai.getTenAllColor(barrel_all)
        return ting
    @classmethod
    def tenQiTui(cls, tehai: Sequence[Self]) -> dict[int, list[dict[int, tuple[tuple[int,...], ...]]]]:
        if len(tehai) != 13:
            return {}
        # 七对子，龙七对包含
        tehai_l = sorted(tehai)
        tui_stack: list[tuple[Self, Self]] = []
        fu: Self | None = None
        last: Self | None = None
        for hai in tehai_l:
            if last is None:
                last = hai
            elif hai == last:
                tui_stack.append((last, hai))
                last = None
            elif fu is None:
                fu = last
                last = hai
            else:
                return {}
        if fu is None and last is not None:
            fu = last
        assert(fu is not None)
        val: dict[int, tuple[tuple[int,...],...]] = {fu.barrel: ((fu.num, fu.num),)}
        for hai1, hai2 in tui_stack:
            if hai1.barrel not in val:
                val[hai1.barrel] = ((hai1.num, hai2.num),)
            else:
                val[hai1.barrel] += ((hai1.num, hai2.num),)
        return {fu.hai: [val]}
    @classmethod
    def tenKokuShi(cls, tehai: Sequence[Self]) -> dict[int, list[dict[int, tuple[tuple[int,...],...]]]]:
        """need to be standard maj nums for this to work."""
        if len(tehai) != 13:
            return {}
        # 国士无双，不分拆
        s = set()
        for hai in tehai:
            if not hai.isYaokyuu:
                return {}
            s.add(hai.hai)
        all = {0,8,9,17,18,26,27,28,29,30,31,32,33}
        last = all - s
        if len(last) >= 2:
            return {}
        if len(last) == 1:
            d = tuple(x.hai for x in tehai)
            h = last.pop()
            return {h: [{0: (d,), 1: ((h,),)}]}
        else:
            #d == (0,8,9,17,18,26,27,28,29,30,31,32,33)
            d = tuple(all)
            return {t: [{0: (d,), 1: ((t,),)}] for t in all}
    @classmethod
    def tenShiSanBuKao(cls, tehai: Sequence[Self]) -> dict[int, list[dict[int, tuple[tuple[int,...],...]]]]:
        return {}
    @classmethod
    def tensu(cls, hai: int, results: list[dict[int, tuple[tuple[int,...],...]]], fuuro: list[FuuRo], els):
        return 0

class MajZjHai(MajHai):
    @functools.total_ordering
    class HeZhong(MajHai.HeZhong):
        dict_name: dict[tuple[int, int, int], str]
        dict_ten: dict[tuple[int, int, int], int]
        dict_name = {(0, 0, 1): "鸡和",
            (1, 1, 1): "平和", (1, 2, 1): "门前清", (1, 3, 1): "断幺九",
            (2, 1, 1): "混一色", (2, 1, 2): "清一色", (2, 2, 1): "九莲宝灯",
            (3, 1, 1): "自风：东", (3, 2, 1): "自风：南", (3, 3, 1): "自风：西", (3, 4, 1): "自风：北",
            (3, 5, 1): "番牌：白", (3, 6, 1): "番牌：发", (3, 7, 1): "番牌：中",
            (3, 8, 1): "小三元", (3, 8, 2): "大三元",
            (3, 9, 1): "小三风", (3, 9, 2): "大三风", (3, 9, 3): "小四喜", (3, 9, 4): "大四喜", (3, 10, 1): "字一色",
            (4, 1, 1): "对对和", (4, 2, 1): "二暗刻", (4, 2, 2): "三暗刻", (4, 2, 3): "四暗刻",
            (4, 3, 1): "一杠子", (4, 3, 2): "二杠子", (4, 3, 3): "三杠子", (4, 3, 4): "四杠子",
            (5, 1, 1): "一般高", (5, 1, 2): "两般高", (5, 1, 3): "一色三同顺", (5, 1, 4): "一色四同顺",
            (6, 1, 1): "三色同顺", (6, 2, 1): "三色小同刻", (6, 2, 2): "三色同刻",
            (7, 1, 1): "一气通贯", (7, 2, 1): "三连刻", (7, 2, 2): "四连刻",
            (8, 1, 1): "混全带幺", (8, 1, 2): "纯全带幺", (8, 1, 3): "混幺九", (8, 1, 4): "清幺九",
            (9, 1, 1): "海底捞月", (9, 1, 2): "河底捞鱼", (9, 2, 1): "岭上开花",
            (9, 3, 1): "抢杠", (9, 4, 1): "天和", (9, 4, 2): "地和",
            (10, 1, 1): "十三幺九", (10, 2, 1): "七对子"}
        dict_ten = {(0, 0, 1): 1,
            (1, 1, 1): 5, (1, 2, 1): 5, (1, 3, 1): 5,
            (2, 1, 1): 40, (2, 1, 2): 80, (2, 2, 1): 480,
            (3, 1, 1): 10, (3, 2, 1): 10, (3, 3, 1): 10, (3, 4, 1): 10,
            (3, 5, 1): 10, (3, 6, 1): 10, (3, 7, 1): 10,
            (3, 8, 1): 40, (3, 8, 2): 130,
            (3, 9, 1): 30, (3, 9, 2): 120, (3, 9, 3): 320, (3, 9, 4): 400, (3, 10, 1): 320,
            (4, 1, 1): 30, (4, 2, 1): 5, (4, 2, 2): 30, (4, 2, 3): 125,
            (4, 3, 1): 5, (4, 3, 2): 20, (4, 3, 3): 120, (4, 3, 4): 480,
            (5, 1, 1): 10, (5, 1, 2): 60, (5, 1, 3): 120, (5, 1, 4): 480,
            (6, 1, 1): 35, (6, 2, 1): 30, (6, 2, 2): 120,
            (7, 1, 1): 40, (7, 2, 1): 100, (7, 2, 2): 200,
            (8, 1, 1): 40, (8, 1, 2): 50, (8, 1, 3): 100, (8, 1, 4): 400,
            (9, 1, 1): 10, (9, 1, 2): 10, (9, 2, 1): 10,
            (9, 3, 1): 10, (9, 4, 1): 155, (9, 4, 2): 155,
            (10, 1, 1): 160, (10, 2, 1): 30}
        class Status(Enum):
            nomangan = 0
            shumangan = 1
            yimangan = 2
            def __str__(self):
                return {0: "", 1: "数满贯", 2: "役满贯"}[self.value]
        def __init__(self, t: tuple[int, int, int]):
            self.tuple = t
        def __str__(self):
            return MajZjHai.HeZhong.dict_name[self.tuple]
        @classmethod
        def ten(cls, l: 'list[MajZjHai.HeZhong]') -> 'tuple[MajZjHai.HeZhong.Status, int]':
            l.sort()
            ten = 0
            status = MajZjHai.HeZhong.Status.nomangan
            for h in l:
                t = MajZjHai.HeZhong.dict_ten[h.tuple]
                if t >= 320:
                    status = MajZjHai.HeZhong.Status.yimangan
                    ten = max(t, ten)
                elif ten < 320:
                    ten += t
                    if ten >= 320:
                        status = MajZjHai.HeZhong.Status.shumangan
                        ten = 320
            return (status, ten)
        def __lt__(self, other):
            if not isinstance(other, MajZjHai.HeZhong):
                return NotImplemented
            return self.tuple < other.tuple
        def __eq__(self, other):
            if not isinstance(other, MajZjHai.HeZhong):
                return NotImplemented
            return self.tuple == other.tuple
    @classmethod
    def ten(cls, tehai: Sequence[Self]) -> dict[int, list[dict[int, tuple[tuple[int,...],...]]]]:
        ten = MajHai.ten(tehai)
        for d in (MajHai.tenQiTui(tehai).items(), MajHai.tenKokuShi(tehai).items()):
            for key, val in d:
                if key in ten:
                    ten[key].extend(val)
                else:
                    ten[key] = val
        return ten
    @classmethod
    def tensu(cls, hai: int, results: list[dict[int, tuple[tuple[int,...],...]]], fuuros: list[FuuRo], els: tuple[PlayerPos, PlayerStatus]):
        def _f(result: dict[int, tuple[tuple[int,...],...]], fuuros: list[FuuRo], els: tuple[PlayerPos, PlayerStatus, int]) -> 'list[MajZjHai.HeZhong]':
            HeZhong: TypeAlias = MajZjHai.HeZhong
            l: list[HeZhong] = []
            #偶然类
            if els[1] & PlayerStatus.FIRST:
                l.append(HeZhong((9, 4, int(els[1] & PlayerStatus.NAKU) + 1)))    #天和&地和
            if els[1] & PlayerStatus.RINSHAN:
                l.append(HeZhong((9, 2, 1)))    #岭上开花
            if els[1] & PlayerStatus.HAIDI:
                l.append(HeZhong((9, 1, int(els[1] & PlayerStatus.NAKU) + 1)))    #海底捞月&河底捞鱼
            if els[1] & PlayerStatus.QIANKAN:
                l.append(HeZhong((9, 3, 1)))    #抢杠
            #特殊类
            if 0 in result and len(result[0][0]) >= 13:
                l.append(HeZhong((10, 1, 1)))   #十三幺九，不加算其余
                return l
            #排序
            tl: TypeAlias = list[tuple[tuple[int,...], int, bool]]
            shun: tl = []
            ke: tl = []
            gang: tl = []
            dui: tl = []
            #如果荣和，且只在暗刻中出现，则暗刻取消。暗顺对点数无影响故不判断
            if els[1] & PlayerStatus.NAKU:
                num = els[2] % 9
                barrel = els[2] // 9 if els[2] // 9 != 3 else num + els[2] // 9
                def _t(r: tuple[tuple[int,...],...]):
                    for val in r:
                        if len(val) == 3 and val[0] != val[1]:
                            return False
                    return True
                minke = (_t(result[barrel]), barrel, num)
            else:
                minke = (False, 0, 0)
            for barrel, vals in result.items():
                for val in vals:
                    if len(val) == 2:
                        dui.append((val, barrel, False))
                    elif len(val) > 2 and val[0] == val[1]:
                        if minke[0] and (barrel, val[0]) == minke[1:]:
                            ke.append((val, barrel, True))
                        else:
                            ke.append((val, barrel, False))
                    else:
                        shun.append((val, barrel, False))
            for fuuro in fuuros:
                if fuuro.status.what == FuuRoStatus.QI:
                    shun.append((fuuro.sorted, fuuro.barrel, True))
                elif fuuro.status.what == FuuRoStatus.PON:
                    ke.append((fuuro.sorted, fuuro.barrel, True))
                elif fuuro.status.what == FuuRoStatus.ANKAN:
                    gang.append((fuuro.sorted, fuuro.barrel, False))
                else:
                    gang.append((fuuro.sorted, fuuro.barrel, True))
            if not (len(dui) == 7 or len(dui) == 1 and len(shun) + len(ke) + len(gang) == 4):
                raise Not14()
            ke += gang
            al = shun + ke + dui
            shun.sort()
            ke.sort()
            gang.sort()
            if len(dui) == 7:
                l.append(HeZhong((10, 2, 1)))   #七对子
            else:
                #门断平类
                if not any(map(lambda x: x.status.what != FuuRoStatus.ANKAN, fuuros)):
                    l.append(HeZhong((1, 2, 1)))    #门前清，不与七对子复合
            if len(shun) == 4:
                l.append(HeZhong((1, 1, 1)))    #平和
            if all(map(lambda x: x[1] <= 2 and all(map(lambda y: y != 0 and y != 8, x[0])), al)):
                l.append(HeZhong((1, 3, 1)))    #断幺九
            colors = set(map(lambda x: x[1], al))
            if len(colors & {0, 1, 2}) == 1:
                if len(colors) == 1:
                    l.append(HeZhong((2, 1, 2)))    #清一色
                    hais: list[int] = list(functools.reduce(operator.add, result[colors.pop()]))
                    hais.remove(els[2] % 9)
                    hais.sort()
                    if tuple(hais) == (0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 8, 8):
                        l.append(HeZhong((2, 2, 1)))    #九莲宝灯
                else:
                    l.append(HeZhong((2, 1, 1)))    #混一色
            elif len(colors & {0, 1, 2}) == 0:
                l.append(HeZhong((3, 10, 1)))   #字一色
            zi = set(x[1] for x in ke if x[1] >= 3)
            zi_dui = dui[0][1]
            for i in (7, 8, 9):
                if i in zi:
                    l.append(HeZhong((3, i - 2, 1)))    #番牌：白发中
            sanyuan = {7, 8, 9}
            if sanyuan <= zi:
                l.append(HeZhong((3, 8, 2)))    #大三元
            elif len(sanyuan - zi) == 1 and zi_dui in sanyuan - zi:
                l.append(HeZhong((3, 8, 1)))    #小三元
            sixi = {3, 4, 5, 6}
            if sixi <= zi:
                l.append(HeZhong((3, 9, 4)))    #大四喜
            elif len(sixi - zi) == 1:
                if zi_dui in sixi - zi:
                    l.append(HeZhong((3, 9, 3)))    #小四喜
                else:
                    l.append(HeZhong((3, 9, 2)))    #大三风
            elif len(sixi - zi) == 2 and zi_dui in sixi - zi:
                l.append(HeZhong((3, 9, 1)))    #小三风
            if int(els[0]) + 3 in zi:
                l.append(HeZhong((3, int(els[0]) + 1, 1)))   #自风
            if len(ke) == 4:
                l.append(HeZhong((4, 1, 1)))    #对对和
            anke = len(list(filter(lambda x: not x[2], ke)))
            if anke >= 2:
                l.append(HeZhong((4, 2, anke - 1))) #x暗刻
            if len(gang) != 0:
                l.append(HeZhong((4, 3, len(gang))))    #x杠子
            t = []
            if len(shun) >= 2:
                for i in range(len(shun) - 1):
                    if shun[i][0:2] == shun[i + 1][0:2]:
                        t.append(i)
            if len(t) == 3:
                l.append(HeZhong((5, 1, 4)))    #一色四同顺
            elif len(t) == 2:
                if t[1] == t[0] + 1:
                    l.append(HeZhong((5, 1, 3)))    #一色三同顺
                else:
                    l.append(HeZhong((5, 1, 2)))    #两般高
            elif len(t) == 1:
                l.append(HeZhong((5, 1, 1)))    #一般高
            for i2, j, k in itertools.combinations(shun, 3):
                if i2[0] == j[0] == k[0] and (i2[1], j[1], k[1]) == (0, 1, 2):
                    l.append(HeZhong((6, 1, 1)))    #三色同顺
                    break
                elif i2[1] == j[1] == k[1] and (i2[0], j[0], k[0]) == ((0, 1, 2), (3, 4, 5), (6, 7, 8)):
                    l.append(HeZhong((7, 1, 1)))    #一气通贯
                    break
            if len(ke) >= 2:
                for i2, j, k in itertools.combinations(itertools.chain(ke, dui), 3):
                    if i2[0][0] == j[0][0] == k[0][0] and {i2[1], j[1], k[1]} == {0, 1, 2}:
                        if len(k[0]) == 2:
                            l.append(HeZhong((6, 2, 1)))    #三色小同刻
                        else:
                            l.append(HeZhong((6, 2, 2)))    #三色同刻
                        break
            if len(ke) == 4 and ke[0][1] == ke[1][1] == ke[2][1] == ke[3][1] and ke[0][0][0] + 3 == ke[1][0][0] + 2 == ke[2][0][0] + 1 == ke[3][0][0]:
                l.append(HeZhong((7, 2, 2)))    #四连刻
            else:
                for i2, j, k in itertools.combinations(ke, 3):
                    if i2[1] == j[1] == k[1] and i2[0][0] + 2 == j[0][0] + 1 == k[0][0]:
                        l.append(HeZhong((7, 2, 1)))    #三连刻
                        break
            if all(map(lambda x: x[1] <= 2 and all(map(lambda y: y == 0 or y == 8, x[0])), al)):
                l.append(HeZhong((8, 1, 4)))    #清幺九
            elif all(map(lambda x: x[1] >= 3 or x[1] <= 2 and all(map(lambda y: y == 0 or y == 8, x[0])), al)):
                l.append(HeZhong((8, 1, 3)))    #混幺九
            elif all(map(lambda x: x[1] <= 2 and any(map(lambda y: y == 0 or y == 8, x[0])), al)):
                l.append(HeZhong((8, 1, 2)))    #纯全带幺
            elif all(map(lambda x: x[1] >= 3 or x[1] <= 2 and any(map(lambda y: y == 0 or y == 8, x[0])), al)):
                l.append(HeZhong((8, 1, 1)))    #混全带幺
            if len(l) == 0:
                l.append(HeZhong((0, 0, 1)))    #鸡和
            return l
        _max: tuple[list[MajZjHai.HeZhong], MajZjHai.HeZhong.Status, int] \
             = ([], MajZjHai.HeZhong.Status.nomangan, 0)
        els2 = els + (hai,)
        for result in results:
            _now = _f(result, fuuros, els2)
            m, ten = MajZjHai.HeZhong.ten(_now)
            if ten > _max[-1]:
                _max = (_now, m, ten)
        return _max

P = TypeVar('P', bound='Player')

class Player(Generic[H]):
    Hai: type[H]
    def __init_subclass__(cls, Hai: type[H], **kwargs):
        super().__init_subclass__(**kwargs)
        cls.Hai = Hai
    TDoable: TypeAlias = tuple[str,...]
    doable_dahai: TDoable = ('kiri', 'ankan', 'kakan', 'tsumo')
    doable_naku_shang: TDoable = ('qi', 'pon', 'daiminkan', 'ron')
    doable_naku_all: TDoable = ('pon', 'daiminkan', 'ron')
    doable_kakan: TDoable = ('ron',)
    doable_ankan: TDoable = ()
    def __init__(self, board: 'MajBoard', pos: int):
        self.tehai: list[H] = []
        self.fuuro: list[FuuRo] = []
        self.ho: list[tuple[H, HaiHoStatus]] = []
        self.ten: dict[int, list[dict[int, tuple[tuple[int, ...], ...]]]] = {}
        self.board = board
        self.tensu: int = 0
        self.pos = pos
    @property
    def index(self):
        return self.board.players.index(self)
    def give(self, tehai: Sequence[H] | H):
        if isinstance(tehai, MajHai):
            self.tehai.append(tehai) # type: ignore
        else:
            self.tehai.extend(tehai)
    def sort(self):
        self.tehai.sort()
    def ten_gen(self, special=False):
        if special:
            self.ten = self.Hai.ten(self.tehai[:-1])
        else:
            self.ten = self.Hai.ten(self.tehai)
    def tsumo_check(self) -> list[None]:
        if self.tehai[-1].hai in self.ten:
            return [None]
        else:
            return []
    def tsumo_do(self, n: None) -> Generator[PlayerStatus, PlayerOption, None]:
        raise Win(self, None)
        yield PlayerStatus.DAHAI
    def kiri_check(self):
        l: list[H] = []
        for hai in self.tehai:
            if all(not hai.isAllSame(x) for x in l):
                l.append(hai)
        return l
    def kiri_do(self, hai: H) -> Generator[PlayerStatus, PlayerOption, None]:
        status = HaiHoStatus.TSUMOKIRI if hai is self.tehai[-1] else HaiHoStatus.TEDASHI
        self.tehai.remove(hai)
        self.sort()
        self.ten_gen()
        self.ho.append((hai, status))
        ret = yield PlayerStatus.DAHAI
        if not ret:
            self.ho[-1] = self.ho[-1][0], self.ho[-1][1] | HaiHoStatus.NAKARERU
        else:
            self.board.now = self.board.next(self.board.now)
            self.board.playerstatus = self.board.status
            self.board.players[self.board.now].give(self.board.tsumo())
    def ankan_check(self) -> list[tuple[H, H, H, H]]:
        return [(i, j, k, l) for i, j, k, l in itertools.combinations(self.tehai, 4) if i == j == k == l]
    def ankan_do(self, tpl: tuple[H, H, H, H]) -> Generator[PlayerStatus, PlayerOption, None]:
        for i in tpl:
            self.tehai.remove(i)
        self.fuuro.append(FuuRo(FuuRoStatus.ANKAN, tpl))
        yield PlayerStatus.QIANANKAN
        self.board.playerstatus |= PlayerStatus.RINSHAN
        self.give(self.board.rinshan())
    def kakan_check(self) -> list[tuple[H, FuuRo]]:
        def _():
            for fuuro in self.fuuro:
                if not fuuro.status & FuuRoStatus.PON:
                    continue
                for hai in self.tehai:
                    if hai == fuuro.hai[0]:
                        yield hai, fuuro
        return list(_())
    def kakan_do(self, tpl: tuple[H, FuuRo]) -> Generator[PlayerStatus, PlayerOption, None]:
        hai, fuuro = tpl
        self.tehai.remove(hai)
        if (yield PlayerStatus.QIANKAN):
            fuuro.status ^= (FuuRoStatus.PON | FuuRoStatus.KAKAN)
            fuuro.hai += (hai,)
            fuuro.sorted = tuple(sorted(map(lambda x: x.num, fuuro.hai)))
        self.board.playerstatus |= PlayerStatus.RINSHAN
        self.give(self.board.rinshan())
    def qi_check(self, hai: H) -> list[tuple[H, H]]:
        l: list[tuple[H, H]] = []
        for i, j in itertools.combinations(self.tehai, 2):
            if i.isaddOne(j) and j.isaddOne(hai) or i.isaddOne(hai) and hai.isaddOne(j) or hai.isaddOne(i) and i.isaddOne(j):
                if not any(x0.isAllSame(i) and x1.isAllSame(j) for x0, x1 in l):
                    l.append((i, j))
        return l
    def qi_do(self, tpl: tuple[FuuRoStatus, H, tuple[H, H]]) -> None:
        for hai in tpl[2]:
            self.tehai.remove(hai)
        self.fuuro.append(FuuRo(tpl[0] | FuuRoStatus.QI, (tpl[1],) + tpl[2]))
    def pon_check(self, hai) -> list[tuple[H, H]]:
        l: list[tuple[H, H]] = []
        for i, j in itertools.combinations(self.tehai, 2):
            if i == j == hai:
                if not any(map(lambda x: x[0].isAllSame(i) and x[1].isAllSame(j), l)):
                    l.append((i, j))
        return l
    def pon_do(self, tpl: tuple[FuuRoStatus, H, tuple[H, H]]) -> None:
        for hai in tpl[2]:
            self.tehai.remove(hai)
        self.fuuro.append(FuuRo(tpl[0] | FuuRoStatus.PON, (tpl[1],) + tpl[2]))
    def daiminkan_check(self, hai) -> list[tuple[H, H, H]] | None:
        for i, j, k in itertools.combinations(self.tehai, 3):
            if i == j == k == hai:
                return [(i, j, k)]
        return None
    def daiminkan_do(self, tpl: tuple[FuuRoStatus, H, tuple[H, H, H]]) -> None:
        for hai in tpl[2]:
            self.tehai.remove(hai)
        self.fuuro.append(FuuRo(tpl[0] | FuuRoStatus.DAIMINKAN, (tpl[1],) + tpl[2]))
        self.give(self.board.rinshan())
    def ron_check(self, hai) -> list[None]:
        if hai in self.ten:
            return [None]
        else:
            return []
    def ron_do(self, tpl: tuple[FuuRoStatus, H, None]) -> None:
        raise Win(self, tpl[1])
    def do_dahai(self, status: PlayerStatus) -> Generator[tuple[Self, PlayerOption, dict[str, Any]], tuple[PlayerOption, H, Any], tuple[H, Generator]]:
        option = PlayerOption.NOTHING
        d = {}
        tpl = self.doable_dahai
        for s in tpl:
            l = self.__getattribute__(s + '_check')()
            if len(l) != 0:
                option |= PlayerOption[s]
                d[s] = l
        option_chosen, hai, t = yield (self, option, d)
        if option_chosen != PlayerOption.NOTHING:
            name = option_chosen.name
            gen = self.__getattribute__(name + '_do')(t) # type: ignore
            return hai, gen
        raise ValueError
    def do_naku(self, status: PlayerStatus, pos: FuuRoStatus, hai: H) -> Generator[tuple[PlayerOption, dict[str, Any]], tuple[PlayerOption, Any], None]:
        option = PlayerOption.NOTHING
        d = {}
        if status & PlayerStatus.QIANKAN:
            tpl = self.doable_kakan
        elif status & PlayerStatus.QIANANKAN:
            tpl = self.doable_ankan
        elif pos == FuuRoStatus.KAMICHA:
            tpl = self.doable_naku_shang
        else:
            tpl = self.doable_naku_all
        for s in tpl:
            l = self.__getattribute__(s + '_check')(hai)
            if len(l) != 0:
                option |= PlayerOption[s]
                d[s] = l
        option_chosen, t = yield (option, d)
        self.__getattribute__(option_chosen.name + '_do')((pos, hai, t)) # type: ignore
        return

B = TypeVar('B', bound='MajBoard')
O = TypeVar('O', bound='MajBoard.NakuOption')
class MajBoard(Generic[H, P]):
    Hai: type[H]
    Player: type[P]
    def __init_subclass__(cls, Hai: type[H], Player: type[P], **kwargs):
        super().__init_subclass__(**kwargs)
        cls.Hai = Hai
        cls.Player = Player
    def __init__(self):
        self.yama = None
        self.players: list[Player] = [self.Player(self, PlayerPos.TON), self.Player(self, PlayerPos.NAN), self.Player(self, PlayerPos.SHA), self.Player(self, PlayerPos.PE)]
        self.toncha = 0
        self.chiicha = 0
        self.isBegin = False
    def __iter__(self):
        try:
            kyoku = self.kyoku()
            yield from kyoku
        except:
            pass
    def haipai(self):
        #配牌
        self.yama = list(map(self.Hai, range(136)))
        random.shuffle(self.yama)
        for p in self.players:
            p.give(self.yama[0:4])
            self.yama = self.yama[4:]
        for p in self.players:
            p.give(self.yama.pop(0))
            p.ten_gen(True)
        self.players[self.toncha].give(self.yama.pop(0))
        for p in self.players:
            p.sort()
    def tsumo(self): # 需被重载
        #摸牌，需包括王牌判定，需改变海底状态
        return self.yama.pop()
    def rinshan(self): # 需被重载
        #摸岭上牌，需包括王牌判定
        return self.yama.pop()
    class NakuOption:
        def __init__(self, pos: FuuRoStatus, options: PlayerOption, args: dict[str, Any]):
            self.pos = pos
            self.options = options
            self.args = args
            self.chosen = None
        def choose(self, option: PlayerOption, arg):
            self.chosen = option
            self.arg = arg
        def isPass(self):
            return self.options == PlayerOption.NOTHING
        def isLargerThan(self, other):
            return self.chosen > other.options
    def nakujun(self, d_send: dict[int, O]) -> Generator[bool | dict[int, O], tuple[int, O] | None, tuple[int, O] | None]:
        n = len(d_send)
        if n == 0:
            yield d_send
            return
        key_wait = set(d_send.keys())
        while len(key_wait) >= 0:
            i, option_chosen = (yield d_send)
            key_wait -= {i}
            if all(map(lambda x: option_chosen.isLargerThan(d_send[x]), key_wait)):
                yield True
                break
        if option_chosen.chosen == PlayerOption.NOTHING:
            return
        else:
            return (i, option_chosen)
    @classmethod
    def next(cls, i):
        if i != 3:
            return i + 1
        else:
            return 0
    def kyoku(self):
        for p in self.players:
            pos = p.index - self.toncha
            p.pos = PlayerPos(pos if pos >= 0 else pos + 4)
        self.haipai()
        for i, p in enumerate(self.players):
            v = i - self.toncha
            if v < 0:
                v += 4
            p.pos = PlayerPos(v)
        self.now = self.toncha
        self.status = PlayerStatus.FIRST | PlayerStatus.TIAN # 场有状态
        self.playerstatus = self.status # 玩家私有状态
        while 1:
            hai, ret = yield from self.players[self.now].do_dahai(PlayerStatus.DAHAI | self.playerstatus)
            status = PlayerStatus.NAKU | PlayerStatus(next(ret))
            def _():
                for i in range(4):
                    if i == self.now:
                        continue
                    pos = self.players[self.now].pos - self.players[i].pos
                    yield i, (pos, self.players[i].do_naku(status | self.status, pos, hai))
            l = dict(_()) # type: dict[int, tuple[FuuRoStatus, Generator]]
            d_send = {} # type: dict[int, NakuOption]
            for i, n in l.items():
                na = self.NakuOption(n[1][0], *(next(n[1][1])))
                if na.isPass():
                    n[1].close() # no bug?
                else:
                    d_send[i] = na
            # 处理荣碰吃的顺序
            ret_nakujun = yield from self.nakujun(d_send)
            if ret_nakujun is None:
                #清理
                for i, g in l:
                    g[1].close()
                try:
                    #调整状态，继续至下家，摸牌
                    ret.send(True)
                except StopIteration:
                    pass
                if self.now == self.toncha:
                    #第一巡结束
                    self.status &= ~PlayerStatus.TIAN
            else:
                i_naku, option_chosen = ret_nakujun
                #清理
                for i, g in l:
                    if i != i_naku:
                        g[1].close()
                #处理鸣牌
                try:
                    l[i_naku][1].send((option_chosen.chosen, option_chosen.arg))
                except StopIteration:
                    pass
                #鸣牌破第一巡
                self.status &= ~PlayerStatus.TIAN
                ret.send(False)
                #玩家顺序
                self.now = i_naku
            #第一张牌结束
            self.status &= ~PlayerStatus.FIRST

class ZjPlayer(Player, Hai=MajZjHai):
    pass

class MajZjBoard(MajBoard, Hai=MajZjHai, Player=ZjPlayer):
    pass

class MajRichiHai(MajHai):
    class HeZhong:
        dict_str = {(1, 1): "立直", (1, 2): "两立直", (1, 3): "一发", (1, 4): "自摸",
            (2, 1): "东", (2, 2): "南", (2, 3): "西", (2, 4): "北",
            (2, 5): "白", (2, 6): "发", (2, 7): "中",
            (3, 1): "枪杠", (3, 2): "岭上开花", (3, 3): "海底摸月", (3, 4): "河底捞鱼",
            (4, 1): "宝牌", (4, 2): "红宝牌", (4, 3): "里宝牌", (4, 4): "北宝牌",
            (5, 1): "断幺九",
            (6, 1): "平和",
            (7, 1): "一杯口", (7, 2): "两杯口",
            (8, 1): "三色同顺", (8, 2): "三色同刻", (8, 3): "一气通贯",
            (9, 1): "七对子",
            (10, 1): "对对和",
            (11, 1): "三暗刻", (11, 2): "四暗刻", (11, 3): "四暗刻单骑",
            (12, 1): "三杠子", (12, 2): "四杠子",
            (13, 1): "小三元", (13, 2): "大三元",
            (14, 1): "小四喜", (14, 2): "大四喜",
            (15, 1): "混全带", (15, 2): "纯全带", (15, 3): "混老头", (15, 4): "清老头",
            (16, 1): "混一色", (16, 2): "清一色", (16, 3): "绿一色", (16, 4): "九莲宝灯", (16, 5): "纯正九莲宝灯",
            (17, 1): "天和", (17, 2): "地和",
            (18, 1): "字一色",
            (19, 1): "国士无双", (19, 2): "国士无双十三面",
            (20, 1): "流局满贯"}
        class Han(IntEnum):
            Futsu = 0
            Menzen = 1
            Kuisagari = 2
            Kazoe = 3
        dict_ten = {(1, 1): (1, 1), (1, 2): (1, 1), (1, 3): (1, 1), (1, 4): (1, 1),
            (2, 1): (1, 3), (2, 2): (1, 3), (2, 3): (1, 3), (2, 4): (1, 3),
            (2, 5): (1, 0), (2, 6): (1, 0), (2, 7): (1, 0),
            (3, 1): (1, 0), (3, 2): (1, 0), (3, 3): (1, 0), (3, 4): (1, 0),
            (4, 1): (1, 3), (4, 2): (1, 3), (4, 3): (1, 3), (4, 4): (1, 3),
            (5, 1): (1, 0),
            (6, 1): (1, 1),
            (7, 1): (1, 1), (7, 2): (3, 1),
            (8, 1): (2, 2), (8, 2): (2, 0), (8, 3): (2, 2),
            (9, 1): (2, 1),
            (10, 1): (2, 0),
            (11, 1): (2, 0), (11, 2): (13, 0), (11, 3): (26, 0),
            (12, 1): (2, 0), (12, 2): (13, 0),
            (13, 1): (2, 0), (13, 2): (13, 0),
            (14, 1): (13, 0), (14, 2): (26, 0),
            (15, 1): (2, 2), (15, 2): (3, 2), (15, 3): (2, 0), (15, 4): (13, 0),
            (16, 1): (3, 2), (16, 2): (6, 2), (16, 3): (13, 0), (16, 4): (13, 0), (16, 5): (26, 0),
            (17, 1): (13, 0), (17, 2): (13, 0),
            (18, 1): (13, 0),
            (19, 1): (13, 0), (19, 2): (26, 0),
            (20, 1): (5, 0)}
            
