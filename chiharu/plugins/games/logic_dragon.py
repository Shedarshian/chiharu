from datetime import datetime, timedelta, date, time
from math import ceil
from os import remove
from collections import Counter
from typing import Dict, List, Set, Tuple, Type, TypedDict, Union, Optional
import itertools, more_itertools
import json, random, re, base64
from PIL import Image, ImageDraw
from io import BytesIO
import requests
from nonebot import CommandSession, NLPSession, on_natural_language, get_bot, permission, scheduler
from nonebot.command import call_command
from nonebot.command.argfilter import extractors, validators
from ..inject import CommandGroup, on_command
from .. import config
from ..config import SessionBuffer
env = config.Environment('logic_dragon')
env_private = config.Environment('logic_dragon', private=True)
env_supervise = config.Environment('logic_dragon_supervise')
env_admin = config.Environment(config.Admin('logic_dragon'))
config.logger.open('dragon')

CommandGroup('dragon', short_des="逻辑接龙相关。", environment=env|env_supervise)

# TODO 十连保底
message_re = re.compile(r"\s*(\d+)([a-z])?\s*接[\s，,]*(.*)[\s，,\n]*.*")

# Version information and changelog
version = "0.3.1"
changelog = """0.3.1 Changelog:
Change:
再次大改结算逻辑。"""

current_event = ""
current_shop = "swim"

class TWords(TypedDict):
    keyword: Tuple[str, List[str]]
    hidden: Tuple[List[str], List[str]]
    begin: List[str]
    bombs: List[str]
    last_update_date: str
with open(config.rel('dragon_words.json'), encoding='utf-8') as f:
    d: TWords = json.load(f)
    keyword = d["keyword"][0]
    hidden_keyword = d["hidden"][0]
    bombs = d["bombs"]
    last_update_date = d["last_update_date"]
    if last_update_date == "2021-09-21":
        current_event = "mid-autumn"
    del d

from .logic_dragon_file import Equipment, Priority, TCounter, TEventListener, TQuest, UserData, UserEvt, global_state, save_global_state, save_data, mission, get_mission, me, Userme, draw_card, Card, _card, Game, User, _status, Tree, StatusNull, StatusDaily, newday_check, _statusnull, _statusdaily, Status, TModule, _equipment, DragonState
from . import logic_dragon_file

# log
log_set : Set[str] = set()
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
def get_yesterday_qq():
    d = date.today() - timedelta(days=1)
    if datetime.now().time() < time(15, 59):
        d -= timedelta(days=1)
    yesterday = rf'log\dragon_log_{d.isoformat()}.txt'
    s = set()
    with open(config.rel(yesterday), encoding='utf-8') as f:
        for line in f.readlines():
            if (match := re.match(r'(\d+)([a-z])?(?:(\+)?<(-?\d+[a-z]?))?(?:/(\d+)/([^/]*)/([^/]*)/)? (.*)', line.strip("\r\n"))) and match.group(5) is not None:
                s.add(int(match.group(5)))
    return s
def check_and_add_log_and_contruct_tree(parent: Tree, word: str, qq: int, kwd: str, hdkwd: str, fork: bool):
    global log_set
    if word in log_set:
        return None
    s = Tree(parent, word, qq, kwd, hdkwd, fork=fork)
    log_set.add(s.word)
    log_file.write(f'{s}\n')
    log_file.flush()
    return s
def rewrite_log_file():
    global log_file
    log_file.close()
    d = date.today()
    if datetime.now().time() < time(15, 59):
        d -= timedelta(days=1)
    today = rf'log\dragon_log_{d.isoformat()}.txt'
    with open(config.rel(today), 'w', encoding='utf-8') as f:
        for node in itertools.chain(*Tree._objs):
            f.write(f'{node}\n')
    log_file = open(config.rel(today), 'a', encoding='utf-8')

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
def update_keyword(d: TWords, if_delete=False):
    global keyword
    s = set(d['keyword'][1]) - log_set - set(bombs)
    if len(s) == 0:
        keyword = ""
        config.logger.dragon << "【LOG】更新关键词失败！"
        return False
    keyword = random.choice(list(s))
    d['keyword'][1].remove(keyword)
    if not if_delete:
        d['keyword'][1].append(d['keyword'][0])
    d['keyword'][0] = keyword
    config.logger.dragon << f"【LOG】关键词更新为：{keyword}。"
    return True
@wrapper_file
def add_hidden_keyword(d: TWords, count=1):
    global hidden_keyword
    if len(d['hidden'][1]) < count:
        config.logger.dragon << "【LOG】隐藏关键词增加失败！"
        return False
    for i in range(count):
        new = random.choice(d['hidden'][1])
        d['hidden'][1].remove(new)
        hidden_keyword.append(new)
        d['hidden'][0].append(new)
    config.logger.dragon << f"【LOG】隐藏关键词更新为：{'，'.join(hidden_keyword)}。"
    return True
@wrapper_file
def remove_hidden_keyword(d: TWords, count=1, if_delete=False):
    global hidden_keyword
    for i in range(count):
        old = hidden_keyword.pop()
        if not if_delete:
            d['hidden'][1].append(old)
        d['hidden'][0].remove(old)
    config.logger.dragon << f"【LOG】隐藏关键词更新为：{'，'.join(hidden_keyword)}。"
    return True
@wrapper_file
def update_hidden_keyword(d: TWords, which, if_delete=False):
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
def remove_bomb(d: TWords, word: str):
    global bombs
    d["bombs"].remove(word)
    bombs.remove(word)
    config.logger.dragon << f"【LOG】移除了炸弹{word}，当前炸弹：{'，'.join(bombs)}。"
@wrapper_file
def remove_all_bomb(d: TWords, p: Optional[float]=None):
    global bombs
    if p is None:
        d["bombs"] = []
        bombs = []
        config.logger.dragon << f"【LOG】移除了所有炸弹。"
    else:
        d["bombs"] = bombs = [bomb for bomb in bombs if random.random() > p]
        config.logger.dragon << f"【LOG】炸弹变成了{'，'.join(bombs)}。"
@wrapper_file
def add_bomb(d: TWords, word: str):
    global bombs
    d["bombs"].append(word)
    bombs.append(word)
    config.logger.dragon << f"【LOG】增加了炸弹{word}，当前炸弹：{'，'.join(bombs)}。"
@wrapper_file
def add_begin(d: TWords, word: str):
    d['begin'].append(word)
    config.logger.dragon << f"【LOG】增加了起始词{word}。"
