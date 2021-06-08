from collections import Counter
from copy import copy
from datetime import datetime, timedelta, date, time
import itertools, more_itertools
import json
import random
import re
from functools import lru_cache, partial, reduce
from nonebot import CommandSession, NLPSession, on_natural_language, get_bot, scheduler
from nonebot.command import call_command
from nonebot.command.argfilter import extractors, validators
from ..inject import CommandGroup, on_command
from .. import config
from ..config import SessionBuffer
env = config.Environment('logic_dragon')
env_supervise = config.Environment('logic_dragon_supervise')
env_admin = config.Environment(config.Admin('logic_dragon'))
config.logger.open('dragon')

CommandGroup('dragon', short_des="逻辑接龙相关。", environment=env|env_supervise)

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

# global_state
# past_two_user : list(int)
# exchange_stack : list(int)
# lianhuan : list(int)
# quest : map(int, list(map('id': int, 'remain': int)))
with open(config.rel('dragon_state.json'), encoding='utf-8') as f:
    global_state = json.load(f)
def save_global_state():
    with open(config.rel('dragon_state.json'), 'w', encoding='utf-8') as f:
        f.write(json.dumps(global_state, indent=4, separators=(',', ': '), ensure_ascii=False))
quest_print_aux = {qq: 0 for qq in global_state['qq'].keys()}

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
async def add_jibi(session, qq, jibi, current_jibi=None):
    if current_jibi is None:
        current_jibi = get_jibi(qq)
    if n := check_status(qq, '2', False):
        jibi *= 2 ** n
        session.send(session.char(qq) + f"触发了{f'{n}次' if n > 1 else ''}变压器的效果，{'获得' if jibi >= 0 else '损失'}击毙加倍为{abs(jibi)}！")
        remove_status(qq, '2', False, remove_all=True)
    config.userdata.execute("update dragon_data set jibi=? where qq=?", (max(0, current_jibi + jibi), qq))
    config.logger.dragon << f"【LOG】玩家原有击毙{current_jibi}，{f'触发了{n}次变压器的效果，' if n > 0 else ''}{'获得' if jibi >= 0 else '损失'}了{abs(jibi)}。"
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
        config.logger.dragon << "【LOG】更新关键词失败！"
        return False
    keyword = random.choice(d['keyword'][1])
    if if_delete:
        d['keyword'][1].remove(keyword)
    d['keyword'][0] = keyword
    config.logger.dragon << f"【LOG】关键词更新为：{keyword}。"
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
        config.logger.dragon << "【LOG】隐藏关键词更新失败！"
        return False
    for i in n:
        hidden_keyword[i] = random.choice(d['hidden'][1])
        if if_delete:
            d['hidden'][1].remove(hidden_keyword[i])
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
    return control

def save_data():
    config.userdata_db.commit()

def add_status(qq, s, is_daily):
    status = find_or_new(qq)['daily_status' if is_daily else 'status']
    if s not in status:
        status += s
        config.userdata.execute('update dragon_data set %s=? where qq=?' % ('daily_status' if is_daily else 'status'), (status, qq))
    config.logger.dragon << f"【LOG】用户{qq}增加了{'每日' if is_daily else '永久'}状态{s}。"
def add_limited_status(qq, s, end_time : datetime):
    status = eval(find_or_new(qq)['status_time'])
    if s not in status:
        status[s] = end_time.isoformat()
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
        if t < datetime.now():
            status.pop('d')
        config.userdata.execute('update dragon_data set status_time=? where qq=?', (str(status), qq))
        return 'd' not in status
    return True

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
    config.logger.dragon << f"【LOG】设置用户手牌为{cards_to_str(hand_card)}。"
def get_card(qq, card=None, node=None):
    s = card or (node or find_or_new(qq))['card']
    return [] if s == '' else [Card(int(x)) for x in s.split(',')]
def check_throw_card(qq, card_ids, hand_card=None):
    if hand_card is None:
        hand_card = get_card(qq)
    if len(card_ids) == 1:
        if Card(card_ids[0]) not in hand_card:
            return False
    else:
        hand_counter = Counter(c.id for c in hand_card)
        hand_counter.subtract(Counter(card_ids))
        if -hand_counter != Counter():
            return False
    return True

