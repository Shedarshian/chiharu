import itertools
import functools
import json
import datetime
from os import path
from typing import Awaitable
from nonebot import CommandSession, get_bot, on_command
import traceback
from collections import UserDict

PATH = "C:\\coolq_data\\"
PATH_IMG = "C:\\Users\\Administrator\\Downloads\\CQP-xiaoi\\酷Q Pro\\data\\image"

def rel(rel_path):
    return path.join(PATH, rel_path)
def img(rel_path):
    return path.join(PATH_IMG, rel_path)

with open(rel('config_data.py'), encoding='utf-8') as f:
    exec(f.read())
with open(rel('maintain.json'), encoding='utf-8') as f:
    maintain_str = json.load(f)
def maintain_str_save():
    with open(rel('maintain.json'), 'w', encoding='utf-8') as f:
        f.write(json.dumps(maintain_str, ensure_ascii=False, indent=4, separators=(',', ': ')))

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
        self.file = open(rel("log\\%s.log" % name), 'a')
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

@functools.singledispatch
def ErrorHandle(f):
    @functools.wraps(f)
    async def _f(session: CommandSession, *args, **kwargs):
        try:
            return await f(session, *args, **kwargs)
        except Exception:
            await session.send(traceback.format_exc(), auto_escape=True)
    return _f

@ErrorHandle.register
def _(g: _logger, if_send=True):
    def _g(f: Awaitable):
        @functools.wraps(f)
        async def _f(session: CommandSession, *args, **kwargs):
            try:
                return await f(session, *args, **kwargs)
            except Exception:
                g << f"【ERR】用户{session.ctx['user_id']} 使用{f.__name__}时 抛出如下错误：\n{traceback.format_exc()}"
                if if_send:
                    await session.send(traceback.format_exc(), auto_escape=True)
        return _f
    return _g
        

def maintain(s):
    global maintain_str
    def _(f):
        @functools.wraps(f)
        async def _f(*args, **kwargs):
            if s not in maintain_str or maintain_str[s] == "":
                return await f(*args, **kwargs)
            else:
                if len(args) >= 1 and isinstance(args[0], CommandSession):
                    await args[0].send(maintain_str[s])
                elif 'session' in kwargs and isinstance(kwargs['session'], CommandSession):
                    await kwargs['session'].send(maintain_str[s])
        return _f
    return _
