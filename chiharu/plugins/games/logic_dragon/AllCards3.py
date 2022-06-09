from typing import *
from datetime import timedelta, datetime
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
from .Dragon import DragonState, TreeLeaf
from .Mission import Mission
from .EventListener import IEventListener
from .Helper import positive
from ... import config
log = config.logger.dragon

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
    isReversable = True
    def reverse(self, c: int):
        return (SJiaodai100(c), SInvJiaodai90(c))
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
    isReversable = True
    def reverse(self, c: int):
        return (SInvJiaodai90(c), SJiaodai100(c))
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
    async def OnDragoned(self, user: 'User', branch: 'TreeLeaf', first10: bool) -> None:
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
                from .AllCards1 import SWorld21
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
    isReversable = True
    def reverse(self, c: int):
        return (SRanSheFaShu109(c), SInvRanSheFaShu108(c))
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
    isReversable = True
    def reverse(self, c: int):
        return (SInvRanSheFaShu108(c), SRanSheFaShu109(c))
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
    isReversable = True
    def reverse(self):
        return (self, SInvNightbloom105(self.count))
    @property
    def description(self):
        return f"{self._description}\n\t剩余{(self.num + 2) // 3}次。" # pylint: disable=no-member
    async def OnDragoned(self, user: 'User', branch: 'TreeLeaf', first10: bool) -> None:
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
    isReversable = True
    def reverse(self):
        return (self, SNightbloom110(self.count))
    @property
    def description(self):
        return f"{self._description}\n\t剩余{(self.num + 2) // 3}次。" # pylint: disable=no-member
    async def OnDragoned(self, user: 'User', branch: 'TreeLeaf', first10: bool) -> None:
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
    isReversable = True
    def reverse(self, c: int):
        return (SPanjueA111(c), SPanjueB112(c))
    async def OnStatusAdd(self, user: 'User', status: 'Status') -> bool:
        """判决重合，无法战斗。"""
        if isinstance(status, SPanjueB112) or isinstance(status, SPanjueBActivated107):
            user.SendStatusEffect(self)
            await user.RemoveAllStatus(SPanjueA111)
            await user.AddStatus(SWufazhandou108(timedelta(hours=4)))
            return True
        return False
    async def OnDragoned(self, user: 'User', branch: 'TreeLeaf', first10: bool) -> None:
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
    isReversable = True
    def reverse(self, c: int):
        return (SPanjueAActivated106(c), SPanjueBActivated107(c))
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
    isReversable = True
    def reverse(self, c: int):
        return (SPanjueB112(c), SPanjueA111(c))
    async def OnStatusAdd(self, user: 'User', status: 'Status') -> bool:
        """判决重合，无法战斗。"""
        if isinstance(status, SPanjueA111) or isinstance(status, SPanjueAActivated106):
            user.SendStatusEffect(self)
            await user.RemoveAllStatus(SPanjueB112)
            await user.AddStatus(SWufazhandou108(timedelta(hours=4)))
            return True
        return False
    async def OnDragoned(self, user: 'User', branch: 'TreeLeaf', first10: bool) -> None:
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
    isReversable = True
    def reverse(self, c: int):
        return (SPanjueBActivated107(c), SPanjueAActivated106(c))
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
    async def OnDragoned(self, user: 'User', branch: 'TreeLeaf', first10: bool) -> None:
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
    _description = "今天所有的接龙词都有10%的几率变成地雷。"
    isGlobal = True
    isReversable = True
    def reverse(self, c: int):
        from AllCards1 import SStar17
        return (SEruption114(c), SStar17(c))
    async def OnDragoned(self, user: 'User', branch: 'TreeLeaf', first10: bool) -> None:
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
    isReversable = True
    def reverse(self, c: int):
        return (SConfession116(c), SInvConfession94(c))
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
    isDebuff = True
    isReversable = True
    def reverse(self, c: int):
        return (SInvConfession94(c), SConfession116(c))
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
    isReversable = True
    def reverse(self, c: int):
        return (SMixidiyatu118(c), SInvMixidiyatu91(c))
