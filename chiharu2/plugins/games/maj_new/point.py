import itertools
from typing import Callable, TypeAlias

PaixingChecker: TypeAlias = 'Callable[[SplitResultWithBarrel], bool]'


from .maj import Paili, SplitResultWithBarrel