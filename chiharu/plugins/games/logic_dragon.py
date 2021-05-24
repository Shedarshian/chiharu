from datetime import datetime, timedelta, date, time
import json
import random
import re
import more_itertools
from functools import lru_cache, partial
from nonebot import CommandSession, NLPSession, on_natural_language, get_bot, scheduler
from nonebot.command import call_command
from nonebot.command.argfilter import extractors, validators
from ..inject import CommandGroup, on_command
from .. import config
from ..config import SessionBuffer
env = config.Environment('logic_dragon')
env_supervise = config.Environment('logic_dragon_supervise')

CommandGroup('dragon', des="逻辑接龙相关。", environment=env|env_supervise)

# TODO 十连保底
message_re = re.compile(r"[\s我那就，]*接[\s，,]*(.*)[\s，,\n]*.*")

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
# log
log_set : set = set()
log_file = None
def load_log():
    global log_set, log_file
    log_set = set()
    if log_file is not None:
        log_file.close()
    d = date.today()
    if datetime.now().time() < time(15, 59):
        d -= timedelta(days=1)
    today = rf'log\dragon_log_{d.isoformat()}.txt'
    for i in range(7):
        try:
            with open(config.rel(rf'log\dragon_log_{d.isoformat()}.txt'), encoding='utf-8') as f:
                log_set.update(s.strip() for s in f.readlines())
        except FileNotFoundError:
            pass
        d -= timedelta(days=1)
    log_file = open(config.rel(today), 'a', encoding='utf-8')
load_log()
def check_and_add_log(s):
    global log_set
    if s in log_set:
        return False
    log_set.add(s)
    log_file.write(s + '\n')
    log_file.flush()
    return True
past_two_user = []

# dragon_data := qq : int, jibi : int, card : str, draw_time : int, death_time : str, today_jibi : int, today_keyword_jibi : int
# status : str, daily_status : str, status_time : str, card_limit : int
# global_status : qq = 2711644761
def find_or_new(qq):
    t = config.userdata.execute("select * from dragon_data where qq=?", (qq,)).fetchone()
    if t is None:
        config.userdata.execute('insert into dragon_data (qq, jibi, draw_time, today_jibi, today_keyword_jibi, death_time, card, status, daily_status, status_time, card_limit) values (?, 0, 0, 10, 10, ?, ?, ?, ?, ?, 4)', (qq, '', '', '', '', '{}'))
        t = config.userdata.execute("select * from dragon_data where qq=?", (qq,)).fetchone()
    return t
def get_jibi(qq):
    return find_or_new(qq)['jibi']
def add_jibi(qq, jibi, current_jibi=None):
    if current_jibi is None:
        current_jibi = get_jibi(qq)
    config.userdata.execute("update dragon_data set jibi=? where qq=?", (max(0, current_jibi + jibi), qq))
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
def update_keyword(d, if_delete=True):
    global keyword
    if len(d['keyword'][1]) == 0:
        return False
    keyword = random.choice(d['keyword'][1])
    if if_delete:
        d['keyword'][1].remove(keyword)
    d['keyword'][0] = keyword
    return True
@wrapper_file
def update_hidden_keyword(d, which, if_delete=False):
    global hidden_keyword
    if which == -1:
        n = {1, 2, 3}
    elif isinstance(which, int):
        n = {which}
    else:
        n = {hidden_keyword.index(which)}
    if len(d['hidden'][1]) < len(n):
        return False
    for i in n:
        hidden_keyword[i] = random.choice(d['hidden'][1])
        if if_delete:
            d['hidden'][1].remove(hidden_keyword[i])
        d['hidden'][0][i] = hidden_keyword[i]
    return True
@wrapper_file
def remove_bomb(d, word):
    global bombs
    d["bombs"].remove(word)
    bombs.remove(word)
@wrapper_file
def add_bomb(d, word):
    global bombs
    d["bombs"].append(word)
    bombs.append(word)
@wrapper_file
def add_begin(d, word):
    d['begin'].append(word)
@wrapper_file
def add_hidden(d, word):
    d['hidden'][1].append(word)


def save_data():
    config.userdata_db.commit()

def add_status(qq, s, is_daily):
    status = find_or_new(qq)['daily_status' if is_daily else 'status']
    if s not in status:
        status += s
        config.userdata.execute('update dragon_data set %s=? where qq=?' % ('daily_status' if is_daily else 'status'), (status, qq))
