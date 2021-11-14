import itertools, hashlib
import random, more_itertools, json, re
from typing import Any, Awaitable, Callable, Coroutine, Dict, Generic, Iterable, List, NamedTuple, Optional, Set, Tuple, Type, TypeVar, TypedDict, Union, final, Iterable, Annotated
from collections import Counter, UserDict, UserList, defaultdict
from functools import lru_cache, partial, wraps
from struct import unpack, pack
from copy import copy, deepcopy
from dataclasses import dataclass, astuple, field
from math import ceil, log
from abc import ABC, ABCMeta, abstractmethod
from datetime import date, datetime, timedelta
from functools import reduce, wraps
from contextlib import asynccontextmanager
from nonebot.command import CommandSession
from pypinyin import pinyin, Style
from nonebot.command.argfilter import extractors, validators
from .. import config
from .logic_dragon_type import NotActive, TGlobalState, TUserData, TCounter, CounterOnly, UserEvt, Priority, TBoundIntEnum, async_data_saved, check_active, nothing, TQuest, ensure_true_lambda, check_handcard, TModule, UnableRequirement, check_if_unable

# TODO change TCount to a real obj, in order to unify 'count' and 'count2' in OnStatusAdd, also _status.on_add
# TODO 在aget的时候如果发现手牌数不足使用条件则跳出结算
with open(config.rel('dragon_state.json'), encoding='utf-8') as f:
    global_state: TGlobalState = json.load(f)
def save_global_state():
    with open(config.rel('dragon_state.json'), 'w', encoding='utf-8') as f:
        f.write(json.dumps(global_state, indent=4, separators=(',', ': '), ensure_ascii=False))
quest_print_aux: Dict[int, int] = {qq: 0 for qq in global_state['quest'].keys()}
module_print_aux: Dict[int, int] = {qq: 0 for qq in global_state['module'].keys()}

# global_status : qq = 2711644761
def find_or_new(qq: int):
    if qq == 0:
        config.logger.dragon << "【WARNING】试图find qq=0的node。"
    t = config.userdata.execute("select * from dragon_data where qq=?", (qq,)).fetchone()
    if t is None:
        extra_data_init = me.extra.data
        config.userdata.execute('insert into dragon_data (qq, jibi, draw_time, today_jibi, today_keyword_jibi, death_time, card, status, daily_status, status_time, card_limit, shop_drawn_card, event_pt, spend_shop, equipment, event_stage, event_shop, extra_data, dead) values (?, 0, 0, 10, 10, ?, ?, ?, ?, ?, 4, 1, 0, 0, ?, 0, 0, ?, false)', (qq, '', '', '', '', '[]', '{}', extra_data_init))
        t = config.userdata.execute("select * from dragon_data where qq=?", (qq,)).fetchone()
    return t

T_card = TypeVar('T_card', bound='_card')
TCard = Type[T_card]
T_status = TypeVar('T_status', bound='_status')
TStatus = Type[T_status]
T_statusnull = TypeVar('T_statusnull', bound='_statusnull')
TNStatus = Type[T_statusnull]
T_statusdaily = TypeVar('T_statusdaily', bound='_statusdaily')
TDStatus = Type[T_statusdaily]
TStatusAll = Union[T_status, TNStatus, TDStatus]
T_equipment = TypeVar('T_equipment', bound='_equipment')
TEquipment = Type[T_equipment]
TIEventListener = TypeVar('TIEventListener', bound='IEventListener')
TEventListener = Type[TIEventListener]
TCount = Union[int, list[T_status]]

TEventList = dict[int, CounterOnly[TEventListener, TCount]]
TEvent = Tuple[int, TEventListener]
newday_check: List[set[str]] = [set(), set(), set(), set()]
class IEventListener:
    @classmethod
    async def OnUserUseCard(cls, count: TCount, user: 'User', card: TCard) -> Tuple[bool, str]:
        """Called before a user intend to use a card.

        Arguments:
        card: The card to be used.

        Returns:
        bool: represents whether the card can be used;
        str: failure message."""
        pass
    @classmethod
    async def BeforeCardUse(cls, count: TCount, user: 'User', card: TCard) -> Tuple[Optional[Awaitable]]:
        """Called After a card is used in any cases. Includes cards consumed when drawn.

        Arguments:
        card: The card used.
        
        Returns:
        Optional[Awaitable]: if not None, replace the card use."""
        pass
    @classmethod
    async def AfterCardUse(cls, count: TCount, user: 'User', card: TCard) -> Tuple[()]:
        """Called After a card is used in any cases.

        Arguments:
        card: The card used."""
        pass
    @classmethod
    async def AfterCardDraw(cls, count: TCount, user: 'User', cards: Iterable[TCard]) -> Tuple[()]:
        """Called after cards are drawn.

        Parameters:
        cards: The cards drawn."""
        pass
    @classmethod
    async def AfterCardDiscard(cls, count: TCount, user: 'User', cards: Iterable[TCard]) -> Tuple[()]:
        """Called after cards are discarded.

        Parameters:
        cards: The cards discarded."""
        pass
    @classmethod
    async def AfterCardRemove(cls, count: TCount, user: 'User', cards: Iterable[TCard]) -> Tuple[()]:
        """Called after cards are removed.

        Parameters:
        cards: The cards removed."""
        pass
    @classmethod
    async def AfterExchange(cls, count: TCount, user: 'User', user2: 'User') -> Tuple[()]:
        """Called after cards are exchanged.

        Parameters:
        user2: The user that cards are exchanged."""
        pass
    @classmethod
    async def OnDeath(cls, count: TCount, user: 'User', killer: 'User', time: int, c: TCounter) -> Tuple[int, bool]:
        """Called when a user is dead.
        
        Arguments:
        killer: Who killed Cock Robin?
        time: The death time, in minute.
        c: The counter object represents the attack result.
        
        Returns:
        int: modified death time;
        bool: represents whether the death is dodged."""
        pass
    @classmethod
    async def OnAttack(cls, count: TCount, user: 'User', attack: 'Attack', c: TCounter) -> Tuple[bool]:
        """Called when a user attack other.

        Arguments:
        attack: the Attack object.
        c: The counter object represents the attack result, mutable.

        Returns:
        bool: represents whether the attack is dodged."""
        pass
    @classmethod
    async def OnAttacked(cls, count: TCount, user: 'User', attack: 'Attack', c: TCounter) -> Tuple[bool]:
        """Called when a user is attacked.

        Arguments:
        attack: the Attack object.
        c: The counter object represents the attack result, mutable.

        Returns:
        bool: represents whether the attack is dodged."""
        pass
    @classmethod
    async def OnDodged(cls, count: TCount, user: 'User') -> Tuple[()]:
        pass
    @classmethod
    async def OnStatusAdd(cls, count: TCount, user: 'User', status: TStatusAll, count2: int) -> Tuple[int]:
        """Called when a status is added.
        
        Arguments:
        status: Statusnull/Statusdaily, or a T_status object.
        count2: the count of the status added.
        
        Returns:
        int: the count of the status really add."""
        pass
    @classmethod
    async def OnStatusRemove(cls, count: TCount, user: 'User', status: TStatusAll, remove_all: bool) -> Tuple[bool]:
        """Called when a status is removed.
        
        Arguments:
        status: a str for statusnull/statusdaily, or a T_status object.
        remove_all: if remove all this state.
        
        Returns:
        bool: whether the removement is dodged."""
        pass
    @classmethod
    async def CheckJibiSpend(cls, count: TCount, user: 'User', jibi: int) -> Tuple[int]:
        """Called when a user intended to use jibi to buy something.

        Arguments:
        jibi: the amount of jibi needed to buy. always positive.

        Returns:
        int: the modified amount of jibi needed to buy."""
        pass
    @classmethod
    async def OnJibiChange(cls, count: TCount, user: 'User', jibi: int, is_buy: bool) -> Tuple[int]:
        """Called when a user added some jibi or decreased some jibi.

        Arguments:
        jibi: the amount of jibi to add.
        is_buy: True if the decreasement is a buying. A buying will not hold if
            jibi + user.jibi < 0.

        Returns:
        int: the modified amount of jibi to add."""
        pass
    @classmethod
    async def CheckEventptSpend(cls, count: TCount, user: 'User', event_pt: int) -> Tuple[int]:
        """Called when a user intended to use event_pt to buy something.

        Arguments:
        event_pt: the amount of event_pt needed to buy. always positive.

        Returns:
        int: the modified amount of event_pt needed to buy."""
        pass
    @classmethod
    async def OnEventptChange(cls, count: TCount, user: 'User', event_pt: int, is_buy: bool) -> Tuple[int]:
        """Called when a user added some event_pt or decreased some event_pt.

        Arguments:
        event_pt: the amount of event_pt to add.
        is_buy: True if the decreasement is a buying. A buying will not hold if
            event_pt + user.event_pt < 0.

        Returns:
        int: the modified amount of event_pt to add."""
        pass
    @classmethod
    async def BeforeDragoned(cls, count: TCount, user: 'User', word: str, parent: 'Tree') -> Tuple[bool, int, str]:
        """Called before a user dragoning.

        Arguments:
        word: the dragon word.
        parent: the parent tree node.

        Returns:
        bool: represents whether the user can dragon;
        int: offset to modify the dragon distance allowed;
        str: failure message."""
        pass
    @classmethod
    async def CheckSuguri(cls, count: TCount, user: 'User', word: str, parent: 'Tree') -> Tuple[bool]:
        """Called when Suguri's Accelerator is checked to be used.

        Arguments:
        word: the dragon word.
        parent: the parent tree node.
        
        Returns:
        bool: represents if accelerated."""
        pass
    @classmethod
    async def OnKeyword(cls, count: TCount, user: 'User', word: str, parent: 'Tree', keyword: str) -> Tuple[int]:
        """Called when a user hit a keyword.
        
        Arguments:
        word: the dragon word.
        parent: the parent tree node.
        keyword: the keyword.
        
        Returns:
        int: the amount of jibi to add."""
        pass
    @classmethod
    async def OnHiddenKeyword(cls, count: TCount, user: 'User', word: str, parent: 'Tree', keyword: str) -> Tuple[int]:
        """Called when a user hit a hidden keyword.
        
        Arguments:
        word: the dragon word.
        parent: the parent tree node.
        keyword: the hidden keyword.
        
        Returns:
        int: the amount of jibi to add."""
        pass
    @classmethod
    async def OnDuplicatedWord(cls, count: TCount, user: 'User', word: str) -> Tuple[bool]:
        """Called when a user dragoned a duplicated word in one week.
        
        Arguments:
        word: the dragon word.
        
        Returns:
        bool: represents whether the hit is dodged."""
        pass
    @classmethod
    async def OnBombed(cls, count: TCount, user: 'User', word: str) -> Tuple[bool]:
        """Called when a user hit a mine.
        
        Arguments:
        word: the dragon word.
        
        Returns:
        bool: represents whether the hit is dodged."""
        pass
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        """Called when the user complete a dragon.
        
        Arguments:
        branch: the dragon branch.
        first10: if it is the first 10 dragon each day."""
        pass
    @classmethod
    async def OnNewDay(cls, count: TCount, user: 'User') -> Tuple[()]:
        """Called when new day begins."""
        pass
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {}

class Attack(ABC):
    name = "null"
    doublable = True
    reboundable = True
    def __init__(self, attacker: 'User', defender: 'User'):
        self.attacker = attacker
        self.defender = defender
        self.rebounded = False
        self.multiplier = 1
        self.counter = TCounter()
    @abstractmethod
    async def self_action(self):
        pass
    @final
    async def action(self):
        if self.rebounded:
            config.logger.dragon << f"【LOG】攻击{self}被反弹。"
            self.rebounded = False
            await self.defender.attacked(self.attacker, self)
        else:
            config.logger.dragon << f"【LOG】执行攻击{self}。"
            await self.self_action()
    def __repr__(self):
        return f"<攻击类型：{self.name}，攻击者：{self.attacker.qq}，被攻击者：{self.defender.qq}，倍数：{self.multiplier}，c：{self.counter}>"
    def double(self) -> bool:
        """return True if double equals dodge."""
        self.multiplier *= 2
        return False
    def rebound(self) -> bool:
        """return True if rebound equals dodge."""
        self.attacker, self.defender = self.defender, self.attacker
        self.counter = TCounter()
        self.rebounded = True
        return False

class Kill(Attack):
    name = "击毙"
    def __init__(self, attacker: 'User', defender: 'User', minute: int):
        self.minute = minute
        super().__init__(attacker, defender)
    async def self_action(self):
        await self.defender.death(self.minute * self.multiplier, self.attacker, self.counter)

class Game:
    session_list: List[CommandSession] = []
    userdatas: Dict[int, 'UserData'] = {}
    @classmethod
    def wrapper_noarg(cls, f: Awaitable[config.SessionBuffer]):
        @wraps(f)
        async def _f(buf: config.SessionBuffer, *args, **kwargs):
            try:
                return await f(buf, *args, **kwargs)
            finally:
                await buf.flush()
                cls.userdatas.clear()
        return _f
    @classmethod
    def wrapper(cls, f: Awaitable[config.SessionBuffer]):
        @wraps(f)
        async def _f(session: CommandSession):
            cls.session_list.append(session)
            buf = config.SessionBuffer(session)
            try:
                await f(buf)
            finally:
                await buf.flush()
                cls.remove_session(session)
        return _f
    @classmethod
    def remove_session(cls, session: CommandSession):
        cls.session_list.remove(session)
        if len(cls.session_list) == 0:
            cls.userdatas.clear()
    @classmethod
    def userdata(cls, qq: int):
        if qq == config.selfqq:
            return me
        if qq in cls.userdatas:
            return cls.userdatas[qq]
        u = UserData(qq)
        cls.userdatas[qq] = u
        return u
class property_dict(UserDict):
    def __init__(self, f: Callable, __dict, **kwargs) -> None:
        super().__init__(__dict, **kwargs)
        self.f = f
    def __setitem__(self, name, value):
        super().__setitem__(name, value)
        self.f(self.data)
    def __delitem__(self, name):
        super().__delitem__(name)
        self.f(self.data)
class property_list(UserList):
    def __init__(self, f: Callable, initlist=None) -> None:
        super().__init__(initlist)
        self.f = f
    def append(self, item):
        super().append(item)
        self.f(self.data)
    def remove(self, item):
        super().remove(item)
        self.f(self.data)
    def pop(self, i):
        super().pop(i)
        self.f(self.data)
    def extend(self, other):
        super().extend(other)
        self.f(self.data)
    def __setitem__(self, i, item):
        super().__setitem__(i, item)
        self.f(self.data)
    def clear(self):
        super().clear()
        self.f(self.data)
    __delitem__ = None
    __iadd__ = None
    __imul__ = None
    def insert(self, i, item):
        super().insert(i, item)
        self.f(self.data)
    reverse = None
    sort = None
class Wrapper:
    def __init__(self, qq):
        self.qq = qq
    def __lshift__(self, log):
        config.logger.dragon << f"【LOG】用户{self.qq}" + log

extra_data_format = '!BLII'
@dataclass
class ExtraData:
    tarot_time: int # unsigned char
    assembling: int # unsigned long
    hp: int         # unsigned int
    mp: int         # unsigned int
    @classmethod
    def make(cls, data, save):
        return cls(*unpack(extra_data_format, data), lambda self: save(pack(extra_data_format, *self)))
@dataclass
class DynamicExtraData:
    data: ExtraData
    save_func_old: Callable
    save_func: Callable = field(init=False)
    def __post_init__(self):
        self.data = ExtraData(*unpack(extra_data_format, self.data))
        self.save_func = lambda value: self.save_func_old(pack(extra_data_format, *astuple(value)))
    def __str__(self):
        return str(self.data)
    @property
    def tarot_time(self):
        return self.data.tarot_time
    @tarot_time.setter
    def tarot_time(self, value):
        self.data.tarot_time = value
        self.save_func(self.data)
    @property
    def assembling(self):
        return self.data.assembling
    @assembling.setter
    def assembling(self, value):
        self.data.assembling = value
        self.save_func(self.data)
    @property
    def hp(self):
        return self.data.hp
    @hp.setter
    def hp(self, value):
        self.data.hp = value
        self.save_func(self.data)
    @property
    def mp(self):
        return self.data.mp
    @mp.setter
    def mp(self, value):
        self.data.mp = value
        self.save_func(self.data)
    # def __getattr__(self, name: str):
    #     if name not in ('data', 'save_func', 'save_func_old'):
    #         return getattr(self.data, name)
    #     else:
    #         return self.__dict__[name]
    # def __setattr__(self, name: str, value: Any) -> None:
    #     if name not in ('data', 'save_func', 'save_func_old'):
    #         setattr(self.data, name, value)
    #         self.save_func(self.data)
    #     else:
    #         self.__dict__[name] = value

class UserData:
    event_listener_init: defaultdict[int, TEventList] = defaultdict(lambda: defaultdict(CounterOnly))
    @classmethod
    def register_checker(cls, checker: IEventListener, count: int=1):
        for key, (priority, el) in checker.register().items():
            cls.event_listener_init[key][priority][el] += count
    def __init__(self, qq: int):
        self._qq = qq
        self.node: TUserData = dict(find_or_new(qq))
        self.hand_card = [] if self.node['card'] == '' else [Card(int(x)) for x in self.node['card'].split(',')]
        def save(key, value):
            config.logger.dragon << f"【LOG】用户{self.qq}保存{key}，值为{value}。"
            config.userdata.execute(f"update dragon_data set {key}=? where qq=?", (str(value), self.qq))
        self.status_time: List[T_status] = property_list(partial(save, 'status_time'), [])
        self.status_time.data = eval(self.node['status_time'])
        self.equipment: Dict[int, int] = property_dict(partial(save, 'equipment'), {})
        self.equipment.data = eval(self.node['equipment'])
        def save2(value):
            config.userdata.execute(f"update dragon_data set extra_data=? where qq=?", (value, self.qq))
        self.extra = DynamicExtraData(self.node['extra_data'], save2)
        self._reregister_things()
    def __del__(self):
        config.logger.dragon << f"【LOG】用户{self.qq}UserData被删除。"
    def _reregister_things(self):
        self.event_listener: defaultdict[int, TEventList] = deepcopy(self.event_listener_init)
        for c in self.hand_card:
            self._register_card(c)
        for s in itertools.chain(map(StatusNull, self.status), map(StatusDaily, self.daily_status)):
            self._register_status(s)
        for s in self.status_time_checked:
            self._register_status_time(s)
        for id, star in self.equipment.items():
            self._register_equipment(Equipment(id), star)
    def _register_card(self, c: TCard, count=1):
        self._register(c, to_add=count)
    def _register_status(self, s: Union[T_statusdaily, T_statusnull], count=1):
        if s.is_global == (self.qq == config.selfqq):
            self._register(s, to_add=count)
    def _register_status_time(self, s: T_status):
        if s.is_global == (self.qq == config.selfqq):
            self._register(s, [s])
    def _register_equipment(self, s: T_equipment, count):
        self._register(s, to_add=count)
    def _register(self, eln: 'IEventListener', to_add=1):
        for key, (priority, el) in eln.register().items():
            self.event_listener[key][priority][el] += to_add
    def _deregister_card(self, c: TCard, /, is_all=False):
        self._deregister(c, is_all=is_all)
    def _deregister_status(self, s: Union[T_statusdaily, T_statusnull], /, is_all=False):
        if s.is_global == (self.qq == config.selfqq):
            self._deregister(s, is_all=is_all)
    def _deregister_status_time(self, eln: Union[str, T_status], /, is_all=False):
        # str -> is_all = True
        if eln.is_global == (self.qq == config.selfqq):
            for key, (priority, el) in eln.register().items():
                if is_all:
                    self.event_listener[key].pop(priority)
                else:
                    self.event_listener[key][priority][el].remove(el)
                    if len(self.event_listener[key][priority][el]) == 0:
                        self.event_listener[key].pop(priority)
    def _deregister(self, eln: 'IEventListener', /, is_all=False):
        for key, (priority, el) in eln.register().items():
            if is_all:
                self.event_listener[key].pop(priority)
            else:
                self.event_listener[key][priority][el] -= 1
                if self.event_listener[key][priority][el] == 0:
                    self.event_listener[key].pop(priority)
    def save_status_time(self):
        self.status_time.f(self.status_time.data)
    def save_equipment(self):
        self.equipment.f(self.equipment.data)
    def reload(self) -> None:
        self.node = dict(find_or_new(self.qq))
    @property
    def qq(self):
        return self._qq
    @property
    def log(self):
        return Wrapper(self.qq)
    @property
    def jibi(self):
        return self.node['jibi']
    @jibi.setter
    def jibi(self, value):
        config.userdata.execute("update dragon_data set jibi=? where qq=?", (value, self.qq))
        self.node['jibi'] = value
    @property
    def draw_time(self):
        return self.node['draw_time']
    @draw_time.setter
    def draw_time(self, value):
        config.userdata.execute("update dragon_data set draw_time=? where qq=?", (value, self.qq))
        self.node['draw_time'] = value
    @property
    def today_jibi(self):
        return self.node['today_jibi']
    @today_jibi.setter
    def today_jibi(self, value):
        config.userdata.execute("update dragon_data set today_jibi=? where qq=?", (value, self.qq))
        self.node['today_jibi'] = value
    @property
    def today_keyword_jibi(self):
        return self.node['today_keyword_jibi']
    @today_keyword_jibi.setter
    def today_keyword_jibi(self, value):
        config.userdata.execute("update dragon_data set today_keyword_jibi=? where qq=?", (value, self.qq))
        self.node['today_keyword_jibi'] = value
    @property
    def card_limit_from_assembling(self):
        c = self.check_equipment(3)
        if c == 0:
            return 0
        return assembling.get_card_limit(self.extra.assembling, c)
    @property
    def card_limit(self):
        return self.card_limit_raw + self.card_limit_from_assembling
    @property
    def card_limit_raw(self):
        return self.node['card_limit']
    @card_limit_raw.setter
    def card_limit_raw(self, value):
        config.userdata.execute("update dragon_data set card_limit=? where qq=?", (value, self.qq))
        self.node['card_limit'] = value
    @property
    def shop_drawn_card(self):
        return self.node['shop_drawn_card']
    @shop_drawn_card.setter
    def shop_drawn_card(self, value):
        config.userdata.execute("update dragon_data set shop_drawn_card=? where qq=?", (value, self.qq))
        self.node['shop_drawn_card'] = value
    @property
    def event_pt(self):
        return self.node['event_pt']
    @event_pt.setter
    def event_pt(self, value):
        config.userdata.execute("update dragon_data set event_pt=? where qq=?", (value, self.qq))
        self.node['event_pt'] = value
    @property
    def spend_shop(self):
        return self.node['spend_shop']
    @spend_shop.setter
    def spend_shop(self, value):
        config.userdata.execute("update dragon_data set spend_shop=? where qq=?", (value, self.qq))
        self.node['spend_shop'] = value
    @property
    def status(self):
        return self.node['status']
    @status.setter
    def status(self, value):
        config.userdata.execute("update dragon_data set status=? where qq=?", (value, self.qq))
        self.node['status'] = value
    @property
    def daily_status(self):
        return self.node['daily_status']
    @daily_status.setter
    def daily_status(self, value):
        config.userdata.execute("update dragon_data set daily_status=? where qq=?", (value, self.qq))
        self.node['daily_status'] = value
    @property
    def event_stage(self):
        if '_event_stage' not in self.__dict__:
            self._event_stage: Grid = Grid(self.node['event_stage'])
        return self._event_stage
    @event_stage.setter
    def event_stage(self, value: 'Grid'):
        self._event_stage = value
        config.userdata.execute("update dragon_data set event_stage=? where qq=?", (self._event_stage.stage, self.qq))
    @property
    def event_shop(self):
        return self.node['event_shop']
    @event_shop.setter
    def event_shop(self, value):
        config.userdata.execute("update dragon_data set event_shop=? where qq=?", (value, self.qq))
        self.node['event_shop'] = value
    @property
    def last_dragon_time(self):
        return self.node['last_dragon_time']
    @last_dragon_time.setter
    def last_dragon_time(self, value):
        config.userdata.execute("update dragon_data set last_dragon_time=? where qq=?", (value, self.qq))
        self.node['last_dragon_time'] = value
    @property
    def status_time_checked(self):
        i = 0
        while i < len(self.status_time):
            t = self.status_time[i]
            if not t.check():
                self.status_time.pop(i)
            else:
                i += 1
        return self.status_time
    def set_cards(self):
        config.userdata.execute("update dragon_data set card=? where qq=?", (','.join(str(c.id) for c in self.hand_card), self.qq))
        config.logger.dragon << f"【LOG】设置用户{self.qq}手牌为{cards_to_str(self.hand_card)}。"
    def check_status(self, s: str) -> int:
        return self.status.count(s)
    def check_daily_status(self, s: str) -> int:
        return self.daily_status.count(s)
    def check_limited_status(self, s: str, extra: Optional[Callable[[T_status], bool]]=None) -> List[T_status]:
        return [t for t in self.status_time_checked if t.id == s and (extra is None or extra(t))]
    def check_throw_card(self, card_ids: List[int]):
        if len(card_ids) == 1:
            if card_ids[0] not in [c.id for c in self.hand_card]:
                return False
        else:
            hand_counter = Counter(c.id for c in self.hand_card)
            hand_counter.subtract(Counter(card_ids))
            if -hand_counter != Counter():
                return False
        return True
    def check_equipment(self, equip_id: int) -> int:
        return self.equipment.get(equip_id, 0)

