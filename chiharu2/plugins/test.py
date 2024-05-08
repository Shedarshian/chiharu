from typing import Optional
import asyncio
from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.adapters.discord import Bot, MessageEvent, MessageSegment, Message, Adapter
from nonebot.adapters.discord.api import *
from nonebot.adapters.discord.commands import CommandOption, on_slash_command

matcher = on_slash_command(
    name="test",
    description="测试用指令"
)

@matcher.handle()
async def test(event: MessageEvent):
    await matcher.finish(f"channel id: {event.channel_id}\n user id: {event.user_id}")

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