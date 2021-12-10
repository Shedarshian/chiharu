import contextlib
import sys
import re
import os
import math
import random
import functools
import asyncio
import requests
import json
import getopt
from datetime import date, timedelta
import wand.image, wand.color
from io import StringIO
from string import Formatter
from nonebot import CommandSession, permission, on_natural_language, NLPSession
from nonebot.message import escape
from .inject import on_command
from . import config
from .birth import myFormatter
from . import math as cmath
from .games import maj
from .games.achievement import achievement

config.CommandGroup('misc', short_des='隐藏指令。')
config.CommandGroup(('misc', 'asc'), short_des='asc/Unicode字符翻译。')

@on_command(('misc', 'asc', 'check'), only_to_me=False, short_des="转换输入字符串的所有字符到unicode码。", shell_like=True, args=['-h'])
@config.ErrorHandle
async def AscCheck(session: CommandSession):
    '''转换输入字符串的所有字符到unicode码。
    可用选项：
        -h/--hex，转换至U+xxxxx十六进制输出'''
    opts, args = getopt.gnu_getopt(session.args['argv'], 'h', ['hex'])
    h = False
    for o, a in opts:
        if o in ('-h', '--hex'):
            h = True
    strin = args[0]
    format_string = "U+{:x}" if h else "{}"
    strout = ' '.join([format_string.format(ord(x)) for x in strin])
    await session.send('对应数字是：\n' + strout)

@on_command(('misc', 'asc', 'trans'), only_to_me=False)
@config.ErrorHandle
async def AscTrans(session: CommandSession):
    '''转换多个数字到unicode字符。'''
    strin = session.current_arg_text.split(' ')
    def _(x):
        if x.startswith('U+'):
            return int(x[2:], 16)
        return int(x)
    try:
        strout = ''.join([chr(_(i)) for i in strin])
        await session.send(escape('对应字符是：\n' + strout))
    except ValueError:
        await session.send('请输入十进制数字或U+xxx十六进制数字。')

@contextlib.contextmanager
def stdoutIO(stdout=None):
    old = sys.stdout
    if stdout is None:
        stdout = StringIO()
    sys.stdout = stdout
    yield stdout
    sys.stdout = old

config.CommandGroup('python', hide=True)

@on_command(('python', 'exec'), only_to_me=False, permission=permission.SUPERUSER, hide=True)
@config.ErrorHandle
async def PythonExec(session: CommandSession):
    with stdoutIO() as s:
        exec(session.current_arg_text, {}, {})
    await session.send(s.getvalue()[:-1])

@on_command(('python', 'await'), only_to_me=False, permission=permission.SUPERUSER, hide=True)
@config.ErrorHandle
async def PythonAwait(session: CommandSession):
    with stdoutIO() as s:
        local = {'session': session}
        exec('async def main():\n  ' + '\n  '.join(session.current_arg_text.split('\n')), local, local)
        await local['main']()
    await session.send(s.getvalue()[:-1])

config.CommandGroup(('misc', 'maj'), short_des='麻将小助手。')

@on_command(('misc', 'maj', 'ten'), only_to_me=False, short_des="日麻算点器。")
@config.ErrorHandle
async def maj_ten(session: CommandSession):
    """日麻算点器。
    输入几番几符，可计算得点。可额外指定亲家或子家。"""
    pu_match = re.search('(\\d+)符', session.current_arg_text)
    han_match = re.search('(\\d+)番', session.current_arg_text)
    qin_match = re.search('亲家|親家', session.current_arg_text)
    zi_match = re.search('子家', session.current_arg_text)
    if not pu_match or not han_match:
        await session.send('输入格式有误。请输入几番几符。')
        return
    pu = int(pu_match.group(1))
    han = int(han_match.group(1))
    qin = qin_match is not None
    zi = zi_match is not None
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

async def GetMajImg(s):
    loop = asyncio.get_event_loop()
    u = 'http://mjv.jp/2/img/n%s.png' % s
    url2 = await loop.run_in_executor(None, functools.partial(requests.get, u,
        headers={'Referer': 'http://tenhou.net/2/img/'}))
    name = str(hash(s))
    with open(config.img(name + '.png'), 'wb') as f:
        f.write(url2.content)
    return name

