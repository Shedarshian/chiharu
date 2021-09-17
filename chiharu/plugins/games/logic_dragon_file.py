import itertools, hashlib
import random, more_itertools, json, re
from typing import Any, Awaitable, Callable, Coroutine, Dict, Generic, Iterable, List, NamedTuple, Optional, Set, Tuple, Type, TypeVar, TypedDict, Union, final, Iterable, Annotated
from collections import Counter, UserDict, UserList, defaultdict
from functools import lru_cache, partial, wraps
from copy import copy, deepcopy
from math import ceil
from datetime import datetime, timedelta
from functools import reduce
from contextlib import asynccontextmanager
from nonebot.command import CommandSession
from pypinyin import pinyin, Style
from nonebot.command.argfilter import extractors, validators
from .. import config

# TODO 互相交换改成全局status
TQuest = TypedDict('TQuest', id=int, remain=int)
TSteal = TypedDict('TSteal', user=List[int], time=int)
class TGlobalState(TypedDict):
    last_card_user: int
    exchange_stack: List[int]
    lianhuan: List[int]
    quest: Dict[int, List[TQuest]]
    steal: Dict[int, TSteal]
    event_route: List[int]
class TUserData(TypedDict):
    qq: int
    jibi: int
    card: str
    draw_time: int
    death_time: str
    today_jibi: int
    today_keyword_jibi: int
    status: str
    daily_status: str
    status_time: str
    card_limit: int
    shop_drawn_card: int
    event_pt: int
    spend_shop: int
    equipment: str
    event_stage: int
    event_shop: int
    last_dragon_time: str
class TCounter(NamedTuple):
    dodge: bool = False
    rebound: bool = False
    pierce: bool = False
    double: int = 0
    @property
    def valid(self):
        return not (self.dodge or self.rebound)

with open(config.rel('dragon_state.json'), encoding='utf-8') as f:
    global_state: TGlobalState = json.load(f)
def save_global_state():
    with open(config.rel('dragon_state.json'), 'w', encoding='utf-8') as f:
        f.write(json.dumps(global_state, indent=4, separators=(',', ': '), ensure_ascii=False))
quest_print_aux: Dict[int, int] = {qq: 0 for qq in global_state['quest'].keys()}

# global_status : qq = 2711644761
def find_or_new(qq: int):
    t = config.userdata.execute("select * from dragon_data where qq=?", (qq,)).fetchone()
    if t is None:
        config.userdata.execute('insert into dragon_data (qq, jibi, draw_time, today_jibi, today_keyword_jibi, death_time, card, status, daily_status, status_time, card_limit, shop_drawn_card, event_pt, spend_shop, equipment, event_stage, event_shop) values (?, 0, 0, 10, 10, ?, ?, ?, ?, ?, 4, 1, 0, 0, ?, 0, 0)', (qq, '', '', '', '', '[]', '{}'))
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
class CountWaiter:
    def __add__(self, var):
        return var
T = TypeVar('T')
class CounterOnly(Generic[T]):
    def __init__(self):
        self.data: T = None
        self.count: TCount = CountWaiter()
    def __getitem__(self, index) -> TCount:
        if self.data is None:
            self.data = index
        elif self.data != index:
            raise IndexError
        return self.count
    def __setitem__(self, index, val):
        if self.data != index:
            raise IndexError
        self.count = val
    @property
    def data_pair(self):
        return self.data, self.count
del T
TEventList = dict[int, CounterOnly[TEventListener]]
TEvent = Tuple[int, TEventListener]
from enum import IntEnum, auto
class UserEvt(IntEnum):
    OnUserUseCard = auto()
    AfterCardUse = auto()
    AfterCardDraw = auto()
    AfterCardDiscard = auto()
    AfterCardRemove = auto()
    AfterExchange = auto()
    OnDeath = auto()
    OnAttacked = auto()
    OnDodged = auto()
    OnStatusAdd = auto()
    OnStatusRemove = auto()
    CheckJibiSpend = auto()
    OnJibiChange = auto()
    CheckEventptSpend = auto()
    OnEventptChange = auto()
    BeforeDragoned = auto()
    CheckSuguri = auto()
    OnKeyword = auto()
    OnHiddenKeyword = auto()
    OnDuplicatedWord = auto()
    OnBombed = auto()
    OnDragoned = auto()
    OnNewDay = auto()
class Priority: # 依照每个优先级从前往后find，而不是iterate
    class OnUserUseCard(IntEnum):
        temperance = auto()
        xingyunhufu = auto()
        cantuse = auto()
    class AfterCardUse(IntEnum):
        pass
    class AfterCardDraw(IntEnum):
        imitator = auto()
    class AfterCardDiscard(IntEnum):
        pass
    class AfterCardRemove(IntEnum):
        pass
    class AfterExchange(IntEnum):
        pass
    class OnDeath(IntEnum):
        invincible = auto()
        miansi = auto()
        sihuihuibizhiyao = auto()
        hongsezhihuan = auto()
        inv_sihuihuibizhiyao = auto()
        death = auto()
        lveduozhebopu = auto()
        huiye = auto()
        inv_huiye = auto()
    class OnAttacked(IntEnum):
        pass
    class OnDodged(IntEnum):
        pass
    class OnStatusAdd(IntEnum):
        jiaodai = auto()
        inv_jiaodai = auto()
        sunflower = auto()
        twinsunflower = auto()
        panjue = auto()                 # contains both a and b
        panjue_activated = auto()       # contains both a and b
    class OnStatusRemove(IntEnum):
        pass
    class CheckJibiSpend(IntEnum):
        bianyaqi = auto()
        steamsummer = auto()
        beijingcard = auto()
    class OnJibiChange(IntEnum):
        gaojie = auto()
        inv_gaojie = auto()
        bianyaqi = auto()
        inv_bianyaqi = auto()
        steamsummer = auto()
        beijingcard = auto()
    class CheckEventptSpend(IntEnum):
        pass
    class OnEventptChange(IntEnum):
        pass
    class BeforeDragoned(IntEnum):
        death = auto()
        shengbing = auto()
        minus1ma = auto()
        plus1ma = auto()
        iceshroom = auto()
        hotshroom = auto()
        ourostone = auto()              # contains two buffs
    class CheckSuguri(IntEnum):
        jisuzhuangzhi = auto()
    class OnKeyword(IntEnum):
        pass
    class OnHiddenKeyword(IntEnum):
        cunqianguan = auto()
        inv_cunqianguan = auto()
    class OnDuplicatedWord(IntEnum):
        hermit = auto()
    class OnBombed(IntEnum):
        hermit = auto()
    class OnDragoned(IntEnum):
        queststone = auto()
        quest = auto()
        xingyunhufu = auto()
        lveduozhebopu = auto()
        plus2 = auto()
        xixuegui = auto()
        panjue = auto()                 # contains both a and b
        panjuecheck = auto()            # contains both a and b
        jack_in_the_box = auto()
        star = auto()
        dihuopenfa = auto()
    class OnNewDay(IntEnum):
        sunflower = auto()
        twinsunflower = auto()
        inv_sunflower = auto()
        inv_twinsunflower = auto()
newday_check = ["", "", ""]
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
    async def OnAttacked(cls, count: TCount, user: 'User') -> Tuple[bool]:
        pass
    @classmethod
    async def OnDodged(cls, count: TCount, user: 'User') -> Tuple[()]:
        pass
    @classmethod
    def OnStatusAdd(cls, count: TCount, user: 'User', status: TStatusAll, count2: int) -> Tuple[int]:
        """Called when a status is added.
        
        Arguments:
        status: a str for statusnull/statusdaily, or a T_status object.
        count2: the count of the status added.
        
        Returns:
        int: the count of the status really add."""
        pass
    @classmethod
    def OnStatusRemove(cls, count: TCount, user: 'User', status: TStatusAll, remove_all: bool) -> Tuple[bool]:
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
    async def OnEventptChange(cls, count: TCount, user: 'User', event_pt: int) -> Tuple[int]:
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
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree') -> Tuple[()]:
        """Called when the user complete a dragon.
        
        Arguments:
        branch: the dragon branch."""
        pass
    @classmethod
    async def OnNewDay(cls, count: TCount, user: 'User') -> Tuple[()]:
        """Called when new day begins."""
        pass
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {}
TBoundIntEnum = TypeVar('TBoundIntEnum', bound=IntEnum)

class Game:
    session_list: List[CommandSession] = []
    userdatas: Dict[int, 'UserData'] = {}
    @classmethod
    def wrapper_noarg(cls, f: Awaitable):
        @wraps(f)
        async def _f(*args, **kwargs):
            try:
                return await f(*args, **kwargs)
            finally:
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
    insert = None
    reverse = None
    sort = None
class Wrapper:
    def __init__(self, qq):
        self.qq = qq
    def __lshift__(self, log):
        config.logger.dragon << f"【LOG】用户{self.qq}" + log

