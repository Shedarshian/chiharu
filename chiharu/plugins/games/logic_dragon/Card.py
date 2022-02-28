from typing import *
from .EventListener import IEventListener
from .Helper import Saveable, BuildIdMeta
if TYPE_CHECKING:
    from .User import User

class Card(IEventListener, Saveable, metaclass=BuildIdMeta):
    name = "NoName"
    description = "NoDes"
    newer = 0
    positive = 0
    weight = 1
    mass = 0.1
    consumedOnDraw = False
    @property
    def briefDescription(self):
        return f"{self.id}. {self.name}"
    @property
    def fullDescription(self):
        return f"{self.id}. {self.name}\n\t{self.description}"
    def __init__(self, data: Optional[str]=None) -> None:
        pass
    def canUse(self, user: 'User', copy: bool) -> tuple[bool, str]:
        return True, ""
    async def use(self, user: 'User') -> None:
        pass
    async def onRemove(self, user: 'User') -> None:
        pass
    async def onDraw(self, user: 'User') -> None:
        pass
    async def onDiscard(self, user: 'User') -> None:
        await self.onRemove(user)
    async def onGive(self, user: 'User', other: 'User') -> None:
        pass
