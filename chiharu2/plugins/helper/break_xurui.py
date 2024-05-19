from typing import List, Tuple, Optional, Union
from functools import total_ordering
from copy import deepcopy
from numbers import Integral
import math
import operator
import itertools

class ENumber:
    Tolerance = 1e-18
    MaxSignificantDigits = 17
    ExpLimit = 2 ** 128 - 1
    def __init__(self, mantissa: float, exponent: int, normalize=True) -> None:
        self.mantissa = mantissa
        self.exponent = exponent
        if normalize:
            self.normalize()
    def normalize(self):
        if 1 <= self.mantissa < 10 or not math.isfinite(self.mantissa):
            return
        tempExp = math.floor(math.log10(abs(self.mantissa)))
        pass