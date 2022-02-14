from more_itertools import only
from nonebot import CommandSession
from .. import config
from ..inject import on_command, CommandGroup

CommandGroup('dyson', short_des="戴森球计划小游戏。", hide_in_parent=True, display_parents='game')

@on_command(("dyson", "check"), only_to_me=False, short_des="查询戴森球相关。")
@config.ErrorHandle
async def dyson_check(session: CommandSession):
    pass


