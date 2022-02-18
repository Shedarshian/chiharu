from contextlib import asynccontextmanager
import functools, re
import itertools
import operator
from copy import copy
from typing import Callable, Counter, Iterable, TypedDict, List, Dict, TypeVar, Generic, Awaitable, Any, Tuple, Optional
from enum import IntEnum, IntFlag, auto, Enum
from dataclasses import dataclass
from ..config import 句尾
from nonebot.command import CommandSession

TQuest = TypedDict('TQuest', id=int, remain=int)
TModule = TypedDict('TModule', id=int, remain=int)
TSteal = TypedDict('TSteal', user=List[int], time=int)

class TGlobalState(TypedDict):
    last_card_user: int
    # exchange_stack: List[int]
    supernova_user: List[List[int]]
    used_cards: List[int]
    global_status: List[Tuple[int, str]]
    observatory: bool
    # lianhuan: List[int]
    quest: Dict[int, List[TQuest]]
    module: Dict[int, List[TModule]]
    steal: Dict[int, TSteal]
    dragon_head: Dict[int, Dict[int, Any]]
    event_route: List[int]
    bingo_state: List[int]
    sign: int

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
    event_skill: int
    last_dragon_time: str
    flags: int
    hp: int
    mp: int

async def nothing(): return False

@dataclass
class TCounter:
    pierce: Callable = nothing
    jump: bool = False
    hpzero: bool = False
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
        return copy(var)

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
        return self.data, self.count

