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
from .Dragon import DragonState, Tree
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
        if self.time < datetime.now():
            user.SendStatusEffect(self)
            self.time = datetime.now() + timedelta(days=1)
            atk = AMagnetShroom129(user.attack.attacker)
            await attack.attacker.attacked(atk)
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
    @property
    def CanUse(self, user: 'User', copy: bool) -> bool:
        return (user.CheckStatusStack(SSunflower130) + user.CheckStatusStack(STwinSunflower133)<10)
    async def Use(self, user: 'User') -> None:
        ss = user.CheckStatusStack(SSunflower130) + user.CheckStatusStack(STwinSunflower133)
        if ss >= 10:
            user.SendCardUse(self, success = False)
            return
        user.SendCardUse(self, success = True)
        await user.AddStatus(SSunflower130())
class SSunflower130(StatusNullStack):
    name = "向日葵"
    id = 130
    description = "跨日结算时你获得1击毙。场上最多存在十株(双子)向日葵。"
    async def OnNewDay(self, user: 'User') -> None:
        user.SendStatusEffect(self, jibi = self.count)
        await user.AddJibi(self.count)
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnNewDay: Priority.OnNewDay.sunflower}
class SInvSunflower125(StatusNullStack):
    name = "背日葵"
    id = 125
    description = "跨日结算时你损失1击毙。"
    async def OnNewDay(self, user: 'User') -> None:
        count = self.count
        await user.AddJibi(-count)
        n = 0
        for i in range(self.count):
            if random.random() > 0.5:
                await user.RemoveStatus(SInvSunflower125(1))
                n += 1
        user.SendStatusEffect(self, jibi = count, turned = n)
        for i in range(n):
            if user.CheckStatusStack(SSunflower130) + user.CheckStatusStack(STwinSunflower133) < 10:
                await user.AddStatus(SSunflower130())
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
            user.SaveStatuses()
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
        return f"{self._description}\n剩余时间：{self.num}分钟。"
    async def OnDeath(self, user: 'User', killer: Optional['User'], time: int, c: 'AttackType') -> Tuple[int, bool]:
        if c.jump:
            return time, False
        m = min(self.num, time)
        self.num -= m
        time -= m
        dead = (time == 0)
        user.SendStatusEffect(self, atime = m, dead = dead)
        user.SaveStatuses()
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
    async def BeforeDragoned(self, user: 'User', state: 'DragonState') -> Tuple[bool, int]:
        return True, 1
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.BeforeDragoned: Priority.BeforeDragoned.iceshroom}
class SHotShroom90(StatusDailyStack):
    name = "炎热菇"
    id = 90
    _description = "今天每个人都可以少隔一个接龙。"
    isGlobal = True
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
    @property
    def CanUse(self, user: 'User', copy: bool) -> bool:
        return (user.CheckStatusStack(SSunflower130)!=0)
    async def Use(self, user: 'User') -> None:
        if user.CheckStatusStack(SSunflower130)==0:
            user.SendCardUse(self, success = False)
            return
        user.SendCardUse(self, success = True)
        await user.RemoveStatus(SSunflower130())
        await user.AddStatus(STwinSunflower133())
class STwinSunflower133(StatusNullStack):
    name = "双子向日葵"
    id = 133
    description = "跨日结算时你获得2击毙。场上最多存在十株(双子)向日葵。"
    async def OnNewDay(self, user: 'User') -> None:
        user.SendStatusEffect(self, jibi = self.count)
        await user.AddJibi(self.count)
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnNewDay: Priority.OnNewDay.twinsunflower}
class SInvSunflower78(StatusNullStack):
    name = "双子背日葵"
    id = 78
    description = "跨日结算时你损失2击毙。"
    async def OnNewDay(self, user: 'User') -> None:
        count = self.count
        await user.AddJibi(-2*count)
        n = 0
        for i in range(self.count):
            if random.random() > 0.5:
                await user.RemoveStatus(SInvSunflower125(1))
                n += 1
        user.SendStatusEffect(self, jibi = to_add, turned = n)
        for i in range(n):
            if user.CheckStatusStack(SSunflower130) + user.CheckStatusStack(STwinSunflower133) >= 10:
                await user.RemoveStatus(SSunflower130())
            await user.AddStatus(STwinSunflower133())
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
            user.SaveStatuses()
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
        return f"{self._description}\n剩余时间：{self.num}分钟。"
    async def OnDeath(self, user: 'User', killer: Optional['User'], time: int, c: 'AttackType') -> Tuple[int, bool]:
        if c.jump:
            return time, False
        m = min(self.num, time)
        self.num -= m
        time -= m
        dead = (time == 0)
        user.SendStatusEffect(self, atime = m, dead = dead)
        user.SaveStatuses()
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
        user.AddStatus(SImitator135())
class SImitator135(StatusNullStack):
    name = "模仿者"
    id = 135
    description = "你下一张抽到的卡会额外再给你一张。"
    async def AfterCardDraw(self, user: 'User', cards: Iterable['Card']) -> None:
        if self.count > len(cards):
            await user.RemoveStatus(SImitator135(len(cards)))
            to_add = cards
        else:
            await user.RemoveAllStatus(SImitator135)
            to_add = cards[:count]
        user.SendStatusEffect(self. cards = [c.DumpData() for c in to_add])
        await user.Draw(cards = to_add)
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.AfterCardDraw: Priority.AfterCardDraw.imitator}
