import json, random
from PIL import Image
from nonebot import CommandSession, permission
from . import config
from .inject import on_command

config.CommandGroup('if', short_des='魔法禁书目录 幻想收束相关指令。', hide=True)

with open(config.rel('if\\card.json'), encoding='utf-8') as f:
    premium_card = json.load(f)

@on_command(('if', 'draw'), only_to_me=False, hide=True) # , args=('[pool=0]')
@config.ErrorHandle
async def if_draw(session: CommandSession):
    '''幻想收束模拟抽卡。'''
    # 卡池信息请使用'-if.draw 卡池'或'-if.draw pool'查询
    if session.current_arg_text in ('卡池', 'pool'):
        # with open(config.rel('if\\pool.json')) as f:
        #     pass
        pass
    else:
        pool_id = '0' if session.current_arg_text == '' else session.current_arg_text
        with open(config.rel('if\\pool.json'), encoding='utf-8') as f:
            pool = json.load(f)
        l = random.choices(pool[pool_id], [d['weight'] for d in pool[pool_id]], k=10)
        r = []
        for i, d in enumerate(l):
            if d['type'] == 'premium':
                a, b = d['card']
                if i == 9 and b == 0:
                    b = 1
                r.append(random.choice(premium_card[a][b]))
            # else:
        distance = 16
        img = Image.new("RGB", (640 + distance * 6, 256 + distance * 3), "#c3e5ff")
        for i, d in enumerate(r):
            row, column = i // 5, i % 5
            c = Image.open(config.rel(f"if\\img\\{d}卡牌头像.jpg"))
            img.paste(c, (column * (128 + distance) + distance, row * (128 + distance) + distance))
        h = hash(tuple(r))
        img.save(config.img(f'if{h}.png'))
        await session.send([config.cq.img(f'if{h}.png')])
