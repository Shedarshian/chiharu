import itertools
import math
import requests
import re
import asyncio
from wand.image import Image
from wand.drawing import Drawing
from wand.color import Color
import chiharu.plugins.config as config
from nonebot import on_command, CommandSession, get_bot, permission
import os

async def latex(s, hsh=()):
    loop = asyncio.get_event_loop()
    ipt = re.sub('\+', '%2B', s)
    url = await loop.run_in_executor(None, functools.partial(requests.get,
        'https://www.zhihu.com/equation?tex=' + ipt,
        headers={'user-agent': config.user_agent}))
    name = str(hash((s,) + hsh))
    with open(config.img(name + '.svg'), 'wb') as f:
        f.write(url.content)
    with wand.image.Image(filename=config.img(name + '.svg')) as image:
        with image.convert('png') as converted:
            converted.background_color = wand.color.Color('white')
            converted.alpha_channel = 'remove'
            converted.save(filename=config.img(name + '.png'))
    return name + '.png'

@on_command(('tools', 'Julia'), only_to_me=False)
@config.ErrorHandle
async def Julia(session: CommandSession):
    c = session.current_arg_text.split(' ')
    if len(c) != 2:
        await session.send("使用格式：-tools.Julia x y\n绘制Julia set，使得c=x+yi")
        return
    x = float(c[0])
    y = float(c[1])
    height = 600
    dx = 0.005
    MAX = 80
    color_in = (128, 48, 10)
    name = 'Julia_%f_%f.png' % (x, y)
    if not os.path.exists(config.img(name)):
        f = lambda i, x: math.log(i + math.log(abs(x) + 3) + 2)
        await session.send("少女计算中...请耐心等待...")
        with Drawing() as draw:
            for x1, y1 in itertools.product(range(height), range(height)):
                x2, y2 = (x1 - height / 2) * dx, (y1 - height / 2) * dx
                for i in range(MAX):
                    x3, y3 = (x2 ** 2 - y2 ** 2 + x, 2 * x2 * y2 + y)
                    if (x2 - x3) ** 2 + (y2 - y3) ** 2 >= 100:
                        break
                    x2, y2 = x3, y3
                else:
                    i += 1
                r2 = math.sqrt(x2 ** 2 + y2 ** 2)
                color = tuple(map(lambda c: c[0] * c[1], zip(color_in, (f(i, x2), f(i, y2), f(i, r2)))))
                draw.fill_color = Color('rgb(%i, %i, %i)' % color)
                draw.point(x1, y1)
            with Image(width=height, height=height) as image:
                draw(image)
                image.save(filename=config.img(name))
    await session.send(config.cq.img(name))

@on_command(('tools', 'Mandelbrot'), only_to_me=False)
@config.ErrorHandle
async def Mandelbrot(session: CommandSession):
    c = session.current_arg_text.split(' ')
    if len(c) != 2:
        await session.send("使用格式：-tools.Mandelbrot x y\n绘制Mandelbrot set，使得z0=x+yi")
        return
    x = float(c[0])
    y = float(c[1])
    height = 600
    dx = 0.005
    MAX = 80
    color_in = (128, 48, 10)
    name = 'Mandelbrot_%f_%f.png' % (x, y)
    if not os.path.exists(config.img(name)):
        f = lambda i, x: math.log(i + math.log(abs(x) + 3) + 2)
        await session.send("少女计算中...请耐心等待...")
        with Drawing() as draw:
            for x1, y1 in itertools.product(range(height), range(height)):
                x2, y2 = (x1 - height / 2) * dx, (y1 - height / 2) * dx
                x4, y4 = x, y
                for i in range(MAX):
                    x3, y3 = (x4 ** 2 - y4 ** 2 + x2, 2 * x4 * y4 + y2)
                    if (x4 - x3) ** 2 + (y4 - y3) ** 2 >= 100:
                        break
                    x4, y4 = x3, y3
                else:
                    i += 1
                r4 = math.sqrt(x4 ** 2 + y4 ** 2)
                color = tuple(map(lambda c: c[0] * c[1], zip(color_in, (f(i, x4), f(i, y4), f(i, r4)))))
                draw.fill_color = Color('rgb(%i, %i, %i)' % color)
                draw.point(x1, y1)
            with Image(width=height, height=height) as image:
                draw(image)
                image.save(filename=config.img(name))
    await session.send(config.cq.img(name))

