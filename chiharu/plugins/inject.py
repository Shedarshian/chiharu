# hack `on_command` and `handle_command` in order to insert custom behaviour
# namely, allow sub-command, and insert `short_des`, `args`, `environment`, `hide` args.
from typing import Union, Iterable, Callable, Optional, Tuple, Awaitable, Type
import warnings, shlex, itertools
import functools
from datetime import timedelta
from more_itertools import only
from nonebot import permission, get_bot
from nonebot.command import CommandHandler_T, Command, CommandSession, CommandManager
from nonebot.typing import CommandName_T, Patterns_T, PermChecker_T
from nonebot.session import BaseSession
from nonebot.permission import check_permission
from nonebot.plugin import Plugin

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
                        await session.send(self.ret)
                    else:
                        await session.send(self.ret(session))
            else:
                await f(session, *args, **kwargs)
        return _f

class MyCommand(Command):
    __slots__ = ('des', 'short_des', 'environment', 'hide', 'hide_in_parent', 'args', 'display_id', 'is_help')
    def __init__(self, *, name: CommandName_T, func: CommandHandler_T,
                 only_to_me: bool, privileged: bool,
                 perm_checker_func: PermChecker_T,
                 expire_timeout: Optional[timedelta],
                 run_timeout: Optional[timedelta],
                 session_class: Optional[Type[CommandSession]],
                 des: str, short_des: str,
                 environment: Optional[Environment],
                 hide: bool, hide_in_parent: bool,
                 args: Optional[tuple], display_id: int):
        super().__init__(name=name, func=func, only_to_me=only_to_me,
                privileged=privileged, perm_checker_func=perm_checker_func,
                expire_timeout=expire_timeout, run_timeout=run_timeout,
                session_class=session_class)
        self.des = des
        self.short_des = short_des
        self.environment = environment
        self.hide = hide
        self.hide_in_parent = hide_in_parent
        self.args = args
        self.display_id = display_id
        self.is_help = False

class CommandGroup:
    command_group_dict = {}
    def __init__(self, name: Union[str, CommandName_T], 
               des: str = "", *,
               short_des: str = "",
               environment: Environment = None,
               hide: bool = False,
               hide_in_parent: bool = False,
               display_parents: Union[None, str, Tuple[str], Iterable[Tuple[str]]] = None,
               display_id: int = 0):
        if isinstance(name, str):
            name = (name,)
        self.short_des = short_des
        self.des = des or short_des
        self.environment = environment
        self.hide = hide
        self.hide_in_parent = hide_in_parent or hide
        self.name = name
        self.display_id = display_id
        self.leaf = {}
        self.help_addition = set()
        self.is_help = False
        self.args = ()
        async def _(session: CommandSession):
            ret = await find_help(name, session)
            if ret:
                await session.send(ret, ensure_private=('.'.join(name) == 'thwiki' and session.ctx['group_id'] in config.group_id_dict['thwiki_send']))
        cmd = MyCommand(name=name, func=_,
                only_to_me=False, privileged=False,
                perm_checker_func=functools.partial(check_permission, permission_required=permission.EVERYBODY),
                expire_timeout=..., run_timeout=..., session_class=None,
                des=des, short_des=short_des, environment=environment,
                hide=hide, hide_in_parent=hide_in_parent or hide, display_id=display_id, args=())
        cmd.is_help = True
        CommandManager.add_command(name, cmd)
        if name in CommandGroup.command_group_dict and isinstance(CommandGroup.command_group_dict[name], dict):
            self.leaf.update(CommandGroup.command_group_dict[name]['leaf'])
            self.help_addition |= CommandGroup.command_group_dict[name]['help_addition']
        CommandGroup.command_group_dict[name] = self
        if len(name) != 0:
            parent_name = name[:-1]
            if parent_name not in CommandGroup.command_group_dict:
                CommandGroup.command_group_dict[parent_name] = {'help_addition': set(), 'leaf': {name[-1]: cmd}}
            elif isinstance(CommandGroup.command_group_dict[parent_name], dict):
                CommandGroup.command_group_dict[parent_name]['leaf'][name[-1]] = cmd
            else:
                CommandGroup.command_group_dict[parent_name].leaf[name[-1]] = cmd
        if display_parents:
            if type(display_parents) is str:
                parents = ((display_parents,),)
            elif type(display_parents[0]) is str:
                parents = (display_parents,)
            else:
                parents = display_parents
            for parent_name in parents:
                if parent_name not in CommandGroup.command_group_dict:
                    CommandGroup.command_group_dict[parent_name] = {'help_addition': {self}, 'leaf': {}}
                elif isinstance(CommandGroup.command_group_dict[parent_name], dict):
                    CommandGroup.command_group_dict[parent_name]['help_addition'].add(self)
                else:
                    CommandGroup.command_group_dict[parent_name].help_addition.add(self)

