from abc import abstractmethod
from typing import *
from .EventListener import IEventListener
from .Helper import Saveable, BuildIdMeta
from ...config import mysingledispatchmethod
if TYPE_CHECKING:
    from .User import User

class Equipment(IEventListener, Saveable):
    _name = "NoName"
    _description = ""
    shopDes = "NoDes"
    @property
    def level(self):
        return 1
    @property
    def name(self):
        return self._name
    @property
    def description(self):
        return self._description
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
    def name(self):
        return f"{self.count * '☆'}{self.name}"