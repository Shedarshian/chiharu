from collections import Counter
from copy import copy
from datetime import datetime, timedelta, date, time
import itertools, more_itertools
import json
import random
import re
from PIL import Image, ImageDraw
from functools import lru_cache, partial, reduce
from nonebot import CommandSession, NLPSession, on_natural_language, get_bot, permission, scheduler
from nonebot.command import call_command
from nonebot.command.argfilter import extractors, validators
from ..inject import CommandGroup, on_command
from .. import config
from ..config import SessionBuffer
from .logic_dragon_file import mission, get_mission
env = config.Environment('logic_dragon')
env_supervise = config.Environment('logic_dragon_supervise')
env_admin = config.Environment(config.Admin('logic_dragon'))
config.logger.open('dragon')

CommandGroup('dragon', short_des="逻辑接龙相关。", environment=env|env_supervise)

# TODO 十连保底
message_re = re.compile(r"\s*(\d+)([a-z])?\s*接[\s，,]*(.*)[\s，,\n]*.*")

# Version information and changelog
version = "0.2.6"
changelog = """0.2.6 Changelog:
Change:
接龙现在会以树状形式储存。
接龙时需显式提供你所接的词汇的id。id相撞时则会判定为接龙失败。
Add:
-dragon.version [-c]：查询逻辑接龙版本与Changelog。
-dragon.fork id（也可使用：分叉 id）：可以指定分叉。
-dragon.check 活动词：查询当前可接的活动词与id。
-dragon.check 状态：查询自己的状态。
-dragon.check 资料：查询自己的资料。
-dragon.delete id（也可使用：驳回 id）：可以驳回节点。
BugFix:
修正了“接太快了”只和时序有关导致在有分叉的情况下不会正常运作的bug。"""

# keyword : [str, list(str)]
# hidden : [list(str), list(str)]
# begin : list(str)
# bombs : list(str)
# last_update_date : str
with open(config.rel('dragon_words.json'), encoding='utf-8') as f:
    d = json.load(f)
    keyword = d["keyword"][0]
    hidden_keyword = d["hidden"][0]
    bombs = d["bombs"]
    last_update_date = d["last_update_date"]
    del d

class Tree:
    __slots__ = ('id', 'parent', 'childs', 'word', 'fork', 'kwd', 'hdkwd', 'qq')
    forests = []
    _objs = [] # [[wd0, wd1, wd2], [wd2a], [wd2b]]
    max_branches = 0
    def __init__(self, parent, word, qq, kwd, hdkwd, *, id=None, fork=False):
        self.parent = parent
        if parent:
            parent.childs.append(self)
            id = id or (parent.id[0] + 1, parent.id[1])
        else:
            id = id or (0, 0)
        if not self.find(id):
            self.id = id
            if Tree.max_branches <= id[1]:
                for i in range(id[1] + 1 - Tree.max_branches):
                    self._objs.append([])
                Tree.max_branches = id[1] + 1
        else:
            self.id = (id[0], Tree.max_branches)
            Tree.max_branches += 1
            self._objs.append([])
        self._objs[self.id[1]].append(self)
        self.childs = []
        self.word = word
        self.fork = fork
        self.qq = qq
        self.kwd = kwd
        self.hdkwd = hdkwd
    @classmethod
    def find(cls, id):
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
    def init(cls, is_daily):
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
    @classmethod
    def graph(self):
        pass

# log
log_set : set = set()
log_file = None
def load_log(init):
    global log_set, log_file
    log_set = set()
    if log_file is not None:
        log_file.close()
    d = date.today()
    if datetime.now().time() < time(15, 59):
        d -= timedelta(days=1)
    today = rf'log\dragon_log_{d.isoformat()}.txt'
    def _(s):
        if match := re.match(r'(\d+[a-z]?(?:\+?<-?\d+[a-z]?)?(?:/\d+/[^/]*/[^/]*/)?) (.*)', s):
            return match.group(2)
        return s
    for i in range(7):
        try:
            with open(config.rel(rf'log\dragon_log_{d.isoformat()}.txt'), encoding='utf-8') as f:
                log_set.update(_(s.strip()) for s in f.readlines())
        except FileNotFoundError:
            pass
        d -= timedelta(days=1)
    if init:
        try:
            with open(config.rel(today), encoding='utf-8') as f:
                for line in f.readlines():
                    if match := re.match(r'(\d+)([a-z])?(?:(\+)?<(-?\d+[a-z]?))?(?:/(\d+)/([^/]*)/([^/]*)/)? (.*)', line.strip("\r\n")):
                        if match.group(1) == '0' and len(Tree._objs) != 0:
                            Tree.forests.append(Tree._objs)
                            Tree.init(is_daily=False)
                        id = Tree.match_to_id(match)
                        if match.group(4) is None: # backward compatability
                            parent = Tree.find((id[0] - 1, id[1]))
                        else:
                            parent = None if match.group(4) == '-1' else Tree.find(Tree.str_to_id(match.group(4)))
                        node = Tree(parent, match.group(8),
                                0 if match.group(5) is None else int(match.group(5)),
                                kwd=match.group(6), hdkwd=match.group(7), id=id,
                                fork=match.group(3) is not None)
        except FileNotFoundError:
            pass
    log_file = open(config.rel(today), 'a', encoding='utf-8')
load_log(True)
def check_and_add_log_and_contruct_tree(parent, word, qq, kwd, hdkwd, fork):
    global log_set
    if word in log_set:
        return None
    s = Tree(parent, word, qq, kwd, hdkwd, fork=fork)
    log_set.add(s.word)
    log_file.write(f'{s}\n')
    log_file.flush()
    return s

# global_state
# exchange_stack : list(int)
# lianhuan : list(int)
# quest : map(int, list(map('id': int, 'remain': int)))
# steal : map(int, map('user': list(int), 'time': int))
with open(config.rel('dragon_state.json'), encoding='utf-8') as f:
    global_state = json.load(f)
def save_global_state():
    with open(config.rel('dragon_state.json'), 'w', encoding='utf-8') as f:
        f.write(json.dumps(global_state, indent=4, separators=(',', ': '), ensure_ascii=False))
quest_print_aux = {qq: 0 for qq in global_state['quest'].keys()}

# dragon_data := qq : int, jibi : int, card : str, draw_time : int, death_time : str, today_jibi : int, today_keyword_jibi : int
# status : str, daily_status : str, status_time : str, card_limit : int, shop_drawn_card: int, event_pt: int
# global_status : qq = 2711644761
def find_or_new(qq):
    t = config.userdata.execute("select * from dragon_data where qq=?", (qq,)).fetchone()
    if t is None:
        config.userdata.execute('insert into dragon_data (qq, jibi, draw_time, today_jibi, today_keyword_jibi, death_time, card, status, daily_status, status_time, card_limit, shop_drawn_card, event_pt) values (?, 0, 0, 10, 10, ?, ?, ?, ?, ?, 4, 0, 0)', (qq, '', '', '', '', '{}'))
        t = config.userdata.execute("select * from dragon_data where qq=?", (qq,)).fetchone()
    return t
def get_jibi(qq):
    return find_or_new(qq)['jibi']
async def add_jibi(session, qq, jibi, current_jibi=None, is_buy=False):
    if current_jibi is None:
        current_jibi = get_jibi(qq)
    if n := check_status(qq, '2', False):
        jibi *= 2 ** n
        session.send(session.char(qq) + f"触发了{f'{n}次' if n > 1 else ''}变压器的效果，{'获得' if jibi >= 0 else '损失'}击毙加倍为{abs(jibi)}！")
        remove_status(qq, '2', False, remove_all=True)
    if (m := check_status(qq, 'S', False)) and is_buy:
        jibi //= 2 ** m
        session.send(session.char(qq) + f"触发了{f'{m}次' if m > 1 else ''}Steam夏季特卖的效果，花费击毙减半为{abs(jibi)}！")
        remove_status(qq, 'S', False, remove_all=True)
    config.userdata.execute("update dragon_data set jibi=? where qq=?", (max(0, current_jibi + jibi), qq))
    config.logger.dragon << f"【LOG】玩家{qq}原有击毙{current_jibi}，{f'触发了{n}次变压器的效果，' if n > 0 else ''}{f'触发了{m}次Steam夏季特卖的效果，' if m > 0 else ''}{'获得' if jibi >= 0 else '损失'}了{abs(jibi)}。"
def wrapper_file(_func):
    def func(*args, **kwargs):
        with open(config.rel('dragon_words.json'), encoding='utf-8') as f:
            d = json.load(f)
        ret = _func(d, *args, **kwargs)
        with open(config.rel('dragon_words.json'), 'w', encoding='utf-8') as f:
            f.write(json.dumps(d, indent=4, separators=(',', ': '), ensure_ascii=False))
        return ret
    return func
# pylint: disable=no-value-for-parameter
@wrapper_file
def update_keyword(d, if_delete=False):
    global keyword
    if len(d['keyword'][1]) == 0:
        config.logger.dragon << "【LOG】更新关键词失败！"
        return False
    keyword = random.choice(d['keyword'][1])
    d['keyword'][1].remove(keyword)
    if not if_delete:
        d['keyword'][1].append(d['keyword'][0])
    d['keyword'][0] = keyword
    config.logger.dragon << f"【LOG】关键词更新为：{keyword}。"
    return True
