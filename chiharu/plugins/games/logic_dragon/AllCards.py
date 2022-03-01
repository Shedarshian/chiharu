from typing import *
from datetime import timedelta
from .Card import Card
from .User import User
from .Status import Status, StatusNumed, StatusTimed, StatusNullStack, StatusDailyStack
from .Attack import Attack, AttackType
from .Priority import UserEvt, Priority
from .Types import Pack
from .Dragon import DragonState, Tree

class SDeath(StatusTimed):
    id = -1
    name = "死亡"
    description = "不可接龙。"
    isDebuff = True
    async def BeforeDragoned(self, user: 'User', state: 'DragonState') -> Tuple[bool, int]:
        # send something TODO
        return False, 0
    def register(self) -> Dict[int, int]:
        return {UserEvt.BeforeDragoned: Priority.BeforeDragoned.death}

class AKill(Attack):
    id = -1
    name = "击毙"
    def __init__(self, attacker: 'User', defender: 'User', minute: int):
        self.minute = minute
        super().__init__(attacker, defender)
    async def self_action(self):
        await self.defender.Death(self.minute * self.multiplier, self.attacker, self.counter)

class CFool(Card):
    id = 0
    name = "0 - 愚者"
    positive = -1
    newer = 2
    description = "抽到时附加效果：你下次使用卡牌无效。"
    consumed_on_draw = True
    pack = Pack.tarot
    async def OnDraw(self, user: 'User') -> None:
        await user.AddStatus(SFool())
class SFool(StatusNullStack):
    id = 0
    name = "0 - 愚者"
    description = "你下次使用卡牌无效。"
    isDebuff = True
    async def BeforeCardUse(self, user: 'User', card: 'Card') -> Optional[Awaitable]:
        async def f():
            await user.RemoveStatus(SFool(1))
        return f()
    @classmethod
    def register(cls) -> dict[int, int]:
        return {UserEvt.BeforeCardUse: Priority.BeforeCardUse.fool}

class CMagician(Card):
    id = 1
    name = "I - 魔术师"
    positive = 1
    description = "选择一张你的手牌（不可选择暴食的蜈蚣与组装机1型），发动3次该手牌的使用效果，并弃置之。此后一周内不得使用该卡。"
    pack = Pack.tarot
    def CanUse(self, user: 'User', copy: bool) -> bool:
        return len(user.data.handCard) >= (1 if copy else 2) # TODO 判断不可选择的卡牌
    async def use(self, user: User):
        async with user.choose_cards("请选择你手牌中的一张牌（不可选择暴食的蜈蚣与组装机1型），输入id号。", 1, 1,
                cards_can_not_choose=(56, 200), require_can_use=True) as l: # choose_cards还没做，先抄着
            card = Card(l[0])
            await user.DiscardCards([card])
            await user.UseCardEffect(card)
            await user.UseCardEffect(card)
            await user.UseCardEffect(card)
            await user.AddStatus(SCantUse(timedelta(weeks=1)))
class SCantUse(StatusTimed):
    id = 1
    isDebuff = True
    # 呃 这个构造函数 有点麻烦 再说

class CHierophant(Card):
    id = 5
    name = "V - 教皇"
    positive = 1
    description = "你的下10次接龙中每次额外获得2击毙，但额外要求首尾接龙。"
    newer = 3
    pack = Pack.tarot
    async def Use(self, user: 'User') -> None:
        await user.AddStatus(SHierophant(10))
class SHierophant(StatusNumed):
    id = 5
    name = "V - 教皇"
    description = "你的下10次接龙中每次额外获得2击毙，但额外要求首尾接龙。"
    async def BeforeDragoned(self, user: 'User', state: 'DragonState') -> Tuple[bool, int]:
        if not await state.RequireShouwei(user):
            return False, 0
        return True, 0
    async def OnDragoned(self, user: 'User', branch: 'Tree', first10: bool) -> None:
        await user.AddJibi(2)
        self.num = self.num - 1
        user.data.SaveStatuses()
    def register(self) -> Dict[int, int]:
        return {UserEvt.BeforeDragoned: Priority.BeforeDragoned.hierophant,
            UserEvt.OnDragoned: Priority.OnDragoned.hierophant}
