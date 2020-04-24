from typing import List, Tuple, Optional, Union
from functools import total_ordering
from copy import deepcopy
from numbers import Integral
import operator
import itertools
def reverse_bisect_right(a, x, lo=0, hi=None):
    if lo < 0:
        raise ValueError('lo must be non-negative')
    if hi is None:
        hi = len(a)
    while lo < hi:
        mid = (lo+hi)//2
        if x > a[mid]: hi = mid
        else: lo = mid+1
    return lo

class NegativeOrdinalError(ArithmeticError):
    pass
class UndivideableOrdinalError(ArithmeticError):
    pass

class Ord:
    @classmethod
    def _create_instance(cls, _val):
        ins = cls()
        ins._val = _val
        ins.check_zero()
        return ins
    def __init__(self, *args):
        if len(args) == 0:
            self._val : 'List[Tuple[Union[Ord, int], int]]' = [] # provided 'Ord' is sorted and 'int' != 0
        elif len(args) == 1 and type(args[0]) is int:
            if args[0] == 0:
                self._val = []
            elif args[0] < 0:
                raise NegativeOrdinalError
            else:
                self._val = [(0, args[0])]
        else:
            raise TypeError(args)
            self.to_std()
    def __eq__(self, other):
        if isinstance(other, Ord):
            return self._val == other._val
        elif isinstance(other, int):
            return self.order == 0 and self.first_val == other
        else:
            return NotImplemented
    def __ne__(self, other):
        if isinstance(other, Ord):
            return self._val != other._val
        elif isinstance(other, int):
            return self.order == 0 and self.first_val != other
        else:
            return NotImplemented
    def __lt__(self, other):
        if isinstance(other, Ord):
            return self._val < other._val
        elif isinstance(other, int):
            return self.order == 0 and self.first_val < other
        else:
            return NotImplemented
    def __le__(self, other):
        if isinstance(other, Ord):
            return self._val <= other._val
        elif isinstance(other, int):
            return self.order == 0 and self.first_val <= other
        else:
            return NotImplemented
    def __gt__(self, other):
        if isinstance(other, Ord):
            return self._val > other._val
        elif isinstance(other, int):
            return self.order == 0 and self.first_val > other
        else:
            return NotImplemented
    def __ge__(self, other):
        if isinstance(other, Ord):
            return self._val >= other._val
        elif isinstance(other, int):
            return self.order == 0 and self.first_val >= other
        else:
            return NotImplemented
    def __bool__(self):
        return len(self._val)
    def __add__(self, other):
        if isinstance(other, Ord):
            if self.order < other.order:
                return deepcopy(other)
            pos = reverse_bisect_right(self._val, (other.order,))
            if self._val[pos][0] == other.order:
                return Ord._create_instance(deepcopy(self._val[:pos] + [(other.order, self._val[pos][1] + other.first_val)] + other._val[1:]))
            return Ord._create_instance(deepcopy(self._val[:pos] + other._val))
        elif isinstance(other, Integral):
            if int(other) < 0:
                raise NegativeOrdinalError
            elif len(self._val) == 0 or self._val[-1][0] != 0:
                return Ord._create_instance(deepcopy(self._val) + [(0, int(other))])
            else:
                return Ord._create_instance(deepcopy(self._val[:-1]) + [(0, self._val[-1][1] + int(other))])
        else:
            return NotImplemented
    def __radd__(self, other):
        if isinstance(other, Integral):
            if self.order == 0:
                return self.first_val + int(other)
            else:
                return deepcopy(self)
        else:
            return NotImplemented
    def __iadd__(self, other):
        if isinstance(other, Ord):
            if self.order < other.order:
                self._val = deepcopy(other._val)
            else:
                pos = reverse_bisect_right(self._val, (other.order,))
                if self._val[pos][0] == other.order:
                    self._val = self._val[:pos] + [(other.order, self._val[pos][1] + other.first_val)] + deepcopy(other._val[1:])
                else:
                    self._val = self._val[:pos] + deepcopy(other._val)
            return self
        elif isinstance(other, Integral):
            if int(other) < 0:
                raise NegativeOrdinalError
            elif len(self._val) == 0 or self._val[-1][0] != 0:
                self._val.append((0, int(other)))
            else:
                self._val[-1] = (0, self._val[-1][1] + int(other))
            return self
        else:
            return NotImplemented
    def __sub__(self, other):
        if isinstance(other, Ord):
            if self.order == 0 and other.order == 0:
                return self.first_val - other.first_val
            for i, (s, o) in enumerate(zip(self._val, other._val)):
                if s < o:
                    raise NegativeOrdinalError
                elif s > o:
                    break
            else:
                return 0
            v = self._val[i][1] - other._val[i][1]
            if v < 0:
                raise NegativeOrdinalError
            return Ord._create_instance(deepcopy([(self._val[i][0], v)] + self._val[i + 1:]))
        elif isinstance(other, Integral):
            if int(other) < 0:
                return int(other) + self
            elif self.order == 0:
                return self.first_val - int(other)
            else:
                return deepcopy(self)
        else:
            return NotImplemented
    def __rsub__(self, other):
        if isinstance(other, Integral) or isinstance(other, Ord):
            if self.order == 0:
                return other - self.first_val
            else:
                raise NegativeOrdinalError
        else:
            return NotImplemented
    def __isub__(self, other):
        if isinstance(other, Ord):
            if self.order == 0 and other.order == 0:
                v = self.first_val - other.first_val
                if v < 0:
                    raise NegativeOrdinalError
                elif v == 0:
                    self._val = []
                else:
                    self._val = [(0, v)]
                return self
            for i, (s, o) in enumerate(zip(self._val, other._val)):
                if s < o:
                    raise NegativeOrdinalError
                elif s > o:
                    break
            else:
                self._val = []
                return self
            self._val = [(self._val[i][0], self._val[i][1] - other._val[i][1])] + self._val[i + 1:]
            return self
        elif isinstance(other, Integral):
            if int(other) < 0:
                t = int(other) + self
                self._val = t._val
            elif self.order == 0:
                self._val = [(0, self.first_val - int(other))]
                self.check_zero()
            return self
        else:
            return NotImplemented
    def __mul__(self, other):
        if isinstance(other, Ord):
            if len(other._val) == 0 or len(self._val) == 0:
                return 0
            m = self.order
            first = deepcopy(other._val)
            sec = first.is_second_type()
            for i, (o, v) in enumerate(first):
                if isinstance(o, Ord):
                    o += m
                else:
                    first[i] = (o + i, v)
            if sec:
                return Ord._create_instance(first)
            b0 = first[-1][1]
            first[-1] = (first[-1][0], b0 * self.first_val)
            return Ord._create_instance(first + deepcopy(self.val[1:]))
        elif isinstance(other, Integral):
            if int(other) < 0:
                if self.order == 0:
                    return self.first_val * int(other)
                raise NegativeOrdinalError
            elif other == 0 or len(self._val) == 0:
                return 0
            return Ord._create_instance([(self.order, int(other) * self.first_val)] + deepcopy(self.val[1:]))
        return NotImplemented
    def __rmul__(self, other):
        if isinstance(other, Integral):
            if len(self._val) == 0 or int(other) == 0:
                return 0
            elif int(other) < 0:
                if self.order == 0:
                    return int(other) * self.first_val
                raise NegativeOrdinalError
            return Ord._create_instance([(self._val[-1][0], self._val[-1][1] * int(other))] + deepcopy(self._val[:-1]))
        return NotImplemented
    def __imul__(self, other):
        if isinstance(other, Ord):
            if len(other._val) == 0 or len(self._val) == 0:
                self._val = []
                return self
            m = self.order
            first = deepcopy(other._val)
            sec = first.is_second_type()
            for i, (o, v) in enumerate(first):
                if isinstance(o, Ord):
                    o += m
                else:
                    first[i] = (o + i, v)
            if sec:
                self._val = first
            else:
                b0 = first[-1][1]
                first[-1] = (first[-1][0], b0 * self.first_val)
                self._val = first + self.val[1:]
            return self
        elif isinstance(other, Integral):
            if int(other) < 0:
                raise NegativeOrdinalError
            elif other == 0 or len(self._val) == 0:
                self._val = []
            else:
                self.val = [(self.order, int(other) * self.first_val)] + self.val[1:]
            return self
        else:
            return NotImplemented
    def __truediv__(self, other):
        if isinstance(other, Ord) or isinstance(other, Integral):
            d, m = divmod(self, other)
            if m == 0:
                return d
            raise UndivideableOrdinalError
        return NotImplemented
    def __rtruediv__(self, other):
        if isinstance(other, Integral):
            if self.order == 0:
                return int(other) / self.first_val
            elif int(other) == 0:
                raise ZeroDivisionError
            elif int(other) < 0:
                raise NegativeOrdinalError
            raise UndivideableOrdinalError
        return NotImplemented
    def __itruediv__(self, other):
        if isinstance(other, Ord) or isinstance(other, Integral):
            d, m = divmod(self, other)
            if m == 0:
                if isinstance(d, Ord):
                    self._val = d._val
                else:
                    self._val = [(0, int(d))]
                return self
            raise UndivideableOrdinalError
        return NotImplemented
    def __floordiv__(self, other):
        if isinstance(other, Ord):
            o = other.order
            i = reverse_bisect_right(self._val, (o,))
            if self._val[i][0] == o:
                return Ord._create_instance([(r - o, v) for r, v in self._val[:i]] + [(0, self._val[i][1] // other.first_val)])
            return Ord._create_instance([(r - o, v) for r, v in self._val[:i]])
        elif isinstance(other, Integral):
            if int(other) < 0:
                if self.order == 0:
                    return self.first_val // int(other)
                raise NegativeOrdinalError
            if len(self._val) == 0 or self._val[-1][0] == 0:
                if int(other) == 0:
                    raise ZeroDivisionError
                return deepcopy(self)
            return Ord._create_instance(deepcopy(self._val[:-1]) + [(0, self._val[-1][1] // int(other))])
        return NotImplemented
    def __rfloordiv__(self, other):
        if isinstance(other, Integral):
            if self.order == 0:
                return int(other) // self.first_val
            elif int(other) == 0:
                raise ZeroDivisionError
            elif int(other) < 0:
                raise NegativeOrdinalError
            return 0
        return NotImplemented
    def __ifloordiv__(self, other):
        if isinstance(other, Ord):
            o = other.order
            i = reverse_bisect_right(self._val, (o,))
            if self._val[i][0] == o:
                self._val = [(r - o, v) for r, v in self._val[:i]] + [(0, self._val[i][1] // other.first_val)]
            else:
                self._val = [(r - o, v) for r, v in self._val[:i]]
            return self
        elif isinstance(other, Integral):
            if int(other) < 0:
                raise NegativeOrdinalError
            if len(self._val) == 0 or self._val[-1][0] == 0:
                if int(other) == 0:
                    raise ZeroDivisionError
                return self
            self._val[-1] = (0, self._val[-1][1] // int(other))
            return self
        return NotImplemented
    def __mod__(self, other):
        if isinstance(other, Ord):
            o = other.order
            i = reverse_bisect_right(self._val, (o,))
            if self._val[i][0] == o:
                return Ord._create_instance([o, self._val[i][1] % other.first_val] + deepcopy(self._val[i + 1:]))
            return Ord._create_instance(deepcopy(self._val[i + 1:]))
        elif isinstance(other, Integral):
            if int(other) < 0:
                if self.order == 0:
                    return self.first_val % int(other)
                raise NegativeOrdinalError
            if len(self._val) == 0 or self._val[-1][0] == 0:
                if int(other) == 0:
                    raise ZeroDivisionError
                return 0
            return self._val[-1][1] % int(other)
        return NotImplemented
    def __rmod__(self, other):
        if isinstance(other, Integral):
            if self.order == 0:
                return int(other) % self.first_val
            elif int(other) == 0:
                raise ZeroDivisionError
            elif int(other) < 0:
                raise NegativeOrdinalError
            return int(other)
        return NotImplemented
    def __imod__(self, other):
        if isinstance(other, Ord):
            o = other.order
            i = reverse_bisect_right(self._val, (o,))
            if self._val[i][0] == o:
                self._val = [o, self._val[i][1] % other.first_val] + deepcopy(self._val[i + 1:])
            else:
                self._val = self._val[i + 1:]
            return self
        elif isinstance(other, Integral):
            if int(other) < 0:
                raise NegativeOrdinalError
            if len(self._val) == 0 or self._val[-1][0] == 0:
                if int(other) == 0:
                    raise ZeroDivisionError
                self._val = []
            else:
                self._val = [(0, self._val[-1][1] % int(other))]
            return self
        return NotImplemented
    def __divmod__(self, other):
        if isinstance(other, Ord):
            o = other.order
            i = reverse_bisect_right(self._val, (o,))
            if self._val[i][0] == o:
                return (Ord._create_instance([(r - o, v) for r, v in self._val[:i]] + [(0, self._val[i][1] // other.first_val)]),
                    Ord._create_instance([o, self._val[i][1] % other.first_val] + deepcopy(self._val[i + 1:])))
            return (Ord._create_instance([(r - o, v) for r, v in self._val[:i]]), 
                Ord._create_instance(deepcopy(self._val[i + 1:])))
        elif isinstance(other, Integral):
            if int(other) < 0:
                if self.order == 0:
                    return divmod(self.first_val, int(other))
                raise NegativeOrdinalError
            if len(self._val) == 0 or self._val[-1][0] == 0:
                if int(other) == 0:
                    raise ZeroDivisionError
                return (deepcopy(self), 0)
            return (Ord._create_instance(deepcopy(self._val[:-1]) + [(0, self._val[-1][1] // int(other))]),
                self._val[-1][1] % int(other))
        return NotImplemented
    def __rdivmod__(self, other):
        if isinstance(other, Integral):
            if self.order == 0:
                return divmod(int(other), self.first_val)
            elif int(other) == 0:
                raise ZeroDivisionError
            elif int(other) < 0:
                raise NegativeOrdinalError
            return (0, int(other))
        return NotImplemented
    def __pow__(self, other, modulo=None):
        if isinstance(other, Ord):
            if len(other._val) == 0:
                if isinstance(modulo, Ord) or isinstance(modulo, Integral) or modulo is None:
                    if modulo == 0:
                        raise ZeroDivisionError
                    return 1
                return NotImplemented
            elif other._val[-1][0] != 0:
                if isinstance(modulo, Ord) or isinstance(modulo, Integral) or modulo is None:
                    v = Ord._create_instance([(self.order * other, 1)])
                    if modulo is not None:
                        v %= modulo
                    return v
                return NotImplemented
            else:
                if modulo is None:
                    n = self.order
                    an = self.first_val
                    o = n * Ord._create_instance(other._val[:-1])
                    b0 = other._val[-1][1]
                    return Ord._create_instance(list(itertools.chain(
                        [(n * other, an)],
                        *[[(onb + d, (a if d == 0 or b == 0 else a * an)) for d, a in self._val[1:]]
                            for onb in [o + n * b for b in range(b0 - 1, -1, -1)]])))
                elif isinstance(modulo, Ord):
                    om = self.order * Ord._create_instance(other._val[:-1])
                    if modulo.order < om:
                        return 0
                    bn, r = divmod(modulo.order - om, self.order)
                    n = self.order
                    an = self.first_val
                    o = n * Ord._create_instance(other._val[:-1])
                    b0 = other._val[-1][1]
                    if b0 - 1 < bn:
                        return Ord._create_instance(list(itertools.chain(
                            [(n * other, an)],
                            *[[(onb + d, (a if d == 0 or b == 0 else a * an)) for d, a in self._val[1:]]
                                for onb in [o + n * b for b in range(b0 - 1, -1, -1)]])))
                    elif b0 - 1 == bn:
                        l = list(itertools.chain(
                            *[[(onb + d, (a if d == 0 or b == 0 else a * an)) for d, a in self._val[1:]]
                                for onb in [o + n * b for b in range(b0 - 1, -1, -1)]]))
                        if r == 0:
                            return Ord._create_instance([(n * other, an % modulo.first_val)] + l)
                        return Ord._create_instance([(n * other, an)] + l)
                    else: # bn must in N
                        return Ord._create_instance(list(itertools.chain(
                            [(o + n * bn + d, (a if d == 0 else a * an)) for d, a in
                                (self % Ord._create_instance([(r, modulo.first_val)]))._val],
                            *[[(onb + d, (a if d == 0 or b == 0 else a * an)) for d, a in self._val[1:]]
                                for onb in [o + n * b for b in range(bn - 1, -1, -1)]])))
                elif isinstance(modulo, Integral):
                    if self.order != 0 or other.order != 0:
                        return 0
                    return pow(self.first_val, other.first_val, int(modulo))
                return NotImplemented
        elif isinstance(other, Integral):
            if int(other) == 0:
                if isinstance(modulo, Ord) or isinstance(modulo, Integral) or modulo is None:
                    if modulo == 0:
                        raise ZeroDivisionError
                    return 1
                return NotImplemented
            else:
                if modulo is None:
                    n = self.order
                    an = self.first_val
                    b0 = int(other)
                    return Ord._create_instance(list(itertools.chain(
                        [(n * other, an)],
                        *[[(onb + d, (a if d == 0 or b == 0 else a * an)) for d, a in self._val[1:]]
                            for onb in [n * b for b in range(b0 - 1, -1, -1)]])))
                elif isinstance(modulo, Ord):
                    bn, r = divmod(modulo.order, self.order)
                    n = self.order
                    an = self.first_val
                    b0 = int(other)
                    if b0 - 1 < bn:
                        return Ord._create_instance(list(itertools.chain(
                            [(n * other, an)],
                            *[[(onb + d, (a if d == 0 or b == 0 else a * an)) for d, a in self._val[1:]]
                                for onb in [n * b for b in range(b0 - 1, -1, -1)]])))
                    elif b0 - 1 == bn:
                        l = list(itertools.chain(
                            *[[(onb + d, (a if d == 0 or b == 0 else a * an)) for d, a in self._val[1:]]
                                for onb in [n * b for b in range(b0 - 1, -1, -1)]]))
                        if r == 0:
                            return Ord._create_instance([(n * other, an % modulo.first_val)] + l)
                        return Ord._create_instance([(n * other, an)] + l)
                    else: # bn must in N
                        return Ord._create_instance(list(itertools.chain(
                            [(n * bn + d, (a if d == 0 else a * an)) for d, a in
                                (self % Ord._create_instance([(r, modulo.first_val)]))._val],
                            *[[(onb + d, (a if d == 0 or b == 0 else a * an)) for d, a in self._val[1:]]
                                for onb in [n * b for b in range(bn - 1, -1, -1)]])))
                elif isinstance(modulo, Integral):
                    if self.order != 0:
                        return 0
                    return pow(self.first_val, int(other), int(modulo))
                return NotImplemented
        return NotImplemented
    def __rpow__(self, other, modulo=None):
        pass
    def __ipow__(self, other):
        if isinstance(other, Ord):
            if len(other._val) == 0:
                self._val = [(0, 1)]
                return self
            elif other._val[-1][0] != 0:
                self._val = [(self.order * other, 1)]
                return self
            else:
                n = self.order
                an = self.first_val
                o = n * Ord._create_instance(other._val[:-1])
                b0 = other._val[-1][1]
                self._val = list(itertools.chain(
                    [(n * other, an)],
                    *[[(onb + d, (a if d == 0 or b == 0 else a * an)) for d, a in self._val[1:]]
                        for onb in [o + n * b for b in range(b0 - 1, -1, -1)]]))
                return self
        elif isinstance(other, Integral):
            if int(other) == 0:
                return 1
            else:
                n = self.order
                an = self.first_val
                b0 = int(other)
                self._val = list(itertools.chain(
                    [(n * other, an)],
                    *[[(onb + d, (a if d == 0 or b == 0 else a * an)) for d, a in self._val[1:]]
                        for onb in [n * b for b in range(b0 - 1, -1, -1)]]))
                return self
        return NotImplemented
    def __neg__(self):
        if self.order == 0:
            return -self.first_val
        raise NegativeOrdinalError
    def __pos__(self):
        return deepcopy(self)
    def __abs__(self):
        return deepcopy(self)
    def __int__(self):
        if self.order == 0:
            return self.first_val
        raise OverflowError
    def to_std(self) -> None:
        self._val.sort(reversed=False)
        i = 0
        while i < len(self._val):
            if self._val[i][1] == 0:
                del self._val[i]
            elif i != len(self._val) - 1 and self._val[i][0] == self._val[i + 1][0]:
                self._val[i] = (self._val[i][0], self._val[i][1] + self._val[i + 1][1])
                del self._val[i]
            else:
                i += 1
    def check_zero(self):
        self._val = filter(operator.itemgetter(1), self._val)
        return self
    @property
    def order(self) -> 'Ord':
        if len(self._val) == 0:
            return 0
        return self._val[0][0]
    @property
    def first_val(self):
        if len(self._val) == 0:
            return 0
        return self._val[0][1]
    def is_second_type(self):
        if self.order == 0:
            return False
        return self._val[-1][0] == 0