class UserEvt(IntEnum):
    OnUserUseCard = auto()
    BeforeCardUse = auto()
    BeforeCardDraw = auto()
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
    AfterStatusRemove = auto()
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
        zhanxingshu = auto()
        temperance = auto()
        cantuse = auto()
        xingyunhufus = auto()
        xingyunhufu = auto()            # 每天一次
    class BeforeCardDraw(IntEnum):
        laplace = auto()
    class BeforeCardUse(IntEnum):
        fool = auto()
        britian = auto()
    class AfterCardUse(IntEnum):
        bingo = auto()
    class AfterCardDraw(IntEnum):
        imitator = auto()
        assembling = auto()
        bingo = auto()
    class AfterCardDiscard(IntEnum):
        inv_belt = auto()
        belt = auto()
    class AfterCardRemove(IntEnum):
        pass
    class AfterExchange(IntEnum):
        pass
    class OnDeath(IntEnum):
        invincible = auto()             # 吸血鬼：免疫死亡
        explore = auto()                # 秘史衍生：免疫死亡，以及死亡时间减少
        miansi = auto()                 # 倒吊人：免疫一次死亡
        sihuihuibizhiyao = auto()       # 死秽：消耗击毙免疫一次死亡
        hongsezhihuan = auto()          # 虹环：一半免疫一次死亡
        inv_sihuihuibizhiyao = auto()   # 反转死秽
        death = auto()                  # 死神：死亡时间加倍
        fuhuoguanghuan = auto()         # 因hp归零死亡时间除以12
        absorb = auto()                 # 吸收死亡时间
        changsheng = auto()             # 吸收死亡时间MkII
        tiesuolianhuan = auto()         # 铁索连环：一起下地狱
        lveduozhebopu = auto()          # 掠夺者：被弃
        huiye = auto()                  # 宝箱：抽卡
        inv_huiye = auto()              # 反转宝箱
        shangba = auto()                # 伤疤：+2击毙
        invshangba = auto()
        antimatter = auto()             # 反物质维度：自动使用卡牌
        bingo = auto()                  # bingo任务
    class OnAttack(IntEnum):
        imaginebreaker = auto()         # 幻杀：破防
                                        # imagine breaker is suggested to be the first
        vector = auto()                 # 矢量：双倍
        youlong = auto()                # 幼龙：造成伤害*1.5
        bizhong = auto()                # 必中：必中并且造成伤害*1.5
        konghe = auto()                 # 恐吓：造成伤害减半
    class OnAttacked(IntEnum):
        McGuffium239 = auto()           # 麦高芬：免疫礼物交换
        shanbi = auto()                 # 闪避：躲避受伤
        imaginebreaker = auto()         # 幻杀：无效
        hudun = auto()                  # 护盾：对龙造成伤害的闪避率+20%
        qiangshenjianti = auto()        # 强身健体：受伤减半
        youlong = auto()                # 幼龙：承担受到伤害的50%
        vector = auto()                 # 矢量：反弹
                                        # vector is suggested to be the last
    class OnDodged(IntEnum):
        pass
    class OnStatusAdd(IntEnum):
        jiaodai = auto()                # 胶带：免除负面状态
        inv_jiaodai = auto()            # 反转胶带
        paean = auto()                  # 光阴神：3*胶带
        sunflower = auto()              # 向日葵：检测是否密植
        twinsunflower = auto()
        panjue = auto()                 # contains both a and b
        panjue_activated = auto()       # contains both a and b
        beacon = auto()                 # 速度插件：检测寒冰菇
        beacon1 = auto()                # 全局速度插件
        bingo = auto()
    class OnStatusRemove(IntEnum):
        train = auto()
    class AfterStatusRemove(IntEnum):
        antimatter = auto()             # 反物质维度：自动使用卡牌
    class CheckJibiSpend(IntEnum):
        bianyaqi = auto()
        steamsummer = auto()
        beijingcard = auto()
    class OnJibiChange(IntEnum):
        gaojie = auto()                 # 告解：每获得击毙+1击毙
        inv_gaojie = auto()             # 反转告解
        bikini = auto()                 # 比基尼：有几率翻倍
        schoolsui = auto()              # 死库水：有几率免单
        beacon = auto()                 # 个人插件-产能：有几率加获得，有上限-节能：有几率降支出，有上限
        beacon0 = auto()                # 分享塔全局插件-产能
        beacon2 = auto()                # 分享塔全局插件-节能
        shuairuo = auto()               # 衰弱：获得击毙降为75%
        bianyaqi = auto()               # 变压器：加倍击毙变动
        inv_bianyaqi = auto()           # 反转变压器
        steamsummer = auto()            # Steam夏季促销：减半购买支出
        beijingcard = auto()            # 一卡通：根据消费总量打折
        shenmouyuanlv = auto()          # 绿帽：击毙减半则免单
        train = auto()                  # 火车：便乘
        bingo = auto()
    class CheckEventptSpend(IntEnum):
        pass
    class OnEventptChange(IntEnum):
        pass
    class BeforeDragoned(IntEnum):
        explore = auto()                # 秘史：减少此次接龙的死亡时间
        death = auto()                  # 死人不能接龙
        wufazhandou = auto()            # 死人不能接龙
        shengbing = auto()              # 病人也不能接龙
        minus1ma = auto()               # ±1马：计算距离
        plus1ma = auto()
        iceshroom = auto()              # 冰/热菇：全局计算距离
        hotshroom = auto()
        lazhuyandong = auto()           # 秘史衍生：计算距离
        invlazhuyandong = auto()
        lieshouzhixue = auto()
        invlieshouzhixue = auto()
        ourostone = auto()              # 衔尾蛇：首尾
                                        # contains two buffs
        ranshefashu = auto()            # **法术：首尾
        inv_ranshefashu = auto()
        jiaotu = auto()                 # 秘史衍生：首尾
        invjiaotu = auto()
        shequn = auto()
        invshequn = auto()
        hierophant = auto()             # 教皇：首尾
        inv_hierophant = auto()
        uncertainty = auto()            # 不确定性原理：修改接龙词
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
        kongzhongcanting = auto()       # 空中餐厅「逻辑」：随机复活
    class OnBombed(IntEnum):
        hermit = auto()
        vector = auto()
        kongzhongcanting = auto()       # 空中餐厅「逻辑」：随机复活
    class OnDragoned(IntEnum):
        mofajiqu = auto()               # 魔法汲取：回复MP
        queststone = auto()             # 任务：完成+3击毙
        quest = auto()
        bingo = auto()                  # bingo：接龙任务
        hierophant = auto()             # 教皇：+2击毙
        inv_hierophant = auto()         # 反转教皇
        lveduozhebopu = auto()          # 掠夺者：偷窃判定
        bianhua = auto()                # 彼岸花：-1/3击毙
        inv_bianhua = auto()            # 反转
        zpm = auto()                    # ZPM：新手保护，+1击毙
        shendian = auto()               # 秘史衍生：+5击毙
        invshendian = auto()
        beizhizhunze = auto()           # +1击毙
        invbeizhizhunze = auto()
        cashprinter = auto()            # 给前面的人+1击毙
        plus2 = auto()                  # +2：抽两张牌
        xixuegui = auto()               # ？？？？
        panjue = auto()                 # 判决传播 contains both a and b
        panjuecheck = auto()            # 判决重合 contains both a and b
        jack_in_the_box = auto()        # 玩偶匣：爆炸判定
        star = auto()                   # 星星：奖励词判定
        dihuopenfa = auto()             # 地火：埋雷判定
        xixueshashou = auto()           # 吸血杀手：抽卡判定
        forkbomb = auto()               # 叉子炸弹：分叉判定
        timebomb = auto()               # 定时炸弹：计次
        circus = auto()                 # 秘史衍生：被弃
        lazhuyandong = auto()
        invlazhuyandong = auto()
        lieshouzhixue = auto()
        invlieshouzhixue = auto()
        shequn = auto()
        invshequn = auto()
        jiaotu = auto()
        invjiaotu = auto()
        explore = auto()                # 秘史
        kongzhongcanting = auto()       # 空中餐厅「逻辑」：随机回满血/复活
    class OnNewDay(IntEnum):
        tarot = auto()
        quest = auto()
        sunflower = auto()
        twinsunflower = auto()
        inv_sunflower = auto()
        inv_twinsunflower = auto()
        timebomb = auto()