daan = {}

@on_command(('misc', 'maj', 'train'), only_to_me=False, shell_like=True, short_des="麻将训练。", args=("number", '[-a]', '[-p]'))
@config.ErrorHandle
async def maj_train(session: CommandSession):
    """麻将训练。
    使用数字指定练习题，-a为查看上题答案。
    0：清一色听牌训练（排序，无暗杠，无鸣牌，不含七对）
    2：清一色加强型听牌训练（排序，无暗杠，无鸣牌，不含七对）
    可用选项：
    -a：查看上题答案。
    -p：使用天凤图。"""
    global daan
    try:
        group_id = session.ctx['group_id']
    except:
        group_id = session.ctx['user_id']
    p, a = False, False
    opts, args = getopt.gnu_getopt(session.args['argv'], 'pa', [])
    for o, a in opts:
        if o == '-p':
            p = True
        if o == '-a':
            a = True
    text = args[0]
    if a:
        if group_id not in daan:
            await session.send('没有当前题目')
        else:
            await session.send('答案为：' + str(daan.pop(group_id)))
    elif text == '0':
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
            name = await GetMajImg(s)
            await session.send([config.cq.text(str_title), config.cq.img(name + '.png')])
        else:
            strout = str_title + ''.join(map(str, stack))
            await session.send(strout)
        result = maj.MajHai._ting(map(lambda x: x - 1, stack))
        daan[group_id] = \
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
        await session.send(strout)
        result = maj.MajHai._ting(map(lambda x: x - 1, stack))
        daan[group_id] = \
            ''.join(map(lambda x: str(x[0] + 1), filter(lambda x: x[1] > 0, enumerate(map(len, result)))))
    else:
        await session.send('使用数字指定练习题，-a为查看上题答案。\n0：清一色听牌训练（排序，无暗杠，无鸣牌，不含七对）\n2：清一色加强型听牌训练（排序，无暗杠，无鸣牌，不含七对）')

class MajException(Exception):
    def __init__(self, arg):
        self.args[0] = arg

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
    """天凤牌图。"""
    try:
        l = session.current_arg_text.split(' ')
        tehai = l[0]
        d = Maj.search_for(' '.join(l[1:]))
        test = Maj.compile(tehai, **d)
    except MajException as e:
        await session.send(e.args[0])
        return
    name = await GetMajImg(test)
    await session.send(config.cq.img(name + '.png'))

@on_command(('misc', 'maj', 'ting'), only_to_me=False)
@config.ErrorHandle
async def maj_ting(session: CommandSession):
    """麻将听牌计算器。"""
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
        if len(tehai) % 3 != 1 or len(tehai) >= 40:
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

@on_command(('misc', 'maj', 'ting_ex'), only_to_me=False, permission=permission.SUPERUSER, hide=True)
@config.ErrorHandle
async def maj_ting_ex(session: CommandSession):
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
        if len(tehai) % 3 != 1 or len(tehai) >= 40:
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
        await session.send(e.args[0])
    except maj.MajErr as e:
        await session.send(str(e))

@on_command(('misc', 'maj', 'zj'), only_to_me=False, short_des="中庸麻将点数计算器。", args=('tehai', '[fuuro]', '[others]'))
@config.ErrorHandle
async def maj_zj_ten(session: CommandSession):
    """中庸麻将点数计算器。
    输入格式为：手牌（如12s33p3s，荣和最后一张牌） 副露（如吃123s暗杠2222p） 其余状态（如南家岭上河底荣和）"""
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
        await session.send(e.args[0])
    except maj.MajErr as e:
        await session.send(str(e))

