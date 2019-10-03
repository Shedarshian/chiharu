# coding=utf-8
import json
import random
import asyncio
from nonebot import on_command, CommandSession, permission
import chiharu.plugins.config as config

with open(config.rel("mbfSub.json"), encoding='utf-8') as mbffile:
    mbfSub = json.load(mbffile)

@on_command(('mbf', 'sub'), only_to_me=False)
@config.ErrorHandle
async def SaveSub(session: CommandSession):
    token = session.get('token')
    if not token.islower() and not await permission.check_permission(session.bot, session.ctx, permission.SUPERUSER):
        await session.send('小写字母子程序可随意使用，欲存入非小写字母子程序请联系维护者~')
        return
    await _SaveSub(token, session.get('content'))
    await session.send("Successfully create sub %s !" % token, auto_escape=True)

@on_command(('mbf', 'str'), only_to_me=False)
@config.ErrorHandle
async def SetSubStr(session: CommandSession):
    token = session.get('token')
    if not token.islower() and not await permission.check_permission(session.bot, session.ctx, permission.SUPERUSER):
        await session.send('小写字母子程序可随意使用，欲存入非小写字母子程序请联系维护者~')
        return
    await _SetSubStr(token, session.get('content'))
    await session.send("Successfully Saved!")

@SaveSub.args_parser
@SetSubStr.args_parser
async def _(session: CommandSession):
    session.args['token'] = session.current_arg_text[0]
    session.args['content'] = session.current_arg_text[2:]

@on_command(('mbf', 'check'), only_to_me=False)
@config.ErrorHandle
async def Check(session: CommandSession):
    await session.send("Sub content is:\n%s\nDescription:\n%s" % tuple(_GetSub(session.current_arg_text)), auto_escape=True)

@Check.args_parser
async def _(session: CommandSession):
    session.args['token'] = session.current_arg_text[0]

@on_command(('mbf', 'ls'), only_to_me=False)
async def List(session: CommandSession):
    await session.send("\n".join(_ListSub()), auto_escape=True)

@on_command(('mbf', 'time'), only_to_me=False)
@config.ErrorHandle
async def Time(session: CommandSession):
    try:
        strout, _break, runtime = await asyncio.wait_for(_Run(session.get('strins'), session.get('strin')), timeout=1)
    except asyncio.TimeoutError:
        await session.send("time out!")
        return
    if runtime >= 10000000:
        await session.send("time out!")
    if _break:
        await session.send("stdin used out!")
    await session.send(str(runtime), auto_escape=True)

@on_command(('mbf', 'run'), only_to_me=False)
@config.ErrorHandle
async def Run(session: CommandSession):
    try:
        strout, _break, runtime = await asyncio.wait_for(_Run(session.get('strins'), session.get('strin')), timeout=600)
    except asyncio.TimeoutError:
        await session.send("time out!")
        return
    if runtime >= 10000000:
        await session.send("time out!")
    if _break:
        await session.send("stdin used out!")
    if len(strout) >= 1000:
        await session.send("stdout too long!")
        await session.send('程序输出结果：\n' + strout[0:1000], auto_escape=True)
    elif strout == "":
        await session.send("No Output!")
    else:
        await session.send('程序输出结果：\n' + strout, auto_escape=True)

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

async def save():
    global mbfSub
    with open(config.rel("mbfSub.json"), "w", encoding='utf-8') as mbffile:
        mbffile.write(json.dumps(mbfSub, ensure_ascii=False, indent=4, separators=(',', ': ')))

def pop(stack):
    if len(stack) == 0:
        return 0
    return stack.pop()

def push(stack, i):
    stack.append(i)

async def parse(liststring):
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
async def mbfChg(pos, listins, listin, char, stack, maps):
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
        maps = await parse(listins)
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
        await mbfChg(pos, listins, listin, char_temp, stack, maps)
    elif char == "'":
        i = pop(stack)
        if i >= 0 and i < len(listins):
            push(stack, ord(listins[i]))
    elif mbfSub.get(char, ["", ""]) != ["", ""]:
        strout, _break, runtime = await mbfInterpret(list(mbfSub[char][0]), listin, stack)
    return pos, strout, _break, runtime

#return strout, break, runtime
async def mbfInterpret(listins, listin, stack):
    maps = await parse(listins)
    runtime = 0
    _break = False
    pos = 0
    strout = ""
    while pos < len(listins) and runtime < 10000000 and not _break:
        pos, strout_add, _break, runtime_add = await mbfChg(pos, listins, listin, listins[pos], stack, maps)
        strout += strout_add
        runtime += runtime_add + 1
        pos += 1
    return strout, _break, runtime

async def _SaveSub(name, content):
    global mbfSub
    if name not in mbfSub:
        mbfSub[name] = [content, ""]
    else:
        mbfSub[name][0] = content
    await save()
    return True

async def _SetSubStr(name, string):
    global mbfSub
    if name in mbfSub:
        mbfSub[name][1] = string
        await save()
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
            if not key.islower() and val[1] != "":
                yield key + "  " + val[1]
    l = list(_g())
    l.sort()
    return l

async def _Run(strins, strin):
    return await mbfInterpret(list(strins), list(strin), [])

# vim:fdm=marker:fdc=3