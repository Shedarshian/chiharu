from typing import *
from datetime import timedelta, datetime
from copy import copy
from math import ceil
from collections import Counter
import itertools, random
from .Game import Game
from .Card import Card
from .User import User
from .Status import Status, StatusNumed, StatusTimed, StatusNullStack, StatusDailyStack
from .Attack import Attack, AttackType
from .Priority import UserEvt, Priority
from .Types import Pack
from .Dragon import DragonState, Tree
from .Mission import Mission
from .EventListener import IEventListener
from .Helper import positive
from ... import config
log = config.logger.dragon

class SDeathN1(StatusTimed):
    id = -1
    name = "死亡"
    _description = "不可接龙。"
    isDebuff = True
    isRemovable = False
    async def BeforeDragoned(self, user: 'User', state: 'DragonState') -> Tuple[bool, int]:
        """因死亡不可接龙。"""
        # user.Send(type="status_effect", status=self.DumpData())
        user.SendStatusEffect(self)
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
        user.SendCardOnDraw(self)
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
        return len(c for c in user.data.handCard if c.id not in (56, 200)) >= (1 if copy else 2)
    async def use(self, user: User):
        """试图选择卡牌。"""
        user.SendCardUse(self)
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
    isRemovable = False
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
    async def OnUserUseCard(self, user: 'User', card: 'Card') -> tuple[bool, bool]:
        """禁止使用卡牌。
        forbiddencard: 禁止使用的卡牌。"""
        if self.cardId == card.id:
            user.SendStatusEffect(self, forbiddencard=card.DumpData())
            return False, False
        return True, False
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnUserUseCard: Priority.OnUserUseCard.cantuse}

class CHighPriestess2(Card):
    id = 2
    name = "II - 女祭司"
    _description = "击毙当前周期内接龙次数最多的玩家。"
    positive = 1
    pack = Pack.tarot
    async def Use(self, user: User):
        """击杀的玩家。
        userIDs: 被击杀的玩家qq号列表。"""
        counter = Counter([tree.qq for tree in itertools.chain(*itertools.chain(user.game.treeObjs, *user.game.treeForests))])
        l = counter.most_common()
        ql = [qq for qq, time in l if time == l[0][1]]
        user.SendCardUse(self, userIDs=ql)
        for q in ql:
            await user.CreateUser(q).Killed(user, isAOE = (len(ql) > 1))

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
        """选择玩家复活。"""
        user.SendCardUse(self)
        if (players := await user.ChoosePlayers(1, 1)) is not None:
            u = user.CreateUser(players[0])
            n = len(u.CheckStatus(SDeathN1)) == 0
            await u.RemoveAllStatus(SDeathN1, remover=user)

class CChariot7(Card):
    id = 7
    name = "VII - 战车"
    positive = 1
    _description = "对你今天第一次和最后一次接龙中间接龙的人（除了你自己）每人做一次10%致死的击毙判定。"
    pack = Pack.tarot
    async def Use(self, user: User) -> None:
        '''概率杀死中间接龙的人
        to_kill：需要杀死的人'''
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
        user.SendCardUse(self, to_kill=list(to_kill))
        for qq in to_kill:
            await user.CreateUser(qq).Killed(user, isAOE = (len(to_kill) > 1))

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
        """免死。"""
        user.SendStatusEffect(self)
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
        """时间加倍。
        count：加倍的次数"""
        user.SendStatusEffect(self, count = self.count)
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
    async def OnUserUseCard(self, user: 'User', card: 'Card') -> tuple[bool, bool]:
        """不能使用卡牌。"""
        if card.id != 100:
            user.SendStatusEffect(self)
            return False, False
        return True, False
    def register(self) -> Dict['UserEvt', int]:
        return {UserEvt.OnUserUseCard: Priority.OnUserUseCard.temperance}

class CDevil15(Card):
    name = "XV - 恶魔"
    id = 15
    positive = 1
    _description = "击毙上一位使用卡牌的人。"
    pack = Pack.tarot
    async def Use(self, user: 'User') -> None:
        """击毙。
        userQQ: 被击毙的人的qq。"""
        qq = user.game.state['last_card_user']
        user.SendCardUse(self, userQQ=qq)
        u = user.CreateUser(qq)
        await u.Killed(user)

class CTower16(Card):
    name = "XVI - 高塔"
    id = 16
    positive = 0
    _description = "随机解除至多3个雷，随机击毙3个玩家。"
    pack = Pack.tarot
    async def Use(self, user: 'User') -> None:
        """击毙。
        qqlist: 被击毙的人的qq的列表。"""
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
        user.SendCardUse(self, qqlist=p)
        for q in p:
            await user.CreateUser(q).Killed(user, isAOE = (len(p)>1))

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
    name = "XVII - 星星"
    _description = "今天的每个词有10%的几率进入奖励词池。"
    isGlobal = True
    async def OnDragoned(self, user: 'User', branch: 'Tree', first10: bool) -> None:
        """添加奖励词。
        word: 添加的词。"""
        if random.random() > 0.9 ** self.num:
            user.SendStatusEffect(self, word=branch.word)
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
        """揭示一个隐藏奖励词。
        hiddenKeyword: 所揭示的奖励词。"""
        user.SendCardUse(self, hiddenKeyword = random.choice(user.game.hiddenKeyword))

class CJudgement20(Card):
    name = "XX - 审判"
    id = 20
    positive = 0
    newer = 3
    _description = "若你今天接龙次数小于5，则扣除20击毙，若你今天接龙次数大于20，则获得20击毙。"
    pack = Pack.tarot
    async def Use(self, user: 'User') -> None:
        """审判。
        flag: 为'"-"时代表扣除20击毙，为"+"时表示获得20击毙，为"0"时表示不加不减。"""
        n = [tree.qq for tree in itertools.chain(*itertools.chain(user.game.treeObjs, *user.game.treeForests))].count(user.qq)
        if n < 5:
            user.SendCardUse(self, flag = '-')
            await user.AddJibi(-20)
        elif n > 20:
            user.SendCardUse(self, flag = '+')
            await user.AddJibi(20)
        else:
            user.SendCardUse(self, flag = '0')

class SWorld21(Status):
    id = 21
    name = "XXI - 世界"
    _description = "除大病一场外，所有“直到跨日为止”的效果延长至明天。"
    isGlobal = True

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
        '''因病了不能接龙。'''
        user.SendStatusEffect(self)
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

class CWenhuaZixin(Card):
    name = "文化自信"
    id = 32
    positive = 0
    _description = "清除所有全局状态的75%，最多五个。"
    pack = Pack.zhu
    async def Use(self, user: 'User') -> None:
        '''移除全局状态
        rstatus：每一步被移除的状态'''
        statuses = list(itertools.chain(*(([c.__class__()] * c.count if c.isNull else [c]) for c in user.ume.data.statuses if c.isRemovable)))
        if len(statuses) == 0:
            return
        num = min(ceil(len(statuses) * 0.75), 5)
        l: list[Status] = []
        for i in range(num):
            c = random.choice(statuses)
            l.append(c)
            statuses.remove(c)
        for d in l:
            user.SendCardUse(self, rstatus = d.DumpData())
            await user.ume.RemoveStatus(d, remover = user)

class CLebusishu35(Card):#TODO
    id = 35
    name = "乐不思蜀"
    positive = -1
    _description = "抽到时为你附加buff：今天每次接龙时，你进行一次判定。有3/4的几率你不得从该节点接龙。"
    pack = Pack.sanguosha
    consumedOnDraw = True
    async def OnDraw(self, user: 'User') -> None:
        await user.AddStatus(SLebusishu35())
class SLebusishu35(StatusDailyStack):
    id = 35
    name = "乐不思蜀"
    isDebuff = True
    _description = '今天每次接龙时，你进行一次判定。有3/4的几率你不得从该节点接龙。'
class SInvLebusishu(StatusDailyStack):
    id = 36
    name = "反转·乐不思蜀"
    isDebuff = True
    _description = '今天每次接龙时，你进行一次判定。有1/4的几率你不得从该节点接龙。'
class ILeChecker(IEventListener):
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnDragoned: Priority.OnDragoned.lecheck}

class CWuzhongshengyou36(Card):
    name = "无中生有"
    id = 36
    positive = 1
    _description = "摸两张牌。"
    pack = Pack.sanguosha
    async def Use(self, user: 'User') -> None:
        await user.Draw(2)

class CJuedou37(Card):
    id = 37
    name = "决斗"
    positive = 0
    _description = "指定一名玩家，下10次接龙为你与祂之间进行（持续1小时后过期）。"
    pack = Pack.sanguosha
    async def Use(self, user: 'User') -> None:
        """决斗
        choose: True时为选择玩家提示。
        ruser: 被选中的玩家。"""
        user.SendCardUse(choose=True)
        if (players := await user.ChoosePlayers(1, 1)) is not None:
            player = players[0]
            if user.ume.CheckStatus(SJuedou37) is not None:
                await user.ume.RemoveAllStatus(SJuedou37)
            user.SendCardUse(self, choose=False, ruser = player)
            await user.ume.AddStatus(SJuedou37(timedelta(hour=1), user.qq, player, 10))
