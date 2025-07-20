import itertools, more_itertools
from collections import Counter
from typing import Callable, TypeAlias, Iterable, Annotated, get_type_hints

type PaixingChecker =   'Callable[[Paili.MianziTuple, ChangStatus, PaiStatus], bool]'
type PaixingRanker =    'Callable[[Paili.MianziTuple, ChangStatus, PaiStatus], int]'
type PaiChecker =       'Callable[[Iterable[Pai]], bool]' # please remove bei and hua
type PaiRanker =        'Callable[[Iterable[Pai]], int]'
type StatusChecker =    'Callable[[ChangStatus, PaiStatus], bool]'
type StatusRanker =    'Callable[[ChangStatus, PaiStatus], int]'
class AllCheckers:
    PingheZj:               PaixingChecker = \
        lambda s, c, p: all(m.type.isShunziOrQuetouOrExtra() for m in s)
    MenqianqingZj:          StatusChecker = \
        lambda c, p: p & PaiStatus.Menqianqing != 0
    Duanyaojiu:             PaiChecker = \
        lambda p: all(x.color != Color.z and 2 <= x.num <= 8 for x in p)
    HunQingZiyise:          PaiRanker = \
        lambda p: 1 if len(st := set(x.color for x in p)) == 2 and Color.z in st else \
                2 if len(st) == 1 and Color.z not in st else \
                3 if len(st) == 1 and Color.z in st else 0
    Jiulianbaodeng:         PaixingRanker = \
        lambda s, c, p: 0 if not ((ap := s.removeExtra().toPai()) and \
                        all(x.type.isExtra() or not x.type.isFulu() for x in s) and \
                        len(set(x.color for x in ap)) == 1) else \
                        2 if sorted(x.num for x in s.removeExtra().allShoupai()) == [1, 1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 9, 9] else \
                        1 if Counter(x.num for x in ap) >= Counter([1, 1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 9, 9]) else 0
    Changfeng:              PaixingRanker = \
        lambda s, c, p: pai.num if (pai := c.ChangToPai()) in s.keziList() else 0
    Zifeng:                 PaixingRanker = \
        lambda s, c, p: pai.num if (pai := c.ZijiaToPai()) in s.keziList() else 0
    XiaoDaSanyuan:          PaixingRanker = \
        lambda s, c, p: sum(d := set(1 << (i - 5) for i in (5, 6, 7) if Pai(Color.z, i) in s.keziList())) + \
                            (16 if len(d) == 3 else 8 if len(d) == 2 and (q := s.quetou()).color == Color.z and q.num not in d else 0)
    SanSiFeng:              PaixingRanker = \
        lambda s, c, p: 4 if len(d := set(i for i in (1, 2, 3, 4) if Pai(Color.z, i) in s.keziList())) == 4 else \
                        3 if len(d) == 3 and (q := s.quetou()).color == Color.z and q.num not in d else \
                        2 if len(d) == 3 else \
                        1 if len(d) == 2 and (q := s.quetou()).color == Color.z and q.num not in d else 0
    Duiduihe:               PaixingChecker = \
        lambda s, c, p: all(m.type.isKeziOrQuetouOrExtra() for m in s)
    Anke:                   PaixingRanker = \
        lambda s, c, p: sum(1 for y in s if y.type in (MianziType.anke, MianziType.angang))
    Gangzi:                 PaixingRanker = \
        lambda s, c, p: sum(1 for x in s if x.type.isGang())
    TongshunLiangbangao:    PaixingRanker = \
        lambda s, c, p: 4 if (cr := Counter(Counter(s.shunziMinList()).values()))[2] == 2 else \
                        3 if 4 in cr else 2 if 3 in cr else 1 if 2 in cr else 0
    Sansetongshun:          PaixingChecker = \
        lambda s, c, p: 3 in Counter(pai.num for pai in set(s.shunziMinList())).values()
    Sansetongke:            PaixingRanker = \
        lambda s, c, p: 2 if len(st := set(s.keziList())) + len(cr := Counter(pai.num for pai in st if pai.color != Color.z)) > 0 and \
                        3 in cr.values() else \
                        1 if any(val == 2 and pai not in st for pai, val in cr.items()) else 0
    Yisebubugao:            PaixingRanker = \
        lambda s, c, p: 0 if (l := more_itertools.only(list(pai.num for pai in b[cl]) for cl in Color if 
                            len(list((b := more_itertools.bucket(sorted(set(s.shunziMinList())), lambda pai: pai.color))[cl])) >= 3)) is None else \
                        (4 if l[1] - l[0] == 1 else 5) \
                        if len(l) == 4 and l[1] * 2 == l[0] + l[2] and l[1] + l[2] == l[0] + l[3] else \
                        3 if 3 in (lj := list(j for j in range(1, 4)
                              if any(all(x in l for x in (i, i + j, i + 2*j)) for i in range(1, 12 - 3*j)))) else \
                        5 if 1 in lj and 2 in lj else 2 if 2 in lj else 1 if 1 in lj else 0
    Lianke:                 PaixingRanker = \
        lambda s, c, p: 0 if (l := more_itertools.only(list(pai.num for pai in b[cl]) for cl in Color if 
                            len(list((b := more_itertools.bucket(sorted(set(s.keziList())), lambda pai: pai.color))[cl])) >= 3)) is None else \
                        (4 if l[1] - l[0] == 1 else 5) \
                        if len(l) == 4 and l[1] * 2 == l[0] + l[2] and l[1] + l[2] == l[0] + l[3] else \
                        3 if 3 in (lj := list(j for j in range(1, 4)
                              if any(all(x in l for x in (i, i + j, i + 2*j)) for i in range(1, 12 - 3*j)))) else \
                        6 if 1 in lj and 2 in lj else 2 if 2 in lj else 1 if 1 in lj else 0
    Quandai:                PaixingRanker = \
        lambda s, c, p: 2 if all(m for m in s.removeExtra() if 1 in m.pai or 9 in m.pai and not m.color == Color.z) else \
                        1 if all(m for m in s.removeExtra() if 1 in m.pai or 9 in m.pai or m.color == Color.z) and \
                            not all(m for m in s.removeExtra() if m.color == Color.z) else 0
    Laotou:                 PaiRanker = \
        lambda p: 2 if all(pai.num in (1, 9) and pai.color != Color.z for pai in p) else \
                    1 if all(pai.num in (1, 9) or pai.color != Color.z for pai in p) and \
                    not all(pai for pai in p if pai.color == Color.z) else 0
    Ouran:                  StatusRanker = \
        lambda c, p: (2 if p & PaiStatus.Ronghe else 1) if p & PaiStatus.Haidi else \
                    3 if p & PaiStatus.Lingshang else 4 if PaiStatus.Qianggang or PaiStatus.Qiangangang else \
                    (7 if p & PaiStatus.Ronghe else 5) if p & PaiStatus.FirstPai else \
                    (8 if p & PaiStatus.Ronghe else 6) if p & PaiStatus.FirstXun else 0

from .maj import Paili, Fulu, ChangStatus, PaiStatus
from .maj import Color, Pai, MianziType

type A = "Callable[[int], int]"
type B = "Callable[[str], str]"
class test:
    fa: A = lambda x: x + 1
    fb: B = lambda y: y + "1"

get_type_hints(test)["fa"].__name__

((l := [i.index(0) for i in [[]]]) for j in range(10))