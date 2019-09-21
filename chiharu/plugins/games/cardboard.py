from abc import ABC, abstractmethod
from typing import Awaitable
import asyncio
import functools

# example usage for CardGame:
# Zhu = CardGame()
#
# class ZhuBoard(Zhu.Board):
#     pass
#
# class ActionCard(Zhu.Card('Action')):
#     pass
#     # can get card deck by deck = ActionCard.Deck
#     # can use deck.draw(), deck.shuffle(), can set deck.empty = _f(default=shuffle) or more
#
# class ZhuPlayer(Zhu.Player):
#     pass

class CardGame:
    def __init__(self):
        class _board(ABC):
            @abstractmethod
            def __init__(self, *args, **kwargs):
                '''need to shuffle decks and something.'''
                #TODO player assign
                pass
            @abstractmethod
            async def process(self, *args, **kwargs):
                '''write it yourself.'''
                pass
            def next_player(self):
                pass # TODO default behaviour
        self.Board = _board
        class _player(ABC):
            response_dict = {}
            @abstractmethod
            def __init__(self, *args, **kwargs):
                '''need i/o set.'''
                pass
            @abstractmethod
            async def round(self, *args, **kwargs):
                '''player's round. generally need to call some other stages.'''
                pass
            def response(self, name):
                def _(f: Awaitable):
                    @functools.wraps(f)
                    async def _f():
                        return await f() # TODO something need to be done?
                    self.response_dict[name] = _f
                    return _f
                return _
            async def wait(self, name):
                return await self.response_dict[name]()
        self.Player = _player
    def Card(self, name):
        class _card(ABC):
            #def __init_subclass__(cls,)
            @abstractmethod
            def usage(self):
                '''return the args needed to be assigned'''
                pass
            @abstractmethod
            def use(self, **kwargs):
                '''use the card on kwargs which is given by self.usage()'''
                pass
        return _card