@on_command(('misc', 'maj', 'voice'), only_to_me=False, short_des="雀魂报番语音。")
@config.ErrorHandle
async def maj_voice(session: CommandSession):
    """雀魂报番语音。
    输入番种名，换行后输入雀士名。不输入雀士名默认为一姬。"""
    if '\n' in session.current_arg_text:
        content, voicer_str = session.current_arg_text.split('\n')
        content = content.strip()
        voicer_str = voicer_str.strip()
    else:
        voicer_str = '1'
        content = session.current_arg_text
    voicer_dict = {'一姬': 1, '1': 1, '二阶堂': 2, '二阶堂美树': 2, '2': 2, '千织': 3, '三上千织': 3, '3': 3, '四宫夏生': 4, '夏生': 4, '4': 4, '相原舞': 5, '抚子': 6, '佳奈': 7, '藤田佳奈': 7, '八木唯': 8, '八木': 8, '8': 8, '九条': 9, '九条璃雨': 9, '9': 9, '泽尼娅': 10, '卡维': 11, '汪次郎': 12, '汪': 12, '一之濑空': 13, '明智英树': 14, '轻库娘': 15, '莎拉': 16, '二之宫花': 17, '二之宫': 17, '白石奈奈': 18, '奈奈': 18, '小鸟游雏田': 19, '五十岚阳菜': 20, '凉宫杏树': 21, '约瑟夫': 22, '斋藤治': 23}
    voicer_name = {1: 'yiji', 2: 'erjietang', 3: 'qianzhi', 4: 'sigongxiasheng', 5: 'xiangyuan', 6: 'fuzi', 7: 'jianai', 8: 'bamuwei', 9: 'jiutiao', 10: 'zeniya', 11: 'kawei', 12: 'wangcilang', 13: 'yizhilaikong', 14: 'mingzhiyingshu', 15: 'qingkuniang', 16: 'shala', 17: 'erzhigonghua', 18: 'baishinainai', 19: 'xiaoniaoyouchutian', 20: 'wushilanyangcai', 21: 'lianggongxingshu', 22: 'yuesefu', 23: 'zhaitengzhi'}
    if voicer_str in voicer_dict:
        voicer = voicer_name[voicer_dict[voicer_str]]
    else:
        await session.send('未找到角色' + voicer_str)
        return
    try:
        l = list(maj_parse(content, voicer_dict[voicer_str]))
    except maj.MajErr as e:
        await session.send(e.args[0])
        return
    if not os.path.isdir(config.rel(f'Cache\\majsoul_voice\\{voicer}')):
        os.mkdir(config.rel(f'Cache\\majsoul_voice\\{voicer}'))
    loop = asyncio.get_event_loop()
    from pydub import AudioSegment
    try:
        for audio in l:
            if not os.path.isfile(config.rel(f'Cache\\majsoul_voice\\{voicer}\\{audio}.mp3')):
                url = await loop.run_in_executor(None, functools.partial(requests.get,
                    f'https://majsoul.com/1/v0.6.74.w/audio/sound/{voicer}/{audio}.mp3'))
                if url.status_code != 200:
                    raise maj.MajErr(f"{voicer}/{audio}.mp3 can't download")
                with open(config.rel(f'Cache\\majsoul_voice\\{voicer}\\{audio}.mp3'), 'wb') as f:
                    f.write(url.content)
    except maj.MajErr as e:
        await session.send(e.args[0])
        return
    except requests.exceptions.SSLError as e:
        await session.send("雀魂连接失败！")
        return
    audio_fin = functools.reduce(lambda x, y: x + AudioSegment.silent(duration=200) + y,
        [AudioSegment.silent(duration=400) + AudioSegment.from_mp3(config.rel(f'Cache\\majsoul_voice\\{voicer}\\{audio}.mp3'))
        if audio.startswith('gameend') else
        AudioSegment.from_mp3(config.rel(f'Cache\\majsoul_voice\\{voicer}\\{audio}.mp3')) for audio in l])
    audio_fin.export(config.rec(str(hash(session.current_arg_text)) + '.mp3'), format='mp3')
    await session.send(config.cq.rec(str(hash(session.current_arg_text)) + '.mp3'))

