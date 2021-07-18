import random, more_itertools, json, re
from collections import Counter
from functools import lru_cache
from copy import copy
from datetime import datetime, timedelta
from functools import reduce
from pypinyin import pinyin, Style
from nonebot.command.argfilter import extractors, validators
from .. import config

# global_state
# last_card_user : int
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
# spend_shop : int, equipment : str
# global_status : qq = 2711644761
def find_or_new(qq):
    t = config.userdata.execute("select * from dragon_data where qq=?", (qq,)).fetchone()
    if t is None:
        config.userdata.execute('insert into dragon_data (qq, jibi, draw_time, today_jibi, today_keyword_jibi, death_time, card, status, daily_status, status_time, card_limit, shop_drawn_card, event_pt, spend_shop, equipment) values (?, 0, 0, 10, 10, ?, ?, ?, ?, ?, 4, 0, 0, 0, ?)', (qq, '', '', '', '', '{}', '{}'))
        t = config.userdata.execute("select * from dragon_data where qq=?", (qq,)).fetchone()
    return t

def save_data():
    config.userdata_db.commit()

class Wrapper:
    def __init__(self, qq):
        self.qq = qq
    def __lshift__(self, log):
        config.logger.dragon << f"【LOG】用户{self.qq}" + log
class User:
    def __init__(self, qq, buf):
        self.qq = qq
        self.node = dict(find_or_new(qq))
        self.buf = buf
        self.hand_card = [] if self.card == '' else [Card(int(x)) for x in self.card.split(',')]
        self.equipment : dict = eval(self.equipment)
    def reload(self):
        self.node = dict(find_or_new(self.qq))
    def __setattr__(self, attr, value):
        self.__dict__[attr] = value
    def __getattr__(self, attr):
        if attr in self.node:
            return self.node[attr]
        else:
            raise AttributeError
    @property
    def char(self):
        return self.buf.char(self.qq)
    @property
    def log(self):
        return Wrapper(self.qq)
    def send_char(self, s):
        self.buf.send(self.char + s)
    def send_log(self, s):
        self.buf.send_log.dragon(self.qq, s)
    def set_cards(self):
        config.userdata.execute("update dragon_data set card=? where qq=?", (','.join(str(c.id) for c in self.hand_card), self.qq))
        config.logger.dragon << f"【LOG】设置用户{self.qq}手牌为{cards_to_str(self.hand_card)}。"
    def set_equipments(self):
        config.userdata.execute("update dragon_data set equipment=? where qq=?", (str(self.equipment), self.qq))
        config.logger.dragon << f"【LOG】设置用户{self.qq}装备为{equips_to_str(self.equipment)}。"
    def check_throw_card(self, card_ids):
        if len(card_ids) == 1:
            if card_ids[0] not in [c.id for c in self.hand_card]:
                return False
        else:
            hand_counter = Counter(c.id for c in self.hand_card)
            hand_counter.subtract(Counter(card_ids))
            if -hand_counter != Counter():
                return False
        return True
    def add_status(self, s):
        status = self.status
        status += s
        config.userdata.execute('update dragon_data set status=? where qq=?', (status, self.qq))
        self.reload()
        self.log << f"增加了永久状态{s}，当前状态为{status}。"
    def add_daily_status(self, s):
        status = self.daily_status
        status += s
        config.userdata.execute('update dragon_data set dailystatus=? where qq=?', (status, self.qq))
        self.reload()
        self.log << f"增加了每日状态{s}，当前状态为{status}。"
    def add_limited_status(self, s, end_time: datetime):
        status = eval(self.status_time)
        if s not in status:
            status[s] = end_time.isoformat()
        else:
            status[s] = max(datetime.fromisoformat(status[s]), end_time).isoformat()
        config.userdata.execute('update dragon_data set status_time=? where qq=?', (str(status), self.qq))
        self.reload()
        self.log << f"增加了限时状态{s}，结束时间为{end_time}。"
    def remove_status(self, s, *, remove_all=True):
        status = self.status
        if remove_all:
            status = ''.join([t for t in status if t != s])
        else:
            l = list(status)
            if s in l:
                l.remove(s)
            status = ''.join(l)
        config.userdata.execute('update dragon_data set status=? where qq=?', (status, self.qq))
        self.log << f"移除了{'一层' if not remove_all else ''}永久状态{s}，当前状态为{status}。"
    def remove_daily_status(self, s, *, remove_all=True):
        status = self.daily_status
        if remove_all:
            status = ''.join([t for t in status if t != s])
        else:
            l = list(status)
            if s in l:
                l.remove(s)
            status = ''.join(l)
        config.userdata.execute('update dragon_data set daily_status=? where qq=?', (status, self.qq))
        self.log << f"移除了{'一层' if not remove_all else ''}每日状态{s}，当前状态为{status}。"
    def remove_limited_status(self, s, status=None):
        status = eval(self.status_time)
        if s in status:
            status.pop(s)
            config.userdata.execute('update dragon_data set status_time=? where qq=?', (str(status), self.qq))
        self.log << f"移除了限时状态{s}，当前限时状态为{str(status)}。"
    def check_status(self, s):
        return self.status.count(s)
    def check_daily_status(self, s):
        return self.daily_status.count(s)
    def check_limited_status(self, s):
        status = eval(self.status_time)
        if s not in status:
            return False
        t = datetime.fromisoformat(status[s])
        if t < datetime.now():
            status.pop(s)
            config.userdata.execute('update dragon_data set status_time=? where qq=?', (str(status), self.qq))
            self.reload()
            return False
        return True
    def check_equipment(self, id):
        return self.equipment.get(id, 0)
    def decrease_death_time(self, time: timedelta):
        status = eval(self.status_time)
        if 'd' in status:
            t = datetime.fromisoformat(status['d'])
            t -= time
            status['d'] = t.isoformat()
            if t < datetime.now():
                status.pop('d')
            config.userdata.execute('update dragon_data set status_time=? where qq=?', (str(status), self.qq))
            self.reload()
            return 'd' not in status
        return True
    def get_limited_time(self, s):
        status = eval(self.status_time)
        if s not in status:
            return None
        delta = datetime.fromisoformat(status[s]) - datetime.now()
        if delta < timedelta():
            status.pop(s)
            config.userdata.execute('update dragon_data set status_time=? where qq=?', (str(status), self.qq))
            self.reload()
            return None
        return delta.seconds // 60
    async def add_event_pt(self, pt):
        current_pt = self.event_pt
        config.userdata.execute('update dragon_data set event_pt=? where qq=?', (current_pt + pt, self.qq))
        self.send_char(f"收到了{pt}活动pt！")
        self.log << f"增加了{pt}活动pt。现有{current_pt + pt}活动pt。"
    async def add_jibi(self, jibi, /, is_buy=False):
        current_jibi = self.jibi
        if n := self.check_status('2'):
            jibi *= 2 ** n
            self.send_char(f"触发了{f'{n}次' if n > 1 else ''}变压器的效果，{'获得' if jibi >= 0 else '损失'}击毙加倍为{abs(jibi)}！")
            self.remove_status('2')
        if q := self.check_equipment(0):
            if jibi > 0 and random.random() < 0.05 * q:
                jibi *= 2
                self.send_char(f"触发了比基尼的效果，获得击毙加倍为{abs(jibi)}！")
            else:
                q = 0
        dodge = False
        if r := self.check_equipment(1):
            if jibi < 0 and random.random() < r / (20 + r):
                dodge = True
                self.send_char(f"触发了学生泳装的效果，本次免单！")
        if (m := self.check_status('S')) and is_buy and not dodge:
            jibi //= 2 ** m
            self.send_char(f"触发了{f'{m}次' if m > 1 else ''}Steam夏季特卖的效果，花费击毙减半为{abs(jibi)}！")
            self.remove_status('S')
        if (p := self.check_status('1')) and is_buy and not dodge:
            if 100 <= self.spend_shop < 150:
                jibi  = int(jibi * 0.8 ** p)
                self.send_char(f"触发了{f'{p}次' if p > 1 else ''}北京市政交通一卡通的效果，花费击毙打了8折变为{abs(jibi)}！")
            elif 150 <= self.spend_shop < 400:
                jibi = int(jibi * 0.5 ** p)
                self.send_char(f"触发了{f'{p}次' if p > 1 else ''}北京市政交通一卡通的效果，花费击毙打了5折变为{abs(jibi)}！")
            elif self.spend_shop >= 400:
                self.send_char("今日已花费400击毙，不再打折！")
        if not dodge:
            config.userdata.execute("update dragon_data set jibi=? where qq=?", (max(0, current_jibi + jibi), self.qq))
        self.log << f"原有击毙{current_jibi}，{f'触发了{n}次变压器的效果，' if n > 0 else ''}{f'触发了比基尼的效果，' if q > 0 else ''}{f'触发了学生泳装的效果，' if dodge else ''}{f'触发了{m}次Steam夏季特卖的效果，' if m > 0 and is_buy and not dodge else ''}{f'触发了{p}次北京市政交通一卡通的效果，' if p > 0 and is_buy and not dodge else ''}{'获得' if jibi >= 0 else '损失'}了{abs(jibi)}。"
        if is_buy and not dodge:
            spend = self.spend_shop + abs(jibi)
            config.userdata.execute("update dragon_data set spend_shop=? where qq=?", (spend, self.qq))
            self.log << f"累计今日商店购买至{spend}。"
        self.reload()
    async def kill(self, hour=2, minute=0):
        """击杀玩家。"""
        dodge = False
        config.logger.dragon << f"【LOG】尝试击杀玩家{self.qq}。"
        if (n := self.check_status('s')) and not dodge:
            if self.jibi >= 5 * 2 ** self.check_status('2'):
                await self.add_jibi(-5)
                self.send_log("触发了死秽回避之药的效果，免除死亡！")
                dodge = True
                self.remove_status('s', remove_all=False)
        if (n := self.check_status('h')) and not dodge:
            for a in range(n):
                self.remove_status('h', remove_all=False)
                if random.randint(0, 1) == 0:
                    self.send_log("触发了虹色之环，闪避了死亡！")
                    dodge = True
                    break
                else:
                    self.send_log("触发虹色之环闪避失败，死亡时间+1h！")
        if (n := self.check_status('p')) and not dodge:
            self.log << f"的{n}张掠夺者啵噗因死亡被弃置。"
            await self.discard_cards([Card(77) for i in range(n)])
        if not dodge:
            self.add_limited_status('d', datetime.now() + timedelta(hours=hour, minutes=minute))
            self.send_char(f"死了！{f'{hour}小时' if hour != 0 else ''}{f'{minute}分钟' if minute != 0 else ''}不得接龙。")
            if (x := self.check_status('x')):
                self.remove_status('x')
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
        cards = [draw_card(positive) for i in range(n)] if cards is None else cards
        if n := cards.count(Card(67)):
            for i in range(n):
                await Card(67).on_draw(self)
        self.send_char('抽到的卡牌是：\n' + '\n'.join(c.full_description(self.qq) for c in cards))
        self.log << f"抽到的卡牌为{cards_to_str(cards)}。"
        for c in cards:
            if not c.consumed_on_draw:
                self.hand_card.append(c)
            if c.id != 67:
                await c.on_draw(self)
        self.set_cards()
        self.log << f"抽完卡牌，当前手牌为{cards_to_str(self.hand_card)}。"
    async def use_card(self, card):
        """使用卡牌。不处理将卡牌移出手牌的操作。"""
        self.send_char('使用了卡牌：\n' + card.full_description(self.qq))
        self.log << f"使用了卡牌{card.name}。"
        await card.use(self)
        await card.on_discard(self)
        self.log << f"使用完卡牌，当前手牌为{cards_to_str(self.hand_card)}。"
    async def discard_cards(self, cards):
        """弃牌。将cards里的卡牌移出手牌。弃光手牌时请复制hand_card作为cards传入。"""
        self.log << f"弃牌{cards_to_str(cards)}。"
        for c in cards:
            self.hand_card.remove(c)
        self.set_cards()
        for card in cards:
            await card.on_discard(self)
        self.log << f"弃完卡牌，当前手牌为{cards_to_str(self.hand_card)}。"
    async def exchange(self, target: 'User'):
        """交换两人手牌。"""
        target_hand_cards = copy(target.hand_cards)
        self_hand_cards = copy(self.hand_card)
        config.logger.dragon << f"【LOG】交换用户{self.qq}与用户{target.qq}的手牌。{self.qq}手牌为{cards_to_str(self_hand_cards)}，{target.qq}手牌为{cards_to_str(target_hand_cards)}。"
        self.hand_card.clear()
        target.hand_card.clear()
        for card in self_hand_cards:
            await card.on_give(self)
        for card in target_hand_cards:
            await card.on_give(self)
        self.hand_card.extend(target_hand_cards)
        target.hand_card.extend(self_hand_cards)
        self.set_cards()
        target_limit = target.card_limit
        if len(self_hand_cards) > target_limit:
            self.buf.send(f"该玩家手牌已超出上限{len(self_hand_cards) - target_limit}张！多余的牌已被弃置。")
            target.log << f"手牌为{cards_to_str(self_hand_cards)}，超出上限{target_limit}，自动弃置。"
            await target.discard_cards(copy(self_hand_cards[target_limit:]))
        target.set_cards()
        config.logger.dragon << f"【LOG】交换完用户{self.qq}与用户{target.qq}的手牌，当前用户{self.qq}的手牌为{cards_to_str(self.hand_card)}。"
    async def settlement(self, to_do):
        """结算卡牌相关。请不要递归调用此函数。"""
        self.log << "开始结算。"
        await to_do
        # discard
        x = len(self.hand_card) - self.card_limit
        while x > 0:
            save_data()
            if self.buf.active != self.qq:
                self.buf.send(f"该玩家手牌已超出上限{x}张！多余的牌已被弃置。")
                self.log << f"手牌为{cards_to_str(self.hand_card)}，超出上限{self.card_limit}，自动弃置。"
                await self.discard_cards(copy(self.hand_card[self.card_limit:]))
            else:
                ret2 = f"您的手牌已超出上限{x}张！请先选择一些牌弃置（输入id号，使用空格分隔）：\n" + \
                    "\n".join(c.full_description(self.qq) for c in self.hand_card)
                self.log << f"手牌超出上限，用户选择弃牌。"
                await self.buf.flush()
                l = await self.buf.aget(prompt=ret2,
                    arg_filters=[
                        extractors.extract_text,
                        lambda s: list(map(int, re.findall(r'\-?\d+', str(s)))),
                        validators.fit_size(x, x, message="请输入正确的张数。"),
                        validators.ensure_true(lambda l: self.check_throw_card(l), message="您选择了错误的卡牌！"),
                        validators.ensure_true(lambda l: 53 not in l, message="空白卡牌不可因超出手牌上限而被弃置！")
                    ])
                self.buf.send("成功弃置。")
                await self.discard_cards([Card(i) for i in l])
            x = len(self.hand_card) - self.card_limit
        self.set_cards()
        await self.buf.flush()
        save_data()

