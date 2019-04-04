import contextlib
import sys
import re
import math
import random
import functools
import asyncio
import requests
import wand.image, wand.color
from io import StringIO
from string import Formatter
from nonebot import on_command, CommandSession, permission
import chiharu.plugins.config as config
from chiharu.plugins.birth import myFormatter
import chiharu.plugins.maj as maj

@on_command(('misc', 'asc', 'check'), only_to_me=False)
@config.ErrorHandle
async def AscCheck(session: CommandSession):
    strin = session.current_arg_text.strip()
    strout = ' '.join(map(str, map(ord, strin)))
    await session.send('对应数字是：\n' + strout, auto_escape=True)

@on_command(('misc', 'asc', 'trans'), only_to_me=False)
@config.ErrorHandle
async def AscTrans(session: CommandSession):
    strin = session.current_arg_text.split(' ')
    strout = ''.join(map(chr, map(int, strin)))
    await session.send('对应字符是：\n' + strout, auto_escape=True)

@contextlib.contextmanager
def stdoutIO(stdout=None):
	old = sys.stdout
	if stdout is None:
		stdout = StringIO()
	sys.stdout = stdout
	yield stdout
	sys.stdout = old

@on_command(('python', 'exec'), only_to_me=False, permission=permission.SUPERUSER)
@config.ErrorHandle
async def PythonExec(session: CommandSession):
    with stdoutIO() as s:
        exec(session.current_arg_text, {}, {})
    await session.send(s.getvalue()[:-1], auto_escape=True)

@on_command(('misc', 'maj', 'ten'), only_to_me=False)
@config.ErrorHandle
async def Maj(session: CommandSession):
    pu = session.get('pu')
    han = session.get('han')
    qin = session.get('qin')
    zi = session.get('zi')
    if not qin and not zi:
        qin = True
        zi = True
    def ceil(x, base = 100):
        return base * math.ceil(x / base)
    if pu % 10 != 0 and pu != 25:
        pu = ceil(pu, 10)
    if han <= 5:
        ten_base = pu * 2 ** (han + 2)
        ten_qin = ceil(6 * ten_base)
        ten_zi = ceil(4 * ten_base)
        if ten_qin >= 12000:
            str_qin = '満贯，12000点，4000ALL'
        else:
            str_qin = '%i点，%iALL' % (ten_qin, ceil(ten_qin / 3))
        if ten_zi >= 8000:
            str_zi = '満贯，8000点，2000，4000'
        else:
            str_zi = '%i点，%i，%i' % (ten_zi, ceil(ten_base), ceil(2 * ten_base))
    else:
        if han >= 13:
            i = 3
        else:
            i = {6: 0, 7: 0, 8: 1, 9: 1, 10: 1, 11: 2, 12: 2}[han]
        str_i = ['跳満', '倍満', '三倍満', '役満'][i]
        int_i = [3000, 4000, 6000, 8000][i]
        str_qin = '%s，%i点，%iALL' % (str_i, int_i * 6, int_i * 2)
        str_zi = '%s，%i点，%i，%i' % (str_i, int_i * 4, int_i, int_i * 2)
    if qin and zi:
        await session.send('親家：%s\n子家：%s' % (str_qin, str_zi))
    elif qin:
        await session.send(str_qin)
    elif zi:
        await session.send(str_zi)

@Maj.args_parser
async def _(session: CommandSession):
    pu = re.search('(\\d+)符', session.current_arg_text)
    han = re.search('(\\d+)番', session.current_arg_text)
    qin = re.search('亲家|親家', session.current_arg_text)
    zi = re.search('子家', session.current_arg_text)
    if pu is None or han is None:
        pass
    session.args['pu'] = int(pu.group(1))
    session.args['han'] = int(han.group(1))
    session.args['qin'] = qin is not None
    session.args['zi'] = zi is not None

daan = {}

