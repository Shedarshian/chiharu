import itertools
from typing import Callable, TypeAlias, Iterable, Annotated, get_type_hints

type PaixingChecker = 'Callable[[SplitResultWithBarrel, list[Fulu], ChangStatus, PaiStatus], bool]'
type PaixingRanker = 'Callable[[SplitResultWithBarrel, list[Fulu], ChangStatus, PaiStatus], int]'
type PaiChecker = 'Callable[[Iterable[Pai]], bool]' # please remove bei and hua
type PaiRanker = 'Callable[[Iterable[Pai]], int]'
class AllCheckers:
    PingheZj:               PaixingChecker = \
        lambda s, f, c, p: all(y.type.isShunziOrQuetou() for x in s.values() for y in x) and all(x.type.isShunziOrExtra() for x in f)
    MenqianqingZj:          PaixingChecker = \
        lambda s, f, c, p: all(x.type.menqianqing() for x in f)
    Duanyaojiu:             PaiChecker = \
        lambda p: all(x.color != Color.z and 2 <= x.num <= 8 for x in p)
    HunQingZiyise:          PaiRanker = \
        lambda p: 1 if len(st := set(x.color for x in p)) == 2 and Color.z in st else \
                2 if len(st) == 1 and Color.z not in st else \
                3 if len(st) == 1 and Color.z in st else 0
    Jiulianbaodeng:         PaixingRanker = \
        lambda s, f, c, p: 0 if all(x.type.isExtra() for x in f) and \
                            len(ap := s.allPai()) > 0 and \
                            len(set(x.color for x in ap)) == 1 and \
                            sorted(x.num for x in s.allShoupai()) == [1, 1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 9, 9]

from .maj import Paili, SplitResultWithBarrel, Fulu, ChangStatus, PaiStatus
from .maj import Color, Pai

type A = "Callable[[int], int]"
type B = "Callable[[str], str]"
class test:
    fa: A = lambda x: x + 1
    fb: B = lambda y: y + "1"

get_type_hints(test)["fa"].__name__


