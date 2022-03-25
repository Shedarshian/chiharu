from typing import *
import random
from .Helper import ProtocolData, positive
from .Item import Ticket, JibiShopItem
from .Card import Card
from .User import User
from .Equipment import Equipment
if TYPE_CHECKING:
    from .Game import Game

class JibiShopUpdateBegin1(JibiShopItem):
    id = 1
    cost = 25
    name = "刷新接龙词"
    description = "(25击毙)从起始词库中刷新一条接龙词。"
    async def Use(self, user: 'User') -> None:
        word, pic = user.game.UpdateBeginWord(False)
        user.Send(type="update_begin_word", word=word, pic=pic)
class JibiShopRevive2(JibiShopItem):
    id = 2
    cost = 0
    name = "减少死亡时间"
    description = "(1击毙/15分钟)死亡时，可以消耗击毙减少死亡时间。"

class JibiShopCard8(JibiShopItem):
    id = 8
    cost = 5
    name = "购买抽卡"
    description = "(5击毙)抽一张卡，每日限一次。"
    async def HandleCost(self, user: 'User') -> ProtocolData:
        if user.data.shopDrawnCard <= 0:
            return {"type": "failed", "error_code": 440}
        return await super().HandleCost(user)
    async def Use(self, user: 'User') -> None:
        user.data.shopDrawnCard -= 1
        await user.Draw(1)

class MajQuan(Ticket):
    id = 0
    name = "麻将摸牌券"
    description = "麻将摸牌券"
    async def HandleCost(self, user: 'User') -> ProtocolData:
        if user.data.majQuan < 3:
            return {"type": "failed", "error_code": 223}
        user.data.majQuan -= 3
        return {"type": "succeed"}
    async def Use(self, user: 'User') -> None:
        await user.DrawMaj()
class ManganQuan(Ticket):
    id = 1
    name = "满贯抽奖券"
    description = "满贯抽奖券"
    async def HandleCost(self, user: 'User') -> ProtocolData:
        if user.data.mangan < 2:
            return {"type": "failed", "error_code": 223}
        user.data.mangan -= 2
        return {"type": "succeed"}
    async def Use(self, user: 'User') -> None:
        a = random.random()
        if a < 0.02 and user.data.CheckEquipment(5) == 0:
            user.data.equipments.append(Equipment.get(5)())
            user.data.SaveEquipments()
        elif a < 0.32:
            await user.Draw(4)
        elif a < 0.67:
            await user.Draw(3)
        else:
            await user.Draw(2, requirement=positive({1}))
class YakumanQuan(Ticket):
    id = 2
    name = "役满抽奖券"
    description = "役满抽奖券"
    async def HandleCost(self, user: 'User') -> ProtocolData:
        if user.data.yakuman < 2:
            return {"type": "failed", "error_code": 223}
        user.data.yakuman -= 1
        return {"type": "succeed"}
    async def Use(self, user: 'User') -> None:
        a = random.random()
        if a < 0.05 and user.data.CheckEquipment(5) == 0:
            user.data.equipments.append(Equipment.get(5)())
            user.data.SaveEquipments()
        elif a < 0.2:
            await user.Draw(6)
        elif a < 0.45:
            await user.Draw(4)
        elif a < 0.65:
            await user.Draw(5)
        else:
            await user.Draw(3, requirement=positive({1}))
        b = random.random()
        if b < 0.02 and user.data.CheckEquipment(5) == 0:
            user.data.equipments.append(Equipment.get(5)())
            user.data.SaveEquipments()
        elif b < 0.12:
            user.data.mangan += 2
        c = random.random()
        if c < 0.01 and user.data.CheckEquipment(5) == 0:
            user.data.equipments.append(Equipment.get(5)())
            user.data.SaveEquipments()
        elif c < 0.21:
            await user.Draw(0, cards=[Card.get(161)()])

