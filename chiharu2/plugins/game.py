from typing import Callable, Iterable, Tuple, Any, Awaitable, List, Dict, TypedDict
import json
import random
from . import config
from nonebot import on_command

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