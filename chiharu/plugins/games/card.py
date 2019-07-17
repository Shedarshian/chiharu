import random
import json
import itertools
import functools
import more_itertools
from enum import IntEnum
import contextlib
import os
from typing import Dict, Iterable, Tuple, Awaitable, List
from datetime import date, datetime
import chiharu.plugins.config as config
from nonebot import on_command, CommandSession, get_bot, permission
from nonebot.command import call_command
config.logger.open('card')

# -game card 引导至card的指令列表
# √抽卡指令（参数：卡池，张数） 参数为空时引导至查看卡池 限额抽完时引导至查看个人信息 再次输入确认使用资源抽卡
# √查看卡池指令（参数：卡池或空） 引导抽卡指令 查看具体卡池 引导至私聊卡池信息
# √添加卡指令（参数：卡名，张数） 限额抽完时引导至查看个人信息
# 查看个人信息，包含资源数，仓库量，剩余免费抽卡次数（级别？） 引导至查看库存与创造卡与留言簿
# 查看库存指令（翻页） 引导至分解卡与创造卡
# 仓储操作指令，包含加入特别喜欢，加入愿望单
# 分解卡指令
# 留言簿指令
# 凌晨：更新每日限额，更新每日卡池
# √批量添加指令
# √查看审核指令
# √审核通过指令
# 预约开放活动卡池指令
# 维护？
# status: 1 已开放 0 已结束 2 未开始 3 已空