@wrapper_file
def add_keyword(d: TWords, word: str):
    d['keyword'][1].append(word)
    config.logger.dragon << f"【LOG】增加了起始词{word}。"
@wrapper_file
def add_hidden(d: TWords, word: str):
    d['hidden'][1].append(word)
    config.logger.dragon << f"【LOG】增加了隐藏关键词{word}。"

def cancellation(session):
    def control(value):
        if value.strip() == "取消":
            config.logger.dragon << f"【LOG】用户{session.ctx['user_id']}取消。"
            session.finish("已取消。")
        return value
    return control

async def update_begin_word(is_daily: bool):
    global last_update_date
    with open(config.rel('dragon_words.json'), encoding='utf-8') as f:
        d: TWords = json.load(f)
    c = random.choice(d['begin'])
    if is_daily:
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

@Game.wrapper_noarg
async def daily_update(buf: SessionBuffer) -> str:
    global global_state
    m: TQuest = {}
    for qq, quests in global_state['quest'].items():
        if len(quests) == 0:
            continue
        m[qq] = [{'id': get_mission(), 'remain': 3} for i in quests]
        config.logger.dragon << f"【LOG】更新了用户{qq}的任务为：{[c['id'] for c in m[qq]]}。"
    global_state['quest'] = m
    m: TModule = {}
    for qq, modules in global_state['module'].items():
        if len(modules) == 0:
            continue
        m[qq] = [{'id': random.randint(0, 2), 'remain': 10} for i in modules]
        config.logger.dragon << f"【LOG】更新了用户{qq}的插件为：{[c['id'] for c in m[qq]]}。"
    global_state['module'] = m
    for qq in global_state['steal']:
        config.logger.dragon << f"【LOG】更新了用户{qq}的偷状态。"
        global_state['steal'][qq] = {'time': 0, 'user': []}
    global_state['used_cards'] = []
    global_state['observatory'] = False
    save_global_state()
    if me.check_daily_status('s'):
        await User(config.selfqq, buf).remove_daily_status('s', remove_all=False)
        config.userdata.execute('update dragon_data set today_jibi=10, today_keyword_jibi=10, shop_drawn_card=1, spend_shop=0')
        for r in config.userdata.execute("select qq, daily_status from dragon_data").fetchall():
            if 'd' in r['daily_status']:
                await User(r['qq'], buf).remove_daily_status('d')
    else: #TODO：当个人daily_status中存在'l'时，仅消除负面daily_status及它自身
        config.userdata.execute('update dragon_data set daily_status=?, today_jibi=10, today_keyword_jibi=10, shop_drawn_card=1, spend_shop=0', ('',))
    for r in config.userdata.execute("select qq, status, daily_status, status_time, equipment from dragon_data").fetchall():
        def _(s, st):
            for c in s:
                if "'" + c + "'" in st:
                    return True
            return False
        def _2(s, st):
            for c in s:
                if c in st:
                    return True
            return False
        if (newday_check[0] & set(r['status'])) or (newday_check[1] & set(r['daily_status'])) or _(newday_check[2], r['status_time']) or _2(newday_check[3], r['equipment']):
            user = User(r['qq'], buf)
            # Event OnNewDay
            for eln, n in user.IterAllEventList(UserEvt.OnNewDay, Priority.OnNewDay):
                await eln.OnNewDay(n, user)
    save_data()
    me.reload()
    me._reregister_things()
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
    if not await env_private.test(session):
        return
    text = session.msg_text.strip()
    if text.startswith("【") and text.endswith("】"):
        text = text[1:-1]
    if text.startswith("查询接龙"):
        await call_command(get_bot(), session.ctx, ('dragon', 'check'), current_arg=text[4:].strip())
    elif text.startswith("查询查询"):
        await call_command(get_bot(), session.ctx, ('help'), current_arg="dragon.check")
    elif text.startswith("查询"):
        await call_command(get_bot(), session.ctx, ('dragon', 'check'), current_arg=text[2:].strip())
    elif text.startswith("查看"):
        await call_command(get_bot(), session.ctx, ('dragon', 'check'), current_arg=text[2:].strip())
    elif text.startswith("商店"):
        await call_command(get_bot(), session.ctx, ('dragon', 'check'), current_arg="商店")
    elif text.startswith("活动商店"):
        await call_command(get_bot(), session.ctx, ('dragon', 'check'), current_arg="活动商店")
    if not await env.test(session):
        return
    if text.startswith("使用手牌") and (len(text) == 4 or text[4] == ' '):
        await call_command(get_bot(), session.ctx, ('dragon', 'use_card'), current_arg=text[4:].strip())
    elif text.startswith("使用卡牌") and (len(text) == 4 or text[4] == ' '):
        await call_command(get_bot(), session.ctx, ('dragon', 'use_card'), current_arg=text[4:].strip())
    elif text.startswith("弃牌") and (len(text) == 2 or text[2] == ' '):
        await call_command(get_bot(), session.ctx, ('dragon', 'discard'), current_arg=text[2:].strip())
    elif text.startswith("抽卡") and (len(text) == 2 or text[2] == ' '):
        await call_command(get_bot(), session.ctx, ('dragon', 'draw'), current_arg=text[2:].strip())
    elif text.startswith("购买") and (len(text) == 2 or text[2] == ' '):
        await call_command(get_bot(), session.ctx, ('dragon', 'buy'), current_arg=text[2:].strip())
    elif text.startswith("购买活动") and (len(text) == 4 or text[4] == ' '):
        await call_command(get_bot(), session.ctx, ('dragon', 'buy_event'), current_arg=text[4:].strip())
    elif text.startswith("分叉") and (len(text) == 2 or text[2] == ' '):
        await call_command(get_bot(), session.ctx, ('dragon', 'fork'), current_arg=text[2:].strip())
    elif text.startswith("驳回分叉"):
        await call_command(get_bot(), session.ctx, ('dragon', 'delete'), current_arg="-f " + text[4:].strip())
    elif text.startswith("驳回"):
        await call_command(get_bot(), session.ctx, ('dragon', 'delete'), current_arg=text[2:].strip())

