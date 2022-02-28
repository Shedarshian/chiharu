from abc import ABC, ABCMeta
from typing import *

class BuildIdMeta(ABCMeta):
    def __new__(cls, clsname: str, bases, attrs):
        if len(bases) != 0 and not clsname.startswith('_') and 'id' in attrs and 'idDict' not in attrs:
            c = super().__new__(cls, clsname, bases, attrs)
            if attrs['id'] in bases[0].idDict:
                raise ValueError
            bases[0].idDict[attrs['id']] = c
        else:
            c = super().__new__(cls, clsname, bases, attrs)
        return c

TSaveable = TypeVar("TSaveable", bound="Saveable")
TSaveableType = Type[TSaveable]
class Saveable(ABC):
    id = -1
    idDict: dict[int, TSaveableType] = {}
    def save(self):
        return f"{self.id}:{self.packData() or ''}"
    def packData(self) -> str:
        """Implement yourself."""
        return ""
    @classmethod
    def packAllData(cls, l: Iterable[TSaveable]):
        return '/'.join(s.save() for s in l)
    @classmethod
    def unpackAllData(cls, s: str):
        l: list[cls] = []
        for c in s.split('/'):
            id, els = c.split(':', 2)
            l.append(cls.idDict[id](els or None))
        return l
    @classmethod
    def get(cls, id: int):
        if id in cls.idDict:
            return cls.idDict[id]
        raise ValueError("哈")

class Session(ABC):
    pass

class indexer:
    def __init__(self, fget=None, fset=None):
        self.fget = fget
        self.fset = fset
        self._indexer = _indexer(self)
        self._name = ''
    def __set_name__(self, owner, name):
        self._name = name
    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        self._indexer.obj = obj
        return self._indexer
    def setter(self, fset):
        prop = type(self)(self.fget, fset)
        prop._name = self._name
        return prop
class _indexer:
    def __init__(self, parent: indexer):
        self.parent: indexer = parent
        self.obj = None
    def __getitem__(self, index):
        return self.parent.fget(self.obj, index)
    def __setitem__(self, index, item):
        self.parent.fset(self.obj, index, item)