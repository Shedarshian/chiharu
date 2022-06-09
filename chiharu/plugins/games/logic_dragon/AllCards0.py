from typing import *
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
