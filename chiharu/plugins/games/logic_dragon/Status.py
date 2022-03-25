from enum import IntFlag
from functools import singledispatchmethod
from typing import *
from datetime import datetime, timedelta
from .EventListener import IEventListener
from .Helper import Saveable, BuildIdMeta
from .Types import ProtocolData
if TYPE_CHECKING:
    from .User import User

TStatus = TypeVar("TStatus", bound='Status')
TStatusStack = TypeVar("TStatusStack", bound='StatusNullStack | StatusDailyStack')

class Status(IEventListener, Saveable):
    name = "NoName"
    _description = "NoDes"
    isNull = False
    isGlobal = False
    isDaily = False
    isDebuff = False
    isMetallic = False
    isRemovable = True
    @property
    def count(self) -> int:
        return 1
    @property
    def valid(self) -> bool:
        return True
    @property
    def description(self) -> str:
        return self._description
    def double(self):
        pass
    def DumpData(self) -> ProtocolData:
        return {"id": self.id, "name": self.name, "description": self.description, "null": self.isNull, "count": self.count}

class StatusAllNumed(Status):
    dataType = (int,)
    def __init__(self, data: int=1) -> None:
        self.num = data
    @property
    def valid(self):
        return self.num > 0
    def packData(self):
        return str(self.num)
    def double(self):
        self.num *= 2

class StatusNullStack(StatusAllNumed):
    isNull = True
    @property
    def count(self):
        return self.num

class StatusDailyStack(StatusAllNumed):
    isNull = True
    isDaily = True
    @property
    def count(self):
        return self.num

class StatusNumed(StatusAllNumed):
    @property
    def description(self):
        return f"{self._description}\n剩余{self.num}次。"

class StatusTimed(Status):
    dataType: Tuple[Callable, ...] = (datetime.fromisoformat,)
    @singledispatchmethod # type: ignore[misc]
    def __init__(self, data: datetime):
        self.time = data
    @__init__.register
    def _(self, data: timedelta):
        self.time = datetime.now() + data
    @property
    def valid(self):
        return self.time >= datetime.now()
    def packData(self) -> str:
        return self.time.isoformat()
    def getStr(self):
        delta = self.time - datetime.now()
        min = delta.seconds // 60
        return f"{f'{delta.days}日' if delta.days != 0 else ''}{f'{min // 60}时' if min // 60 != 0 else ''}{min % 60}分"
    @property
    def description(self):
        return f"{self._description}\n\t结束时间：{self.getStr()}。"
    def double(self):
        self.time += self.time - datetime.now()