class SJuedou37(StatusTimed):
    id = 37
    name = "决斗"
    isGlobal = True
    dataType: Tuple[Callable[[str], Any],...] = (datetime.fromisoformat, int, int, int)
    def __init__(self, data: datetime | timedelta, player1: int, player2: int, count: int):
        self.player1 = player1
        self.player2 = player2
        self.count = count
        super().__init__(data)
    @property
    def valid(self):
        return self.time >= datetime.now() and self.count > 0
    def packData(self) -> str:
        return ','.join((self.time.isoformat(), str(self.player1), str(self.player2), str(self.count)))
    @property
    def description(self):
        return f"决斗：接下来的{self.count}次接龙由玩家{self.player1}与{self.player2}之间进行。\n\t结束时间：{self.getStr()}。"
    async def BeforeDragoned(self, user: 'User', state: 'DragonState') -> Tuple[bool, int]:
        """不可干扰决斗。"""
        if user.qq == self.player1 or user.qq == self.player2:
            return True, -100
        else:
            user.SendStatusEffect(self, time = 'BeforeDragoned')
            return False, 0
    async def OnDragoned(self, user: 'User', branch: 'Tree', first10: bool) -> None:
        self.count -= 1
        user.ume.data.SaveStatuses()
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.BeforeDragoned: Priority.BeforeDragoned.juedou,
            UserEvt.OnDragoned: Priority.OnDragoned.juedou}

class CTiesuolianhuan39(Card):
    name = "铁索连环"
    id = 38
    positive = 1
    _description = "指定至多两名玩家进入或解除其连环状态。任何处于连环状态的玩家被击毙时所有连环状态的玩家也被击毙并失去此效果。"
    isMetallic = True
    pack = Pack.sanguosha
    async def Use(self, user: 'User') -> None:
        """铁索连环。
        choose: True时为选择玩家提示。
        tplayer: 被连环的玩家qq列表。"""
        user.SendCardUse(self, choose=True)
        if players := user.ChoosePlayers(1, 2) is not None:
            user.SendCardUse(self, choose=False, tplayer = players)
            for target in players:
                atk = ATiesuolianhuan38(user, u := user.CreateUser(target))
                atk.counter.isAOE = (len(players) > 1)
                await u.Attacked(atk)
class ATiesuolianhuan38(Attack):
    name = "铁索连环"
    doublable = False
    async def selfAction(self):
        if self.defender.CheckStatus(STiesuolianhuan38) is not None:
            # TODO SendAttack
            await self.defender.RemoveAllStatus(STiesuolianhuan38, remover=self.attacker)
        else:
            await self.defender.AddStatus(STiesuolianhuan38())
class STiesuolianhuan38(StatusNullStack):
    name = "铁索连环"
    id = 38
    _description = "指定至多两名玩家进入或解除其连环状态。任何处于连环状态的玩家被击毙时所有连环状态的玩家也被击毙并失去此效果。"
    isMetallic = True
    isDebuff = True
    async def OnDeath(self, user: 'User', killer: Optional['User'], time: int, c: 'AttackType') -> Tuple[int, bool]:
        '''连坐死亡
        rqqs：被连坐的玩家'''
        all_qqs: list[int] = []
        all_users: list[User] = []
        for r in user.game.AllUserQQs():
            if r == user.qq:
                continue
            if (u := user.CreateUser(r)).CheckStatusStack(STiesuolianhuan38) != 0:
                all_qqs.append(r)
                all_users.append(u)
        user.SendStatusEffect(self, tqqs = all_qqs)
        for u in all_users:
            await u.RemoveAllStatus(STiesuolianhuan38)
            await u.Killed(user, minute = time, isAOE = len(all_qqs) > 1)
        return time, False

class CMinus1Ma39(Card):
    name = "-1马"
    id = 39
    positive = 1
    _description = "今天你可以少隔一个接龙，但最少隔一个。"
    mass = 0.75
    pack = Pack.sanguosha
    async def Use(self, user: 'User') -> None:
        await user.AddStatus(SMinus1Ma39())
class SMinus1Ma39(StatusDailyStack):
    name = "-1马"
    id = 39
    _description = "今天你可以少隔一个接龙，但最少隔一个。"
    async def BeforeDragoned(self, user: 'User', state: 'DragonState') -> Tuple[bool, int]:
        return True, -self.count
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.BeforeDragoned: Priority.BeforeDragoned.minus1ma}
class SPlus1Ma36(StatusDailyStack):
    name = "+1马"
    id = 36
    isDebuff = True
    _description = "今天你必须额外隔一个才能接龙。"
    async def BeforeDragoned(self, user: 'User', state: 'DragonState') -> Tuple[bool, int]:
        return True, self.count
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.BeforeDragoned: Priority.BeforeDragoned.plus1ma}

class CSiHuiHuiBiZhiYao50(Card):
    name = "死秽回避之药"
    id = 50
    positive = 1
    _description = "你下次死亡时自动消耗5击毙免除死亡。若击毙不足则不发动。"
    pack = Pack.honglongdong
    async def Use(self, user: 'User') -> None:
        await user.AddStatus(SSiHuiHuiBiZhiYao50())
class SSiHuiHuiBiZhiYao50(StatusNullStack):
    name = "死秽回避之药"
    id = 50
    _description = "你下次死亡时自动消耗5击毙免除死亡。若击毙不足则不发动。"
    async def OnDeath(self, user: 'User', killer: Optional['User'], time: int, c: 'AttackType') -> Tuple[int, bool]:
        """消耗5击毙免除死亡。"""
        if await user.AddJibi(-5, isBuy=True):
            user.SendStatusEffect(self)
            await user.RemoveStatus(SSiHuiHuiBiZhiYao50())
            return time, True
        return time, False
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnDeath: Priority.OnDeath.sihuihuibizhiyao}
class SInvSiHuiHuiBiZhiYao53(StatusNullStack):
    name = "反转·死秽回避之药"
    id = 53
    _description = "你下次死亡时获得5击毙，但是死亡时间增加2h。"
    async def OnDeath(self, user: 'User', killer: Optional['User'], time: int, c: 'AttackType') -> Tuple[int, bool]:
        """获得5击毙，但是死亡时间增加2h。
        count：buff层数"""
        count = self.count
        user.SendStatusEffect(self, count = count)
        await user.AddJibi(5 * count)
        await user.RemoveAllStatus(SInvSiHuiHuiBiZhiYao53)
        return time + 120 * count, False
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnDeath: Priority.OnDeath.inv_sihuihuibizhiyao}

class CHuiYe52(Card):
    name = "辉夜姬的秘密宝箱"
    id = 52
    positive = 1
    _description = "你下一次死亡的时候奖励你抽一张卡。"
    mass = 0.2
    isMetallic = True
    pack = Pack.honglongdong
    async def Use(self, user: 'User') -> None:
        await user.AddStatus(SHuiYe52())
class SHuiYe52(StatusNullStack):
    name = "辉夜姬的秘密宝箱"
    id = 52
    _description = "你下一次死亡的时候奖励你抽一张卡。"
    isMetallic = True
    async def OnDeath(self, user: 'User', killer: Optional['User'], time: int, c: 'AttackType') -> Tuple[int, bool]:
        """因死亡抽卡。
        count：抽卡的张数"""
        count = self.count
        user.SendStatusEffect(self, count = count)
        await user.RemoveAllStatus(SHuiYe52)
        await user.Draw(count)
        return time, False
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnDeath: Priority.OnDeath.huiye}
class SInvHuiYe54(StatusNullStack):
    name = "反转·辉夜姬的秘密宝箱"
    id = 54
    _description = "你下一次死亡的时候随机弃一张牌。"
    isDebuff = True
    isMetallic = True
    async def OnDeath(self, user: 'User', killer: Optional['User'], time: int, c: 'AttackType') -> Tuple[int, bool]:
        '''随机弃一张牌。
        cards：因为此状态需要弃掉的卡牌。'''
        count = self.count
        await user.RemoveAllStatus(SInvHuiYe54)
        x = min(len(user.data.handCard), count)
        l = copy(user.data.handCard)
        l2: List[Card] = []
        for i in range(x):
            l2.append(random.choice(l))
            l.remove(l2[-1])
        user.SendStatusEffect(self, cards = [c.DumpData() for c in l2])
        await user.DiscardCards(l2)
        return time, False
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnDeath: Priority.OnDeath.inv_huiye}

class CBlank53(Card):
    name = "空白卡牌"
    id = 53
    positive = -1
    _description = "使用时弃置随机5张手牌。此牌不可因手牌超出上限而被弃置。"
    pack = Pack.honglongdong
    async def Use(self, user: 'User') -> None:
        '''弃置随机5张手牌。
        cards：因为此状态需要弃掉的卡牌'''
        if len(user.data.handCard) <= 5:
            user.SendCardUse(self, cards = copy(user.data.handCard))
            await user.DiscardCards(copy(user.data.handCard))
        else:
            l = copy(user.data.handCard)
            l2: List[Card] = []
            for j in range(5):
                l2.append(random.choice(l))
                l.remove(l2[-1])
            user.SendCardUse(self, cards = [c.DumpData() for c in l2])
            await user.DiscardCards(l2)

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

class CBaoshideWugong56(Card):
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
        """摸两张牌。
        count：摸两张牌的次数"""
        user.SendStatusEffect(self, count=self.count)
        await user.ume.RemoveStatus(self)
        cards = list(itertools.chain(*[[user.game.RandomNewCards(user, requirement=positive({-1, 0}))[0], user.game.RandomNewCards(user, requirement=positive({0, 1}))[0]] for i in range(self.count)]))
        await user.Draw(0, cards=cards)
    def register(self) -> Dict['UserEvt', int]:
        return {UserEvt.OnDragoned: Priority.OnDragoned.plus2}