@wrapper_file
def update_hidden_keyword(d, which, if_delete=False):
    global hidden_keyword
    if which == -1:
        n = {0, 1, 2}
    elif isinstance(which, int):
        n = {which}
    else:
        n = {hidden_keyword.index(which)}
    if len(d['hidden'][1]) < len(n):
        config.logger.dragon << "【LOG】隐藏关键词更新失败！"
        return False
    for i in n:
        hidden_keyword[i] = random.choice(d['hidden'][1])
        d['hidden'][1].remove(hidden_keyword[i])
        if not if_delete:
            d['hidden'][1].append(d['hidden'][0][i])
        d['hidden'][0][i] = hidden_keyword[i]
    config.logger.dragon << f"【LOG】隐藏关键词更新为：{'，'.join(hidden_keyword)}。"
    return True
@wrapper_file
def remove_bomb(d, word):
    global bombs
    d["bombs"].remove(word)
    bombs.remove(word)
    config.logger.dragon << f"【LOG】移除了炸弹{word}，当前炸弹：{'，'.join(bombs)}。"
@wrapper_file
def remove_all_bomb(d):
    global bombs
    d["bombs"] = []
    bombs = []
    config.logger.dragon << f"【LOG】移除了所有炸弹。"
@wrapper_file
def add_bomb(d, word):
    global bombs
    d["bombs"].append(word)
    bombs.append(word)
    config.logger.dragon << f"【LOG】增加了炸弹{word}，当前炸弹：{'，'.join(bombs)}。"
@wrapper_file
def add_begin(d, word):
    d['begin'].append(word)
    config.logger.dragon << f"【LOG】增加了起始词{word}。"
@wrapper_file
def add_keyword(d, word):
    d['keyword'][1].append(word)
    config.logger.dragon << f"【LOG】增加了起始词{word}。"
@wrapper_file
def add_hidden(d, word):
    d['hidden'][1].append(word)
    config.logger.dragon << f"【LOG】增加了隐藏关键词{word}。"

def cancellation(session):
    def control(value):
        if value == "取消":
            config.logger.dragon << f"【LOG】用户{session.ctx['user_id']}取消。"
            session.finish("已取消。")
        return value
    return control

def save_data():
    config.userdata_db.commit()

def add_status(qq, s, is_daily):
    status = find_or_new(qq)['daily_status' if is_daily else 'status']
    status += s
    config.userdata.execute('update dragon_data set %s=? where qq=?' % ('daily_status' if is_daily else 'status'), (status, qq))
    config.logger.dragon << f"【LOG】用户{qq}增加了{'每日' if is_daily else '永久'}状态{s}。"
def add_limited_status(qq, s, end_time : datetime):
    status = eval(find_or_new(qq)['status_time'])
    if s not in status:
        status[s] = end_time.isoformat()
    else:
        status[s] = max(datetime.fromisoformat(status[s]), end_time).isoformat()
    config.userdata.execute('update dragon_data set status_time=? where qq=?', (str(status), qq))
    config.logger.dragon << f"【LOG】用户{qq}增加了限时状态{s}，结束时间为{end_time}。"
def add_global_status(s, is_daily):
    return add_status(2711644761, s, is_daily)
def add_global_limited_status(s, end_time : datetime):
    return add_limited_status(2711644761, s, end_time)
def check_status(qq, s, is_daily, node=None):
    node = node or find_or_new(qq)
    return node['daily_status' if is_daily else 'status'].count(s)
def check_limited_status(qq, s, node=None):
    node = node or find_or_new(qq)
    status = eval(node['status_time'])
    if s not in status:
        return False
    t = datetime.fromisoformat(status[s])
    if t < datetime.now():
        status.pop(s)
        config.userdata.execute('update dragon_data set status_time=? where qq=?', (str(status), qq))
        return False
    return True
def check_global_status(s, is_daily, node=None):
    return check_status(2711644761, s, is_daily, node)
def check_global_limited_status(s, node=None):
    return check_limited_status(2711644761, s, node)
def remove_status(qq, s, is_daily, remove_all=True, status=None):
    status = status or find_or_new(qq)['daily_status' if is_daily else 'status']
    if remove_all:
        status = ''.join([t for t in status if t != s])
    else:
        l = list(status)
        if s in l:
            l.remove(s)
        status = ''.join(l)
    config.userdata.execute('update dragon_data set %s=? where qq=?' % ('daily_status' if is_daily else 'status'), (status, qq))
    config.logger.dragon << f"【LOG】用户{qq}移除了{'一层' if not remove_all else ''}{'每日' if is_daily else '永久'}状态{s}，当前状态为{status}。"
def remove_limited_status(qq, s, status=None):
    status = status or eval(find_or_new(qq)['status_time'])
    if s in status:
        status.pop(s)
        config.userdata.execute('update dragon_data set status_time=? where qq=?', (str(status), qq))
    config.logger.dragon << f"【LOG】用户{qq}移除了限时状态{s}，当前限时状态为{str(status)}。"
def remove_global_status(s, is_daily, remove_all=True, status=None):
    return remove_status(2711644761, s, is_daily, remove_all, status)
def remove_global_limited_status(s, status=None):
    return remove_limited_status(2711644761, s, status)
def decrease_death_time(qq, time: timedelta, node=None):
    node = node or find_or_new(qq)
    status = eval(node['status_time'])
    if 'd' in status:
        t = datetime.fromisoformat(status['d'])
        t -= time
        status['d'] = t.isoformat()
        if t < datetime.now():
            status.pop('d')
        config.userdata.execute('update dragon_data set status_time=? where qq=?', (str(status), qq))
        return 'd' not in status
    return True
def get_limited_time(qq, s, status=None):
    status = status or eval(find_or_new(qq)['status_time'])
    if s not in status:
        return None
    delta = datetime.fromisoformat(status[s]) - datetime.now()
    if delta < timedelta():
        status.pop(s)
        config.userdata.execute('update dragon_data set status_time=? where qq=?', (str(status), qq))
        return None
    return delta.seconds // 60

async def add_event_pt(session, qq, pt, current_pt=None):
    current_pt = current_pt or find_or_new(qq)['event_pt']
    config.userdata.execute('update dragon_data set event_pt=? where qq=?', (current_pt + pt, qq))
    session.send(session.char(qq) + f"收到了{pt}活动pt！")
    config.logger.dragon << f"【LOG】用户{qq}增加了{pt}活动pt。现有{current_pt + pt}活动pt。"

def cards_to_str(cards):
    return '，'.join(c.name for c in cards)
def draw_card(positive=None):
    x = positive is not None and len(positive & {-1, 0, 1}) != 0
    if check_global_status('j', True):
        if (x and (-1 in positive) or not x) and random.random() < 0.2:
            return -1
    c = random.choice(list(_card.card_id_dict.values()))
    while (x and c.positive not in positive) or c.id < 0:
        c = random.choice(list(_card.card_id_dict.values()))
    return c
def set_cards(qq, hand_card):
    config.userdata.execute("update dragon_data set card=? where qq=?", (','.join(str(c.id) for c in hand_card), qq))
    config.logger.dragon << f"【LOG】设置用户{qq}手牌为{cards_to_str(hand_card)}。"
def get_card(qq, card=None, node=None):
    s = card or (node or find_or_new(qq))['card']
    return [] if s == '' else [Card(int(x)) for x in s.split(',')]
def check_throw_card(qq, card_ids, hand_card=None):
    if hand_card is None:
        hand_card = get_card(qq)
    if len(card_ids) == 1:
        if card_ids[0] not in [c.id for c in hand_card]:
            return False
    else:
        hand_counter = Counter(c.id for c in hand_card)
        hand_counter.subtract(Counter(card_ids))
        if -hand_counter != Counter():
            return False
    return True

# 击杀玩家。
async def kill(session, qq, hand_card, hour=2, minute=0):
    dodge = False
    config.logger.dragon << f"【LOG】尝试击杀玩家{qq}。"
    if (n := check_status(qq, 's', False)) and not dodge:
        jibi = get_jibi(qq)
        if jibi >= 5 * 2 ** check_status(qq, '2', False):
            await add_jibi(session, qq, -5, jibi)
            session.send_log.dragon(qq, "触发了死秽回避之药的效果，免除死亡！")
            dodge = True
            remove_status(qq, 's', False, remove_all=False)
    if (n := check_status(qq, 'h', False)) and not dodge:
        for a in range(n):
            remove_status(qq, 'h', False, remove_all=False)
            if random.randint(0, 1) == 0:
                session.send_log.dragon(qq, "触发了虹色之环，闪避了死亡！")
                dodge = True
                break
            else:
                session.send_log.dragon(qq, "触发虹色之环闪避失败，死亡时间+1h！")
                hour += 1
    if (n := check_status(qq, 'p', False)) and not dodge:
        config.logger.dragon << f"【LOG】用户{qq}的{n}张掠夺者啵噗因死亡被弃置。"
        await discard_cards([Card(77) for i in range(n)], session, qq, hand_card)
    if not dodge:
        add_limited_status(qq, 'd', datetime.now() + timedelta(hours=hour, minutes=minute))
        session.send(session.char(qq) + f"死了！{f'{hour}小时' if hour != 0 else ''}{f'{minute}分钟' if minute != 0 else ''}不得接龙。")
        if (x := check_status(qq, 'x', False)):
            remove_status(qq, 'x', False, remove_all=True)
            session.send_log.dragon(qq, f"触发了辉夜姬的秘密宝箱！奖励抽卡{x}张。")
            await draw(x, session, qq, hand_card)
        global global_state
        if qq in global_state['lianhuan']:
            l = copy(global_state['lianhuan'])
            global_state['lianhuan'] = []
            save_global_state()
            l.remove(qq)
            session.send(f"由于铁索连环的效果，{' '.join(f'[CQ:at,qq={target}]' for target in l)}个人也一起死了！")
            config.logger.dragon << f"【LOG】用户{qq}触发了铁索连环的效果至{l}。"
            for target in l:
                await kill(session, target, get_card(target), hour=hour)

