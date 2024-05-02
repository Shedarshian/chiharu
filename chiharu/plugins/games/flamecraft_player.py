from collections import Counter

class Player:
    def __init__(self, board: 'Board', isDummy: bool=False) -> None:
        self.hand: 'list[Dragon]' = []
        self.fancy: 'list[Fancy]' = []
        self.resources: 'Counter[Resource]' = Counter()
        for resource in Resource:
            self.resources[resource] = 0
        self.score: int = 0
        self.place: 'Shop | None' = None
        self.isDummy = isDummy
        self.board = board
    def addResource(self, resource: 'Resource'):
        self.resources[resource] += 1
    def addResources(self, resources: 'Counter[Resource]'):
        self.resources.update(resources)

from .flamecraft_resource import Resource
from .flamecraft_artisan import Dragon
from .flamecraft_fancy import Fancy
from .flamecraft_shop import Shop
from .flamecraft_board import Board