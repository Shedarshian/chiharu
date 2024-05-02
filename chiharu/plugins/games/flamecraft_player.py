

class Player:
    def __init__(self, isDummy: bool=False) -> None:
        self.hand: 'list[Dragon]' = []
        self.fancy: 'list[Fancy]' = []
        self.resources: 'dict[Resource, int]' = {}
        for resource in Resource:
            self.resources[resource] = 0
        self.score: int = 0
        self.place: 'Shop | None' = None
        self.isDummy = isDummy

from .flamecraft_resource import Resource
from .flamecraft_artisan import Dragon
from .flamecraft_fancy import Fancy
from .flamecraft_shop import Shop