import functools
from typing import Callable, TypedDict, List, Dict, TypeVar, Generic, Awaitable
from dataclasses import dataclass

TQuest = TypedDict('TQuest', id=int, remain=int)
TSteal = TypedDict('TSteal', user=List[int], time=int)
class TGlobalState(TypedDict):
    last_card_user: int
    exchange_stack: List[int]
    # lianhuan: List[int]
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
async def nothing(): return False
@dataclass
class TCounter:
    pierce: Callable = nothing
    jump: bool = False
def async_data_saved(f: Callable):
    i = None
    @functools.wraps(f)
    async def _():
        nonlocal i
        if i is None:
            i = await f()
        return i
    return _

class CountWaiter:
    def __add__(self, var):
        return var
T = TypeVar('T')
TCount = TypeVar('TCount')
class CounterOnly(Generic[T, TCount]):
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
        return self.data, self.count\

from enum import IntEnum, auto
class UserEvt(IntEnum):
    OnUserUseCard = auto()
    AfterCardUse = auto()
    AfterCardDraw = auto()
    AfterCardDiscard = auto()
    AfterCardRemove = auto()
    AfterExchange = auto()
    OnDeath = auto()
    OnAttack = auto()
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
        absorb = auto()
        tiesuolianhuan = auto()
        lveduozhebopu = auto()
        huiye = auto()
        inv_huiye = auto()
    class OnAttack(IntEnum):
        imaginebreaker = auto()         # imagine breaker is suggested to be the first
        vector = auto()
    class OnAttacked(IntEnum):
        McGuffium239 = auto()
        imaginebreaker = auto()
        vector = auto()                 # vector is suggested to be the last
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
        bikini = auto()
        schoolsui = auto()
        bianyaqi = auto()
        inv_bianyaqi = auto()
        steamsummer = auto()
        beijingcard = auto()
        shenmouyuanlv = auto()
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
        huxiangjiaohuan = auto()
    class OnDuplicatedWord(IntEnum):
        hermit = auto()
    class OnBombed(IntEnum):
        hermit = auto()
        vector = auto()
    class OnDragoned(IntEnum):
        queststone = auto()
        quest = auto()
        xingyunhufu = auto()
        lveduozhebopu = auto()
        bianhua = auto()
        inv_bianhua = auto()
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
TBoundIntEnum = TypeVar('TBoundIntEnum', bound=IntEnum)

