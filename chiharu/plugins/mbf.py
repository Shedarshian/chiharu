# coding=utf-8
import json
import random
import asyncio
from pebble import concurrent
from concurrent.futures import TimeoutError, ThreadPoolExecutor, _base
import getopt
from nonebot import CommandSession, permission
from nonebot.message import escape
from . import config
from .inject import on_command

with open(config.rel("mbfSub.json"), encoding='utf-8') as mbffile:
    mbfSub = json.load(mbffile)

config.CommandGroup('mbf', des="脚本语言modified brainf**k：\n有一个由整数组成的堆栈。从左到右依次读取instruction。堆栈为空时欲取出任何数均为0。\n.\t向堆栈中塞入一个0\n0-9\t堆栈顶数乘以10加输入数。即比如输入一个十进制数135可以使用.135\n+-*/%\t弹出堆栈顶两个数并塞入计算后的数。除法取整数除\n&|^\t按位运算\n><=\t比较栈顶两个数，true视为1，false视为0\n_\t栈顶数取负，即比如输入一个数-120可以使用.120_\n!\t0变为1，非0变为0\n(\t栈顶数+1\n)\t栈顶数-1\n:\t输入stdin的char至栈顶\n;\t输出栈顶的char至stdout，并消耗，超出范围则弹出后不做任何事\n[\t如果堆栈顶数为0则跳转至配对的]，并消耗掉栈顶数\n{\t与[相反，堆栈顶数非0则跳转至配对的}，并消耗掉栈顶数\n]\t如果堆栈顶数非0则跳转回匹配的[，并消耗掉栈顶数\n}\t与]相反，堆栈顶数为0则跳转回配对的{，并消耗掉栈顶数\n\\\t交换栈顶两数\n,\t弹出栈顶数n，并复制栈顶下数第n个数塞回栈顶，n超出范围则弹出n后不做任何事\n$\t塞入当前栈包含的整数总数\n~\tpop掉栈顶数\n\"\t弹出栈顶数n，删除栈顶下数第n个数，n超出范围则弹出n后不做任何事\n@\t弹出栈顶数n1之后n2，将输入序列的第n1个字符修改成n2对应的char，n1或n2超出范围则弹出两数后不做任何事\n?\t弹出栈顶数n，生成一个0至n-1的随机整数塞回堆栈，n非正则弹出n后不做任何事\n#\t复制栈顶数\n`\t弹出栈顶数，执行栈顶数对应的char对应的指令。超出范围则弹出后不做任何事\n'\t弹出栈顶数n，将输入序列第n个字符对应的ascii塞入堆栈\n字母为子程序，子程序与主程序共用堆栈。", short_des='modified brainf**k', hide_in_parent=True, display_parents='code')
config.CommandGroup('code', des='脚本语言解释器。\n使用如-mbf.run 指令运行脚本。', short_des='脚本语言解释器。')

@on_command(('mbf', 'sub'), only_to_me=False, shell_like=True, short_des="存入mbf子程序。", args=("subname", "[str]", "[-d des]"))
@config.ErrorHandle
async def SaveSub(session: CommandSession):
    """存入mbf子程序。
    可用选项：
        -d, --description：存入描述字符串。"""
    opts, args = getopt.gnu_getopt(session.args['argv'], 'd:', ['description='])
    des = None
    for o, a in opts:
        if o in ('-d', '--description'):
            des = a
    token, *els = args
    if not token.islower() and not await permission.check_permission(session.bot, session.ctx, permission.SUPERUSER):
        await session.send('小写字母子程序可随意使用，欲存入非小写字母子程序请联系维护者shedarshian@gmail.com~')
        return
    if len(els) != 0:
        _SaveSub(token, els[0])
    if des is not None:
        _SetSubStr(token, des)
    await session.send(escape("Successfully Saved sub %s !" % token))

@on_command(('mbf', 'check'), only_to_me=False, args=("subname",))
@config.ErrorHandle
async def Check(session: CommandSession):
    """查看mbf子程序内容。"""
    try:
        await session.send(escape("Sub content is:\n%s\nDescription:\n%s" % tuple(_GetSub(session.current_arg_text))))
    except KeyError:
        await session.send('未找到子程序。')

@on_command(('mbf', 'ls'), only_to_me=False)
async def List(session: CommandSession):
    """列出所有mbf子程序。"""
    await session.send(escape("\n".join(_ListSub())))

@on_command(('mbf', 'time'), only_to_me=False, args=("code [\\n stdin]"))
@config.ErrorHandle
async def Time(session: CommandSession):
    """返回mbf程序的运行时间。输入第二行内容作为standard input。"""
    try:
        loop = asyncio.get_event_loop()
        future = _Run(session.get('strins'), session.get('strin'))
        with ThreadPoolExecutor() as pool:
            strout, _break, runtime = await loop.run_in_executor(pool, future.result)
    except (TimeoutError, _base.CancelledError):
        session.finish("time out!")
    except ZeroDivisionError:
        await session.send("ZeroDivisionError: integer division or modulo by zero")
        return
    if runtime >= 10000000:
        await session.send("time out!")
    if _break:
        await session.send("stdin used out!")
    await session.send(str(runtime))

