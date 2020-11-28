import itertools
import math
import requests
import re
import asyncio
import functools
import datetime
import shlex
import getopt
from pebble import concurrent, ThreadPool
from concurrent.futures import TimeoutError, ThreadPoolExecutor, _base
from wand.image import Image
from wand.drawing import Drawing
from wand.color import Color
import os
import json
from matplotlib import pyplot
import numpy
from . import config
from nonebot import CommandSession, get_bot, permission
from .helper.function.function import parser, ParserError
from .inject import on_command
#pylint: disable=no-member

async def latex(s, hsh=()):
    loop = asyncio.get_event_loop()
    ipt = re.sub('&', '%26', re.sub('\+', '%2B', s))
    url = await loop.run_in_executor(None, functools.partial(requests.get,
        'https://www.zhihu.com/equation?tex=' + ipt,
        headers={'user-agent': config.user_agent}))
    name = str(hash((s,) + hsh))
    with open(config.img(name + '.svg'), 'wb') as f:
        f.write(url.content)
    with Image(filename=config.img(name + '.svg')) as image:
        with image.convert('png') as converted:
            converted.background_color = Color('white')
            converted.alpha_channel = 'remove'
            converted.save(filename=config.img(name + '.png'))
    return name + '.png'

config.CommandGroup('tools', short_des='数理小工具。')

@on_command(('tools', 'Julia'), only_to_me=False, short_des="绘制Julia集。", args=("x", "y"))
@config.ErrorHandle
async def Julia(session: CommandSession):
    """绘制以c=x+yi为参数，z→z^2+c的Julia集。
    Julia集为在复平面上，使得无限迭代z→z^2+c不发散的初值z_0的集合。
    Ref：https://en.wikipedia.org/wiki/Julia_set"""
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

@on_command(('tools', 'Mandelbrot'), only_to_me=False, short_des="绘制Mandelbrot集。", args=("x", "y"), hide=True)
@config.ErrorHandle
async def Mandelbrot(session: CommandSession):
    """绘制以z_0=x+yi为初值，z→z^2+c的Mandelbrot集。
    Mandelbrot集为在复平面上，使得无限迭代z→z^2+c不发散的参数c的集合。
    Ref：https://en.wikipedia.org/wiki/Mandelbrot_set"""
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

@on_command(('tools', 'oeis'), only_to_me=False, short_des="查询oeis（整数序列在线百科全书）。", args=("[Anumber]", "[a_1, a_2, ...]"))
@config.ErrorHandle
async def oeis(session: CommandSession):
    """查询oeis（整数序列在线百科全书）。
    参数为序列中的几项，使用逗号分隔。或为oeis编号如A036057。"""
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
    try:
        response = await asyncio.wait_for(loop.run_in_executor(None, requests.get,
            'http://oeis.org/' + s), timeout=600.0)
    except asyncio.TimeoutError:
        return "time out!"
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

@on_command(('tools', 'quiz'), only_to_me=False, shell_like=True, short_des="每月趣题。", args=("[-t YYYYMM]", "[-a]"))
@config.ErrorHandle
async def quiz(session: CommandSession):
    """每月趣题。
    可用选项：
        -t, --time 接六位月份码查看历史趣题。
        -a, --answer 查看答案。
    欢迎提交好的东方化（或其他IP化也欢迎~）的趣题至维护者邮箱shedarshian@gmail.com（难度至少让维护者能看懂解答）"""
    opts, args = getopt.gnu_getopt(session.args['argv'], 't:a', ['time=', 'answer'])
    d = datetime.date.today()
    s, ans = None, False
    for o, a in opts:
        if o in ('-t', '--time'):
            s = a
            print(a)
            if not re.match('\d{6,}', s):
                session.finish('请使用YYYYMM（四位年份加两位月份）来获取往年试题')
            if int(s[0:4]) > d.year or int(s[0:4]) == d.year and int(s[4:6]) > d.month:
                session.finish('未发现该月题目，题目自201910开始')
        elif o in ('-a', '--answer'):
            ans = True
    if s is None:
        s = f'{d.year}{d.month:02}'
    try:
        print(s)
        with open(config.rel("games\\quiz.json"), encoding='utf-8') as f:
            await session.send(json.load(f)["math"][s][int(ans)], ensure_private=ans)
    except KeyError:
        await session.send('未发现该月题目，题目自201910开始')

@on_command(('tools', 'quiz_submit'), only_to_me=False, shell_like=True, args=("content",))
@config.ErrorHandle
async def quiz_submit(session: CommandSession):
    """提交每月趣题答案。"""
    for group in config.group_id_dict['aaa']:
        await get_bot().send_group_msg(group_id=group, message=f'用户{session.ctx["user_id"]} 提交答案：\n{session.current_arg}', auto_escape=True)
    await session.send('您已成功提交答案')

@concurrent.process(timeout=30)
def calculate(s):
    parser.reset()
    parser.max_sum = 10000
    try:
        return parser.parse(s)
    except ParserError as e:
        return 'SyntaxError: ' + str(e)
    except Exception as e:
        return type(e).__name__ + ': ' + str(e)

