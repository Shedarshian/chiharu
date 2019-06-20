import itertools
import math
from wand.image import Image
from wand.drawing import Drawing
from wand.color import Color
import chiharu.plugins.config as config
from nonebot import on_command, CommandSession, get_bot, permission
import os

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