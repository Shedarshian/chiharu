from typing import *
from datetime import timedelta, datetime
from copy import copy
import itertools, random
from .Card import Card
from .User import User
from .Status import Status, StatusNumed, StatusTimed, StatusNullStack, StatusDailyStack
from .Attack import Attack, AttackType
from .Priority import UserEvt, Priority
from .Types import Pack
from .Dragon import DragonState, Tree
from .Mission import Mission
from .Helper import positive

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
    consumedOnDraw = True
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
        user.SendStatusEffect(self)
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
            user.SendStatusEffect(self, cardId=self.cardId)
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
        """完成任务。
        jibi: 获得的击毙数。
        remain: 剩余完成次数。
        mission: 任务描述。"""
        mission = Mission.get(self.questId)()
        if mission.check(branch.word):
            self.num = self.num - 1 # pylint: disable=attribute-defined-outside-init
            user.SendStatusEffect(self, remain=self.num, jibi=self.jibi, mission=mission.description)
            await user.AddJibi(self.jibi)
            user.data.SaveStatuses()
    async def OnNewDay(self, user: 'User') -> None:
        await user.RemoveAllStatus(SQuest3)
    def register(self) -> dict['UserEvt', int]:
        return {UserEvt.OnDragoned: Priority.OnDragoned.quest,
            UserEvt.OnNewDay: Priority.OnNewDay.quest}

class CEmperor4(Card):
    id = 4
    name = "IV - 皇帝"
    positive = 1
    _description = "为你派发一个随机任务，可完成10次，每次完成获得2击毙，跨日时消失。"
    pack = Pack.tarot
    async def Use(self, user: 'User') -> None:
        await user.AddStatus(SQuest3(10, 2, Mission.RandomQuestStoneId()))

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
            user.SendStatusEffect(self, time="BeforeDragoned")
            return False, 0
        return True, 0
    async def OnDragoned(self, user: 'User', branch: 'Tree', first10: bool) -> None:
        """奖励2击毙。"""
        user.SendStatusEffect(self, time="OnDragoned")
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
            user.SendStatusEffect(self, time="BeforeDragoned")
            return False, 0
        return True, 0
    async def OnDragoned(self, user: 'User', branch: 'Tree', first10: bool) -> None:
        """损失2击毙。"""
        user.SendStatusEffect(self, time="OnDragoned")
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

class CChariot7(Card):
    id = 7
    name = "VII - 战车"
    positive = 1
    newer = 5
    _description = "对你今天第一次和最后一次接龙中间接龙的人（除了你自己）每人做一次10%致死的击毙判定。"
    pack = Pack.tarot
    async def Use(self, user: User) -> None:
        to_kill = set()
        for l in user.game.treeObjs:
            node = l[-1]
            temp: List[Tree] = []
            while node.parent is not None:
                if node.qq == user.qq:
                    if len(temp) != 0:
                        to_kill |= set(n.qq for n in temp)
                    temp = [node]
                elif len(temp) != 0:
                    temp.append(node)
                node = node.parent
        if user.qq in to_kill:
            to_kill.remove(user.qq)
        to_kill = set(qq for qq in to_kill if random.random() < (0.1 + 0.01 * user.data.luck))
        # user.buf.send(f"{'，'.join(f'[CQ:at,qq={qq}]' for qq in to_kill)}被你击杀了{句尾}")
        for qq in to_kill:
            await user.CreateUser(qq).Killed(user)

class CHermit9(Card):
    id = 9
    name = "IX - 隐者"
    positive = 1
    _description = "今天你不会因为接到重复词或触雷而死亡。"
    pack = Pack.tarot
    async def Use(self, user: 'User') -> None:
        await user.AddStatus(SHermit9())
class SHermit9(StatusDailyStack):
    id = 9
    name = "IX - 隐者"
    _description = "今天你不会因为接到重复词或触雷而死亡。"
    async def OnDuplicatedWord(self, user: 'User', word: str, originalQQ: int) -> bool:
        """抵消接到重复词死亡效果。"""
        user.SendStatusEffect(self, time="OnDuplicatedWord")
        return True
    async def OnBombed(self, user: 'User', word: str) -> bool:
        """抵消触雷死亡效果。"""
        user.SendStatusEffect(self, time="OnBombed")
        return True
    def register(self) -> Dict['UserEvt', int]:
        return {UserEvt.OnDuplicatedWord: Priority.OnDuplicatedWord.hermit,
            UserEvt.OnBombed: Priority.OnBombed.hermit}

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
    name = "X - 命运之轮"
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
        await user.AddJibi(n * 5)