TBoundIntEnum = TypeVar('TBoundIntEnum', bound=IntEnum)

class Pack(Enum):
    tarot = auto()
    minecraft = auto()
    zhu = auto()
    sanguosha = auto()
    honglongdong = auto()
    uno = auto()
    once_upon_a_time = auto()
    explodes = auto()
    stone_story = auto()
    orange_juice = auto()
    playtest = auto()
    poker = auto()
    gregtech = auto()
    cultist = auto()
    ff14 = auto()
    toaru = auto()
    pvz = auto()
    secret_history = auto()
    misc = auto()
    factorio = auto()
    silly = auto()
    physic = auto()
    stare = auto()
    rusty_lake = auto()
class Sign(IntEnum):
    shiyuan = 0
    jiesha = 1
    tonglin = 2
    momi = 3
    xieshen = 4
    tianqiong = 5
    #feixi = 6
    @classmethod
    def random(cls):
        import random
        return random.choice(list(cls))
    def pack(self):
        return [{Pack.tarot},
            {Pack.zhu, Pack.sanguosha, Pack.uno, Pack.once_upon_a_time, Pack.playtest, Pack.poker},
            {Pack.minecraft, Pack.gregtech, Pack.explodes, Pack.orange_juice, Pack.ff14},
            {Pack.cultist, Pack.secret_history, Pack.pvz, Pack.stone_story},
            {Pack.toaru, Pack.factorio, Pack.physic},
            {Pack.misc},
            {Pack.honglongdong, Pack.silly},
            {Pack.stare, Pack.rusty_lake}][self]
    @property
    def name_ch(self):
        return ["始源座", "皆杀座", "通林座", "墨密座", "械神座", "天穹座", "飞戏座"][self]
    @property
    def contains_ch(self):
        return ["塔罗",
            "逐梦东方圈、三国杀、uno、很久很久以前、试个好游戏、扑克牌",
            "Minecraft、格雷科技、保持说话不会爆炸、100%鲜橙汁、FF14",
            "密教模拟器及其秘史、植物大战僵尸、Stone Story RPG",
            "魔法禁书目录，factorio，近代物理",
            "Misc",
            "东方虹龙洞卡牌、愚蠢",
            "凝视、锈湖"][self]
    @property
    def description(self):
        return f"{self.name_ch}{句尾}\n\t卡包：{self.contains_ch}的牌掉率提升{句尾}"
    @classmethod
    def description_all(cls):
        return "\n".join(f"{int(i)}. {i.description}" for i in Sign)

class UnableRequirement(Exception):
    pass
class NotActive(Exception):
    pass