def maj_parse(content: str, voicer_id: int):
    # args
    d = {"立直": (1, 1), "立": (1, 1), "两立直": (1, 2), "一发": (1, 3), "自摸": (1, 4), "门前清自摸和": (1, 4), "门": (1, 1),
        "东": (2, 1), "南": (2, 2), "西": (2, 3), "北": (2, 4), "白": (2, 5), "发": (2, 6), "中": (2, 7),
        "枪杠": (3, 1), "抢杠": (3, 1), "岭上开花": (3, 2), "岭上": (3, 2), "海底摸月": (3, 3), "海底": (3, 3), "河底捞鱼": (3, 4), "河底": (3, 4),
        "断幺九": (5, 1), "断幺": (5, 1), "断": (5, 1),
        "平和": (6, 1), "平": (6, 1),
        "一杯口": (7, 1), "一杯": (7, 1), "一般高": (7, 1), "两杯口": (7, 2), "两杯": (7, 2), "二杯口": (7, 2),
        "三色同顺": (8, 1), "三色同刻": (8, 2), "三色": (8, 1), "一气通贯": (8, 3), "一气": (8, 3), "一通": (8, 3),
        "七对子": (9, 1), "七对": (9, 1),
        "对对和": (10, 1), "对对": (10, 1), "碰碰和": (10, 1),
        "三暗刻": (11, 1), "三暗": (11, 1), "四暗刻单骑": (11, 3), "四暗刻": (11, 2), "四暗单": (11, 3), "四暗": (11, 2),
        "三杠子": (12, 1), "四杠子": (12, 2),
        "小三元": (13, 1), "大三元": (13, 2),
        "小四喜": (14, 1), "大四喜": (14, 2), "四喜和": (14, 1), "四喜": (14, 1),
        "混全带幺九": (15, 1), "混全带": (15, 1), "混全": (15, 1), "全带": (15, 1), "纯全带幺九": (15, 2), "纯全带": (15, 2), "纯全": (15, 2),
        "混老头": (15, 3), "混幺九": (15, 3), "清老头": (15, 4), "清幺九": (15, 4),
        "混一色": (16, 1), "清一色": (16, 2), "绿一色": (16, 3), "九莲宝灯": (16, 4), "九莲": (16, 4), "纯正九莲宝灯": (16, 5), "纯九莲": (16, 5), "准正九莲宝灯": (16, 4),
        "天和": (17, 1), "地和": (17, 2),
        "字一色": (18, 1),
        "国士无双十三面": (19, 2), "国士无双13面": (19, 2), "国士无双": (19, 1), "十三幺九": (19, 1), "十三幺": (19, 1), "纯国士无双": (19, 2), "国士十三面": (19, 2), "国士13面": (19, 2), "国士": (19, 1),
        "流局满贯": (20, 1), "流满": (20, 1)}
    voice = {(1, 1): "rich", (1, 2): "drich", (1, 3): "yifa", (1, 4): "tumo",
        (2, 1): "dong", (2, 2): "nan", (2, 3): "xi", (2, 4): "bei",
        (2, 5): "bai", (2, 6): "fa", (2, 7): "zhong",
        (3, 1): "qianggang", (3, 2): "lingshang", (3, 3): "haidi", (3, 4): "hedi",
        #(4, 1): "宝牌", (4, 2): "红宝牌", (4, 3): "里宝牌", (4, 4): "北宝牌",
        (5, 1): "duanyao",
        (6, 1): "pinghu",
        (7, 1): "yibeikou", (7, 2): "erbeikou",
        (8, 1): "sansetongshun", (8, 2): "sansetongke", (8, 3): "yiqitongguan",
        (9, 1): "qiduizi",
        (10, 1): "duiduihu",
        (11, 1): "sananke", (11, 2): "sianke", (11, 3): "siankedanqi",
        (12, 1): "sangangzi", (12, 2): "sigangzi",
        (13, 1): "xiaosanyuan", (13, 2): "dasanyuan",
        (14, 1): "xiaosixi", (14, 2): "dasixi",
        (15, 1): "hunquandaiyaojiu", (15, 2): "chunquandaiyaojiu", (15, 3): "hunlaotou", (15, 4): "qinglaotou",
        (16, 1): "hunyise", (16, 2): "qingyise", (16, 3): "lvyise", (16, 4): "jiulianbaodeng", (16, 5): "chunzhengjiulianbaodeng",
        (17, 1): "tianhu", (17, 2): "dihu",
        (18, 1): "ziyise",
        (19, 1): "guoshiwushuang", (19, 2): "guoshishisanmian",
        (20, 1): "liujumanguan"}
    if voicer_id >= 8:
        voice[(1, 1)] = 'liqi'
        voice[(1, 2)] = 'dliqi'
        voice[(1, 4)] = 'zimo'
    #ddr = {"dora": 1, "宝": 1, "赤宝": 2, "红宝":2, "里宝": 3}
    w = re.compile('东|南|西|北|立直?')
    al = re.compile('|'.join(d.keys()))
    dora = re.compile('(dr|dora|宝|赤宝|红宝|里宝|赤|里)牌?(\d*)')
    d2 = {"满贯": 'manguan', "跳满": 'tiaoman', "倍满": 'beiman', "三倍满": 'sanbeiman', "役满": 'yiman1',
        "累计役满": 'leijiyiman', "两倍役满": "yiman2", "三倍役满": "yiman3", "四倍役满": "yiman4",
        "五倍役满": "yiman5", "六倍役满": "yiman6"}
    ten = re.compile('|'.join(d2.keys()))
    if_w = ''
    if_end = ''
    yakuman = 0
    while len(content):
        if if_w:
            match = w.match(content)
            if match:
                content = content[match.span()[1]:]
                if match.group()[0] == '立':
                    yield 'fan_' + voice[(1, 2)]
                else:
                    yield 'fan_double' + voice[d[match.group()]]
            else:
                raise maj.MajErr('役种名读取失败: ' + if_w + content[0:1] + '...')
            if_w = ''
        elif content[0] == ' ':
            content = content[1:]
        elif if_end:
            raise maj.MajErr(if_end + '应为结尾')
        elif content[0] == 'w' or content[0] == '连':
            content = content[1:]
            if_w = content[0]
        else:
            match = al.match(content)
            if match:
                content = content[match.span()[1]:]
                yield 'fan_' + voice[d[match.group()]]
                han = maj.MajRichiHai.HeZhong.dict_ten[d[match.group()]][0]
                if han >= 13:
                    yakuman += han // 13
            else:
                match = dora.match(content)
                if match:
                    content = content[match.span()[1]:]
                    count = 1 if match.group(2) == '' else int(match.group(2))
                    if count > 13:
                        count = 13
                    yield 'fan_dora' + str(count)
                else:
                    match = ten.match(content)
                    if match:
                        content = content[match.span()[1]:]
                        if_end = match.group(0)
                        yield 'gameend_' + d2[match.group(0)]
                    else:
                        raise maj.MajErr('役种名读取失败: ' + content[0:2] + '...')
    if if_end == '' and yakuman > 0 and yakuman <= 6:
        yield 'gameend_yiman' + str(yakuman)

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

