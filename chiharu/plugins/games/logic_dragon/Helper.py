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
        l = []
        for c in s.split('/'):
            id, els = c.split(':', 2)
            l.append(cls.idDict[id](els or None))
        return l
    @classmethod
    def get(cls, id: int):
        if id in cls.idDict:
            return cls.idDict[id]
        raise ValueError("哈")