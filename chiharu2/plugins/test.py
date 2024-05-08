from typing import Optional
import asyncio, sys, contextlib
from io import StringIO
from nonebot import on_command
from nonebot.permission import SUPERUSER
from nonebot.params import CommandArg
from nonebot.adapters.discord import Bot, MessageEvent, Event, InteractionCreateEvent
from nonebot.adapters.discord.api import *
from nonebot.adapters.discord.commands import CommandOption, on_slash_command

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
    await matcher.send_response(f"channel id: {event.channel_id}\n user id: {event.member.user.id}") # type: ignore

matcher2 = on_slash_command(
    name="python",
    description="测试用指令",
    options=[SubCommandOption(
        name="exec",
        description="执行",
        options=[StringOption(
            name="command",
            description="指令"
        )]
    ), SubCommandOption(
        name="await",
        description="异步执行",
        options=[StringOption(
            name="command",
            description="指令"
        )]
    )]
)

@contextlib.contextmanager
def stdoutIO(stdout=None):
    old = sys.stdout
    if stdout is None:
        stdout = StringIO()
    sys.stdout = stdout
    yield stdout
    sys.stdout = old

@matcher2.handle_sub_command("exec")
async def python_exec(command: CommandOption[str], event: InteractionCreateEvent):
    import nonebot
    config = nonebot.get_driver().config
    if event.member and event.member.user and event.member.user.id in config.superusers:
        await matcher2.send_deferred_response()
        with stdoutIO() as s:
            exec(command)
        await matcher2.edit_response(s.getvalue()[:-1])

@matcher2.handle_sub_command("await")
async def PythonAwait(command: CommandOption[str], event: InteractionCreateEvent):
    import nonebot
    config = nonebot.get_driver().config
    if event.member and event.member.user and event.member.user.id in config.superusers:
        await matcher2.send_deferred_response()
        with stdoutIO() as s:
            exec('async def main():\n  ' + '\n  '.join(command.split('\n')))
            await locals()['main']()
        await matcher2.edit_response(s.getvalue()[:-1])

# matcher = on_slash_command(
#     name="permission",
#     description="权限管理",
#     options=[
#         SubCommandOption(
#             name="add",
#             description="添加",
#             options=[
#                 StringOption(
#                     name="plugin",
#                     description="插件名",
#                     required=True,
#                 ),
#                 IntegerOption(
#                     name="priority",
#                     description="优先级",
#                     required=False,
#                 ),
#             ],
#         ),
#         SubCommandOption(
#             name="remove",
#             description="移除",
#             options=[
#                 StringOption(name="plugin", description="插件名", required=True),
#                 NumberOption(name="time", description="时长", required=False),
#             ],
#         ),
#         SubCommandOption(
#             name="ban",
#             description="禁用",
#             options=[
#                 UserOption(name="user", description="用户", required=False),
#             ],
#         ),
#     ],
# )

# @matcher.handle_sub_command("add")
# async def handle_user_add(
#     plugin: CommandOption[str], priority: CommandOption[Optional[int]]
# ):
#     await matcher.send_deferred_response()
#     await asyncio.sleep(2)
#     await matcher.edit_response(f"你添加了插件 {plugin}，优先级 {priority}")
#     await asyncio.sleep(2)
#     fm = await matcher.send_followup_msg(
#         f"你添加了插件 {plugin}，优先级 {priority} (新消息)"
#     )
#     await asyncio.sleep(2)
#     await matcher.edit_followup_msg(
#         fm.id, f"你添加了插件 {plugin}，优先级 {priority} (新消息修改后)"
#     )