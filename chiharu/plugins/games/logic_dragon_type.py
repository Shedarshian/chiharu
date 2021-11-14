from contextlib import asynccontextmanager
import functools
from typing import Callable, TypedDict, List, Dict, TypeVar, Generic, Awaitable, Any, Tuple
from dataclasses import dataclass
from nonebot.command import CommandSession

TQuest = TypedDict('TQuest', id=int, remain=int)
TModule = TypedDict('TModule', id=int, remain=int)
TSteal = TypedDict('TSteal', user=List[int], time=int)

class TGlobalState(TypedDict):
    last_card_user: int
    exchange_stack: List[int]
    used_cards: List[int]
    global_status: List[Tuple[int, str]]
    observatory: bool
    # lianhuan: List[int]
    quest: Dict[int, List[TQuest]]
    module: Dict[int, List[TModule]]
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
    BeforeCardUse = auto()
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

class Priority:  # 依照每个优先级从前往后find，而不是iterate
    class OnUserUseCard(IntEnum):
        temperance = auto()
        xingyunhufu = auto()
        cantuse = auto()
    class BeforeCardUse(IntEnum):
        fool = auto()
        britian = auto()
    class AfterCardUse(IntEnum):
        pass
    class AfterCardDraw(IntEnum):
        imitator = auto()
        assembling = auto()
    class AfterCardDiscard(IntEnum):
        inv_belt = auto()
        belt = auto()
    class AfterCardRemove(IntEnum):
        pass
    class AfterExchange(IntEnum):
        pass
    class OnDeath(IntEnum):
        invincible = auto()             #吸血鬼：免疫死亡
        miansi = auto()                 #倒吊人：免疫一次死亡
        sihuihuibizhiyao = auto()       #死秽：消耗击毙免疫一次死亡
        hongsezhihuan = auto()          #虹环：一半免疫一次死亡
        inv_sihuihuibizhiyao = auto()   #反转死秽
        death = auto()                  #成功击杀，计算时间
        absorb = auto()                 #吸收死亡时间
        changsheng = auto()             #吸收死亡时间MkII
        tiesuolianhuan = auto()         #铁索连环：一起下地狱
        lveduozhebopu = auto()          #掠夺者：被弃
        huiye = auto()                  #宝箱：抽卡
        inv_huiye = auto()              #反转宝箱
        shangba = auto()                #伤疤：+2击毙
        invshangba = auto()
    class OnAttack(IntEnum):
        imaginebreaker = auto()         #幻杀：破防
                                        # imagine breaker is suggested to be the first
        vector = auto()                 #矢量：双倍
    class OnAttacked(IntEnum):
        McGuffium239 = auto()           #麦高芬：免疫礼物交换
        imaginebreaker = auto()         #矢量：反转
        vector = auto()                 #幻杀：无效
                                        # vector is suggested to be the last
    class OnDodged(IntEnum):
        pass
    class OnStatusAdd(IntEnum):
        jiaodai = auto()                #胶带：免除负面状态
        inv_jiaodai = auto()            #反转胶带
        paean = auto()                  #光阴神：3*胶带
        sunflower = auto()              #向日葵：检测是否密植
        twinsunflower = auto()
        panjue = auto()                 # contains both a and b
        panjue_activated = auto()       # contains both a and b
        beacon = auto()                 #速度插件：检测寒冰菇
        beacon1 = auto()                #全局速度插件
    class OnStatusRemove(IntEnum):
        train = auto()
    class CheckJibiSpend(IntEnum):
        bianyaqi = auto()
        steamsummer = auto()
        beijingcard = auto()
    class OnJibiChange(IntEnum):
        gaojie = auto()                 #告解：每获得击毙+1击毙
        inv_gaojie = auto()             #反转告解
        bikini = auto()                 #比基尼：有几率翻倍
        schoolsui = auto()              #死库水：有几率免单
        beacon = auto()                 #个人插件-产能：有几率加获得，有上限-节能：有几率降支出，有上限
        beacon0 = auto()                #分享塔全局插件-产能
        beacon2 = auto()                #分享塔全局插件-节能
        shuairuo = auto()               #衰弱：获得击毙降为75%
        bianyaqi = auto()               #变压器：加倍击毙变动
        inv_bianyaqi = auto()           #反转变压器
        steamsummer = auto()            #Steam夏季促销：减半购买支出
        beijingcard = auto()            #一卡通：根据消费总量打折
        shenmouyuanlv = auto()          #绿帽：击毙减半则免单
        train = auto()                  #火车：便乘
    class CheckEventptSpend(IntEnum):
        pass
    class OnEventptChange(IntEnum):
        pass
    class BeforeDragoned(IntEnum):
        death = auto()                  #死人不能接龙
        wufazhandou = auto()            #死人不能接龙
        shengbing = auto()              #病人也不能接龙
        minus1ma = auto()               #±1马：计算距离
        plus1ma = auto()
        iceshroom = auto()              #冰/热菇：全局计算距离
        hotshroom = auto()
        lazhuyandong = auto()           #秘史衍生：计算距离
        invlazhuyandong = auto()
        lieshouzhixue = auto()
        invlieshouzhixue = auto()
        ourostone = auto()              #衔尾蛇：首尾
                                        # contains two buffs
        ranshefashu = auto()            #**法术：首尾
        inv_ranshefashu = auto()
        jiaotu = auto()                 #秘史衍生：首尾
        invjiaotu = auto()
        shequn = auto()
        invshequn = auto()
        hierophant = auto()             #教皇：首尾
        inv_hierophant = auto()
    class CheckSuguri(IntEnum):
        jisuzhuangzhi = auto()
    class OnKeyword(IntEnum):
        pass
    class OnHiddenKeyword(IntEnum):
        cunqianguan = auto()
        inv_cunqianguan = auto()
        huxiangjiaohuan = auto()
        moon = auto()
        inv_moon = auto()
    class OnDuplicatedWord(IntEnum):
        hermit = auto()
    class OnBombed(IntEnum):
        hermit = auto()
        vector = auto()
    class OnDragoned(IntEnum):
        queststone = auto()             #任务：完成+3击毙
        quest = auto()
        xingyunhufu = auto()            #幸运护符：+0.5击毙
        hierophant = auto()             #教皇：+2击毙
        inv_hierophant = auto()         #反转教皇
        lveduozhebopu = auto()          #掠夺者：偷窃判定
        bianhua = auto()                #彼岸花：-1/3击毙
        inv_bianhua = auto()            #反转
        zpm = auto()                    #ZPM：新手保护，+1击毙
        shendian = auto()               #秘史衍生：+5击毙
        invshendian = auto()
        beizhizhunze = auto()           #+2击毙
        invbeizhizhunze = auto()
        plus2 = auto()                  #+2：抽两张牌
        xixuegui = auto()               #？？？？
        panjue = auto()                 #判决传播 contains both a and b
        panjuecheck = auto()            #判决重合 contains both a and b
        jack_in_the_box = auto()        #玩偶匣：爆炸判定
        star = auto()                   #星星：奖励词判定
        dihuopenfa = auto()             #地火：埋雷判定
        xixueshashou = auto()           #吸血杀手：抽卡判定
        forkbomb = auto()               #叉子炸弹：分叉判定
        circus = auto()                 #秘史衍生：被弃
        lazhuyandong = auto()
        invlazhuyandong = auto()
        lieshouzhixue = auto()
        invlieshouzhixue = auto()
        shequn = auto()
        invshequn = auto()
        jiaotu = auto()
        invjiaotu = auto()
    class OnNewDay(IntEnum):
        tarot = auto()
        quest = auto()
        sunflower = auto()
        twinsunflower = auto()
        inv_sunflower = auto()
        inv_twinsunflower = auto()

TBoundIntEnum = TypeVar('TBoundIntEnum', bound=IntEnum)

class UnableRequirement(Exception):
    pass
class NotActive(Exception):
    pass

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

def check_handcard(user):
    def validate(value):
        if value in ("查询手牌", "查看手牌"):
            _raise_failure("你的手牌为：\n" + '\n'.join(s.brief_description(user.qq) for s in user.data.hand_card))
        elif value in ("查询详细手牌", "查看详细手牌"):
            _raise_failure("你的手牌为：\n" + '\n'.join(s.full_description(user.qq) for s in user.data.hand_card))
        return value
    return validate

# def check_can_use(user, can_use_func):
#     def validate(value):
#         if not can_use_func(user, value):
#             pass
#         return value
#     return validate

def check_if_unable(unable_func, session: CommandSession):
    def validate(value):
        if unable_func(value):
            raise UnableRequirement
        return value
    return validate

@asynccontextmanager
async def check_active(value):
    if value is None:
        raise NotActive
    yield None