class UserData:
    event_listener_init: defaultdict[int, TEventList] = defaultdict(lambda: defaultdict(CounterOnly))
    def __init__(self, qq: int):
        self._qq = qq
        self.node: TUserData = dict(find_or_new(qq))
        self.hand_card = [] if self.node['card'] == '' else [Card(int(x)) for x in self.node['card'].split(',')]
        def save(key, value):
            config.userdata.execute(f"update dragon_data set {key}=? where qq=?", (str(value), self.qq))
        self.status_time: List[T_status] = property_list(partial(save, 'status_time'), [])
        self.status_time.data = eval(self.node['status_time'])
        self.equipment = property_dict(partial(save, 'equipment'), {})
        self.equipment.data = eval(self.node['equipment'])
        self._reregister_things()
    def _reregister_things(self):
        self.event_listener: defaultdict[int, TEventList] = deepcopy(self.event_listener_init)
        for c in self.hand_card:
            self._register_card(c)
        for s in itertools.chain(map(StatusNull, self.status), map(StatusDaily, self.daily_status)):
            self._register_status(s)
        for s in self.status_time_checked:
            self._register_status_time(s)
    def _register_card(self, c: TCard, count=1):
        self._register(c, to_add=count)
    def _register_status(self, s: Union[T_statusdaily, T_statusnull], count=1):
        if s.is_global == (self.qq == config.selfqq):
            self._register(s, to_add=count)
    def _register_status_time(self, s: T_status):
        if s.is_global == (self.qq == config.selfqq):
            self._register(s, [s])
    def _register(self, eln: 'IEventListener', to_add=1):
        for key, (priority, el) in eln.register().items():
            self.event_listener[key][priority][el] += to_add
    def _deregister_card(self, c: TCard, /, is_all=False):
        self._deregister(c, is_all=is_all)
    def _deregister_status(self, s: Union[T_statusdaily, T_statusnull], /, is_all=False):
        if s.is_global == (self.qq == config.selfqq):
            self._deregister(s, is_all=is_all)
    def _deregister_status_time(self, eln: T_status, /, is_all=False):
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
    def card_limit(self):
        return self.node['card_limit']
    @card_limit.setter
    def card_limit(self, value):
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
    def IterAllEventList(self, evt: UserEvt, priority: Type[TBoundIntEnum], /, no_global: bool=False):
        user_list = self.data.event_listener[evt]
        global_list = me.event_listener[evt]
        for p in priority:
            ret = user_list.get(p)
            if not no_global:
                ret = ret or global_list.get(p)
            if ret is not None:
                yield ret.data_pair
    def add_status(self, s: str, count=1):
        # Event OnStatusAdd
        for eln, n in self.IterAllEventList(UserEvt.OnStatusAdd, Priority.OnStatusAdd):
            count, = eln.OnStatusAdd(n, self, StatusNull(s), count)
            if count == 0:
                break
        else:
            self.data.status += s * count
            self.log << f"增加了永久状态{s}，当前状态为{self.data.status}。"
            self.data._register_status(StatusNull(s), count=count)
    def add_daily_status(self, s: str, count=1):
        # Event OnStatusAdd
        for eln, n in self.IterAllEventList(UserEvt.OnStatusAdd, Priority.OnStatusAdd):
            count, = eln.OnStatusAdd(n, self, StatusDaily(s), count)
            if count == 0:
                break
        else:
        # if s in _card.daily_debuffs and s != 'd' and self.check_status('8'):
        #     self.remove_status('8', remove_all=False)
        #     self.send_log("触发了胶带的效果，免除此负面状态！")
        #     return
        # if s not in _card.daily_debuffs and self.check_status('9'):
        #     self.remove_status('9', remove_all=False)
        #     self.send_log("触发了反转·胶带的效果，免除此非负面状态！")
        #     return
            self.data.daily_status += s * count
            self.log << f"增加了每日状态{s}，当前状态为{self.data.daily_status}。"
            self.data._register_status(StatusDaily(s), count=count)
    def add_limited_status(self, s: Union[str, T_status], *args, **kwargs):
        if isinstance(s, str):
            ss = Status(s)(*args, **kwargs)
        else:
            ss = s
        # Event OnStatusAdd
        for eln, n in self.IterAllEventList(UserEvt.OnStatusAdd, Priority.OnStatusAdd):
            count, = eln.OnStatusAdd(n, self, ss)
            if count == 0:
                break
        else:
        # if ss.is_debuff and ss.id != 'd' and self.check_status('8'):
        #     self.remove_status('8', remove_all=False)
        #     self.send_log("触发了胶带的效果，免除此负面状态！")
        #     return
        # if not ss.is_debuff and self.check_status('9'):
        #     self.remove_status('9', remove_all=False)
        #     self.send_log("触发了反转·胶带的效果，免除此非负面状态！")
        #     return
            self.data.status_time.append(ss)
            self.log << f"增加了限时状态{ss}。"
            self.data._register_status_time(ss)
    def remove_status(self, s: str, /, remove_all=True):
        # Event OnStatusRemove
        for eln, n in self.IterAllEventList(UserEvt.OnStatusRemove, Priority.OnStatusRemove):
            dodge, = eln.OnStatusRemove(n, self, StatusNull(s), remove_all)
            if dodge:
                break
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
    def remove_daily_status(self, s: str, /, remove_all=True):
        # Event OnStatusRemove
        for eln, n in self.IterAllEventList(UserEvt.OnStatusRemove, Priority.OnStatusRemove):
            dodge, = eln.OnStatusRemove(n, self, StatusDaily(s), remove_all)
            if dodge:
                break
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
    def remove_limited_status(self, s: T_status):
        # Event OnStatusRemove
        for eln, n in self.IterAllEventList(UserEvt.OnStatusRemove, Priority.OnStatusRemove):
            dodge, = eln.OnStatusRemove(n, self, s, False)
            if dodge:
                break
        else:
            self.data.status_time.remove(s)
            self.log << f"移除了一个限时状态{s}。"
            self.data._deregister(s, is_all=False)
    def remove_all_limited_status(self, s: str):
        l = [c for c in self.data.status_time if c.id == s]
        if len(l) == 0:
            return self.data.status_time
        # Event OnStatusRemove
        for eln, n in self.IterAllEventList(UserEvt.OnStatusRemove, Priority.OnStatusRemove):
            dodge, = eln.OnStatusRemove(n, self, l[0], True)
            if dodge:
                break
        else:
            i = 0
            while i < len(self.data.status_time):
                t: T_status = self.data.status_time[i]
                if not t.check() or t.id == s:
                    self.data.status_time.pop(i)
                else:
                    i += 1
            self.log << f"移除了所有限时状态{s}。"
            self.data._deregister(s, is_all=True)
            return self.data.status_time
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
                pt = await eln.CheckEventptSpend(n, self, pt)
            if current_event_pt < pt:
                return False
            pt = -pt
        # Event OnEventptChange
        for eln, n in self.IterAllEventList(UserEvt.OnEventptChange, Priority.OnEventptChange):
            pt = await eln.OnEventptChange(n, self, pt, is_buy)
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
                jibi = await eln.CheckJibiSpend(n, self, jibi)
            if current_jibi < jibi:
                return False
            jibi = -jibi
        # Event OnJibiChange
        for eln, n in self.IterAllEventList(UserEvt.OnJibiChange, Priority.OnJibiChange):
            jibi = await eln.OnJibiChange(n, self, jibi, is_buy)
            if jibi == 0:
                break
        self.data.jibi = max(self.data.jibi + jibi, 0)
        # if q := self.data.check_equipment(0):
        #     if jibi > 0 and random.random() < 0.05 * q:
        #         jibi *= 2
        #         self.send_char(f"触发了比基尼的效果，获得击毙加倍为{abs(jibi)}！")
        #     else: q = 0
        # dodge = False
        # if r := self.data.check_equipment(1):
        #     if jibi < 0 and random.random() < r / (20 + r):
        #         dodge = True
        #         self.send_char(f"触发了学生泳装的效果，本次免单！")
        # if m := self.check_status('S'):
        #     if is_buy and not dodge:
        #         jibi //= 2 ** m
        #         self.send_char(f"触发了{f'{m}次' if m > 1 else ''}Steam夏季特卖的效果，花费击毙减半为{abs(jibi)}！")
        #         self.remove_status('S')
        #     else: m = 0
        # dodge2 = False
        # if t := self.check_status('n'):
        #     if not dodge and jibi < 0 and -jibi >= self.data.jibi / 2:
        #         dodge2 = True
        #         self.remove_status('n', remove_all=False)
        #         self.send_char(f"触发了深谋远虑之策的效果，此次免单！")
        if is_buy and jibi < 0:
            self.data.spend_shop += abs(jibi)
            self.log << f"累计今日商店购买至{self.data.spend_shop}。"
        self.data.save_status_time()
        return True
    async def kill(self, hour: int=2, minute: int=0, killer=None, jump=False):
        """击杀玩家。"""
        killer = killer or self
        config.logger.dragon << f"【LOG】尝试击杀玩家{self.qq}。"
        time_num = 60 * hour + minute
        c = await self.check_attacked(killer)
        if c.dodge:
            return
        elif c.rebound:
            await killer.kill(killer=self)
            return
        elif c.double:
            time_num *= 2 ** c.double
        dodge = False
        # Event OnDeath
        for eln, n in self.IterAllEventList(UserEvt.OnDeath, Priority.OnDeath):
            time_num, dodge = await eln.OnDeath(n, self, killer, time_num, c)
            if dodge:
                break
        # if (l := self.check_limited_status('o')) and not dodge and not jump:
        #     o1 = o2 = None
        #     for o in l:
        #         if o.is_pumpkin:
        #             o2 = o
        #         else:
        #             o1 = o
        #     if o2 is not None:
        #         m = min(o2.num, time_num)
        #         o2 -= m
        #         time_num -= m
        #         self.send_log(f"的南瓜头为你吸收了{m}分钟的死亡时间！", end='')
        #         if time_num == 0:
        #             dodge = True
        #             self.send_char("没死！")
        #         else:
        #             self.buf.send("")
        #     if o1 is not None and not dodge:
        #         m = min(o1.num, time_num)
        #         o1 -= m
        #         time_num -= m
        #         self.send_log(f"的坚果墙为你吸收了{m}分钟的死亡时间！", end='')
        #         if time_num == 0:
        #             dodge = True
        #             self.send_char("没死！")
        #         else:
        #             self.buf.send("")
        #     self.data.save_status_time()
        #     global global_state
        #     if self.qq in global_state['lianhuan']:
        #         if c.pierce:
        #             global_state['lianhuan'].remove(self.qq)
        #             save_global_state()
        #             self.send_log("铁索连环的效果被幻想杀手消除了！")
        #         else:
        #             l = copy(global_state['lianhuan'])
        #             global_state['lianhuan'] = []
        #             save_global_state()
        #             l.remove(self.qq)
        #             self.buf.send(f"由于铁索连环的效果，{' '.join(f'[CQ:at,qq={target}]' for target in l)}个人也一起死了！")
        #             self.log << f"触发了铁索连环的效果至{l}。"
        #             for target in l:
        #                 await User(target, self.buf).kill(hour=hour)
    async def draw(self, n: int, /, positive=None, cards=None):
        """抽卡。将卡牌放入手牌。"""
        cards = draw_cards(positive, n) if cards is None else cards
        self.log << f"抽到的卡牌为{cards_to_str(cards)}。"
        self.send_char('抽到的卡牌是：')
        for c in cards:
            if c.des_need_init:
                await c.on_draw(self)
            self.buf.send(c.full_description(self.qq))
        for c in cards:
            if not c.consumed_on_draw:
                self.add_card(c)
            if not c.des_need_init:
                await c.on_draw(self)
        # Event AfterCardDraw
        for el, n in self.IterAllEventList(UserEvt.AfterCardDraw, Priority.AfterCardDraw):
            await el.AfterCardDraw(n, self, cards)
        self.data.set_cards()
        self.log << f"抽完卡牌，当前手牌为{cards_to_str(self.data.hand_card)}。"
    async def draw_and_use(self, card: TCard):
        """抽取卡牌，立即使用，并发动卡牌的销毁效果。不经过手牌。"""
        if card.des_need_init:
            await card.on_draw(self)
        self.log << f"抽取并使用了卡牌{card.name}。"
        self.send_char('抽到并使用了卡牌：\n' + card.full_description(self.qq))
        if not card.des_need_init:
            await card.on_draw(self)
        await self.use_card_effect(card)
        await card.on_remove(self)
    async def use_card_effect(self, card: TCard):
        """发动卡牌的使用效果。"""
        self.log << f"发动卡牌的使用效果{card.name}。"
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
        target_limit = target.data.card_limit
        if len(self_hand_cards) > target_limit:
            self.buf.send(f"该玩家手牌已超出上限{len(self_hand_cards) - target_limit}张！多余的牌已被弃置。")
            target.log << f"手牌为{cards_to_str(self_hand_cards)}，超出上限{target_limit}，自动弃置。"
            await target.discard_cards(copy(self_hand_cards[target_limit:]))
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
        try:
            yield
            # discard
            x = len(self.data.hand_card) - self.data.card_limit
            while x > 0:
                save_data()
                if not self.active:
                    self.buf.send(f"该玩家手牌已超出上限{x}张！多余的牌已被弃置。")
                    self.log << f"手牌为{cards_to_str(self.data.hand_card)}，超出上限{self.data.card_limit}，自动弃置。"
                    await self.discard_cards(copy(self.data.hand_card[self.data.card_limit:]))
                else:
                    ret2 = f"您的手牌已超出上限{x}张！请先选择一些牌弃置（输入id号，使用空格分隔）：\n" + \
                        "\n".join(c.full_description(self.qq) for c in self.data.hand_card)
                    self.log << f"手牌超出上限，用户选择弃牌。"
                    await self.buf.flush()
                    l = await self.buf.aget(prompt=ret2,
                        arg_filters=[
                            extractors.extract_text,
                            lambda s: list(map(int, re.findall(r'\-?\d+', str(s)))),
                            validators.fit_size(x, x, message="请输入正确的张数。"),
                            validators.ensure_true(lambda l: self.data.check_throw_card(l), message="您选择了错误的卡牌！"),
                            validators.ensure_true(lambda l: 53 not in l, message="空白卡牌不可因超出手牌上限而被弃置！")
                        ])
                    self.buf.send("成功弃置。")
                    await self.discard_cards([Card(i) for i in l])
                x = len(self.data.hand_card) - self.data.card_limit
            await self.buf.flush()
        finally:
            self.data.set_cards()
            save_data()
    async def event_move(self, n):
        self.log << f"走了{n}格。"
        current = self.data.event_stage
        begin = current.stage
        while n != 0:
            if p := self.check_status('D'):
                self.remove_status('D')
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
    async def check_attacked(self, killer: 'User', not_valid: TCounter=TCounter()):
        if self == killer:
            return TCounter()
        if self.check_status('0') and not not_valid.dodge:
            self.send_char("触发了幻想杀手的效果，防住了对方的攻击！")
            self.remove_status('0', remove_all=False)
            return TCounter(dodge=True)
        if killer.check_status('0'):
            pierce = True
            def pierce_f():
                killer.buf.send(f"但{killer.char}触发了幻想杀手的效果，无视了对方的反制！")
                killer.remove_status('0', remove_all=False)
        else:
            pierce = False
        if self.check_status('v') and not not_valid.rebound:
            self.send_char("触发了矢量操作的效果，反弹了对方的攻击！")
            self.remove_status('v', remove_all=False)
            if pierce:
                pierce_f()
            else:
                return TCounter(rebound=True)
        if (n := killer.check_status('v')) and not not_valid.double:
            killer.send_char("触发了矢量操作的效果，攻击加倍！")
            killer.remove_status('v')
            return TCounter(double=n)
        return TCounter()

