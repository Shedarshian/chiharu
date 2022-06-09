from typing import *
import re
from .EventListener import IEventListener
from .Helper import Saveable, BuildIdMeta
from .Types import Pack, ProtocolData
if TYPE_CHECKING:
    from .User import User

class Card(IEventListener, Saveable, hasIdDict=True):
    name = "NoName"
    _description = "NoDes"
    newer = 0
    positive = 0
    weight: Union[float, Callable[['User'], float]] = 1
    mass = 0.1
    consumedOnDraw = False
    pack = Pack.misc
    isMetallic = False
    @property
    def description(self):
        return self._description
    def CanUse(self, user: 'User', copy: bool) -> bool:
        return True
    def CanDiscard(self, user: 'User') -> bool:
        return True
    async def Use(self, user: 'User') -> None:
        t = Card.idDict[1]
    async def OnRemove(self, user: 'User') -> None:
        pass
    async def OnDraw(self, user: 'User') -> None:
        pass
    async def OnDiscard(self, user: 'User') -> None:
        await self.OnRemove(user)
    async def OnGive(self, user: 'User', other: 'User') -> None:
        pass
    def DumpData(self) -> ProtocolData:
        return {"id": self.id, "name": self.name, "description": self.description, "eff_draw": self.consumedOnDraw, "data": self.packData()}
    def __init_subclass__(cls) -> None:
        if match := re.search(r"DLC(\d+)", cls.__module__):
            cls.newer = int(match.group(1))
        return super().__init_subclass__()

class CardNumed(Card):
    dataType: Tuple[Callable[[str], Any],...] = (int,)
    def __init__(self) -> None:
        self.num = 0
    def packData(self):
        return str(self.num)
    def DumpData(self) -> ProtocolData:
        return super().DumpData() | {"num": self.num}

class CardDoubleNumed(Card):
    dataType: Tuple[Callable[[str], Any],...] = (int, int)
    def __init__(self) -> None:
        self.num1 = 0
        self.num2 = 0
    def packData(self):
        return f"{self.num1},{self.num2}"
    def DumpData(self) -> ProtocolData:
        return super().DumpData() | {"num1": self.num1, "num2": self.num2}