class User:
    def __init__(self, qq: int, buf: config.SessionBuffer, /, data: UserData=None):
        self.qq = qq
        self.data = data or Game.userdata(qq)
        self.buf = buf
    def __del__(self):
        pass
    @property
    def active(self):
        return self.buf.active == self.qq
    def __eq__(self, other: 'User'):
        return self.qq == other.qq and self.buf == other.buf
    @property
    def char(self):
        return self.buf.char(self.qq)
    def send_char(self, s: str, /, end='\n'):
        self.buf.send(self.char + s, end=end)
    def send_log(self, s: str, /, end='\n'):
        self.buf.send_log.dragon(self.qq, s, end=end)
    def decrease_death_time(self, time: timedelta):
        t = self.data.check_limited_status('d')
        if len(t) == 0:
            return True
        ret = True
        for c in t:
            c -= time
            if c.check():
                ret = False
        self.data.save_status_time()
        return ret
    async def choose(self):
        if not self.active:
            config.logger.dragon << f"【LOG】用户{self.qq}非活跃，无法选择。"
            self.send_char("非活跃，无法选择卡牌！")
            return False
        else:
            await self.buf.flush()
            return True
    @property
    def log(self):
        return self.data.log
    def IterAllEventList(self, evt: UserEvt, priority: Type[TBoundIntEnum], /, no_global: bool=False, extra_listeners: List[TEventList]=None):
        user_lists = [self.data.event_listener[evt]]
        if extra_listeners is not None:
            user_lists += extra_listeners
        if not no_global and not (self.check_status('%') and self.buf.state.get('circus')):
            user_lists.append(me.event_listener[evt])
        for p in priority:
            for e in user_lists:
                ret = e.get(p)
                if ret is not None:
                    yield ret.data_pair
                    break
    async def add_status(self, s: str, count=1):
        # Event OnStatusAdd
        for eln, n in self.IterAllEventList(UserEvt.OnStatusAdd, Priority.OnStatusAdd):
            count, = await eln.OnStatusAdd(n, self, StatusNull(s), count)
            if count == 0:
                return False
        else:
            self.data.status += s * count
            self.log << f"增加了永久状态{s}，当前状态为{self.data.status}。"
            self.data._register_status(StatusNull(s), count=count)
            await StatusNull(s).on_add(count)
            if StatusNull(s).is_global():
                global_state['global_status'].append([0,s]*count)
                save_global_state()
            return True
    async def add_daily_status(self, s: str, count=1):
        # Event OnStatusAdd
        for eln, n in self.IterAllEventList(UserEvt.OnStatusAdd, Priority.OnStatusAdd):
            count, = await eln.OnStatusAdd(n, self, StatusDaily(s), count)
            if count == 0:
                return False
        else:
            self.data.daily_status += s * count
            self.log << f"增加了每日状态{s}，当前状态为{self.data.daily_status}。"
            self.data._register_status(StatusDaily(s), count=count)
            await StatusDaily(s).on_add(count)
            if StatusDaily(s).is_global():
                global_state['global_status'].append([1,s]*count)
                save_global_state()
            return True
    async def add_limited_status(self, s: Union[str, T_status], *args, **kwargs):
        if isinstance(s, str):
            ss = Status(s)(*args, **kwargs)
        else:
            ss = s
        count = 1
        # Event OnStatusAdd
        for eln, n in self.IterAllEventList(UserEvt.OnStatusAdd, Priority.OnStatusAdd):
            count, = await eln.OnStatusAdd(n, self, ss, count)
            if count == 0:
                return False
        else:
            self.data.status_time.append(ss)
            self.log << f"增加了限时状态{ss}。"
            self.data._register_status_time(ss)
            await ss.on_add([ss])
            if ss.is_global():
                global_state['global_status'].append([2,repr(ss)])
                save_global_state()
            return True
    async def remove_status(self, s: str, /, remove_all=True):
        # Event OnStatusRemove
        for eln, n in self.IterAllEventList(UserEvt.OnStatusRemove, Priority.OnStatusRemove):
            dodge, = await eln.OnStatusRemove(n, self, StatusNull(s), remove_all)
            if dodge:
                return False
        else:
            if remove_all:
                self.data.status = ''.join([t for t in self.data.status if t != s])
            else:
                l = list(self.data.status)
                if s in l:
                    l.remove(s)
                self.data.status = ''.join(l)
            self.log << f"移除了{'一层' if not remove_all else ''}永久状态{s}，当前状态为{self.data.status}。"
            self.data._deregister(StatusNull(s), is_all=remove_all)
            await StatusNull(s).on_remove(remove_all)
            if StatusNull(s).is_global:
                if remove_all:
                    while [0, s] in global_state['global_status']:
                        global_state['global_status'].remove([0, s])
                else:
                    global_state['global_status'].remove([0, s])
                save_global_state()
            return True
    async def remove_daily_status(self, s: str, /, remove_all=True):
        # Event OnStatusRemove
        for eln, n in self.IterAllEventList(UserEvt.OnStatusRemove, Priority.OnStatusRemove):
            dodge, = await eln.OnStatusRemove(n, self, StatusDaily(s), remove_all)
            if dodge:
                return False
        else:
            if remove_all:
                self.data.daily_status = ''.join([t for t in self.data.daily_status if t != s])
            else:
                l = list(self.data.daily_status)
                if s in l:
                    l.remove(s)
                self.data.daily_status = ''.join(l)
            self.log << f"移除了{'一层' if not remove_all else ''}每日状态{s}，当前状态为{self.data.daily_status}。"
            self.data._deregister(StatusDaily(s), is_all=remove_all)
            await StatusDaily(s).on_remove(remove_all)
            if StatusDaily(s).is_global:
                if remove_all:
                    while [1, s] in global_state['global_status']:
                        global_state['global_status'].remove([1, s])
                else:
                    global_state['global_status'].remove([1, s])
                save_global_state()
            return True
    async def remove_limited_status(self, s: T_status):
        # Event OnStatusRemove
        for eln, n in self.IterAllEventList(UserEvt.OnStatusRemove, Priority.OnStatusRemove):
            dodge, = await eln.OnStatusRemove(n, self, s, False)
            if dodge:
                return False
        else:
            self.data.status_time.remove(s)
            self.log << f"移除了一个限时状态{s}。"
            self.data._deregister_status_time(s, is_all=False)
            await s.on_remove(False)
            if s.is_global and [2, repr(s)] in global_state['global_status']:
                global_state['global_status'].remove([2, repr(s)])
                save_global_state()
            return True
    async def remove_all_limited_status(self, s: str):
        l = [c for c in self.data.status_time if c.id == s]
        if len(l) == 0:
            return self.data.status_time
        # Event OnStatusRemove
        for eln, n in self.IterAllEventList(UserEvt.OnStatusRemove, Priority.OnStatusRemove):
            dodge, = await eln.OnStatusRemove(n, self, l[0], True)
            if dodge:
                return False
        else:
            i = 0
            while i < len(self.data.status_time):
                t: T_status = self.data.status_time[i]
                if not t.check() or t.id == s:
                    self.data.status_time.pop(i)
                else:
                    i += 1
            self.log << f"移除了所有限时状态{s}。"
            self.data._deregister_status_time(Status(s), is_all=True)
            await Status(s).on_remove(True)
            if Status(s).is_global:
                global_state['global_status'] = [t for t in global_state['global_status'] if t[0] == 2 and t[1].startswith(f"Status('{s}')")]
                save_global_state()
            return True
            # return self.data.status_time
    def check_status(self, s: str) -> int:
        return self.data.check_status(s)
    def check_daily_status(self, s: str) -> int:
        return self.data.check_daily_status(s)
    def check_limited_status(self, s: str, extra: Optional[Callable[[T_status], bool]]=None) -> List[T_status]:
        return self.data.check_limited_status(s, extra)
    def add_card(self, card: TCard):
        self.data.hand_card.append(card)
        self.data._register_card(card)
    def remove_card(self, card: TCard):
        self.data.hand_card.remove(card)
        self.data._deregister_card(card)
    async def add_event_pt(self, pt: int, /, is_buy: bool=False):
        current_event_pt = self.data.event_pt
        if is_buy and pt < 0:
            pt = -pt
            # Event CheckEventptSpend
            for eln, n in self.IterAllEventList(UserEvt.CheckEventptSpend, Priority.CheckEventptSpend):
                pt, = await eln.CheckEventptSpend(n, self, pt)
            if current_event_pt < pt:
                return False
            pt = -pt
        # Event OnEventptChange
        for eln, n in self.IterAllEventList(UserEvt.OnEventptChange, Priority.OnEventptChange):
            pt, = await eln.OnEventptChange(n, self, pt, is_buy)
            if pt == 0:
                break
        self.data.event_pt = max(self.data.event_pt + pt, 0)
        if not is_buy:
            self.send_char(f"收到了{pt}活动pt！")
        self.log << f"增加了{pt}活动pt。现有{self.data.event_pt}活动pt。"
        return True
    async def add_jibi(self, jibi: int, /, is_buy: bool=False) -> bool:
        if jibi == 0:
            return True,
        current_jibi = self.data.jibi
        if is_buy and jibi < 0:
            jibi = -jibi
            # Event CheckJibiSpend
            for eln, n in self.IterAllEventList(UserEvt.CheckJibiSpend, Priority.CheckJibiSpend):
                jibi, = await eln.CheckJibiSpend(n, self, jibi)
            if current_jibi < jibi:
                return False
            jibi = -jibi
        # Event OnJibiChange
        for eln, n in self.IterAllEventList(UserEvt.OnJibiChange, Priority.OnJibiChange):
            jibi, = await eln.OnJibiChange(n, self, jibi, is_buy)
            if jibi == 0:
                break
        self.data.jibi = max(self.data.jibi + jibi, 0)
        if is_buy and jibi < 0:
            self.data.spend_shop += abs(jibi)
            self.log << f"累计今日商店购买至{self.data.spend_shop}。"
        self.data.save_status_time()
        return True
    async def attacked(self, attacker: 'User', attack: Attack):
        """受到攻击。"""
        config.logger.dragon << f"【LOG】玩家受到攻击{attack}。"
        dodge = False
        c = TCounter()
        # Event OnAttack
        for eln, n in attacker.IterAllEventList(UserEvt.OnAttack, Priority.OnAttack):
            dodge, = await eln.OnAttack(n, attacker, attack, c)
            if dodge:
                return
        # Event OnAttacked
        for eln, n in self.IterAllEventList(UserEvt.OnAttacked, Priority.OnAttacked):
            dodge, = await eln.OnAttacked(n, self, attack, c)
            if dodge:
                return
        await attack.action()
    async def killed(self, killer: 'User', hour: int=2, minute: int=0):
        """击杀玩家。"""
        config.logger.dragon << f"【LOG】{killer.qq}尝试击杀玩家{self.qq}。"
        time_num = 60 * hour + minute
        attack = Kill(killer, self, time_num)
        await self.attacked(killer, attack)
    async def death(self, minute: int=120, killer=None, c: TCounter=None):
        """玩家死亡。"""
        config.logger.dragon << f"【LOG】玩家{self.qq}死亡。"
        dodge = False
        if c is None:
            c = TCounter()
        # Event OnDeath
        for eln, n in self.IterAllEventList(UserEvt.OnDeath, Priority.OnDeath):
            minute, dodge = await eln.OnDeath(n, self, killer, minute, c)
            if dodge:
                break
        else:
            self.send_char(f"死了！{minute}分钟不得接龙。")
            await self.add_limited_status(SDeath(datetime.now() + timedelta(minutes=minute)))
    async def draw(self, n: int, /, positive=None, cards=None, extra_lambda=None):
        """抽卡。将卡牌放入手牌。"""
        if self.active and self.buf.state.get('exceed_limit'):
            self.send_log("因手牌超出上限，不可摸牌！")
            return
        cards = draw_cards(positive, n, extra_lambda=extra_lambda) if cards is None else cards
        self.log << f"抽到的卡牌为{cards_to_str(cards)}。"
        self.send_char('抽到的卡牌是：')
        for c in cards:
            if c.des_need_init:
                await self.draw_card_effect(c)
            self.buf.send(c.full_description(self.qq))
        for c in cards:
            if not c.consumed_on_draw:
                self.add_card(c)
            if not c.des_need_init:
                await self.draw_card_effect(c)
        # Event AfterCardDraw
        for el, n in self.IterAllEventList(UserEvt.AfterCardDraw, Priority.AfterCardDraw):
            await el.AfterCardDraw(n, self, cards)
        self.data.set_cards()
        self.log << f"抽完卡牌，当前手牌为{cards_to_str(self.data.hand_card)}。"
    async def draw_and_use(self, card: TCard):
        """抽取卡牌，立即使用，并发动卡牌的销毁效果。不经过手牌。"""
        if card.des_need_init:
            await self.draw_card_effect(card)
        self.log << f"抽取并使用了卡牌{card.name}。"
        self.send_char('抽到并使用了卡牌：\n' + card.full_description(self.qq))
        if not card.des_need_init:
            await self.draw_card_effect(card)
        await self.use_card_effect(card)
        if card.id not in global_state['used_cards']:
            global_state['used_cards'].append(card.id)
            save_global_state()
        await card.on_remove(self)
    async def draw_card_effect(self, card: TCard):
        """抽卡时的结算。"""
        if card.consumed_on_draw:
            # Event BeforeCardUse
            for el, n in self.IterAllEventList(UserEvt.BeforeCardUse, Priority.BeforeCardUse):
                block, = await el.BeforeCardUse(n, self, card)
                if block is not None:
                    self.log << f"卡牌使用被阻挡！"
                    await block
                    return
        await card.on_draw(self)
    async def use_card_effect(self, card: TCard):
        """发动卡牌的使用效果。"""
        self.log << f"发动卡牌的使用效果{card.name}。"
        if not card.consumed_on_draw:
            block = None
            # Event BeforeCardUse
            for el, n in self.IterAllEventList(UserEvt.BeforeCardUse, Priority.BeforeCardUse):
                block, = await el.BeforeCardUse(n, self, card)
                if block is not None:
                    self.log << f"卡牌使用被阻挡！"
                    await block
                    return
            await card.use(self)
            # Event AfterCardUse
            for el, n in self.IterAllEventList(UserEvt.AfterCardUse, Priority.AfterCardUse):
                await el.AfterCardUse(n, self, card)
    async def use_card(self, card: TCard):
        """将卡牌移出手牌，使用卡牌然后执行销毁操作。"""
        self.send_char('使用了卡牌：\n' + card.full_description(self.qq))
        self.log << f"使用了卡牌{card.name}。"
        self.remove_card(card)
        await self.use_card_effect(card)
        await card.on_remove(self)
        self.log << f"使用完卡牌，当前手牌为{cards_to_str(self.data.hand_card)}。"
    async def use_equipment(self, eq: TEquipment, count: int):
        """使用装备。"""
        self.send_char('使用了装备：\n' + eq.description(count))
        self.log << f"使用了装备{eq.name}，等级为{eq.count}。"
        await eq.use(self, count)
    async def remove_cards(self, cards: List[TCard]):
        """将cards里的卡牌移出手牌，不结算弃牌。"""
        self.log << f"烧牌{cards_to_str(cards)}。"
        for c in cards:
            self.remove_card(c)
        self.data.set_cards()
        for card in cards:
            await card.on_remove(self)
        # Event AfterCardRemove
        for el, n in self.IterAllEventList(UserEvt.AfterCardRemove, Priority.AfterCardRemove):
            await el.AfterCardRemove(n, self, cards)
    async def discard_cards(self, cards: List[TCard]):
        """弃牌。将cards里的卡牌移出手牌。弃光手牌时请复制hand_card作为cards传入。"""
        self.log << f"弃牌{cards_to_str(cards)}。"
        for c in cards:
            self.remove_card(c)
        self.data.set_cards()
        for card in cards:
            await card.on_discard(self)
        # Event AfterCardDiscard
        for el, n in self.IterAllEventList(UserEvt.AfterCardDiscard, Priority.AfterCardDiscard):
            await el.AfterCardDiscard(n, self, cards)
        self.log << f"弃完卡牌，当前手牌为{cards_to_str(self.data.hand_card)}。"
    async def exchange(self, target: 'User'):
        """交换两人手牌。"""
        if self == target:
            return
        target_hand_cards = copy(target.data.hand_card)
        self_hand_cards = copy(self.data.hand_card)
        config.logger.dragon << f"【LOG】交换用户{self.qq}与用户{target.qq}的手牌。{self.qq}手牌为{cards_to_str(self_hand_cards)}，{target.qq}手牌为{cards_to_str(target_hand_cards)}。"
        self.data.hand_card.clear()
        target.data.hand_card.clear()
        for card in self_hand_cards:
            await card.on_give(self, target)
        for card in target_hand_cards:
            await card.on_give(target, self)
        self.data.hand_card.extend(target_hand_cards)
        target.data.hand_card.extend(self_hand_cards)
        self.data.set_cards()
        # target_limit = target.data.card_limit
        # if len(self_hand_cards) > target_limit:
        #     self.buf.send(f"该玩家手牌已超出上限{len(self_hand_cards) - target_limit}张！多余的牌已被弃置。")
        #     target.log << f"手牌为{cards_to_str(self_hand_cards)}，超出上限{target_limit}，自动弃置。"
        #     await target.discard_cards(copy(self_hand_cards[target_limit:]))
        target.data.set_cards()
        config.logger.dragon << f"【LOG】交换完用户{self.qq}与用户{target.qq}的手牌，当前用户{self.qq}的手牌为{cards_to_str(self.data.hand_card)}。"
        # Event AfterExchange
        for eln, n in self.IterAllEventList(UserEvt.AfterExchange, Priority.AfterExchange):
            await eln.AfterExchange(n, self, target)
        for eln, n in target.IterAllEventList(UserEvt.AfterExchange, Priority.AfterExchange, no_global=True):
            await eln.AfterExchange(n, target, self)
    @asynccontextmanager
    async def settlement(self):
        """结算卡牌相关。请不要递归调用此函数。"""
        self.log << "开始结算。"
        if not await self.choose():
            return
        try:
            yield
            if self.active and self.buf.state.get('exceed_limit'):
                self.log << "因手牌超出上限，无需弃牌。"
                return
            # discard
            cards_can_not_choose = (53,)
            d = len(list(c for c in self.data.hand_card if c in cards_can_not_choose))
            x = len(self.data.hand_card) - max(d, self.data.card_limit)
            while x > 0:
                self.log << f"手牌超出上限，用户选择弃牌。"
                async with self.choose_cards(f"您的手牌已超出上限{x}张！请先选择一些牌弃置（输入id号，使用空格分隔）：", 1, x,
                        cards_can_not_choose) as l:
                        self.buf.send("成功弃置。")
                        await self.discard_cards([Card(i) for i in l])
                d = len(list(c for c in self.data.hand_card if c in cards_can_not_choose))
                x = len(self.data.hand_card) - max(d, self.data.card_limit)
            await self.buf.flush()
        finally:
            self.data.set_cards()
            self.data.save_status_time()
            save_data()
    async def event_move(self, n):
        self.log << f"走了{n}格。"
        current = self.data.event_stage
        begin = current.stage
        while n != 0:
            if p := self.check_status('D'):
                await self.remove_status('D')
                n *= 2 ** p
            current = Grid(max(current.stage + n, 0))
            self.log << f"行走至格子{current}。"
            n = await current.do(self)
        self.data.event_stage = current
        end = current.stage
        if begin // 50 < (e := end // 50) and e <= 8:
            pt = (10, 20, 10, 50, 10, 20, 10, 50)[e - 1]
            self.send_log(f"经过了{e * 50}层，获得了{pt}pt！")
            await self.add_event_pt(pt)
        t = (current.stage, self.qq)
        u = self
        while 1:
            l = config.userdata.execute("select qq from dragon_data where event_stage=? and qq<>?", t).fetchone()
            if l is None:
                break
            u.send_log(f"将玩家{l['qq']}踢回了一格！")
            current = current.parent
            if current is None:
                break
            u = User(l['qq'], self.buf)
            u.data.event_stage = current
            t = (current.stage, u.qq)
    @asynccontextmanager
    async def choose_cards(self, attempt: str, min: int, max: int, cards_can_not_choose: Iterable[int]=(),
        require_can_use: bool=False):
        """args:
        attempt: 显示的语句，后换行接手牌的所有卡牌简称。
        min: 最少选择的卡牌数目。
        max: 最多选择的卡牌数目。
        cards_can_not_choose: 不能选择的卡牌id列表。
        require_can_use: 是否要求卡牌可以使用。"""
        config.logger.dragon << f"【LOG】询问用户{self.qq}选择牌。"
        cards_can_not_choose_fin = cards_can_not_choose_org = set(cards_can_not_choose)
        if await self.choose():
            prompt = attempt + "\n" + "\n".join(c.brief_description(self.qq) for c in self.data.hand_card)
            ca = lambda l: len(list(c for c in self.data.hand_card if c.id not in cards_can_not_choose_fin)) < min
            arg_filters = [extractors.extract_text,
                    check_handcard(self),
                    lambda s: list(map(int, re.findall(r'\-?\d+', str(s)))),
                    check_if_unable(ca, self.buf.session),
                    validators.fit_size(min, max, message="请输入正确的张数。"),
                    validators.ensure_true(
                        lambda l: all(i in _card.card_id_dict and Card(i) in self.data.hand_card for i in l),
                        message="您选择了错误的卡牌！")]
            if require_can_use:
                arg_filters.append(ensure_true_lambda(
                    lambda l: Card(l[0]).can_use(self, True),
                    message_lambda=lambda l: Card(l[0]).failure_message))
                cards_can_not_choose_fin = cards_can_not_choose_org | \
                    set(c.id for c in self.data.hand_card if not c.can_use(self, True))
            if len(cards_can_not_choose_fin) != 0:
                arg_filters.append(validators.ensure_true(
                    lambda l: len(set(l) & cards_can_not_choose_fin) == 0,
                    message="此卡牌不可选择！"))
            try:
                try:
                    if ca(None):
                        raise UnableRequirement
                    ret = await self.buf.aget(prompt=prompt, arg_filters=arg_filters)
                    self.log << f"选择了{ret}。"
                    yield ret
                except UnableRequirement:
                    self.send_log("手牌无法选择，选择进程中止！")
                    yield None
            except NotActive:
                pass
            finally:
                self.data.set_cards()
                self.data.save_status_time()
                save_data()
        else:
            yield None

Userme: Callable[[User], User] = lambda user: User(config.selfqq, user.buf)

def save_data():
    config.userdata_db.commit()
    me.reload()

def cards_to_str(cards: List[TCard]):
    return '，'.join(c.name for c in cards)
def draw_cards(positive: Optional[Set[int]]=None, k: int=1, extra_lambda=None):
    x = positive is not None and len(positive & {-1, 0, 1}) != 0
    cards = [c for c in _card.card_id_dict.values() if c.id >= 0 and (not x or x and c.positive in positive)]
    if extra_lambda is not None:
        cards = [c for c in cards if extra_lambda(c)]
    weight = [c.weight for c in cards]
    if me.check_daily_status('j') and (not x or x and (-1 in positive)):
        return [(Card(-1) if random.random() < 0.2 else random.choices(cards, weight)[0]) for i in range(k)]
    l = random.choices(cards, weight, k=k)
    return l
def draw_card(positive: Optional[Set[int]]=None):
    return draw_cards(positive, k=1)[0]
def equips_to_str(equips: Dict[int, TEquipment]):
    return '，'.join(f"{count}*{c.name}" for c, count in equips.items())

class status_meta(ABCMeta):
    def __new__(cls, clsname, bases, attrs):
        if len(bases) != 0 and not clsname.startswith('_') and 'id' in attrs:
            c = super().__new__(cls, clsname, bases, attrs)
            if attrs['id'] in bases[0].id_dict:
                raise ValueError
            bases[0].id_dict[attrs['id']] = c
        else:
            c = super().__new__(cls, clsname, bases, attrs)
        return c

def Status(id: str):
    return _status.id_dict[id]

brief_f = lambda s: (s if '：' not in s else s[:s.index('：')] + s[s.index('\n\t'):] if '\n\t' in s else s[:s.index('：')])
class _statusall(IEventListener, metaclass=status_meta):
    id = ""
    des = ""
    is_debuff = False
    is_global = False
    @classmethod
    @property
    def brief_des(cls):
        return brief_f(cls.des)
    @classmethod
    async def on_add(cls, count: TCount):
        pass
    @classmethod
    async def on_remove(cls, remove_all: bool=True):
        pass
class _status(_statusall):
    id_dict: Dict[str, TStatus] = {}
    def __init__(self, s: str):
        pass
    def check(self) -> bool:
        return True
    def construct_repr(self, *args):
        return f"Status('{self.id}')(" + ', '.join(repr(s) for s in args) + ")"
    def __repr__(self) -> str:
        return ""
    @property
    def brief_des(self) -> str:
        return brief_f(str(self))
    def __str__(self) -> str:
        return self.des
    def __add__(self, other) -> T_status:
        pass
    def __sub__(self, other) -> T_status:
        pass
    def __iadd__(self, other) -> T_status:
        return self
    def __isub__(self, other) -> T_status:
        return self
    def double(self) -> List[T_status]:
        return [self]
# Why construct_repr use str instead of num itself??????

class TimedStatus(_status):
    def __init__(self, s: Union[str, datetime]):
        if isinstance(s, datetime):
            self.time = s
        else:
            self.time = datetime.fromisoformat(s)
    def check(self) -> bool:
        return self.time >= datetime.now()
    def __repr__(self) -> str:
        return self.construct_repr(self.time.isoformat())
    def __str__(self) -> str:
        delta = self.time - datetime.now()
        min = delta.seconds // 60
        return f"{self.des}\n\t结束时间：{f'{delta.days}日' if delta.days != 0 else ''}{f'{min // 60}时' if min // 60 != 0 else ''}{min % 60}分钟。"
    def __add__(self, other: timedelta) -> T_status:
        return self.__class__(self.time + other)
    def __sub__(self, other: timedelta) -> T_status:
        return self.__class__(self.time - other)
    def __iadd__(self, other: timedelta) -> T_status:
        self.time += other
        return self
    def __isub__(self, other: timedelta) -> T_status:
        self.time -= other
        return self
    def double(self):
        return [self.__class__(self.time + (self.time - datetime.now()))]

@final
class SDeath(TimedStatus):
    id = 'd'
    is_debuff = True
    des = "死亡：不可接龙。"
    @classmethod
    async def BeforeDragoned(cls, count: TCount, user: 'User', word: str, parent: 'Tree') -> Tuple[bool, int, str]:
        return False, 0, '你已死，不能接龙！'
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.BeforeDragoned: (Priority.BeforeDragoned.death, cls)}

class NumedStatus(_status):
    def __init__(self, s: Union[str, int]):
        self.num = int(s)
    def check(self) -> bool:
        return self.num > 0
    def __repr__(self) -> str:
        return self.construct_repr(str(self.num))
    def __str__(self) -> str:
        return f"{self.des}\n\t剩余次数：{self.num}次。"
    def __add__(self, other: int) -> T_status:
        return self.__class__(self.num + other)
    def __sub__(self, other: int) -> T_status:
        return self.__class__(self.num - other)
    def __iadd__(self, other: int) -> T_status:
        self.num += other
        return self
    def __isub__(self, other: int) -> T_status:
        self.num -= other
        return self

class ListStatus(_status):
    def __init__(self, s: Union[str, list]):
        if isinstance(s, str):
            self.list : list = eval(s)
        else:
            self.list = s
    def check(self) -> bool:
        return len(self.list) > 0
    def __repr__(self) -> str:
        return self.construct_repr(str(self.list))
    def __add__(self, other: list) -> T_status:
        return self.__class__(self.list + other)
    __sub__ = None
    def __iadd__(self, other: list) -> T_status:
        self.list += other
        return self
    __isub__ = None

@final
class SLe(ListStatus):
    id = 'l'
    is_debuff = True
    des = '乐不思蜀：今天每次接龙时，你进行一次判定。有3/4的几率你不得从该节点接龙。'
    def check(self) -> bool:
        return True
    def __str__(self) -> str:
        from .logic_dragon import Tree
        ids = [tree.id_str for tree in Tree.get_active()]
        return f"{self.des}\n\t你不能从{','.join(c for c in self.list if c in ids)}节点接龙。"

@final
class SKe(ListStatus):
    id = 'k'
    is_debuff = True
    des = '反转·乐不思蜀：今天每次接龙时，你进行一次判定。有1/4的几率你不得从该节点接龙。'
    def check(self) -> bool:
        return True
    def __str__(self) -> str:
        from .logic_dragon import Tree
        ids = [tree.id_str for tree in Tree.get_active()]
        return f"{self.des}\n\t你不能从{','.join(c for c in self.list if c in ids)}节点接龙。"

class _statusnull(_statusall):
    id_dict: Dict[str, TNStatus] = {}
def StatusNull(id: str):
    return _statusnull.id_dict[id]
class _statusdaily(_statusall):
    id_dict: Dict[str, TDStatus] = {}
def StatusDaily(id: str):
    return _statusdaily.id_dict[id]

@lru_cache(10)
def Card(id):
    if id in _card.card_id_dict:
        return _card.card_id_dict[id]
    else:
        raise ValueError("哈")

class card_meta(type):
    def __new__(cls, clsname, bases, attrs):
        if len(bases) != 0 and 'card_id_dict' in bases[0].__dict__:
            if status := attrs.get('status'):
                @classmethod
                async def use(self, user: User):
                    await user.add_status(status)
                attrs['use'] = use
            elif status := attrs.get('daily_status'):
                @classmethod
                async def use(self, user: User):
                    await user.add_daily_status(status)
                attrs['use'] = use
            elif status := attrs.get('limited_status'):
                @classmethod
                async def use(self, user: User):
                    await user.add_limited_status(status, *attrs['limited_init'])
                attrs['use'] = use
            elif status := attrs.get('global_status'):
                @classmethod
                async def use(self, user: User):
                    await Userme(user).add_status(status)
                attrs['use'] = use
            elif status := attrs.get('global_daily_status'):
                @classmethod
                async def use(self, user: User):
                    await Userme(user).add_daily_status(status)
                attrs['use'] = use
            elif status := attrs.get('global_limited_status'):
                @classmethod
                async def use(self, user: User):
                    await Userme(user).add_limited_status(status, *attrs['global_limited_init'])
                attrs['use'] = use
            elif status := attrs.get('on_draw_status'):
                to_send = attrs.get('on_draw_send')
                to_send_char = attrs.get('on_draw_send_char')
                @classmethod
                async def on_draw(self, user: User):
                    ret = await user.add_status(status)
                    if to_send and ret:
                        user.buf.send(to_send)
                    if to_send_char and ret:
                        user.send_char(to_send_char)
                attrs['on_draw'] = on_draw
            elif status := attrs.get('on_draw_daily_status'):
                to_send = attrs.get('on_draw_send')
                to_send_char = attrs.get('on_draw_send_char')
                @classmethod
                async def on_draw(self, user: User):
                    ret = await user.add_daily_status(status)
                    if to_send and ret:
                        user.buf.send(to_send)
                    if to_send_char and ret:
                        user.send_char(to_send_char)
                attrs['on_draw'] = on_draw
            elif status := attrs.get('on_draw_limited_status'):
                to_send = attrs.get('on_draw_send')
                to_send_char = attrs.get('on_draw_send_char')
                @classmethod
                async def on_draw(self, user: User):
                    ret = await user.add_limited_status(status, *attrs['limited_init'])
                    if to_send and ret:
                        user.buf.send(to_send)
                    if to_send_char and ret:
                        user.send_char(to_send_char)
                attrs['on_draw'] = on_draw
            elif status := attrs.get('on_draw_global_status'):
                to_send = attrs.get('on_draw_send')
                to_send_char = attrs.get('on_draw_send_char')
                @classmethod
                async def on_draw(self, user: User):
                    ret = await Userme(user).add_status(status)
                    if to_send and ret:
                        user.buf.send(to_send)
                attrs['on_draw'] = on_draw
            elif status := attrs.get('on_draw_global_daily_status'):
                to_send = attrs.get('on_draw_send')
                to_send_char = attrs.get('on_draw_send_char')
                @classmethod
                async def on_draw(self, user: User):
                    ret = await Userme(user).add_daily_status(status)
                    if to_send and ret:
                        user.buf.send(to_send)
                attrs['on_draw'] = on_draw
            elif status := attrs.get('on_draw_global_limited_status'):
                to_send = attrs.get('on_draw_send')
                to_send_char = attrs.get('on_draw_send_char')
                @classmethod
                async def on_draw(self, user: User):
                    ret = await Userme(user).add_limited_status(status, *attrs['limited_init'])
                    if to_send and ret:
                        user.buf.send(to_send)
                attrs['on_draw'] = on_draw
            c = type.__new__(cls, clsname, bases, attrs)
            bases[0].card_id_dict[attrs['id']] = c
        else:
            c = type.__new__(cls, clsname, bases, attrs)
        return c
    def __str__(self):
        return f"<卡牌: {self.name}, id: {self.id}>"
    @property
    # @abstractmethod
    def img(self):
        pass