# 击杀玩家。
async def kill(session, qq, hand_card, hour=4):
    dodge = False
    config.logger.dragon << f"【LOG】尝试击杀玩家{qq}。"
    if (n := check_status(qq, 's', False)) and not dodge:
        jibi = get_jibi(qq)
        if jibi >= 10 * 2 ** check_status(qq, '2', False):
            await add_jibi(session, qq, -10, jibi)
            session.send(session.char(qq) + "触发了死秽回避之药的效果，免除死亡！")
            config.logger.dragon << f"【LOG】用户{qq}触发了死秽回避之药的效果，免除死亡。"
            dodge = True
            remove_status(qq, 's', False, remove_all=False)
    if (n := check_status(qq, 'h', False)) and not dodge:
        for a in range(n):
            remove_status(qq, 'h', False, remove_all=False)
            if random.randint(0, 1) == 0:
                session.send(session.char(qq) + "使用了虹色之环，闪避了死亡！")
                config.logger.dragon << f"【LOG】用户{qq}触发了虹色之环，闪避了死亡。"
                dodge = True
                break
            else:
                session.send(session.char(qq) + "使用虹色之环闪避失败，死亡时间+1h！")
                config.logger.dragon << f"【LOG】用户{qq}使用虹色之环闪避失败，死亡时间+1h。"
                hour += 1
    if (n := check_status(qq, 'p', False)) and not dodge:
        session.send(session.char(qq) + f"因掠夺者啵噗的效果，死亡时间+{n}h！")
        config.logger.dragon << f"【LOG】用户{qq}因掠夺者啵噗的效果，死亡时间+{n}h。"
        hour += n
    if not dodge:
        add_limited_status(qq, 'd', datetime.now() + timedelta(hours=hour))
        if (x := check_status(qq, 'x', False)):
            remove_status(qq, 'x', False, remove_all=True)
            session.send(session.char(qq) + f"触发了辉夜姬的秘密宝箱！奖励抽卡{x}张。")
            config.logger.dragon << f"【LOG】用户{qq}触发了辉夜姬的秘密宝箱{x}次。"
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
    cards = [draw_card(positive) for i in range(n)] if cards is not None else cards
    session.send(session.char(qq) + '抽到的卡牌是：\n' + '\n'.join(c.full_description(qq) for c in cards))
    config.logger.dragon << f"【LOG】用户{qq}抽到的卡牌为{cards_to_str(cards)}。"
    for c in cards:
        if not c.consumed_on_draw:
            hand_card.append(c)
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
        await card.on_give(session, qq, hand_card, target)
    for card in target_hand_cards:
        await card.on_give(session, target, [], qq)
    hand_card.extend(target_hand_cards)
    set_cards(qq, hand_card)
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
        if buf.active == qq:
            await buf.session.send(f"该玩家手牌已超出上限{x}张！多余的牌已被弃置。")
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

async def update_begin_word():
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
    return c

async def daily_update():
    global global_state
    m = {}
    for qq, quests in global_state['quest']:
        if len(quests) == 0:
            continue
        m[qq] = [{'id': get_mission(), 'remain': 3} for i in quests]
        config.logger.dragon << f"【LOG】更新了用户{qq}的任务为：{[c['id'] for c in m[qq]]}。"
    global_state['quest'] = m
    save_global_state()
    config.userdata.execute('update dragon_data set daily_status=?, today_jibi=10, today_keyword_jibi=10', ('',))
    return "今日关键词：" + await update_begin_word()

