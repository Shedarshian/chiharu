from typing import *
from .Card import Card
from .User import User
from .Status import Status, StatusNumed, StatusTimed, StatusNullStack, StatusDailyStack
from .Attack import Attack, AttackType
from .Priority import UserEvt, Priority
if TYPE_CHECKING:
    from .Dragon import DragonState

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