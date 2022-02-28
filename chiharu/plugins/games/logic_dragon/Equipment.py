from abc import abstractmethod
from typing import *
from .EventListener import IEventListener
from .Helper import Saveable, BuildIdMeta
from ...config import mysingledispatchmethod
if TYPE_CHECKING:
    from .User import User

class Equipment(IEventListener, Saveable, metaclass=BuildIdMeta):
    name = "NoName"
    description = ""
    shopDes = "NoDes"
    @property
    def level(self):
        return 1
    @property
    def fullDescription(self):
        return f"{self.id}. {self.name}\n\t{self.description}"
    def __init__(self, data: Optional[str]=None) -> None:
        pass
    def canUse(self, user: 'User') -> tuple[bool, str]:
        return True, ""
    async def use(self, user: 'User') -> None:
        pass

class EquipmentStar(Equipment):
    @property
    def level(self):
        return self.count
    @property
    def fullDescription(self):
        return f"{self.id}. {self.count * '☆'}{self.name}\n\t{self.description}"
    @mysingledispatchmethod
    def __init__(self, data: Optional[str] = None) -> None:
        if data is None:
            self.count = 1
        else:
            self.count = int(data)
    @__init__.register
    def _(self, data: int):
        self.count = data