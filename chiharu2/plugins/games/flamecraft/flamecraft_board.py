import more_itertools

class Board:
    def __init__(self, player_num: int) -> None:
        self.shops: 'list[Shop]' = []
        self.shopDeck: 'list[Shop]' = []
        self.players = [Player(i, self) for i in range(player_num)]
        self.park: 'list[Dragon]' = []
        self.dragonDeck: 'list[Dragon]' = []
        self.fancys: 'list[Fancy]' = []
        self.spells: 'list[Spell]' = []
        self.spellDeck: 'list[Spell]' = []
        self.state: State = State.End
    def popDragons(self, l: list[int]) -> 'list[Dragon] | None':
        l.sort()
        if not all(0 <= i <= len(self.park) for i in l) or not more_itertools.all_unique(i for i in l if i < len(self.park)):
            return None
        drs = [self.park[i] for i in l if 0 <= i < len(self.park)]
        n = sum(1 for i in l if i == len(self.park))
        if n > len(self.dragonDeck):
            return []
        for dr in drs:
            self.park.remove(dr)
        drs.extend(self.dragonDeck.pop(0) for _ in range(n))
        return drs
    def getShop(self, i: int) -> 'Shop | None':
        if 0 <= i < len(self.shops):
            return self.shops[i]
        return None

from .flamecraft_shop import Shop
from .flamecraft_player import Player
from .flamecraft_artisan import Dragon
from .flamecraft_fancy import Fancy
from .flamecraft_resource import Resource, State, Spell
