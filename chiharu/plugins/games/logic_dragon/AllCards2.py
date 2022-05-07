from typing import *
from copy import copy
from math import ceil
import itertools, random
from .Card import Card, CardDoubleNumed
from .User import User
from .Status import Status, StatusListInt, StatusNumed, StatusTimed, StatusNullStack, StatusDailyStack
from .Attack import Attack, AttackType
from .Priority import UserEvt, Priority
from .Types import Pack
from .Dragon import DragonState, Tree
from .Mission import Mission
from .Helper import positive
from ... import config
log = config.logger.dragon

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

class CQueststone67(CardDoubleNumed):
    name = "任务之石"
    id = 67
    positive = 1
    _description = "持有此石时，你每天会刷新一个接龙任务。每次完成接龙任务可以获得3击毙，每天最多3次。使用将丢弃此石。"
    desNeedInit = True
    mass = 0.2
    pack = Pack.stone_story
    def __init__(self) -> None:
        super().__init__()
        self.num1 = Mission.RandomQuestStoneId()
        self.num2 = 3
    @property
    def QuestDes(self):
        # pylint: disable=no-member
        r = Mission.get(self.num1)().description
        remain = self.num2
        return "\t当前任务：" + r + f"。剩余{remain}次。"
    @property
    def description(self):
        return self._description + "\n" + self.QuestDes
    async def OnDragoned(self, user: 'User', branch: 'Tree', first10: bool) -> None:
        """完成任务
        remain: 剩余次数
        mission: 任务描述"""
        # pylint: disable=no-member
        quest = Mission.get(self.num1)()
        if self.num2 > 0:
            if quest.check(branch.word):
                self.num2 -= 1
                user.SendCardEffect(self, time="OnDragoned", remain=self.num2, mission=quest.description)
                await user.AddJibi(3)
                user.data.SaveStatuses()
    async def OnNewDay(self, user: 'User') -> None:
        user.SendCardEffect(self, time="OnNewDay")
        self.num1 = Mission.RandomQuestStoneId()
        self.num2 = 3
        user.data.SaveStatuses()
    def register(self) -> Dict['UserEvt', int]:
        return {UserEvt.OnDragoned: Priority.OnDragoned.queststone,
                UserEvt.OnNewDay: Priority.OnNewDay.queststone}

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

class CHuxiangjiaohuan75(Card):
    name = '互相交换'
    id = 75
    positive = 0
    _description = "下一个接中隐藏奖励词的玩家手牌与你互换，手牌量变化最多为2。"
    pack = Pack.orange_juice
    async def Use(self, user: 'User') -> None:
        l = user.ume.CheckStatus(SHuxiangjiaohuan75)
        if len(l) != 0:
            l[0].list += [user.qq]
            user.data.SaveStatuses()
        else:
            await user.ume.AddStatus(SHuxiangjiaohuan75([user.qq]))
class SHuxiangjiaohuan75(StatusListInt):
    id = 75
    name = "互相交换"
    isGlobal = True
    @property
    def description(self) -> str:
        return f"下{len(self.list)}个接中隐藏奖励词的玩家手牌与某人互换。"
    async def OnHiddenKeyword(self, user: 'User', word: str, parent: 'Tree', keyword: str) -> int:
        to_exchange = self.list.pop()
        user.data.SaveStatuses()
        u = User(to_exchange, user.buf)
        atk = AHuxiangjiaohuan75(u, user)
        await user.Attacked(atk)
        return 0
    def register(self) -> Dict['UserEvt', int]:
        return {UserEvt.OnHiddenKeyword: Priority.OnHiddenKeyword.huxiangjiaohuan}
class AHuxiangjiaohuan75(Attack):
    id = 75
    name = "攻击：互相交换"
    doublable = False
    async def selfAction(self):
        max_sub = 2
        target_card = copy(self.defender.data.handCard)
        self_card = copy(self.attacker.data.handCard)
        target_choose = list(range(len(target_card)))
        self_choose = list(range(len(self_card)))
        if len(target_card) - len(self_card) > max_sub:
            random.shuffle(target_choose)
            target_choose = target_choose[:len(self_card) + max_sub]
            target_choose.sort()
            target_card = [target_card[i] for i in target_choose]
        elif len(self_card) - len(target_card) > max_sub:
            random.shuffle(self_choose)
            self_choose = self_choose[:len(target_card) + max_sub]
            self_choose.sort()
            self_card = [self_card[i] for i in self_choose]
        for card in self_card:
            await self.attacker.GiveCard(self.defender, card)
        for card in target_card:
            await self.defender.GiveCard(self.attacker, card)

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
        n = len(user.data.handCard)
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
class SDefeat79(StatusDailyStack):
    id = 79
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