@on_command(('dragon', 'construct'), hide=True, environment=env)
@config.ErrorHandle(config.logger.dragon)
@Game.wrapper
async def dragon_construct(buf: SessionBuffer):
    if buf.current_arg_text.startswith("【") and buf.current_arg_text.endswith("】"):
        match = message_re.match(buf.current_arg_text[1:-1])
    else:
        match = message_re.match(buf.current_arg_text)
    if match:
        qq = buf.ctx['user_id']
        user = User(qq, buf)
        if len(user.data.hand_card) > user.data.card_limit:
            buf.finish("你的手牌超出上限，请先使用或弃牌再接龙！")
        async with user.settlement():
            global global_state
            to_exchange = None
            parent = Tree.find(Tree.match_to_id(match))
            if parent is None:
                await buf.session.send("请输入存在的id号。")
                return
            word: str = match.group(3).strip()
            user.log << f"尝试接龙{word}，母节点id为{parent.id}。"
            if len(parent.childs) != 0 and not parent.fork:
                config.logger.dragon << f"【LOG】节点{parent.id}不可分叉，接龙失败。"
                await buf.session.send(f"节点不可分叉，接龙{word}失败。")
                return
            if parent.fork and len(parent.childs) == 2:
                config.logger.dragon << f"【LOG】节点{parent.id}已分叉，接龙失败。"
                await buf.session.send(f"节点已分叉，接龙{word}失败。")
                return
            dist = 2
            if not buf.state.get('circus'):
                buf.state['circus'] = True
            # Event BeforeDragoned
            dragon_state = DragonState(word, parent)
            for eln, n in user.IterAllEventList(UserEvt.BeforeDragoned, Priority.BeforeDragoned):
                allowed, dist_mod, msg = await eln.BeforeDragoned(n, user, dragon_state)
                if not allowed:
                    buf.send(msg)
                    await buf.flush()
                    return
                dist += dist_mod
            dist = max(dist, 1)
            if qq in parent.get_parent_qq_list(dist):
                # Event CheckSuguri
                for eln, n in user.IterAllEventList(UserEvt.CheckSuguri, Priority.CheckSuguri):
                    allowed, = await eln.CheckSuguri(n, user, dragon_state)
                    if allowed:
                        break
                else:
                    await buf.session.send(f"你接太快了！两次接龙之间至少要隔{dist}个人。")
                    user.log << f"接龙过快，失败。"
                    return
            save_global_state()
            kwd = hdkwd = ""
            if word == keyword:
                user.log << f"接到了奖励词{keyword}。"
                buf.send("你接到了奖励词！", end='')
                kwd = keyword
                jibi_to_add = 0
                if user.data.today_keyword_jibi > 0:
                    user.log << "已拿完今日奖励词击毙。"
                    buf.send("奖励10击毙。")
                    user.data.today_keyword_jibi -= 10
                    jibi_to_add = 10
                else:
                    buf.send("")
                # Event OnKeyword
                for eln, n in user.IterAllEventList(UserEvt.OnKeyword, Priority.OnKeyword):
                    jibi, = await eln.OnKeyword(n, user, word, parent, kwd)
                    jibi_to_add += jibi
                await user.add_jibi(jibi_to_add)
                if update_keyword(if_delete=True):
                    buf.end(f"奖励词已更新为：{keyword}。")
                else:
                    buf.end("奖励词池已空！")
            for i, k in enumerate(hidden_keyword):
                if k in word:
                    hdkwd = k
                    user.log << f"接到了隐藏奖励词{k}。"
                    buf.send(f"你接到了隐藏奖励词{k}！奖励10击毙。")
                    jibi_to_add = 10
                    if not update_hidden_keyword(i, True):
                        buf.end("隐藏奖励词池已空！")
                    # Event OnHiddenKeyword
                    for eln, n in user.IterAllEventList(UserEvt.OnHiddenKeyword, Priority.OnHiddenKeyword):
                        jibi, = await eln.OnHiddenKeyword(n, user, word, parent, hdkwd)
                        jibi_to_add += jibi
                    await user.add_jibi(jibi_to_add)
                    break
            if (tree_node := check_and_add_log_and_contruct_tree(parent, word, qq, kwd=kwd, hdkwd=hdkwd, fork=False)) is None:
                user.log << f"由于过去一周接过此词，死了。"
                buf.send("过去一周之内接过此词，你死了！")
                # Event OnDuplicatedWord
                for eln, n in user.IterAllEventList(UserEvt.OnDuplicatedWord, Priority.OnDuplicatedWord):
                    dodged, = await eln.OnDuplicatedWord(n, user, word)
                    if dodged:
                        break
                else:
                    await user.death()
            else:
                buf.send(f"成功接龙！接龙词：{word}，id为【{tree_node.id_str}】。", end='')
                user.data.last_dragon_time = datetime.now().isoformat()
                if first10 := user.data.today_jibi > 0:
                    user.log << f"仍有{user.data.today_jibi}次奖励机会。"
                    buf.send(f"奖励1击毙。")
                    user.data.today_jibi -= 1
                    await user.add_jibi(1)
                    if user.data.today_jibi == 9:
                        buf.send("你今日首次接龙，奖励1抽奖券！")
                        user.log << f"首次接龙，奖励1抽奖券。"
                        user.data.draw_time += 1
                else:
                    buf.send("")
                if word in bombs:
                    buf.send("你成功触发了炸弹，被炸死了！")
                    user.log << f"触发了炸弹，被炸死了。"
                    remove_bomb(word)
                    # Event OnBombed
                    for eln, n in user.IterAllEventList(UserEvt.OnBombed, Priority.OnBombed):
                        dodged, = await eln.OnBombed(n, user, word)
                        if dodged:
                            break
                    else:
                        await user.death()
                # Event OnDragoned
                for eln, n in user.IterAllEventList(UserEvt.OnDragoned, Priority.OnDragoned):
                    await eln.OnDragoned(n, user, tree_node, first10)
                # if to_exchange is not None:
                #     buf.send(f"你与[CQ:at,qq={to_exchange.qq}]交换了手牌与击毙！")
                #     jibi = (user.data.jibi, to_exchange.data.jibi)
                #     user.log << f"与{to_exchange}交换了手牌与击毙。{qq}击毙为{jibi[0]}，{to_exchange}击毙为{jibi[1]}。"
                #     await user.add_jibi(jibi[1] - jibi[0])
                #     await to_exchange.add_jibi(jibi[0] - jibi[1])
                #     await user.exchange(to_exchange)
                if current_event == "swim" and first10:
                    n = random.randint(1, 6)
                    user.send_log(f"移动了{n}格，", end='')
                    await user.event_move(n)
                    user.send_log(f"现在位于{user.data.event_stage}。")

