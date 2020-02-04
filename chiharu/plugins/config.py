import itertools
import functools
import json
import datetime
import getopt
from os import path
from typing import Awaitable, Generator, Set, Callable, Tuple
from nonebot import CommandSession, get_bot, on_command, permission
import traceback
from collections import UserDict

PATH = "C:\\coolq_data\\"
PATH_IMG = "C:\\Users\\Administrator\\Downloads\\CQP-xiaoi\\酷Q Pro\\data\\image"
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
    def at(s: (int, str)):
        if type(s) == str:
            return {'type': 'at', 'data': {'qq': s}}
        elif type(s) == int:
            return {'type': 'at', 'data': {'qq': str(s)}}
    @staticmethod
    def img(s: str):
        return {'type': 'image', 'data': {'file': s}}
    @staticmethod
    def rec(s: str):
        return {'type': 'record', 'data': {'file': s}}

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

class Environment:
    def __init__(self, *args, private=False, ret=""):
        self.group = set()
        self.admin = set()
        self.private = private
        for s in args:
            if type(s) == str:
                self.group |= set(group_id_dict[s])
            elif isinstance(s, Admin):
                self.admin |= set(group_id_dict[s.name])
        self.ret = ret
    async def test(self, session: CommandSession):
        try:
            group_id = session.ctx['group_id']
            if group_id in self.group:
                return True
            elif group_id in self.admin:
                return await permission.check_permission(get_bot(), session.ctx, permission.GROUP_ADMIN)
            else:
                return False
        except KeyError:
            if not self.private:
                if self.ret != "":
                    await session.send(self.ret)
                return False
            else:
                return True

def description(s: str="", args: Tuple[str]=(), environment: Environment=None, hide=False):
    def _(f):
        f.description = s
        f.args = args
        f.environment = environment
        f.hide = hide
        if environment is not None:
            @functools.wraps(f)
            async def _f(session, *args, **kwargs):
                if await environment.test(session):
                    return await f(session, *args, **kwargs)
            return _f
        return f
    return _

from .games.achievement import achievement

@functools.singledispatch
def ErrorHandle(f):
    @functools.wraps(f)
    async def _f(*args, **kwargs):
        if len(args) >= 1 and isinstance(args[0], CommandSession):
            session = args[0]
        elif 'session' in kwargs and isinstance(kwargs['session'], CommandSession):
            session = kwargs['session']
        else:
            session = None
        try:
            return await f(*args, **kwargs)
        except getopt.GetoptError as e:
            if session is not None:
                await session.send('参数错误！' + str(e.args), auto_escape=True)
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
            except Exception:
                if len(args) >= 1 and isinstance(args[0], CommandSession):
                    g << f"【ERR】用户{args[0].ctx['user_id']} 使用{f.__name__}时 抛出如下错误：\n{traceback.format_exc()}"
                    if if_send:
                        await args[0].send(traceback.format_exc(), auto_escape=True)
                        qq = session.ctx['user_id']
                        if achievement.bug.get(qq):
                            await args[0].send(achievement.bug.get_str())
                elif 'session' in kwargs and isinstance(kwargs['session'], CommandSession):
                    g << f"【ERR】用户{kwargs['session'].ctx['user_id']} 使用{f.__name__}时 抛出如下错误：\n{traceback.format_exc()}"
                    if if_send:
                        await kwargs['session'].send(traceback.format_exc(), auto_escape=True)
                        qq = session.ctx['user_id']
                        if achievement.bug.get(qq):
                            await kwargs['session'].send(achievement.bug.get_str())
                else:
                    g << f"【ERR】调用{f.__name__}时 抛出如下错误：\n{traceback.format_exc()}"
        return _f
    return _g

class Admin:
    def __init__(self, s):
        self.name = s

def maintain(s):
    global maintain_str

    def _(f):
        @functools.wraps(f)
        async def _f(*args, **kwargs):
            if s not in maintain_str or maintain_str[s] == "":
                await f(*args, **kwargs)
            else:
                if len(args) >= 1 and isinstance(args[0], CommandSession):
                    session = args[0]
                elif 'session' in kwargs and isinstance(kwargs['session'], CommandSession):
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

class Constraint:
    def __init__(self, id_s: Set[int], can_respond: Callable[..., bool], ret: str = ""):
        self.id_s = id_s
        self._f = can_respond
        self.ret = ret
    def __call__(self, f: Awaitable):
        @functools.wraps(f)
        async def _f(session: CommandSession, *args, **kwargs):
            try:
                group_id = session.ctx['group_id']
            except KeyError:
                await f(session, *args, **kwargs)
                return
            if group_id in self.id_s and not self._f():
                if self.ret != "":
                    await session.send(self.ret, auto_escape=True)
            else:
                await f(session, *args, **kwargs)
        return _f