class CHangedMan12(Card):
    id = 12
    name = "XII - 倒吊人"
    positive = 1
    _description = "你立即死亡，然后免疫你下一次死亡。"
    pack = Pack.tarot
    async def Use(self, user: 'User') -> None:
        await user.Death()
        await user.AddStatus(SHangedMan12())
class SHangedMan12(StatusNullStack):
    id = 12
    name = "XII - 倒吊人"
    _description = "免疫你下一次死亡。"
    async def OnDeath(self, user: 'User', killer: Optional['User'], time: int, c: 'AttackType') -> Tuple[int, bool]:
        self.num -= 1 # pylint: disable=no-member
        return time, True
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnDeath: Priority.OnDeath.miansi}

class CDeath13(Card):
    id = 13
    name = "XIII - 死神"
    positive = 0
    _description = "今天的所有死亡时间加倍。"
    pack = Pack.tarot
    async def Use(self, user: 'User') -> None:
        await user.ume.AddStatus(SDeath13())
class SDeath13(StatusDailyStack):
    id = 13
    name = "XIII - 死神"
    _description = "今天的所有死亡时间加倍。"
    isGlobal = True
    isDebuff = True
    async def OnDeath(self, user: 'User', killer: Optional['User'], time: int, c: 'AttackType') -> Tuple[int, bool]:
        time *= 2 ** self.count
        return time, False
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnDeath: Priority.OnDeath.death}

class CTemperance14(Card):
    name = "XIV - 节制"
    id = 14
    _description = "随机抽取1名玩家，今天该玩家不能使用除胶带外的卡牌。"
    positive = 0
    pack = Pack.tarot
    async def Use(self, user: 'User') -> None:
        l = user.game.AllUserQQs()
        qq = random.choice(l)
        target = user.CreateUser(qq)
        atk = ATemperance14(user, target)
        await target.Attacked(user, atk)
class ATemperance14(Attack):
    id = 14
    name = "节制"
    doublable = False
    async def selfAction(self):
        await self.defender.AddStatus(STemperance14())
class STemperance14(StatusDailyStack):
    id = 14
    name = "XIV - 节制"
    _description = "今天你不能使用除胶带外的卡牌。"
    isDebuff = True
    async def OnUserUseCard(self, user: 'User', card: 'Card') -> bool:
        if card.id != 100:
            return False
        return True
    def register(self) -> Dict['UserEvt', int]:
        return {UserEvt.OnUserUseCard: Priority.OnUserUseCard.temperance}

class CDevil15(Card):
    name = "XV - 恶魔"
    id = 15
    positive = 1
    _description = "击毙上一位使用卡牌的人。"
    pack = Pack.tarot
    async def Use(self, user: 'User') -> None:
        qq = user.game.state['last_card_user']
        u = user.CreateUser(qq)
        await u.Killed(user)

class CTower16(Card):
    name = "XVI - 高塔"
    id = 16
    positive = 0
    _description = "随机解除至多3个雷，随机击毙3个玩家。"
    pack = Pack.tarot
    async def Use(self, user: 'User') -> None:
        for i in range(3):
            if len(user.game.bombs) == 0:
                break
            b = random.choice(user.game.bombs)
            user.game.RemoveBomb(b)
        l = user.game.AllUserQQs()
        p: List[int] = []
        for i in range(3):
            p.append(random.choice(l))
            l.remove(p[-1])
        for q in p:
            await user.CreateUser(q).Killed(user)

class CStar17(Card):
    name = "XVII - 星星"
    id = 17
    positive = 0
    _description = "今天的每个词有10%的几率进入奖励词池。"
    pack = Pack.tarot
    async def Use(self, user: 'User') -> None:
        await user.ume.AddStatus(SStar17())
class SStar17(StatusDailyStack):
    id = 17
    _description = "XVII - 星星：今天的每个词有10%的几率进入奖励词池。"
    isGlobal = True
    async def OnDragoned(self, user: 'User', branch: 'Tree', first10: bool) -> None:
        if random.random() > 0.9 ** self.num:
            user.game.AddKeyword(branch.word)
    def register(self) -> Dict['UserEvt', int]:
        return {UserEvt.OnDragoned: Priority.OnDragoned.star}