# 抽卡。将卡牌放入手牌。
async def draw(n: int, session: SessionBuffer, qq: int, hand_card, *, positive=None, cards=None):
    cards = [draw_card(positive) for i in range(n)] if cards is None else cards
    if n := cards.count(Card(67)):
        for i in range(n):
            await Card(67).on_draw(session, qq, hand_card)
    session.send(session.char(qq) + '抽到的卡牌是：\n' + '\n'.join(c.full_description(qq) for c in cards))
    config.logger.dragon << f"【LOG】用户{qq}抽到的卡牌为{cards_to_str(cards)}。"
    for c in cards:
        if not c.consumed_on_draw:
            hand_card.append(c)
        if c.id != 67:
            await c.on_draw(session, qq, hand_card)
    config.logger.dragon << f"【LOG】用户{qq}抽完卡牌，当前手牌为{cards_to_str(hand_card)}。"

# 使用卡牌。不处理将卡牌移出手牌的操作。
async def use_card(card, session: SessionBuffer, qq: int, hand_card):
    session.send(session.char(qq) + '使用了卡牌：\n' + card.full_description(qq))
    config.logger.dragon << f"【LOG】用户{qq}使用了卡牌{card.name}。"
    await card.use(session, qq, hand_card)
    await card.on_discard(session, qq, hand_card)
    config.logger.dragon << f"【LOG】用户{qq}使用完卡牌，当前手牌为{cards_to_str(hand_card)}。"

# 弃牌。将cards里的卡牌移出手牌。弃光手牌时请复制hand_card作为cards传入。
async def discard_cards(cards, session: SessionBuffer, qq: int, hand_card):
    config.logger.dragon << f"【LOG】用户{qq}弃牌{cards_to_str(cards)}。"
    for c in cards:
        hand_card.remove(c)
    set_cards(qq, hand_card)
    for card in cards:
        await card.on_discard(session, qq, hand_card)
    config.logger.dragon << f"【LOG】用户{qq}弃完卡牌，当前手牌为{cards_to_str(hand_card)}。"

# 交换两人手牌。
async def exchange(session: SessionBuffer, qq: int, hand_card, *, target: int):
    target_hand_cards = get_card(target)
    self_hand_cards = copy(hand_card)
    config.logger.dragon << f"【LOG】交换用户{qq}与用户{target}的手牌。{qq}手牌为{cards_to_str(self_hand_cards)}，{target}手牌为{cards_to_str(target_hand_cards)}。"
    hand_card.clear()
    for card in self_hand_cards:
        await card.on_give(session, qq, target)
    for card in target_hand_cards:
        await card.on_give(session, target, qq)
    hand_card.extend(target_hand_cards)
    set_cards(qq, hand_card)
    target_limit = find_or_new(target)['card_limit']
    if len(self_hand_cards) > target_limit:
        session.send(f"该玩家手牌已超出上限{len(self_hand_cards) - target_limit}张！多余的牌已被弃置。")
        config.logger.dragon << f"【LOG】用户{target}手牌为{cards_to_str(self_hand_cards)}，超出上限{target_limit}，自动弃置。"
        await discard_cards(copy(self_hand_cards[target_limit:]), session, target, self_hand_cards)
    set_cards(target, self_hand_cards)
    config.logger.dragon << f"【LOG】交换完用户{qq}与用户{target}的手牌，当前用户{qq}的手牌为{cards_to_str(hand_card)}。"

# 结算卡牌相关。请不要递归调用此函数。
async def settlement(buf: SessionBuffer, qq: int, to_do):
    config.logger.dragon << f"【LOG】用户{qq}开始结算。"
    node = find_or_new(qq)
    hand_card = get_card(qq, node=node)
    await to_do(buf, qq, hand_card)
    # discard
    x = len(hand_card) - node['card_limit']
    while x > 0:
        save_data()
        if buf.active != qq:
            buf.send(f"该玩家手牌已超出上限{x}张！多余的牌已被弃置。")
            config.logger.dragon << f"【LOG】用户{qq}手牌为{cards_to_str(hand_card)}，超出上限{node['card_limit']}，自动弃置。"
            await discard_cards(copy(hand_card[node['card_limit']:]), buf, qq, hand_card)
        else:
            ret2 = f"您的手牌已超出上限{x}张！请先选择一些牌弃置（输入id号，使用空格分隔）：\n" + \
                "\n".join(c.full_description(qq) for c in hand_card)
            config.logger.dragon << f"【LOG】用户{qq}手牌超出上限，用户选择弃牌。"
            await buf.flush()
            l = await buf.aget(prompt=ret2,
                arg_filters=[
                    extractors.extract_text,
                    lambda s: list(map(int, re.findall(r'\d+', str(s)))),
                    validators.fit_size(x, x, message="请输入正确的张数。"),
                    validators.ensure_true(lambda l: check_throw_card(qq, l, hand_card=hand_card), message="您选择了错误的卡牌！"),
                    validators.ensure_true(lambda l: 53 not in l, message="空白卡牌不可因超出手牌上限而被弃置！")
                ])
            buf.send("成功弃置。")
            await discard_cards([Card(i) for i in l], buf, qq, hand_card)
        x = len(hand_card) - node['card_limit']
    set_cards(qq, hand_card)
    await buf.flush()
    save_data()

async def update_begin_word(is_daily):
    global last_update_date
    with open(config.rel('dragon_words.json'), encoding='utf-8') as f:
        d = json.load(f)
    c = random.choice(d['begin'])
    d['last_update_date'] = last_update_date = date.today().isoformat()
    d['begin'].remove(c)
    config.logger.dragon << f"【LOG】更新了起始词：{c}。"
    if len(d['begin']) == 0:
        for group in config.group_id_dict['logic_dragon_supervise']:
            await get_bot().send_group_msg(group_id=group, message="起始词库已空！")
        config.logger.dragon << f"【LOG】起始词库已空！"
    with open(config.rel('dragon_words.json'), 'w', encoding='utf-8') as f:
        f.write(json.dumps(d, indent=4, separators=(',', ': '), ensure_ascii=False))
    word_stripped = re.sub(r'\[CQ:image,file=.*\]', '', c).strip()
    Tree.init(is_daily)
    if is_daily:
        load_log(init=False)
        log_set.add(word_stripped)
        log_file.write(f'0 {word_stripped}\n')
        log_file.flush()
    else:
        Tree.forests.append(Tree._objs)
    root = Tree(None, word_stripped, 2711644761, '', '')
    return c

async def daily_update():
    global global_state
    m = {}
    for qq, quests in global_state['quest'].items():
        if len(quests) == 0:
            continue
        m[qq] = [{'id': get_mission(), 'remain': 3} for i in quests]
        config.logger.dragon << f"【LOG】更新了用户{qq}的任务为：{[c['id'] for c in m[qq]]}。"
    global_state['quest'] = m
    for qq in global_state['steal']:
        global_state['steal'][qq] = {'time': 0, 'user': []}
    save_global_state()
    config.userdata.execute('update dragon_data set daily_status=?, today_jibi=10, today_keyword_jibi=10, shop_drawn_card=0', ('',))
    save_data()
    word = await update_begin_word(is_daily=True)
    return "今日关键词：" + word + "\nid为【0】。"

@on_natural_language(keywords="接", only_to_me=False, only_short_message=False)
@config.ErrorHandle(config.logger.dragon)
async def logical_dragon(session: NLPSession):
    if not await env.test(session):
        return
    await call_command(get_bot(), session.ctx, ('dragon', 'construct'), current_arg=session.msg_text)

@on_natural_language(only_to_me=False, only_short_message=True)
@config.ErrorHandle(config.logger.dragon)
async def logical_dragon_else(session: NLPSession):
    if not await env.test(session):
        return
    text = session.msg_text.strip()
    if text.startswith("查询接龙"):
        await call_command(get_bot(), session.ctx, ('dragon', 'check'), current_arg=text[4:].strip())
    elif text.startswith("查询"):
        await call_command(get_bot(), session.ctx, ('dragon', 'check'), current_arg=text[2:].strip())
    elif text.startswith("使用手牌") and (len(text) == 4 or text[4] == ' '):
        await call_command(get_bot(), session.ctx, ('dragon', 'use_card'), current_arg=text[4:].strip())
    elif text.startswith("使用卡牌") and (len(text) == 4 or text[4] == ' '):
        await call_command(get_bot(), session.ctx, ('dragon', 'use_card'), current_arg=text[4:].strip())
    elif text.startswith("抽卡") and (len(text) == 2 or text[2] == ' '):
        await call_command(get_bot(), session.ctx, ('dragon', 'draw'), current_arg=text[2:].strip())
    elif text.startswith("查看手牌"):
        await call_command(get_bot(), session.ctx, ('dragon', 'check'), current_arg="手牌")
    elif text.startswith("商店"):
        await call_command(get_bot(), session.ctx, ('dragon', 'check'), current_arg="商店")
    elif text.startswith("购买") and (len(text) == 2 or text[2] == ' '):
        await call_command(get_bot(), session.ctx, ('dragon', 'buy'), current_arg=text[2:].strip())
    elif text.startswith("分叉") and (len(text) == 2 or text[2] == ' '):
        await call_command(get_bot(), session.ctx, ('dragon', 'fork'), current_arg=text[2:].strip())
    elif text.startswith("驳回分叉"):
        await call_command(get_bot(), session.ctx, ('dragon', 'delete'), current_arg="-f " + text[4:].strip())
    elif text.startswith("驳回"):
        await call_command(get_bot(), session.ctx, ('dragon', 'delete'), current_arg=text[2:].strip())