class CDream62(Card):
    name = "这一切都是主角做的一场梦"
    id = 62
    positive = 0
    _description = "50%概率回溯到随机一个节点，50%概率随机一个节点立即分叉。"
    mass = 0
    pack = Pack.once_upon_a_time
    async def Use(self, user: 'User') -> None:
        node = random.choice(list(itertools.chain(*user.game.treeObjs)))
        c = random.random()
        if c < 0.5 + 0.02 * user.data.luck:
            if_luck = c > 0.5
            if node.left is not None:
                user.game.RemoveTree(node.left)
            if node.right is not None:
                user.game.RemoveTree(node.right)
        else:
            user.game.ForkTree(node, True)

class CHezuowujian63(Card):
    name = "合作无间"
    id = 63
    positive = 1
    _description = "拆除所有雷，每个雷有70%的概率被拆除。"
    pack = Pack.explodes
    async def Use(self, user: 'User') -> None:
        """拆除了所有雷。"""
        user.SendCardUse(self)
        await user.game.RemoveAllBomb(0.7)

class COuroStone66(Card):
    name = "衔尾蛇之石"
    id = 66
    positive = 0
    _description = "修改当前规则至首尾接龙直至跨日。"
    mass = 0.2
    pack = Pack.stone_story
    async def Use(self, user: 'User') -> None:
        if user.ume.CheckStatus(SOuroStone66) is not None:
            user.ume.RemoveAllStatus(SOuroStone66)
        if user.ume.CheckStatus(SInvOuroStone63) is not None:
            user.ume.RemoveAllStatus(SInvOuroStone63)
        await user.ume.AddStatus(SOuroStone66())
class SOuroStone66(StatusDailyStack):
    name = "衔尾蛇之石"
    id = 66
    _description = "规则为首尾接龙直至跨日。"
    isGlobal = True
    async def BeforeDragoned(self, user: 'User', state: 'DragonState') -> Tuple[bool, int]:
        """需首尾接龙。"""
        if not await state.RequireShouwei(user):
            user.SendStatusEffect(self)
            return False, 0
        return True, 0
    def register(self) -> Dict['UserEvt', int]:
        return {UserEvt.BeforeDragoned: Priority.BeforeDragoned.ourostone}
class SInvOuroStone63(StatusDailyStack):
    name = "石之蛇尾衔"
    id = 63
    _description = "规则为尾首接龙直至跨日。"
    isGlobal = True
    async def BeforeDragoned(self, user: 'User', state: 'DragonState') -> Tuple[bool, int]:
        """需尾首接龙。"""
        if not await state.RequireWeishou(user):
            user.SendStatusEffect(self)
            return False, 0
        return True, 0
    def register(self) -> Dict['UserEvt', int]:
        return {UserEvt.BeforeDragoned: Priority.BeforeDragoned.ourostone}

class queststone(Card):
    name = "任务之石"
    id = 67
    positive = 1
    _description = "持有此石时，你每天会刷新一个接龙任务。每次完成接龙任务可以获得3击毙，每天最多3次。使用将丢弃此石。"
    desNeedInit = True
    mass = 0.2
    pack = Pack.stone_story
#     @classmethod TODO
#     def quest_des(cls, qq: int):
#         r = Game.userdata(qq).quest_c
#         m = mission[r['id']][1]
#         remain = r['remain']
#         return "\t当前任务：" + m + f"剩余{remain}次。"
#     @classmethod
#     def full_description(cls, qq: int):
#         return super().full_description(qq) + "\n" + cls.quest_des(qq)
#     @classmethod
#     async def on_draw(cls, user: User):
#         user.data.quests.append({'id': (i := get_mission()), 'remain': 3})
#         config.logger.dragon << f"【LOG】用户{user.qq}刷新了一个任务{mission[i][1]}，现有任务：{[mission[c['id']][1] for c in user.data.quests]}。"
#         save_global_state()
#     @classmethod
#     async def on_remove(cls, user: User):
#         r = user.data.pop_quest()
#         config.logger.dragon << f"【LOG】用户{user.qq}删除了一个任务{mission[r['id']][1]}，现有任务：{[mission[c['id']][1] for c in user.data.quests]}。"
#         save_global_state()
#     @classmethod
#     async def on_give(cls, user: User, target: User):
#         r = user.data.pop_quest()
#         config.logger.dragon << f"【LOG】用户{user.qq}删除了一个任务{mission[r['id']][1]}，现有任务：{[mission[c['id']][1] for c in user.data.quests]}。"
#         target.data.quests.append(r)
#         config.logger.dragon << f"【LOG】用户{target.qq}增加了一个任务{mission[r['id']][1]}，现有任务：{[mission[c['id']][1] for c in target.data.quests]}。"
#         save_global_state()
#     @classmethod
#     async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
#         for m in user.data.quests:
#             if m['remain'] > 0:
#                 id, name, func = mission[m['id']]
#                 if func(branch.word):
#                     user.send_char(f"完成了任务：{name[:-1]}{句尾}奖励3击毙。此任务还可完成{m['remain'] - 1}次。")
#                     user.log << f"完成了一次任务{name}，剩余{m['remain'] - 1}次。"
#                     m['remain'] -= 1
#                     await user.add_jibi(3)
#                     save_global_state()
#     @classmethod
#     def register(cls) -> dict[int, TEvent]:
#         return {UserEvt.OnDragoned: (Priority.OnDragoned.queststone, cls)}

class CCunqianguan70(Card):
    name = "存钱罐"
    id = 70
    positive = 1
    _description = "下次触发隐藏词的奖励+10击毙。"
    isMetallic = True
    mass = 0.25
    pack = Pack.orange_juice
    async def Use(self, user: 'User') -> None:
        await user.ume.AddStatus(SCunqianguan70())
class SCunqianguan70(StatusNullStack):
    name = "存钱罐"
    id = 70
    _description = "下次触发隐藏词的奖励+10击毙。"
    isMetallic = True
    isGlobal = True
    async def OnHiddenKeyword(self, user: 'User', word: str, parent: 'Tree', keyword: str) -> int:
        """存钱罐，奖励+10击毙。
        count：触发次数。"""
        user.SendStatusEffect(self, count = self.count)
        await user.ume.RemoveAllStatus(self)
        return self.count * 10
    def register(self) -> Dict['UserEvt', int]:
        return {UserEvt.OnHiddenKeyword: Priority.OnHiddenKeyword.cunqianguan}
class SInvCunqianguan72(StatusNullStack):
    id = 72
    name = "反转·存钱罐"
    _description = "下次触发隐藏词的奖励-10击毙。"
    isMetallic = True
    isGlobal = True
    isDebuff = True
    async def OnHiddenKeyword(self, user: 'User', word: str, parent: 'Tree', keyword: str) -> int:
        """反转存钱罐，奖励-10击毙。
        count：触发次数。"""
        user.SendStatusEffect(self, count = self.count)
        await user.ume.RemoveAllStatus(self)
        return -self.count * 10,
    def register(self) -> Dict['UserEvt', int]:
        return {UserEvt.OnHiddenKeyword: Priority.OnHiddenKeyword.inv_cunqianguan}

class CHongsezhihuan71(Card):
    name = "虹色之环"
    id = 71
    positive = 0
    _description = "下次你死亡时，有1/2几率闪避，1/2几率死亡时间+1小时。"
    pack = Pack.orange_juice
    async def Use(self, user: 'User') -> None:
        await user.AddStatus(SHongsezhihuan71())
class SHongsezhihuan71(StatusNullStack):
    id = 71
    name = "虹色之环"
    _description = '下次死亡时，有1/2几率闪避，1/2几率死亡时间+1小时。'
    async def OnDeath(self, user: 'User', killer: Optional['User'], time: int, c: 'AttackType') -> Tuple[int, bool]:
        """闪避死亡。
        success: 闪避是否成功。
        lucky: 是否因幸运加成。"""
        for a in range(self.count):
            await user.RemoveStatus(SHongsezhihuan71(1))
            if (c := random.random()) < 0.5 + 0.02 * user.data.luck:
                lucky = False
                if c > 0.5:
                    lucky = True
                user.SendStatusEffect(self, success = True, lucky = lucky)
                return time, True
            else:
                time += 60
                user.SendStatusEffect(self, success = False)
        return time, False
    def register(self) -> Dict['UserEvt', int]:
        return {UserEvt.OnDeath: Priority.OnDeath.hongsezhihuan}