@on_command(('misc', 'maj', 'train'), only_to_me=False)
@config.ErrorHandle
async def maj_train(session: CommandSession):
    global daan
    text = session.current_arg_text
    p = False
    if text.startswith('p'):
        text = text[1:]
        p = True
    if text == '0':
        str_title = '清一色听牌训练（排序，无暗杠，无鸣牌，不含七对）\n'
        _continue = True
        while _continue:
            stack = []
            for i in range(4):
                if random.random() < 0.3:
                    a = random.randint(1, 9)
                    stack.append(a)
                    stack.append(a)
                    stack.append(a)
                else:
                    a = random.randint(1, 7)
                    stack.append(a)
                    stack.append(a + 1)
                    stack.append(a + 2)
            a = random.randint(1, 9)
            stack.append(a)
            stack.append(a)
            stack.sort()
            stack.pop(random.randint(0, len(stack) - 1))
            test = [0, 0, 0, 0, 0, 0, 0, 0, 0]
            for i in stack:
                test[i - 1] += 1
            _continue = False
            for i in test:
                if i > 4:
                    _continue = True
        if p:
            tehai = ''.join(map(str, stack)) + random.choice(['m', 's', 'p']) + '5z'
            d = Maj.search_for('')
            s = Maj.compile(tehai, **d)
            loop = asyncio.get_event_loop()
            u = 'http://mjv.jp/2/img/n%s.png' % s
            url2 = await loop.run_in_executor(None, functools.partial(requests.get, u,
                headers={'Referer': 'http://tenhou.net/2/img/'}))
            name = str(hash((s, session.ctx['group_id'], session.ctx['user_id'])))
            with open(config.img(name + '.png'), 'wb') as f:
                f.write(url2.content)
            await session.send([config.cq.text(str_title), config.cq.img(name + '.png')], auto_escape=True)
        else:
            strout = str_title + ''.join(map(str, stack))
            await session.send(strout, auto_escape=True)
        result = maj.MajHai._ting(map(lambda x: x - 1, stack))
        daan[session.ctx['group_id']] = \
            ''.join(map(lambda x: str(x[0] + 1), filter(lambda x: x[1] > 0, enumerate(map(len, result)))))
    elif text == '2':
        str_title = '清一色加强型听牌训练（排序，无暗杠，无鸣牌，不含七对）\n'
        stack = []
        for i in range(random.randint(5, 8)):
            if random.random() < 0.3:
                a = random.randint(1, 9)
                stack.append(a)
                stack.append(a)
                stack.append(a)
            else:
                a = random.randint(1, 7)
                stack.append(a)
                stack.append(a + 1)
                stack.append(a + 2)
        a = random.randint(1, 9)
        stack.append(a)
        stack.append(a)
        stack.sort()
        stack.pop(random.randint(0, len(stack) - 1))
        strout = str_title + ''.join(map(str, stack))
        await session.send(strout, auto_escape=True)
        result = maj.MajHai._ting(map(lambda x: x - 1, stack))
        daan[session.ctx['group_id']] = \
            ''.join(map(lambda x: str(x[0] + 1), filter(lambda x: x[1] > 0, enumerate(map(len, result)))))
    elif text == '-1':
        if session.ctx['group_id'] not in daan:
            await session.send('没有题目')
        else:
            await session.send(daan.pop(session.ctx['group_id']))
    else:
        await session.send('支持参数：\n0或p0：清一色听牌训练（排序，无暗杠，无鸣牌，不含七对）\n2：清一色加强型听牌训练（排序，无暗杠，无鸣牌，不含七对）\n-1：返回上次的答案')

class MajException(Exception):
    def __init__(self, arg):
        self.args = arg

class Maj:
    @staticmethod
    def expand(s: str):
        l = []
        for char in s:
            if char in '0123456789':
                l.append(char)
            elif char in 'mpsz':
                for i in l:
                    yield i + char
                l = []
            else:
                raise MajException('unknown char ' + char)
        if len(l) != 0:
            for i in l:
                yield i
    @staticmethod
    def extract34(s: str):
        return re.sub('(\d)z', '4\\1',
            re.sub('(\d)s', '3\\1',
            re.sub('(\d)p', '2\\1',
            re.sub('(\d)m', '1\\1',
            re.sub('0s', '53',
            re.sub('0p', '52',
            re.sub('0m', '51', s)))))))
    @staticmethod
    def compile(tehai: str, tehaionly: bool, dora: str, kyoku: int, step: int, rot: int):
        q = Maj.extract34(''.join(Maj.expand(tehai)))
        if len(q) != 14 * 2:
            raise MajException('INVALID TEHAI LENGTH')
        if not tehaionly:
            dora = Maj.extract34(''.join(Maj.expand(dora)))
            tail = '%02d%02d%1d' % (kyoku, step, rot)
            q += dora + tail
        return q
    @staticmethod
    def search_for(k: str):
        if k == '':
            return {'tehaionly': True, 'dora': None, 'kyoku': None, 'step': None, 'rot': None}
        kyoku = re.search('(?:([东東])|(南))(\d)局', k)
        step = re.search('(\d+)巡目', k)
        rot = re.search('(?:([东東])|(南)|(西)|(北))家', k)
        dora = re.search('dora(?:\s*):(?:\s*)(.*)$', k)
        if not kyoku and not step and not rot and not dora:
            return {'tehaionly': True, 'dora': None, 'kyoku': None, 'step': None, 'rot': None}
        if not dora:
            raise MajException('没有宝牌')
        if not kyoku:
            raise MajException('没有局数')
        if not step:
            raise MajException('没有巡目')
        if not rot:
            raise MajException('没有自家')
        kyoku = (0 if kyoku.group(1) is not None else 4) + int(kyoku.group(3)) - 1
        rot = (0 if rot.group(1) is not None else (1 if rot.group(2) is not None else
            (2 if rot.group(3) is not None else 3)))
        return {'tehaionly': False, 'dora': dora.group(1), 'kyoku': kyoku,
            'step': int(step.group(1)), 'rot': rot}