@on_command(('dragon', 'construct'), hide=True, environment=env)
@config.ErrorHandle(config.logger.dragon)
@config.buffer_dec
async def dragon_construct(buf: SessionBuffer):
    match = message_re.match(buf.current_arg_text)
    if match:
        qq = buf.ctx['user_id']
        global global_state
        node = find_or_new(qq)
        to_exchange = None
        if check_limited_status(qq, 'd', node) or check_status(qq, 'd', True, node):
            await buf.session.send('你已死，不能接龙！')
            config.logger.dragon << f"【LOG】用户{qq}已死，接龙失败。"
            return
        parent = Tree.find(Tree.match_to_id(match))
        if not parent:
            await buf.session.send("请输入存在的id号。")
            return
        word = match.group(3).strip()
        config.logger.dragon << f"【LOG】用户{qq}尝试接龙{word}，母节点id为{parent.id}。"
        if len(parent.childs) != 0 and not parent.fork:
            config.logger.dragon << f"【LOG】节点{parent.id}不可分叉，接龙失败。"
            await buf.session.send(f"节点不可分叉，接龙{word}失败。")
            return
        if parent.fork and len(parent.childs) == 2:
            config.logger.dragon << f"【LOG】节点{parent.id}已分叉，接龙失败。"
            await buf.session.send(f"节点已分叉，接龙{word}失败。")
            return
        if check_global_status('o', True):
            if parent.word != '' and word != '' and parent.word[-1] != word[0]:
                await buf.session.send("当前规则为首尾接龙，接龙失败。")
                return
        m = check_status(qq, 'm', True, node)
        if m and qq == parent.qq or not m and (qq == parent.qq or parent.parent is not None and qq == parent.parent.qq):
            if check_status(qq, 'z', False, node):
                buf.send("你触发了极速装置！")
                config.logger.dragon << f"【LOG】用户{qq}触发了极速装置。"
                remove_status(qq, 'z', False, remove_all=False)
            else:
                await buf.session.send(f"你接太快了！两次接龙之间至少要隔{'一' if m else '两'}个人。")
                config.logger.dragon << f"【LOG】用户{qq}接龙过快，失败。"
                return
        save_global_state()
        kwd = hdkwd = ""
        if word == keyword:
            config.logger.dragon << f"【LOG】用户{qq}接到了奖励词{keyword}。"
            buf.send("你接到了奖励词！", end='')
            kwd = keyword
            if node['today_keyword_jibi'] > 0:
                config.logger.dragon << f"【LOG】用户{qq}已拿完今日奖励词击毙。"
                buf.send("奖励10击毙。")
                config.userdata.execute("update dragon_data set today_keyword_jibi=? where qq=?", (node['today_keyword_jibi'] - 10, qq))
                await add_jibi(buf, qq, 10)
            else:
                buf.send("")
            if update_keyword(if_delete=True):
                buf.end(f"奖励词已更新为：{keyword}。")
            else:
                buf.end("奖励词池已空！")
        for i, k in enumerate(hidden_keyword):
            if k in word:
                hdkwd = k
                config.logger.dragon << f"【LOG】用户{qq}接到了隐藏奖励词{k}。"
                buf.send(f"你接到了隐藏奖励词{k}！奖励10击毙。")
                await add_jibi(buf, qq, 10)
                n = check_global_status('m', False)
                if n:
                    config.logger.dragon << f"【LOG】用户{qq}触发了存钱罐{n}次。"
                    buf.send(f"\n你触发了存钱罐，奖励+{n * 10}击毙！")
                    remove_global_status('m', False)
                    await add_jibi(buf, qq, n * 10)
                if global_state['exchange_stack']:
                    to_exchange = global_state['exchange_stack'].pop(-1)
                    config.logger.dragon << f"【LOG】用户{qq}触发了互相交换，来自{to_exchange}。"
                    save_global_state()
                if not update_hidden_keyword(i, True):
                    buf.end("隐藏奖励词池已空！")
                break
        fork = False
        if (n := check_global_status('b', True)):
            fork = random.random() > 0.95 ** n
        if not (tree_node := check_and_add_log_and_contruct_tree(parent, word, qq, kwd=kwd, hdkwd=hdkwd, fork=fork)):
            config.logger.dragon << f"【LOG】用户{qq}由于过去一周接过此词，死了。"
            buf.send("过去一周之内接过此词，你死了！")
            await settlement(buf, qq, kill)
        else:
            buf.send(f"成功接龙！接龙词：{word}，id为【{tree_node.id_str}】。", end='')
            if node['today_jibi'] > 0:
                config.logger.dragon << f"【LOG】用户{qq}仍有{node['today_jibi']}次奖励机会。"
                jibi_to_add = 1
                if (n := check_status(qq, 'y', False, node)) and node['today_jibi'] % 2 == 1:
                    config.logger.dragon << f"【LOG】用户{qq}触发了幸运护符{n}次。"
                    jibi_to_add += n
                    buf.send("\n你因为幸运护符的效果，", end='')
                buf.send(f"奖励{jibi_to_add}击毙。")
                config.userdata.execute("update dragon_data set today_jibi=? where qq=?", (node['today_jibi'] - 1, qq))
                await add_jibi(buf, qq, jibi_to_add)
                if node['today_jibi'] == 1:
                    buf.send("你今日全勤，奖励1抽奖券！")
                    config.logger.dragon << f"【LOG】用户{qq}全勤，奖励1抽奖券。"
                    config.userdata.execute("update dragon_data set draw_time=? where qq=?", (node['draw_time'] + 1, qq))
            else:
                buf.send("")
            if (n := check_status(qq, 'p', False, node)):
                user = parent.qq
                if user not in global_state['steal'][str(qq)]['user'] and global_state['steal'][str(qq)]['time'] < 10:
                    global_state['steal'][str(qq)]['time'] += 1
                    global_state['steal'][str(qq)]['user'].append(user)
                    save_global_state()
                    config.logger.dragon << f"【LOG】用户{qq}触发了{n}次掠夺者啵噗的效果，偷取了{user}击毙，剩余偷取次数{9 - global_state['steal'][str(qq)]['time']}。"
                    if (p := get_jibi(user)) > 0:
                        buf.send(f"你从上一名玩家处偷取了{min(n, p)}击毙！")
                        await add_jibi(buf, user, -n)
                        await add_jibi(buf, qq, min(n, p))
            if fork:
                buf.send("你触发了Fork Bomb，此词变成了分叉点！")
            if l := global_state['quest'].get(str(qq)):
                for m in l:
                    if m['remain'] > 0:
                        id, name, func = mission[m['id']]
                        if func(word):
                            buf.send(f"你完成了任务：{name[:-1]}！奖励3击毙。此任务还可完成{m['remain'] - 1}次。")
                            config.logger.dragon << f"【LOG】用户{qq}完成了一次任务{name}，剩余{m['remain'] - 1}次。"
                            m['remain'] -= 1
                            await add_jibi(buf, qq, 3)
                            save_global_state()
                            break
            if word in bombs:
                buf.send("你成功触发了炸弹，被炸死了！")
                config.logger.dragon << f"【LOG】用户{qq}触发了炸弹，被炸死了。"
                remove_bomb(word)
                await settlement(buf, qq, kill)
            if (n := check_global_status('+', False)):
                remove_global_status('+', False)
                buf.send(f"你触发了{n}次+2的效果，摸{n}张非正面牌与{n}张非负面牌！")
                config.logger.dragon << f"【LOG】用户{qq}触发了+2的效果。"
                cards = list(itertools.chain(*[[draw_card({-1, 0}), draw_card({0, 1})] for i in range(n)]))
                await settlement(buf, qq, partial(draw, 0, cards=cards))
            if to_exchange is not None:
                buf.send(f"你与[CQ:at,qq={to_exchange}]交换了手牌与击毙！")
                jibi = (get_jibi(qq), get_jibi(to_exchange))
                config.logger.dragon << f"【LOG】用户{qq}与{to_exchange}交换了手牌与击毙。{qq}击毙为{jibi[0]}，{to_exchange}击毙为{jibi[1]}。"
                await add_jibi(buf, qq, jibi[1] - jibi[0])
                await add_jibi(buf, to_exchange, jibi[0] - jibi[1])
                await settlement(buf, qq, partial(exchange, target=to_exchange))
        await buf.flush()
        save_data()