# class liwujiaohuan(_card): TODO
#     name = "礼物交换"
#     id = 72
#     positive = 1
#     description = "最近接过龙的玩家每人抽出一张手牌集合在一起随机分配。"
#     pack = Pack.orange_juice
#     @classmethod
#     async def use(cls, user: User):
#         user.data.set_cards()
#         config.logger.dragon << f"【LOG】用户{user.qq}交换了最近接过龙的玩家的手牌。"
#         qqs = set(tree.qq for tree in itertools.chain(*itertools.chain(Tree._objs, *Tree.forests)))
#         from .logic_dragon import get_yesterday_qq
#         qqs |= get_yesterday_qq()
#         l = [User(qq, user.buf) for qq in qqs if qq != 0]
#         config.logger.dragon << f"【LOG】这些人的手牌为：{','.join(f'{user.qq}: {cards_to_str(user.data.hand_card)}' for user in l)}。"
#         all_users: List[User] = []
#         all_cards: List[Tuple[User, TCard]] = []
#         for u in l:
#             if len(u.data.hand_card) != 0:
#                 atk = ALiwujiaohuan(user, u, all_users)
#                 await u.attacked(user, atk)
#         config.logger.dragon << f"【LOG】所有参与交换的人为{[c.qq for c in all_users]}。"
#         for u in all_users:
#             c = random.choice(u.data.hand_card)
#             config.logger.dragon << f"【LOG】用户{u.qq}取出了手牌{c.name}。"
#             all_cards.append((u, c))
#         random.shuffle(all_cards)
#         lose = get = None
#         for u, (u2, c) in zip(all_users, all_cards):
#             u.data.hand_card.append(c)
#             u2.data.hand_card.remove(c)
#             await c.on_give(u2, u)
#             config.logger.dragon << f"【LOG】{u.qq}从{u2.qq}处收到了{c}。"
#             if u == user:
#                 get = c
#             elif u2 == user:
#                 lose = c
#         for u in all_users:
#             u.data.set_cards()
#         if lose is None and get is None:
#             user.buf.send(f"你交换了大家的手牌{句尾}")
#         else:
#             user.buf.send(f"你用一张：\n{lose}\n换到了一张：\n{get}")
class ALiwuJiaohuan72(Attack):
    name = "礼物交换"
    doublable = False
    # def __init__(self, attacker: 'User', defender: 'User', todo_list: List):
    #     self.todo_list = todo_list
    #     super().__init__(attacker, defender)
    # def rebound(self) -> bool:
    #     return True
    # async def self_action(self):
    #     self.todo_list.append(self.defender)

class CLuckyCharm73(Card):
    name = "幸运护符"
    id = 73
    # hold_des = '幸运护符：每天只能使用一张其他卡牌，你的幸运值+1。'
    positive = 1
    _description = "持有此卡时，每天只能使用一张其他卡牌，你的幸运值+1。使用将丢弃这张卡。"
    pack = Pack.orange_juice
    async def OnUserUseCard(self, user: 'User', card: 'Card') -> tuple[bool, bool]:
        """今天幸运护符的使用卡牌次数已完。"""
        if not isinstance(card, CLuckyCharm73):
            user.SendCardEffect(self)
            await user.AddStatus(SLuckyCharm73())
        return True, False
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnUserUseCard: Priority.OnUserUseCard.xingyunhufu}
class SLuckyCharm73(StatusDailyStack):
    id = 73
    name = "幸运护符次数已用完："
    _description = "今天你不能使用除幸运护符以外的卡牌。"
    isDebuff = True
    async def OnUserUseCard(self, user: 'User', card: 'Card') -> tuple[bool, bool]:
        """不能使用除幸运护符以外的卡牌。"""
        if any(isinstance(c, CLuckyCharm73) for c in user.data.handCard) and not isinstance(card, CLuckyCharm73):
            user.SendStatusEffect(self)
            return False, False
        return True, False
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnUserUseCard: Priority.OnUserUseCard.xingyunhufus}

class CJiSuZhuangZhi74(Card):
    name = "极速装置"
    id = 74
    positive = 1
    _description = '你下次你可以连续接龙两次。'
    pack = Pack.orange_juice
    async def Use(self, user: 'User') -> None:
        await user.AddStatus(SJiSuZhuangZhi74())
class SJiSuZhuangZhi74(StatusNullStack):
    id = 74
    name = "极速装置"
    _description = "你下次可以连续接龙两次。"
    async def CheckSuguri(self, user: 'User', state: 'DragonState') -> bool:
        """使用极速装置。"""
        user.SendStatusEffect(self)
        await user.RemoveStatus(SJiSuZhuangZhi74(1))
        return True
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.CheckSuguri: Priority.CheckSuguri.jisuzhuangzhi}

# class huxiangjiaohuan(_card): TODO
#     name = '互相交换'
#     id = 75
#     positive = 0
#     description = "下一个接中隐藏奖励词的玩家手牌与你互换，手牌量变化最多为2。"
#     pack = Pack.orange_juice
#     @classmethod
#     async def use(cls, user: User):
#         l = Game.me.check_limited_status('x')
#         if l:
#             l[0] += [user.qq]
#             user.log << f"被加入交换堆栈，现为{l[0].list}。"
#             Game.me.save_status_time()
#         else:
#             await Userme(user).add_limited_status(SHuxiangjiaohuan([user.qq]))
# class SHuxiangjiaohuan(ListStatus):
#     id = 'x'
#     des = "互相交换：下一个接中隐藏奖励词的玩家手牌与某人互换。"
#     def __str__(self):
#         return '\n'.join("互相交换：下一个接中隐藏奖励词的玩家手牌与某人互换。" for i in self.list)
#     @property
#     def brief_des(self):
#         return '\n'.join("互相交换" for i in self.list)
#     is_global = True
#     @classmethod
#     async def OnHiddenKeyword(cls, count: TCount, user: 'User', word: str, parent: 'Tree', keyword: str) -> Tuple[int]:
#         to_exchange = count[0].list.pop()
#         Game.me.save_status_time()
#         u = User(to_exchange, user.buf)
#         atk = AHuxiangjiaohuan(u, user)
#         await user.attacked(u, atk)
#         return 0,
#     @classmethod
#     def register(cls) -> dict[int, TEvent]:
#         return {UserEvt.OnHiddenKeyword: (Priority.OnHiddenKeyword.huxiangjiaohuan, cls)}
# class AHuxiangjiaohuan(Attack):
#     name = "攻击：互相交换"
#     doublable = False
#     async def self_action(self):
#         self.defender.send_char(f"与[CQ:at,qq={self.attacker.qq}]交换了手牌{句尾}")
#         jibi = (self.defender.data.jibi, self.attacker.data.jibi)
#         self.defender.log << f"与{self.attacker.qq}交换了手牌。"
#         await self.defender.exchange(self.attacker, max_sub=2)

class CZhongShenDeXiXi76(Card):
    name = "众神的嬉戏"
    id = 76
    positive = 0
    _description = '抽取一张卡并立即发动其使用效果。'
    pack = Pack.orange_juice
    async def Use(self, user: 'User') -> None:
        await user.DrawAndUse()

# class lveduozhebopu(_card): TODO
#     name = "掠夺者啵噗"
#     id = 77
#     positive = 1
#     hold_des = '掠夺者啵噗：你每天可从所接龙的人处偷取1击毙，每人限一次，最多10击毙，若目标没有击毙则不可偷取。'
#     description = "持有此卡时，你每天你可从你所接龙的人处偷取1击毙，每人限一次，最多10击毙，若目标没有击毙则不可偷取。使用或死亡时将丢弃这张卡。"
#     pack = Pack.orange_juice
#     @classmethod
#     async def on_draw(cls, user: User):
#         user.data.steal
#         save_global_state()
#     @classmethod
#     async def on_remove(cls, user: User):
#         if Card(77) not in user.data.hand_card and str(user.qq) in global_state['steal']:
#             del global_state['steal'][str(user.qq)]
#         save_global_state()
#     @classmethod
#     async def on_give(cls, user: User, target: User):
#         target.data.steal = user.data.steal
#         if Card(77) not in user.data.hand_card and str(user.qq) in global_state['steal']:
#             del global_state['steal'][str(user.qq)]
#         save_global_state()
#     @classmethod
#     async def OnDeath(cls, count: TCount, user: User, killer: User, time: int, c: TAttackType) -> Tuple[int, bool]:
#         user.send_log(f"的{f'{count}张' if count > 1 else ''}掠夺者啵噗被弃了{句尾}")
#         await user.discard_cards([cls] * count)
#         return time, False
#     @classmethod
#     async def OnDragoned(cls, count: TCount, user: User, branch: 'Tree', first10: bool) -> Tuple[()]:
#         global global_state
#         last_qq = branch.parent.qq
#         if branch.parent.id != (0, 0):
#             last = User(last_qq, user.buf)
#             s = user.data.steal
#             if last_qq not in s['user'] and s['time'] < 10:
#                 s['time'] += 1
#                 s['user'].append(last_qq)
#                 save_global_state()
#                 atk = AStealJibi(user, last, count)
#                 await last.attacked(user, atk)
#     @classmethod
#     def register(cls):
#         return {UserEvt.OnDeath: (Priority.OnDeath.lveduozhebopu, cls),
#             UserEvt.OnDragoned: (Priority.OnDragoned.lveduozhebopu, cls)}
# class AStealJibi(Attack):
#     name = "偷击毙"
#     def __init__(self, attacker: 'User', defender: 'User', count: int):
#         self.count = count
#         super().__init__(attacker, defender)
#     async def self_action(self):
#         self.attacker.log << f"触发了{self.count}次掠夺者啵噗的效果，偷取了{self.defender.qq}击毙，剩余偷取次数{(9 - global_state['steal'][str(self.attacker.qq)]['time']) if str(self.attacker.qq) in global_state['steal'] else 'null'}。"
#         if (p := self.defender.data.jibi) > 0:
#             n = self.count * self.multiplier
#             self.attacker.send_char(f"从上一名玩家处偷取了{min(n, p)}击毙{句尾}")
#             await self.defender.add_jibi(-n)
#             await self.attacker.add_jibi(min(n, p))

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
    isGlobal = True
    _description = "今日卡池中有一定概率出现【邪恶的间谍行动~执行】。"