class DragonState:
    def __init__(self, word: str, parent: 'Tree'):
        self.word = word
        self.parent = parent
        self.shouwei = parent.word == '' or word == '' or parent.word[-1] == word[0]
        self.weishou = parent.word == '' or word == '' or parent.word[0] == word[-1]
    async def OnShouWei(self, user): # changable in card USB Type-A
        pass
    async def OnWeiShou(self, user): # changable in card USB Type-A
        pass
    async def require_shouwei(self, user):
        await self.OnShouWei(user)
        return self.shouwei
    async def require_weishou(self, user):
        await self.OnWeiShou(user)
        return self.weishou

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
            _raise_failure("你的手牌为：\n" + '\n'.join(s.brief_description() for s in user.data.hand_card))
        elif value in ("查询详细手牌", "查看详细手牌"):
            _raise_failure("你的手牌为：\n" + '\n'.join(s.full_description(user.qq) for s in user.data.hand_card))
        elif value in ("查询装备", "查看装备"):
            from .logic_dragon_file import Equipment
            _raise_failure("你的装备为：\n" + '\n'.join(Equipment(id).full_description(num, user) for id, num in user.data.equipment.items()))
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

class indexer:
    def __init__(self, fget=None, fset=None):
        self.fget = fget
        self.fset = fset
        self._indexer = _indexer(self)
        self._name = ''
    def __set_name__(self, owner, name):
        self._name = name
    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        self._indexer.obj = obj
        return self._indexer
    def setter(self, fset):
        prop = type(self)(self.fget, fset)
        prop._name = self._name
        return prop
class _indexer:
    def __init__(self, parent: indexer):
        self.parent: indexer = parent
        self.obj = None
    def __getitem__(self, index):
        return self.parent.fget(self.obj, index)
    def __setitem__(self, index, item):
        self.parent.fset(self.obj, index, item)

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

from .maj import MajHai