def add_limited_status(qq, s, end_time : datetime):
    status = eval(find_or_new(qq)['status_time'])
    if s not in status:
        status[s] = end_time.isoformat()
        config.userdata.execute('update dragon_data set status_time=? where qq=?', (str(status), qq))
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
        l.remove(s)
        status = ''.join(l)
    config.userdata.execute('update dragon_data set %s=? where qq=?' % ('daily_status' if is_daily else 'status'), (status, qq))
def remove_limited_status(qq, s, status=None):
    status = status or eval(find_or_new(qq)['status_time'])
    status.pop(s)
    config.userdata.execute('update dragon_data set status_time=? where qq=?', (str(status), qq))
def remove_global_status(s, is_daily, remove_all=True, status=None):
    return remove_status(2711644761, s, is_daily, remove_all, status)
def remove_global_limited_status(s, status=None):
    return remove_limited_status(2711644761, s, status)

char = lambda x: "该玩家" if x else "你"

async def kill(session, qq, hand_card, hour=4, no_requirement=False):
    dodge = False
    n = check_status(qq, 's', False)
    if n and not dodge:
        jibi = get_jibi(qq)
        if jibi >= 10:
            add_jibi(qq, -10, jibi)
            session.send(char(no_requirement) + "触发了死秽回避之药的效果，免除死亡！")
            dodge = True
            remove_status(qq, 's', False, remove_all=False)
    n = check_status(qq, 'h', False)
    if n and not dodge:
        for a in range(n):
            if random.randint(0, 1) == 0:
                session.send(char(no_requirement) + "使用了虹色之环，闪避了死亡！")
                dodge = True
                break
            else:
                session.send(char(no_requirement) + "使用虹色之环闪避失败，死亡时间+1h！")
                hour += 1
        remove_status(qq, 'h', False)
    if not dodge:
        add_limited_status(qq, 'd', datetime.now() + timedelta(hours=hour))

def draw_card(positive=None):
    c = random.choice(list(_card.card_id_dict.values()))
    if positive is not None or len(positive & {-1, 0, 1}) == 0:
        while c.positive not in positive:
            c = random.choice(list(_card.card_id_dict.values()))
    return c
def set_cards(qq, hand_card):
    config.userdata.execute("update dragon_data set card=? where qq=?", (','.join(str(x) for x in hand_card), qq))
def get_card(qq, card=None, node=None):
    s = card or (node or find_or_new(qq))['card']
    return [] if s == '' else [Card(int(x)) for x in s.split(',')]
def throw_card(qq, cards, hand_card=None):
    if hand_card is None:
        hand_card = get_card(qq)
    for c in cards:
        if c not in hand_card:
            return False
        hand_card.remove(c)
    config.userdata.execute("update dragon_data set card=? where qq=?", (','.join(str(c.id) for c in hand_card), qq))
    return True

async def draw(n: int, session: SessionBuffer, qq: int, hand_card, *, no_requirement=False):
    cards = [draw_card() for i in range(n)]
    session.send(char(no_requirement) + '抽到的卡牌是：\n' + '\n'.join(c.full_description for c in cards))
    for c in cards:
        if not c.consumed_on_draw:
            hand_card.append(c)
        r = await c.on_draw(session, qq, hand_card, no_requirement=no_requirement)
        if r:
            session.send('\n' + r)

async def use_card(card, session: SessionBuffer, qq: int, hand_card, *, no_requirement=False):
    session.send(char(no_requirement) + '使用了卡牌：\n' + card.full_description)
    await card.use(session, qq, hand_card, no_requirement=no_requirement)

async def settlement(session: CommandSession, qq: int, to_do, *, no_requirement=False):
    node = find_or_new(qq)
    hand_card = get_card(qq, node=node)
    buf = SessionBuffer(session)
    await to_do(buf, qq, hand_card, no_requirement=no_requirement)
    await buf.flush()
    # discard
    x = len(hand_card) - node['card_limit']
    if x > 0:
        save_data()
        if no_requirement:
            await session.send(f"该玩家手牌已超出上限{x}张！多余的牌已被弃置。")
            hand_card = hand_card[:node['card_limit']]
            set_cards(qq, hand_card)
        else:
            ret2 = f"您的手牌已超出上限{x}张！请先选择一些牌弃置（输入id号，使用空格分隔）：\n" + \
                "\n".join(c.full_description for c in hand_card)
            l = await session.aget("discard_cards",
                prompt=ret2,
                arg_filters=[
                    extractors.extract_text,
                    lambda s: list(map(int, re.findall(r'\d+', str(s)))),
                    validators.fit_size(x, x, message="请输入正确的张数。"),
                    validators.ensure_true(lambda l: throw_card(qq, l, hand_card=hand_card), message="您选择了错误的卡牌！")
                ])
            await session.send("成功弃置。")
    save_data()

