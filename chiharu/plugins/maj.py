import random
import functools
import itertools
import abc
import asyncio
import operator
from copy import copy
from enum import Enum, IntFlag, IntEnum
from typing import Sequence, Union, TypeVar, Generic, Type, Dict, List, Tuple, Set, FrozenSet, Iterable, Union, Generator, Any, Callable

H = TypeVar('H', bound='MajHai')
class MajErr(Exception):
    pass
class FuuRoNotValid(MajErr):
    def __init__(self, status: 'FuuRoStatus', hai: Sequence[H]):
        self.args = (status, hai)
    def __str__(self):
        pass
class MajIdError(MajErr):
    def __init__(self, id):
        self.args = (id,)
    def __str__(self):
        return 'Id %i out of bound' % self.args
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
    def __sub__(self, other) -> FuuRoStatus:
        v = other.value - self.value - 1
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
class FuuRo:
    def __init__(self, status: FuuRoStatus, hai: Tuple[H]):
        self.status = status
        self.hai = hai
        self.sorted = tuple(sorted(map(lambda x: x.num, hai)))
    def __str__(self):
        return '(%s %s %s)' % (self.status.what_str, self.status.who_str, ' '.join(map(str, self.hai)))
    @property
    def barrel(self):
        return self.hai[0].barrel
    @property
    def isValid(self):
        if self.status.what == FuuRoStatus.QI:
            return len(self.hai) == 3 \
                and functools.reduce(lambda x, y: x and y, map(lambda x: x.barrel == self.hai[0].barrel, self.hai)) \
                and self.sorted[2] == self.sorted[1] + 1 == self.sorted[0] + 2
        else:
            return functools.reduce(lambda x, y: x and y, map(lambda x: x.hai == self.hai[0].hai, self.hai)) \
                and (self.status.what == FuuRoStatus.PON and len(self.hai) == 3 \
                or self.status.what != FuuRoStatus.PON and len(self.hai) == 4)

