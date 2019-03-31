import asyncio
import chiharu.plugins.config as config
import chiharu.plugins.maj as maj
from typing import Type
from nonebot import on_command, CommandSession, get_bot, permission

players = {}

@on_command(('maj', 'test', 'begin'), only_to_me=False)
@config.ErrorHandle
async def maj_test_begin(session: CommandSession):
    pass