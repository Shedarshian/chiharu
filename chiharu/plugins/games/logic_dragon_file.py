import itertools, hashlib
import random, more_itertools, json, re
from typing import Any, Awaitable, Callable, Coroutine, Dict, Generic, Iterable, List, NamedTuple, Optional, Set, Tuple, Type, TypeVar, TypedDict, Union, final, Annotated
from collections import Counter, UserDict, UserList, defaultdict
from functools import lru_cache, partial, wraps, reduce
from struct import unpack, pack
from copy import copy, deepcopy
from dataclasses import dataclass, astuple, field
from math import ceil, log
from abc import ABC, ABCMeta, abstractmethod
from datetime import date, datetime, timedelta, time
from contextlib import asynccontextmanager
from nonebot import get_bot
from nonebot.command import CommandSession
from pypinyin import pinyin, Style
from nonebot.command.argfilter import extractors, validators
from nonebot.command.argfilter.validators import _raise_failure
from .. import config
from ..config import 句尾
from .logic_dragon_type import NotActive, Pack, Sign, TGlobalState, TUserData, TAttackType, CounterOnly, UserEvt, Priority, TBoundIntEnum, async_data_saved, check_active, indexer, nothing, TQuest, ensure_true_lambda, check_handcard, TModule, UnableRequirement, check_if_unable, Tree, DragonState, MajOneHai
from .maj import MajIdError

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
        extra_data_init = Game.me.extra.data.pack()
        config.userdata.execute('insert into dragon_data (qq, jibi, draw_time, today_jibi, today_keyword_jibi, death_time, card, status, daily_status, status_time, card_limit, shop_drawn_card, event_pt, spend_shop, equipment, event_stage, event_shop, extra_data, dead, flags, hp, mp, collections) values (?, 0, 0, 10, 10, ?, ?, ?, ?, ?, 4, 0, 0, 0, ?, 0, 0, ?, false, 0, 500, 500, ?)', (qq, '', '', '', '', '[]', '{}', extra_data_init, '{}'))
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
T_skill = TypeVar('T_skill', bound='DragonSkill')
TSkill = Type[T_skill]
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
    async def BeforeCardDraw(cls, count: TCount, user: 'User', n: int, positive: Optional[set[int]], extra_lambda: Optional[Callable]) -> Tuple[Optional[List[TCard]]]:
        """Called Before a card is drawn in any cases. Includes cards consumed when drawn.

        Arguments:
        n: the number to draw.
        positive: specify 'positive' of the card drawn.
        extra_lambda: extra constraint of the card drawn.
        
        Returns:
        Optional[List[TCard]]: if not None, replace the card drawn, and halt."""
        pass
    @classmethod
    async def BeforeCardUse(cls, count: TCount, user: 'User', card: TCard) -> Tuple[Optional[Awaitable]]:
        """Called Before a card is used in any cases. Includes cards consumed when drawn.

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
    async def OnDeath(cls, count: TCount, user: 'User', killer: 'User', time: int, c: TAttackType) -> Tuple[int, bool]:
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
    async def OnAttack(cls, count: TCount, user: 'User', attack: 'Attack') -> Tuple[bool]:
        """Called when a user attack other.

        Arguments:
        attack: the Attack object.

        Returns:
        bool: represents whether the attack is dodged."""
        pass
    @classmethod
    async def OnAttacked(cls, count: TCount, user: 'User', attack: 'Attack') -> Tuple[bool]:
        """Called when a user is attacked.

        Arguments:
        attack: the Attack object.

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
    async def OnStatusRemove(cls, count: TCount, user: 'User', status: TStatusAll, remove_all: bool, remover: Optional['User']=None) -> Tuple[bool]:
        """Called when a status is removed.
        
        Arguments:
        status: a str for statusnull/statusdaily, or a T_status object.
        remove_all: if remove all this state.
        remover: who removes this state.
        
        Returns:
        bool: whether the removement is dodged."""
        pass
    @classmethod
    async def AfterStatusRemove(cls, count: TCount, user: 'User', status: TStatusAll, remove_all: bool) -> Tuple[()]:
        """Called after a status is removed.
        
        Arguments:
        status: a str for statusnull/statusdaily, or a T_status object.
        remove_all: if remove all this state."""
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
    async def BeforeDragoned(cls, count: TCount, user: 'User', state: DragonState) -> Tuple[bool, int, str]:
        """Called before a user dragoning.

        Arguments:
        state: contains the dragon word, the parent tree node, and extra info.

        Returns:
        bool: represents whether the user can dragon;
        int: offset to modify the dragon distance allowed;
        str: failure message."""
        pass
    @classmethod
    async def CheckSuguri(cls, count: TCount, user: 'User', state: DragonState) -> Tuple[bool]:
        """Called when Suguri's Accelerator is checked to be used.

        Arguments:
        state: contains the dragon word, the parent tree node, and extra info.
        
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
        self.counter = TAttackType()
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
        self.counter = TAttackType()
        self.rebounded = True
        return False

class Kill(Attack):
    name = "击毙"
    def __init__(self, attacker: 'User', defender: 'User', minute: int):
        self.minute = minute
        super().__init__(attacker, defender)
    async def self_action(self):
        await self.defender.death(self.minute * self.multiplier, self.attacker, self.counter)

# 屠龙活动里的伤害
class Damage(Attack):
    name = "造成伤害"
    def __init__(self, attacker: 'User', defender: 'User', damage: int, must_hit: bool=False):
        self.damage = damage
        self.must_hit = must_hit
        self.dodge_rate = 0.1
        self.dodge_pt = random.random()
        super().__init__(attacker, defender)
    def dodge(self):
        return not self.must_hit and self.dodge_pt < self.dodge_rate
    async def self_action(self):
        if self.dodge():
            self.defender.send_log(f"闪避了此次伤害{句尾}")
        else:
            beg = self.defender.data.hp // 100
            self.defender.send_log(f"受到了{self.damage * self.multiplier}点伤害{句尾}")
            if self.defender.data.hp < self.damage * self.multiplier:
                self.defender.data.hp = 0
            else:
                self.defender.data.hp -= self.damage * self.multiplier
            jibi_to_add = beg - self.defender.data.hp // 100
            if self.attacker.qq != 1:
                self.attacker.send_log(f"获得了{jibi_to_add}击毙与{jibi_to_add}pt{句尾}")
                await self.attacker.add_jibi(jibi_to_add)
                await self.attacker.add_event_pt(jibi_to_add)
            if self.defender.data.hp == 0:
                self.defender.data.hp = self.defender.data.hp_max
                self.defender.data.mp = self.defender.data.mp_max
                if self.defender.qq == 1:
                    self.defender.send_log(f"死了一条命{句尾}")
                    self.defender.data.dragon_event_exp += 1
                    if self.attacker.qq != 1:
                        self.attacker.send_log("获得了10击毙与20pt" + 句尾)
                        await self.attacker.add_jibi(10)
                        await self.attacker.add_event_pt(20)
                else:
                    self.defender.send_log(f"死了{句尾}")
                    await self.defender.death(60, c=TAttackType(hpzero=True))

class Game:
    session_list: List[CommandSession] = []
    userdatas: Dict[int, 'UserData'] = {}
    me: 'UserData' = None
    @classmethod
    def wrapper_noarg(cls, f: Callable[[Any], Awaitable[config.SessionBuffer]]):
        @wraps(f)
        async def _f(buf: config.SessionBuffer, *args, **kwargs):
            try:
                return await f(buf, *args, **kwargs)
            finally:
                await buf.flush()
        return _f
    @classmethod
    def wrapper(cls, f: Callable[[Any], Awaitable[config.SessionBuffer]]):
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
    @classmethod
    def userdata(cls, qq: int):
        if qq == config.selfqq:
            return Game.me
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

extra_data_format = '!BLIIIIBBI'
@dataclass
class ExtraData:
    tarot_time: int # unsigned char
    assembling: int # unsigned long
    placeholder0: int         # unsigned int
    placeholder1: int         # unsigned int
    placeholder2: int     # unsigned int
    placeholder3: int     # unsigned int
    mangan: int     # unsigned char
    yakuman: int    # unsigned char
    maj_quan: int   # unsigned int
    def pack(self):
        return pack(extra_data_format, *astuple(self))
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
        self.data.assembling = max(0, value)
        self.save_func(self.data)
    # @property
    # def hp(self):
    #     return self.data.hp
    # @hp.setter
    # def hp(self, value):
    #     self.data.hp = value
    #     self.save_func(self.data)
    # @property
    # def mp(self):
    #     return self.data.mp
    # @mp.setter
    # def mp(self, value):
    #     self.data.mp = value
    #     self.save_func(self.data)
    # @property
    # def hp_max(self):
    #     return self.data.hp_max
    # @hp_max.setter
    # def hp_max(self, value):
    #     self.data.hp_max = value
    #     self.save_func(self.data)
    # @property
    # def mp_max(self):
    #     return self.data.mp_max
    # @mp_max.setter
    # def mp_max(self, value):
    #     self.data.mp_max = value
    #     self.save_func(self.data)
    @property
    def mangan(self):
        return self.data.mangan
    @mangan.setter
    def mangan(self, value):
        self.data.mangan = value
        self.save_func(self.data)
    @property
    def yakuman(self):
        return self.data.yakuman
    @yakuman.setter
    def yakuman(self, value):
        self.data.yakuman = value
        self.save_func(self.data)
    @property
    def maj_quan(self):
        return self.data.maj_quan
    @maj_quan.setter
    def maj_quan(self, value):
        self.data.maj_quan = value
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
        config.logger.dragon << f"【DEBUG】用户{qq}UserData被创建。"
        self._qq = qq
        self.node: TUserData = dict(find_or_new(qq))
        self.hand_card = [] if self.node['card'] == '' else [Card(int(x)) for x in self.node['card'].split(',')]
        def save(key, value):
            config.logger.dragon << f"【LOG】用户{self.qq}保存{key}，值为{value}。"
            config.userdata.execute(f"update dragon_data set {key}=? where qq=?", (str(value), self.qq))
        self.status_time: List[T_status] = property_list(partial(save, 'status_time'), [])
        self.status_time.data = eval(self.node['status_time'])
        if self.node['maj'] is None:
            self.maj: Tuple[List[int], List[int]] = (sorted(MajOneHai.get_random() for i in range(13)), [])
            self.save_maj()
        else:
            self.maj: Tuple[List[int], List[int]] = eval(self.node['maj']) # ([1, 2, 3], [4])
        self.equipment: Dict[int, int] = property_dict(partial(save, 'equipment'), {})
        self.equipment.data = eval(self.node['equipment'])
        self.collections: Dict[int, Any] = property_dict(partial(save, 'collections'), {})
        self.collections.data = eval(self.node['collections'])
        def save2(value):
            config.userdata.execute(f"update dragon_data set extra_data=? where qq=?", (value, self.qq))
        self.extra = DynamicExtraData(self.node['extra_data'], save2)
        self._reregister_things()
    def __del__(self):
        config.logger.dragon << f"【DEBUG】用户{self.qq}UserData被删除。"
        # self.save_status_time()
        # self.set_cards()
    def _reregister_things(self):
        self.event_listener: defaultdict[int, TEventList] = deepcopy(self.event_listener_init)
        for c in self.hand_card:
            self._register_card(c)
        for s in itertools.chain(map(StatusNull, self.status), map(StatusDaily, self.daily_status)):
            self._register_status(s)
        for s in self.status_time:
            self._register_status_time(s)
        for id, star in self.equipment.items():
            self._register_equipment(Equipment(id), star)
        self.status_time_checked
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
                    if priority in self.event_listener[key]:
                        self.event_listener[key].pop(priority)
                else:
                    self.event_listener[key][priority][el].remove(eln)
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
    def save_collections(self):
        self.collections.f(self.collections.data)
    def save_maj(self):
        config.userdata.execute("update dragon_data set maj=? where qq=?", (str(self.maj), self.qq))
        config.logger.dragon << f"【LOG】设置用户{self.qq}麻将为{str(self.maj)}。"
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
        return min(20, self.card_limit_raw + self.card_limit_from_assembling)+self.daily_status.count('H')
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
    def dragon_event_exp(self):
        return self.node['event_stage']
    @dragon_event_exp.setter
    def dragon_event_exp(self, value):
        config.userdata.execute("update dragon_data set event_stage=? where qq=?", (value, self.qq))
        self.node['event_stage'] = value
    @property
    def event_skill(self):
        return self.node['event_skill']
    @event_skill.setter
    def event_skill(self, value):
        config.userdata.execute("update dragon_data set event_skill=? where qq=?", (value, self.qq))
        self.node['event_skill'] = value
    @indexer
    def dragon_event_skill(self, index):
        return (self.event_skill // 10 ** index) % 10
    @dragon_event_skill.setter
    def dragon_event_skill(self, index, item):
        if not 0 <= item <= 4:
            raise ValueError
        self.event_skill += (item - (self.event_skill // 10 ** index) % 10) * 10 ** index
    @property
    def hp(self):
        return self.node['hp']
    @hp.setter
    def hp(self, value):
        config.userdata.execute("update dragon_data set hp=? where qq=?", (value, self.qq))
        self.node['hp'] = value
    @property
    def mp(self):
        return self.node['mp']
    @mp.setter
    def mp(self, value):
        config.userdata.execute("update dragon_data set mp=? where qq=?", (value, self.qq))
        self.node['mp'] = value
    @property
    def last_dragon_time(self):
        return self.node['last_dragon_time']
    @last_dragon_time.setter
    def last_dragon_time(self, value):
        config.userdata.execute("update dragon_data set last_dragon_time=? where qq=?", (value, self.qq))
        self.node['last_dragon_time'] = value
    @property
    def if_richi(self):
        return bool(self.node['flags'] & 1)
    @if_richi.setter
    def if_richi(self, value):
        self.node['flags'] = (self.node['flags'] & ~1) + int(bool(value)) * 1
        config.userdata.execute("update dragon_data set flags=? where qq=?", (self.node['flags'], self.qq))
    @property
    def not_first_round(self):
        return bool(self.node['flags'] & 2)
    @not_first_round.setter
    def not_first_round(self, value):
        self.node['flags'] = (self.node['flags'] & ~2) + int(bool(value)) * 2
        config.userdata.execute("update dragon_data set flags=? where qq=?", (self.node['flags'], self.qq))
    @property
    def status_time_checked(self):
        i = 0
        while i < len(self.status_time):
            t = self.status_time[i]
            if not t.check():
                self._deregister_status_time(t)
                self.status_time.pop(i)
            else:
                i += 1
        return self.status_time
    @property
    def quests(self):
        q = str(self.qq)
        if q not in global_state['quest']:
            global_state['quest'][q] = []
            quest_print_aux[q] = 0
            save_global_state()
        return global_state['quest'][q]
    @property
    def quest_c(self):
        q = str(self.qq)
        r = self.quests[quest_print_aux[q]]
        quest_print_aux[q] += 1
        if quest_print_aux[q] >= len(self.quests):
            quest_print_aux[q] = 0
        return r
    def pop_quest(self):
        q = str(self.qq)
        r = self.quest_c
        del self.quests[quest_print_aux[q]]
        if quest_print_aux[q] >= len(self.quests):
            quest_print_aux[q] = 0
        return r
    @property
    def modules(self):
        q = str(self.qq)
        if q not in global_state['module']:
            global_state['module'][q] = []
            module_print_aux[q] = 0
            save_global_state()
        return global_state['module'][q]
    @property
    def module_c(self):
        q = str(self.qq)
        r = self.modules[module_print_aux[q]]
        module_print_aux[q] += 1
        if module_print_aux[q] >= len(self.modules):
            module_print_aux[q] = 0
        return r
    def pop_module(self):
        q = str(self.qq)
        r = self.module_c
        del self.modules[module_print_aux[q]]
        if module_print_aux[q] >= len(self.modules):
            module_print_aux[q] = 0
        return r
    @property
    def steal(self):
        q = str(self.qq)
        if q not in global_state['steal']:
            global_state['steal'][q] = {'time': 0, 'user': []}
            save_global_state()
        return global_state['steal'][q]
    @steal.setter
    def steal(self, value):
        global_state['steal'][str(self.qq)] = value
    @property
    def dragon_head(self):
        q = str(self.qq)
        if q not in global_state['dragon_head']:
            global_state['dragon_head'][q] = {}
            save_global_state()
        return global_state['dragon_head'][q]
    @property
    def luck(self):
        return 5 * self.check_equipment(5) + self.hand_card.count(xingyunhufu)
    @property
    def dragon_level(self):
        """begin from 0."""
        if self.qq == 1:
            return self.dragon_event_exp
        if self.dragon_event_exp >= 55:
            return (self.dragon_event_exp - 55) // 10 + 10
        else:
            return int((self.dragon_event_exp * 2 + 0.25) ** 0.5 - 0.5)
    @property
    def hp_max(self):
        return 500 + 25 * self.dragon_level
    @property
    def mp_max(self):
        return 500 + 25 * self.dragon_level
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
        self.data.status_time_checked
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
    def send_log(self, s: str, /, end='\n', no_char=False):
        self.buf.send_log.dragon(self.qq, s, end=end, no_char=no_char)
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
    async def choose(self, flush=True):
        if not self.active:
            config.logger.dragon << f"【LOG】用户{self.qq}非活跃，无法选择。"
            self.send_char(f"非活跃，无法选择卡牌{句尾}")
            return False
        else:
            if flush:
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
            user_lists.append(Game.me.event_listener[evt])
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
            if StatusNull(s).is_global:
                global_state['global_status'].extend([[0, s]] * count)
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
            if StatusDaily(s).is_global:
                global_state['global_status'].extend([[1, s]] * count)
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
            if ss.is_global:
                global_state['global_status'].append([2, repr(ss)])
                save_global_state()
            self.data.save_status_time()
            return True
    async def remove_status(self, s: str, /, remove_all=True, remover: Optional['User']=None):
        # Event OnStatusRemove
        for eln, n in self.IterAllEventList(UserEvt.OnStatusRemove, Priority.OnStatusRemove):
            dodge, = await eln.OnStatusRemove(n, self, StatusNull(s), remove_all, remover=remover)
            if dodge:
                return False
        else:
            await StatusNull(s).on_remove(remove_all)
            if remove_all:
                self.data.status = ''.join([t for t in self.data.status if t != s])
            else:
                l = list(self.data.status)
                if s in l:
                    l.remove(s)
                self.data.status = ''.join(l)
            self.log << f"移除了{'一层' if not remove_all else ''}永久状态{s}，当前状态为{self.data.status}。"
            for eln, n in self.IterAllEventList(UserEvt.AfterStatusRemove, Priority.AfterStatusRemove):
                await eln.AfterStatusRemove(n, self, StatusNull(s), remove_all)
            self.data._deregister(StatusNull(s), is_all=remove_all)
            if StatusNull(s).is_global:
                if remove_all:
                    while [0, s] in global_state['global_status']:
                        global_state['global_status'].remove([0, s])
                else:
                    if [0, s] in global_state['global_status']:
                        global_state['global_status'].remove([0, s])
                save_global_state()
            return True
    async def remove_daily_status(self, s: str, /, remove_all=True, remover: Optional['User']=None):
        # Event OnStatusRemove
        for eln, n in self.IterAllEventList(UserEvt.OnStatusRemove, Priority.OnStatusRemove):
            dodge, = await eln.OnStatusRemove(n, self, StatusDaily(s), remove_all, remover=remover)
            if dodge:
                return False
        else:
            await StatusDaily(s).on_remove(remove_all)
            if remove_all:
                self.data.daily_status = ''.join([t for t in self.data.daily_status if t != s])
            else:
                l = list(self.data.daily_status)
                if s in l:
                    l.remove(s)
                self.data.daily_status = ''.join(l)
            self.log << f"移除了{'一层' if not remove_all else ''}每日状态{s}，当前状态为{self.data.daily_status}。"
            for eln, n in self.IterAllEventList(UserEvt.AfterStatusRemove, Priority.AfterStatusRemove):
                await eln.AfterStatusRemove(n, self, StatusDaily(s), remove_all)
            self.data._deregister(StatusDaily(s), is_all=remove_all)
            if StatusDaily(s).is_global:
                if remove_all:
                    while [1, s] in global_state['global_status']:
                        global_state['global_status'].remove([1, s])
                else:
                    if [1, s] in global_state['global_status']:
                        global_state['global_status'].remove([1, s])
                save_global_state()
            return True
    async def remove_limited_status(self, s: T_status, /, remover: Optional['User']=None):
        # Event OnStatusRemove
        for eln, n in self.IterAllEventList(UserEvt.OnStatusRemove, Priority.OnStatusRemove):
            dodge, = await eln.OnStatusRemove(n, self, s, False, remover=remover)
            if dodge:
                return False
        else:
            await s.on_remove(False)
            self.data.status_time.remove(s)
            self.log << f"移除了一个限时状态{s}。"
            for eln, n in self.IterAllEventList(UserEvt.AfterStatusRemove, Priority.AfterStatusRemove):
                await eln.AfterStatusRemove(n, self, s, False)
            self.data._deregister_status_time(s, is_all=False)
            if s.is_global and [2, repr(s)] in global_state['global_status']:
                global_state['global_status'].remove([2, repr(s)])
                save_global_state()
            self.data.save_status_time()
            return True
    async def remove_all_limited_status(self, s: str, /, remover: Optional['User']=None):
        l = [c for c in self.data.status_time if c.id == s]
        if len(l) == 0:
            return self.data.status_time
        # Event OnStatusRemove
        for eln, n in self.IterAllEventList(UserEvt.OnStatusRemove, Priority.OnStatusRemove):
            dodge, = await eln.OnStatusRemove(n, self, l[0], True, remover=remover)
            if dodge:
                return False
        else:
            await Status(s).on_remove(True)
            i = 0
            while i < len(self.data.status_time):
                t: T_status = self.data.status_time[i]
                if not t.check() or t.id == s:
                    self.data.status_time.pop(i)
                else:
                    i += 1
            self.log << f"移除了所有限时状态{s}。"
            for c in l:
                for eln, n in self.IterAllEventList(UserEvt.AfterStatusRemove, Priority.AfterStatusRemove):
                    await eln.AfterStatusRemove(n, self, c, True)
            self.data._deregister_status_time(Status(s), is_all=True)
            if Status(s).is_global:
                global_state['global_status'] = [t for t in global_state['global_status'] if t[0] == 2 and t[1].startswith(f"Status('{s}')")]
                save_global_state()
            self.data.save_status_time()
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
            self.send_char(f"收到了{pt}活动pt{句尾}")
        self.log << f"增加了{pt}活动pt。现有{self.data.event_pt}活动pt。"
        return True
    async def add_jibi(self, jibi: int, /, is_buy: bool=False) -> bool:
        if jibi == 0:
            return True
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
        self.log << f"增加击毙{jibi}，现有击毙{max(self.data.jibi + jibi, 0)}。"
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
        # Event OnAttack
        for eln, n in attacker.IterAllEventList(UserEvt.OnAttack, Priority.OnAttack):
            dodge, = await eln.OnAttack(n, attacker, attack)
            if dodge:
                return
        # Event OnAttacked
        for eln, n in attack.defender.IterAllEventList(UserEvt.OnAttacked, Priority.OnAttacked):
            dodge, = await eln.OnAttacked(n, attack.defender, attack)
            if dodge:
                return
        await attack.action()
    async def killed(self, killer: 'User', hour: int=2, minute: int=0):
        """击杀玩家。"""
        config.logger.dragon << f"【LOG】{killer.qq}尝试击杀玩家{self.qq}。"
        time_num = 60 * hour + minute
        attack = Kill(killer, self, time_num)
        await self.attacked(killer, attack)
    async def death(self, minute: int=120, killer=None, c: TAttackType=None):
        """玩家死亡。"""
        config.logger.dragon << f"【LOG】玩家{self.qq}死亡。"
        dodge = False
        if c is None:
            c = TAttackType()
        # Event OnDeath
        for eln, n in self.IterAllEventList(UserEvt.OnDeath, Priority.OnDeath):
            minute, dodge = await eln.OnDeath(n, self, killer, minute, c)
            minute = int(minute)
            if dodge:
                break
        else:
            self.send_char(f"死了{句尾}{minute}分钟不得接龙。")
            await self.add_limited_status(SDeath(datetime.now() + timedelta(minutes=minute)))
    async def draw(self, n0: int, /, positive=None, cards: List[TCard]=None, extra_lambda=None, replace_prompt=None):
        """抽卡。将卡牌放入手牌。"""
        if self.active and self.buf.state.get('exceed_limit'):
            self.send_log(f"因手牌超出上限，不可摸牌{句尾}")
            return False
        if cards is None:
            # Event BeforeCardDraw
            for el, n in self.IterAllEventList(UserEvt.BeforeCardDraw, Priority.BeforeCardDraw):
                ret, = await el.BeforeCardDraw(n, self, n0, positive, extra_lambda)
                if ret is not None:
                    cards = ret
                    break
            else:
                cards = draw_cards(self, positive, n0, extra_lambda=extra_lambda)
        elif Card(-65537) in cards:
            if self.qq in global_state["supernova_user"][0] + global_state["supernova_user"][1] + global_state["supernova_user"][2]:
                cards.remove(Card(-65537))
                if len(cards) == 0:
                    return False
            else:
                global_state["supernova_user"][0].append(self.qq)
        self.log << f"抽到的卡牌为{cards_to_str(cards)}。"
        if replace_prompt is not None:
            self.buf.send(replace_prompt)
        else:
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
        return True
    async def draw_and_use(self, /, positive=None, card: TCard=None, extra_lambda=None):
        """抽取卡牌，立即使用，并发动卡牌的销毁效果。不经过手牌。"""
        if card is None:
            # Event BeforeCardDraw
            for el, n in self.IterAllEventList(UserEvt.BeforeCardDraw, Priority.BeforeCardDraw):
                ret, = await el.BeforeCardDraw(n, self, 1, positive, extra_lambda)
                if ret is not None:
                    cards = ret
                    break
            else:
                cards = draw_cards(self, positive, 1, extra_lambda=extra_lambda)
        else:
            cards = [card]
        for c in cards:
            if c.des_need_init:
                await self.draw_card_effect(c)
            self.log << f"抽取并使用了卡牌{c.name}。"
            self.send_char('抽到并使用了卡牌：\n' + c.full_description(self.qq))
        for c in cards:
            if not c.des_need_init:
                await self.draw_card_effect(c)
            await self.use_card_effect(c)
            if c.id not in global_state['used_cards']:
                global_state['used_cards'].append(c.id)
                save_global_state()
            await c.on_remove(self)
    async def draw_card_effect(self, card: TCard):
        """抽卡时的结算。"""
        if card.consumed_on_draw:
            # Event BeforeCardUse
            for el, n in self.IterAllEventList(UserEvt.BeforeCardUse, Priority.BeforeCardUse):
                block, = await el.BeforeCardUse(n, self, card)
                if block is not None:
                    self.log << f"卡牌使用被阻挡{句尾}"
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
                    self.log << f"卡牌使用被阻挡{句尾}"
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
        self.data.set_cards()
        self.log << f"使用完卡牌，当前手牌为{cards_to_str(self.data.hand_card)}。"
    async def use_equipment(self, eq: TEquipment, count: int):
        """使用装备。"""
        self.send_char('使用了装备：\n' + eq.description(count))
        self.log << f"使用了装备{eq.name}，等级为{count}。"
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
    async def exchange(self, target: 'User', max_sub=65536):
        """交换两人手牌。"""
        if self == target:
            return
        config.logger.dragon << f"【LOG】交换用户{self.qq}与用户{target.qq}的手牌。{self.qq}手牌为{cards_to_str(self.data.hand_card)}，{target.qq}手牌为{cards_to_str(target.data.hand_card)}。"
        if len(target.data.hand_card) - len(self.data.hand_card) > max_sub:
            random.shuffle(target.data.hand_card)
            target_hand_cards = target.data.hand_card[:len(self.data.hand_card) + max_sub]
            target.data.hand_card = target.data.hand_card[len(self.data.hand_card) + max_sub:]
            self_hand_cards = self.data.hand_card
            self.data.hand_card = []
        elif len(self.data.hand_card) - len(target.data.hand_card) > max_sub:
            random.shuffle(self.data.hand_card)
            self_hand_cards = self.data.hand_card[:len(target.data.hand_card) + max_sub]
            self.data.hand_card = self.data.hand_card[len(target.data.hand_card) + max_sub:]
            target_hand_cards = target.data.hand_card
            target.data.hand_card = []
        else:
            target_hand_cards = target.data.hand_card
            target.data.hand_card = []
            self_hand_cards = self.data.hand_card
            self.data.hand_card = []
        for card in self_hand_cards:
            await card.on_give(self, target)
        for card in target_hand_cards:
            await card.on_give(target, self)
        self.data.hand_card.extend(target_hand_cards)
        target.data.hand_card.extend(self_hand_cards)
        self.data.set_cards()
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
        if not await self.choose(flush=False):
            yield
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
                async with self.choose_cards(f"您的手牌已超出上限{x}张{句尾}请先选择一些牌弃置（输入id号，使用空格分隔）：", 1, x,
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
            self.send_log(f"经过了{e * 50}层，获得了{pt}pt{句尾}")
            await self.add_event_pt(pt)
        t = (current.stage, self.qq)
        u = self
        while 1:
            l = config.userdata.execute("select qq from dragon_data where event_stage=? and qq<>?", t).fetchone()
            if l is None:
                break
            u.send_log(f"将玩家{l['qq']}踢回了一格{句尾}")
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
        try:
            if await self.choose():
                prompt = attempt + "\n" + "\n".join(c.brief_description() for c in self.data.hand_card)
                ca = lambda l: len(list(c for c in self.data.hand_card if c.id not in cards_can_not_choose_fin)) < min
                arg_filters = [extractors.extract_text,
                        check_handcard(self),
                        lambda s: list(map(int, re.findall(r'\-?\d+', str(s)))),
                        check_if_unable(ca, self.buf.session),
                        validators.fit_size(min, max, message="请输入正确的张数。"),
                        validators.ensure_true(
                            lambda l: all(i in _card.card_id_dict for i in l) and
                            len(list((Counter(l) - Counter([c.id for c in self.data.hand_card])).elements())) == 0,
                            message=f"您选择了错误的卡牌{句尾}")]
                if require_can_use:
                    arg_filters.append(ensure_true_lambda(
                        lambda l: Card(l[0]).can_use(self, True),
                        message_lambda=lambda l: Card(l[0]).failure_message))
                    cards_can_not_choose_fin = cards_can_not_choose_org | \
                        set(c.id for c in self.data.hand_card if not c.can_use(self, True))
                if len(cards_can_not_choose_fin) != 0:
                    arg_filters.append(validators.ensure_true(
                        lambda l: len(set(l) & cards_can_not_choose_fin) == 0,
                        message=f"此卡牌不可选择{句尾}"))
                try:
                    if ca(None):
                        raise UnableRequirement
                    ret = await self.buf.aget(prompt=prompt, arg_filters=arg_filters)
                    self.log << f"选择了{ret}。"
                    yield ret
                except UnableRequirement:
                    self.send_log(f"手牌无法选择，选择进程中止{句尾}")
                    yield None
                finally:
                    self.data.set_cards()
                    self.data.save_status_time()
                    save_data()
            else:
                yield None
        except NotActive:
            pass
    async def damaged(self, damage: int, attacker=None, must_hit=False):
        if attacker is None:
            attacker = dragon(self)
        atk = Damage(attacker, self, damage, must_hit=must_hit)
        await self.attacked(attacker, atk)
    async def use_object(self, args: str):
        if args == "满贯抽奖券":
            if self.data.extra.mangan < 2:
                self.buf.send(f"你的满贯抽奖券不足{句尾}")
                return
            self.data.extra.mangan -= 2
            a = random.random()
            if a < 0.02 and self.data.check_equipment(5) == 0:
                self.send_log(f"获得了赌神魔戒{句尾}")
                self.data.equipment[5] = 1
                self.data.save_equipment()
            elif a < 0.32:
                self.send_log(f"获得了4张卡{句尾}")
                await self.draw(4)
            elif a < 0.67:
                self.send_log(f"获得了3张卡{句尾}")
                await self.draw(3)
            else:
                self.send_log(f"获得了2张正面卡{句尾}")
                await self.draw(2, positive={1})
        elif args == "役满抽奖券":
            if self.data.extra.yakuman < 1:
                self.buf.send("你的役满抽奖券不足！")
                return
            self.data.extra.yakuman -= 1
            a = random.random()
            if a < 0.05 and self.data.check_equipment(5) == 0:
                self.send_log(f"获得了赌神魔戒{句尾}")
                self.data.equipment[5] = 1
                self.data.save_equipment()
            elif a < 0.2:
                self.send_log(f"获得了6张卡{句尾}")
                await self.draw(6)
            elif a < 0.45:
                self.send_log(f"获得了4张卡{句尾}")
                await self.draw(4)
            elif a < 0.65:
                self.send_log(f"获得了5张卡{句尾}")
                await self.draw(5)
            else:
                self.send_log(f"获得了3张正面卡{句尾}")
                await self.draw(3, positive={1})
            b = random.random()
            if b < 0.02 and self.data.check_equipment(5) == 0:
                self.send_log(f"获得了赌神魔戒{句尾}")
                self.data.equipment[5] = 1
                self.data.save_equipment()
            elif b < 0.12:
                self.send_log(f"获得了1张满贯抽奖券{句尾}")
                self.data.extra.mangan += 2
            c = random.random()
            if c < 0.01 and self.data.check_equipment(5) == 0:
                self.send_log(f"获得了赌神魔戒{句尾}")
                self.data.equipment[5] = 1
                self.data.save_equipment()
            elif c < 0.21:
                await self.draw(0, cards=[shengkong], replace_prompt=self.char + "获得了1张卡牌：")
        elif args == "麻将摸牌券":
            if self.data.extra.maj_quan < 3:
                self.buf.send("你的麻将摸牌券不足！")
                return
            self.data.extra.maj_quan -= 3
            await self.draw_maj()
        else:
            self.buf.send("此物品不可使用。")
    async def draw_maj(self, to_draw=None):
        if not await self.choose(flush=False):
            return
        hand_maj = [MajOneHai(s) for s in self.data.maj[0]] # assume sorted
        if to_draw is None:
            to_draw = MajOneHai(MajOneHai.get_random())
            if self.data.check_equipment(5) and random.random() < 0.2:
                to_draw2 = MajOneHai(MajOneHai.get_random())
                def check2(value: str):
                    try:
                        maj = MajOneHai(value.strip())
                        if maj != to_draw and maj != to_draw2:
                            _raise_failure("请选择一个可执行的操作。")
                        return maj
                    except MajIdError:
                        _raise_failure("请输入正确的麻将牌。")
                self.buf.send(f"你幸运地摸到了{str(to_draw)}和{str(to_draw2)}，请选择一张：\n{await MajOneHai.draw_maj(hand_maj, self.data.maj[1], to_draw)}\n{await MajOneHai.draw_maj(hand_maj, self.data.maj[1], to_draw2)}")
                await self.buf.flush()
                to_draw = await self.buf.aget(prompt="", arg_filters=[
                    extractors.extract_text,
                    check_handcard(self),
                    check2
                ])
        self.log << f"摸到了{str(to_draw)}"
        t = MajOneHai.ten(hand_maj)
        huchu = to_draw.hai in t
        richi = []
        if not self.data.if_richi:
            for i in range(len(hand_maj)):
                if huchu or len(MajOneHai.ten(hand_maj[:i] + hand_maj[i+1:] + [to_draw])) != 0:
                    if len(richi) == 0 or richi[-1] != hand_maj[i]:
                        richi.append(hand_maj[i])
            if len(t) != 0:
                richi.append(to_draw)
            richi.sort()
            richi = list(more_itertools.unique_justseen(richi, lambda s: s.hai))
        c = Counter(h.hai for h in hand_maj + [to_draw])
        ankan = [MajOneHai(i) for i, d in c.items() if d >= 4]
        if self.data.if_richi:
            if to_draw not in ankan:
                ankan = []
            else:
                m = copy(hand_maj)
                for i in range(3):
                    m.remove(to_draw)
                if MajOneHai.ten(m).keys() == t.keys():
                    ankan = [to_draw]
        choose = -1 # 0: 切牌 1: 立直 2: 暗杠 3: 和出
        names = ["切牌", "立直", "暗杠", "和出"]
        if self.data.if_richi:
            can_choose = [[to_draw], richi, ankan, huchu]
        else:
            can_choose = [hand_maj + [to_draw], richi, ankan, huchu]
        to_choose = None
        self.send_char(f"摸到了{str(to_draw)}{句尾}{self.char}现在的牌是：\n{await MajOneHai.draw_maj(hand_maj, self.data.maj[1], to_draw)}")
        prompt = ""
        if len(richi) == 0 and len(ankan) == 0 and not huchu:
            choose = 0
        elif self.data.if_richi and not huchu and len(ankan) == 0:
            choose = 0
            to_choose = to_draw
        else:
            if self.data.if_richi:
                prompt = f"请选择切摸到的牌，或是："
            else:
                prompt = f"请选择一张牌切牌，或是："
            for i in range(1, 3):
                if len(can_choose[i]) != 0:
                    prompt += f"\n{names[i]}：" + ' '.join(str(s) for s in can_choose[i])
            if huchu:
                prompt += "\n和出"
            async def check(value: str):
                if value == "重新询问":
                    _raise_failure(f"{self.char}摸到了{str(to_draw)}{句尾}{self.char}现在的牌是：\n{await MajOneHai.draw_maj(hand_maj, self.data.maj[1], to_draw)}")
                try:
                    for i in range(3):
                        if value.startswith(names[i]) and len(can_choose[i]) != 0:
                            if value == names[i]:
                                return (i, None)
                            maj = MajOneHai(value[2:].strip())
                            if maj not in can_choose[i]:
                                _raise_failure(["请选择手牌中的一张牌切出。", "请选择可立直的牌。", "请选择可暗杠的牌。"][i])
                            return (i, maj)
                    if value.strip() == "和出":
                        return (3, True)
                    _raise_failure("请选择一个可执行的操作，输入重新询问再发送一次。")
                except MajIdError:
                    _raise_failure("请输入正确的麻将牌，输入重新询问再发送一次。")
            self.buf.send(prompt)
            await self.buf.flush()
            choose, to_choose = await self.buf.aget(prompt="", arg_filters=[
                extractors.extract_text,
                check_handcard(self),
                check
            ])
        if to_choose is None:
            if len(can_choose[choose]) == 1:
                to_choose = can_choose[choose][0]
            else:
                if choose == 0:
                    prompt += "请选择一张牌切牌。"
                else:
                    prompt += f"请选择一张牌{names[choose]}：" + ' '.join(str(s) for s in can_choose[choose])
                async def check3(value: str):
                    if value == "重新询问":
                        _raise_failure(f"{self.char}摸到了{str(to_draw)}{句尾}{self.char}现在的牌是：\n{await MajOneHai.draw_maj(hand_maj, self.data.maj[1], to_draw)}")
                    try:
                        i = choose
                        maj = MajOneHai(value.strip())
                        if maj not in can_choose[i]:
                            _raise_failure(["请选择手牌中的一张牌切出。", "请选择可立直的牌。", "请选择可暗杠的牌。"][i])
                        return maj
                    except MajIdError:
                        _raise_failure("请输入正确的麻将牌，输入重新询问再发送一次。")
                self.buf.send(prompt)
                await self.buf.flush()
                to_choose = await self.buf.aget(prompt="", arg_filters=[
                    extractors.extract_text,
                    check_handcard(self),
                    check3
                ])
        # do things
        if choose == 3:
            self.send_log(f"和了{句尾}")
            if self.data.if_richi:
                ura = [MajOneHai(MajOneHai.get_random()) for i in range(len(self.data.maj[1]) + 1)]
                self.buf.send("里宝指示牌是：" + ''.join(str(c) for c in ura))
                config.logger.dragon << "【LOG】里宝牌是：" + ''.join(str(c) for c in ura)
                if self.data.check_equipment(5):
                    for i in range(len(ura)):
                        dora1 = ura[i].addOneDora()
                        if dora1 not in hand_maj and dora1.hai not in self.data.maj[1] and dora1 != to_draw and random.random() < 0.5:
                            dora2 = MajOneHai(MajOneHai.get_random())
                            self.buf.send(f"指示牌{str(ura[i])}没有抽中，重抽出了{str(dora2)}{句尾}")
                            config.logger.dragon << f"指示牌{str(ura[i])}没有抽中，重抽出了{str(dora2)}{句尾}"
                            ura[i] = dora2
            else:
                ura = []
            
            l, ten = MajOneHai.tensu(t[to_draw.hai], self.data.maj[1], to_draw.hai, self.data.if_richi, ura,
                not self.data.not_first_round, "rinshan" in self.buf.state and self.buf.state["rinshan"])
            self.log << f"和种为{[str(c) for c in l]}，点数为{ten}。"
            if ten <= 3:    r = "";             jibi = 5;       quan = 0
            elif ten <= 5:  r = "，满贯";        jibi = 10;     quan = 2
            elif ten <= 7:  r = "，跳满";        jibi = 15;     quan = 3
            elif ten <= 10: r = "，倍满";        jibi = 20;     quan = 4
            elif ten <= 12: r = "，三倍满";      jibi = 30;     quan = 6
            elif ten // 13 == 1: r = "，役满";     jibi = 40
            else:  r = '，' + str(ten // 13) + "倍役满"; jibi = 40
            if self.data.if_richi:
                fan = [f"{str(s)} {s.int()}番" for s in l if s.tuple < (0, 2, 0)]
                fan.append(f"{str(MajOneHai.HeZhong((0, 2, 0)))} {l.count(MajOneHai.HeZhong((0, 2, 0)))}番")
                fan += [f"{str(s)} {s.int()}番" for s in l if s.tuple > (0, 2, 0)]
            else:
                fan = [f"{str(s)} {s.int()}番" for s in l]
            self.buf.send('\n'.join(fan) + f"\n合计：{ten}番{r}{句尾}")
            self.buf.send(f"奖励{self.char}{jibi}击毙", end="")
            if ten <= 3:
                self.buf.send(f"以及被击毙{句尾}")
                await self.add_jibi(jibi)
                await self.death()
            elif ten <= 12:
                if quan % 2 == 0:
                    self.buf.send(f"以及{quan // 2}张满贯抽奖券{句尾}")
                else:
                    self.buf.send(f"以及{quan / 2}张满贯抽奖券{句尾}")
                await self.add_jibi(jibi)
                self.data.extra.mangan += quan
            else:
                self.buf.send(f"以及{ten // 13}张役满抽奖券{句尾}")
                await self.add_jibi(jibi)
                self.data.extra.yakuman += ten // 13
            if 10 < ten <= 12:
                await self.draw(0, cards=[shengkong], replace_prompt="以及一张卡：")
            self.data.maj = (sorted(MajOneHai.get_random() for i in range(13)), [])
            self.data.if_richi = False
            self.data.not_first_round = False
            self.data.save_maj()
            return
        hand_maj.append(to_draw)
        hand_maj.remove(to_choose)
        hand_maj.sort()
        if choose == 0:
            self.send_log(f"切出了{str(to_choose)}，手中麻将为：")
        elif choose == 1:
            self.send_log(f"切出了{str(to_choose)}{'' if self.data.not_first_round else '两'}立直，手中麻将为：")
            self.data.if_richi = True
        elif choose == 2:
            hand_maj.remove(to_choose)
            hand_maj.remove(to_choose)
            hand_maj.remove(to_choose)
            self.data.maj[1].append(to_choose.hai)
            self.buf.state["rinshan"] = True
            self.send_log(f"暗杠了{str(to_choose)}{句尾}，手中麻将为：")
        self.buf.send(await MajOneHai.draw_maj(hand_maj, self.data.maj[1]))
        self.log << ''.join(str(h) for h in hand_maj) + ' ' + ''.join(str(h) for h in self.data.maj[1])
        self.data.maj = ([s.hai for s in hand_maj], self.data.maj[1])
        self.data.save_maj()
        if not self.data.if_richi:
            self.data.not_first_round = True
        if choose == 2:
            await self.draw_maj()
    async def dragon_event(self, slot: int, branch: Tree):
        """slot: 0 for normal, 1~4 for slot A to D."""
        if slot == 0:
            skill = 0
        else:
            skill = self.data.dragon_event_skill[slot - 1]
            if skill != 0:
                skill += [0, 4, 0, 8][slot - 1]
        mp_usage = [0, 100, 0, 100, 100, 200, 0, 200, 200, 400, 0, 400, 400][skill]
        all_qq = [c["qq"] for c in config.userdata.execute("select qq from dragon_data where dead=false").fetchall()]
        if self.data.mp < mp_usage:
            self.send_log("当前MP不足，无法释放技能" + 句尾)
            skill = 0
        # 平a/技能内容
        dr = dragon(self)
        dragon_skill = draw_skill(dr)
        if skill == 0:
            self.send_log("对龙进行了一次普通攻击" + 句尾)
            await dr.damaged(100 + self.data.dragon_level * 2)
        elif skill == 1:
            # 消耗100MP，回复所有玩家250点HP。
            self.data.mp -= 100
            self.send_log(f"消耗了100点MP，当前MP为{self.data.mp}{句尾}")
            self.send_log("回复了所有玩家250点HP" + 句尾)
            for qq in all_qq:
                ud = Game.userdata(qq)
                ud.hp = min(ud.hp + 250, ud.hp_max)
        elif skill == 2:
            # 回复所有玩家250点MP。
            self.send_log("回复了所有玩家250点MP" + 句尾)
            for qq in all_qq:
                ud = Game.userdata(qq)
                ud.mp = min(ud.mp + 250, ud.mp_max)
        elif skill == 3:
            # 消耗100MP，为所有人增加持续一次的必中并且攻击增加50%的buff。
            self.data.mp -= 100
            self.send_log(f"消耗了100点MP，当前MP为{self.data.mp}{句尾}")
            self.send_log("为所有人增加了buff必中" + 句尾)
            for qq in all_qq:
                await User(qq, self.buf).add_status('c')
        elif skill == 4:
            # 消耗100MP，选择一名已死亡的玩家，将其复活，或选择一名未死亡的玩家，将其HP与MP恢复满。
            if await self.choose(flush=False):
                config.logger.dragon << f"【LOG】询问用户{self.qq}选择玩家。"
                qq: int = (await self.buf.aget(prompt="请at群内一名玩家。\n",
                    arg_filters=[
                            lambda s: [int(r) for r in re.findall(r'qq=(\d+)', str(s))],
                            validators.fit_size(1, 1, message="请at正确的人数。")
                        ]))[0]
                u = User(qq, self.buf)
                if u.check_limited_status('d'):
                    self.send_log("复活了该玩家" + 句尾)
                    await u.remove_all_limited_status('d')
                else:
                    self.send_log("将该玩家的HP与MP恢复满了" + 句尾)
                    u.data.hp = u.data.hp_max
                    u.data.mp = u.data.mp_max
        elif skill == 5:
            # 消耗200MP，回复所有玩家500点HP。
            self.data.mp -= 200
            self.send_log(f"消耗了200点MP，当前MP为{self.data.mp}{句尾}")
            self.send_log("回复了所有玩家500点HP" + 句尾)
            for qq in all_qq:
                ud = Game.userdata(qq)
                ud.hp = min(ud.hp + 500, ud.hp_max)
        elif skill == 6:
            # 回复所有玩家500点MP。
            self.send_log("回复了所有玩家500点MP" + 句尾)
            for qq in all_qq:
                ud = Game.userdata(qq)
                ud.mp = min(ud.mp + 500, ud.mp_max)
        elif skill == 7:
            # 消耗200MP，为所有人增加持续一次的闪避buff。
            self.data.mp -= 200
            self.send_log(f"消耗了200点MP，当前MP为{self.data.mp}{句尾}")
            self.send_log("为所有人增加了buff闪避" + 句尾)
            for qq in all_qq:
                await User(qq, self.buf).add_status('f')
        elif skill == 8:
            # 消耗200MP，给龙增加混乱debuff：下次技能选择玩家时随机选择。
            self.data.mp -= 200
            self.send_log(f"消耗了200点MP，当前MP为{self.data.mp}{句尾}")
            self.send_log("为龙增加了debuff混乱" + 句尾)
            await dr.add_status('X')
        elif skill == 9:
            # 消耗400MP，给所有玩家增加buff复活光环：下次因HP归零死亡的复活时间减少至5分钟。
            self.data.mp -= 400
            self.send_log(f"消耗了400点MP，当前MP为{self.data.mp}{句尾}")
            self.send_log("为所有人增加了buff复活光环" + 句尾)
            for qq in all_qq:
                await User(qq, self.buf).add_status('u')
        elif skill == 10:
            # 给所有玩家增加buff魔法汲取：接下来5次平a每次回复150点MP。
            self.send_log("为所有人增加了buff魔法汲取" + 句尾)
            for qq in all_qq:
                if l := (u := User(qq, self.buf)).check_limited_status('w'):
                    l[0].num += 5
                    u.data.save_status_time()
                else:
                    await u.add_limited_status(Smofajiqu(5))
        elif skill == 11:
            # 消耗400MP，为所有人附加buff强身健体：接下来5次受到伤害减半。
            self.data.mp -= 400
            self.send_log(f"消耗了400点MP，当前MP为{self.data.mp}{句尾}")
            self.send_log("为所有人增加了buff强身健体" + 句尾)
            for qq in all_qq:
                if l := (u := User(qq, self.buf)).check_limited_status('q'):
                    l[0].num += 5
                    u.data.save_status_time()
                else:
                    await u.add_limited_status(Sqiangshenjianti(5))
        elif skill == 12:
            # 消耗400MP，若龙使用的是9号或以上的技能，则防止此次技能使用，否则对龙造成200点伤害。
            self.data.mp -= 400
            self.send_log(f"消耗了400点MP，当前MP为{self.data.mp}{句尾}")
            if dragon_skill.id >= 9:
                self.send_log("防止了龙的技能使用" + 句尾)
                dragon_skill = GetSkill(0)
            else:
                await dr.damaged(200 + self.data.dragon_level * 4)
        dr.send_log(f"使用了技能：{dragon_skill.full_description()}")
        await dragon_skill.use(self, branch)

Userme: Callable[[User], User] = lambda user: User(config.selfqq, user.buf)

def save_data():
    config.userdata_db.commit()

up_newer = -1
def cards_to_str(cards: List[TCard]):
    return '，'.join(c.brief_description() for c in cards)
def draw_cards(user: User, positive: Optional[Set[int]]=None, k: int=1, extra_lambda=None):
    x = positive is not None and len(positive & {-1, 0, 1}) != 0
    cards = [c for c in _card.card_id_dict.values() if c.id >= 0 and (not x or x and c.positive in positive)]
    if extra_lambda is not None:
        cards = [c for c in cards if extra_lambda(c)]
    packs = Sign(global_state["sign"]).pack()
    weight = [(c.weight(user) if callable(c.weight) else c.weight) + (4 if c.pack in packs else 0) + (1.5 if c.newer == up_newer else 0) for c in cards]
    if Game.me.check_daily_status('j') and (not x or x and (-1 in positive)):
        l = [(Card(-1) if random.random() < 0.2 else random.choices(cards, weight)[0]) for i in range(k)]
    else:
        l = random.choices(cards, weight, k=k)
    if user.data.luck != 0:
        for i in range(len(l)):
            if callable(l[i].weight) and random.random() > 1 / l[i].weight(user):
                user.send_log("幸运地抽到了" + l[i].name + 句尾)
            elif l[i] is dabingyichang and random.random() < 0.1 * min(user.data.luck, 5):
                user.send_log("抽到了大病一场，幸运重抽" + 句尾)
                l[i] = random.choices(cards, weight, k=1)[0]
            elif l[i] is jiandiezhixing and random.random() < 0.1 * min(user.data.luck, 5):
                user.send_log("抽到了间谍执行，幸运重抽" + 句尾)
                l[i] = random.choices(cards, weight, k=1)[0]
    return l
def draw_card(user: User, positive: Optional[Set[int]]=None):
    return draw_cards(user, positive, k=1)[0]
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

name_f = lambda s: s if '：' not in s else s[:s.index('：')]
brief_f = lambda s: (s if '：' not in s else s[:s.index('：')] + s[s.index('\n\t'):] if '\n\t' in s else s[:s.index('：')])
class _statusall(IEventListener, metaclass=status_meta):
    id = ""
    des = ""
    is_debuff = False
    is_global = False
    is_metallic = False
    removeable = True
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
    async def BeforeDragoned(cls, count: TCount, user: 'User', state: DragonState) -> Tuple[bool, int, str]:
        return False, 0, f'你已死，不能接龙{句尾}'
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

class SNoDragon(ListStatus):
    """only implemented length 1 and 3."""
    id = 'n'
    des = "不可接龙：无法从以下节点接龙。"
    is_debuff = True
    def __init__(self, s: Union[str, list], length: int=1):
        self.length = int(length)
        super().__init__(s)
    def __repr__(self) -> str:
        return self.construct_repr(str(self.list), str(self.length))
    def check(self) -> bool:
        return True
    def __str__(self) -> str:
        ids = [tree.id_str for tree in Tree.get_active()]
        if self.length == 1:
            return f"{self.des}\n\t{','.join(c for c in self.list if c in ids)}"
        if self.length == 3:
            this = [Tree.find(Tree.str_to_id(c)) for c in self.list if c in ids]
            this2 = list(itertools.chain(*[c.childs for c in this]))
            this3 = list(itertools.chain(*[c.childs for c in this2]))
            return f"{self.des}\n\t{','.join(c.id_str for c in this + this2 + this3 if c.id_str in ids)}"
    def check_node(self, node: 'Tree'):
        if self.length == 1:
            if node.id_str in self.list:
                return False
        elif self.length == 3:
            if node.id_str in self.list or Tree.before(node, 1).id_str in self.list or Tree.before(node, 2).id_str in self.list:
                return False
        return True
    @classmethod
    async def BeforeDragoned(cls, count: TCount, user: 'User', state: DragonState) -> Tuple[bool, int, str]:
        for c in count:
            if not c.check_node(state.parent):
                return False, 0, "你不能从此节点接龙" + 句尾
        return True, 0, ""
    @classmethod
    async def OnNewDay(cls, count: TCount, user: 'User') -> Tuple[()]:
        await user.remove_all_limited_status('n')
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.BeforeDragoned: (Priority.BeforeDragoned.nodragon, cls),
            UserEvt.OnNewDay: (Priority.OnNewDay.nodragon, cls)}
newday_check[2].add('n')

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
    is_metallic = False
    mass = 0.1
    pack = Pack.misc
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
    def brief_description(cls):
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
    mass = 10000
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
    failure_message = "此牌不可被使用" + 句尾
    pack = Pack.orange_juice
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
    mass = 0.5
    pack = Pack.toaru
    @classmethod
    async def use(cls, user: User) -> None:
        await user.add_limited_status(SInvincible(datetime.now() + timedelta(hours=2)))
class SInvincible(TimedStatus):
    id = 'v'
    des = '无敌：免疫死亡。'
    @classmethod
    async def OnDeath(cls, count: TCount, user: 'User', killer: 'User', time: int, c: TAttackType) -> Tuple[int, bool]:
        if await c.pierce():
            user.send_log(f"无敌的效果被幻想杀手消除了{句尾}")
            await user.remove_all_limited_status('v', remover=killer)
        else:
            user.send_log(f"触发了无敌的效果，免除死亡{句尾}")
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
    pack = Pack.tarot
class fool_s(_statusnull):
    id = 'O'
    des = "0 - 愚者：你下次使用卡牌无效。"
    is_debuff = True
    @classmethod
    async def BeforeCardUse(cls, count: TCount, user: 'User', card: TCard) -> Tuple[Optional[Awaitable]]:
        async def f():
            user.send_log(f"你太笨了{句尾}这张卡的使用无效{句尾}")
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
    pack = Pack.tarot
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
                return False, f"你太疲劳了，不能使用{card.name}{句尾}"
        return True, ""
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnUserUseCard: (Priority.OnUserUseCard.cantuse, cls)}

class high_priestess(_card):
    name = "II - 女祭司"
    id = 2
    positive = 0
    description = "击毙当前周期内接龙次数最多的玩家。"
    pack = Pack.tarot
    @classmethod
    async def use(cls, user: User):
        counter = Counter([tree.qq for tree in itertools.chain(*itertools.chain(Tree._objs, *Tree.forests))])
        l = counter.most_common()
        ql = [qq for qq, time in l if time == l[0][1]]
        if len(ql) == 1:
            user.buf.send(f"当前周期内接龙次数最多的玩家是[CQ:at,qq={ql[0]}]{句尾}")
        else:
            user.buf.send(f"当前周期内接龙次数最多的玩家有{''.join(f'[CQ:at,qq={q}]' for q in ql)}{句尾}")
        for q in ql:
            await User(q, user.buf).killed(user)

class empress(_card):
    name = "III - 女皇"
    id = 3
    description = "你当前手牌中所有任务之石的可完成次数+3。如果当前手牌无任务之石，则为你派发一个可完成3次的任务，每次完成获得3击毙，跨日时消失。"
    positive = 1
    pack = Pack.tarot
    @classmethod
    async def use(cls, user: User) -> None:
        if Card(67) in user.data.hand_card:
            for q in global_state['quest'][str(user.qq)]:
                q["remain"] += 3
            user.send_char(f"的任务剩余次数增加了3{句尾}")
        else:
            await user.add_limited_status(SQuest(3, 3, n := get_mission()))
            user.send_char(f"获得了一个任务：{mission[n][1]}")

class emperor(_card):
    name = "IV - 皇帝"
    id = 4
    positive = 1
    description = "为你派发一个随机任务，可完成10次，每次完成获得2击毙，跨日时消失。"
    pack = Pack.tarot
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
                user.send_char(f"完成了每日任务：{name[:-1]}{句尾}奖励{q.jibi}击毙。此任务还可完成{q.num - 1}次。")
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
newday_check[2].add('q')

class hierophant(_card):
    name = "V - 教皇"
    id = 5
    positive = 1
    description = "你的下10次接龙中每次额外获得2击毙，但额外要求首尾接龙。"
    limited_status = 'f'
    limited_init = (10,)
    newer = 3
    pack = Pack.tarot
class hierophant_s(NumedStatus):
    id = 'f'
    des = "V - 教皇：你的下10次接龙中每次额外获得2击毙，但额外要求首尾接龙。"
    @classmethod
    async def BeforeDragoned(cls, count: TCount, user: User, state: DragonState) -> Tuple[bool, int, str]:
        if not await state.require_shouwei(user):
            return False, 0, "教皇说，你需要首尾接龙，接龙失败。"
        return True, 0, ""
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        user.send_log(f"收到了教皇奖励你的2击毙{句尾}")
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
    async def BeforeDragoned(cls, count: TCount, user: User, state: DragonState) -> Tuple[bool, int, str]:
        if not await state.require_weishou(user):
            return False, 0, "教皇说，你需要尾首接龙，接龙失败。"
        return True, 0, ""
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        user.send_log(f"被教皇扣除了2击毙{句尾}")
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
    pack = Pack.tarot
    @classmethod
    async def use(cls, user: User):
        if await user.choose():
            l = await user.buf.aget(prompt="请at一名玩家复活。\n",
                arg_filters=[
                        lambda s: [int(q) for q in re.findall(r'qq=(\d+)', str(s))],
                        validators.fit_size(1, 1, message="请at正确的人数。"),
                    ])
            u = User(l[0], user.buf)
            n = len(u.check_limited_status('d')) == 0
            await u.remove_all_limited_status('d', remover=user)
            user.buf.send(f"已复活{句尾}" + ("（虽然目标并没有死亡）" if n else ''))

class chariot(_card):
    id = 7
    name = "VII - 战车"
    positive = 1
    newer = 5
    description = "对你今天第一次和最后一次接龙中间接龙的人（除了你自己）每人做一次10%致死的击毙判定。"
    pack = Pack.tarot
    @classmethod
    async def use(cls, user: User) -> None:
        to_kill = set()
        for l in Tree._objs:
            node = l[-1]
            temp: List[Tree] = []
            while node.id[0] != 0:
                if node.qq == user.qq:
                    if len(temp) != 0:
                        to_kill |= set(n.qq for n in temp)
                    temp = [node]
                elif len(temp) != 0:
                    temp.append(node)
                node = node.parent
        if user.qq in to_kill:
            to_kill.remove(user.qq)
        to_kill = set(qq for qq in to_kill if random.random() < (0.1 + 0.01 * user.data.luck))
        user.buf.send(f"{'，'.join(f'[CQ:at,qq={qq}]' for qq in to_kill)}被你击杀了{句尾}" if len(to_kill) > 0 else f'但没有车到任何人{句尾}')
        for qq in to_kill:
            await User(qq, user.buf).killed(user)

class strength(_card):
    name = "VIII - 力量"
    id = 8
    positive = 0
    description = "加倍你身上所有的非持有性状态，消耗2^n-1击毙，n为状态个数。击毙不足则无法使用。"
    failure_message = "你的击毙不足" + 句尾
    pack = Pack.tarot
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
            user.send_char(f"太弱小了，没有力量{句尾}")
            return
        else:
            user.send_char(f"花费了{2 ** l - 1}击毙{句尾}")
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
    pack = Pack.tarot
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
    pack = Pack.tarot
class wheel_of_fortune_s(_statusdaily):
    id = 'O'
    des = "X - 命运之轮：直至下次刷新前，在商店增加抽奖机，可以消耗5击毙抽奖。"
    is_global = True

class justice(_card):
    name = "XI - 正义"
    id = 11
    positive = 1
    description = "现在你身上每有一个状态，奖励你5击毙。"
    pack = Pack.tarot
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
    pack = Pack.tarot
    @classmethod
    async def use(cls, user: User):
        await user.death()
        await user.add_status('r')
class miansi(_statusnull):
    id = 'r'
    des = "免死：免疫你下一次死亡。"
    @classmethod
    async def OnDeath(cls, count: TCount, user: User, killer: User, time: int, c: TAttackType) -> Tuple[int, bool]:
        if await c.pierce():
            user.send_log(f"免死的效果被幻想杀手消除了{句尾}")
            await user.remove_status('r', remove_all=True, remover=killer)
            return time, False
        else:
            user.send_log(f"触发了免死的效果，免除死亡{句尾}")
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
    pack = Pack.tarot
class death_s(_statusdaily):
    id = 'D'
    des = "XIII - 死神：今天的所有死亡时间加倍。"
    is_debuff = True
    is_global = True
    @classmethod
    async def OnDeath(cls, count: TCount, user: 'User', killer: 'User', time: int, c: TAttackType) -> Tuple[int, bool]:
        return time * 2 ** count, False
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDeath: (Priority.OnDeath.death, cls)}

class temperance(_card):
    name = "XIV - 节制"
    id = 14
    positive = 0
    description = "随机抽取1名玩家，今天该玩家不能使用除胶带外的卡牌。"
    pack = Pack.tarot
    @classmethod
    async def use(cls, user: User) -> None:
        l = config.userdata.execute("select qq from dragon_data where dead=false").fetchall()
        q: int = random.choice(l)["qq"]
        user.send_char(f"抽到了[CQ:at,qq={q}]{句尾}")
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
    des = "XIV - 节制：今天你不能使用除胶带外的卡牌。"
    is_debuff = True
    @classmethod
    async def OnUserUseCard(cls, count: TCount, user: User, card: TCard) -> Tuple[bool, str]:
        if card.id != 100:
            return False, f"你因XIV - 节制的效果，不能使用除胶带外的卡牌{句尾}"
        return True, ""
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnUserUseCard: (Priority.OnUserUseCard.temperance, cls)}

class devil(_card):
    name = "XV - 恶魔"
    id = 15
    positive = 1
    description = "击毙上一位使用卡牌的人。"
    pack = Pack.tarot
    @classmethod
    async def use(cls, user: User):
        q = global_state['last_card_user']
        u = User(q, user.buf)
        user.buf.send(f'[CQ:at,qq={q}]被你击毙了{句尾}')
        await u.killed(user)

class tower(_card):
    name = "XVI - 高塔"
    id = 16
    positive = 0
    description = "随机解除至多3个雷，随机击毙3个玩家。"
    pack = Pack.tarot
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
        user.send_char(f"抽到了{'，'.join(f'[CQ:at,qq={q}]' for q in p)}{句尾}")
        for q in p:
            await User(q, user.buf).killed(user)

class star(_card):
    name = "XVII - 星星"
    id = 17
    positive = 0
    description = "今天的每个词有10%的几率进入奖励词池。"
    global_daily_status = 't'
    pack = Pack.tarot
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
    pack = Pack.tarot
class moon_s(_statusnull):
    id = 'k'
    des = "XVIII - 月亮：下次有人接到隐藏奖励词前，隐藏奖励词数量加1。"
    is_global = True
    @classmethod
    async def on_add(cls, count: TCount):
        from .logic_dragon import add_hidden_keyword
        to_add_amount = count - min(0, 2 + Game.me.check_status('k') - Game.me.check_status('o'))
        if to_add_amount != 0:
            add_hidden_keyword(count=to_add_amount)
    @classmethod
    async def on_remove(cls, remove_all=True):
        from .logic_dragon import remove_hidden_keyword
        count = Game.me.check_status('k') if remove_all else 1
        to_remove_amount = count - min(0, 2 + Game.me.check_status('k') - Game.me.check_status('o'))
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
        to_remove_amount = count - min(0, 2 + Game.me.check_status('k') - Game.me.check_status('o'))
        if to_remove_amount != 0:
            remove_hidden_keyword(count=to_remove_amount)
    @classmethod
    async def on_remove(cls, remove_all=True):
        from .logic_dragon import add_hidden_keyword
        count = Game.me.check_status('o') if remove_all else 1
        to_add_amount = count - min(0, 2 + Game.me.check_status('k') - Game.me.check_status('o'))
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
    pack = Pack.tarot
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
    pack = Pack.tarot
    @classmethod
    async def use(cls, user: User):
        n = [tree.qq for tree in itertools.chain(*itertools.chain(Tree._objs, *Tree.forests))].count(user.qq)
        user.send_log(f"今天的接龙次数是{n}次，", end='')
        if n < 5:
            user.buf.send("扣除" + user.char + f"20击毙{句尾}")
            await user.add_jibi(-20)
        elif n > 20:
            user.send_char(f"获得20击毙{句尾}")
            await user.add_jibi(20)
        else:
            user.buf.send('')

class world(_card):
    name = "XXI - 世界"
    id = 21
    positive = 0
    global_daily_status = 's'
    description = "除大病一场外，所有“直到跨日为止”的效果延长至明天。"
    pack = Pack.tarot
class world_s(_statusdaily):
    id = 's'
    des = "XXI - 世界：除大病一场外，所有“直到跨日为止”的效果延长至明天。"

class randommaj(_card):
    id = 29
    name = "扣置的麻将"
    positive = 1
    mass = 0.25
    description = "增加5次麻将摸牌的机会，然后抽一张卡。发送“摸麻将”摸牌，然后选择切牌/立直/暗杠/和出。"
    newer = 6
    pack = Pack.misc
    @classmethod
    async def use(cls, user: User) -> None:
        user.data.extra.maj_quan += 15
        user.send_log("增加了5张麻将摸牌券" + 句尾)
        await user.draw(1)

class dabingyichang(_card):
    name = "大病一场"
    id = 30
    positive = -1
    description = "抽到时，直到跨日前不得接龙。"
    on_draw_daily_status = 'd'
    on_draw_send_char = "病了" + 句尾 + "直到跨日前不得接龙。"
    consumed_on_draw = True
    pack = Pack.zhu
class shengbing(_statusdaily):
    id = 'd'
    des = "生病：直到跨日前不可接龙。"
    is_debuff = True
    @classmethod
    async def BeforeDragoned(cls, count: TCount, user: User, state: DragonState) -> Tuple[bool, int, str]:
        return False, 0, f"你病了，不能接龙{句尾}"
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.BeforeDragoned: (Priority.BeforeDragoned.shengbing, cls)}

class caipiaozhongjiang(_card):
    name = "彩票中奖"
    id = 31
    positive = 1
    description = "抽到时，你立即获得20击毙与两张牌。"
    consumed_on_draw = True
    pack = Pack.zhu
    @classmethod
    def weight(cls, user: User):
        return 1 + user.data.luck / 2
    @classmethod
    async def on_draw(cls, user: User):
        user.send_char(f"中奖了{句尾}获得20击毙与两张牌。")
        await user.add_jibi(20)
        await user.draw(2)

class wenhuazixin(_card):
    name = "文化自信"
    id = 32
    positive = 0
    description = "清除所有全局状态的75%，最多五个。"
    pack = Pack.zhu
    @classmethod
    async def use(cls, user: User) -> None:
        ume = Userme(user)
        statuses = [(0, c) for c in Game.me.status if StatusNull(c).removeable]
        daily_statuses = [(1, c) for c in Game.me.daily_status if StatusDaily(c).removeable]
        status_times = [(2, c) for c in Game.me.status_time_checked if c.removeable]
        l: list[tuple[int, str | T_status]] = statuses + daily_statuses + status_times
        if len(l) == 0:
            return
        import math
        num = min(math.ceil(len(l) * 0.75), 5)
        l3: list[tuple[int, str | T_status]] = []
        for i in range(num):
            j = random.choice(l)
            l3.append(j)
            l.remove(j)
        for j in l3:
            if j[0] == 0:
                user.send_log("移除了" + name_f(StatusNull(j[1]).des))
                await ume.remove_status(j[1], remove_all=False, remover=user)
            elif j[0] == 1:
                user.send_log("移除了" + name_f(StatusDaily(j[1]).des))
                await ume.remove_daily_status(j[1], remove_all=False, remover=user)
            else:
                user.send_log("移除了" + name_f(j[1].des))
                await ume.remove_limited_status(j[1], remover=user)
        Game.me.save_status_time()

class lebusishu(_card):
    id = 35
    name = "乐不思蜀"
    positive = -1
    description = "抽到时为你附加buff：今天每次接龙时，你进行一次判定。有3/4的几率你不得从该节点接龙。"
    pack = Pack.sanguosha
    newer = 7
    consumed_on_draw = True
    on_draw_daily_status = 'L'
class SLe(_statusdaily):
    id = 'L'
    is_debuff = True
    des = '乐不思蜀：今天每次接龙时，你进行一次判定。有3/4的几率你不得从该节点接龙。'
class SKe(_statusdaily):
    id = 'K'
    is_debuff = True
    des = '反转·乐不思蜀：今天每次接龙时，你进行一次判定。有1/4的几率你不得从该节点接龙。'
class le_checker(IEventListener):
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        checks = [c['qq'] for c in config.userdata.execute("select qq from dragon_data where dead=false and (daily_status like '%K%' or daily_status like '%L%')").fetchall()]
        for qq in checks:
            u = User(qq, user.buf)
            l = u.check_limited_status('n', lambda s: s.length == 1)
            if (n := u.check_daily_status('L')):
                if (r := random.random()) > (0.25 + 0.0375 * u.data.luck) ** n:
                    u.log << f"不可从节点{branch.id_str}接龙。"
                    user.buf.send(f"玩家{qq}判定失败，不可从此节点接龙{句尾}")
                    if len(l) == 0:
                        await u.add_limited_status(SNoDragon([branch.id_str], 1))
                    else:
                        l[0].list.append(branch.id_str)
                elif r > 0.25 ** n:
                    user.buf.send(f"玩家{qq}幸运地判定成功了{句尾}")
            if (n := u.check_daily_status('K')):
                if (r := random.random()) > (0.75 + 0.0375 * u.data.luck) ** n:
                    u.log << f"不可从节点{branch.id_str}接龙。"
                    user.buf.send(f"玩家{qq}判定失败，不可从此节点接龙{句尾}")
                    if len(l) == 0:
                        await u.add_limited_status(SNoDragon([branch.id_str], 1))
                    else:
                        l[0].list.append(branch.id_str)
                elif r > 0.75 ** n:
                    user.buf.send(f"玩家{qq}幸运地判定成功了{句尾}")
            u.data.save_status_time()
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDragoned: (Priority.OnDragoned.lecheck, cls)}
UserData.register_checker(le_checker)

class wuzhongshengyou(_card):
    name = "无中生有"
    id = 36
    positive = 1
    description = "摸两张牌。"
    pack = Pack.sanguosha
    @classmethod
    async def use(cls, user: User):
        await user.draw(2)

class juedou(_card):
    id = 37
    name = "决斗"
    positive = 0
    description = "指定一名玩家，下10次接龙为你与祂之间进行（持续1小时后过期）。"
    newer = 7
    pack = Pack.sanguosha
    @classmethod
    async def use(cls, user: User) -> None:
        if await user.choose():
            config.logger.dragon << f"【LOG】询问用户{user.qq}选择玩家。"
            qq: int = (await user.buf.aget(prompt="请at群内一名玩家。\n",
                arg_filters=[
                        lambda s: [int(r) for r in re.findall(r'qq=(\d+)', str(s))],
                        validators.fit_size(1, 1, message="请at正确的人数。")
                    ]))[0]
            ume = Userme(user)
            if ume.check_limited_status('j'):
                await ume.remove_all_limited_status('j')
            user.buf.send("接下来的10次接龙由你二人进行" + 句尾)
            await ume.add_limited_status(SJuedou(datetime.now() + timedelta(hours=1), user.qq, qq, 10))
class SJuedou(TimedStatus):
    id = 'j'
    is_global = True
    @property
    def des(self):
        return f"决斗：接下来的接龙由玩家{self.player1}与{self.player2}之间进行。"
    def __init__(self, s: Union[str, datetime], player1: int, player2: int, count: int):
        self.player1 = player1
        self.player2 = player2
        self.count = count
        super().__init__(s)
    def check(self) -> bool:
        return self.time >= datetime.now() and self.count > 0
    def __repr__(self) -> str:
        return self.construct_repr(str(self.time), self.player1, self.player2, self.count)
    def __str__(self) -> str:
        delta = self.time - datetime.now()
        min = delta.seconds // 60
        return f"{self.des}\n\t剩余{self.count}次，结束时间：{f'{delta.days}日' if delta.days != 0 else ''}{f'{min // 60}时' if min // 60 != 0 else ''}{min % 60}分钟。"
    @classmethod
    async def BeforeDragoned(cls, count: TCount, user: 'User', state: DragonState) -> Tuple[bool, int, str]:
        if user.qq == count[0].player1 or user.qq == count[0].player2:
            return True, -100, ""
        else:
            return False, 0, "不可打扰玩家间的决斗" + 句尾
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        count[0].count -= 1
        Game.me.save_status_time()
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.BeforeDragoned: (Priority.BeforeDragoned.juedou, cls),
            UserEvt.OnDragoned: (Priority.OnDragoned.juedou, cls)}

class tiesuolianhuan(_card):
    name = "铁索连环"
    id = 38
    positive = 1
    description = "指定至多两名玩家进入或解除其连环状态。任何处于连环状态的玩家被击毙时所有连环状态的玩家也被击毙并失去此效果。"
    is_metallic = True
    pack = Pack.sanguosha
    @classmethod
    async def use(cls, user: User):
        if await user.choose():
            config.logger.dragon << f"【LOG】询问用户{user.qq}铁索连环。"
            l: List[int] = await user.buf.aget(prompt="请at群内至多两名玩家进行铁索连环。\n",
                arg_filters=[
                        lambda s: [int(r) for r in re.findall(r'qq=(\d+)', str(s))],
                        validators.ensure_true(lambda s: config.selfqq not in s, message=f"不能选我{句尾}"),
                        validators.fit_size(1, 2, message="请at正确的人数。")
                    ])
            config.logger.dragon << f"【LOG】用户{user.qq}铁索连环选择{l}。"
            for target in l:
                u = User(target, user.buf)
                atk = ATiesuolianhuan(user, u)
                await u.attacked(user, atk)
            user.buf.send(f"成功切换连环状态{句尾}")
            save_global_state()
class ATiesuolianhuan(Attack):
    name = "铁索连环"
    doublable = False
    async def self_action(self):
        if self.defender.check_status('l'):
            await self.defender.remove_status('l', remover=self.attacker)
        else:
            await self.defender.add_status('l')
class tiesuolianhuan_s(_statusnull):
    id = 'l'
    des = "铁索连环：任何处于连环状态的玩家被击毙时所有连环状态的玩家也被击毙并失去此效果。"
    is_debuff = True
    is_metallic = True
    @classmethod
    async def OnDeath(cls, count: TCount, user: 'User', killer: 'User', time: int, c: TAttackType) -> Tuple[int, bool]:
        if await c.pierce():
            await user.remove_status('l', remove_all=True)
            user.send_log(f"铁索连环的效果被幻想杀手消除了{句尾}")
        else:
            all_qqs: List[int] = []
            for r in config.userdata.execute("select qq from dragon_data where status like '%l%'").fetchall():
                if r['qq'] == user.qq: continue
                all_qqs.append(r['qq'])
            user.buf.send(f"由于铁索连环的效果，{' '.join(f'[CQ:at,qq={target}]' for target in all_qqs)}也一起死了{句尾}")
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
    mass = 0.75
    pack = Pack.sanguosha
class minus1ma_s(_statusdaily):
    id = 'm'
    des = "-1马：今天你可以少隔一个接龙，但最少隔一个。"
    @classmethod
    async def BeforeDragoned(cls, count: TCount, user: User, state: DragonState) -> Tuple[bool, int, str]:
        return True, -1, ""
    @classmethod
    def register(cls):
        return {UserEvt.BeforeDragoned: (Priority.BeforeDragoned.minus1ma, cls)}
class plus1ma_s(_statusdaily):
    id = 'M'
    des = "+1马：今天你必须额外隔一个才能接龙。"
    is_debuff = True
    @classmethod
    async def BeforeDragoned(cls, count: TCount, user: User, state: DragonState) -> Tuple[bool, int, str]:
        return True, 1, ""
    @classmethod
    def register(cls):
        return {UserEvt.BeforeDragoned: (Priority.BeforeDragoned.plus1ma, cls)}

class sihuihuibizhiyao(_card):
    name = "死秽回避之药"
    id = 50
    positive = 1
    status = 's'
    description = "你下次死亡时自动消耗5击毙免除死亡。若击毙不足则不发动。"
    pack = Pack.honglongdong
class sihuihuibizhiyao_s(_statusnull):
    id = 's'
    des = '死秽回避之药：下次死亡时自动消耗5击毙免除死亡。若击毙不足则不发动。'
    @classmethod
    async def OnDeath(cls, count: TCount, user: User, killer: User, time: int, c: TAttackType) -> Tuple[int, bool]:
        if await c.pierce():
            user.send_log(f"死秽回避之药的效果被幻想杀手消除了{句尾}")
            await user.remove_status('s', remove_all=True, remover=killer)
            return time, False
        elif await user.add_jibi(-5, is_buy=True):
            user.send_log(f"触发了死秽回避之药的效果，免除死亡{句尾}")
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
    async def OnDeath(cls, count: TCount, user: User, killer: User, time: int, c: TAttackType) -> Tuple[int, bool]:
        if await c.pierce():
            user.send_log(f"反转·死秽回避之药的效果被幻想杀手消除了{句尾}")
            await user.remove_status('t', remover=killer)
            return time, False
        user.send_log(f"触发了{count}次反转·死秽回避之药的效果，增加{5 * count}击毙，死亡时间增加{2 * count}小时{句尾}")
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
    mass = 0.2
    is_metallic = True
    pack = Pack.honglongdong
class huiye_s(_statusnull):
    id = 'x'
    des = '辉夜姬的秘密宝箱：下一次死亡的时候奖励抽一张卡。'
    is_metallic = True
    @classmethod
    async def OnDeath(cls, count: TCount, user: User, killer: User, time: int, c: TAttackType) -> Tuple[int, bool]:
        if await c.pierce():
            user.send_log(f"辉夜姬的秘密宝箱的效果被幻想杀手消除了{句尾}")
            await user.remove_status('x', remover=killer)
        else:
            user.send_log(f"触发了辉夜姬的秘密宝箱{句尾}奖励抽卡{count}张。")
            await user.remove_status('x')
            await user.draw(count)
        return time, False
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDeath: (Priority.OnDeath.huiye, cls)}
class inv_huiye_s(_statusnull):
    id = 'y'
    des = '反转·辉夜姬的秘密宝箱：你下一次死亡的时候随机弃一张牌。'
    is_debuff = True
    is_metallic = True
    @classmethod
    async def OnDeath(cls, count: TCount, user: User, killer: User, time: int, c: TAttackType) -> Tuple[int, bool]:
        if await c.pierce():
            user.send_log(f"反转·辉夜姬的秘密宝箱的效果被幻想杀手消除了{句尾}")
            await user.remove_status('y', remover=killer)
        else:
            user.send_log(f"触发了反转·辉夜姬的秘密宝箱{句尾}随机弃{count}张卡。")
            await user.remove_status('y')
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
    description = "使用时弃置随机5张手牌。此牌不可因手牌超出上限而被弃置。"
    pack = Pack.honglongdong
    @classmethod
    async def use(cls, user: User):
        if len(user.data.hand_card) <= 5:
            user.send_log("弃光了所有手牌。")
            await user.discard_cards(copy(user.data.hand_card))
        else:
            l = list(range(len(user.data.hand_card)))
            p: List[TCard] = []
            for _ in range(5):
                i = random.choice(l)
                p.append(user.data.hand_card[i])
                l.remove(i)
            user.send_log(f"弃置了{'，'.join(c.name for c in p)}。")
            await user.discard_cards(p)

class dragontube(_card):
    name = "龙之烟管"
    id = 54
    positive = 1
    description = "你今天通过普通接龙获得的击毙上限增加10。"
    is_metallic = True
    mass = 0.2
    pack = Pack.honglongdong
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
    pack = Pack.honglongdong
    @classmethod
    async def use(cls, user: User):
        await user.draw_and_use(positive={1})

class baoshidewugong(_card):
    name = "暴食的蜈蚣"
    id = 56
    positive = 1
    description = "你的手牌上限永久+1。"
    pack = Pack.honglongdong
    @classmethod
    def weight(cls, user: User):
        if user.data.card_limit < 20:
            return 1 + user.data.luck / 10 * (20 - user.data.card_limit)
        return 1
    @classmethod
    async def use(cls, user: User):
        user.data.card_limit_raw += 1
        config.logger.dragon << f"【LOG】用户{user.qq}增加了raw手牌上限至{user.data.card_limit_raw}。"

class zhaocaimao(_card):
    name = "擅长做生意的招财猫"
    id = 57
    positive = 1
    description = "你今天可以额外购买3次商店里的购买卡牌。"
    pack = Pack.honglongdong
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
    pack = Pack.uno
class plus2_s(_statusnull):
    id = '+'
    des = "+2：下一个接龙的人摸一张非负面卡和一张非正面卡。"
    is_global = True
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        await Userme(user).remove_status('+')
        user.send_char(f"触发了{count}次+2的效果，摸{count}张非正面牌与{count}张非负面牌{句尾}")
        user.log << f"触发了+2的效果。"
        cards = list(itertools.chain(*[[draw_card(user, {-1, 0}), draw_card(user, {0, 1})] for i in range(count)]))
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
    mass = 0
    pack = Pack.once_upon_a_time
    @classmethod
    async def use(cls, user: User) -> None:
        node = random.choice(list(itertools.chain(*Tree._objs)))
        c = random.random()
        config.logger.dragon << f"【DEBUG】c={c}"
        if c < 0.5 + 0.02 * user.data.luck:
            if c > 0.5:
                user.buf.send("幸运地", end='')
            user.buf.send(f"回溯到了节点{node.id_str}{句尾}")
            for n in node.childs:
                n.remove()
            from .logic_dragon import rewrite_log_file
            rewrite_log_file()
        else:
            user.buf.send(f"节点{node.id_str}被分叉了{句尾}")
            config.logger.dragon << f"【LOG】节点{node.id_str}被分叉了。"
            node.fork = True

class hezuowujian(_card):
    name = "合作无间"
    id = 63
    positive = 1
    description = "拆除所有雷，每个雷有70%的概率被拆除。"
    pack = Pack.explodes
    @classmethod
    async def use(cls, user: User):
        from .logic_dragon import remove_all_bomb
        remove_all_bomb(0.7)

class ourostone(_card):
    name = "衔尾蛇之石"
    id = 66
    positive = 0
    description = "修改当前规则至首尾接龙直至跨日。"
    mass = 0.2
    pack = Pack.stone_story
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
    async def BeforeDragoned(cls, count: TCount, user: User, state: DragonState) -> Tuple[bool, int, str]:
        if not await state.require_shouwei(user):
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
    async def BeforeDragoned(cls, count: TCount, user: User, state: DragonState) -> Tuple[bool, int, str]:
        if not await state.require_weishou(user):
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
    mass = 0.2
    pack = Pack.stone_story
    @classmethod
    def quest_des(cls, qq: int):
        r = Game.userdata(qq).quest_c
        m = mission[r['id']][1]
        remain = r['remain']
        return "\t当前任务：" + m + f"剩余{remain}次。"
    @classmethod
    def full_description(cls, qq: int):
        return super().full_description(qq) + "\n" + cls.quest_des(qq)
    @classmethod
    async def on_draw(cls, user: User):
        user.data.quests.append({'id': (i := get_mission()), 'remain': 3})
        config.logger.dragon << f"【LOG】用户{user.qq}刷新了一个任务{mission[i][1]}，现有任务：{[mission[c['id']][1] for c in user.data.quests]}。"
        save_global_state()
    @classmethod
    async def on_remove(cls, user: User):
        r = user.data.pop_quest()
        config.logger.dragon << f"【LOG】用户{user.qq}删除了一个任务{mission[r['id']][1]}，现有任务：{[mission[c['id']][1] for c in user.data.quests]}。"
        save_global_state()
    @classmethod
    async def on_give(cls, user: User, target: User):
        r = user.data.pop_quest()
        config.logger.dragon << f"【LOG】用户{user.qq}删除了一个任务{mission[r['id']][1]}，现有任务：{[mission[c['id']][1] for c in user.data.quests]}。"
        target.data.quests.append(r)
        config.logger.dragon << f"【LOG】用户{target.qq}增加了一个任务{mission[r['id']][1]}，现有任务：{[mission[c['id']][1] for c in target.data.quests]}。"
        save_global_state()
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        for m in user.data.quests:
            if m['remain'] > 0:
                id, name, func = mission[m['id']]
                if func(branch.word):
                    user.send_char(f"完成了任务：{name[:-1]}{句尾}奖励3击毙。此任务还可完成{m['remain'] - 1}次。")
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
    is_metallic = True
    mass = 0.25
    pack = Pack.orange_juice
class cunqianguan_s(_statusnull):
    id = 'm'
    des = "存钱罐：下次触发隐藏词的奖励+10击毙。"
    is_metallic = True
    is_global = True
    @classmethod
    async def OnHiddenKeyword(cls, count: TCount, user: 'User', word: str, parent: 'Tree', keyword: str) -> Tuple[int]:
        user.send_log(f"触发了存钱罐，奖励+{count * 10}击毙{句尾}")
        await Userme(user).remove_status('m')
        return count * 10,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnHiddenKeyword: (Priority.OnHiddenKeyword.cunqianguan, cls)}
class inv_cunqianguan_s(_statusnull):
    id = 'M'
    des = "反转·存钱罐：下次触发隐藏词的奖励-10击毙。"
    is_metallic = True
    is_global = True
    is_debuff = True
    @classmethod
    async def OnHiddenKeyword(cls, count: TCount, user: 'User', word: str, parent: 'Tree', keyword: str) -> Tuple[int]:
        user.send_log(f"触发了反转·存钱罐，奖励-{count * 10}击毙{句尾}")
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
    pack = Pack.orange_juice
class hongsezhihuan_s(_statusnull):
    id = 'h'
    des = '虹色之环：下次死亡时，有1/2几率闪避，1/2几率死亡时间+1小时。'
    @classmethod
    async def OnDeath(cls, count: TCount, user: User, killer: User, time: int, c: TAttackType) -> Tuple[int, bool]:
        if await c.pierce():
            user.send_log(f"虹色之环的效果被幻想杀手消除了{句尾}")
            await user.remove_status('h', remove_all=True, remover=killer)
            return time, False
        for a in range(count):
            await user.remove_status('h', remove_all=False)
            if (c := random.random()) < 0.5 + 0.02 * user.data.luck:
                if c > 0.5:
                    user.buf.send("幸运地", end="")
                user.send_log(f"触发了虹色之环，闪避了死亡{句尾}")
                return time, True
            else:
                time += 60
                user.send_log(f"触发虹色之环闪避失败，死亡时间+1h{句尾}")
        return time, False
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDeath: (Priority.OnDeath.hongsezhihuan, cls)}

class liwujiaohuan(_card):
    name = "礼物交换"
    id = 72
    positive = 1
    description = "最近接过龙的玩家每人抽出一张手牌集合在一起随机分配。"
    pack = Pack.orange_juice
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
        for u in all_users:
            u.data.set_cards()
        if lose is None and get is None:
            user.buf.send(f"你交换了大家的手牌{句尾}")
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
    hold_des = '幸运护符：每天只能使用一张其他卡牌，你的幸运值+1。'
    positive = 1
    description = "持有此卡时，每天只能使用一张其他卡牌，你的幸运值+1。使用将丢弃这张卡。"
    pack = Pack.orange_juice
    @classmethod
    async def OnUserUseCard(cls, count: TCount, user: User, card: TCard) -> Tuple[bool, str]:
        if card is not xingyunhufu:
            user.send_log("今天幸运护符的使用卡牌次数已用完" + 句尾)
            await user.add_daily_status('U')
        return True, ""
    @classmethod
    def register(cls):
        return {UserEvt.OnUserUseCard: (Priority.OnUserUseCard.xingyunhufu, cls)}
class xingyunhufu_s(_statusdaily):
    id = 'U'
    des = "幸运护符次数已用完：今天你不能使用除幸运护符以外的卡牌。"
    is_debuff = True
    @classmethod
    async def OnUserUseCard(cls, count: TCount, user: User, card: TCard) -> Tuple[bool, str]:
        if xingyunhufu in user.data.hand_card and card is not xingyunhufu:
            return False, f"你今天幸运护符的使用卡牌次数已用完，不可使用{句尾}"
        return True, ""
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnUserUseCard: (Priority.OnUserUseCard.xingyunhufus, cls)}

class jisuzhuangzhi(_card):
    name = "极速装置"
    id = 74
    status = 'z'
    positive = 1
    description = '你下次你可以连续接龙两次。'
    pack = Pack.orange_juice
class jisuzhuangzhi_s(_statusnull):
    id = 'z'
    des = "极速装置：你下次可以连续接龙两次。"
    @classmethod
    async def CheckSuguri(cls, count: TCount, user: 'User', state: DragonState) -> Tuple[bool]:
        await user.remove_status('z', remove_all=False)
        return True,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.CheckSuguri: (Priority.CheckSuguri.jisuzhuangzhi, cls)}

class huxiangjiaohuan(_card):
    name = '互相交换'
    id = 75
    positive = 0
    description = "下一个接中隐藏奖励词的玩家手牌与你互换，手牌量变化最多为2。"
    pack = Pack.orange_juice
    @classmethod
    async def use(cls, user: User):
        l = Game.me.check_limited_status('x')
        if l:
            l[0] += [user.qq]
            user.log << f"被加入交换堆栈，现为{l[0].list}。"
            Game.me.save_status_time()
        else:
            await Userme(user).add_limited_status(SHuxiangjiaohuan([user.qq]))
class SHuxiangjiaohuan(ListStatus):
    id = 'x'
    des = "互相交换：下一个接中隐藏奖励词的玩家手牌与某人互换。"
    def __str__(self):
        return '\n'.join("互相交换：下一个接中隐藏奖励词的玩家手牌与某人互换。" for i in self.list)
    @property
    def brief_des(self):
        return '\n'.join("互相交换" for i in self.list)
    is_global = True
    @classmethod
    async def OnHiddenKeyword(cls, count: TCount, user: 'User', word: str, parent: 'Tree', keyword: str) -> Tuple[int]:
        to_exchange = count[0].list.pop()
        Game.me.save_status_time()
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
        self.defender.send_char(f"与[CQ:at,qq={self.attacker.qq}]交换了手牌{句尾}")
        jibi = (self.defender.data.jibi, self.attacker.data.jibi)
        self.defender.log << f"与{self.attacker.qq}交换了手牌。"
        await self.defender.exchange(self.attacker, max_sub=2)

class zhongshendexixi(_card):
    name = "众神的嬉戏"
    id = 76
    positive = 0
    description = '抽取一张卡并立即发动其使用效果。'
    pack = Pack.orange_juice
    @classmethod
    async def use(cls, user: User):
        await user.draw_and_use()

class lveduozhebopu(_card):
    name = "掠夺者啵噗"
    id = 77
    positive = 1
    hold_des = '掠夺者啵噗：你每天可从所接龙的人处偷取1击毙，每人限一次，最多10击毙，若目标没有击毙则不可偷取。'
    description = "持有此卡时，你每天你可从你所接龙的人处偷取1击毙，每人限一次，最多10击毙，若目标没有击毙则不可偷取。使用或死亡时将丢弃这张卡。"
    pack = Pack.orange_juice
    @classmethod
    async def on_draw(cls, user: User):
        user.data.steal
        save_global_state()
    @classmethod
    async def on_remove(cls, user: User):
        if Card(77) not in user.data.hand_card and str(user.qq) in global_state['steal']:
            del global_state['steal'][str(user.qq)]
        save_global_state()
    @classmethod
    async def on_give(cls, user: User, target: User):
        target.data.steal = user.data.steal
        if Card(77) not in user.data.hand_card and str(user.qq) in global_state['steal']:
            del global_state['steal'][str(user.qq)]
        save_global_state()
    @classmethod
    async def OnDeath(cls, count: TCount, user: User, killer: User, time: int, c: TAttackType) -> Tuple[int, bool]:
        user.send_log(f"的{f'{count}张' if count > 1 else ''}掠夺者啵噗被弃了{句尾}")
        await user.discard_cards([cls] * count)
        return time, False
    @classmethod
    async def OnDragoned(cls, count: TCount, user: User, branch: 'Tree', first10: bool) -> Tuple[()]:
        global global_state
        last_qq = branch.parent.qq
        if branch.parent.id != (0, 0):
            last = User(last_qq, user.buf)
            s = user.data.steal
            if last_qq not in s['user'] and s['time'] < 10:
                s['time'] += 1
                s['user'].append(last_qq)
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
            self.attacker.send_char(f"从上一名玩家处偷取了{min(n, p)}击毙{句尾}")
            await self.defender.add_jibi(-n)
            await self.attacker.add_jibi(min(n, p))

class jiandieyubei(_card):
    name = "邪恶的间谍行动～预备"
    id = 78
    positive = 0
    global_daily_status = 'j'
    description = "今日卡池中有一定概率出现【邪恶的间谍行动~执行】。"
    pack = Pack.orange_juice
class jiandieyubei_s(_statusdaily):
    id = 'j'
    des = "邪恶的间谍行动～预备：今日卡池中有一定概率出现【邪恶的间谍行动~执行】。"

class qijimanbu(_card):
    name = "奇迹漫步"
    id = 79
    positive = 1
    description = "弃置你所有手牌，并摸取等量的非负面牌。"
    pack = Pack.orange_juice
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
    pack = Pack.playtest
class ComicSans_s(_statusdaily):
    id = 'c'
    des = 'Comic Sans：七海千春今天所有生成的图片均使用Comic Sans作为西文字体（中文使用华文彩云）。'

class PC(_card):
    name = "PC"
    id = 81
    positive = 1
    description = '今天接过龙的所有人立刻获得胜利。'
    pack = Pack.playtest
    @classmethod
    async def use(cls, user: User):
        user.buf.send(f"今天接龙的所有人都赢了{句尾}恭喜你们{句尾}")
        qqs = [tree.qq for tree in itertools.chain(*itertools.chain(Tree._objs, *Tree.forests))]
        for qq in set(qqs):
            await User(qq, user.buf).add_daily_status('W')
class win(_statusdaily):
    id = 'W'
    des = "胜利：恭喜，今天你赢了" + 句尾
class defeat(_statusdaily):
    id = 'X'
    des = "失败：对不起，今天你输了" + 句尾
    is_debuff = True

class suicideking(_card):
    name = "自杀之王（♥K）"
    id = 90
    positive = -1
    description = "抽到时立即死亡。"
    consumed_on_draw = True
    pack = Pack.poker
    @classmethod
    async def on_draw(cls, user: User):
        user.send_char("抽到了自杀之王，" + user.char + f"死了{句尾}")
        await user.death()

class zhu(_card):
    name = "猪（♠Q）"
    id = 91
    positive = -1
    description = "抽到时损失20击毙（但不会扣至0以下）。"
    consumed_on_draw = True
    pack = Pack.poker
    @classmethod
    async def on_draw(cls, user: User):
        await user.add_jibi(-20)
        user.send_char(f"抽到了猪，损失了20击毙{句尾}")

class yang(_card):
    name = "羊（♦J）"
    id = 92
    positive = 1
    description = "抽到时获得20击毙。"
    consumed_on_draw = True
    pack = Pack.poker
    @classmethod
    async def on_draw(cls, user: User):
        await user.add_jibi(20)
        user.send_char(f"抽到了羊，获得了20击毙{句尾}")

class bianyaqi(_card):
    name = "变压器（♣10）"
    id = 93
    status = '2'
    positive = 0
    description = "下一次你的击毙变动变动值加倍。"
    is_metallic = True
    mass = 0.2
    pack = Pack.poker
class bianyaqi_s(_statusnull):
    id = '2'
    des = "变压器（♣10）：下一次击毙变动变动值加倍。"
    is_metallic = True
    @classmethod
    async def CheckJibiSpend(cls, count: TCount, user: 'User', jibi: int) -> Tuple[int]:
        return jibi * 2 ** count,
    @classmethod
    async def OnJibiChange(cls, count: TCount, user: 'User', jibi: int, is_buy: bool) -> Tuple[int]:
        await user.remove_status('2')
        user.send_log(f'触发了{f"{count}次" if count != 1 else ""}变压器的效果，获得击毙变为{jibi * 2 ** count}{句尾}')
        return jibi * 2 ** count,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.CheckJibiSpend: (Priority.CheckJibiSpend.bianyaqi, cls),
            UserEvt.OnJibiChange: (Priority.OnJibiChange.inv_bianyaqi, cls)}
class inv_bianyaqi_s(_statusnull):
    id = '1'
    des = "反转·变压器（♣10）：下一次你的击毙变动变动值减半。"
    is_metallic = True
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
            UserEvt.OnJibiChange: (Priority.OnJibiChange.inv_bianyaqi, cls)}

class guanggaopai(_card):
    name = "广告牌"
    id = 94
    positive = 0
    consumed_on_draw = True
    pack = Pack.poker
    @classmethod
    @property
    def description(self):
        return random.choice([
            "广告位永久招租，联系邮箱：shedarshian@gmail.com",
            "MUASTG，车万原作游戏前沿逆向研究，主要研究弹幕判定、射击火力、ZUN引擎弹幕设计等，曾发表车万顶刊华胥三绝，有意者加群796991184",
            "你想明白生命的意义吗？你想真正……的活着吗？\n\t☑下载战斗天邪鬼：https://pan.baidu.com/s/1FIAxhHIaggld3yRAyFr9FA",
            "欢迎关注甜品站弹幕研究协会，国内一流的东方STG学术交流平台，从避弹，打分到neta，可以学到各种高端姿势：https://www.isndes.com/ms?m=2",
            "[CQ:at,qq=1469335215]哈斯塔快去画逻辑接龙卡图",
            "《世界計畫 繽紛舞台！ feat. 初音未來》正式開啓公測！欢迎下载：www.tw-pjsekai.com",
            "嘉然…嘿嘿🤤…小嘉然…嘿嘿🤤然然带我走吧…🤤",
            "这是一个历经多年开发并且仍在更新的，包罗万象、应有尽有的MC整合包；这是一个让各个模组互相联动融为一体，向独立游戏看齐的MC整合包。加入GTNH，一起跨越科技的巅峰！www.gtnewhorizons.com",
            "真人面对面收割，美女角色在线掉分，发狂玩蛇新天地，尽在 https://arcaea.lowiro.com",
            "[SPAM]真味探寻不止\n只有6种成分，世棒经典午餐肉就是这么简单！肉嫩多汁、肉香四溢，猪肉含量>90%！源自1937年的美国，快来尝试吧！",
        ])

class baipai(_card):
    name = "白牌"
    id = 95
    positive = 1
    description = "选择你手牌中的一张牌，执行其使用效果。"
    pack = Pack.poker
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

class jiaodai(_card):
    name = "布莱恩科技航空专用强化胶带FAL84型"
    id = 100
    positive = 1
    description = "取消掉你身上的至多6种负面状态（不包括死亡），并免疫下次即刻生效的负面状态（不包括死亡）。"
    pack = Pack.gregtech
    @classmethod
    def weight(cls, user: User):
        if user.data.luck == 0:
            return 1
        count = sum(1 for c in map(StatusNull, user.data.status) if c.id != 'd' and c.is_debuff and c.removeable) \
            + sum(1 for c in map(StatusDaily, user.data.daily_status) if c.id != 'd' and c.is_debuff and c.removeable) \
            + sum(1 for s in user.data.status_time_checked if s.id != 'd' and not isinstance(s, Swufazhandou) and s.is_debuff and s.removeable)
        return 1 + user.data.luck / 5 * min(count, 6)
    @classmethod
    async def use(cls, user: User) -> None:
        has = 6
        for c in map(StatusNull, user.data.status):
            if c.id != 'd' and c.is_debuff and c.removeable and has > 0:
                has -= 1
                user.send_char(f"的{c.des[:c.des.index('：')]}被取消了{句尾}")
                await user.remove_status(c.id, remove_all=False, remover=user)
        for c in map(StatusDaily, user.data.daily_status):
            if c.id != 'd' and c.is_debuff and c.removeable and has > 0:
                has -= 1
                user.send_char(f"的{c.des[:c.des.index('：')]}被取消了{句尾}")
                await user.remove_daily_status(c.id, remove_all=False, remover=user)
        i = 0
        while i < len(user.data.status_time_checked):
            s = user.data.status_time[i]
            if s.id != 'd' and not isinstance(s, Swufazhandou) and s.is_debuff and s.removeable and has > 0:
                has -= 1
                des = s.des
                user.send_log(f"的{des[:des.index('：')]}被取消了{句尾}")
                await user.remove_limited_status(s, remover=user)
            else:
                i += 1
        user.data.save_status_time()
        await user.add_status('8')
class jiaodai_s(_statusnull):
    id = '8'
    des = "布莱恩科技航空专用强化胶带FAL84型：免疫你下次即刻生效的负面状态（不包括死亡）。"
    @classmethod
    async def OnStatusAdd(cls, count: TCount, user: 'User', status: TStatusAll, count2: int) -> Tuple[int]:
        if status.is_debuff and status.id != 'd' and not isinstance(status, Swufazhandou):
            for i in range(min(count, count2)):
                await user.remove_status('8', remove_all=False)
            user.send_log(f"触发了胶带的效果，免除此负面状态{句尾}")
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
            user.send_log(f"触发了反转·胶带的效果，免除此非负面状态{句尾}")
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
    is_metallic = True
    pack = Pack.gregtech
class SZPM(_statusnull):
    id = 'Z'
    des = "零点模块：若你当前击毙少于100，则每次接龙为你额外提供1击毙，若你当前击毙多于100，此buff立即消失。"
    is_metallic = True
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        if user.data.jibi > 100:
            user.send_char(f"已经不再需要零点模块了{句尾}")
            await user.remove_status('Z')
        else:
            user.send_char(f"因为零点模块额外获得1击毙{句尾}")
            await user.add_jibi(1)
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDragoned: (Priority.OnDragoned.zpm, cls)}

class McGuffium239(_card):
    name = "Mc Guffium 239"
    id = 102
    positive = 1
    status = 'G'
    description = "下一次礼物交换不对你生效。"
    pack = Pack.gregtech
class McGuffium239_s(_statusnull):
    id = 'G'
    des = "Mc Guffium 239：下一次礼物交换不对你生效。"
    @classmethod
    async def OnAttacked(cls, count: TCount, user: 'User', attack: 'Attack') -> Tuple[bool]:
        if isinstance(attack, ALiwujiaohuan):
            if await attack.counter.pierce():
                user.send_log(f"Mc Guffium 239的效果被幻想杀手消除了{句尾}")
                await user.remove_status('G', remove_all=True, remover=attack.attacker)
            else:
                user.buf.send(f"玩家{user.qq}触发了Mc Guffium 239，礼物交换对{user.char}无效{句尾}")
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
    failure_message = "你的手牌不足，无法使用" + 句尾
    pack = Pack.cultist
    @classmethod
    def can_use(cls, user: User, copy: bool) -> bool:
        return len(user.data.hand_card) >= (2 if copy else 3)
    @classmethod
    async def use(cls, user: User) -> None:
        async with user.choose_cards("请选择你手牌中的两张牌聚集，输入id号。", 2, 2) as l, check_active(l):
            await user.remove_cards([Card(l[0]), Card(l[1])])
            id_new = l[0] + l[1]
            if id_new not in _card.card_id_dict:
                user.buf.send(f"不存在id为{id_new}的牌{句尾}")
                id_new = -1
            else:
                user.send_char(f"将这两张牌合成为了id为{id_new}的牌{句尾}")
            c = Card(id_new)
            await user.draw(0, cards=[c])

class liebianfashu(_card):
    name = "裂变法术"
    id = 106
    positive = 1
    description = "将一张手牌变为两张随机牌，这两张牌的id之和为之前的卡牌的id。若不存在这样的组合，则变为两张【邪恶的间谍行动～执行】。"
    failure_message = "你的手牌不足，无法使用" + 句尾
    pack = Pack.cultist
    @classmethod
    def can_use(cls, user: User, copy: bool) -> bool:
        return len(user.data.hand_card) >= (1 if copy else 2)
    @classmethod
    async def use(cls, user: User) -> None:
        async with user.choose_cards("请选择你手牌中的一张牌裂变，输入id号。", 1, 1) as l, check_active(l):
            await user.remove_cards([Card(l[0])])
            l2 = [(id, l[0] - id) for id in _card.card_id_dict if l[0] - id in _card.card_id_dict]
            if len(l2) == 0:
                user.buf.send(f"不存在两张和为{l[0]}的牌{句尾}")
                id_new = (-1, -1)
            else:
                id_new = random.choice(l2)
                user.send_char(f"将这张牌分解为了id为{id_new[0]}与{id_new[1]}的牌{句尾}")
            await user.draw(0, cards=[Card(id_new[0]), Card(id_new[1])])

class jingxingfashu(_card):
    name = "警醒法术"
    id = 107
    positive = 1
    description = "揭示至多三个雷。"
    pack = Pack.cultist
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
    description = "对指定玩家发动，该玩家的每条可清除状态都有1/2的概率被清除；或是发送qq=2711644761对千春使用，消除【XXI-世界】外50%的全局状态，最多5个。"
    pack = Pack.cultist
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
                user.send_log(f"选择了千春{句尾}消除了【XXI-世界】外的50%的全局状态{句尾}")
                ume = Userme(user)
                statuses = [(0, c) for c in Game.me.status if StatusNull(c).removeable]
                daily_statuses = [(1, c) for c in Game.me.daily_status if StatusDaily(c).removeable]
                status_times = [(2, c) for c in Game.me.status_time_checked if c.removeable]
                l: list[tuple[int, str | T_status]] = statuses + daily_statuses + status_times
                if len(l) == 0:
                    return
                import math
                num = min(math.ceil(l * 0.5), 5)
                l3: list[tuple[int, str | T_status]] = []
                for i in range(num):
                    j = random.choice(l)
                    l3.append(j)
                    l.remove(j)
                for j in l3:
                    if j[0] == 0:
                        user.send_log("移除了" + name_f(StatusNull(j[1]).des))
                        await ume.remove_status(j[1], remove_all=False, remover=user)
                    elif j[0] == 1:
                        user.send_log("移除了" + name_f(StatusDaily(j[1]).des))
                        await ume.remove_daily_status(j[1], remove_all=False, remover=user)
                    else:
                        user.send_log("移除了" + name_f(j[2].des))
                        await ume.remove_limited_status(j[2], remover=user)
                Game.me.save_status_time()
            else:
                user.send_log(f"选择了玩家{qq}{句尾}")
                u = User(qq, user.buf)
                atk = AXiaohunfashu(user, u)
                await u.attacked(user, atk)
class AXiaohunfashu(Attack):
    name = "攻击：销魂法术"
    doublable = False
    async def self_action(self):
        # 永久状态
        for c in self.defender.data.status:
            if random.random() > 0.5 ** self.multiplier or not StatusNull(c).removeable:
                continue
            await self.defender.remove_status(c, remove_all=False, remover=self.attacker)
            des = StatusNull(c).des
            self.defender.send_log(f"的{des[:des.index('：')]}被消除了{句尾}")
        # 每日状态
        for c in self.defender.data.daily_status:
            if random.random() > 0.5 ** self.multiplier or not StatusDaily(c).removeable:
                continue
            await self.defender.remove_daily_status(c, remove_all=False, remover=self.attacker)
            des = StatusDaily(c).des
            self.defender.send_log(f"的{des[:des.index('：')]}被消除了{句尾}")
        # 带附加值的状态
        l = [c for c in self.defender.data.status_time_checked if c.removeable]
        i = 0
        for i in l:
            if random.random() < 0.5 ** self.multiplier:
                des = i.des
                self.defender.send_log(f"的{des[:des.index('：')]}被消除了{句尾}")
                await self.defender.remove_limited_status(i, remover=self.attacker)
        self.defender.data.save_status_time()

class ranshefashu(_card):
    name = "蚺虵法术"
    id = 109
    positive = 1
    newer = 3
    description = "对指定玩家发动，该玩家当日每次接龙需额外遵循首尾接龙规则。"
    pack = Pack.cultist
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
    doublable = False
    async def self_action(self):
        await self.defender.add_daily_status('R')
        self.defender.send_char(f"今天接龙需额外遵循首尾接龙规则{句尾}")
class ranshefashu_s(_statusdaily):
    id = 'R'
    des = "蚺虵法术：你当日每次接龙需额外遵循首尾接龙规则。"
    @classmethod
    async def BeforeDragoned(cls, count: TCount, user: 'User', state: DragonState) -> Tuple[bool, int, str]:
        if not await state.require_shouwei(user):
            return False, 0, "你需额外遵循首尾接龙规则，接龙失败。"
        return True, 0, ""
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.BeforeDragoned: (Priority.BeforeDragoned.ranshefashu, cls)}
class inv_ranshefashu_s(_statusdaily):
    id = 'Z'
    des = "反转·蚺虵法术：你当日每次接龙需额外遵循尾首接龙规则。"
    @classmethod
    async def BeforeDragoned(cls, count: TCount, user: 'User', state: DragonState) -> Tuple[bool, int, str]:
        if not await state.require_weishou(user):
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
    pack = Pack.ff14
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
                user.send_char(f"触发了月下彼岸花的效果，损失1击毙{句尾}")
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
                user.send_char(f"触发了反转·月下彼岸花的效果，获得1击毙{句尾}")
                await user.add_jibi(1)
            user.data.save_status_time()
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDragoned: (Priority.OnDragoned.inv_bianhua, cls)}

class panjuea(_card):
    name = "最终判决α"
    id = 111
    description = "抽到时附加buff：最终判决α。你接龙后，将此buff传递给你接龙后第五次接龙的玩家。与最终判决β重合时，罪行加重，判处死刑。"
    positive = -1
    on_draw_status = 'A'
    is_debuff = True
    consumed_on_draw = True
    pack = Pack.ff14
class panjuea_s(_statusnull):
    id = 'A'
    des = "最终判决α：你下次接龙后，将此buff传递给你接龙后第五次接龙的玩家。与最终判决β重合时，罪行加重，判处死刑。"
    is_debuff = True
    @classmethod
    async def OnStatusAdd(cls, count: TCount, user: 'User', status: TStatusAll, count2: int) -> Tuple[int]:
        if status is panjueb_s or status is panjueb_activated_s:
            user.send_char(f"判决重合，被判处死刑，陷入无法战斗状态{句尾}")
            for i in range(min(count, count2)):
                await user.remove_status('A', remove_all=False)
            await user.add_limited_status(Swufazhandou(datetime.now() + timedelta(minutes=240)))
            return max(0, count2 - count),
        return count2,
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        user.log << f"的{count}个最终判决α激活了。"
        await user.remove_status('A', remove_all=True)
        await user.add_status('a', count=count)
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnStatusAdd: (Priority.OnStatusAdd.panjue, cls),
            UserEvt.OnDragoned: (Priority.OnDragoned.panjue, cls)}
class panjuea_activated_s(_statusnull):
    id = 'a'
    des = "最终判决α：将此buff传递给你上次接龙后第五次接龙的玩家。与最终判决β重合时，罪行加重，判处死刑。"
    is_debuff = True
    @classmethod
    async def OnStatusAdd(cls, count: TCount, user: 'User', status: TStatusAll, count2: int) -> Tuple[int]:
        if status is panjueb_s or status is panjueb_activated_s:
            user.send_char(f"判决重合，被判处死刑，陷入无法战斗状态{句尾}")
            for i in range(min(count, count2)):
                await user.remove_status('a', remove_all=False)
            await user.add_limited_status(Swufazhandou(datetime.now() + timedelta(minutes=240)))
            return max(0, count2 - count),
        return count2,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnStatusAdd: (Priority.OnStatusAdd.panjue_activated, cls)}

class panjueb(_card):
    name = "最终判决β"
    id = 112
    description = "抽到时附加buff：最终判决β。你接龙后，将此buff传递给你接龙后第五次接龙的玩家。与最终判决α重合时，罪行加重，判处死刑。"
    positive = -1
    on_draw_status = 'B'
    is_debuff = True
    consumed_on_draw = True
    pack = Pack.ff14
class panjueb_s(_statusnull):
    id = 'B'
    des = "最终判决β：你下次接龙后，将此buff传递给你接龙后第五次接龙的玩家。与最终判决α重合时，罪行加重，判处死刑。"
    is_debuff = True
    @classmethod
    async def OnStatusAdd(cls, count: TCount, user: 'User', status: TStatusAll, count2: int) -> Tuple[int]:
        if status is panjuea_s or status is panjuea_activated_s:
            user.send_char(f"判决重合，被判处死刑，陷入无法战斗状态{句尾}")
            for i in range(min(count, count2)):
                user.remove_status('B', remove_all=False)
            await user.add_limited_status(Swufazhandou(datetime.now() + timedelta(minutes=240)))
            return max(0, count2 - count),
        return count2,
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        user.log << f"的{count}个最终判决β激活了。"
        await user.remove_status('B', remove_all=True)
        await user.add_status('b', count=count)
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnStatusAdd: (Priority.OnStatusAdd.panjue, cls),
            UserEvt.OnDragoned: (Priority.OnDragoned.panjue, cls)}
class panjueb_activated_s(_statusnull):
    id = 'b'
    des = "最终判决β：将此buff传递给你上次接龙后第五次接龙的玩家。与最终判决α重合时，罪行加重，判处死刑。"
    is_debuff = True
    @classmethod
    async def OnStatusAdd(cls, count: TCount, user: 'User', status: TStatusAll, count2: int) -> Tuple[int]:
        if status is panjuea_s or status is panjuea_activated_s:
            user.send_char(f"判决重合，被判处死刑，陷入无法战斗状态{句尾}")
            for i in range(min(count, count2)):
                await user.remove_status('b', remove_all=False)
            await user.add_limited_status(Swufazhandou(datetime.now() + timedelta(minutes=240)))
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
                user.log << f"从五个人前面接来了{na}个最终判决α。"
                await user.add_status('a', count=na)
            if nb := u.check_status('b'):
                await u.remove_status('b')
                user.log << f"从五个人前面接来了{nb}个最终判决β。"
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
    async def BeforeDragoned(cls, count: TCount, user: 'User', state: DragonState) -> Tuple[bool, int, str]:
        return False, 0, f'你无法战斗，不能接龙{句尾}'
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

class dadiyaodong(_card):
    id = 113
    name = "大地摇动"
    description = "抽到时附加全局buff：今天每个分支最后接龙的第2,5,8,11,14个人每人扣除4击毙。"
    positive = -1
    newer = 7
    pack = Pack.ff14
    consumed_on_draw = True
    on_draw_global_status = '!'
class dadiyaodong_s(_statusnull):
    id = '!'
    des = "大地摇动：今天每个分支最后接龙的第2,5,8,11,14个人每人扣除4击毙。"
    is_debuff = True
    is_global = True
    @classmethod
    async def OnNewDay(cls, count: TCount, user: 'User') -> Tuple[()]:
        to_send = Counter()
        for branch in Tree._objs:
            if len(branch) == 0:
                continue
            end = branch[-1]
            for i in range(1, 15, 3):
                tr = end.before(i)
                if tr is not None and tr.id != (0, 0):
                    to_send[tr.qq] += 1
        if len(to_send) != 0:
            for qq, count in to_send.items():
                user.buf.send(f"玩家{qq}因大地摇动被扣除{4 * count}击毙{句尾}")
                await User(qq, user.buf).add_jibi(-4 * count)
        await Userme(user).remove_status('!', remove_all=False)
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnNewDay: (Priority.OnNewDay.dadiyaodong, cls)}
newday_check[0] |= set('!')

class dihuopenfa(_card):
    name = "地火喷发"
    id = 114
    description = "今天所有的接龙词都有10%的几率变成地雷。"
    positive = 0
    global_daily_status = 'B'
    pack = Pack.ff14
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
    pack = Pack.ff14
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
    pack = Pack.ff14
class shenmouyuanlv_s(_statusnull):
    id = 'n'
    des = "深谋远虑之策：当你一次使用/损失了超过你现有击毙一半以上的击毙时，恢复这些击毙。"
    @classmethod
    async def OnJibiChange(cls, count: TCount, user: 'User', jibi: int, is_buy: bool) -> Tuple[int]:
        if jibi < 0 and -jibi > user.data.jibi / 2:
            await user.remove_status('n', remove_all=False)
            user.send_char(f"触发了深谋远虑之策的效果，此次免单{句尾}")
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
    pack = Pack.ff14
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
    pack = Pack.ff14
    @classmethod
    def weight(cls, user: User):
        if user.check_daily_status('d'):
            return 1 + user.data.luck / 2
        return 1
    @classmethod
    async def use(cls, user: User) -> None:
        for c in map(StatusDaily, user.data.daily_status):
            if c is shengbing:
                user.send_char(f"的大病一场被取消了{句尾}")
                await user.remove_daily_status('d', remover=user)
                return
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
            if status.is_debuff and status.id != 'd' and status.removeable and not isinstance(status, Swufazhandou):
                if i.num >= count2:
                    i.num -= count2
                    user.send_log(f"触发了凯歌的效果，免除此负面状态{句尾}")
                    user.data.save_status_time()
                    return 0,
                else:
                    count2 -= i.num
                    i.num = 0
                    user.send_log(f"触发了凯歌的效果，免除此负面状态{句尾}")
                    continue
            elif status is shengbing and i.num == 3:
                i.num -= 3
                user.send_log(f"触发了凯歌的效果，免除大病一场{句尾}")
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
    pack = Pack.toaru
class imaginebreaker_s(_statusnull):
    id = '0'
    des = "幻想杀手：你的下一次攻击无视对方的所有反制效果，下一次目标为你的攻击无效。以上两项只能发动一项。"
    @classmethod
    async def OnAttack(cls, count: TCount, user: 'User', attack: 'Attack') -> Tuple[bool]:
        async def pierce_f():
            user.send_char(f"触发了幻想杀手的效果，无视了对方的反制{句尾}")
            user.log << f"{user.char}触发了幻想杀手（攻击）的效果。"
            await user.remove_status('0', remove_all=False)
            return True
        attack.counter.pierce = async_data_saved(pierce_f)
        return False,
    @classmethod
    async def OnAttacked(cls, count: TCount, user: 'User', attack: 'Attack') -> Tuple[bool]:
        if await attack.counter.pierce():
            attack.counter.pierce = nothing
            user.buf.send("但", end='')
            user.send_log(f"触发了幻想杀手的效果，防住了对方的攻击{句尾}")
            return False,
        user.send_log(f"触发了幻想杀手的效果，防住了对方的攻击{句尾}")
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
    pack = Pack.toaru
class vector_s(_statusnull):
    id = 'v'
    des = "矢量操作：你的下一次攻击效果加倍，下一次对你的攻击反弹至攻击者，免除你下一次触雷。以上三项只能发动一项。"
    @classmethod
    async def OnAttack(cls, count: TCount, user: 'User', attack: 'Attack') -> Tuple[bool]:
        if attack.doublable:
            user.send_log(f"触发了矢量操作的效果，攻击加倍{句尾}")
            await user.remove_status('v', remove_all=False)
            return attack.double(),
        return False,
    @classmethod
    async def OnAttacked(cls, count: TCount, user: 'User', attack: 'Attack') -> Tuple[bool]:
        if await attack.counter.pierce():
            await user.remove_status('v', remove_all=True, remover=attack.attacker)
            user.send_log(f"矢量操作的效果被幻想杀手消除了{句尾}")
            return False,
        if attack.reboundable:
            await user.remove_status('v', remove_all=False)
            user.send_log(f"触发了矢量操作的效果，反弹了对方的攻击{句尾}")
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

class youxianshushi(_card):
    id = 123
    name = "优先术式"
    positive = 0
    description = "今天所有攻击效果都变为击杀，礼物交换无效。"
    global_daily_status = 'y'
    newer = 7
    pack = Pack.toaru
class youxianshushi_s(_statusdaily):
    id = 'y'
    is_global = True
    des = "优先术式：今天所有攻击效果都变为击杀，礼物交换无效。"
    @classmethod
    async def OnAttack(cls, count: TCount, user: 'User', attack: 'Attack') -> Tuple[bool]:
        if await attack.counter.pierce():
            await Userme(user).remove_daily_status('y', remove_all=True, remover=attack.attacker)
            user.send_log(f"优先术式的效果被幻想杀手消除了{句尾}")
            return False,
        elif isinstance(attack, ALiwujiaohuan):
            if user.buf.state.get("liwujiaohuan_invalid_sent"):
                user.buf.state["liwujiaohuan_invalid_sent"] = True
                user.buf.send("由于优先术式，礼物交换无效" + 句尾)
            return True,
        elif not isinstance(attack, (Damage, Kill)):
            user.log << "由于优先术式，攻击变成击杀" + 句尾
            user.buf.send("由于优先术式，攻击变成击杀" + 句尾)
            atk_new = Kill(attack.attacker, attack.defender, 120)
            await attack.defender.attacked(attack.attacker, atk_new)
            return True,
        return False,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnAttack: (Priority.OnAttack.youxianshushi, cls)}

class xixueshashou(_card):
    name = "吸血杀手"
    id = 124
    positive = 1
    description = "今天你每次接龙时有10%几率获得一张【吸血鬼】。"
    daily_status = 'x'
    pack = Pack.toaru
class xixueshashou_s(_statusdaily):
    id = 'x'
    des = "吸血杀手：今天你每次接龙时有10%几率获得一张【吸血鬼】。"
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        for i in range(count):
            if random.random() < 0.1 + 0.01 * user.data.luck:
                user.buf.send(f"你获得了一张【吸血鬼】{句尾}")
                await user.draw(0, cards=[Card(-2)])
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDragoned: (Priority.OnDragoned.xixueshashou, cls)}

class railgun(_card):
    id = 125
    name = "超电磁炮"
    description = "花费1击毙或者手牌中一张金属制的牌或者身上一个金属制的buff，选择一个与你接龙距离3以内（若选择的是金属则为5以内）的人击毙。目标身上的每个金属制buff有1/2的几率被烧掉。"
    pack = Pack.toaru
    newer = 7
    positive = 1
    failure_message = "使用此卡必须身上有弹药并且今天接过龙" + 句尾
    @classmethod
    def can_use(cls, user: User, copy: bool) -> bool:
        if user.qq not in [tree.qq for tree in itertools.chain(*itertools.chain(Tree._objs, *Tree.forests))]:
            return False
        if user.data.jibi != 0:
            return True
        cards = [d for d in user.data.hand_card if d.is_metallic]
        status_nulles = [s for s in user.data.status if StatusNull(s).is_metallic]
        status_dailyes = [s for s in user.data.daily_status if StatusDaily(s).is_metallic]
        statuses = [s for s in user.data.status_time_checked if s.is_metallic]
        return len(cards) + len(status_nulles) + len(status_dailyes) + len(statuses) != 0
    @classmethod
    async def use(cls, user: User) -> None:
        if await user.choose(flush=False):
            if user.qq not in [tree.qq for tree in itertools.chain(*itertools.chain(Tree._objs, *Tree.forests))]:
                user.send_log("今天没有接过龙，附近没有人可以击中" + 句尾)
                return False
            cards = [d for d in user.data.hand_card if d.is_metallic]
            status_nulles = [s for s in user.data.status if StatusNull(s).is_metallic]
            status_dailyes = [s for s in user.data.daily_status if StatusDaily(s).is_metallic]
            statuses = [s for s in user.data.status_time_checked if s.is_metallic]
            l = len(cards) + len(status_nulles) + len(status_dailyes) + len(statuses)
            to_choose: list[tuple[int, Any]] = []
            if user.data.jibi != 0:
                to_choose.append((0, "1击毙", ("击毙", "1击毙"), 0))
            to_choose.extend([(1, d.brief_description(), (str(d.id),), i) for i, d in enumerate(cards)])
            to_choose.extend([(2, name_f(StatusNull(d).des), (name_f(StatusNull(d).des),), i) for i, d in enumerate(status_nulles)])
            to_choose.extend([(3, name_f(StatusDaily(d).des), (name_f(StatusDaily(d).des),), i) for i, d in enumerate(status_dailyes)])
            to_choose.extend([(4, name_f(d.des), (name_f(d.des),), i) for i, d in enumerate(statuses)])
            if len(to_choose) == 0:
                user.send_log("没有弹药，无法发射" + 句尾)
                return
            elif len(to_choose) == 1:
                user.send_log("只有一个物品可发射，自动使用" + to_choose[0][1] + "作为弹药" + 句尾)
                num, st, _, count = to_choose[0]
            else:
                prompt = "请选择要发射的弹药，手牌请输入id，状态请输入全名，重新查询列表请输入“重新查询”。\n" + "\n".join(s for i, s, t, c in to_choose)
                def check(value: str):
                    if value == "重新查询":
                        _raise_failure(prompt)
                    for i, s, t, count in to_choose:
                        if value in t:
                            return (i, s, count)
                    _raise_failure("请选择一个在列表中的物品，重新查询列表请输入“重新查询”。")
                user.buf.send(prompt)
                await user.buf.flush()
                num, st, count = await user.buf.aget(prompt="", arg_filters=[
                    extractors.extract_text,
                    check_handcard(user),
                    check
                ])
            distance = 3 if num == 0 else 5
            allqq = set()
            for branches in Tree._objs:
                for node in branches:
                    if node.qq == user.qq:
                        for s in range(-distance, distance + 1):
                            for i in range(-(distance - abs(s)), distance - abs(s) + 1):
                                ret = Tree.find((node.id[0] + s, node.id[1] + i))
                                if ret is not None:
                                    allqq.add(ret.qq)
            allqq.remove(user.qq)
            prompt = f"请at群内一名玩家。\n与你距离{distance}以内的玩家有：\n" + "\n".join(str(q) for q in allqq)
            user.buf.send(prompt)
            await user.buf.flush()
            qq: int = (await user.buf.aget(prompt="",
                arg_filters=[
                        lambda s: [int(r) for r in re.findall(r'qq=(\d+)', str(s))],
                        validators.fit_size(1, 1, message="请at正确的人数。"),
                        validators.ensure_true(lambda q: q[0] in allqq, message=f"请at与你接龙距离{distance}以内的玩家：\n" + "\n".join(str(q) for q in allqq))
                    ]))[0]
            u = User(qq, user.buf)
            user.send_char("花费了" + st + "。")
            if num == 0:
                await user.add_jibi(-1)
            elif num == 1:
                await user.remove_cards([cards[count]])
            elif num == 2:
                await user.remove_status(status_nulles[count], remover=user)
            elif num == 3:
                await user.remove_daily_status(status_dailyes[count], remover=user)
            elif num == 4:
                await user.remove_limited_status(count, remover=user)
            atk = ARailgun(user, u)
            await u.attacked(user, atk)
class ARailgun(Attack):
    name = "超电磁炮"
    async def self_action(self):
        self.defender.death(120 * self.multiplier, killer = self.attacker)
        for d in self.defender.data.hand_card:
            if d.is_metallic and random.random() > (0.5 - 0.02 * self.attacker.data.luck) ** self.multiplier:
                self.defender.send_log(f"的{d.name}被烧掉了{句尾}")
                await self.defender.remove_cards([d])
        for s in self.defender.data.status:
            if StatusNull(s).is_metallic and random.random() > (0.5 - 0.02 * self.attacker.data.luck) ** self.multiplier:
                self.defender.send_log(f"的{name_f(StatusNull(s).des)}被烧掉了{句尾}")
                await self.defender.remove_status(s, remover=self.attacker)
        for s in self.defender.data.daily_status:
            if StatusDaily(s).is_metallic and random.random() > (0.5 - 0.02 * self.attacker.data.luck) ** self.multiplier:
                self.defender.send_log(f"的{name_f(StatusDaily(s).des)}被烧掉了{句尾}")
                await self.defender.remove_daily_status(s, remover=self.attacker)
        for s in self.defender.data.status_time_checked:
            if s.is_metallic and random.random() > (0.5 - 0.02 * self.attacker.data.luck) ** self.multiplier:
                self.defender.send_log(f"的{name_f(s.des)}被烧掉了{句尾}")
                await self.defender.remove_limited_status(s, remover=self.attacker)

class magnet(_card):
    id = 129
    name = "磁力菇"
    description = "种植植物磁力菇：有人攻击你时，随机移除其身上的一件金属制品，然后24小时不能发动。"
    positive = 1
    newer = 7
    pack = Pack.pvz
    is_metallic = True
    @classmethod
    async def use(self, user: User):
        await user.add_limited_status(magnet_s(datetime.now()))
class magnet_s(TimedStatus):
    id = 'G'
    des = "磁力菇：有人攻击你时，随机移除其身上的一件金属制品，然后24小时不能发动。"
    def check(self):
        return True
    def __str__(self) -> str:
        if self.time > datetime.now():
            delta = self.time - datetime.now()
            min = delta.seconds // 60
            return f"{self.des}\n\t充能时间：{f'{delta.days}日' if delta.days != 0 else ''}{f'{min // 60}时' if min // 60 != 0 else ''}{min % 60}分钟。"
        else:
            return f"{self.des}\n\t充能完毕。"
    @classmethod
    async def OnAttacked(cls, count: TCount, user: 'User', attack: 'Attack') -> Tuple[bool]:
        for c in count:
            if c.time <= datetime.now():
                user.send_log("发动了磁力菇的效果" + 句尾)
                c.time = datetime.now() + timedelta(days=1)
                atk = AMagnet(user, attack.attacker, c)
                await attack.attacker.attacked(user, atk)
                user.data.save_status_time()
                return False,
        return False,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnAttacked: (Priority.OnAttacked.magnet, cls)}
class AMagnet(Attack):
    name = "磁力菇吸走金属制品"
    doublable = False
    def __init__(self, attacker: 'User', defender: 'User', c: magnet_s):
        self.c = c
        super().__init__(attacker, defender)
    async def self_action(self):
        cards = [d for d in self.defender.data.hand_card if d.is_metallic]
        status_nulles = [s for s in self.defender.data.status if StatusNull(s).is_metallic]
        status_dailyes = [s for s in self.defender.data.daily_status if StatusDaily(s).is_metallic]
        statuses = [s for s in self.defender.data.status_time_checked if s.is_metallic]
        l = len(cards) + len(status_nulles) + len(status_dailyes) + len(statuses)
        if l == 0:
            self.defender.send_log("身上没有金属制品" + 句尾)
        else:
            i = random.choice(range(l))
            self.c.time = datetime.now() + timedelta(hours=24)
            self.attacker.send_char("的磁力菇移除了" + self.defender.char, end="")
            if i < len(cards):
                self.defender.buf.send("的手牌：" + cards[i].name)
                self.defender.log << "移除了手牌" + cards[i].brief_description()
                await self.defender.discard_cards([cards[i]])
                return
            i -= len(cards)
            if i < len(status_nulles):
                self.defender.buf.send("的状态：" + StatusNull(status_nulles[i]).brief_des)
                self.defender.log << "移除了永久状态" + status_nulles[i]
                await self.defender.remove_status(status_nulles[i], remover=self.attacker)
                return
            i -= len(status_nulles)
            if i < len(status_dailyes):
                self.defender.buf.send("的状态：" + StatusDaily(status_dailyes[i]).brief_des)
                self.defender.log << "移除了每日状态" + status_dailyes[i]
                await self.defender.remove_daily_status(status_dailyes[i], remover=self.attacker)
                return
            i -= len(status_dailyes)
            self.defender.buf.send("的状态：" + statuses[i].brief_des)
            self.defender.log << "移除了状态" + str(statuses[i])
            await self.defender.remove_limited_status(status_dailyes[i], remover=self.attacker)
            return

class sunflower(_card):
    name = "向日葵"
    id = 130
    description = "种植植物向日葵：跨日结算时你获得1击毙。场上最多存在十株(双子)向日葵。"
    status = '('
    positive = 1
    pack = Pack.pvz
class sunflower_s(_statusnull):
    id = '('
    des = "向日葵：跨日结算时你获得1击毙。场上最多存在十株(双子)向日葵。"
    @classmethod
    async def OnNewDay(cls, count: TCount, user: 'User') -> Tuple[()]:
        s = user.check_status(')')
        to_add = max(0, min(count + s, 10) - s)
        user.buf.send(f"玩家{user.qq}种下的向日葵产出了{to_add}击毙{句尾}")
        await user.add_jibi(to_add)
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnNewDay: (Priority.OnNewDay.sunflower, cls)}
class inv_sunflower_s(_statusnull):
    id = '['
    des = "背日葵：跨日结算时你损失1击毙。"
    @classmethod
    async def OnNewDay(cls, count: TCount, user: 'User') -> Tuple[()]:
        s = user.check_status(']')
        to_add = max(0, min(count + s, 10) - s)
        user.buf.send(f"玩家{user.qq}种下的背日葵使其损失了{to_add}击毙{句尾}")
        await user.add_jibi(-to_add)
        n = 0
        for i in range(count):
            if random.random() > 0.5:
                await user.remove_status('[', remove_all=False)
                n += 1
        user.buf.send(f"玩家{user.qq}的{n}朵背日葵转了过来{句尾}")
        for i in range(n):
            await user.add_status('(')
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnNewDay: (Priority.OnNewDay.inv_sunflower, cls)}
newday_check[0] |= set("()[]")

class wallnut(_card):
    name = "坚果墙"
    id = 131
    description = "种植植物坚果墙：为你吸收死亡时间总计4小时。重复使用将修补坚果墙。"
    positive = 1
    mass = 0.2
    pack = Pack.pvz
    @classmethod
    async def use(cls, user: User) -> None:
        o = user.check_limited_status('o', lambda x: not x.is_pumpkin)
        if len(o) > 0:
            o[0].num = 240
            user.data.save_status_time()
            user.send_log("修补了" + user.char + f"的坚果墙{句尾}")
        else:
            await user.add_limited_status(SAbsorb(240, False))
            user.send_log(f"种植了坚果墙{句尾}")
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
    async def OnDeath(cls, count: TCount, user: 'User', killer: 'User', time: int, c: TAttackType) -> Tuple[int, bool]:
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
            user.send_log(f"的南瓜头为{user.char}吸收了{m}分钟的死亡时间{句尾}", end='')
            if time == 0:
                user.send_char(f"没死{句尾}")
            else:
                user.buf.send("")
        if o1 is not None and time != 0:
            m = min(o1.num, time)
            o1 -= m
            time -= m
            user.send_log(f"的坚果墙为{user.char}吸收了{m}分钟的死亡时间{句尾}", end='')
            if time == 0:
                user.send_char(f"没死{句尾}")
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
    description = "抽到时种植寒冰菇：今天每个人都需要额外隔一个才能接龙。"
    consumed_on_draw = True
    on_draw_global_daily_status = 'i'
    pack = Pack.pvz
class iceshroom_s(_statusdaily):
    id = 'i'
    des = "寒冰菇：今天每个人都需要额外隔一个才能接龙。"
    is_debuff = True
    is_global = True
    @classmethod
    async def BeforeDragoned(cls, count: TCount, user: 'User', state: DragonState) -> Tuple[bool, int, str]:
        return True, 1, ""
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.BeforeDragoned: (Priority.BeforeDragoned.iceshroom, cls)}
class hotshroom_s(_statusdaily):
    id = 'I'
    des = "炎热菇：今天每个人都可以少隔一个接龙。"
    is_global = True
    @classmethod
    async def BeforeDragoned(cls, count: TCount, user: 'User', state: DragonState) -> Tuple[bool, int, str]:
        return True, -1, ""
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.BeforeDragoned: (Priority.BeforeDragoned.hotshroom, cls)}

class twinsunflower(_card):
    name = "双子向日葵"
    id = 133
    description = "只能在你场上存在向日葵时种植。使你的一株向日葵变成双子向日葵(跨日结算时你获得2击毙)。场上最多存在十株(双子)向日葵。"
    positive = 1
    failure_message = "你场地上没有“向日葵”" + 句尾
    pack = Pack.pvz
    @classmethod
    def can_use(cls, user: User, copy: bool) -> bool:
        return user.check_status('(') > 0
    @classmethod
    async def use(cls, user: User) -> None:
        if user.check_status('(') == 0:
            user.send_char(f"场地上没有“向日葵”{句尾}")
            return
        await user.remove_status('(', remove_all=False)
        await user.add_status(')')
        user.send_char(f"的一株“向日葵”变成了“双子向日葵”{句尾}")
class twinsunflower_s(_statusnull):
    id = ')'
    des = "双子向日葵：跨日结算时你获得2击毙。场上最多存在十株(双子)向日葵。"
    @classmethod
    async def OnNewDay(cls, count: TCount, user: 'User') -> Tuple[()]:
        user.buf.send(f"玩家{user.qq}种下的双子向日葵产出了{2 * min(count, 10)}击毙{句尾}")
        await user.add_jibi(2 * min(count, 10))
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnNewDay: (Priority.OnNewDay.twinsunflower, cls)}
class inv_twinsunflower_s(_statusnull):
    id = ']'
    des = "双子背日葵：跨日结算时你损失2击毙。"
    @classmethod
    async def OnNewDay(cls, count: TCount, user: 'User') -> Tuple[()]:
        user.buf.send(f"玩家{user.qq}种下的双子背日葵使其损失了{2 * min(count, 10)}击毙{句尾}")
        await user.add_jibi(-2 * min(count, 10))
        n = 0
        for i in range(count):
            if random.random() > 0.5:
                await user.remove_status(']', remove_all=False)
                n += 1
        user.buf.send(f"玩家{user.qq}的{n}朵双子背日葵转了过来{句尾}")
        for i in range(n):
            await user.add_status(')')
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnNewDay: (Priority.OnNewDay.inv_twinsunflower, cls)}

class pumpkin(_card):
    name = "南瓜保护套"
    id = 134
    description = "种植植物南瓜保护套：为你吸收死亡时间总计6小时。重复使用将修补南瓜保护套。可与坚果墙叠加。"
    positive = 1
    mass = 0.2
    pack = Pack.pvz
    @classmethod
    async def use(cls, user: User) -> None:
        o = user.check_limited_status('o', lambda x: x.is_pumpkin)
        if len(o) > 0:
            o[0].num = 360
            user.data.save_status_time()
            user.send_log("修补了" + user.char + f"的南瓜保护套{句尾}")
        else:
            await user.add_limited_status(SAbsorb(360, True))
            user.send_log(f"种植了南瓜保护套{句尾}")

class imitator(_card):
    name = "模仿者"
    id = 135
    positive = 0
    description = "你下一张抽到的卡会额外再给你一张。"
    status = 'i'
    pack = Pack.pvz
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
        user.send_log(f"触发了模仿者的效果，额外获得了卡牌{句尾}获得的卡牌是：")
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
    on_draw_send_char = "获得了玩偶匣" + 句尾
    consumed_on_draw = True
    is_metallic = True
    pack = Pack.pvz
class jack_in_the_box_s(_statusnull):
    id = 'j'
    des = "玩偶匣：你每次接龙时有5%的几率爆炸，炸死以你为中心5x5的人，然后buff消失。若场上有寒冰菇状态则不会爆炸。"
    is_debuff = True
    is_metallic = True
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        if Game.me.check_daily_status('i'):
            return
        if random.random() > 0.95 ** count:
            user.send_log(f"的玩偶匣爆炸了{句尾}")
            await user.remove_status('j', remove_all=False)
            qqs = {user.qq}
            id = branch.id
            for i, j in itertools.product(range(-2, 3), range(-2, 3)):
                ret = Tree.find((id[0] + i, id[1] + j))
                if ret is not None:
                    qqs.add(ret.qq)
            qqs -= {config.selfqq}
            user.send_char("炸死了" + "".join(f"[CQ:at,qq={qqq}]" for qqq in qqs) + 句尾)
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
    pack = Pack.pvz
    @classmethod
    async def on_draw(cls, user: User) -> None:
        if Game.me.check_daily_status('i'):
            user.buf.send(f"蹦极僵尸被寒冰菇冻住了{句尾}")
            user.log << f"蹦极僵尸被寒冰菇冻住了{句尾}"
        elif g := user.check_limited_status('G'):
            user.send_log(f"的磁力菇被偷走了{句尾}")
            await user.remove_limited_status(g[0])
        elif o := more_itertools.only(user.check_limited_status('o', lambda x: not x.is_pumpkin)):
            user.send_log(f"的坚果墙被偷走了{句尾}")
            await user.remove_limited_status(o)
        elif user.check_status(')'):
            user.send_log(f"的双子向日葵被偷走了{句尾}")
            await user.remove_status(')', remove_all=False)
        elif user.check_status('('):
            user.send_log(f"的向日葵被偷走了{句尾}")
            await user.remove_status('(', remove_all=False)
        elif p := more_itertools.only(user.check_limited_status('o', lambda x: x.is_pumpkin)):
            user.send_log(f"的南瓜头被偷走了{句尾}")
            await user.remove_limited_status(p)
        else:
            user.send_log(f"没有植物，蹦极僵尸放下了一只僵尸{句尾}")
            await user.death(minute=60)

class polezombie(_card):
    name = "撑杆跳僵尸"
    id = 138
    positive = -1
    description = "抽到时击毙你一次，此击毙不会被坚果墙或南瓜保护套阻挡。若场上有寒冰菇状态则不会生效。"
    consumed_on_draw = True
    pack = Pack.pvz
    @classmethod
    async def on_draw(cls, user: User) -> None:
        if Game.me.check_daily_status('i'):
            user.buf.send(f"撑杆跳僵尸被寒冰菇冻住了{句尾}")
            user.log << f"撑杆跳僵尸被寒冰菇冻住了{句尾}"
        else:
            await user.death(c=TAttackType(jump=True))

class mishi1(_card):
    name = "密教残篇"
    id = 140
    positive = 1
    newer = 5
    description = "获得正面状态“探索都城”，该系列效果同一玩家同时只能拥有一个。"
    pack = Pack.secret_history
    @classmethod
    async def use(cls, user: User) -> None:
        M = user.check_limited_status('M')
        if len(M) > 0:
            M[0].num = 1
            user.data.save_status_time()
            user.send_log(f"取消了之前的探索并开始探索都城{句尾}")
        else:
            await user.add_limited_status(Sexplore(1))
            user.send_log(f"开始探索都城{句尾}")
class mishi2(_card):
    name = "鬼祟的真相"
    id = 141
    positive = 1
    newer = 5
    description = "获得正面状态“探索各郡”，该系列效果同一玩家同时只能拥有一个。"
    pack = Pack.secret_history
    @classmethod
    async def use(cls, user: User) -> None:
        M = user.check_limited_status('M')
        if len(M) > 0:
            M[0].num = 2
            user.data.save_status_time()
            user.send_log(f"取消了之前的探索并开始探索各郡{句尾}")
        else:
            await user.add_limited_status(Sexplore(2))
            user.send_log(f"开始探索各郡{句尾}")
class mishi3(_card):
    name = "被遗忘的史籍"
    id = 142
    positive = 1
    newer = 5
    description = "获得正面状态“探索大陆”，该系列效果同一玩家同时只能拥有一个。"
    pack = Pack.secret_history
    @classmethod
    async def use(cls, user: User) -> None:
        M = user.check_limited_status('M')
        if len(M) > 0:
            M[0].num = 3
            user.data.save_status_time()
            user.send_log(f"取消了之前的探索并开始探索大陆{句尾}")
        else:
            await user.add_limited_status(Sexplore(3))
            user.send_log(f"开始探索大陆{句尾}")
class mishi4(_card):
    name = "禁断的史诗"
    id = 143
    positive = 1
    newer = 5
    description = "获得正面状态“探索森林尽头之地”，该系列效果同一玩家同时只能拥有一个。"
    pack = Pack.secret_history
    @classmethod
    async def use(cls, user: User) -> None:
        M = user.check_limited_status('M')
        if len(M) > 0:
            M[0].num = 4
            user.data.save_status_time()
            user.send_log(f"取消了之前的探索并开始森林尽头之地{句尾}")
        else:
            await user.add_limited_status(Sexplore(4))
            user.send_log(f"开始探索森林尽头之地{句尾}")
class mishi5(_card):
    name = "悬而未定的模棱两可"
    id = 144
    positive = 1
    newer = 5
    description = "获得正面状态“探索撕身山脉”，该系列效果同一玩家同时只能拥有一个。"
    pack = Pack.secret_history
    @classmethod
    async def use(cls, user: User) -> None:
        M = user.check_limited_status('M')
        if len(M) > 0:
            M[0].num = 5
            user.data.save_status_time()
            user.send_log(f"取消了之前的探索并开始探索撕身山脉{句尾}")
        else:
            await user.add_limited_status(Sexplore(5))
            user.send_log(f"开始探索撕身山脉{句尾}")
class mishi6(_card):
    name = "浪游旅人的地图"
    id = 145
    positive = 1
    newer = 5
    description = "获得正面状态“探索荒寂而平阔的沙地”，该系列效果同一玩家同时只能拥有一个。"
    pack = Pack.secret_history
    @classmethod
    async def use(cls, user: User) -> None:
        M = user.check_limited_status('M')
        if len(M) > 0:
            M[0].num = 6
            user.data.save_status_time()
            user.send_log(f"取消了之前的探索并开始探索荒寂而平阔的沙地{句尾}")
        else:
            await user.add_limited_status(Sexplore(6))
            user.send_log(f"开始探索荒寂而平阔的沙地{句尾}")
class mishi7(_card):
    name = "午港奇闻"
    id = 146
    positive = 1
    newer = 5
    description = "获得正面状态“探索薄暮群屿”，该系列效果同一玩家同时只能拥有一个。"
    pack = Pack.secret_history
    @classmethod
    async def use(cls, user: User) -> None:
        M = user.check_limited_status('M')
        if len(M) > 0:
            M[0].num = 7
            user.data.save_status_time()
            user.send_log(f"取消了之前的探索并开始探索薄暮群屿{句尾}")
        else:
            await user.add_limited_status(Sexplore(7))
            user.send_log(f"开始探索薄暮群屿{句尾}")
class Sexplore(NumedStatus):
    id = 'M'
    @property
    def des(self):
        i = self.num
        if i in range(1, 8):
            spot = ["都城", "各郡", "大陆", "森林尽头之地", "撕身山脉", "荒寂而平阔的沙地", "薄暮群屿"][self.num - 1]
            return f"探索{spot}：你将会触发一系列随机事件。"
        elif i == 8:
            return "探索薄暮群屿：你将会触发一系列随机事件。\n\t置身格里克堡：直到失去状态“探索薄暮群屿”，抵御所有死亡效果。"
    def __str__(self) -> str:
        return f"{self.des}"
    def double(self):
        return [self]
    @classmethod
    async def BeforeDragoned(cls, count: TCount, user: 'User', state: DragonState) -> Tuple[bool, int, str]:
        user.buf.state['mishi_id'] = i = random.randint(0, 5 if count[0].num <= 4 else 4)
        user.buf.state['dragon_who'] = user.qq
        if count[0].num <= 4 and i == 5 or count[0].num > 4 and i == 4:
            if random.random() < 0.1 * min(user.data.luck, 5):
                user.send_log("随机到了死亡，重新随机" + 句尾)
                user.buf.state['mishi_id'] = i = random.randint(0, 5 if count[0].num <= 4 else 4)
        if count[0].num == 1 and i == 1:
            user.send_log("置身被遗忘的密特拉寺：")
            user.buf.send("你在此地进行了虔诚（）的祈祷。如果你此次接龙因各种原因被击毙，减少0～10%的死亡时间。")
        elif count[0].num == 2 and i == 1:
            user.send_log("置身洛克伍德沼地：")
            user.buf.send("成真的神明或是在守望此地。如果你此次接龙被击毙，减少25%死亡时间。")
        elif count[0].num == 4 and i == 1:
            user.send_log("置身大公的城塞：")
            user.buf.send("他平复了许多人的干渴，最终又败给了自己的干渴。若你因本次接龙被击毙，减少50%的死亡时间。")
        elif count[0].num == 5 and i == 1:
            user.send_log("置身避雪神庙：")
            user.buf.send("神庙可以回避一些袭击。本次接龙不会因为一周内接龙过或是踩雷而被击毙，但也没有接龙成功。")
        return True, 0, ""
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        if (i := user.buf.state.get('mishi_id')) is None:
            i = random.randint(0, 5 if count[0].num <= 4 else 4)
        if count[0].num == 1:
            if i == 0:
                user.send_log("置身斯特拉斯科因的寓所：")
                user.buf.send("发现了一些稀有的收藏。抽取一张广告牌。")
                await user.draw(0, cards=[Card(94)])
            elif i == 1:
                pass
            elif i == 2:
                user.send_log("置身凯特与赫洛有限公司：")
                user.buf.send("你在因不明爆炸而荒废的大厦中可能寻得一些东西，或是失去一些东西。")
                if random.random() < 0.5:
                    user.send_char(f"获得了1击毙{句尾}")
                    await user.add_jibi(1)
                else:
                    user.send_char(f"损失了1击毙{句尾}")
                    await user.add_jibi(-1)
            elif i == 3:
                user.send_log("置身圣亚割尼医院：")
                user.buf.send("医院给了你活力。你在本日获得额外1次接龙获得击毙的机会。")
                user.data.today_jibi += 1
                config.logger.dragon << f"【LOG】用户{user.qq}增加了接龙击毙上限至{user.data.today_jibi}。"
            elif i == 4:
                user.send_log("置身许伦的圣菲利克斯之会众：")
                user.buf.send("你被虔诚的教徒们包围了，他们追奉启之法则。你下一次接龙需要进行首尾接龙。")
                await user.add_status('J')
            else:
                user.send_log("置身荒废的河岸街：")
                user.buf.send("你掉进了河里。被击毙15分钟，并失去状态“探索都城”。")
                count[0].num = 0
                await user.death(15)
                user.data.save_status_time()
        elif count[0].num == 2:
            if i == 0:
                user.send_log("置身格拉德温湖：")
                user.buf.send("此处有蛇群把守。下一个接龙的人需要进行首尾接龙。")
                await Userme(user).add_status('|')
            elif i == 1:
                pass
            elif i == 2:
                user.send_log("置身克罗基斯山丘：")
                user.buf.send("守望此地之人将充满伤疤。今天你每死亡一次便获得2击毙。")
                await user.add_daily_status('S')
            elif i == 3:
                user.send_log("置身凯格琳的财宝：")
                user.buf.send("这里曾经是银矿，再下面则是具名者的藏匿。获得5击毙，然后抽取一张非正面卡片并立即使用。")
                await user.add_jibi(5)
                await user.draw_and_use(positive={0, -1})
            elif i == 4:
                user.send_log("置身高威尔旅馆：")
                user.buf.send("藏书室非常隐蔽。25%概率抽一张卡。")
                if random.random() < 0.25:
                    await user.draw(1)
            else:
                user.send_log("置身凯尔伊苏姆：")
                user.buf.send("你在最后一个房间一念之差被困住了。被击毙30分钟，并失去状态“探索各郡”。")
                count[0].num = 0
                await user.death(30)
                user.data.save_status_time()
        elif count[0].num == 3:
            if i == 0:
                user.send_log("置身拉维林城堡：")
                user.buf.send("住在这里的曾是太阳王的后裔。随机解除你的一个负面效果。")
                l = [s for s in itertools.chain(map(StatusNull, user.data.status), map(StatusDaily, user.data.daily_status), user.data.status_time_checked) if s.is_debuff]
                if len(l) == 0:
                    user.send_log(f"没有负面状态{句尾}")
                else:
                    c = random.choice(l)
                    if isinstance(c, type) and isinstance(c(), _statusnull):
                        user.send_char(f"的{c.des[:c.des.index('：')]}被取消了{句尾}")
                        await user.remove_status(c.id, remove_all=False)
                    elif isinstance(c, type) and isinstance(c(), _statusdaily):
                        user.send_char(f"的{c.des[:c.des.index('：')]}被取消了{句尾}")
                        await user.remove_daily_status(c.id, remove_all=False)
                    elif isinstance(c, _status):
                        des = c.des
                        user.send_log(f"的{des[:des.index('：')]}被取消了{句尾}")
                        await user.remove_limited_status(c)
                        user.data.save_status_time()
            elif i == 1:
                user.send_log("置身费米尔修道院：")
                user.buf.send("僧侣信奉象征欲望的杯之准则。失去5击毙，然后你今天每次接龙额外获得1击毙。")
                await user.add_jibi(-5)
                await user.add_daily_status('C')
            elif i == 2:
                user.send_log("置身俄尔托斯树林：")
                user.buf.send("你目睹了群鸦的回忆。触发本日内曾被使用过的一张卡片的效果。")
                if len(global_state['used_cards']) == 0:
                    user.send_log(f"今日没有使用过卡牌{句尾}")
                else:
                    c = Card(random.choice(global_state['used_cards']))
                    user.send_log(f"遇见的群鸦选择了卡牌{c.name}。")
                    await user.use_card_effect(c)
            elif i == 3:
                user.send_log("置身范德沙夫收藏馆：")
                user.buf.send("严密把守的储藏室中有不吉利的宝物。获得10击毙，并触发你手牌中一张非正面卡牌的效果。如果你的手中没有非正面卡牌，则将一张“邪恶的间谍行动～执行”置入你的手牌。")
                await user.add_jibi(10)
                cs = [c for c in user.data.hand_card if c.positive != 1]
                if len(cs) == 0:
                    user.send_log("手上没有非正面卡牌。")
                    await user.draw(0, cards=[Card(-1)])
                else:
                    card = random.choice(cs)
                    user.send_log(f"触发的宝物选择了卡牌{card.name}。")
                    await user.use_card_effect(card)
            elif i == 4:
                user.send_log("置身钥匙猎人的阁楼：")
                user.buf.send("我们听说了一名狩猎空想之钥的古怪猎人所著的一小批古怪书籍。你今天获得额外五次接龙机会。")
                user.data.today_jibi += 5
                config.logger.dragon << f"【LOG】用户{user.qq}增加了接龙击毙上限至{user.data.today_jibi}。"
            else:
                user.send_log("置身一望无际的巨石阵：")
                user.buf.send("当无月之夜来临，当地人会补充残留下的东西。被击毙60分钟，并失去状态“探索大陆”。")
                count[0].num = 0
                await user.death(60)
                user.data.save_status_time()
        elif count[0].num == 4:
            if i == 0:
                user.send_log("置身蜡烛岩洞：")
                user.buf.send("岩洞的内部出乎意料地明亮。你下一次接龙只需要相隔一个人。")
                await user.add_status('L')
            elif i == 1:
                pass
            elif i == 2:
                user.send_log("置身格吕内瓦尔德的常驻马戏团：")
                user.buf.send("马戏团众人在每个地方都贴满了写满图标的纸张，这个地方散发着虚界的气息。你的下一次接龙不受全局状态的影响。")
                await user.add_status('%')
            elif i == 3:
                user.send_log("置身瑞弗克塔楼：")
                user.buf.send("你们离去时，残塔消失了。清除上一个添加的全局状态。")
                if len(global_state['global_status']) == 0:
                    user.send_log(f"没有可以清除的全局状态{句尾}")
                else:
                    ss = global_state['global_status'][-1]
                    if ss[0] == 0 and Game.me.check_status(ss[1]):
                        sdes = StatusNull(ss[1]).des
                        user.send_log(f"移除了{sdes[:sdes.index('：')]}。")
                        await Userme(user).remove_status(ss[1], remove_all=False, remover=user)
                    elif ss[0] == 1 and Game.me.check_daily_status(ss[1]):
                        sdes = StatusDaily(ss[1]).des
                        user.send_log(f"移除了{sdes[:sdes.index('：')]}。")
                        await Userme(user).remove_daily_status(ss[1], remove_all=False, remover=user)
                    elif ss[0] == 2 and (gl := 
                            Userme(user).check_limited_status((sl := eval(ss[1]).id), lambda c: repr(c) == ss[1])):
                        sdes = gl[0].des
                        user.send_log(f"移除了{sdes[:sdes.index('：')]}。")
                        await Userme(user).remove_limited_status(gl[0], remover=user)
                    else:
                        user.buf.send(f"上一个添加的全局状态早就被清除了{句尾}")
                        user.log << "上一个添加的全局状态早就被清除了。"
            elif i == 4:
                user.send_log("置身库兹涅佐夫的捐赠：")
                user.buf.send("库兹涅佐夫公爵将他沾满鲜血的财富的四分之一捐给这座地方大学以建立末世学学部。随机添加一个全局状态。")
                i = random.random()
                if i < 0.5:
                    while True:
                        s = random.choice(list(_statusnull.id_dict.keys()))
                        if StatusNull(s).is_global:
                            break
                    await Userme(user).add_status(s)
                    t = StatusNull(s)
                    user.send_log(f"添加了全局状态{t.des[:t.des.index('：')]}。")
                else:
                    while True:
                        s = random.choice(list(_statusdaily.id_dict.keys()))
                        if StatusDaily(s).is_global:
                            break
                    await Userme(user).add_daily_status(s)
                    t = StatusDaily(s)
                    user.send_log(f"添加了全局状态{t.des[:t.des.index('：')]}。")
            else:
                user.send_log("置身狐百合原野：")
                user.buf.send("我们将布浸入氨水，蒙在脸上，以抵抗狐百合的香气。即便这样，我们仍然头晕目眩，身体却对各种矛盾的欲望作出回应。被击毙90分钟，并失去状态“探索森林尽头之地”。")
                count[0].num = 0
                await user.death(90)
                user.data.save_status_time()
        elif count[0].num == 5:
            if i == 0:
                user.send_log("置身猎手之穴：")
                user.buf.send("在这里必须隐藏自己。上一个人下一次接龙需要间隔三个人。")
                pq = branch.parent.qq
                if pq != config.selfqq and pq != 0:
                    User(pq, user.buf).add_status('&')
                else:
                    user.send_log(f"无上一个接龙的玩家{句尾}")
            elif i == 1:
                if not user.buf.state.get("branch_removed"):
                    user.buf.state["branch_removed"] = True
                    branch.remove()
                    from .logic_dragon import rewrite_log_file
                    rewrite_log_file()
                user.buf.send("不，你的接龙失败了。")
            elif i == 2:
                user.send_log("置身伊克玛维之眼：")
                user.buf.send("这里是观星台，是大地的眼睛。公开揭示今天一个隐藏奖励词，该效果每天只会触发一次。")
                if not global_state['observatory']:
                    from .logic_dragon import hidden_keyword
                    user.buf.send("你揭示的一个隐藏奖励词是：" + random.choice(hidden_keyword))
                    global_state['observatory'] = True
                else:
                    user.buf.send(f"今天已经触发过观星台{句尾}")
            elif i == 3:
                user.send_log("置身石狼陵墓：")
                user.buf.send("送葬者不见踪影，而死者被引来此处。本次接龙额外获得10击毙。")
                await user.add_jibi(10)
            else:
                user.send_log("置身无影众王的墓群：")
                user.buf.send("众王皆向往不死，而仅有一人实现了愿望，其他人只留下了陪葬品。立刻被击毙120分钟，并失去状态“探索撕身山脉”。")
                count[0].num = 0
                await user.death(120)
                user.data.save_status_time()
        elif count[0].num == 6:
            if i == 0:
                user.send_log("置身被星辰击碎的神殿：")
                user.buf.send("掉落的陨石反而成了朝拜的对象。在你之后接龙的一个人会额外获得5击毙。")
                await Userme(user).add_status('^')
            elif i == 1:
                user.send_log("置身拉贡之墓：")
                user.buf.send("曾经不死的长生者的尸体被保存得很好，直到我们到来。击毙上一个接龙的玩家十五分钟。")
                pq = branch.parent.qq
                if pq != config.selfqq and pq != 0:
                    await User(pq, user.buf).death(15)
                else:
                    user.send_log(f"无上一个接龙的玩家{句尾}")
            elif i == 2:
                user.send_log("置身墨萨拿：")
                user.buf.send("村民们拥有超过自然限度的长寿。获得状态“长生的宴席”。")
                await user.add_limited_status(Schangsheng(120))
            elif i == 3:
                user.send_log("置身七蟠寺：")
                user.buf.send("这座寺庙存在于每一重历史之中。你将于今天结束的正面状态延长至明天。")
                await user.add_daily_status('l')
            else:
                user.send_log("置身弥阿：")
                user.buf.send("有时是我们寻到死者拥有的知识，有时是死者寻到我们。被击毙180分钟，并失去状态“探索荒寂而平阔的沙地”。")
                count[0].num = 0
                await user.death(180)
                user.data.save_status_time()
        elif count[0].num == 7 or count[0].num == 8:
            if i == 0:
                user.send_log("置身渡鸦屿：")
                user.buf.send("索奎焰特在洞壁上用一百种语言描述他们悲惨的历史。获得一个可以完成10次的新任务，每次可以获得2击毙。")
                await user.add_limited_status(SQuest(10, 2, n := get_mission()))
                user.send_char(f"获得了一个任务：{mission[n][1]}")
            elif i == 1:
                user.send_log("置身格里克堡：")
                user.buf.send("帝国和岛屿没有在任何正史中出现过，但岛上总督的堡垒还在，或许他本人也是。直到失去状态“探索薄暮群屿”，抵御所有死亡效果。")
                count[0].num = 8
                user.data.save_status_time()
            elif i == 2:
                user.send_log("置身克丽斯塔贝号船骸：")
                user.buf.send("一头海兽来向这艘船求爱，但当船不回应这份爱慕时，海兽击碎了它。选择一张手牌弃置，然后抽两张正面卡牌。")
                async with user.choose_cards("请选择你手牌中的一张牌弃置，输入id号。", 1, 1) as l, check_active(l):
                    await user.discard_cards([Card(l[0])])
                await user.draw(2, positive={1})
            elif i == 3:
                user.send_log("置身深邃之门的圣滕特雷托之僧院：")
                user.buf.send("僧院危悬在崖边，它早该坠入海中了。从以下三个效果中随机触发一个：获得20击毙、抽一张牌或随机弃置一张牌。")
                j = random.randint(0, 2)
                if j == 0:
                    user.send_log(f"获得了20击毙{句尾}")
                    await user.add_jibi(20)
                elif j == 1:
                    user.send_log(f"抽了一张卡{句尾}")
                    await user.draw(1)
                elif len(user.data.hand_card) == 0:
                    user.send_log(f"无手牌可弃{句尾}")
                else:
                    cd = random.choice(user.data.hand_card)
                    user.send_log(f"丢弃了{cd.name}{句尾}")
                    await user.discard_cards([cd])
            else:
                user.send_log("置身午港：")
                user.buf.send("这座名为“午”的小小岛港是不死者的流放地。被击毙240分钟，并失去状态“探索薄暮群屿”。")
                count[0].num = 0
                await user.death(240)
                user.data.save_status_time()
        else:
            count[0].num = 0
            user.data.save_status_time()
        user.buf.state.pop('mishi_id')
    @classmethod
    async def OnDeath(cls, count: TCount, user: 'User', killer: 'User', time: int, c: TAttackType) -> Tuple[int, bool]:
        i = user.buf.state.get('mishi_id') # maybe None
        if user.buf.state.get('dragon_who') != user.qq:
            return time, False
        if count[0].num == 1 and i == 1:
            if await c.pierce():
                user.send_log(f"被遗忘的密特拉寺的效果被幻想杀手消除了{句尾}")
                return time, False
            s = random.random() * 0.1
            user.send_log(f"触发了被遗忘的密特拉寺的效果，死亡时间减少了{s * 100:.2f}%{句尾}")
            return (1 - s) * time, False
        elif count[0].num == 2 and i == 1:
            if await c.pierce():
                user.send_log(f"洛克伍德沼地的效果被幻想杀手消除了{句尾}")
                return time, False
            user.send_log(f"触发了洛克伍德沼地的效果，死亡时间减少了25%{句尾}")
            return 0.75 * time, False
        elif count[0].num == 4 and i == 1:
            if await c.pierce():
                user.send_log(f"大公的城塞的效果被幻想杀手消除了{句尾}")
                return time, False
            user.send_log(f"触发了大公的城塞的效果，死亡时间减少了50%{句尾}")
            return 0.5 * time, False
        elif count[0].num == 5 and i == 1:
            if await c.pierce():
                user.send_log(f"避雪神庙的效果被幻想杀手消除了{句尾}")
                return time, False
            user.send_log(f"触发了避雪神庙的效果，回避了死亡{句尾}")
            return 0, True
        elif count[0].num == 8:
            if await c.pierce():
                user.send_log(f"堡垒的效果被幻想杀手消除了{句尾}")
                count[0].num = 7
                user.data.save_status_time()
                return time, False
            else:
                user.send_log(f"触发了堡垒的效果，免除死亡{句尾}")
                return time, True
        return time, False
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.BeforeDragoned: (Priority.BeforeDragoned.explore, cls),
            UserEvt.OnDragoned: (Priority.OnDragoned.explore, cls),
            UserEvt.OnDeath: (Priority.OnDeath.explore, cls)}

class Sjiaotu(_statusnull):
    id = 'J'
    des = "置身许伦的圣菲利克斯之会众：被虔诚的教徒们包围，他们追奉启之法则，你下一次接龙需要进行首尾接龙。"
    is_debuff = True
    @classmethod
    async def BeforeDragoned(cls, count: TCount, user: User, state: DragonState) -> Tuple[bool, int, str]:
        if not await state.require_shouwei(user):
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
    async def BeforeDragoned(cls, count: TCount, user: User, state: DragonState) -> Tuple[bool, int, str]:
        if not await state.require_weishou(user):
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
    async def BeforeDragoned(cls, count: TCount, user: User, state: DragonState) -> Tuple[bool, int, str]:
        if not await state.require_shouwei(user):
            return False, 0, "蛇群阻止了你的非首尾接龙，接龙失败。"
        return True, 0, ""
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        await Userme(user).remove_status('|', remove_all=False)
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
    async def BeforeDragoned(cls, count: TCount, user: User, state: DragonState) -> Tuple[bool, int, str]:
        if not await state.require_weishou(user):
            return False, 0, "蛇群阻止了你的非尾首接龙，接龙失败。"
        return True, 0, ""
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        await Userme(user).remove_status('/', remove_all=False)
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.BeforeDragoned: (Priority.BeforeDragoned.invshequn, cls),
            UserEvt.OnDragoned: (Priority.OnDragoned.invshequn, cls)}
class Sshangba(_statusdaily):
    id = 'S'
    des = "伤疤：今天你每死亡一次便获得2击毙。"
    @classmethod
    async def OnDeath(cls, count: TCount, user: User, killer: User, time: int, c: TAttackType) -> Tuple[int, bool]:
        if await c.pierce():
            user.send_log(f"伤疤的效果被幻想杀手消除了{句尾}")
            await user.remove_status('S', remover=killer)
        else:
            user.send_log(f"触发了伤疤{句尾}奖励{2 * count}击毙。")
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
    async def OnDeath(cls, count: TCount, user: User, killer: User, time: int, c: TAttackType) -> Tuple[int, bool]:
        if await c.pierce():
            user.send_log(f"反转-伤疤的效果被幻想杀手消除了{句尾}")
            await user.remove_status('P', remover=killer)
        else:
            user.send_log(f"触发了反转-伤疤{句尾}失去{2 * count}击毙。")
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
        user.send_char(f"因为杯之准则额外获得{count}击毙{句尾}")
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
        user.send_char(f"因为反转-杯之准则额外失去{count}击毙{句尾}")
        await user.add_jibi(-1*count)
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDragoned: (Priority.OnDragoned.invbeizhizhunze, cls)}
class Slazhuyandong(_statusnull):
    id = 'L'
    des = "置身蜡烛岩洞：下一次接龙可以少间隔一个人。"
    @classmethod
    async def BeforeDragoned(cls, count: TCount, user: User, state: DragonState) -> Tuple[bool, int, str]:
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
    async def BeforeDragoned(cls, count: TCount, user: User, state: DragonState) -> Tuple[bool, int, str]:
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
    async def BeforeDragoned(cls, count: TCount, user: User, state: DragonState) -> Tuple[bool, int, str]:
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
    async def BeforeDragoned(cls, count: TCount, user: User, state: DragonState) -> Tuple[bool, int, str]:
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
        user.send_log(f"因星辰击碎的神殿额外获得{5 * count}击毙{句尾}")
        await Userme(user).remove_status('^')
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
        user.send_log(f"因反转-置身被星辰击碎的神殿额外失去{5*count}击毙{句尾}")
        await Userme(user).remove_status('$')
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
    async def OnDeath(cls, count: TCount, user: 'User', killer: 'User', time: int, c: TAttackType) -> Tuple[int, bool]:
        for i in count:
            m = min(i.num, time)
            i.num -= m
            time -= m
            user.send_log(f"的长生的宴席为{user.char}吸收了{m}分钟的死亡时间{句尾}", end='')
            if time == 0:
                user.send_char(f"没死{句尾}")
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

class mindgap(_card):
    id = 150
    name = "小心空隙"
    description = "今天接龙时有20%几率被神隐，被神隐的词消失，接龙人需再等待两个词才可接龙。"
    global_daily_status = 'z'
    positive = 0
    newer = 7
    pack = Pack.misc
class mindgap_s(_statusdaily):
    id = 'z'
    des = "小心空隙：今天接龙时有20%几率被神隐，被神隐的词消失，接龙人需再等待两个词才可接龙。"
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        if random.random() < 0.2:
            user.send_log("的接龙词被神隐了，需再等待两个词才可接龙。" + 句尾)
            l = user.check_limited_status('n', lambda s: s.length == 3)
            if len(l) == 0:
                await user.add_limited_status(SNoDragon([branch.parent.id_str], 3))
            else:
                l[0].list.append(branch.parent.id_str)
            user.data.save_status_time()
            if not user.buf.state.get("branch_removed"):
                user.buf.state["branch_removed"] = True
                branch.remove()
                from .logic_dragon import rewrite_log_file
                rewrite_log_file()
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDragoned: (Priority.OnDragoned.mindgap, cls)}

class steamsummer(_card):
    name = "Steam夏季特卖"
    id = 151
    positive = 1
    status = 'S'
    description = "你下一次购物花费减少50%。"
    pack = Pack.misc
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
    is_metallic = True
    mass = 0.2
    pack = Pack.misc
class forkbomb_s(_statusdaily):
    id = 'b'
    des = "Fork Bomb：今天每个接龙词都有5%几率变成分叉点。"
    is_global = True
    is_metallic = True
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        if (c := random.random()) > (0.95 - 0.005 * user.data.luck) ** count:
            if c < 0.95 ** count:
                user.buf.send("幸运地", end='')
            user.send_log(f"触发了Fork Bomb，此词变成了分叉点{句尾}")
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
    pack = Pack.misc
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
                user.send_char(f"触发了{f'{count}次' if count > 1 else ''}北京市政交通一卡通的效果，花费击毙打了8折变为{jibi}{句尾}")
            elif 150 <= user.data.spend_shop < 400:
                jibi = int(jibi * 0.5 ** count)
                user.send_char(f"触发了{f'{count}次' if count > 1 else ''}北京市政交通一卡通的效果，花费击毙打了5折变为{jibi}{句尾}")
            elif user.data.spend_shop >= 400:
                user.send_char(f"今日已花费400击毙，不再打折{句尾}")
            user.log << f"触发了{count}次北京市政交通一卡通的效果，花费击毙变为{jibi}。"
        return jibi,
    @classmethod
    def register(cls):
        return {UserEvt.OnJibiChange: (Priority.OnJibiChange.beijingcard, cls),
            UserEvt.CheckJibiSpend: (Priority.CheckJibiSpend.beijingcard, cls)}

class timebomb(_card):
    name = "定时炸弹"
    id = 154
    positive = -1
    description = "抽到时附加buff：需要此后在今日内完成10次接龙，否则在跨日时扣除2*剩余次数的击毙。"
    newer = 5
    consumed_on_draw = True
    is_metallic = True
    on_draw_limited_status = 'B'
    limited_init = (10,)
    pack = Pack.misc
class Stimebomb(NumedStatus):
    id = 'B'
    des = "定时炸弹：需要此后在今日内完成10次接龙，否则在跨日时扣除2*剩余次数的击毙。"
    is_debuff = True
    is_metallic = True
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        count[0].num -= 1
        user.data.save_status_time()
    @classmethod
    async def OnNewDay(cls, count: TCount, user: 'User') -> Tuple[()]:
        b = 2 * count[0].num
        user.send_log(f"因为定时炸弹失去了{b}击毙{句尾}")
        await user.add_jibi(-b)
        count[0].num = 0
        user.data.save_status_time()
    @classmethod
    def register(cls):
        return {UserEvt.OnDragoned: (Priority.OnDragoned.timebomb, cls),
            UserEvt.OnNewDay: (Priority.OnNewDay.timebomb, cls)}
newday_check[2].add('B')

class cashprinter(_card):
    name = "印钞机"
    id = 155
    positive = 1
    description = "使用后，你接下来10次接龙时会奖励接了上一个词的人1击毙。如果上一个词是起始词则不消耗生效次数。"
    newer = 5
    is_metallic = True
    limited_status = 'p'
    limited_init = (10,)
    mass = 0.25
    pack = Pack.misc
class Scashprinter(NumedStatus):
    id = 'p'
    des = "印钞机：你接下来接龙时会奖励接了上一个词的人1击毙。如果上一个词是起始词则不消耗生效次数。"
    is_metallic = True
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        pq = branch.parent.qq
        if pq != config.selfqq and pq != 0:
            user.send_log(f"奖励了[CQ:at,qq={pq}]{len(count)}击毙{句尾}")
            await User(pq, user.buf).add_jibi(len(count))
            for c in count:
                c.num -= 1
            user.data.save_status_time()
        else:
            user.send_log(f"无上一个接龙的玩家{句尾}")
    @classmethod
    def register(cls):
        return {UserEvt.OnDragoned: (Priority.OnDragoned.cashprinter, cls)}
class Sinvcashprinter(NumedStatus):
    id = 'u'
    des = "反转·印钞机：你接下来接龙时会扣除接了上一个词的人1击毙。如果上一个词是起始词则不消耗生效次数。"
    is_metallic = True
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        pq = branch.parent.qq
        if pq != config.selfqq and pq != 0:
            user.send_log(f"扣除了[CQ:at,qq={pq}]{len(count)}击毙{句尾}")
            await User(pq, user.buf).add_jibi(-len(count))
            for c in count:
                c.num -= 1
            user.data.save_status_time()
        else:
            user.send_log(f"无上一个接龙的玩家{句尾}")
    @classmethod
    def register(cls):
        return {UserEvt.OnDragoned: (Priority.OnDragoned.invcashprinter, cls)}

class upsidedown(_card):
    name = "天下翻覆"
    id = 156
    positive = 0
    description = "每条全局状态和你的状态有50%的概率反转，除了那些不能反转的以外。"
    weight = 5
    pack = Pack.misc
    @classmethod
    async def use(cls, user: User) -> None:
        # 永久状态
        async def _s(u: User):
            to_remove = ""
            to_add = ""
            for c in u.data.status:
                if (d := random.random()) > 0.5 + (0.02 * user.data.luck if StatusNull(c).is_debuff else 0):
                    continue
                if c in revert_status_map:
                    des = StatusNull(c).des
                    u.send_log(f"的{des[:des.index('：')]}{'幸运地' if d > 0.5 else ''}被反转了{句尾}")
                    to_remove += c
                    to_add += revert_status_map[c]
            for c in to_remove:
                await u.remove_status(c, remove_all=False, remover=user)
            for c in to_add:
                await u.add_status(c)
        await _s(user)
        # 每日状态
        async def _d(u: User):
            to_remove = ""
            to_add = ""
            for c in u.data.daily_status:
                if (d := random.random()) > 0.5 + (0.02 * user.data.luck if StatusDaily(c).is_debuff else 0):
                    continue
                if c in revert_daily_status_map:
                    des = StatusDaily(c).des
                    u.send_log(f"的{des[:des.index('：')]}{'幸运地' if d > 0.5 else ''}被反转了{句尾}")
                    to_remove += c
                    to_add += revert_daily_status_map[c]
            for c in to_remove:
                await u.remove_daily_status(c, remove_all=False, remover=user)
            for c in to_add:
                await u.add_daily_status(c)
        await _d(user)
        # 带附加值的状态
        l = user.data.status_time_checked
        for i in range(len(l)):
            if (d := random.random()) > 0.5 + (0.02 * user.data.luck if l[i].is_debuff else 0):
                continue
            if l[i].id == 'q':
                l[i].jibi = -l[i].jibi
                user.send_log(f"的每日任务{'幸运地' if d > 0.5 else ''}被反转了{句尾}")
            elif l[i].id == 'b':
                l[i] = SCian(l[i].num)
                user.send_log(f"的月下彼岸花{'幸运地' if d > 0.5 else ''}被反转了{句尾}")
            elif l[i].id == 'c':
                l[i] = SBian(l[i].num)
                user.send_log(f"的反转·月下彼岸花{'幸运地' if d > 0.5 else ''}被反转了{句尾}")
            elif l[i].id == 'e':
                l[i] = inv_hierophant_s(l[i].num)
                user.send_log(f"的反转·教皇{'幸运地' if d > 0.5 else ''}被反转了{句尾}")
            elif l[i].id == 'f':
                l[i] = hierophant_s(l[i].num)
                user.send_log(f"的教皇{'幸运地' if d > 0.5 else ''}被反转了{句尾}")
            elif l[i].id == 'p':
                l[i] = Sinvcashprinter(l[i].num)
                user.send_log(f"的印钞机{'幸运地' if d > 0.5 else ''}被反转了{句尾}")
            elif l[i].id == 'u':
                l[i] = Scashprinter(l[i].num)
                user.send_log(f"的反转·印钞机{'幸运地' if d > 0.5 else ''}被反转了{句尾}")
            elif l[i].id == 'g':
                global genderlist
                if l[i].num == 0:
                    l[i].num = 1
                elif l[i].num == 1:
                    l[i].num = 0
                else:
                    l[i].num = nnum if l[i].num > (nnum := random.choice(range(2, len(genderlist) - 1))) else nnum + 1
                user.buf.send("你的性别被改变到了{}".format(genderlist[l[i].num]) + 句尾)
        user.data.save_status_time()
        # 全局状态
        await _s(Userme(user))
        await _d(Userme(user))
        # l = Game.me.status_time_checked
        # for i in range(len(l)):
        #     if random.random() > 0.5:
        #         continue
        # Game.me.save_status_time()
revert_status_map: Dict[str, str] = {}
for c in ('AB', 'ab', 'st', 'xy', 'Mm', 'QR', '12', '89', '([', ')]', 'cd', '34', 'JK', '|/', 'LI', '&*', '^$'):
    revert_status_map[c[0]] = c[1]
    revert_status_map[c[1]] = c[0]
revert_daily_status_map: Dict[str, str] = {}
for c in ('RZ', 'Bt', 'Ii', 'Mm', 'op', '@#', 'SP', 'CE', 'lk', 'KL', 'Aa', 'Gg'):
    revert_daily_status_map[c[0]] = c[1]
    revert_daily_status_map[c[1]] = c[0]

class bloom(_card):
    id = 157
    name = "绽放"
    positive = 1
    description = "摸13张牌，然后弃牌至max(4,手牌上限-6)张（最多为10）。（特别的，可以弃置空白卡牌）"
    newer = 5
    pack = Pack.misc
    @classmethod
    async def use(cls, user: User) -> None:
        await user.draw(13)
        if len(user.data.hand_card) > min(10, max(4, user.data.card_limit - 6)):
            x = len(user.data.hand_card) - min(10, max(4, user.data.card_limit - 6))
            if not await user.choose():
                random.shuffle(user.data.hand_card)
                user.data.set_cards()
                user.send_char(f"随机弃置了{x}张牌{句尾}")
                user.log << f"预计手牌为{[c.name for c in user.data.hand_card[:max(4, user.data.card_limit - 6)]]}"
                await user.discard_cards(user.data.hand_card[max(4, user.data.card_limit - 6):])
            else:
                async with user.choose_cards(f"请选择{x}牌弃置（输入id号，使用空格分隔）：", x, x) as l:
                    user.buf.send("成功弃置。")
                    await user.discard_cards([Card(i) for i in l])

class excalibur(_card):
    id = 158
    name = "EX咖喱棒"
    positive = 1
    description = "只可在胜利时使用。统治不列颠。"
    newer = 1
    is_metallic = True
    mass = 1
    pack = Pack.misc
    @classmethod
    def can_use(cls, user: User, copy: bool) -> bool:
        return user.check_daily_status('W') > 0
    @classmethod
    async def use(cls, user: User) -> None:
        if user.check_daily_status('W') == 0:
            user.send_char(f"没有胜利，无法使用{句尾}")
        else:
            user.send_log(f"统治了不列颠{句尾}")
            await user.add_limited_status(SBritian([]))
class SBritian(ListStatus):
    id = 'W'
    des = "统治不列颠：使用塔罗牌系列牌时，若本效果不包含“魔力 - {该塔罗牌名}”，不发动该牌的原本使用效果，并为本效果增加“魔力 - {该塔罗牌名}”。当拥有所有22种“魔力 - {塔罗牌名}”时，获得装备“塔罗原典”。"
    removeable = False
    def __str__(self) -> str:
        if len(self.list) == 0:
            return self.des
        return f"{self.des}\n\t包含：{'，'.join(('“魔力 - ' + Card(i).name[Card(i).name.index(' - ') + 3:] + '”') for i in self.list)}。"
    def double(self) -> List[T_status]:
        return [self]
    @property
    def brief_des(self) -> str:
        nt = "\n\t"
        return f"统治不列颠{(nt + '包含：'+','.join(str(c) for c in self.list)) if len(self.list) > 0 else ''}。"
    def check(self) -> bool:
        return True
    @classmethod
    async def BeforeCardUse(cls, count: TCount, user: 'User', card: TCard) -> Tuple[Optional[Awaitable]]:
        if card.id <= 21 and card.id >= 0:
            for c in count:
                if card.id not in c.list:
                    async def f():
                        user.send_log(f"获得了“魔力 - {card.name[card.name.index(' - ') + 3:]}”{句尾}")
                        c.list.append(card.id)
                        c.list.sort()
                        user.log << f"现有{c.list}。"
                        if len(c.list) == 22:
                            await user.remove_limited_status(c)
                            b = user.data.check_equipment(2)
                            user.data.equipment[2] = b + 1
                            if b == 0:
                                user.send_log(f"获得了装备“塔罗原典”{句尾}")
                            elif b == 6:
                                user.send_log(f"将装备“塔罗原典”升星至{b + 1}星{句尾}")
                                user.send_log("仍可继续升级，不过8星以上的塔罗原典将不会有任何额外作用。")
                            elif b >= 7:
                                user.send_log(f"将装备“塔罗原典”升星至{b + 1}星（虽然没有什么作用）{句尾}")
                            else:
                                user.send_log(f"将装备“塔罗原典”升星至{b + 1}星{句尾}")
                        user.data.save_status_time()
                    return f(),
        return None,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.BeforeCardUse: (Priority.BeforeCardUse.britian, cls)}

class envelop(_card):
    id = 160
    name = "信封"
    description = "花费2击毙，选择一张手牌，将其寄给一名指定的玩家，50%概率使该玩家再获得一张信封。"
    positive = 1
    newer = 6
    failure_message = "你的击毙不足" + 句尾
    pack = Pack.misc
    @classmethod
    def can_use(cls, user: User, copy: bool) -> bool:
        return user.data.jibi >= 2
    @classmethod
    async def use(cls, user: User) -> None:
        if not await user.add_jibi(-2, is_buy=True):
            user.send_log("的击毙不足" + 句尾)
        if await user.choose():
            async with user.choose_cards("请选择一张手牌：", 1, 1) as l:
                qq: int = (await user.buf.aget(prompt="请at群内一名玩家。\n",
                    arg_filters=[
                            lambda s: [int(r) for r in re.findall(r'qq=(\d+)', str(s))],
                            validators.fit_size(1, 1, message="请at正确的人数。")
                        ]))[0]
                u = User(qq, user.buf)
                c = Card(l[0])
                user.send_log(f"将手牌{c.name}寄了出去{句尾}")
                await user.remove_cards([c])
                a = random.random()
                if a > 0.5 + 0.02 * min(u.data.luck, 5) + 0.02 * min(user.data.luck, 5):
                    await u.draw(0, cards=[c])
                else:
                    if a > 0.5:
                        u.send_char("幸运地保留了信封" + 句尾)
                    await u.draw(0, cards=[c, envelop])

class shengkong(_card):
    id = 161
    name = "声控"
    description = "摸一张指定的麻将牌，然后50%概率抽一张牌。"
    positive = 1
    newer = 6
    pack = Pack.misc
    @classmethod
    async def use(cls, user: User) -> None:
        if await user.choose():
            hai = (await user.buf.aget(prompt=f"你的麻将牌是：{await MajOneHai.draw_maj([MajOneHai(s) for s in user.data.maj[0]], [MajOneHai(s).hai for s in user.data.maj[1]])}，请指定任意一张麻将牌摸取：\n",
                arg_filters=[
                        lambda s: [r for r in re.findall(r'\d[spmz]', str(s))],
                        validators.fit_size(1, 1, message="请输入一张牌。")
                    ]))[0]
            h = MajOneHai(hai)
            await user.draw_maj(h)
        b = random.random()
        if b < 0.5 + 0.02 * user.data.luck:
            await user.draw(1, replace_prompt=user.char + f"声控的很大声，一张牌{'幸运地' if b > 0.5 else ''}从天花板上掉了下来，竟然是：")

class zhanxingshu(_card):
    id = 162
    name = "占星术"
    description = "一周之内只能使用一次本卡牌。使用后可以自选一个星座，将本周的星座改变。"
    positive = 1
    newer = 7
    pack = Pack.misc
    @classmethod
    async def use(cls, user: User) -> None:
        if await user.choose():
            user.buf.send("请从以下星座中选择一个：")
            user.buf.send(Sign.description_all())
            await user.buf.flush()
            num = (await user.buf.aget(prompt="", arg_filters=[
                extractors.extract_text,
                check_handcard(user),
                lambda s: [int(c) for c in re.findall(r'\-?\d+', str(s))],
                validators.fit_size(1, 1, message="请输入正确的数目。"),
                validators.ensure_true(lambda l: l[0] in list(Sign), message="请输入存在的星座编号。")
            ]))[0]
            user.log << f"选择了{num}。"
            global_state["sign"] = num
            user.send_log(f"改变了当前星座至{Sign(num).name_ch}{句尾}")
            save_global_state()
            await Userme(user).add_status('\\')
class zhanxingshu_exhaust(_statusnull):
    id = '\\'
    des = "星相已尽：本周星座已被改变。"
    is_debuff = True
    removeable = False
    @classmethod
    async def OnUserUseCard(cls, count: TCount, user: 'User', card: TCard) -> Tuple[bool, str]:
        if card is zhanxingshu:
            return False, "本周星座已被改变，无法再次改变。"
        return True, ""
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnUserUseCard: (Priority.OnUserUseCard.zhanxingshu, cls)}

class assembling_machine(_card):
    id = 200
    name = "组装机1型"
    description = "如果你没有组装机，你获得装备：组装机1型。如果你已有组装机1型，将其升级为组装机2型。如果你已有组装机2型，将其升级为组装机3型。如果你已有组装机3型，你获得200组装量。"
    newer = 4
    positive = 1
    is_metallic = True
    mass = 0.2
    pack = Pack.factorio
    @classmethod
    async def use(cls, user: User) -> None:
        c = user.data.check_equipment(3)
        if c == 3:
            user.send_log(f"获得了200组装量{句尾}")
            user.data.extra.assembling += 200
        else:
            if c == 0:
                user.send_log(f"获得了装备：组装机1型{句尾}")
            else:
                user.send_log(f"将组装机{c}型升级到了组装机{c + 1}型{句尾}")
            user.data.equipment[3] = c + 1
            user.data.save_equipment()

class belt(_card):
    id = 201
    name = "传送带"
    description = "当其它玩家丢弃第一张手牌时，你获得之。"
    positive = 1
    newer = 4
    status = '3'
    is_metallic = True
    pack = Pack.factorio
class belt_s(_statusnull):
    id = '3'
    des = "传送带：当其它玩家丢弃第一张手牌时，你获得之。"
    is_metallic = True
class belt_checker(IEventListener):
    @classmethod
    async def AfterCardDiscard(cls, count: TCount, user: 'User', cards: Iterable[TCard]) -> Tuple[()]:
        qqs = [t['qq'] for t in config.userdata.execute("select qq from dragon_data where status like '%3%'").fetchall()]
        if len(qqs) == 0:
            return
        users = [User(qq, user.buf) for qq in qqs if qq != user.qq]
        for card in cards:
            if len(users) == 0:
                return
            u = random.choice(users)
            user.buf.send(f"玩家{u.qq}从传送带上捡起了" + user.char + f"掉的卡{句尾}")
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
    is_metallic = True
    @classmethod
    async def AfterCardDiscard(cls, count: TCount, user: 'User', cards: Iterable[TCard]) -> Tuple[()]:
        qqs = [t['qq'] for t in config.userdata.execute("select qq from dragon_data where dead=false").fetchall()]
        for card in cards:
            qq = random.choice(qqs)
            u = User(qq, user.buf)
            user.buf.send(f"玩家{u.qq}从传送带上捡起了" + user.char + f"掉的卡{句尾}")
            await u.draw(0, cards=[card])
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
    is_metallic = True
    mass = 5
    pack = Pack.factorio
    @classmethod
    async def use(cls, user: User) -> None:
        l = Game.me.check_limited_status('t')
        for tr in l:
            if random.random() < 0.25:
                user.send_log(f"的火车和玩家{tr.qq}的火车发生了碰撞{句尾}")
                await Userme(user).remove_limited_status(tr, remover=user)
                return
        await Userme(user).add_limited_status(STrain(user.qq, False))
class STrain(_status):
    id = 't'
    des = "火车：其它玩家一次获得5以上击毙时，某玩家便乘1击毙。"
    is_global = True
    is_metallic = True
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
            config.logger.dragon << f"【DEBUG】count: {count}, c: {c}"
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
                user.buf.send(f"玩家{tr.qq}乘坐火车便乘了1击毙{句尾}")
                config.logger.dragon << f"【LOG】玩家{tr.qq}乘坐火车便乘了1击毙。"
                await User(tr.qq, user.buf).add_jibi(1)
        return jibi,
    @classmethod
    async def OnStatusRemove(cls, count: TCount, user: 'User', status: TStatusAll, remove_all: bool, remover: Optional['User'] = None) -> Tuple[bool]:
        # TODO structure need change 目前无法处理一部分闪避一部分被消的情况
        if isinstance(status, STrain):
            for tr in count:
                if user.data.luck != 0 and random.random() < 0.1 * min(user.data.luck, 5):
                    user.send_log(f"幸运地防止了碰撞{句尾}")
                    return True,
                if tr.if_def:
                    tr.if_def = False
                    user.data.save_status_time()
                    user.send_log(f"的火车跳板为你的火车防止了碰撞{句尾}")
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
    is_metallic = True
    mass = 0.75
    pack = Pack.factorio
    @classmethod
    def module_des(cls, qq: int):
        m = Game.userdata(qq).module_c
        return "\t" + cls.extra_info[m['id']] + f"剩余：{m['remain'] // (10 if m['id'] == 1 else 1)}{'次' if m['id'] == 1 else '击毙'}。"
    @classmethod
    def full_description(cls, qq: int):
        return super().full_description(qq) + "\n" + cls.module_des(qq)
    @classmethod
    async def on_draw(cls, user: User):
        user.data.modules.append({'id': (r := random.randint(0, 2)), 'remain': 10})
        config.logger.dragon << f"【LOG】用户{user.qq}刷新了一个插件{r}，现有插件：{[c['id'] for c in user.data.modules]}。"
        save_global_state()
    @classmethod
    async def on_remove(cls, user: User):
        r = user.data.pop_module()
        config.logger.dragon << f"【LOG】用户{user.qq}删除了一个插件{r['id']}，现有插件：{[c['id'] for c in user.data.modules]}。"
        save_global_state()
    @classmethod
    async def on_give(cls, user: User, target: User):
        m = user.data.pop_module()
        config.logger.dragon << f"【LOG】用户{user.qq}删除了一个插件{m['id']}，现有插件：{[c['id'] for c in user.data.modules]}。"
        target.data.modules.append(m)
        config.logger.dragon << f"【LOG】用户{target.qq}增加了一个插件{m['id']}，现有插件：{[c['id'] for c in target.data.modules]}。"
        save_global_state()
    @classmethod
    async def OnJibiChange(cls, count: TCount, user: 'User', jibi: int, is_buy: bool) -> Tuple[int]:
        q = str(user.qq)
        if jibi > 0:
            for c in user.data.modules:
                if c['id'] == 0 and c['remain'] > 0 and random.random() < 0.15:
                    if c['remain'] >= jibi:
                        c['remain'] -= jibi
                        jibi *= 2
                    else:
                        jibi += c['remain']
                        c['remain'] = 0
                    user.send_log(f"触发了插件——产率的效果，获得击毙加倍为{jibi}{句尾}")
        elif jibi < 0:
            for c in user.data.modules:
                if jibi != 0 and c['id'] == 2 and c['remain'] > 0:
                    d = ceil(-jibi / 10)
                    if c['remain'] >= d:
                        c['remain'] -= d
                        jibi += d
                    else:
                        jibi += c['remain']
                        c['remain'] = 0
                    user.send_log(f"触发了插件——节能的效果，失去击毙减少为{-jibi}{句尾}")
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
                    user.send_log(f"的插件——速度抵消了寒冰菇的效果{句尾}但你被击毙了30分钟{句尾}")
                    await user.death(30)
                else:
                    q = random.choice(qqstrs)
                    user.buf.send(f"玩家{q}的插件——速度抵消了寒冰菇的效果{句尾}")
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
            user.send_log(f"触发了插件——产率的效果，获得击毙加倍为{jibi}{句尾}")
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
            user.buf.send(f"插件——速度抵消了寒冰菇的效果{句尾}")
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
            user.send_log(f"触发了插件——节能的效果，失去击毙减少为{-jibi}{句尾}")
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
    is_metallic = True
    mass = 0.75
    pack = Pack.factorio
    @classmethod
    def weight(cls, user: User):
        if user.data.luck == 0:
            return 1
        count = 0
        if Game.me.check_limited_status('t', lambda c: c.qq == user.qq):
            count += 1
        if user.data.check_equipment(3) != 0:
            count += 1
        if Card(203) in user.data.hand_card:
            count += 1
        return 1 + user.data.luck / 5 * count
    @classmethod
    async def use(cls, user: User) -> None:
        if t1 := Game.me.check_limited_status('t', lambda c: c.qq == user.qq):
            user.send_log("有火车，" + user.char + f"的每辆火车获得了火车跳板{句尾}")
            for tr in t1:
                tr.if_def = True
            user.data.save_status_time()
        if (t2 := user.data.check_equipment(3) != 0):
            user.send_log("的装备中有组装机，" + user.char + f"获得了一张集装机械臂{句尾}")
            await user.draw(0, cards=[stack_inserter])
        if (t3 := Card(203) in user.data.hand_card):
            q = str(user.qq)
            l = global_state["module"][q]
            u = Userme(user)
            user.send_log("的装备中有插件分享塔，" + user.char + "增加了全局状态：", end='')
            config.logger.dragon << ",".join(str(m['id']) for m in l)
            for m in l:
                c = str(m["id"] + 7)
                await u.add_daily_status(c)
                user.buf.send(StatusDaily(c).brief_des, end='')
            user.buf.send(句尾)
        if t1 and t2 and t3:
            user.send_log(f"获得了一张核弹{句尾}")
            await user.draw(0, cards=[nuclear_bomb])
        if not (t1 or t2 or t3):
            user.send_log(f"抽了一张factorio系列的牌{句尾}")
            await user.draw(1, extra_lambda=lambda c: c.pack == Pack.factorio)

class stack_inserter(_card):
    id = -4
    name = "集装机械臂"
    positive = 1
    description = "选择一张卡牌，将其销毁，并获得等同于卡牌编号/5的击毙。如果你有组装机，使其获得等同于卡牌编号的组装量。"
    is_metallic = True
    pack = Pack.factorio
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
            user.send_char(f"获得了{card.id // 5}击毙{句尾}")
            await user.add_jibi(card.id // 5)
            if count := user.data.check_equipment(3):
                old = assembling.get_card_limit(user.data.extra.assembling, count)
                user.data.extra.assembling += card.id
                new = assembling.get_card_limit(user.data.extra.assembling, count)
                user.log << f"增加了{card.id}的组装量，现有{user.data.extra.assembling}。"
                if new > old:
                    user.send_char(f"的组装机{count}型为你增加了{new - old}的手牌上限{句尾}")

class nuclear_bomb(_card):
    id = -131073
    name = "核弹"
    description = "杀死所有人120分钟。"
    positive = 0
    is_metallic = True
    mass = 0.5
    pack = Pack.factorio
    @classmethod
    async def use(cls, user: User) -> None:
        user.send_char(f"杀死了所有人{句尾}")
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
    is_metallic = True
    mass = 0.25
    pack = Pack.factorio
    @classmethod
    async def on_draw(cls, user: User) -> None:
        if Game.me.check_daily_status('i'):
            user.send_char(f"摧毁了一个寒冰菇，获得了50击毙{句尾}" + user.char + f"就是今天的英雄{句尾}")
            Userme(user).remove_daily_status('i', remove_all=False, remover=user)
            await user.add_jibi(50)
        else:
            user.send_char(f"今天没有寒冰菇{句尾}" + user.char + f"被击毙了{句尾}")
            await user.death()

class rocket(_card):
    id = 206
    name = "火箭"
    description = "发射一枚火箭，获得游戏的胜利。"
    positive = 1
    newer = 4
    is_metallic = True
    mass = 5
    pack = Pack.factorio
    @classmethod
    async def use(cls, user: User) -> None:
        user.buf.send(f"恭喜{user.char}，今天{user.char}赢了{句尾}")
        await user.add_daily_status('W')

# class gluon(_card):
#     id = 221
#     name = "胶子"
#     positive = -1
#     description = "抽到时，会随机将你的两张牌粘在一起。使用/弃置/销毁某一张牌时另一张也会被使用/弃置/销毁。"
#     newer = 6
#     weight = 0
#     consumed_on_draw = True
#     pack = Pack.physic
#     @classmethod
#     async def on_draw(cls, user: User) -> None:
#         if len(user.data.hand_card) < 1:
#             user.send_log("的手牌数不足2！")
#         else:
#             c1, c2 = random.choice(list(itertools.combinations(user.data.hand_card, 2)))
#             await user.add_limited_status(SStick(c1.id, c2.id))
class SStick(_status):
    id = 's'
    is_debuff = True
    def __init__(self, s1: Union[str, int], s2: Union[str, int]):
        self.card1 = int(s1)
        self.card2 = int(s2)
    @property
    def des(self):
        return f"胶子：你的手牌【{Card(self.card1).name}】与【{Card(self.card2).name}】粘在一起了。使用其中一张牌时另一张也会被使用。"
    @property
    def brief_des(self):
        return f"胶子：【{Card(self.card1).name}】与【{Card(self.card2).name}】"
    @classmethod
    async def AfterCardUse(cls, count: TCount, user: 'User', card: TCard) -> Tuple[()]:
        for st in count:
            pass

class uncertainty(_card):
    id = 222
    name = "不确定性原理"
    description = "不可使用。持有时，你每次接龙每个字有5%的几率随机变成一周以内接过的字。"
    mass = 0
    positive = -1
    newer = 6
    failure_message = "此牌不可被使用" + 句尾
    pack = Pack.physic
    @classmethod
    def can_use(cls, user: User, copy: bool) -> bool:
        return False
    @classmethod
    async def BeforeDragoned(cls, count: TCount, user: 'User', state: DragonState) -> Tuple[bool, int, str]:
        from .logic_dragon import log_set
        all_str = "".join(log_set)
        for i in range(len(state.word)):
            s = random.random()
            if s > 0.95 ** count:
                new = random.choice(all_str)
                user.send_log(f"接龙词里的“{state.word[i]}”由于不确定性原理变成了“{new}”{句尾}")
                state.word = state.word[:i] + new + state.word[i + 1:]
        return True, 0, ""
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.BeforeDragoned: (Priority.BeforeDragoned.uncertainty, cls)}

class antimatterdimension(_card):
    id = 223
    name = "反物质维度"
    description = "抽到时，将你的随机一张手牌吸入反物质维度。你下次死亡或本buff消失时，自动使用这张手牌。"
    newer = 6
    positive = -1
    consumed_on_draw = True
    pack = Pack.physic
    @classmethod
    async def on_draw(cls, user: User) -> None:
        if len(user.data.hand_card) == 0:
            user.send_log("没有手牌" + 句尾)
        else:
            card = random.choice(user.data.hand_card)
            user.send_log(f"的手牌{card.name}被吸入了反物质维度{句尾}")
            await user.remove_cards([card]) # TODO 处理胶子，可能同时吸入多张卡
            await user.add_limited_status(SAntimatterDimension(card.id))
class SAntimatterDimension(NumedStatus):
    id = 'a'
    def check(self) -> bool:
        return True
    @property
    def des(self):
        return f"反物质维度：你下次死亡或本buff消失时，自动使用卡牌【{Card(self.num).name}】。"
    def __str__(self):
        return self.des + f"\n\t{Card(self.num).description}"
    @property
    def brief_des(self) -> str:
        return f"反物质维度：卡牌【{Card(self.num).name}】。"
    @classmethod
    async def OnDeath(cls, count: TCount, user: 'User', killer: 'User', time: int, c: TAttackType) -> Tuple[int, bool]:
        await user.remove_all_limited_status('a')
        user.data.save_status_time()
        return time, False
    @classmethod
    async def AfterStatusRemove(cls, count: TCount, user: 'User', status: TStatusAll, remove_all: bool) -> Tuple[()]:
        if isinstance(status, SAntimatterDimension):
            cd = Card(status.num)
            user.send_log(f"卡牌【{cd.name}】从反物质维度中被释放了出来{句尾}", no_char=True)
            await user.use_card_effect(cd)
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDeath: (Priority.OnDeath.antimatter, cls),
            UserEvt.AfterStatusRemove: (Priority.AfterStatusRemove.antimatter, cls)}

class doublebetadecay(_card):
    id = 224
    name = "无中微子双β衰变"
    description = "抽到时，如果你所有手牌的id+2后均不是合理手牌，则你重新摸一张牌。否则你手牌里随机一张牌id+2，并摸2张【邪恶的间谍行动～执行】。"
    positive = -1
    newer = 6
    consumed_on_draw = True
    pack = Pack.physic
    @classmethod
    async def on_draw(cls, user: User) -> None:
        l: List[TCard] = []
        for c in user.data.hand_card:
            if c.id + 2 in _card.card_id_dict:
                l.append(c)
        if len(l) == 0:
            user.send_log(f"手牌中没有合理的牌{句尾}")
            await user.draw(1)
        else:
            c = random.choice(l)
            c2 = Card(c.id + 2)
            user.send_log(f"手牌中的{c.name}衰变成了{c2.name}和两张【邪恶的间谍行动～执行】{句尾}")
            await user.remove_cards([c])
            await user.draw(0, cards=[c2, Card(-1), Card(-1)])

class wormhole(_card):
    id = 226
    name = "虫洞"
    description = "将你身上的一个随机负面状态或是负面手牌转移给另一名随机玩家。"
    positive = 1
    newer = 6
    mass = -10
    pack = Pack.physic
    @classmethod
    async def use(cls, user: User) -> None:
        l: List[Tuple[int, Any]] = []
        for c in user.data.hand_card:
            if c.positive == -1:
                l.append((0, c))
        for c in user.data.status:
            if (s := StatusNull(c)).is_debuff and s.removeable:
                l.append((1, s))
        for c in user.data.daily_status:
            if (s := StatusDaily(c)).is_debuff and s.removeable:
                l.append((2, s))
        for c in user.data.status_time_checked:
            if c.is_debuff and c.removeable:
                l.append((3, c))
        if len(l) == 0:
            user.send_log("没有负面状态或是负面手牌" + 句尾)
        else:
            i, s = random.choice(l)
            pl = config.userdata.execute("select qq from dragon_data where dead=false").fetchall()
            pl: List[int] = [c['qq'] for c in pl if c['qq'] != 0 and c['qq'] != user.qq]
            u2 = User(random.choice(pl), user.buf)
            if i == 0:
                user.send_log(f"的手牌{s.name}转移给了[CQ:at,qq={u2.qq}]{句尾}")
                await user.remove_cards([s])
                await u2.draw(0, cards=[s])
            elif i == 1:
                user.send_log(f"的状态{s.des[:s.des.index('：')]}转移给了[CQ:at,qq={u2.qq}]{句尾}")
                await user.remove_status(s.id, remover=user)
                await u2.add_status(s.id)
            elif i == 2:
                user.send_log(f"的状态{s.des[:s.des.index('：')]}转移给了[CQ:at,qq={u2.qq}]{句尾}")
                await user.remove_daily_status(s.id, remover=user)
                await u2.add_daily_status(s.id)
            elif i == 3:
                user.send_log(f"的状态{s.des[:s.des.index('：')]}转移给了[CQ:at,qq={u2.qq}]{句尾}")
                await user.remove_limited_status(s, remover=user)
                await u2.add_limited_status(s)

class photoelectric(_card):
    id = 227
    name = "光电效应"
    description = "抽到时，你身上每有一个金属制品，你摸一个电子。"
    positive = 1
    newer = 7
    pack = Pack.physic
    consumed_on_draw = True
    @classmethod
    async def on_draw(cls, user: User) -> None:
        cards = [d for d in user.data.hand_card if d.is_metallic]
        status_nulles = [s for s in user.data.status if StatusNull(s).is_metallic]
        status_dailyes = [s for s in user.data.daily_status if StatusDaily(s).is_metallic]
        statuses = [s for s in user.data.status_time_checked if s.is_metallic]
        l = len(cards) + len(status_nulles) + len(status_dailyes) + len(statuses)
        user.send_log(f"身上有{l}个金属制品，奖励{l}张电子{句尾}")
        await user.draw(0, cards=[electron] * l)
class electron(_card):
    id = -6
    name = "电子"
    description = "从自己最后的一次接龙之前开始顺序向前，每有一个人身上有金属制品就击毙10分钟（同一个人的击毙时间叠加），直到身上没有金属制品的人为止。"
    positive = 1
    newer = 7
    pack = Pack.physic
    @classmethod
    async def use(cls, user: User) -> None:
        c = Counter()
        checked = set()
        for branches in Tree._objs:
            found = False
            node = None if len(l := [tr for tr in branches if tr.qq == user.qq]) == 0 else l[-1].parent
            while node is not None and node.id_str not in checked:
                ud = Game.userdata(node.qq)
                cards = [d for d in ud.hand_card if d.is_metallic]
                status_nulles = [s for s in ud.status if StatusNull(s).is_metallic]
                status_dailyes = [s for s in ud.daily_status if StatusDaily(s).is_metallic]
                statuses = [s for s in ud.status_time_checked if s.is_metallic]
                l = len(cards) + len(status_nulles) + len(status_dailyes) + len(statuses)
                if l == 0:
                    break
                else:
                    c[node.qq] += 1
                    checked.add(node.id_str)
                node = node.parent
        if len(c) == 0:
            user.send_log("没有击毙任何人" + 句尾)
        else:
            user.buf.send("\n".join(f"[CQ:at,qq={qq}]被你击毙了{10 * count}分钟。" for qq, count in c.items()))
            user.log << '，'.join(f"{qq}被击杀了{10 * count}分钟" for qq, count in c.items())
            for qq, count in c.items():
                await User(qq, user.buf).killed(user, hour=0, minute=10 * count)

class laplace(_card):
    id = 228
    name = "拉普拉斯魔"
    description = "私聊告诉你牌堆的下3张牌是什么。"
    positive = 1
    newer = 6
    mass = 0
    pack = Pack.physic
    @classmethod
    async def use(cls, user: User) -> None:
        ume = Userme(user)
        if l := Game.me.check_limited_status('P'):
            if len(l[0].list) >= 3:
                cards = [Card(c) for c in l[0].list[:3]]
            else:
                to_add = draw_cards(ume, k=3 - len(l[0].list))
                cards = [Card(c) for c in l[0].list]
                l[0].list.extend([c.id for c in to_add])
                cards += to_add
        else:
            cards = draw_cards(ume, k=3)
            await ume.add_limited_status(SLaplace([c.id for c in cards]))
        if await user.choose():
            #user.buf.send("卡牌已通过私聊发送" + 句尾)
            user.log << f"查询结果为{[c.brief_description() for c in cards]}。"
            x = '\n'
            user.buf.send(f"牌堆顶的3张卡为：{x.join(c.full_description(user.qq) for c in cards)}")
class SLaplace(ListStatus):
    id = 'P'
    is_global = True
    @property
    def des(self):
        return f"拉普拉斯魔：牌堆顶的{len(self.list)}张牌已经被看了。"
    @classmethod
    async def BeforeCardDraw(cls, count: TCount, user: 'User', n: int, positive: Optional[set[int]], extra_lambda: Optional[Callable]) -> Tuple[Optional[List[TCard]]]:
        b: List[int] = count[0].list
        can_draw = [Card(c) for c in b if (positive is None or Card(c).positive in positive)
                                    and (extra_lambda is None or extra_lambda(Card(c)))]
        if len(can_draw) == 0:
            return None,
        if len(can_draw) >= n:
            to_remove = can_draw[:n]
            new = []
        else:
            to_remove = can_draw
            new = draw_cards(user, positive, n - len(can_draw), extra_lambda)
        for c in to_remove:
            count[0].list.remove(c.id)
        Game.me.save_status_time()
        return to_remove + new,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.BeforeCardDraw: (Priority.BeforeCardDraw.laplace, cls)}

class randommaj2(_card):
    id = 239
    name = "扣置的麻将"
    positive = 1
    mass = 0.25
    newer = 6
    description = "增加5次麻将摸牌的机会，然后抽一张卡。发送“摸麻将”摸牌，然后选择切牌/立直/暗杠/和出。"
    pack = Pack.misc
    @classmethod
    async def use(cls, user: User) -> None:
        user.data.extra.maj_quan += 15
        user.send_log("增加了5张麻将摸牌券" + 句尾)
        await user.draw(1)


class YamatoTamasi(_card):
    id = 250
    name = "大和魂"
    positive = 0
    newer = 8
    description = "抽到时附加状态：当你死亡时，千春为你吟诵一首俳句。"
    pack = Pack.silly
    consumed_on_draw = True
    on_draw_status = 'Y'
class SYamatoTamasi(_statusnull):
    id = 'Y'
    des = "大和魂：当你死亡时，千春为你吟诵一首俳句。"
    @classmethod
    async def OnDeath(cls, count: TCount, user: 'User', killer: 'User', time: int, c: TAttackType) -> Tuple[int, bool]:
        await user.remove_status('Y', remove_all=False)
        msg0 = random.choice(["采菊东篱下","反物质维度","回家睡大觉","出租车司机","鹰角有新饼","秦王又不播","今天吃什么","通信电子战","软件无线电","热心谜之声","石头上刻着","万用回形针","元火动漫社","僧踢夜下门","太空侵略者","西直门换乘","老北京豆汁","一个九宫格","海王幻想入","马骑马小姐","若想要变强","晚睡打游戏","这算俳句吗","互联网世界","不是我说啊","从前有座山","虽然不太懂","先去洗个澡","一觉醒来后","做了一个梦","所谓人生啊","网抑云音乐","迟早有一天","今天好天气","头发随风走","网络有点卡","你可能会死","机械烈海王","三个龙骑士","今日死蚊子","清华次世代","如果早知道","几分钟之后","陌生天花板","啥时候女装","蜗牛观光客","不想学习了","地铁坐过站","温暖大家庭","占星家宣布","向前一小步","多线程初恋","超时空将军","踏上独轮车","双层大肘子","美式冰豆汁","夏季大三角","读书人的事","工口足球场","微博连读学","复读被打断","我现在发现","美少女贴贴","完全一向听"])
        msg1 = random.choice(["可口可乐强无敌","叔叔我要生气了","我是一头小毛驴","你的朋友们爱你","植物大战僵尸二","我要成为双马尾","智械危机要来了","你这是不道德的","垂死病中惊坐起","天若有情天亦老","爽哥还在打游戏","超级无敌我爱你","这你得问概率论","不如回家卖红薯","总之先加点体力","看会沙雕视频先","总之这样就好了","神必言论大放送","假装无事发生过","快进到世界末日","活着难道不好吗","小拳拳捶你胸口","内容不适宜传播","行吧那就没事了","我是手机操作的","不存在打错的事","所以不是我的错","都是世界的问题","突然想起一件事","好像还得写作业","死线当头好烦啊","但是又想摸个鱼","干脆投个滴一百","结果是你没朋友","不许僧踢月下门","不行我要笑死了","随机数他有问题","生草请看下一句","半部论语治天下","总之先上到五楼","你这又是何苦呢","中间要有七个字","菜就可以上桌了","您就可以下锅了","还有一位没有来","发起了语音通话","你的猫度不够高","多年以后风还有","但你也能玩到爽","痛击了我的队友","但是又想上厕所","H的意义上来说","准备用舌头去舔","好想被大姐姐揉","为什么要投骰子","那代价是什么呢","饱暖何不思淫欲","艾欧泽亚沙之家","男孩也会被性侵","这个彬彬就是逊","但是已经不饿了","快进到酒后乱性","不明不白被日了","不如穿女装被日","新手千万不要选","神奇动物在哪里","你全家都是萝莉","扑通一声跳下水","我口味很清水的","我不需要看医生","不慎错过末班车","发出杀猪般嚎叫","那何不假装偶遇","一看结果两道杠","请来一趟石之家","鸡蛋香蕉胡萝卜","说到一半忘词了","抢红包没你的份","集体化身乐子人","二零七七又跳票","特朗普夜间电话","凌空一指成步堂","我家的猫它变了","居家隔离十四天","连接数据库失败","光辉十连大暗骰","光吉猛修他全家","小丑竟是我自己","爱顾有难终了致","人为什么要睡觉","这是一条元俳句","半泽直树真上头","您们还想吃点啥","一次只能加一个","老头地铁看手机","请耐心等待整改","您遇到了假医生","列克星敦又沉了","西直门坏起来了","跳校河头破血流"])
        msg2 = random.choice(["黑暗剑22","僧踢月下门","烫烫烫烫烫","厕所没纸了","真的合理吗","完全理解了","杰哥不要啊","就要吃禁果","其实是做梦","可惜不现实","活着好累啊","还是烤肉好","我要美少女","wdnmd","草草草草草","多吃两碗饭","你在第几层","泪洒宿舍楼","沉尸未名湖","狂喝气泡水","变成死肥宅","看山还是山","谁又不是呢","俺寻思能行","连吃三大碗","骰子灌铅了","我也不造啊","幸存者偏差","去吃肯德基","我季节语呢","我叫逗你玩","回去等死吧","为何不阉割","去吃烤肉吧","不如五反田","谜医生主刀","求生欲不够","这真步河里","谁会在意呢","可你没朋友","我不能接受","头发不再有","那再来一个","绝对许早苗","明天再努力","海猫二百玉","那你很勇哦","多少有问题","快来爽一爽","会死得很惨","真不是我啊","闷声大发财","再学五分钟","死于一把盐","便乘魔怔人","回不了家了","东方永夜抄","建议问骰子","能别恶心么","文明一大步","诚招鼓励师","电脑没电了","后半句忘了","一切转冲蝗","社会性死亡","容易被硌到","互联网暴力","大鸟转转转","纪念API","立省百分百","法克买来福","黄前久美子","骰子灌铅了","臭男人落泪","玛奇玛打码","不是大问题","送你见上帝","谢谢你美国","不然人没了","草生了出来","爽哥带带货"])
        user.buf.send(f"千春道：{msg0}，{msg1}，{msg2}。")
        return time, False
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDeath: (Priority.OnDeath.yamatotamasi, cls)}

genderlist = ["不是原本的性别","原本的性别","Aftgender","Agender","Agenderfluid","Agenderflux","Agiaspec","Agingender","Aiaspec","Aingender","Aliagender","Alysgender","Ambonec","Androgyne","Anongender","Aporagender","Aporine","Aragender","Asterfluid","Axera","Axvir","Azurgirl","Bigender","Boi","Boyfluid","Boyflux","Butch","Cassfluid","Cassflux","Cassgender","Citrabinary","Clowncoric","Cluttergender","Contrastgender","Coric","Cuavgender","Daimogender","Demiagender","Demiandrogyne","Demiboy","Demifem","Demifeminine","Demifemme","Demifluid","Demiflux","Demigender","Demigirl","Demimasc","Demimasculine","Demimaverique","Eafluid","Exofluid","Fa'afafine","Femme","Fiaspec","Fingender","Fluidqueer","Fluxstatic","Apagender","Genderfaer","Genderfaun","Genderfaunet","Genderflor","Genderfloren","Genderflorent","Genderflorer","Genderfloret","Genderfloretten","Genderfluid","Genderflux","Genderfrect","Genderfree","Genderfrict","Genderfrith","Genderfrithen","Genderfrither","Genderfrithet","Genderfruct","Genderneutral","Genderqueer","Gendersatyr","Genderselkie","Genderspirit","Gendersylph","Gendersylphen","Gendersylpher","Gendersylphet","Girlfluid","Girlflux","Gxrl","Hijra","Intergender","Intrabinary","Juxera","Khanith","Kidcoric","Liaspec","Librafeminine","Libramasculine","Libranonbinary","Lilafluid","Lingender","Littlefluid","Lunagender","Lunarset","Magifluid","Marfluid","Maricagender","Maverique","Mekangender","Miaspec","Mingender","Mixflux","Multigender","Muxe","Māhū","Neoboy","Neogirl","Neurogender","Neutrandrogyne","Neutrois","Niaspec","Ningender","Nuncgender","Octogender","Oiaspec","Oingender","Pangender","Parafluid","Perifluid","Polygender","Proxvir","Qariwarmi","Quadgender","Quintgender","Regius-Gender","Retrofluid","Rosboy","Schrodingergender","Soy Boy","Male to Female","Female to Male","Trigender","Vaxgender","Venufluid","Wistrafluid","X-gender","Xenofluid","Xenogender","Xiaspec","Xingender","Yinyang Ren"]
class wirecutter(_card):
    id = 251
    name = "剪线钳"
    positive = 0
    newer = 8
    description = "改变你的性别。"
    pack = Pack.silly
    @classmethod
    async def use(cls, user: User) -> None:
        l = user.check_limited_status('g')
        if len(l) != 0:
            if l[0].num == 0:
                l[0].num = 1
            elif l[0].num == 1:
                l[0].num = 0
            else:
                l[0].num = (nnum := random.choice(range(2, len(genderlist) - 1))) if l[0].num > nnum else nnum + 1
            user.buf.send("你的性别被改变至{}。".format(genderlist[l[0].num]) + 句尾)
            user.data.save_status_time()
        else:
            res: str = (await user.buf.aget(prompt="请选择你的性别为“二元性别”或“非二元性别”。",
                arg_filters=[
                    extractors.extract_text,
                    validators.ensure_true(lambda c: c == "二元性别" or c == "非二元性别", message = "请选择你的性别为“二元性别”或“非二元性别”。")
                    ]))
            if res == "二元性别":
                nnum = 0
            else:
                nnum = random.choice(range(2, len(genderlist)))
            user.buf.send("你获得的性别为{}。".format(genderlist[nnum]))
            await user.add_limited_status(Sgender(nnum))
class Sgender(NumedStatus):
    id = 'g'
    @property
    def des(self) -> str:
        return f"你当前性别为{genderlist[self.num]}。"
    def __str__(self) -> str:
        return self.des
    def double(self):
        return [self]

class TYPEA(_card):
    id = 252
    name = "TYPE-A"
    positive = -1
    newer = 8
    description = "抽到时附加状态：当规则为首尾或尾首接龙时，如果你接龙时按另一者接，那么你会死于强迫症。"
    pack = Pack.silly
    consumed_on_draw = True
    on_draw_daily_status = 'A'
class STYPEA(_statusdaily):
    id = 'A'
    des = "TYPE-A：当规则为首尾或尾首接龙时，如果你接龙时按另一者接，那么你会死于强迫症。"
    @classmethod
    async def BeforeDragoned(cls, count: TCount, user: 'User', state: DragonState) -> Tuple[bool, int, str]:
        async def OnShouWei(self: DragonState, user: 'User'):
            if self.weishou and not self.shouwei:
                user.buf.send_log(f"因弄反首尾接龙死于强迫症" + 句尾)
                await user.death()
        async def OnWeiShou(self: DragonState, user: 'User'):
            if self.shouwei and not self.weishou:
                user.buf.send_log(f"因弄反尾首接龙死于强迫症" + 句尾)
                await user.death()
        state.OnShouWei = OnShouWei
        state.OnWeiShou = OnWeiShou
        return True, 0, ""
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.BeforeDragoned: (Priority.BeforeDragoned.typea, cls)}
class STYPEC(_statusdaily):
    id = 'a'
    des = "TYPE-C：当规则为首尾或尾首接龙时，你接龙时可以按任意一个接。"
    @classmethod
    async def BeforeDragoned(cls, count: TCount, user: 'User', state: DragonState) -> Tuple[bool, int, str]:
        async def OnShouWei(self: DragonState, user: 'User'):
            if self.weishou:
                self.shouwei = True
        async def OnWeiShou(self: DragonState, user: 'User'):
            if self.shouwei:
                self.weishou = True
        state.OnShouWei = OnShouWei
        state.OnWeiShou = OnWeiShou
        return True, 0, ""
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.BeforeDragoned: (Priority.BeforeDragoned.typec, cls)}

class Onemore(_card):
    id = 253
    name = "再来一瓶"
    positive = 1
    newer = 8
    description = "抽一张卡。"
    pack = Pack.silly
    @classmethod
    async def use(cls, user: User) -> None:
        await user.draw(1)

class Heianjian22(_card):
    id = 254
    name = "黑暗剑22"
    description = "你获得装备黑暗剑22。"
    positive = 0
    newer = 8
    pack = Pack.silly

class HungryCentipede(_card):
    id = 255
    name = "饥饿的百足虫"
    description = "他看起来像是暴食的蜈蚣，但其实不是。使用后，今天内手牌上限+1。"
    positive = 1
    newer = 8
    pack = Pack.silly
    daily_status = 'H'
class SHungruCentipede(_statusdaily):
    id = 'H'
    des = "饥饿的百足虫：他看起来像是贪食的蜈蚣，但其实不是。今天内手牌上限+1。"

# class aomenduchang(_card):

class Orga(_card):
    id = 257
    name = "奥尔加"
    description = "抽到时，附加全局状态奥尔加。"
    positive = 0
    newer = 8
    pack = Pack.silly
    consumed_on_draw = True
    on_draw_global_daily_status = 'G'
class SOrga(_statusdaily):
    id = 'G'
    des = "奥尔加：今日内，如果距离上一次接龙之间的时间差小于一小时，那么路就会不断延伸。"
    is_global = True
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        if datetime.now() <= datetime.fromisoformat(global_state['last_dragon_time']) + timedelta(hours=1):
            user.buf.send("道路还在不断延伸...\n")
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDragoned: (Priority.OnDragoned.orga, cls)}
class SInvOrga(_statusdaily):
    id = 'g'
    des = "反转·奥尔加：可能会有意想不到的事情发生。"
    is_global = True
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        def inb(words: str):
            return words in branch.word
        if inb("女") or inb("唱歌") or inb("男人死") or inb("女人唱歌男人死"):
            user.buf.send("ₘₙⁿ\n▏n\n█▏　､⺍\n█▏ ⺰ʷʷｨ\n█◣▄██◣\n◥██████▋\n　◥████ █▎\n　　███▉ █▎\n　◢████◣⌠ₘ℩\n　　██◥█◣\≫\n　　██　◥█◣\n　　█▉　　█▊\n　　█▊　　█▊\n　　█▊　　█▋\n　　 █▏　　█▙\n　　 █\n止まるんじゃねぇぞ！\n")
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDragoned: (Priority.OnDragoned.inv_orga, cls)}

# class oneplusoneequal12(_card): #TODO

class showyourfoolish(_card):
    id = 261
    name = "奇文共赏"
    description = "抽到此卡时，展示一张愚蠢卡牌包的卡，你可以选择：\n\t他很愚蠢：你获得这张卡；\n\t他不够愚蠢：免费提交一张卡，并(在经过审查后)自动加入愚蠢扩展包。"
    positive = 0
    newer = 8
    pack = Pack.silly
    consumed_on_draw = True
    @classmethod
    async def on_draw(cls, user: User) -> None:
        if await user.choose(flush=False):
            card = random.choice([c for id, c in _card.card_id_dict.items() if c.pack == Pack.silly])
            cdes = card.full_description(user.qq)
            user.buf.send(f"你抽到的愚蠢卡牌是：\n{cdes}\n")
            await user.buf.flush()
            res: str = (await user.buf.aget(prompt="请选择“他很愚蠢”或“他不够愚蠢”",
                arg_filters=[
                    extractors.extract_text,
                    validators.ensure_true(lambda c: c == "他很愚蠢" or c == "他不够愚蠢", message = "请选择“他很愚蠢”或“他不够愚蠢”")
                    ]))
            if res == '他很愚蠢':
                await user.draw(0, cards=[card])
            elif res == '他不够愚蠢':
                config.logger.dragon << f"【LOG】询问用户{user.qq}提交的卡牌。"
                s = await user.buf.aget(prompt="请提交卡牌名与卡牌效果描述，所属类别默认为愚蠢扩展包。\n\t请注意，只能输入一次。")
                config.logger.dragon << f"【LOG】用户{user.qq}提交卡牌{s}。"
                for group in config.group_id_dict['logic_dragon_supervise']:
                    await get_bot().send_group_msg(group_id=group, message=s)
                user.buf.send(f"您已成功提交{句尾}")

class shuffer(_card):
    id = 262
    name = "洗牌器"
    description = "抽到时，将你的手牌洗牌。"
    positive = 0
    newer = 8
    pack = Pack.silly
    consumed_on_draw = True
    @classmethod
    async def on_draw(cls, user: User) -> None:
        random.shuffle(user.data.hand_card)
        user.data.set_cards()
        user.send_log("的手牌被洗牌了" + 句尾)

class fakeattack(_card):
    id = 265
    name = "佯攻"
    description = "选择一个玩家，对他进行一次无任何效果的攻击。"
    positive = 1
    newer = 8
    pack = Pack.silly
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
            atk = Afakeattack(user, u)
            await u.attacked(user, atk)
class Afakeattack(Attack):
    name = "佯攻"
    doublable = False
    async def self_action(self):
        self.attacker.send_char(f"攻击了" + self.defender.char + 句尾)

class Ugun(_card):
    id = 266
    name = "U型枪管"
    description = "抽到时附加全局状态：今天所有攻击别人的效果都变成攻击自己。"
    positive = 0
    newer = 8
    pack = Pack.silly
    consumed_on_draw = True
    on_draw_global_daily_status = 'u'
class SUgun(_statusdaily):
    id = 'u'
    des = "U型枪管：今天所有攻击别人的效果都变成攻击自己。"
    is_global = True
    @classmethod
    async def OnAttack(cls, count: TCount, user: 'User', attack: 'Attack') -> Tuple[bool]:
        user.send_log("的攻击变成了攻击你自己" + 句尾)
        attack.defender = attack.attacker
        return False,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnAttack: (Priority.OnAttack.Ugun, cls)}

class bestchiharu(_card):
    id = 267
    name = "守护我们最好的千春"
    description = "为千春加上同名状态：此状态被移除时，扣除移除者25击毙。"
    positive = 1
    newer = 8
    pack = Pack.silly
    global_status = 'C'
class Sbestchiharu(_statusnull):
    id = 'C'
    des = "守护我们最好的千春：此状态被移除时，扣除移除者25击毙。"
    is_global = True
    @classmethod
    async def OnStatusRemove(cls, count: TCount, user: 'User', status: TStatusAll, remove_all: bool, remover: Optional['User'] = None) -> Tuple[bool]:
        if status is Sbestchiharu:
            remover.send_log("怎么能伤害我们最好的千春😠" + 句尾 + f"扣除你{25 * (count if remove_all else 1)}击毙" + 句尾)
            await remover.add_jibi(-25 * (count if remove_all else 1))
        return False,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnStatusRemove: (Priority.OnStatusRemove.bestchiharu, cls)}

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
            user.send_log(f"触发了比基尼的效果，获得击毙加倍为{abs(jibi)}{句尾}")
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
            user.send_log(f"触发了学生泳装的效果，本次免单{句尾}")
        return jibi,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnJibiChange: (Priority.OnJibiChange.schoolsui, cls)}

class tarot(_equipment):
    id = 2
    name = "塔罗原典"
    @classmethod
    def description(cls, count: TCount) -> str:
        return f"每天限一次，可以从{2 * min(count, 7)}张塔罗牌中选择一张发动。"
    @classmethod
    def can_use(cls, user: User, count: int) -> bool:
        return user.data.extra.tarot_time != 0
    failure_message = "你今日使用次数已完" + 句尾
    @classmethod
    async def use(cls, user: User, count: int):
        if await user.choose():
            if user.data.extra.tarot_time == 0:
                user.send_char(f"今日使用次数已完{句尾}")
                return
            d = date.today()
            if datetime.now().time() < time(15, 59):
                d -= timedelta(days=1)
            h = f"{user.qq} {d.isoformat()}"
            state = random.getstate()
            random.seed(h)
            l1 = list(range(22))
            random.shuffle(l1)
            l2 = sorted(l1[:2 * min(count, 7)])
            random.setstate(state)
            config.logger.dragon << f"【LOG】询问用户{user.qq}选择塔罗原典。"
            cards = "\n".join(Card(i).full_description(user.qq) for i in l2)
            c = (await user.buf.aget(prompt="你今天可以从以下牌中选择一张使用，请输入id号，输入取消退出。\n" + cards,
                arg_filters=[
                        extractors.extract_text,
                        check_handcard(user),
                        lambda s: [(int(c) if c != "取消" else c) for c in re.findall(r'取消|\-?\d+', str(s))],
                        validators.fit_size(1, 1, message="请输入正确的张数。"),
                        validators.ensure_true(lambda l: l[0] == "取消" or l[0] in l2, message="请输入在范围内的牌。")
                    ]))[0]
            if c == "取消":
                user.log << f"取消。"
            else:
                user.log << f"选择了卡牌{c}。"
                user.data.extra.tarot_time -= 1
                await user.draw_and_use(card=Card(c))
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
        return f"{cls.id}. {cls.name}{count}型\n\t{cls.description(count)}\n\t当前组装量：{user.data.extra.assembling}，已获得手牌上限{user.data.card_limit_from_assembling}"
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
            user.send_char(f"的组装机{count}型为你增加了{new - old}的手牌上限{句尾}")
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.AfterCardDraw: (Priority.AfterCardDraw.assembling, cls)}

class dragon_head(_equipment):
    id = 4
    name = "龙首"
    @classmethod
    def description(cls, count: TCount) -> str:
        return f"可以保存{count}张卡。保存的卡独立于手牌之外（不受礼物交换/空白卡牌影响），不能直接使用。"
    @classmethod
    def full_description(cls, count: TCount, user: User) -> str:
        return super().full_description(count, user) + f"\n\t当前保存卡牌：{'，'.join(f'{Card(c).id}.{Card(c).name}' for c in user.data.dragon_head)}。"
    @classmethod
    async def use(cls, user: User, count: int):
        if await user.choose():
            from nonebot.command.argfilter.validators import _raise_failure
            def validate(value: str):
                try:
                    if value.startswith("返回"):
                        return -1
                    elif value.startswith("放入"):
                        id = int(value[2:])
                        if id not in _card.card_id_dict or Card(id) not in user.data.hand_card:
                            _raise_failure(f"此卡不在你的手牌中，请重新选择{句尾}")
                        return (0, id)
                    elif value.startswith("取出"):
                        id = int(value[2:])
                        if id not in user.data.dragon_head:
                            _raise_failure(f"此卡不在龙首内，请重新选择{句尾}")
                        return (1, id)
                except ValueError:
                    _raise_failure("请输入正确的卡牌id号。")
            c: Tuple[int, TCard] = await user.buf.aget(prompt="请选择放入或取出手牌。输入“放入 xx”将卡牌放入龙首，“取出 xx”将卡牌从龙首中取出，“返回”退出（仍可查询当前手牌或装备）。\n",
                arg_filters=[
                        extractors.extract_text,
                        check_handcard(user),
                        validate,
                        validators.ensure_true(lambda v: v is not None, "输入“放入 xx”将卡牌放入龙首，“取出 xx”将卡牌从龙首中取出，“返回”退出（仍可查询当前手牌或装备）。")
                    ])
            if c == -1:
                return
            elif c[0] == 0:
                if len(user.data.dragon_head) >= count:
                    user.send_char(f"龙首已满，无法放入{句尾}")
                    return
                if c[1] == queststone.id:
                    user.data.dragon_head[c[1]] = user.data.quest_c
                elif c[1] == beacon.id:
                    user.data.dragon_head[c[1]] = user.data.module_c
                elif c[1] == lveduozhebopu.id:
                    user.data.dragon_head[c[1]] = user.data.steal
                else:
                    user.data.dragon_head[c[1]] = None
                user.send_log(f"将卡牌{Card(c[1]).name}放入了龙首{句尾}")
                await user.remove_cards([Card(c[1])])
            elif c[0] == 1:
                data = user.data.dragon_head.pop(c[1])
                if c[1] == queststone.id:
                    user.data.quests.append(data)
                elif c[1] == beacon.id:
                    user.data.modules.append(data)
                elif c[1] == lveduozhebopu.id:
                    if user.data.steal['time'] == 0:
                        user.data.steal = data
                user.send_log(f"从龙首中取出了卡牌{Card(c[1]).name}{句尾}")
                await user.add_card(Card(c[1]))
                user.data.set_cards()
            save_global_state()
            user.data.save_equipment()

class dushen_ring(_equipment):
    id = 5
    name = "赌神魔戒"
    @classmethod
    def description(cls, count: TCount) -> str:
        return "你的幸运值+5。"
    @classmethod
    def full_description(cls, count: TCount, user: User) -> str:
        return f"{cls.id}. {cls.name}\n\t{cls.description(count)}"

class golden_belt(_equipment):
    id = 6
    name = "金腰带"
    description = "你的姿势水平+1。"
class goldenbelt_checker(IEventListener):
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        if user.data.check_equipment(6):
            return
        if 0 not in user.data.collections:
            user.data.collections[0] = []
        p = list(itertools.chain(*pinyin(branch.word, errors='ignore', style=Style.NORMAL, strict=True)))
        alls = ("gou", "li", "guo", "jia", "sheng", "si", "yi", "qi", "yin", "huo", "fu", "bi", "qu", "zhi")
        allzi = "苟利国家生死以岂因祸福避趋之"
        l = [i for i, n in enumerate(alls) if n in p and i not in user.data.collections[0]]
        luck = False
        if len(l) == 0:
            if random.random() < user.data.luck * 0.004:
                l = list(range(14))
                luck = True
            else:
                return
        elif random.random() < 0.5:
            return
        i = random.choice(l)
        user.data.collections[0] = sorted(user.data.collections[0] + [i])
        user.send_log(f"{'幸运地' if luck else ''} 收集 到了单字卡“{allzi[i]}”{句尾}")
        if len(user.data.collections[0]) == 14:
            user.data.equipment[6] = 1
            user.send_log("获得了装备：金腰带" + 句尾)
            user.data.save_equipment()
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDragoned: (Priority.OnDragoned.jinyaodai, cls)}
UserData.register_checker(goldenbelt_checker)

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
            await user.draw_and_use()
        elif content < 95: # 你下次行走距离加倍。
            user.send_log("走到了：你下次行走距离加倍。")
            await user.add_status('D')
        else: # 随机获得10~30活动pt。
            user.send_log("走到了：随机获得10~30活动pt。")
            n = random.randint(10, 30)
            user.send_log(f"获得了{n}pt{句尾}")
            await user.add_event_pt(n)
        return 0
class kuaizou_s(_statusnull):
    id = 'D'
    des = "快走：在活动中，你下次行走距离加倍。"

Game.me = UserData(config.selfqq)
def new_me():
    del Game.me
    Game.me = UserData(config.selfqq)

dragon: Callable[[User], User] = lambda user: User(1, user.buf)

def draw_skill(dr: User):
    return GetSkill(random.randint(0, min(dr.data.dragon_level + 3, len(DragonSkill.id_dict))))
def GetSkill(id: int):
    return DragonSkill.id_dict[id]
class DragonSkill(metaclass=status_meta):
    id = -1
    name = ""
    des = ""
    id_dict: Dict[int, TSkill] = {}
    @classmethod
    def brief_description(cls):
        return f"{cls.id}. {cls.name}"
    @classmethod
    def full_description(cls):
        return f"{cls.id}. {cls.name}\n\t{cls.des}"
    @classmethod
    async def use(cls, user: User, branch: Tree):
        pass

class dadun(DragonSkill):
    id = 0
    name = "打盹"
    des = "没有效果。"
class penhuo(DragonSkill):
    id = 1
    name = "喷火"
    des = "对玩家造成100点伤害。"
    @classmethod
    async def use(cls, user: User, branch: Tree):
        await user.damaged(100 + dragon(user).data.dragon_level * 2)
        if Game.me.check_daily_status('i'):
            user.buf.send(f"火焰解除了寒冰菇的效果{句尾}")
            await Userme(user).remove_daily_status('i', remove_all=True, remover=user)
class yaoren(DragonSkill):
    id = 2
    name = "咬人"
    des = "对玩家造成150点伤害。"
    @classmethod
    async def use(cls, user: User, branch: Tree):
        await user.damaged(150 + dragon(user).data.dragon_level * 3)
class touxi(DragonSkill):
    id = 3
    name = "偷袭"
    des = "对玩家造成100点必中伤害。"
    @classmethod
    async def use(cls, user: User, branch: Tree):
        await user.damaged(100 + dragon(user).data.dragon_level * 2, must_hit=True)
class enhui(DragonSkill):
    id = 4
    name = "恩惠"
    des = "玩家随机获得一张正面卡牌。"
    @classmethod
    async def use(cls, user: User, branch: Tree):
        await user.draw(1, positive={1})
class tukoushui(DragonSkill):
    id = 5
    name = "吐口水"
    des = "玩家随机获得一张非正面卡牌。"
    @classmethod
    async def use(cls, user: User, branch: Tree):
        await user.draw(1, positive={0, -1})
class konghe(DragonSkill):
    id = 6
    name = "恐吓"
    des = "给玩家附加害怕debuff：下次造成伤害减半。"
    @classmethod
    async def use(cls, user: User, branch: Tree):
        await user.add_status('H')
class konghe_s(_statusnull):
    id = 'H'
    des = "恐吓：下次造成伤害减半。"
    @classmethod
    async def OnAttack(cls, count: TCount, user: 'User', attack: 'Attack') -> Tuple[bool]:
        if isinstance(attack, Damage):
            user.send_char(f"因被恐吓，造成伤害减半{句尾}")
            await user.remove_status('H', remove_all=True)
            attack.damage //= 2 ** count
        return False,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnAttack: (Priority.OnAttack.konghe, cls)}
class hudun(DragonSkill):
    id = 7
    name = "护盾"
    des = "下次受到伤害时闪避率+20%。"
    @classmethod
    async def use(cls, user: User, branch: Tree):
        await dragon(user).add_status('d')
class hudun_s(_statusnull):
    id = 'd'
    des = "护盾：受到伤害时闪避率+20%。"
    @classmethod
    async def OnAttacked(cls, count: TCount, user: 'User', attack: 'Attack') -> Tuple[bool]:
        if isinstance(attack, Damage):
            if await attack.counter.pierce():
                user.buf.send(f"护盾的效果被幻想杀手消除了{句尾}")
                await user.remove_status('d', remove_all=True, remover=attack.attacker)
            else:
                user.send_char(f"的闪避率增加了20%{句尾}")
                await user.remove_status('d', remove_all=False)
                attack.dodge_rate += 0.2
        return False,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnAttacked: (Priority.OnAttacked.hudun, cls)}
class shihun(DragonSkill):
    id = 8
    name = "噬魂"
    des = "玩家失去100点MP。"
    @classmethod
    async def use(cls, user: User, branch: Tree):
        atk = AShihun(dr := dragon(user), user, 100)
        await user.attacked(dr, atk)
class AShihun(Attack):
    name = "攻击：噬魂"
    def __init__(self, attacker: 'User', defender: 'User', amount: int):
        self.amount = amount
        super().__init__(attacker, defender)
    async def self_action(self):
        self.defender.send_char(f"失去了{self.amount * self.multiplier}MP{句尾}")
        self.defender.data.mp -= self.amount * self.multiplier
class longwo(DragonSkill):
    id = 9
    name = "龙窝"
    des = "召唤一个幼龙，血量1000，承担龙受到伤害的50%，并使龙的攻击增加50%（不可叠加）。"
    @classmethod
    async def use(cls, user: User, branch: Tree):
        await dragon(user).add_limited_status(SLongwo(1000))
class SLongwo(NumedStatus):
    id = 'L'
    des = '幼龙：承担龙受到伤害的50%，并使龙的攻击增加50%。'
    def __str__(self) -> str:
        return f"{self.des}\n\t剩余血量：{self.num}。"
    @classmethod
    async def OnAttacked(cls, count: TCount, user: 'User', attack: 'Attack') -> Tuple[bool]:
        if isinstance(attack, Damage) and not attack.dodge(): # 不能被幻杀消除？？
            to_def = attack.damage // 2
            attack.damage -= to_def
            for i in count:
                if i.num <= to_def:
                    user.buf.send(f"幼龙承担了{i.num}的伤害{句尾}")
                    to_def -= i.num
                    i.num = 0
                else:
                    user.buf.send(f"幼龙承担了{attack.damage}的伤害{句尾}")
                    i.num -= to_def
                    to_def = 0
                    break
            attack.damage += to_def
        return False,
    @classmethod
    async def OnAttack(cls, count: TCount, user: 'User', attack: 'Attack') -> Tuple[bool]:
        if isinstance(attack, Damage):
            user.buf.send(f"幼龙为龙增加了50%的攻击{句尾}")
            attack.damage = attack.damage * 3 // 2
        return False,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnAttack: (Priority.OnAttack.youlong, cls),
            UserEvt.OnAttacked: (Priority.OnAttacked.youlong, cls)}
class qunlongwushou(DragonSkill):
    id = 10
    name = "群龙无首"
    des = "若boss有幼龙，则对玩家造成300点伤害，否则造成50点伤害。"
    @classmethod
    async def use(cls, user: User, branch: Tree):
        dr = dragon(user)
        if len(dr.check_limited_status('L')) != 0:
            await user.damaged(300 + dragon(user).data.dragon_level * 6)
        else:
            await user.damaged(50 + dragon(user).data.dragon_level)
class longhukaying(DragonSkill):
    id = 11
    name = "龙呼卡应"
    des = "随机抽两个技能，并使用其中编号大的一个技能使用。"
    @classmethod
    async def use(cls, user: User, branch: Tree):
        dr = dragon(user)
        sk1, sk2 = draw_skill(dr), draw_skill(dr)
        dr.send_log(f"抽到了技能{sk1.brief_description()}与{sk2.brief_description()}{句尾}")
        sk = GetSkill(max(sk1.id, sk2.id))
        dr.send_log(f"使用了技能{sk.full_description()}{句尾}")
        await sk.use(user)
class canbaolizhua(DragonSkill):
    id = 12
    name = "残暴利爪"
    des = "对玩家造成玩家血量的伤害。"
    @classmethod
    async def use(cls, user: User, branch: Tree):
        atk = Damage(dr := dragon(user), user, user.data.hp)
        await user.attacked(dr, atk)
class kongzhongcanting(DragonSkill):
    id = 13
    name = "空中餐厅「逻辑」"
    des = "附加全局效果：每次接龙的时候有10%的概率触发。若玩家未死则回复所有血量并失去回复血量除以20的击毙，若玩家当前已死则失去25击毙复活。触发后效果消失。"
    @classmethod
    async def use(cls, user: User, branch: Tree):
        await Userme(user).add_status('"')
class kongzhongcanting_s(_statusnull):
    id = '"'
    des = "空中餐厅「逻辑」：每次接龙的时候有10%的概率触发。若玩家未死则回复所有血量并失去回复血量除以20的击毙，若玩家当前已死则失去25击毙复活。触发后效果消失。"
    is_global = True
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        if random.random() < 0.1:
            if len(user.check_limited_status('d')) != 0:
                user.send_log(f"你被“空中餐厅「逻辑」”复活了，失去了25击毙{句尾}")
                await user.remove_all_limited_status('d')
                await user.add_jibi(-25)
                await Userme(user).remove_status('"', remove_all=False)
            elif user.data.hp != user.data.hp_max:
                lose = ceil(user.data.hp_max - user.data.hp / 20)
                user.send_log(f"你被“空中餐厅「逻辑」”回满了血量，失去了{lose}击毙{句尾}")
                user.data.hp = user.data.hp_max
                await user.add_jibi(-lose)
                await Userme(user).remove_status('"', remove_all=False)
    @classmethod
    async def OnDuplicatedWord(cls, count: TCount, user: 'User', word: str) -> Tuple[bool]:
        if random.random() < 0.1 and len(user.check_limited_status('d')) != 0:
            user.send_log(f"你被“空中餐厅「逻辑」”复活了，失去了25击毙{句尾}")
            await user.remove_all_limited_status('d')
            await user.add_jibi(-25)
            await Userme(user).remove_status('"', remove_all=False)
    @classmethod
    async def OnBombed(cls, count: TCount, user: 'User', word: str) -> Tuple[bool]:
        if random.random() < 0.1 and len(user.check_limited_status('d')) != 0:
            user.send_log(f"你被“空中餐厅「逻辑」”复活了，失去了25击毙{句尾}")
            await user.remove_all_limited_status('d')
            await user.add_jibi(-25)
            await Userme(user).remove_status('"', remove_all=False)
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDragoned: (Priority.OnDragoned.kongzhongcanting, cls),
            UserEvt.OnDuplicatedWord: (Priority.OnDuplicatedWord.kongzhongcanting, cls),
            UserEvt.OnBombed: (Priority.OnBombed.kongzhongcanting, cls)}
class huoyanxuanwo(DragonSkill):
    id = 14
    name = "火焰漩涡"
    des = "对今天所有接龙过的玩家造成100点伤害。"
    @classmethod
    async def use(cls, user: User, branch: Tree):
        qqs = [tree.qq for tree in itertools.chain(*itertools.chain(Tree._objs, *Tree.forests))]
        for qq in set(qqs):
            await User(qq, user.buf).damaged(100 + dragon(user).data.dragon_level * 2)
        if Game.me.check_daily_status('i'):
            user.buf.send(f"火焰解除了寒冰菇的效果{句尾}")
            await Userme(user).remove_daily_status('i', remove_all=True, remover=user)
class xujiadexiwang(DragonSkill):
    id = 15
    name = "虚假的希望"
    des = "回复玩家的所有血量，并对范围7x7的其他玩家造成同等数量的伤害。"
    @classmethod
    async def use(cls, user: User, branch: Tree):
        dmg = user.data.hp_max - user.data.hp
        user.send_log(f"回复了{dmg}的血量{句尾}")
        qqs = {user.qq}
        id = branch.id
        for i, j in itertools.product(range(-3, 4), range(-3, 4)):
            ret = Tree.find((id[0] + i, id[1] + j))
            if ret is not None:
                qqs.add(ret.qq)
        qqs -= {config.selfqq, user.qq}
        for qq in qqs:
            await User(qq, user.buf).damaged(dmg)
class qiangduo(DragonSkill):
    id = 16
    name = "抢夺"
    des = "玩家随机失去一张手牌，若此牌为正面牌，则对玩家造成200点伤害。"
    @classmethod
    async def use(cls, user: User, branch: Tree):
        if len(user.data.hand_card) == 0:
            user.send_log(f"没有手牌{句尾}")
            return
        card = random.choice(user.data.hand_card)
        user.send_log(f"失去了卡牌：{card.name}{句尾}")
        await user.remove_cards([card])
        if card.positive == 1:
            await user.damaged(200 + dragon(user).data.dragon_level * 4)
class qumo(DragonSkill):
    id = 17
    name = "祛魔"
    des = "玩家随机失去一条状态，若状态为非负面状态，则对玩家造成100点伤害。"
    @classmethod
    async def use(cls, user: User, branch: Tree):
        if (l := len(user.data.status) + len(user.data.daily_status) + len(user.data.status_time_checked)) == 0:
            user.send_log(f"没有状态{句尾}")
            return
        i = random.randint(0, l - 1)
        if i <= len(user.data.status):
            st = StatusNull(user.data.status[i])
            user.send_log(f"失去了状态：{st.brief_des}{句尾}")
            await user.remove_status(user.data.status[i], remover=dragon(user))
        elif i <= len(user.data.daily_status):
            i -= len(user.data.status)
            st = StatusDaily(user.data.daily_status[i])
            user.send_log(f"失去了状态：{st.brief_des}{句尾}")
            await user.remove_daily_status(user.data.daily_status[i], remover=dragon(user))
        else:
            i -= len(user.data.status) + len(user.data.daily_status)
            st = user.data.status_time[i]
            user.send_log(f"失去了状态：{st.brief_des}{句尾}")
            await user.remove_limited_status(st, remover=dragon(user))
        if not st.is_debuff:
            await user.damaged(100 + dragon(user).data.dragon_level * 2)

class bizhong(_statusnull):
    id = 'c'
    des = "必中：你的下次攻击必中并且攻击增加50%。"
    @classmethod
    async def OnAttack(cls, count: TCount, user: 'User', attack: 'Attack') -> Tuple[bool]:
        if isinstance(attack, Damage):
            user.send_log(f"的此次攻击必中并且攻击增加{50 * count}%{句尾}")
            attack.must_hit = True
            attack.damage = int(attack.damage * (1 + 0.5 * count))
            await user.remove_status('c')
        return False,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnAttack: (Priority.OnAttack.bizhong, cls)}
class shanbi(_statusnull):
    id = 'f'
    des = '闪避：必定躲避下次受伤。'
    @classmethod
    async def OnAttacked(cls, count: TCount, user: 'User', attack: 'Attack') -> Tuple[bool]:
        if isinstance(attack, Damage):
            user.send_log("触发了闪避的效果，躲避此次受伤。")
            await user.remove_status('f', remove_all=False)
            return True,
        return False,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnAttacked: (Priority.OnAttacked.shanbi, cls)}
class hunluan(_statusnull):
    id = 'X'
    des = "混乱：下次技能选择玩家时随机选择。"
class fuhuoguanghuan(_statusnull):
    id = 'u'
    des = "复活光环：下次因HP归零死亡的复活时间减少至5分钟。"
    @classmethod
    async def OnDeath(cls, count: TCount, user: 'User', killer: 'User', time: int, c: TAttackType) -> Tuple[int, bool]:
        if c.hpzero:
            time = time // 12
            user.send_log(f"因复活光环的效果，死亡时间减少至{time}分钟" + 句尾)
            await user.remove_status('u', remove_all=False)
        return time, False
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDeath: (Priority.OnDeath.fuhuoguanghuan, cls)}
class Smofajiqu(NumedStatus):
    id = 'y'
    des = "魔法汲取：你接下来的每次接龙为你回复150MP。"
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        user.send_log("的魔法汲取为" + user.char + "回复了150MP" + 句尾)
        count[0].num -= 1
        user.data.mp = min(user.data.mp + 150, user.data.mp_max)
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDragoned: (Priority.OnDragoned.mofajiqu, cls)}
class Sqiangshenjianti(NumedStatus):
    id = 'r'
    des = "强身健体：接下来5次受到伤害减半。"
    @classmethod
    async def OnAttacked(cls, count: TCount, user: 'User', attack: 'Attack') -> Tuple[bool]:
        if isinstance(attack, Damage):
            user.send_log("的身体很强壮" + 句尾 + "伤害减半" + 句尾)
            count[0].num -= 1
            attack.damage //= 2
        return False,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnAttacked: (Priority.OnAttacked.qiangshenjianti, cls)}

bingo_id = [(0, 18), (4, 0), (3, 0), (1, 30), (0, 12), (5, 0), (1, 200), (0, 4), (2, 80)]
# 0: 接龙任务，1: 使用一张i~i+39的卡，2: 摸一张i~i+79的卡，3：有人死亡，4：花费或扣除击毙，5：添加一个非死亡状态

class bingo_checker(IEventListener):
    @classmethod
    def check_complete_line(cls):
        return len([1 for b in ((0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)) if all(i in global_state["bingo_state"] for i in b)])
    @classmethod
    def print(cls):
        box = "┌──┬──┬──┐\n│{}│{}│{}│\n├──┼──┼──┤\n│{}│{}│{}│\n├──┼──┼──┤\n│{}│{}│{}│\n└──┴──┴──┘\n".format(*[('ABC'[i // 3] + str(i % 3) if i not in global_state["bingo_state"] else '▓▓') for i in range(9)])
        des = '\n'.join('ABC'[i // 3] + str(i % 3) + "：" + cls.get_des(*bingo_id[i]) for i in range(9) if i not in global_state["bingo_state"])
        return box + des
    @classmethod
    def get_des(cls, i, j):
        if i == 0:
            _, name, func = mission[j]
            return f"接龙任务：{name}"
        elif i == 1: return f"使用一张{j}~{j+39}的卡。"
        elif i == 2: return f"摸一张{j}~{j+79}的卡。"
        elif i == 3: return "有人死亡。"
        elif i == 4: return "花费或扣除击毙。"
        elif i == 5: return "添加一个非死亡状态。"
    @classmethod
    async def complete(cls, id, user: User):
        n1 = cls.check_complete_line()
        global_state["bingo_state"].append(id)
        save_global_state()
        n2 = cls.check_complete_line()
        if n1 == 0 and n2 != 0 or n2 == 8 and n1 != 8:
            active_user = user if user.buf.active == -1 else User(user.buf.active, user.buf)
            active_user.send_char(f"完成了{n2}行bingo，奖励{active_user.char}一张超新星{句尾}")
            if not await active_user.draw(0, cards=[Card(-65537)]):
                active_user.send_log(f"最近已摸过超新星，请把机会留给别人{句尾}")
                global_state["bingo_state"].remove(id)
                save_global_state()
        user.buf.end(cls.print())
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        for id, (i, j) in enumerate(bingo_id):
            if id not in global_state["bingo_state"] and i == 0:
                _, name, func = mission[j]
                if func(branch.word):
                    user.buf.send(f"Bingo！{user.char}完成了接龙任务：{name[:-1]}{句尾}")
                    user.log << f"完成了一次bingo任务{name}"
                    await cls.complete(id, user)
    @classmethod
    async def AfterCardUse(cls, count: TCount, user: 'User', card: TCard) -> Tuple[()]:
        for id, (i, j) in enumerate(bingo_id):
            if id not in global_state["bingo_state"] and i == 1 and j <= card.id < j + 40:
                user.buf.send(f"Bingo！{user.char}完成了任务：使用一张{j}~{j+39}的卡{句尾}")
                user.log << f"完成了一次bingo任务：使用一张{j}~{j+39}的卡。"
                await cls.complete(id, user)
    @classmethod
    async def AfterCardDraw(cls, count: TCount, user: 'User', cards: Iterable[TCard]) -> Tuple[()]:
        for id, (i, j) in enumerate(bingo_id):
            if id not in global_state["bingo_state"] and i == 2 and any(j <= c.id < j + 80 for c in cards):
                user.buf.send(f"Bingo！{user.char}完成了任务：摸一张{j}~{j+79}的卡{句尾}")
                user.log << f"完成了一次bingo任务：摸一张{j}~{j+79}的卡。"
                await cls.complete(id, user)
    @classmethod
    async def OnDeath(cls, count: TCount, user: 'User', killer: 'User', time: int, c: TAttackType) -> Tuple[int, bool]:
        for id, (i, j) in enumerate(bingo_id):
            if id not in global_state["bingo_state"] and i == 3:
                user.buf.send(f"Bingo！{user.char}完成了任务：有人死亡{句尾}")
                user.log << f"完成了一次bingo任务：有人死亡。"
                await cls.complete(id, user)
        return time, False
    @classmethod
    async def OnJibiChange(cls, count: TCount, user: 'User', jibi: int, is_buy: bool) -> Tuple[int]:
        if jibi < 0:
            for id, (i, j) in enumerate(bingo_id):
                if id not in global_state["bingo_state"] and i == 4:
                    user.buf.send(f"Bingo！{user.char}完成了任务：花费或扣除击毙{句尾}")
                    user.log << f"完成了一次bingo任务：花费或扣除击毙。"
                    await cls.complete(id, user)
        return jibi,
    @classmethod
    async def OnStatusAdd(cls, count: TCount, user: 'User', status: TStatusAll, count2: int) -> Tuple[int]:
        if not isinstance(status, SDeath):
            for id, (i, j) in enumerate(bingo_id):
                if id not in global_state["bingo_state"] and i == 5:
                    user.buf.send(f"Bingo！{user.char}完成了任务：添加一个非死亡状态{句尾}")
                    user.log << f"完成了一次bingo任务：添加一个非死亡状态。"
                    await cls.complete(id, user)
        return count,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDragoned: (Priority.OnDragoned.bingo, cls),
            UserEvt.AfterCardUse: (Priority.AfterCardUse.bingo, cls),
            UserEvt.AfterCardDraw: (Priority.AfterCardDraw.bingo, cls),
            UserEvt.OnDeath: (Priority.OnDeath.bingo, cls),
            UserEvt.OnJibiChange: (Priority.OnJibiChange.bingo, cls),
            UserEvt.OnStatusAdd: (Priority.OnStatusAdd.bingo, cls)}
UserData.register_checker(bingo_checker)
