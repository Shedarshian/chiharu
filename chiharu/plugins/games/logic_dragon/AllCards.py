from typing import *
from datetime import timedelta, datetime
import itertools, random
from .Card import Card
from .User import User
from .Status import Status, StatusNumed, StatusTimed, StatusNullStack, StatusDailyStack
from .Attack import Attack, AttackType
from .Priority import UserEvt, Priority
from .Types import Pack
from .Dragon import DragonState, Tree
from .Mission import Mission

class SDeathN1(StatusTimed):
    id = -1
    name = "死亡"
    _description = "不可接龙。"
    isDebuff = True
    async def BeforeDragoned(self, user: 'User', state: 'DragonState') -> Tuple[bool, int]:
        """因死亡不可接龙。"""
        user.Send(type="status_effect", status=self.DumpData())
        return False, 0
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.BeforeDragoned: Priority.BeforeDragoned.death}

class AKill0(Attack):
    id = 0
    name = "击毙"
    def __init__(self, attacker: 'User', defender: 'User', minute: int):
        self.minute = minute
        super().__init__(attacker, defender)
    async def selfAction(self):
        await self.defender.Death(self.minute * self.multiplier, self.attacker, self.counter)

class ADamage1(Attack):
    id = 1
    name = "伤害"
    def __init__(self, attacker: 'User', defender: 'User', damage: int, mustHit: bool):
        self.damage = damage
        self.mustHit = mustHit
        super().__init__(attacker, defender)
    async def selfAction(self):
        pass # TODO

class CFool0(Card):
    id = 0
    name = "0 - 愚者"
    positive = -1
    newer = 2
    _description = "抽到时附加效果：你下次使用卡牌无效。"
    consumed_on_draw = True
    pack = Pack.tarot
    async def OnDraw(self, user: 'User') -> None:
        await user.AddStatus(SFool0())
class SFool0(StatusNullStack):
    id = 0
    name = "0 - 愚者"
    _description = "你下次使用卡牌无效。"
    isDebuff = True
    async def BeforeCardUse(self, user: 'User', card: 'Card') -> Optional[Awaitable]:
        """阻挡使用卡牌。"""
        user.Send(type="status_effect", status=self.DumpData())
        async def f():
            await user.RemoveStatus(SFool0, 1)
        return f()
    @classmethod
    def register(cls) -> dict[UserEvt, int]:
        return {UserEvt.BeforeCardUse: Priority.BeforeCardUse.fool}

class CMagician1(Card):
    id = 1
    name = "I - 魔术师"
    positive = 1
    _description = "选择一张你的手牌（不可选择暴食的蜈蚣与组装机1型），发动3次该手牌的使用效果，并弃置之。此后一周内不得使用该卡。"
    pack = Pack.tarot
    def CanUse(self, user: 'User', copy: bool) -> bool:
        return len(user.data.handCard) >= (1 if copy else 2) # TODO 判断不可选择的卡牌
    async def use(self, user: User):
        # send TODO "请选择你手牌中的一张牌（不可选择暴食的蜈蚣与组装机1型），输入id号。"
        l = await user.ChooseHandCards(1, 1,
                requirement=lambda c: c.id not in (56, 200),
                requireCanUse=True)
        card = l[0]
        await user.DiscardCards([card])
        await user.UseCardEffect(card)
        await user.UseCardEffect(card)
        await user.UseCardEffect(card)
        await user.AddStatus(SCantUse1(timedelta(weeks=1), card.id))
class SCantUse1(StatusTimed):
    id = 1
    isDebuff = True
    dataType = (datetime.fromisoformat, int)
    def __init__(self, data: Union[datetime, timedelta], cardId: int):
        super().__init__(data)
        self.cardId = cardId
    def packData(self) -> str:
        return super().packData() + "," + str(self.cardId)
    @property
    def description(self):
        return f"疲劳：不可使用卡牌【{Card(self.cardId).name}】。"
    @property
    def brief_des(self):
        delta = self.time - datetime.now()
        min = delta.seconds // 60
        return f"疲劳【{Card(self.cardId).name}】\n\t结束时间：{self.getStr()}。"
    async def OnUserUseCard(self, user: 'User', card: 'Card') -> bool:
        """禁止使用卡牌。
        cardId: 禁止使用的卡牌id。"""
        if self.cardId == card.id:
            user.Send(type="status_effect", status=self.DumpData(), cardId=self.cardId)
            return False
        return True
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnUserUseCard: Priority.OnUserUseCard.cantuse}

class CHighPriestess2(Card):
    id = 2
    name = "II - 女祭司"
    _description = "击毙当前周期内接龙次数最多的玩家。"
    positive = 1
    pack = Pack.tarot
    async def Use(self, user: User):
        counter = Counter([tree.qq for tree in itertools.chain(*itertools.chain(user.game.treeObjs, *user.game.treeForests))])
        l = counter.most_common()
        ql = [qq for qq, time in l if time == l[0][1]]
        for q in ql:
            await user.CreateUser(q).Killed(user)

class CEmpress3(Card):
    id = 3
    name = "III - 女皇"
    _description = "你当前手牌中所有任务之石的可完成次数+3。如果当前手牌无任务之石，则为你派发一个可完成3次的任务，每次完成获得3击毙，跨日时消失。"
    positive = 1
    pack = Pack.tarot
    async def Use(self, user: 'User') -> None:
        done = False
        for card in user.data.handCard:
            if card.id == 67:
                card.num += 3 # TODO
                done = True
        if not done:
            await user.AddStatus(SQuest3(3, 3, Mission.RandomQuestStoneId()))