class CSun19(Card):
    name = "XIX - 太阳"
    id = 19
    positive = 1
    _description = "随机揭示一个隐藏奖励词。"
    pack = Pack.tarot
    async def Use(self, user: 'User') -> None:
        random.choice(user.game.hiddenKeyword) # TODO

class CJudgement20(Card):
    name = "XX - 审判"
    id = 20
    positive = 0
    newer = 3
    _description = "若你今天接龙次数小于5，则扣除20击毙，若你今天接龙次数大于20，则获得20击毙。"
    pack = Pack.tarot
    async def Use(self, user: 'User') -> None:
        n = [tree.qq for tree in itertools.chain(*itertools.chain(user.game.treeObjs, *user.game.treeForests))].count(user.qq)
        if n < 5:
            await user.AddJibi(-20)
        elif n > 20:
            await user.AddJibi(20)

class CRandomMaj29(Card):
    id = 29
    name = "扣置的麻将"
    positive = 1
    mass = 0.25
    _description = "增加5次麻将摸牌的机会，然后抽一张卡。"
    pack = Pack.misc
    async def Use(self, user: 'User') -> None:
        user.data.majQuan += 5
        await user.Draw(1)

class CIll30(Card):
    id = 30
    name = "大病一场"
    positive = -1
    _description = "抽到时，直到跨日前不得接龙。"
    consumedOnDraw = True
    pack = Pack.zhu
    async def OnDraw(self, user: 'User') -> None:
        await user.AddStatus(SIll30())
class SIll30(StatusDailyStack):
    id = 30
    name = "大病一场"
    isDebuff = True
    isRemovable = False
    _description = "直到跨日前不得接龙。"
    async def BeforeDragoned(self, user: 'User', state: 'DragonState') -> Tuple[bool, int]:
        # send something
        return False, 0
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.BeforeDragoned: Priority.BeforeDragoned.shengbing}

class CCaiPiaoZhongJiang31(Card):
    id = 31
    name = "彩票中奖"
    positive = 1
    _description = "抽到时，你立即获得20击毙与两张牌。"
    consumedOnDraw = True
    pack = Pack.zhu
    async def OnDraw(self, user: 'User') -> None:
        await user.AddJibi(20)
        await user.Draw(2)

class CDragonTube54(Card):
    name = "龙之烟管"
    id = 54
    positive = 1
    _description = "你今天通过普通接龙获得的击毙上限增加10。"
    isMetallic = True
    mass = 0.2
    pack = Pack.honglongdong
    async def Use(self, user: 'User') -> None:
        user.data.todayJibi += 10

class CXingYunTuJiao55(Card):
    name = "幸运兔脚"
    id = 55
    positive = 1
    _description = "抽取一张正面卡并立即发动其使用效果。"
    pack = Pack.honglongdong
    async def Use(self, user: 'User') -> None:
        await user.DrawAndUse(requirement=positive({1}))

class CBaoShiDeWuGong56(Card):
    name = "暴食的蜈蚣"
    id = 56
    positive = 1
    _description = "你的手牌上限永久+1。"
    pack = Pack.honglongdong
    @staticmethod
    def _weight(user: User):
        # if user.data.card_limit < 20:
        #     return 1 + user.data.luck / 10 * (20 - user.data.card_limit)
        return 1
    weight = _weight
    async def Use(self, user: 'User') -> None:
        user.data.cardLimitRaw += 1

class CZhaoCaiMao57(Card):
    name = "擅长做生意的招财猫"
    id = 57
    positive = 1
    _description = "你今天可以额外购买3次商店里的购买卡牌。"
    pack = Pack.honglongdong
    async def Use(self, user: 'User') -> None:
        user.data.shopDrawnCard += 3

class CPlusTwo60(Card):
    name = "+2"
    id = 60
    positive = 0
    _description = "下一个接龙的人摸一张非负面卡和一张非正面卡。"
    pack = Pack.uno
    async def Use(self, user: 'User') -> None:
        await user.ume.AddStatus(SPlusTwo60())
