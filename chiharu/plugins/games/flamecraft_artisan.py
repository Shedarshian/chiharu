from typing import Generator

class Dragon:
    allDragons: 'dict[Resource, type[Dragon]]' = {}
    color: 'Resource'
    def __init_subclass__(cls) -> None:
        Dragon.allDragons[cls.color] = cls
    def __init__(self, parent: 'Player | Board | Shop', isStarter: bool=False) -> None:
        self.parent = parent
        self.isStarter = isStarter
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
        return
        yield

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
        player.board.state = State.ChooseDiamondArtisan
        last_err: int = 0
        while 1:
            ret = yield Send(last_err)
            assert isinstance(ret, RecieveResources)
            if len(ret.resources) > 3:
                last_err = -1
                continue
            if not all(x == 1 for x in ret.resources.values()):
                last_err = -2
                continue
            player.addResources(ret.resources)
            break
        yield from player.board.dragons[0].ability(player)

class DragonPlant:
    color = Resource.Plant
    def ability(self, player: Player) -> 'TAsync[None]':
        return
        yield