me = User(2711644761, None)

def cards_to_str(cards):
    return '，'.join(c.name for c in cards)
def draw_card(positive=None):
    x = positive is not None and len(positive & {-1, 0, 1}) != 0
    if me.check_daily_status('j'):
        if (x and (-1 in positive) or not x) and random.random() < 0.2:
            return Card(-1)
    c = random.choice(list(_card.card_id_dict.values()))
    while (x and c.positive not in positive) or c.id < 0:
        c = random.choice(list(_card.card_id_dict.values()))
    return c
def equips_to_str(equips):
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
                async def use(self, user):
                    user.add_status(status)
                attrs['use'] = use
            elif 'daily_status' in attrs and attrs['daily_status']:
                status = attrs['daily_status']
                bases[0].add_daily_status(status, attrs['status_des'])
                @classmethod
                async def use(self, user):
                    user.add_daily_status(status)
                attrs['use'] = use
            elif 'limited_status' in attrs and attrs['limited_status']:
                status = attrs['limited_status']
                bases[0].add_limited_status(status, attrs['status_des'])
                @classmethod
                async def use(self, user):
                    user.add_limited_status(status, datetime.now() + attrs['limited_time'])
                attrs['use'] = use
            elif 'global_status' in attrs and attrs['global_status']:
                status = attrs['global_status']
                bases[0].add_status(status, attrs['status_des'])
                @classmethod
                async def use(self, user):
                    me.add_status(status)
                attrs['use'] = use
            elif 'global_daily_status' in attrs and attrs['global_daily_status']:
                status = attrs['global_daily_status']
                bases[0].add_daily_status(status, attrs['status_des'])
                @classmethod
                async def use(self, user):
                    me.add_daily_status(status)
                attrs['use'] = use
            elif 'global_limited_status' in attrs and attrs['global_limited_status']:
                status = attrs['global_limited_status']
                bases[0].add_limited_status(status, attrs['status_des'])
                @classmethod
                async def use(self, user):
                    me.add_limited_status(status, datetime.now() + attrs['global_limited_time'])
                attrs['use'] = use
            elif 'hold_status' in attrs and attrs['hold_status']:
                status = attrs['hold_status']
                bases[0].add_status(status, attrs['status_des'])
                @classmethod
                async def on_draw(cls, user):
                    user.add_status(status)
                @classmethod
                async def on_discard(cls, user):
                    user.remove_status(status, remove_all=False)
                @classmethod
                async def on_give(cls, user, target):
                    user.remove_status(status)
                    target.add_status(status)
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
    id = -127
    positive = 0
    description = ""
    arg_num = 0
    consumed_on_draw = False
    @classmethod
    async def use(cls, user):
        pass
    @classmethod
    async def on_draw(cls, user):
        pass
    @classmethod
    async def on_discard(cls, user):
        pass
    @classmethod
    async def on_give(cls, user, target):
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
    async def on_discard(cls, user):
        await user.kill()

