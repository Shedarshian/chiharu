from typing import Callable, Iterable, Tuple, Any, Awaitable, List, Dict, TypedDict
from dataclasses import dataclass
import json
import random
from . import config
from nonebot import on_command, CommandGroup

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

play = CommandGroup('play')

@dataclass
class Group:
    pass
@dataclass
class QQGroup(Group):
    group_id: int
    def __str__(self):
        return f"QQ{self.group_id}"
@dataclass
class DiscordGroup(Group):
    group_id: int
    channel_id: int
    def __str__(self):
        return f"DC{self.group_id}_{self.channel_id}"

class GameSameGroup:
    # group: [{'players': [qq], 'game': GameSameGroup instance, 'anything': anything}]
    def __init__(self, name: str, can_private=False):
        # group: {'players': [qq], 'anything': anything}
        self.uncomplete: dict[Group, dict[str, Any]] = {}
        self.name = name
        self.can_private = can_private
        self.center: dict[Group, list[dict[str, Any]]] = {}
        self.uncomplete_func: Callable[..., Awaitable] | None = None
        self.complete_func: Callable[..., Awaitable] | None = None
    def begin_uncomplete(self, command: tuple[str], player: Tuple[int, int]):
        self.begin_command = command
        self.begin_player = player

        def _(_i: Callable[..., Awaitable]):
            self.uncomplete_func = _i
            return _i
        return _
    def begin_complete(self, confirm_command: tuple[str]):
        self.confirm_command = confirm_command

        def _(_f: Awaitable) -> Awaitable:
            self.complete_func = _f

            @on_command(self.begin_command, only_to_me=False, hide=True)
            @config.ErrorHandle
            async def _g():
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

