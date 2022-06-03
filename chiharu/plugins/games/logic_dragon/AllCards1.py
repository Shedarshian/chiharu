from typing import *
from math import ceil
from datetime import timedelta, datetime
from collections import Counter
import itertools, random
from .Game import Game
from .Card import Card
from .User import User
from .Status import Status, StatusNumed, StatusTimed, StatusNullStack, StatusDailyStack, StatusListInt
from .Attack import Attack, AttackType
from .Priority import UserEvt, Priority
from .Types import Pack
from .Dragon import DragonState, Tree, TreeLeaf
from .Mission import Mission
from .EventListener import IEventListener
from ... import config
from .Helper import positive
log = config.logger.dragon

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
        return len([c for c in user.data.handCard if c.id not in (56, 200)]) >= (1 if copy else 2)
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
    async def OnDragoned(self, user: 'User', branch: 'TreeLeaf', first10: bool) -> None:
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
    isReversable = True
    def reverse(self):
        return (self, SInvHierophant6(self.count))
    async def BeforeDragoned(self, user: 'User', state: 'DragonState') -> Tuple[bool, int]:
        """禁止非首尾接龙。"""
        if not await state.RequireShouwei(user):
            user.SendStatusEffect(self, time="BeforeDragoned")
            return False, 0
        return True, 0
    async def OnDragoned(self, user: 'User', branch: 'TreeLeaf', first10: bool) -> None:
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
    isReversable = True
    def reverse(self):
        return (self, SHierophant5(self.count))
    async def BeforeDragoned(self, user: 'User', state: 'DragonState') -> Tuple[bool, int]:
        """禁止非尾首接龙。"""
        if not await state.RequireWeishou(user):
            user.SendStatusEffect(self, time="BeforeDragoned")
            return False, 0
        return True, 0
    async def OnDragoned(self, user: 'User', branch: 'TreeLeaf', first10: bool) -> None:
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
            from .AllCards0 import SDeathN1
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
    isReversable = True
    def reverse(self, c: int):
        from AllCards3 import SEruption114
        return (SStar17(c), SEruption114(c))
    async def OnDragoned(self, user: 'User', branch: 'TreeLeaf', first10: bool) -> None:
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

class CWorld21(Card):
    name = "XXI - 世界"
    id = 21
    _description = "除大病一场外，所有“直到跨日为止”的效果延长至明天。"
    pack = Pack.tarot
    async def Use(self, user: 'User') -> None:
        await user.ume.AddStatus(SWorld21())
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

class CLebusishu35(Card):#TODO reverse TODO
    id = 35
    name = "乐不思蜀"
    positive = -1
    _description = "抽到时为你附加buff：今天每次接龙时，你进行一次判定。有3/4的几率你不得从该节点接龙。"
    pack = Pack.sanguosha
    consumedOnDraw = True
    async def OnDraw(self, user: 'User') -> None:
        await user.AddStatus(SLebusishu35())
class SLebusishu35(StatusListInt):
    id = 35
    name = "乐不思蜀"
    isDebuff = True
    _description = '今天每次接龙时，你进行一次判定。有3/4的几率你不得从该节点接龙。'
class SInvLebusishu32(StatusListInt):
    id = 32
    name = "反转·乐不思蜀"
    isDebuff = True
    _description = '今天每次接龙时，你进行一次判定。有1/4的几率你不得从该节点接龙。'
class ILeChecker(IEventListener):#TODO
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
        user.SendCardUse(self, choose=True)
        if (players := await user.ChoosePlayers(1, 1)) is not None:
            player = players[0]
            if user.ume.CheckStatus(SJuedou37) is not None:
                await user.ume.RemoveAllStatus(SJuedou37)
            user.SendCardUse(self, choose=False, ruser = player)
            await user.ume.AddStatus(SJuedou37(timedelta(hours=1), user.qq, player, 10))
class SJuedou37(StatusTimed):
    id = 37
    name = "决斗"
    isGlobal = True
    dataType: Tuple[Callable[[str], Any],...] = (datetime.fromisoformat, int, int, int)
    def __init__(self, data: datetime | timedelta, player1: int, player2: int, count: int):
        self.player1 = player1
        self.player2 = player2
        self._count = count
        super().__init__(data)
    @property
    def valid(self):
        return self.time >= datetime.now() and self._count > 0
    def packData(self) -> str:
        return ','.join((self.time.isoformat(), str(self.player1), str(self.player2), str(self._count)))
    @property
    def description(self):
        return f"决斗：接下来的{self._count}次接龙由玩家{self.player1}与{self.player2}之间进行。\n\t结束时间：{self.getStr()}。"
    async def BeforeDragoned(self, user: 'User', state: 'DragonState') -> Tuple[bool, int]:
        """不可干扰决斗。"""
        if user.qq == self.player1 or user.qq == self.player2:
            return True, -100
        else:
            user.SendStatusEffect(self, time = 'BeforeDragoned')
            return False, 0
    async def OnDragoned(self, user: 'User', branch: 'TreeLeaf', first10: bool) -> None:
        self._count -= 1
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
        if (players := await user.ChoosePlayers(1, 2)) is not None:
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
    isReversable = True
    def reverse(self, c: int):
        return (SMinus1Ma39(c), SPlus1Ma36(c))
    async def BeforeDragoned(self, user: 'User', state: 'DragonState') -> Tuple[bool, int]:
        return True, -self.count
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.BeforeDragoned: Priority.BeforeDragoned.minus1ma}
class SPlus1Ma36(StatusDailyStack):
    name = "+1马"
    id = 36
    _description = "今天你必须额外隔一个才能接龙。"
    isDebuff = True
    isReversable = True
    def reverse(self, c: int):
        return (SPlus1Ma36(c), SMinus1Ma39(c))
    async def BeforeDragoned(self, user: 'User', state: 'DragonState') -> Tuple[bool, int]:
        return True, self.count
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.BeforeDragoned: Priority.BeforeDragoned.plus1ma}