@on_natural_language(keywords="接", only_to_me=False, only_short_message=False)
async def logical_dragon(session: NLPSession):
    if not await env.test(session):
        return
    match = message_re.match(session.msg_text)
    if match:
        buf = SessionBuffer(session)
        qq = session.ctx['user_id']
        global global_state
        node = find_or_new(qq)
        to_exchange = None
        if check_limited_status(qq, 'd', node) or check_status(qq, 'd', True, node):
            await session.send('你已死，不能接龙！')
            config.logger.dragon << f"【LOG】用户{qq}已死，接龙失败。"
            return
        m = check_status(qq, 'm', True, node)
        if m and len(global_state['past_two_user']) != 0 and qq == global_state['past_two_user'][1] or not m and qq in global_state['past_two_user']:
            if check_status(qq, 'z', False, node):
                buf.send("你触发了极速装置！")
                config.logger.dragon << f"【LOG】用户{qq}触发了极速装置。"
                remove_status(qq, 'z', False, remove_all=False)
            else:
                await session.send(f"你接太快了！两次接龙之间至少要隔{'一' if m else '两'}个人。")
                config.logger.dragon << f"【LOG】用户{qq}接龙过快，失败。"
                return
        global_state['past_two_user'].append(qq)
        if len(global_state['past_two_user']) > 2:
            global_state['past_two_user'].pop(0)
        save_global_state()
        word = match.group(1).strip()
        config.logger.dragon << f"【LOG】用户{qq}尝试接龙{word}。"
        if word == keyword:
            config.logger.dragon << f"【LOG】用户{qq}接到了奖励词{keyword}。"
            buf.send("你接到了奖励词！", end='')
            if node['today_keyword_jibi'] > 0:
                config.logger.dragon << f"【LOG】用户{qq}已拿完今日奖励词击毙。"
                buf.send("奖励10击毙。", end='')
                config.userdata.execute("update dragon_data set today_keyword_jibi=? where qq=?", (node['today_keyword_jibi'] - 1, qq))
                await add_jibi(buf, qq, 10)
            if update_keyword():
                buf.send(f"奖励词已更新为：{keyword}。")
            else:
                buf.send("奖励词池已空！")
        for i, k in enumerate(hidden_keyword):
            if k in word:
                config.logger.dragon << f"【LOG】用户{qq}接到了隐藏奖励词{k}。"
                buf.send(f"你接到了隐藏奖励词{k}！奖励10击毙。", end='')
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
                    buf.send("隐藏奖励词池已空！")
                break
        if not check_and_add_log(word):
            config.logger.dragon << f"【LOG】用户{qq}由于过去一周接过此词，死了。"
            buf.send("过去一周之内接过此词，你死了！")
            await settlement(buf, qq, kill)
        else:
            buf.send(f"成功接龙！接龙词：{word}。", end='')
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
                if (n := check_status(qq, 'p', False, node)):
                    user = global_state['past_two_user'][0]
                    config.logger.dragon << f"【LOG】用户{qq}触发了{n}次掠夺者啵噗的效果，偷取了{user}击毙。"
                    if (p := get_jibi(user)) > 0:
                        buf.send(f"你从上一名玩家处偷取了{min(n, p)}击毙！")
                        await add_jibi(buf, user, -n)
                        await add_jibi(buf, qq, min(n, p))
                if node['today_jibi'] == 1:
                    buf.send("你今日全勤，奖励1抽奖券！")
                    config.logger.dragon << f"【LOG】用户{qq}全勤，奖励1抽奖券。"
                    config.userdata.execute("update dragon_data set draw_time=? where qq=?", (node['draw_time'] + 1, qq))
            if l := global_state.get('qq'):
                for m in l:
                    if m['remain'] > 0:
                        id, name, func = mission[m['id']]
                        if func(word):
                            buf.send(f"你完成了任务：{name}！奖励3击毙。此任务还可完成{m['remain'] - 1}次。")
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
                buf.send(f"你与{to_exchange}交换了手牌与击毙！")
                jibi = (get_jibi(qq), get_jibi(to_exchange))
                config.logger.dragon << f"【LOG】用户{qq}与{to_exchange}交换了手牌与击毙。{qq}击毙为{jibi[0]}，{to_exchange}击毙为{jibi[1]}。"
                await add_jibi(buf, qq, jibi[1] - jibi[0])
                await add_jibi(buf, to_exchange, jibi[0] - jibi[1])
                await settlement(buf, qq, partial(exchange, target=to_exchange))
        await buf.flush()
        save_data()

@on_natural_language(only_to_me=False, only_short_message=True)
async def logical_dragon_else(session: NLPSession):
    if not await env.test(session):
        return
    text = session.msg_text.strip()
    if text.startswith("查询接龙"):
        await call_command(get_bot(), session.ctx, ('dragon', 'check'), current_arg=text[4:].strip())
    elif text.startswith("添加炸弹"):
        await call_command(get_bot(), session.ctx, ('dragon', 'add_bomb'), current_arg=text[4:].strip())
    elif text.startswith("使用手牌"):
        await call_command(get_bot(), session.ctx, ('dragon', 'use_card'), current_arg=text[4:].strip())
    elif text.startswith("抽卡"):
        await call_command(get_bot(), session.ctx, ('dragon', 'draw'), current_arg=text[2:].strip())
    elif text.startswith("查看手牌"):
        await call_command(get_bot(), session.ctx, ('dragon', 'check'), current_arg="手牌")
    elif text.startswith("商店"):
        await call_command(get_bot(), session.ctx, ('dragon', 'check'), current_arg="商店")
    elif text.startswith("购买"):
        await call_command(get_bot(), session.ctx, ('dragon', 'buy'), current_arg=text[2:].strip())

