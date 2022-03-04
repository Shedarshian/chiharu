from typing import *
from .Helper import HasId

class Mission(HasId):
    description = "NoDes"
    def check(self, s: str) -> bool:
        return False