@functools.total_ordering
class MajHai:
    class HeZhong:
        pass
    color_dict = {0: 'm', 1: 'p', 2: 's', 3: 'z'}
    MAX = 9
    SAME = 4
    ZI_MAX = 7
    COLOR = 3
    def __init__(self, id: Union[int, str]):
        if type(id) == int:
            if not (id >= 0 and id < self.SAME * (self.MAX * self.COLOR + self.ZI_MAX)):
                raise MajIdError(id)
            self.id = id
            self.hai = id // self.SAME
            self.num = self.hai % self.MAX
            self.color = self.hai // self.MAX # 0: m, 1: p, 2: s, 3: z
            self.barrel = self.color if self.color != self.COLOR else self.num + self.color
        elif type(id) == str:
            if not (len(id) == 2 and id[0] in '0123456789' and id[1] in 'mpsz'):
                raise MajIdError(id)
            self.num = int(id[0]) - 1
            self.color = {'m': 0, 'p': 1, 's': 2, 'z': 3}[id[1]]
            self.hai = self.color * 9 + self.num
            self.barrel = self.color if self.color != 3 else self.num + self.color
            if not (self.hai < 136):
                raise MajIdError(id)
            self.id = -1
    @property
    def color_c(self):
        return MajHai.color_dict[self.color]
    def __str__(self):
        return '%i%s' % (self.num + 1, self.color_c)
    def __lt__(self, other):
        return self.hai < other.hai
    def __eq__(self, other): # 赤ドラ same
        return self.hai == other.hai
    def isSame(self, other): # 赤ドラ differs
        return self.hai == other.hai
    def isaddOne(self, other):
        return self.color == other.color and self.color != 3 and self.num + 1 == other.num
    @property
    def isYaokyuu(self):
        return self.color == 3 or self.num == 0 or self.num == 8
    @property
    def isDummy(self):
        return self.id == -1
    @staticmethod
    def _hai(num, barrel):
        if barrel <= 2:
            return barrel * 9 + num
        else:
            return 27 + num
    @staticmethod
    def _barrel(val: Iterable[int]) -> List[List[int]]:
        d = list(map(lambda x: [], range(MajHai.MAX)))
        for hai in val:
            d[hai].append(hai)
        return d
    @staticmethod
    def _3(d: List[List[int]], s: List[Tuple[int,...]], hasTou: bool) -> Set[Tuple[Tuple[int,...],...]]: # s: [(pai's),(pai's)]
        for key, val in enumerate(d):
            if len(val) != 0:
                break
        else:
            return set((tuple(sorted(s)),))
        result = set()
        if key < MajHai.MAX - 2 and len(d[key + 1]) != 0 and len(d[key + 2]) != 0:
            d_temp = list(map(copy, d))
            s_temp = list(map(copy, s))
            s_temp.append((d_temp[key].pop(), d_temp[key + 1].pop(), d_temp[key + 2].pop()))
            result |= MajHai._3(d_temp, s_temp, hasTou)
        if len(val) >= 2 and not hasTou:
            d_temp = list(map(copy, d))
            s_temp = list(map(copy, s))
            s_temp.append((d_temp[key].pop(), d_temp[key].pop()))
            result |= MajHai._3(d_temp, s_temp, True)
        if len(val) >= 3:
            d_temp = list(map(copy, d))
            s_temp = list(map(copy, s))
            s_temp.append((d_temp[key].pop(), d_temp[key].pop(), d_temp[key].pop()))
            result |= MajHai._3(d_temp, s_temp, hasTou)
        return result
    @staticmethod
    def _chai(d: Iterable[int]) -> Tuple[Set[Tuple[Tuple[int,...],...]], List[List[int]]]:
        barrel = MajHai._barrel(d)
        return MajHai._3(barrel, [], False)
    @staticmethod
    def _ting(d: Iterable[int]):
        barrel = MajHai._barrel(d)
        results = []
        for i in range(MajHai.MAX):
            barrel[i].append(i)
            result = MajHai._3(barrel, [], False)
            results.append(result)
            barrel[i].pop()
        return results
    @staticmethod
    def _barrel_all(hai: Dict[int, Iterable[int]]) -> List[List[int]]:
        d_c = list(map(lambda x: [], range(10)))
        for key, val in hai.items():
            d_c[key] = list(val)
        return d_c
    @staticmethod
    def ting_all(barrel_all: List[List[int]]) -> Dict[int, List[Dict[int, Tuple[Tuple[int,...],...]]]]:
        mod1_barrel = []
        mod2_barrel = []
        mod3_barrel = [] # type: List[Tuple[int, List[int]]]
        for key, val in enumerate(barrel_all):
            if len(val) % 3 == 1:
                mod1_barrel.append((key, val))
            elif len(val) % 3 == 2:
                mod2_barrel.append((key, val))
            elif len(val) != 0:
                mod3_barrel.append((key, val))
        l = (len(mod1_barrel), len(mod2_barrel))
        if not (l == (1, 0) or l == (0, 2)):
            return {}
        results = {} # type: Dict[int, List[List[Tuple[int, Tuple[Tuple[int,...],...]]]]]
        # {26: [[(0, ((1,1),(1,2,3),(4,4,4)))], [(0, ((1,1,1),(2,3,4),(4,4)))]]}
        result_nonten = [[]] # type: List[List[Tuple[int, Tuple[Tuple[int,...],...]]]]
        # [[(0, ((1,1,1),(2,2,2),(3,3,3)))], [(0, ((1,2,3),(1,2,3),(1,2,3)))]]
        for key, val in mod3_barrel: # val: type: List[int]
            if key <= 2:
                #数牌
                result = MajHai._chai(val) # type: Set[Tuple[Tuple[int,...],...]]
                if len(result) == 0:
                    return {}
                result_nonten = [r + [(key, r2)] for r in result_nonten for r2 in result]
            else:
                #字牌
                def _(val):
                    while len(val) >= 3:
                        yield tuple(val[0:3])
                        val = val[3:]
                result = tuple(_(val))
                result_nonten = [r + [(key, result)] for r in result_nonten]
        if l == (1, 0):
            key, val = mod1_barrel[0]
            if key <= 2:
                #数牌
                result = MajHai._ting(val) # type: List[Set[Tuple[Tuple[int,...],...]]]
                for i, s in enumerate(result):
                    if len(s) == 0:
                        continue
                    hai = MajHai._hai(i, key)
                    results[hai] = [r + [(key, r2)] for r in result_nonten for r2 in s]
            else:
                #字牌单骑
                def _(val):
                    while len(val) >= 3:
                        yield tuple(val[0:3])
                        val = val[3:]
                result = tuple(_(val)) + ((val[0], val[0]),)
                results[val[0] + 27] = [r + [(key, result)] for r in result_nonten]
        else:
            ((key1, val1), (key2, val2)) = mod2_barrel
            for k1, t1, k2, t2 in ((key1, val1, key2, val2), (key2, val2, key1, val1)):
                result1 = MajHai._ting(t1) # type: List[Set[Tuple[Tuple[int,...],...]]]
                result2 = MajHai._chai(t2) # type: Set[Tuple[Tuple[int,...],...]]
                if len(result2) == 0:
                    continue
                l0 = len(result_nonten)
                l2 = len(result2)
                for i, re in enumerate(result1):
                    if len(re) == 0:
                        continue
                    hai = MajHai._hai(i, k1)
                    l1 = len(re)
                    results[hai] = [r + [(k1, r1)] + [(k2, r2)] for r in result_nonten for r1 in re for r2 in result2]
        for key in results:
            results[key] = list(map(dict, results[key]))
        return results
    @staticmethod
    def ten(tehai: List[H]) -> Dict[int, List[Dict[int, Tuple[Tuple[int,...],...]]]]:
        assert(len(tehai) % 3 == 1)
        #标准型
        barrel_all = list(map(lambda x: [], range(10)))
        for hai in tehai:
            barrel_all[hai.barrel].append(hai.num)
        ting = MajHai.ting_all(barrel_all)
        if not ting:
            return {}
        return ting
    @staticmethod
    def qitui(tehai: List[H]) -> Dict[int, List[Dict[int, Tuple[Tuple[int,...],...]]]]:
        if len(tehai) != 13:
            return {}
        #七对子，龙七对包含
        tehai.sort()
        tui_stack = []
        fu = None
        last = None
        for hai in tehai:
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
        assert(fu is not None and len(tui_stack) == 6)
        val = {fu.barrel: ((fu.num, fu.num),)}
        for hai1, hai2 in tui_stack:
            if hai1.barrel not in val:
                val[hai1.barrel] = ((hai1.num, hai2.num),)
            else:
                val[hai1.barrel] += ((hai1.num, hai2.num),)
        return {fu.hai: [val]}
    @staticmethod
    def kokushimusou(tehai: List[H]) -> Dict[int, List[Dict[int, Tuple[Tuple[int,...],...]]]]:
        if len(tehai) != 13:
            return {}
        #国士无双，不分拆
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
            d = tuple(map(lambda x: x.hai, tehai))
            hai = last.pop()
            return {hai: [{0: (d,), 1: ((hai,),)}]}
        else:
            #d == (0,8,9,17,18,26,27,28,29,30,31,32,33)
            d = tuple(all)
            def _():
                for key in d:
                    for t in all:
                        yield t, [{0: (d,), 1: ((t,),)}]
            return dict(_())
    @staticmethod
    def tensu(hai: int, results: List[Dict[int, Tuple[Tuple[int,...],...]]], fuuro: List[FuuRo], els):
        return 0