# @on_command(('dragon', 'add_bomb'), aliases="添加炸弹", only_to_me=False, args=("keyword"), environment=env)
# @config.ErrorHandle
# async def dragon_add_bomb(session: CommandSession):
#     """添加炸弹。"""
#     add_bomb(session.current_arg_text.strip())
#     save_data()

@on_command(('dragon', 'use_card'), aliases="使用手牌", only_to_me=False, args=("card"), environment=env)
@config.ErrorHandle(config.logger.dragon)
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
    config.logger.dragon << f"【LOG】用户{qq}试图使用手牌{card.name}，当前手牌为{hand_card}。"
    if card not in hand_card:
        session.finish("你还未拥有这张牌！")
    if card.id == -1:
        config.logger.dragon << f"【LOG】用户{qq}无法使用卡牌{card.name}。"
        session.finish("此牌不可被使用！")
    hand_card.remove(card)
    set_cards(qq, hand_card)
    save_data()
    buf = SessionBuffer(session)
    await settlement(buf, qq, partial(use_card, card))
    save_data()

@on_command(('dragon', 'draw'), only_to_me=False, args=("num"), environment=env)
@config.ErrorHandle(config.logger.dragon)
async def dragon_draw(session: CommandSession):
    """使用抽卡券进行抽卡。"""
    qq = session.ctx['user_id']
    try:
        n = int(session.current_arg_text.strip() or 1)
    except ValueError:
        n = 1
    config.logger.dragon << f"【LOG】用户{qq}试图抽卡{n}次。"
    draw_time = find_or_new(qq)['draw_time']
    buf = SessionBuffer(session)
    if draw_time < n:
        config.logger.dragon << f"【LOG】用户{qq}的抽卡券只有{draw_time}张。"
        n = draw_time
        buf.send(f"您的抽卡券只有{n}张！\n")
    if n == 0:
        session.finish("您没有抽卡券！")
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
    复活时间/recover_time：查询自己的复活时间。
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
        session.finish("1. (25击毙)从起始词库中刷新一条接龙词。\n2. (1击毙/15分钟)死亡时，可以消耗击毙减少死亡时间。\n3. (70击毙)向起始词库中提交一条词（需审核）。提交时请携带一张图。\n4. (35击毙)回溯一条接龙。\n5. (10击毙)将一条前一段时间内接过的词标记为雷。雷的存在无时间限制，若有人接到此词则立即被炸死。\n6. (5击毙)刷新一组隐藏奖励词。\n7. (50击毙)提交一张卡牌候选（需审核）。请提交卡牌名、来源、与卡牌效果描述。")
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
        session.finish("你的手牌为：\n" + '\n'.join(s.full_description(session.ctx['user_id']) for s in cards))
    elif data in ("击毙", "jibi"):
        session.finish("你的击毙数为：" + str(node['jibi']))