async def daily_update():
    global last_update_date
    with open(config.rel('dragon_words.json'), encoding='utf-8') as f:
        d = json.load(f)
    config.userdata.execute('update dragon_data set daily_status=?, today_jibi=10, today_keyword_jibi=10', ('',))
    c = random.choice(d['begin'])
    d['last_update_date'] = last_update_date = date.today().isoformat()
    d['begin'].remove(c)
    if len(d['begin']) == 0:
        for group in config.group_id_dict['logic_dragon_supervise']:
            await get_bot().send_group_msg(group_id=group, message="起始词库已空！")
    with open(config.rel('dragon_words.json'), 'w', encoding='utf-8') as f:
        f.write(json.dumps(d, indent=4, separators=(',', ': '), ensure_ascii=False))
    return "今日关键词：" + c

@on_natural_language(keywords="接", only_to_me=False, only_short_message=False)
async def logical_dragon(session: NLPSession):
    if not await env.test(session):
        return
    match = message_re.match(session.msg_text)
    if match:
        ret = ""
        qq = session.ctx['user_id']
        global past_two_user
        node = find_or_new(qq)
        if check_limited_status(qq, 'd', node) or check_status(qq, 'd', True, node):
            await session.send('你已死，不能接龙！')
            return
        m = check_status(qq, 'm', True, node)
        if m and len(past_two_user) != 0 and qq == past_two_user[1] or not m and qq in past_two_user:
            if check_status(qq, 'p', False, node):
                ret += "\n你触发了极速装置！"
                remove_status(qq, 'p', False, remove_all=False)
            else:
                await session.send(f"你接太快了！两次接龙之间至少要隔{'一' if m else '两'}个人。")
                return
        past_two_user.append(qq)
        if len(past_two_user) > 2:
            past_two_user.pop(0)
        word = match.group(1).strip()
        if word == keyword:
            ret += "\n你接到了奖励词！"
            if node['today_keyword_jibi'] > 0:
                ret += "奖励10击毙。"
                config.userdata.execute("update dragon_data set today_keyword_jibi=? where qq=?", (node['today_keyword_jibi'] - 1, qq))
                add_jibi(qq, 10)
            if update_keyword():
                ret += f"奖励词已更新为：{keyword}。"
            else:
                ret += "奖励词池已空！"
        for i, k in enumerate(hidden_keyword):
            if k in word:
                ret += f"\n你接到了隐藏奖励词{k}！奖励10击毙。"
                add_jibi(qq, 10)
                n = check_global_status('m', False)
                if n:
                    ret += f"\n你触发了存钱罐，奖励+{n * 10}击毙！"
                    remove_global_status('m', False)
                    add_jibi(qq, n * 10)
                if not update_hidden_keyword(i):
                    ret += "隐藏奖励词池已空！"
        if not check_and_add_log(word):
            ret += "\n过去一周之内接过此词，你死了！"
            s = kill(qq)
            if s:
                ret += '\n' + s
        else:
            ret += f"\n成功接龙！接龙词：{word}。"
            if node['today_jibi'] > 0:
                ret += "奖励1击毙。"
                config.userdata.execute("update dragon_data set today_jibi=? where qq=?", (node['today_jibi'] - 1, qq))
                add_jibi(qq, 1)
                if node['today_jibi'] == 1:
                    ret += "\n你今日全勤，奖励1抽奖券！"
                    config.userdata.execute("update dragon_data set draw_time=? where qq=?", (node['draw_time'] + 1, qq))
            if word in bombs:
                ret += "\n你成功触发了炸弹，被炸死了！"
                remove_bomb(word)
                s = kill(qq)
                if s:
                    ret += '\n' + s
        save_data()
        await session.send(ret.strip())

@on_natural_language(only_to_me=False, only_short_message=True)
async def logical_dragon_else(session: NLPSession):
    if not await env.test(session):
        return
    text = session.msg_text.strip()
    # 查询接龙
    if text.startswith("查询接龙"):
        await call_command(get_bot(), session.ctx, ('dragon', 'check'), current_arg=text[4:].strip())
    # 添加炸弹
    elif text.startswith("添加炸弹"):
        await call_command(get_bot(), session.ctx, ('dragon', 'add_bomb'), current_arg=text[4:].strip())
    # 使用手牌
    elif text.startswith("使用手牌"):
        await call_command(get_bot(), session.ctx, ('dragon', 'use_card'), current_arg=text[4:].strip())
    # 抽卡
    elif text.startswith("抽卡"):
        await call_command(get_bot(), session.ctx, ('dragon', 'draw'), current_arg=text[2:].strip())

