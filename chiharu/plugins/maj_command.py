import asyncio
import chiharu.plugins.config as config
import chiharu.plugins.maj as maj
from typing import Type, TypeVar
from nonebot import on_command, CommandSession, get_bot, permission

players = {}
boards_test = {"zj": {}}
boards_typ = {"zj": maj.MajZjBoard}

B = TypeVar('B', bound=maj.MajBoard)
@config.ErrorHandle
async def maj_test(board: B):
    pass

@on_command(('maj', 'test', 'begin'), only_to_me=False)
@config.description(hide=True)
@config.ErrorHandle
async def maj_test_begin(session: CommandSession):
    typ_name = session.current_arg_text
    if typ_name not in boards_test:
        await session.send("未找到麻雀名称")
        return
    try:
        group_id = session.ctx['group_id']
    except KeyError:
        group_id = session.ctx['user_id']
    if group_id in boards_test[typ_name]:
        await session.send("已有对局！")
        return
    board = boards_typ[typ_name]()
    boards_test[typ_name][group_id] = board
    #首家打牌选择
    player, option, dct = next(board)
    index = player.index