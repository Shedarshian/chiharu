from abc import abstractmethod
from typing import *
from .EventListener import IEventListener
from .Helper import Saveable, BuildIdMeta
from ...config import mysingledispatchmethod
if TYPE_CHECKING:
    from .User import User

class Equipment(IEventListener, Saveable):
    name = "NoName"
    description = ""
    shopDes = "NoDes"
    @property
    def level(self):
        return 1
    @property
    def fullDescription(self):
        return f"{self.id}. {self.name}\n\t{self.description}"
    def canUse(self, user: 'User') -> tuple[bool, str]:
        return True, ""
    async def use(self, user: 'User') -> None:
        pass

class EquipmentStar(Equipment):
    dataType = (int,)
    def __init__(self, data: int):
        self.count = data
    @property
    def level(self):
        return self.count
    @property
    def fullDescription(self):
        return f"{self.id}. {self.count * '☆'}{self.name}\n\t{self.description}"