@on_command(('dragon', 'add_bomb'), aliases="添加炸弹", only_to_me=False, args=("keyword"), environment=env)
async def dragon_add_bomb(session: CommandSession):
    """添加炸弹。"""
    add_bomb(session.current_arg_text.strip())
    save_data()

@on_command(('dragon', 'use_card'), aliases="使用手牌", only_to_me=False, args=("card"), environment=env)
async def dragon_use_card(session: CommandSession):
    """使用手牌。"""
    args = session.current_arg_text.strip()
    if len(args) == 0:
        session.finish("请输入想使用的卡牌！")
    try:
        card = Card(int(args))
    except (ValueError, IndexError):
        card = more_itertools.only([cls for cls in _card.card_id_dict.values() if cls.name == args])
    if card is None:
        session.finish("请输入存在的卡牌id号或卡牌名。")
    qq = session.ctx['user_id']
    hand_card = get_card(qq)
    if card not in hand_card:
        session.finish("你还未拥有这张牌！")
    card = Card(id)
    throw_card(qq, id, hand_card=hand_card)
    await settlement(session, qq, partial(use_card, card))
    save_data()

@on_command(('dragon', 'draw'), only_to_me=False, args=("num"), environment=env)
async def dragon_draw(session: CommandSession):
    """使用抽卡券进行抽卡。"""
    qq = session.ctx['user_id']
    try:
        n = int(session.current_arg_text.strip() or 1)
    except ValueError:
        n = 1
    draw_time = find_or_new(qq)['draw_time']
    ret = ""
    if draw_time < n:
        n = draw_time
        ret += f"您的抽卡券只有{n}张！\n"
    if n == 0:
        session.finish("您没有抽卡券！")
    ret += "您抽到的卡牌是：\n"
    draw_time -= n
    config.userdata.execute('update dragon_data set draw_time=? where qq=?', (draw_time, qq))
    await settlement(session, qq, partial(draw, n))
    save_data()

@on_command(('dragon', 'check'), aliases="查询接龙", only_to_me=False, short_des="查询逻辑接龙相关数据。", args=("name",), environment=env)
async def dragon_check(session: CommandSession):
    """查询逻辑接龙相关数据。可选参数：
    奖励词/keyword：查询当前奖励词。
    奖励池/keyword_pool：查询当前奖励词池大小。
    起始池/begin_pool：查询当前起始词池大小。
    隐藏奖励池/hidden_keyword_pool：查询当前隐藏奖励池大小。
    卡池/card_pool：查询当前卡池总卡数。
    复活时间/recover_time：查询自己的复活时间。
    手牌/hand_cards：查询自己当前手牌。
    击毙/jibi：查询自己的击毙数。"""
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
    node = find_or_new(session.ctx['user_id'])
    if data in ("复活时间", "recover_time"):
        status = eval(node['status_time'])
        if 'd' in status:
            session.finish("你的复活时间为：" + status['d'])
        session.finish("你目前没有复活时间！")
    elif data in ("手牌", "hand_cards"):
        cards = get_card(session.ctx['user_id'])
        if len(cards) == 0:
            session.finish("你没有手牌！")
        session.finish("你的手牌为：\n" + '\n'.join(Card(s).full_description for s in cards))
    elif data in ("击毙", "jibi"):
        session.finish("你的击毙数为：" + str(node['jibi']))

@on_command(('dragon', 'add_begin'), only_to_me=False, environment=env_supervise)
async def dragon_add_begin(session: CommandSession):
    """添加起始词。黑幕群可用。"""
    add_begin(session.current_arg.strip())
    await session.send('成功添加起始词。')

@on_command(('dragon', 'add_hidden'), only_to_me=False, environment=env_supervise)
async def dragon_add_hidden(session: CommandSession):
    """添加隐藏奖励词。黑幕群可用。"""
    add_hidden(session.current_arg_text.strip())
    await session.send('成功添加隐藏奖励词。')

