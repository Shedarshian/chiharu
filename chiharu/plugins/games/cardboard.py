from abc import ABC, abstractmethod
from typing import Awaitable, Dict, Any
import asyncio
from asyncio import Queue
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
#     # need to implement usage(), use(**args)
#     # can get card deck by deck = ActionCard.deck or Zhu.Deck('Action') or ZhuBoard.Deck(self, 'Action')
#     # can use deck.draw(), deck.shuffle(), can set deck.on_empty = _f or more
#
# class GuaBiao(ActionCard, name='挂裱', num=1):
#     pass # need to implement property(description()), usage(), use()
#
# class ZhuPlayer(Zhu.Player):
#     response = ['on_scale_up'] # need to be inited after Board
#     # so can use board.on_scale_up() to call players' on_scale_up()
#     # so player need to implement/assign on_scale_up() ※IMPORTANT: need to except asyncio.CancelledError
#     pass # need to implement player.round()
#     # can use player.wait()

async def Nothing(*args, **kwargs):
    pass

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
            def __init_subclass__(cls):
                self._board_class = cls
                cls._game = self
            @abstractmethod
            def __init__(self2, player_num, *args, **kwargs):
                '''need to shuffle decks and something.'''
                self2.players = [self2._game._player_class(id=i, board=self) for i in range(player_num)]
                self2.current_player_id = 0
            def Deck(self2, name):
                return self2._game._deck[name]
            @property
            def current_player(self2):
                return self2.players[self2.current_player_id]
            def next_player(self2, *args, **kwargs):
                '''default behaviour.'''
                self2.current_player_id += 1
                if self2.current_player_id == len(self2.players):
                    self2.current_player_id = 0
            @abstractmethod
            async def process(self2, *args, **kwargs):
                '''write it yourself.'''
        self.Board = _board
        class _player(ABC):
            def __init_subclass__(cls):
                self._player_class = cls
                cls._game = self
                try:
                    responses = cls.responses
                except AttributeError:
                    responses = []
                for s in responses:
                    async def _(self, *args, **kwargs):
                        tasks = []
                        for player in self.players:
                            tasks.append(asyncio.create_task(player.__getattr__(s)(*args, **kwargs)))
                        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
                        for task in pending:
                            task.cancel()
                    _.__name__ = s
                    setattr(self._board_class, s, _)
                    if s not in cls.__dict__:
                        setattr(cls, s, Nothing)
                try:
                    responses = cls.self_responses
                except AttributeError:
                    responses = []
                for s in responses:
                    if s not in cls.__dict__:
                        setattr(cls, s, Nothing)
            @abstractmethod
            def __init__(self2, id, board, *args, **kwargs):
                '''need i/o set.'''
                self2.id = id
                self2.board = board
                self2.queue_in = Queue(1)
                self2.queue_out = Queue(1)
            def response(self2, name):
                def _(f: Awaitable):
                    @functools.wraps(f)
                    async def _f():
                        return await f() # TODO something need to be done?
                    return _f
                return _
            async def wait(self2, data: Dict[str, Any]):
                self2.queue_out.put_nowait(data)
                return await self2.queue_in.get()
            @abstractmethod
            async def round(self2, *args, **kwargs):
                '''player's round. generally need to call some other stages.'''
        self.Player = _player
        self._deck = {}
    def Card(self, deck_name):
        class _card(ABC):
            _game = self
            _deck_name = deck_name
            def __init_subclass__(child):
                @classmethod
                def _(grandchild, num=0):
                    _card.deck._add_init_card(grandchild, num)
                child.__init_subclass__ = _
            name = 'NoName'
            description = 'NoDescription'
            @abstractmethod
            def usage(self2):
                '''return the args needed to be assigned'''
            @abstractmethod
            async def use(self2, player, **kwargs):
                '''use the card on kwargs which is given by self.usage()'''
        _deck = Deck(_card)
        self._deck[deck_name] = _deck
        _card.deck = _deck
        return _card
    def Deck(self, name):
        return self._deck[name]

