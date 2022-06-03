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

class CMagnetShroom129(Card):
    id = 129
    name = "磁力菇"
    _description = "种植植物磁力菇：有人攻击你时，随机移除其身上的一件金属制品，然后24小时不能发动。"
    positive = 1
    pack = Pack.pvz
    isMetallic = True
    async def Use(self, user: 'User') -> None:
        await user.AddStatus(SMagnetShroom129())
class SMagnetShroom129(StatusTimed):
    id = 129
    name = "磁力菇"
    _description = "有人攻击你时，随机移除其身上的一件金属制品，然后24小时不能发动。"
    @property
    def valid(self):
        return True
    def getStr(self):
        if self.time > datetime.now():
            delta = self.time - datetime.now()
            min = delta.seconds // 60
            return f"""充能时间：{f'{min // 60}时' if min // 60 != 0 else ''}{min % 60}分钟。"""
        else:
            return "充能完毕。"
    def description(self):
        return f"{self._description}\n\t{self.getStr()}。"
    def double(self):
        pass
    async def OnAttacked(self, user: 'User', attack: 'Attack') -> bool:
         # pylint: disable=access-member-before-definition,attribute-defined-outside-init
        if self.time < datetime.now():
            user.SendStatusEffect(self)
            self.time = datetime.now() + timedelta(days=1)
            atk = AMagnetShroom129(user, attack.attacker)
            await attack.attacker.Attacked(atk)
            user.data.SaveStatuses()
            return False
        return False
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnAttacked: Priority.OnAttacked.magnet}
class AMagnetShroom129(Attack):
    name = "磁力菇"
    doublable = False
    async def selfAction(self):
        to_choose: List[Card | Status] = []
        to_choose.extend([d for d in self.defender.data.handCard if d.isMetallic])
        to_choose.extend([s for s in self.defender.data.statuses if s.isMetallic])
        if len(to_choose) == 0:
            self.defender.SendAttack(self, target = None)
        else:
            target = random.choice(to_choose)
            self.defender.SendAttack(self, target = target)
            if isinstance(target, Card):
                await self.defender.RemoveCards([target])
            elif isinstance(target, Status):
                await self.defender.RemoveStatus(target, remover = self.attacker)

class CSunflower130(Card):
    name = "向日葵"
    id = 130
    description = "种植植物向日葵：跨日结算时你获得1击毙。场上最多存在十株(双子)向日葵。"
    positive = 1
    pack = Pack.pvz
    def CanUse(self, user: 'User', copy: bool) -> bool:
        return user.CheckSunflower() < 10
    async def Use(self, user: 'User') -> None:
        """种植
        success: 是否成功。"""
        if user.CheckSunflower() >= 10:
            user.SendCardUse(self, success = False)
            return
        user.SendCardUse(self, success = True)
        await user.AddStatus(SSunflower130())
class SSunflower130(StatusNullStack):
    name = "向日葵"
    id = 130
    description = "跨日结算时你获得1击毙。场上最多存在十株(双子)向日葵。"
    isReversable = True
    def reverse(self, c: Int):
        return (SSunflower130(c), SInvSunflower125(c))
    async def OnNewDay(self, user: 'User') -> None:
        """获得击毙
        jibi: 获得的击毙。"""
        user.SendStatusEffect(self, jibi = self.count)
        await user.AddJibi(self.count)
    async def OnStatusAdd(self, user: 'User', status: 'Status') -> bool:
        if isinstance(status, SSunflower130):
            status.num = min(status.num, 10 - user.CheckSunflower())
            return status.num == 0
        elif isinstance(status, STwinSunflower133):
            if (u := status.num + user.CheckSunflower()) > 10:
                await user.RemoveStatus(SSunflower130(u - 10))
        return False
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnNewDay: Priority.OnNewDay.sunflower,
            UserEvt.OnStatusAdd: Priority.OnStatusAdd.sunflower}