class SInvMixidiyatu91(StatusNullStack):
    name = "反转·通灵之术-密西迪亚兔"
    id = 91
    _description = "你的屁股上出现了一只可爱的小兔子。"
    isReversable = True
    def reverse(self, c: int):
        return (SInvMixidiyatu91(c), SMixidiyatu118(c))

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
            from AllCards1 import SIll30
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
        from AllCards1 import SIll30
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
        from AllCards0 import AKill0, ADamage1
        from AllCards2 import ALiwuJiaohuan72
        if isinstance(attack, ALiwuJiaohuan72):
            user.SendStatusEffect(self, flag = 'liwujiaohuan')
            return True
        elif not isinstance(attack, AKill0) or not isinstance(attack, ADamage1):
            user.SendStatusEffect(self, flag='else')
            atk_new = AKill0(attack.attacker, attack.defender, 120)
            await attack.defender.Attacked(atk_new)
            return True
        return False
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnAttack: Priority.OnAttack.youxianshushi}

class CXixueShashou124(Card):
    name = "吸血杀手"
    id = 124
    positive = 1
    _description = "今天你每次接龙时有10%几率获得一张【吸血鬼】。"
    pack = Pack.toaru
    async def Use(self, user: 'User') -> None:
        await user.AddStatus(SXixueShashou124())
class SXixueShashou124(StatusDailyStack):
    name = "吸血杀手"
    id = 124
    _description = "今天你每次接龙时有10%几率获得一张【吸血鬼】。"
    async def OnDragoned(self, user: 'User', branch: 'TreeLeaf', first10: bool) -> None:
        '''概率抽卡'''
        for i in range(self.count):
            if random.random() < 0.1 + 0.01 * user.data.luck:
                user.SendStatusEffect(self)
                await user.Draw(cards=[Card.get(-2)()])
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnDragoned: Priority.OnDragoned.xixueshashou}
class CVampireN2(Card):
    name = "吸血鬼"
    id = -2
    positive = 1
    weight = 0
    _description = "此牌通常情况下无法被抽到。2小时内免疫死亡。"
    mass = 0.5
    pack = Pack.toaru
    async def Use(self, user: 'User') -> None:
        await user.AddStatus(SVampireN2(timedelta(hours=2)))
class SVampireN2(StatusTimed):
    name = "吸血鬼"
    id = -2
    _description = "免疫死亡。"
    async def OnDeath(self, user: 'User', killer: Optional['User'], time: int, c: 'AttackType') -> Tuple[int, bool]:
        """免疫死亡。"""
        user.SendStatusEffect(self)
        return time, True
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnDeath: Priority.OnDeath.vampire}

