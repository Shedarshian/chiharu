from typing import Generator

class Dragon:
    allDragons: 'dict[Resource, type[Dragon]]' = {}
    color: 'Resource'
    def __init_subclass__(cls) -> None:
        Dragon.allDragons[cls.color] = cls
    def ability(self, player: 'Player') -> Generator:
        return
        yield

from .flamecraft_resource import Resource
from .flamecraft_player import Player

class DragonBread:
    color = Resource.Bread
    def ability(self, player: Player) -> Generator:
        return
        yield