class SPlusTwo60(StatusNullStack):
    id = 60
    name = "+2"
    _description = "下一个接龙的人摸一张非负面卡和一张非正面卡。"
    isGlobal = True
    async def OnDragoned(self, user: 'User', branch: 'Tree', first10: bool) -> None:
        await user.ume.RemoveStatus(self)
        cards = list(itertools.chain(*[[user.game.RandomNewCards(user, requirement=positive({-1, 0}))[0], user.game.RandomNewCards(user, requirement=positive({0, 1}))[0]] for i in range(self.count)]))
        await user.Draw(0, cards=cards)
    def register(self) -> Dict['UserEvt', int]:
        return {UserEvt.OnDragoned: Priority.OnDragoned.plus2}

class CLuckyCharm73(Card):
    name = "幸运护符"
    id = 73
    # hold_des = '幸运护符：每天只能使用一张其他卡牌，你的幸运值+1。'
    positive = 1
    _description = "持有此卡时，每天只能使用一张其他卡牌，你的幸运值+1。使用将丢弃这张卡。"
    pack = Pack.orange_juice
    async def OnUserUseCard(self, user: 'User', card: 'Card') -> bool:
        if not isinstance(card, CLuckyCharm73):
            # user.send_log("今天幸运护符的使用卡牌次数已用完" + 句尾)
            await user.AddStatus(SLuckyCharm73())
        return True
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnUserUseCard: Priority.OnUserUseCard.xingyunhufu}
class SLuckyCharm73(StatusDailyStack):
    id = 73
    name = "幸运护符次数已用完："
    _description = "今天你不能使用除幸运护符以外的卡牌。"
    isDebuff = True
    async def OnUserUseCard(self, user: 'User', card: 'Card') -> bool:
        if any(isinstance(c, CLuckyCharm73) for c in user.data.handCard) and not isinstance(card, CLuckyCharm73):
            # TODO
            return False
        return True
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnUserUseCard: Priority.OnUserUseCard.xingyunhufus}

class CJiSuZhuangZhi74(Card):
    name = "极速装置"
    id = 74
    positive = 1
    _description = '你下次你可以连续接龙两次。'
    pack = Pack.orange_juice
    async def Use(self, user: 'User') -> None:
        user.AddStatus(SJiSuZhuangZhi74())
class SJiSuZhuangZhi74(StatusNullStack):
    id = 74
    name = "极速装置"
    _description = "你下次可以连续接龙两次。"
    async def CheckSuguri(self, user: 'User', state: 'DragonState') -> bool:
        # TODO
        await user.RemoveStatus(SJiSuZhuangZhi74(1))
        return True
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.CheckSuguri: Priority.CheckSuguri.jisuzhuangzhi}

class CZhongShenDeXiXi76(Card):
    name = "众神的嬉戏"
    id = 76
    positive = 0
    _description = '抽取一张卡并立即发动其使用效果。'
    pack = Pack.orange_juice
    async def Use(self, user: 'User') -> None:
        await user.DrawAndUse()

class CJianDieYuBei78(Card):
    name = "邪恶的间谍行动～预备"
    id = 78
    positive = 0
    _description = "今日卡池中有一定概率出现【邪恶的间谍行动~执行】。"
    pack = Pack.orange_juice
    async def Use(self, user: 'User') -> None:
        await user.ume.AddStatus(SJianDieYuBei78())
class SJianDieYuBei78(StatusDailyStack):
    id = 78
    name = "邪恶的间谍行动～预备"
    _description = "今日卡池中有一定概率出现【邪恶的间谍行动~执行】。"

class CQiJiManBu79(Card):
    name = "奇迹漫步"
    id = 79
    positive = 1
    _description = "弃置你所有手牌，并摸取等量的非负面牌。"
    pack = Pack.orange_juice
    async def Use(self, user: 'User') -> None:
        n = len(user.data.handCard)
        await user.DiscardCards(copy(user.data.handCard)) # I think this need to be shallow copy
        await user.Draw(n, requirement=positive({0, 1}))

class CComicSans80(Card): # TODO
    name = "Comic Sans"
    id = 80
    positive = 0
    _description = "七海千春今天所有生成的图片均使用Comic Sans作为西文字体（中文使用华文彩云）。"
    pack = Pack.playtest
    async def Use(self, user: 'User') -> None:
        await user.ume.AddStatus(SComicSans80())
class SComicSans80(StatusDailyStack):
    name = "Comic Sans"
    id = 80
    isGlobal = True
    _description = "七海千春今天所有生成的图片均使用Comic Sans作为西文字体（中文使用华文彩云）。"