# class nvjisi(_card):
#     name = "II - 女祭司"
#     id = 2
#     positive = 0
#     description = "击毙当前周期内接龙次数最多的玩家。"
#     @classmethod
#     async def use(cls, user):
#         pass

# class lianren(_card):
#     name = "VI - 恋人"
#     id = 6
#     positive = 1
#     description = "复活1名指定玩家。"
#     @classmethod
#     async def use(cls, user):
#         await user.buf.flush()
#         l = await user.buf.aget(prompt="请at一名玩家复活。\n",
#             arg_filters=[
#                     lambda s: [r.group(1) for r in re.findall(r'qq=(\d+)', str(s))],
#                     validators.fit_size(1, 1, message="请at正确的人数。"),
#                 ])
#         u = User(l[0], user.buf)
#         n = u.check_limited_status('d')
#         u.remove_limited_status('d')
#         user.buf.send("已复活！" + ("（虽然目标并没有死亡）" if n else ''))

# class yinzhe(_card):
#     name = "IX - 隐者"
#     id = 9
#     positive = 1
#     daily_status = 'Y'
#     status_des = "IX - 隐者：今天你不会因为接到重复词或触雷而死亡。"
#     description = "今天你不会因为接到重复词或触雷而死亡。"

# class fortune(_card):
#     name = "X - 命运之轮"
#     id = 10
#     positive = 0
#     global_daily_status = 'O'
#     status_des = "X - 命运之轮：直至下次刷新前，在商店增加抽奖机，可以消耗5击毙抽奖。"
#     description = "直至下次刷新前，在商店增加抽奖机，可以消耗5击毙抽奖。"