Userme: Callable[[User], User] = lambda user: User(config.selfqq, user.buf)

def save_data():
    config.userdata_db.commit()
    me.reload()

def cards_to_str(cards: List[TCard]):
    return '，'.join(c.name for c in cards)
def draw_cards(positive: Optional[Set[int]]=None, k: int=1):
    x = positive is not None and len(positive & {-1, 0, 1}) != 0
    cards = [c for c in _card.card_id_dict.values() if c.id >= 0 and (not x or x and c.positive in positive)]
    weight = [c.weight for c in cards]
    if me.check_daily_status('j') and (not x or x and (-1 in positive)):
        return [(Card(-1) if random.random() < 0.2 else random.choices(cards, weight)[0]) for i in range(k)]
    l = random.choices(cards, weight, k=k)
    return l
def draw_card(positive: Optional[Set[int]]=None):
    return draw_cards(positive, k=1)[0]
def equips_to_str(equips: Dict[int, TEquipment]):
    return '，'.join(f"{count}*{c.name}" for c, count in equips.items())

from nonebot.typing import Filter_T
from nonebot.command.argfilter.validators import _raise_failure
def ensure_true_lambda(bool_func: Callable[[Any], bool], message_lambda: Callable[[Any], str]) -> Filter_T:
    """
    Validate any object to ensure the result of applying
    a boolean function to it is True.
    """

    def validate(value):
        if bool_func(value) is not True:
            _raise_failure(message_lambda(value))
        return value

    return validate

from abc import ABCMeta, abstractmethod
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

class _statusall(IEventListener, metaclass=status_meta):
    id = ""
    des = ""
    is_debuff = False
    is_global = False
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
    @abstractmethod
    def double(self) -> List[T_status]:
        return [self]

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
        return f"{self.des}\n\t结束时间：{delta.seconds // 60}分钟。"
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

@final
class SQuest(NumedStatus):
    id = 'q'
    @property
    def des(self):
        return f"今日任务：{mission[self.quest_id][1]}"
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
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree') -> Tuple[()]:
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
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDragoned: (Priority.OnDragoned.quest, cls)}

@final
class SBian(NumedStatus):
    id = 'b'
    des = '月下彼岸花：你每接龙三次会损失1击毙。'
    is_debuff = True
    def __str__(self) -> str:
        return f"{self.des}\n\t剩余次数：{(self.num + 2) // 3}次。"
    def double(self) -> List[T_status]:
        return [self, self.__class__(self.num)]

@final
class SCian(NumedStatus):
    id = 'c'
    des = '反转·月下彼岸花：你每接龙三次会获得1击毙。'
    def __str__(self) -> str:
        return f"{self.des}\n\t剩余次数：{(self.num + 2) // 3}次。"
    def double(self) -> List[T_status]:
        return [self, self.__class__(self.num)]

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

class ListStatus(_status):
    def __init__(self, s: Union[str, List]):
        if isinstance(s, str):
            self.list : List = eval(s)
        else:
            self.list = s
    def check(self) -> bool:
        return len(self.list) > 0
    def __repr__(self) -> str:
        return self.construct_repr(str(self.list))
    def __add__(self, other: List) -> T_status:
        return self.__class__(self.list + other)
    __sub__ = None
    def __iadd__(self, other: List) -> T_status:
        self.list += other
        return self
    __isub__ = None