@on_command(('mbf', 'run'), only_to_me=False, short_des="运行mbf程序。输入第二行内容作为standard input。", args=("code [\\n stdin]"))
@config.ErrorHandle
async def Run(session: CommandSession):
    "运行mbf程序。输入第二行内容作为standard input。\n\n脚本语言modified brainf**k帮助：\n有一个由整数组成的堆栈。从左到右依次读取instruction。堆栈为空时欲取出任何数均为0。\n.\t向堆栈中塞入一个0\n0-9\t堆栈顶数乘以10加输入数。即比如输入一个十进制数135可以使用.135\n+-*/%\t弹出堆栈顶两个数并塞入计算后的数。除法取整数除\n&|^\t按位运算\n><=\t比较栈顶两个数，true视为1，false视为0\n_\t栈顶数取负，即比如输入一个数-120可以使用.120_\n!\t0变为1，非0变为0\n(\t栈顶数+1\n)\t栈顶数-1\n:\t输入stdin的char至栈顶\n;\t输出栈顶的char至stdout，并消耗，超出范围则弹出后不做任何事\n[\t如果堆栈顶数为0则跳转至配对的]，并消耗掉栈顶数\n{\t与[相反，堆栈顶数非0则跳转至配对的}，并消耗掉栈顶数\n]\t如果堆栈顶数非0则跳转回匹配的[，并消耗掉栈顶数\n}\t与]相反，堆栈顶数为0则跳转回配对的{，并消耗掉栈顶数\n\\\t交换栈顶两数\n,\t弹出栈顶数n，并复制栈顶下数第n个数塞回栈顶，n超出范围则弹出n后不做任何事\n$\t塞入当前栈包含的整数总数\n~\tpop掉栈顶数\n\"\t弹出栈顶数n，删除栈顶下数第n个数，n超出范围则弹出n后不做任何事\n@\t弹出栈顶数n1之后n2，将输入序列的第n1个字符修改成n2对应的char，n1或n2超出范围则弹出两数后不做任何事\n?\t弹出栈顶数n，生成一个0至n-1的随机整数塞回堆栈，n非正则弹出n后不做任何事\n#\t复制栈顶数\n`\t弹出栈顶数，执行栈顶数对应的char对应的指令。超出范围则弹出后不做任何事\n'\t弹出栈顶数n，将输入序列第n个字符对应的ascii塞入堆栈\n字母为子程序，子程序与主程序共用堆栈。"
    try:
        loop = asyncio.get_event_loop()
        future = _Run(session.get('strins'), session.get('strin'))
        with ThreadPoolExecutor() as pool:
            strout, _break, runtime = await loop.run_in_executor(pool, future.result)
    except (TimeoutError, _base.CancelledError):
        session.finish("time out!")
    except ZeroDivisionError:
        session.finish("ZeroDivisionError: integer division or modulo by zero")
    if runtime >= 10000000:
        await session.send("time out!")
    if _break:
        await session.send("stdin used out!")
    if len(strout) >= 1000:
        await session.send("stdout too long!")
        await session.send(escape('程序输出结果：\n' + strout[0:1000]))
    elif strout == "":
        await session.send("No Output!")
    else:
        await session.send(escape('程序输出结果：\n' + strout))

@Time.args_parser
@Run.args_parser
async def _(session: CommandSession):
    content = session.current_arg_text
    if content.find('\n') == -1:
        session.args['strins'] = content
        session.args['strin'] = ""
    else:
        session.args['strins'] = content[:content.find('\n') + 1]
        session.args['strin'] = content[content.find('\n') + 1:]

def save():
    global mbfSub
    with open(config.rel("mbfSub.json"), "w", encoding='utf-8') as mbffile:
        mbffile.write(json.dumps(mbfSub, ensure_ascii=False, indent=4, separators=(',', ': ')))

def pop(stack):
    if len(stack) == 0:
        return 0
    return stack.pop()

def push(stack, i):
    stack.append(i)

def parse(liststring):
    stack_mid = []
    stack_big = []
    map_mid_lr = {}
    map_mid_rl = {}
    map_big_lr = {}
    map_big_rl = {}
    pos = 0
    for char in liststring:
        if char == '[':
            push(stack_mid, pos)
        elif char == '{':
            push(stack_big, pos)
        elif char == ']':
            if(len(stack_mid) == 0):
                map_mid_rl[pos] = -1
            i = pop(stack_mid)
            map_mid_lr[i] = pos
            map_mid_rl[pos] = i
        elif char == '}':
            if(len(stack_big) == 0):
                map_big_rl[pos] = -1
            i = pop(stack_big)
            map_big_lr[i] = pos
            map_big_rl[pos] = i
        pos += 1
    if len(stack_mid) != 0:
        for mid in stack_mid:
            map_mid_lr[mid] = len(liststring) - 1
        for big in stack_big:
            map_big_lr[big] = len(liststring) - 1
    return map_mid_lr, map_mid_rl, map_big_lr, map_big_rl

