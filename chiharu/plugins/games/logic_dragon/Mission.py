from typing import *
import random
from .Helper import HasId

class Mission(HasId, hasIdDict=True):
    description = "NoDes"
    inQuestStone = True
    @classmethod
    def RandomQuestStoneId(cls):
        return random.choice([i for i, t in cls.idDict.items() if t.inQuestStone])
    def check(self, s: str) -> bool:
        return False

for i in range(0, 7):
    class _(Mission):
        id = i
        description = f"字数为{2 + i}"
        inQuestStone = True
        def check(self, s: str) -> bool:
            return len(s) == 2 + self.id
    _.__name__ = f"Mission{i}"
