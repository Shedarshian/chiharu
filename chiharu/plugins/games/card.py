import random
import json
import itertools
import functools
import more_itertools
from enum import IntEnum
import contextlib
import os
from typing import Dict, Iterable, Tuple, Awaitable, List, Set, Union
from datetime import date, datetime
import chiharu.plugins.config as config
from nonebot import on_command, CommandSession, get_bot, permission, scheduler
from nonebot.command import call_command
config.logger.open('card')
def _time():
    h = datetime.now().hour
    return h < 6 or 11 <= h < 13 or h >= 23
c1 = config.Constraint(config.group_id_dict['card_constraint'], _time, "现时段本群功能管制，开放时段为11～13 23～30点，欢迎加入bot测试群947279366刷屏")

# -game card 引导至card的指令列表
# √抽卡指令（参数：卡池，张数） 参数为空时引导至查看卡池 限额抽完时引导至查看个人信息 再次输入确认使用资源抽卡
# √查看卡池指令（参数：卡池或空） 引导抽卡指令 查看具体卡池 引导至私聊卡池信息
# √添加卡指令（参数：卡名，张数） 限额抽完时引导至查看个人信息
# √查看个人信息，包含资源数，剩余免费抽卡次数（级别？） 引导至查看库存与创造卡与留言簿
# √查看库存指令（翻页） 引导至分解卡与创造卡
# √查看愿望单 引导至加入愿望单，说明在首次抽到愿望单卡时会自动取消并加入特别喜欢，可以再次加入愿望单代表想要更多
# 仓储操作指令，包含√加入特别喜欢，√加入愿望单，√消息箱设置，指令提示设置
# √查看消息箱指令
# √分解卡指令
# √留言簿指令
# 凌晨：更新每日限额，更新每日卡池
# √批量添加指令
# √查看审核指令
# √审核通过指令
# 预约开放活动卡池指令
# 回复留言指令（指直接塞入消息箱）
# 维护？
# status: 1 已开放 0 已结束 2 未开始 3 已空

page_max = 40
# daily_draw = 10
# daily_create = 30
# daily_create_type = 10
daily_draw = 10
daily_create = 30
daily_create_type = 10
daily_pool_num = 3
daily_pool_cap = 300
daily_pool_exceed = 400

guide = {'draw': '使用-card.draw 卡池id/名字 抽卡次数 进行抽卡，次数不填默认为单抽，\n-card.draw5 卡池id/名字 直接进行五连抽卡',
    'check_detail': '私聊-card.check 卡池id/名字 查询卡池具体信息（刷屏预警）',
    'check': '使用-card.check 不带参数 查询卡池列表',
    'add': '使用-card.add 卡片名字 张数 创造卡片加入次日新卡卡池与每日随机卡池 张数不填默认为1张',
    'info': '使用-card.userinfo 查看个人信息，包含en数，剩余免费抽卡次数等等',
    'storage': '使用-card.storage 查看库存',
    'discard': '使用-card.discard 卡片名 数量 分解不需要的卡片获得资源（数量默认为1）',
    'wishlist': '使用-card.wishlist 查看愿望单',
    'check_message': '使用-card.message 手动查看消息箱',
    'fav&wish': '使用-card.fav 卡片名 将卡片加入特别喜欢，-card.wish 卡片名 将卡片加入愿望单',
    'wish': '使用-card.wish 卡片名 将卡片加入愿望单',
    'confirm': '使用-card.set.unconfirm 取消今日确认使用en抽卡',
    'message': '使用-card.set.message 参数 设置消息箱提醒',
    'guide': '使用-card.set.guide on或off 开启或关闭指令提示',
    'comment': '使用-card.comment 给维护者留言~',
    'check_card': '使用-card.check_card 卡片名 查询卡片余量',
    'add_des': '使用-card.add_des 卡片名 换行后添加卡牌描述'}
    #17个，超了！

with open(config.rel(r"games\card\pool"), 'rb') as f:
    pool = list(itertools.starmap(lambda x, y: int(x) * 256 + int(y), more_itertools.chunked(f.read(), 2)))
with open(config.rel(r"games\card\card_info.json"), encoding='utf-8') as f:
    card_info = json.load(f)
with open(config.rel(r"games\card\daily_pool.json"), encoding='utf-8') as f:
    daily_pool_all = json.load(f)
    daily_pool = [x for x in daily_pool_all if x['status'] == 1 or x['status'] == 3]
    daily_pool_draw = [x['cards'] for x in daily_pool]
def save_card_info():
    with open(config.rel(r"games\card\card_info.json"), 'w', encoding='utf-8') as f:
        f.write(json.dumps(card_info, ensure_ascii=False, indent=4, separators=(',', ': ')))