@final
class SLe(ListStatus):
    id = 'l'
    is_debuff = True
    des = '乐不思蜀：不能从以下节点接龙：'
    def check(self) -> bool:
        return True
    def __str__(self) -> str:
        from .logic_dragon import Tree
        ids = [tree.id_str for tree in Tree.get_active()]
        return f"{self.des}\n\t{','.join(c for c in self.list if c in ids)}。"
    def double(self) -> List[T_status]:
        return [self]

@final
class SKe(ListStatus):
    id = 'k'
    is_debuff = True
    des = '反转·乐不思蜀：不能从以下节点接龙：'
    def check(self) -> bool:
        return True
    def __str__(self) -> str:
        from .logic_dragon import Tree
        ids = [tree.id_str for tree in Tree.get_active()]
        return f"{self.des}\n\t{','.join(c for c in self.list if c in ids)}。"
    def double(self) -> List[T_status]:
        return [self]

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
        if len(bases) != 0 and 'status_dict' in bases[0].__dict__:
            if status := attrs.get('status'):
                @classmethod
                async def use(self, user: User):
                    user.add_status(status)
                attrs['use'] = use
            elif status := attrs.get('daily_status'):
                @classmethod
                async def use(self, user: User):
                    user.add_daily_status(status)
                attrs['use'] = use
            elif status := attrs.get('limited_status'):
                @classmethod
                async def use(self, user: User):
                    user.add_limited_status(status, *attrs['limited_init'])
                attrs['use'] = use
            elif status := attrs.get('global_status'):
                @classmethod
                async def use(self, user: User):
                    Userme(user).add_status(status)
                attrs['use'] = use
            elif status := attrs.get('global_daily_status'):
                @classmethod
                async def use(self, user: User):
                    Userme(user).add_daily_status(status)
                attrs['use'] = use
            elif status := attrs.get('global_limited_status'):
                @classmethod
                async def use(self, user: User):
                    Userme(user).add_limited_status(status, *attrs['global_limited_init'])
                attrs['use'] = use
            elif status := attrs.get('on_draw_status'):
                to_send = attrs.get('on_draw_send')
                to_send_char = attrs.get('on_draw_send_char')
                @classmethod
                async def on_draw(self, user: User):
                    user.add_status(status)
                    if to_send:
                        user.buf.send(to_send)
                    if to_send_char:
                        user.send_char(to_send_char)
                attrs['on_draw'] = on_draw
            elif status := attrs.get('on_draw_daily_status'):
                to_send = attrs.get('on_draw_send')
                to_send_char = attrs.get('on_draw_send_char')
                @classmethod
                async def on_draw(self, user: User):
                    user.add_daily_status(status)
                    if to_send:
                        user.buf.send(to_send)
                    if to_send_char:
                        user.send_char(to_send_char)
                attrs['on_draw'] = on_draw
            elif status := attrs.get('on_draw_limited_status'):
                to_send = attrs.get('on_draw_send')
                to_send_char = attrs.get('on_draw_send_char')
                @classmethod
                async def on_draw(self, user: User):
                    user.add_limited_status(status, *attrs['limited_init'])
                    if to_send:
                        user.buf.send(to_send)
                    if to_send_char:
                        user.send_char(to_send_char)
                attrs['on_draw'] = on_draw
            elif status := attrs.get('on_draw_global_status'):
                to_send = attrs.get('on_draw_send')
                to_send_char = attrs.get('on_draw_send_char')
                @classmethod
                async def on_draw(self, user: User):
                    Userme(user).add_status(status)
                    if to_send:
                        user.buf.send(to_send)
                attrs['on_draw'] = on_draw
            elif status := attrs.get('on_draw_global_daily_status'):
                to_send = attrs.get('on_draw_send')
                to_send_char = attrs.get('on_draw_send_char')
                @classmethod
                async def on_draw(self, user: User):
                    Userme(user).add_daily_status(status)
                    if to_send:
                        user.buf.send(to_send)
                attrs['on_draw'] = on_draw
            elif status := attrs.get('on_draw_global_limited_status'):
                to_send = attrs.get('on_draw_send')
                to_send_char = attrs.get('on_draw_send_char')
                @classmethod
                async def on_draw(self, user: User):
                    Userme(user).add_limited_status(status, *attrs['limited_init'])
                    if to_send:
                        user.buf.send(to_send)
                attrs['on_draw'] = on_draw
            c = type.__new__(cls, clsname, bases, attrs)
            bases[0].card_id_dict[attrs['id']] = c
        else:
            c = type.__new__(cls, clsname, bases, attrs)
        return c
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
    def can_use(cls, user: User) -> bool:
        return True
    @classmethod
    def full_description(cls, qq):
        return f"{cls.id}. {cls.name}\n\t{cls.description}"

class supernova(_card):
    name = "超新星"
    id = -65536
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
        await user.kill()
    @classmethod
    def can_use(cls, user: User) -> bool:
        return False

class vampire(_card):
    name = "吸血鬼"
    id = -2
    positive = 1
    weight = 0
    description = "此牌通常情况下无法被抽到。2小时内免疫死亡。"
    @classmethod
    async def use(cls, user: User) -> None:
        user.add_limited_status(SInvincible(datetime.now() + timedelta(hours=2)))
class SInvincible(TimedStatus):
    id = 'v'
    des = '无敌：免疫死亡。'
    @classmethod
    async def OnDeath(cls, count: TCount, user: 'User', killer: 'User', time: int, c: TCounter) -> Tuple[int, bool]:
        if c.pierce:
            user.send_log("无敌的效果被幻想杀手消除了！")
            user.remove_all_limited_status('v')
        else:
            user.send_log("触发了无敌的效果，免除死亡！")
            return time, True

class magician(_card):
    name = "I - 魔术师"
    id = 1
    positive = 1
    description = "选择一张你的手牌（不可选择暴食的蜈蚣），执行3次该手牌的效果，并弃置该手牌。此后一周内不得使用该卡。"
    @classmethod
    async def use(cls, user: User):
        if await user.choose():
            config.logger.dragon << f"【LOG】询问用户{user.qq}选择牌执行I - 魔术师。"
            l = await user.buf.aget(prompt="请选择你手牌中的一张牌（不可选择暴食的蜈蚣），输入id号。\n" + "\n".join(c.full_description(user.qq) for c in user.data.hand_card),
                arg_filters=[
                        extractors.extract_text,
                        lambda s: list(map(int, re.findall(r'\-?\d+', str(s)))),
                        validators.fit_size(1, 1, message="请输入正确的张数。"),
                        validators.ensure_true(lambda l: l[0] in _card.card_id_dict and Card(l[0]) in user.data.hand_card, message="您选择了错误的卡牌！"),
                        ensure_true_lambda(lambda l: Card(l[0]).can_use(user), message_lambda=lambda l: Card(l[0]).failure_message),
                        validators.ensure_true(lambda l: 56 not in l, message="此牌不可选择！")
                    ])
            card = Card(l[0])
            config.logger.dragon << f"【LOG】用户{user.qq}选择了卡牌{card.name}。"
            user.send_char('使用了三次卡牌：\n' + card.full_description(user.qq))
            await user.discard_cards([card])
            user.add_limited_status(SCantUse(datetime.now() + timedelta(weeks=1), l[0]))
            await user.use_card_effect(card)
            await user.use_card_effect(card)
            await user.use_card_effect(card)
class SCantUse(TimedStatus):
    id = 'm'
    is_debuff = True
    @property
    def des(self):
        return f"疲劳：不可使用卡牌【{Card(self.card_id).name}】。"
    def __init__(self, s: Union[str, datetime], card_id: int):
        super().__init__(s)
        self.card_id = card_id
    def __repr__(self) -> str:
        return self.construct_repr(self.time.isoformat(), self.card_id)
    def __str__(self) -> str:
        delta = self.time - datetime.now()
        return f"{self.des}\n\t结束时间：{delta.seconds // 60}分钟。"
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
            await User(q, user.buf).kill(killer=user)

class empress(_card):
    name = "III - 女皇"
    id = 3
    description = "你当前所有任务的可完成次数+5。如果当前手牌无任务之石，则为你派发一个可完成3次的任务，每次完成获得3击毙，下次刷新时消失。"
    positive = 1
    @classmethod
    async def use(cls, user: User) -> None:
        if Card(67) in user.data.hand_card:
            for q in global_state['quest'][user.qq]:
                q["remain"] += 5
            user.send_char("的任务剩余次数增加了5！")
        else:
            user.add_limited_status(SQuest(3, 3, n := get_mission()))
            user.send_char(f"获得了一个任务：{mission[n][1]}")

class emperor(_card):
    name = "IV - 皇帝"
    id = 4
    positive = 1
    description = "为你派发一个随机任务，可完成10次，每次完成获得2击毙，下次刷新时消失。"
    @classmethod
    async def use(cls, user: User) -> None:
        user.add_limited_status(SQuest(10, 2, n := get_mission()))
        user.send_char(f"获得了一个任务：{mission[n][1]}")

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
            u.remove_all_limited_status('d')
            user.buf.send("已复活！" + ("（虽然目标并没有死亡）" if n else ''))

class strength(_card):
    name = "VIII - 力量"
    id = 8
    positive = 0
    description = "加倍你身上所有的非持有性buff，消耗2^n-1击毙。击毙不足则无法使用。"
    failure_message = "你的击毙不足！"
    @classmethod
    def can_use(cls, user: User) -> bool:
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
            user.add_status(c)
        for c in user.data.daily_status:
            user.add_daily_status(c)
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
    description = "直至下次刷新前，在商店增加抽奖机，可以消耗5击毙抽奖。"