@on_command(('misc', 'token'), only_to_me=False, short_des="Unicode字符翻译。")
@config.ErrorHandle
async def token_alpha(session: CommandSession):
    """Unicode字符翻译。
    将输入文本中大括号包含的token转换成latex中包含的unicode字符。
    使用的替换为：https://github.com/joom/latex-unicoder.vim/blob/master/autoload/unicoder.vim, https://pastebin.com/jxHsjQK0
    例：-misc.token f(0)={\\aleph}_0,f({\\alpha}+1)={\\aleph}_{\\alpha}"""
    try:
        global token
        strout = myFormatter().vformat(session.current_arg_text, (), token)
        await session.send(escape('对应字符是：\n' + strout))
    except KeyError as e:
        await session.send(f'字符{e.args[0]}未能识别')

@on_command(('misc', 'latex'), only_to_me=False)
@config.ErrorHandle
async def latex(session: CommandSession):
    """渲染latex公式。"""
    if session.current_arg_text == "":
        session.finish('输入不可为空。')
    try:
        group = session.ctx['group_id']
    except KeyError:
        group = None
    await session.send(config.cq.img(await cmath.latex(session.current_arg_text, hsh=(group, session.ctx['user_id']))))

class MoneyComputer:
    class Man:
        def __init__(self, name, id):
            self.name = name
            self.id = id
    class Strategy:
        oneman_id = 0
        @staticmethod
        def oneman(name):
            return (MoneyComputer.Strategy.oneman_id, name)
    
    def __init__(self):
        self.man = []
        self.money = {}
    def clear(self):
        self.man = []
        self.money = {}
    def addMan(self, name):
        self.man.append(MoneyComputer.Man(name, len(self.man)))
        self.money[self.man[-1]] = 0.
    def findMan(self, name):
        return list(filter(lambda x: x.name == name, self.man))[0]
    def addBill(self, m, money, l):
        if len(l) == 0:
            l = self.man
        self.money[m] += float(money)
        part = float(money) / len(l)
        for i in l:
            self.money[i] -= part
    def output(self, strategy):
        if strategy[0] == MoneyComputer.Strategy.oneman_id:
            man = strategy[1]
            def _f():
                for m in self.man:
                    if m is not man:
                        if self.money[m] < 0:
                            yield "%s should give %s %f yuan" % (m.name, man.name, abs(self.money[m]))
                        elif self.money[m] > 0:
                            yield "%s should give %s %f yuan" % (man.name, m.name, self.money[m])
            return "\n".join(list(_f()))
    def process(self, command):
        t = command.split(" ")
        if len(t) == 0:
            return
        if t[0] == "clear":
            self.clear()
        elif t[0] == "add":
            self.addMan(t[1])
        elif t[0] == "bill": # bill name1 money [name2 ...]
            self.addBill(self.findMan(t[1]), float(t[2]), list(map(self.findMan, t[3:])))
        elif t[0] == "output":
            if t[1] == "oneman":
                return self.output(MoneyComputer.Strategy.oneman(self.findMan(t[2])))
    def processLines(self, commands):
        for line in commands:
            ret = self.process(line)
            if ret is not None:
                return ret
        return ''