class _card(IEventListener, metaclass=card_meta):
    card_id_dict: Dict[int, TCard] = {}
    name = ""
    hold_des = None
    id = -127
    newer = 0
    weight = 1
    positive = 0
    description = ""
    arg_num = 0
    consumed_on_draw = False
    failure_message = ""
    des_need_init = False
    @classmethod
    async def use(cls, user: User) -> None:
        pass
    @classmethod
    async def on_remove(cls, user: User) -> None:
        pass
    @classmethod
    async def on_draw(cls, user: User) -> None:
        pass
    @classmethod
    async def on_discard(cls, user: User) -> None:
        await cls.on_remove(user)
    @classmethod
    async def on_give(cls, user: User, target: User) -> None:
        pass
    @classmethod
    def can_use(cls, user: User, copy: bool) -> bool:
        return True
    @classmethod
    def brief_description(cls, qq):
        return f"{cls.id}. {cls.name}"
    @classmethod
    def full_description(cls, qq):
        return f"{cls.id}. {cls.name}\n\t{cls.description}"

class supernova(_card):
    name = "超新星"
    id = -65537
    positive = 1
    weight = 0
    description = "获得一张炙手可热的新卡。"
    @classmethod
    async def use(cls, user: User) -> None:
        max = 0
        l = []
        for id, card in _card.card_id_dict.items():
            if card.newer == max:
                l.append(card)
            elif card.newer > max:
                max = card.newer
                l = [card]
        c = random.choice(l)
        await user.draw(0, cards=[c])

class jiandiezhixing(_card):
    name = "邪恶的间谍行动～执行"
    id = -1
    positive = -1
    weight = 0
    description = "此牌不可被使用，通常情况下无法被抽到。当你弃置此牌时立即死亡。"
    failure_message = "此牌不可被使用！"
    @classmethod
    async def on_discard(cls, user: User):
        await user.death()
        return await super().on_discard(user)
    @classmethod
    def can_use(cls, user: User, copy: bool) -> bool:
        return False

class vampire(_card):
    name = "吸血鬼"
    id = -2
    positive = 1
    weight = 0
    description = "此牌通常情况下无法被抽到。2小时内免疫死亡。"
    @classmethod
    async def use(cls, user: User) -> None:
        await user.add_limited_status(SInvincible(datetime.now() + timedelta(hours=2)))
class SInvincible(TimedStatus):
    id = 'v'
    des = '无敌：免疫死亡。'
    @classmethod
    async def OnDeath(cls, count: TCount, user: 'User', killer: 'User', time: int, c: TCounter) -> Tuple[int, bool]:
        if await c.pierce():
            user.send_log("无敌的效果被幻想杀手消除了！")
            await user.remove_all_limited_status('v')
        else:
            user.send_log("触发了无敌的效果，免除死亡！")
            return time, True
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDeath: (Priority.OnDeath.invincible, cls)}

class fool(_card):
    name = "0 - 愚者"
    id = 0
    positive = -1
    newer = 2
    description = "抽到时附加效果：你下次使用卡牌无效。"
    consumed_on_draw = True
    on_draw_status = 'O'
class fool_s(_statusnull):
    id = 'O'
    des = "0 - 愚者：你下次使用卡牌无效。"
    is_debuff = True
    @classmethod
    async def BeforeCardUse(cls, count: TCount, user: 'User', card: TCard) -> Tuple[Optional[Awaitable]]:
        async def f():
            user.send_log("你太笨了！这张卡的使用无效！")
            await user.remove_status('O', remove_all=False)
        return f(),
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.BeforeCardUse: (Priority.BeforeCardUse.fool, cls)}

class magician(_card):
    name = "I - 魔术师"
    id = 1
    positive = 1
    description = "选择一张你的手牌（不可选择暴食的蜈蚣与组装机1型），发动3次该手牌的使用效果，并弃置之。此后一周内不得使用该卡。"
    @classmethod
    def can_use(cls, user: User, copy: bool) -> bool:
        return len(user.data.hand_card) >= (1 if copy else 2)
    @classmethod
    async def use(cls, user: User):
        async with user.choose_cards("请选择你手牌中的一张牌（不可选择暴食的蜈蚣与组装机1型），输入id号。", 1, 1,
                cards_can_not_choose=(56, 200), require_can_use=True) as l, check_active(l):
            card = Card(l[0])
            config.logger.dragon << f"【LOG】用户{user.qq}选择了卡牌{card.name}。"
            user.send_char('使用了三次卡牌：\n' + card.full_description(user.qq))
            await user.discard_cards([card])
            await user.use_card_effect(card)
            await user.use_card_effect(card)
            await user.use_card_effect(card)
            await user.add_limited_status(SCantUse(datetime.now() + timedelta(weeks=1), l[0]))
class SCantUse(TimedStatus):
    id = 'm'
    is_debuff = True
    @property
    def des(self):
        return f"疲劳：不可使用卡牌【{Card(self.card_id).name}】。"
    @property
    def brief_des(self):
        delta = self.time - datetime.now()
        min = delta.seconds // 60
        return f"疲劳【{Card(self.card_id).name}】\n\t结束时间：{f'{delta.days}日' if delta.days != 0 else ''}{f'{min // 60}时' if min // 60 != 0 else ''}{min % 60}分钟。"
    def __init__(self, s: Union[str, datetime], card_id: int):
        super().__init__(s)
        self.card_id = card_id
    def __repr__(self) -> str:
        return self.construct_repr(self.time.isoformat(), self.card_id)
    def __str__(self) -> str:
        delta = self.time - datetime.now()
        min = delta.seconds // 60
        return f"{self.des}\n\t结束时间：{f'{delta.days}日' if delta.days != 0 else ''}{f'{min // 60}时' if min // 60 != 0 else ''}{min % 60}分钟。"
    def __add__(self, other: timedelta) -> T_status:
        return self.__class__(self.time + other, self.card_id)
    def __sub__(self, other: timedelta) -> T_status:
        return self.__class__(self.time - other, self.card_id)
    def double(self) -> List[T_status]:
        return [self.__class__(self.time + (self.time - datetime.now()), self.card_id)]
    @classmethod
    async def OnUserUseCard(cls, count: TCount, user: 'User', card: TCard) -> Tuple[bool, str]:
        for s in count:
            if s.card_id == card.id:
                return False, f"你太疲劳了，不能使用{card.name}！"
        return True, ""
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnUserUseCard: (Priority.OnUserUseCard.cantuse, cls)}

class high_priestess(_card):
    name = "II - 女祭司"
    id = 2
    positive = 0
    description = "击毙当前周期内接龙次数最多的玩家。"
    @classmethod
    async def use(cls, user: User):
        from .logic_dragon import Tree
        counter = Counter([tree.qq for tree in itertools.chain(*itertools.chain(Tree._objs, *Tree.forests))])
        l = counter.most_common()
        ql = [qq for qq, time in l if time == l[0][1]]
        if len(ql) == 1:
            user.buf.send(f"当前周期内接龙次数最多的玩家是[CQ:at,qq={ql[0]}]！")
        else:
            user.buf.send(f"当前周期内接龙次数最多的玩家有{''.join(f'[CQ:at,qq={q}]' for q in ql)}！")
        for q in ql:
            await User(q, user.buf).killed(user)

class empress(_card):
    name = "III - 女皇"
    id = 3
    description = "你当前手牌中所有任务之石的可完成次数+3。如果当前手牌无任务之石，则为你派发一个可完成3次的任务，每次完成获得3击毙，跨日时消失。"
    positive = 1
    @classmethod
    async def use(cls, user: User) -> None:
        if Card(67) in user.data.hand_card:
            for q in global_state['quest'][str(user.qq)]:
                q["remain"] += 3
            user.send_char("的任务剩余次数增加了3！")
        else:
            await user.add_limited_status(SQuest(3, 3, n := get_mission()))
            user.send_char(f"获得了一个任务：{mission[n][1]}")

class emperor(_card):
    name = "IV - 皇帝"
    id = 4
    positive = 1
    description = "为你派发一个随机任务，可完成10次，每次完成获得2击毙，跨日时消失。"
    @classmethod
    async def use(cls, user: User) -> None:
        await user.add_limited_status(SQuest(10, 2, n := get_mission()))
        user.send_char(f"获得了一个任务：{mission[n][1]}")
@final
class SQuest(NumedStatus):
    id = 'q'
    @property
    def des(self):
        return f"今日任务：{mission[self.quest_id][1]}"
    @property
    def brief_des(self):
        return str(self)
    @property
    def is_debuff(self):
        return self.jibi < 0
    def __init__(self, s: Union[str, int], jibi: int, quest_id: int):
        super().__init__(s)
        self.jibi = jibi
        self.quest_id = quest_id
    def __repr__(self) -> str:
        return self.construct_repr(str(self.num), self.jibi, self.quest_id)
    def __str__(self) -> str:
        return f"{self.des}\n\t剩余次数：{self.num}次，完成获得击毙：{self.jibi}。"
    def double(self):
        return [self.__class__(self.num * 2, self.jibi, self.quest_id)]
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        changed = False
        for q in count:
            id, name, func = mission[q.quest_id]
            if func(branch.word):
                user.send_char(f"完成了每日任务：{name[:-1]}！奖励{q.jibi}击毙。此任务还可完成{q.num - 1}次。")
                user.log << f"完成了一次任务{name}，剩余{q.num - 1}次。"
                q.num -= 1
                await user.add_jibi(q.jibi)
                changed = True
        if changed:
            user.data.save_status_time()
    @classmethod
    async def OnNewDay(cls, count: TCount, user: 'User') -> Tuple[()]:
        await user.remove_all_limited_status('q')
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDragoned: (Priority.OnDragoned.quest, cls),
            UserEvt.OnNewDay: (Priority.OnNewDay.quest, cls)}

class hierophant(_card):
    name = "V - 教皇"
    id = 5
    positive = 1
    description = "你的下10次接龙中每次额外获得2击毙，但额外要求首尾接龙。"
    limited_status = 'f'
    limited_init = (10,)
    newer = 3
class hierophant_s(NumedStatus):
    id = 'f'
    des = "V - 教皇：你的下10次接龙中每次额外获得2击毙，但额外要求首尾接龙。"
    @classmethod
    async def BeforeDragoned(cls, count: TCount, user: User, word: str, parent: 'Tree') -> Tuple[bool, int, str]:
        if parent.word != '' and word != '' and parent.word[-1] != word[0]:
            return False, 0, "教皇说，你需要首尾接龙，接龙失败。"
        return True, 0, ""
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        user.send_log("收到了教皇奖励你的2击毙！")
        await user.add_jibi(2)
        count[0].num -= 1
        user.data.save_status_time()
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.BeforeDragoned: (Priority.BeforeDragoned.hierophant, cls),
            UserEvt.OnDragoned: (Priority.OnDragoned.hierophant, cls)}
class inv_hierophant_s(NumedStatus):
    id = 'e'
    des = "反转 - 教皇：你的下10次接龙中每次损失2击毙，并且额外要求尾首接龙。"
    is_debuff = True
    @classmethod
    async def BeforeDragoned(cls, count: TCount, user: User, word: str, parent: 'Tree') -> Tuple[bool, int, str]:
        if parent.word != '' and word != '' and parent.word[0] != word[-1]:
            return False, 0, "教皇说，你需要首尾接龙，接龙失败。"
        return True, 0, ""
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        user.send_log("被教皇扣除了2击毙！")
        await user.add_jibi(-2)
        count[0].num -= 1
        user.data.save_status_time()
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.BeforeDragoned: (Priority.BeforeDragoned.inv_hierophant, cls),
            UserEvt.OnDragoned: (Priority.OnDragoned.inv_hierophant, cls)}

class lovers(_card):
    name = "VI - 恋人"
    id = 6
    positive = 1
    description = "复活1名指定玩家。"
    @classmethod
    async def use(cls, user: User):
        if await user.choose():
            l = await user.buf.aget(prompt="请at一名玩家复活。\n",
                arg_filters=[
                        lambda s: re.findall(r'qq=(\d+)', str(s)),
                        validators.fit_size(1, 1, message="请at正确的人数。"),
                    ])
            u = User(l[0], user.buf)
            n = len(u.check_limited_status('d')) == 0
            await u.remove_all_limited_status('d')
            user.buf.send("已复活！" + ("（虽然目标并没有死亡）" if n else ''))

class strength(_card):
    name = "VIII - 力量"
    id = 8
    positive = 0
    description = "加倍你身上所有的非持有性状态，消耗2^n-1击毙，n为状态个数。击毙不足则无法使用。"
    failure_message = "你的击毙不足！"
    @classmethod
    def can_use(cls, user: User, copy: bool) -> bool:
        if len(user.check_limited_status('W', lambda o: 8 not in o.list)) > 0:
            return True
        l = len(user.data.status) + len(user.data.daily_status)
        l += len(user.data.status_time_checked)
        return user.data.jibi >= 2 ** l - 1
    @classmethod
    async def use(cls, user: User):
        l = len(user.data.status) + len(user.data.daily_status) + len(user.data.status_time_checked)
        if user.data.jibi < 2 ** l - 1:
            user.send_char("太弱小了，没有力量！")
            return
        else:
            user.send_char(f"花费了{2 ** l - 1}击毙！")
        await user.add_jibi(-2 ** l + 1)
        for c in user.data.status:
            await user.add_status(c)
        for c in user.data.daily_status:
            await user.add_daily_status(c)
        i = 0
        while i < len(user.data.status_time):
            t = user.data.status_time[i].double()
            user.data.status_time[i] = t[0]
            if len(t) == 2:
                user.data.status_time.insert(i + 1, t[1])
                i += 1
            i += 1
        user.data.save_status_time()

class hermit(_card):
    name = "IX - 隐者"
    id = 9
    positive = 1
    daily_status = 'Y'
    description = "今天你不会因为接到重复词或触雷而死亡。"
class hermit_s(_statusdaily):
    id = 'Y'
    des = "IX - 隐者：今天你不会因为接到重复词或触雷而死亡。"
    @classmethod
    async def OnDuplicatedWord(cls, count: TCount, user: User, word: str) -> Tuple[bool]:
        user.send_log("触发了IX - 隐者的效果，没死。")
        return True,
    @classmethod
    async def OnBombed(cls, count: TCount, user: User, word: str) -> Tuple[bool]:
        user.send_log("触发了IX - 隐者的效果，没死。")
        return True,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDuplicatedWord: (Priority.OnDuplicatedWord.hermit, cls),
            UserEvt.OnBombed: (Priority.OnBombed.hermit, cls)}

class wheel_of_fortune(_card):
    name = "X - 命运之轮"
    id = 10
    positive = 0
    global_daily_status = 'O'
    description = "直至下次刷新前，在商店增加抽奖机，可以花费5击毙抽奖。"
class wheel_of_fortune_s(_statusdaily):
    id = 'O'
    des = "X - 命运之轮：直至下次刷新前，在商店增加抽奖机，可以消耗5击毙抽奖。"
    is_global = True

class justice(_card):
    name = "XI - 正义"
    id = 11
    positive = 1
    description = "现在你身上每有一个状态，奖励你5击毙。"
    @classmethod
    async def use(cls, user: User):
        n = len(user.data.status) + len(user.data.daily_status) + len(user.data.status_time_checked)
        user.buf.send(f"你身上有{n}个状态，奖励你{n * 5}个击毙。")
        await user.add_jibi(n * 5)

class hanged_man(_card):
    name = "XII - 倒吊人"
    id = 12
    positive = 1
    description = "你立即死亡，然后免疫你下一次死亡。"
    @classmethod
    async def use(cls, user: User):
        await user.death()
        await user.add_status('r')
class miansi(_statusnull):
    id = 'r'
    des = "免死：免疫你下一次死亡。"
    @classmethod
    async def OnDeath(cls, count: TCount, user: User, killer: User, time: int, c: TCounter) -> Tuple[int, bool]:
        if await c.pierce():
            user.send_log("免死的效果被幻想杀手消除了！")
            await user.remove_status('r', remove_all=True)
            return time, False
        else:
            user.send_log("触发了免死的效果，免除死亡！")
            await user.remove_status('r', remove_all=False)
            return 0, True
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDeath: (Priority.OnDeath.miansi, cls)}

class death(_card):
    name = "XIII - 死神"
    id = 13
    positive = 0
    description = "今天的所有死亡时间加倍。"
    global_daily_status = 'D'
class death_s(_statusdaily):
    id = 'D'
    des = "XIII - 死神：今天的所有死亡时间加倍。"
    is_debuff = True
    is_global = True
    @classmethod
    async def OnDeath(cls, count: TCount, user: 'User', killer: 'User', time: int, c: TCounter) -> Tuple[int, bool]:
        return time * 2 ** count, False
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDeath: (Priority.OnDeath.death, cls)}

class temperance(_card):
    name = "XIV - 节制"
    id = 14
    positive = 0
    description = "随机抽取1名玩家，今天该玩家不能使用卡牌。"
    @classmethod
    async def use(cls, user: User) -> None:
        l = config.userdata.execute("select qq from dragon_data where dead=false").fetchall()
        q: int = random.choice(l)["qq"]
        user.send_char(f"抽到了[CQ:at,qq={q}]！")
        target = User(q, user.buf)
        atk = ATemperance(user, target)
        await target.attacked(user, atk)
class ATemperance(Attack):
    name = "攻击：节制"
    doublable = False
    async def self_action(self):
        await self.defender.add_daily_status('T')
class temperance_s(_statusdaily):
    id = 'T'
    des = "XIV - 节制：今天你不能使用卡牌。"
    is_debuff = True
    @classmethod
    async def OnUserUseCard(cls, count: TCount, user: User, card: TCard) -> Tuple[bool, str]:
        return False, "你因XIV - 节制的效果，不能使用卡牌！"
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnUserUseCard: (Priority.OnUserUseCard.temperance, cls)}

class devil(_card):
    name = "XV - 恶魔"
    id = 15
    positive = 1
    description = "击毙上一位使用卡牌的人。"
    @classmethod
    async def use(cls, user: User):
        q = global_state['last_card_user']
        u = User(q, user.buf)
        user.buf.send(f'[CQ:at,qq={q}]被你击毙了！')
        await u.killed(user)

class tower(_card):
    name = "XVI - 高塔"
    id = 16
    positive = 0
    description = "随机解除至多3个雷，随机击毙3个玩家。"
    @classmethod
    async def use(cls, user: User) -> None:
        from .logic_dragon import bombs, remove_bomb
        for i in range(3):
            if len(bombs) == 0:
                break
            b = random.choice(bombs)
            remove_bomb(b)
        l = config.userdata.execute("select qq from dragon_data where dead=false").fetchall()
        l: List[int] = [c['qq'] for c in l if c['qq'] != 0]
        p: List[int] = []
        for i in range(3):
            p.append(random.choice(l))
            l.remove(p[-1])
        user.send_char(f"抽到了{'，'.join(f'[CQ:at,qq={q}]' for q in p)}！")
        for q in p:
            await User(q, user.buf).killed(user)

class star(_card):
    name = "XVII - 星星"
    id = 17
    positive = 0
    description = "今天的每个词有10%的几率进入奖励词池。"
    global_daily_status = 't'
class star_s(_statusdaily):
    id = 't'
    des = "XVII - 星星：今天的每个词有10%的几率进入奖励词池。"
    is_global = True
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        if random.random() > 0.9 ** count:
            from .logic_dragon import add_keyword
            add_keyword(branch.word)
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDragoned: (Priority.OnDragoned.star, cls)}

class moon(_card):
    name = "XVIII - 月亮"
    id = 18
    positive = 1
    newer = 3
    description = "下次有人接到隐藏奖励词前，隐藏奖励词数量加1。"
    global_status = 'k'
class moon_s(_statusnull):
    id = 'k'
    des = "XVIII - 月亮：下次有人接到隐藏奖励词前，隐藏奖励词数量加1。"
    is_global = True
    @classmethod
    async def on_add(cls, count: TCount):
        from .logic_dragon import add_hidden_keyword
        to_add_amount = count - min(0, 2 + me.check_status('k') - me.check_status('o'))
        if to_add_amount != 0:
            add_hidden_keyword(count=to_add_amount)
    @classmethod
    async def on_remove(cls, remove_all=True):
        from .logic_dragon import remove_hidden_keyword
        count = me.check_status('k') if remove_all else 1
        to_remove_amount = count - min(0, 2 + me.check_status('k') - me.check_status('o'))
        if to_remove_amount != 0:
            remove_hidden_keyword(count=to_remove_amount)
    @classmethod
    async def OnHiddenKeyword(cls, count: TCount, user: 'User', word: str, parent: 'Tree', keyword: str) -> Tuple[int]:
        await Userme(user).remove_status('k', remove_all=False)
        return 0,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnHiddenKeyword: (Priority.OnHiddenKeyword.moon, cls)}
class inv_moon_s(_statusnull):
    id = 'o'
    des = "反转 - 月亮：下次有人接到隐藏奖励词前，隐藏奖励词数量减1，但最少为1。"
    is_global = True
    @classmethod
    async def on_add(cls, count: TCount):
        from .logic_dragon import remove_hidden_keyword
        to_remove_amount = count - min(0, 2 + me.check_status('k') - me.check_status('o'))
        if to_remove_amount != 0:
            remove_hidden_keyword(count=to_remove_amount)
    @classmethod
    async def on_remove(cls, remove_all=True):
        from .logic_dragon import add_hidden_keyword
        count = me.check_status('o') if remove_all else 1
        to_add_amount = count - min(0, 2 + me.check_status('k') - me.check_status('o'))
        if to_add_amount != 0:
            add_hidden_keyword(count=to_add_amount)
    @classmethod
    async def OnHiddenKeyword(cls, count: TCount, user: 'User', word: str, parent: 'Tree', keyword: str) -> Tuple[int]:
        await Userme(user).remove_status('o', remove_all=False)
        return 0,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnHiddenKeyword: (Priority.OnHiddenKeyword.inv_moon, cls)}

class sun(_card):
    name = "XIX - 太阳"
    id = 19
    positive = 1
    description = "随机揭示一个隐藏奖励词。"
    @classmethod
    async def use(cls, user: User):
        from .logic_dragon import hidden_keyword
        user.buf.send("你揭示的一个隐藏奖励词是：" + random.choice(hidden_keyword))

class judgement(_card):
    name = "XX - 审判"
    id = 20
    positive = 0
    newer = 3
    description = "若你今天接龙次数小于5，则扣除20击毙，若你今天接龙次数大于20，则获得20击毙。"
    @classmethod
    async def use(cls, user: User):
        n = [tree.qq for tree in itertools.chain(*itertools.chain(Tree._objs, *Tree.forests))].count(user.qq)
        user.send_log(f"今天的接龙次数是{n}次，", end='')
        if n < 5:
            user.buf.send("扣除" + user.char + "20击毙！")
            await user.add_jibi(-20)
        elif n > 20:
            user.send_char("获得20击毙！")
            await user.add_jibi(20)
        else:
            user.buf.send('')

class world(_card):
    name = "XXI - 世界"
    id = 21
    positive = 0
    global_daily_status = 's'
    description = "除大病一场外，所有“直到跨日为止”的效果延长至明天。"
class world_s(_statusdaily):
    id = 's'
    des = "XXI - 世界：除大病一场外，所有“直到跨日为止”的效果延长至明天。"

class dabingyichang(_card):
    name = "大病一场"
    id = 30
    positive = -1
    description = "抽到时，直到跨日前不得接龙。"
    on_draw_daily_status = 'd'
    on_draw_send_char = "病了！直到跨日前不得接龙。"
    is_debuff = True
    consumed_on_draw = True
class shengbing(_statusdaily):
    id = 'd'
    des = "生病：直到跨日前不可接龙。"
    is_debuff = True
    @classmethod
    async def BeforeDragoned(cls, count: TCount, user: User, word: str, parent: 'Tree') -> Tuple[bool, int, str]:
        return False, 0, "你病了，不能接龙！"
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.BeforeDragoned: (Priority.BeforeDragoned.shengbing, cls)}

class caipiaozhongjiang(_card):
    name = "彩票中奖"
    id = 31
    positive = 1
    description = "抽到时，你立即获得20击毙与两张牌。"
    consumed_on_draw = True
    @classmethod
    async def on_draw(cls, user: User):
        user.send_char("中奖了！获得20击毙与两张牌。")
        await user.add_jibi(20)
        await user.draw(2)

class wenhuazixin(_card):
    name = "文化自信"
    id = 32
    positive = 0
    description = "清除所有全局状态。"
    @classmethod
    async def use(cls, user: User) -> None:
        me.status = ""
        me.daily_status = ""
        me.status_time.clear()
        me._reregister_things()

class wuzhongshengyou(_card):
    name = "无中生有"
    id = 36
    positive = 1
    description = "摸两张牌。"
    @classmethod
    async def use(cls, user: User):
        await user.draw(2)

class tiesuolianhuan(_card):
    name = "铁索连环"
    id = 38
    positive = 1
    description = "指定至多两名玩家进入或解除其连环状态。任何处于连环状态的玩家被击毙时所有连环状态的玩家也被击毙并失去此效果。"
    @classmethod
    async def use(cls, user: User):
        if await user.choose():
            config.logger.dragon << f"【LOG】询问用户{user.qq}铁索连环。"
            l: List[int] = await user.buf.aget(prompt="请at群内至多两名玩家进行铁索连环。\n",
                arg_filters=[
                        lambda s: [int(r) for r in re.findall(r'qq=(\d+)', str(s))],
                        validators.ensure_true(lambda s: config.selfqq not in s, message="不能选我！"),
                        validators.fit_size(1, 2, message="请at正确的人数。")
                    ])
            config.logger.dragon << f"【LOG】用户{user.qq}铁索连环选择{l}。"
            for target in l:
                u = User(target, user.buf)
                atk = ATiesuolianhuan(user, u)
                await u.attacked(user, atk)
            user.buf.send("成功切换连环状态！")
            save_global_state()
class ATiesuolianhuan(Attack):
    name = "铁索连环"
    doublable = False
    async def self_action(self):
        if self.defender.check_status('l'):
            await self.defender.remove_status('l')
        else:
            await self.defender.add_status('l')
class tiesuolianhuan_s(_statusnull):
    id = 'l'
    des = "铁索连环：任何处于连环状态的玩家被击毙时所有连环状态的玩家也被击毙并失去此效果。"
    is_debuff = True
    @classmethod
    async def OnDeath(cls, count: TCount, user: 'User', killer: 'User', time: int, c: TCounter) -> Tuple[int, bool]:
        if await c.pierce():
            await user.remove_status('l', remove_all=True)
            user.send_log("铁索连环的效果被幻想杀手消除了！")
        else:
            all_qqs: List[int] = []
            for r in config.userdata.execute("select qq from dragon_data where status like '%l%'").fetchall():
                if r['qq'] == user.qq: continue
                all_qqs.append(r['qq'])
            user.buf.send(f"由于铁索连环的效果，{' '.join(f'[CQ:at,qq={target}]' for target in all_qqs)}也一起死了！")
            user.log << f"触发了铁索连环的效果至{all_qqs}。"
            for q in all_qqs:
                await (u := User(q, user.buf)).remove_status('l')
                await u.killed(user, hour=0, minute=time)
            await user.remove_status('l')
        return time, False
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDeath: (Priority.OnDeath.tiesuolianhuan, cls)}

class minus1ma(_card):
    name = "-1马"
    id = 39
    daily_status = 'm'
    positive = 1
    description = "今天你可以少隔一个接龙，但最少隔一个。"
class minus1ma_s(_statusdaily):
    id = 'm'
    des = "-1马：今天你可以少隔一个接龙，但最少隔一个。"
    @classmethod
    async def BeforeDragoned(cls, count: TCount, user: User, word: str, parent: 'Tree') -> Tuple[bool, int, str]:
        return True, -1, ""
    @classmethod
    def register(cls):
        return {UserEvt.BeforeDragoned: (Priority.BeforeDragoned.minus1ma, cls)}
class plus1ma_s(_statusdaily):
    id = 'M'
    des = "+1马：今天你必须额外隔一个才能接龙。"
    is_debuff = True
    @classmethod
    async def BeforeDragoned(cls, count: TCount, user: User, word: str, parent: 'Tree') -> Tuple[bool, int, str]:
        return True, 1, ""
    @classmethod
    def register(cls):
        return {UserEvt.BeforeDragoned: (Priority.BeforeDragoned.plus1ma, cls)}

class dongfeng(_card):
    name = "东风（🀀）"
    id = 40
    positive = 0
    description = "可邀请持有南风、西风、北风的群友各一位进行一局麻将对战，根据结算顺位获得奖励（一位20击毙，二位10击毙，三位5击毙，四位被击毙），对局结束后此牌被消耗。"

class nanfeng(_card):
    name = "南风（🀁）"
    id = 41
    positive = 0
    description = "可邀请持有东风、西风、北风的群友各一位进行一局麻将对战，根据结算顺位获得奖励（一位20击毙，二位10击毙，三位5击毙，四位被击毙），对局结束后此牌被消耗。"

class xifeng(_card):
    name = "西风（🀂）"
    id = 42
    positive = 0
    description = "可邀请持有东风、南风、北风的群友各一位进行一局麻将对战，根据结算顺位获得奖励（一位20击毙，二位10击毙，三位5击毙，四位被击毙），对局结束后此牌被消耗。"

