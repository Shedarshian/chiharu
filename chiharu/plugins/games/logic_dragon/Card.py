from typing import *
from .EventListener import IEventListener
from .Helper import Saveable, BuildIdMeta
from .Types import Pack, ProtocolData
if TYPE_CHECKING:
    from .User import User

class Card(IEventListener, Saveable):
    name = "NoName"
    _description = "NoDes"
    newer = 0
    positive = 0
    weight: Union[float, Callable[['User'], float]] = 1
    mass = 0.1
    consumedOnDraw = False
    pack = Pack.misc
    @property
    def description(self):
        return self._description
    def CanUse(self, user: 'User', copy: bool) -> bool:
        return True
    def CanDiscard(self, user: 'User') -> bool:
        return True
    async def Use(self, user: 'User') -> None:
        pass
    async def OnRemove(self, user: 'User') -> None:
        pass
    async def OnDraw(self, user: 'User') -> None:
        pass
    async def OnDiscard(self, user: 'User') -> None:
        await self.OnRemove(user)
    async def OnGive(self, user: 'User', other: 'User') -> None:
        pass
    def DumpData(self) -> ProtocolData:
        return {"id": self.id, "name": self.name, "description": self.description, "eff_draw": self.consumedOnDraw}