@on_command(('misc', 'maj', 'img'), only_to_me=False)
@config.ErrorHandle
async def maj_img(session: CommandSession):
    test = session.get('arg')
    if test == False:
        await session.send(''.join(session.get('except').args), auto_escape=True)
        return
    loop = asyncio.get_event_loop()
    u = 'http://mjv.jp/2/img/n%s.png' % test
    url2 = await loop.run_in_executor(None, functools.partial(requests.get, u,
        headers={'Referer': 'http://tenhou.net/2/img/'}))
    name = str(hash((test, session.ctx['group_id'], session.ctx['user_id'])))
    with open(config.img(name + '.png'), 'wb') as f:
        f.write(url2.content)
    await session.send(config.cq.img(name + '.png'), auto_escape=True)

@maj_img.args_parser
@config.ErrorHandle
async def _(session: CommandSession):
    try:
        l = session.current_arg_text.split(' ')
        tehai = l[0]
        d = Maj.search_for(' '.join(l[1:]))
        session.args['arg'] = Maj.compile(tehai, **d)
    except MajException as e:
        session.args['arg'] = False
        session.args['except'] = e

@on_command(('misc', 'maj', 'ting'), only_to_me=False)
@config.ErrorHandle
async def maj_ting(session: CommandSession):
    def expand(s):
        l = []
        for char in s:
            if char in '123456789':
                l.append(char)
            elif char in 'mpsz':
                for i in l:
                    yield i + char
                l = []
            else:
                raise MajException('unknown char ' + char)
        if len(l) != 0:
            raise MajException('unknown end')
    try:
        tehai = list(map(maj.MajHai, expand(session.current_arg_text)))
        if len(tehai) % 3 != 1:
            await session.send('INVALID TEHAI LENGTH')
            return
        result = maj.MajHai.ten(tehai)
        if len(tehai) == 13:
            result.update(maj.MajHai.qitui(tehai))
            result.update(maj.MajHai.kokushimusou(tehai))
        if result == {}:
            await session.send('没听')
        else:
            def _():
                keys = list(result.keys())
                keys.sort()
                for hai in keys:
                    num = hai % 9
                    color = hai // 9
                    color_c = {0: 'm', 1: 'p', 2: 's', 3: 'z'}[color]
                    yield str(num + 1) + color_c
            await session.send(' '.join(_()))
    except MajException as e:
        await session.send(''.join(e.args))
    except maj.MajErr as e:
        await session.send(str(e))

@on_command(('misc', 'maj', 'ting_ex'), only_to_me=False)
@config.ErrorHandle
async def maj_ting(session: CommandSession):
    def expand(s):
        l = []
        for char in s:
            if char in '123456789':
                l.append(char)
            elif char in 'mpsz':
                for i in l:
                    yield i + char
                l = []
            else:
                raise MajException('unknown char ' + char)
        if len(l) != 0:
            raise MajException('unknown end')
    try:
        tehai = list(map(maj.MajHai, expand(session.current_arg_text)))
        if len(tehai) % 3 != 1:
            await session.send('INVALID TEHAI LENGTH')
            return
        result = maj.MajHai.ten(tehai)
        if len(tehai) == 13:
            result.update(maj.MajHai.qitui(tehai))
            result.update(maj.MajHai.kokushimusou(tehai))
        if result == {}:
            await session.send('没听')
        else:
            def _():
                keys = list(result.keys())
                keys.sort()
                for hai in keys:
                    num = hai % 9
                    color = hai // 9
                    color_c = {0: 'm', 1: 'p', 2: 's', 3: 'z'}[color]
                    s = str(num + 1) + color_c + ": "
                    for barrel, v in result[hai][0].items():
                        if barrel <= 2:
                            for t in v:
                                s += ''.join(map(lambda x: str(x + 1), t))
                                s += {0: 'm', 1: 'p', 2: 's'}[barrel]
                        else:
                            s += ''.join(map(lambda x: str(barrel - 2), t))
                            s += 'z'
                    yield s
            await session.send('\n'.join(_()))
    except MajException as e:
        await session.send(''.join(e.args))
    except maj.MajErr as e:
        await session.send(str(e))