@on_command(('dragon', 'buy'), aliases="购买", only_to_me=False, short_des="购买逻辑接龙相关商品。", args=("id",), environment=env)
@config.ErrorHandle(config.logger.dragon)
async def dragon_buy(session: CommandSession):
    try:
        id = int(session.current_arg_text)
    except ValueError:
        session.finish("请输入要购买的商品id。")
    qq = session.ctx['user_id']
    buf = SessionBuffer(session)
    config.logger.dragon << f"【LOG】用户{qq}购买商品{id}。"
    if id == 1:
        # (25击毙)从起始词库中刷新一条接龙词。
        add_jibi(buf, qq, -25)
        buf.send("您刷新的关键词为：" + await update_begin_word())
    elif id == 2:
        # (1击毙/15分钟)死亡时，可以消耗击毙减少死亡时间。
        config.logger.dragon << f"【LOG】询问用户{qq}减少的死亡时间。"
        n = await buf.aget(prompt="请输入你想要减少的死亡时间。",
            arg_filters=[
                extractors.extract_text,
                lambda s: list(map(int, re.findall(r'\d+', str(s)))),
                validators.fit_size(1, 1, message="请输入一个自然数。"),
            ])[0]
        n //= 15
        if (jibi := get_jibi(qq)) < n:
            buf.send(f"您只有{jibi}击毙！")
            n = jibi
        config.logger.dragon << f"【LOG】用户{qq}使用{n}击毙减少{15 * n}分钟死亡时间。"
        add_jibi(buf, qq, -n)
        b = decrease_death_time(qq, timedelta(minutes=15 * n))
        buf.send(f"您减少了{15 * n}分钟的死亡时间！" + ("您活了！" if b else ""))
    elif id == 3:
        # (70击毙)向起始词库中提交一条词（需审核）。提交时请携带一张图。
        config.logger.dragon << f"【LOG】询问用户{qq}提交起始词与图。"
        s = await buf.aget(prompt="请提交起始词和一张图。（审核不通过不返还击毙），输入取消退出。", arg_filter=[cancellation(session)])
        config.logger.dragon << f"【LOG】用户{qq}提交起始词：{s}。"
        add_jibi(buf, qq, -70)
        for group in config.group_id_dict['dragon_supervise']:
            await get_bot().send_group_msg(group_id=group, message=s)
        buf.send("您已成功提交！")
    elif id == 4:
        # (35击毙)回溯一条接龙。
        add_jibi(buf, qq, -35)
        buf.send("成功回溯！")
    elif id == 5:
        # (10击毙)将一条前一段时间内接过的词标记为雷。雷的存在无时间限制，若有人接到此词则立即被炸死。
        config.logger.dragon << f"【LOG】询问用户{qq}标记的雷。"
        c = await buf.aget(prompt="请输入标记为雷的词。",
            arg_filters=[
                extractors.extract_text,
                validators.ensure_true(lambda c: c in log_set, message="请输入一周以内接过的词汇。输入取消退出。"),
                cancellation(session)
            ])
        config.logger.dragon << f"【LOG】用户{qq}标记{c}为雷。"
        add_jibi(buf, qq, -10)
        add_bomb(c)
        buf.send(f"成功添加词汇{c}！")
    elif id == 6:
        # (5击毙)刷新一组隐藏奖励词。
        add_jibi(buf, qq, -5)
        update_hidden_keyword(-1)
        buf.send("成功刷新！")
    elif id == 7:
        # (50击毙)提交一张卡牌候选（需审核）。请提交卡牌名、来源、与卡牌效果描述。
        config.logger.dragon << f"【LOG】询问用户{qq}提交的卡牌。"
        s = await buf.aget(prompt="请提交卡牌名、来源、与卡牌效果描述。（审核不通过不返还击毙），输入取消退出。", arg_filter=[cancellation(session)])
        config.logger.dragon << f"【LOG】用户{qq}提交卡牌{s}。"
        add_jibi(buf, qq, -50)
        for group in config.group_id_dict['dragon_supervise']:
            await get_bot().send_group_msg(group_id=group, message=s)
        buf.send("您已成功提交！")
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
async def dragon_kill(session: CommandSession):
    match = re.search('qq=(\\d+)', session.current_arg)
    if not match:
        session.finish("没有@人！")
    qq = match.group(1)
    buf = SessionBuffer(session)
    await settlement(buf, qq, kill)

# @on_command(('dragon', 'add_draw'), only_to_me=False, environment=env_supervise)
# @config.ErrorHandle
# async def _(session: CommandSession):
#     qq = session.ctx['user_id']
#     node = find_or_new(qq)
#     config.userdata.execute("update dragon_data set draw_time=? where qq=?", (node['draw_time'] + int(session.current_arg_text), qq)) 

