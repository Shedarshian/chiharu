from datetime import datetime, timedelta, date, time
import itertools, more_itertools
import json, random, re
from PIL import Image, ImageDraw
from nonebot import CommandSession, NLPSession, on_natural_language, get_bot, permission, scheduler
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
message_re = re.compile(r"\s*(\d+)([a-z])?\s*接[\s，,]*(.*)[\s，,\n]*.*")

# Version information and changelog
version = "0.3.0"
changelog = """0.3.0 Changelog:
Change:
大改结算逻辑。"""

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
        if value.strip() == "取消":
            config.logger.dragon << f"【LOG】用户{session.ctx['user_id']}取消。"
            session.finish("已取消。")
        return value
    return control

from .logic_dragon_file import global_state, save_global_state, save_data, mission, get_mission, User, me, draw_card, Card, _card
from . import logic_dragon_file

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
    config.userdata.execute('update dragon_data set daily_status=?, today_jibi=10, today_keyword_jibi=10, shop_drawn_card=0, spend_shop=0', ('',))
    save_data()
    me.reload()
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
        user = User(qq, buf)
        global global_state
        to_exchange = None
        if user.check_limited_status('d') or user.check_daily_status('d'):
            await buf.session.send('你已死，不能接龙！')
            user.log << f"已死，接龙失败。"
            return
        parent = Tree.find(Tree.match_to_id(match))
        if not parent:
            await buf.session.send("请输入存在的id号。")
            return
        word = match.group(3).strip()
        user.log << f"尝试接龙{word}，母节点id为{parent.id}。"
        if len(parent.childs) != 0 and not parent.fork:
            config.logger.dragon << f"【LOG】节点{parent.id}不可分叉，接龙失败。"
            await buf.session.send(f"节点不可分叉，接龙{word}失败。")
            return
        if parent.fork and len(parent.childs) == 2:
            config.logger.dragon << f"【LOG】节点{parent.id}已分叉，接龙失败。"
            await buf.session.send(f"节点已分叉，接龙{word}失败。")
            return
        if me.check_daily_status('o'):
            if parent.word != '' and word != '' and parent.word[-1] != word[0]:
                await buf.session.send("当前规则为首尾接龙，接龙失败。")
                return
        m = user.check_daily_status('m')
        if m and qq == parent.qq or not m and (qq == parent.qq or parent.parent is not None and qq == parent.parent.qq):
            if user.check_status('z'):
                buf.send("你触发了极速装置！")
                user.log << f"触发了极速装置。"
                user.remove_status('z', remove_all=False)
            else:
                await buf.session.send(f"你接太快了！两次接龙之间至少要隔{'一' if m else '两'}个人。")
                user.log << f"接龙过快，失败。"
                return
        save_global_state()
        kwd = hdkwd = ""
        if word == keyword:
            user.log << f"接到了奖励词{keyword}。"
            buf.send("你接到了奖励词！", end='')
            kwd = keyword
            if user.today_keyword_jibi > 0:
                user.log << "已拿完今日奖励词击毙。"
                buf.send("奖励10击毙。")
                config.userdata.execute("update dragon_data set today_keyword_jibi=? where qq=?", (user.today_keyword_jibi - 10, qq))
                user.reload()
                await user.add_jibi(10)
            else:
                buf.send("")
            if update_keyword(if_delete=True):
                buf.end(f"奖励词已更新为：{keyword}。")
            else:
                buf.end("奖励词池已空！")
        for i, k in enumerate(hidden_keyword):
            if k in word:
                hdkwd = k
                user.log << f"接到了隐藏奖励词{k}。"
                buf.send(f"你接到了隐藏奖励词{k}！奖励10击毙。")
                await user.add_jibi(10)
                n = me.check_status('m')
                if n:
                    user.log << f"触发了存钱罐{n}次。"
                    buf.send(f"\n你触发了存钱罐，奖励+{n * 10}击毙！")
                    me.remove_status('m')
                    await user.add_jibi(n * 10)
                if global_state['exchange_stack']:
                    to_exchange = User(global_state['exchange_stack'].pop(-1), buf)
                    user.log << f"触发了互相交换，来自{to_exchange.qq}。"
                    save_global_state()
                if not update_hidden_keyword(i, True):
                    buf.end("隐藏奖励词池已空！")
                break
        fork = False
        if (n := me.check_daily_status('b')):
            fork = random.random() > 0.95 ** n
        if not (tree_node := check_and_add_log_and_contruct_tree(parent, word, qq, kwd=kwd, hdkwd=hdkwd, fork=fork)):
            user.log << f"由于过去一周接过此词，死了。"
            buf.send("过去一周之内接过此词，你死了！")
            if user.check_daily_status('Y'):
                user.log << f"触发了IX - 隐者的效果，没死。"
                buf.send_char("触发了IX - 隐者的效果，没死。")
            else:
                await user.settlement(buf, qq, user.kill())
        else:
            buf.send(f"成功接龙！接龙词：{word}，id为【{tree_node.id_str}】。", end='')
            if user.today_jibi > 0:
                user.log << f"仍有{user.today_jibi}次奖励机会。"
                jibi_to_add = 1
                if (n := user.check_status('y')) and user.today_jibi % 2 == 1:
                    user.log << f"触发了幸运护符{n}次。"
                    jibi_to_add += n
                    buf.send("\n你因为幸运护符的效果，", end='')
                buf.send(f"奖励{jibi_to_add}击毙。")
                config.userdata.execute("update dragon_data set today_jibi=? where qq=?", (user.today_jibi - 1, qq))
                user.reload()
                await user.add_jibi(jibi_to_add)
                if user.today_jibi == 1:
                    buf.send("你今日全勤，奖励1抽奖券！")
                    user.log << f"全勤，奖励1抽奖券。"
                    config.userdata.execute("update dragon_data set draw_time=? where qq=?", (user.draw_time + 1, qq))
                    user.reload()
            else:
                buf.send("")
            if (n := user.check_status('p')):
                last_qq = parent.qq
                last = User(last_qq, buf)
                if last_qq not in global_state['steal'][str(qq)]['user'] and global_state['steal'][str(qq)]['time'] < 10:
                    global_state['steal'][str(qq)]['time'] += 1
                    global_state['steal'][str(qq)]['user'].append(last_qq)
                    save_global_state()
                    user.log << f"触发了{n}次掠夺者啵噗的效果，偷取了{last_qq}击毙，剩余偷取次数{9 - global_state['steal'][str(qq)]['time']}。"
                    if (p := last.jibi) > 0:
                        buf.send(f"你从上一名玩家处偷取了{min(n, p)}击毙！")
                        await last.add_jibi(-n)
                        await user.add_jibi(min(n, p))
            if fork:
                buf.send("你触发了Fork Bomb，此词变成了分叉点！")
            if l := global_state['quest'].get(str(qq)):
                for m in l:
                    if m['remain'] > 0:
                        id, name, func = mission[m['id']]
                        if func(word):
                            buf.send(f"你完成了任务：{name[:-1]}！奖励3击毙。此任务还可完成{m['remain'] - 1}次。")
                            user.log << f"完成了一次任务{name}，剩余{m['remain'] - 1}次。"
                            m['remain'] -= 1
                            await user.add_jibi(3)
                            save_global_state()
                            break
            if word in bombs:
                buf.send("你成功触发了炸弹，被炸死了！")
                user.log << f"触发了炸弹，被炸死了。"
                remove_bomb(word)
                if user.check_daily_status('Y'):
                    user.log << f"触发了IX - 隐者的效果，没死。"
                    buf.send_char("触发了IX - 隐者的效果，没死。")
                else:
                    await user.settlement(user.kill())
            if (n := me.check_status('+')):
                me.remove_status('+')
                buf.send(f"你触发了{n}次+2的效果，摸{n}张非正面牌与{n}张非负面牌！")
                user.log << f"触发了+2的效果。"
                cards = list(itertools.chain(*[[draw_card({-1, 0}), draw_card({0, 1})] for i in range(n)]))
                await user.settlement(user.draw(0, cards=cards))
            if to_exchange is not None:
                buf.send(f"你与[CQ:at,qq={to_exchange.qq}]交换了手牌与击毙！")
                jibi = (user.jibi, to_exchange.jibi)
                user.log << f"与{to_exchange}交换了手牌与击毙。{qq}击毙为{jibi[0]}，{to_exchange}击毙为{jibi[1]}。"
                await user.add_jibi(jibi[1] - jibi[0])
                await to_exchange.add_jibi(jibi[0] - jibi[1])
                await user.settlement(user.exchange(to_exchange))
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
    user = User(qq, buf)
    user.log << f"试图使用手牌{card.name}，当前手牌为{user.hand_card}。"
    if card not in user.hand_card:
        buf.finish("你还未拥有这张牌！")
    if card.id == -1:
        user.log << f"无法使用卡牌{card.name}。"
        buf.finish("此牌不可被使用！")
    global_state['last_card_user'] = qq
    save_global_state()
    user.hand_card.remove(card)
    user.set_cards()
    save_data()
    await user.settlement(user.use_card(card))
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
    user = User(qq, buf)
    user.log << f"试图抽卡{n}次。"
    draw_time = user.draw_time
    if draw_time < n:
        user.log << f"的抽卡券只有{draw_time}张。"
        n = draw_time
        buf.send(f"您的抽卡券只有{n}张！\n")
    if n == 0:
        buf.send("您没有抽卡券！")
        await buf.flush()
        return
    draw_time -= n
    config.userdata.execute('update dragon_data set draw_time=? where qq=?', (draw_time, qq))
    user.reload()
    await user.settlement(user.draw(n))
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
    buf = SessionBuffer(session)
    user = User(qq, buf)
    if data in ("复活时间", "recover_time"):
        time = user.get_limited_time('d')
        if time is None:
            session.finish("你目前没有复活时间！")
        else:
            session.finish(f"你的复活时间为：{time}分钟。")
    elif data in ("手牌", "hand_cards"):
        cards = user.hand_card
        if len(cards) == 0:
            session.finish("你没有手牌！")
        session.finish("你的手牌为：\n" + '\n'.join(s.full_description(qq) for s in cards))
    elif data in ("击毙", "jibi"):
        session.finish("你的击毙数为：" + str(user.jibi))
    elif data in ("状态", "status"):
        status = user.status
        daily_status = user.daily_status
        status_time = eval(user.status_time)
        def _():
            for s in status:
                yield _card.status_dict[s]
            for s in daily_status:
                yield _card.daily_status_dict[s]
            for key in status_time:
                time = user.get_limited_time(key)
                if time is not None:
                    yield f"{_card.limited_status_dict[key]}\n\t结束时间：{time}分钟。"
            if qq in global_state['lianhuan']:
                yield logic_dragon_file.tiesuolianhuan.status_des
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
        m = user.check_daily_status('m')
        session.finish("当前活动词为：\n" + '\n'.join(f"{s.word}，{'⚠️' if s.qq == qq or s.parent is not None and s.parent.qq == qq and not m else ''}id为{s.id_str}" for s in words))
    elif data in ("资料", "profile"):
        session.finish(f"你的资料为：\n今日剩余获得击毙次数：{user.today_jibi}。\n今日剩余获得关键词击毙：{user.today_keyword_jibi}。\n剩余抽卡券：{user.draw_time}。\n手牌上限：{user.card_limit}。")

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
    user = User(qq, buf)
    user.log << f"购买商品{id}。"
    if id == 1:
        # (25击毙)从起始词库中刷新一条接龙词。
        await user.add_jibi(-25, is_buy=True)
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
        if (jibi := user.jibi) < n:
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
        await user.add_jibi(-70, is_buy=True)
        for group in config.group_id_dict['logic_dragon_supervise']:
            await get_bot().send_group_msg(group_id=group, message=s)
        buf.send("您已成功提交！")
    elif id == 4:
        # (35击毙)回溯一条接龙。
        await user.add_jibi(-35, is_buy=True)
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
        await user.add_jibi(-10, is_buy=True)
        add_bomb(c)
        buf.send(f"成功添加词汇{c}！")
    elif id == 6:
        # (5击毙)刷新一组隐藏奖励词。
        await user.add_jibi(-5, is_buy=True)
        update_hidden_keyword(-1)
        buf.send("成功刷新！")
    elif id == 7:
        # (50击毙)提交一张卡牌候选（需审核）。请提交卡牌名、来源、与卡牌效果描述。
        config.logger.dragon << f"【LOG】询问用户{qq}提交的卡牌。"
        s = await buf.aget(prompt="请提交卡牌名、来源、与卡牌效果描述。（审核不通过不返还击毙），输入取消退出。", arg_filters=[cancellation(buf.session)])
        config.logger.dragon << f"【LOG】用户{qq}提交卡牌{s}。"
        await user.add_jibi(-50, is_buy=True)
        for group in config.group_id_dict['logic_dragon_supervise']:
            await get_bot().send_group_msg(group_id=group, message=s)
        buf.send("您已成功提交！")
    elif id == 8:
        # (25击毙)抽一张卡，每日限一次。
        if user.shop_drawn_card >= 1:
            buf.send("您今日已在商店购买过抽卡！")
        else:
            config.userdata.execute("update dragon_data set shop_drawn_card=? where qq=?", (user.shop_drawn_card + 1, qq))
            user.reload()
            await user.add_jibi(-25, is_buy=True)
            await user.settlement(user.draw(1))
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
        n = User(node.qq, buf)
        await n.settlement(n.kill())
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
    n = User(qq, buf)
    await n.settlement(n.kill())

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

@on_command(('dragon', 'char'), only_to_me=False, hide=True, permission=permission.SUPERUSER)
@config.ErrorHandle(config.logger.dragon)
async def dragon_char(session: CommandSession):
    await session.send(f"status: {''.join(sorted(_card.status_dict.keys()))}\ndaily_status: {''.join(sorted(_card.daily_status_dict.keys()))}\nlimited_status: {''.join(sorted(_card.limited_status_dict.keys()))}")