from abc import ABC, abstractmethod
from typing import Awaitable
import asyncio
import functools
import random

# example usage for CardGame:
# Zhu = CardGame()
#
# class ZhuBoard(Zhu.Board):
#     pass # need to implement __init__(), process()
#
# class ActionCard(Zhu.Card('Action')):
#     pass
#     # can get card deck by deck = ActionCard.deck or Zhu.Deck('Action')
#     # can use deck.draw(), deck.shuffle(), can set deck.on_empty = _f or more
#
# class GuaBiao(ActionCard, name='挂裱', num=1):
#     pass # need to implement property(description()), usage(), use()

class Deck:
    def __init__(self, card_cls):
        self._card_cls = card_cls
        self._card_list = []
        self._deck_num = []
        self._deck = [] # end means the upper most card in deck. saves id.
        self._discard = []
    def _add_init_card(self, Card_cls, num):
        Card_cls._id = len(self._card_list)
        self._card_list.append(Card_cls)
        self._deck_num.append(num)
    def begin(self):
        for id, num in enumerate(self._deck_num):
            for i in range(num):
                self._deck.append(id)
        random.shuffle(self._deck)
    @property
    def is_empty(self):
        return len(self._deck) == 0
    def shuffle(self):
        random.shuffle(self._deck)
    def collect_discard(self):
        self._deck.extend(self._discard)
        self._discard = []
    def on_empty(self):
        '''things auto done when empty. default = collect_discard and shuffle.'''
        #if len(self._discard) == 0:
        self.collect_discard()
        self.shuffle()
    def draw(self, reverse=False):
        if self.is_empty:
            self.on_empty()
            if self.is_empty:
                # if remain empty after on_empty then return None
                return None
        if reverse:
            return self._card_list[self._deck.pop(0)]
        else:
            return self._card_list[self._deck.pop()]
    def peek(self, reverse=False):
        if self.is_empty:
            self.on_empty()
            if self.is_empty:
                # if remain empty after on_empty then return None
                return None
        if reverse:
            return self._card_list[self._deck[0]]
        else:
            return self._card_list[self._deck[-1]]
    def discard(self, card):
        self._discard.append(card._id)
    def peek_discard(self):
        if len(self._discard) == 0:
            return None
        else:
            return self._card_list[self._discard[-1]]
    def put_back(self, card, reverse=False):
        if reverse:
            self._deck = [card._id] + self._deck
        else:
            self._deck.append(card._id)
class CardGame:
    def __init__(self):
        class _board(ABC):
            @abstractmethod
            def __init__(self, *args, **kwargs):
                '''need to shuffle decks and something.'''
                #TODO player assign
            @abstractmethod
            async def process(self, *args, **kwargs):
                '''write it yourself.'''
            def next_player(self):
                pass # TODO default behaviour
        self.Board = _board
        class _player(ABC):
            response_dict = {}
            @abstractmethod
            def __init__(self, *args, **kwargs):
                '''need i/o set.'''
            @abstractmethod
            async def round(self, *args, **kwargs):
                '''player's round. generally need to call some other stages.'''
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
        self._deck = {}
    def Card(self, deck_name):
        class _card(ABC):
            _game = self
            deck = self._deck
            _deck_name = deck_name
            def __init_subclass__(child, **kwargs):
                super().__init_subclass__(**kwargs)
                @classmethod
                def _(grandchild, num=0):
                    _card.deck[_card._deck_name]._add_init_card(grandchild, num)
                child.__init_subclass__ = _
            name = 'NoName'
            description = 'NoDescription'
            @abstractmethod
            def usage(self):
                '''return the args needed to be assigned'''
            @abstractmethod
            def use(self, player, **kwargs):
                '''use the card on kwargs which is given by self.usage()'''
        _deck = Deck(_card)
        self._deck[deck_name] = _deck
        return _card
    def Deck(self, name):
        return self._deck[name]

