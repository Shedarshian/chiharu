import itertools
import functools
import json
import datetime
import getopt
from os import path
from typing import Awaitable, Generator, Set, Callable, Tuple, Dict
from nonebot import get_bot, permission
from nonebot.session import BaseSession
from nonebot.command import _PauseException, _FinishException, SwitchException
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

class Constraint:
    def __init__(self, id_s: Set[int], can_respond: Callable[..., bool], ret: str = ""):
        self.id_s = id_s
        self._f = can_respond
        self.ret = ret
    def __call__(self, f: Awaitable):
        @functools.wraps(f)
        async def _f(session: BaseSession, *args, **kwargs):
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

class Environment:
    def __init__(self, *args, private=False, ret="", group=None, admin=None):
        self.group = group if group is not None else set()
        self.admin = admin if admin is not None else set()
        self.private = private
        for s in args:
            if type(s) == str:
                self.group |= set(group_id_dict[s])
            elif isinstance(s, Admin):
                self.admin |= set(group_id_dict[s.name])
        self.ret = ret
    def __or__(self, other):
        if self.private != other.private:
            raise TypeError
        return Environment(private=self.private, group=self.group | other.group, admin=self.admin | other.admin, ret=self.ret)
    async def test(self, session: BaseSession):
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
        f.has_des = True
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

# hack `on_command` and `handle_command` in order to insert custom behaviour
# namely, allow sub-command, and insert `short_des`, `args`, `environment`, `hide` args.
from typing import Union, Iterable, Callable, Optional
import warnings
from nonebot import permission as perm
from nonebot.command import CommandHandler_T, Command, CommandFunc
from nonebot.typing import CommandName_T

class _CommandGroup:
    def __init__(self, des="", short_des="", args=(), environment=None, hide=False, command=None):
        self.short_des = short_des
        self.environment = environment
        self.hide = hide
        self.args = args
        self.leaf = {}
        self.command = command
    def get(self, item):
        if item not in self.leaf:
            self.leaf[item] = _CommandGroup()
        return self.leaf[item]
    def __contains__(self, item):
        return item in self.leaf

_registry = _CommandGroup()

def CommandGroup(name: Union[str, CommandName_T], 
               des: str = "", *,
               short_des: str = "",
               environment: Environment = None,
               hide: bool = False):
    cmd_name = (name,) if isinstance(name, str) else name
    current_parent = _registry
    for parent_key in cmd_name[:-1]:
        current_parent = current_parent.get(parent_key)
    if cmd_name[-1] in current_parent:
        c = current_parent.get(cmd_name[-1])
        c.des = des
        c.short_des = short_des
        c.environment = environment
        c.hide = hide
    else:
        current_parent.leaf[cmd_name[-1]] = _CommandGroup(des=des, short_des=short_des, environment=environment, hide=hide)

def on_command(name: Union[str, CommandName_T], *,
               aliases: Union[Iterable[str], str] = (),
               permission: int = perm.EVERYBODY,
               only_to_me: bool = True,
               privileged: bool = False,
               shell_like: bool = False,
               short_des: str = "",
               args: Tuple[str] = (),
               environment: Environment = None,
               hide: bool = False) -> Callable:
    """
    Decorator to register a function as a command.
    :param name: command name (e.g. 'echo' or ('random', 'number'))
    :param aliases: aliases of command name, for convenient access
    :param permission: permission required by the command
    :param only_to_me: only handle messages to me
    :param privileged: can be run even when there is already a session
    :param shell_like: use shell-like syntax to split arguments
    :param short_des: inline help text
    :param args: args for this command
    :param environment: environment for this command
    :param hide: whether hide in helps
    """
    def deco(func: CommandHandler_T) -> CommandHandler_T:
        if not isinstance(name, (str, tuple)):
            raise TypeError('the name of a command must be a str or tuple')
        if not name:
            raise ValueError('the name of a command must not be empty')

        cmd_name = (name,) if isinstance(name, str) else name

        cmd = Command(name=cmd_name, func=func, permission=permission,
                      only_to_me=only_to_me, privileged=privileged)
        if shell_like:
            async def shell_like_args_parser(session):
                session.args['argv'] = shlex.split(session.current_arg)

            cmd.args_parser_func = shell_like_args_parser
        
        current_parent = _registry
        for parent_key in cmd_name[:-1]:
            current_parent = current_parent.get(parent_key)
        if cmd_name[-1] in current_parent:
            c = current_parent.get(cmd_name[-1])
            if c.command is not None:
                warnings.warn(f'There is already a command named {cmd_name}')
                return func
            warnings.warn(f'There is a command group named {cmd_name}, parameters ignored')
            c.command = cmd
        else:
            current_parent.leaf[cmd_name[-1]] = _CommandGroup(des=func.__doc__, short_des=short_des, environment=environment, hide=hide, args=args, command=cmd)

        from nonebot.command import _aliases
        nonlocal aliases
        if isinstance(aliases, str):
            aliases = (aliases,)
        for alias in aliases:
            _aliases[alias] = cmd_name

        return CommandFunc(cmd, func)
        
    return deco

from nonebot import CommandSession, get_bot
from nonebot.command import call_command
def _find_command(name: Union[str, CommandName_T]) -> Optional[Command]:
    cmd_name = (name,) if isinstance(name, str) else name
    if not cmd_name:
        return None

    cmd_tree = _registry
    for part in cmd_name:
        if part not in cmd_tree:
            return None
        cmd_tree = cmd_tree.leaf[part]

    if cmd_tree.command is None:
        async def _(session: CommandSession):
            await call_command(get_bot(), session.ctx, ('help',), current_arg='.'.join(cmd_name))
        cmd_tree.command = Command(name=cmd_name, func=_, permission=perm.EVERYBODY,
                      only_to_me=False, privileged=False)
    return cmd_tree.command

import nonebot.command
nonebot.command.on_command = on_command
nonebot.command._find_command = _find_command
nonebot.on_command = on_command

from nonebot.log import logger as _nonebot_logger
_nonebot_logger.info('Successfully injected "on_command" and "_find_command"')