@scheduler.scheduled_job('cron', id="dragon_daily", hour='16', minute='00-03')
async def dragon_daily():
    global last_update_date
    config.logger.dragon << f"【LOG】尝试每日更新。"
    if last_update_date == date.today().isoformat():
        return
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
        if len(bases) != 0 and 'status_set' in bases[0].__dict__:
            if 'status' in attrs and attrs['status']:
                status = attrs['status']
                bases[0].add_status(status)
                @classmethod
                async def use(self, session, qq, hand_card):
                    add_status(qq, status, False)
                attrs['use'] = use
            elif 'daily_status' in attrs and attrs['daily_status']:
                status = attrs['daily_status']
                bases[0].add_daily_status(status)
                @classmethod
                async def use(self, session, qq, hand_card):
                    add_status(qq, status, True)
                attrs['use'] = use
            elif 'limited_status' in attrs and attrs['limited_status']:
                status = attrs['limited_status']
                bases[0].add_limited_status(status)
                @classmethod
                async def use(self, session, qq, hand_card):
                    add_limited_status(qq, status, datetime.now() + self.limited_time)
                attrs['use'] = use
            elif 'global_status' in attrs and attrs['global_status']:
                status = attrs['global_status']
                bases[0].add_status(status)
                @classmethod
                async def use(self, session, qq, hand_card):
                    add_global_status(status, False)
                attrs['use'] = use
            elif 'global_daily_status' in attrs and attrs['global_daily_status']:
                status = attrs['global_daily_status']
                bases[0].add_daily_status(status)
                @classmethod
                async def use(self, session, qq, hand_card):
                    add_global_status(status, True)
                attrs['use'] = use
            elif 'global_limited_status' in attrs and attrs['global_limited_status']:
                status = attrs['global_limited_status']
                bases[0].add_limited_status(status)
                @classmethod
                async def use(self, session, qq, hand_card):
                    add_global_limited_status(status, datetime.now() + self.global_limited_time)
                attrs['use'] = use
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
    status_set = {'d'}
    daily_status_set = set()
    limited_status_set = {'d'}
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
    async def on_give(cls, session, qq, hand_card, target):
        pass
    @classmethod
    def add_daily_status(cls, s):
        if s in cls.daily_status_set:
            raise ImportError
        cls.daily_status_set.add(s)
    @classmethod
    def add_status(cls, s):
        if s in cls.status_set:
            raise ImportError
        cls.status_set.add(s)
    @classmethod
    def add_limited_status(cls, s):
        if s in cls.limited_status_set:
            raise ImportError
        cls.limited_status_set.add(s)
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
_card.add_daily_status('d')

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
    description = "指定至多两名玩家进入连环状态。任何处于连环状态的玩家被击毙时所有连环状态的玩家也被击毙并失去此效果。也可用于解除至多两人的连环状态。"
    @classmethod
    async def use(cls, session, qq, hand_card):
        await session.flush()
        config.logger.dragon << f"【LOG】询问用户{qq}铁索连环。"
        l = await session.aget(prompt="请at群内至多两名玩家进行铁索连环。\n",
            arg_filters=[
                    lambda s: [r.group(1) for r in re.findall(r'qq=(\d+)', str(s))],
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
    positive = 1
    description = "你下次死亡时自动消耗10击毙免除死亡。"

class huiye(_card):
    name = "辉夜姬的秘密宝箱"
    id = 52
    status = 'x'
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
    positive = 0
    description = "修改当前规则至首尾接龙直至下次刷新。首尾接龙时，每个汉语词必须至少包含3个汉字，英语词必须至少包含4个字母。"

class queststone(_card):
    name = "任务之石"
    id = 67
    positive = 1
    description = "持有此石时，你每天会刷新一个接龙任务。每次完成接龙任务可以获得3击毙，每天最多3次。使用将丢弃此石。"
    @classmethod
    def full_description(cls, qq):
        m = mission[global_state['quest'][qq][quest_print_aux[qq]]['id']][1]
        remain = global_state['quest'][qq][quest_print_aux[qq]]['remain']
        quest_print_aux[qq] += 1
        if quest_print_aux[qq] >= len(mission):
            quest_print_aux[qq] = 0
        return super().full_description(qq) + "\n\t当前任务：" + m + f"剩余{remain}次。"
    @classmethod
    async def on_draw(cls, session, qq, hand_card):
        if qq not in global_state['quest']:
            global_state['quest'][qq] = []
        global_state['quest'][qq].append({'id': (i := get_mission()), 'remain': 3})
        config.logger.dragon << f"【LOG】用户{qq}刷新了一个任务{mission[i][1]}，现有任务：{[mission[c['id']][1] for c in global_state['quest'][qq]]}。"
        save_global_state()
    @classmethod
    async def on_discard(cls, session, qq, hand_card):
        del global_state['quest'][qq][quest_print_aux[qq]]
        if quest_print_aux[qq] >= len(mission):
            quest_print_aux[qq] = 0
        config.logger.dragon << f"【LOG】用户{qq}删除了一个任务{mission[i][1]}，现有任务：{[mission[c['id']][1] for c in global_state['quest'][qq]]}。"
        save_global_state()
    @classmethod
    async def on_give(cls, session, qq, hand_card, target):
        m = global_state['quest'][qq][quest_print_aux[qq]]
        del global_state['quest'][qq][quest_print_aux[qq]]
        if quest_print_aux[qq] >= len(mission):
            quest_print_aux[qq] = 0
        config.logger.dragon << f"【LOG】用户{qq}删除了一个任务{mission[i][1]}，现有任务：{[mission[c['id']][1] for c in global_state['quest'][qq]]}。"
        global_state['quest'][target].append(m)
        config.logger.dragon << f"【LOG】用户{target}增加了一个任务{mission[i][1]}，现有任务：{[mission[c['id']][1] for c in global_state['quest'][qq]]}。"
        save_global_state()

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
        all_cards = list(itertools.chain(*(c for q, c in l)))
        random.shuffle(all_cards)
        hand_card.clear()
        for q, c in l:
            if (n := len(c)):
                if qq == q:
                    hand_card.extend(all_cards[:n])
                set_cards(q, all_cards[:n])
                config.logger.dragon << f"【LOG】{q}交换后的手牌为：{cards_to_str(all_cards[:n])}。"
                all_cards = all_cards[n:]
        if len(hand_card) != 0:
            session.send("通过交换，你获得了手牌：\n" + '\n'.join(c.full_description(qq) for c in hand_card))
        else:
            session.send("你交换了大家的手牌！")

class xingyunhufu(_card):
    name = "幸运护符"
    id = 73
    positive = 1
    description = "持有此卡时，你无法使用其他卡牌。你每进行两次接龙额外获得一个击毙（每天上限为5击毙）。使用将丢弃这张卡。"
    @classmethod
    async def on_draw(cls, session, qq, hand_card):
        add_status(qq, 'y', False)
    @classmethod
    async def on_discard(cls, session, qq, hand_card):
        remove_status(qq, 'y', False)
    @classmethod
    async def on_give(cls, session, qq, hand_card, target):
        remove_status(qq, 'y', False)
        add_status(target, 'y', False)
_card.add_status('y')

class jisuzhuangzhi(_card):
    name = "极速装置"
    id = 74
    status = 'z'
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
    description = "持有此卡时，你死亡时间增加1小时。每天你因接龙获得1击毙时，可从你所接龙的人处偷取1击毙。若目标没有击毙则不可偷取。使用将丢弃这张卡。"
    @classmethod
    async def on_draw(cls, session, qq, hand_card):
        add_status(qq, 'p', False)
    @classmethod
    async def on_discard(cls, session, qq, hand_card):
        remove_status(qq, 'p', False)
    @classmethod
    async def on_give(cls, session, qq, hand_card, target):
        remove_status(qq, 'p', False)
        add_status(target, 'p', False)
_card.add_status('p')

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

from pypinyin import pinyin, Style

mission = []
def add_mission(doc):
    def _(f):
        global mission
        mission.append((len(mission), doc, f))
        return f
def get_mission():
    return random.randint(0, len(mission) - 1)

for i in range(2, 9):
    add_mission(f"字数为{i}。")(lambda s: len([c for c in s if c != ' ']) == i)
add_mission("包含一个非佛经大数的数字。")(lambda s: len(set(s) & set('0123456789零一二三四五六七八九十百千万亿壹贰叁肆伍陆柒捌玖拾佰仟')) != 0)
add_mission("包含一个常用的人称代词。")(lambda s: len(set(s) & set('我你他她它祂您怹咱俺恁')) != 0)
@add_mission("包含一个中国的省级行政单位的全称。")
def _(s):
    for c in ("黑龙江", "吉林", "辽宁", "河北", "河南", "山东", "山西", "安徽", "江西", "江苏", "浙江", "福建", "台湾", "广东", "湖南", "湖北", "海南", "云南", "贵州", "四川", "青海", "甘肃", "陕西", "内蒙古自治区", "新疆维吾尔自治区", "广西壮族自治区", "宁夏回族自治区", "西藏自治区", "北京", "天津", "上海", "重庆", "香港特别行政区", "澳门特别行政区"):
        if c in s:
            return True
    return False
add_mission("包含的/地/得。")(lambda s: len(set(s) & set('的地得')) != 0)
add_mission("包含叠字。")(lambda s: any(a == b and ord(a) > 255 for a, b in more_itertools.windowed(s, 2)))
for c in ("人", "大", "小", "方", "龙"):
    add_mission(f"包含“{c}”。")(lambda s: c in s)
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
