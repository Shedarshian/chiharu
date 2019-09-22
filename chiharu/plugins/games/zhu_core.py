import asyncio
from .cardboard import CardGame

Zhu = CardGame()

class ActionCard(Zhu.Card('Action')):
    pass

class YingLi(ActionCard, num=4):
    name = '盈利'
    description = '摸两张行动牌。'
    def usage(self):
        return {}
    def use(self, player):
        player.draw_action(2)

class ZhuBoard(Zhu.Board):
    def __init__(self):
        pass