from typing import *
from .Helper import HasId

class Mission(HasId, hasIdDict=True):
    description = "NoDes"
    inQuestStone = True
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