class CJianDieZhiXingN1(Card):
    pass # TODO

class CQiJiManBu79(Card):
    name = "奇迹漫步"
    id = 79
    positive = 1
    _description = "弃置你所有手牌，并摸取等量的非负面牌。"
    pack = Pack.orange_juice
    async def Use(self, user: 'User') -> None:
        n = len(user.data.handCard)                       # what if handCard is None
        await user.DiscardCards(copy(user.data.handCard)) # I think this need to be shallow copy
        await user.Draw(n, requirement=positive({0, 1}))

class CComicSans80(Card):
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

class CPC81(Card):
    name = "PC"
    id = 81
    positive = 1
    _description = '今天接过龙的所有人立刻获得胜利。'
    pack = Pack.playtest
    async def Use(self, user: 'User') -> None:
        """全部胜利。"""
        user.SendCardUse(self)
        qqs = [tree.qq for tree in itertools.chain(*itertools.chain(user.game.treeObjs, *user.game.treeForests))]
        for qq in set(qqs):
            await user.CreateUser(qq).AddStatus(SWin81())
class SWin81(StatusDailyStack):
    id = 81
    name = "胜利"
    _description = "恭喜，今天你赢了。"
class SDefeat82(StatusDailyStack):
    id = 82
    name = "失败"
    _description = "对不起，今天你输了。"
    isDebuff = True

class CSuicideKing90(Card):
    name = "自杀之王（♥K）"
    id = 90
    positive = -1
    _description = "抽到时立即死亡。"
    consumedOnDraw = True
    pack = Pack.poker
    async def OnDraw(self, user: 'User') -> None:
        """死了。"""
        user.SendCardOnDraw(self)
        await user.Death()

class CPig91(Card):
    name = "猪（♠Q）"
    id = 91
    positive = -1
    _description = "抽到时损失20击毙（但不会扣至0以下）。"
    consumedOnDraw = True
    pack = Pack.poker
    async def OnDraw(self, user: 'User') -> None:
        """抽到了猪。"""
        user.SendCardOnDraw(self)
        await user.AddJibi(-20)

class CSheep92(Card):
    name = "羊（♦J）"
    id = 92
    positive = 1
    _description = "抽到时获得20击毙。"
    consumedOnDraw = True
    pack = Pack.poker
    async def OnDraw(self, user: 'User') -> None:
        """抽到了羊。"""
        user.SendCardOnDraw(self)
        await user.AddJibi(20)

class CTransformer93(Card):
    name = "变压器（♣10）"
    id = 93
    positive = 0
    _description = "下一次你的击毙变动变动值加倍。"
    isMetallic = True
    mass = 0.2
    pack = Pack.poker
    async def Use(self, user: 'User') -> None:
        await user.AddStatus(STransformer93())
class STransformer93(StatusNullStack):
    name = "变压器（♣10）"
    id = 93
    _description = "下一次你的击毙变动变动值加倍。"
    isMetallic = True
    async def CheckJibiSpend(self, user: 'User', jibi: int) -> int:
        return jibi * 2 ** self.count
    async def OnJibiChange(self, user: 'User', jibi: int, isBuy: bool) -> int:
        """加倍击毙变化
        count：加倍的次数
        njibi：修正后的击毙变化量"""
        count = self.count
        njibi = jibi * 2 ** count
        user.SendStatusEffect(self, count=count, njibi=njibi)
        await user.RemoveAllStatus(STransformer93)
        return njibi
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.CheckJibiSpend: Priority.CheckJibiSpend.bianyaqi,
            UserEvt.OnJibiChange: Priority.OnJibiChange.bianyaqi}
class SInvTransformer92(StatusNullStack):
    name = "反转·变压器（♣10）"
    id = 92
    _description = "下一次你的击毙变动变动值减半。"
    isMetallic = True
    async def CheckJibiSpend(self, user: 'User', jibi: int) -> int:
        return ceil(jibi / 2 ** self.count)
    async def OnJibiChange(self, user: 'User', jibi: int, isBuy: bool) -> int:
        """减半击毙变化
        count：减半的次数
        njibi：修正后的击毙变化量"""
        count = self.count
        njibi = ceil(jibi / 2 ** count)
        user.SendStatusEffect(self, count=count, njibi=njibi)
        await user.RemoveAllStatus(SInvTransformer92)
        return njibi
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.CheckJibiSpend: Priority.CheckJibiSpend.inv_bianyaqi,
            UserEvt.OnJibiChange: Priority.OnJibiChange.inv_bianyaqi}

class CAdCard94(Card):
    name = "广告牌"
    id = 94
    positive = 0
    consumedOnDraw = True
    pack = Pack.poker
    @property
    def description(self):
        return random.choice([
            "广告位永久招租，联系邮箱：shedarshian@gmail.com",
            "MUASTG，车万原作游戏前沿逆向研究，主要研究弹幕判定、射击火力、ZUN引擎弹幕设计等，曾发表车万顶刊华胥三绝，有意者加群796991184",
            "你想明白生命的意义吗？你想真正……的活着吗？\n\t☑下载战斗天邪鬼：https://pan.baidu.com/s/1FIAxhHIaggld3yRAyFr9FA",
            "欢迎关注甜品站弹幕研究协会，国内一流的东方STG学术交流平台，从避弹，打分到neta，可以学到各种高端姿势：https://www.isndes.com/ms?m=2",
            "[CQ:at,qq=1469335215]哈斯塔快去画逻辑接龙卡图",
            "《世界計畫 繽紛舞台！ feat. 初音未來》正式開啓公測！欢迎下载：www.tw-pjsekai.com",
            "嘉然…嘿嘿🤤…小嘉然…嘿嘿🤤然然带我走吧…🤤",
            "这是一个历经多年开发并且仍在更新的，包罗万象、应有尽有的MC整合包；这是一个让各个模组互相联动融为一体，向独立游戏看齐的MC整合包。加入GTNH，一起跨越科技的巅峰！www.gtnewhorizons.com",
            "真人面对面收割，美女角色在线掉分，发狂玩蛇新天地，尽在 https://arcaea.lowiro.com",
            "[SPAM]真味探寻不止\n只有6种成分，世棒经典午餐肉就是这么简单！肉嫩多汁、肉香四溢，猪肉含量>90%！源自1937年的美国，快来尝试吧！",
        ])

class CEmptyCard95(Card):
    name = "白牌"
    id = 95
    positive = 1
    _description = "选择你手牌中的一张牌，执行其使用效果。"
    pack = Pack.poker
    def CanUse(self, user: 'User', copy: bool) -> bool:
        return len(c for c in user.data.handCard if c.id not in (95,)) >= (1 if copy else 2)
    async def Use(self, user: 'User') -> None:
        """使用卡牌效果
        choose: True时为选择牌的提示。False时为使用卡牌效果。
        card：被使用效果的卡牌"""
        user.SendCardUse(self, choose=True)
        l = await user.ChooseHandCards(1, 1,
                requirement=lambda c: c.id not in (95,),
                requireCanUse=True)
        card = l[0]
        user.SendCardUse(self, choose=False, card=card)
        await user.UseCardEffect(card)

class CJiaodai100(Card):
    name = "布莱恩科技航空专用强化胶带FAL84型"
    id = 100
    positive = 1
    _description = "取消掉你身上的至多6种可取消的负面状态，并免疫下次即刻生效的负面状态。"
    pack = Pack.gregtech
    @staticmethod
    def _weight(user: User):
        if user.data.luck == 0:
            return 1
        count = sum(1 for c in user.data.statuses if c.isDebuff and c.isRemovable)
        return 1 + user.data.luck / 5 * min(count, 6)
    weight = _weight
    async def Use(self, user: 'User') -> None:
        '''消除负面状态
        rstatus: 消除的状态。'''
        has = 6
        for c in user.data.statuses:
            if has <= 0:
                break
            if not c.isDebuff or not c.isRemovable:
                continue
            if has >= c.count:
                has -= c.count
                user.SendCardUse(self, rstatus=c.DumpData())
                await user.RemoveStatus(c, remover=user)
            elif has < c.count:
                await user.RemoveStatus(s := type(c)(has), remover=user)
                user.SendCardUse(self, rstatus=s.DumpData())
                has = 0
        await user.AddStatus(SJiaodai100())
class SJiaodai100(StatusNullStack):
    name = "布莱恩科技航空专用强化胶带FAL84型"
    id = 100
    _description = "免疫下次即刻生效的负面状态。"
    async def OnStatusAdd(self, user: 'User', status: 'Status') -> bool:
        if status.isDebuff and status.isRemovable:
            '''免除负面状态
            flag：是否防止了全部的负面状态。all：是全部；part：是部分。
            rstatus: 所防止的负面状态。'''
            if self.count >= status.count:
                user.SendStatusEffect(self, flag = 'all', rstatus=status.DumpData())
                await user.RemoveStatus(SJiaodai100(status.count))
                return True
            else:
                status.num -= self.count # type: ignore[attr-defined]
                user.SendStatusEffect(self, flag = 'part', rstatus=type(status)(self.count))
                await user.RemoveAllStatus(SJiaodai100)
        return False
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnStatusAdd: Priority.OnStatusAdd.jiaodai}
class SInvJiaodai90(StatusNullStack):
    name = "反转·布莱恩科技航空专用强化胶带FAL84型"
    id = 90
    _description = "免疫你下次即刻生效的非负面状态。"
    async def OnStatusAdd(self, user: 'User', status: 'Status') -> bool:
        if not status.isDebuff and status.isRemovable:
            '''免除非负面状态
            flag：是否防止了全部的非负面状态。all：是全部；part：是部分。
            rstatus: 所防止的负面状态。'''
            if self.count >= status.count:
                user.SendStatusEffect(self, flag = 'all', rstatus=status.DumpData())
                await user.RemoveStatus(SInvJiaodai90(status.count))
                return True
            else:
                status.num -= self.count # type: ignore[attr-defined]
                user.SendStatusEffect(self, flag = 'part', rstatus=type(status)(self.count))
                await user.RemoveAllStatus(SInvJiaodai90)
        return False
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnStatusAdd: Priority.OnStatusAdd.inv_jiaodai}

