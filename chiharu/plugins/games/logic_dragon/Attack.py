from typing import *
from abc import ABC, abstractmethod
from dataclasses import dataclass
from .Helper import BuildIdMeta
if TYPE_CHECKING:
    from .User import User

TAttack = TypeVar("TAttack", bound="Attack")
TAttackType = Type[TAttack]
class Attack(metaclass=BuildIdMeta):
    id = -1
    idDict: dict[int, TAttackType] = {}
    name = "NoName"
    doublable = True
    reboundable = True
    def __init__(self, attacker: 'User', defender: 'User'):
        self.attacker = attacker
        self.defender = defender
        self.rebounded = False
        self.multiplier = 1
        self.counter = AttackType()
    @abstractmethod
    async def selfAction(self):
        pass
    @final
    async def action(self):
        if self.rebounded:
            self.rebounded = False
            await self.defender.Attacked(self)
        else:
            await self.selfAction()
    def __repr__(self):
        return f"<攻击类型：{self.name}，攻击者：{self.attacker.qq}，被攻击者：{self.defender.qq}，倍数：{self.multiplier}，c：{self.counter}>"
    def double(self) -> bool:
        """return True if double equals dodge."""
        self.multiplier *= 2
        return False
    def rebound(self) -> bool:
        """return True if rebound equals dodge."""
        self.attacker, self.defender = self.defender, self.attacker
        self.counter = AttackType()
        self.rebounded = True
        return False

async def nothing(): return False

@dataclass
class AttackType:
    pierce: Callable = nothing
    jump: bool = False
    hpzero: bool = False