from . import config
def on_command(name: Union[str, CommandName_T], *,
               aliases: Union[Iterable[str], str] = (),
               permission: int = permission.EVERYBODY,
               patterns: Patterns_T = (),
               only_to_me: bool = True,
               privileged: bool = False,
               shell_like: bool = False,
               expire_timeout: Optional[timedelta] = ...,
               run_timeout: Optional[timedelta] = ...,
               session_class: Optional[Type[CommandSession]] = None,
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
    :param expire_timeout: will override SESSION_EXPIRE_TIMEOUT if provided
    :param run_timeout: will override SESSION_RUN_TIMEOUT if provided
    :param session_class: session class
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
    if session_class is not None and not issubclass(session_class,
                                                        CommandSession):
            raise TypeError(
                'session_class must be a subclass of CommandSession')
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

        perm_checker = functools.partial(check_permission, permission_required=permission)
        cmd = MyCommand(name=cmd_name, func=func, perm_checker_func=perm_checker,
                      only_to_me=only_to_me, privileged=privileged,
                      expire_timeout=expire_timeout, run_timeout=run_timeout, session_class=session_class,
                      des=func.__doc__,
                      short_des=short_des or func.__doc__,
                      environment=environment, hide=hide,
                      hide_in_parent=hide_in_parent or hide,
                      args=args, display_id=display_id)
        if shell_like:
            async def shell_like_args_parser(session):
                session.args['argv'] = shlex.split(session.current_arg)

            cmd.args_parser_func = shell_like_args_parser
        
        nonlocal aliases
        global CommandManager
        CommandManager.add_command(cmd_name, cmd)
        CommandManager.add_aliases(aliases, cmd)
        CommandManager.add_patterns(patterns, cmd)
        parent_name = cmd_name[:-1]
        if parent_name not in CommandGroup.command_group_dict:
            CommandGroup.command_group_dict[parent_name] = {'help_addition': set(), 'leaf': {cmd_name[-1]: cmd}}
        elif isinstance(CommandGroup.command_group_dict[parent_name], dict):
            CommandGroup.command_group_dict[parent_name]['leaf'][cmd_name[-1]] = cmd
        else:
            CommandGroup.command_group_dict[parent_name].leaf[cmd_name[-1]] = cmd
        if display_parents:
            if type(display_parents) is str:
                parents = ((display_parents,),)
            elif type(display_parents[0]) is str:
                parents = (display_parents,)
            else:
                parents = display_parents
            for parent_name in parents:
                if parent_name not in CommandGroup.command_group_dict:
                    CommandGroup.command_group_dict[parent_name] = {'help_addition': {cmd}, 'leaf': {}}
                elif isinstance(CommandGroup.command_group_dict[parent_name], dict):
                    CommandGroup.command_group_dict[parent_name]['help_addition'].add(cmd)
                else:
                    CommandGroup.command_group_dict[parent_name].help_addition.add(cmd)
        
        Plugin.GlobalTemp.commands.add(cmd)
        func.args_parser = cmd.args_parser

        return func
        
    return deco

import nonebot.command
nonebot.command.on_command = on_command
nonebot.on_command = on_command
nonebot.command.CommandGroup = CommandGroup
nonebot.CommandGroup = CommandGroup

from nonebot.log import logger as _nonebot_logger
_nonebot_logger.info('Successfully injected "on_command" and "_find_command"')
del _nonebot_logger

async def find_help(cmd_name: tuple, session: CommandSession):
    if (is_command_group := cmd_name in CommandGroup.command_group_dict):
        cmd_tree = CommandGroup.command_group_dict[cmd_name]
        if isinstance(cmd_tree, dict):
            t = CommandGroup(cmd_name)
            t.leaf.update(cmd_tree['leaf'])
            t.help_addition |= cmd_tree['help_addition']
            cmd_tree = CommandGroup.command_group_dict[cmd_name] = t
    else:
        cmd_tree = CommandManager()._find_command(cmd_name)

    if cmd_tree is None or cmd_tree.hide or (cmd_tree.environment and not await cmd_tree.environment.test(session, no_reply=True)):
        return
    if not is_command_group:
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