@on_command(('dragon', 'use_card'), aliases="使用手牌", short_des="使用手牌。", only_to_me=False, args=("card"), environment=env)
@config.ErrorHandle(config.logger.dragon)
@config.buffer_dec
async def dragon_use_card(buf: SessionBuffer):
    """使用手牌。
    使用方法为：使用手牌 id号"""
    args = buf.current_arg_text.strip()
    if len(args) == 0:
        buf.finish("请输入想使用的卡牌！")
    try:
        card = Card(int(args))
    except (ValueError, IndexError):
        card = more_itertools.only([cls for cls in _card.card_id_dict.values() if cls.name == args])
    if card is None:
        buf.finish("请输入存在的卡牌id号或卡牌名。")
    qq = buf.ctx['user_id']
    hand_card = get_card(qq)
    config.logger.dragon << f"【LOG】用户{qq}试图使用手牌{card.name}，当前手牌为{hand_card}。"
    if card not in hand_card:
        buf.finish("你还未拥有这张牌！")
    if card.id == -1:
        config.logger.dragon << f"【LOG】用户{qq}无法使用卡牌{card.name}。"
        buf.finish("此牌不可被使用！")
    hand_card.remove(card)
    set_cards(qq, hand_card)
    save_data()
    await settlement(buf, qq, partial(use_card, card))
    save_data()

@on_command(('dragon', 'draw'), short_des="使用抽卡券进行抽卡。", only_to_me=False, args=("num"), environment=env)
@config.ErrorHandle(config.logger.dragon)
@config.buffer_dec
async def dragon_draw(buf: SessionBuffer):
    """使用抽卡券进行抽卡。
    使用方法：抽卡 张数"""
    qq = buf.ctx['user_id']
    try:
        n = int(buf.current_arg_text.strip() or 1)
    except ValueError:
        n = 1
    config.logger.dragon << f"【LOG】用户{qq}试图抽卡{n}次。"
    draw_time = find_or_new(qq)['draw_time']
    if draw_time < n:
        config.logger.dragon << f"【LOG】用户{qq}的抽卡券只有{draw_time}张。"
        n = draw_time
        buf.send(f"您的抽卡券只有{n}张！\n")
    if n == 0:
        buf.finish("您没有抽卡券！")
    draw_time -= n
    config.userdata.execute('update dragon_data set draw_time=? where qq=?', (draw_time, qq))
    await settlement(buf, qq, partial(draw, n))
    save_data()

@on_command(('dragon', 'check'), aliases="查询接龙", only_to_me=False, short_des="查询逻辑接龙相关数据。", args=("name",), environment=env)
@config.ErrorHandle(config.logger.dragon)
async def dragon_check(session: CommandSession):
    """查询逻辑接龙相关数据。可选参数：
    奖励词/keyword：查询当前奖励词。
    奖励池/keyword_pool：查询当前奖励词池大小。
    起始池/begin_pool：查询当前起始词池大小。
    隐藏奖励池/hidden_keyword_pool：查询当前隐藏奖励池大小。
    卡池/card_pool：查询当前卡池总卡数。
    活动词/active：查询当前可以接的词。
    复活时间/recover_time：查询自己的复活时间。
    状态/status：查询自己当前状态。
    资料/profile：查询自己当前资料。
    手牌/hand_cards：查询自己当前手牌。
    击毙/jibi：查询自己的击毙数。
    商店/shop：查询可购买项目。"""
    with open(config.rel('dragon_words.json'), encoding='utf-8') as f:
        d = json.load(f)
    data = session.current_arg_text
    if data in ("奖励词", "keyword"):
        session.finish("当前奖励词为：" + keyword)
    elif data in ("奖励池", "keyword_pool"):
        session.finish("当前奖励池大小为：" + str(len(d['keyword'][1])))
    elif data in ("起始池", "begin_pool"):
        session.finish("当前起始池大小为：" + str(len(d['begin'])))
    elif data in ("隐藏奖励池", "hidden_keyword_pool"):
        session.finish("当前隐藏奖励池大小为：" + str(len(d['hidden'][1])))
    elif data in ("卡池", "card_pool"):
        session.finish("当前卡池大小为：" + str(len(_card.card_id_dict)))
    elif data in ("商店", "shop"):
        session.finish("1. (25击毙)从起始词库中刷新一条接龙词。\n2. (1击毙/15分钟)死亡时，可以消耗击毙减少死亡时间。\n3. (70击毙)向起始词库中提交一条词（需审核）。提交时请携带一张图。\n4. (35击毙)回溯一条接龙。\n5. (10击毙)将一条前一段时间内接过的词标记为雷。雷的存在无时间限制，若有人接到此词则立即被炸死。\n6. (5击毙)刷新一组隐藏奖励词。\n7. (50击毙)提交一张卡牌候选（需审核）。请提交卡牌名、来源、与卡牌效果描述。\n8. (25击毙)抽一张卡，每日限一次。")
    qq = session.ctx['user_id']
    node = find_or_new(qq)
    if data in ("复活时间", "recover_time"):
        status = eval(node['status_time'])
        time = get_limited_time(qq, 'd', status)
        if time is None:
            session.finish("你目前没有复活时间！")
        else:
            session.finish(f"你的复活时间为：{time}分钟。")
    elif data in ("手牌", "hand_cards"):
        cards = get_card(qq)
        if len(cards) == 0:
            session.finish("你没有手牌！")
        session.finish("你的手牌为：\n" + '\n'.join(s.full_description(qq) for s in cards))
    elif data in ("击毙", "jibi"):
        session.finish("你的击毙数为：" + str(node['jibi']))
    elif data in ("状态", "status"):
        status = node['status']
        daily_status = node['daily_status']
        status_time = eval(node['status_time'])
        def _():
            for s in status:
                yield _card.status_dict[s]
            for s in daily_status:
                yield _card.daily_status_dict[s]
            for key in status_time:
                time = get_limited_time(qq, key, status)
                if time is not None:
                    yield f"{_card.limited_status_dict[key]}\n\t结束时间：{time}分钟。"
            if qq in global_state['lianhuan']:
                yield tiesuolianhuan.status_des
        ret = '\n'.join(_())
        if ret == '':
            session.finish("你目前没有状态！")
        else:
            session.finish("你的状态为：\n" + ret)
    elif data in ("活动词", "active"):
        words = [s[-1] for s in Tree._objs if len(s) != 0 and len(s[-1].childs) == 0]
        for s in Tree._objs:
            for word in s:
                if word.fork and len(word.childs) == 1:
                    words.append(word)
        session.finish("当前活动词为：\n" + '\n'.join(f"{s.word}，{'⚠️' if s.qq == qq or s.parent is not None and s.parent.qq == qq else ''}id为{s.id_str}" for s in words))
    elif data in ("资料", "profile"):
        session.finish(f"你的资料为：\n今日剩余获得击毙次数：{node['today_jibi']}。\n今日剩余获得关键词击毙：{node['today_keyword_jibi']}。\n剩余抽卡券：{node['draw_time']}。\n手牌上限：{node['card_limit']}。")

@on_command(('dragon', 'buy'), aliases="购买", only_to_me=False, short_des="购买逻辑接龙相关商品。", args=("id",), environment=env)
@config.ErrorHandle(config.logger.dragon)
@config.buffer_dec
async def dragon_buy(buf: SessionBuffer):
    """购买逻辑接龙相关商品。
    使用方法：购买 id号"""
    try:
        id = int(buf.current_arg_text)
    except ValueError:
        buf.finish("请输入要购买的商品id。")
    qq = buf.ctx['user_id']
    config.logger.dragon << f"【LOG】用户{qq}购买商品{id}。"
    if id == 1:
        # (25击毙)从起始词库中刷新一条接龙词。
        await add_jibi(buf, qq, -25, is_buy=True)
        buf.send("您刷新的关键词为：" + await update_begin_word() + "，id为【0】。")
    elif id == 2:
        # (1击毙/15分钟)死亡时，可以消耗击毙减少死亡时间。
        config.logger.dragon << f"【LOG】询问用户{qq}减少的死亡时间。"
        n = (await buf.aget(prompt="请输入你想要减少的死亡时间，单位为分钟。",
            arg_filters=[
                extractors.extract_text,
                lambda s: list(map(int, re.findall(r'\d+', str(s)))),
                validators.fit_size(1, 1, message="请输入一个自然数。"),
            ]))[0]
        n //= 15
        if (jibi := get_jibi(qq)) < n:
            buf.send(f"您只有{jibi}击毙！")
            n = jibi
        config.logger.dragon << f"【LOG】用户{qq}使用{n}击毙减少{15 * n}分钟死亡时间。"
        await add_jibi(buf, qq, -n, is_buy=True)
        b = decrease_death_time(qq, timedelta(minutes=15 * n))
        buf.send(f"您减少了{15 * n}分钟的死亡时间！" + ("您活了！" if b else ""))
    elif id == 3:
        # (70击毙)向起始词库中提交一条词（需审核）。提交时请携带一张图。
        config.logger.dragon << f"【LOG】询问用户{qq}提交起始词与图。"
        s = await buf.aget(prompt="请提交起始词和一张图。（审核不通过不返还击毙），输入取消退出。", arg_filters=[cancellation(session)])
        config.logger.dragon << f"【LOG】用户{qq}提交起始词：{s}。"
        await add_jibi(buf, qq, -70, is_buy=True)
        for group in config.group_id_dict['logic_dragon_supervise']:
            await get_bot().send_group_msg(group_id=group, message=s)
        buf.send("您已成功提交！")
    elif id == 4:
        # (35击毙)回溯一条接龙。
        await add_jibi(buf, qq, -35, is_buy=True)
        buf.send("成功回溯！")
    elif id == 5:
        # (10击毙)将一条前一段时间内接过的词标记为雷。雷的存在无时间限制，若有人接到此词则立即被炸死。
        config.logger.dragon << f"【LOG】询问用户{qq}标记的雷。"
        c = await buf.aget(prompt="请输入标记为雷的词。",
            arg_filters=[
                extractors.extract_text,
                validators.ensure_true(lambda c: c in log_set, message="请输入一周以内接过的词汇。输入取消退出。"),
                cancellation(buf.session)
            ])
        config.logger.dragon << f"【LOG】用户{qq}标记{c}为雷。"
        await add_jibi(buf, qq, -10, is_buy=True)
        add_bomb(c)
        buf.send(f"成功添加词汇{c}！")
    elif id == 6:
        # (5击毙)刷新一组隐藏奖励词。
        await add_jibi(buf, qq, -5, is_buy=True)
        update_hidden_keyword(-1)
        buf.send("成功刷新！")
    elif id == 7:
        # (50击毙)提交一张卡牌候选（需审核）。请提交卡牌名、来源、与卡牌效果描述。
        config.logger.dragon << f"【LOG】询问用户{qq}提交的卡牌。"
        s = await buf.aget(prompt="请提交卡牌名、来源、与卡牌效果描述。（审核不通过不返还击毙），输入取消退出。", arg_filter=[cancellation(buf.session)])
        config.logger.dragon << f"【LOG】用户{qq}提交卡牌{s}。"
        await add_jibi(buf, qq, -50, is_buy=True)
        for group in config.group_id_dict['dragon_supervise']:
            await get_bot().send_group_msg(group_id=group, message=s)
        buf.send("您已成功提交！")
    elif id == 8:
        # (25击毙)抽一张卡，每日限一次。
        node = find_or_new(qq)
        if node['shop_drawn_card'] >= 1:
            buf.send("您今日已在商店购买过抽卡！")
        else:
            config.userdata.execute("update dragon_data set shop_drawn_card=? where qq=?", (node['shop_drawn_card'] + 1, qq))
            await add_jibi(buf, qq, -25, is_buy=True)
            await settlement(buf, qq, partial(draw, 1))
            save_data()
    await buf.flush()