@on_command(('dragon', 'use_card'), aliases="使用手牌", short_des="使用手牌。", only_to_me=False, args=("card"), environment=env)
@config.ErrorHandle(config.logger.dragon)
@Game.wrapper
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
    user = User(qq, buf)
    if len(user.data.hand_card) > user.data.card_limit:
        buf.session.state['exceed_limit'] = True
    user.log << f"试图使用手牌{card.name}，当前手牌为{user.data.hand_card}。"
    if card not in user.data.hand_card:
        buf.finish("你还未拥有这张牌！")
    # Event OnUserUseCard
    for el, n in user.IterAllEventList(UserEvt.OnUserUseCard, Priority.OnUserUseCard):
        can_use, msg = await el.OnUserUseCard(n, user, card)
        if not can_use:
            buf.finish(msg)
    # if Card(73) in user.data.hand_card and card.id != 73:
    #     buf.finish("你因幸运护符的效果，不可使用其他手牌！")
    if not card.can_use(user, False):
        user.log << f"无法使用卡牌{card.name}。"
        buf.finish(card.failure_message)
    async with user.settlement():
        await user.use_card(card)
        if card.id not in global_state['used_cards']:
            global_state['used_cards'].append(card.id)
    global_state['last_card_user'] = qq
    save_global_state()

@on_command(('dragon', 'use_equipment'), aliases="使用装备", short_des="使用装备。", only_to_me=False, args=("eq"), environment=env)
@config.ErrorHandle(config.logger.dragon)
@Game.wrapper
async def dragon_use_equipment(buf: SessionBuffer):
    """使用装备。
    使用方法为：使用装备 id号"""
    args = buf.current_arg_text.strip()
    if len(args) == 0:
        buf.finish("请输入想使用的卡牌！")
    try:
        eq = Equipment(int(args))
    except (ValueError, IndexError):
        eq = more_itertools.only([cls for cls in _equipment.id_dict.values() if cls.name == args])
    if eq is None:
        buf.finish("请输入存在的装备id号或装备名。")
    qq = buf.ctx['user_id']
    user = User(qq, buf)
    if len(user.data.hand_card) > user.data.card_limit:
        buf.finish("你的手牌超出上限，请先使用或弃牌再使用装备！")
    user.log << f"试图使用装备{eq.name}。"
    if (count := user.data.check_equipment(eq.id)) == 0:
        buf.finish("你还未拥有这个装备！")
    # # Event OnUserUseCard
    # for el, n in user.IterAllEventList(UserEvt.OnUserUseCard, Priority.OnUserUseCard):
    #     can_use, msg = await el.OnUserUseCard(n, user, card)
    #     if not can_use:
    #         buf.finish(msg)
    if not eq.can_use(user):
        user.log << f"无法使用装备{eq.name}。"
        buf.finish(eq.failure_message)
    async with user.settlement():
        await user.use_equipment(eq, count)

@on_command(('dragon', 'discard'), aliases="弃牌", only_to_me=False, short_des="弃牌，只可在手牌超出上限时使用。", args=("card"), environment=env)
@config.ErrorHandle(config.logger.dragon)
@Game.wrapper
async def dragon_discard(buf: SessionBuffer):
    """弃牌，只可在手牌超出上限时使用。
    使用方法为：弃牌 id号（可多个）"""
    args = buf.current_arg_text.strip()
    if len(args) == 0:
        buf.finish("请输入想使用的卡牌！")
    try:
        cards = [Card(int(c)) for c in args.split(' ')]
    except (ValueError, IndexError):
        buf.finish("请输入存在的卡牌id号或卡牌名。")
        return
    qq = buf.ctx['user_id']
    user = User(qq, buf)
    if len(user.data.hand_card) <= user.data.card_limit:
        buf.finish("主动弃牌只可在手牌超出上限时使用！")
    if Card(53) in cards:
        buf.finish("此牌不可弃置！")
    buf.session.state['exceed_limit'] = True
    user.log << f"试图弃牌{[c.name for c in cards]}，当前手牌为{user.data.hand_card}。"
    async with user.settlement():
        user.send_char("弃掉了手牌：\n" + '\n'.join(c.brief_description(qq) for c in cards))
        await user.discard_cards(cards)

@on_command(('dragon', 'draw'), short_des="使用抽卡券进行抽卡。", only_to_me=False, args=("num"), environment=env)
@config.ErrorHandle(config.logger.dragon)
@Game.wrapper
async def dragon_draw(buf: SessionBuffer):
    """使用抽卡券进行抽卡。
    使用方法：抽卡 张数"""
    qq = buf.ctx['user_id']
    try:
        n = int(buf.current_arg_text.strip() or 1)
    except ValueError:
        n = 1
    user = User(qq, buf)
    user.log << f"试图抽卡{n}次。"
    if len(user.data.hand_card) > user.data.card_limit:
        buf.finish("你的手牌超出上限，请先使用或弃牌再抽卡！")
    if user.data.draw_time < n:
        user.log << f"的抽卡券只有{user.data.draw_time}张。"
        n = user.data.draw_time
        buf.send(f"您的抽卡券只有{n}张！\n")
    if n == 0:
        buf.send("您没有抽卡券！")
        await buf.flush()
        return
    user.data.draw_time -= n
    async with user.settlement():
        await user.draw(n)
    save_data()

