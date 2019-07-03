import random
import json
import itertools
import chiharu.plugins.config as config
from nonebot import on_command, CommandSession, get_bot, permission

def to_byte(num):
    return bytes([num // 256, num % 256])

with open(config.rel(r"games\card\pool"), 'rb') as f:
    pool = list(itertools.starmap(lambda x, y: int(x) * 256 + int(y), config.group(2, f.read())))
with open(config.rel(r"games\card\card_info.json"), encoding='utf-8') as f:
    card_info = json.load(f)
def save_card_info():
    global card_info
    with open(config.rel(r"games\card\card_info.json"), 'w') as f:
        f.write(json.dumps(card_info, ensure_ascii=False, indent=4, separators=(',', ': ')), encoding='utf-8')
#with open(config.rel("games\\card\\daily_pool.json")) as f:
#    pass




def center_card(*args):
    return ""

def add_cardname(name, **kwargs):
    global card_info
    card_info.append(dict(name=name, **kwargs))
    with open(config.rel(r"games\card\pool"), 'ab') as f:
        f.write(to_byte(0)) # 每个卡最多65535张

def add_card(id, num):
    global pool
    with open(config.rel(r"games\card\pool"), 'rb+') as f:
        f.seek(2 * id)
        num_new = pool[id] + num
        f.write(to_byte(num_new))

@on_command(('card', 'draw'), only_to_me=False)
@config.ErrorHandle
async def card_draw(session: CommandSession):
    if session.current_arg_text == "":
        # 卡池介绍
        pass
    pass

@on_command(('card', 'add'), only_to_me=False)
@config.ErrorHandle
async def card_add(session: CommandSession):
    pass

@on_command(('card', 'add_group'), only_to_me=False, permission=permission.SUPERUSER)
@config.ErrorHandle
async def card_add_group(session: CommandSession):
    lst = session.current_arg_text.split('\n')
    group = lst[0].strip()
    for line in lst[1:]:
        add_cardname(line.strip(), group=group)