class CRailgun125(Card):
    id = 125
    name = "超电磁炮"
    _description = "花费1击毙或者手牌中一张金属制的牌或者身上一个金属制的buff，选择一个与你接龙距离3以内（若选择的是金属则为5以内）的人击毙。目标身上的每个金属制buff有1/2的几率被烧掉。"
    pack = Pack.toaru
    positive = 1
    # failure_message = "使用此卡必须身上有弹药并且今天接过龙" + 句尾
    def CanUse(self, user: 'User', copy: bool) -> bool:
        """无法使用原因。
        flag: "dragon":今天未接过龙, "ammo":没有弹药"""
        if user.qq not in [tree.qq for tree in itertools.chain(*itertools.chain(user.game.treeObjs, *user.game.treeForests))]:
            user.SendCardEffect(self, reason='NoStartPoint', time="CanUse")
            return False
        if user.data.jibi != 0:
            return True
        cards = [d for d in user.data.handCard if d.isMetallic]
        statuses = [s for s in user.data.statuses if s.isMetallic]
        if len(cards) + len(statuses) != 0:
            return True
        user.SendCardEffect(self, reason="NoAmmo", time="CanUse")
        return False
    async def Use(self, user: 'User') -> None:
        '''进行电磁炮攻击
        success：是否成功攻击
        在success为False时调用:
        reason：使用失败的理由
        在success为True时调用:
        chooseAmmo：True为询问弹药选择
        ammoList：可用弹药列表
        tammo：发射使用的弹药，击毙时为“1击毙”
        chooseUser：True为询问攻击目标
        userList：可以攻击的玩家列表
        tuser：攻击到的玩家'''
        async def ChooseAmmo(self, ammoList: List[str | Card | Status]):
            #TODO
            return tammo
            # prompt = "请选择要发射的弹药，手牌请输入id，状态请输入全名，重新查询列表请输入“重新查询”。\n" + "\n".join(s for i, s, t, c in to_choose)
            # def check(value: str):
            #     if value == "重新查询":
            #         _raise_failure(prompt)
            #     for i, s, t, count in to_choose:
            #         if value in t:
            #             return (i, s, count)
            #     _raise_failure("请选择一个在列表中的物品，重新查询列表请输入“重新查询”。")
            # user.buf.send(prompt)
            # await user.buf.flush()
            # num, st, count = await user.buf.aget(prompt="", arg_filters=[
            #     extractors.extract_text,
            #     check_handcard(user),
            #     check
            # ])
        if await user.choose(flush=False):
            if user.qq not in [tree.qq for tree in itertools.chain(*itertools.chain(user.game.treeObjs, *user.game.treeForests))]:
                user.SendCardUse(self, success = False, reason = 'NoDragon')
                return
            cards = [d for d in user.data.handCard if d.isMetallic]
            statuses = [s for s in user.data.statuses if s.isMetallic]
            l = len(cards) + len(statuses)
            to_choose: list[str | Card | Status] = []
            if user.data.jibi != 0:
                to_choose.append("1击毙")
            to_choose.extend(cards)
            to_choose.extend(statuses)
            if len(to_choose) == 0:
                user.SendCardUse(self, success = False, reason = 'NoAmmo')
                return
            elif len(to_choose) == 1:
                tammo = to_choose[0]
                user.SendCardUse(self, success = True, chooseAmmo = False, tammo = tammo if isinstance(tammo, str) else tammo.DumpData())
            else:
                user.SendCardUse(self, success = True, chooseAmmo = True, ammoList = to_choose)
                tammo = await ChooseAmmo(self, to_choose)
            distance = 3 if tammo == "1击毙" else 5
            allqq = set()
            for branches in user.game.treeObjs:
                for node in branches:
                    if node.qq == user.qq:
                        for s in range(-distance, distance + 1):
                            for i in range(-(distance - abs(s)), distance - abs(s) + 1):
                                ret = user.game.FindTree((node.id[0] + s, node.id[1] + i))
                                if ret is not None:
                                    allqq.add(ret.qq)
            allqq.remove(user.qq)
            user.SendCardUse(self, success = True, chooseUser = True, userList = allqq)
            tqqs = await user.ChoosePlayers(1, 1, range = set(allqq))
            if tqqs is None:
                return
            tqq = tqqs[0]
            user.SendCardUse(self, success = True, tammo = tammo if isinstance(tammo, str) else tammo.DumpData(), tuser = tqq)
            if tammo == "1击毙":
                await user.AddJibi(-1)
            elif isinstance(tammo, Card):
                await user.RemoveCards([tammo])
            elif isinstance(tammo, Status):
                await user.RemoveStatus(tammo, remover=user)
            u = user.CreateUser(tqq)
            atk = ARailgun125(user, u)
            await u.Attacked(atk)
class ARailgun125(Attack):
    name = "超电磁炮"
    async def selfAction(self):
        self.defender.Death(120 * self.multiplier, killer = self.attacker)
        '''烧毁金属制品
        tcard：被烧毁的卡牌
        tstatus：被烧毁的状态'''
        for d in self.defender.data.handCard:
            if d.isMetallic and random.random() > (0.5 - 0.02 * self.attacker.data.luck) ** self.multiplier:
                self.defender.SendAttack(self, tcard = d.DumpData())
                await self.defender.RemoveCards([d])
        for s in self.defender.data.statuses:
            if s.isMetallic and random.random() > (0.5 - 0.02 * self.attacker.data.luck) ** self.multiplier:
                self.defender.SendAttack(self, status = s.DumpData())
                await self.defender.RemoveStatus(s, remover = self.attacker)