@on_command(('dragon', 'check'), aliases="查询接龙", only_to_me=False, short_des="查询逻辑接龙相关数据。", args=("name",), environment=env_private)
@config.ErrorHandle(config.logger.dragon)
@Game.wrapper
async def dragon_check(buf: SessionBuffer):
    """查询逻辑接龙相关数据。可选参数：
    奖励词/keyword：查询当前奖励词。
    奖励池/keyword_pool：查询当前奖励词池大小。
    起始池/begin_pool：查询当前起始词池大小。
    隐藏奖励池/hidden_keyword_pool：查询当前隐藏奖励池大小。
    卡池/card_pool：查询当前卡池总卡数。
    活动词/active：查询当前可以接的词。
    复活时间/recover_time：查询自己的复活时间。
    状态/status：查询自己当前状态。
    详细状态/full_status：查询自己当前详细状态。
    全局状态/global_status：查询当前全局状态。
    资料/profile：查询自己当前资料。
    手牌/hand_cards：查询自己当前手牌。
    详细手牌/full_hand_cards：查询自己当前详细手牌。
    装备/equipments：查询自己当前装备。
    任务/quest：查询自己手牌中的任务之石的任务。
    击毙/jibi：查询自己的击毙数。
    商店/shop：查询可购买项目。
    bingo：查询bingo活动进度。"""
    with open(config.rel('dragon_words.json'), encoding='utf-8') as f:
        d = json.load(f)
    def _(d: UserData, qq=None):
        for s, k in Counter(d.status).items():
            yield k, StatusNull(s).des
        for s, k in Counter(d.daily_status).items():
            yield k, StatusDaily(s).des
        for s, k in Counter(d.hand_card).items():
            if s.hold_des:
                yield k, s.hold_des
        for s in d.status_time_checked:
            yield 1, str(s)
    def _brief(d: UserData, qq=None):
        from .logic_dragon_file import brief_f
        for s, k in Counter(d.status).items():
            yield k, StatusNull(s).brief_des
        for s, k in Counter(d.daily_status).items():
            yield k, StatusDaily(s).brief_des
        for s, k in Counter(d.hand_card).items():
            if s.hold_des:
                yield k, brief_f(s.hold_des)
        for s in d.status_time_checked:
            yield 1, s.brief_des
    data = buf.current_arg_text
    qq = buf.ctx['user_id']
    if data in ("奖励词", "keyword"):
        buf.finish("当前奖励词为：" + keyword)
    elif data in ("奖励池", "keyword_pool"):
        buf.finish("当前奖励池大小为：" + str(len(d['keyword'][1])))
    elif data in ("起始池", "begin_pool"):
        buf.finish("当前起始池大小为：" + str(len(d['begin'])))
    elif data in ("隐藏奖励池", "hidden_keyword_pool"):
        buf.finish("当前隐藏奖励池大小为：" + str(len(d['hidden'][1])))
    elif data in ("卡池", "card_pool"):
        buf.finish("当前卡池大小为：" + str(len(_card.card_id_dict)))
    elif data in ("全局状态", "global_status"):
        l = list(_(me))
        ret = '\n'.join((s if k == 1 else f'{k}* ' + s) for k, s in l)
        if ret == '':
            buf.finish("目前没有全局状态！")
        else:
            buf.finish("全局状态为：\n" + ret)
    elif data in ("bingo",):
        from .logic_dragon_file import bingo_checker
        buf.finish("第一个完成一行或一列或一个对角线的玩家，以及第一个全部完成的玩家，将会获得一张超新星作为奖励，总共2张。\n" + bingo_checker.print())
    user = User(qq, buf)
    if data in ("商店", "shop"):
        buf.finish(f"1. (25击毙)从起始词库中刷新一条接龙词。\n2. (1击毙/15分钟)死亡时，可以消耗击毙减少死亡时间。\n3. (70击毙)向起始词库中提交一条词（需审核）。提交时请携带一张图。\n4. ({10 if me.check_daily_status('o') or me.check_daily_status('p') else 35}击毙)回溯一条接龙。\n5. (10击毙)将一条前一段时间内接过的词标记为雷。雷的存在无时间限制，若有人接到此词则立即被炸死。\n6. (5击毙)刷新一组隐藏奖励词。\n7. (50击毙)提交一张卡牌候选（需审核）。请提交卡牌名、来源、与卡牌效果描述。\n8. (5击毙)抽一张卡，每日限一次。" + ("\n9. (24击毙)解除无法战斗状态并以衰弱状态复生" if user.check_limited_status('D') else '') + ("\n16. (5击毙)🎰🎲💰选我抽奖！💰🎲🎰" if me.check_daily_status('O') else ''))
    elif data in ("详细手牌", "full_hand_cards"):
        cards = user.data.hand_card
        if len(cards) == 0:
            buf.finish("你没有手牌！")
        buf.finish("你的手牌为：\n" + '\n'.join(s.full_description(qq) for s in cards))
    elif data in ("手牌", "hand_cards"):
        cards = user.data.hand_card
        if len(cards) == 0:
            buf.finish("你没有手牌！")
        buf.finish("你的手牌为：\n" + '\n'.join(s.brief_description(qq) for s in cards))
    elif data in ("任务", "quest"):
        n = user.data.hand_card.count(Card(67))
        if n == 0:
            buf.finish("你的手牌中没有任务之石！")
        buf.finish("你的任务为：\n" + '\n'.join(Card(67).quest_des(qq) for s in range(n)))
    elif data in ("装备", "equipments"):
        equipments = user.data.equipment
        if len(equipments) == 0:
            buf.finish("你没有手牌！")
        buf.finish("你的装备为：\n" + '\n'.join(Equipment(id).full_description(num, user) for id, num in equipments.items()))
    elif data in ("击毙", "jibi"):
        buf.finish("你的击毙数为：" + str(user.data.jibi))
    elif data in ("详细状态", "full_status"):
        ret = '\n'.join((s if k == 1 else f'{k}* ' + s) for k, s in _(user.data, qq))
        if ret == '':
            buf.finish("你目前没有状态！")
        else:
            buf.finish("你的状态为：\n" + ret)
    elif data in ("状态", "status"):
        ret = '\n'.join((('' if k == 1 else f'{k}* ') + s) for k, s in _brief(user.data, qq))
        if ret == '':
            buf.finish("你目前没有状态！")
        else:
            buf.finish("你的状态为：\n" + ret)
    elif data in ("活动词", "active"):
        words = Tree.get_active()
        m = user.check_daily_status('m')
        i = me.check_daily_status('i')
        I = me.check_daily_status('I')
        M = user.check_daily_status('M')
        dis = max(2 + i - I - m + M, 1)
        buf.finish("当前活动词" + ('🔄' if me.check_daily_status('o') else '♻️' if me.check_daily_status('p') else '') + "为：\n" + '\n'.join(f"{s.word}，{'⚠️' if qq in s.get_parent_qq_list(dis)else ''}id为{s.id_str}" for s in words))
    elif data in ("资料", "profile"):
        buf.finish(f"你的资料为：\n今日剩余获得击毙次数：{user.data.today_jibi}。\n今日剩余获得关键词击毙：{user.data.today_keyword_jibi}。\n剩余抽卡券：{user.data.draw_time}。\n手牌上限：{user.data.card_limit}。" + (f"\n活动pt：{user.data.event_pt}。\n当前在活动第{user.data.event_stage}。" if current_event == "swim" else ""))
    elif data in ("活动商店", "event_shop"):
        if current_shop == "swim":
            b = user.data.check_equipment(0)
            s = user.data.check_equipment(1)
            p = user.data.event_shop
            nt = '\n\t'
            buf.finish(f"1. (75pt){'升星' if b else '购买'}比基尼。（{'不可购买' if s else (f'余{3 - b}次' + ('，拥有学校泳装时不可购买' if b == 0 else ''))}）\n\t{Equipment(0).des_shop}\n2. (75pt){'升星' if s else '购买'}学校泳装。（{'不可购买' if b else (f'余{3 - s}次' + ('，拥有比基尼时不可购买' if s == 0 else ''))}）\n\t{Equipment(1).des_shop}\n3. (75pt)暴食的蜈蚣。（余{1 - p % 2}次）\n4. (50pt)幻想杀手。（余{1 - p // 2}次）\n5. (30pt)抽卡券。")