class MajZjHai(MajHai):
    @functools.total_ordering
    class HeZhong:
        dict_str = {(0, 0, 1): "鸡和",
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
        def __init__(self, t: Tuple[int, int, int]):
            self.tuple = t
        def __str__(self):
            return MajZjHai.HeZhong.dict_str[self.tuple]
        def int(self):
            return MajZjHai.HeZhong.dict_ten[self.tuple]
        @staticmethod
        def ten(l: 'List[MajZjHai.HeZhong]') -> 'Tuple[MajZjHai.HeZhong.Status, int]':
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
            return self.tuple < other.tuple
        def __eq__(self, other):
            return self.tuple == other.tuple
    @staticmethod
    def ten(tehai: 'List[MajZjHai]') -> Dict[int, List[Dict[int, Tuple[Tuple[int,...],...]]]]:
        ten = MajHai.ten(tehai)
        for d in (MajHai.qitui(tehai).items(), MajHai.kokushimusou(tehai).items()):
            for key, val in d:
                if key in ten:
                    ten[key].extend(val)
                else:
                    ten[key] = val
        return ten
    @staticmethod
    def tensu(hai: int, results: List[Dict[int, Tuple[Tuple[int,...],...]]], fuuros: List[FuuRo], els: Tuple[PlayerPos, PlayerStatus]) -> 'Tuple[List[MajZjHai.HeZhong], MajZjHai.HeZhong.Status, int]':
        def _f(result: Dict[int, Tuple[Tuple[int,...],...]], fuuros: List[FuuRo], els: Tuple[PlayerPos, PlayerStatus, int]) -> 'List[MajZjHai.HeZhong]':
            HeZhong = MajZjHai.HeZhong
            l = []
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
            shun, ke, gang, dui = [], [], [], []
            #如果荣和，且只在暗刻中出现，则暗刻取消。暗顺对点数无影响故不判断
            if els[1] & PlayerStatus.NAKU:
                num = els[2] % 9
                barrel = els[2] // 9 if els[2] // 9 != 3 else num + els[2] // 9
                def _t(r):
                    for val in r:
                        if len(val) == 3 and val[0] != val[1]:
                            return False
                    return True
                minke = (_t(result[barrel]), barrel, num)
            else:
                minke = (False,)
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
                    hais = list(functools.reduce(operator.add, result[colors.pop()]))
                    print(hais)
                    hais.remove(els[2] % 9)
                    hais.sort()
                    if tuple(hais) == (0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 8, 8):
                        l.append(HeZhong((2, 2, 1)))    #九莲宝灯
                else:
                    l.append(HeZhong((2, 1, 1)))    #混一色
            elif len(colors & {0, 1, 2}) == 0:
                l.append(HeZhong((3, 10, 1)))   #字一色
            zi = set(filter(lambda x: x >= 3, map(lambda x: x[1], ke)))
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
            for i, j, k in itertools.combinations(shun, 3):
                if i[0] == j[0] == k[0] and (i[1], j[1], k[1]) == (0, 1, 2):
                    l.append(HeZhong((6, 1, 1)))    #三色同顺
                    break
                elif i[1] == j[1] == k[1] and (i[0], j[0], k[0]) == ((0, 1, 2), (3, 4, 5), (6, 7, 8)):
                    l.append(HeZhong((7, 1, 1)))    #一气通贯
                    break
            if len(ke) >= 2:
                for i, j, k in itertools.combinations(itertools.chain(ke, dui), 3):
                    if i[0][0] == j[0][0] == k[0][0] and {i[1], j[1], k[1]} == {0, 1, 2}:
                        if len(k[0]) == 2:
                            l.append(HeZhong((6, 2, 1)))    #三色小同刻
                        else:
                            l.append(HeZhong((6, 2, 2)))    #三色同刻
                        break
            if len(ke) == 4 and ke[0][1] == ke[1][1] == ke[2][1] == ke[3][1] and ke[0][0][0] + 3 == ke[1][0][0] + 2 == ke[2][0][0] + 1 == ke[3][0][0]:
                l.append(HeZhong((7, 2, 2)))    #四连刻
            else:
                for i, j, k in itertools.combinations(ke, 3):
                    if i[1] == j[1] == k[1] and i[0][0] + 2 == j[0][0] + 1 == k[0][0]:
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
        _max = (None, MajZjHai.HeZhong.Status.nomangan, 0)
        els += (hai,)
        for result in results:
            _now = _f(result, fuuros, els)
            m, ten = MajZjHai.HeZhong.ten(_now)
            if ten > _max[-1]:
                _max = (_now, m, ten)
        return _max

P = TypeVar('P', bound='Player')
class Player:
    def __init_subclass__(cls, Hai: Type[H], **kwargs):
        super().__init_subclass__(**kwargs)
        cls.Hai = Hai
    doable_dahai = ('kiri', 'ankan', 'kakan', 'tsumo')
    doable_naku_shang = ('qi', 'pon', 'daiminkan', 'ron')
    doable_naku_all = ('pon', 'daiminkan', 'ron')
    doable_kakan = ('ron',)
    doable_ankan = ()
    def __init__(self, board):
        self.tehai = [] # type: List[H]
        self.fuuro = [] # type: List[FuuRo]
        self.ho = [] # type: List[Tuple[H, HaiHoStatus]]
        self.ting = {}
        self.board = board
    def give(self, tehai: Union[Sequence[H], H]):
        if isinstance(tehai, MajHai):
            self.tehai.append(tehai)
        else:
            self.tehai.extend(tehai)
    def sort(self):
        self.tehai.sort()
    def ten_gen(self, special=False):
        if special:
            self.ten = self.Hai.ten(self.tehai[:-1])
        else:
            self.ten = self.Hai.ten(self.tehai)
    def tsumo_check(self) -> List[None]:
        if self.tehai[-1].hai in self.ten:
            return [None]
        else:
            return []
    def tsumo_do(self, n: None) -> Generator[PlayerStatus, PlayerOption, None]:
        raise Win(self, None)
        yield PlayerStatus.NOTHING
    def kiri_check(self) -> List[H]:
        l = []
        for hai in tehai:
            if all(lambda x: not hai.isSame(x), l):
                l.append(hai)
        return l
    def kiri_do(self, hai: H) -> Generator[PlayerStatus, PlayerOption, None]:
        status = HaiHoStatus.TSUMOKIRI if hai is self.tehai[-1] else HaiHoStatus.TEDASHI
        self.tehai.remove(hai)
        self.sort()
        self.ten_gen()
        self.ho.append((hai, status))
        ret = yield PlayerStatus.NOTHING
        if not ret:
            self.ho[-1][1] |= HaiHoStatus.NAKARERU
        else:
            self.board.now = self.board.next(self.board.now)
            self.board.playerstatus = self.board.status
            self.board.players[self.board.now].give(self.board.tsumo())
    def ankan_check(self) -> List[Tuple[H, H, H, H]]:
        def _():
            for i, j, k, l in itertools.combinations(self.tehai, 4):
                if i == j == k == l:
                    yield i, j, k, l
        return list(_())
    def ankan_do(self, tpl: Tuple[H, H, H, H]) -> Generator[PlayerStatus, PlayerOption, None]:
        for i in tpl:
            self.tehai.remove(i)
        self.fuuro.append(FuuRo(FuuRoStatus.ANKAN, tpl))
        yield PlayerStatus.QIANANKAN
        self.board.playerstatus |= PlayerStatus.rinshan
        self.give(self.board.rinshan())
    def kakan_check(self) -> List[Tuple[H, FuuRo]]:
        def _():
            for fuuro in self.fuuro:
                if not fuuro.status & FuuRoStatus.PON:
                    continue
                for hai in self.tehai:
                    if hai == fuuro.hai[0]:
                        yield hai, fuuro
        return list(_())
    def kakan_do(self, tpl: Tuple[H, FuuRo]) -> Generator[PlayerStatus, PlayerOption, None]:
        hai, fuuro = tpl
        self.tehai.remove(hai)
        if (yield PlayerStatus.QIANKAN):
            fuuro.status ^= (FuuRoStatus.PON | FuuRoStatus.KAKAN)
            fuuro.hai += (hai,)
            fuuro.sorted = tuple(sorted(map(lambda x: x.num, fuuro.hai)))
        self.board.playerstatus |= PlayerStatus.rinshan
        self.give(self.board.rinshan())
    def qi_check(self, hai) -> List[Tuple[H, H]]:
        l = []
        for i, j in functools.combinations(self.tehai, 2):
            if i.isaddOne(j) and j.isaddOne(hai) or i.isaddOne(hai) and hai.isaddOne(j) or hai.isaddOne(i) and i.isaddOne(j):
                if not any(map(lambda x: x[0].isSame(i) and x[1].isSame(j), l)):
                    l.append((i, j))
        return l
    def qi_do(self, tpl: Tuple[FuuRoStatus, H, Tuple[H, H]]) -> None:
        for hai in tpl[2]:
            self.tehai.remove(hai)
        self.fuuros.append(FuuRo(tpl[0] | FuuRoStatus.QI), (tpl[1],) + tpl[2])
    def pon_check(self, hai) -> List[Tuple[H, H]]:
        l = []
        for i, j in functools.combinations(self.tehai, 2):
            if i == j == hai:
                if not any(map(lambda x: x[0].isSame(i) and x[1].isSame(j), l)):
                    l.append((i, j))
        return l
    def pon_do(self, tpl: Tuple[FuuRoStatus, H, Tuple[H, H]]) -> None:
        for hai in tpl[2]:
            self.tehai.remove(hai)
        self.fuuros.append(FuuRo(tpl[0] | FuuRoStatus.PON), (tpl[1],) + tpl[2])
    def daiminkan_check(self, hai) -> List[Tuple[H, H, H]]:
        for i, j, k in functools.combinations(self.tehai, 3):
            if i == j == k == hai:
                return [(i, j, k)]
    def daiminkan_do(self, tpl: Tuple[FuuRoStatus, H, Tuple[H, H, H]]) -> None:
        for hai in tpl[2]:
            self.tehai.remove(hai)
        self.fuuros.append(FuuRo(tpl[0] | FuuRoStatus.DAIMINKAN), (tpl[1],) + tpl[2])
        self.give(self.board.rinshan())
    def ron_check(self, hai) -> List[None]:
        if hai in self.ten:
            return [None]
        else:
            return []
    def ron_do(self, tpl: Tuple[FuuRoStatus, H, None]) -> None:
        raise Win(self, tpl[1])
    def do_dahai(self, status: PlayerStatus) -> Generator[Tuple[P, PlayerOption, Dict[str, Any]], Tuple[PlayerOption, H, Any], Tuple[H, Generator]]:
        option = PlayerOption.NOTHING
        d = {}
        tpl = self.doable_dahai
        for s in tpl:
            l = self.__getattribute__(s + '_check')()
            if len(l) != 0:
                option |= PlayerOption.__getattr__(s)
                d[s] = l
        option_chosen, hai, t = yield (self, option, d)
        gen = self.__getattribute__(option_chosen.name + '_do')(t)
        return hai, gen
    def do_naku(self, status: PlayerStatus, pos: FuuRoStatus, hai: H) -> Generator[Tuple[PlayerOption, Dict[str, Any]], Tuple[PlayerOption, Any], None]:
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
                option |= PlayerOption.__getattr__(s)
                d[s] = l
        option_chosen, t = yield (option, d)
        self.__getattribute__(option_chosen.name + '_do')((pos, hai, t))
        return

class ZjPlayer(Player, Hai=MajZjHai):
    pass

B = TypeVar('B', bound='MajBoard')
O = TypeVar('O', bound='MajBoard.NakuOption')
class MajBoard:
    def __init_subclass__(cls, Hai: Type[H], Player: Type[P], **kwargs):
        super().__init_subclass__(**kwargs)
        cls.Hai = Hai
        cls.Player = Player
    def __init__(self, typ):
        self.yama = None
        self.players = [self.Player(self), self.Player(self), self.Player(self), self.Player(self)]
        self.toncha = 0
        self.chiicha = 0
        self.isBegin = False
    def haipai(self):
        #配牌
        self.yama = list(map(self.Hai, range(136)))
        random.shuffle(self.yama)
        for i, p in itertools.product(range(3), self.players):
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
        def __init__(self, pos: FuuRoStatus, options: PlayerOption, args: Dict[str, Any]):
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
    def nakujun(self, d_send: Dict[int, O]) -> Generator[Union[bool, Dict[int, O]], Union[None, Tuple[int, O]], Union[None, Tuple[int, O]]]:
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
    @staticmethod
    def next(i):
        if i != 3:
            return i + 1
        else:
            return 0
    def kyoku(self):
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
            l = dict(_()) # type: Dict[int, Tuple[FuuRoStatus, Generator]]
            d_send = {} # type: Dict[int, NakuOption]
            for i, n in l.items():
                na = self.NakuOption(x[1][0], *(next(x[1][1])))
                if na.isPass():
                    l[i].close()
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
                except StopIteration as e:
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
                except StopIteration as e:
                    pass
                #鸣牌破第一巡
                self.status &= ~PlayerStatus.TIAN
                ret.send(False)
                #玩家顺序
                self.now = i_naku
            #第一张牌结束
            self.status &= ~PlayerStatus.FIRST

class MajZjBoard(MajBoard, Hai=MajZjHai, Player=ZjPlayer):
    pass