class SInvSunflower125(StatusNullStack):
    name = "背日葵"
    id = 125
    description = "跨日结算时你损失1击毙。"
    isReversable = True
    def reverse(self, c: Int):
        return (SInvSunflower125(c), SSunflower130(c))
    async def OnNewDay(self, user: 'User') -> None:
        """失去击毙
        jibi: 失去的击毙。
        turn: 转过来的数量。"""
        count = self.count
        await user.AddJibi(-count)
        n = 0
        for i in range(self.count):
            if random.random() > 0.5:
                await user.RemoveStatus(SInvSunflower125(1))
                n += 1
        user.SendStatusEffect(self, jibi = count, turned = n)
        await user.AddStatus(SSunflower130(n))
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnNewDay: Priority.OnNewDay.inv_sunflower}

class CWallnut131(Card):
    name = "坚果墙"
    id = 131
    _description = "种植植物坚果墙：为你吸收死亡时间总计4小时。重复使用将修补坚果墙。"
    positive = 1
    mass = 0.2
    pack = Pack.pvz
    async def Use(self, user: 'User') -> None:
        o = user.CheckStatus(SWallnut131)
        if len(o) > 0:
            o[0].num = 240
            user.data.SaveStatuses()
            user.SendCardUse(self, type = 'mend')
        else:
            await user.AddStatus(SWallnut131(240))
            user.SendCardUse(self, type = 'plant')
class SWallnut131(StatusNumed):
    name = "坚果墙"
    id = 131
    _description = "为你吸收死亡时间。"
    @property
    def description(self):
        # pylint: disable=no-member
        return f"{self._description}\n剩余时间：{self.num}分钟。"
    async def OnDeath(self, user: 'User', killer: Optional['User'], time: int, c: 'AttackType') -> Tuple[int, bool]:
        """抵挡死亡。
        atime: 抵挡的时间。
        dead: 是否死亡"""
        # pylint: disable=no-member
        if c.jump:
            return time, False
        m = min(self.num, time)
        self.num -= m
        time -= m
        dead = (time == 0)
        user.SendStatusEffect(self, atime = m, dead = dead)
        user.data.SaveStatuses()
        return time, dead
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnDeath: Priority.OnDeath.wallnut}

class CIceShroom132(Card):
    name = "寒冰菇"
    id = 132
    positive = -1
    _description = "抽到时种植寒冰菇：今天每个人都需要额外隔一个才能接龙。"
    consumedOnDraw = True
    pack = Pack.pvz
    async def OnDraw(self, user: 'User') -> None:
        await user.ume.AddStatus(SIceShroom132())
class SIceShroom132(StatusDailyStack):
    name = "寒冰菇"
    id = 132
    _description = "今天每个人都需要额外隔一个才能接龙。"
    isDebuff = True
    isGlobal = True
    isReversable = True
    def reverse(self, c: Int):
        return (SIceShroom132(c), SHotShroom90(c))
    async def BeforeDragoned(self, user: 'User', state: 'DragonState') -> Tuple[bool, int]:
        return True, 1
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.BeforeDragoned: Priority.BeforeDragoned.iceshroom}
class SHotShroom90(StatusDailyStack):
    name = "炎热菇"
    id = 90
    _description = "今天每个人都可以少隔一个接龙。"
    isGlobal = True
    isReversable = True
    def reverse(self, c: Int):
        return (SHotShroom90(c), SIceShroom132(c))
    async def BeforeDragoned(self, user: 'User', state: 'DragonState') -> Tuple[bool, int]:
        return True, -1
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.BeforeDragoned: Priority.BeforeDragoned.hotshroom}

class CTwinSunflower133(Card):
    name = "双子向日葵"
    id = 133
    description = "只能在你场上存在向日葵时种植。使你的一株向日葵变成双子向日葵(跨日结算时你获得2击毙)。场上最多存在十株(双子)向日葵。"
    positive = 1
    # failure_message = "你场地上没有“向日葵”" + 句尾
    pack = Pack.pvz
    def CanUse(self, user: 'User', copy: bool) -> bool:
        return user.CheckStatusStack(SSunflower130) != 0
    async def Use(self, user: 'User') -> None:
        """种植
        success: 是否成功。"""
        if user.CheckStatusStack(SSunflower130) == 0:
            user.SendCardUse(self, success = False)
            return
        user.SendCardUse(self, success = True)
        await user.RemoveStatus(SSunflower130())
        await user.AddStatus(STwinSunflower133())