# class emo(_card):
#     name = "XV - 恶魔"
#     id = 15
#     positive = 1
#     description = "击毙上一位使用卡牌的人。"
#     @classmethod
#     async def use(cls, user):
#         q = global_state['last_card_user']
#         u = User(q, user.buf)
#         user.buf.send(f'[CQ:at,qq={q}]被你击毙了！')
#         await u.kill()

# class taiyang(_card):
#     name = "XIX - 太阳"
#     id = 19
#     positive = 1
#     description = "随机揭示一个隐藏奖励词。"
#     @classmethod
#     async def use(cls, user):
#         from .logic_dragon import hidden_keyword
#         user.buf.send("你揭示的一个隐藏奖励词是：" + random.choice(hidden_keyword))

class dabingyichang(_card):
    name = "大病一场"
    id = 30
    positive = -1
    description = "抽到时，直到下一次主题出现前不得接龙。"
    consumed_on_draw = True
    @classmethod
    async def on_draw(cls, user):
        user.add_daily_status('d')
        user.send_char("病了！直到下一次主题出现前不得接龙。")
_card.add_daily_status('d', "生病：直到下一次主题出现前不可接龙。")

class caipiaozhongjiang(_card):
    name = "彩票中奖"
    id = 31
    positive = 1
    description = "抽到时立即获得20击毙与两张牌。"
    consumed_on_draw = True
    @classmethod
    async def on_draw(cls, user):
        user.send_char("中奖了！获得20击毙与两张牌。")
        await user.add_jibi(20)
        await user.draw(2)