class beifeng(_card):
    name = "北风（🀃）"
    id = 43
    positive = 0
    description = "可邀请持有东风、南风、西风的群友各一位进行一局麻将对战，根据结算顺位获得奖励（一位20击毙，二位10击毙，三位5击毙，四位被击毙），对局结束后此牌被消耗。"

class baiban(_card):
    name = "白板（🀆）"
    id = 44
    positive = 1
    description = "选择你手牌中的一张牌，执行其使用效果。"
    @classmethod
    def can_use(cls, user: User, copy: bool) -> bool:
        return len(user.data.hand_card) >= (1 if copy else 2)
    @classmethod
    async def use(cls, user: User):
        async with user.choose_cards("请选择你手牌中的一张牌复制，输入id号。", 1, 1,
            cards_can_not_choose=(44,), require_can_use=True) as l, check_active(l):
            card = Card(l[0])
            config.logger.dragon << f"【LOG】用户{user.qq}选择了卡牌{card.name}。"
            user.send_char('使用了卡牌：\n' + card.full_description(user.qq))
            await user.use_card_effect(card)

class hongzhong(_card):
    name = "红中（🀄）"
    id = 46
    positive = 1
    description = "在同时有人驳回和同意时，可以使用此卡强制通过。"

class sihuihuibizhiyao(_card):
    name = "死秽回避之药"
    id = 50
    positive = 1
    status = 's'
    description = "你下次死亡时自动消耗5击毙免除死亡。若击毙不足则不发动。"
class sihuihuibizhiyao_s(_statusnull):
    id = 's'
    des = '死秽回避之药：下次死亡时自动消耗5击毙免除死亡。若击毙不足则不发动。'
    @classmethod
    async def OnDeath(cls, count: TCount, user: User, killer: User, time: int, c: TCounter) -> Tuple[int, bool]:
        if await c.pierce():
            user.send_log("死秽回避之药的效果被幻想杀手消除了！")
            await user.remove_status('s', remove_all=True)
            return time, False
        elif await user.add_jibi(-5, is_buy=True):
            user.send_log("触发了死秽回避之药的效果，免除死亡！")
            await user.remove_status('s', remove_all=False)
            return time, True
        return time, False
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDeath: (Priority.OnDeath.sihuihuibizhiyao, cls)}
class inv_sihuihuibizhiyao_s(_statusnull):
    id = 't'
    des = '反转·死秽回避之药：你下次死亡时获得5击毙，但是死亡时间增加2h。'
    @classmethod
    async def OnDeath(cls, count: TCount, user: User, killer: User, time: int, c: TCounter) -> Tuple[int, bool]:
        if await c.pierce():
            user.send_log("反转·死秽回避之药的效果被幻想杀手消除了！")
            await user.remove_status('t')
            return time, False
        user.send_log(f"触发了{count}次反转·死秽回避之药的效果，增加{5 * count}击毙，死亡时间增加{2 * count}小时！")
        await user.add_jibi(5 * count)
        await user.remove_status('t')
        return time + 120 * count, False
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDeath: (Priority.OnDeath.inv_sihuihuibizhiyao, cls)}

class huiye(_card):
    name = "辉夜姬的秘密宝箱"
    id = 52
    positive = 1
    status = 'x'
    description = "你下一次死亡的时候奖励你抽一张卡。"
class huiye_s(_statusnull):
    id = 'x'
    des = '辉夜姬的秘密宝箱：下一次死亡的时候奖励抽一张卡。'
    @classmethod
    async def OnDeath(cls, count: TCount, user: User, killer: User, time: int, c: TCounter) -> Tuple[int, bool]:
        await user.remove_status('x')
        if await c.pierce():
            user.send_log("辉夜姬的秘密宝箱的效果被幻想杀手消除了！")
        else:
            user.send_log(f"触发了辉夜姬的秘密宝箱！奖励抽卡{count}张。")
            await user.draw(count)
        return time, False
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDeath: (Priority.OnDeath.huiye, cls)}
class inv_huiye_s(_statusnull):
    id = 'y'
    des = '反转·辉夜姬的秘密宝箱：你下一次死亡的时候随机弃一张牌。'
    is_debuff = True
    @classmethod
    async def OnDeath(cls, count: TCount, user: User, killer: User, time: int, c: TCounter) -> Tuple[int, bool]:
        await user.remove_status('y')
        if await c.pierce():
            user.send_log("反转·辉夜姬的秘密宝箱的效果被幻想杀手消除了！")
        else:
            user.send_log(f"触发了反转·辉夜姬的秘密宝箱！随机弃{count}张卡。")
            x = min(len(user.data.hand_card), count)
            l = copy(user.data.hand_card)
            l2: List[TCard] = []
            for i in range(x):
                l2.append(random.choice(l))
                l.remove(l2[-1])
            user.send_log("弃了：" + '，'.join(c.name for c in l2) + "。")
            await user.discard_cards(l2)
        return time, False
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDeath: (Priority.OnDeath.inv_huiye, cls)}

class blank(_card):
    name = "空白卡牌"
    id = 53
    positive = -1
    description = "使用时弃置所有手牌。此牌不可因手牌超出上限而被弃置。"
    @classmethod
    async def use(cls, user: User):
        user.buf.send("你弃光了所有手牌。")
        await user.discard_cards(copy(user.data.hand_card))

class dragontube(_card):
    name = "龙之烟管"
    id = 54
    positive = 1
    description = "你今天通过普通接龙获得的击毙上限增加10。"
    @classmethod
    async def use(cls, user: User):
        user.data.today_jibi += 10
        config.logger.dragon << f"【LOG】用户{user.qq}增加了接龙击毙上限至{user.data.today_jibi}。"
        user.buf.send("已增加。")

class xingyuntujiao(_card):
    name = "幸运兔脚"
    id = 55
    positive = 1
    description = "抽取一张正面卡并立即发动其使用效果。"
    @classmethod
    async def use(cls, user: User):
        c = draw_card({1})
        await user.draw_and_use(c)

class baoshidewugong(_card):
    name = "暴食的蜈蚣"
    id = 56
    positive = 1
    description = "你的手牌上限永久+1。"
    @classmethod
    async def use(cls, user: User):
        user.data.card_limit_raw += 1
        config.logger.dragon << f"【LOG】用户{user.qq}增加了raw手牌上限至{user.data.card_limit_raw}。"

class zhaocaimao(_card):
    name = "擅长做生意的招财猫"
    id = 57
    positive = 1
    description = "你今天可以额外购买3次商店里的购买卡牌。"
    @classmethod
    async def use(cls, user: User) -> None:
        user.data.shop_drawn_card += 3
        config.logger.dragon << f"【LOG】用户{user.qq}增加了可购买卡牌至{user.data.shop_drawn_card}。"

class plus2(_card):
    name = "+2"
    id = 60
    global_status = '+'
    positive = 0
    description = "下一个接龙的人摸一张非负面卡和一张非正面卡。"
class plus2_s(_statusnull):
    id = '+'
    des = "+2：下一个接龙的人摸一张非负面卡和一张非正面卡。"
    is_global = True
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        await Userme(user).remove_status('+')
        user.send_char(f"触发了{count}次+2的效果，摸{count}张非正面牌与{count}张非负面牌！")
        user.log << f"触发了+2的效果。"
        cards = list(itertools.chain(*[[draw_card({-1, 0}), draw_card({0, 1})] for i in range(count)]))
        await user.draw(0, cards=cards)
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDragoned: (Priority.OnDragoned.plus2, cls)}

class dream(_card):
    name = "这一切都是主角做的一场梦"
    id = 62
    newer = 3
    positive = 0
    description = "50%概率回溯到随机一个节点，50%概率随机一个节点立即分叉。"
    @classmethod
    async def use(cls, user: User) -> None:
        node = random.choice(list(itertools.chain(*Tree._objs)))
        if random.random() < 0.5:
            user.buf.send(f"回溯到了节点{node.id_str}！")
            for n in node.childs:
                n.remove()
            from .logic_dragon import rewrite_log_file
            rewrite_log_file()
        else:
            user.buf.send(f"节点{node.id_str}被分叉了！")
            config.logger.dragon << f"【LOG】节点{node.id_str}被分叉了。"
            node.fork = True

class hezuowujian(_card):
    name = "合作无间"
    id = 63
    positive = 1
    description = "拆除所有雷，每个雷有70%的概率被拆除。"
    @classmethod
    async def use(cls, user: User):
        from .logic_dragon import remove_all_bomb
        remove_all_bomb(0.7)

class ourostone(_card):
    name = "衔尾蛇之石"
    id = 66
    positive = 0
    description = "修改当前规则至首尾接龙直至跨日。"
    @classmethod
    async def use(cls, user: User) -> None:
        u = Userme(user)
        if u.check_daily_status('o'):
            await u.remove_daily_status('o')
        if u.check_daily_status('p'):
            await u.remove_daily_status('p')
        await u.add_daily_status('o')
class ourostone_s(_statusdaily):
    id = 'o'
    des = "衔尾蛇之石：规则为首尾接龙直至跨日。"
    is_global = True
    @classmethod
    async def BeforeDragoned(cls, count: TCount, user: User, word: str, parent: 'Tree') -> Tuple[bool, int, str]:
        if parent.word != '' and word != '' and parent.word[-1] != word[0]:
            return False, 0, "当前规则为首尾接龙，接龙失败。"
        return True, 0, ""
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.BeforeDragoned: (Priority.BeforeDragoned.ourostone, cls)}
class inv_ourostone_s(_statusdaily):
    id = 'p'
    des = "石之蛇尾衔：规则为尾首接龙直至跨日。"
    is_global = True
    @classmethod
    async def BeforeDragoned(cls, count: TCount, user: User, word: str, parent: 'Tree') -> Tuple[bool, int, str]:
        if parent.word != '' and word != '' and parent.word[0] != word[-1]:
            return False, 0, "当前规则为尾首接龙，接龙失败。"
        return True, 0, ""
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.BeforeDragoned: (Priority.BeforeDragoned.ourostone, cls)}

class queststone(_card):
    name = "任务之石"
    id = 67
    positive = 1
    description = "持有此石时，你每天会刷新一个接龙任务。每次完成接龙任务可以获得3击毙，每天最多3次。使用将丢弃此石。"
    des_need_init = True
    @classmethod
    def quest_des(cls, qq: int):
        q = str(qq)
        m = mission[global_state['quest'][q][quest_print_aux[q]]['id']][1]
        remain = global_state['quest'][q][quest_print_aux[q]]['remain']
        quest_print_aux[q] += 1
        if quest_print_aux[q] >= len(global_state['quest'][q]):
            quest_print_aux[q] = 0
        return "\t当前任务：" + m + f"剩余{remain}次。"
    @classmethod
    def full_description(cls, qq: int):
        return super().full_description(qq) + "\n" + cls.quest_des(qq)
    @classmethod
    async def on_draw(cls, user: User):
        q = str(user.qq)
        if q not in global_state['quest']:
            global_state['quest'][q] = []
            quest_print_aux[q] = 0
        global_state['quest'][q].append({'id': (i := get_mission()), 'remain': 3})
        config.logger.dragon << f"【LOG】用户{user.qq}刷新了一个任务{mission[i][1]}，现有任务：{[mission[c['id']][1] for c in global_state['quest'][q]]}。"
        save_global_state()
    @classmethod
    async def on_remove(cls, user: User):
        q = str(user.qq)
        i = global_state['quest'][q][quest_print_aux[q]]['id']
        del global_state['quest'][q][quest_print_aux[q]]
        if quest_print_aux[q] >= len(mission):
            quest_print_aux[q] = 0
        config.logger.dragon << f"【LOG】用户{user.qq}删除了一个任务{mission[i][1]}，现有任务：{[mission[c['id']][1] for c in global_state['quest'][q]]}。"
        save_global_state()
    @classmethod
    async def on_give(cls, user: User, target: User):
        q = str(user.qq)
        m = global_state['quest'][q][quest_print_aux[q]]
        i = m['id']
        del global_state['quest'][q][quest_print_aux[q]]
        if quest_print_aux[q] >= len(mission):
            quest_print_aux[q] = 0
        config.logger.dragon << f"【LOG】用户{user.qq}删除了一个任务{mission[i][1]}，现有任务：{[mission[c['id']][1] for c in global_state['quest'][q]]}。"
        t = str(target.qq)
        if t not in global_state['quest']:
            global_state['quest'][t] = []
            quest_print_aux[t] = 0
        global_state['quest'][t].append(m)
        config.logger.dragon << f"【LOG】用户{target.qq}增加了一个任务{mission[i][1]}，现有任务：{[mission[c['id']][1] for c in global_state['quest'][t]]}。"
        save_global_state()
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        l = global_state['quest'].get(str(user.qq))
        for m in l:
            if m['remain'] > 0:
                id, name, func = mission[m['id']]
                if func(branch.word):
                    user.send_char(f"完成了任务：{name[:-1]}！奖励3击毙。此任务还可完成{m['remain'] - 1}次。")
                    user.log << f"完成了一次任务{name}，剩余{m['remain'] - 1}次。"
                    m['remain'] -= 1
                    await user.add_jibi(3)
                    save_global_state()
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDragoned: (Priority.OnDragoned.queststone, cls)}

class cunqianguan(_card):
    name = "存钱罐"
    id = 70
    global_status = 'm'
    positive = 1
    description = "下次触发隐藏词的奖励+10击毙。"
class cunqianguan_s(_statusnull):
    id = 'm'
    des = "存钱罐：下次触发隐藏词的奖励+10击毙。"
    is_global = True
    @classmethod
    async def OnHiddenKeyword(cls, count: TCount, user: 'User', word: str, parent: 'Tree', keyword: str) -> Tuple[int]:
        user.send_log(f"触发了存钱罐，奖励+{count * 10}击毙！")
        await Userme(user).remove_status('m')
        return count * 10,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnHiddenKeyword: (Priority.OnHiddenKeyword.cunqianguan, cls)}
class inv_cunqianguan_s(_statusnull):
    id = 'M'
    des = "反转·存钱罐：下次触发隐藏词的奖励-10击毙。"
    is_global = True
    is_debuff = True
    @classmethod
    async def OnHiddenKeyword(cls, count: TCount, user: 'User', word: str, parent: 'Tree', keyword: str) -> Tuple[int]:
        user.send_log(f"触发了反转·存钱罐，奖励-{count * 10}击毙！")
        await Userme(user).remove_status('M')
        return -count * 10,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnHiddenKeyword: (Priority.OnHiddenKeyword.inv_cunqianguan, cls)}

class hongsezhihuan(_card):
    name = "虹色之环"
    id = 71
    positive = 0
    status = 'h'
    description = "下次你死亡时，有1/2几率闪避，1/2几率死亡时间+1小时。"
class hongsezhihuan_s(_statusnull):
    id = 'h'
    des = '虹色之环：下次死亡时，有1/2几率闪避，1/2几率死亡时间+1小时。'
    @classmethod
    async def OnDeath(cls, count: TCount, user: User, killer: User, time: int, c: TCounter) -> Tuple[int, bool]:
        if await c.pierce():
            user.send_log("虹色之环的效果被幻想杀手消除了！")
            await user.remove_status('h', remove_all=True)
            return time, False
        for a in range(count):
            await user.remove_status('h', remove_all=False)
            if random.randint(0, 1) == 0:
                user.send_log("触发了虹色之环，闪避了死亡！")
                return time, True
            else:
                time += 60
                user.send_log("触发虹色之环闪避失败，死亡时间+1h！")
        return time, False
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDeath: (Priority.OnDeath.hongsezhihuan, cls)}

class liwujiaohuan(_card):
    name = "礼物交换"
    id = 72
    positive = 1
    description = "最近接过龙的玩家每人抽出一张手牌集合在一起随机分配。"
    @classmethod
    async def use(cls, user: User):
        user.data.set_cards()
        config.logger.dragon << f"【LOG】用户{user.qq}交换了最近接过龙的玩家的手牌。"
        qqs = set(tree.qq for tree in itertools.chain(*itertools.chain(Tree._objs, *Tree.forests)))
        from .logic_dragon import get_yesterday_qq
        qqs |= get_yesterday_qq()
        l = [User(qq, user.buf) for qq in qqs if qq != 0]
        config.logger.dragon << f"【LOG】这些人的手牌为：{','.join(f'{user.qq}: {cards_to_str(user.data.hand_card)}' for user in l)}。"
        all_users: List[User] = []
        all_cards: List[Tuple[User, TCard]] = []
        for u in l:
            if len(u.data.hand_card) != 0:
                atk = ALiwujiaohuan(user, u, all_users)
                await u.attacked(user, atk)
        config.logger.dragon << f"【LOG】所有参与交换的人为{[c.qq for c in all_users]}。"
        for u in all_users:
            c = random.choice(u.data.hand_card)
            config.logger.dragon << f"【LOG】用户{u.qq}取出了手牌{c.name}。"
            all_cards.append((u, c))
        random.shuffle(all_cards)
        lose = get = None
        for u, (u2, c) in zip(all_users, all_cards):
            u.data.hand_card.append(c)
            u2.data.hand_card.remove(c)
            await c.on_give(u2, u)
            config.logger.dragon << f"【LOG】{u.qq}从{u2.qq}处收到了{c}。"
            if u == user:
                get = c
            elif u2 == user:
                lose = c
        if lose is None and get is None:
            user.buf.send("你交换了大家的手牌！")
        else:
            user.buf.send(f"你用一张：\n{lose}\n换到了一张：\n{get}")
class ALiwujiaohuan(Attack):
    name = "礼物交换"
    doublable = False
    def __init__(self, attacker: 'User', defender: 'User', todo_list: List):
        self.todo_list = todo_list
        super().__init__(attacker, defender)
    def rebound(self) -> bool:
        return True
    async def self_action(self):
        self.todo_list.append(self.defender)

class xingyunhufu(_card):
    name = "幸运护符"
    id = 73
    hold_des = '幸运护符：无法使用其他卡牌。每进行两次接龙额外获得一个击毙（每天上限为5击毙）。'
    positive = 1
    description = "持有此卡时，你无法使用其他卡牌。你每进行两次接龙额外获得一个击毙（每天上限为5击毙）。使用将丢弃这张卡。"
    @classmethod
    async def OnUserUseCard(cls, count: TCount, user: User, card: TCard) -> Tuple[bool, str]:
        if card.id != 73:
            return False, "你因幸运护符的效果，不可使用其他手牌！"
        return True, ""
    @classmethod
    async def OnDragoned(cls, count: TCount, user: User, branch: 'Tree', first10: bool) -> Tuple[()]:
        if user.data.today_jibi % 2 == 1:
            user.buf.send(f"你因为幸运护符的效果，额外奖励{count}击毙。")
            await user.add_jibi(count)
    @classmethod
    def register(cls):
        return {UserEvt.OnUserUseCard: (Priority.OnUserUseCard.xingyunhufu, cls),
            UserEvt.OnDragoned: (Priority.OnDragoned.xingyunhufu, cls)}

class jisuzhuangzhi(_card):
    name = "极速装置"
    id = 74
    status = 'z'
    status_des = '极速装置：你下次可以连续接龙两次。'
    positive = 1
    description = '你下次你可以连续接龙两次。'
class jisuzhuangzhi_s(_statusnull):
    id = 'z'
    des = "极速装置：你下次可以连续接龙两次。"
    @classmethod
    async def CheckSuguri(cls, count: TCount, user: 'User', word: str, parent: 'Tree') -> Tuple[bool]:
        await user.remove_status('z', remove_all=False)
        return True,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.CheckSuguri: (Priority.CheckSuguri.jisuzhuangzhi, cls)}

class huxiangjiaohuan(_card):
    name = '互相交换'
    id = 75
    positive = 0
    description = "下一个接中隐藏奖励词的玩家手牌与你互换。"
    @classmethod
    async def use(cls, user: User):
        l = me.check_limited_status('x')
        if l:
            l[0] += [user.qq]
            user.log << f"被加入交换堆栈，现为{l[0].list}。"
            me.save_status_time()
        else:
            await Userme(user).add_limited_status(SHuxiangjiaohuan([user.qq]))
class SHuxiangjiaohuan(ListStatus):
    id = 'x'
    des = "互相交换：下一个接中隐藏奖励词的玩家手牌与某人互换。"
    is_global = True
    @classmethod
    async def OnHiddenKeyword(cls, count: TCount, user: 'User', word: str, parent: 'Tree', keyword: str) -> Tuple[int]:
        to_exchange = count[0].list.pop()
        u = User(to_exchange, user.buf)
        atk = AHuxiangjiaohuan(u, user)
        await user.attacked(u, atk)
        return 0,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnHiddenKeyword: (Priority.OnHiddenKeyword.huxiangjiaohuan, cls)}
class AHuxiangjiaohuan(Attack):
    name = "攻击：互相交换"
    doublable = False
    async def self_action(self):
        self.defender.send_char(f"与[CQ:at,qq={self.attacker.qq}]交换了手牌！")
        jibi = (self.defender.data.jibi, self.attacker.data.jibi)
        self.defender.log << f"与{self.attacker.qq}交换了手牌。"
        await self.defender.exchange(self.attacker)

class zhongshendexixi(_card):
    name = "众神的嬉戏"
    id = 76
    positive = 0
    description = '抽取一张卡并立即发动其使用效果。'
    @classmethod
    async def use(cls, user: User):
        c = draw_card()
        await user.draw_and_use(c)

class lveduozhebopu(_card):
    name = "掠夺者啵噗"
    id = 77
    positive = 1
    hold_des = '掠夺者啵噗：你每天可从所接龙的人处偷取1击毙，每人限一次，最多10击毙，若目标没有击毙则不可偷取。'
    description = "持有此卡时，你每天你可从你所接龙的人处偷取1击毙，每人限一次，最多10击毙，若目标没有击毙则不可偷取。使用或死亡时将丢弃这张卡。"
    @classmethod
    async def on_draw(cls, user: User):
        if str(user.qq) not in global_state['steal']:
            global_state['steal'][str(user.qq)] = {'time': 0, 'user': []}
        save_global_state()
    @classmethod
    async def on_remove(cls, user: User):
        if Card(77) not in user.data.hand_card and str(user.qq) in global_state['steal']:
            del global_state['steal'][str(user.qq)]
        save_global_state()
    @classmethod
    async def on_give(cls, user: User, target: User):
        global_state['steal'][str(target.qq)] = global_state['steal'][str(user.qq)]
        if Card(77) not in user.data.hand_card and str(user.qq) in global_state['steal']:
            del global_state['steal'][str(user.qq)]
        save_global_state()
    @classmethod
    async def OnDeath(cls, count: TCount, user: User, killer: User, time: int, c: TCounter) -> Tuple[int, bool]:
        user.send_log(f"的{f'{count}张' if count > 1 else ''}掠夺者啵噗被弃了！")
        await user.discard_cards([cls] * count)
        return time, False
    @classmethod
    async def OnDragoned(cls, count: TCount, user: User, branch: 'Tree', first10: bool) -> Tuple[()]:
        global global_state
        last_qq = branch.parent.qq
        qq = user.qq
        if branch.parent.id != (0, 0):
            last = User(last_qq, user.buf)
            if last_qq not in global_state['steal'][str(qq)]['user'] and global_state['steal'][str(qq)]['time'] < 10:
                global_state['steal'][str(qq)]['time'] += 1
                global_state['steal'][str(qq)]['user'].append(last_qq)
                save_global_state()
                atk = AStealJibi(user, last, count)
                await last.attacked(user, atk)
    @classmethod
    def register(cls):
        return {UserEvt.OnDeath: (Priority.OnDeath.lveduozhebopu, cls),
            UserEvt.OnDragoned: (Priority.OnDragoned.lveduozhebopu, cls)}
class AStealJibi(Attack):
    name = "偷击毙"
    def __init__(self, attacker: 'User', defender: 'User', count: int):
        self.count = count
        super().__init__(attacker, defender)
    async def self_action(self):
        self.attacker.log << f"触发了{self.count}次掠夺者啵噗的效果，偷取了{self.defender.qq}击毙，剩余偷取次数{(9 - global_state['steal'][str(self.attacker.qq)]['time']) if str(self.attacker.qq) in global_state['steal'] else 'null'}。"
        if (p := self.defender.data.jibi) > 0:
            n = self.count * self.multiplier
            self.attacker.send_char(f"从上一名玩家处偷取了{min(n, p)}击毙！")
            await self.defender.add_jibi(-n)
            await self.attacker.add_jibi(min(n, p))

class jiandieyubei(_card):
    name = "邪恶的间谍行动～预备"
    id = 78
    positive = 0
    global_daily_status = 'j'
    description = "今日卡池中有一定概率出现【邪恶的间谍行动~执行】。"
class jiandieyubei_s(_statusdaily):
    id = 'j'
    des = "邪恶的间谍行动～预备：今日卡池中有一定概率出现【邪恶的间谍行动~执行】。"

class qijimanbu(_card):
    name = "奇迹漫步"
    id = 79
    positive = 1
    description = "弃置你所有手牌，并摸取等量的非负面牌。"
    @classmethod
    async def use(cls, user: User):
        n = len(user.data.hand_card)
        await user.discard_cards(copy(user.data.hand_card))
        await user.draw(n, positive={0, 1})

class ComicSans(_card): # TODO
    name = "Comic Sans"
    id = 80
    global_daily_status = 'c'
    positive = 0
    description = "七海千春今天所有生成的图片均使用Comic Sans作为西文字体（中文使用华文彩云）。"
class ComicSans_s(_statusdaily):
    id = 'c'
    des = 'Comic Sans：七海千春今天所有生成的图片均使用Comic Sans作为西文字体（中文使用华文彩云）。'

class PC(_card):
    name = "PC"
    id = 81
    positive = 1
    description = '今天接过龙的所有人立刻获得胜利。'
    @classmethod
    async def use(cls, user: User):
        user.buf.send("今天接龙的所有人都赢了！恭喜你们！")
        from .logic_dragon import Tree
        qqs = [tree.qq for tree in itertools.chain(*itertools.chain(Tree._objs, *Tree.forests))]
        for qq in set(qqs):
            await User(qq, user.buf).add_daily_status('W')
class win(_statusdaily):
    id = 'W'
    des = "胜利：恭喜，今天你赢了！"
class defeat(_statusdaily):
    id = 'X'
    des = "失败：对不起，今天你输了！"
    is_debuff = True

class suicideking(_card):
    name = "自杀之王（♥K）"
    id = 90
    positive = -1
    description = "抽到时立即死亡。"
    consumed_on_draw = True
    @classmethod
    async def on_draw(cls, user: User):
        user.send_char("抽到了自杀之王，" + user.char + "死了！")
        await user.death()

class zhu(_card):
    name = "猪（♠Q）"
    id = 91
    positive = -1
    description = "抽到时损失20击毙（但不会扣至0以下）。"
    consumed_on_draw = True
    @classmethod
    async def on_draw(cls, user: User):
        await user.add_jibi(-20)
        user.send_char("抽到了猪，损失了20击毙！")

class yang(_card):
    name = "羊（♦J）"
    id = 92
    positive = 1
    description = "抽到时获得20击毙。"
    consumed_on_draw = True
    @classmethod
    async def on_draw(cls, user: User):
        await user.add_jibi(20)
        user.send_char("抽到了羊，获得了20击毙！")

class bianyaqi(_card):
    name = "变压器（♣10）"
    id = 93
    status = '2'
    positive = 0
    description = "下一次你的击毙变动变动值加倍。"
class bianyaqi_s(_statusnull):
    id = '2'
    des = "变压器（♣10）：下一次击毙变动变动值加倍。"
    @classmethod
    async def CheckJibiSpend(cls, count: TCount, user: 'User', jibi: int) -> Tuple[int]:
        return jibi * 2 ** count,
    @classmethod
    async def OnJibiChange(cls, count: TCount, user: 'User', jibi: int, is_buy: bool) -> Tuple[int]:
        await user.remove_status('2')
        user.send_log(f'触发了{f"{count}次" if count != 1 else ""}变压器的效果，获得击毙变为{jibi * 2 ** count}！')
        return jibi * 2 ** count,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.CheckJibiSpend: (Priority.CheckJibiSpend.bianyaqi, cls),
            UserEvt.OnJibiChange: (Priority.OnJibiChange.bianyaqi, cls)}
class inv_bianyaqi_s(_statusnull):
    id = '1'
    des = "反转·变压器（♣10）：下一次你的击毙变动变动值减半。"
    @classmethod
    async def CheckJibiSpend(cls, count: TCount, user: 'User', jibi: int) -> Tuple[int]:
        return ceil(jibi / 2 ** count),
    @classmethod
    async def OnJibiChange(cls, count: TCount, user: 'User', jibi: int, is_buy: bool) -> Tuple[int]:
        user.remove_status('2')
        return ceil(jibi / 2 ** count),
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.CheckJibiSpend: (Priority.CheckJibiSpend.bianyaqi, cls),
            UserEvt.OnJibiChange: (Priority.OnJibiChange.bianyaqi, cls)}