class CZPM101(Card):
    name = "Zero-Point Module"
    id = 101
    positive = 1
    _description = "抽到时附加buff：若你当前击毙少于100，则每次接龙为你额外提供1击毙，若你当前击毙多于100，此buff立即消失。"
    consumedOnDraw = True
    isMetallic = True
    pack = Pack.gregtech
    async def OnDraw(self, user: 'User') -> None:
        await user.AddStatus(SZPM101())
class SZPM101(StatusNullStack):
    id = 101
    name = "零点模块"
    _description = "若你当前击毙不多于100，则每次接龙为你额外提供1击毙，若你当前击毙多于100，此buff立即消失。"
    isMetallic = True
    async def OnDragoned(self, user: 'User', branch: 'Tree', first10: bool) -> None:
        """接龙为你提供1击毙。"""
        user.SendStatusEffect(self, time='OnDragoned')
        await user.AddJibi(1)
    async def AfterJibiChange(self, user: 'User', jibi: int) -> None:
        """当前击毙多于100，buff消失。"""
        if user.data.jibi > 100:
            user.SendStatusEffect(self, time='AfterJibiChange')
            await user.RemoveAllStatus(SZPM101)
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnDragoned: Priority.OnDragoned.zpm,
            UserEvt.AfterJibiChange: Priority.AfterJibiChange.zpm}

class CMcGuffin239102(Card):
    name = "Mc Guffium 239"
    id = 102
    positive = 1
    _description = "下一次同时对多人生效的攻击效果不对你生效。"
    pack = Pack.gregtech
    async def Use(self, user: 'User') -> None:
        await user.AddStatus(SMcGuffin239102())
class SMcGuffin239102(StatusNullStack):
    name = "Mc Guffium 239"
    id = 102
    _description = "下一次同时对多人生效的攻击效果不对你生效。"
    async def OnAttacked(self, user: 'User', attack: 'Attack') -> bool:
        """此攻击同时对多人生效，无效此攻击。"""
        if attack.counter.isAOE:
            user.SendStatusEffect(self)
            await user.RemoveStatus(SMcGuffin239102())
            return True
        return False
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnAttacked: Priority.OnAttacked.McGuffium239}

class CJuJiFaShu105(Card):
    name = "聚集法术"
    id = 105
    positive = 1
    _description = "将两张手牌的id相加变为新的手牌。若这两牌id之和不是已有卡牌的id，则变为【邪恶的间谍行动～执行】。"
    # failure_message = "你的手牌不足，无法使用" + 句尾
    pack = Pack.cultist
    def CanUse(self, user: 'User', copy: bool) -> bool:
        return len(user.data.handCard) >= (2 if copy else 3)
    async def Use(self, user: 'User') -> None:
        """将两张手牌聚集。
        choose: True时为选择卡牌提示。
        id: 聚集结果的id。
        available：是否能找到对应id号的卡牌。"""
        user.SendCardUse(self, choose=True)
        l = await user.ChooseHandCards(2, 2)
        await user.RemoveCards([l[0], l[1]])
        id_new = l[0].id + l[1].id
        if id_new not in Card.idDict:
            user.SendCardUse(self, choose=False, id = id_new, available = False)
            id_new = -1
        else:
            user.SendCardUse(self, choose=False, id = id_new, available = True)
        await user.Draw(0, cards=[Card.get(id_new)()])

class CLieBianFaShu106(Card):
    name = "裂变法术"
    id = 106
    positive = 1
    _description = "将一张手牌变为两张随机牌，这两张牌的id之和为之前的卡牌的id。若不存在这样的组合，则变为两张【邪恶的间谍行动～执行】。"
    # failure_message = "你的手牌不足，无法使用" + 句尾
    pack = Pack.cultist
    def CanUse(self, user: 'User', copy: bool) -> bool:
        return len(user.data.handCard) >= (1 if copy else 2)
    async def Use(self, user: 'User') -> None:
        """将一张手牌分解。
        choose: True时为选择卡牌提示。
        available：是否能找到对应id的卡牌。
        ids: 分解结果的id列表。"""
        user.SendCardUse(self, choose=True)
        l = await user.ChooseHandCards(1, 1)
        await user.RemoveCards([l[0]])
        l2 = [(id, l[0].id - id) for id in Card.idDict if l[0].id - id in Card.idDict]
        if len(l2) == 0:
            user.SendCardUse(self, choose=False, available = False)
            id_new = (-1, -1)
        else:
            id_new = random.choice(l2)
            user.SendCardUse(self, choose=False, available = True, ids = list(id_new))
        await user.Draw(0, cards=[Card.get(id_new[0])(), Card.get(id_new[1])()])

class CJingXingFaShu107(Card):
    name = "警醒法术"
    id = 107
    positive = 1
    _description = "揭示至多三个雷。"
    pack = Pack.cultist
    async def Use(self, user: 'User') -> None:
        """揭示雷。
        bombs: 所揭示的雷列表。"""
        k = min(len(user.game.bombs), 3)
        l = []
        for i in range(k):
            l.append(random.choice(user.game.bombs))
            while l[-1] in l[:-1]:
                l[-1] = random.choice(user.game.bombs)
        user.SendCardUse(self, bombs = l)

class CXiaoHunFaShu108(Card):
    name = "销魂法术"
    id = 108
    positive = 1
    _description = "对指定玩家发动，该玩家的每条可清除状态都有1/2的概率被清除；或是发送qq=2711644761对千春使用，消除【XXI-世界】外50%的全局状态，最多5个。"
    pack = Pack.cultist
    async def Use(self, user: 'User') -> None:
        """发动效果。
        choose: True时为选择玩家提示。
        chiharu: 是否选择的是千春。"""
        user.SendCardUse(self, choose=True)
        if (players := await user.ChoosePlayers(1, 1)) is not None:
            player = players[0]
            if player == user.game.managerQQ:#TODO
                user.SendCardUse(self, choose=False, chiharu=True)
                l = list(itertools.chain(*[[type(status)()] * status.count if status.isNull else [status] for status in user.game.me.statuses if status.isRemovable and not isinstance(status, SWorld21)]))
                num = min(ceil(len(l) * 0.5), 5)
                l3: list[Status] = []
                for i in range(num):
                    j = random.choice(l)
                    l3.append(j)
                    l.remove(j)
                ume = user.ume
                for status in l3:
                    await ume.RemoveStatus(status, remover=user)
            else:
                user.SendCardUse(self, choose=False, chiharu=False)
                atk = AXiaoHunFaShu108(user, u := user.CreateUser(player))
                await u.Attacked(atk)
class AXiaoHunFaShu108(Attack):
    id = 108
    name = "销魂法术"
    doublable = False
    async def selfAction(self):
        to_remove: list[Status] = []
        for status in self.defender.data.statuses:
            if not status.isRemovable:
                continue
            if status.isNull:
                n = sum(1 for i in range(status.count) if random.random() > 0.5 ** self.multiplier)
                to_remove.append(type(status)(n))
            else:
                if random.random() > 0.5 ** self.multiplier:
                    to_remove.append(status)
        for status in to_remove:
            await self.defender.RemoveStatus(status, remover=self.attacker)

class CRanSheFaShu109(Card):
    name = "蚺虵法术"
    id = 109
    positive = 1
    _description = "对指定玩家发动，该玩家当日每次接龙需额外遵循首尾接龙规则。"
    pack = Pack.cultist
    async def Use(self, user: 'User') -> None:
        """选择玩家。"""
        user.SendCardUse(self)
        if (players := await user.ChoosePlayers(1, 1)) is not None:
            target = user.CreateUser(players[0])
            atk = ARanSheFaShu109(user, target)
            await target.Attacked(user, atk)
class ARanSheFaShu109(Attack):
    id = 109
    name = "蚺虵法术"
    doublable = False
    async def selfAction(self):
        await self.defender.AddStatus(SRanSheFaShu109())
class SRanSheFaShu109(StatusDailyStack):
    id = 109
    name = "蚺虵法术"
    _description = "你当日每次接龙需额外遵循首尾接龙规则。"
    async def BeforeDragoned(self, user: 'User', state: 'DragonState') -> Tuple[bool, int]:
        """需首尾接龙。"""
        if not await state.RequireShouwei(user):
            user.SendStatusEffect(self)
            return False, 0
        return True, 0
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.BeforeDragoned: Priority.BeforeDragoned.ranshefashu}
class SInvRanSheFaShu108(StatusDailyStack):
    id = 108
    name = "反转·蚺虵法术"
    _description = "你当日每次接龙需额外遵循尾首接龙规则。"
    async def BeforeDragoned(self, user: 'User', state: 'DragonState') -> Tuple[bool, int]:
        """需尾首接龙。"""
        if not await state.RequireWeishou(user):
            user.SendStatusEffect(self)
            return False, 0
        return True, 0
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.BeforeDragoned: Priority.BeforeDragoned.inv_ranshefashu}

