import itertools
from collections import Counter
from typing import Callable, TypeAlias, Iterable, Annotated, get_type_hints

type PaixingChecker = 'Callable[[Paili.MianziTuple, Paili.MianziTuple, ChangStatus, PaiStatus], bool]'
type PaixingRanker = 'Callable[[Paili.MianziTuple, Paili.MianziTuple, ChangStatus, PaiStatus], int]'
type PaiChecker = 'Callable[[Iterable[Pai]], bool]' # please remove bei and hua
type PaiRanker = 'Callable[[Iterable[Pai]], int]'
class AllCheckers:
    PingheZj:               PaixingChecker = \
        lambda s, f, c, p: all(m.type.isShunziOrQuetouOrExtra() for m in (s + f))
    MenqianqingZj:          PaixingChecker = \
        lambda s, f, c, p: f.menqianqing()
    Duanyaojiu:             PaiChecker = \
        lambda p: all(x.color != Color.z and 2 <= x.num <= 8 for x in p)
    HunQingZiyise:          PaiRanker = \
        lambda p: 1 if len(st := set(x.color for x in p)) == 2 and Color.z in st else \
                2 if len(st) == 1 and Color.z not in st else \
                3 if len(st) == 1 and Color.z in st else 0
    Jiulianbaodeng:         PaixingRanker = \
        lambda s, f, c, p: 0 if not ((ap := s.toPai()) and f.onlyExtra() and \
                            len(set(x.color for x in ap)) == 1) else \
                            2 if sorted(x.num for x in s.allShoupai()) == [1, 1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 9, 9] else \
                            1 if Counter(x.num for x in ap) >= Counter([1, 1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 9, 9]) else 0
    Changfeng:              PaixingRanker = \
        lambda s, f, c, p: pai.num if (pai := c.ChangToPai()) in (s + f).keziList() else 0
    Zifeng:                 PaixingRanker = \
        lambda s, f, c, p: pai.num if (pai := c.ZijiaToPai()) in (s + f).keziList() else 0
    XiaoDaSanyuan:          PaixingRanker = \
        lambda s, f, c, p: sum(d := set(1 << (i - 5) for i in (5, 6, 7) if Pai(Color.z, i) in (s + f).keziList())) + \
                            (16 if len(d) == 3 else 8 if len(d) == 2 and (q := s.quetou()).color == Color.z and q.num not in d else 0)
    SanSiFeng:              PaixingRanker = \
        lambda s, f, c, p: 4 if len(d := set(i for i in (1, 2, 3, 4) if Pai(Color.z, i) in (s + f).keziList())) == 4 else \
                            3 if len(d) == 3 and (q := s.quetou()).color == Color.z and q.num not in d else \
                            2 if len(d) == 3 else \
                            1 if len(d) == 2 and (q := s.quetou()).color == Color.z and q.num not in d else 0
    Duiduihe:               PaixingChecker = \
        lambda s, f, c, p: all(m.type.isKeziOrQuetouOrExtra() for m in (s + f))
    Anke:                   PaixingRanker = \
        lambda s, f, c, p: sum(1 for y in s if y.type == MianziType.anke) + \
                            sum(1 for x in f if x.type == MianziType.angang)
    Gangzi:                 PaixingRanker = \
        lambda s, f, c, p: sum(1 for x in f if x.type in (MianziType.minggang, MianziType.jiagang, MianziType.angang))
    TongshunLiangbangao:    PaixingRanker = \
        lambda s, f, c, p: 4 if (cr := Counter(Counter((s + f).shunziMinList()).values()))[2] == 2 else \
                            3 if 4 in cr else 2 if 3 in cr else 1 if 2 in cr else 0
    Sansetongshun:          PaixingChecker = \
        lambda s, f, c, p: 3 in Counter(pai.num for pai in set((s + f).shunziMinList())).values()
    Sansetongke:            PaixingRanker = \
        lambda s, f, c, p: 2 if len(st := set((s + f).keziList())) + len(cr := Counter(pai.num for pai in st if pai.color != Color.z)) > 0 and \
                            3 in cr.values() else \
                            1 if any(val == 2 and pai not in st for pai, val in cr.items()) else 0
    Yiqitongguan:           PaixingChecker = \
        lambda s, f, c, p: (s + f).shunziMinList()

from .maj import Paili, Fulu, ChangStatus, PaiStatus
from .maj import Color, Pai, MianziType

type A = "Callable[[int], int]"
type B = "Callable[[str], str]"
class test:
    fa: A = lambda x: x + 1
    fb: B = lambda y: y + "1"

get_type_hints(test)["fa"].__name__
