from typing import *
from .Helper import HasId, ProtocolData
if TYPE_CHECKING:
    from .User import User

class Item:
    name = "NoName"
    description = "NoDes"
    async def HandleCost(self, user: 'User') -> ProtocolData:
        return {"type": "succeed"}
    async def Use(self, user: 'User') -> None:
        pass

class JibiShopItem(Item, HasId):
    cost = 0
    async def HandleCost(self, user: 'User') -> ProtocolData:
        ret = await user.AddJibi(self.cost, isBuy=True)
        if ret:
            return {"type": "succeed"}
        return {"type": "failed", "error_code": 410}

class EventShopItem(Item, HasId):
    cost = 0
    async def HandleCost(self, user: 'User') -> ProtocolData:
        ret = await user.AddEventPt(self.cost, isBuy=True)
        if ret:
            return {"type": "succeed"}
        return {"type": "failed", "error_code": 411}

class Ticket(Item, HasId):
    def DumpData(self):
        return {"id": self.id, "name": self.name, "description": self.description}
