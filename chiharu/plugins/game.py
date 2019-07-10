from typing import Callable, Iterable, Tuple, Any, Awaitable, List, Dict
import chiharu.plugins.config as config
import chiharu.plugins.games.card as card
from nonebot import on_command, CommandSession, get_bot, permission, on_natural_language, NLPSession, IntentCommand

class ChessError(BaseException):
    def __init__(self, arg):
        self.args = [arg]

class ChessWin(ChessError):
    pass

class GameSameGroup:
    center = {} # group_id: [{'players': [qq], 'game': GameSameGroup instance, 'anything': anything}]
    def __init__(self, name: str):
        self.uncomplete = {} # group_id: {'players': [qq], 'anything': anything}
        self.name = name
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
            @on_command(self.begin_command, only_to_me=False)
            @config.ErrorHandle
            async def _g(session: CommandSession):
                try:
                    group_id = int(session.ctx['group_id'])
                except KeyError:
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
                    if len(self.uncomplete[group_id]['players']) == self.begin_player[1]: # 已达上限，开始游戏
                        dct = {'players': self.uncomplete.pop(group_id)['players'], 'game': self}
                        await _f(session, dct) # add data to dct
                        if group_id in self.center:
                            self.center[group_id].append(dct)
                        else:
                            self.center[group_id] = [dct]
                        bot = get_bot()
                        for group in config.group_id_dict['log']:
                            await bot.send_group_msg(group_id=group, message='%s begin in group %s' % (self.name, group_id))
                        return
                else:
                    self.uncomplete[group_id] = {'players': [qq]}
                await self.uncomplete_func(session, self.uncomplete[group_id])
            @on_command(confirm_command, only_to_me=False)
            @config.ErrorHandle
            async def _h(session: CommandSession):
                try:
                    group_id = int(session.ctx['group_id'])
                except KeyError:
                    await session.send("请在群里玩")
                    return
                qq = int(session.ctx['user_id'])
                if group_id not in self.uncomplete:
                    return
                if len(self.uncomplete[group_id]['players']) < self.begin_player[0]:
                    await session.send('匹配人数未达下限，请耐心等待')
                else:
                    dct = {'players': self.uncomplete.pop(group_id)['players'], 'game': self}
                    await _f(session, dct) # add data to dct
                    if group_id in self.center:
                        self.center[group_id].append(dct)
                    else:
                        self.center[group_id] = [dct]
                    bot = get_bot()
                    for group in config.group_id_dict['log']:
                        await bot.send_group_msg(group_id=group, message='%s begin in group %s' % (self.name, group_id))
        return _
    def end(self, end_command: Iterable[str]):
        def _(_f: Awaitable) -> Awaitable:
            @on_command(end_command, only_to_me=False)
            @config.ErrorHandle
            async def _g(session: CommandSession):
                try:
                    group_id = int(session.ctx['group_id'])
                except KeyError:
                    await session.send("请在群里玩")
                    return
                qq = int(session.ctx['user_id'])
                is_admin = await permission.check_permission(get_bot(), session.ctx, permission.GROUP_ADMIN)
                if_in = False
                if group_id in self.center:
                    l = list(filter(lambda x: x['game'] is self, self.center[group_id]))
                    if_in = is_admin or (len(l) != 0 and qq in l[0]['players'])
                if if_in and len(l) != 0:
                    await _f(session, l[0])
                    self.center[group_id].remove(l[0]) # delete 函数？
                    bot = get_bot()
                    for group in config.group_id_dict['log']:
                        await bot.send_group_msg(group_id=group, message='%s end in group %s' % (self.name, group_id))
                elif group_id in self.uncomplete and (is_admin or qq in self.uncomplete[group_id]['players']):
                    await _f(session, self.uncomplete[group_id])
                    self.uncomplete.pop(group_id)
            return _f
        return _
    def process(self, only_short_message: bool=True):
        def _(_f: Awaitable) -> Awaitable:
            @on_natural_language(only_to_me=False, only_short_message=only_short_message)
            async def _g(session: NLPSession): # 以后可能搁到一起？
                try:
                    group_id = int(session.ctx['group_id'])
                except KeyError:
                    return
                qq = int(session.ctx['user_id'])
                if group_id not in self.center:
                    return
                l = list(filter(lambda x: x['game'] is self, self.center[group_id]))
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

@on_command('game', only_to_me=False)
@config.ErrorHandle
async def game_center(session: CommandSession):
    if session.current_arg_text == '':
        await session.send(config.game_center_help)
    elif session.current_arg_text == 'card':
        await session.send(card.center_card)

# xiangqi = GameSameGroup('xiangqi')

# @xiangqi.begin_uncomplete(('play', 'xiangqi', 'begin'), (2, 2))
# async def chess_begin_uncomplete(session: CommandSession, data: Dict[str, Any]):
#     # data: {'players': [qq], 'anything': anything}
#     await session.send('已为您安排红方，等候黑方')

# @xiangqi.begin_complete(('play', 'xiangqi', 'confirm'))
# async def chess_begin_complete(session: CommandSession, data: Dict[str, Any]):
#     # data: {'players': [qq], 'game': GameSameGroup instance, 'anything': anything}
#     await session.send('已为您安排黑方')
#     #开始游戏
#     #data['board'] = board

# @xiangqi.end(('play', 'xiangqi', 'end'))
# async def chess_end(session: CommandSession, data: Dict[str, Any]):
#     await session.send('已删除')

# @xiangqi.process(only_short_message=True)
# async def chess_process(session: NLPSession, data: Dict[str, Any], delete_func: Callable[[], None]):
#     pass