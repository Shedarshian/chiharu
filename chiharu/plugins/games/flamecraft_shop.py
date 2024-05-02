from typing import Literal, Generator
from abc import abstractmethod
from collections import defaultdict

class Slot:
    def __init__(self, award: 'Award | None'=None) -> None:
        self.award: 'Award' = award or Award()
    def fill(self, player: 'Player') -> Generator: # TODO
        return
        yield
class DragonSlot(Slot):
    def __init__(self, dragonType: 'tuple[Resource, ...]' = (), award: 'Award | None' = None) -> None:
        self.dragonType = dragonType
        super().__init__(award)
class Coin2Slot(Slot):
    def __init__(self, award: 'Award | None' = None) -> None:
        self.filled: bool = False
        super().__init__(award)

class Shop:
    allShops: 'dict[Resource, list[type[Shop]]]' = defaultdict(list)
    isStarter: int = 0 # 1为起始商店，2为另一组起始商店，会自动初始化槽位和能力
    canSpell: bool = True
    resource: "Resource | Literal['Wild'] | Literal['Three'] | Literal['Dragon'] | None" = None
    slot1: Slot
    slot2: Slot
    slot3: Slot
    def __init_subclass__(cls) -> None:
        if cls.__name__ == 'AltStarterShop': # 排除掉基类
            return
        if isinstance(cls.resource, Resource):
            Shop.allShops[cls.resource].append(cls)
        else:
            Shop.allShops[Resource.Coin].append(cls)
        if cls.isStarter == 1:
            assert isinstance(cls.resource, Resource)
            cls.slot1 = DragonSlot()
            cls.slot2 = DragonSlot((cls.resource, Resource((cls.resource + 1) % 6)), Award(coin=1))
            cls.slot3 = DragonSlot((Resource((cls.resource + 1) % 6),), Award(fancy=1))
        elif cls.isStarter == 2:
            pass # TODO
    def __init__(self) -> None:
        self.dragons: list[Dragon | None] = [None, None, None]
        if self.isStarter > 0:
            assert isinstance(self.resource, Resource)
            dragon = Dragon.get(self.resource)(self, True)
            self.dragons[0] = dragon
        self.spells: list[Spell] = []
        self.players: list[Player] = []
    def getSlot(self, i: int):
        return (self.slot1, self.slot2, self.slot3)[i]
    def getDragon(self, i: int):
        return self.dragons[i]
    def special(self, player: 'Player') -> Generator:
        return
        yield

from flamecraft_resource import Resource, Award, Spell

class DracoBell(Shop):
    isStarter = 1
    resource = Resource.Meat
class CryticalRolls(Shop):
    isStarter = 1
    resource = Resource.Bread
class PortablePotions(Shop):
    isStarter = 1
    resource = Resource.Potion
class FragileReptile(Shop):
    isStarter = 1
    resource = Resource.Crystal
class HelloNursery(Shop):
    isStarter = 1
    resource = Resource.Plant
class SmithMart(Shop):
    isStarter = 1
    resource = Resource.Iron
class AltStarterShop(Shop): # 所有另一组起始商店的基类，因为它们的特殊行为一样所以合并
    isStarter = 2
    def special(self, player: 'Player') -> Generator:
        return super().special(player) # TODO

from flamecraft_artisan import Dragon
from flamecraft_player import Player