@scheduler.scheduled_job('cron', id="dragon_daily", hour='16', minute='00-03')
async def dragon_daily():
    global last_update_date
    if last_update_date == date.today().isoformat():
        return
    ret = await daily_update()
    for group in config.group_id_dict['logic_dragon_send']:
        await get_bot().send_group_msg(group_id=group, message=ret)

@lru_cache(10)
def Card(id):
    if id in _card.card_id_dict:
        return _card.card_id_dict[id]()
    else:
        return None

class card_meta(type):
    def __new__(cls, clsname, bases, attrs):
        if len(bases) != 0 and 'status_set' in bases[0].__dict__:
            if 'status' in attrs and attrs['status']:
                status = attrs['status']
                if status in bases[0].status_set:
                    raise ImportError
                bases[0].status_set.add(status)
                @classmethod
                async def use(self, session, qq, hand_card, no_requirement=False):
                    add_status(qq, status, False)
                attrs['use'] = use
            elif 'daily_status' in attrs and attrs['daily_status']:
                status = attrs['daily_status']
                if status in bases[0].daily_status_set:
                    raise ImportError
                bases[0].daily_status_set.add(status)
                @classmethod
                async def use(self, session, qq, hand_card, no_requirement=False):
                    add_status(qq, status, True)
                attrs['use'] = use
            elif 'limited_status' in attrs and attrs['limited_status']:
                status = attrs['limited_status']
                if status in bases[0].limited_status_set:
                    raise ImportError
                bases[0].limited_status_set.add(status)
                @classmethod
                async def use(self, session, qq, hand_card, no_requirement=False):
                    add_limited_status(qq, status, datetime.now() + self.limited_time)
                attrs['use'] = use
            elif 'global_status' in attrs and attrs['global_status']:
                status = attrs['global_status']
                if status in bases[0].status_set:
                    raise ImportError
                bases[0].status_set.add(status)
                @classmethod
                async def use(self, session, qq, hand_card, no_requirement=False):
                    add_global_status(status, False)
                attrs['use'] = use
            elif 'global_daily_status' in attrs and attrs['global_daily_status']:
                status = attrs['global_daily_status']
                if status in bases[0].daily_status_set:
                    raise ImportError
                bases[0].daily_status_set.add(status)
                @classmethod
                async def use(self, session, qq, hand_card, no_requirement=False):
                    add_global_status(status, True)
                attrs['use'] = use
            elif 'global_limited_status' in attrs and attrs['global_limited_status']:
                status = attrs['global_limited_status']
                if status in bases[0].limited_status_set:
                    raise ImportError
                bases[0].limited_status_set.add(status)
                @classmethod
                async def use(self, session, qq, hand_card, no_requirement=False):
                    add_global_limited_status(status, datetime.now() + self.global_limited_time)
                attrs['use'] = use
            c = type.__new__(cls, clsname, bases, attrs)
            bases[0].card_id_dict[attrs['id']] = c
        else:
            c = type.__new__(cls, clsname, bases, attrs)
        return c

class _card(metaclass=card_meta):
    card_id_dict = {}
    status_set = {'d'}
    daily_status_set = set()
    limited_status_set = set()
    @property
    # @abstractmethod
    def img(self):
        pass
    name = ""
    id = -1
    positive = 0
    description = ""
    arg_num = 0
    consumed_on_draw = False
    @classmethod
    async def use(cls, session, qq, hand_card, no_requirement=False):
        pass
    @classmethod
    async def on_draw(cls, session, qq, hand_card, no_requirement=False):
        pass
    @property
    def full_description(self):
        return f"{self.id}. {self.name}\n\t{self.description}"

class dabingyichang(_card):
    name = "大病一场"
    id = 30
    daily_status = 'd'
    positive = -1
    description = "抽到时，直到下一次主题出现前不得接龙。"
    consumed_on_draw = True
    @classmethod
    async def on_draw(cls, session, qq, hand_card, no_requirement=False):
        await cls.use(session, qq, hand_card)
        session.send(char(no_requirement) + "病了！直到下一次主题出现前不得接龙。")

class caipiaozhongjiang(_card):
    name = "彩票中奖"
    id = 31
    positive = 1
    description = "抽到时立即获得20击毙与两张牌。"
    consumed_on_draw = True
    @classmethod
    async def on_draw(cls, session, qq, hand_card, no_requirement=False):
        session.send(char(no_requirement) + "中奖了！获得20击毙与两张牌。" + char(no_requirement) + "抽到的牌为：")
        add_jibi(qq, 20)
        await draw(2, session, qq, hand_card, no_requirement=no_requirement)

