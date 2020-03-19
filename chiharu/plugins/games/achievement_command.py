from .achievement import _all
from .. import config
from nonebot import on_command, CommandSession, get_bot, permission

@on_command('game', only_to_me=False, short_des="\U0001F6AA七海千春游戏大厅\U0001F6AA")
@config.ErrorHandle
async def game_center(session: CommandSession):
    """欢迎使用-game 指令访问七海千春游戏大厅~"""
    if session.current_arg_text == '':
        await session.send(config.game_center_help)
    elif session.current_arg_text == 'card':
        await session.send(config.center_card)
    else:
        await session.send('game not found')

config.CommandGroup('achievement', short_des='成就系统。')

@on_command(('achievement', 'check'), only_to_me=False, args='[name]')
@config.ErrorHandle
async def check(session: CommandSession):
    """查看成就信息。"""
    qq = session.ctx['user_id']
    for key, val in _all.items():
        if session.current_arg_text == val.val['name'] and ('hide' not in val.val or val.check(qq)):
            session.finish(val.get_des(qq))
    else:
        await session.send('未发现此成就。')

@on_command(('achievement', 'list'), only_to_me=False)
@config.ErrorHandle
async def check(session: CommandSession):
    """列出已获得成就。"""
    qq = session.ctx['user_id']
    await session.send('成就列表：\n\t' + '\n\t'.join(val.get_brief(qq) for key, val in sorted(_all.items(), key=lambda x: x[1].val['id'])))