@on_command(('tools', 'oeis'), only_to_me=False)
@config.ErrorHandle
async def oeis(session: CommandSession):
    if re.match('A\d+', session.current_arg_text):
        result = await oeis_id(session.current_arg_text)
        if type(result) == str:
            await session.send(result)
        else:
            await session.send('%s\nDESCRIPTION: %s\n%s\nEXAMPLE: %s' % \
                    (result['Id'], result['description'], result['numbers'], result['example']))
    elif re.fullmatch('(-?\d+, ?)*-?\d+', session.current_arg_text):
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, requests.get,
                'http://oeis.org/search?q=' + session.current_arg_text + '&sort=&language=&go=Search')
        if response.status_code != 200:
            await session.send('sequence not found!')
            return
        match = re.search('A\d+', response.text)
        if not match:
            await session.send('sequence not found!')
            return
        s = match.group()
        result = await oeis_id(s)
        if type(result) == str:
            await session.send(result)
        else:
            await session.send('%s\nDESCRIPTION: %s\n%s\nEXAMPLE: %s' % \
                    (result['Id'], result['description'], result['numbers'], result['example']))
    else:
        await session.send("I don't know what you mean.")

async def oeis_id(s):
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, requests.get,
            'http://oeis.org/' + s)
    if response.status_code != 200:
        return 'Name not found!'
    text = response.text
    begin_pos = 0
    match = re.search('<title>(A\d+)', text[begin_pos:])
    if not match:
        return 'Title not found!'
    begin_pos += match.span()[1]
    Id = match.group(1)
    match = re.search('<td valign=top align=left>\n(.*)\n', text[begin_pos:])
    if not match:
        return 'Description not found!'
    begin_pos += match.span()[1]
    description = match.group(1).strip()
    match = re.search('<td width="710">', text[begin_pos:])
    if not match:
        return 'Numbers not found!'
    begin_pos += match.span()[1]
    match = re.search('<tt>(.*?)</tt>', text[begin_pos:])
    if not match:
        return 'Numbers not found!'
    numbers = match.group(1)
    match = re.search('EXAMPLE', text[begin_pos:])
    if not match:
        example = None
    else:
        example_pos = begin_pos + match.span()[1]
        match2 = re.search('<font size=', text[example_pos:])
        match3 = re.search('</table>', text[example_pos:])
        if not match2:
            match2 = match3
        if not match3:
            example = None
        else:
            example_end = example_pos + match2.span()[1]
            example_list = []
            while 1:
                match2 = re.search('<tt>(.*)</tt>', text[example_pos:example_end])
                if not match2:
                    break
                example_pos += match2.span()[1]
                example_list.append(re.sub('&nbsp;', '\t', re.sub('<.*?>', '', match2.group(1))).strip())
            example = '\n'.join(example_list)
    result = {'Id': Id, 'description': description, 'numbers': numbers, 'example': example}
    return result

@on_command(('tools', 'quiz'), only_to_me=False)
@config.ErrorHandle
async def quiz(session: CommandSession):
    if session.current_arg_text == 'math':
        await session.send("""今日趣题：A、B两人在主持人C的带领下玩一个游戏。C向两人宣布游戏规则：“一会儿我会随机产生两个不同的形如n–1/2^k–1/2^(k+r)的数，其中n、k是正整数，r是非负整数。然后，我会把这两个数分别交给你们。你们每个人都只知道自己手中的数是多少，但不知道对方手中的数是多少。你们需要猜测，谁手中的数更大一些。”这里，我们假设所有人的逻辑推理能力都是无限强的，并且这一点本身也成为了共识。C按照规则随机产生了两个数，把它们交给了A和B，然后问他们是否知道谁手中的数更大。于是有了这样的一段对话。

A：我不知道。
B：我也不知道。
A：我还是不知道。
B：我也还是不知道。
C：这样下去是没有用的！可以告诉你们，不管你们像这样来来回回说多少轮，你们仍然都没法知道，谁手中的数更大一些。
A：哇，这个信息量好像有点儿大！不过，即使知道了这一点，我还是不知道谁手中的数更大。
B：我也还是不知道。
A：我继续不知道。
B：我也继续不知道。
C：还是套用刚才的话，不管你们像这样继续说多少轮，你们仍然没法知道谁手中的数更大。
A：哦……不过，我还是不知道谁手中的数更大。
B：而且我也还是不知道。我们究竟什么时候才能知道呢？
C：事实上啊，如果我们三个就像这样继续重复刚才的一切——你们俩互相说一堆不知道，我告诉你们这样永远没用，然后你们继续互说不知道，我继续说这不管用——那么不管这一切重复多少次，你们仍然不知道谁手中的数更大！
A：哇，这次的信息量就真的大了。只可惜，我还是不知道谁的数更大一些。
B：我也还是不知道。
A：是吗？好，那我现在终于知道谁的数更大了。
B：这样的话，那我也知道了。而且，我还知道我们俩手中的数具体是多少了。
A：那我也知道了。

那么，C究竟把哪两个数给了A和B？""")