import random
import json
import itertools
import functools
from enum import IntEnum
import contextlib
import os
from typing import Dict, Iterable, Tuple, Awaitable, List
from datetime import date
import chiharu.plugins.config as config
from nonebot import on_command, CommandSession, get_bot, permission

# -game card 引导至card的指令列表
# 抽卡指令（参数：卡池，张数） 参数为空时引导至查看卡池 限额抽完时引导至查看个人信息 再次输入确认使用资源抽卡
# 查看卡池指令（参数：卡池或空） 引导抽卡指令 查看具体卡池 引导至私聊卡池信息
# 添加卡指令（参数：卡名，张数） 引导至查看卡池
# 查看个人信息，包含资源数，仓库量，剩余免费抽卡次数（级别？） 引导至查看库存与分解卡与留言簿
# 查看库存指令（翻页）
# 仓储操作指令，包含加入特别喜欢，加入愿望单
# 分解卡指令
# 留言簿指令
# 批量添加指令
# 查看审核指令
# 审核通过指令
# 预约开放活动卡池指令
# 维护？
# status: 1 已开放 0 已结束 2 未开始 3 已空

def to_byte(num):
    return bytes([num // 256, num % 256])

with open(config.rel(r"games\card\pool"), 'rb') as f:
    pool = list(itertools.starmap(lambda x, y: int(x) * 256 + int(y), config.group(2, f.read())))
with open(config.rel(r"games\card\card_info.json"), encoding='utf-8') as f:
    card_info = json.load(f)
with open(config.rel(r"games\card\daily_pool.json"), encoding='utf-8') as f:
    daily_pool_all = json.load(f)
    daily_pool = list(filter(lambda x: x['status'] == 1, daily_pool_all))
def save_card_info():
    with open(config.rel(r"games\card\card_info.json"), 'w', encoding='utf-8') as f:
        f.write(json.dumps(card_info, ensure_ascii=False, indent=4, separators=(',', ': ')))
def save_pool():
    with open(config.rel(r"games\card\pool"), 'wb') as f:
        f.write(bytes(itertools.chain(*map(lambda x: [x // 256, x % 256], pool))))
def save_daily_pool():
    with open(config.rel(r"games\card\daily_pool.json"), 'w', encoding='utf-8') as f:
        f.write(json.dumps(daily_pool_all, ensure_ascii=False, indent=4, separators=(',', ': ')))
maintain_str = ""

# class user:
#     def __init_subclass__(self, path):
#         self.path_all = config.rel(path)
#     def __init__(self, index):
#         self.path = self.path_all % index
#         try:
#             with open(self.path, encoding='utf-8') as f:
#                 self.val = json.load(f)
#         except FileNotFoundError:
#             self.val = {}
class user_info:
    def __init_subclass__(cls, path):
        cls.path_all = config.rel(path)
    def __init__(self, index, operate='r'):
        self.path = self.path_all % index
        self.file = open(self.path, '+')
        # if operate != 'r' and operate != 'w':
        #     raise ValueError
        # self.operate = operate
    def __del__(self):
        self.file.close()
class user_storage(user, path=r"games\card\user_storage\%i"):
    def check(self):
        if os.stat(self.path).st_size < 4 * len(pool):
            self.file.seek(0, 2)
            self.file.write(bytes(map(lambda x: 0, range(4 * len(pool) - os.stat(self.path).st_size))))
            self.file.flush()
    def read(self, id):
        self.file.seek(4 * id)
        a, b, c, d = self.file.read(4)
        return {'num': a * 256 + b, 'fav': bool(d & 2), 'wish': bool(d & 1)}
    def save(self, id, dct):
        self.file.seek(4 * id)
        self.file.write(bytes([red['num'] // 256, red['num'] % 256, 0, red['fav'] * 2 + red['wish']]))
    # 4 byte data for each card
    def give(self, *args) -> Dict[str, List[int]]:
        self.check()
        ret = {'max': [], 'wish_reset': []}
        for i in args:
            data = self.read(i)
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
class user_create(user, path=r"games\card\user_create\%i.json"):
    pass
@contextlib.contextmanager
def open_user_create(qq, operate='r'):
    resource = user_create(qq, operate)
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
#    f.give(id)

def _des(l, if_len=True, max=3):
    if len(l) > max:
        return '，'.join(map(lambda x: card_info[x]['name'], random.sample(l, k=max))) + f'等{len(l)}种' if if_len else ''
    else:
        return '，'.join(map(lambda x: card_info[x]['name'], l))
def pool_des(pool_info: Dict):
    title = {'event': '活动卡池', 'daily': '每日卡池', 'new': '新卡卡池'}
    not_zero = list(filter(lambda x: pool[x] > 0, pool_info['cards']))
    if len(not_zero) == 0:
        #raise
        pass
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

def add_cardname(names, num=0, **kwargs):
    global card_info, pool
    with open(config.rel(r"games\card\pool"), 'ab') as f:
        for name in names:
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

# 维护
def maintain(f: Awaitable):
    async def _(session: CommandSession):
        if maintain_str != "":
            await session.send(maintain_str)
        else:
            await f()
    return _

@on_command(('card', 'draw'), only_to_me=False)
@config.ErrorHandle
@maintain
async def card_draw(session: CommandSession):
    if session.current_arg_text == "":
        # 卡池介绍
        await session.send('\n\n'.join(map(lambda x: pool_des(x), daily_pool)) + '\n\n使用-card.draw 卡池id 抽卡次数 进行抽卡', auto_escape=True)
    pass

@on_command(('card', 'check'), only_to_me=False)
@config.ErrorHandle
@maintain
async def card_check(session: CommandSession):
    if session.current_arg_text == "":
        await session.send('\n\n'.join(map(lambda x: pool_des(x), daily_pool)) + '\n\n使用-card.draw 卡池id 抽卡次数 进行抽卡\n私聊-card.check 卡池id 查询卡池具体信息（刷屏预警）', auto_escape=True)
    else:
        id = int(session.current_arg_text)
        find = list(filter(lambda x: x['id'] == id, daily_pool))
        if len(find) == 0:
            await session.send('未发现此id的卡池')
            return
        await session.send(pool_des_detail(find[0]) + '\n\n使用-card.draw 卡池id 抽卡次数 进行抽卡\n-card.check 不带参数 查询卡池列表', auto_escape=True)

@on_command(('card', 'add'), only_to_me=False)
@config.ErrorHandle
@maintain
async def card_add(session: CommandSession):
    pass

@on_command(('card', 'add_group'), only_to_me=False, permission=permission.SUPERUSER)
@config.ErrorHandle
async def card_add_group(session: CommandSession):
    lst = session.current_arg_text.split('\n')
    group = lst[0].strip()
    num = int(lst[-1])
    if num >= 65536:
        await session.send(">65536")
        return
    add_cardname(map(lambda x: x.strip(), lst[1:-1]), num=num, group=group)
    await session.send("successfully added cards")

@on_command(('card', 'check_valid'), only_to_me=False, permission=permission.SUPERUSER)
@config.ErrorHandle
async def card_valid(session: CommandSession):
    pass