@on_command(('misc', 'money'), only_to_me=False, short_des="面基算钱小助手。")
@config.ErrorHandle
async def shuru(session: CommandSession):
    """面基算钱小助手。\n\n每个行为一条指令。指令：\nclear: 清除所有数据。\nadd [人名]: 增加一个人。\nbill [人名] [金额] [可选：需付费的人名列表]: 增加一个需付费账单，人名列表为空则默认【包括自己的】所有人。\noutput [策略] [参数]: 输出金额交换。策略目前有：\n\toneman [参数：人名]: 所有金额交换全部支付给此人/由此人支付。"""
    await session.send("结果为：" + MoneyComputer().processLines(session.current_arg_text.split('\n')))

@on_command(('misc', 'omikuji'), only_to_me=False, short_des="妹妹的御神签。")
@config.ErrorHandle
async def omikuji(session: CommandSession):
    """妹妹的御神签。
    每周只能抽一次。"""
    # """千春酱御神签~
    # 每周只能抽一次哦~"""
    version = "チハルちゃんおみくじ ver0.0.1"
    qq = session.ctx['user_id']
    today = date.today()
    with open(config.rel('omikuji.json'), encoding='utf-8') as f:
        m = json.load(f)
    o = m[0]['obfuscate']
    state = random.getstate()
    random.seed((o + (today - timedelta(days=today.weekday())).isoformat() + str(qq)))
    h = random.randint(0, 999)
    random.setstate(state)
    def pick(m, h):
        for i in m:
            h -= i["weight"]
            if h < 0:
                return i
    d = pick(m, h)
    await session.send(f"{version}\n{d['ji']}    {d['name']}\n\n{d['des']}")
    if d['ji'] == '大大吉':
        if achievement.omikuji.get(qq):
            await session.send(achievement.omikuji.get_str())
    elif d['ji'] in ('大凶', '大大凶'):
        if achievement.omikuji2.get(qq):
            await session.send(achievement.omikuji2.get_str())

