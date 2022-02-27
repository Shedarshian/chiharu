from enum import IntFlag
from typing import *
from datetime import datetime, timedelta
from .EventListener import IEventListener
from .Helper import Saveable, BuildIdMeta
from ...config import mysingledispatchmethod
if TYPE_CHECKING:
    from .User import User

class Status(IEventListener, Saveable, metaclass=BuildIdMeta):
    name = "NoName"
    description = "NoDes"
    isNull = False
    isGlobal = False
    isDaily = False
    isDebuff = False
    isMetallic = False
    isRemovable = True
    @property
    def count(self):
        return 1
    @property
    def valid(self):
        return True
    @property
    def briefDescription(self):
        return self.name
    @property
    def fullDescription(self):
        return f"{self.name}：{self.description}"
    def __init__(self, data: Optional[str]=None) -> None:
        super().__init__()
    def double(self):
        pass

class StatusAllNumed(Status):
    @property
    def valid(self):
        return self.num > 0
    def packData(self):
        return str(self.num)
    @mysingledispatchmethod
    def __init__(self, data: Optional[str]=None) -> None:
        if data is None:
            self.num = 1
        else:
            self.num = int(data)
    @__init__.register
    def _(self, data: int) -> None:
        self.num = data
    @property
    def briefDescription(self):
        return f"{self.num}* {super().briefDescription}"
    @property
    def fullDescription(self):
        return f"{self.num}* {super().fullDescription}"
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
    def briefDescription(self):
        return f"{Status.briefDescription.fget(self)}\n剩余{self.num}次。"
    @property
    def fullDescription(self):
        return f"{Status.fullDescription.fget(self)}\n剩余{self.num}次。"

class StatusTimed(Status):
    @mysingledispatchmethod
    def __init__(self, data: Optional[str]=None):
        self.time = datetime.fromisoformat(data)
    @__init__.register
    def _(self, data: datetime):
        self.time = data
    @__init__.register
    def _(self, data: timedelta):
        self.time = datetime.now() + data
    
    @property
    def valid(self):
        return self.time >= datetime.now()
    def getStr(self):
        delta = self.time - datetime.now()
        min = delta.seconds // 60
        return f"{f'{delta.days}日' if delta.days != 0 else ''}{f'{min // 60}时' if min // 60 != 0 else ''}{min % 60}分"
    @property
    def briefDescription(self):
        return f"{super().briefDescription}\n\t结束时间：{self.getStr()}。"
    @property
    def fullDescription(self):
        delta = self.time - datetime.now()
        min = delta.seconds // 60
        return f"{super().fullDescription}\n\t结束时间：{self.getStr()}。"
    def double(self):
        self.time += self.time - datetime.now()