class wuzhongshengyou(_card):
    name = "无中生有"
    id = 40
    positive = 1
    description = "摸两张牌。"
    @classmethod
    async def use(cls, session, qq, hand_card, no_requirement=False):
        session.send(char(no_requirement) + "抽到的牌为：")
        await draw(2, session, qq, hand_card, no_requirement=no_requirement)

class minus1ma(_card):
    name = "-1马"
    id = 43
    daily_status = 'm'
    positive = 1
    description = "直到下次主题刷新为止，你隔一次就可以接龙。"

class sihuihuibizhiyao(_card):
    name = "死秽回避之药"
    id = 50
    status = 's'
    positive = 1
    description = "你下次死亡时自动消耗10击毙免除死亡。"

class xingyuntujiao(_card):
    name = "幸运兔脚"
    id = 55
    positive = 1
    description = "抽取一张正面卡并立即发动效果。"
    @classmethod
    async def use(cls, session, qq, hand_card, no_requirement=False):
        c = draw_card({1})
        session.send(char(no_requirement) + '抽到并使用了卡牌：\n' + c.full_description)
        await c.use(session, qq, hand_card, no_requirement=no_requirement)

class cunqianguan(_card):
    name = "存钱罐"
    id = 70
    global_status = 'm'
    positive = 0
    description = "下次触发隐藏词的奖励+10击毙。"

class hongsezhihuan(_card):
    name = "虹色之环"
    id = 71
    status = 'h'
    positive = 0
    description = "下次你死亡时，有1/2几率闪避，1/2几率死亡时间+1小时。"

class jisuzhuangzhi(_card):
    name = "极速装置"
    id = 74
    status = 'p'
    positive = 1
    description = '下次你可以连续接龙两次。'

class ComicSans(_card): # TODO
    name = "Comic Sans"
    id = 80
    global_daily_status = 'c'
    positive = 0
    description = "七海千春今天所有生成的图片均使用Comic Sans作为西文字体（中文使用华文彩云）。"

class suicideking(_card):
    name = "自杀之王（♥K）"
    id = 90
    positive = -1
    description = "抽到时立即死亡。"
    consumed_on_draw = True
    @classmethod
    async def on_draw(cls, session, qq, hand_card, no_requirement=False):
        session.send(char(no_requirement) + "抽到了自杀之王，" + char(no_requirement) + "死了！")
        await kill(session, qq, hand_card)

class zhu(_card):
    name = "猪（♠Q）"
    id = 91
    positive = -1
    description = "抽到时损失20击毙（但不会扣至0以下）。"
    consumed_on_draw = True
    @classmethod
    async def on_draw(cls, session, qq, hand_card, no_requirement=False):
        add_jibi(qq, -20)
        session.send(char(no_requirement) + "抽到了猪，损失了20击毙！")

class yang(_card):
    name = "羊（♦J）"
    id = 92
    positive = 1
    description = "抽到时获得20击毙。"
    consumed_on_draw = True
    @classmethod
    async def on_draw(cls, session, qq, hand_card, no_requirement=False):
        add_jibi(qq, 20)
        session.send(char(no_requirement) + "抽到了羊，获得了20击毙！")

class guanggaopai(_card):
    name = "广告牌"
    id = 94
    positive = 0
    consumed_on_draw = True
    @property
    def description(self):
        return random.choice([
            "广告位永久招租，联系邮箱：shedarshian@gmail.com",
            "我给你找了个厂，虹龙洞里挖龙珠的，两班倒，20多金点包酸素勾玉，一天活很多，也不会很闲，明天你就去上班吧，不想看到你整天在群里接龙，无所事事了，是谁我就不在群里指出来了，等下你没面子。\n\t先填个表https://store.steampowered.com/app/1566410",
            "MUASTG，车万原作游戏前沿逆向研究，主要研究弹幕判定、射击火力、ZUN引擎弹幕设计等，曾发表车万顶刊华胥三绝，有意者加群796991184",
            "你想明白生命的意义吗？你想真正……的活着吗？\n\t☑下载战斗天邪鬼：https://pan.baidu.com/s/1FIAxhHIaggld3yRAyFr9FA",
            "肥料掺了金坷垃，一袋能顶两袋撒！肥料掺了金坷垃，不流失，不浪费，不蒸发，能吸收两米下的氮磷钾！",
            "欢迎关注甜品站弹幕研究协会，国内一流的东方STG学术交流平台，从避弹，打分到neta，可以学到各种高端姿势：https://www.isndes.com/ms?m=2"
        ])