@on_command(('tools', 'calculator'), only_to_me=False, aliases=('cal',), short_des="计算器。别名：-cal")
@config.ErrorHandle
async def calculator(session: CommandSession):
    """计算器。计算给定式子的结果。别名：-cal
    运算过程中有浮点布尔列表三种类型，计算结果必须为浮点数。
    可以使用的运算符：
        列表 {1,2,3,4}
        C++中的一元与二元运算符 + - * / ^ == != < <= > >= && || ! 下标[]
        括号 ( )
        C++中的三目运算符 ? :
        定义临时变量的运算符 := （使用例：(t:=2^3+1)*(t^2-2)
        求和 sum[变量名](下限，上限，表达式)或者sum[变量名](列表，表达式) （使用例：sum[t](1,100,sum[n](1,t,2^n/Gamma(n+1)))+sum[t](L:={2,3,5,7},t)/sum[t](L,1))
    可以使用的函数名：
        指数函数exp 自然对数ln 常用对数lg 绝对值abs 开根号sqrt 向下取整floor
        六种三角函数（sin等） 六种反三角函数（asin等） 六种双曲三角函数（sinh等） 六种反双曲三角函数（asinh等）
        误差函数erf 伽马函数Gamma 贝塔函数Beta 双伽马函数psi 不完全伽马函数Gammainc
        黎曼zeta函数或赫尔维茨zeta函数zeta（重载）
        雅克比椭圆函数ellipse_sn ellipse_cn ellipse_dn
        贝塞尔函数BesselJ BesselY BesselK BesselI
        球贝塞尔函数Besselj Bessely Besselk Besseli
        艾里函数Airy Biry
        均匀分布随机数random 高斯分布随机数gauss
    可以使用的常量：
        圆周率pi 自然对数的底e 欧拉常数gamma"""
    try:
        loop = asyncio.get_event_loop()
        future = calculate(session.current_arg_text)
        with ThreadPoolExecutor() as pool:
            result = await loop.run_in_executor(pool, future.result)
    except (TimeoutError, _base.CancelledError):
        session.finish("time out!")
    if type(result) is float:
        await session.send(str(result), auto_escape=True)
    elif type(result) is str:
        await session.send(result, auto_escape=True)
    else:
        await session.send('TypeError ' + str(result), auto_escape=True)

@on_command(('tools', 'function'), only_to_me=False, short_des="绘制函数。", args=("[-b begin=0]", "[-e end=10]", "[-s step=0.01]"))
@config.ErrorHandle
async def plot_function(session: CommandSession):
    """绘制函数。语法见-tools.calculator的帮助。
    可用选项：
        -b, --begin: 起始范围，默认为0。
        -e, --end: 结束范围，默认为10。
        -s, --step: 步长，默认为0.01。
        以上三个选项均可以输入表达式，但是在包含空格时需要用引号包裹。
    函数自变量符号为x。
    函数不可包含换行符。在函数包含空格时，请用引号包裹函数体部分。
    也可以在第一行输入选项，换行后输入函数体。"""
    opt_str, *els = session.current_arg_text.split('\n')
    print(session.current_arg_text, session.current_arg_text[0])
    if len(els) >= 2:
        await session.send('函数不可包含换行符。')
        return
    begin, end, step = 0, 10, 0.01
    opts, args = getopt.gnu_getopt(shlex.split(opt_str.strip()), 'b:e:s:', ['begin=', 'end=', 'step='])
    loop = asyncio.get_event_loop()
    try:
        with ThreadPoolExecutor() as pool:
            for o, a in opts:
                if o in ('-b', '--begin'):
                    future = calculate(a)
                    begin = await loop.run_in_executor(pool, future.result)
                    if type(begin) is str:
                        session.finish(begin, auto_escape=True)
                elif o in ('-e', '--end'):
                    future = calculate(a)
                    end = await loop.run_in_executor(pool, future.result)
                    if type(end) is str:
                        session.finish(end, auto_escape=True)
                elif o in ('-s', '--step'):
                    step = calculate(a)
                    begin = await loop.run_in_executor(pool, future.result)
                    if type(step) is str:
                        session.finish(step, auto_escape=True)
    except (TimeoutError, _base.CancelledError):
        session.finish("time out!")
    if len(els) == 1:
        func_str = els[0].strip()
    elif len(args) != 0:
        func_str = args[0].strip()
    else:
        await session.send('请输入函数。')
    num = math.ceil((end - begin) / step)
    if num > 10000:
        session.finish('点数不能大于10000。')
    parser.reset()
    parser.setstate('x')
    try:
        result = parser.parse(func_str)
        if type(result) is float:
            result2 = result
            result = lambda *args: result2
        result(begin)
        x = numpy.linspace(begin, end, num)
        loop = asyncio.get_event_loop()
        # ufunc = numpy.frompyfunc(result, 1, 1)
        # future = _f(ufunc, x)
        with ThreadPool() as pool:
            future = pool.map(result, x, timeout=30)
            y = await loop.run_in_executor(None, lambda: list(future.result()))
    except (TimeoutError, _base.CancelledError):
        session.finish("time out!")
    except IndexError:
        session.finish('请输入一元函数。')
    except ParserError as e:
        session.finish('SyntaxError: ' + str(e), auto_escape=True)
    except Exception as e:
        session.finish(type(e).__name__ + ': ' + str(e), auto_escape=True)
    pyplot.clf()
    pyplot.plot(x, y)
    name = f'func_{hash(session.current_arg_text)}.png'
    pyplot.savefig(config.img(name))
    await session.send(config.cq.img(name))