class wheel_of_fortune_s(_statusnull):
    id = 'O'
    des = "X - 命运之轮：直至下次刷新前，在商店增加抽奖机，可以消耗5击毙抽奖。"
    is_global = True
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {}

class justice(_card):
    name = "XI - 正义"
    id = 11
    positive = 1
    description = "现在你身上每有一个buff，奖励你5击毙。"
    @classmethod
    async def use(cls, user: User):
        n = len(user.data.status) + len(user.data.daily_status) + len(user.data.status_time_checked)
        user.buf.send(f"你身上有{n}个buff，奖励你{n * 5}个击毙。")
        await user.add_jibi(n * 5)

class hanged_man(_card):
    name = "XII - 倒吊人"
    id = 12
    positive = 1
    description = "你立即死亡，然后免疫你下一次死亡。"
    @classmethod
    async def use(cls, user: User):
        await user.kill()
        user.add_status('r')
class miansi(_statusnull):
    id = 'r'
    des = "免死：免疫你下一次死亡。"
    @classmethod
    async def OnDeath(cls, count: TCount, user: User, killer: User, time: int, c: TCounter) -> Tuple[int, bool]:
        user.send_log("触发了免死的效果，免除死亡！")
        user.remove_status('r', remove_all=False)
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
    description = "随机抽取1名玩家，下次刷新前祂不能使用卡牌。"
    @classmethod
    async def use(cls, user: User) -> None:
        l = config.userdata.execute("select qq from dragon_data where qq<>?", (config.selfqq,)).fetchall()
        q: int = random.choice(l)["qq"]
        user.send_char(f"抽到了[CQ:at,qq={q}]！")
        u = User(q, user.buf)
        c = await u.check_attacked(user, not_valid=TCounter(double=1))
        if c.dodge:
            return
        elif c.rebound:
            user.add_daily_status('T')
        else:
            u.add_daily_status('T')
class temperance_s(_statusdaily):
    id = 'T'
    des = "XIV - 节制：下次刷新前你不能使用卡牌。"
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
        await u.kill(killer=user)

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
        l = config.userdata.execute("select qq from dragon_data where qq<>?", (config.selfqq,)).fetchall()
        l: List[int] = [c['qq'] for c in l]
        p: List[int] = []
        for i in range(3):
            p.append(random.choice(l))
            l.remove(p[-1])
        user.send_char(f"抽到了{'，'.join(f'[CQ:at,qq={q}]' for q in p)}！")
        for q in p:
            await User(q, user.buf).kill(killer=user)

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
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree') -> Tuple[()]:
        if random.random() > 0.9 ** count:
            from .logic_dragon import add_keyword
            add_keyword(branch.word)
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDragoned: (Priority.OnDragoned.star, cls)}

class sun(_card):
    name = "XIX - 太阳"
    id = 19
    positive = 1
    description = "随机揭示一个隐藏奖励词。"
    @classmethod
    async def use(cls, user: User):
        from .logic_dragon import hidden_keyword
        user.buf.send("你揭示的一个隐藏奖励词是：" + random.choice(hidden_keyword))

class world(_card):
    name = "XXI - 世界"
    id = 21
    positive = 0
    global_daily_status = 's'
    status_des = "XXI - 世界：除大病一场外，所有“直到下次主题刷新为止”的效果延长至明天。"
    description = "除大病一场外，所有“直到下次主题刷新为止”的效果延长至明天。"

class dabingyichang(_card):
    name = "大病一场"
    id = 30
    positive = -1
    description = "抽到时，直到下一次主题出现前不得接龙。"
    on_draw_daily_status = 'd'
    on_draw_send_char = "病了！直到下一次主题出现前不得接龙。"
    is_debuff = True
    consumed_on_draw = True
class shengbing(_statusdaily):
    id = 'd'
    des = "生病：直到下一次主题出现前不可接龙。"
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
    description = "抽到时立即获得20击毙与两张牌。"
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
        global global_state
        global_state["exchange_stack"] = []
        save_global_state()

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
    status_des = "铁索连环：任何处于连环状态的玩家被击毙时所有连环状态的玩家也被击毙并失去此效果。"
    description = "指定至多两名玩家进入连环状态。任何处于连环状态的玩家被击毙时所有连环状态的玩家也被击毙并失去此效果。也可用于解除至多两人的连环状态。"
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
            def toggle(target):
                global global_state
                if target in global_state['lianhuan']:
                    global_state['lianhuan'].remove(target)
                else:
                    global_state['lianhuan'].append(target)
            for target in l:
                u = User(target, user.buf)
                if (c := await u.check_attacked(user, TCounter(double=1))).dodge:
                    continue
                elif c.rebound:
                    toggle(user.qq)
                    user.buf.send('成功切换' + user.char + '的连环状态！')
                elif u.check_status('8'):
                    u.remove_status('8', remove_all=False)
                    u.send_log("触发了胶带的效果，免除此debuff！")
                else:
                    toggle(target)
                    user.buf.send('成功切换' + u.char + '的连环状态！')
            save_global_state()

class minus1ma(_card):
    name = "-1马"
    id = 39
    daily_status = 'm'
    positive = 1
    description = "直到下次主题刷新为止，你可以少隔一个接龙，但最少隔一个。"
class minus1ma_s(_statusdaily):
    id = 'm'
    des = "-1马：直到下次主题刷新为止，你可以少隔一个接龙，但最少隔一个。"
    @classmethod
    async def BeforeDragoned(cls, count: TCount, user: User, word: str, parent: 'Tree') -> Tuple[bool, int, str]:
        return True, -1, ""
    @classmethod
    def register(cls):
        return {UserEvt.BeforeDragoned: (Priority.BeforeDragoned.minus1ma, cls)}
class plus1ma_s(_statusdaily):
    id = 'M'
    des = "+1马：直到下次主题刷新为止，你必须额外隔一个才能接龙。"
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
    description = "复制你手牌中一张牌的效果。"
    @classmethod
    async def use(cls, user: User):
        if await user.choose():
            config.logger.dragon << f"【LOG】询问用户{user.qq}复制牌。"
            l: List[int] = await user.buf.aget(prompt="请选择你手牌中的一张牌复制，输入id号。\n" + "\n".join(c.full_description(user.qq) for c in user.data.hand_card),
                arg_filters=[
                        extractors.extract_text,
                        lambda s: list(map(int, re.findall(r'\-?\d+', str(s)))),
                        validators.fit_size(1, 1, message="请输入正确的张数。"),
                        validators.ensure_true(lambda l: l[0] in _card.card_id_dict and Card(l[0]) in user.data.hand_card, message="您选择了错误的卡牌！"),
                        ensure_true_lambda(lambda l: Card(l[0]).can_use(user), message_lambda=lambda l: Card(l[0]).failure_message)
                    ])
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
    description = "你下次死亡时自动消耗5击毙免除死亡。"
class sihuihuibizhiyao_s(_statusnull):
    id = 's'
    des = '死秽回避之药：下次死亡时自动消耗5击毙免除死亡。'
    @classmethod
    async def OnDeath(cls, count: TCount, user: User, killer: User, time: int, c: TCounter) -> Tuple[int, bool]:
        if c.pierce:
            user.send_log("死秽回避之药的效果被幻想杀手消除了！")
            user.remove_status('s', remove_all=True)
            return time, False
        elif await user.add_jibi(-5, is_buy=True):
            user.send_log("触发了死秽回避之药的效果，免除死亡！")
            user.remove_status('s', remove_all=False)
            return time, True
        return time, False
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDeath: (Priority.OnDeath.sihuihuibizhiyao, cls)}
class inv_sihuihuibizhiyao_s(_statusnull):
    id = 't'
    des = '反转·死秽回避之药：下次死亡时获得5击毙，但是死亡时间增加2h。'
    @classmethod
    async def OnDeath(cls, count: TCount, user: User, killer: User, time: int, c: TCounter) -> Tuple[int, bool]:
        if c.pierce:
            user.send_log("反转·死秽回避之药的效果被幻想杀手消除了！")
            user.remove_status('t')
            return time, False
        user.send_log(f"触发了{count}次反转·死秽回避之药的效果，增加{5 * count}击毙，死亡时间增加{2 * count}小时！")
        await user.add_jibi(5 * count)
        user.remove_status('t')
        return time + 120 * count, False
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDeath: (Priority.OnDeath.inv_sihuihuibizhiyao, cls)}

class huiye(_card):
    name = "辉夜姬的秘密宝箱"
    id = 52
    positive = 1
    description = "你下一次死亡的时候奖励你抽一张卡。"
class huiye_s(_statusnull):
    id = 'x'
    des = '辉夜姬的秘密宝箱：下一次死亡的时候奖励抽一张卡。'
    @classmethod
    async def OnDeath(cls, count: TCount, user: User, killer: User, time: int, c: TCounter) -> Tuple[int, bool]:
        user.remove_status('x')
        if c.pierce:
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
        user.remove_status('y')
        if c.pierce:
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
    description = "抽取一张正面卡并立即发动效果。"
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
        user.data.card_limit += 1
        config.logger.dragon << f"【LOG】用户{user.qq}增加了手牌上限至{user.data.card_limit}。"

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
    description = "下一个接龙的人抽一张非负面卡和一张非正面卡。"