class guanggaopai(_card):
    name = "广告牌"
    id = 94
    positive = 0
    consumed_on_draw = True
    @classmethod
    @property
    def description(self):
        return random.choice([
            "广告位永久招租，联系邮箱：shedarshian@gmail.com",
            "我给你找了个厂，虹龙洞里挖龙珠的，两班倒，20多金点包酸素勾玉，一天活很多，也不会很闲，明天你就去上班吧，不想看到你整天在群里接龙，无所事事了，是谁我就不在群里指出来了，等下你没面子。\n\t先填个表https://store.steampowered.com/app/1566410",
            "MUASTG，车万原作游戏前沿逆向研究，主要研究弹幕判定、射击火力、ZUN引擎弹幕设计等，曾发表车万顶刊华胥三绝，有意者加群796991184",
            "你想明白生命的意义吗？你想真正……的活着吗？\n\t☑下载战斗天邪鬼：https://pan.baidu.com/s/1FIAxhHIaggld3yRAyFr9FA",
            "肥料掺了金坷垃，一袋能顶两袋撒！肥料掺了金坷垃，不流失，不浪费，不蒸发，能吸收两米下的氮磷钾！",
            "下蛋公鸡，公鸡中的战斗鸡，哦也",
            "欢迎关注甜品站弹幕研究协会，国内一流的东方STG学术交流平台，从避弹，打分到neta，可以学到各种高端姿势：https://www.isndes.com/ms?m=2"
        ])

class jiaodai(_card):
    name = "布莱恩科技航空专用强化胶带FAL84型"
    id = 100
    description = "取消掉你身上的至多6种负面状态（不包括死亡），并免疫下次即刻生效的负面状态（不包括死亡）。"
    @classmethod
    async def use(cls, user: User) -> None:
        has = 6
        for c in map(StatusNull, user.data.status):
            if c.id != 'd' and c.is_debuff and has > 0:
                has -= 1
                user.send_char(f"的{c.des[:c.des.index('：')]}被取消了！")
                await user.remove_status(c.id, remove_all=False)
        for c in map(StatusDaily, user.data.daily_status):
            if c.id != 'd' and c.is_debuff and has > 0:
                has -= 1
                user.send_char(f"的{c.des[:c.des.index('：')]}被取消了！")
                await user.remove_daily_status(c.id, remove_all=False)
        i = 0
        while i < len(user.data.status_time_checked):
            s = user.data.status_time[i]
            if s.id != 'd' and not isinstance(s, Swufazhandou) and s.is_debuff and has > 0:
                has -= 1
                des = s.des
                user.send_log(f"的{des[:des.index('：')]}被取消了！")
                await user.remove_limited_status(s)
            else:
                i += 1
        user.data.save_status_time()
        await user.add_status('8')
class jiaodai_s(_statusnull):
    id = '8'
    des = "布莱恩科技航空专用强化胶带FAL84型：免疫你下次即刻生效的负面状态（不包括死亡）。"
    @classmethod
    async def OnStatusAdd(cls, count: TCount, user: 'User', status: TStatusAll, count2: int) -> Tuple[int]:
        if status.is_debuff and status.id != 'd' and status is not Swufazhandou:
            for i in range(min(count, count2)):
                await user.remove_status('8', remove_all=False)
            user.send_log("触发了胶带的效果，免除此负面状态！")
            return max(0, count2 - count),
        return count2,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnStatusAdd: (Priority.OnStatusAdd.jiaodai, cls)}
class inv_jiaodai_s(_statusnull):
    id = '9'
    des = "反转·布莱恩科技航空专用强化胶带FAL84型：免疫你下次即刻生效的非负面状态。"
    is_debuff = True
    @classmethod
    async def OnStatusAdd(cls, count: TCount, user: 'User', status: TStatusAll, count2: int) -> Tuple[int]:
        if not status.is_debuff:
            for i in range(min(count, count2)):
                await user.remove_status('9', remove_all=False)
            user.send_log("触发了反转·胶带的效果，免除此非负面状态！")
            return max(0, count2 - count),
        return count2,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnStatusAdd: (Priority.OnStatusAdd.inv_jiaodai, cls)}

class ZPM(_card):
    name = "Zero-Point Module"
    id = 101
    positive = 1
    description = "抽到时附加buff：若你当前击毙少于100，则每次接龙为你额外提供1击毙，若你当前击毙多于100，此buff立即消失。"
    on_draw_status = 'Z'
    newer = 3
    consumed_on_draw = True
class SZPM(_statusnull):
    id = 'Z'
    des = "零点模块：若你当前击毙少于100，则每次接龙为你额外提供1击毙，若你当前击毙多于100，此buff立即消失。"
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        if user.data.jibi > 100:
            user.send_char(f"已经不再需要零点模块了！")
            await user.remove_status('Z')
        else:
            user.send_char(f"因为零点模块额外获得{count}击毙！")
            await user.add_jibi(count)
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDragoned: (Priority.OnDragoned.zpm, cls)}

class McGuffium239(_card):
    name = "Mc Guffium 239"
    id = 102
    positive = 1
    status = 'G'
    description = "下一次礼物交换不对你生效。"
class McGuffium239_s(_statusnull):
    id = 'G'
    des = "Mc Guffium 239：下一次礼物交换不对你生效。"
    @classmethod
    async def OnAttacked(cls, count: TCount, user: 'User', attack: 'Attack', c: TCounter) -> Tuple[bool]:
        if isinstance(attack, ALiwujiaohuan):
            if await c.pierce():
                user.send_log("Mc Guffium 239的效果被幻想杀手消除了！")
                await user.remove_status('G', remove_all=True)
            else:
                user.buf.send(f"玩家{user.qq}触发了Mc Guffium 239，礼物交换对{user.char}无效！")
                user.log << f"触发了Mc Guffium 239。"
                await user.remove_status('G', remove_all=False)
                return True,
        return False,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnAttacked: (Priority.OnAttacked.McGuffium239, cls)}

class jujifashu(_card):
    name = "聚集法术"
    id = 105
    positive = 1
    description = "将两张手牌的id相加变为新的手牌。若这两牌id之和不是已有卡牌的id，则变为【邪恶的间谍行动～执行】。"
    failure_message = "你的手牌不足，无法使用！"
    @classmethod
    def can_use(cls, user: User, copy: bool) -> bool:
        return len(user.data.hand_card) >= (2 if copy else 3)
    @classmethod
    async def use(cls, user: User) -> None:
        async with user.choose_cards("请选择你手牌中的两张牌聚集，输入id号。", 2, 2) as l, check_active(l):
            await user.remove_cards([Card(l[0]), Card(l[1])])
            id_new = l[0] + l[1]
            if id_new not in _card.card_id_dict:
                user.buf.send(f"不存在id为{id_new}的牌！")
                id_new = -1
            else:
                user.send_char(f"将这两张牌合成为了id为{id_new}的牌！")
            c = Card(id_new)
            await user.draw(0, cards=[c])

class liebianfashu(_card):
    name = "裂变法术"
    id = 106
    positive = 1
    description = "将一张手牌变为两张随机牌，这两张牌的id之和为之前的卡牌的id。若不存在这样的组合，则变为两张【邪恶的间谍行动～执行】。"
    failure_message = "你的手牌不足，无法使用！"
    @classmethod
    def can_use(cls, user: User, copy: bool) -> bool:
        return len(user.data.hand_card) >= (1 if copy else 2)
    @classmethod
    async def use(cls, user: User) -> None:
        async with user.choose_cards("请选择你手牌中的一张牌裂变，输入id号。", 1, 1) as l, check_active(l):
            await user.remove_cards([Card(l[0])])
            l2 = [(id, l[0] - id) for id in _card.card_id_dict if l[0] - id in _card.card_id_dict]
            if len(l2) == 0:
                user.buf.send(f"不存在两张和为{l[0]}的牌！")
                id_new = (-1, -1)
            else:
                id_new = random.choice(l2)
                user.send_char(f"将这张牌分解为了id为{id_new[0]}与{id_new[1]}的牌！")
            await user.draw(0, cards=[Card(id_new[0]), Card(id_new[1])])

class jingxingfashu(_card):
    name = "警醒法术"
    id = 107
    positive = 1
    description = "揭示至多三个雷。"
    @classmethod
    async def use(cls, user: User) -> None:
        from .logic_dragon import bombs
        k = min(len(bombs), 3)
        user.send_char(f"揭示的{k}个雷为：", end='')
        l = []
        for i in range(k):
            l.append(random.choice(bombs))
            while l[-1] in l[:-1]:
                l[-1] = random.choice(bombs)
        user.buf.send('，'.join(l) + '。')

class xiaohunfashu(_card):
    name = "销魂法术"
    id = 108
    positive = 1
    description = "对指定玩家发动，该玩家的每条状态都有1/2的概率被清除（统治不列颠除外）；或是发送qq=2711644761对千春使用，消除【XXI-世界】外的所有全局状态。"
    @classmethod
    async def use(cls, user: User) -> None:
        if await user.choose():
            config.logger.dragon << f"【LOG】询问用户{user.qq}选择玩家。"
            qq: int = (await user.buf.aget(prompt="请at群内一名玩家。\n",
                arg_filters=[
                        lambda s: [int(r) for r in re.findall(r'qq=(\d+)', str(s))],
                        validators.fit_size(1, 1, message="请at正确的人数。")
                    ]))[0]
            if qq == config.selfqq:
                user.send_log("选择了千春！消除了【XXI-世界】外的所有全局状态！")
                me.status = ""
                s = me.check_daily_status('s')
                me.daily_status = s * 's'
                me.status_time.clear()
                me._reregister_things()
            else:
                user.send_log(f"选择了玩家{qq}！")
                u = User(qq, user.buf)
                atk = AXiaohunfashu(user, u)
                await u.attacked(user, atk)
class AXiaohunfashu(Attack):
    name = "攻击：销魂法术"
    async def self_action(self):
        # 永久状态
        for c in self.defender.data.status:
            if random.random() > 0.5 ** self.multiplier or c == 'W':
                continue
            await self.defender.remove_status(c, remove_all=False)
            des = StatusNull(c).des
            self.defender.send_log(f"的{des[:des.index('：')]}被消除了！")
        # 每日状态
        for c in self.defender.data.daily_status:
            if random.random() > 0.5 ** self.multiplier:
                continue
            await self.defender.remove_daily_status(c, remove_all=False)
            des = StatusDaily(c).des
            self.defender.send_log(f"的{des[:des.index('：')]}被消除了！")
        # 带附加值的状态
        l = self.defender.data.status_time_checked
        i = 0
        while i < len(l):
            if random.random() > 0.5 ** self.multiplier:
                i += 1
            else:
                des = l[i].des
                self.defender.send_log(f"的{des[:des.index('：')]}被消除了！")
                l.pop(i)
        self.defender.data.save_status_time()

class ranshefashu(_card):
    name = "蚺虵法术"
    id = 109
    positive = 1
    newer = 3
    description = "对指定玩家发动，该玩家当日每次接龙需额外遵循首尾接龙规则。"
    @classmethod
    async def use(cls, user: User) -> None:
        if await user.choose():
            config.logger.dragon << f"【LOG】询问用户{user.qq}选择玩家。"
            qq: int = (await user.buf.aget(prompt="请at群内一名玩家。\n",
                arg_filters=[
                        lambda s: [int(r) for r in re.findall(r'qq=(\d+)', str(s))],
                        validators.fit_size(1, 1, message="请at正确的人数。")
                    ]))[0]
            u = User(qq, user.buf)
            atk = Aranshefashu(user, u)
            await u.attacked(user, atk)
class Aranshefashu(Attack):
    name = "攻击：蚺虵法术"
    async def self_action(self):
        await self.defender.add_daily_status('R')
        self.defender.send_char("今天接龙需额外遵循首尾接龙规则！")
class ranshefashu_s(_statusdaily):
    id = 'R'
    des = "蚺虵法术：你当日每次接龙需额外遵循首尾接龙规则。"
    @classmethod
    async def BeforeDragoned(cls, count: TCount, user: 'User', word: str, parent: 'Tree') -> Tuple[bool, int, str]:
        if parent.word != '' and word != '' and parent.word[-1] != word[0]:
            return False, 0, "你需额外遵循首尾接龙规则，接龙失败。"
        return True, 0, ""
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.BeforeDragoned: (Priority.BeforeDragoned.ranshefashu, cls)}
class inv_ranshefashu_s(_statusdaily):
    id = 'Z'
    des = "反转·蚺虵法术：你当日每次接龙需额外遵循尾首接龙规则。"
    @classmethod
    async def BeforeDragoned(cls, count: TCount, user: 'User', word: str, parent: 'Tree') -> Tuple[bool, int, str]:
        if parent.word != '' and word != '' and parent.word[0] != word[-1]:
            return False, 0, "你需额外遵循尾首接龙规则，接龙失败。"
        return True, 0, ""
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.BeforeDragoned: (Priority.BeforeDragoned.inv_ranshefashu, cls)}

class yuexiabianhua(_card):
    name = "月下彼岸花"
    id = 110
    positive = -1
    description = "抽到时附加buff：你每接龙三次会损失1击毙，效果发动20次消失。"
    on_draw_limited_status = 'b'
    consumed_on_draw = True
    limited_init = (60,)
@final
class SBian(NumedStatus):
    id = 'b'
    des = '月下彼岸花：你每接龙三次会损失1击毙。'
    is_debuff = True
    def __str__(self) -> str:
        return f"{self.des}\n\t剩余次数：{(self.num + 2) // 3}次。"
    def double(self) -> List[T_status]:
        return [self, self.__class__(self.num)]
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        for b in count:
            b -= 1
            if b.num % 3 == 0:
                user.send_char("触发了月下彼岸花的效果，损失1击毙！")
                await user.add_jibi(-1)
            user.data.save_status_time()
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDragoned: (Priority.OnDragoned.bianhua, cls)}
@final
class SCian(NumedStatus):
    id = 'c'
    des = '反转·月下彼岸花：你每接龙三次会获得1击毙。'
    def __str__(self) -> str:
        return f"{self.des}\n\t剩余次数：{(self.num + 2) // 3}次。"
    def double(self) -> List[T_status]:
        return [self, self.__class__(self.num)]
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        for b in count:
            b -= 1
            if b.num % 3 == 0:
                user.send_char("触发了反转·月下彼岸花的效果，获得1击毙！")
                await user.add_jibi(1)
            user.data.save_status_time()
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDragoned: (Priority.OnDragoned.inv_bianhua, cls)}

class panjuea(_card):
    name = "判决α"
    id = 111
    description = "抽到时附加buff：判决α。你接龙后，将此buff传递给你接龙后第五次接龙的玩家。与判决β同时存在时立刻死亡。"
    positive = -1
    on_draw_status = 'A'
    is_debuff = True
    consumed_on_draw = True
class panjuea_s(_statusnull):
    id = 'A'
    des = "判决α：你下次接龙后，将此buff传递给你接龙后第五次接龙的玩家。与判决β同时存在时立刻死亡。"
    is_debuff = True
    @classmethod
    async def OnStatusAdd(cls, count: TCount, user: 'User', status: TStatusAll, count2: int) -> Tuple[int]:
        if status is panjueb_s or status is panjueb_activated_s:
            user.send_char("从五个人前面接来了判决β！")
            for i in range(min(count, count2)):
                await user.remove_status('A', remove_all=False)
            await user.add_limited_status(Swufazhandou(240))
            return max(0, count2 - count),
        return count2,
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        user.log << f"的{count}个判决α激活了。"
        await user.remove_status('A', remove_all=True)
        await user.add_status('a', count=count)
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnStatusAdd: (Priority.OnStatusAdd.panjue, cls),
            UserEvt.OnDragoned: (Priority.OnDragoned.panjue, cls)}
class panjuea_activated_s(_statusnull):
    id = 'a'
    des = "判决α：将此buff传递给你上次接龙后第五次接龙的玩家。与判决β同时存在时立刻死亡。"
    is_debuff = True
    @classmethod
    async def OnStatusAdd(cls, count: TCount, user: 'User', status: TStatusAll, count2: int) -> Tuple[int]:
        if status is panjueb_s or status is panjueb_activated_s:
            user.send_char("从五个人前面接来了判决β！")
            for i in range(min(count, count2)):
                await user.remove_status('a', remove_all=False)
            await user.add_limited_status(Swufazhandou(240))
            return max(0, count2 - count),
        return count2,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnStatusAdd: (Priority.OnStatusAdd.panjue_activated, cls)}

class panjueb(_card):
    name = "判决β"
    id = 112
    description = "抽到时附加buff：判决β。你接龙后，将此buff传递给你接龙后第五次接龙的玩家。与判决α同时存在时立刻死亡。"
    positive = -1
    on_draw_status = 'B'
    is_debuff = True
    consumed_on_draw = True
class panjueb_s(_statusnull):
    id = 'B'
    des = "判决β：你下次接龙后，将此buff传递给你接龙后第五次接龙的玩家。与判决α同时存在时立刻死亡。"
    is_debuff = True
    @classmethod
    async def OnStatusAdd(cls, count: TCount, user: 'User', status: TStatusAll, count2: int) -> Tuple[int]:
        if status is panjuea_s or status is panjuea_activated_s:
            user.send_char("从五个人前面接来了判决α！")
            for i in range(min(count, count2)):
                user.remove_status('B', remove_all=False)
            await user.add_limited_status(Swufazhandou(240))
            return max(0, count2 - count),
        return count2,
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        user.log << f"的{count}个判决β激活了。"
        await user.remove_status('B', remove_all=True)
        await user.add_status('b', count=count)
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnStatusAdd: (Priority.OnStatusAdd.panjue, cls),
            UserEvt.OnDragoned: (Priority.OnDragoned.panjue, cls)}
class panjueb_activated_s(_statusnull):
    id = 'b'
    des = "判决β：将此buff传递给你上次接龙后第五次接龙的玩家。与判决α同时存在时立刻死亡。"
    is_debuff = True
    @classmethod
    async def OnStatusAdd(cls, count: TCount, user: 'User', status: TStatusAll, count2: int) -> Tuple[int]:
        if status is panjuea_s or status is panjuea_activated_s:
            user.send_char("从五个人前面接来了判决α！")
            for i in range(min(count, count2)):
                await user.remove_status('b', remove_all=False)
            await user.add_limited_status(Swufazhandou(240))
            return max(0, count2 - count),
        return count2,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnStatusAdd: (Priority.OnStatusAdd.panjue_activated, cls)}
class panjue_checker(IEventListener):
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        if (nd := branch.before(5)) and nd.qq != config.selfqq and nd.qq != 0 and (u := User(nd.qq, user.buf)) != user:
            if na := u.check_status('a'):
                await u.remove_status('a')
                user.log << f"从五个人前面接来了{na}个判决α。"
                await user.add_status('a', count=na)
            if nb := u.check_status('b'):
                await u.remove_status('b')
                user.log << f"从五个人前面接来了{nb}个判决β。"
                await user.add_status('b', count=nb)
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDragoned: (Priority.OnDragoned.panjuecheck, cls)}
UserData.register_checker(panjue_checker)

class Swufazhandou(TimedStatus):
    id = 'D'
    is_debuff = True
    des = "无法战斗：不可接龙。"
    @classmethod
    async def BeforeDragoned(cls, count: TCount, user: 'User', word: str, parent: 'Tree') -> Tuple[bool, int, str]:
        return False, 0, '你无法战斗，不能接龙！'
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.BeforeDragoned: (Priority.BeforeDragoned.wufazhandou, cls)}
class Sshuairuo(TimedStatus):
    id = 'S'
    is_debuff = True 
    des = "衰弱：你所有的击毙收入减少为75%。"
    @classmethod
    async def OnJibiChange(cls, count: TCount, user: 'User', jibi: int, is_buy: bool) -> Tuple[int]:
        if jibi > 0:
            njibi = ceil(0.75*jibi)
            user.send_log(f"触发了衰弱的效果，获得击毙减少为{njibi}。")
            return njibi,
        return jibi,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnJibiChange: (Priority.OnJibiChange.shuairuo, cls)}

class dihuopenfa(_card):
    name = "地火喷发"
    id = 114
    description = "今天所有的接龙词都有10%的几率变成地雷。"
    positive = 0
    global_daily_status = 'B'
class dihuopenfa_s(_statusdaily):
    id = 'B'
    des = "地火喷发：今天所有的接龙词都有10%的几率变成地雷。"
    is_global = True
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        if random.random() > 0.9 ** count:
            from .logic_dragon import add_bomb
            add_bomb(branch.word)
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDragoned: (Priority.OnDragoned.dihuopenfa, cls)}

class gaojie(_card):
    name = "告解"
    id = 116
    description = "今天每次你获得击毙时额外获得1击毙。"
    positive = 1
    daily_status = '@'
class gaojie_s(_statusdaily):
    id = '@'
    des = "告解：今日每次你获得击毙时额外获得1击毙。"
    @classmethod
    async def OnJibiChange(cls, count: TCount, user: 'User', jibi: int, is_buy: bool) -> Tuple[int]:
        if jibi > 0:
            user.send_log(f"触发了{f'{count}次' if count > 1 else ''}告解的效果，获得击毙加{count}。")
            return jibi + count,
        return jibi,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnJibiChange: (Priority.OnJibiChange.gaojie, cls)}
class inv_gaojie_s(_statusdaily):
    id = '#'
    des = "反转·告解：今日每次你获得击毙时少获得1击毙。"
    @classmethod
    async def OnJibiChange(cls, count: TCount, user: 'User', jibi: int, is_buy: bool) -> Tuple[int]:
        if jibi > 0:
            user.send_log(f"触发了{f'{count}次' if count > 1 else ''}反转·告解的效果，获得击毙减{count}。")
            return max(jibi - count, 0),
        return jibi,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnJibiChange: (Priority.OnJibiChange.inv_gaojie, cls)}

class shenmouyuanlv(_card):
    name = "深谋远虑之策"
    id = 117
    description = "当你一次使用/损失了超过你现有击毙一半以上的击毙时，恢复这些击毙。"
    positive = 0
    status = 'n'
class shenmouyuanlv_s(_statusnull):
    id = 'n'
    des = "深谋远虑之策：当你一次使用/损失了超过你现有击毙一半以上的击毙时，恢复这些击毙。"
    @classmethod
    async def OnJibiChange(cls, count: TCount, user: 'User', jibi: int, is_buy: bool) -> Tuple[int]:
        if jibi < 0 and -jibi > user.data.jibi / 2:
            await user.remove_status('n', remove_all=False)
            user.send_char(f"触发了深谋远虑之策的效果，此次免单！")
            return 0,
        return jibi,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnJibiChange: (Priority.OnJibiChange.shenmouyuanlv, cls)}

class mixidiyatu(_card):
    name = "通灵之术-密西迪亚兔"
    id = 118
    description = "你的头上会出现一只可爱的小兔子。"
    positive = 0
    status = 'R'
class mixidiyatu_s(_statusnull):
    id = 'R'
    des = "通灵之术-密西迪亚兔：你的头上出现了一只可爱的小兔子。"
class inv_mixidiyatu_s(_statusnull):
    id = 'Q'
    des = "反转·通灵之术-密西迪亚兔：你的屁股上出现了一只可爱的小兔子。"

class wardenspaean(_card):
    name = "光阴神的礼赞凯歌"
    id = 119
    description = "免疫三次负面状态或消耗全部次数免疫大病一场，或主动使用解除大病一场。"
    positive = 1
    newer = 2
    @classmethod
    async def use(cls, user: User) -> None:
        for c in map(StatusDaily, user.data.daily_status):
            if c is shengbing:
                user.send_char(f"的大病一场被取消了！")
                user.remove_daily_status('d')
            else:
                await user.add_limited_status('w',3)
class wardenspaean_s(NumedStatus):
    id = 'w'
    des = "光阴神的礼赞凯歌：免疫三次负面状态或消耗全部次数免疫大病一场。"
    def __str__(self) -> str:
        return f"{self.des}\n\t剩余次数：{self.num}次。"
    def double(self) -> List[T_status]:
        return [self, self.__class__(self.num)]
    @classmethod
    async def OnStatusAdd(cls, count: TCount, user: 'User', status: TStatusAll, count2: int) -> Tuple[int]:
        for i in count:
            if status.is_debuff and status.id != 'd' and status is not Swufazhandou:
                if i.num >= count2:
                    i.num -= count2
                    user.send_log(f"触发了凯歌的效果，免除此负面状态！")
                    user.data.save_status_time()
                    return 0,
                else:
                    count2 -= i.num
                    i.num = 0
                    user.send_log(f"触发了凯歌的效果，免除此负面状态！")
                    continue
            elif status is shengbing and i.num == 3:
                i.num -= 3
                user.send_log(f"触发了凯歌的效果，免除大病一场！")
                user.data.save_status_time()
                return 0,
        user.data.save_status_time()
        return count2,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnStatusAdd: (Priority.OnStatusAdd.paean, cls)}

class imaginebreaker(_card):
    name = "幻想杀手"
    id = 120
    description = "你的下一次攻击无视对方的所有反制效果，下一次目标为你的攻击无效。以上两项只能发动一项。"
    positive = 1
    status = '0'
class imaginebreaker_s(_statusnull):
    id = '0'
    des = "幻想杀手：你的下一次攻击无视对方的所有反制效果，下一次目标为你的攻击无效。以上两项只能发动一项。"
    @classmethod
    async def OnAttack(cls, count: TCount, user: 'User', attack: 'Attack', c: TCounter) -> Tuple[bool]:
        async def pierce_f():
            user.send_char(f"触发了幻想杀手的效果，无视了对方的反制！")
            user.log << f"{user.char}触发了幻想杀手（攻击）的效果。"
            await user.remove_status('0', remove_all=False)
            return True
        c.pierce = async_data_saved(pierce_f)
        return False,
    @classmethod
    async def OnAttacked(cls, count: TCount, user: 'User', attack: 'Attack', c: TCounter) -> Tuple[bool]:
        if await c.pierce():
            c.pierce = nothing
            user.buf.send("但", end='')
            user.send_log("触发了幻想杀手的效果，防住了对方的攻击！")
            return False,
        user.send_log("触发了幻想杀手的效果，防住了对方的攻击！")
        await user.remove_status('0', remove_all=False)
        return True,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnAttack: (Priority.OnAttack.imaginebreaker, cls),
            UserEvt.OnAttacked: (Priority.OnAttacked.imaginebreaker, cls)}

class vector(_card):
    name = "矢量操作"
    id = 121
    description = "你的下一次攻击效果加倍，下一次对你的攻击反弹至攻击者，免除你下一次触雷。以上三项只能发动一项。"
    positive = 1
    status = 'v'
class vector_s(_statusnull):
    id = 'v'
    des = "矢量操作：你的下一次攻击效果加倍，下一次对你的攻击反弹至攻击者，免除你下一次触雷。以上三项只能发动一项。"
    @classmethod
    async def OnAttack(cls, count: TCount, user: 'User', attack: 'Attack', c: TCounter) -> Tuple[bool]:
        if attack.doublable:
            user.send_log("触发了矢量操作的效果，攻击加倍！")
            await user.remove_status('v', remove_all=False)
            return attack.double(),
        return False,
    @classmethod
    async def OnAttacked(cls, count: TCount, user: 'User', attack: 'Attack', c: TCounter) -> Tuple[bool]:
        if await c.pierce():
            await user.remove_status('v', remove_all=True)
            user.send_log("矢量操作的效果被幻想杀手消除了！")
            return False,
        if attack.reboundable:
            await user.remove_status('v', remove_all=False)
            user.send_log("触发了矢量操作的效果，反弹了对方的攻击！")
            return attack.rebound(),
        return False,
    @classmethod
    async def OnBombed(cls, count: TCount, user: 'User', word: str) -> Tuple[bool]:
        await user.remove_status('v', remove_all=False)
        user.send_log("触发了矢量操作的效果，没死。")
        return True,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnAttack: (Priority.OnAttack.vector, cls),
            UserEvt.OnAttacked: (Priority.OnAttacked.vector, cls),
            UserEvt.OnBombed: (Priority.OnBombed.vector, cls)}

class xixueshashou(_card):
    name = "吸血杀手"
    id = 124
    positive = 1
    description = "今天你每次接龙时有10%几率获得一张【吸血鬼】。"
    daily_status = 'x'
class xixueshashou_s(_statusdaily):
    id = 'x'
    des = "吸血杀手：今天你每次接龙时有10%几率获得一张【吸血鬼】。"
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        for i in range(count):
            if random.random() > 0.9:
                user.buf.send("你获得了一张【吸血鬼】！")
                await user.draw(0, cards=[Card(-2)])
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDragoned: (Priority.OnDragoned.xixueshashou, cls)}

class sunflower(_card):
    name = "向日葵"
    id = 130
    description = "附加buff：跨日结算时你获得1击毙。此buff最多叠加10层。"
    status = '('
    positive = 1
class sunflower_s(_statusnull):
    id = '('
    des = "向日葵：跨日结算时你获得1击毙。此buff最多叠加10层。"
    @classmethod
    async def OnNewDay(cls, count: TCount, user: 'User') -> Tuple[()]:
        user.buf.send(f"玩家{user.qq}种下的向日葵产出了{count}击毙！")
        await user.add_jibi(count)
    @classmethod
    async def OnStatusAdd(cls, count: TCount, user: 'User', status: TStatusAll, count2: int) -> Tuple[int]:
        if status is sunflower_s or status is twinsunflower_s:
            num = count + user.check_status(')')
            if num >= 10:
                user.send_log("的向日葵已经种满了10株，种植失败！")
                return 0,
            return min(count2, 10 - num),
        return count2,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnNewDay: (Priority.OnNewDay.sunflower, cls),
            UserEvt.OnStatusAdd: (Priority.OnStatusAdd.sunflower, cls)}
