
class Board:
    def __init__(self, player_num: int) -> None:
        self.shops: 'list[Shop]' = []
        self.players = [Player(self) for i in range(player_num)]
        self.dragons: 'list[Dragon]' = []
        self.fancys: 'list[Fancy]' = []
        self.state: State = State.End
    def getShop(self, i: int):
        if 0 <= i < len(self.shops):
            return self.shops[i]
        return None

from .flamecraft_shop import Shop
from .flamecraft_player import Player
from .flamecraft_artisan import Dragon
from .flamecraft_fancy import Fancy
from .flamecraft_resource import Resource, State