class plus2_s(_card):
    id = '+'
    des = "+2：下一个接龙的人抽一张非负面卡和一张非正面卡。"
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree') -> Tuple[()]:
        Userme(user).remove_status('+')
        user.send_char(f"触发了{count}次+2的效果，摸{count}张非正面牌与{count}张非负面牌！")
        user.log << f"触发了+2的效果。"
        cards = list(itertools.chain(*[[draw_card({-1, 0}), draw_card({0, 1})] for i in range(count)]))
        await user.draw(0, cards=cards)
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDragoned: (Priority.OnDragoned.plus2, cls)}

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
    description = "修改当前规则至首尾接龙直至下次刷新。"
    @classmethod
    async def use(cls, user: User) -> None:
        u = Userme(user)
        if u.check_daily_status('o'):
            u.remove_daily_status('o')
        if u.check_daily_status('p'):
            u.remove_daily_status('p')
        u.add_daily_status('o')
class ourostone_s(_statusdaily):
    id = 'o'
    des = "衔尾蛇之石：规则为首尾接龙直至下次刷新。"
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
    des = "石之蛇尾衔：规则为尾首接龙直至下次刷新。"
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
    def full_description(cls, qq: int):
        q = str(qq)
        m = mission[global_state['quest'][q][quest_print_aux[q]]['id']][1]
        remain = global_state['quest'][q][quest_print_aux[q]]['remain']
        quest_print_aux[q] += 1
        if quest_print_aux[q] >= len(global_state['quest'][q]):
            quest_print_aux[q] = 0
        return super().full_description(qq) + "\n\t当前任务：" + m + f"剩余{remain}次。"
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
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree') -> Tuple[()]:
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
        Userme(user).remove_status('m')
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
        Userme(user).remove_status('M')
        return -count * 10,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnHiddenKeyword: (Priority.OnHiddenKeyword.inv_cunqianguan, cls)}

class hongsezhihuan(_card):
    name = "虹色之环"
    id = 71
    positive = 0
    description = "下次你死亡时，有1/2几率闪避，1/2几率死亡时间+1小时。"
class hongsezhihuan_s(_statusnull):
    id = 'h'
    des = '虹色之环：下次死亡时，有1/2几率闪避，1/2几率死亡时间+1小时。'
    @classmethod
    async def OnDeath(cls, count: TCount, user: User, killer: User, time: int, c: TCounter) -> Tuple[int, bool]:
        if c.pierce:
            user.send_log("虹色之环的效果被幻想杀手消除了！")
            user.remove_status('h', remove_all=True)
            return time, False
        for a in range(count):
            user.remove_status('h', remove_all=False)
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
    description = "所有玩家手牌集合在一起随机分配，手牌张数不变。"
    @classmethod
    async def use(cls, user: User):
        user.data.set_cards()
        config.logger.dragon << f"【LOG】用户{user.qq}交换了所有人的手牌。"
        l = [User(t['qq'], user.buf) for t in config.userdata.execute("select qq from dragon_data").fetchall() if t['qq'] != config.selfqq]
        config.logger.dragon << f"【LOG】所有人的手牌为：{','.join(f'{user.qq}: {cards_to_str(user.data.hand_card)}' for user in l)}。"
        all_cards: List[Tuple[User, TCard]] = []
        all_users: List[User] = []
        for u in l:
            if u.check_status('G'):
                u.remove_status("G", remove_all=False)
            elif not (await u.check_attacked(user, TCounter(double=1))).valid:
                pass
            else:
                for c in u.data.hand_card:
                    all_cards.append((u, c))
                all_users.append(u)
        random.shuffle(all_cards)
        for u in all_users:
            if (n := len(u.data.hand_card)):
                cards_temp = [c1 for q1, c1 in all_cards[:n]]
                u.data.hand_card.clear()
                u.data.hand_card.extend(cards_temp)
                u.data.set_cards()
                for userqqq, c in all_cards[:n]:
                    await c.on_give(userqqq, u)
                config.logger.dragon << f"【LOG】{u.qq}交换后的手牌为：{cards_to_str(cards_temp)}。"
                all_cards = all_cards[n:]
        if len(user.data.hand_card) != 0:
            user.buf.send("通过交换，你获得了手牌：\n" + '\n'.join(c.full_description(user.qq) for c in user.data.hand_card))
        else:
            user.buf.send("你交换了大家的手牌！")

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
    async def OnDragoned(cls, count: TCount, user: User, branch: 'Tree') -> Tuple[()]:
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
    status_des = '极速装置：下次可以连续接龙两次。'
    positive = 1
    description = '下次你可以连续接龙两次。'
class jisuzhuangzhi_s(_statusnull):
    id = 'z'
    des = "极速装置：下次可以连续接龙两次。"
    @classmethod
    async def CheckSuguri(cls, count: TCount, user: 'User', word: str, parent: 'Tree') -> Tuple[bool]:
        user.remove_status('z', remove_all=False)
        return True,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.CheckSuguri: (Priority.CheckSuguri.jisuzhuangzhi, cls)}

class huxiangjiaohuan(_card):
    name = '互相交换'
    id = 75
    positive = 0
    status_des = "互相交换：下一个接中隐藏奖励词的玩家手牌、击毙与某人互换。"
    description = "下一个接中隐藏奖励词的玩家手牌、击毙与你互换。"
    @classmethod
    async def use(cls, user: User):
        user.log << f"被加入交换堆栈，现为{global_state['exchange_stack']}。"
        global_state['exchange_stack'].append(user.qq)
        save_global_state()

class zhongshendexixi(_card):
    name = "众神的嬉戏"
    id = 76
    positive = 0
    description = '抽取一张卡并立即发动效果。'
    @classmethod
    async def use(cls, user: User):
        c = draw_card()
        await user.draw_and_use(c)

class lveduozhebopu(_card):
    name = "掠夺者啵噗"
    id = 77
    positive = 1
    hold_des = '掠夺者啵噗：每天可从所接龙的人处偷取1击毙，每人限一次，最多10击毙，若目标没有击毙则不可偷取。'
    description = "每天你可从你所接龙的人处偷取1击毙，每人限一次，最多10击毙，若目标没有击毙则不可偷取。死亡时或使用将丢弃这张卡。"
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
    async def OnDragoned(cls, count: TCount, user: User, branch: 'Tree') -> Tuple[()]:
        last_qq = branch.qq
        qq = user.qq
        if branch.id != (0, 0):
            last = User(last_qq, user.buf)
            c = await last.check_attacked(user)
            if last_qq not in global_state['steal'][str(qq)]['user'] and global_state['steal'][str(qq)]['time'] < 10 and c.valid:
                global_state['steal'][str(qq)]['time'] += 1
                global_state['steal'][str(qq)]['user'].append(last_qq)
                save_global_state()
                user.log << f"触发了{count}次掠夺者啵噗的效果，偷取了{last_qq}击毙，剩余偷取次数{9 - global_state['steal'][str(qq)]['time']}。"
                if (p := last.data.jibi) > 0:
                    n = count * 2 ** c.double
                    user.buf.send(f"你从上一名玩家处偷取了{min(n, p)}击毙！")
                    await last.add_jibi(-n)
                    await user.add_jibi(min(n, p))
    @classmethod
    def register(cls):
        return {UserEvt.OnDeath: (Priority.OnDeath.lveduozhebopu, cls),
            UserEvt.OnDragoned: (Priority.OnDragoned.lveduozhebopu, cls)}

class jiandieyubei(_card):
    name = "邪恶的间谍行动～预备"
    id = 78
    positive = 0
    global_daily_status = 'j'
    status_des = "邪恶的间谍行动～预备：今日卡池中有一定概率出现【邪恶的间谍行动~执行】。"
    description = "今日卡池中有一定概率出现【邪恶的间谍行动~执行】。"

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
    description = '所有人立刻获得胜利。'
    @classmethod
    async def use(cls, user: User):
        user.buf.send("今天接龙的所有人都赢了！恭喜你们！")
        from .logic_dragon import Tree
        qqs = [tree.qq for tree in itertools.chain(*itertools.chain(Tree._objs, *Tree.forests))]
        for qq in set(qqs):
            User(qq, user.buf).add_daily_status('W')
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
        await user.kill()

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
        user.remove_status('2')
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
    description = "取消掉至多6种负面状态（不包括死亡），并免疫下次即刻生效的负面状态（不包括死亡）。"
    @classmethod
    async def use(cls, user: User) -> None:
        has = 6
        for c in map(StatusNull, user.data.status):
            if c.id != 'd' and c.is_debuff and has > 0:
                has -= 1
                user.send_char(f"的{c.des[:c.des.index('：')]}被取消了！")
                user.remove_status(c, remove_all=False)
        if user.qq in global_state['lianhuan'] and has > 0:
            user.send_char("的铁索连环被取消了！")
            global_state['lianhuan'].remove(user.qq)
        for c in map(StatusDaily, user.data.daily_status):
            if c.id != 'd' and c.is_debuff and has > 0:
                has -= 1
                user.send_char(f"的{c.des[:c.des.index('：')]}被取消了！")
                user.remove_daily_status(c, remove_all=False)
        i = 0
        while i < len(user.data.status_time_checked):
            s = user.data.status_time[i]
            if s.id != 'd' and s.is_debuff and has > 0:
                has -= 1
                des = s.des
                user.send_log(f"的{des[:des.index('：')]}被取消了！")
                user.remove_limited_status(s)
            else:
                i += 1
        user.data.save_status_time()
        user.add_status('8')