def to_byte(num):
    return bytes([num // 256, num % 256])
guide = {'draw': '使用-card.draw 卡池id/名字 抽卡次数 进行抽卡，次数不填默认为单抽，\n-card.draw5 卡池id/名字 直接进行五连抽卡',
    'check_detail': '私聊-card.check 卡池id/名字 查询卡池具体信息（刷屏预警）',
    'check': '使用-card.check 不带参数 查询卡池列表',
    'add': '使用-card.add 卡片名字 张数 创造卡片加入次日新卡卡池与每日随机卡池 张数不填默认为1张',
    'info': '使用-card.userinfo 查看个人信息，包含en数，剩余免费抽卡次数等等',
    'confirm': '使用-card.set.unconfirm 取消今日确认',
    'message': '使用-xxxxxx 设置消息箱提醒'
}

with open(config.rel(r"games\card\pool"), 'rb') as f:
    pool = list(itertools.starmap(lambda x, y: int(x) * 256 + int(y), more_itertools.chunked(f.read(), 2)))
with open(config.rel(r"games\card\card_info.json"), encoding='utf-8') as f:
    card_info = json.load(f)
with open(config.rel(r"games\card\daily_pool.json"), encoding='utf-8') as f:
    daily_pool_all = json.load(f)
    daily_pool = list(filter(lambda x: x['status'] == 1 or x['status'] == 3, daily_pool_all))
    daily_pool_draw = list(map(lambda x: x['cards'], daily_pool))
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

def get_card_names(*l):
    return '，'.join([card_info[i]['name'] for i in l])
def daily_pool_find(s):
    return more_itertools.only(filter(lambda x: x['name'] == s or str(x['id']) == s, daily_pool))
def card_find(s):
    return more_itertools.only(filter(lambda x: x['name'] == s, card_info))

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
    def init_begin(self):
        self.file = open(self.path, 'x+b' if self.if_binary else 'x+')
        self.file.write(bytes([0, 0, 10, 10, 0, 30, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]))
    def check(self):
        if os.stat(self.path).st_size < 4 * len(pool) + 16:
            self.file.seek(0, 2)
            self.file.write(bytes(map(lambda x: 0, range(4 * len(pool) + 16 - os.stat(self.path).st_size))))
            self.file.flush()
    def read_info(self):
        # 16 byte data for user info
        self.file.seek(0)
        a, b, c, d, e, f, g, h, i, j, k, l, m, n, o, p = self.file.read(16)
        return {'money': a * 256 + b, 'confirm': bool(c & 128), 'time': c % 128, 'create_type': d, 'create_num': e * 256 + f, 'message': g % 16}
    def save_info(self, val):
        self.file.seek(0)
        self.file.write(bytes([val['money'] // 256, val['money'] % 256, val['confirm'] * 128 + val['time'], val['create_type'], val['create_num'] // 256, val['create_num'] % 256, val['message'], 0, 0, 0, 0, 0, 0, 0, 0, 0]))
    def read_nocheck(self, id):
        # 4 byte data for each card
        self.file.seek(4 * id + 16)
        a, b, c, d = self.file.read(4)
        return {'num': a * 256 + b, 'fav': bool(d & 2), 'wish': bool(d & 1)}
    def save(self, id, dct):
        self.file.seek(4 * id + 16)
        self.file.write(bytes([dct['num'] // 256, dct['num'] % 256, 0, dct['fav'] * 2 + dct['wish']]))
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
        info = self.read_info()
        if info['message'] == 0:
            await get_bot().send_private_msg(user_id=self.qq, message=msg + f'\n{guide["message"]}', auto_escape=True)
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
    def create(self, id, num, is_first):
        self.check()
        data = self.read_nocheck(id)
        data['num'] += num
        data['first'] = is_first
        self.save(id, data)
    def check_created(self, name):
        try:
            with open(self.path + '.txt', 'r') as f:
                self.c = list(map(lambda x: x.strip(), f.readlines()))
        except FileNotFoundError:
            self.c = []
        return name in self.c
    def new_created_type_checked(self, name):
        self.c.append(name)
        with open(self.path + '.txt', 'w') as f:
            for i in self.c:
                f.write(i + '\n')

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
def pool_des(pool_info: Dict):
    title = {'event': '活动卡池', 'daily': '每日卡池', 'new': '新卡卡池'}
    not_zero = list(filter(lambda x: pool[x] > 0, pool_info['cards']))
    only_one = list(filter(lambda x: pool[x] == 1, pool_info['cards']))
    num = functools.reduce(lambda x, y: x + y, map(lambda x: pool[x], pool_info['cards']))
    return f"""{title[pool_info['type']]}{f'''：{pool_info['name']} id：{pool_info['id']}
{pool_info['description']} {pool_info['end_date']} 截止''' if pool_info['type'] == 'event' else ''}
包含{_des(not_zero)}共{num}张。{f'''
{_des(only_one)}只余一张！''' if len(only_one) != 0 else ''}"""
def pool_des_detail(pool_info: Dict):
    title = {'event': '活动卡池', 'daily': '每日卡池', 'new': '新卡卡池'}
    not_zero = list(filter(lambda x: pool[x] > 0, pool_info['cards']))
    return f"""{title[pool_info['type']]}{f'''：{pool_info['name']} id：{pool_info['id']}
{pool_info['description']} {pool_info['end_date']} 截止''' if pool_info['type'] == 'event' else ''}
包含卡牌：{'，'.join(map(lambda x: f'''{card_info[x]['name']}x{pool[x]}''', not_zero))}"""

def center_card(*args):
    return ""

def add_cardname(arg: Iterable[Tuple[int, int]], **kwargs):
    global card_info, pool
    with open(config.rel(r"games\card\pool"), 'ab') as f:
        for name, num in arg:
            card_info.append(dict(name=name, id=len(card_info), **kwargs))
            pool.append(num)
            f.write(to_byte(num)) # 每个卡最多65535张
    save_card_info()
def add_card(arg: Iterable[Tuple[int, int]]):
    global pool
    with open(config.rel(r"games\card\pool"), 'rb+') as f:
        for id, num in arg:
            f.seek(2 * id)
            pool[id] += num
            f.write(to_byte(pool[id]))

@on_command(('card', 'draw'), only_to_me=False, aliases=('抽卡'))
@config.ErrorHandle(config.logger.card)
@config.maintain('card')
async def card_draw(session: CommandSession):
    if session.get('name') is None:
        # 卡池介绍
        await session.send('\n\n'.join([pool_des(x) for x in daily_pool]) + '\n\n' + guide['draw'], auto_escape=True)
    else:
        qq = session.ctx['user_id']
        name, num = session.get('name'), session.get('num')
        if num > 5 or num <= 0:
            await session.send('一次最多五连抽卡！')
            return
        p = daily_pool_find(name)
        if p is None:
            await session.send('未发现此卡池\n' + guide['draw'])
        elif p['status'] == 3:
            await session.send('卡池已空，无法继续抽取')
        else:
            config.logger.card << f'【LOG】用户{qq} 于卡池{p["id"]} 进行{num}次抽卡'
            with open_user_storage(qq) as f:
                data = {'empty': False, 'payed': False, 'money': 0}
                info = f.read_info()
                weight = list(map(lambda x: pool[x], p['cards']))
                pool_num = functools.reduce(lambda x, y: x + y, weight)
                if pool_num <= num:
                    num = pool_num
                    data['empty'] = True
                if info['time'] == 0:
                    if not info['confirm']:
                        if info['money'] >= 100:
                            info['confirm'] = True
                            f.save_info(info)
                            await session.send(f'您今日的免费10次抽卡次数已用尽，是否确认使用en进行抽卡？再次输入抽卡指令确认\n{guide["info"]}\n{guide["confirm"]}', auto_escape=True) # 取消确认？？？ TODO
                            config.logger.card << f'【LOG】用户{qq} 免费抽卡次数已用尽 可以使用en进行抽卡'
                        else:
                            await session.send(f'您今日的免费10次抽卡次数已用尽\n{guide["info"]}', auto_escape=True)
                            config.logger.card << f'【LOG】用户{qq} 免费抽卡次数已用尽'
                        return
                    else:
                        if info['money'] >= 100 * num:
                            info['money'] -= 100 * num
                            data['payed'] = True
                            data['money'] = info['money']
                            f.save_info(info)
                        else:
                            await session.send(f'您剩余en已不足\n\n您还有{info["money"]}en，每100en可以抽一张卡\n{guide["info"]}', auto_escape=True)
                            config.logger.card << f'【LOG】用户{qq} en数不足'
                            return
                elif info['time'] < num:
                    await session.send(f'您今日的免费10次抽卡次数不足，只剩{info["time"]}次\n{guide["info"]}', auto_escape=True)
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
            await session.send(f"""{'''您已把卡池抽空！
''' if data['empty'] else ''}恭喜您抽中：
{get_card_names(*get)}{f'''
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
@config.ErrorHandle(config.logger.card)
@config.maintain('card')
async def card_draw_5(session: CommandSession):
    if session.current_arg_text == "":
        await call_command(get_bot(), session.ctx, ('card', 'draw'), current_arg="")
    else:
        await call_command(get_bot(), session.ctx, ('card', 'draw'), current_arg=session.current_arg_text.strip() + ' 5')

@on_command(('card', 'check'), only_to_me=False)
@config.ErrorHandle(config.logger.card)
@config.maintain('card')
async def card_check(session: CommandSession):
    if session.current_arg_text == "":
        await session.send('\n\n'.join([pool_des(x) for x in daily_pool]) + f'\n\n{guide["draw"]}\n{guide["check_detail"]}', auto_escape=True)
    else:
        p = daily_pool_find(session.current_arg_text)
        if p is None:
            await session.send('未发现此卡池')
        else:
            await session.send(pool_des_detail(find[0]) + f'\n\n{guide["draw"]}\n{guide["check"]}', auto_escape=True)

@on_command(('card', 'add'), only_to_me=False)
@config.ErrorHandle(config.logger.card)
@config.maintain('card')
async def card_add(session: CommandSession):
    if session.get('name') is None:
        await session.send(guide['add'])
        return
    qq = session.ctx['user_id']
    name, num = session.get('name'), session.get('num')
    if num <= 0:
        await session.send('不能创造负数张卡')
    with open_user_storage(qq) as f1, open_user_create(qq) as f2:
        info = f1.read_info()
        n = '\n'
        created = f2.check_created(name)
        if info['create_type'] < 1 and not created:
            await session.send(f"您今日创造卡片的种类已达上限，上限为10种30张，您只剩{info['create_type']}种{info['create_num']}张。{n}{guide['info']}", auto_escape=True)
        elif info['create_num'] < num:
            await session.send(f"您今日创造卡片的剩余张数不足，上限为10种30张，您只剩{info['create_type']}种{info['create_num']}张。{n}{guide['info']}", auto_escape=True)
        elif '\n' in name or '\t' in name or '\r' in name:
            await session.send("卡片名中含有非法字符，未通过")
        else:
            c = card_find(name)
            if not created:
                info['create_type'] -= 1
            info['create_num'] -= num
            if c is None:
                # new card 加入审核
                f1.save_info(info)
                f2.new_created_type_checked(name)
                verify = read_verify()
                a = more_itertools.only(filter(lambda x: x['name'] == name, verify))
                if a is None:
                    id_max = max(-1, -1, *[x['id'] for x in verify]) + 1
                    verify.append({'name': name, 'id': id_max, 'user': [{'qq': qq, 'num': num}]})
                else:
                    b = more_itertools.only(filter(lambda x: x['qq'] == qq, a['user']))
                    if b is None:
                        a['user'].append({'qq': qq, 'num': num})
                    else:
                        b['num'] += num
                save_verify(verify)
                info['money'] += 20 * num
                f1.save_info(info)
                config.logger.card << f"【LOG】用户{qq} 提交卡片名 {name} ，{num}张，待审核"
                config.logger.card << f'【LOG】用户{qq} 获得了{20 * num}en 剩余{info["money"]}en'
                await session.send(f"已提交卡片 {name} ，待审核，审核成功后会将通知发送至消息箱（默认为私聊）~\n您已获得{20 * num}en\n\n{guide['check']}\n{guide['info']}", auto_escape=True)
                for group in config.group_id_dict['card_verify']:
                    await get_bot().send_group_msg(group_id=group, message=f'用户{qq} 提交卡片名\n{name}\n{num}张', auto_escape=True)
            else:
                add_card(c['id'])
                f2.create(c['id'], num, False)
                info['money'] += 20 * num
                f1.save_info(info)
                config.logger.card << f"【LOG】用户{qq} 创造卡片{c['id']}，{num}张"
                config.logger.card << f'【LOG】用户{qq} 获得了{20 * num}en 剩余{info["money"]}en'
                await session.send(f"成功放入卡片 {c['name']} {num}张，欢迎明日查看新卡卡池\n您已获得{20 * num}en\n\n{guide['check']}\n{guide['info']}", auto_escape=True)

@card_draw.args_parser
@card_add.args_parser
async def _(session: CommandSession):
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
            session.state['num'] = int(s[i + 1:])

@on_command(('card', 'userinfo'), only_to_me=False)
@config.ErrorHandle(config.logger.card)
async def card_userinfo(session: CommandSession):
    with open_user_storage(session.ctx['user_id']) as f:
        info = f.read_info()
        await session.send(f"""剩余en数：{info['money']}\n今日剩余：免费抽卡次数{info['time']} 创造卡片种类{info['create_type']} 创造卡片张数{info['create_num']}{'''
今日已确认使用en抽卡''' if info['confirm'] else ''}\n消息箱设置：{ {0: '立即私聊', 1: '手动收取', 2: '凌晨定时发送私聊'}[info['message']] }\n\n{guide['message']}""")

@on_command(('card', 'set', 'unconfirm'), only_to_me=False, permission=permission.SUPERUSER)
@config.ErrorHandle
async def card_unconfirm(session: CommandSession):
    with open_user_storage(session.ctx['user_id']) as f:
        info = f.read_info()
        info['confirm'] = False
        f.save_info(info)
        await session.send("已成功取消自动使用en抽卡")

@on_command(('card', 'add_group'), only_to_me=False, permission=permission.SUPERUSER)
@config.ErrorHandle
async def card_add_group(session: CommandSession):
    lst = session.current_arg_text.split('\n')
    group = lst[0].strip()
    num = int(lst[-1])
    if num >= 65536:
        await session.send(">65536")
        return
    add_cardname(map(lambda x: (x.strip(), num), lst[1:-1]), group=group)
    await session.send("successfully added cards")
    config.logger.card << f'【LOG】卡池新增{group}卡组共{len(lst) - 2}种，每种{num}张'

@on_command(('card', 'vlist'), only_to_me=False, permission=permission.SUPERUSER)
@config.ErrorHandle
async def card_vlist(session: CommandSession):
    verify = read_verify()
    if len(verify) == 0:
        await session.send('empty')
    else:
        await session.send('\n'.join([f"""id:{x['id']} {x['name']}\n\t{' '.join([f"{a['qq']}的{a['num']}张" for a in x['user']])}""" for x in verify]))

@on_command(('card', 'verify'), only_to_me=False, permission=permission.SUPERUSER)
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
        add_cardname([(a['name'], functools.reduce(lambda x, y: x + y, [x['num'] for x in a['user']]))])
        for x in a['user']:
            with open_user_create(x['qq']) as f:
                f.create(len(card_info) - 1, x['num'], True) # 一定是add一个cardname
            with open_user_storage(x['qq']) as f:
                await f.send(f"您创建的卡片 {a['name']} 已通过审核，欢迎明日查看新卡卡池")
        await session.send('成功审核 通过')
    else:
        for x in a['user']:
            with open_user_storage(x['qq']) as f:
                await f.send(f"十分抱歉，您创建的卡片 {a['name']} 未通过审核")
        await session.send('成功审核 未通过')
    verify.remove(a)
    save_verify(verify)