from nonebot.adapters.discord import on_slash_command, InteractionCreateEvent, CommandOption
from nonebot.adapters.discord.api import SubCommandOption, StringOption
from nonebot.matcher import Matcher
from .achievement import _all
from .. import config

# @on_command('game', only_to_me=False, short_des="\U0001F6AA七海千春游戏大厅\U0001F6AA")
# @config.ErrorHandle
# async def game_center(session: CommandSession):
#     """欢迎使用-game 指令访问七海千春游戏大厅~"""
#     if session.current_arg_text == '':
#         await session.send(config.game_center_help)
#     elif session.current_arg_text == 'card':
#         await session.send(config.center_card)
#     else:
#         await session.send('game not found')

matcher = on_slash_command(name="play",
    description="开始游戏",
    options=[
        SubCommandOption(
            name='check',
            description='查看成就信息。',
            options=[
                StringOption(
                    name='name',
                    description='成就名称',
                    required=True
                )
            ]
        ),
        SubCommandOption(
            name='list',
            description='列出已获得成就。'
        )
    ])

@matcher.handle()
async def achievement_check(event: InteractionCreateEvent, name: CommandOption[str]):
    """查看成就信息。"""
    user_id = event.member.user.id
    for key, val in _all.items():
        if name == val.val['name'] and ('hide' not in val.val or val.check(user_id)):
            await matcher.send(val.get_des(user_id))
    else:
        await matcher.send('未发现此成就。')

@matcher.handle()
async def achievement_list(event: InteractionCreateEvent):
    """列出已获得成就。"""
    user_id = event.member.user.id
    await matcher.send('成就列表：\n- ' + '\n- '.join(val.get_brief(user_id) for key, val in sorted(_all.items(), key=lambda x: x[1].val['id'])))