class jiaodai_s(_statusnull):
    id = '8'
    des = "布莱恩科技航空专用强化胶带FAL84型：免疫你下次即刻生效的负面状态（不包括死亡）。"
    @classmethod
    async def OnStatusAdd(cls, count: TCount, user: 'User', status: TStatusAll, count2: int) -> Tuple[int]:
        if status.is_debuff and status.id != 'd':
            for i in range(min(count, count2)):
                user.remove_status('8', remove_all=False)
            user.send_log("触发了胶带的效果，免除此负面状态！")
            return max(0, count2 - count)
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
                user.remove_status('9', remove_all=False)
            user.send_log("触发了反转·胶带的效果，免除此非负面状态！")
            return max(0, count2 - count)
        return count2,
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnStatusAdd: (Priority.OnStatusAdd.inv_jiaodai, cls)}

class McGuffium239(_card):
    name = "Mc Guffium 239"
    id = 102
    positive = 1
    status = 'G'
    status_des = 'Mc Guffium 239：下一次礼物交换不对你生效。'
    description = "下一次礼物交换不对你生效。"

class jujifashu(_card):
    name = "聚集法术"
    id = 105
    positive = 1
    description = "将两张手牌的id相加变为新的手牌。若这两牌id之和不是已有卡牌的id，则变为id是-1的卡牌。"
    failure_message = "你的手牌不足，无法使用！"
    @classmethod
    async def can_use(cls, user: User) -> bool:
        return len(user.data.hand_card) >= 3
    @classmethod
    async def use(cls, user: User) -> None:
        if await user.choose():
            if len(user.data.hand_card) < 2:
                user.send_char("的手牌不足，无法使用！")
                return
            config.logger.dragon << f"【LOG】询问用户{user.qq}选择牌执行聚集法术。"
            l = await user.buf.aget(prompt="请选择你手牌中的两张牌，输入id号。\n" + "\n".join(c.full_description(user.qq) for c in user.data.hand_card),
                arg_filters=[
                        extractors.extract_text,
                        lambda s: list(map(int, re.findall(r'\-?\d+', str(s)))),
                        validators.fit_size(2, 2, message="请输入正确的张数。"),
                        validators.ensure_true(lambda l: l[0] in _card.card_id_dict and Card(l[0]) in user.data.hand_card, message="您选择了错误的卡牌！"),
                        validators.ensure_true(lambda l: l[1] in _card.card_id_dict and Card(l[1]) in user.data.hand_card, message="您选择了错误的卡牌！")
                    ])
            user.log << f"选择了卡牌{l[0]}与{l[1]}。"
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
    description = "将一张手牌变为两张随机牌，这两张牌的id之和为之前的卡牌的id。"
    failure_message = "你的手牌不足，无法使用！"
    @classmethod
    async def can_use(cls, user: User) -> bool:
        return len(user.data.hand_card) >= 2
    @classmethod
    async def use(cls, user: User) -> None:
        if await user.choose():
            if len(user.data.hand_card) < 1:
                user.send_char("的手牌不足，无法使用！")
                return
            config.logger.dragon << f"【LOG】询问用户{user.qq}选择牌执行裂变法术。"
            l = await user.buf.aget(prompt="请选择你手牌中的一张牌，输入id号。\n" + "\n".join(c.full_description(user.qq) for c in user.data.hand_card),
                arg_filters=[
                        extractors.extract_text,
                        lambda s: list(map(int, re.findall(r'\-?\d+', str(s)))),
                        validators.fit_size(1, 1, message="请输入正确的张数。"),
                        validators.ensure_true(lambda l: l[0] in _card.card_id_dict and Card(l[0]) in user.data.hand_card, message="您选择了错误的卡牌！")
                    ])
            user.log << f"选择了卡牌{l[0]}。"
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
    description = "对指定玩家发动，该玩家的每条状态都有1/2的概率被清除；或是对千春使用，消除【XXI-世界】外的所有全局状态。"
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
                global global_state
                global_state["exchange_stack"] = []
                me._reregister_things()
                save_global_state()
            else:
                u = User(qq, user.buf)
                ret = await u.check_attacked(user)
                u2 = u
                if ret.dodge:
                    return
                elif ret.rebound:
                    u2 = user
                double = ret.double
                # 永久状态
                for c in u2.data.status:
                    if random.random() < 0.5 ** (2 ** double) or c == 'W':
                        continue
                    u2.remove_status(c, remove_all=False)
                    u2.send_log(f"的{c.des[:c.des.index('：')]}被消除了！")
                # 每日状态
                for c in u2.data.daily_status:
                    if random.random() < 0.5 ** (2 ** double):
                        continue
                    u2.remove_daily_status(c, remove_all=False)
                    u2.send_log(f"的{c.des[:c.des.index('：')]}被消除了！")
                # 带附加值的状态
                l = user.data.status_time_checked
                i = 0
                while i < len(l):
                    if random.random() < 0.5 ** (2 ** double):
                        i += 1
                    else:
                        des = l[i].des
                        u2.send_log(f"的{des[:des.index('：')]}被消除了！")
                        l.pop(i)
                u2.data.save_status_time()

class yuexiabianhua(_card):
    name = "月下彼岸花"
    id = 110
    positive = -1
    description = "抽到时附加buff：你每接龙三次会损失1击毙，效果发动20次消失。"
    on_draw_limited_status = 'b'
    consumed_on_draw = True
    limited_init = (60,)

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
                user.remove_status('A', remove_all=False)
            await user.kill()
            return max(0, count2 - count)
        return count2
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree') -> Tuple[()]:
        user.log << f"的{count}个判决α激活了。"
        user.remove_status('A', remove_all=True)
        user.add_status('a', count=count)
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
        if status == panjueb_s or status == panjueb_activated_s:
            user.send_char("从五个人前面接来了判决β！")
            for i in range(min(count, count2)):
                user.remove_status('a', remove_all=False)
            await user.kill()
            return max(0, count2 - count)
        return count2
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnStatusAdd: (Priority.OnStatusAdd.panjue_activated, cls)}

class panjueb(_card):
    name = "判决β"
    id = 111
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
            await user.kill()
            return max(0, count2 - count)
        return count2
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree') -> Tuple[()]:
        user.log << f"的{count}个判决β激活了。"
        user.remove_status('B', remove_all=True)
        user.add_status('b', count=count)
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
        if status == panjuea_s or status == panjuea_activated_s:
            user.send_char("从五个人前面接来了判决α！")
            for i in range(min(count, count2)):
                user.remove_status('b', remove_all=False)
            await user.kill()
            return max(0, count2 - count)
        return count2
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnStatusAdd: (Priority.OnStatusAdd.panjue_activated, cls)}
class panjue_checker(IEventListener):
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree') -> Tuple[()]:
        if (nd := branch.before(5)) and nd.qq != config.selfqq and (u := User(nd.qq, user.buf)) != user:
            if na := u.check_status('a'):
                u.remove_status('a')
                user.log << f"从五个人前面接来了{na}个判决α。"
                user.add_status('a', count=na)
            if nb := u.check_status('b'):
                u.remove_status('b')
                user.log << f"从五个人前面接来了{na}个判决β。"
                user.add_status('b', count=na)
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDragoned: (Priority.OnDragoned.panjuecheck, cls)}
for key, (priority, el) in panjue_checker.register().items():
    UserData.event_listener_init[key][priority][el] += 1

class dihuopenfa(_card):
    name = "地火喷发"
    id = 114
    description = "今天之内所有的接龙词都有10%的几率变成地雷。"
    positive = 0
    global_daily_status = 'B'
class dihuopenfa_s(_statusdaily):
    id = 'B'
    des = "地火喷发：今天之内所有的接龙词都有10%的几率变成地雷。"
    is_global = True
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree') -> Tuple[()]:
        if random.random() > 0.9 ** count:
            from .logic_dragon import add_bomb
            add_bomb(branch.word)
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnDragoned: (Priority.OnDragoned.dihuopenfa, cls)}

class gaojie(_card):
    name = "告解"
    id = 116
    description = "今日每次你获得击毙时额外获得1击毙。"
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
    status_des = "深谋远虑之策：当你一次使用/损失了超过你现有击毙一半以上的击毙时，恢复这些击毙。"

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

class imaginebreaker(_card):
    name = "幻想杀手"
    id = 120
    description = "你的下一次攻击无视对方的所有反制效果，下一次目标为你的攻击无效。以上两项只能发动一项。"
    positive = 1
    status = '0'
    status_des = "幻想杀手：你的下一次攻击无视对方的所有反制效果，下一次目标为你的攻击无效。以上两项只能发动一项。"

class vector(_card):
    name = "矢量操作"
    id = 121
    description = "你的下一次攻击效果加倍，下一次对你的攻击反弹至攻击者，免除你下一次触雷。以上三项只能发动一项。"
    positive = 1
    status = 'v'
    status_des = "矢量操作：你的下一次攻击效果加倍，下一次对你的攻击反弹至攻击者，免除你下一次触雷。以上三项只能发动一项。"

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
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree') -> Tuple[()]:
        for i in range(count):
            if random.random() > 0.9:
                user.buf.send("你获得了一张【吸血鬼】！")
                await user.draw(0, cards=[Card(-2)])

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
        num = count + user.check_status(')')
        if num >= 10:
            user.send_log("的向日葵已经种满了10株，种植失败！")
            return 0,
        return min(count2, 10 - num),
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
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnNewDay: (Priority.OnNewDay.inv_sunflower, cls)}
newday_check[0] += "()[]"