#return newpos, strout, break, runtime
def mbfChg(pos, listins, listin, char, stack, maps):
    strout = ""
    _break = False
    runtime = 0
    if char == ".":
        push(stack, 0)
    elif char in "0123456789":
        i = pop(stack)
        push(stack, 10 * i + int(char))
    elif char == "+":
        i = pop(stack)
        j = pop(stack)
        push(stack, i + j)
    elif char == "-":
        i = pop(stack)
        j = pop(stack)
        push(stack, i - j)
    elif char == "*":
        i = pop(stack)
        j = pop(stack)
        push(stack, i * j)
    elif char == "/":
        i = pop(stack)
        j = pop(stack)
        push(stack, i // j)
    elif char == "%":
        i = pop(stack)
        j = pop(stack)
        push(stack, i % j)
    elif char == "&":
        i = pop(stack)
        j = pop(stack)
        push(stack, i & j)
    elif char == "|":
        i = pop(stack)
        j = pop(stack)
        push(stack, i | j)
    elif char == "^":
        i = pop(stack)
        j = pop(stack)
        push(stack, i ^ j)
    elif char == ">":
        i = pop(stack)
        j = pop(stack)
        push(stack, int(i > j))
    elif char == "<":
        i = pop(stack)
        j = pop(stack)
        push(stack, int(i < j))
    elif char == "=":
        i = pop(stack)
        j = pop(stack)
        push(stack, int(i == j))
    elif char == "_":
        i = pop(stack)
        push(stack, -i)
    elif char == "!":
        i = pop(stack)
        push(stack, int(i == 0))
    elif char == "(":
        i = pop(stack)
        push(stack, i + 1)
    elif char == ")":
        i = pop(stack)
        push(stack, i - 1)
    elif char == ":":
        if(len(listin) == 0):
            _break = True
        else:
            push(stack, ord(listin[0]))
            listin.pop(0)
    elif char == ";":
        i = pop(stack)
        strout = chr(i)
    elif char == "[":
        if pop(stack) == 0:
            pos = maps[0][pos]
    elif char == "]":
        if pop(stack) != 0:
            pos = maps[1][pos]
    elif char == "{":
        if pop(stack) != 0:
            pos= maps[2][pos]
    elif char == "}":
        if pop(stack) == 0:
            pos = maps[3][pos]
    elif char == "\\":
        i = pop(stack)
        j = pop(stack)
        push(stack, i)
        push(stack, j)
    elif char == ",":
        i = pop(stack)
        if i >= 1 and i <= len(stack):
            push(stack, stack[len(stack) - i])
    elif char == "$":
        push(stack, len(stack))
    elif char == "~":
        pop(stack)
    elif char == "\"":
        i = pop(stack)
        if i >= 1 and i <= len(stack):
            del stack[len(stack) - i]
    elif char == "@":
        i = pop(stack)
        j = pop(stack)
        if i >= 0 and i < len(listins[0]):
            listins[i] = chr(j)
        maps = parse(listins)
    elif char == "?":
        i = pop(stack)
        if i > 0:
            push(stack, random.randint(0, i - 1))
    elif char == "#":
        i = pop(stack)
        push(stack, i)
        push(stack, i)
    elif char == "`":
        i = pop(stack)
        char_temp = chr(i)
        pos2, strout, _break, runtime = mbfChg(pos, listins, listin, char_temp, stack, maps)
    elif char == "'":
        i = pop(stack)
        if i >= 0 and i < len(listins):
            push(stack, ord(listins[i]))
    elif mbfSub.get(char, ["", ""]) != ["", ""]:
        strout, _break, runtime = mbfInterpret(list(mbfSub[char][0]), listin, stack)
    return pos, strout, _break, runtime

#return strout, break, runtime
def mbfInterpret(listins, listin, stack):
    maps = parse(listins)
    runtime = 0
    _break = False
    pos = 0
    strout = ""
    while pos < len(listins) and runtime < 10000000 and not _break:
        pos, strout_add, _break, runtime_add = mbfChg(pos, listins, listin, listins[pos], stack, maps)
        strout += strout_add
        runtime += runtime_add + 1
        pos += 1
    return strout, _break, runtime

def _SaveSub(name, content):
    global mbfSub
    if name not in mbfSub:
        mbfSub[name] = [content, ""]
    else:
        mbfSub[name][0] = content
    save()
    return True

def _SetSubStr(name, string):
    global mbfSub
    if name in mbfSub:
        mbfSub[name][1] = string
        save()
        return True
    else:
        return False

def _GetSub(name):
    global mbfSub
    return mbfSub[name]

def _ListSub():
    global mbfSub
    def _g():
        for key, val in mbfSub.items():
            if not key.islower():
                yield key + "  " + (val[1] if val[1] != "" else "无描述")
            elif key.islower() and val[1] != "":
                yield key + "  " + val[1]
    l = list(_g())
    l.sort()
    return l

@concurrent.process(timeout=15)
def _Run(strins, strin):
    return mbfInterpret(list(strins), list(strin), [])

# vim:fdm=marker:fdc=3