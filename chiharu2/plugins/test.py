from typing import Optional
import asyncio, sys, contextlib, subprocess
from io import StringIO
from .helper.helper import rel
from nonebot import on_command
from nonebot.permission import SUPERUSER
from nonebot.params import CommandArg
from nonebot.message import event_postprocessor
from nonebot.adapters.discord import Bot, MessageEvent, Event, InteractionCreateEvent, Message, ReadyEvent
from nonebot.adapters.discord.api import *
from nonebot.adapters.discord.commands import CommandOption, on_slash_command
from nonebot.matcher import Matcher

matcher = on_slash_command(
    name="test",
    description="测试用指令",
    options=[StringOption(
        name="option",
        description="测试"
    )]
)

@matcher.handle()
async def test(option: CommandOption[str], bot: Bot, event: InteractionCreateEvent):
    if option == "check":
        await matcher.send_response(f"channel id: {event.channel_id}\n user id: {event.member.user.id}") # type: ignore
    else:
        await matcher.send_response("unknown option!")

matcher_exec = on_command(('python', 'exec'))
matcher_await = on_command(('python', 'await'))
matcher_pull = on_command(('python', 'pull'))
matcher_shutdown = on_command(('python', 'shutdown'))

# matcher2 = on_slash_command(
#     name="python",
#     description="测试用指令",
#     options=[SubCommandOption(
#         name="exec",
#         description="执行",
#         options=[StringOption(
#             name="command",
#             description="指令"
#         )]
#     ), SubCommandOption(
#         name="await",
#         description="异步执行",
#         options=[StringOption(
#             name="command",
#             description="指令"
#         )]
#     )]
# )

@contextlib.contextmanager
def stdoutIO(stdout=None):
    old = sys.stdout
    if stdout is None:
        stdout = StringIO()
    sys.stdout = stdout
    try:
        yield stdout
    finally:
        sys.stdout = old

@matcher_exec.handle()
async def python_exec(bot: Bot, event: MessageEvent, matcher: Matcher, msg: Message = CommandArg()):
    import nonebot
    config = nonebot.get_driver().config
    if str(event.user_id) in config.superusers:
        with stdoutIO() as s:
            exec(msg.extract_plain_text())
        await matcher_exec.send(s.getvalue()[:-1])

@matcher_await.handle()
async def PythonAwait(bot: Bot, event: MessageEvent, matcher: Matcher, msg: Message = CommandArg()):
    import nonebot
    config = nonebot.get_driver().config
    if str(event.user_id) in config.superusers:
        with stdoutIO() as s:
            exec('async def main(bot, event):\n  ' + '\n  '.join(msg.extract_plain_text().split('\n')))
            await locals()['main'](bot, event)
        await matcher_await.send(s.getvalue()[:-1])

@matcher_pull.handle()
async def PythonPull():
    batcmd = "git pull"
    result = subprocess.check_output(batcmd, shell=True)
    await matcher_pull.send(result.decode('utf-8'))

@matcher_shutdown.handle()
async def PythonRestart(event: MessageEvent):
    import nonebot
    config = nonebot.get_driver().config
    if str(event.user_id) in config.superusers:
        with open(rel("restart.txt"), 'w') as f:
            f.write(str(event.channel_id))
        import sys
        sys.exit(2)

@event_postprocessor
async def Ready(bot: Bot, event: ReadyEvent):
    import os
    if os.path.exists(rel("restart.txt")):
        with open(rel("restart.txt"), 'r') as f:
            channel_id = int(f.readline().strip())
        os.remove(rel("restart.txt"))
        await bot.send_to(channel_id, "restarted!")