class STwinSunflower133(StatusNullStack):
    name = "双子向日葵"
    id = 133
    description = "跨日结算时你获得2击毙。场上最多存在十株(双子)向日葵。"
    isReversable = True
    def reverse(self, c: Int):
        return (STwinSunflower133(c), SInvSunflower78(c))
    async def OnNewDay(self, user: 'User') -> None:
        """获得击毙
        jibi: 获得的击毙。"""
        user.SendStatusEffect(self, jibi = self.count)
        await user.AddJibi(self.count)
    async def OnStatusAdd(self, user: 'User', status: 'Status') -> bool:
        if isinstance(status, SSunflower130) or isinstance(status, STwinSunflower133):
            status.num = min(status.num, 10 - user.CheckSunflower())
            return status.num == 0
        return False
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnNewDay: Priority.OnNewDay.twinsunflower,
            UserEvt.OnStatusAdd: Priority.OnStatusAdd.twinsunflower}
class SInvSunflower78(StatusNullStack):
    name = "双子背日葵"
    id = 78
    description = "跨日结算时你损失2击毙。"
    isReversable = True
    def reverse(self, c: Int):
        return (SInvSunflower78(c), STwinSunflower133(c))
    async def OnNewDay(self, user: 'User') -> None:
        """失去击毙
        jibi: 失去的击毙。
        turn: 转过来的数量。"""
        count = self.count
        await user.AddJibi(-2 * count)
        n = 0
        for i in range(self.count):
            if random.random() > 0.5:
                await user.RemoveStatus(SInvSunflower125(1))
                n += 1
        user.SendStatusEffect(self, jibi = 2 * count, turned = n)
        await user.AddStatus(STwinSunflower133(n))
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnNewDay: Priority.OnNewDay.inv_twinsunflower}

class CPumpkin134(Card):
    name = "南瓜保护套"
    id = 134
    _description = "种植植物南瓜保护套：为你吸收死亡时间总计6小时。重复使用将修补南瓜保护套。可与坚果墙叠加。"
    positive = 1
    mass = 0.2
    pack = Pack.pvz
    async def Use(self, user: 'User') -> None:
        o = user.CheckStatus(SPumpkin134)
        if len(o) > 0:
            o[0].num = 360
            user.data.SaveStatuses()
            user.SendCardUse(self, type = 'mend')
        else:
            await user.AddStatus(SPumpkin134(360))
            user.SendCardUse(self, type = 'plant')
class SPumpkin134(StatusNumed):
    name = "南瓜保护套"
    id = 134
    _description = "为你吸收死亡时间。"
    @property
    def description(self):
        # pylint: disable=no-member
        return f"{self._description}\n剩余时间：{self.num}分钟。"
    async def OnDeath(self, user: 'User', killer: Optional['User'], time: int, c: 'AttackType') -> Tuple[int, bool]:
        """抵挡死亡。
        atime: 抵挡的时间。
        dead: 是否死亡"""
        # pylint: disable=no-member
        if c.jump:
            return time, False
        m = min(self.num, time)
        self.num -= m
        time -= m
        dead = (time == 0)
        user.SendStatusEffect(self, atime = m, dead = dead)
        user.data.SaveStatuses()
        return time, dead
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnDeath: Priority.OnDeath.pumpkin}

class CImitator135(Card):
    name = "模仿者"
    id = 135
    positive = 0
    description = "你下一张抽到的卡会额外再给你一张。"
    pack = Pack.pvz
    async def Use(self, user: 'User') -> None:
        await user.AddStatus(SImitator135())
class SImitator135(StatusNullStack):
    name = "模仿者"
    id = 135
    description = "你下一张抽到的卡会额外再给你一张。"
    async def AfterCardDraw(self, user: 'User', cards: list['Card']) -> None:
        if self.count > len(cards):
            await user.RemoveStatus(SImitator135(len(cards)))
            to_add = cards
        else:
            await user.RemoveAllStatus(SImitator135)
            to_add = cards[:self.count]
        user.SendStatusEffect(self, cards = [c.DumpData() for c in to_add])
        await user.Draw(cards = to_add)
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.AfterCardDraw: Priority.AfterCardDraw.imitator}