@on_command(('dragon', 'buy'), aliases="购买", only_to_me=False, short_des="购买逻辑接龙相关商品。", args=("id",), environment=env)
@config.ErrorHandle(config.logger.dragon)
@Game.wrapper
async def dragon_buy(buf: SessionBuffer):
    """购买逻辑接龙相关商品。
    使用方法：购买 id号"""
    try:
        id = int(buf.current_arg_text)
    except ValueError:
        buf.finish("请输入要购买的商品id。")
    qq = buf.ctx['user_id']
    user = User(qq, buf)
    user.log << f"购买商品{id}。"
    if id == 1:
        # (25击毙)从起始词库中刷新一条接龙词。
        if not await user.add_jibi(-25, is_buy=True):
            buf.finish("您的击毙不足！")
        buf.send("您刷新的关键词为：" + await update_begin_word(is_daily=False) + "，id为【0】。")
    elif id == 2:
        # (1击毙/15分钟)死亡时，可以消耗击毙减少死亡时间。
        config.logger.dragon << f"【LOG】询问用户{qq}减少的死亡时间。"
        n = (await buf.aget(prompt="请输入你想要减少的死亡时间，单位为分钟。",
            arg_filters=[
                extractors.extract_text,
                lambda s: list(map(int, re.findall(r'\d+', str(s)))),
                validators.fit_size(1, 1, message="请输入一个自然数。"),
            ]))[0]
        n = ceil(n / 15)
        if (jibi := user.data.jibi) < n:
            buf.send(f"您只有{jibi}击毙！")
            n = jibi
        config.logger.dragon << f"【LOG】用户{qq}使用{n}击毙减少{15 * n}分钟死亡时间。"
        await user.add_jibi(-n, is_buy=True)
        b = user.decrease_death_time(timedelta(minutes=15 * n))
        buf.send(f"您减少了{15 * n}分钟的死亡时间！" + ("您活了！" if b else ""))
    elif id == 3:
        # (70击毙)向起始词库中提交一条词（需审核）。提交时请携带一张图。
        config.logger.dragon << f"【LOG】询问用户{qq}提交起始词与图。"
        s = await buf.aget(prompt="请提交起始词和一张图。（审核不通过不返还击毙），输入取消退出。", arg_filters=[cancellation(buf.session)])
        config.logger.dragon << f"【LOG】用户{qq}提交起始词：{s}。"
        if not await user.add_jibi(-70, is_buy=True):
            buf.finish("您的击毙不足！")
        for group in config.group_id_dict['logic_dragon_supervise']:
            await get_bot().send_group_msg(group_id=group, message=s)
        buf.send("您已成功提交！")
    elif id == 4:
        # (35击毙)回溯一条接龙。首尾接龙时10击毙。
        nodes = Tree.get_active(have_fork=False)
        if len(nodes) == 1:
            to_do = nodes[0]
        else:
            to_do = await buf.aget(prompt="请选择一个节点回溯，输入id号，输入取消退出。\n" + "\n".join(f"{tree.id_str}：{tree.word}" for tree in nodes),
                arg_filters=[
                    extractors.extract_text,
                    cancellation(buf.session),
                    lambda s: list(re.findall(r'\d+[a-z]?', str(s))),
                    validators.fit_size(1, 1, message="请输入一个节点的id号。"),
                    lambda l: Tree.find(Tree.str_to_id(l[0])),
                    validators.ensure_true(lambda s: s is not None, message="请从活动词中选择一个。")
                ])
        if to_do.id == (0, 0):
            buf.send("不可回溯根节点！")
        else:
            cost = -10 if me.check_daily_status('o') or me.check_daily_status('p') else -35
            if not await user.add_jibi(cost, is_buy=True):
                buf.finish("您的击毙不足！")
            to_do.remove()
            buf.send("成功回溯！")
    elif id == 5:
        # (10击毙)将一条前一段时间内接过的词标记为雷。雷的存在无时间限制，若有人接到此词则立即被炸死。
        config.logger.dragon << f"【LOG】询问用户{qq}标记的雷。"
        c = await buf.aget(prompt="请输入标记为雷的词。",
            arg_filters=[
                extractors.extract_text,
                cancellation(buf.session),
                validators.ensure_true(lambda c: c in log_set, message="请输入一周以内接过的词汇。输入取消退出。")
            ])
        config.logger.dragon << f"【LOG】用户{qq}标记{c}为雷。"
        if not await user.add_jibi(-10, is_buy=True):
            buf.finish("您的击毙不足！")
        add_bomb(c)
        buf.send(f"成功添加词汇{c}！")
    elif id == 6:
        # (5击毙)刷新一组隐藏奖励词。
        if not await user.add_jibi(-5, is_buy=True):
            buf.finish("您的击毙不足！")
        update_hidden_keyword(-1)
        buf.send("成功刷新！")
    elif id == 7:
        # (50击毙)提交一张卡牌候选（需审核）。请提交卡牌名、来源、与卡牌效果描述。
        config.logger.dragon << f"【LOG】询问用户{qq}提交的卡牌。"
        s = await buf.aget(prompt="请提交卡牌名、来源、与卡牌效果描述。（审核不通过不返还击毙），输入取消退出。", arg_filters=[cancellation(buf.session)])
        config.logger.dragon << f"【LOG】用户{qq}提交卡牌{s}。"
        if not await user.add_jibi(-50, is_buy=True):
            buf.finish("您的击毙不足！")
        for group in config.group_id_dict['logic_dragon_supervise']:
            await get_bot().send_group_msg(group_id=group, message=s)
        buf.send("您已成功提交！")
    elif id == 8:
        # (5击毙)抽一张卡，每日限一次。
        if user.data.shop_drawn_card <= 0:
            buf.send("您今日已在商店购买过抽卡！")
        else:
            async with user.settlement():
                if not await user.add_jibi(-5, is_buy=True):
                    buf.finish("您的击毙不足！")
                user.data.shop_drawn_card -= 1
                await user.draw(1)
    elif id == 9 and user.check_limited_status('D'):
        #（24击毙）解除无法战斗状态并以衰弱状态复生
        if not await user.add_jibi(-24,is_buy=True):
            buf.finish("您的击毙不足！")
        i = 0
        while i < len(user.data.status_time_checked):
            s = user.data.status_time[i]
            if s.id == 'D':
                user.send_log(f"的无法战斗状态已被解除！")
                await user.remove_limited_status(s)
            i += 1
        user.save_status_time()
        await user.add_limited_status(Status('S')(240))
    elif id == 16 and me.check_daily_status('O'):
        # (5击毙)抽奖
        # 15%几率掉一张卡
        # 30%几率获得1-10击毙
        # 15%几率在过去一周内随机标记一个雷
        # 5%几率抽奖机爆炸击毙抽奖人，抽奖机消失
        # 35%几率什么都不掉
        if not await user.add_jibi(-5, is_buy=True):
            buf.finish("您的击毙不足！")
        r = random.random()
        user.log << f"抽奖机抽到了{r}。"
        if r < 0.15:
            buf.send("🎴🎴🎴恭喜您抽到了卡牌！")
            async with user.settlement():
                await user.draw(1)
        elif r < 0.45:
            p = random.randint(1, 10)
            buf.send(f"💰💰💰恭喜您抽到了{p}击毙！")
            await user.add_jibi(p)
        elif r < 0.6:
            buf.send("💣💣💣恭喜你抽到了雷！")
            buf.send("过去一周的一个随机词汇变成了雷！")
            w = random.choice(list(log_set))
            config.logger.dragon << f"【LOG】{w}被随机标记为雷。"
            add_bomb(w)
        elif r < 0.65:
            buf.send("💥💥💥抽奖机爆炸了！")
            await Userme(user).remove_daily_status('O', remove_all=False)
            await user.death()
        else:
            r = '   '
            while r[0] == r[1] == r[2]:
                r = ''.join(random.choice('🎴💰💣') for i in range(3))
            buf.send(r + "你什么都没有抽到……再来一次吧！")
        save_data()
    await buf.flush()

