from abc import abstractmethod
from typing import *
from .EventListener import IEventListener
from .Helper import Saveable, BuildIdMeta
from .Types import ProtocolData
if TYPE_CHECKING:
    from .User import User

TEquipment = TypeVar("TEquipment", bound='Equipment')

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
    def canUse(self, user: 'User') -> bool:
        return True
    async def use(self, user: 'User') -> None:
        pass
    def DumpData(self) -> ProtocolData:
        return {"id": self.id, "name": self.name, "description": self.description}

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