class inv_sunflower_s(_statusnull):
    id = '['
    des = "背日葵：跨日结算时你损失1击毙。"
    @classmethod
    async def OnNewDay(cls, count: TCount, user: 'User') -> Tuple[()]:
        user.buf.send(f"玩家{user.qq}种下的背日葵使其损失了{count}击毙！")
        await user.add_jibi(-count)
        n = 0
        for i in range(count):
            if random.random() > 0.5:
                await user.remove_status('[')
                n += 1
        user.buf.send(f"玩家{user.qq}的{n}朵背日葵转了过来！")
        for i in range(n):
            await user.add_status('(')
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnNewDay: (Priority.OnNewDay.inv_sunflower, cls)}
newday_check[0] |= set("()[]")

class wallnut(_card):
    name = "坚果墙"
    id = 131
    description = "为你吸收死亡时间总计4小时。"
    positive = 1
    @classmethod
    async def use(cls, user: User) -> None:
        o = user.check_limited_status('o', lambda x: not x.is_pumpkin)
        if len(o) > 0:
            o[0].num = 240
            user.data.save_status_time()
            user.send_log("修补了" + user.char + "的坚果墙！")
        else:
            await user.add_limited_status(SAbsorb(240, False))
            user.send_log("种植了坚果墙！")
@final
class SAbsorb(NumedStatus):
    id = 'o'
    @property
    def des(self):
        return ('南瓜头' if self.is_pumpkin else '坚果墙') + '：为你吸收死亡时间。'
    def __init__(self, s: Union[str, int], is_pumpkin=False):
        super().__init__(s)
        self.is_pumpkin = is_pumpkin
    def __repr__(self) -> str:
        return self.construct_repr(str(self.num), self.is_pumpkin)
    def __str__(self) -> str:
        return f"{self.des}\n\t剩余时间：{self.num}分钟。"
    def double(self):
        return [self.__class__(self.num * 2)]
    @classmethod
    async def OnDeath(cls, count: TCount, user: 'User', killer: 'User', time: int, c: TCounter) -> Tuple[int, bool]:
        if c.jump:
            return time, False
        o1 = o2 = None
        for o in count:
            if o.is_pumpkin:
                o2 = o
            else:
                o1 = o
        if o2 is not None:
            m = min(o2.num, time)
            o2 -= m
            time -= m
            user.send_log(f"的南瓜头为{user.char}吸收了{m}分钟的死亡时间！", end='')
            if time == 0:
                user.send_char("没死！")
            else:
                user.buf.send("")
        if o1 is not None and time != 0:
            m = min(o1.num, time)
            o1 -= m
            time -= m
            user.send_log(f"的坚果墙为{user.char}吸收了{m}分钟的死亡时间！", end='')
            if time == 0:
                user.send_char("没死！")
            else:
                user.buf.send("")
        user.data.save_status_time()
        return time, (time == 0)
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDeath: (Priority.OnDeath.absorb, cls)}

class iceshroom(_card):
    name = "寒冰菇"
    id = 132
    positive = -1
    description = "抽到时附加全局buff：今天每个人都需要额外隔一个才能接龙。"
    consumed_on_draw = True
    on_draw_global_daily_status = 'i'
class iceshroom_s(_statusdaily):
    id = 'i'
    des = "寒冰菇：今天每个人都需要额外隔一个才能接龙。"
    is_debuff = True
    is_global = True
    @classmethod
    async def BeforeDragoned(cls, count: TCount, user: 'User', word: str, parent: 'Tree') -> Tuple[bool, int, str]:
        return True, 1, ""
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.BeforeDragoned: (Priority.BeforeDragoned.iceshroom, cls)}
class hotshroom_s(_statusdaily):
    id = 'I'
    des = "炎热菇：今天每个人都可以少隔一个接龙。"
    is_global = True
    @classmethod
    async def BeforeDragoned(cls, count: TCount, user: 'User', word: str, parent: 'Tree') -> Tuple[bool, int, str]:
        return True, -1, ""
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.BeforeDragoned: (Priority.BeforeDragoned.hotshroom, cls)}

class twinsunflower(_card):
    name = "双子向日葵"
    id = 133
    description = "只能在你有“向日葵”buff时使用。使你的一层“向日葵”buff变成“双子向日葵”buff（跨日结算时你获得2击毙）。此buff与“向日葵”buff加在一起最多叠加10层。"
    positive = 1
    failure_message = "你场地上没有“向日葵”！"
    @classmethod
    def can_use(cls, user: User, copy: bool) -> bool:
        return user.check_status('(') > 0
    @classmethod
    async def use(cls, user: User) -> None:
        if user.check_status('(') == 0:
            user.send_char("场地上没有“向日葵”！")
            return
        await user.remove_status('(', remove_all=False)
        await user.add_status(')')
        user.send_char("的一株“向日葵”变成了“双子向日葵”！")
class twinsunflower_s(_statusnull):
    id = ')'
    des = "双子向日葵：跨日结算时你获得2击毙。此buff与“向日葵”buff加在一起最多叠加10层。"
    @classmethod
    async def OnNewDay(cls, count: TCount, user: 'User') -> Tuple[()]:
        user.buf.send(f"玩家{user.qq}种下的双子向日葵产出了{2 * count}击毙！")
        await user.add_jibi(2 * count)
    @classmethod
    async def OnStatusAdd(cls, count: TCount, user: 'User', status: TStatusAll, count2: int) -> Tuple[int]:
        if status is sunflower_s or status is twinsunflower_s:
            num = count + user.check_status('(')
            if num >= 10:
                user.send_log("的向日葵已经种满了10株，种植失败！")
                return 0,
            return min(count2, 10 - num),
        return count2,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnNewDay: (Priority.OnNewDay.twinsunflower, cls),
            UserEvt.OnStatusAdd: (Priority.OnStatusAdd.twinsunflower, cls)}
class inv_twinsunflower_s(_statusnull):
    id = ']'
    des = "双子背日葵：跨日结算时你损失2击毙。"
    @classmethod
    async def OnNewDay(cls, count: TCount, user: 'User') -> Tuple[()]:
        user.buf.send(f"玩家{user.qq}种下的双子背日葵使其损失了{2 * count}击毙！")
        await user.add_jibi(-2 * count)
        n = 0
        for i in range(count):
            if random.random() > 0.5:
                await user.remove_status(']')
                n += 1
        user.buf.send(f"玩家{user.qq}的{n}朵双子背日葵转了过来！")
        for i in range(n):
            await user.add_status(')')
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnNewDay: (Priority.OnNewDay.inv_twinsunflower, cls)}

class pumpkin(_card):
    name = "南瓜头"
    id = 134
    description = "为你吸收死亡时间总计6小时。可与坚果墙叠加。"
    positive = 1
    @classmethod
    async def use(cls, user: User) -> None:
        o = user.check_limited_status('o', lambda x: x.is_pumpkin)
        if len(o) > 0:
            o[0].num = 360
            user.data.save_status_time()
            user.send_log("修补了" + user.char + "的南瓜头！")
        else:
            await user.add_limited_status(SAbsorb(360, True))
            user.send_log("种植了南瓜头！")

class imitator(_card):
    name = "模仿者"
    id = 135
    positive = 0
    description = "你下一张抽到的卡会额外再给你一张。"
    status = 'i'
class imitator_s(_statusnull):
    id = 'i'
    des = "模仿者：你下一张抽到的卡会额外再给你一张。"
    @classmethod
    async def AfterCardDraw(cls, count: TCount, user: 'User', cards: Iterable[TCard]) -> Tuple[()]:
        if count > len(cards):
            for i in range(len(cards)):
                await user.remove_status('i', remove_all=False)
            to_add = cards
        else:
            await user.remove_status('i', remove_all=True)
            to_add = cards[:count]
        user.send_log("触发了模仿者的效果，额外获得了卡牌！获得的卡牌是：")
        for c in to_add:
            if c.des_need_init:
                await c.on_draw(user)
            user.buf.send(c.full_description(user.qq))
        for c in to_add:
            if not c.consumed_on_draw:
                user.add_card(c)
            if not c.des_need_init:
                await c.on_draw(user)
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.AfterCardDraw: (Priority.AfterCardDraw.imitator, cls)}

class jack_in_the_box(_card):
    name = "玩偶匣"
    id = 136
    positive = -1
    description = "抽到时附加buff：你每次接龙时有5%的几率爆炸，炸死以你为中心5x5的人，然后buff消失。若场上有寒冰菇状态则不会爆炸。"
    on_draw_status = 'j'
    on_draw_send_char = "获得了玩偶匣！"
    consumed_on_draw = True
class jack_in_the_box_s(_statusnull):
    id = 'j'
    des = "玩偶匣：你每次接龙时有5%的几率爆炸，炸死以你为中心5x5的人，然后buff消失。若场上有寒冰菇状态则不会爆炸。"
    is_debuff = True
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        if me.check_daily_status('i'):
            return
        if random.random() > 0.95 ** count:
            user.send_log("的玩偶匣爆炸了！")
            await user.remove_status('j', remove_all=False)
            qqs = {user.qq}
            id = branch.id
            for i, j in itertools.product(range(-2, 3), range(-2, 3)):
                ret = Tree.find((id[0] + i, id[1] + j))
                if ret is not None:
                    qqs.add(ret.qq)
            qqs -= {config.selfqq}
            user.send_char("炸死了" + "".join(f"[CQ:at,qq={qqq}]" for qqq in qqs) + "！")
            user.log << "炸死了" + ", ".join(str(qqq) for qqq in qqs) + "。"
            for qqq in qqs:
                await User(qqq, user.buf).killed(user)
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDragoned: (Priority.OnDragoned.jack_in_the_box, cls)}

class bungeezombie(_card):
    name = "蹦极僵尸"
    id = 137
    positive = -1
    description = "抽到时依照优先级移除你的一层植物效果。若你没有植物，则放下一只僵尸，你死亡一个小时。若场上有寒冰菇状态则不会生效。"
    consumed_on_draw = True
    @classmethod
    async def on_draw(cls, user: User) -> None:
        if me.check_daily_status('i'):
            user.buf.send("蹦极僵尸被寒冰菇冻住了！")
            user.log << "蹦极僵尸被寒冰菇冻住了！"
        elif o := more_itertools.only(user.check_limited_status('o', lambda x: not x.is_pumpkin)):
            user.send_log("的坚果墙被偷走了！")
            await user.remove_limited_status(o)
        elif user.check_status(')'):
            user.send_log("的双子向日葵被偷走了！")
            await user.remove_status(')', remove_all=False)
        elif user.check_status('('):
            user.send_log("的向日葵被偷走了！")
            await user.remove_status('(', remove_all=False)
        elif p := more_itertools.only(user.check_limited_status('o', lambda x: x.is_pumpkin)):
            user.send_log("的南瓜头被偷走了！")
            await user.remove_limited_status(p)
        else:
            user.send_log("没有植物，蹦极僵尸放下了一只僵尸！")
            await user.death(hour=1)

class polezombie(_card):
    name = "撑杆跳僵尸"
    id = 138
    positive = -1
    description = "抽到时击毙你一次，此击毙不会被坚果墙或南瓜保护套阻挡。若场上有寒冰菇状态则不会生效。"
    consumed_on_draw = True
    @classmethod
    async def on_draw(cls, user: User) -> None:
        if me.check_daily_status('i'):
            user.buf.send("撑杆跳僵尸被寒冰菇冻住了！")
            user.log << "撑杆跳僵尸被寒冰菇冻住了！"
        else:
            await user.death(c=TCounter(jump=True))

# class mishi1(_card):
#     name = "密教残篇"
#     id = 140
#     positive = 1
#     description = "获得正面状态“探索都城”，该系列效果同一玩家同时只能拥有一个。"
#     @classmethod
#     async def use(cls, user: User) -> None:
#         M = user.check_limited_status('M')
#         if len(M) > 0:
#             M[0].num = 1
#             user.data.save_status_time()
#             user.send_log(f"取消了之前的探索并开始探索都城！")
#         else:
#             await user.add_limited_status(Sexplore(1))
#             user.send_log(f"开始探索都城！")
# class mishi2(_card):
#     name = "鬼祟的真相"
#     id = 141
#     positive = 1
#     description = "获得正面状态“探索各郡”，该系列效果同一玩家同时只能拥有一个。"
#     @classmethod
#     async def use(cls, user: User) -> None:
#         M = user.check_limited_status('M')
#         if len(M) > 0:
#             M[0].num = 2
#             user.data.save_status_time()
#             user.send_log(f"取消了之前的探索并开始探索各郡！")
#         else:
#             await user.add_limited_status(Sexplore(2))
#             user.send_log(f"开始探索各郡！")
# class mishi3(_card):
#     name = "被遗忘的史籍"
#     id = 142
#     positive = 1
#     description = "获得正面状态“探索大陆”，该系列效果同一玩家同时只能拥有一个。"
#     @classmethod
#     async def use(cls, user: User) -> None:
#         M = user.check_limited_status('M')
#         if len(M) > 0:
#             M[0].num = 3
#             user.data.save_status_time()
#             user.send_log(f"取消了之前的探索并开始探索大陆！")
#         else:
#             await user.add_limited_status(Sexplore(3))
#             user.send_log(f"开始探索大陆！")
# class mishi4(_card):
#     name = "禁断的史诗"
#     id = 143
#     positive = 1
#     description = "获得正面状态“探索森林尽头之地”，该系列效果同一玩家同时只能拥有一个。"
#     @classmethod
#     async def use(cls, user: User) -> None:
#         M = user.check_limited_status('M')
#         if len(M) > 0:
#             M[0].num = 4
#             user.data.save_status_time()
#             user.send_log(f"取消了之前的探索并开始森林尽头之地！")
#         else:
#             await user.add_limited_status(Sexplore(4))
#             user.send_log(f"开始森林尽头之地！")
# class mishi5(_card):
#     name = "悬而未定的模棱两可"
#     id = 144
#     positive = 1
#     description = "获得正面状态“探索撕身山脉”，该系列效果同一玩家同时只能拥有一个。"
#     @classmethod
#     async def use(cls, user: User) -> None:
#         M = user.check_limited_status('M')
#         if len(M) > 0:
#             M[0].num = 5
#             user.data.save_status_time()
#             user.send_log(f"取消了之前的探索并开始探索撕身山脉！")
#         else:
#             await user.add_limited_status(Sexplore(5))
#             user.send_log(f"开始探索撕身山脉！")
# class mishi6(_card):
#     name = "浪游旅人的地图"
#     id = 145
#     positive = 1
#     description = "获得正面状态“探索荒寂而平阔的沙地”，该系列效果同一玩家同时只能拥有一个。"
#     @classmethod
#     async def use(cls, user: User) -> None:
#         M = user.check_limited_status('M')
#         if len(M) > 0:
#             M[0].num = 6
#             user.data.save_status_time()
#             user.send_log(f"取消了之前的探索并开始探索荒寂而平阔的沙地！")
#         else:
#             await user.add_limited_status(Sexplore(6))
#             user.send_log(f"开始探索荒寂而平阔的沙地！")
# class mishi7(_card):
#     name = "午港奇闻"
#     id = 146
#     positive = 1
#     description = "获得正面状态“探索薄暮群屿”，该系列效果同一玩家同时只能拥有一个。"
#     @classmethod
#     async def use(cls, user: User) -> None:
#         M = user.check_limited_status('M')
#         if len(M) > 0:
#             M[0].num = 7
#             user.data.save_status_time()
#             user.send_log(f"取消了之前的探索并开始探索薄暮群屿！")
#         else:
#             await user.add_limited_status(Sexplore(7))
#             user.send_log(f"开始探索薄暮群屿！")
# class Sexplore(NumedStatus):
#     id = 'M'
#     @property
#     def des(self):
#         i = count[0].num
#         if i in range(1,8)
#             spot = ["都城","各郡","大陆","森林尽头之地","撕身山脉","荒寂而平阔的沙地","薄暮群屿"][self.num-1]
#             return f"探索{spot}：你将会触发一系列随机事件。"
#         elif i == 8:
#             return f"探索薄暮群屿：你将会触发一系列随机事件。\n\t置身格里克堡：直到失去状态“探索薄暮群屿”，抵御所有死亡效果。"
#     def __str__(self) -> str:
#         return f"{self.des}"
#     def double(self):
#         return self
#     @classmethod
#     async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
#         if count[0].num == 1:
#             i = int(random.randon()*6)
#             if i == 0:
#                 user.send_log(f"置身斯特拉斯科因的寓所")
#                 user.buf.send("你发现了一些稀有的收藏。抽取一张广告牌。")
#                 await user.draw(0,cards=[Card(94)])
#             elif i == 1:
#                 user.send_log(f"置身被遗忘的密特拉寺")
#                 user.buf.send("你在此地进行了虔诚（）的祈祷。如果你此次接龙因各种原因被击毙，减少0～10%的死亡时间。")
#                 await #减少随机0~10%！
#             elif i == 2:
#                 user.send_log(f"置身凯特与赫洛有限公司")
#                 user.buf.send("你在因不明爆炸而荒废的大厦中可能寻得一些东西，或是失去一些东西。")
#                 if random.random() < 0.5:
#                     user.add_jibi(1)
#                 else:
#                     user.add_jibi(-1)
#             elif i == 3:
#                 user.send_log(f"置身圣亚割尼医院")
#                 user.buf.send("医院给了你活力。你在本日获得额外1次接龙获得击毙的机会。")
#                 user.data.today_jibi += 1
#                 config.logger.dragon << f"【LOG】用户{user.qq}增加了接龙击毙上限至{user.data.today_jibi}。"
#             elif i == 4:
#                 user.send_log(f"置身许伦的圣菲利克斯之会众")
#                 user.buf.send("你被虔诚的教徒们包围了，他们追奉启之法则。你下一次接龙需要进行首尾接龙。")
#                 user.add_status('J')
#             else:
#                 user.send_log(f"置身荒废的河岸街")
#                 user.buf.send("你掉进了河里。被击毙15分钟，并失去状态“探索都城”。")
#                 count[0].num = 0
#                 await user.death(15)
#                 user.data.save_status_time()
#         elif count[0].num == 2:
#             i = int(random.randon()*6)
#             if i == 0:
#                 user.send_log(f"置身格拉德温湖")
#                 user.buf.send("此处有蛇群把守。下一个接龙的人需要进行首尾接龙。")
#                 await Userme(user).add_status('|')
#             elif i == 1:
#                 user.send_log(f"置身洛克伍德沼地")
#                 user.buf.send("成真的神明或是在守望此地。如果你此次接龙被击毙，减少25%死亡时间。")
#                 await #减少25%！
#             elif i == 2:
#                 user.send_log(f"置身克罗基斯山丘")
#                 user.buf.send("守望此地之人将充满伤疤。")
#                 await user.add_daily_status('S')
#             elif i == 3:
#                 user.send_log(f"置身凯格琳的财宝")
#                 user.buf.send("这里曾经是银矿，再下面则是具名者的藏匿。获得5击毙，然后抽取一张负面卡片并立即使用。")
#                 user.add_jibi(5)
#                 c = draw_card({-1})
#                 await user.draw_and_use(c)
#             elif i == 4:
#                 user.send_log(f"置身高威尔旅馆")
#                 user.buf.send("藏书室非常隐蔽。25%概率抽一张卡。")
#                 if random.random() < 0.25:
#                     await user.draw(1)
#             else:
#                 user.send_log(f"置身凯尔伊苏姆")
#                 user.buf.send("你在最后一个房间一念之差被困住了。被击毙30分钟，并失去状态“探索各郡”。")
#                 count[0].num = 0
#                 await user.death(30)
#                 user.data.save_status_time()
#         elif count[0].num == 3:
#             i = int(random.randon()*6)
#             if i == 0:
#                 user.send_log(f"置身拉维林城堡")
#                 user.buf.send("住在这里的曾是太阳王的后裔。随机解除你的一个负面效果。")
#                 has = 1
#                 for c in map(StatusNull, user.data.status):
#                     if c.id != 'd' and c.is_debuff and has > 0:
#                         has -= 1
#                         user.send_char(f"的{c.des[:c.des.index('：')]}被取消了！")
#                         await user.remove_status(c.id, remove_all=False)
#                 for c in map(StatusDaily, user.data.daily_status):
#                     if c.id != 'd' and c.is_debuff and has > 0:
#                         has -= 1
#                         user.send_char(f"的{c.des[:c.des.index('：')]}被取消了！")
#                         await user.remove_daily_status(c.id, remove_all=False)
#                 i = 0
#                 while i < len(user.data.status_time_checked):
#                     s = user.data.status_time[i]
#                     if s.id != 'd' and s is not Swufazhandou and s.is_debuff and has > 0:
#                         has -= 1
#                         des = s.des
#                         user.send_log(f"的{des[:des.index('：')]}被取消了！")
#                         await user.remove_limited_status(s)
#                     else:
#                         i += 1
#                 user.data.save_status_time()
#             elif i == 1:
#                 user.send_log(f"置身费米尔修道院")
#                 user.buf.send("僧侣信奉象征欲望的杯之准则。失去5击毙，然后你今天每次接龙额外获得1击毙。")
#                 user.add_jibi(-5)
#                 await user.add_daily_status('C')
#             elif i == 2:
#                 user.send_log(f"置身俄尔托斯树林")
#                 user.buf.send("你目睹了群鸦的回忆。触发本日内曾被使用过的一张卡片的效果。")
#                 if len(global_state['used_cards']) == 0:
#                     user.send_log("今日没有使用过卡牌！")
#                 else:
#                     c = Card[random.choice(global_state['used_cards'])]
#                     user.send_log(f"遇见的群鸦选择了卡牌{c.name}。")
#                     await user.use_card_effect(c)
#             elif i == 3:
#                 user.send_log(f"置身范德沙夫收藏馆")
#                 user.buf.send("严密把守的储藏室中有不吉利的宝物。获得10击毙，并触发你手牌中一张非正面卡牌的效果。如果你的手中没有非正面卡牌，则将一张“邪恶的间谍行动～执行”置入你的手牌。")
#                 user.add_jibi(10)
#                 cs = []
#                 for c in user.data.hand_card:
#                     if c.positive != -1:
#                         cs.append(c)
#                 if len(cs) == 0:
#                     user.draw(0,cards=[Card(-1)])
#                 else:
#                     card = random.choice(cs)
#                     user.send_log(f"触发的宝物选择了卡牌{card.name}。")
#                     await user.use_card_effect(card)
#             elif i == 4:
#                 user.send_log(f"置身钥匙猎人的阁楼")
#                 user.buf.send("我们听说了一名狩猎空想之钥的古怪猎人所著的一小批古怪书籍。你今天获得额外五次接龙机会。")
#                 user.data.today_jibi += 5
#                 config.logger.dragon << f"【LOG】用户{user.qq}增加了接龙击毙上限至{user.data.today_jibi}。"
#             else:
#                 user.send_log(f"置身一望无际的巨石阵")
#                 user.buf.send("当无月之夜来临，当地人会补充残留下的东西。被击毙60分钟，并失去状态“探索大陆”。")
#                 count[0].num = 0
#                 await user.death(60)
#                 user.data.save_status_time()
#         elif count[0].num == 4:
#             i = int(random.randon()*6)
#             if i == 0:
#                 user.send_log(f"置身蜡烛岩洞")
#                 user.buf.send("岩洞的内部出乎意料地明亮。你下一次接龙只需要相隔一个人。")
#                 await user.add_status('L')
#             elif i == 1:
#                 user.send_log(f"置身大公的城塞")
#                 user.buf.send("他平复了许多人的干渴，最终又败给了自己的干渴。若你因本次接龙被击毙，减少50%的死亡时间。")
#                 await #减少50！
#             elif i == 2:
#                 user.send_log(f"置身格吕内瓦尔德的常驻马戏团")
#                 user.buf.send("马戏团众人在每个地方都贴满了写满图标的纸张，这个地方散发着虚界的气息。你的下一次接龙不受全局状态的影响。")
#                 await user.add_status('%')
#             elif i == 3:
#                 user.send_log(f"置身瑞弗克塔楼")
#                 user.buf.send("你们离去时，残塔消失了。清除上一个添加的全局状态。")
#                 if len(global_state['global_status']) == 0:
#                     user.send_log("没有可以清除的全局状态！")
#                 else:
#                     ss = global_state['global_status'][-1]
#                     if ss[0] == 0:
#                         sdes = StatusNull(ss[1]).des
#                         sdes = sdes[:sdes.index['：']]
#                         user.send_log(f"移除了{sdes}。")
#                         await Userme(user).remove_status(ss[1])
#                     elif ss[0] == 1:
#                         sdes = StatusDaily(ss[1]).des
#                         sdes = sdes[:sdes.index['：']]
#                         user.send_log(f"移除了{sdes}。")
#                         await Userme(user).remove_daily_status(ss[1])
#                     else:
#                         for gs in Userme(user).check_limited_status():
#                             if repr(gs) == ss[1]:
#                                 sdes = gs.des
#                                 sdes = sdes[:sdes.index['：']]
#                                 user.send_log(f"移除了{sdes}。")
#                                 await Userme(user).remove_limited_status(gs)
#             elif i == 4:
#                 user.send_log(f"置身库兹涅佐夫的捐赠")
#                 user.buf.send("库兹涅佐夫公爵将他沾满鲜血的财富的四分之一捐给这座地方大学以建立末世学学部。随机添加一个全局状态。")
#                 i = random.random()
#                 if i < 0.5:
#                     while True:
#                         s = random.choice(_statusnull.id_dict.keys())
#                         if StatusNull(s).is_global:
#                             break
#                     await user.add_status(s)
#                     user.send_log(f"添加了全局状态{s.des[:s.des.index('：')]}。")
#                 else:
#                     while True:
#                         s = random.choice(_statusdaily.id_dict.keys())
#                         if StatusDaily(s).is_global:
#                             break
#                     await user.add_daily_status(s)
#                     user.send_log(f"添加了全局状态{s.des[:s.des.index('：')]}。")
#             else:
#                 user.send_log(f"置身狐百合原野")
#                 user.buf.send("我们将布浸入氨水，蒙在脸上，以抵抗狐百合的香气。即便这样，我们仍然头晕目眩，身体却对各种矛盾的欲望作出回应。被击毙90分钟，并失去状态“探索森林尽头之地”。")
#                 count[0].num = 0
#                 await user.death(90)
#                 user.data.save_status_time()
#         elif count[0].num == 5:
#             i = int(random.random()*5)
#             if i == 0:
#                 user.send_log(f"置身猎手之穴")
#                 user.buf.send("在这里必须隐藏自己。上一个人下一次接龙需要间隔三个人。")
#                 pq = branch.parent.qq
#                 if pq != self.qq and pq != 0:
#                     User(pq, user.buf).add_status('&')
#                 else:
#                     user.send_log(f"无上一个接龙的玩家！")
#             elif i == 1:
#                 user.send_log(f"置身避雪神庙")
#                 user.buf.send("神庙可以回避一些袭击。本次接龙不会因为一周内接龙过或是踩雷而被击毙，但也没有接龙成功。")
#                 node = branch.parent
#                 for n in node.childs:
#                     n.remove()
#                 from .logic_dragon import rewrite_log_file
#                 rewrite_log_file()
#                 await #减少100%！
#             elif i == 2:
#                 user.send_log(f"置身伊克玛维之眼")
#                 user.buf.send("这里是观星台，是大地的眼睛。公开揭示今天一个隐藏奖励词，该效果每天只会触发一次。")
#                 if not global_state['observatory']
#                     from .logic_dragon import hidden_keyword
#                     user.buf.send("你揭示的一个隐藏奖励词是：" + random.choice(hidden_keyword))
#                     global_state['observatory'] = True
#                 else:
#                     user.buf.send("今天已经使用过观星台！")
#             elif i == 3:
#                 user.send_log(f"置身石狼陵墓")
#                 user.buf.send("送葬者不见踪影，而死者被引来此处。本次接龙额外获得10击毙。")
#                 await user.add_jibi(10)
#             else:
#                 user.send_log(f"置身无影众王的墓群")
#                 user.buf.send("众王皆向往不死，而仅有一人实现了愿望，其他人只留下了陪葬品。立刻被击毙120分钟，并失去状态“探索撕身山脉”。")
#                 count[0].num = 0
#                 await user.death(120)
#                 user.data.save_status_time()
#         elif count[0].num == 6:
#             i = int(random.random()*5)
#             if i == 0:
#                 user.send_log(f"置身被星辰击碎的神殿")
#                 user.buf.send("掉落的陨石反而成了朝拜的对象。在你之后接龙的一个人会额外获得5击毙。")
#                 await user.add_status('^')
#             elif i == 1:
#                 user.send_log(f"置身拉贡之墓")
#                 user.buf.send("曾经不死的长生者的尸体被保存得很好，直到我们到来。击毙上一个接龙的玩家十五分钟。")
#                 pq = branch.parent.qq
#                 if pq != self.qq and pq != 0:
#                     await User(pq, user.buf).death(15)
#                 else:
#                     user.send_log(f"无上一个接龙的玩家！")
#             elif i == 2:
#                 user.send_log(f"置身墨萨拿")
#                 user.buf.send("村民们拥有超过自然限度的长寿。获得状态“长生的宴席”。")
#                 await user.add_limited_status(Schangsheng(120))
#             elif i == 3:
#                 user.send_log(f"置身七蟠寺")
#                 user.buf.send("这座寺庙存在于每一重历史之中。你将与今天结束的正面状态延长至明天。")
#                 await user.add_daily_status('l')
#             else:
#                 user.send_log(f"置身弥阿")
#                 user.buf.send("有时是我们寻到死者拥有的知识，有时是死者寻到我们。被击毙180分钟，并失去状态“探索荒寂而平阔的沙地”。")
#                 count[0].num = 0
#                 await user.death(180)
#                 user.data.save_status_time()
#         elif count[0].num == 7:
#             i = int(random.random()*5)
#             if i == 0:
#                 user.send_log(f"置身渡鸦屿")
#                 user.buf.send("索奎焰特在洞壁上用一百种语言描述他们悲惨的历史。获得一个可以完成10次的新任务，每次可以获得2击毙。")
#                 await user.add_limited_status(SQuest(10, 2, n := get_mission()))
#                 user.send_char(f"获得了一个任务：{mission[n][1]}")
#             elif i == 1:
#                 user.send_log(f"置身格里克堡")
#                 user.buf.send("帝国和岛屿没有在任何正史中出现过，但岛上总督的堡垒还在，或许他本人也是。直到失去状态“探索薄暮群屿”，抵御所有死亡效果。")
#                 count[0].num = 8
#                 user.data.save_status_time()
#             elif i == 2:
#                 user.send_log(f"置身克丽斯塔贝号船骸")
#                 user.buf.send("一头海兽来向这艘船求爱，但当船不回应这份爱慕时，海兽击碎了它。选择一张手牌弃置，然后抽两张正面卡牌。")
#                 async with user.choose_cards("请选择你手牌中的一张牌弃置，输入id号。", 1, 1,) as l, check_active(l):
#                     await user.discard_cards(l)
#                 await user.draw(2,positive=1)
#             elif i == 3:
#                 user.send_log(f"置身深邃之门的圣滕特雷托之僧院")
#                 user.buf.send("僧院危悬在崖边，它早该坠入海中了。从以下三个效果中随机触发一个：获得20击毙、抽一张牌或随机弃置一张牌。")
#                 j = int(random.random()*3)
#                 if j == 0:
#                     user.send_log(f"获得了20击毙！")
#                     await user.add_jibi(20)
#                 elif j == 1:
#                     user.send_log(f"抽了一张卡！")
#                     await user.draw(1)
#                 elif len(copy(user.data.hand_cards)) == 0:
#                     user.send_log(f"无手牌可弃！")
#                 else:
#                     cd = random.choice(copy(user.data.hand_cards))
#                     user.send_log(f"丢弃了{cd.name}！")
#                     await user.discard_cards(cd)
#             else:
#                 user.send_log(f"置身午港")
#                 user.buf.send("这座名为“午”的小小岛港是不死者的流放地。被击毙240分钟，并失去状态“探索薄暮群屿”。")
#                 count[0].num = 0
#                 await user.death(240)
#                 user.data.save_status_time()
#         elif count[0].num == 8:
#             i = int(random.random()*5)
#             if i == 0:
#                 user.send_log(f"置身渡鸦屿")
#                 user.buf.send("索奎焰特在洞壁上用一百种语言描述他们悲惨的历史。获得一个可以完成10次的新任务，每次可以获得2击毙。")
#                 await user.add_limited_status(SQuest(10, 2, n := get_mission()))
#                 user.send_char(f"获得了一个任务：{mission[n][1]}")
#             elif i == 1:
#                 user.send_log(f"置身格里克堡")
#                 user.buf.send("帝国和岛屿没有在任何正史中出现过，但岛上总督的堡垒还在，或许他本人也是。直到失去状态“探索薄暮群屿”，抵御所有死亡效果。")
#                 user.send_log(f"已经置身于格里克堡了！")
#             elif i == 2:
#                 user.send_log(f"置身克丽斯塔贝号船骸")
#                 user.buf.send("一头海兽来向这艘船求爱，但当船不回应这份爱慕时，海兽击碎了它。选择一张手牌弃置，然后抽两张正面卡牌。")
#                 async with user.choose_cards("请选择你手牌中的一张牌弃置，输入id号。", 1, 1,) as l, check_active(l):
#                     await user.discard_cards(l)
#                 await user.draw(2,positive=1)
#             elif i == 3:
#                 user.send_log(f"置身深邃之门的圣滕特雷托之僧院")
#                 user.buf.send("僧院危悬在崖边，它早该坠入海中了。从以下三个效果中随机触发一个：获得20击毙、抽一张牌或随机弃置一张牌。")
#                 j = int(random.random()*3)
#                 if j == 0:
#                     user.send_log(f"获得了20击毙！")
#                     await user.add_jibi(20)
#                 elif j == 1:
#                     user.send_log(f"抽了一张卡！")
#                     await user.draw(1)
#                 elif len(copy(user.data.hand_cards)) == 0:
#                     user.send_log(f"无手牌可弃！")
#                 else:
#                     cd = random.choice(copy(user.data.hand_cards))
#                     user.send_log(f"丢弃了{cd.name}！")
#                     await user.discard_cards(cd)
#             else:
#                 user.send_log(f"置身午港")
#                 user.buf.send("这座名为“午”的小小岛港是不死者的流放地。被击毙240分钟，并失去状态“探索薄暮群屿”。")
#                 count[0].num = 0
#                 await user.death(240)
#                 user.data.save_status_time()
#         else:
#             count[0].num = 0
#             user.data.save_status_time()
#     @classmethod
#     async def OnDeath(cls, count: TCount, user: 'User', killer: 'User', time: int, c: TCounter) -> Tuple[int, bool]:
#         if count[0].num != 8:
#             return time, False
#         else:
#             if await c.pierce():
#                 user.send_log("堡垒的效果被幻想杀手消除了！")
#                 count[0].num = 7
#                 user.save_status_time()
#             else:
#                 user.send_log("触发了堡垒的效果，免除死亡！")
#                 return time, True
#     @classmethod
#     def register(cls) -> dict[int, TEvent]:
#         return {UserEvt.OnDragoned: (Priority.OnDragoned.explore, cls),
#             UserEvt.OnDeath: (Priority.OnDeath.explore, cls)}

