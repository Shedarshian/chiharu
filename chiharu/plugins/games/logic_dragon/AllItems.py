from typing import *
from .Helper import ProtocolData
from .Item import Item, JibiShopItem
from .Card import Card
from .User import User
if TYPE_CHECKING:
    from .Game import Game

class JibiShopCard(JibiShopItem):
    id = 8
    cost = 5
    name = "抽卡"
    description = "抽一张卡，每日限一次。"
    async def HandleCost(self, user: 'User') -> ProtocolData:
        if user.data.shopDrawnCard <= 0:
            return {"type": "failed", "error_code": 440}
        return await super().HandleCost(user)
    async def Use(self, user: 'User') -> None:
        user.data.shopDrawnCard -= 1
        await user.Draw(1)