@on_command(('misc', 'maj', 'zj'), only_to_me=False)
@config.ErrorHandle
async def maj_zj_ten(session: CommandSession):
    try:
        tehai = []
        fuuros = []
        l = []
        fuuro_status = None
        for char in session.current_arg_text:
            if char in '123456789':
                l.append(char)
            elif char in 'mpsz':
                if fuuro_status is None:
                    tehai.extend(map(lambda x: maj.MajZjHai(x + char), l))
                else:
                    fuuros.append(maj.FuuRo(fuuro_status, tuple(map(lambda x: maj.MajZjHai(x + char), l))))
                l = []
            elif char == '暗':
                fuuro_status = maj.FuuRoStatus(0)
            elif char in '吃碰杠':
                if len(l) != 0:
                    raise MajException('unknown end')
                if fuuro_status == 0 and char == '杠':
                    pass
                else:
                    fuuro_status = maj.FuuRoStatus({'吃': 4, '碰': 8, '杠': 16}[char])
            elif char != ' ':
                break
        status = maj.PlayerStatus(0)
        if "岭上" in session.current_arg_text:
            status |= maj.PlayerStatus.RINSHAN
        if "河底" in session.current_arg_text or "海底" in session.current_arg_text:
            status |= maj.PlayerStatus.HAIDI
        if "抢杠" in session.current_arg_text:
            status |= maj.PlayerStatus.QIANKAN
        if "荣" in session.current_arg_text:
            status |= maj.PlayerStatus.NAKU
        pos = maj.PlayerPos(0)
        if "南家" in session.current_arg_text:
            pos = maj.PlayerPos(1)
        elif "西家" in session.current_arg_text:
            pos = maj.PlayerPos(2)
        elif "北家" in session.current_arg_text:
            pos = maj.PlayerPos(3)
        if len(l) != 0:
            raise MajException('unknown end')
        if len(tehai) % 3 != 2:
            await session.send('INVALID TEHAI LENGTH')
            return
        for fuuro in fuuros:
            if not fuuro.isValid:
                await session.send(str(fuuro) + "不合理")
                return
        results = maj.MajZjHai.ten(tehai[:-1])  # type: Dict[int, List[Dict[int, Tuple[Tuple[int,...],...]]]]
        hai = tehai[-1].hai
        if hai not in results:
            await session.send("没和")
            return
        result = results[hai]
        hezhong, hestatus, ten = maj.MajZjHai.tensu(hai, result, fuuros, (pos, status))
        await session.send('\n'.join(map(lambda x: "%s  %i点" % (str(x), x.int()), hezhong)) + "\n" + ((str(hestatus) + "\n") if str(hestatus) != "" else "") + ("%i点" % ten))
    except maj.Not14 as e:
        await session.send(str(e))
    except MajException as e:
        await session.send(''.join(e.args))
    except maj.MajErr as e:
        await session.send(str(e))

token = {}
with open(config.rel('unicode.txt'), encoding='utf-16') as f:
    for line in f:
        match2 = re.search('"(.*)"\\s*:\\s*"(.*)"', line)
        match1 = re.search("'(.*)'\\s*:\\s*'(.*)'", line)
        if not match1 and not match2:
            raise KeyError
        if match1:
            token[match1.group(1)] = match1.group(2)
        else:
            token[re.sub('\\\\\\\\', '\\\\', match2.group(1))] = re.sub('\\\\\\\\', '\\\\', match2.group(2))

@on_command(('misc', 'token'), only_to_me=False)
@config.ErrorHandle
async def token_alpha(session: CommandSession):
    try:
        global token
        strout = myFormatter().vformat(session.current_arg_text, (), token)
        await session.send('对应字符是：\n' + strout, auto_escape=True)
    except KeyError:
        await session.send('KeyError')

@on_command(('misc', 'latex'), only_to_me=False)
@config.ErrorHandle
async def latex(session: CommandSession):
    loop = asyncio.get_event_loop()
    ipt = re.sub('\+', '%2B', session.current_arg_text)
    url = await loop.run_in_executor(None, functools.partial(requests.get,
        'https://www.zhihu.com/equation?tex=' + ipt,
        headers={'user-agent': config.user_agent}))
    name = str(hash((session.current_arg_text, session.ctx['group_id'], session.ctx['user_id'])))
    with open(config.img(name + '.svg'), 'wb') as f:
        f.write(url.content)
    with wand.image.Image(filename=config.img(name + '.svg')) as image:
        with image.convert('png') as converted:
            converted.background_color = wand.color.Color('white')
            converted.alpha_channel = 'remove'
            converted.save(filename=config.img(name + '.png'))
    await session.send(config.cq.img(name + '.png'))

@on_command(('misc', 'shuru'), only_to_me=False)
@config.ErrorHandle
async def shuru(session: CommandSession):
    pass