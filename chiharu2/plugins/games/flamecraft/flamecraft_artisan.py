from typing import Generator

class Dragon:
    allDragons: 'dict[Resource, type[Dragon]]' = {}
    color: 'Resource'
    def __init_subclass__(cls) -> None:
        Dragon.allDragons[cls.color] = cls
    def __init__(self, parent: 'Player | Board | Shop', isStarter: bool=False) -> None:
        self.parent = parent
        self.isStarter = isStarter
        self.goods: int = 0
    def setParent(self, parent: 'Player | Board | Shop'):
        self.parent = parent
    def ability(self, player: 'Player') -> 'TAsync[None]':
        return
        yield
    @classmethod
    def get(cls, type: 'Resource'):
        return cls.allDragons[type]

from .flamecraft_resource import Resource, TAsync
from .flamecraft_player import Player
from .flamecraft_shop import Shop
from .flamecraft_board import Board

class DragonBread:
    color = Resource.Bread
    def ability(self, player: Player) -> 'TAsync[None]':
        l = yield from player.chooseDragonStack(1)
        yield from player.drawDragon(l)

class DragonMeat:
    color = Resource.Meat
    def ability(self, player: Player) -> 'TAsync[None]':
        return
        yield

class DragonIron:
    color = Resource.Iron
    def ability(self, player: Player) -> 'TAsync[None]':
        return
        yield

class DragonPotion:
    color = Resource.Potion
    def ability(self, player: Player) -> 'TAsync[None]':
        return
        yield

class DragonCrystal:
    color = Resource.Crystal
    def ability(self, player: Player) -> 'TAsync[None]':
        from .flamecraft_resource import State, Send, RecieveResources
        player.board.state = State.ChooseCrystalArtisan
        last_err: int = 0
        while 1:
            ret = yield Send(last_err)
            assert isinstance(ret, RecieveResources)
            if len(ret.resources) > 3:
                last_err = -1 # 选择多于三种
                continue
            if not all(x == 1 for x in ret.resources.values()):
                last_err = -2 # 选择同一种多于一个
                continue
            player.addResources(ret.resources)
            break

class DragonPlant:
    color = Resource.Plant
    def ability(self, player: Player) -> 'TAsync[None]':
        return
        yield
