from nonebot.adapters.discord.commands import CommandOption, on_slash_command
from nonebot.adapters.discord.api import *

matcher = on_slash_command(name="echo",
    description="复读",
    options=[StringOption(
        name="string",
        description="复读内容",
        required=True,
    )])

@matcher.handle()
async def echo(string: CommandOption[str]):
    await matcher.send_response(string)