def save_pool():
    with open(config.rel(r"games\card\pool"), 'wb') as f:
        f.write(bytes(itertools.chain(*map(lambda x: [x // 256, x % 256], pool))))
def save_daily_pool():
    with open(config.rel(r"games\card\daily_pool.json"), 'w', encoding='utf-8') as f:
        f.write(json.dumps(daily_pool_all, ensure_ascii=False, indent=4, separators=(',', ': ')))
def read_verify():
    with open(config.rel(r"games\card\verify.json"), encoding='utf-8') as f:
        verify = json.load(f)
    return verify
def save_verify(verify):
    with open(config.rel(r"games\card\verify.json"), 'w', encoding='utf-8') as f:
        f.write(json.dumps(verify, ensure_ascii=False, indent=4, separators=(',', ': ')))
def read_new_card():
    with open(config.rel(r'games\card\new_card.json')) as f:
        return json.load(f)
def save_new_card(new_card):
    with open(config.rel(r'games\card\new_card.json'), 'w') as f:
        f.write(json.dumps(new_card))
def add_new_card(id):
    new_card = read_new_card()
    new_card[-1].append(id)
    save_new_card(new_card)

def to_byte(num):
    return bytes([num // 256, num % 256])
def get_card_names(*l):
    return '，'.join([card_info[i]['name'] for i in l])
def daily_pool_find(s):
    return more_itertools.only(filter(lambda x: x['name'] == s or str(x['id']) == s, daily_pool))
def card_find(s):
    return more_itertools.only(filter(lambda x: x['name'] == s, card_info))
def refresh_status(pool_info):
    num = functools.reduce(lambda x, y: x + y, [pool[x] for x in pool_info['cards']], 0)
    if pool_info['status'] == 3 and num != 0:
        pool_info['status'] = 1
    elif pool_info['status'] == 1 and num == 0:
        pool_info['status'] = 3

class user_info:
    def __init_subclass__(cls, path, if_binary=False):
        cls.path_all = config.rel(path)
        cls.if_binary = if_binary
    def __init__(self, index):
        self.path = self.path_all % index
        self.qq = index
        try:
            self.file = open(self.path, 'r+b' if self.if_binary else 'r+')
        except FileNotFoundError:
            self.init_begin()
    def init_begin(self):
        self.file = open(self.path, 'x+b' if self.if_binary else 'x+')
    def __del__(self):
        self.file.close()
class user_storage(user_info, path=r"games\card\user_storage\%i", if_binary=True):
    def __init__(self, index):
        super(user_storage, self).__init__(index)
        self.guide = user_storage._(self)
    def init_begin(self):
        self.file = open(self.path, 'x+b' if self.if_binary else 'x+')
        self.file.write(bytes([0, 0, daily_draw, daily_create_type, daily_create // 256, daily_create % 256, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]))
    def check(self):
        if os.stat(self.path).st_size < 4 * len(pool) + 16:
            self.file.seek(0, 2)
            self.file.write(bytes(map(lambda x: 0, range(4 * len(pool) + 16 - os.stat(self.path).st_size))))
            self.file.flush()
    def read_info(self):
        # 16 byte data for user info
        self.file.seek(0)
        a, b, c, d, e, f, g, h, i, j, k, l, m, n, o, p = self.file.read(16)
        return {'money': a * 256 + b, 'confirm': bool(c & 128), 'time': c % 128, 'create_type': d, 'create_num': e * 256 + f, 'message': g % 32, 'guide1': h, 'guide2': i, 'guide3': j}
    def save_info(self, val):
        self.file.seek(0)
        self.file.write(bytes([val['money'] // 256, val['money'] % 256, val['confirm'] * 128 + val['time'], val['create_type'], val['create_num'] // 256, val['create_num'] % 256, val['message'], val['guide1'], val['guide2'], val['guide3'], 0, 0, 0, 0, 0, 0]))
        self.file.flush()
    def read_nocheck(self, id):
        # 4 byte data for each card
        self.file.seek(4 * id + 16)
        a, b, c, d = self.file.read(4)
        return {'num': a * 256 + b, 'fav': bool(d & 2), 'wish': bool(d & 1)}
    def yield_all(self):
        self.file.seek(16)
        for a, b, c, d in iter(lambda: self.file.read(4), b''):
            yield {'num': a * 256 + b, 'fav': bool(d & 2), 'wish': bool(d & 1)}
    def read_all(self):
        return list(self.yield_all())
    def save(self, id, dct):
        self.file.seek(4 * id + 16)
        self.file.write(bytes([dct['num'] // 256, dct['num'] % 256, 0, dct['fav'] * 2 + dct['wish']]))
        self.file.flush()
    def give(self, *args) -> Dict[str, List[int]]:
        self.check()
        ret = {'max': [], 'wish_reset': []}
        for i in args:
            data = self.read_nocheck(i)
            data['num'] += 1
            # 超过上限
            if data['num'] >= 65536:
                data['num'] -= 1
                ret['max'].append(i)
            # 抽到首张时取消愿望单，并加入特别喜欢
            if data['num'] == 1 and data['wish']:
                data['wish'] = False
                data['fav'] = True
                ret['wish_reset'].append(i)
            self.save(i, data)
        return ret
    async def send(self, msg):
        info = self.read_info()['message']
        if info == 0:
            await get_bot().send_private_msg(user_id=self.qq, message=msg + self.guide["message"], auto_escape=True)
        elif info == 1 or info == 2:
            with open(config.rel(r"games\card\message.json"), encoding='utf-8') as f:
                message = json.load(f)
            import datetime
            msg = f"{datetime.datetime.now().isoformat(' ')} {msg}"
            if str(self.qq) not in message:
                message[str(self.qq)] = [msg]
            else:
                message[str(self.qq)].append(msg)
            with open(config.rel(r"games\card\message.json"), 'w', encoding='utf-8') as f:
                f.write(json.dumps(message, ensure_ascii=False, indent=4, separators=(',', ': ')))
    def check_message(self):
        with open(config.rel(r"games\card\message.json"), encoding='utf-8') as f:
            message = json.load(f)
        if str(self.qq) not in message:
            return []
        else:
            s = message.pop(str(self.qq))
            with open(config.rel(r"games\card\message.json"), 'w', encoding='utf-8') as f:
                f.write(json.dumps(message, ensure_ascii=False, indent=4, separators=(',', ': ')))
            return s
    class _:
        def __init__(self, c):
            self.c = c
        def __getitem__(self, key):
            info = self.c.read_info()
            try:
                id = list(guide.keys()).index(key)
                if id >= 16:
                    res = bool(info['guide3'] & 2 ** (id - 16))
                elif id >= 8:
                    res = bool(info['guide2'] & 2 ** (id - 8))
                else:
                    res = bool(info['guide1'] & 2 ** id)
                if res:
                    return ''
                else:
                    return '\n' + guide[key]
            except ValueError:
                raise KeyError
    def close(self, key):
        info = self.read_info()
        try:
            id = list(guide.keys()).index(key)
            if id >= 16:
                if not info['guide3'] & 2 ** (id - 16):
                    config.logger.card << f'用户{self.qq} 已自动关闭指令引导{key}'
                    info['guide3'] |= 2 ** (id - 16)
                    self.save_info(info)
            elif id >= 8:
                if not info['guide2'] & 2 ** (id - 8):
                    config.logger.card << f'用户{self.qq} 已自动关闭指令引导{key}'
                    info['guide2'] |= 2 ** (id - 8)
                    self.save_info(info)
            else:
                if not info['guide1'] & 2 ** id:
                    config.logger.card << f'用户{self.qq} 已自动关闭指令引导{key}'
                    info['guide1'] |= 2 ** id
                    self.save_info(info)
        except ValueError:
            raise KeyError
class user_create(user_info, path=r"games\card\user_create\%i", if_binary=True):
    def check(self):
        if os.stat(self.path).st_size < 4 * len(pool):
            self.file.seek(0, 2)
            self.file.write(bytes(map(lambda x: 0, range(4 * len(pool) - os.stat(self.path).st_size))))
            self.file.flush()
    def read_nocheck(self, id):
        # 4 byte data for each card
        self.file.seek(4 * id)
        a, b, c, d = self.file.read(4)
        return {'num': a * 256 + b, 'first': bool(d & 1)}
    def save(self, id, dct):
        self.file.seek(4 * id)
        self.file.write(bytes([dct['num'] // 256, dct['num'] % 256, 0, dct['first']]))
        self.file.flush()
    def create(self, id, num, is_first):
        self.check()
        data = self.read_nocheck(id)
        data['num'] += num
        data['first'] = is_first
        self.save(id, data)
    def check_created(self, name):
        try:
            with open(self.path + '.txt', 'r', encoding='utf-8') as f:
                self.c = list(map(lambda x: x.strip(), f.readlines()))
        except FileNotFoundError:
            self.c = []
        return name in self.c
    def new_created_type_checked(self, name):
        self.c.append(name)
        with open(self.path + '.txt', 'w', encoding='utf-8') as f:
            for i in self.c:
                f.write(i + '\n')
                f.flush()

@contextlib.contextmanager
def open_user_create(qq):
    resource = user_create(qq)
    try:
        yield resource
    finally:
        del resource
@contextlib.contextmanager
def open_user_storage(qq):
    resource = user_storage(qq)
    try:
        yield resource
    finally:
        del resource
#with open_user_storage(qq) as f:
#    f.give(id, id)

def _des(l, if_len=True, max=3):
    if len(l) > max:
        return '，'.join(map(lambda x: card_info[x]['name'], random.sample(l, k=max))) + f'等{len(l)}种' if if_len else ''
    else:
        return '，'.join(map(lambda x: card_info[x]['name'], l))
def pool_des(pool_info: Dict, wish: Set):
    title = {'event': '活动卡池', 'daily': '每日卡池', 'new': '新卡卡池'}
    not_zero = [x for x in pool_info['cards'] if pool[x] > 0]
    only_one = [x for x in pool_info['cards'] if pool[x] == 1]
    in_wish = [x for x in pool_info['cards'] if x in wish and pool[x] > 0]
    num = functools.reduce(lambda x, y: x + y, map(lambda x: pool[x], pool_info['cards']), 0)
    return f"""{f'''{title[pool_info['type']]}：{pool_info['name']} id：{pool_info['id']}
{pool_info['description']} {pool_info['end_date']} 截止''' if pool_info['type'] == 'event' else f"{pool_info['name']} id：{pool_info['id']}"}
{f'包含{_des(not_zero)}共{num}张。' if num != 0 else '卡池已空。'}{f'''
{_des(only_one)}只余一张！''' if len(only_one) != 0 else ''}{f'''
【{_des(in_wish)}在您的愿望单中！】''' if len(in_wish) != 0 else ''}"""
def pool_des_detail(pool_info: Dict, wish: Set):
    title = {'event': '活动卡池', 'daily': '每日卡池', 'new': '新卡卡池'}
    not_wish = [x for x in pool_info['cards'] if pool[x] > 0 and x not in wish and pool[x] > 0]
    in_wish = [x for x in pool_info['cards'] if pool[x] > 0 and x in wish and pool[x] > 0]
    return f"""{(f'''{title[pool_info['type']]}：{pool_info['name']} id：{pool_info['id']}
{pool_info['description']} {pool_info['end_date']} 截止''' if pool_info['type'] == 'event' else f"{pool_info['name']} id：{pool_info['id']}")}
包含卡牌：{'，'.join([f'''{card_info[x]['name']}x{pool[x]}''' for x in not_wish])}""" + (f"""
【在您的愿望单中的卡牌】：{'，'.join([f'''{card_info[x]['name']}x{pool[x]}''' for x in in_wish])}""" if len(in_wish) != 0 else '')

def add_cardname(arg: Iterable[Tuple[str, int, Union[str, None]]], **kwargs):
    global card_info, pool
    with open(config.rel(r"games\card\pool"), 'ab') as f:
        for name, num, des in arg:
            c = card_find(name)
            if c is None:
                if des is not None:
                    card_info.append(dict(name=name, id=len(card_info), des=des, **kwargs))
                else:
                    card_info.append(dict(name=name, id=len(card_info), **kwargs))
                pool.append(num)
                f.write(to_byte(num)) # 每个卡最多65535张
            else:
                f.seek(2 * c['id'])
                pool[c['id']] += num
                f.write(to_byte(pool[c['id']]))
    save_card_info()
def add_card(arg: Iterable[Tuple[int, int]]):
    global pool
    with open(config.rel(r"games\card\pool"), 'rb+') as f:
        for id, num in arg:
            f.seek(2 * id)
            pool[id] += num
            f.write(to_byte(pool[id]))

@on_command(('card', 'draw'), only_to_me=False, aliases=('抽卡',))
@c1
@config.maintain('card')
@config.ErrorHandle(config.logger.card)
async def card_draw(session: CommandSession):
    if session.get('name') is None:
        # 卡池介绍
        with open_user_storage(session.ctx['user_id']) as f:
            wish = set(i for i, data in enumerate(f.yield_all()) if data['wish'])
            await session.send(('\n'.join([pool_des(x, wish) for x in daily_pool]) + f'\n{f.guide["draw"]}{f.guide["check_detail"]}').strip(), auto_escape=True)
    else:
        qq = session.ctx['user_id']
        name, num = session.get('name'), session.get('num')
        if num > 5 or num <= 0:
            await session.send('一次最多五连抽卡！')
            return
        p = daily_pool_find(name)
        if p is None:
            with open_user_storage(qq) as f:
                await session.send('未发现此卡池' + f.guide['draw'])
            return
        refresh_status(p)
        if p['status'] == 3:
            await session.send('卡池已空，无法继续抽取')
        else:
            config.logger.card << f'【LOG】用户{qq} 于卡池{p["id"]} 进行{num}次抽卡'
            with open_user_storage(qq) as f:
                data = {'empty': False, 'payed': False, 'money': 0}
                info = f.read_info()
                weight = list(map(lambda x: pool[x], p['cards']))
                pool_num = functools.reduce(lambda x, y: x + y, weight, 0)
                if pool_num <= num:
                    num = pool_num
                    data['empty'] = True
                if info['time'] == 0:
                    if not info['confirm']:
                        if info['money'] >= 100:
                            info['confirm'] = True
                            f.save_info(info)
                            await session.send(f'您今日的免费10次抽卡次数已用尽，是否确认使用en进行抽卡？再次输入抽卡指令确认{f.guide["info"]}{f.guide["confirm"]}', auto_escape=True) # 取消确认？？？
                            config.logger.card << f'【LOG】用户{qq} 免费抽卡次数已用尽 可以使用en进行抽卡'
                        else:
                            await session.send(f'您今日的免费10次抽卡次数已用尽{f.guide["info"]}{f.guide["wish"]}', auto_escape=True)
                            config.logger.card << f'【LOG】用户{qq} 免费抽卡次数已用尽'
                        return
                    else:
                        if info['money'] >= 100 * num:
                            info['money'] -= 100 * num
                            data['payed'] = True
                            data['money'] = info['money']
                            f.save_info(info)
                        else:
                            await session.send(f'您剩余en已不足\n\n您还有{info["money"]}en，每100en可以抽一张卡{f.guide["info"]}{f.guide["wish"]}', auto_escape=True)
                            config.logger.card << f'【LOG】用户{qq} en数不足'
                            return
                elif info['time'] < num:
                    await session.send(f'您今日的免费10次抽卡次数不足，只剩{info["time"]}次{f.guide["info"]}', auto_escape=True)
                    config.logger.card << f'【LOG】用户{qq} 免费抽卡次数不足'
                    return
                else:
                    info['time'] -= num
                    f.save_info(info)
                if data['empty']:
                    def _f():
                        for id, n in zip(p['cards'], weight):
                            for i in range(n):
                                pool[id] -= 1
                                yield id
                    p['status'] = 3
                    save_daily_pool()
                else:
                    def _f():
                        for i in range(num):
                            index = random.choices(range(len(p['cards'])), weight)[0]
                            weight[index] -= 1
                            pool[p['cards'][index]] -= 1
                            yield p['cards'][index]
                get = list(_f())
                ret = f.give(*get)
                save_pool()
                f.close('draw')
            await session.send(f"""{'''您已把卡池抽空！
''' if data['empty'] else ''}恭喜您抽中：
{get_card_names(*get)}{f'''
{card_info[get[0]]['des']}''' if len(get) == 1 and 'des' in card_info[get[0]] else ''}{f'''
库存 {get_card_names(*ret['max'])} 已达到上限''' if len(ret['max']) != 0 else ''}{f'''
{get_card_names(*ret['wish_reset'])} 已自动取消愿望单''' if len(ret['wish_reset']) != 0 else ''}{f'''
您还剩余{data['money']}en''' if data['payed'] else ''}""", auto_escape=True)
            if data['payed']:
                config.logger.card << f'【LOG】用户{qq} 消耗了{100 * num}en 剩余{data["money"]}en'
            else:
                config.logger.card << f'【LOG】用户{qq} 剩余{info["time"]}次免费抽取机会'
            config.logger.card << f'【LOG】用户{qq} 获得卡片{get}'
            if len(ret['max']) != 0:
                config.logger.card << f'【LOG】用户{qq} 卡片{ret["max"]}已达到上限'
            if len(ret['wish_reset']) != 0:
                config.logger.card << f'【LOG】用户{qq} 愿望单内{ret["wish_reset"]}已被自动取消'
            if data['empty']:
                config.logger.card << f'【LOG】卡池{p["id"]}已空'

@on_command(('card', 'draw5'), aliases=('五连抽卡',), only_to_me=False)
@c1
@config.maintain('card')
@config.ErrorHandle(config.logger.card)
async def card_draw_5(session: CommandSession):
    if session.current_arg_text == "":
        await call_command(get_bot(), session.ctx, ('card', 'draw'), current_arg="")
    else:
        await call_command(get_bot(), session.ctx, ('card', 'draw'), current_arg=session.current_arg_text.strip() + ' 5')

@on_command(('card', 'check'), only_to_me=False)
@c1
@config.maintain('card')
@config.ErrorHandle(config.logger.card)
async def card_check(session: CommandSession):
    qq = session.ctx['user_id']
    if session.current_arg_text == "":
        with open_user_storage(qq) as f:
            f.close('check')
            wish = set(i for i, data in enumerate(f.yield_all()) if data['wish'])
            await session.send(('\n'.join([pool_des(x, wish) for x in daily_pool]) + f'\n{f.guide["draw"]}{f.guide["check_detail"]}').strip(), auto_escape=True)
    else:
        p = daily_pool_find(session.current_arg_text)
        if p is None:
            await session.send('未发现此卡池')
        else:
            with open_user_storage(qq) as f:
                f.close('check_detail')
                wish = set(i for i, data in enumerate(f.yield_all()) if data['wish'])
                await session.send((pool_des_detail(p, wish) + f'\n{f.guide["draw"]}{f.guide["check_card"]}').strip(), auto_escape=True)

@on_command(('card', 'check_card'), only_to_me=False)
@c1
@config.maintain('card')
@config.ErrorHandle(config.logger.card)
async def card_check_card(session: CommandSession):
    c = card_find(session.current_arg_text.replace('，', ','))
    if c is None:
        await session.send('未发现此卡牌')
    else:
        pools = [x['name'] for x in daily_pool if c['id'] in x['cards']]
        with open_user_storage(session.ctx['user_id']) as f, open_user_create(session.ctx['user_id']) as f2:
            f.close('check_card')
            f.check()
            check = f.read_nocheck(c['id'])['num'] > 0 or f2.check_created(c['name'])
            strout = (f"卡牌 {c['name']}：余量{pool[c['id']]}张" + '\n' + (f"出现于卡池：{'，'.join(pools)}" if len(pools) > 0 else "未出现在今日卡池") + (('\n' + c['des'] if check else '\n描述文本已因您未拥有此卡牌而隐藏') if 'des' in c else '\n') + f"{f.guide['check']}").strip()
            if f2.check_created(c['name']):
                strout += '\n此卡牌是您首次创造'
        await session.send(strout, auto_escape=True)

@on_command(('card', 'add'), only_to_me=False)
@c1
@config.maintain('card')
@config.ErrorHandle(config.logger.card)
async def card_add(session: CommandSession):
    if session.get('name') is None:
        await session.send(guide['add'])
        return
    qq = session.ctx['user_id']
    name, num = session.get('name'), session.get('num')
    if num <= 0:
        await session.send('不能创造非正数张卡')
        return
    async def _f():
        pass
    with open_user_storage(qq) as f1, open_user_create(qq) as f2:
        info = f1.read_info()
        created = f2.check_created(name)
        strout = ''
        if info['create_type'] < 1 and not created:
            strout = f"您今日创造卡片的种类已达上限，上限为10种30张，您只剩{info['create_type']}种{info['create_num']}张。{f1.guide['info']}"
        elif info['create_num'] < num:
            strout = f"您今日创造卡片的剩余张数不足，上限为10种30张，您只剩{info['create_type']}种{info['create_num']}张。{f1.guide['info']}"
        elif '\n' in name or '\t' in name or '\r' in name or name.startswith(' ') or name.endswith(' '):
            strout = "卡片名中含有非法字符，未通过"
        elif len(name) >= 17:
            strout = "卡片名过长"
        else:
            name = name.replace('，', ',')
            c = card_find(name)
            if not created:
                info['create_type'] -= 1
            info['create_num'] -= num
            if c is None:
                # new card 加入审核
                f1.save_info(info)
                verify = read_verify()
                a = more_itertools.only(filter(lambda x: x.get('name', '') == name, verify))
                des = None
                if a is None:
                    f2.new_created_type_checked(name)
                    id_max = max(-1, -1, *[x['id'] for x in verify]) + 1
                    verify.append({'name': name, 'id': id_max, 'user': [{'qq': qq, 'num': num}]})
                    if session.get('des') is not None:
                        verify[-1]['des'] = des = session.get('des')
                        des = '\n' + des + '\n'
                else:
                    if session.get('des') is not None:
                        strout += "该卡片不是您首次创造，已忽略描述文本\n"
                    id_max = None
                    b = more_itertools.only(filter(lambda x: x['qq'] == qq, a['user']))
                    if b is None:
                        a['user'].append({'qq': qq, 'num': num})
                    else:
                        b['num'] += num
                save_verify(verify)
                info['money'] += 20 * num
                f1.save_info(info)
                config.logger.card << f"【LOG】用户{qq} 提交卡片名 {name} ，{num}张{f'，描述为{des}' if des is not None else ''}，待审核"
                config.logger.card << f'【LOG】用户{qq} 获得了{20 * num}en 剩余{info["money"]}en'
                strout += f"已提交卡片 {name} {f'，描述为{des}' if des is not None else ''}，待审核，审核成功后会将通知发送至消息箱（默认为私聊）~\n您已获得{20 * num}en{f1.guide['add_des']}{f1.guide['info']}{f1.guide['wish']}".strip()
                async def _f():
                    for group in config.group_id_dict['card_verify']:
                        await get_bot().send_group_msg(group_id=group, message=f"{qq}提交\n{name}\n{num}张{f'，描述为{des}' if des is not None else ''} id:{id_max}", auto_escape=True)
            else:
                if session.get('des') is not None:
                    strout += "该卡片不是您首次创造，已忽略描述文本\n"
                add_new_card(c['id'])
                add_card(((c['id'], num),))
                f2.create(c['id'], num, False)
                info['money'] += 20 * num
                f1.save_info(info)
                config.logger.card << f"【LOG】用户{qq} 创造卡片{c['id']}，{num}张"
                config.logger.card << f'【LOG】用户{qq} 获得了{20 * num}en 剩余{info["money"]}en'
                strout += f"成功放入卡片 {c['name']} {num}张，欢迎明日查看新卡卡池\n您已获得{20 * num}en\n{f1.guide['add_des']}{f1.guide['info']}{f1.guide['wish']}".strip()
            f1.close('add')
    await session.send(strout, auto_escape=True)
    await _f()

@on_command(('card', 'add_des'), only_to_me=False)
@c1
@config.maintain('card')
@config.ErrorHandle(config.logger.card)
async def card_add_des(session: CommandSession):
    qq = session.ctx['user_id']
    n = session.current_arg_text.find('\n')
    if n == -1:
        await session.send('请在卡片名换行后输入描述文本')
        return
    card_name = session.current_arg_text[:n].strip().replace('，', ',')
    des = session.current_arg_text[n + 1:].strip()
    c = card_find(card_name)
    if c is None:
        await session.send('未找到此卡牌')
        return
    strout = ""
    with open_user_storage(qq) as f1, open_user_create(qq) as f2:
        if not f2.check_created(card_name):
            strout = '此卡片不是您首次创造，无法添加描述文本'
            out = False
        else:
            verify = read_verify()
            id_max = max(-1, -1, *[x['id'] for x in verify]) + 1
            verify.append({'card_id': c['id'], 'id': id_max, 'des': des, 'user': qq})
            save_verify(verify)
            des = '\n' + des + '\n'
            strout = f"已提交卡片 {c['name']} 的描述 {des}，待审核，审核成功后会将通知发送至消息箱（默认为私聊）~{f1.guide['check_card']}{f1.guide['wish']}".strip()
            config.logger.card << f"【LOG】用户{qq} 提交卡牌 {c['name']} 的描述 {des}"
            f1.close('add_des')
            out = True
    await session.send(strout, auto_escape=True)
    if out:
        for group in config.group_id_dict['card_verify']:
            await get_bot().send_group_msg(group_id=group, message=f"{qq} 提交卡牌 {c['name']} 的描述 {des}\nid:{id_max}", auto_escape=True)

@on_command(('card', 'userinfo'), only_to_me=False)
@c1
@config.maintain('card')
@config.ErrorHandle(config.logger.card)
async def card_userinfo(session: CommandSession):
    qq = session.ctx['user_id']
    with open_user_storage(qq) as f:
        f.close('info')
        info = f.read_info()
        await session.send(f"""剩余en数：{info['money']}\n今日剩余：免费抽卡次数{info['time']} 创造卡片种类{info['create_type']} 创造卡片张数{info['create_num']}{'''
今日已确认使用en抽卡''' if info['confirm'] else ''}\n消息箱设置：{ {0: '立即私聊', 1: '手动收取', 2: '凌晨定时发送私聊'}[info['message']] }{f'''{f.guide['check_message']}''' if info['message'] == 1 else ''}{f.guide['message']}{f.guide['storage']}{f.guide['confirm'] if info['confirm'] else ''}{f.guide['guide']}{f.guide['comment']}""")

@on_command(('card', 'wishlist'), only_to_me=False)
@c1
@config.maintain('card')
@config.ErrorHandle(config.logger.card)
async def card_wishlist(session: CommandSession):
    if session.current_arg_text != '':
        page = int(session.current_arg_text)
    else:
        page = 1
    qq = session.ctx['user_id']
    with open_user_storage(qq) as f:
        wish = [card_info[i]['name'] for i, data in enumerate(f.yield_all()) if data['wish']]
        if len(wish) == 0:
            await session.send(f'您的愿望单是空的呢{f.guide["fav&wish"]}', auto_escape=True)
            return
        page_count = (len(wish) - 1) // page_max + 1
        if page <= 0 or page > page_count:
            await session.send(f'页码超出范围，您的愿望单共有{page_count}页')
            return
        strout = '，'.join(wish[page_max * (page - 1):page_max * page])
        if page_count != 1:
            strout += f'\npage: {page}/{page_count}'
        f.close('wishlist')
        await session.send(f'您的愿望单包含：\n{strout}{f.guide["storage"]}', auto_escape=True)

@on_command(('card', 'fav'), only_to_me=False)
@c1
@config.maintain('card')
@config.ErrorHandle(config.logger.card)
async def card_fav(session: CommandSession):
    name = session.current_arg_text.strip()
    qq = session.ctx['user_id']
    card = card_find(name)
    if card is None:
        await session.send('未找到卡片')
    else:
        with open_user_storage(qq) as f:
            f.check()
            data = f.read_nocheck(card['id'])
            if data['fav']:
                await session.send('该卡已在您的特别喜欢之内')
            elif data['num'] == 0:
                await session.send('您还未拥有该卡，可' + guide['wish'])
            else:
                f.close('fav&wish')
                data['fav'] = True
                f.save(card['id'], data)
                config.logger.card << f"【LOG】用户{qq} 将卡片{card['name']}加入特别喜欢"
                await session.send(f'已成功将卡片{card["name"]}加入特别喜欢{f.guide["storage"]}')

@on_command(('card', 'wish'), only_to_me=False)
@c1
@config.maintain('card')
@config.ErrorHandle(config.logger.card)
async def card_wish(session: CommandSession):
    name = session.current_arg_text.strip()
    qq = session.ctx['user_id']
    card = card_find(name)
    if card is None:
        await session.send('未找到卡片')
    else:
        with open_user_storage(qq) as f:
            f.check()
            data = f.read_nocheck(card['id'])
            if data['wish']:
                await session.send('该卡已在您的愿望单之内')
            else:
                f.close('wish')
                data['wish'] = True
                f.save(card['id'], data)
                config.logger.card << f"【LOG】用户{qq} 将{'未' if data['num'] == 0 else '已'}拥有的卡片{card['name']}加入愿望单"
                await session.send(f"已成功将{'未' if data['num'] == 0 else '已'}拥有的卡片{card['name']}加入愿望单{f.guide['storage']}{f.guide['wishlist']}")

@on_command(('card', 'set', 'unconfirm'), only_to_me=False)
@c1
@config.maintain('card')
@config.ErrorHandle(config.logger.card)
async def card_unconfirm(session: CommandSession):
    with open_user_storage(session.ctx['user_id']) as f:
        f.close('confirm')
        info = f.read_info()
        info['confirm'] = False
        f.save_info(info)
        config.logger.card << f'【LOG】用户{session.ctx["user_id"]} 取消今日自动使用en抽卡'
        await session.send("已成功取消自动使用en抽卡")

@on_command(('card', 'set', 'message'), only_to_me=False)
@c1
@config.maintain('card')
@config.ErrorHandle(config.logger.card)
async def card_set_message(session: CommandSession):
    if session.current_arg_text in {'0', '1', '2'}:
        qq = session.ctx['user_id']
        with open_user_storage(qq) as f:
            f.close('message')
            info = f.read_info()
            info['message'] = int(session.current_arg_text)
            f.save_info(info)
            config.logger.card << f"【LOG】用户{qq} 修改消息箱设置至{info['message']}：{ {0: '立即私聊', 1: '手动收取', 2: '凌晨定时发送私聊'}[info['message']]}"
            await session.send(f"消息箱设置已修改为：{ {0: '立即私聊', 1: '手动收取', 2: '凌晨定时发送私聊'}[info['message']]}{f.guide['info']}")
    else:
        await session.send("支持参数：\n-card.set.message 0：立即私聊\n-card.set.message 1：手动收取\n-card.set.message 2：凌晨定时发送私聊")

@on_command(('card', 'set', 'guide'), only_to_me=False)
@c1
@config.maintain('card')
@config.ErrorHandle(config.logger.card)
async def card_set_guide(session: CommandSession):
    if session.current_arg_text == 'off':
        off = 255
    elif session.current_arg_text == 'on':
        off = 0
    else:
        await session.send('使用-card.set.guide on或off：开启或关闭全部指令引导。指令引导会在使用一次该指令后自动关闭')
        return
    with open_user_storage(session.ctx['user_id']) as f:
        #f.close('guide')
        info = f.read_info()
        info['guide1'] = off
        info['guide2'] = off
        f.save_info(info)
        config.logger.card << f'用户{session.ctx["user_id"]} 已{"关闭" if off else "开启"}全部指令引导'
        await session.send(f'您已成功{"关闭" if off else "开启"}全部指令引导')

@on_command(('card', 'storage'), only_to_me=False)
@c1
@config.maintain('card')
@config.ErrorHandle(config.logger.card)
async def card_storage(session: CommandSession):
    if session.current_arg_text != '':
        page = int(session.current_arg_text)
    else:
        page = 1
    qq = session.ctx['user_id']
    with open_user_storage(qq) as f:
        have = [(i, data) for i, data in enumerate(f.yield_all()) if data['num'] != 0]
        if len(have) == 0:
            await session.send(f'您的仓库是空的呢{f.guide["draw"]}', auto_escape=True)
            return
        fav = [f"{card_info[i]['name']}x{data['num']}" if data['num'] > 1 else card_info[i]['name']
            for i, data in have if data['fav']]
        not_fav = [f"{card_info[i]['name']}x{data['num']}" if data['num'] > 1 else card_info[i]['name']
            for i, data in have if not data['fav']]
        page_count = (len(have) - 1) // page_max + 1
        if page <= 0 or page > page_count:
            await session.send(f'页码超出范围，您的仓库共有{page_count}页')
            return
        if len(fav) >= page_max * page:
            strout = '特别喜欢：\n' + '，'.join(fav[page_max * (page - 1):page_max * page])
        elif len(fav) >= page_max * (page - 1) and len(fav) != 0:
            strout = '特别喜欢：\n' + '，'.join(fav[page_max * (page - 1):]) + '\n您的卡牌：\n' + '，'.join(not_fav[:page_max * page - len(fav)])
        else:
            strout = '您的卡牌：\n' + '，'.join(not_fav[page_max * (page - 1) - len(fav):page_max * page - len(fav)])
        if page_count != 1:
            strout += f'\npage: {page}/{page_count}'
        f.close('storage')
        await session.send(strout + f'{f.guide["add"]}{f.guide["discard"]}{f.guide["fav&wish"]}', auto_escape=True)

@on_command(('card', 'discard'), only_to_me=False)
@c1
@config.maintain('card')
@config.ErrorHandle(config.logger.card)
async def card_discard(session: CommandSession):
    if session.get('name') is None:
        await session.send('请输入想分解的卡名')
        return
    card = card_find(session.get('name'))
    if card is None:
        await session.send('未找到该卡')
        return
    qq = session.ctx['user_id']
    num = session.get('num')
    if num <= 0:
        await session.send('不能分解非正数张卡')
        return
    with open_user_storage(qq) as f:
        f.check()
        data = f.read_nocheck(card['id'])
        if data['num'] == 0:
            await session.send('您没有此卡，无法分解')
        elif data['num'] < num:
            await session.send(f'您此卡余量不足，只有{data["num"]}张')
        else:
            f.close('discard')
            data['num'] -= num
            info = f.read_info()
            info['money'] += num * 20
            f.save(card['id'], data)
            f.save_info(info)
            config.logger.card << f"【LOG】用户{qq} 分解了{num}张{card['name']}"
            config.logger.card << f'【LOG】用户{qq} 获得了{20 * num}en 剩余{info["money"]}en'
            if data['num'] == 0 and data['fav']:
                data['fav'] = False
            config.logger.card << f'【LOG】用户{qq} 已无{card["name"]}，自动从特别喜欢中删除'
            await session.send(f'您已成功分解{num}张{card["name"]}，现剩余{info["money"]}en{f.guide["info"]}', auto_escape=True)

@card_draw.args_parser
@card_discard.args_parser
async def name_num_parser(session: CommandSession):
    if session.current_arg_text == "":
        session.state['name'] = None
    else:
        s = session.current_arg_text.strip()
        i = s.rfind(' ')
        if i == -1:
            session.state['name'] = s
            session.state['num'] = 1
        else:
            session.state['name'] = s[:i]
            try:
                session.state['num'] = int(s[i + 1:])
            except ValueError:
                session.state['num'] = -1

@card_add.args_parser
async def add_parser(session: CommandSession):
    if session.current_arg_text == "":
        session.state['name'] = None
    else:
        s = session.current_arg_text.strip()
        n = s.find('\n')
        if n == -1:
            session.state['des'] = None
        else:
            session.state['des'] = s[n + 1:].strip()
            s = s[:n].strip()
        i = s.rfind(' ')
        if i == -1:
            session.state['name'] = s
            session.state['num'] = 1
        else:
            session.state['name'] = s[:i].strip()
            try:
                session.state['num'] = int(s[i + 1:])
            except ValueError:
                session.state['num'] = -1

@on_command(('card', 'message'), only_to_me=False)
@c1
@config.maintain('card')
@config.ErrorHandle(config.logger.card)
async def card_check(session: CommandSession):
    with open_user_storage(session.ctx['user_id']) as f:
        message = f.check_message()
        if message == []:
            await session.send('消息箱为空')
        else:
            f.close('check_message')
            config.logger.card << f'【LOG】用户{session.ctx["user_id"]} 已接收消息：\n' + '\n'.join(message)
            await session.send('您的消息箱包含以下消息：\n' + '\n'.join(message))

@on_command(('card', 'comment'), only_to_me=False)
@c1
@config.maintain('card')
@config.ErrorHandle(config.logger.card)
async def card_comment(session: CommandSession):
    with open(config.rel(r'games\card\comment.json'), encoding='utf-8') as f:
        comments = json.load(f)
    import datetime
    comments.append({'qq': session.ctx['user_id'], 'time': datetime.datetime.now().isoformat(' '), 'content': session.current_arg})
    with open(config.rel(r'games\card\comment.json'), 'w', encoding='utf-8') as f:
        f.write(json.dumps(comments, ensure_ascii=False, indent=4, separators=(',', ': ')))
    config.logger.card << f"【LOG】用户{session.ctx['user_id']} 留言：\n{session.current_arg}"
    with open_user_storage(session.ctx["user_id"]) as f:
        f.close('message')
    await session.send('您已成功送出一条留言~感谢您的反馈')
    for group in config.group_id_dict['card_verify']:
        await get_bot().send_group_msg(group_id=group, message=f'用户{session.ctx["user_id"]} 留言：\n{session.current_arg}', auto_escape=True)

@on_command(('card', 'help'), only_to_me=False)
@c1
@config.maintain('card')
@config.ErrorHandle(config.logger.card)
async def card_help(session: CommandSession):
    await call_command(get_bot(), session.ctx, ('help',), current_arg="card")
    with open_user_storage(session.ctx["user_id"]) as f:
        f.close('message')

@on_command(('card', 'add_group'), only_to_me=False, permission=permission.SUPERUSER)
@config.ErrorHandle
async def card_add_group(session: CommandSession):
    lst = session.current_arg_text.split('\n')
    group = lst[0].strip()
    num = int(lst[-1])
    if num >= 65536:
        await session.send(">65536")
        return
    add_cardname(map(lambda x: (x.strip(), num, None), lst[1:-1]), group=group)
    await session.send("successfully added cards")
    config.logger.card << f'【LOG】卡池新增{group}卡组共{len(lst) - 2}种，每种{num}张'

@on_command(('card', 'vlist'), only_to_me=False, aliases=('cvl',), permission=permission.SUPERUSER)
@config.ErrorHandle
async def card_vlist(session: CommandSession):
    verify = read_verify()
    if len(verify) == 0:
        await session.send('empty')
    else:
        await session.send('\n'.join([(f"""id:{x['id']} {x['name']}\n\t{' '.join([f"{a['qq']}的{a['num']}张" for a in x['user']])}""" if 'name' in x else f"""id:{x['id']} {card_info[x['card_id']]['name']} 的描述\n{x['des']}\n\t{x['user']}""") for x in verify]))

@on_command(('card', 'verify'), only_to_me=False, aliases=('cvf',), permission=permission.SUPERUSER)
@config.ErrorHandle
async def card_verify(session: CommandSession):
    verify = read_verify()
    l = session.current_arg_text.strip().split(' ')
    if len(l) == 1:
        id = int(l[0])
        if_pass = True
    else:
        id = int(l[0])
        if_pass = (l[1].upper() == 'T')
    a = more_itertools.only(filter(lambda x: x['id'] == id, verify))
    if a is None:
        await session.send('wrong id')
        return
    elif if_pass:
        if 'name' in a:
            add_cardname([(a['name'], functools.reduce(lambda x, y: x + y, [x['num'] for x in a['user']]), None if 'des' not in a else a['des'])])
            add_new_card(len(card_info) - 1)
            for x in a['user']:
                with open_user_create(x['qq']) as f:
                    f.create(len(card_info) - 1, x['num'], True) # 一定是add一个cardname
                with open_user_storage(x['qq']) as f:
                    await f.send(f"您创建的卡片 {a['name']} 已通过审核，欢迎明日查看新卡卡池")
            await session.send('成功审核 通过')
        elif 'card_id' in a:
            card_info[a['card_id']]['des'] = a['des']
            save_card_info()
            with open_user_storage(a['user']) as f:
                await f.send(f"您为卡片 {card_info[a['card_id']]['name']} 添加的描述\n{a['des']}\n已通过审核")
            await session.send('成功审核 通过')
    else:
        if 'name' in a:
            for x in a['user']:
                with open_user_storage(x['qq']) as f:
                    await f.send(f"十分抱歉，您创建的卡片 {a['name']} 未通过审核")
            await session.send('成功审核 未通过')
        elif 'card_id' in a:
            with open_user_storage(a['user']) as f:
                await f.send(f"十分抱歉，您为卡片 {card_info[a['card_id']]['name']} 添加的描述\n{a['des']}\n未通过审核")
            await session.send('成功审核 未通过')
    verify.remove(a)
    save_verify(verify)

@on_command(('card', 'verify_all'), only_to_me=False, aliases=('cva',), permission=permission.SUPERUSER)
@config.ErrorHandle
async def card_verify_all(session: CommandSession):
    verify = read_verify()
    send = {}
    send_des = {}
    for a in verify:
        if 'name' in a:
            add_cardname([(a['name'], functools.reduce(lambda x, y: x + y, [x['num'] for x in a['user']]), None if 'des' not in a else a['des'])])
            add_new_card(len(card_info) - 1)
            for x in a['user']:
                with open_user_create(x['qq']) as f:
                    f.create(len(card_info) - 1, x['num'], True) # 一定是add一个cardname
                if x['qq'] in send:
                    send[x['qq']].append(a['name'])
                else:
                    send[x['qq']] = [a['name']]
        elif 'card_id' in a:
            card_info[a['card_id']]['des'] = a['des']
            save_card_info()
            if a['user'] in send_des:
                send_des[a['user']].append(f"您为卡片 {card_info[a['card_id']]['name']} 添加的描述\n{a['des']}\n已通过审核")
            else:
                send_des[a['user']] = [f"您为卡片 {card_info[a['card_id']]['name']} 添加的描述\n{a['des']}\n已通过审核"]
    for qq, names in send.items():
        with open_user_storage(qq) as f:
            await f.send(f"您创建的卡片 {'，'.join(names)} 已通过审核，欢迎明日查看新卡卡池")
    for qq, strs in send_des.items():
        with open_user_storage(qq) as f:
            for s in strs:
                await f.send(s)
    await session.send('成功审核 通过')
    verify = []
    save_verify(verify)

@on_command(('card', 'reply'), only_to_me=False, permission=permission.SUPERUSER)
@config.ErrorHandle
async def card_reply(session: CommandSession):
    n = session.current_arg_text.find('\n')
    qq = int(session.current_arg_text[:n])
    content = session.current_arg_text[n + 1:]
    with open_user_storage(qq) as f:
        await f.send('留言回复：\n' + content)
    await session.send('消息已送出')

@scheduler.scheduled_job('cron', hour='05')
@config.ErrorHandle(config.logger.card)
async def update():
    global daily_pool_all, daily_pool
    #new card pool
    new_card = read_new_card()
    all_new = list(itertools.chain(*new_card))
    all_new.sort()
    all_new = list(more_itertools.unique_justseen(all_new))
    pool_info = more_itertools.only(filter(lambda x: x['id'] == 0, daily_pool))
    num = functools.reduce(lambda x, y: x + y, map(lambda x: pool[x], pool_info['cards']), 0)
    if pool_info is None:
        daily_pool_all.append({"type": "new", "name": "新卡卡池", "id": 0, "status": 3 if num == 0 else 1, "cards": all_new})
    else:
        pool_info['cards'] = all_new
        if num == 0:
            pool_info['status'] = 3
        else:
            pool_info['status'] = 1
    new_card.pop(0)
    new_card.append([])
    save_new_card(new_card)
    #daily pool
    for i in range(1, daily_pool_num + 1):
        #generate
        num = 0
        all = list(range(len(card_info)))
        pool_now = []
        while num < daily_pool_cap:
            p = random.choice(all)
            all.remove(p)
            if num + pool[p] >= daily_pool_exceed:
                config.logger.card << f'【WARNING】在生成每日卡池时出现超额，卡池为{pool_now}共{num}张，试图加入{p}共{pool[p]}张失败'
                continue
            pool_now.append(p)
            num += pool[p]
            if len(all) == 0:
                break
        pool_info = more_itertools.only(filter(lambda x: x['id'] == i, daily_pool))
        pool_now.sort()
        if pool_info is None:
            daily_pool_all.append({"type": "daily", "name": "每日卡池" + str(i), "id": i, "status": 1, "cards": pool_now})
        else:
            pool_info['cards'] = pool_now
            pool_info['status'] = 1
    #event pool
    for p in daily_pool:
        if p['type'] == 'event':
            if date.fromisoformat(p['end_date']) <= date.today():
                p['status'] = 0
            elif p['status'] == 2 and date.fromisoformat(p['begin_date']) <= date.today():
                p['status'] = 1
    save_daily_pool()
    #person info
    for qq in os.listdir(config.rel(r'games\card\user_storage')):
        with open_user_storage(int(qq)) as f:
            info = f.read_info()
            info['time'] = daily_draw
            info['create_type'] = daily_create_type
            info['create_num'] = daily_create
            info['confirm'] = False
            f.save_info(info)
            if info['message'] == 2:
                message = f.check_message()
                if message != []:
                    config.logger.card << f'【LOG】已定时向用户{f.qq}发送消息：\n' + '\n'.join(message)
                    await get_bot().send_private_msg(user_id=f.qq, message='\n'.join(message), auto_escape=True)
    for group in config.group_id_dict['card_verify']:
        await get_bot().send_group_msg(group_id=group, message='card updated')

@on_command(('card', 'maintain'), only_to_me=False, permission=permission.SUPERUSER)
@config.ErrorHandle
async def card_maintain(session: CommandSession):
    config.maintain_str['card'] = session.current_arg_text
    config.maintain_str_save()
    await session.send('已进入维护状态')

@on_command(('card', 'oshirase'), only_to_me=False, permission=permission.SUPERUSER)
@config.ErrorHandle
async def card_oshirase(session: CommandSession):
    for qq in os.listdir(config.rel(r'games\card\user_storage')):
        with open_user_storage(int(qq)) as f:
            await f.send('【抽卡游戏公告】' + session.current_arg_text)
    await session.send('成功发送')

@on_command(('card', 'update'), only_to_me=False, permission=permission.SUPERUSER)
@config.ErrorHandle
async def card_update(session: CommandSession):
    global daily_pool_all, daily_pool
    #new card pool
    new_card = read_new_card()
    all_new = list(itertools.chain(*new_card))
    all_new.sort()
    all_new = list(more_itertools.unique_justseen(all_new))
    pool_info = more_itertools.only(filter(lambda x: x['id'] == 0, daily_pool))
    num = functools.reduce(lambda x, y: x + y, map(lambda x: pool[x], pool_info['cards']), 0)
    if pool_info is None:
        daily_pool_all.append({"type": "new", "name": "新卡卡池", "id": 0, "status": 3 if num == 0 else 1, "cards": all_new})
    else:
        pool_info['cards'] = all_new
        if num == 0:
            pool_info['status'] = 3
        else:
            pool_info['status'] = 1
    new_card.pop(0)
    new_card.append([])
    save_new_card(new_card)
    #daily pool
    for i in range(1, daily_pool_num + 1):
        #generate
        num = 0
        all = list(range(len(card_info)))
        pool_now = []
        while num < daily_pool_cap:
            p = random.choice(all)
            all.remove(p)
            if num + pool[p] >= daily_pool_exceed:
                config.logger.card << f'【WARNING】在生成每日卡池时出现超额，卡池为{pool_now}共{num}张，试图加入{p}共{pool[p]}张失败'
                continue
            pool_now.append(p)
            num += pool[p]
            if len(all) == 0:
                break
        pool_info = more_itertools.only(filter(lambda x: x['id'] == i, daily_pool))
        pool_now.sort()
        if pool_info is None:
            daily_pool_all.append({"type": "daily", "name": "每日卡池" + str(i), "id": i, "status": 1, "cards": pool_now})
        else:
            pool_info['cards'] = pool_now
            pool_info['status'] = 1
    #event pool
    for p in daily_pool:
        if p['type'] == 'event':
            if date.fromisoformat(p['end_date']) <= date.today():
                p['status'] = 0
            elif p['status'] == 2 and date.fromisoformat(p['begin_date']) <= date.today():
                p['status'] = 1
    save_daily_pool()
    #person info
    for qq in os.listdir(config.rel(r'games\card\user_storage')):
        with open_user_storage(int(qq)) as f:
            info = f.read_info()
            info['time'] = daily_draw
            info['create_type'] = daily_create_type
            info['create_num'] = daily_create
            info['confirm'] = False
            f.save_info(info)
            if info['message'] == 2:
                message = f.check_message()
                if message != []:
                    config.logger.card << f'【LOG】已定时向用户{f.qq}发送消息：\n' + '\n'.join(message)
                    await get_bot().send_private_msg(user_id=f.qq, message='\n'.join(message), auto_escape=True)

@on_command(('card', 'test'), only_to_me=False, permission=permission.SUPERUSER)
@config.ErrorHandle
async def card_test(session: CommandSession):
    await session.send(str(functools.reduce(lambda x, y: x + y, pool)))