class MajOneHai(MajHai):
    SAME = 1
    @staticmethod
    def ten(tehai: 'List[MajOneHai]') -> Dict[int, List[Dict[int, Tuple[Tuple[int,...],...]]]]:
        ten = MajHai.ten(tehai)
        for d in (MajHai.qitui(tehai).items(), MajHai.kokushimusou(tehai).items()):
            for key, val in d:
                if key in ten:
                    ten[key].extend(val)
                else:
                    ten[key] = val
        return ten
    @staticmethod
    async def draw_maj(tehai: 'List[MajOneHai]',
            ankan: Iterable[int] = (),
            to_draw: Optional['MajOneHai'] = None) -> str:
        from ..misc import Maj, GetMajImg
        s = ''.join([str(MajOneHai(c)) * 3 for c in ankan] + [str(c) for c in tehai])
        if to_draw is None:
            s += "0p"
        else:
            s += str(to_draw)
        test = Maj.compile(s, True, None, None, None, None)
        name = await GetMajImg(test)
        img = "[CQ:image,file=" + name + ".png]"
        if len(ankan) != 0:
            img += f"（左侧有{len(ankan)}个暗杠）"
        return img
        # return ('' if len(ankan) == 0 else ' '.join(str(h) * 4 for h in ankan)) + ''.join(str(h) for h in tehai) + ('' if to_draw is None else ' ' + str(to_draw))
    @functools.total_ordering
    class HeZhong:
        data: Dict[Tuple[int, int, int], Tuple[str, int]] = {(0, 0, 0): ("立直", 1), (0, 0, 1): ("两立直", 2),
        (0, 1, 0): ("门前清自摸和", 1), (0, 2, 0): ("里宝牌", 1), (1, 0, 0): ("断幺九", 1), (1, 1, 0): ("平和", 1),
        (2, 0, 0): ("混一色", 3), (2, 0, 1): ("清一色", 6), (2, 1, 0): ("九莲宝灯", 13), (2, 1, 1): ("纯正九莲宝灯", 26),
            (2, 2, 0): ("绿一色", 13), (2, 3, 0): ("黑一色", 13), (2, 4, 0): ("天地创造", 105),
        (3, 0, 0): ("三元牌：白", 1), (3, 1, 0): ("三元牌：发", 1), (3, 2, 0): ("三元牌：中", 1),
            (3, 3, 0): ("小三元", 2), (3, 3, 1): ("大三元", 13),
            (3, 4, 0): ("小三风", 1), (3, 4, 1): ("大三风", 2), (3, 4, 2): ("小四喜", 13), (3, 4, 3): ("大四喜", 26),
            (3, 5, 0): ("字一色", 13),
        (4, 0, 0): ("三暗刻", 2), (4, 0, 1): ("四暗刻", 13), (4, 0, 2): ("四暗刻单骑", 26),
            (4, 1, 0): ("一杠子", 1), (4, 1, 1): ("二杠子", 2), (4, 1, 2): ("三杠子", 3), (4, 1, 3): ("四杠子", 13),
        (5, 0, 0): ("一杯口", 1), (5, 0, 1): ("两杯口", 3), (5, 0, 2): ("一色三同顺", 3), (5, 0, 3): ("一色四同顺", 13),
            (5, 1, 0): ("双同刻", 2), (5, 1, 1): ("一色三同刻", 4), (5, 1, 2): ("一色四同刻", 13),
        (6, 0, 0): ("三色同顺", 2), (6, 1, 0): ("三色小同刻", 1), (6, 1, 1): ("三色同刻", 2),
        (7, 0, 0): ("一气通贯", 2),
        (8, 0, 0): ("混全带幺九", 2), (8, 0, 1): ("纯全带幺九", 3), (8, 0, 2): ("混老头", 2), (8, 0, 3): ("清老头", 13),
        (9, 0, 0): ("五门齐", 2),
        (10, 0, 0): ("国士无双", 13), (10, 0, 1): ("国士无双十三面听", 26),
            (10, 1, 0): ("七对子", 2), (10, 1, 1): ("大数邻", 13), (10, 1, 2): ("大车轮", 13), (10, 1, 3): ("大竹林", 13),
            (10, 1, 4): ("大七星", 26),
        (11, 0, 0): ("岭上开花", 1), (11, 1, 0): ("天和", 13)}
        @staticmethod
        def ten(l: 'List[MajOneHai.HeZhong]') -> int:
            l.sort()
            ten = 0
            for h in l:
                ten += h.int()
            return ten
        def __init__(self, t: Tuple[int, int, int]):
            self.tuple = t
        def __str__(self):
            return self.data[self.tuple][0]
        def int(self):
            return self.data[self.tuple][1]
        def __lt__(self, other):
            return self.tuple < other.tuple
        def __eq__(self, other):
            return self.tuple == other.tuple
    @staticmethod
    def tensu(results: List[Dict[int, Tuple[Tuple[int,...],...]]], ankan: List[int], final_hai: int, if_richi: bool, ura: List['MajOneHai'], is_first: bool, is_rinshan: bool) -> 'Tuple[List[MajOneHai.HeZhong], MajOneHai.HeZhong.Status, int]':
        def _f(result: Dict[int, Tuple[Tuple[int,...],...]], ankan: List[int], final_hai: int, if_richi: bool, ura: List['MajOneHai'], is_first: bool, is_rinshan: bool) -> 'List[MajOneHai.HeZhong]':
            HeZhong = MajOneHai.HeZhong
            l = []
            if is_first:
                if if_richi:
                    l.append(HeZhong((0, 0, 1)))   # 两立直
                else:
                    l.append(HeZhong((11, 1, 0)))   # 天和
            elif if_richi:
                l.append(HeZhong((0, 0, 0)))    # 立直
            if is_rinshan:
                l.append(HeZhong((11, 0, 0)))   # 岭上开花
            if set(result.keys()) == {7} and set(ankan) == {31}:
                l.append(HeZhong((2, 4, 0)))     # 天地创造
                if if_richi:
                    for dora in ura:
                        dora1 = dora.addOneDora()
                        if dora1.hai == 31:
                            for i in range(len(ankan) + 14):
                                l.append(HeZhong((0, 2, 0)))    # 里宝牌
                l.sort()
                return l
            l.append(HeZhong((0, 1, 0)))            # 门前清自摸和
            if if_richi:
                for dora in ura:
                    dora1 = dora.addOneDora()
                    for key, val in result.items():
                        for h in functools.reduce(operator.add, val):
                            if key == dora1.barrel and (dora1.barrel >= 3 or h == dora1.num):
                                l.append(HeZhong((0, 2, 0)))    # 里宝牌
                    for hai in ankan:
                        if hai == dora1.hai:
                            l.append(HeZhong((0, 2, 0)))
                            l.append(HeZhong((0, 2, 0)))
                            l.append(HeZhong((0, 2, 0)))
                            l.append(HeZhong((0, 2, 0)))
            #特殊类
            if 0 in result and len(result[0][0]) >= 13:
                if result[1][0][0] == final_hai:
                    l.append(HeZhong((10, 0, 1)))   # 国士无双十三面
                else:
                    l.append(HeZhong((10, 0, 0)))   # 国士无双，不加算其他
                return l
            shun: List[Tuple[Tuple[int,...], int]] = []
            ke  : List[Tuple[Tuple[int,...], int]] = []
            dui : List[Tuple[Tuple[int,...], int]] = []
            gang: List[Tuple[Tuple[int,...], int]] = [(((t := MajOneHai(s)).num, t.num, t.num, t.num), t.barrel) for s in ankan]
            for barrel, vals in result.items():
                for val in vals:
                    if len(val) == 2:
                        dui.append((val, barrel))
                    elif len(val) > 2 and val[0] == val[1]:
                        ke.append((val, barrel))
                    else:
                        shun.append((val, barrel))
            assert(len(dui) == 7 or len(dui) == 1 and len(shun) + len(ke) + len(gang) == 4)
            ke += gang
            al = shun + ke + dui
            shun.sort()
            ke.sort()
            gang.sort()
            if len(dui) == 7:
                if all(b == dui[0][1] for i, b in dui) and dui[0][1] <= 2 and set(i[0] for i, b in dui) == {1, 2, 3, 4, 5, 6, 7}:
                    l.append(HeZhong((10, 1, dui[0][1] + 1))) # 大车轮等
                elif set(b for i, b in dui) == {3, 4, 5, 6, 7, 8, 9}:
                    l.append(HeZhong((10, 1, 4)))   # 大七星
                else:
                    l.append(HeZhong((10, 1, 0)))   # 七对子
            if len(shun) == 4:
                for i, b in shun:
                    if final_hai == i[0] or final_hai == i[2]:
                        l.append(HeZhong((1, 1, 0)))    # 平和
                        break
            if all(map(lambda x: x[1] <= 2 and all(map(lambda y: y != 0 and y != 8, x[0])), al)):
                l.append(HeZhong((1, 0, 0)))    #断幺九
            colors = set(map(lambda x: x[1], al))
            if len(colors & {0, 1, 2}) == 1:
                if len(colors) == 1:
                    hais = list(functools.reduce(operator.add, result[list(colors)[0]]))
                    hais.remove(final_hai % 9)
                    hais.sort()
                    if tuple(hais) == (0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 8, 8):
                        l.append(HeZhong((2, 1, 1)))    #纯正九莲宝灯
                    else:
                        hais.append(final_hai % 9)
                        t = Counter(hais)
                        t.subtract(Counter((0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 8, 8)))
                        if t == +t:
                            l.append(HeZhong((2, 1, 0)))    #九莲宝灯
                        else:
                            l.append(HeZhong((2, 0, 1)))    #清一色
                else:
                    l.append(HeZhong((2, 0, 0)))    #混一色
            elif len(colors & {0, 1, 2}) == 0 and HeZhong((10, 1, 4)) not in l:
                l.append(HeZhong((3, 5, 0)))   #字一色
            if colors - {2, 8} == set():
                if 2 not in result:
                    l.append(HeZhong((2, 2, 0)))
                else:
                    hais = set(functools.reduce(operator.add, result[2]))
                    if hais - {1, 2, 3, 5, 7} == set():
                        l.append(HeZhong((2, 2, 0)))    #绿一色
            elif colors - {1, 3, 4, 5, 6} == set():
                if 1 not in result:
                    l.append(HeZhong((2, 3, 0)))
                else:
                    hais = set(functools.reduce(operator.add, result[1]))
                    if hais - {1, 3, 7} == set():
                        l.append(HeZhong((2, 3, 0)))    #黑一色
            zi = [x[1] for x in ke if x[1] >= 3]
            zi_dui = dui[0][1]
            for i in zi:
                if i in (7, 8, 9):
                    l.append(HeZhong((3, i - 7, 0)))    #番牌：白发中
            zi = set(zi)
            sanyuan = {7, 8, 9}
            if sanyuan <= zi:
                l.append(HeZhong((3, 3, 1)))    #大三元
            elif len(sanyuan - zi) == 1 and zi_dui in sanyuan - zi:
                l.append(HeZhong((3, 3, 0)))    #小三元
            sixi = {3, 4, 5, 6}
            if sixi <= zi:
                l.append(HeZhong((3, 4, 3)))    #大四喜
            elif len(sixi - zi) == 1:
                if zi_dui in sixi - zi:
                    l.append(HeZhong((3, 4, 2)))    #小四喜
                else:
                    l.append(HeZhong((3, 4, 1)))    #大三风
            elif len(sixi - zi) == 2 and zi_dui in sixi - zi:
                l.append(HeZhong((3, 4, 0)))    #小三风
            if len(ke) == 4:
                if final_hai % 9 in dui[0][0] and MajOneHai(final_hai).barrel == dui[0][1]:
                    l.append(HeZhong((4, 0, 2)))    #四暗刻单骑
                else:
                    l.append(HeZhong((4, 0, 1)))    #四暗刻
            elif len(ke) == 3:
                l.append(HeZhong((4, 0, 0)))    #三暗刻
            if len(gang) != 0:
                l.append(HeZhong((4, 1, len(gang) - 1)))    #x杠子
            t = []
            if len(shun) >= 2:
                for i in range(len(shun) - 1):
                    if shun[i][0:2] == shun[i + 1][0:2]:
                        t.append(i)
            if len(t) == 3:
                l.append(HeZhong((5, 0, 3)))    #一色四同顺
            elif len(t) == 2:
                if t[1] == t[0] + 1:
                    l.append(HeZhong((5, 0, 2)))    #一色三同顺
                else:
                    l.append(HeZhong((5, 0, 1)))    #两般高
            elif len(t) == 1:
                l.append(HeZhong((5, 0, 0)))    #一般高
            t = []
            if len(ke) >= 2:
                for i in range(len(ke) - 1):
                    if ke[i][0] == ke[i + 1][0]:
                        t.append(i)
            if len(t) == 3:
                l.append(HeZhong((5, 1, 2)))    #一色四同刻
            elif len(t) == 2:
                if t[1] == t[0] + 1:
                    l.append(HeZhong((5, 1, 1)))    #一色三同刻
            elif len(t) == 1:
                l.append(HeZhong((5, 1, 0)))    #双同刻
            for i, j, k in itertools.combinations(shun, 3):
                if i[0] == j[0] == k[0] and (i[1], j[1], k[1]) == (0, 1, 2):
                    l.append(HeZhong((6, 0, 0)))    #三色同顺
                    break
                elif i[1] == j[1] == k[1] and (i[0], j[0], k[0]) == ((0, 1, 2), (3, 4, 5), (6, 7, 8)):
                    l.append(HeZhong((7, 0, 0)))    #一气通贯
                    break
            if len(ke) >= 2:
                for i, j, k in itertools.combinations(itertools.chain(ke, dui), 3):
                    if i[0][0] == j[0][0] == k[0][0] and {i[1], j[1], k[1]} == {0, 1, 2}:
                        if len(k[0]) == 2:
                            l.append(HeZhong((6, 1, 0)))    #三色小同刻
                        else:
                            l.append(HeZhong((6, 1, 1)))    #三色同刻
                        break
            if all(map(lambda x: x[1] <= 2 and all(map(lambda y: y == 0 or y == 8, x[0])), al)):
                l.append(HeZhong((8, 0, 3)))    #清老头
            elif all(map(lambda x: x[1] >= 3 or x[1] <= 2 and all(map(lambda y: y == 0 or y == 8, x[0])), al)):
                l.append(HeZhong((8, 0, 2)))    #混老头
            elif all(map(lambda x: x[1] <= 2 and any(map(lambda y: y == 0 or y == 8, x[0])), al)):
                l.append(HeZhong((8, 0, 1)))    #纯全带幺九
            elif all(map(lambda x: x[1] >= 3 or x[1] <= 2 and any(map(lambda y: y == 0 or y == 8, x[0])), al)):
                l.append(HeZhong((8, 0, 0)))    #混全带幺九
            s = set(b for i, b in al)
            if {0, 1, 2} <= s and s & {3, 4, 5, 6} and s & {7, 8, 9}:
                l.append(HeZhong((9, 0, 0)))    #五门齐
            l.sort()
            return l
        _max = ([], 0)
        for result in results:
            _now = _f(result, ankan, final_hai, if_richi, ura, is_first, is_rinshan)
            ten = MajOneHai.HeZhong.ten(_now)
            if ten > _max[1]:
                _max = (_now, ten)
        return _max