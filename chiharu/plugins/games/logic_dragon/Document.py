from io import TextIOWrapper
from .Priority import UserEvt
from .Card import Card

def DocGen(f: TextIOWrapper):
    f.write("\n")
    for id, card in Card.idDict.items():
        for c in UserEvt:
            if c.name in card.__dict__:
                pass