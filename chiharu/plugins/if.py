import json, random, itertools
from PIL import Image
from nonebot import CommandSession, permission
from . import config
from .inject import on_command

config.CommandGroup('if', short_des='魔法禁书目录 幻想收束相关指令。', hide=True)

with open(config.rel('if\\card.json'), encoding='utf-8') as f:
    premium_card = json.load(f)

@on_command(('if', 'gacha'), only_to_me=False, hide=True, args=('[pool=0]'))
@config.ErrorHandle
async def if_gacha(session: CommandSession):
    '''幻想收束模拟抽卡。
    使用'-if.gacha 卡池id'抽卡。
    卡池信息请使用'-if.gacha 卡池'或'-if.gacha pool'查询。'''
    if session.current_arg_text in ('卡池', 'pool'):
        with open(config.rel('if\\pool.json'), encoding='utf-8') as f:
            pool = json.load(f)
        await session.send('\n'.join(f'{i}: {l[0]}' for i, l in pool['metainfo']))
    else:
        pool_id = '0' if session.current_arg_text == '' else session.current_arg_text.strip()
        with open(config.rel('if\\pool.json'), encoding='utf-8') as f:
            pool = json.load(f)
        if pool_id not in pool['metainfo']:
            session.finish('请输入正确的卡池id。')
        metainfo = pool['metainfo'][pool_id]
        if metainfo[2] is not None: 
            pool_id_changed = metainfo[2]
        else:
            pool_id_changed = pool_id
        l = random.choices(pool[pool_id_changed], [d['weight'] for d in pool[pool_id_changed]], k=10)
        if metainfo[1].startswith('ex'):
            l[-1] = random.choices(pool[metainfo[1]], [d['weight'] for d in pool[metainfo[1]]], k=1)
        r = []
        for i, d in enumerate(l):
            if d['type'] == 'premium':
                a, b = d['card']
                if metainfo[1] == '2':
                    if i == 9 and b == 0:
                        b = 1
                r.append(random.choice(premium_card[a][b]))
            elif d['type'] == 'up':
                r.append(random.choice(d['card']))
            elif d['type'] == 'mixed':
                r.append(random.choice(itertools.chain(*[premium_card[a][b] for a, b in d['card'][:-1]], d['card'][-1])))
        distance = 16
        img = Image.new("RGB", (640 + distance * 6, 256 + distance * 3), "#c3e5ff")
        for i, d in enumerate(r):
            row, column = i // 5, i % 5
            c = Image.open(config.rel(f"if\\img\\{d}卡牌头像.jpg"))
            img.paste(c, (column * (128 + distance) + distance, row * (128 + distance) + distance))
        h = hash(tuple(r))
        img.save(config.img(f'if{h}.png'))
        await session.send([config.cq.img(f'if{h}.png')])