@on_command(('dragon', 'fork'), aliases="分叉", only_to_me=False, short_des="分叉接龙。", args=("id",), environment=env)
@config.ErrorHandle(config.logger.dragon)
async def dragon_fork(session: CommandSession):
    """分叉接龙。
    使用方法：分叉 id号"""
    match = re.search(r'(\d+)([a-z])?', session.current_arg_text)
    parent = Tree.find(Tree.match_to_id(match))
    if not parent:
        session.finish("请输入存在的id号。")
    parent.fork = True
    config.logger.dragon << f"【LOG】用户{session.ctx['user_id']}将id{parent.id}分叉。"
    session.finish("成功分叉！")

@on_command(('dragon', 'delete'), aliases="驳回", only_to_me=False, short_des="管理可用，驳回节点。", args=("[-f]", "id"), environment=env_admin)
@config.ErrorHandle(config.logger.dragon)
async def dragon_delete(session: CommandSession):
    """管理可用，驳回节点。
    可选参数：
        -f：驳回该节点的分叉。
    可使用：驳回 id 或 驳回分叉 id。"""
    match = re.search(r'(\d+)([a-z])?', session.current_arg_text)
    node = Tree.find(Tree.match_to_id(match))
    if not node:
        session.finish("请输入存在的id号。")
    to_delete = None
    f = session.current_arg_text.strip().startswith('-f')
    if f:
        if len(node.childs) == 2:
            to_delete = node.childs[1]
        node.fork = False
    else:
        to_delete = node
    if await session.aget(prompt=f"要{f'驳回节点{node.word}的分叉' if f else ''}{'并' if f and to_delete is not None else ''}{f'驳回节点{to_delete.word}' if to_delete is not None else ''}，输入确认继续，输入取消退出。") != "确认":
        session.finish("已退出。")
    to_delete.remove()
    # 保存到log文件
    d = date.today()
    if datetime.now().time() < time(15, 59):
        d -= timedelta(days=1)
    today = rf'log\dragon_log_{d.isoformat()}.txt'
    global log_file
    log_file.close()
    with open(config.rel(today), 'w', encoding='utf-8') as file:
        file.writelines(str(word) + '\n' for word in itertools.chain(*Tree._objs))
    log_file = open(config.rel(today), 'a', encoding='utf-8')
    buf = SessionBuffer(session)
    buf.send("已成功驳回。")
    if not f:
        await settlement(buf, node.qq, kill)
    else:
        await buf.flush()

@on_command(('dragon', 'add_begin'), only_to_me=False, environment=env_supervise)
@config.ErrorHandle(config.logger.dragon)
async def dragon_add_begin(session: CommandSession):
    """添加起始词。黑幕群可用。"""
    add_begin(session.current_arg.strip())
    await session.send('成功添加起始词。')

@on_command(('dragon', 'add_keyword'), only_to_me=False, environment=env_supervise)
@config.ErrorHandle(config.logger.dragon)
async def dragon_add_keyword(session: CommandSession):
    """添加关键词。黑幕群可用。"""
    add_keyword(session.current_arg.strip())
    await session.send('成功添加关键词。')

@on_command(('dragon', 'add_hidden'), only_to_me=False, environment=env_supervise)
@config.ErrorHandle(config.logger.dragon)
async def dragon_add_hidden(session: CommandSession):
    """添加隐藏关键词。黑幕群可用。"""
    add_hidden(session.current_arg_text.strip())
    await session.send('成功添加隐藏关键词。')

@on_command(('dragon', 'kill'), only_to_me=False, args=('@s',), environment=env_admin)
@config.ErrorHandle(config.logger.dragon)
@config.buffer_dec
async def dragon_kill(buf: SessionBuffer):
    """击毙玩家，管理可用，用于处理驳回。"""
    match = re.search('qq=(\\d+)', buf.current_arg)
    if not match:
        buf.finish("没有@人！")
    qq = match.group(1)
    await settlement(buf, qq, kill)

@on_command(('dragon', 'version'), only_to_me=False, short_des="查看逻辑接龙版本。", args=("[-c]",))
@config.ErrorHandle(config.logger.dragon)
async def dragon_version(session: CommandSession):
    """查看逻辑接龙版本。
    可选参数：
    -c：一并输出Changelog。"""
    if session.current_arg_text == '-c':
        await session.send(f"七海千春 逻辑接龙 ver.{version} 为您服务\n{changelog}")
    else:
        await session.send(f"七海千春 逻辑接龙 ver.{version} 为您服务")

@scheduler.scheduled_job('cron', id="dragon_daily", hour='16', minute='00-03')
async def dragon_daily():
    global last_update_date
    config.logger.dragon << f"【LOG】尝试每日更新。"
    if last_update_date == date.today().isoformat():
        return
    graph = Tree.graph()
    # for group in config.group_id_dict['logic_dragon_send']:
    #     await get_bot().send_group_msg(group_id=group, message=[config.cq.text("昨天的接龙图："), config.cq.img(graph)])
    ret = await daily_update()
    for group in config.group_id_dict['logic_dragon_send']:
        await get_bot().send_group_msg(group_id=group, message=ret)

@on_command(('dragon', 'update'), only_to_me=False, hide=True, permission=permission.SUPERUSER)
@config.ErrorHandle(config.logger.dragon)
async def dragon_update(session: CommandSession):
    global last_update_date
    config.logger.dragon << f"【LOG】强制每日更新。"
    graph = Tree.graph()
    # for group in config.group_id_dict['logic_dragon_send']:
    #     await get_bot().send_group_msg(group_id=group, message=[config.cq.text("昨天的接龙图："), config.cq.img(graph)])
    ret = await daily_update()
    for group in config.group_id_dict['logic_dragon_send']:
        await get_bot().send_group_msg(group_id=group, message=ret)

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
                async def use(self, session, qq, hand_card):
                    add_status(qq, status, False)
                attrs['use'] = use
            elif 'daily_status' in attrs and attrs['daily_status']:
                status = attrs['daily_status']
                bases[0].add_daily_status(status, attrs['status_des'])
                @classmethod
                async def use(self, session, qq, hand_card):
                    add_status(qq, status, True)
                attrs['use'] = use
            elif 'limited_status' in attrs and attrs['limited_status']:
                status = attrs['limited_status']
                bases[0].add_limited_status(status, attrs['status_des'])
                @classmethod
                async def use(self, session, qq, hand_card):
                    add_limited_status(qq, status, datetime.now() + self.limited_time)
                attrs['use'] = use
            elif 'global_status' in attrs and attrs['global_status']:
                status = attrs['global_status']
                bases[0].add_status(status, attrs['status_des'])
                @classmethod
                async def use(self, session, qq, hand_card):
                    add_global_status(status, False)
                attrs['use'] = use
            elif 'global_daily_status' in attrs and attrs['global_daily_status']:
                status = attrs['global_daily_status']
                bases[0].add_daily_status(status, attrs['status_des'])
                @classmethod
                async def use(self, session, qq, hand_card):
                    add_global_status(status, True)
                attrs['use'] = use
            elif 'global_limited_status' in attrs and attrs['global_limited_status']:
                status = attrs['global_limited_status']
                bases[0].add_limited_status(status, attrs['status_des'])
                @classmethod
                async def use(self, session, qq, hand_card):
                    add_global_limited_status(status, datetime.now() + self.global_limited_time)
                attrs['use'] = use
            elif 'hold_status' in attrs and attrs['hold_status']:
                status = attrs['hold_status']
                bases[0].add_status(status, attrs['status_des'])
                @classmethod
                async def on_draw(cls, session, qq, hand_card):
                    add_status(qq, status, False)
                @classmethod
                async def on_discard(cls, session, qq, hand_card):
                    remove_status(qq, status, False)
                @classmethod
                async def on_give(cls, session, qq, target):
                    remove_status(qq, status, False)
                    add_status(target, status, False)
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
    card_id_dict = {}
    status_dict = {'d': "永久死亡。"}
    daily_status_dict = {}
    limited_status_dict = {'d': "死亡：不可接龙。"}
    name = ""
    id = -15
    positive = 0
    description = ""
    arg_num = 0
    consumed_on_draw = False
    @classmethod
    async def use(cls, session, qq, hand_card):
        pass
    @classmethod
    async def on_draw(cls, session, qq, hand_card):
        pass
    @classmethod
    async def on_discard(cls, session, qq, hand_card):
        pass
    @classmethod
    async def on_give(cls, session, qq, target):
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
    async def on_discard(cls, session, qq, hand_card):
        await kill(session, qq, hand_card)

