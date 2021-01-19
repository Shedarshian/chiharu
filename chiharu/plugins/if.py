import json, random, itertools
from PIL import Image
from nonebot import CommandSession, permission, get_bot
from . import config
from .inject import on_command

config.CommandGroup('if', short_des='魔法禁书目录 幻想收束相关指令。')

with open(config.rel('if\\card.json'), encoding='utf-8') as f:
    metainfo, *premium_card = json.load(f)

@on_command(('if', 'gacha'), only_to_me=False, args=('[pool=0]'))
@config.ErrorHandle
async def if_gacha(session: CommandSession):
    '''幻想收束模拟抽卡。
    使用'-if.gacha 卡池id'抽卡。
    卡池信息请使用'-if.gacha 卡池'或'-if.gacha pool'查询。'''
    # 对于card.json的[0]，是一个dict，key代表卡池代号，val[0]代表卡池名，val[1]代表保底机制，
    # "2"表示premium的1星升级为2星，"ex???"代表第10张导向名为"ex???"的卡池文件，
    # val[2]若为str，则为前9个指向的卡池文件，若为list，则举例为[["1", 5], ["fes58", 4], ["fes9", 1]]，
    # 代表哪n张卡导向名为什么的文件。
    # 对于卡池文件，type有三种：premium, up, mixed。premium表示普池卡，
    # up表示等概率分布的特定卡，mixed格式举例为[[0, 2], [1, 2], ["abc", "def"]]，
    # 表示普池的[0, 2]与[1, 2]以及两张特定卡所有这些卡等概率。
    if session.current_arg_text in ('卡池', 'pool'):
        await session.send('\n'.join(f'{i}: {l[0]}' for i, l in metainfo.items()))
    else:
        pool_id = '0' if session.current_arg_text == '' else session.current_arg_text.strip()
        if pool_id not in metainfo:
            session.finish('请输入正确的卡池id。')
        pool_metainfo = metainfo[pool_id]
        if pool_metainfo[2] is not None:
            pool_id_changed = pool_metainfo[2]
        else:
            pool_id_changed = pool_id
        if isinstance(pool_id_changed, list):
            def _(name):
                with open(config.rel(f'if\\pools\\{name}.json'), encoding='utf-8') as f:
                    j = json.load(f)
                    return j, [d['weight'] for d in j]
            l = list(itertools.chain(*[random.choices(*_(name), k=n) for name, n in pool_id_changed]))
        else:
            with open(config.rel(f'if\\pools\\{pool_id_changed}.json'), encoding='utf-8') as f:
                pool = json.load(f)
            l = random.choices(pool, [d['weight'] for d in pool], k=10)
        if pool_metainfo[1].startswith('ex'):
            with open(config.rel(f'if\\pools\\{pool_metainfo[1]}.json'), encoding='utf-8') as f:
                pool1 = json.load(f)
            l[-1] = random.choices(pool1, [d['weight'] for d in pool1], k=1)[0]
        r = []
        for i, d in enumerate(l):
            if d['type'] == 'premium':
                a, b = d['card']
                if pool_metainfo[1] == '2':
                    if i == 9 and b == 0:
                        b = 1
                r.append(random.choice(premium_card[a][b]))
            elif d['type'] == 'up':
                r.append(random.choice(d['card']))
            elif d['type'] == 'mixed':
                r.append(random.choice(list(itertools.chain(*[premium_card[a][b] for a, b in d['card'][:-1]], d['card'][-1]))))
        distance = 16
        img = Image.new("RGB", (640 + distance * 6, 256 + distance * 3), "#c3e5ff")
        for i, d in enumerate(r):
            row, column = i // 5, i % 5
            c = Image.open(config.rel(f"if\\img\\{d}卡牌头像.jpg"))
            img.paste(c, (column * (128 + distance) + distance, row * (128 + distance) + distance))
        h = hash(tuple(r))
        img.save(config.img(f'if{h}.png'))
        await session.send([config.cq.at(session.ctx['user_id']), config.cq.img(f'if{h}.png')])

@on_command(('if', 'oshirase'), only_to_me=False, hide=True, permission=permission.SUPERUSER)
@config.ErrorHandle
async def if_oshirase(session: CommandSession):
    for group in config.group_id_dict['if_pool_update']:
        await get_bot().send_group_msg(group_id=group, message=session.current_arg)
    await session.send('已发送')