class CNightbloom110(Card):
    name = "月下彼岸花"
    id = 110
    positive = -1
    _description = "抽到时附加buff：你每接龙三次会损失1击毙，效果发动20次消失。"
    consumedOnDraw = True
    pack = Pack.ff14
    async def OnDraw(self, user: 'User') -> None:
        await user.AddStatus(SNightbloom110(60))
class SNightbloom110(StatusNumed):
    name = "月下彼岸花"
    id = 110
    isDebuff = True
    _description = "你每接龙三次会损失1击毙"
    @property
    def description(self):
        return f"{self._description}\n\t剩余{(self.num + 2) // 3}次。" # pylint: disable=no-member
    async def OnDragoned(self, user: 'User', branch: 'Tree', first10: bool) -> None:
        """扣除击毙。"""
        self.num -= 1 # pylint: disable=no-member
        if self.num % 3 == 0: # pylint: disable=no-member
            user.SendStatusEffect(self)
            await user.AddJibi(-1)
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnDragoned: Priority.OnDragoned.bianhua}
class SInvNightbloom105(StatusNumed):
    name = "反转·月下彼岸花"
    id = 105
    _description = "你每接龙三次会获得1击毙。"
    @property
    def description(self):
        return f"{self._description}\n\t剩余{(self.num + 2) // 3}次。" # pylint: disable=no-member
    async def OnDragoned(self, user: 'User', branch: 'Tree', first10: bool) -> None:
        """奖励击毙。"""
        self.num -= 1 # pylint: disable=no-member
        if self.num % 3 == 0: # pylint: disable=no-member
            user.SendStatusEffect(self)
            await user.AddJibi(1)
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnDragoned: Priority.OnDragoned.inv_bianhua}

class CPanjueA111(Card):
    name = "最终判决α"
    id = 111
    _description = "抽到时附加buff：最终判决α。你接龙后，将此buff传递给你接龙后第五次接龙的玩家。与最终判决β重合时，罪行加重，判处死刑。"
    positive = -1
    consumedOnDraw = True
    pack = Pack.ff14
    async def OnDraw(self, user: 'User') -> None:
        await user.AddStatus(SPanjueA111())
class SPanjueA111(StatusNullStack):
    name = "最终判决α"
    id = 111
    _description = "你下次接龙后，将此buff传递给你接龙后第五次接龙的玩家。与最终判决β重合时，罪行加重，判处死刑。"
    isDebuff = True
    async def OnStatusAdd(self, user: 'User', status: 'Status') -> bool:
        """判决重合，无法战斗。"""
        if isinstance(status, SPanjueB112) or isinstance(status, SPanjueBActivated107):
            user.SendStatusEffect(self)
            await user.RemoveAllStatus(SPanjueA111)
            await user.AddStatus(SWufazhandou108(timedelta(hours=4)))
            return True
        return False
    async def OnDragoned(self, user: 'User', branch: 'Tree', first10: bool) -> None:
        count = self.count
        await user.RemoveAllStatus(SPanjueA111)
        await user.AddStatus(SPanjueAActivated106(count))
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnStatusAdd: Priority.OnStatusAdd.panjue,
            UserEvt.OnDragoned: Priority.OnDragoned.panjue}
class SPanjueAActivated106(StatusNullStack):
    name = "最终判决α"
    id = 106
    _description = "将此buff传递给你接龙后第五次接龙的玩家。与最终判决β重合时，罪行加重，判处死刑。"
    isDebuff = True
    async def OnStatusAdd(self, user: 'User', status: 'Status') -> bool:
        """判决重合，无法战斗。"""
        if isinstance(status, SPanjueB112) or isinstance(status, SPanjueBActivated107):
            user.SendStatusEffect(self)
            await user.RemoveAllStatus(SPanjueA111)
            await user.AddStatus(SWufazhandou108(timedelta(hours=4)))
            return True
        return False
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnStatusAdd: Priority.OnStatusAdd.panjue_activated}

class CPanjueB112(Card):
    name = "最终判决β"
    id = 112
    _description = "抽到时附加buff：最终判决β。你接龙后，将此buff传递给你接龙后第五次接龙的玩家。与最终判决α重合时，罪行加重，判处死刑。"
    positive = -1
    consumedOnDraw = True
    pack = Pack.ff14
    async def OnDraw(self, user: 'User') -> None:
        await user.AddStatus(SPanjueB112())
class SPanjueB112(StatusNullStack):
    name = "最终判决β"
    id = 112
    _description = "你下次接龙后，将此buff传递给你接龙后第五次接龙的玩家。与最终判决α重合时，罪行加重，判处死刑。"
    isDebuff = True
    async def OnStatusAdd(self, user: 'User', status: 'Status') -> bool:
        """判决重合，无法战斗。"""
        if isinstance(status, SPanjueA111) or isinstance(status, SPanjueAActivated106):
            user.SendStatusEffect(self)
            await user.RemoveAllStatus(SPanjueB112)
            await user.AddStatus(SWufazhandou108(timedelta(hours=4)))
            return True
        return False
    async def OnDragoned(self, user: 'User', branch: 'Tree', first10: bool) -> None:
        count = self.count
        await user.RemoveAllStatus(SPanjueB112)
        await user.AddStatus(SPanjueBActivated107(count))
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnStatusAdd: Priority.OnStatusAdd.panjue,
            UserEvt.OnDragoned: Priority.OnDragoned.panjue}
class SPanjueBActivated107(StatusNullStack):
    name = "最终判决β"
    id = 107
    _description = "将此buff传递给你接龙后第五次接龙的玩家。与最终判决α重合时，罪行加重，判处死刑。"
    isDebuff = True
    async def OnStatusAdd(self, user: 'User', status: 'Status') -> bool:
        """判决重合，无法战斗。"""
        if isinstance(status, SPanjueA111) or isinstance(status, SPanjueAActivated106):
            user.SendStatusEffect(self)
            await user.RemoveAllStatus(SPanjueBActivated107)
            await user.AddStatus(SWufazhandou108(timedelta(hours=4)))
            return True
        return False
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnStatusAdd: Priority.OnStatusAdd.panjue_activated}

class IPanjueChecker(IEventListener):
    async def OnDragoned(self, user: 'User', branch: 'Tree', first10: bool) -> None:
        if (nd := branch.before(5)) and nd.qq != user.game.managerQQ and nd.qq != 0 and (u := user.CreateUser(nd.qq)) != user:
            if na := u.CheckStatusStack(SPanjueAActivated106):
                await u.RemoveAllStatus(SPanjueAActivated106)
                await user.AddStatus(SPanjueA111(na))
            if nb := u.CheckStatusStack(SPanjueBActivated107):
                await u.RemoveAllStatus(SPanjueBActivated107)
                await user.AddStatus(SPanjueB112(nb))
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnDragoned: Priority.OnDragoned.panjuecheck}
Game.RegisterEventCheckerInit(IPanjueChecker())

class SWufazhandou108(StatusTimed):
    id = 108
    name = "无法战斗"
    _description = "不能接龙"
    isDebuff = True
    isRemovable = False
    async def BeforeDragoned(self, user: 'User', state: 'DragonState') -> Tuple[bool, int]:
        """无法战斗，不能接龙。"""
        user.SendStatusEffect(self)
        return False, 0
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.BeforeDragoned: Priority.BeforeDragoned.wufazhandou}
class SShuairuo95(StatusTimed):
    id = 95
    name = "衰弱"
    isDebuff = True
    isRemovable = False
    async def OnJibiChange(self, user: 'User', jibi: int, isBuy: bool) -> int:
        """击毙收入减少
        njibi：减少后的击毙收入"""
        if jibi > 0:
            njibi = ceil(0.75 * jibi)
            user.SendStatusEffect(self, njibi=njibi)
            return njibi
        return jibi
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnJibiChange: Priority.OnJibiChange.shuairuo}

class CEarthquake113(Card):
    id = 113
    name = "大地摇动"
    _description = "抽到时附加全局buff：今天每个分支最后接龙的第2,5,8,11,14个人每人扣除4击毙。"
    positive = -1
    pack = Pack.ff14
    consumedOnDraw = True
    async def OnDraw(self, user: 'User') -> None:
        await user.ume.AddStatus(SEarthquake113())
class SEarthquake113(StatusNullStack):
    id = 113
    name = "大地摇动"
    _description = "今天每个分支最后接龙的第2,5,8,11,14个人每人扣除4击毙。"
    isDebuff = True
    isGlobal = True
    async def OnNewDay(self, user: 'User') -> None:
        '''扣除玩家击毙
        userQQ: 玩家qq
        count: 扣除的击毙的次数'''
        to_send: Counter[int] = Counter()
        for branch in user.game.treeObjs:
            if len(branch) == 0:
                continue
            end = branch[-1]
            for i in range(1, 15, 3):
                tr = end.before(i)
                if tr is not None and tr.id != (0, 0):
                    to_send[tr.qq] += 1
        if len(to_send) != 0:
            for qq, count in to_send.items():
                user.SendStatusEffect(self, userQQ=qq, count=count)
                await user.CreateUser(qq).AddJibi(-4 * count)
        await user.ume.RemoveStatus(SEarthquake113)
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnNewDay: Priority.OnNewDay.earthquake}

