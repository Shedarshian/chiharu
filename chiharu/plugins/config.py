import itertools
import functools
import json
import datetime
import getopt
from os import path
from typing import Awaitable, Generator, Set, Callable, Tuple, Dict, Union
from nonebot import CommandSession, get_bot, permission
from nonebot.natural_language import NLPSession
from nonebot.session import BaseSession
from nonebot.command import _PauseException, _FinishException, SwitchException
import traceback
from collections import UserDict
from .inject import find_help, CommandGroup, Environment, AllGroup, Admin, Constraint, on_command

PATH = "C:\\coolq_data\\"
PATH_IMG = "C:\\coolq\\image"
PATH_REC = "C:\\Users\\Administrator\\Downloads\\CQP-xiaoi\\酷Q Pro\\data\\record"

def rel(rel_path):
    return path.join(PATH, rel_path)
def img(rel_path):
    return path.join(PATH_IMG, rel_path)
def rec(rel_path):
    return path.join(PATH_REC, rel_path)

group_id_dict = {}
tiemu_basic = {}
headers = {}
user_agent = ''
center_gonggao = ''
game_center_help = ''
center_card = ''
card = set()
with open(rel('config_data.py'), encoding='utf-8') as f:
    exec(f.read())
with open(rel('maintain.json'), encoding='utf-8') as f:
    maintain_str = json.load(f)
def maintain_str_save():
    with open(rel('maintain.json'), 'w', encoding='utf-8') as f:
        f.write(json.dumps(maintain_str, ensure_ascii=False,
                           indent=4, separators=(',', ': ')))

class cq:
    @staticmethod
    def text(s: str):
        return {'type': 'text', 'data': {'text': s}}
    @staticmethod
    def at(s: Union[int, str]):
        if type(s) == str:
            return {'type': 'at', 'data': {'qq': s}}
        elif type(s) == int:
            return {'type': 'at', 'data': {'qq': str(s)}}
    @staticmethod
    def img(s: str):
        return {'type': 'image', 'data': {'file': 'file:///' + img(s)}}
    @staticmethod
    def rec(s: str):
        return {'type': 'record', 'data': {'file': 'file:///' + rec(s)}}

def group(n, *iterables):
    def _(n, it):
        try:
            for i in range(n):
                yield next(it)
        except StopIteration:
            pass
    chain = itertools.chain(*iterables)
    it = iter(chain)
    while 1:
        a = tuple(_(n, it))
        if len(a) != n:
            return
        else:
            yield a

class _logger:
    def __init__(self, name):
        self.file = open(rel("log\\%s.log" % name), 'a', encoding='utf-8')
    def __del__(self):
        self.file.close()
    def __lshift__(self, a):
        self.file.write(datetime.datetime.now().isoformat(' '))
        self.file.write(' ')
        self.file.write(str(a))
        self.file.write('\n')
        self.file.flush()

class _logger_meta(type):
    def __getattr__(cls, attr):
        return cls._l[attr]

class logger(metaclass=_logger_meta):
    _l = {}
    @staticmethod
    def open(name):
        logger._l[name] = _logger(name)

from .games.achievement import achievement

@functools.singledispatch
def ErrorHandle(f):
    @functools.wraps(f)
    async def _f(*args, **kwargs):
        if len(args) >= 1 and isinstance(args[0], BaseSession):
            session = args[0]
        elif 'session' in kwargs and isinstance(kwargs['session'], BaseSession):
            session = kwargs['session']
        else:
            session = None
        try:
            return await f(*args, **kwargs)
        except getopt.GetoptError as e:
            if session is not None:
                await session.send('参数错误！' + str(e.args), auto_escape=True)
        except (_PauseException, _FinishException, SwitchException):
            raise
        except Exception:
            if session is not None:
                await args[0].send(traceback.format_exc(), auto_escape=True)
                qq = session.ctx['user_id']
                if achievement.bug.get(qq):
                    await args[0].send(achievement.bug.get_str())
    return _f

@ErrorHandle.register
def _(g: _logger, if_send=True):
    def _g(f: Awaitable):
        @functools.wraps(f)
        async def _f(*args, **kwargs):
            try:
                return await f(*args, **kwargs)
            except (_PauseException, _FinishException, SwitchException):
                raise
            except Exception:
                if len(args) >= 1 and isinstance(args[0], BaseSession):
                    g << f"【ERR】用户{args[0].ctx['user_id']} 使用{f.__name__}时 抛出如下错误：\n{traceback.format_exc()}"
                    if if_send:
                        await args[0].send(traceback.format_exc(), auto_escape=True)
                        qq = args[0].ctx['user_id']
                        if achievement.bug.get(qq):
                            await args[0].send(achievement.bug.get_str())
                elif 'session' in kwargs and isinstance(kwargs['session'], BaseSession):
                    g << f"【ERR】用户{kwargs['session'].ctx['user_id']} 使用{f.__name__}时 抛出如下错误：\n{traceback.format_exc()}"
                    if if_send:
                        await kwargs['session'].send(traceback.format_exc(), auto_escape=True)
                        qq = kwargs['session'].ctx['user_id']
                        if achievement.bug.get(qq):
                            await kwargs['session'].send(achievement.bug.get_str())
                else:
                    g << f"【ERR】调用{f.__name__}时 抛出如下错误：\n{traceback.format_exc()}"
        return _f
    return _g

