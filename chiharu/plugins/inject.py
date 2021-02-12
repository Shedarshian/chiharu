# hack `on_command` and `handle_command` in order to insert custom behaviour
# namely, allow sub-command, and insert `short_des`, `args`, `environment`, `hide` args.
from typing import Union, Iterable, Callable, Optional, Tuple, Awaitable
import warnings, shlex, itertools
import functools
from nonebot import permission
from nonebot.command import CommandHandler_T, Command, CommandFunc
from nonebot.typing import CommandName_T
from nonebot.session import BaseSession

class Admin:
    def __init__(self, s):
        self.name = s

class AllGroup(set):
    def __contains__(self, item):
        return True
    def __or__(self, other):
        o = AllGroup(self)
        for t in other:
            o.add(t)
        return o

class Environment:
    def __init__(self, *args, private=False, ret="", group=None, admin=None, constraint=None):
        from .config import group_id_dict
        self.group = group or set()
        self.admin = admin or set()
        self.constraint = constraint or dict()
        self.private = private
        for s in args:
            if s == 'all':
                self.group = AllGroup()
            elif isinstance(s, str):
                self.group |= set(group_id_dict[s])
            elif isinstance(s, Admin):
                self.admin |= set(group_id_dict[s.name])
            elif isinstance(s, Constraint):
                for group_id in s.group:
                    self.constraint[group_id] = s
        self.ret = ret
    def __or__(self, other):
        if self.private != other.private:
            raise TypeError
        return Environment(private=self.private, group=self.group | other.group, admin=self.admin | other.admin, ret=self.ret, constraint={**self.constraint, **other.constraint})
    async def test(self, session: BaseSession, no_reply: bool=False):
        try:
            group_id = session.ctx['group_id']
            if group_id in self.block:
                return False
            elif group_id in self.constraint:
                ret = self.constraint[group_id]._f(session)
                if not ret and self.constraint[group_id].ret and not no_reply:
                    if isinstance(self.constraint[group_id].ret, str):
                        await session.send(self.constraint[group_id].ret)
                    else:
                        await session.send(self.constraint[group_id].ret(session))
                return ret
            elif group_id in self.group:
                return True
            elif group_id in self.admin:
                return await permission.check_permission(get_bot(), session.ctx, permission.GROUP_ADMIN)
            else:
                return False
        except KeyError:
            if not self.private:
                if self.ret != "" and not no_reply:
                    if isinstance(self.ret, str):
                        await session.send(self.ret)
                    else:
                        await session.send(self.ret(session))
                return False
            else:
                return True
# register a 'Environment.all' object in 'config_data.py'
# and add a 'block' class property in 'config_data.py'

class Constraint:
    def __init__(self, *args, can_respond: Callable[..., bool], ret: Union[str, Callable[..., str]] = ""):
        from .config import group_id_dict
        self.group = set()
        for arg in args:
            if type(arg) is str:
                self.group |= set(group_id_dict[arg])
            elif type(arg) is set:
                self.group |= arg
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
            if group_id in self.group and not self._f(session):
                if self.ret != "":
                    if isinstance(self.ret, str):
                        await session.send(self.ret, auto_escape=True)
                    else:
                        await session.send(self.ret(session), auto_escape=True)
            else:
                await f(session, *args, **kwargs)
        return _f

class _CommandGroup:
    def __init__(self, des="", short_des="", args=(), environment=None, hide=False, command=None, name=(), hide_in_parent=False, display_id: int = 0):
        self.short_des = short_des
        self.des = des
        self.environment = environment
        self.hide = hide
        self.hide_in_parent = hide_in_parent or hide
        self.args = args if type(args) is not str else (args,)
        self.name = name
        self.display_id = display_id
        self.leaf = {}
        self.help_addition = set()
        self.command = command
        self.is_help = False
    def get(self, item):
        if item not in self.leaf:
            self.leaf[item] = _CommandGroup(name=self.name + (item,))
        return self.leaf[item]
    def __contains__(self, item):
        return item in self.leaf

_registry = _CommandGroup()

def CommandGroup(name: Union[str, CommandName_T], 
               des: str = "", *,
               short_des: str = "",
               environment: Environment = None,
               hide: bool = False,
               hide_in_parent: bool = False,
               display_parents: Union[None, str, Tuple[str], Iterable[Tuple[str]]] = None,
               display_id: int = 0):
    cmd_name = (name,) if isinstance(name, str) else name
    current_parent = _registry
    for parent_key in cmd_name:
        current_parent = current_parent.get(parent_key)
    current_parent.des = des or short_des
    current_parent.short_des = short_des
    current_parent.environment = environment
    current_parent.hide = hide
    current_parent.hide_in_parent = hide_in_parent or hide
    current_parent.display_id = display_id
    if display_parents:
        if type(display_parents) is str:
            parents = ((display_parents,),)
        elif type(display_parents[0]) is str:
            parents = (display_parents,)
        else:
            parents = display_parents
        for parent_name in parents:
            c = _registry
            for parent_key in parent_name:
                c = c.get(parent_key)
            c.help_addition.add(current_parent)

