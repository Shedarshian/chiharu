from typing import *
from .EventListener import IEventListener
from .Helper import Saveable, BuildIdMeta
from .Types import Pack
if TYPE_CHECKING:
    from .User import User

class Card(IEventListener, Saveable):
    name = "NoName"
    description = "NoDes"
    newer = 0
    positive = 0
    weight: Union[float, Callable[['User'], float]] = 1
    mass = 0.1
    consumedOnDraw = False
    pack = Pack.misc
    @property
    def briefDescription(self):
        return f"{self.id}. {self.name}"
    @property
    def fullDescription(self):
        return f"{self.id}. {self.name}\n\t{self.description}"
    def __init__(self, data: Optional[str]=None) -> None:
        pass
    def CanUse(self, user: 'User', copy: bool) -> bool:
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