class CEruption114(Card):
    name = "地火喷发"
    id = 114
    _description = "今天所有的接龙词都有10%的几率变成地雷。"
    positive = 0
    pack = Pack.ff14
    async def Use(self, user: 'User') -> None:
        await user.ume.AddStatus(SEruption114())
class SEruption114(StatusDailyStack):
    name = "地火喷发"
    id = 114
    _description = "地火喷发：今天所有的接龙词都有10%的几率变成地雷。"
    isGlobal = True
    async def OnDragoned(self, user: 'User', branch: 'Tree', first10: bool) -> None:
        """添加地雷。
        word: 添加的词。"""
        if random.random() > 0.9 ** self.num:
            user.SendStatusEffect(self, word=branch.word)
            user.game.AddBomb(branch.word)
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnDragoned: Priority.OnDragoned.eruption}

class CConfession116(Card):
    name = "告解"
    id = 116
    _description = "今天每次你获得击毙时额外获得1击毙。"
    positive = 1
    pack = Pack.ff14
    async def Use(self, user: 'User') -> None:
        await user.AddStatus(SConfession116())
class SConfession116(StatusDailyStack):
    name = "告解"
    id = 116
    _description = "今天每次你获得击毙时额外获得1击毙。"
    async def OnJibiChange(self, user: 'User', jibi: int, isBuy: bool) -> int:
        """额外获得击毙。
        count: 增加的击毙数"""
        if jibi > 0:
            user.SendStatusEffect(self, count=self.count)
            return jibi + self.count
        return jibi
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnJibiChange: Priority.OnJibiChange.confession}
class SInvConfession94(StatusDailyStack):
    name = "反转·告解"
    id = 94
    _description = "今日每次你获得击毙时少获得1击毙。"
    async def OnJibiChange(self, user: 'User', jibi: int, isBuy: bool) -> int:
        """额外获得击毙。
        count: 减少的击毙数"""
        if jibi > 0:
            user.SendStatusEffect(self, count=self.count)
            return max(jibi - self.count, 0)
        return jibi
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnJibiChange: Priority.OnJibiChange.inv_confession}

class CExcogitation117(Card):
    name = "深谋远虑之策"
    id = 117
    _description = "当你一次使用/损失了超过你现有击毙一半以上的击毙时，恢复这些击毙。"
    positive = 0
    pack = Pack.ff14
    async def Use(self, user: 'User') -> None:
        await user.AddStatus(SExcogitation117())
class SExcogitation117(StatusNullStack):
    name = "深谋远虑之策"
    id = 117
    _description = "当你一次使用/损失了超过你现有击毙一半以上的击毙时，恢复这些击毙。"
    async def OnJibiChange(self, user: 'User', jibi: int, isBuy: bool) -> int:
        """恢复击毙。"""
        if jibi < 0 and -jibi > user.data.jibi / 2:
            await user.RemoveStatus(SExcogitation117)
            user.SendStatusEffect(self)
            return 0
        return jibi
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnJibiChange: Priority.OnJibiChange.excogitation}

class CMixidiyatu118(Card):
    name = "通灵之术-密西迪亚兔"
    id = 118
    _description = "你的头上会出现一只可爱的小兔子。"
    positive = 0
    pack = Pack.ff14
    async def Use(self, user: 'User') -> None:
        await user.AddStatus(SMixidiyatu118())
class SMixidiyatu118(StatusNullStack):
    name = "通灵之术-密西迪亚兔"
    id = 118
    _description = "你的头上会出现一只可爱的小兔子。"
class SInvMixidiyatu91(StatusNullStack):
    name = "反转·通灵之术-密西迪亚兔"
    id = 91
    _description = "你的屁股上出现了一只可爱的小兔子。"

class CWardensPaean119(Card):
    name = "光阴神的礼赞凯歌"
    id = 119
    _description = "免疫三次负面状态或消耗全部次数免疫大病一场，或主动使用解除大病一场。"
    positive = 1
    pack = Pack.ff14
    @staticmethod
    def _weight(user: User):
        # if user.check_daily_status('d'):
        #     return 1 + user.data.luck / 2
        return 1
    weight = _weight
    async def Use(self, user: 'User') -> None:
        for c in user.data.statuses:
            if isinstance(c, SIll30):
                user.SendCardUse(self)
                await user.RemoveAllStatus(SIll30, remover=user)
                return
        await user.AddStatus(SWardensPaean119(3))
class SWardensPaean119(StatusNumed):
    name = "光阴神的礼赞凯歌"
    id = 119
    _description = "免疫三次负面状态或消耗全部次数（大于等于3）免疫大病一场。"
    async def OnStatusAdd(self, user: 'User', status: 'Status') -> bool:
        '''免除负面状态
        flag：是否防止了全部的负面状态。ill：防止的是大病一场；all：是全部；part：是部分。
        rstatus: 所防止的负面状态。'''
        if isinstance(status, SIll30) and self.count >= 3:
            user.SendStatusEffect(self, flag = 'ill', rstatus=status.DumpData())
            await user.RemoveStatus(self)
            return True
        elif status.isDebuff and status.isRemovable:
            if self.count >= status.count:
                user.SendStatusEffect(self, flag = 'all', rstatus=status.DumpData())
                self.num -= status.count # pylint: disable=no-member
                user.data.SaveStatuses()
                return True
            else:
                # pylint: disable=no-member
                status.num -= self.count # type: ignore[attr-defined]
                user.SendStatusEffect(self, flag = 'part', rstatus=type(status)(self.count).DumpData())
                await user.RemoveStatus(self)
                user.data.SaveStatuses()
        return False
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnStatusAdd: Priority.OnStatusAdd.paean}

class CImagineBreaker120(Card):
    name = "幻想杀手"
    id = 120
    _description = "你的下一次攻击无视对方的所有反制效果，下一次目标为你的攻击无效。以上两项只能发动一项。"
    positive = 1
    pack = Pack.toaru
    async def Use(self, user: 'User') -> None:
        await user.AddStatus(SImagineBreaker120())
class SImagineBreaker120(StatusNullStack):
    name = "幻想杀手"
    id = 120
    _description = "你的下一次攻击无视对方的所有反制效果，下一次目标为你的攻击无效。以上两项只能发动一项。"
    async def OnAttack(self, user: 'User', attack: 'Attack') -> bool:
        pass#TODO
    async def OnAttacked(self, user: 'User', attack: 'Attack') -> bool:
        pass#TODO
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnAttack: Priority.OnAttack.imaginebreaker,
            UserEvt.OnAttacked: Priority.OnAttacked.imaginebreaker}

class CVector121(Card):
    name = "矢量操作"
    id = 121
    _description = "你的下一次攻击效果加倍，下一次对你的攻击反弹至攻击者，免除你下一次触雷。以上三项只能发动一项。"
    positive = 1
    pack = Pack.toaru
    async def Use(self, user: 'User') -> None:
        await user.AddStatus(SVector121())
class SVector121(StatusNullStack):
    name = "矢量操作"
    id = 121
    _description = "你的下一次攻击效果加倍，下一次对你的攻击反弹至攻击者，免除你下一次触雷。以上三项只能发动一项。"
    async def OnAttack(self, user: 'User', attack: 'Attack') -> bool:
        if attack.doublable:
            user.SendStatusEffect(self, time = 'OnAttack')
            await user.RemoveStatus(self)
            return attack.double()
        return False
    async def OnAttacked(self, user: 'User', attack: 'Attack') -> bool:
        if attack.reboundable:
            user.SendStatusEffect(self, time = 'OnAttacked')
            await user.RemoveStatus(self)
            return attack.rebound()
        return False
    async def OnBombed(self, user: 'User', word: str) -> bool:
        user.SendStatusEffect(self, time = 'OnBombed')
        await user.RemoveStatus(self)
        return True
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnAttack: Priority.OnAttack.vector,
            UserEvt.OnAttacked: Priority.OnAttacked.vector,
            UserEvt.OnBombed: Priority.OnBombed.vector}

class CYouxianShushi123(Card):
    id = 123
    name = "优先术式"
    positive = 0
    _description = "今天所有攻击效果都变为击杀，礼物交换无效。"
    pack = Pack.toaru
    async def Use(self, user: 'User') -> None:
        await user.ume.AddStatus(SYouxianShushi123())
class SYouxianShushi123(StatusDailyStack):
    id = 123
    name = "优先术式"
    _description = "今天所有攻击效果都变为击杀，礼物交换无效。"
    isGlobal = True
    async def OnAttack(self, user: 'User', attack: 'Attack') -> bool:
        """优先术式。
        flag: liwujiaohuan：礼物交换无效。else：其他攻击。"""
        if isinstance(attack, ALiwuJiaohuan72):
            user.SendStatusEffect(self, flag = 'liwujiaohuan')
            return True
        elif not isinstance(attack, AKill0) or not isinstance(attack, ADamage1):
            user.SendStatusEffect(self, flag='else')
            atk_new = AKill0(attack.attacker, attack.defender, 120)
            await attack.defender.Attacked(attack.attacker, atk_new)
            return True
        return False
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnAttack: Priority.OnAttack.youxianshushi}
