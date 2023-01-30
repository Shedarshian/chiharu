from ast import Call
from typing import Callable, Iterable, Tuple, Any, Awaitable, List, Dict, TypedDict
from abc import ABC, abstractmethod
import json
import random
from . import config
from .inject import on_command
from nonebot import CommandSession, get_bot, permission, on_natural_language, NLPSession, IntentCommand
# example usage for GameSameGroup:
# xiangqi = GameSameGroup('xiangqi')
#
# @xiangqi.begin_uncomplete(('play', 'xiangqi', 'begin'), (2, 2))
# async def chess_begin_uncomplete(session: CommandSession, data: Dict[str, Any]):
#     # data: {'players': [qq], 'args': [args], 'anything': anything}
#     await session.send('已为您安排红方，等候黑方')
#
# @xiangqi.begin_complete(('play', 'xiangqi', 'confirm'))
# async def chess_begin_complete(session: CommandSession, data: Dict[str, Any]):
#     # data: {'players': [qq], 'game': GameSameGroup instance, 'args': [args], 'anything': anything}
#     await session.send('已为您安排黑方')
#     #开始游戏
#     #data['board'] = board
#
# @xiangqi.end(('play', 'xiangqi', 'end'))
# async def chess_end(session: CommandSession, data: Dict[str, Any]):
#     await session.send('已删除')
#
# @xiangqi.process(only_short_message=True)
# async def chess_process(session: NLPSession, data: Dict[str, Any], delete_func: Awaitable):
#     pass
#

class ChessError(BaseException):
    def __init__(self, arg):
        self.args = [arg]
class ChessWin(ChessError):
    pass

config.CommandGroup('play', hide=True)

