from typing import *
from .Helper import HasId

class Mission(HasId):
    description = "NoDes"
    inQuestStone = True
    def check(self, s: str) -> bool:
        return False

class Mission0(Mission):
    description = "字数为2"
    def check(self, s: str) -> bool:
        return len(s) == 2