class wallnut(_card):
    name = "坚果墙"
    id = 131
    description = "坚果墙：为你吸收死亡时间总计4小时。"
    positive = 1
    @classmethod
    async def use(cls, user: User) -> None:
        o = user.check_limited_status('o', lambda x: not x.is_pumpkin)
        if len(o) > 0:
            o[0].num = 240
            user.data.save_status_time()
            user.send_log("修补了" + user.char + "的坚果墙！")
        else:
            user.add_limited_status(SAbsorb(240, False))
            user.send_log("种植了坚果墙！")

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
    async def can_use(cls, user: User) -> bool:
        return user.check_status('(') > 0
    @classmethod
    async def use(cls, user: User) -> None:
        if user.check_status('(') == 0:
            user.send_char("场地上没有“向日葵”！")
            return
        user.remove_status('(', remove_all=False)
        user.add_status(')')
        user.send_char("的一株“向日葵”变成了“双子向日葵”！")
class twinsunflower_s(_statusnull):
    id = '('
    des = "双子向日葵：跨日结算时你获得2击毙。此buff与“向日葵”buff加在一起最多叠加10层。"
    @classmethod
    async def OnNewDay(cls, count: TCount, user: 'User') -> Tuple[()]:
        user.buf.send(f"玩家{user.qq}种下的双子向日葵产出了{2 * count}击毙！")
        await user.add_jibi(2 * count)
    @classmethod
    async def OnStatusAdd(cls, count: TCount, user: 'User', status: TStatusAll, count2: int) -> Tuple[int]:
        num = count + user.check_status('(')
        if num >= 10:
            user.send_log("的向日葵已经种满了10株，种植失败！")
            return 0,
        return min(count2, 10 - num),
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
    @classmethod
    def register(cls) -> dict[int, TEvent]:
        return {UserEvt.OnNewDay: (Priority.OnNewDay.inv_twinsunflower, cls)}

class pumpkin(_card):
    name = "南瓜头"
    id = 134
    description = "南瓜头：为你吸收死亡时间总计6小时。可与坚果墙叠加。"
    positive = 1
    @classmethod
    async def use(cls, user: User) -> None:
        o = user.check_limited_status('o', lambda x: x.is_pumpkin)
        if len(o) > 0:
            o[0].num = 360
            user.data.save_status_time()
            user.send_log("修补了" + user.char + "的南瓜头！")
        else:
            user.add_limited_status(SAbsorb(360, True))
            user.send_log("种植了南瓜头！")

class imitator(_card):
    name = "模仿者"
    id = 135
    positive = 0
    description = "你下一张抽到的卡会额外再给你一张。"
    status = 'i'
    status_des = "模仿者：你下一张抽到的卡会额外再给你一张。"
class imitator_s(_statusnull):
    id = 'i'
    des = "模仿者：你下一张抽到的卡会额外再给你一张。"
    @classmethod
    async def AfterCardDraw(cls, count: TCount, user: 'User', cards: Iterable[TCard]) -> Tuple[()]:
        if count > len(cards):
            for i in range(count):
                user.remove_status('i', remove_all=False)
            to_add = cards
        else:
            user.remove_status('i', remove_all=True)
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
    status_des = "玩偶匣：你每次接龙时有5%的几率爆炸，炸死以你为中心5x5的人，然后buff消失。若场上有寒冰菇状态则不会爆炸。"
    on_draw_send_char = "获得了玩偶匣！"
    is_debuff = True
    consumed_on_draw = True
class jack_in_the_box_s(_statusnull):
    id = 'j'
    status_des = "玩偶匣：你每次接龙时有5%的几率爆炸，炸死以你为中心5x5的人，然后buff消失。若场上有寒冰菇状态则不会爆炸。"
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree') -> Tuple[()]:
        if me.check_daily_status('i'):
            return
        if random.random() > 0.95 ** count:
            user.send_log("的玩偶匣爆炸了！")
            user.remove_status('j', remove_all=False)
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
                await User(qqq, user.buf).kill()

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
            user.remove_limited_status(o)
        elif user.check_status(')'):
            user.send_log("的双子向日葵被偷走了！")
            user.remove_status(')', remove_all=False)
        elif user.check_status('('):
            user.send_log("的向日葵被偷走了！")
            user.remove_status('(', remove_all=False)
        elif p := more_itertools.only(user.check_limited_status('o', lambda x: x.is_pumpkin)):
            user.send_log("的南瓜头被偷走了！")
            user.remove_limited_status(p)
        else:
            user.send_log("没有植物，蹦极僵尸放下了一只僵尸！")
            await user.kill(hour=1)

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
            await user.kill(jump=True)

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
class forkbomb_s(_statusnull):
    id = 'b'
    des = "Fork Bomb：今天每个接龙词都有5%几率变成分叉点。"
    is_global = True
    @classmethod
    async def OnDragoned(cls, count: TCount, user: 'User', branch: 'Tree') -> Tuple[()]:
        if random.random() > 0.95 ** count:
            user.send_log("触发了Fork Bomb，此词变成了分叉点！")
            branch.fork = True

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
            user.send_log(f"触发了{count}次北京市政交通一卡通的效果，花费击毙变为{jibi}。")
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
        def _s(u: User):
            to_remove = ""
            to_add = ""
            for c in u.data.status:
                if random.random() > 0.5:
                    continue
                if c in revert_status_map:
                    des = _card.status_dict[c]
                    user.send_log(f"的{des[:des.index('：')]}被反转了！")
                    to_remove += c
                    to_add += revert_status_map[c]
            for c in to_remove:
                u.remove_status(c, remove_all=False)
            for c in to_add:
                u.add_status(c)
        _s(user)
        # 每日状态
        def _d(u: User):
            to_remove = ""
            to_add = ""
            for c in u.data.daily_status:
                if random.random() > 0.5:
                    continue
                if c in revert_daily_status_map:
                    des = _card.daily_status_dict[c]
                    user.send_log(f"的{des[:des.index('：')]}被反转了！")
                    to_remove += c
                    to_add += revert_daily_status_map[c]
            for c in to_remove:
                u.remove_daily_status(c, remove_all=False)
            for c in to_add:
                u.add_daily_status(c)
        _d(user)
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
            elif l[i].id == 'f':
                l[i].jibi = -l[i].jibi
                user.send_log("的聚变堆被反转了！")
        user.data.save_status_time()
        # 全局状态
        _s(Userme(user))
        _d(Userme(user))
revert_status_map: Dict[str, str] = {}
for c in ('YZ', 'AB', 'ab', 'st', 'xy', 'Mm', 'QR', '12', '89', '([', ')]', 'WX'):
    revert_status_map[c[0]] = c[1]
    revert_status_map[c[1]] = c[0]
revert_daily_status_map: Dict[str, str] = {}
for c in ('Bt', 'Ii', 'Mm', 'op', '@#', 'WX'):
    revert_daily_status_map[c[0]] = c[1]
    revert_daily_status_map[c[1]] = c[0]

class excalibur(_card):
    id = 158
    name = "EX咖喱棒"
    positive = 1
    description = "只可在胜利时使用。统治不列颠。"
    newer = 1
    @classmethod
    async def can_use(cls, user: User) -> bool:
        return user.check_daily_status('W') > 0
    @classmethod
    async def use(cls, user: User) -> None:
        if user.check_daily_status('W') == 0:
            user.send_char("没有胜利，无法使用！")
        else:
            user.send_log("统治了不列颠！")
            user.add_status('W')
_card.add_status('W', "统治不列颠：使用塔罗牌时，若你没有对应的“魔力-{塔罗牌名}”状态，取消其原来的效果并获得效果“魔力-{塔罗牌名}”状态。")
_card.add_status('X', "被不列颠统治：若你有对应的“魔力-{塔罗牌名}”状态，你可取消效果“魔力-{塔罗牌名}”状态并使用一张对应塔罗牌。")

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

from collections import namedtuple
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
    @classmethod
    def description(cls, count: TCount) -> str:
        pass
    @classmethod
    def full_description(cls, count: TCount) -> str:
        return f"{cls.id}. {count * '☆'}{cls.name}\n\t{cls.description(count)}"

class bikini(_equipment):
    id = 0
    name = '比基尼'
    des_shop = '你每次获得击毙时都有一定几率加倍。一星为5%，二星为10%，三星为15%。'
    @classmethod
    def description(cls, count: TCount):
        return f'你每次获得击毙时都有{5 * count}%几率加倍。'

class schoolsui(_equipment):
    id = 1
    name = '学校泳装'
    des_shop = '你每次击毙减少或商店购买都有一定几率免单。一星为4.76%，二星为9.09%，三星为13.04%。'
    @classmethod
    def description(cls, count: TCount):
        return f'你每次击毙减少或商店购买都有{count / (20 + count) * 100:.2f}%几率免单。'

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
            await user.kill(hour=0, minute=content // 2 * 5 + 5)
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
            user.add_status('D')
        else: # 随机获得10~30活动pt。
            user.send_log("走到了：随机获得10~30活动pt。")
            n = random.randint(10, 30)
            user.send_log(f"获得了{n}pt！")
            await user.add_event_pt(n)
        return 0
_card.add_status('D', "快走：在活动中，你下次行走距离加倍。")


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
