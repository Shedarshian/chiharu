from typing import Dict, Any, Callable, Awaitable
from .carcassonne import Connectable, Dir, TraderCounter, open_pack
from .carcassonne import Board, Tile, Segment, Object, Feature, Token, Player
from ..inject import CommandGroup, on_command
from .. import config, game
from nonebot import CommandSession, NLPSession

cacason = game.GameSameGroup('cacason', can_private=True)
config.CommandGroup(('play', 'cacason'), hide=True)
config.CommandGroup('cacason', des='', short_des='卡卡颂。', hide_in_parent=True, display_parents='game')

@cacason.begin_uncomplete(('play', 'cacason', 'begin'), (2, 6))
async def ccs_begin_uncomplete(session: CommandSession, data: Dict[str, Any]):
    # data: {'players': [qq], 'args': [args], 'anything': anything}
    name = await game.GameSameGroup.get_name(session)
    if 'names' in data:
        data['names'].append(name)
    else:
        data['names'] = [name]
    await session.send(f'玩家{name}已参与匹配，人数足够可使用-play.cacason.confirm开始比赛。')

@cacason.begin_complete(('play', 'cacason', 'confirm'))
async def ccs_begin_complete(session: CommandSession, data: Dict[str, Any]):
    # data: {'players': [qq], 'game': GameSameGroup instance, 'args': [args], 'anything': anything}
    qq = session.ctx['user_id']
    name = await game.GameSameGroup.get_name(session)
    if qq not in data['players']:
        if 'names' in data:
            data['names'].append(name)
        else:
            data['names'] = [name]
        await session.send(f'玩家{name}已参与匹配，游戏开始')
    else:
        await session.send('游戏开始')
    #开始游戏
    board = data['board'] = Board(open_pack()["packs"][0:1], len(data['players']))
    await session.send([board.saveImg()])
    await session.send(f'玩家{data["names"][board.current_player_id]}开始行动。')

@cacason.end(('play', 'cacason', 'end'))
async def ccs_end(session: CommandSession, data: dict[str, Any]):
    await session.send('已删除')

@cacason.process(only_short_message=True)
@config.ErrorHandle
async def sp2_process(session: NLPSession, data: dict[str, Any], delete_func: Callable[[], Awaitable]):
    command = session.msg_text.strip()
    user_id: int = data['players'].index(session.ctx['user_id'])
    board: Board = data['board']
    if board.current_player_id != user_id:
        return
