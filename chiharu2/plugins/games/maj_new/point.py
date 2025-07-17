import itertools
from typing import Callable, TypeAlias

PaixingChecker: TypeAlias = 'Callable[[SplitResultWithBarrel, list[Fulu], ChangStatus, PaiStatus], bool]'
PaixingRanker: TypeAlias = 'Callable[[SplitResultWithBarrel, list[Fulu], ChangStatus, PaiStatus], int]'
PingheZj:           PaixingChecker = \
    lambda s, f, c, p: all(y.type.isShunziOrQuetou() for x in s.values() for y in x) and all(x.type.isShunziOrExtra() for x in f)
MenqianqingZj:      PaixingChecker = \
    lambda s, f, c, p: all(x.type.menqianqing() for x in f)
Duanyaojiu:         PaixingChecker = \
    lambda s, f, c, p: all(x.color != Color.z and 2 <= x.num <= 8 for x in s.allPaiWithFulu(f))


from .maj import Paili, SplitResultWithBarrel, Fulu, ChangStatus, PaiStatus
from .maj import Color