class Sjiaotu(_statusnull):
    id = 'J'
    des = "置身许伦的圣菲利克斯之会众：被虔诚的教徒们包围，他们追奉启之法则，你下一次接龙需要进行首尾接龙。"
    is_debuff = True
    @classmethod
    async def BeforeDragoned(cls, count: TCount, user: User, word: str, parent: 'Tree') -> Tuple[bool, int, str]:
        if parent.word != '' and word != '' and parent.word[-1] != word[0]:
            return False, 0, "虔诚的教徒们说，你需要首尾接龙，接龙失败。"
        return True, 0, ""
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        await user.remove_status('J', remove_all=False)
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.BeforeDragoned: (Priority.BeforeDragoned.jiaotu, cls),
            UserEvt.OnDragoned: (Priority.OnDragoned.jiaotu, cls)}
class Sinvjiaotu(_statusnull):
    id = 'K'
    des = "反转-置身许伦的圣菲利克斯之会众：被虔诚的教徒们包围，他们追奉启之法则，你下一次接龙需要进行尾首接龙。"
    is_debuff = True
    @classmethod
    async def BeforeDragoned(cls, count: TCount, user: User, word: str, parent: 'Tree') -> Tuple[bool, int, str]:
        if parent.word != '' and word != '' and parent.word[0] != word[-1]:
            return False, 0, "虔诚的教徒们说，你需要尾首接龙，接龙失败。"
        return True, 0, ""
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        await user.remove_status('K', remove_all=False)
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.BeforeDragoned: (Priority.BeforeDragoned.invjiaotu, cls),
            UserEvt.OnDragoned: (Priority.OnDragoned.invjiaotu, cls)}
class Sshequn(_statusnull):
    id = '|'
    des = "置身格拉德温湖：此处有蛇群把守。下一个接龙的人需要进行首尾接龙。"
    is_global = True
    is_debuff = True
    @classmethod
    async def BeforeDragoned(cls, count: TCount, user: User, word: str, parent: 'Tree') -> Tuple[bool, int, str]:
        if parent.word != '' and word != '' and parent.word[-1] != word[0]:
            return False, 0, "蛇群阻止了你的非首尾接龙，接龙失败。"
        return True, 0, ""
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        await user.remove_status('|', remove_all=False)
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.BeforeDragoned: (Priority.BeforeDragoned.shequn, cls),
            UserEvt.OnDragoned: (Priority.OnDragoned.shequn, cls)}
class Sinvshequn(_statusnull):
    id = '/'
    des = "反转-置身格拉德温湖：此处有蛇群把守。下一个接龙的人需要进行尾首接龙。"
    is_global = True
    is_debuff = True
    @classmethod
    async def BeforeDragoned(cls, count: TCount, user: User, word: str, parent: 'Tree') -> Tuple[bool, int, str]:
        if parent.word != '' and word != '' and parent.word[0] != word[-1]:
            return False, 0, "蛇群阻止了你的非尾首接龙，接龙失败。"
        return True, 0, ""
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        await user.remove_status('/', remove_all=False)
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.BeforeDragoned: (Priority.BeforeDragoned.invshequn, cls),
            UserEvt.OnDragoned: (Priority.OnDragoned.invshequn, cls)}
class Sshangba(_statusdaily):
    id = 'S'
    des = "伤疤：今天你每死亡一次便获得2击毙。"
    @classmethod
    async def OnDeath(cls, count: TCount, user: User, killer: User, time: int, c: TCounter) -> Tuple[int, bool]:
        if await c.pierce():
            user.send_log("伤疤的效果被幻想杀手消除了！")
            await user.remove_status('S')
        else:
            user.send_log(f"触发了伤疤！奖励{2 * count}击毙。")
            await user.add_jibi(2 * count)
        return time, False
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDeath: (Priority.OnDeath.shangba, cls)}
class Sinvshangba(_statusdaily):
    id = 'P'
    des = "反转-伤疤：今天你每死亡一次便失去2击毙。"
    is_debuff = True
    @classmethod
    async def OnDeath(cls, count: TCount, user: User, killer: User, time: int, c: TCounter) -> Tuple[int, bool]:
        if await c.pierce():
            user.send_log("反转-伤疤的效果被幻想杀手消除了！")
            await user.remove_status('P')
        else:
            user.send_log(f"触发了反转-伤疤！失去{2 * count}击毙。")
            await user.add_jibi(-2 * count)
        return time, False
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDeath: (Priority.OnDeath.invshangba, cls)}
class Sbeizhizhunze(_statusdaily):
    id = 'C'
    des = "杯之准则：你今天每次接龙额外获得1击毙。"
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        user.send_char(f"因为杯之准则额外获得{count}击毙！")
        await user.add_jibi(count)
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDragoned: (Priority.OnDragoned.beizhizhunze, cls)}
class Sinvbeizhizhunze(_statusdaily):
    id = 'E'
    des = "反转-杯之准则：你今天每次接龙额外失去1击毙。"
    is_debuff = True
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        user.send_char(f"因为反转-杯之准则额外失去{count}击毙！")
        await user.add_jibi(-1*count)
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDragoned: (Priority.OnDragoned.invbeizhizhunze, cls)}
class Slazhuyandong(_statusnull):
    id = 'L'
    des = "置身蜡烛岩洞：下一次接龙可以少间隔一个人。"
    @classmethod
    async def BeforeDragoned(cls, count: TCount, user: User, word: str, parent: 'Tree') -> Tuple[bool, int, str]:
        return True, -1, ""
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        await user.remove_status('L', remove_all=False)
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.BeforeDragoned: (Priority.BeforeDragoned.lazhuyandong, cls),
            UserEvt.OnDragoned: (Priority.OnDragoned.lazhuyandong, cls)}
class Sinvlazhuyandong(_statusnull):
    id = 'I'
    des = "反转-置身蜡烛岩洞：下一次接龙需要多间隔一个人。"
    @classmethod
    async def BeforeDragoned(cls, count: TCount, user: User, word: str, parent: 'Tree') -> Tuple[bool, int, str]:
        return True, 1, ""
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        await user.remove_status('I', remove_all=False)
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.BeforeDragoned: (Priority.BeforeDragoned.invlazhuyandong, cls),
            UserEvt.OnDragoned: (Priority.OnDragoned.invlazhuyandong, cls)}
class Scircus(_statusnull):
    id = '%'
    des = "置身格吕内瓦尔德的常驻马戏团：下一次接龙不受全局状态的影响。"
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        user.send_log(f"因置身马戏团不受全局状态影响。")
        await user.remove_status('%', remove_all=False)
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDragoned: (Priority.OnDragoned.circus, cls)}
class Slieshouzhixue(_statusnull):
    id = '&'
    des = "置身猎手之穴：下一次接龙需要多间隔一个人。"
    is_debuff = True
    @classmethod
    async def BeforeDragoned(cls, count: TCount, user: User, word: str, parent: 'Tree') -> Tuple[bool, int, str]:
        return True, 1, ""
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        await user.remove_status('&', remove_all=False)
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.BeforeDragoned: (Priority.BeforeDragoned.lieshouzhixue, cls),
            UserEvt.OnDragoned: (Priority.OnDragoned.lieshouzhixue, cls)}
class Sinvlieshou(_statusnull):
    id = '*'
    des = "反转-置身猎手之穴：下一次接龙可以少间隔一个人。"
    @classmethod
    async def BeforeDragoned(cls, count: TCount, user: User, word: str, parent: 'Tree') -> Tuple[bool, int, str]:
        return True, -1, ""
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        await user.remove_status('*', remove_all=False)
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.BeforeDragoned: (Priority.BeforeDragoned.invlieshouzhixue, cls),
            UserEvt.OnDragoned: (Priority.OnDragoned.invlieshouzhixue, cls)}
class Sshendian(_statusnull):
    id = '^'
    des = "置身被星辰击碎的神殿：之后接龙的一个人会额外获得5击毙。"
    is_global = True
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        await user.add_jibi(5 * count)
        user.send_log(f"因置身被星辰击碎的神殿额外获得{5*count}击毙！")
        await user.remove_status('^')
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDragoned: (Priority.OnDragoned.shendian, cls)}
class Sinvshendian(_statusnull):
    id = '$'
    des = "反转-置身被星辰击碎的神殿：之后接龙的一个人会额外失去5击毙。"
    is_debuff = True
    is_global = True
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        await user.add_jibi(-5 * count)
        user.send_log(f"因反转-置身被星辰击碎的神殿额外失去{5*count}击毙！")
        await user.remove_status('$')
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDragoned: (Priority.OnDragoned.invshendian, cls)}
class Schangsheng(NumedStatus):
    id = 'C'
    des = "长生的宴席：可以抵消累计120分钟死亡。"
    def __str__(self) -> str:
        return f"{self.des}\n\t剩余时间：{self.num}分钟。"
    def double(self):
        return [self.__class__(self.num * 2)]
    @classmethod
    async def OnDeath(cls, count: TCount, user: 'User', killer: 'User', time: int, c: TCounter) -> Tuple[int, bool]:
        for i in count:
            m = min(i.num, time)
            i.num -= m
            time -= m
            user.send_log(f"的长生的宴席为{user.char}吸收了{m}分钟的死亡时间！", end='')
            if time == 0:
                user.send_char("没死！")
                break
            else:
                user.buf.send("")
        user.data.save_status_time()
        return time, (time == 0)
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDeath: (Priority.OnDeath.changsheng, cls)}
class Stemple(_statusdaily):
    id = 'l'
    des = "置身七蟠寺：今天结束的非负面状态延长至明天。"
class Sinvtemple(_statusdaily):
    id = 'k'
    des = "反转-置身七蟠寺：今天结束的负面状态延长至明天。"

class steamsummer(_card):
    name = "Steam夏季特卖"
    id = 151
    positive = 1
    status = 'S'
    description = "你下一次购物花费减少50%。"
class steamsummer_s(_statusnull):
    id = 'S'
    des = "Steam夏季特卖：你下一次购物花费减少50%。"
    @classmethod
    async def CheckJibiSpend(cls, count: TCount, user: 'User', jibi: int) -> Tuple[int]:
        return jibi // 2 ** count,
    @classmethod
    async def OnJibiChange(cls, count: TCount, user: 'User', jibi: int, is_buy: bool) -> Tuple[int]:
        if jibi < 0 and is_buy:
            await user.remove_status('S')
            return jibi // 2 ** count,
        return jibi,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.CheckJibiSpend: (Priority.CheckJibiSpend.steamsummer, cls),
            UserEvt.OnJibiChange: (Priority.OnJibiChange.steamsummer, cls)}

class forkbomb(_card):
    name = "Fork Bomb"
    id = 152
    positive = 0
    global_daily_status = 'b'
    description = "今天每个接龙词都有5%几率变成分叉点。"
class forkbomb_s(_statusdaily):
    id = 'b'
    des = "Fork Bomb：今天每个接龙词都有5%几率变成分叉点。"
    is_global = True
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        if random.random() > 0.95 ** count:
            user.send_log("触发了Fork Bomb，此词变成了分叉点！")
            branch.fork = True
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDragoned: (Priority.OnDragoned.forkbomb, cls)}

class beijingcard(_card):
    name = "北京市市政交通一卡通"
    id = 153
    positive = 1
    description = "持有此卡时，你当天在商店总消费达100击毙后商店所有物品变为8折，当天在商店总消费达150击毙后商店所有物品变为5折，当天在商店总消费达400击毙后不再打折。"
    hold_des = "北京市市政交通一卡通：你当天在商店总消费达100击毙后商店所有物品变为8折，当天在商店总消费达150击毙后商店所有物品变为5折，当天在商店总消费达400击毙后不再打折。"
    @classmethod
    async def CheckJibiSpend(cls, count: TCount, user: User, jibi: int) -> Tuple[int]:
        if 100 <= user.data.spend_shop < 150:
            jibi = int(jibi * 0.8 ** count)
        elif 150 <= user.data.spend_shop < 400:
            jibi = int(jibi * 0.5 ** count)
        return jibi,
    @classmethod
    async def OnJibiChange(cls, count: TCount, user: User, jibi: int, is_buy: bool) -> Tuple[int]:
        if jibi < 0 and is_buy:
            if 100 <= user.data.spend_shop < 150:
                jibi = int(jibi * 0.8 ** count)
                user.send_char(f"触发了{f'{count}次' if count > 1 else ''}北京市政交通一卡通的效果，花费击毙打了8折变为{jibi}！")
            elif 150 <= user.data.spend_shop < 400:
                jibi = int(jibi * 0.5 ** count)
                user.send_char(f"触发了{f'{count}次' if count > 1 else ''}北京市政交通一卡通的效果，花费击毙打了5折变为{jibi}！")
            elif user.data.spend_shop >= 400:
                user.send_char("今日已花费400击毙，不再打折！")
            user.log << f"触发了{count}次北京市政交通一卡通的效果，花费击毙变为{jibi}。"
        return jibi,
    @classmethod
    def register(cls):
        return {UserEvt.OnJibiChange: (Priority.OnJibiChange.beijingcard, cls),
            UserEvt.CheckJibiSpend: (Priority.CheckJibiSpend.beijingcard, cls)}

class upsidedown(_card):
    name = "天下翻覆"
    id = 156
    positive = 0
    description = "每条全局状态和你的状态有50%的概率反转，除了那些不能反转的以外。"
    weight = 5
    @classmethod
    async def use(cls, user: User) -> None:
        # 永久状态
        async def _s(u: User):
            to_remove = ""
            to_add = ""
            for c in u.data.status:
                if random.random() > 0.5:
                    continue
                if c in revert_status_map:
                    des = StatusNull(c).des
                    u.send_log(f"的{des[:des.index('：')]}被反转了！")
                    to_remove += c
                    to_add += revert_status_map[c]
            for c in to_remove:
                await u.remove_status(c, remove_all=False)
            for c in to_add:
                await u.add_status(c)
        await _s(user)
        # 每日状态
        async def _d(u: User):
            to_remove = ""
            to_add = ""
            for c in u.data.daily_status:
                if random.random() > 0.5:
                    continue
                if c in revert_daily_status_map:
                    des = StatusDaily(c).des
                    u.send_log(f"的{des[:des.index('：')]}被反转了！")
                    to_remove += c
                    to_add += revert_daily_status_map[c]
            for c in to_remove:
                await u.remove_daily_status(c, remove_all=False)
            for c in to_add:
                await u.add_daily_status(c)
        await _d(user)
        # 带附加值的状态
        l = user.data.status_time_checked
        for i in range(len(l)):
            if random.random() > 0.5:
                continue
            if l[i].id == 'q':
                l[i].jibi = -l[i].jibi
                user.send_log("的每日任务被反转了！")
            elif l[i].id == 'b':
                l[i] = SCian(l[i].num)
                user.send_log("的月下彼岸花被反转了！")
            elif l[i].id == 'c':
                l[i] = SBian(l[i].num)
                user.send_log("的反转·月下彼岸花被反转了！")
            elif l[i].id == 'l':
                l[i] = SKe(l[i].list)
                user.send_log("的乐不思蜀被反转了！")
            elif l[i].id == 'k':
                l[i] = SLe(l[i].list)
                user.send_log("的反转·乐不思蜀被反转了！")
            elif l[i].id == 'e':
                l[i] = inv_hierophant_s(l[i].num)
                user.send_log("的反转·教皇被反转了！")
            elif l[i].id == 'f':
                l[i] = hierophant_s(l[i].num)
                user.send_log("的教皇被反转了！")
            if l[i].id == 'W':
                l[i] = SInvBritian(l[i].list)
                user.send_log("的统治不列颠被反转了！")
            if l[i].id == 'X':
                l[i] = SBritian(l[i].list)
                user.send_log("的被不列颠统治被反转了！")
        user.data.save_status_time()
        # 全局状态
        await _s(Userme(user))
        await _d(Userme(user))
        # l = me.status_time_checked
        # for i in range(len(l)):
        #     if random.random() > 0.5:
        #         continue
        # me.save_status_time()
revert_status_map: Dict[str, str] = {}
for c in ('AB', 'ab', 'st', 'xy', 'Mm', 'QR', '12', '89', '([', ')]', 'cd', '34', 'JK', '|/', 'LI', '&*', '^$'):
    revert_status_map[c[0]] = c[1]
    revert_status_map[c[1]] = c[0]
revert_daily_status_map: Dict[str, str] = {}
for c in ('RZ', 'Bt', 'Ii', 'Mm', 'op', '@#', 'WX', 'SP', 'CE', 'lk'):
    revert_daily_status_map[c[0]] = c[1]
    revert_daily_status_map[c[1]] = c[0]

class excalibur(_card):
    id = 158
    name = "EX咖喱棒"
    positive = 1
    description = "只可在胜利时使用。统治不列颠。"
    newer = 1
    @classmethod
    def can_use(cls, user: User, copy: bool) -> bool:
        return user.check_daily_status('W') > 0
    @classmethod
    async def use(cls, user: User) -> None:
        if user.check_daily_status('W') == 0:
            user.send_char("没有胜利，无法使用！")
        else:
            user.send_log("统治了不列颠！")
            await user.add_limited_status(SBritian([]))
class SBritian(ListStatus):
    id = 'W'
    des = "统治不列颠：使用塔罗牌系列牌时，若本效果不包含“魔力 - {该塔罗牌名}”，不发动该牌的原本使用效果，并为本效果增加“魔力 - {该塔罗牌名}”。当拥有所有22种“魔力 - {塔罗牌名}”时，获得装备“塔罗原典”。"
    def __str__(self) -> str:
        if len(self.list) == 0:
            return self.des
        return f"{self.des}\n\t包含：{'，'.join(('“魔力 - ' + Card(i).name[Card(i).name.index(' - ') + 3:] + '”') for i in self.list)}。"
    @property
    def brief_des(self) -> str:
        return f"统治不列颠\n\t包含：{','.join(str(c) for c in self.list)}。"
    def check(self) -> bool:
        return True
    @classmethod
    async def BeforeCardUse(cls, count: TCount, user: 'User', card: TCard) -> Tuple[Optional[Awaitable]]:
        if card.id <= 21 and card.id >= 0:
            for c in count:
                if card.id not in c.list:
                    async def f():
                        user.send_log(f"获得了“魔力 - {card.name[card.name.index(' - ') + 3:]}”！")
                        c.list.append(card.id)
                        c.list.sort()
                        user.log << f"现有{c.list}。"
                        if len(c.list) == 22:
                            await user.remove_limited_status(c)
                            b = user.data.check_equipment(2)
                            user.data.equipment[2] = b + 1
                            if b == 0:
                                user.send_log("获得了装备“塔罗原典”！")
                            else:
                                user.send_log(f"将装备“塔罗原典”升星至{b + 1}星！")
                        user.data.save_status_time()
                    return f(),
        return None,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.BeforeCardUse: (Priority.BeforeCardUse.britian, cls)}
class SInvBritian(ListStatus):
    id = 'X'
    des = "被不列颠统治：若本效果包含“魔力 - {某塔罗牌名}”，你可取消本效果中的“魔力 - {该塔罗牌名}”，并凭空使用一张该塔罗牌。"
    def check(self) -> bool:
        return True

class assembling_machine(_card):
    id = 200
    name = "组装机1型"
    description = "如果你没有组装机，你获得装备：组装机1型。如果你已有组装机1型，将其升级为组装机2型。如果你已有组装机2型，将其升级为组装机3型。如果你已有组装机3型，你获得200组装量。"
    newer = 4
    positive = 1
    @classmethod
    async def use(cls, user: User) -> None:
        c = user.data.check_equipment(3)
        if c == 3:
            user.send_log("获得了200组装量！")
            user.data.extra.assembling += 200
        else:
            if c == 0:
                user.send_log("获得了装备：组装机1型！")
            else:
                user.send_log(f"将组装机{c}型升级到了组装机{c + 1}型！")
            user.data.equipment[3] = c + 1
            user.data.save_equipment()

class belt(_card):
    id = 201
    name = "传送带"
    description = "当其它玩家丢弃第一张手牌时，你获得之。"
    positive = 1
    newer = 4
    status = '3'
class belt_s(_statusnull):
    id = '3'
    des = "传送带：当其它玩家丢弃第一张手牌时，你获得之。"
class belt_checker(IEventListener):
    @classmethod
    async def AfterCardDiscard(cls, count: TCount, user: 'User', cards: Iterable[TCard]) -> Tuple[()]:
        qqs = [t['qq'] for t in config.userdata.execute("select qq from dragon_data where status like '%3%'").fetchall()]
        if len(qqs) == 0:
            return
        users = [User(qq, user.buf) for qq in qqs]
        for card in cards:
            if len(users) == 0:
                return
            u = random.choice(users)
            user.buf.send(f"玩家{u.qq}从传送带上捡起了" + user.char + "掉的卡！")
            await u.draw(0, cards=[card])
            await u.remove_status('3', remove_all=False)
            if u.check_status('3') == 0:
                users.remove(u)
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.AfterCardDiscard: (Priority.AfterCardDiscard.belt, cls)}
UserData.register_checker(belt_checker)
class inv_belt_s(_statusnull):
    id = '4'
    des = "反转·传送带：当你丢弃第一张手牌时，把它丢给随机一名玩家。"
    @classmethod
    async def AfterCardDiscard(cls, count: TCount, user: 'User', cards: Iterable[TCard]) -> Tuple[()]:
        qqs = [t['qq'] for t in config.userdata.execute("select qq from dragon_data where dead=false").fetchall()]
        for card in cards:
            qq = random.choice(qqs)
            u = User(qq, user.buf)
            user.buf.send(f"玩家{u.qq}从传送带上捡起了" + user.char + "掉的卡！")
            await u.draw(0, [card])
            await user.remove_status('4', remove_all=False)
            if not user.check_status('4'):
                break
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.AfterCardDiscard: (Priority.AfterCardDiscard.inv_belt, cls)}

class train(_card):
    id = 202
    name = "火车"
    description = "附加全局状态：若你最近接过龙，其它玩家一次获得5以上击毙时，你便乘1击毙。若场上已经有火车，发动新的火车有1/4的几率与已有的每一辆火车发生碰撞，碰撞时两个火车都会消失。"
    positive = 1
    newer = 4
    @classmethod
    async def use(cls, user: User) -> None:
        l = me.check_limited_status('t')
        for tr in l:
            if random.random() < 0.25:
                user.send_log(f"的火车和玩家{tr.qq}的火车发生了碰撞！")
                await Userme(user).remove_limited_status(tr)
                return
        await Userme(user).add_limited_status(STrain(user.qq, False))
