import itertools, hashlib
import random, more_itertools, json, re
from typing import Any, Awaitable, Callable, Coroutine, Dict, Iterable, List, NamedTuple, Optional, Set, Tuple, Type, TypeVar, TypedDict, Union
from collections import Counter, UserDict
from functools import lru_cache, partial, wraps
from copy import copy
from datetime import datetime, timedelta
from functools import reduce
from nonebot.command import CommandSession
from pypinyin import pinyin, Style
from nonebot.command.argfilter import extractors, validators
from .. import config

class UserChooseMe(Exception):
    pass

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
        config.userdata.execute('insert into dragon_data (qq, jibi, draw_time, today_jibi, today_keyword_jibi, death_time, card, status, daily_status, status_time, card_limit, shop_drawn_card, event_pt, spend_shop, equipment) values (?, 0, 0, 10, 10, ?, ?, ?, ?, ?, 4, 0, 0, 0, ?)', (qq, '', '', '', '', '{}', '{}'))
        t = config.userdata.execute("select * from dragon_data where qq=?", (qq,)).fetchone()
    return t

T_card = TypeVar('T_card', bound='_card')
TCard = Type[T_card]
T_equipment = TypeVar('T_equipment', bound='_equipment')
TEquipment = Type[T_equipment]

class Game:
    session_list: List[CommandSession] = []
    userdatas: Dict[int, 'UserData'] = {}
    @classmethod
    def wrapper_noarg(cls, f: Awaitable):
        @wraps(f)
        async def _f():
            try:
                return await f()
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
            except UserChooseMe:
                buf.send("呀！不能选我！")
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
            raise UserChooseMe()
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
class Wrapper:
    def __init__(self, qq):
        self.qq = qq
    def __lshift__(self, log):
        config.logger.dragon << f"【LOG】用户{self.qq}" + log
