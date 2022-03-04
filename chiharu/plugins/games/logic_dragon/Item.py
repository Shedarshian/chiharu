from typing import *
from .Helper import HasId, ProtocolData
if TYPE_CHECKING:
    from .User import User

class Item:
    name = "NoName"
    description = "NoDes"
    async def HandleCost(self, user: 'User') -> bool:
        return True
    async def Use(self, user: 'User') -> None:
        pass

class JibiShopItem(Item, HasId):
    cost = 0
    async def HandleCost(self, user: 'User') -> ProtocolData:
        ret = await user.AddJibi(self.cost, isBuy=True)
        if ret:
            return {"type": "succeed"}
        else:
            return {"type": "failed", "error_code": 410}