class STrain(_status):
    id = 't'
    des = "火车：其它玩家一次获得5以上击毙时，某玩家便乘1击毙。"
    is_global = True
    def __init__(self, s: Union[str, int], if_def: Union[str, bool]):
        self.qq = int(s)
        self.if_def = if_def in ('True', True)
    def __repr__(self) -> str:
        return self.construct_repr(self.qq, self.if_def)
    @classmethod
    @property
    def brief_des(cls) -> str:
        return "火车"
    def __str__(self) -> str:
        return self.des + ('\n\t存在火车跳板。' if self.if_def else '')
    def double(self) -> List[T_status]:
        return [self, self.__class__(self.qq, self.if_def)]
    @classmethod
    async def OnJibiChange(cls, count: TCount, user: 'User', jibi: int, is_buy: bool) -> Tuple[int]:
        if jibi >= 5:
            # 从buf.state里拿有没有结算过火车，保证同一个人的火车在一次结算里只触发一次
            if not user.buf.state.get('train'):
                user.buf.state['train'] = set()
            c = [tr for tr in count if tr.qq not in user.buf.state['train']]
            user.buf.state['train'] |= set([tr.qq for tr in count])
            qqs = set(tree.qq for tree in itertools.chain(*itertools.chain(Tree._objs, *Tree.forests)))
            from .logic_dragon import get_yesterday_qq
            qqs |= get_yesterday_qq()
            for tr in c:
                if tr.qq == user.qq:
                    continue
                if tr.qq not in qqs:
                    continue
                # 结算火车
                user.buf.send(f"玩家{tr.qq}乘坐火车便乘了1击毙！")
                config.logger.dragon << f"【LOG】玩家{tr.qq}乘坐火车便乘了1击毙。"
                await User(tr.qq, user.buf).add_jibi(1)
        return jibi,
    @classmethod
    async def OnStatusRemove(cls, count: TCount, user: 'User', status: TStatusAll, remove_all: bool) -> Tuple[bool]:
        # TODO structure need change 目前无法处理一部分闪避一部分被消的情况
        for tr in count:
            if tr.if_def:
                tr.if_def = False
                user.data.save_status_time()
                user.send_log("你的火车跳板为你的火车防止了碰撞！")
                return True,
        return False,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnJibiChange: (Priority.OnJibiChange.train, cls),
            UserEvt.OnStatusRemove: (Priority.OnStatusRemove.train, cls)}

class beacon(_card):
    name = "插件分享塔"
    id = 203
    positive = 1
    newer = 4
    description = "使用将丢弃这张卡。持有时，每天随机获得产率、速度、节能三个增益之一。"
    extra_info = {0: "插件——产率：获得击毙时，有15%的几率使其翻倍。", 1: "插件——速度：当有人发动寒冰菇时，该发动无效；如果发动的人是你，你被击毙30分钟。", 2: "插件——节能：消费击毙时，消费的击毙变为九折。"}
    des_need_init = True
    @classmethod
    def module_des(cls, qq: int):
        q = str(qq)
        m = global_state['module'][q][module_print_aux[q]]
        module_print_aux[q] += 1
        if module_print_aux[q] >= len(global_state['module'][q]):
            module_print_aux[q] = 0
        return "\t" + cls.extra_info[m['id']] + f"剩余：{m['remain'] // (10 if m['id'] == 1 else 1)}{'次' if m['id'] == 1 else '击毙'}。"
    @classmethod
    def full_description(cls, qq: int):
        return super().full_description(qq) + "\n" + cls.module_des(qq)
    @classmethod
    async def on_draw(cls, user: User):
        q = str(user.qq)
        if q not in global_state['module']:
            global_state['module'][q] = []
            module_print_aux[q] = 0
        global_state['module'][q].append({'id': (r := random.randint(0, 2)), 'remain': 10})
        config.logger.dragon << f"【LOG】用户{user.qq}刷新了一个插件{r}，现有插件：{[c['id'] for c in global_state['module'][q]]}。"
        save_global_state()
    @classmethod
    async def on_remove(cls, user: User):
        q = str(user.qq)
        r = global_state['module'][q][module_print_aux[q]]['id']
        del global_state['module'][q][module_print_aux[q]]
        if module_print_aux[q] >= len(mission):
            module_print_aux[q] = 0
        config.logger.dragon << f"【LOG】用户{user.qq}删除了一个插件{r}，现有插件：{[c['id'] for c in global_state['module'][q]]}。"
        save_global_state()
    @classmethod
    async def on_give(cls, user: User, target: User):
        q = str(user.qq)
        m = global_state['module'][q][module_print_aux[q]]
        del global_state['module'][q][module_print_aux[q]]
        if module_print_aux[q] >= len(mission):
            module_print_aux[q] = 0
        config.logger.dragon << f"【LOG】用户{user.qq}删除了一个插件{m['id']}，现有插件：{[c['id'] for c in global_state['module'][q]]}。"
        t = str(target.qq)
        if t not in global_state['module']:
            global_state['module'][t] = []
            module_print_aux[t] = 0
        global_state['module'][t].append(m)
        config.logger.dragon << f"【LOG】用户{target.qq}增加了一个插件{m['id']}，现有插件：{[c['id'] for c in global_state['module'][t]]}。"
        save_global_state()
    @classmethod
    async def OnJibiChange(cls, count: TCount, user: 'User', jibi: int, is_buy: bool) -> Tuple[int]:
        q = str(user.qq)
        l = global_state['module'][q]
        if jibi > 0:
            for c in l:
                if c['id'] == 0 and c['remain'] > 0 and random.random() < 0.15:
                    if c['remain'] >= jibi:
                        c['remain'] -= jibi
                        jibi *= 2
                    else:
                        jibi += c['remain']
                        c['remain'] = 0
                    user.send_log(f"触发了插件——产率的效果，获得击毙加倍为{jibi}！")
        elif jibi < 0:
            for c in l:
                if jibi != 0 and c['id'] == 2 and c['remain'] > 0:
                    d = ceil(-jibi / 10)
                    if c['remain'] >= d:
                        c['remain'] -= d
                        jibi += d
                    else:
                        jibi += c['remain']
                        c['remain'] = 0
                    user.send_log(f"触发了插件——节能的效果，失去击毙减少为{-jibi}！")
        save_global_state()
        return jibi,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnJibiChange: (Priority.OnJibiChange.beacon, cls)}
class beacon_checker(IEventListener):
    @classmethod
    async def OnStatusAdd(cls, count: TCount, user: 'User', status: TStatusAll, count2: int) -> Tuple[int]:
        if status is iceshroom_s:
            c = count2
            for i in range(count2):
                qqstrs = [q for q, l in global_state['module'].items() if any(c['id'] == 1 and c['remain'] == 10 for c in l)]
                if len(qqstrs) == 0:
                    return
                if str(user.qq) in qqstrs:
                    q = str(user.qq)
                    user.send_log(f"的插件——速度抵消了寒冰菇的效果！但你被击毙了30分钟！")
                    await user.death(30)
                else:
                    q = random.choice(qqstrs)
                    user.buf.send(f"玩家{q}的插件——速度抵消了寒冰菇的效果！")
                    config.logger.dragon << f"玩家{q}的插件——速度抵消了寒冰菇的效果。"
                # u = User(int(q), user.buf)
                for d in global_state['module'][q]:
                    if d['id'] == 1 and d['remain'] == 10:
                        d['remain'] = 0
                        break
                c -= 1
            save_global_state()
            return c,
        return count,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnStatusAdd: (Priority.OnStatusAdd.beacon, cls)}
UserData.register_checker(beacon_checker)
class beacon0(_statusdaily):
    id = '7'
    des = "插件——产率：今天获得击毙时，有15%的几率使其翻倍。"
    is_global = True
    @classmethod
    async def OnJibiChange(cls, count: TCount, user: 'User', jibi: int, is_buy: bool) -> Tuple[int]:
        if jibi > 0 and random.random() < 0.15:
            jibi *= 2
            user.send_log(f"触发了插件——产率的效果，获得击毙加倍为{jibi}！")
        return jibi,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnJibiChange: (Priority.OnJibiChange.beacon0, cls)}
class beacon1(_statusdaily):
    id = '8'
    des = "插件——速度：当今天有人发动寒冰菇时，该发动无效。"
    is_global = True
    @classmethod
    async def OnStatusAdd(cls, count: TCount, user: 'User', status: TStatusAll, count2: int) -> Tuple[int]:
        if status is iceshroom_s:
            user.buf.send(f"插件——速度抵消了寒冰菇的效果！")
            return 0,
        return count,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnStatusAdd: (Priority.OnStatusAdd.beacon1, cls)}
class beacon2(_statusdaily):
    id = '9'
    des = "插件——节能：今天消费击毙时，消费的击毙变为九折。"
    is_global = True
    @classmethod
    async def OnJibiChange(cls, count: TCount, user: 'User', jibi: int, is_buy: bool) -> Tuple[int]:
        if jibi < 0:
            d = ceil(-jibi / 10)
            jibi += d
            user.send_log(f"触发了插件——节能的效果，失去击毙减少为{-jibi}！")
        return jibi,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnJibiChange: (Priority.OnJibiChange.beacon2, cls)}

class lab(_card):
    id = 204
    name = "科技中心"
    description = "如果全局状态中存在你的火车，你的所有火车获得火车跳板；如果你的装备中有组装机，你获得一张集装机械臂；如果你的手牌中有插件分享塔，今日你的插件效果会变为全局状态；如果三者都有，你获得一张核弹；如果三者都没有，你抽一张factorio系列的牌。"
    positive = 1
    newer = 4
    @classmethod
    async def use(cls, user: User) -> None:
        if t1 := me.check_limited_status('t', lambda c: c.qq == user.qq):
            user.send_log("有火车，" + user.char + "的每辆火车获得了火车跳板！")
            for tr in t1:
                tr.if_def = True
            user.data.save_status_time()
        if (t2 := user.data.check_equipment(3) != 0):
            user.send_log("的装备中有组装机，" + user.char + "获得了一张集装机械臂！")
            await user.draw(0, cards=[stack_inserter])
        if (t3 := Card(203) in user.data.hand_card):
            q = str(user.qq)
            l = global_state["module"][q]
            u = Userme(user)
            user.send_log("的装备中有插件分享塔，" + user.char + "增加了全局状态：", end='')
            config.logger.dragon << ",".join(m['id'] for m in l)
            for m in l:
                c = str(m["id"] + 7)
                await u.add_daily_status(c)
                user.buf.send(Status(c).brief_des, end='')
            user.buf.send('！')
        if t1 and t2 and t3:
            user.send_log("获得了一张核弹！")
            await user.draw(0, cards=[nuclear_bomb])
        if not (t1 or t2 or t3):
            user.send_log("抽了一张factorio系列的牌！")
            await user.draw(1, extra_lambda=lambda c: c.id >= 200 and c.id < 210)

class stack_inserter(_card):
    id = -4
    name = "集装机械臂"
    positive = 1
    description = "选择一张卡牌，将其销毁，并获得等同于卡牌编号/5的击毙。如果你有组装机，使其获得等同于卡牌编号的组装量。"
    @classmethod
    def can_use(cls, user: User, copy: bool) -> bool:
        return len(user.data.hand_card) >= (1 if copy else 2)
    @classmethod
    async def use(cls, user: User) -> None:
        async with user.choose_cards("请选择你手中的一张牌销毁，输入id号。", 1, 1) as l, check_active(l):
            card = Card(l[0])
            config.logger.dragon << f"【LOG】用户{user.qq}选择了卡牌{card.name}。"
            user.send_char('销毁了卡牌：\n' + card.full_description(user.qq))
            await user.remove_cards([card])
            user.send_char(f"获得了{card.id // 5}击毙！")
            await user.add_jibi(card.id // 5)
            if count := user.data.check_equipment(3):
                old = assembling.get_card_limit(user.data.extra.assembling, count)
                user.data.extra.assembling += card.id
                new = assembling.get_card_limit(user.data.extra.assembling, count)
                user.log << f"增加了{card.id}的组装量，现有{user.data.extra.assembling}。"
                if new > old:
                    user.send_char(f"的组装机{count}型为你增加了{new - old}的手牌上限！")

class nuclear_bomb(_card):
    id = -131073
    name = "核弹"
    description = "杀死所有人120分钟。"
    positive = 0
    @classmethod
    async def use(cls, user: User) -> None:
        user.send_char("杀死了所有人！")
        qqs = [t['qq'] for t in config.userdata.execute("select qq from dragon_data where dead=false").fetchall()]
        for qq in qqs:
            await User(qq, user.buf).killed(user)

class flamethrower(_card):
    id = 205
    name = "火焰喷射器"
    description = "抽到时，如果场上有寒冰菇，摧毁一个寒冰菇，获得50击毙，并被誉为今天的英雄。如果没有，自己被击毙。"
    positive = 0
    newer = 4
    consumed_on_draw = True
    @classmethod
    async def on_draw(cls, user: User) -> None:
        if me.check_daily_status('i'):
            user.send_char("摧毁了一个寒冰菇，获得了50击毙！" + user.char + "就是今天的英雄！")
            Userme(user).remove_daily_status('i', remove_all=False)
            await user.add_jibi(50)
        else:
            user.send_char("今天没有寒冰菇！" + user.char + "被击毙了！")
            await user.death()

class rocket(_card):
    id = 206
    name = "火箭"
    description = "发射一枚火箭，获得游戏的胜利。"
    positive = 1
    newer = 4
    @classmethod
    async def use(cls, user: User) -> None:
        user.buf.send(f"恭喜{user.char}，今天{user.char}赢了！")
        await user.add_daily_status('W')

mission: List[Tuple[int, str, Callable[[str], bool]]] = []
def add_mission(doc: str):
    def _(f: Callable[[str], bool]):
        global mission
        mission.append((len(mission), doc, f))
        return f
    return _
def get_mission():
    return random.randint(0, len(mission) - 1)

for i in range(2, 9):
    add_mission(f"字数为{i}。")((lambda i: lambda s: len([c for c in s if c != ' ']) == i)(i))
add_mission("包含一个亿或以下的常用单汉字数字或阿拉伯数字。")(lambda s: len(set(s) & set('0123456789零一二三四五六七八九十百千万亿兆壹贰叁肆伍陆柒捌玖拾佰仟')) != 0)
add_mission("包含一个常用的人称代词。")(lambda s: len(set(s) & set('我你他她它祂您怹咱俺恁')) != 0)
@add_mission("包含一个中国的省级行政单位的全称（可以不带省、市、xx族自治区或特别行政区这几个字）。")
def _(s):
    for c in ("黑龙江", "吉林", "辽宁", "河北", "河南", "山东", "山西", "安徽", "江西", "江苏", "浙江", "福建", "台湾", "广东", "湖南", "湖北", "海南", "云南", "贵州", "四川", "青海", "甘肃", "陕西", "内蒙古", "新疆", "广西", "宁夏", "西藏", "北京", "天津", "上海", "重庆", "香港", "澳门"):
        if c in s:
            return True
    return False
add_mission("包含的/地/得。")(lambda s: len(set(s) & set('的地得')) != 0)
add_mission("包含叠字。")(lambda s: any(a == b and ord(a) > 255 for a, b in more_itertools.windowed(s, 2)))
for c in ("人", "大", "小", "方", "龙"):
    add_mission(f"包含“{c}”。")((lambda c: lambda s: c in s)(c))
@add_mission("包含国际单位制的七个基本单位制之一。")
def _(s):
    for c in ("米", "千克", "公斤", "秒", "安", "开", "摩尔", "坎德拉"):
        if c in s:
            return True
    return False
add_mission("前两个字的声母相同。")(lambda s: len(p := pinyin(list(s[0:2]), style=Style.INITIALS, strict=True, errors='ignore', heteronym=True)) >= 2 and len(set(p[0]) & set(p[1])) != 0)
add_mission("前两个字的韵母相同。")(lambda s: len(p := pinyin(list(s[0:2]), style=Style.FINALS, strict=True, errors='ignore', heteronym=True)) >= 2 and len(set(p[0]) & set(p[1])) != 0)
add_mission("首字没有声母。")(lambda s: len(p := pinyin(s[0:1], style=Style.INITIALS, strict=True, errors='ignore', heteronym=True)) >= 1 and '' in p[0])
add_mission("首字是多音字。")(lambda s: len(p := pinyin(s[0:1], style=Style.TONE, strict=True, errors='ignore', heteronym=True)) >= 1 and len(p[0]) > 1)
add_mission("所有字音调相同且至少包含两个字。")(lambda s: len(p := pinyin(list(s), style=Style.FINALS_TONE3, neutral_tone_with_five=True, strict=True, errors='ignore', heteronym=True)) > 1 and len(reduce(lambda x, y: x & y, (set(c[-1] for c in s) for s in p))) != 0)
add_mission("首字与尾字相同且至少包含两个字。")(lambda s: len(s) >= 2 and s[0] == s[-1])

@lru_cache(10)
def Equipment(id):
    if id in _equipment.id_dict:
        return _equipment.id_dict[id]
    else:
        raise ValueError("斯")

class equipment_meta(type):
    def __new__(cls, clsname, bases, attrs):
        if len(bases) != 0 and 'id_dict' in bases[0].__dict__:
            c = type.__new__(cls, clsname, bases, attrs)
            bases[0].id_dict[attrs['id']] = c
        else:
            c = type.__new__(cls, clsname, bases, attrs)
        return c

class _equipment(IEventListener, metaclass=equipment_meta):
    id_dict: Dict[int, TEquipment] = {}
    id = -127
    name = ''
    des_shop = ''
    failure_message = ''
    @classmethod
    def description(cls, count: TCount) -> str:
        pass
    @classmethod
    def full_description(cls, count: TCount, user: User) -> str:
        return f"{cls.id}. {count * '☆'}{cls.name}\n\t{cls.description(count)}"
    @classmethod
    def can_use(cls, user: User, count: int) -> bool:
        return True
    @classmethod
    async def use(cls, user: User, count: int):
        pass

class bikini(_equipment):
    id = 0
    name = '比基尼'
    des_shop = '你每次获得击毙时都有一定几率加倍。一星为5%，二星为10%，三星为15%。'
    @classmethod
    def description(cls, count: TCount):
        return f'你每次获得击毙时都有{5 * count}%几率加倍。'
    @classmethod
    async def OnJibiChange(cls, count: TCount, user: 'User', jibi: int, is_buy: bool) -> Tuple[int]:
        if jibi > 0 and random.random() < 0.02 * count:
            jibi *= 2
            user.send_log(f"触发了比基尼的效果，获得击毙加倍为{abs(jibi)}！")
        return jibi,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnJibiChange: (Priority.OnJibiChange.bikini, cls)}

class schoolsui(_equipment):
    id = 1
    name = '学校泳装'
    des_shop = '你每次击毙减少或商店购买都有一定几率免单。一星为4.76%，二星为9.09%，三星为13.04%。'
    @classmethod
    def description(cls, count: TCount):
        return f'你每次击毙减少或商店购买都有{count / (20 + count) * 100:.2f}%几率免单。'
    @classmethod
    async def OnJibiChange(cls, count: TCount, user: 'User', jibi: int, is_buy: bool) -> Tuple[int]:
        if jibi < 0 and random.random() < count / (20 + count):
            jibi = 0
            user.send_log("触发了学生泳装的效果，本次免单！")
        return jibi,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnJibiChange: (Priority.OnJibiChange.schoolsui, cls)}

class tarot(_equipment):
    id = 2
    name = "塔罗原典"
    @classmethod
    def description(cls, count: TCount) -> str:
        return f"每天限一次，可以从{2 * count}张塔罗牌中选择一张发动。"
    @classmethod
    def can_use(cls, user: User, count: int) -> bool:
        return user.data.extra.tarot_time != 0
    failure_message = "你今日使用次数已完！"
    @classmethod
    async def use(cls, user: User, count: int):
        if await user.choose():
            if user.data.extra.tarot_time == 0:
                user.send_char("今日使用次数已完！")
                return
            h = f"{user.qq} {date.today().isoformat()}"
            state = random.getstate()
            random.seed(h)
            l1 = list(range(22))
            random.shuffle(l1)
            l2 = sorted(l1[:2 * count])
            random.setstate(state)
            config.logger.dragon << f"【LOG】询问用户{user.qq}选择塔罗原典。"
            cards = "\n".join(Card(i).full_description(user.qq) for i in l2)
            c = await user.buf.aget(prompt="你今天可以从以下牌中选择一张使用，请输入id号。\n" + cards,
                arg_filters=[
                        extractors.extract_text,
                        check_handcard(user),
                        lambda s: list(map(int, re.findall(r'\-?\d+', str(s)))),
                        validators.fit_size(1, 1, message="请输入正确的张数。"),
                        validators.ensure_true(lambda l: l[0] in l2)
                    ])[0]
            user.log << f"选择了卡牌{c}。"
            user.data.extra.tarot_time -= 1
            await user.draw_and_use(Card(c))
    @classmethod
    async def OnNewDay(cls, count: TCount, user: 'User') -> Tuple[()]:
        user.data.extra.tarot_time = 1
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnNewDay: (Priority.OnNewDay.tarot, cls)}
newday_check[3] |= set(('2: ',))

class assembling(_equipment):
    id = 3
    name = "组装机"
    @classmethod
    def description(cls, count: TCount) -> str:
        d = {1: 200, 2: 150, 3: 100}[count]
        return f"当你抽卡时，组装机获得等同于卡牌编号的组装量（不小于0）。你每有2^n*{d}组装量，手牌上限+1，其中n为已经生产过的手牌上限个数。"
    @classmethod
    def full_description(cls, count: TCount, user: User) -> str:
        return f"{cls.id}. {cls.name}{count}型\n\t{cls.description(count)}\n\t当前组装量：{user.data.extra.assembling}"
    @classmethod
    def get_card_limit(cls, data: int, count: TCount) -> int:
        d = {1: 200, 2: 150, 3: 100}[count]
        return int(log(data // d + 1, 2))
    @classmethod
    async def AfterCardDraw(cls, count: TCount, user: 'User', cards: Iterable[TCard]) -> Tuple[()]:
        old = cls.get_card_limit(user.data.extra.assembling, count)
        user.data.extra.assembling += (s := sum(max(c.id, 0) for c in cards))
        new = cls.get_card_limit(user.data.extra.assembling, count)
        user.log << f"增加了{s}的组装量，现有{user.data.extra.assembling}。"
        if new > old:
            user.send_char(f"的组装机{count}型为你增加了{new - old}的手牌上限！")
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.AfterCardDraw: (Priority.AfterCardDraw.assembling, cls)}

# 爬塔格子
class Grid:
    __slots__ = ('stage', 'hashed')
    pool: Dict[int, 'Grid'] = {}
    def __new__(cls, stage: int) -> Any:
        if i := cls.pool.get(stage):
            return i
        return super(Grid, cls).__new__(cls)
    def __init__(self, stage: int):
        self.stage = stage
        h = f"{stage} 0".encode('utf-8')
        b = hashlib.sha1(h).digest()
        self.hashed = int.from_bytes(b[0:3], 'big')
    def __hash__(self):
        return hash((self.stage,))
    def __str__(self):
        return f"{self.stage}层"
    @property
    def description(self):
        i = self.hashed
        s = "" if self.stage > 400 else f"增加{2 + i % 4}pt，"
        i //= 4
        content = i % 100
        if content < 6:
            s += f"被击毙{content // 2 * 5 + 5}分钟。"
        elif content < 10:
            s += f"扣除{content // 2 * 2 - 4}击毙。"
        elif content < 60:
            s += f"获得{content // 10 * 2}击毙。"
        elif content < 75:
            s += f"获得活动pt后，再扔一次骰子{'前进' if content < 70 else '后退'}。"
        elif content < 85:
            s += "抽一张卡并立即发动效果。"
        elif content < 95:
            s += "你下次行走距离加倍。"
        else:
            s += "随机获得10~30活动pt。"
        return s
    @property
    def parent(self):
        if self.stage >= 1:
            return Grid(self.stage - 1)
        else:
            return None
    @property
    def child(self):
        return Grid(self.stage + 1)
    async def do(self, user: User):
        i = self.hashed
        if self.stage <= 400:
            await user.add_event_pt(2 + i % 4)
        i //= 4
        content = i % 100
        if content < 6: # 被击毙5/10/15/20/25分钟
            user.send_log(f"走到了：被击毙{content // 2 * 5 + 5}分钟。")
            await user.death(content // 2 * 5 + 5)
        elif content < 10: # 扣除2/4击毙
            user.send_log(f"走到了：扣除{content // 2 * 2 - 4}击毙。")
            await user.add_jibi(-(content // 2 * 2 - 4))
        elif content < 60: # 获得2/4/6/8/10击毙
            user.send_log(f"走到了：获得{content // 10 * 2}击毙。")
            await user.add_jibi(content // 10 * 2)
        elif content < 75: # 获得活动pt后，再扔一次骰子前进（10）/后退（5）
            n = random.randint(1, 6)
            user.send_log(f"走到了：获得活动pt后，再扔一次骰子{'前进' if content < 70 else '后退'}。{user.char}扔到了{n}。")
            return n if content < 70 else -n
        elif content < 85: # 抽一张卡并立即发动效果
            user.send_log("走到了：抽一张卡并立即发动效果。")
            c = draw_card()
            await user.draw_and_use(c)
        elif content < 95: # 你下次行走距离加倍。
            user.send_log("走到了：你下次行走距离加倍。")
            await user.add_status('D')
        else: # 随机获得10~30活动pt。
            user.send_log("走到了：随机获得10~30活动pt。")
            n = random.randint(10, 30)
            user.send_log(f"获得了{n}pt！")
            await user.add_event_pt(n)
        return 0
class kuaizou_s(_statusnull):
    id = 'D'
    des = "快走：在活动中，你下次行走距离加倍。"

class Tree:
    __slots__ = ('id', 'parent', 'childs', 'word', 'fork', 'kwd', 'hdkwd', 'qq')
    forests: List[List[List['Tree']]] = []
    _objs: List[List['Tree']] = [] # [[wd0, wd1, wd2], [wd2a], [wd2b]]
    max_branches = 0
    def __init__(self, parent: 'Tree', word: str, qq: int, kwd: str, hdkwd: str, *, id: Optional[Tuple[int, int]]=None, fork: bool=False):
        self.parent = parent
        if parent:
            parent.childs.append(self)
            id = id or (parent.id[0] + 1, parent.id[1])
        else:
            id = id or (0, 0)
        if not self.find(id):
            self.id: Tuple[int, int] = id
            if Tree.max_branches <= id[1]:
                for i in range(id[1] + 1 - Tree.max_branches):
                    self._objs.append([])
                Tree.max_branches = id[1] + 1
        else:
            self.id = (id[0], Tree.max_branches)
            Tree.max_branches += 1
            self._objs.append([])
        self._objs[self.id[1]].append(self)
        self.childs: List['Tree'] = []
        self.word = word
        self.fork = fork
        self.qq = qq
        self.kwd = kwd
        self.hdkwd = hdkwd
    @classmethod
    def find(cls, id: Tuple[int, int]):
        try:
            if len(cls._objs[id[1]]) == 0:
                return None
            return cls._objs[id[1]][id[0] - cls._objs[id[1]][0].id[0]]
        except IndexError:
            return None
    @property
    def id_str(self):
        return str(self.id[0]) + ('' if self.id[1] == 0 else chr(96 + self.id[1]))
    @staticmethod
    def str_to_id(str):
        match = re.match(r'(\d+)([a-z])?', str)
        return int(match.group(1)), (0 if match.group(2) is None else ord(match.group(2)) - 96)
    @staticmethod
    def match_to_id(match):
        return int(match.group(1)), (0 if match.group(2) is None else ord(match.group(2)) - 96)
    @classmethod
    def init(cls, is_daily: bool):
        cls._objs = []
        cls.max_branches = 0
        if is_daily:
            cls.forests = []
    def __repr__(self):
        return f"<id: {self.id}, parent_id: {'None' if self.parent is None else self.parent.id}, word: \"{self.word}\">"
    def __str__(self):
        return f"{self.id_str}{'+' if self.fork else ''}<{'-1' if self.parent is None else self.parent.id_str}/{self.qq}/{self.kwd}/{self.hdkwd}/ {self.word}"
    def remove(self):
        id = self.id
        begin = id[0] - Tree._objs[id[1]][0].id[0]
        to_remove = set(Tree._objs[id[1]][begin:])
        Tree._objs[id[1]] = Tree._objs[id[1]][:begin]
        while True:
            count = 0
            for s in Tree._objs:
                if len(s) == 0 or (parent := s[0].parent) is None:
                    continue
                if parent in to_remove:
                    to_remove.update(Tree._objs[s[0].id[1]])
                    Tree._objs[s[0].id[1]] = []
                    count += 1
            # TODO 额外判断有多个parents的节点
            if count == 0:
                break
        if self.parent is not None:
            self.parent.childs.remove(self)
    def before(self, n):
        node = self
        for i in range(n):
            node = node and node.parent
        return node
    def get_parent_qq_list(self, n: int):
        parent_qqs: List[int] = []
        begin = self
        for j in range(n):
            parent_qqs.append(begin.qq)
            begin = begin.parent
            if begin is None:
                break
        return parent_qqs
    @classmethod
    def get_active(cls, have_fork=True):
        words = [s[-1] for s in cls._objs if len(s) != 0 and len(s[-1].childs) == 0]
        if have_fork:
            for s in cls._objs:
                for word in s:
                    if word.fork and len(word.childs) == 1:
                        words.append(word)
        return words
    @classmethod
    def graph(self):
        pass

me = UserData(config.selfqq)
dragondata = UserData(0)

class Dragon:
    def __init__(self, buf: Union[config.SessionBuffer, User]):
        self.data = dragondata
        if isinstance(buf, User):
            self.buf = buf.buf
        else:
            self.buf = buf
    

dragon: Callable[[User], Dragon] = lambda user: Dragon(user.buf)