# class nvjisi(_card):
#     name = "II - 女祭司"
#     id = 2
#     positive = 0
#     description = "击毙当前周期内接龙次数最多的玩家。"
#     @classmethod
#     async def use(cls, session, qq, hand_card):
#         pass

# class lianren(_card):
#     name = "VI - 恋人"
#     id = 6
#     positive = 1
#     description = "复活1名指定玩家。"
#     @classmethod
#     async def use(cls, session, qq, hand_card):
#         await session.flush()
#         l = await session.aget(prompt="请at一名玩家复活。\n",
#             arg_filters=[
#                     lambda s: [r.group(1) for r in re.findall(r'qq=(\d+)', str(s))],
#                     validators.fit_size(1, 1, message="请at正确的人数。"),
#                 ])
#         n = check_limited_status(l[0], 'd')
#         remove_limited_status(l[0], 'd')
#         session.send("已复活！" + ("（虽然目标并没有死亡）" if n else ''))

# class taiyang(_card):
#     name = "XIX - 太阳"
#     id = 19
#     positive = 1
#     description = "随机揭示一个隐藏奖励词。"
#     @classmethod
#     async def use(cls, session, qq, hand_card):
#         session.send("你揭示的一个隐藏奖励词是：" + random.choice(hidden_keyword))

class dabingyichang(_card):
    name = "大病一场"
    id = 30
    positive = -1
    description = "抽到时，直到下一次主题出现前不得接龙。"
    consumed_on_draw = True
    @classmethod
    async def on_draw(cls, session, qq, hand_card):
        add_status(qq, 'd', True)
        session.send(session.char(qq) + "病了！直到下一次主题出现前不得接龙。")
_card.add_daily_status('d', "生病：直到下一次主题出现前不可接龙。")

class caipiaozhongjiang(_card):
    name = "彩票中奖"
    id = 31
    positive = 1
    description = "抽到时立即获得20击毙与两张牌。"
    consumed_on_draw = True
    @classmethod
    async def on_draw(cls, session, qq, hand_card):
        session.send(session.char(qq) + "中奖了！获得20击毙与两张牌。")
        await add_jibi(session, qq, 20)
        await draw(2, session, qq, hand_card)

class wuzhongshengyou(_card):
    name = "无中生有"
    id = 36
    positive = 1
    description = "摸两张牌。"
    @classmethod
    async def use(cls, session, qq, hand_card):
        await draw(2, session, qq, hand_card)

class tiesuolianhuan(_card):
    name = "铁索连环"
    id = 38
    positive = 1
    status_des = "铁索连环：任何处于连环状态的玩家被击毙时所有连环状态的玩家也被击毙并失去此效果。"
    description = "指定至多两名玩家进入连环状态。任何处于连环状态的玩家被击毙时所有连环状态的玩家也被击毙并失去此效果。也可用于解除至多两人的连环状态。"
    @classmethod
    async def use(cls, session, qq, hand_card):
        await session.flush()
        config.logger.dragon << f"【LOG】询问用户{qq}铁索连环。"
        l = await session.aget(prompt="请at群内至多两名玩家进行铁索连环。\n",
            arg_filters=[
                    lambda s: [int(r) for r in re.findall(r'qq=(\d+)', str(s))],
                    validators.fit_size(1, 2, message="请at正确的人数。"),
                ])
        config.logger.dragon << f"【LOG】用户{qq}铁索连环选择{l}。"
        global global_state
        for target in l:
            if target in global_state['lianhuan']:
                global_state['lianhuan'].remove(target)
            else:
                global_state['lianhuan'].append(target)
        save_global_state()
        session.send('成功切换玩家的连环状态！')

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
    async def use(cls, session, qq, hand_card):
        await session.flush()
        config.logger.dragon << f"【LOG】询问用户{qq}复制牌。"
        l = await session.aget(prompt="请选择你手牌中的一张牌复制，输入id号。\n" + "\n".join(c.full_description(qq) for c in hand_card),
            arg_filters=[
                    extractors.extract_text,
                    lambda s: list(map(int, re.findall(r'\d+', str(s)))),
                    validators.fit_size(1, 1, message="请输入正确的张数。"),
                    validators.ensure_true(lambda l: Card(l[0]) in hand_card, message="您选择了错误的卡牌！"),
                    validators.ensure_true(lambda l: -1 not in l, message="此牌不可使用！")
                ])
        card = Card(l[0])
        config.logger.dragon << f"【LOG】用户{qq}选择了卡牌{card.name}。"
        session.send(session.char(qq) + '使用了卡牌：\n' + card.full_description(qq))
        await card.use(session, qq, hand_card)

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
    async def use(cls, session, qq, hand_card):
        session.send("你弃光了所有手牌。")
        await discard_cards(copy(hand_card), session, qq, hand_card)

class dragontube(_card):
    name = "龙之烟管"
    id = 54
    positive = 1
    description = "你今天通过普通接龙获得的击毙上限增加10。"
    @classmethod
    async def use(cls, session, qq, hand_card):
        node = find_or_new(qq)
        config.logger.dragon << f"【LOG】用户{qq}增加了接龙击毙上限至{node['today_jibi'] + 10}。"
        config.userdata.execute('update dragon_data set today_jibi=? where qq=?', (node['today_jibi'] + 10, qq))
        session.send("已增加。")

class xingyuntujiao(_card):
    name = "幸运兔脚"
    id = 55
    positive = 1
    description = "抽取一张正面卡并立即发动效果。"
    @classmethod
    async def use(cls, session, qq, hand_card):
        c = draw_card({1})
        config.logger.dragon << f"【LOG】用户{qq}幸运兔脚抽取了卡牌{c.name}。"
        session.send(session.char(qq) + '抽到并使用了卡牌：\n' + c.full_description(qq))
        await c.on_draw(session, qq, hand_card)
        await c.use(session, qq, hand_card)
        await c.on_discard(session, qq, hand_card)

class baoshidewugong(_card):
    name = "暴食的蜈蚣"
    id = 56
    positive = 1
    description = "你的手牌上限永久+1。"
    @classmethod
    async def use(cls, session, qq, hand_card):
        node = find_or_new(qq)
        config.logger.dragon << f"【LOG】用户{qq}增加了手牌上限至{node['card_limit'] + 1}。"
        config.userdata.execute('update dragon_data set card_limit=? where qq=?', (node['card_limit'] + 1, qq))

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
    description = "拆除所有雷。"
    @classmethod
    async def use(cls, session, qq, hand_card):
        remove_all_bomb()

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
    def full_description(cls, qq):
        m = mission[global_state['quest'][str(qq)][quest_print_aux[str(qq)]]['id']][1]
        remain = global_state['quest'][str(qq)][quest_print_aux[str(qq)]]['remain']
        quest_print_aux[str(qq)] += 1
        if quest_print_aux[str(qq)] >= len(global_state['quest'][str(qq)]):
            quest_print_aux[str(qq)] = 0
        return super().full_description(qq) + "\n\t当前任务：" + m + f"剩余{remain}次。"
    @classmethod
    async def on_draw(cls, session, qq, hand_card):
        if str(qq) not in global_state['quest']:
            global_state['quest'][str(qq)] = []
            quest_print_aux[str(qq)] = 0
        global_state['quest'][str(qq)].append({'id': (i := get_mission()), 'remain': 3})
        config.logger.dragon << f"【LOG】用户{qq}刷新了一个任务{mission[i][1]}，现有任务：{[mission[c['id']][1] for c in global_state['quest'][str(qq)]]}。"
        save_global_state()
    @classmethod
    async def on_discard(cls, session, qq, hand_card):
        i = global_state['quest'][str(qq)][quest_print_aux[str(qq)]]['id']
        del global_state['quest'][str(qq)][quest_print_aux[str(qq)]]
        if quest_print_aux[str(qq)] >= len(mission):
            quest_print_aux[str(qq)] = 0
        config.logger.dragon << f"【LOG】用户{qq}删除了一个任务{mission[i][1]}，现有任务：{[mission[c['id']][1] for c in global_state['quest'][str(qq)]]}。"
        save_global_state()
    @classmethod
    async def on_give(cls, session, qq, target):
        m = global_state['quest'][str(qq)][quest_print_aux[str(qq)]]
        i = m['id']
        del global_state['quest'][str(qq)][quest_print_aux[str(qq)]]
        if quest_print_aux[str(qq)] >= len(mission):
            quest_print_aux[str(qq)] = 0
        config.logger.dragon << f"【LOG】用户{qq}删除了一个任务{mission[i][1]}，现有任务：{[mission[c['id']][1] for c in global_state['quest'][str(qq)]]}。"
        if str(target) not in global_state['quest']:
            global_state['quest'][str(target)] = []
            quest_print_aux[str(target)] = 0
        global_state['quest'][str(target)].append(m)
        config.logger.dragon << f"【LOG】用户{target}增加了一个任务{mission[i][1]}，现有任务：{[mission[c['id']][1] for c in global_state['quest'][str(target)]]}。"
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
    async def use(cls, session, qq, hand_card):
        set_cards(qq, hand_card)
        config.logger.dragon << f"【LOG】用户{qq}交换了所有人的手牌。"
        l = [(t['qq'], get_card(t['qq'], t['card'])) for t in config.userdata.execute("select qq, card from dragon_data").fetchall()]
        config.logger.dragon << f"【LOG】所有人的手牌为：{','.join(f'{qq}: {cards_to_str(cards)}' for qq, cards in l)}。"
        all_cards = list(itertools.chain(*([(q, c) for c in cs] for q, cs in l)))
        random.shuffle(all_cards)
        hand_card.clear()
        for q, c in l:
            if (n := len(c)):
                cards_temp = [c for q, c in all_cards[:n]]
                if qq == q:
                    hand_card.extend(cards_temp)
                set_cards(q, cards_temp)
                for qqq, c in all_cards[:n]:
                    await c.on_give(session, qqq, q)
                config.logger.dragon << f"【LOG】{q}交换后的手牌为：{cards_to_str(cards_temp)}。"
                all_cards = all_cards[n:]
        if len(hand_card) != 0:
            session.send("通过交换，你获得了手牌：\n" + '\n'.join(c.full_description(qq) for c in hand_card))
        else:
            session.send("你交换了大家的手牌！")

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
    async def use(cls, session, qq, hand_card):
        config.logger.dragon << f"【LOG】用户{qq}被加入交换堆栈，现为{global_state['exchange_stack']}。"
        global_state['exchange_stack'].append(qq)
        save_global_state()