def load_todo(qq):
    with open(config.rel('todo.json'), encoding='utf-8') as f:
        return json.load(f)[qq]
def save_todo(qq, todo):
    with open(config.rel('todo.json'), encoding='utf-8') as f:
        all = json.load(f)
    all[qq] = todo
    with open(config.rel('todo.json'), 'w', encoding='utf-8') as f:
        f.write(json.dumps(all, ensure_ascii=False, indent=4, separators=(',', ': ')))

def to_str(dct):
    return dct['name'] + (f"\n    progress: {dct['progress']}" if 'progress' in dct else '')
todo_modes = {'progress', 'new', 'move'}
from .helper.function.function import parser, ParserError

@on_command(('todo',), only_to_me=False, permission=permission.SUPERUSER, hide=True)
@config.ErrorHandle
async def todo(session: CommandSession):
    qq = str(session.ctx['user_id'])
    todo_l = load_todo(qq)
    mode = ''
    pointer = None
    for command in session.current_arg_text.split(' '):
        if command == 'remove':
            if pointer is None:
                await session.send('pointer is None')
            else:
                todo_l.pop(pointer)
        elif command in todo_modes:
            mode = command
        elif mode == '':
            # find name/id
            try:
                pointer = [i for i, b in enumerate(todo_l) if str(i) == command or b['name'] == command][0]
            except IndexError:
                await session.send(command + ' not found')
        elif mode == 'new':
            todo_l.append({'name': command})
            mode = ''
        elif pointer is None:
            await session.send('pointer is None')
        elif mode == 'progress':
            if 'progress' not in todo_l[pointer]:
                todo_l[pointer]['progress'] = 0
            parser.reset()
            parser.setstate('x')
            try:
                f = parser.parse(command)
                if type(f) is float:
                    todo_l[pointer]['progress'] = f
                else:
                    todo_l[pointer]['progress'] = f(todo_l[pointer]['progress'])
            except IndexError:
                await session.send('请输入一元函数。')
            except ParserError as e:
                await session.send('SyntaxError: ' + str(e))
            except Exception as e:
                await session.send(type(e).__name__ + ': ' + str(e))
            mode = ''
        elif mode == 'move':
            end = int(command)
            todo_l.insert(end, todo_l.pop(pointer))
            mode = ''
    save_todo(qq, todo_l)
    await session.send('\n'.join([f'{i} {to_str(b)}' for i, b in enumerate(todo_l)]))

from .config import Environment
env = Environment('link_converter', private=True)
@on_natural_language(only_to_me=False)
async def linkconverter(session: NLPSession):
    if await env.test(session):
        match = re.match("\[CQ:rich,content=.*(?:https?://www\.bilibili\.com/video/|https?://b23\.tv/)([0-9a-zA-Z]+).*\]", session.msg)
        if match:
            await session.send('http://b23.tv/' + match.group(1))

@on_command(('misc', 'avtobv'), hide=True, only_to_me=False)
async def avtobv(session: CommandSession):
    text = session.current_arg_text
    if text.startswith('av'):
        await session.send(config.AvBvConverter.enc(text))
    else:
        await session.send('av' + str(config.AvBvConverter.dec(text)))

@on_command(('misc', 'r'), only_to_me=False, short_des="随机骰子。")
@config.ErrorHandle
async def roll(session: CommandSession):
    """随机骰子。
    使用例：-misc.r 3d20+d6+2d
    d前不填默认为1，d后不填默认为100"""
    l = session.current_arg_text.split('+')
    ret = []
    for c in l:
        match = re.match(r'^(\d*)d(\d*)$', c.strip())
        if not match:
            session.finish('语法错误')
        n = int(match.group(1) or 1)
        d = int(match.group(2) or 100)
        if n >= 100:
            session.finish('骰子过多')
        for i in range(n):
            ret.append(random.randint(1, d))
        if len(ret) >= 100:
            session.finish('骰子过多')
    await session.send('骰子结果为：\n' + '+'.join(str(c) for c in ret) + '=' + str(sum(ret)))