class wuzhongshengyou(_card):
    name = "无中生有"
    id = 36
    positive = 1
    description = "摸两张牌。"
    @classmethod
    async def use(cls, user):
        await user.draw(2)

class tiesuolianhuan(_card):
    name = "铁索连环"
    id = 38
    positive = 1
    status_des = "铁索连环：任何处于连环状态的玩家被击毙时所有连环状态的玩家也被击毙并失去此效果。"
    description = "指定至多两名玩家进入连环状态。任何处于连环状态的玩家被击毙时所有连环状态的玩家也被击毙并失去此效果。也可用于解除至多两人的连环状态。"
    @classmethod
    async def use(cls, user):
        await user.buf.flush()
        config.logger.dragon << f"【LOG】询问用户{user.qq}铁索连环。"
        l = await user.buf.aget(prompt="请at群内至多两名玩家进行铁索连环。\n",
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
    async def use(cls, user):
        await user.buf.flush()
        config.logger.dragon << f"【LOG】询问用户{user.qq}复制牌。"
        l = await user.buf.aget(prompt="请选择你手牌中的一张牌复制，输入id号。\n" + "\n".join(c.full_description(user.qq) for c in user.hand_card),
            arg_filters=[
                    extractors.extract_text,
                    lambda s: list(map(int, re.findall(r'\d+', str(s)))),
                    validators.fit_size(1, 1, message="请输入正确的张数。"),
                    validators.ensure_true(lambda l: Card(l[0]) in user.hand_card, message="您选择了错误的卡牌！"),
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
    async def use(cls, user):
        user.buf.send("你弃光了所有手牌。")
        await user.discard_cards(copy(user.hand_card))

class dragontube(_card):
    name = "龙之烟管"
    id = 54
    positive = 1
    description = "你今天通过普通接龙获得的击毙上限增加10。"
    @classmethod
    async def use(cls, user):
        config.logger.dragon << f"【LOG】用户{user.qq}增加了接龙击毙上限至{user.today_jibi + 10}。"
        config.userdata.execute('update dragon_data set today_jibi=? where qq=?', (user.today_jibi + 10, user.qq))
        user.reload()
        user.buf.send("已增加。")

class xingyuntujiao(_card):
    name = "幸运兔脚"
    id = 55
    positive = 1
    description = "抽取一张正面卡并立即发动效果。"
    @classmethod
    async def use(cls, user):
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
    async def use(cls, user):
        config.logger.dragon << f"【LOG】用户{user.qq}增加了手牌上限至{user.card_limit + 1}。"
        config.userdata.execute('update dragon_data set card_limit=? where qq=?', (user.card_limit + 1, user.qq))
        user.reload()

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
    async def use(cls, user):
        from .logic_dragon import remove_all_bomb
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
        q = str(qq)
        m = mission[global_state['quest'][q][quest_print_aux[q]]['id']][1]
        remain = global_state['quest'][q][quest_print_aux[q]]['remain']
        quest_print_aux[q] += 1
        if quest_print_aux[q] >= len(global_state['quest'][q]):
            quest_print_aux[q] = 0
        return super().full_description(qq) + "\n\t当前任务：" + m + f"剩余{remain}次。"
    @classmethod
    async def on_draw(cls, user):
        q = str(user.qq)
        if q not in global_state['quest']:
            global_state['quest'][q] = []
            quest_print_aux[q] = 0
        global_state['quest'][q].append({'id': (i := get_mission()), 'remain': 3})
        config.logger.dragon << f"【LOG】用户{user.qq}刷新了一个任务{mission[i][1]}，现有任务：{[mission[c['id']][1] for c in global_state['quest'][q]]}。"
        save_global_state()
    @classmethod
    async def on_discard(cls, user):
        q = str(user.qq)
        i = global_state['quest'][q][quest_print_aux[q]]['id']
        del global_state['quest'][q][quest_print_aux[q]]
        if quest_print_aux[q] >= len(mission):
            quest_print_aux[q] = 0
        config.logger.dragon << f"【LOG】用户{user.qq}删除了一个任务{mission[i][1]}，现有任务：{[mission[c['id']][1] for c in global_state['quest'][q]]}。"
        save_global_state()
    @classmethod
    async def on_give(cls, user, target):
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
        user.set_cards()
        config.logger.dragon << f"【LOG】用户{user.qq}交换了所有人的手牌。"
        l = [(t['qq'], user.hand_card, t['status']) for t in config.userdata.execute("select qq, card, status from dragon_data").fetchall()]
        config.logger.dragon << f"【LOG】所有人的手牌为：{','.join(f'{qq}: {cards_to_str(cards)}' for qq, cards in l)}。"
        def _():
            for q, cs, status in l:
                userq = User(q, user.buf)
                if userq.check_status('G'):
                    userq.remove_status("G")
                else:
                    for c in cs:
                        yield (userq, c)
        all_cards = list(_())
        random.shuffle(all_cards)
        for userq, c in l:
            if (n := len(c)):
                cards_temp = [c1 for q1, c1 in all_cards[:n]]
                userq.hand_card.clear()
                userq.hand_card.extend(cards_temp)
                userq.set_cards()
                for userqqq, c in all_cards[:n]:
                    await c.on_give(userqqq, userq)
                config.logger.dragon << f"【LOG】{userq.qq}交换后的手牌为：{cards_to_str(cards_temp)}。"
                all_cards = all_cards[n:]
        if len(user.hand_card) != 0:
            user.buf.send("通过交换，你获得了手牌：\n" + '\n'.join(c.full_description(user.qq) for c in user.hand_card))
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
    async def use(cls, user):
        user.log << f"被加入交换堆栈，现为{global_state['exchange_stack']}。"
        global_state['exchange_stack'].append(user.qq)
        save_global_state()

class zhongshendexixi(_card):
    name = "众神的嬉戏"
    id = 76
    positive = 0
    description = '抽取一张卡并立即发动效果。'
    @classmethod
    async def use(cls, user):
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
    async def on_draw(cls, user):
        user.add_status('p')
        if str(user.qq) not in global_state['steal']:
            global_state['steal'][str(user.qq)] = {'time': 0, 'user': []}
        save_global_state()
    @classmethod
    async def on_discard(cls, user):
        user.remove_status('p', remove_all=False)
        if not user.check_status('p'):
            del global_state['steal'][str(user.qq)]
        save_global_state()
    @classmethod
    async def on_give(cls, user, target):
        user.remove_status('p')
        target.add_status('p')
        global_state['steal'][str(target.qq)] = global_state['steal'][str(user.qq)]
        if not user.check_status('p'):
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
    async def use(cls, user):
        n = len(user.hand_card)
        await user.discard_cards(copy(user.hand_card))
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
    async def use(cls, user):
        user.buf.send("所有人都赢了！恭喜你们！")

class suicideking(_card):
    name = "自杀之王（♥K）"
    id = 90
    positive = -1
    description = "抽到时立即死亡。"
    consumed_on_draw = True
    @classmethod
    async def on_draw(cls, user):
        user.send_char("抽到了自杀之王，" + user.char + "死了！")
        await user.kill()

class zhu(_card):
    name = "猪（♠Q）"
    id = 91
    positive = -1
    description = "抽到时损失20击毙（但不会扣至0以下）。"
    consumed_on_draw = True
    @classmethod
    async def on_draw(cls, user):
        await user.add_jibi(-20)
        user.send_char("抽到了猪，损失了20击毙！")

class yang(_card):
    name = "羊（♦J）"
    id = 92
    positive = 1
    description = "抽到时获得20击毙。"
    consumed_on_draw = True
    @classmethod
    async def on_draw(cls, user):
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

mission = []
def add_mission(doc):
    def _(f):
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

from collections import namedtuple

# 飞行棋棋盘格子
class Grid(namedtuple('Grid', ["id", "content", "data", "pos", "childs_id", "parents_id"], defaults=[None, None])):
    __slots__ = ()
    all_items = {}
    topology = 0
    # example: Grid(1, 1, (3, 10), (20, 20), ((2,), (3,), (3,))) # 奖励3pt，被击毙10分钟，在不同拓扑下childs不同
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
    async def move(self, user, n, back=False):
        current = self
        for i in range(n):
            if back:
                current = current.parents[0] # TODO: choose
            else:
                current = current.childs[0] # TODO: choose
        user.log << f"走到了{current.id}。"
        return current
    async def do(self, user: User):
        await user.add_event_pt(self.data[0])
        if self.content == 0: # 改变拓扑结构至环面/莫比乌斯带/克莱因瓶
            user.send_log("走到了：改变拓扑结构至" + {0: "环面", 1: "莫比乌斯带", 2: "克莱因瓶"}[self.data[1]] + "。")
            Grid.topology = self.data[1]
        elif self.content == 1: # 被击毙5/10/15/20/25分钟
            user.send_log(f"走到了：被击毙{self.data[1]}分钟。")
            await user.kill(minute=self.data[1])
        elif self.content == 2: # 获得2/4/6/8/10击毙
            user.send_log(f"走到了：获得{self.data[1]}击毙。")
            await user.add_jibi(self.data[1])
        elif self.content == 3: # 获得活动pt后，再扔一次骰子前进/后退 
            n = random.randint(1, 6)
            user.send_log(f"走到了：获得活动pt后，再扔一次骰子{'前进' if self.data[1] == 1 else '后退'}。{user.char}扔到了{n}。")
            grid = await self.move(user, n, back=(self.data[1] != 1))
            return await grid.do(user)
        elif self.content == 16: # 抽一张卡并立即发动效果
            user.send_log("走到了：抽一张卡并立即发动效果。")
            c = draw_card()
            user.send_char('抽到并使用了卡牌：\n' + c.full_description(user.qq))
            user.log << f"抽取了卡牌{c.name}。"
            await c.on_draw(user)
            await c.use(user)
            await c.on_discard(user)
        elif self.content == 17: # 获得20活动pt并随机飞到一个格子
            user.send_log(f"走到了：获得{self.data[1]}活动pt并随机飞到一个格子。")
            await user.add_event_pt(self.data[1])
            grid = random.choice(list(self.all_items.values()))
            user.log << f"飞到了{grid.id}。"
            return await grid.do(user)
        return self

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
    id_dict = {}
    id = -127
    name = ''
    des_shop = ''
    @classmethod
    def description(cls, count):
        pass

class bikini(_equipment):
    id = 0
    name = '比基尼'
    des_shop = '你每次获得击毙时都有一定几率加倍。一星为5%，二星为10%，三星为15%。'
    @classmethod
    def description(cls, count):
        return f'你每次获得击毙时都有{5 * count}%几率加倍。'

class schoolsui(_equipment):
    id = 1
    name = '学校泳装'
    des_shop = '你每次击毙减少或商店购买都有一定几率免单。一星为4.76%，二星为9.09%，三星为13.04%。'
    @classmethod
    def description(cls, count):
        return f'你每次击毙减少或商店购买都有{count / (20 + count) * 100:.2f}%几率免单。'