class UserData:
    def __init__(self, qq: int):
        self._qq = qq
        self.node: TUserData = dict(find_or_new(qq))
        self.hand_card = [] if self.node['card'] == '' else [Card(int(x)) for x in self.node['card'].split(',')]
        def save(key, value):
            config.userdata.execute(f"update dragon_data set {key}=? where qq=?", (str(value), self.qq))
        self.status_time = property_dict(partial(save, 'status_time'), {})
        self.status_time.data = eval(self.node['status_time'])
        self.equipment = property_dict(partial(save, 'equipment'), {})
        self.equipment.data = eval(self.node['equipment'])
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
            self._event_stage: Grid = Grid(self.node['event_stage'] % 2048, self.node['event_stage'] // 2048)
        return self._event_stage
    @event_stage.setter
    def event_stage(self, value: 'Grid'):
        self._event_stage = value
        config.userdata.execute("update dragon_data set event_stage=? where qq=?", (self._event_stage.data_saved, self.qq))
    @property
    def event_shop(self):
        return self.node['event_shop']
    @event_shop.setter
    def event_shop(self, value):
        config.userdata.execute("update dragon_data set event_shop=? where qq=?", (value, self.qq))
        self.node['event_shop'] = value
    def set_cards(self):
        config.userdata.execute("update dragon_data set card=? where qq=?", (','.join(str(c.id) for c in self.hand_card), self.qq))
        config.logger.dragon << f"【LOG】设置用户{self.qq}手牌为{cards_to_str(self.hand_card)}。"
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
    def add_status(self, s: str):
        self.status += s
        self.log << f"增加了永久状态{s}，当前状态为{self.status}。"
    def add_daily_status(self, s: str):
        self.daily_status += s
        self.log << f"增加了每日状态{s}，当前状态为{self.daily_status}。"
    def add_limited_status(self, s: str, end_time: datetime):
        if s not in self.status_time:
            self.status_time[s] = end_time.isoformat()
        else:
            self.status_time[s] = max(datetime.fromisoformat(self.status_time[s]), end_time).isoformat()
        self.log << f"增加了限时状态{s}，结束时间为{end_time}。"
    def remove_status(self, s: str, *, remove_all=True):
        if remove_all:
            self.status = ''.join([t for t in self.status if t != s])
        else:
            l = list(self.status)
            if s in l:
                l.remove(s)
            self.status = ''.join(l)
        self.log << f"移除了{'一层' if not remove_all else ''}永久状态{s}，当前状态为{self.status}。"
    def remove_daily_status(self, s: str, *, remove_all=True):
        if remove_all:
            self.daily_status = ''.join([t for t in self.daily_status if t != s])
        else:
            l = list(self.daily_status)
            if s in l:
                l.remove(s)
            self.daily_status = ''.join(l)
        self.log << f"移除了{'一层' if not remove_all else ''}每日状态{s}，当前状态为{self.daily_status}。"
    def remove_limited_status(self, s: str):
        if s in self.status_time:
            del self.status_time[s]
        self.log << f"移除了限时状态{s}，当前限时状态为{str(self.status_time)}。"
    def check_status(self, s: str) -> int:
        return self.status.count(s)
    def check_daily_status(self, s: str) -> int:
        return self.daily_status.count(s)
    def check_limited_status(self, s: str):
        if s not in self.status_time:
            return False
        t = datetime.fromisoformat(self.status_time[s])
        if t < datetime.now():
            del self.status_time[s]
            return False
        return True
    def get_limited_time(self, s: str):
        if s not in self.status_time:
            return None
        delta = datetime.fromisoformat(self.status_time[s]) - datetime.now()
        if delta < timedelta():
            del self.status_time[s]
            return None
        return delta.seconds // 60
    def check_equipment(self, equip_id: int) -> int:
        return self.equipment.get(equip_id, 0)

class User:
    def __init__(self, qq: int, buf: config.SessionBuffer):
        self.qq = qq
        self.data = Game.userdata(qq)
        self.buf = buf
    @property
    def char(self):
        return self.buf.char(self.qq)
    def send_char(self, s: str):
        self.buf.send(self.char + s)
    def send_log(self, s: str):
        self.buf.send_log.dragon(self.qq, s)
    def decrease_death_time(self, time: timedelta):
        if 'd' in self.data.status_time:
            t = datetime.fromisoformat(self.data.status_time['d'])
            t -= time
            if t < datetime.now():
                self.data.status_time.pop('d')
            else:
                self.data.status_time['d'] = t.isoformat()
            return 'd' not in self.data.status_time
        return True
    @property
    def log(self):
        return self.data.log
    async def add_event_pt(self, pt: int):
        self.data.event_pt += pt
        self.send_char(f"收到了{pt}活动pt！")
        self.log << f"增加了{pt}活动pt。现有{self.data.event_pt}活动pt。"
    async def add_jibi(self, jibi: int, /, is_buy: bool=False):
        current_jibi = self.data.jibi
        if s := self.data.check_daily_status('@'):
            if jibi > 0:
                jibi += s
                self.send_char(f"触发了{f'{s}次' if s > 1 else ''}告解的效果，获得击毙加{s}。")
            else: s = 0
        if n := self.data.check_status('2'):
            jibi *= 2 ** n
            self.send_char(f"触发了{f'{n}次' if n > 1 else ''}变压器的效果，{'获得' if jibi >= 0 else '损失'}击毙加倍为{abs(jibi)}！")
            self.data.remove_status('2')
        if q := self.data.check_equipment(0):
            if jibi > 0 and random.random() < 0.05 * q:
                jibi *= 2
                self.send_char(f"触发了比基尼的效果，获得击毙加倍为{abs(jibi)}！")
            else: q = 0
        dodge = False
        if r := self.data.check_equipment(1):
            if jibi < 0 and random.random() < r / (20 + r):
                dodge = True
                self.send_char(f"触发了学生泳装的效果，本次免单！")
        if m := self.data.check_status('S'):
            if is_buy and not dodge:
                jibi //= 2 ** m
                self.send_char(f"触发了{f'{m}次' if m > 1 else ''}Steam夏季特卖的效果，花费击毙减半为{abs(jibi)}！")
                self.data.remove_status('S')
            else: m = 0
        if p := self.data.check_status('1'):
            if is_buy and not dodge:
                if 100 <= self.data.spend_shop < 150:
                    jibi  = int(jibi * 0.8 ** p)
                    self.send_char(f"触发了{f'{p}次' if p > 1 else ''}北京市政交通一卡通的效果，花费击毙打了8折变为{abs(jibi)}！")
                elif 150 <= self.data.spend_shop < 400:
                    jibi = int(jibi * 0.5 ** p)
                    self.send_char(f"触发了{f'{p}次' if p > 1 else ''}北京市政交通一卡通的效果，花费击毙打了5折变为{abs(jibi)}！")
                elif self.data.spend_shop >= 400:
                    self.send_char("今日已花费400击毙，不再打折！")
            else: p = 0
        dodge2 = False
        if t := self.data.check_status('n'):
            if not dodge and jibi < 0 and -jibi >= self.data.jibi / 2:
                dodge2 = True
                self.data.remove_status('n', remove_all=False)
        if not dodge and not dodge2:
            self.data.jibi += jibi
        self.log << f"原有击毙{current_jibi}，{f'触发了{s}次告解的效果，' if s > 0 else ''}{f'触发了{n}次变压器的效果，' if n > 0 else ''}{f'触发了比基尼的效果，' if q > 0 else ''}{f'触发了学生泳装的效果，' if dodge else ''}{f'触发了{m}次Steam夏季特卖的效果，' if m > 0 else ''}{f'触发了{p}次北京市政交通一卡通的效果，' if p > 0 else ''}{f'触发了深谋远虑之策的效果，' if dodge2 else ''}{'获得' if jibi >= 0 else '损失'}了{abs(jibi)}。"
        if is_buy and not dodge:
            self.data.spend_shop += abs(jibi)
            self.log << f"累计今日商店购买至{self.data.spend_shop}。"
    async def kill(self, hour: int=2, minute: int=0):
        """击杀玩家。"""
        dodge = False
        config.logger.dragon << f"【LOG】尝试击杀玩家{self.qq}。"
        if self.data.check_status('r') and not dodge:
            dodge = True
            self.send_log("触发了免死的效果，免除死亡！")
            self.data.remove_status('r', remove_all=False)
        if (n := self.data.check_status('s')) and not dodge:
            if self.data.jibi >= 5 * 2 ** self.data.check_status('2'):
                await self.add_jibi(-5)
                self.send_log("触发了死秽回避之药的效果，免除死亡！")
                dodge = True
                self.data.remove_status('s', remove_all=False)
        if (n := self.data.check_status('h')) and not dodge:
            for a in range(n):
                self.data.remove_status('h', remove_all=False)
                if random.randint(0, 1) == 0:
                    self.send_log("触发了虹色之环，闪避了死亡！")
                    dodge = True
                    break
                else:
                    self.send_log("触发虹色之环闪避失败，死亡时间+1h！")
        if (n := self.data.check_status('p')) and not dodge:
            self.log << f"的{n}张掠夺者啵噗因死亡被弃置。"
            await self.discard_cards([Card(77) for i in range(n)])
        time = timedelta(hours=hour, minutes=minute)
        if (n := me.check_daily_status('D')) and not dodge:
            time *= 2 ** n
        if not dodge:
            self.data.add_limited_status('d', datetime.now() + time)
            m = time.seconds // 60
            self.send_char(f"死了！{f'{m // 60}小时' if m >= 60 else ''}{f'{m % 60}分钟' if m % 60 != 0 else ''}不得接龙。")
            if (x := self.data.check_status('x')):
                self.data.remove_status('x')
                self.send_log(f"触发了辉夜姬的秘密宝箱！奖励抽卡{x}张。")
                await self.draw(x)
            global global_state
            if self.qq in global_state['lianhuan']:
                l = copy(global_state['lianhuan'])
                global_state['lianhuan'] = []
                save_global_state()
                l.remove(self.qq)
                self.buf.send(f"由于铁索连环的效果，{' '.join(f'[CQ:at,qq={target}]' for target in l)}个人也一起死了！")
                self.log << f"触发了铁索连环的效果至{l}。"
                for target in l:
                    await User(target, self.buf).kill(hour=hour)
    async def draw(self, n: int, /, positive=None, cards=None):
        """抽卡。将卡牌放入手牌。"""
        cards = draw_cards(positive, n) if cards is None else cards
        if n := cards.count(Card(67)):
            for i in range(n):
                await Card(67).on_draw(self)
        self.send_char('抽到的卡牌是：\n' + '\n'.join(c.full_description(self.qq) for c in cards))
        self.log << f"抽到的卡牌为{cards_to_str(cards)}。"
        for c in cards:
            if not c.consumed_on_draw:
                self.data.hand_card.append(c)
            if c.id != 67:
                await c.on_draw(self)
        self.data.set_cards()
        self.log << f"抽完卡牌，当前手牌为{cards_to_str(self.data.hand_card)}。"
    async def use_card(self, card: TCard):
        """使用卡牌。不处理将卡牌移出手牌的操作。"""
        self.send_char('使用了卡牌：\n' + card.full_description(self.qq))
        self.log << f"使用了卡牌{card.name}。"
        await card.use(self)
        await card.on_discard(self)
        self.log << f"使用完卡牌，当前手牌为{cards_to_str(self.data.hand_card)}。"
    async def discard_cards(self, cards: List[TCard]):
        """弃牌。将cards里的卡牌移出手牌。弃光手牌时请复制hand_card作为cards传入。"""
        self.log << f"弃牌{cards_to_str(cards)}。"
        for c in cards:
            self.data.hand_card.remove(c)
        self.data.set_cards()
        for card in cards:
            await card.on_discard(self)
        self.log << f"弃完卡牌，当前手牌为{cards_to_str(self.data.hand_card)}。"
    async def exchange(self, target: 'User'):
        """交换两人手牌。"""
        target_hand_cards = copy(target.data.hand_card)
        self_hand_cards = copy(self.data.hand_card)
        config.logger.dragon << f"【LOG】交换用户{self.qq}与用户{target.qq}的手牌。{self.qq}手牌为{cards_to_str(self_hand_cards)}，{target.qq}手牌为{cards_to_str(target_hand_cards)}。"
        self.data.hand_card.clear()
        target.data.hand_card.clear()
        for card in self_hand_cards:
            await card.on_give(self)
        for card in target_hand_cards:
            await card.on_give(self)
        self.data.hand_card.extend(target_hand_cards)
        target.data.hand_card.extend(self_hand_cards)
        self.data.set_cards()
        target_limit = target.card_limit
        if len(self_hand_cards) > target_limit:
            self.buf.send(f"该玩家手牌已超出上限{len(self_hand_cards) - target_limit}张！多余的牌已被弃置。")
            target.log << f"手牌为{cards_to_str(self_hand_cards)}，超出上限{target_limit}，自动弃置。"
            await target.discard_cards(copy(self_hand_cards[target_limit:]))
        target.set_cards()
        config.logger.dragon << f"【LOG】交换完用户{self.qq}与用户{target.qq}的手牌，当前用户{self.qq}的手牌为{cards_to_str(self.data.hand_card)}。"
    async def settlement(self, to_do: Coroutine):
        """结算卡牌相关。请不要递归调用此函数。"""
        self.log << "开始结算。"
        await to_do
        # discard
        x = len(self.data.hand_card) - self.data.card_limit
        while x > 0:
            save_data()
            if self.buf.active != self.qq:
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
        self.data.set_cards()
        await self.buf.flush()
        save_data()
    async def event_move(self, n):
        current: Grid = self.data.event_stage
        begin = current.stage
        while n != 0:
            for i in range(abs(n)):
                if n > 0:
                    childs = current.childs
                    if len(childs) == 1:
                        current = childs[0]
                    else:
                        await self.buf.flush()
                        config.logger.dragon << f"【LOG】询问用户{self.qq}接下来的路线。"
                        s = await self.buf.session.aget(prompt="请选择你接下来的路线【附图】", force_update=True, arg_filters=[
                            extractors.extract_text,
                            lambda s: list(map(int, re.findall(r'\-?\d+', str(s)))),
                            validators.fit_size(1, 1, message="请输入数字。"),
                            lambda l: l[0],
                            validators.ensure_true(lambda s: 0 <= s < len(childs), message="数字输入错误！"),
                        ])
                        current = childs[s]
                else:
                    p = current.parent
                    current = p or current
            self.log << f"行走至格子{current}。"
            self.data.event_stage = current
            n = await current.do(self)
        end = current.stage
        if begin // 50 < (e := end // 50) and e <= 8:
            pt = (10, 20, 10, 50, 10, 20, 10, 50)[e - 1]
            self.send_log(f"经过了{e * 50}层，获得了{pt}pt！")
            await self.add_event_pt(pt)
        t = (current.data_saved, self.qq)
        u = self
        while 1:
            l = config.userdata.execute("select qq from dragon_data where event_stage=? and qq<>?", t).fetchone()
            if l is None:
                break
            u.send_log(f"将玩家{l['qq']}踢回了一格！")
            u = User(l['qq'], self.buf)
            current = current.parent
            u.data.event_stage = current
            t = (current.data_saved, u.qq)

me = UserData(config.selfqq)

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

@lru_cache(10)
def Card(id):
    if id in _card.card_id_dict:
        return _card.card_id_dict[id]
    else:
        raise ValueError("哈")

class card_meta(type):
    def __new__(cls, clsname, bases, attrs):
        if len(bases) != 0 and 'status_dict' in bases[0].__dict__:
            if 'status' in attrs and attrs['status']:
                status = attrs['status']
                bases[0].add_status(status, attrs['status_des'])
                @classmethod
                async def use(self, user: User):
                    user.data.add_status(status)
                attrs['use'] = use
            elif 'daily_status' in attrs and attrs['daily_status']:
                status = attrs['daily_status']
                bases[0].add_daily_status(status, attrs['status_des'])
                @classmethod
                async def use(self, user: User):
                    user.data.add_daily_status(status)
                attrs['use'] = use
            elif 'limited_status' in attrs and attrs['limited_status']:
                status = attrs['limited_status']
                bases[0].add_limited_status(status, attrs['status_des'])
                @classmethod
                async def use(self, user: User):
                    user.data.add_limited_status(status, datetime.now() + attrs['limited_time'])
                attrs['use'] = use
            elif 'global_status' in attrs and attrs['global_status']:
                status = attrs['global_status']
                bases[0].add_status(status, attrs['status_des'])
                @classmethod
                async def use(self, user: User):
                    me.add_status(status)
                attrs['use'] = use
            elif 'global_daily_status' in attrs and attrs['global_daily_status']:
                status = attrs['global_daily_status']
                bases[0].add_daily_status(status, attrs['status_des'])
                @classmethod
                async def use(self, user: User):
                    me.add_daily_status(status)
                attrs['use'] = use
            elif 'global_limited_status' in attrs and attrs['global_limited_status']:
                status = attrs['global_limited_status']
                bases[0].add_limited_status(status, attrs['status_des'])
                @classmethod
                async def use(self, user: User):
                    me.add_limited_status(status, datetime.now() + attrs['global_limited_time'])
                attrs['use'] = use
            elif 'hold_status' in attrs and attrs['hold_status']:
                status = attrs['hold_status']
                bases[0].add_status(status, attrs['status_des'])
                bases[0].is_hold += attrs['status_des']
                @classmethod
                async def on_draw(cls, user: User):
                    user.data.add_status(status)
                @classmethod
                async def on_discard(cls, user: User):
                    user.data.remove_status(status, remove_all=False)
                @classmethod
                async def on_give(cls, user: User, target: User):
                    user.data.remove_status(status)
                    target.data.add_status(status)
                attrs['on_draw'] = on_draw
                attrs['on_discard'] = on_discard
                attrs['on_give'] = on_give
            c = type.__new__(cls, clsname, bases, attrs)
            bases[0].card_id_dict[attrs['id']] = c
        else:
            c = type.__new__(cls, clsname, bases, attrs)
        return c
    @property
    # @abstractmethod
    def img(self):
        pass

class _card(metaclass=card_meta):
    card_id_dict: Dict[int, TCard] = {}
    status_dict: Dict[str, str] = {'d': "永久死亡。"}
    daily_status_dict: Dict[str, str] = {}
    limited_status_dict: Dict[str, str] = {'d': "死亡：不可接龙。"}
    is_hold = ''
    debuffs = 'd'
    daily_debuffs = 'd'
    name = ""
    id = -127
    weight = 1
    positive = 0
    description = ""
    arg_num = 0
    consumed_on_draw = False
    @classmethod
    async def use(cls, user: User) -> None:
        pass
    @classmethod
    async def on_draw(cls, user: User) -> None:
        pass
    @classmethod
    async def on_discard(cls, user: User) -> None:
        pass
    @classmethod
    async def on_give(cls, user: User, target: User) -> None:
        pass
    @classmethod
    def add_daily_status(cls, s, des):
        if s in cls.daily_status_dict:
            raise ImportError
        cls.daily_status_dict[s] = des
    @classmethod
    def add_status(cls, s, des):
        if s in cls.status_dict:
            raise ImportError
        cls.status_dict[s] = des
    @classmethod
    def add_limited_status(cls, s, des):
        if s in cls.limited_status_dict:
            raise ImportError
        cls.limited_status_dict[s] = des
    @classmethod
    def full_description(cls, qq):
        return f"{cls.id}. {cls.name}\n\t{cls.description}"

class jiandiezhixing(_card):
    name = "邪恶的间谍行动～执行"
    id = -1
    positive = -1
    description = "此牌不可被使用，通常情况下无法被抽到。当你弃置此牌时立即死亡。"
    @classmethod
    async def on_discard(cls, user: User):
        await user.kill()

class magician(_card):
    name = "I - 魔术师"
    id = 1
    positive = 1
    description = "选择一张你的手牌（不可选择暴食的蜈蚣），执行3次该手牌的效果，并弃置该手牌。"
    @classmethod
    async def use(cls, user: User):
        await user.buf.flush()
        config.logger.dragon << f"【LOG】询问用户{user.qq}选择牌执行I - 魔术师。"
        l = await user.buf.aget(prompt="请选择你手牌中的一张牌（不可选择暴食的蜈蚣），输入id号。\n" + "\n".join(c.full_description(user.qq) for c in user.data.hand_card),
            arg_filters=[
                    extractors.extract_text,
                    lambda s: list(map(int, re.findall(r'\-?\d+', str(s)))),
                    validators.fit_size(1, 1, message="请输入正确的张数。"),
                    validators.ensure_true(lambda l: l[0] in _card.card_id_dict and Card(l[0]) in user.data.hand_card, message="您选择了错误的卡牌！"),
                    validators.ensure_true(lambda l: -1 not in l, message="此牌不可使用！"),
                    validators.ensure_true(lambda l: 56 not in l, message="此牌不可选择！")
                ])
        card = Card(l[0])
        config.logger.dragon << f"【LOG】用户{user.qq}选择了卡牌{card.name}。"
        user.send_char('使用了三次卡牌：\n' + card.full_description(user.qq))
        await user.discard_cards([card])
        await card.use(user)
        await card.use(user)
        await card.use(user)

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
            user.buf.send(f"当前周期内接龙次数最多的玩家有{''.join(f'[CQ:at,qq={q}]' for q in l)}！")
        for q in ql:
            await User(q, user.buf).kill()

class lovers(_card):
    name = "VI - 恋人"
    id = 6
    positive = 1
    description = "复活1名指定玩家。"
    @classmethod
    async def use(cls, user: User):
        await user.buf.flush()
        l = await user.buf.aget(prompt="请at一名玩家复活。\n",
            arg_filters=[
                    lambda s: re.findall(r'qq=(\d+)', str(s)),
                    validators.fit_size(1, 1, message="请at正确的人数。"),
                ])
        u = User(l[0], user.buf)
        n = u.data.check_limited_status('d')
        u.data.remove_limited_status('d')
        user.buf.send("已复活！" + ("（虽然目标并没有死亡）" if n else ''))

class strength(_card):
    name = "VIII - 力量"
    id = 8
    positive = 0
    description = "加倍你身上所有的非持有性buff。"
    @classmethod
    async def use(cls, user: User):
        status = user.data.status
        status_time = user.data.status_time
        user.data.add_status(''.join(s for s in status if s not in _card.is_hold))
        user.data.add_daily_status(user.data.daily_status)
        for k, val in status_time.items():
            if user.data.check_limited_status(k):
                user.data.add_limited_status(k, datetime.now() + (datetime.fromisoformat(val) - datetime.now()) * 2)

class hermit(_card):
    name = "IX - 隐者"
    id = 9
    positive = 1
    daily_status = 'Y'
    status_des = "IX - 隐者：今天你不会因为接到重复词或触雷而死亡。"
    description = "今天你不会因为接到重复词或触雷而死亡。"

class wheel_of_fortune(_card):
    name = "X - 命运之轮"
    id = 10
    positive = 0
    global_daily_status = 'O'
    status_des = "X - 命运之轮：直至下次刷新前，在商店增加抽奖机，可以消耗5击毙抽奖。"
    description = "直至下次刷新前，在商店增加抽奖机，可以消耗5击毙抽奖。"

class justice(_card):
    name = "XI - 正义"
    id = 11
    positive = 1
    description = "现在你身上每有一个buff，奖励你5击毙。"
    @classmethod
    async def use(cls, user: User):
        n = len(user.data.status) + len(user.data.daily_status)
        for k in user.data.status_time:
            if user.data.check_limited_status(k):
                n += 1
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
        user.data.add_status('r')
_card.add_status('r', "免死：免疫你下一次死亡。")

class death(_card):
    name = "XIII - 死神"
    id = 13
    description = "今天的所有死亡时间加倍。"
    global_daily_status = 'D'
    status_des = "XIII - 死神：今天的所有死亡时间加倍。"

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
        await u.kill()

class star(_card):
    name = "XVII - 星星"
    id = 17
    positive = 0
    description = "今天的每个词有10%的几率进入奖励词池。"
    global_daily_status = 't'
    status_des = "XVII - 星星：今天的每个词有10%的几率进入奖励词池。"

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
    consumed_on_draw = True
    @classmethod
    async def on_draw(cls, user: User):
        user.data.add_daily_status('d')
        user.send_char("病了！直到下一次主题出现前不得接龙。")
_card.add_daily_status('d', "生病：直到下一次主题出现前不可接龙。")

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
        await user.buf.flush()
        config.logger.dragon << f"【LOG】询问用户{user.qq}铁索连环。"
        l: List[int] = await user.buf.aget(prompt="请at群内至多两名玩家进行铁索连环。\n",
            arg_filters=[
                    lambda s: [int(r) for r in re.findall(r'qq=(\d+)', str(s))],
                    validators.fit_size(1, 2, message="请at正确的人数。"),
                ])
        config.logger.dragon << f"【LOG】用户{user.qq}铁索连环选择{l}。"
        global global_state
        for target in l:
            if target in global_state['lianhuan']:
                global_state['lianhuan'].remove(target)
            else:
                global_state['lianhuan'].append(target)
        save_global_state()
        user.buf.send('成功切换玩家的连环状态！')

class minus1ma(_card):
    name = "-1马"
    id = 39
    daily_status = 'm'
    status_des = "-1马：直到下次主题刷新为止，你隔一次就可以接龙。"
    positive = 1
    description = "直到下次主题刷新为止，你隔一次就可以接龙。"

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
        await user.buf.flush()
        config.logger.dragon << f"【LOG】询问用户{user.qq}复制牌。"
        l: List[int] = await user.buf.aget(prompt="请选择你手牌中的一张牌复制，输入id号。\n" + "\n".join(c.full_description(user.qq) for c in user.data.hand_card),
            arg_filters=[
                    extractors.extract_text,
                    lambda s: list(map(int, re.findall(r'\-?\d+', str(s)))),
                    validators.fit_size(1, 1, message="请输入正确的张数。"),
                    validators.ensure_true(lambda l: l[0] in _card.card_id_dict and Card(l[0]) in user.data.hand_card, message="您选择了错误的卡牌！"),
                    validators.ensure_true(lambda l: -1 not in l, message="此牌不可使用！")
                ])
        card = Card(l[0])
        config.logger.dragon << f"【LOG】用户{user.qq}选择了卡牌{card.name}。"
        user.send_char('使用了卡牌：\n' + card.full_description(user.qq))
        await card.use(user)

class hongzhong(_card):
    name = "红中（🀄）"
    id = 46
    positive = 1
    description = "在同时有人驳回和同意时，可以使用此卡强制通过。"

class sihuihuibizhiyao(_card):
    name = "死秽回避之药"
    id = 50
    status = 's'
    status_des = '死秽回避之药：下次死亡时自动消耗5击毙免除死亡。'
    positive = 1
    description = "你下次死亡时自动消耗5击毙免除死亡。"

class huiye(_card):
    name = "辉夜姬的秘密宝箱"
    id = 52
    status = 'x'
    status_des = '辉夜姬的秘密宝箱：下一次死亡的时候奖励抽一张卡。'
    positive = 1
    description = "你下一次死亡的时候奖励你抽一张卡。"

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
        config.logger.dragon << f"【LOG】用户{user.qq}幸运兔脚抽取了卡牌{c.name}。"
        user.send_char('抽到并使用了卡牌：\n' + c.full_description(user.qq))
        await c.on_draw(user)
        await c.use(user)
        await c.on_discard(user)

class baoshidewugong(_card):
    name = "暴食的蜈蚣"
    id = 56
    positive = 1
    description = "你的手牌上限永久+1。"
    @classmethod
    async def use(cls, user: User):
        user.data.card_limit += 1
        config.logger.dragon << f"【LOG】用户{user.qq}增加了手牌上限至{user.data.card_limit}。"

class plus2(_card):
    name = "+2"
    id = 60
    global_status = '+'
    status_des = '+2：下一个接龙的人抽一张非负面卡和一张非正面卡。'
    positive = 0
    description = "下一个接龙的人抽一张非负面卡和一张非正面卡。"

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
    global_daily_status = 'o'
    status_des = "衔尾蛇之石：规则为首尾接龙直至下次刷新。首尾接龙时，每个汉语词必须至少包含3个汉字，英语词必须至少包含4个字母。"
    positive = 0
    description = "修改当前规则至首尾接龙直至下次刷新。首尾接龙时，每个汉语词必须至少包含3个汉字，英语词必须至少包含4个字母。"

class queststone(_card):
    name = "任务之石"
    id = 67
    positive = 1
    description = "持有此石时，你每天会刷新一个接龙任务。每次完成接龙任务可以获得3击毙，每天最多3次。使用将丢弃此石。"
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
    async def on_discard(cls, user: User):
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

class cunqianguan(_card):
    name = "存钱罐"
    id = 70
    global_status = 'm'
    status_des = '存钱罐：下次触发隐藏词的奖励+10击毙。'
    positive = 0
    description = "下次触发隐藏词的奖励+10击毙。"

class hongsezhihuan(_card):
    name = "虹色之环"
    id = 71
    status = 'h'
    status_des = '虹色之环：下次死亡时，有1/2几率闪避，1/2几率死亡时间+1小时。'
    positive = 0
    description = "下次你死亡时，有1/2几率闪避，1/2几率死亡时间+1小时。"

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
        def _():
            for u in l:
                if not u.data.check_status('G'):
                    for c in u.data.hand_card:
                        yield (u, c)
        all_cards = list(_())
        random.shuffle(all_cards)
        for u in l:
            if u.data.check_status('G'):
                u.data.remove_status("G")
                continue
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
    hold_status = 'y'
    status_des = '幸运护符：无法使用其他卡牌。每进行两次接龙额外获得一个击毙（每天上限为5击毙）。'
    positive = 1
    description = "持有此卡时，你无法使用其他卡牌。你每进行两次接龙额外获得一个击毙（每天上限为5击毙）。使用将丢弃这张卡。"

class jisuzhuangzhi(_card):
    name = "极速装置"
    id = 74
    status = 'z'
    status_des = '极速装置：下次可以连续接龙两次。'
    positive = 1
    description = '下次你可以连续接龙两次。'

class huxiangjiaohuan(_card):
    name = '互相交换'
    id = 75
    positive = 0
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
        user.send_char('抽到并使用了卡牌：\n' + c.full_description(user.qq))
        user.log << f"众神的嬉戏抽取了卡牌{c.name}。"
        await c.on_draw(user)
        await c.use(user)
        await c.on_discard(user)

class lveduozhebopu(_card):
    name = "掠夺者啵噗"
    id = 77
    positive = 1
    description = "每天你可从你所接龙的人处偷取1击毙，每人限一次，最多10击毙，若目标没有击毙则不可偷取。死亡时或使用将丢弃这张卡。"
    @classmethod
    async def on_draw(cls, user: User):
        user.data.add_status('p')
        if str(user.qq) not in global_state['steal']:
            global_state['steal'][str(user.qq)] = {'time': 0, 'user': []}
        save_global_state()
    @classmethod
    async def on_discard(cls, user: User):
        user.data.remove_status('p', remove_all=False)
        if not user.data.check_status('p'):
            del global_state['steal'][str(user.qq)]
        save_global_state()
    @classmethod
    async def on_give(cls, user: User, target: User):
        user.data.remove_status('p')
        target.data.add_status('p')
        global_state['steal'][str(target.qq)] = global_state['steal'][str(user.qq)]
        if not user.data.check_status('p'):
            del global_state['steal'][str(user.qq)]
        save_global_state()
_card.add_status('p', '掠夺者啵噗：每天可从所接龙的人处偷取1击毙，每人限一次，最多10击毙，若目标没有击毙则不可偷取。')

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
    status_des = 'Comic Sans：七海千春今天所有生成的图片均使用Comic Sans作为西文字体（中文使用华文彩云）。'
    positive = 0
    description = "七海千春今天所有生成的图片均使用Comic Sans作为西文字体（中文使用华文彩云）。"

class PC(_card):
    name = "PC"
    id = 81
    positive = 1
    description = '所有人立刻获得胜利。'
    @classmethod
    async def use(cls, user: User):
        user.buf.send("所有人都赢了！恭喜你们！")

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
    status_des = '变压器（♣10）：下一次击毙变动变动值加倍。'
    positive = 0
    description = "下一次你的击毙变动变动值加倍。"

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

class McGuffium239(_card):
    name = "Mc Guffium 239"
    id = 102
    positive = 1
    status = 'G'
    status_des = 'Mc Guffium 239：下一次礼物交换不对你生效。'
    description = "下一次礼物交换不对你生效。"

class dihuopenfa(_card):
    name = "地火喷发"
    id = 114
    description = "今天之内所有的接龙词都有10%的几率变成地雷。"
    global_daily_status = 'B'
    status_des = "地火喷发：今天之内所有的接龙词都有10%的几率变成地雷。"

class gaojie(_card):
    name = "告解"
    id = 116
    description = "今日每次你获得击毙时额外获得1击毙。"
    daily_status = "@"
    status_des = "告解：今日每次你获得击毙时额外获得1击毙。"

class shenmouyuanlv(_card):
    name = "深谋远虑之策"
    id = 117
    description = "当你一次使用/损失了超过你现有击毙一半以上的击毙时，恢复这些击毙。"
    status = 'n'
    status_des = "深谋远虑之策：当你一次使用/损失了超过你现有击毙一半以上的击毙时，恢复这些击毙。"

class steamsummer(_card):
    name = "Steam夏季特卖"
    id = 151
    positive = 1
    status = 'S'
    status_des = "Steam夏季特卖：你下一次购物花费减少50%。"
    description = "你下一次购物花费减少50%。"

class forkbomb(_card):
    name = "Fork Bomb"
    id = 152
    positive = 0
    global_daily_status = 'b'
    status_des = "Fork Bomb：今天每个接龙词都有5%几率变成分叉点。"
    description = "今天每个接龙词都有5%几率变成分叉点。"

class beijingcard(_card):
    name = "北京市市政交通一卡通"
    id = 153
    positive = 1
    hold_status = '1'
    description = "持有此卡时，你当天在商店总消费达100击毙后商店所有物品变为8折，当天在商店总消费达150击毙后商店所有物品变为5折，当天在商店总消费达400击毙后不再打折。"
    status_des = "北京市市政交通一卡通：你当天在商店总消费达100击毙后商店所有物品变为8折，当天在商店总消费达150击毙后商店所有物品变为5折，当天在商店总消费达400击毙后不再打折。"

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
add_mission("前两个字的声母相同。")(lambda s: len(p := pinyin(s[0:2], style=Style.INITIALS, strict=True, errors='ignore', heteronym=True)) >= 2 and len(set(p[0]) & set(p[1])) != 0)
add_mission("前两个字的韵母相同。")(lambda s: len(p := pinyin(s[0:2], style=Style.FINALS, strict=True, errors='ignore', heteronym=True)) >= 2 and len(set(p[0]) & set(p[1])) != 0)
add_mission("首字没有声母。")(lambda s: len(p := pinyin(s[0:1], style=Style.INITIALS, strict=True, errors='ignore', heteronym=True)) >= 1 and '' in p[0])
add_mission("首字是多音字。")(lambda s: len(p := pinyin(s[0:1], style=Style.INITIALS, strict=True, errors='ignore', heteronym=True)) >= 1 and len(p[0]) > 1)
add_mission("所有字音调相同且至少包含两个字。")(lambda s: len(p := pinyin(s, style=Style.FINALS_TONE3, neutral_tone_with_five=True, strict=True, errors='ignore', heteronym=True)) > 1 and len(reduce(lambda x, y: x & y, (set(c[-1] for c in s) for s in p))) != 0)
add_mission("首字与尾字相同且至少包含两个字。。")(lambda s: len(s) >= 2 and s[0] == s[-1])

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

class _equipment(metaclass=equipment_meta):
    id_dict: Dict[int, TEquipment] = {}
    id = -127
    name = ''
    des_shop = ''
    @classmethod
    def description(cls, count: int):
        pass

class bikini(_equipment):
    id = 0
    name = '比基尼'
    des_shop = '你每次获得击毙时都有一定几率加倍。一星为5%，二星为10%，三星为15%。'
    @classmethod
    def description(cls, count: int):
        return f'你每次获得击毙时都有{5 * count}%几率加倍。'

class schoolsui(_equipment):
    id = 1
    name = '学校泳装'
    des_shop = '你每次击毙减少或商店购买都有一定几率免单。一星为4.76%，二星为9.09%，三星为13.04%。'
    @classmethod
    def description(cls, count: int):
        return f'你每次击毙减少或商店购买都有{count / (20 + count) * 100:.2f}%几率免单。'

# 爬塔格子
class Grid:
    __slots__ = ('stage', 'route', 'hashed')
    pool: Dict[Tuple[int, int], 'Grid'] = {}
    def __new__(cls, stage: int, route: int) -> Any:
        if i := cls.pool.get((stage, route)):
            return i
        return object.__new__(cls, stage, route)
    def __init__(self, stage: int, route: int):
        self.stage = stage
        self.route = route
        h = f"{stage} {route}".encode('utf-8')
        b = hashlib.sha1(h).digest()
        self.hashed = int.from_bytes(b[0:3], 'big')
    def __hash__(self):
        return hash((self.stage, self.route))
    def __str__(self):
        return f"{self.stage}层{self.route}列"
    @property
    def data_saved(self):
        return self.stage + self.route * 2048
    @property
    def description(self):
        i = self.hashed
        s = f"增加{2 + i % 4}pt，"
        i //= 4
        content = i % 100
        if content < 10:
            s += f"被击毙{content // 2 * 5}分钟。"
        elif content < 60:
            s += f"获得{(content - 10) // 10 * 2 + 2}击毙。"
        elif content < 75:
            s += f"获得活动pt后，再扔一次骰子{'前进' if content < 70 else '后退'}。"
        elif content < 85:
            s += "抽一张卡并立即发动效果。"
        else: # ？
            pass
        return s
    @property
    def parent(self):
        if self.route != 0 and (p := global_state["event_route"][self.route - 1]) + 1 == self.stage:
            return Grid(p % 2048, p // 2048)
        elif self.stage >= 1:
            return Grid(self.stage - 1, self.route)
        else:
            return None
    @property
    def childs(self):
        route = [self.route]
        if self.data_saved in global_state["event_route"]:
            route += [i for i, d in enumerate(global_state["event_route"]) if d == self.data_saved]
        return [Grid(self.stage + 1, r) for r in route]
    def fork(self):
        global_state["event_route"].append(self.data_saved)
    async def do(self, user: User):
        i = self.hashed
        await user.add_event_pt(2 + i % 4)
        i //= 4
        content = i % 100
        if content < 10: # 被击毙5/10/15/20/25分钟
            user.send_log(f"走到了：被击毙{content // 2 * 5}分钟。")
            await user.kill(minute=content // 2 * 5 + 5)
        elif content < 60: # 获得2/4/6/8/10击毙
            user.send_log(f"走到了：获得{(content - 10) // 10 * 2 + 2}击毙。")
            await user.add_jibi((content - 10) // 10 * 2 + 2)
        elif content < 75: # 获得活动pt后，再扔一次骰子前进（10）/后退（5）
            n = random.randint(1, 6)
            user.send_log(f"走到了：获得活动pt后，再扔一次骰子{'前进' if content < 70 else '后退'}。{user.char}扔到了{n}。")
            return n if content < 70 else -n
        elif content < 85: # 抽一张卡并立即发动效果
            user.send_log("走到了：抽一张卡并立即发动效果。")
            c = draw_card()
            user.send_char('抽到并使用了卡牌：\n' + c.full_description(user.qq))
            user.log << f"抽取了卡牌{c.name}。"
            await c.on_draw(user)
            await c.use(user)
            await c.on_discard(user)
        else: # ？
            pass
        return 0
