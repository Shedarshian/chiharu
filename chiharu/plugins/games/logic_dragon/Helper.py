from abc import ABC, ABCMeta, abstractmethod
from typing import *
import json
from .Types import ProtocolData
if TYPE_CHECKING:
    from .Card import Card

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

THasId = TypeVar("THasId", bound="HasId")
THasIdType = Type[THasId]
class HasId(metaclass=BuildIdMeta):
    id = -1
    if TYPE_CHECKING:
        _idDict: dict[int, THasIdType] = {}
        @classmethod
        @property
        def idDict(cls: Type[THasId]) -> dict[int, Type[THasId]]:
            return cls._idDict
    else:
        idDict = {}
    @classmethod
    def get(cls: Type[THasId], id: int) -> Type[THasId]:
        if id in cls.idDict: # pylint: disable=unsupported-membership-test
            return cls.idDict[id] # pylint: disable=unsubscriptable-object
        raise ValueError("哈")

class Saveable(HasId):
    def save(self):
        return f"{self.id}:{self.packData() or ''}"
    def packData(self) -> str:
        """Implement yourself."""
        return ""
    @classmethod
    def packAllData(cls, l: Iterable['Saveable']):
        return '/'.join(s.save() for s in l)
    @classmethod
    def unpackAllData(cls, s: str):
        l: list[cls] = []
        for c in s.split('/'):
            id, els = c.split(':', 2)
            l.append(cls.idDict[id](els or None)) # pylint: disable=unsubscriptable-object
        return l

class Buffer(ABC):
    def __init__(self, qq: int) -> None:
        self.datas: list[ProtocolData] = []
        self.dataBuffer: list[ProtocolData] = []
        self.qq = qq
    def Serialize(self):
        s = json.dumps(self.datas + self.dataBuffer)
        return s
    def ClearBuffer(self):
        self.datas.extend(self.dataBuffer)
        self.dataBuffer = []
    def CollectBuffer(self):
        ret = self.dataBuffer
        self.dataBuffer = []
        return ret
    def AddData(self, data: ProtocolData):
        self.dataBuffer.append(data)
    dataListener: list[Callable[[list[ProtocolData]], Awaitable[None]]] = []
    @abstractmethod
    async def selfFlush(self):
        """DO NOT CLEAR SELF.DATAS!!!"""
        pass
    async def Flush(self):
        await self.selfFlush()
        for listener in self.dataListener:
            await listener(self.datas + self.dataBuffer)
        self.datas.clear()
        self.dataBuffer.clear()
    @classmethod
    def addDataListener(cls, listener: Callable[[list[ProtocolData]], Awaitable[None]]):
        cls.dataListener.append(listener)
    @abstractmethod
    async def GetResponse(self, request: ProtocolData) -> ProtocolData:
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

def positive(s: set[int]) -> Callable[[Type['Card']], bool]:
        return lambda c: c.id in s