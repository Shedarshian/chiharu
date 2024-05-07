from typing import List, Tuple, Optional, Union
from functools import total_ordering
from copy import deepcopy
from numbers import Integral
import operator
import itertools

class ENumber:
    def __init__(self, num: float, exp: int) -> None:
        self.num = num
        self.exp = exp
    def check(self):
        pass