class SQuest3(StatusNumed):
    id = 3
    @property
    def isDebuff(self):
        return self.jibi < 0
    dataType = (int, int, int)
    def __init__(self, data: int, jibi: int, questId: int) -> None:
        super().__init__(data)
        self.jibi = jibi
        self.questId = questId
    def packData(self):
        return f"{super().packData()},{self.jibi},{self.questId}"
    @property
    def description(self):
        return f"今日任务：{Mission.get(self.questId).description}\n\t剩余次数：{self.num}次，完成获得击毙：{self.jibi}。"
    async def OnDragoned(self, user: 'User', branch: 'Tree', first10: bool) -> None:
        mission = Mission.get(self.questId)
        if mission().check(branch.word):
            self.num = self.num - 1 # pylint: disable=attribute-defined-outside-init
            await user.AddJibi(self.jibi)
            user.data.SaveStatuses()
    async def OnNewDay(self, user: 'User') -> None:
        await user.RemoveAllStatus(SQuest3)
    def register(self) -> dict['UserEvt', int]:
        return {UserEvt.OnDragoned: Priority.OnDragoned.quest,
            UserEvt.OnNewDay: Priority.OnNewDay.quest}


class CHierophant5(Card):
    id = 5
    name = "V - 教皇"
    positive = 1
    _description = "你的下10次接龙中每次额外获得2击毙，但额外要求首尾接龙。"
    newer = 3
    pack = Pack.tarot
    async def Use(self, user: 'User') -> None:
        await user.AddStatus(SHierophant5(10))
class SHierophant5(StatusNumed):
    id = 5
    name = "V - 教皇"
    _description = "你的下10次接龙中每次额外获得2击毙，但额外要求首尾接龙。"
    async def BeforeDragoned(self, user: 'User', state: 'DragonState') -> Tuple[bool, int]:
        """禁止非首尾接龙。"""
        if not await state.RequireShouwei(user):
            user.Send(type="status_effect", status=self.DumpData(), time="BeforeDragoned")
            return False, 0
        return True, 0
    async def OnDragoned(self, user: 'User', branch: 'Tree', first10: bool) -> None:
        """奖励2击毙。"""
        user.Send(type="status_effect", status=self.DumpData(), time="OnDragoned")
        await user.AddJibi(2)
        self.num = self.num - 1 # pylint: disable=attribute-defined-outside-init
        user.data.SaveStatuses()
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.BeforeDragoned: Priority.BeforeDragoned.hierophant,
            UserEvt.OnDragoned: Priority.OnDragoned.hierophant}
class SInvHierophant6(StatusNumed):
    id = 6
    name = "反转 - 教皇"
    _description = "你的下10次接龙中每次损失2击毙，并且额外要求尾首接龙。"
    isDebuff = True
    async def BeforeDragoned(self, user: 'User', state: 'DragonState') -> Tuple[bool, int]:
        """禁止非尾首接龙。"""
        if not await state.RequireWeishou(user):
            user.Send(type="status_effect", status=self.DumpData(), time="BeforeDragoned")
            return False, 0
        return True, 0
    async def OnDragoned(self, user: 'User', branch: 'Tree', first10: bool) -> None:
        """损失2击毙。"""
        user.Send(type="status_effect", status=self.DumpData(), time="OnDragoned")
        await user.AddJibi(-2)
        self.num = self.num - 1 # pylint: disable=attribute-defined-outside-init
        user.data.SaveStatuses()
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.BeforeDragoned: Priority.BeforeDragoned.inv_hierophant,
            UserEvt.OnDragoned: Priority.OnDragoned.inv_hierophant}

class CLovers6(Card):
    id = 6
    name = "VI - 恋人"
    _description = "复活1名指定玩家。"
    positive = 1
    pack = Pack.tarot
    async def Use(self, user: User):
        if (players := await user.ChoosePlayers(1, 1)) is not None:
            u = user.CreateUser(players[0])
            n = len(u.CheckStatus(SDeathN1)) == 0
            await u.RemoveAllStatus(SDeathN1)

class CWheelOfFortune10(Card):
    id = 10
    name = "X - 命运之轮"
    positive = 0
    _description = "直至下次刷新前，在商店增加抽奖机，可以花费5击毙抽奖。"
    pack = Pack.tarot
    async def Use(self, user: 'User') -> None:
        await user.ume.AddStatus(SWOF10())
class SWOF10(Status):
    id = 10
    name = "命运之轮"
    _description = "直至下次刷新前，在商店增加抽奖机，可以消耗5击毙抽奖。"
    isGlobal = True

class CJustice11(Card):
    id = 11
    name = "XI - 正义"
    positive = 1
    _description = "现在你身上每有一个状态，奖励你5击毙。"
    pack = Pack.tarot
    async def Use(self, user: 'User') -> None:
        n = len(user.data.statuses)
        user.Send(type="card_effect", status=self.DumpData(), time="OnCardUse")
        await user.AddJibi(n * 5)

class CHangedMan12(Card):
    id = 12
    name = "XII - 倒吊人"
    positive = 1
    _description = "你立即死亡，然后免疫你下一次死亡。"
    pack = Pack.tarot
    async def Use(self, user: 'User') -> None:
        await user.AddStatus(SDeathN1(seconds = 120))
        await user.AddStatus(SHangedMan12())
class SHangedMan12(StatusNullStack):
    id = 12
    name = "倒吊人"
    _description = "免疫你下一次死亡。"
    async def OnDeath(self, user: 'User', attacker: 'User') -> bool:
        self.num -= 1
        reutrn False
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnDeath: Priority.OnDeath.miansi}