class zhongshendexixi(_card):
    name = "众神的嬉戏"
    id = 76
    positive = 0
    description = '抽取一张卡并立即发动效果。'
    @classmethod
    async def use(cls, session, qq, hand_card):
        c = draw_card()
        session.send(session.char(qq) + '抽到并使用了卡牌：\n' + c.full_description(qq))
        config.logger.dragon << f"【LOG】用户{qq}众神的嬉戏抽取了卡牌{c.name}。"
        await c.on_draw(session, qq, hand_card)
        await c.use(session, qq, hand_card)
        await c.on_discard(session, qq, hand_card)

class lveduozhebopu(_card):
    name = "掠夺者啵噗"
    id = 77
    positive = 1
    description = "每天你可从你所接龙的人处偷取1击毙，每人限一次，最多10击毙，若目标没有击毙则不可偷取。死亡时或使用将丢弃这张卡。"
    @classmethod
    async def on_draw(cls, session, qq, hand_card):
        add_status(qq, 'p', False)
        if str(qq) not in global_state['steal']:
            global_state['steal'][str(qq)] = {'time': 0, 'user': []}
        save_global_state()
    @classmethod
    async def on_discard(cls, session, qq, hand_card):
        remove_status(qq, 'p', False)
        if not check_status(qq, 'p', False):
            del global_state['steal'][str(qq)]
        save_global_state()
    @classmethod
    async def on_give(cls, session, qq, target):
        remove_status(qq, 'p', False)
        add_status(target, 'p', False)
        global_state['steal'][str(target)] = global_state['steal'][str(qq)]
        if not check_status(qq, 'p', False):
            del global_state['steal'][str(qq)]
        save_global_state()
_card.add_status('p', '掠夺者啵噗：每天可从所接龙的人处偷取1击毙，每人限一次，最多10击毙，若目标没有击毙则不可偷取。')

class jiandieyubei(_card):
    name = "邪恶的间谍行动～预备"
    id = 78
    positive = 0
    global_daily_statue = 'j'
    description = "今日卡池中有一定概率出现【邪恶的间谍行动~执行】。"

class qijimanbu(_card):
    name = "奇迹漫步"
    id = 79
    positive = 1
    description = "弃置你所有手牌，并摸取等量的非负面牌。"
    @classmethod
    async def use(cls, session, qq, hand_card):
        n = len(hand_card)
        await discard_cards(copy(hand_card), session, qq, hand_card)
        await draw(n, session, qq, hand_card, positive={0, 1})

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
    async def use(cls, session, qq, hand_card):
        session.send("所有人都赢了！恭喜你们！")

class suicideking(_card):
    name = "自杀之王（♥K）"
    id = 90
    positive = -1
    description = "抽到时立即死亡。"
    consumed_on_draw = True
    @classmethod
    async def on_draw(cls, session, qq, hand_card):
        session.send(session.char(qq) + "抽到了自杀之王，" + session.char(qq) + "死了！")
        await kill(session, qq, hand_card)

class zhu(_card):
    name = "猪（♠Q）"
    id = 91
    positive = -1
    description = "抽到时损失20击毙（但不会扣至0以下）。"
    consumed_on_draw = True
    @classmethod
    async def on_draw(cls, session, qq, hand_card):
        await add_jibi(session, qq, -20)
        session.send(session.char(qq) + "抽到了猪，损失了20击毙！")

class yang(_card):
    name = "羊（♦J）"
    id = 92
    positive = 1
    description = "抽到时获得20击毙。"
    consumed_on_draw = True
    @classmethod
    async def on_draw(cls, session, qq, hand_card):
        await add_jibi(session, qq, 20)
        session.send(session.char(qq) + "抽到了羊，获得了20击毙！")

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

from collections import namedtuple

# 飞行棋棋盘格子
class Grid(namedtuple('Grid', ["id", "content", "data", "pos", "childs_id", "parents_id"], defaults=[None, None])):
    __slots__ = ()
    all_items = {}
    topology = 0
    # example: Grid(1, 1, (20, 20), (3, 10), ((2,), (3,), (3,))) # 奖励3pt，被击毙10分钟，在不同拓扑下childs不同
    def __init__(self, *args, **kwargs):
        super(Grid, self).__init__(*args, **kwargs)
        Grid.all_items[self.id] = self
    @classmethod
    def find(cls, id):
        return cls.all_items[id]
    @property
    def parents(self):
        if self.parents_id is None:
            return [self.find(self.id - 1)]
        elif isinstance(self.parents_id[0], (tuple, list)):
            return [self.find(id) for id in self.parents_id[self.topology]]
        else:
            return [self.find(id) for id in self.parents_id]
    @property
    def childs(self):
        if self.childs_id is None:
            return [self.find(self.id + 1)]
        elif isinstance(self.childs_id[0], (tuple, list)):
            return [self.find(id) for id in self.childs_id[self.topology]]
        else:
            return [self.find(id) for id in self.childs_id]
    async def move(self, session, qq, hand_card, n, back=False):
        current = self
        for i in range(n):
            if back:
                current = current.parents[0] # TODO: choose
            else:
                current = current.childs[0] # TODO: choose
        config.logger.dragon << f"【LOG】用户{qq}走到了{current.id}。"
        return current
    async def do(self, session, qq, hand_card):
        await add_event_pt(session, qq, self.data[0])
        if self.content == 0: # 改变拓扑结构至环面/莫比乌斯带/克莱因瓶
            session.send_log.dragon(qq, "走到了：改变拓扑结构至" + {0: "环面", 1: "莫比乌斯带", 2: "克莱因瓶"}[self.data[1]] + "。")
            Grid.topology = self.data[1]
        elif self.content == 1: # 被击毙5/10/15/20/25分钟
            session.send_log.dragon(qq, f"走到了：被击毙{self.data[1]}分钟。")
            await kill(session, qq, hand_card, minute=self.data[1])
        elif self.content == 2: # 获得2/4/6/8/10击毙
            session.send_log.dragon(f"走到了：获得{self.data[1]}击毙。")
            await add_jibi(session, qq, self.data[1])
        elif self.content == 3: # 获得活动pt后，再扔一次骰子前进/后退 
            n = random.randint(1, 6)
            session.send_log.dragon(qq, f"走到了：获得活动pt后，再扔一次骰子{'前进' if self.data[1] == 1 else '后退'}。{session.char(qq)}扔到了{n}。")
            grid = await self.move(session, qq, hand_card, n, back=(self.data[1] != 1))
            return await grid.do(session, qq, hand_card)
        elif self.content == 16: # 抽一张卡并立即发动效果
            session.send_log.dragon("走到了：抽一张卡并立即发动效果。")
            c = draw_card()
            session.send(session.char(qq) + '抽到并使用了卡牌：\n' + c.full_description(qq))
            config.logger.dragon << f"【LOG】用户{qq}抽取了卡牌{c.name}。"
            await c.on_draw(session, qq, hand_card)
            await c.use(session, qq, hand_card)
            await c.on_discard(session, qq, hand_card)
        elif self.content == 17: # 获得20活动pt并随机飞到一个格子
            session.send_log.dragon(f"走到了：获得{self.data[1]}活动pt并随机飞到一个格子。")
            await add_event_pt(session, qq, self.data[1])
            grid = random.choice(list(self.all_items.values()))
            config.logger.dragon << f"【LOG】用户{qq}飞到了{grid.id}。"
            return await grid.do(session, qq, hand_card)
        return self