class GameSameGroup:
    # group_id: [{'players': [qq], 'game': GameSameGroup instance, 'anything': anything}]
    center: dict[int, list[dict[str, Any]]] = {}
    def __init__(self, name: str, can_private=False):
        # group_id: {'players': [qq], 'anything': anything}
        self.uncomplete: dict[int, dict[str, Any]] = {}
        self.name = name
        self.can_private = can_private
    def begin_uncomplete(self, command: Iterable[str], player: Tuple[int, int]):
        self.begin_command = command
        self.begin_player = player

        def _(_i: Awaitable) -> Awaitable:
            self.uncomplete_func = _i
            return _i
        return _
    def begin_complete(self, confirm_command: Iterable[str]):
        self.confirm_command = confirm_command

        def _(_f: Awaitable) -> Awaitable:
            self.complete_func = _f

            @on_command(self.begin_command, only_to_me=False, hide=True)
            @config.ErrorHandle
            async def _g(session: CommandSession):
                try:
                    group_id = int(session.ctx['group_id'])
                except KeyError:
                    if self.can_private:
                        group_id = int(session.ctx['user_id'])
                    else:
                        await session.send("请在群里玩")
                        return
                qq = int(session.ctx['user_id'])
                if group_id in self.center:
                    for dct in self.center[group_id]:
                        if self is dct['game']:
                            await session.send('本群已有本游戏进行中')
                            return
                        elif qq in dct['players']:
                            await session.send('您在本群正在游戏中')
                            return
                if group_id in self.uncomplete:
                    if qq in self.uncomplete[group_id]['players']:
                        await session.send('您已参加本游戏匹配，请耐心等待')
                        return
                    self.uncomplete[group_id]['players'].append(qq)
                    self.uncomplete[group_id]['args'].append(
                        session.current_arg_text)
                else:
                    self.uncomplete[group_id] = {'players': [
                        qq], 'args': [session.current_arg_text]}
                # 已达上限，开始游戏
                if len(self.uncomplete[group_id]['players']) == self.begin_player[1]:
                    dct = self.uncomplete.pop(group_id)
                    dct['game'] = self
                    try:
                        await _f(session, dct)  # add data to dct
                    except ChessError:
                        return
                    if group_id in self.center:
                        self.center[group_id].append(dct)
                    else:
                        self.center[group_id] = [dct]
                    bot = get_bot()
                    for group in config.group_id_dict['log']:
                        await bot.send_group_msg(group_id=group, message='%s begin in group %s' % (self.name, group_id))
                    return
                await self.uncomplete_func(session, self.uncomplete[group_id])

            @on_command(confirm_command, only_to_me=False, hide=True)
            @config.ErrorHandle
            async def _h(session: CommandSession):
                try:
                    group_id = int(session.ctx['group_id'])
                except KeyError:
                    if self.can_private:
                        group_id = int(session.ctx['user_id'])
                    else:
                        await session.send("请在群里玩")
                        return
                qq = int(session.ctx['user_id'])
                if group_id not in self.uncomplete:
                    return
                if len(self.uncomplete[group_id]['players']) < self.begin_player[0]:
                    await session.send('匹配人数未达下限，请耐心等待')
                else:
                    dct = self.uncomplete.pop(group_id)
                    dct['game'] = self
                    try:
                        await _f(session, dct)  # add data to dct
                    except ChessError:
                        return
                    if group_id in self.center:
                        self.center[group_id].append(dct)
                    else:
                        self.center[group_id] = [dct]
                    bot = get_bot()
                    for group in config.group_id_dict['log']:
                        await bot.send_group_msg(group_id=group, message='%s begin in group %s' % (self.name, group_id))
            return _f
        return _
    def end(self, end_command: Iterable[str]):
        self.end_command = end_command

        def _(_f: Awaitable) -> Awaitable:
            @on_command(end_command, only_to_me=False, hide=True)
            @config.ErrorHandle
            async def _g(session: CommandSession):
                try:
                    group_id = int(session.ctx['group_id'])
                except KeyError:
                    if self.can_private:
                        group_id = int(session.ctx['user_id'])
                    else:
                        await session.send("请在群里玩")
                        return
                qq = int(session.ctx['user_id'])
                is_admin = await permission.check_permission(get_bot(), session.ctx, permission.GROUP_ADMIN)
                if_in = False
                if group_id in self.center:
                    l = list(
                        filter(lambda x: x['game'] is self, self.center[group_id]))
                    if_in = is_admin or (len(l) != 0 and qq in l[0]['players'])
                if if_in and len(l) != 0:
                    await _f(session, l[0])
                    self.center[group_id].remove(l[0])  # delete 函数？
                    bot = get_bot()
                    for group in config.group_id_dict['log']:
                        await bot.send_group_msg(group_id=group, message='%s end in group %s' % (self.name, group_id))
                elif group_id in self.uncomplete and (is_admin or qq in self.uncomplete[group_id]['players']):
                    await _f(session, self.uncomplete[group_id])
                    self.uncomplete.pop(group_id)
            return _f
        return _
    def process(self, only_short_message: bool = True):
        def _(_f: Awaitable) -> Awaitable:
            @on_natural_language(only_to_me=False, only_short_message=only_short_message)
            async def _g(session: NLPSession):  # 以后可能搁到一起？
                try:
                    group_id = int(session.ctx['group_id'])
                except KeyError:
                    if self.can_private:
                        group_id = int(session.ctx['user_id'])
                    else:
                        return
                qq = int(session.ctx['user_id'])
                if group_id not in self.center:
                    return
                l = list(filter(lambda x: x['game']
                                is self, self.center[group_id]))
                if len(l) == 0 or qq not in l[0]['players']:
                    return

                async def _h():
                    self.center[group_id].remove(l[0])
                    bot = get_bot()
                    for group in config.group_id_dict['log']:
                        await bot.send_group_msg(group_id=group, message='%s end in group %s' % (self.name, group_id))
                return await _f(session, l[0], _h)
            return _g
        return _
    def open_data(self, qq):
        try:
            with open(config.rel(f'games\\user_data\\{qq}.json'), encoding='utf-8') as f:
                data = json.load(f)
                if self.name not in data:
                    return {}
                return data[self.name]
        except FileNotFoundError:
            return {}
    def save_data(self, qq, data_given):
        try:
            with open(config.rel(f'games\\user_data\\{qq}.json'), encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            data = {}
        data[self.name] = data_given
        with open(config.rel(f'games\\user_data\\{qq}.json'), 'w', encoding='utf-8') as f:
            f.write(json.dumps(data, ensure_ascii=False,
                               indent=4, separators=(',', ': ')))
    @classmethod
    async def get_name(cls, session: CommandSession):
        import aiocqhttp
        qq = session.ctx['user_id']
        group = session.ctx['group_id']
        try:
            c = await get_bot().get_group_member_info(group_id=group, user_id=qq)
            if c['card'] == '':
                name = c['nickname']
            else:
                name = c['card']
        except aiocqhttp.exceptions.ActionFailed:
            name = str(qq)
        return name

# example usage for GamePrivate:
# maj = GamePrivate('maj')
#
# @maj.begin_uncomplete(('play', 'maj', 'begin'), (4, 4))
# async def chess_begin_uncomplete(session: CommandSession, data: Dict[str, Any]):
#     # data: {'players': [qq], 'public': bool, 'type': type_str, 'game': GamePrivate instance, 'group': group, 'anything': anything}
#     # args: -play.maj.begin 'type_str public/private+password' or '友人房id+password(optional)'
#     await session.send('已为您参与匹配')

class TRoomPrivate(TypedDict, total=False):
    players: list[int]
    public: bool
    id: int
    type: str
    game: 'GamePrivate'
    password: str | None

class GamePrivate:
    def __init__(self, name: str, allow_group_live: bool = True):
        # room_id: {'players': [qq], 'public': bool, 'id': room_id, 'type': type_str, 'game': GamePrivate instance, 'group': group, 'anything': anything}
        self.center: dict[int, TRoomPrivate] = {}
        self.uncomplete: dict[int, TRoomPrivate] = {}  # room_id: dct
        self.players_status: dict[int, tuple[bool, TRoomPrivate]] = {}  # qq: [bool: Complete, ptr to dct]
        self.allow_group_live = allow_group_live
        self.name = name
        self.types = {'': (0, 32767)}
        self.begin_command: tuple[str,...] = ()
        self.confirm_command: tuple[str,...] = ()
        self.quit_command: tuple[str,...] = ()
        self.uncomplete_func: Callable[[CommandSession, TRoomPrivate], Awaitable] = None
        self.complete_func: Callable[[CommandSession, TRoomPrivate], Awaitable] = None
    def set_types(self, types: Dict[str, Tuple[int, int]]):
        self.types = types
    def begin_uncomplete(self, command: tuple[str,...], player: Tuple[int, int] = (0, 32767)):
        self.begin_command = command
        if '' in self.types:
            self.types[''] = player

        def _(_i: Callable[[CommandSession, TRoomPrivate], Awaitable]) \
                -> Callable[[CommandSession, TRoomPrivate], Awaitable]:
            self.uncomplete_func = _i
            return _i
        return _
    def begin_complete(self, confirm_command: tuple[str,...]):
        self.confirm_command = confirm_command

        def _(_f: Callable[[CommandSession, TRoomPrivate], Awaitable]) \
                -> Callable[[CommandSession, TRoomPrivate], Awaitable]:
            self.complete_func = _f

            @on_command(self.begin_command, only_to_me=False, hide=True)
            @config.ErrorHandle
            async def _g(session: CommandSession):
                qq = int(session.ctx['user_id'])
                s = session.current_arg_text.strip()
                n = s.split(' ')
                room_id = None
                password = None
                # args: -play.maj.begin 'type_str public/private+password' or '友人房id+password(optional)'
                try:
                    if len(n) == 0:
                        if '' in self.types:
                            public = True
                            typ = ''
                        else:
                            raise FileNotFoundError
                    if len(n) == 1:
                        if s in {'public', 'private'} and '' in self.types:
                            public = s == 'public'
                            typ = ''
                        elif s in self.types:
                            public = True
                            typ = s
                        elif s.isdigit():
                            room_id = int(s)
                            password = None
                        else:
                            raise FileNotFoundError
                    elif len(n) == 2:
                        if n[0] == 'priavte' and '' in self.types:
                            public = False
                            password = n[1]
                            typ = ''
                        elif n[0] in self.types and n[1] in {'public', 'private'}:
                            public = n[1] == 'public'
                            typ = n[0]
                        elif n[0].isdigit():
                            room_id = int(s)
                            password = n[1]
                        else:
                            raise FileNotFoundError
                    elif len(n) == 3:
                        if n[0] in self.types and n[1] == 'private':
                            public = False
                            typ = n[0]
                            password = n[2]
                    else:
                        raise FileNotFoundError
                except FileNotFoundError:
                    await session.send('未发现此分类，支持分类：\n' + '，'.join(self.types))
                    return
                if not public and password is None:
                    await session.send('请在private空格后输入房间密码')
                elif qq in self.players_status:
                    await session.send('不能同时进行两个同一游戏')
                elif password is not None and not password.encode('utf-8').isalnum():
                    await session.send('密码只能包含字母与数字！')
                elif room_id is not None:
                    # 加入房间
                    room = self.uncomplete.get(room_id)
                    if room is None:
                        if room_id in self.center:
                            await session.send('此房间对战已开始')
                        else:
                            await session.send('未发现此房间')
                    elif not room['public'] and password is None:
                        await session.send('此房间为private房间，请输入密码')
                    elif not room['public'] and password != room['password']:
                        await session.send('密码错误！')
                    elif len(room['players']) == self.types[room['type']][1]:
                        await session.send('房间已满！')
                    else:
                        room['players'].append(qq)
                        self.players_status[qq] = (False, room)
                        full = len(room["players"]) == self.types[room['type']][1]
                        msg = f'玩家{qq}已加入房间{room_id}，现有{len(room["players"])}人' + (
                            '，已满' if full else '')
                        await self.send(room, msg)
                    await self.uncomplete_func(session, room)
                else:
                    prefix = 0
                    while 1:
                        r = [i for i in range(
                            prefix, prefix + 1000) if i not in self.center and i not in self.uncomplete]
                        if len(r) == 0:
                            prefix += 1000
                        else:
                            break
                    room_id = random.choice(r)
                    room = self.uncomplete[room_id] = {'players': [
                        qq], 'public': public, 'type': typ, 'game': self, 'id': room_id, 'password': None}
                    if not public and password is not None:
                        room['password'] = password
                    self.players_status[qq] = (False, room)
                    await session.send(f'已创建{"公开" if public else "非公开"}房间 {room_id}')
                    await self.uncomplete_func(session, room)

            @on_command(self.confirm_command, only_to_me=False, hide=True)
            @config.ErrorHandle
            async def _h(session: CommandSession):
                qq = int(session.ctx['user_id'])
                if qq not in self.players_status:
                    return
                begin, room = self.players_status[qq]
                if begin:
                    await session.send("房间对战已开始")
                elif len(room['players']) < self.types[room['type']][0]:
                    await session.send('匹配人数未达下限，请耐心等待')
                else:
                    room_id = room["id"]
                    dct = self.uncomplete.pop(room_id)
                    await _f(session, dct)  # add data to dct
                    self.center[room_id] = dct
                    bot = get_bot()
                    for group in config.group_id_dict['log']:
                        await bot.send_group_msg(group_id=group, message='%s begin in roomid %i' % (self.name, room_id))

            return _f
        return _
    def quit(self, quit_command: tuple[str,...]):
        self.quit_command = quit_command

        def _(_f: Awaitable) -> Awaitable:
            @on_command(quit_command, only_to_me=False, hide=True)
            @config.ErrorHandle
            async def _g(session: CommandSession):
                qq = int(session.ctx['user_id'])
                if qq not in self.players_status:
                    return
                begin, room = self.players_status[qq]
                if begin:
                    await _f(session, room)
                    self.end_room(room)
                    await self.send(room, f"玩家{qq}已中止此游戏。")
                elif len(room['players']) == 1:
                    await _f(session, room)
                    self.end_room(room)
                    await session.send("已退出房间。房间已关闭。")
                else:
                    room['players'].pop(qq)
                    self.players_status.pop(qq)
                    await self.send(room, f"玩家{qq}已退出此房间，此房间剩余：{'，'.join(f'玩家{q}' for q in room['players'])}")
            return _f
        return _
    def process(self, only_short_message: bool = True):
        def _(_f: Callable[[NLPSession, TRoomPrivate, Callable[[], Awaitable]], Awaitable]) \
                -> Callable[[NLPSession, TRoomPrivate, Callable[[], Awaitable]], Awaitable]:
            @on_natural_language(only_to_me=False, only_short_message=only_short_message)
            async def _g(session: NLPSession):  # 以后可能搁到一起？
                qq = int(session.ctx['user_id'])
                if qq not in self.players_status:
                    return
                begin, room = self.players_status[qq]
                if not begin:
                    return

                async def _h():
                    self.end_room(room)
                    bot = get_bot()
                    for group in config.group_id_dict['log']:
                        await bot.send_group_msg(group_id=group, message='%s end in room %i' % (self.name, room['id']))
                return await _f(session, room, _h)
            return _f
        return _
    def end_room(self, room: TRoomPrivate):
        for qq in room['players']:
            self.players_status.pop(qq)
        room_id = room['id']
        if room_id in self.uncomplete:
            self.uncomplete.pop(room_id)
        elif room_id in self.center:
            self.center.pop(room_id)
    async def send(self, room: TRoomPrivate, msg: str):
        for qqq in room['players']:
            await get_bot().send_private_msg(user_id=qqq, message=msg)
    async def send_private(self, player: int, msg: str):
        await get_bot().send_private_msg(user_id=player, message=msg)