@on_command(('dragon', 'buy_event'), aliases="购买活动", only_to_me=False, short_des="购买逻辑接龙活动商店相关商品。", args=("id",), environment=env, hide=(current_shop == ''))
@config.ErrorHandle(config.logger.dragon)
@Game.wrapper
async def dragon_buy_event(buf: SessionBuffer):
    """购买逻辑接龙相关商品。
    使用方法：购买活动 id号"""
    if current_shop == '':
        return
    try:
        id = int(buf.current_arg_text)
    except ValueError:
        buf.finish("请输入要购买的商品id。")
    qq = buf.ctx['user_id']
    user = User(qq, buf)
    user.log << f"购买活动商品{id}。"
    if current_shop == 'swim':
        b = user.data.check_equipment(0)
        s = user.data.check_equipment(1)
        if id == 1:
            # （75pt）购买或升星比基尼（拥有学校泳装时不可购买）（余3次）
            if s != 0:
                buf.finish("您已拥有学校泳装，不可购买比基尼！")
            elif b == 3:
                buf.finish("此商品已售罄！")
            if not await user.add_event_pt(-75, is_buy=True):
                buf.finish("您的活动pt不足！")
            user.data.equipment[0] = b + 1
            buf.send(f"您{'购买了1星比基尼' if b == 0 else f'将比基尼升至了{b + 1}星'}！")
        elif id == 2:
            # （75pt）购买或升星学校泳装（拥有比基尼时不可购买）（余3次）
            if b != 0:
                buf.finish("您已拥有比基尼，不可购买学校泳装！")
            elif s == 3:
                buf.finish("此商品已售罄！")
            if not await user.add_event_pt(-75, is_buy=True):
                buf.finish("您的活动pt不足！")
            user.data.equipment[1] = s + 1
            buf.send(f"您{'购买了1星学校泳装' if s == 0 else f'将学校泳装升至了{s + 1}星'}！")
        elif id == 3:
            # （75pt）暴食的蜈蚣（余1次）
            p = user.data.event_shop
            if p % 2 == 1:
                buf.finish("此商品已售罄！")
            if not await user.add_event_pt(-75, is_buy=True):
                buf.finish("您的活动pt不足！")
            user.data.event_shop += 1
            buf.send("您购买了暴食的蜈蚣！")
            async with user.settlement():
                await user.draw(0, cards=[Card(56)])
        elif id == 4:
            # （50pt）幻想杀手（余1次）
            p = user.data.event_shop
            if p // 2 == 1:
                buf.finish("此商品已售罄！")
            if not await user.add_event_pt(-50, is_buy=True):
                buf.finish("您的活动pt不足！")
            user.data.event_shop += 2
            buf.send("您购买了幻想杀手！")
            async with user.settlement():
                await user.draw(0, cards=[Card(120)])
        elif id == 5:
            # （30pt）抽卡券
            if not await user.add_event_pt(-30, is_buy=True):
                buf.finish("您的活动pt不足！")
            user.data.draw_time += 1
            buf.send("您购买了1张抽卡券！")

@on_command(('dragon', 'fork'), aliases="分叉", only_to_me=False, short_des="分叉接龙。", args=("id",), environment=env)
@config.ErrorHandle(config.logger.dragon)
async def dragon_fork(session: CommandSession):
    """分叉接龙。
    使用方法：分叉 id号"""
    match = re.search(r'(\d+)([a-z])?', session.current_arg_text)
    if not match:
        return
    parent = Tree.find(Tree.match_to_id(match))
    if not parent:
        session.finish("请输入存在的id号。")
    parent.fork = True
    config.logger.dragon << f"【LOG】用户{session.ctx['user_id']}将id{parent.id}分叉。"
    session.finish("成功分叉！")