def maintain(s):
    global maintain_str

    def _(f):
        @functools.wraps(f)
        async def _f(*args, **kwargs):
            if s not in maintain_str or maintain_str[s] == "":
                await f(*args, **kwargs)
            else:
                if len(args) >= 1 and isinstance(args[0], BaseSession):
                    session = args[0]
                elif 'session' in kwargs and isinstance(kwargs['session'], BaseSession):
                    session = kwargs['session']
                else:
                    return
                try:
                    group_id = session.ctx['group_id']
                except KeyError:
                    return
                if group_id in group_id_dict['aaa']:
                    await f(*args, **kwargs)
                else:
                    await session.send(maintain_str[s], auto_escape=True)
        return _f
    return _

class AvBvConverter:
    table='fZodR9XQDSUm21yCkr6zBqiveYah8bt4xsWpHnJE7jL5VG3guMTKNPAwcF'
    tr={}
    s=[11,10,3,8,4,6]
    xor=177451812
    add=8728348608

    @staticmethod
    def dec(x):
        r=0
        for i in range(6):
            r+=AvBvConverter.tr[x[AvBvConverter.s[i]]]*58**i
        return (r-AvBvConverter.add)^AvBvConverter.xor

    @staticmethod
    def enc(x):
        x=(x^AvBvConverter.xor)+AvBvConverter.add
        r=list('BV1  4 1 7  ')
        for i in range(6):
            r[AvBvConverter.s[i]]=AvBvConverter.table[x//58**i%58]
        return ''.join(r)

for i in range(58):
    AvBvConverter.tr[AvBvConverter.table[i]]=i

import sqlite3
userdata_db = sqlite3.connect(rel('users.db'))
userdata_db.row_factory = sqlite3.Row
userdata = userdata_db.cursor()

import asyncio
from nonebot.command import _PauseException, _FinishException
from functools import partial
from typing import Optional, List, Any, NoReturn
from nonebot.typing import Message_T, Filter_T
from nonebot.command.argfilter import ValidateError

class SessionBuffer:
    __slots__ = ('buffer', 'session', 'active', 'send_end', '_future', '_run_future', 'apause', 'aget', 'pause')
    def __init__(self, session: BaseSession):
        self.buffer: str = ''
        self.send_end: str = ''
        self.session: BaseSession = session
        self.active = session.ctx['user_id']
        if isinstance(self.session, NLPSession):
            self._run_future = partial(asyncio.run_coroutine_threadsafe,
                                   loop=self.session.bot.loop)
            async def apause(self, message = None, **kwargs) -> None:
                if message:
                    self._run_future(self.send(message, **kwargs))
                while True:
                    try:
                        self._future = asyncio.get_event_loop().create_future()
                        # timeout_opt = self.expire_timeout
                        timeout = None
                        await asyncio.wait_for(self._future, timeout)
                        break
                    except _PauseException:
                        continue
                    except (_FinishException, asyncio.TimeoutError):
                        raise
            async def aget(self,
                        *,
                        prompt: Optional[Message_T] = None,
                        arg_filters: Optional[List[Filter_T]] = None,
                        **kwargs) -> Any:
                await self.apause(prompt, **kwargs)
                arg = session.current_arg
                for f in arg_filters:
                    try:
                        res = f(arg)
                        if isinstance(res, Awaitable):
                            res = await res
                        arg = res
                    except ValidateError as e:
                        failure_message = e.message
                        if failure_message is None:
                            failure_message = "失败"
                        session.pause(failure_message, **kwargs)
                return arg
            def pause(self, message: Optional[Message_T] = None, **kwargs) -> NoReturn:
                if message:
                    self._run_future(self.send(message, **kwargs))
                self._raise(_PauseException())
            self.pause = pause
            self.apause = apause
            self.aget = aget
    def send(self, s, end='\n'):
        self.buffer += s
        self.buffer += end
    def end(self, s, end='\n'):
        self.send_end += s
        self.send_end += end
    async def flush(self):
        if self.buffer or self.send_end:
            await self.session.send((self.buffer + self.send_end).strip())
            self.buffer = ''
    def __getattr__(self, name: str):
        return getattr(self.session, name)
    def char(self, qq):
        if qq == self.active:
            return '你'
        else:
            return '该玩家'