class CJackInTheBox136(Card):
    name = "玩偶匣"
    id = 136
    positive = -1
    _description = "抽到时附加buff：你每次接龙时有5%的几率爆炸，炸死以你为中心5x5的人，然后buff消失。若场上有寒冰菇状态则不会爆炸。"
    consumedOnDraw = True
    isMetallic = True
    pack = Pack.pvz
    async def OnDraw(self, user: 'User') -> None:
        user.SendCardOnDraw(self)
        await user.AddStatus(SJackInTheBox136())
class SJackInTheBox136(StatusNullStack):
    name = "玩偶匣"
    id = 136
    _description = "你每次接龙时有5%的几率爆炸，炸死以你为中心5x5的人，然后buff消失。若场上有寒冰菇状态则不会爆炸。"
    isDebuff = True
    isMetallic = True
    async def OnDragoned(self, user: 'User', branch: 'TreeLeaf', first10: bool) -> None:
        '''炸死好多人
        tqqs：被炸死的玩家QQ'''
        if user.ume.CheckStatus(SIceShroom132):
            return
        if random.random() > 0.95 ** self.count:
            await user.RemoveStatus(SJackInTheBox136())
            qqs = {user.qq}
            id = branch.id
            for i, j in itertools.product(range(-2, 3), range(-2, 3)):
                ret = user.game.FindTree((id[0] + i, id[1] + j))
                if ret is not None:
                    qqs.add(ret.qq)
            qqs -= {user.game.managerQQ}
            user.SendStatusEffect(self, tqqs = list(qqs))
            for qqq in qqs:
                await user.CreateUser(qqq).Killed(user)
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnDragoned: Priority.OnDragoned.jack_in_the_box}

class CBungeeZombie137(Card):
    name = "蹦极僵尸"
    id = 137
    positive = -1
    _description = "抽到时依照优先级移除你的一层植物效果。若你没有植物，则放下一只僵尸，你死亡一个小时。若场上有寒冰菇状态则不会生效。"
    consumedOnDraw = True
    pack = Pack.pvz
    async def OnDraw(self, user: 'User') -> None:
        if user.ume.CheckStatus(SIceShroom132):
            user.SendCardOnDraw(self, flag = "iceshroom")
        elif mag := user.CheckStatus(SMagnetShroom129):
            user.SendCardOnDraw(self, flag = 'magnetshroom')
            await user.RemoveStatus(mag[0])
        elif nut := user.CheckStatus(SWallnut131):
            user.SendCardOnDraw(self, flag = 'wallnut')
            await user.RemoveStatus(nut[0])
        elif user.CheckStatus(STwinSunflower133):
            user.SendCardOnDraw(self, flag = 'twinsunflower')
            await user.RemoveStatus(STwinSunflower133(1))
        elif user.CheckStatus(SSunflower130):
            user.SendCardOnDraw(self, flag = 'sunflower')
            await user.RemoveStatus(SSunflower130(1))
        elif pkn := user.CheckStatus(SPumpkin134):
            user.SendCardOnDraw(self, flag = 'pumpkin')
            await user.RemoveStatus(pkn[0])
        else:
            user.SendCardOnDraw(self, flag = 'zombie')
            await user.Death(minute=60)

class CPoleZombie(Card):
    name = "撑杆跳僵尸"
    id = 138
    positive = -1
    _description = "抽到时击毙你一次，此击毙不会被坚果墙或南瓜保护套阻挡。若场上有寒冰菇状态则不会生效。"
    consumedOnDraw = True
    pack = Pack.pvz
    async def OnDraw(self, user: 'User') -> None:
        if user.ume.CheckStatus(SIceShroom132):
            user.SendCardOnDraw(self, flag = "iceshroom")
        else:
            user.SendCardOnDraw(self, flag = 'success')
            await user.Death(c=AttackType(jump = True))