@on_command(('dragon', 'delete'), aliases="驳回", only_to_me=False, short_des="管理可用，驳回节点。", args=("[-f]", "id"), environment=env_admin)
@config.ErrorHandle(config.logger.dragon)
@Game.wrapper
async def dragon_delete(buf: SessionBuffer):
    """管理可用，驳回节点。
    可选参数：
        -f：驳回该节点的分叉。
    可使用：驳回 id 或 驳回分叉 id。"""
    match = re.search(r'(\d+)([a-z])?', buf.current_arg_text)
    node = Tree.find(Tree.match_to_id(match))
    if not node:
        buf.finish("请输入存在的id号。")
    to_delete = None
    f = buf.current_arg_text.strip().startswith('-f')
    if f:
        if len(node.childs) == 2:
            to_delete = node.childs[1]
        node.fork = False
    else:
        to_delete = node
    if await buf.aget(prompt=f"要{f'驳回节点{node.word}的分叉' if f else ''}{'并' if f and to_delete is not None else ''}{f'驳回节点{to_delete.word}' if to_delete is not None else ''}，输入确认继续，输入取消退出。") != "确认":
        buf.finish("已退出。")
    to_delete.remove()
    # 保存到log文件
    rewrite_log_file()
    buf.send("已成功驳回。")
    if not f:
        n = User(node.qq, buf)
        async with n.settlement():
            await n.death()
    else:
        await buf.flush()

@on_command(('dragon', 'add_begin'), only_to_me=False, environment=env_supervise)
@config.ErrorHandle(config.logger.dragon)
async def dragon_add_begin(session: CommandSession):
    """添加起始词。黑幕群可用。"""
    if len(session.current_arg_images) != 1:
        session.finish("请附1张图！")
    url = session.current_arg_images[0]
    response = requests.get(url)
    name = hash(url)
    with open(config.img(f"{name}.jpg"), 'wb') as f:
        f.write(response.content)
    add_begin(session.current_arg_text.strip() + f"[CQ:image,file={name}.jpg]")
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

@on_command(('dragon', 'compensate'), only_to_me=False, environment=env_supervise)
@config.ErrorHandle(config.logger.dragon)
async def dragon_compensate(session: CommandSession):
    """发放超新星作为补偿。
    指令后接qq号，可以用空格连接多个。"""
    qqs = list(map(int, session.current_arg_text.split(' ')))
    buf = SessionBuffer(None, group_id=list(config.group_id_dict['logic_dragon_send'])[0])
    for qq in qqs:
        await User(qq, buf).draw(0, cards=[Card(-65537)])
    await buf.flush()
    save_data()

@on_command(('dragon', 'kill'), only_to_me=False, args=('@s',), environment=env_admin)
@config.ErrorHandle(config.logger.dragon)
@Game.wrapper
async def dragon_kill(buf: SessionBuffer):
    """击毙玩家，管理可用，用于处理驳回。"""
    match = re.search('qq=(\\d+)', buf.current_arg)
    if not match:
        buf.finish("没有@人！")
    qq = match.group(1)
    n = User(qq, buf)
    async with n.settlement():
        await n.death()

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
@config.ErrorHandle(config.logger.dragon)
async def dragon_daily():
    global last_update_date
    config.logger.dragon << f"【LOG】尝试每日更新。"
    if last_update_date == date.today().isoformat():
        return
    graph = Tree.graph()
    # for group in config.group_id_dict['logic_dragon_send']:
    #     await get_bot().send_group_msg(group_id=group, message=[config.cq.text("昨天的接龙图："), config.cq.img(graph)])
    buf = SessionBuffer(None, group_id=list(config.group_id_dict['logic_dragon_send'])[0])
    ret = await daily_update(buf)
    await buf.flush()
    if date.today().isoformat() == "2021-08-01":
        global current_event, current_shop
        current_event = current_shop = "swim"
        ret += "\n泳装活动今天开始！接龙即可获得活动pt，发送“查询活动商店”以及“购买活动 xx”来购买活动商品！"
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
    buf = SessionBuffer(session)
    ret = await daily_update(buf)
    await buf.flush()
    for group in config.group_id_dict['logic_dragon_send']:
        await get_bot().send_group_msg(group_id=group, message=ret)

@on_command(('dragon', 'char'), only_to_me=False, hide=True)
@config.ErrorHandle(config.logger.dragon)
async def dragon_char(session: CommandSession):
    await session.send(f"status: {''.join(sorted(_statusnull.id_dict.keys()))}\ndaily_status: {''.join(sorted(_statusdaily.id_dict.keys()))}\nlimited_status: {''.join(sorted(_status.id_dict.keys()))}")

@on_command(('dragon', 'add_extra'), only_to_me=False, hide=True, permission=permission.SUPERUSER)
@config.ErrorHandle(config.logger.dragon)
async def dragon_add_extra(session: CommandSession):
    if not re.fullmatch("b'.*'", session.current_arg_text):
        session.finish("请输入b'.*'。")
    for t in config.userdata.execute("select qq, extra_data from dragon_data").fetchall():
        config.userdata.execute(f"update dragon_data set extra_data=? where qq=?", (t['extra_data'] + eval(session.current_arg_text), t['qq']))
    save_data()

@on_command(('dragon', 'check_user'), only_to_me=False, hide=True, permission=permission.SUPERUSER)
@config.ErrorHandle(config.logger.dragon)
@Game.wrapper
async def dragon_check_user_data(buf: SessionBuffer):
    qq = int(buf.current_arg_text)
    data = Game.userdata(qq)
    n = {a: b for a, b in data.node.items() if a not in ("extra_data",)}
    buf.send(f"手牌：{', '.join(str(c) for c in data.hand_card)}\nnode：{n}\nextra data：{data.extra}")

@on_command(('dragon', 'op'), only_to_me=False, hide=True, permission=permission.SUPERUSER)
@config.ErrorHandle(config.logger.dragon)
async def dragon_op(session: CommandSession):
    pass

@on_command(('dragon', 'test'), only_to_me=False, hide=True, permission=permission.SUPERUSER)
@config.ErrorHandle(config.logger.dragon)
async def dragon_test(session: CommandSession):
    buf = SessionBuffer(session)
    for r in [1569603950, 1469335215, 1440962524, 3068954061, 1198645569]:
        u = User(r, buf)
        await u.remove_all_limited_status('W')
        if r == 1440962524:
            await u.add_limited_status(Status('W')([]))
            await u.add_limited_status(Status('W')([]))
        await u.add_limited_status(Status('W')([]))
        u.data.save_status_time()
    for r in [1569603950]:
        u = User(r, buf)
        await u.add_limited_status(Status('X')([]))
        u.data.save_status_time()
    save_data()