from . import config
def on_command(name: Union[str, CommandName_T], *,
               aliases: Union[Iterable[str], str] = (),
               permission: int = permission.EVERYBODY,
               only_to_me: bool = True,
               privileged: bool = False,
               shell_like: bool = False,
               short_des: str = "",
               args: Union[str, Tuple[str]] = (),
               environment: Environment = None,
               hide: bool = False,
               hide_in_parent: bool = False,
               display_parents: Union[None, str, Tuple[str], Iterable[Tuple[str]]] = None,
               display_id: int = 0) -> Callable:
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
    :param hide_in_parent: whether hide in parents' help contents, will be 'or'ed with the :param hide:.
    :param display_parents: can be displayed in other command's help content
    :param display_id: order in parents' help contents
    """
    if type(args) is str:
        args = (args,)
    def deco(func_original: CommandHandler_T) -> CommandHandler_T:
        if not isinstance(name, (str, tuple)):
            raise TypeError('the name of a command must be a str or tuple')
        if not name:
            raise ValueError('the name of a command must not be empty')

        cmd_name = (name,) if isinstance(name, str) else name
        
        nonlocal environment
        if environment is None:
            environment = Environment.all
        @functools.wraps(func_original)
        async def _f(session, *args, **kwargs):
            if await environment.test(session):
                return await func_original(session, *args, **kwargs)
        func = _f

        cmd = Command(name=cmd_name, func=func, permission=permission,
                      only_to_me=only_to_me, privileged=privileged)
        if shell_like:
            async def shell_like_args_parser(session):
                session.args['argv'] = shlex.split(session.current_arg)

            cmd.args_parser_func = shell_like_args_parser
        
        current_parent = _registry
        for parent_key in cmd_name:
            current_parent = current_parent.get(parent_key)
        if current_parent.command is not None:
            warnings.warn(f'There is already a command named {cmd_name}')
            return func
        current_parent.command = cmd
        current_parent.des = func.__doc__
        current_parent.short_des = short_des or func.__doc__
        current_parent.environment = environment
        current_parent.hide = hide
        current_parent.hide_in_parent = hide_in_parent or hide
        current_parent.args = args
        current_parent.display_id = display_id
        if display_parents:
            if type(display_parents) is str:
                parents = ((display_parents,),)
            elif type(display_parents[0]) is str:
                parents = (display_parents,)
            else:
                parents = display_parents
            for parent_name in parents:
                c = _registry
                for parent_key in parent_name:
                    c = c.get(parent_key)
                c.help_addition.add(current_parent)

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
            ret = await find_help(cmd_name, session)
            if ret:
                await session.send(ret, ensure_private=('.'.join(cmd_name) == 'thwiki' and session.ctx['group_id'] in config.group_id_dict['thwiki_send']))
            # await call_command(get_bot(), session.ctx, ('help',), current_arg='.'.join(cmd_name))
        cmd_tree.command = Command(name=cmd_name, func=_, permission=permission.EVERYBODY,
                      only_to_me=False, privileged=False)
        cmd_tree.is_help = True
    return cmd_tree.command

import nonebot.command
nonebot.command.on_command = on_command
nonebot.command._find_command = _find_command
nonebot.on_command = on_command

from nonebot.log import logger as _nonebot_logger
_nonebot_logger.info('Successfully injected "on_command" and "_find_command"')
del _nonebot_logger

async def find_help(cmd_name: tuple, session: CommandSession):
    cmd_tree = _registry
    for part in cmd_name:
        if part not in cmd_tree:
            return
        cmd_tree = cmd_tree.leaf[part]

    if cmd_tree.hide or (cmd_tree.environment and not await cmd_tree.environment.test(session, no_reply=True)):
        return
    if cmd_tree.command and not cmd_tree.is_help:
        # command
        return f"-{'.'.join(cmd_name)}{''.join(' ' + x for x in cmd_tree.args)}\n{cmd_tree.des}"
    else:
        # command group
        async def _(cmd_tree):
            for command, if_hide_in_parent in itertools.chain(zip(cmd_tree.leaf.values(), itertools.repeat(True)), zip(cmd_tree.help_addition, itertools.repeat(False))):
                if if_hide_in_parent and command.hide_in_parent or (command.environment and not await command.environment.test(session, no_reply=True)):
                    continue
                yield (command.display_id, f"-{'.'.join(command.name)}{''.join(' ' + x for x in command.args)}：{command.short_des}")
        return (cmd_tree.des + '\n' + '\n'.join(s2 for id, s2 in sorted([s async for s in _(cmd_tree)], key=lambda x: x[0]))).strip()
