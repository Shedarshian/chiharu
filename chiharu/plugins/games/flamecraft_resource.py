from enum import IntEnum, auto
from dataclasses import dataclass

class Resource(IntEnum):
    Bread = 0
    Meat = 1
    Iron = 2
    Potion = 3
    Crystal = 4
    Plant = 5
    Coin = -1

@dataclass
class Award:
    point: int = 0
    coin: int = 0
    fancy: int = 0
    dragon: int = 0

@dataclass
class Spell:
    type: Resource
    price: dict[Resource, int]
    award: Award
    noCoin: bool = False

