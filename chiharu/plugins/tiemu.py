import json
import re
import hashlib
import chiharu.plugins.config as config
from nonebot import on_command, CommandSession, on_natural_language, scheduler, NLPSession, IntentCommand, get_bot, permission

with open(config.rel('tiemu.json'), encoding='utf-8') as f:
    tiemu_g = json.load(f)

async def save():
    global tiemu_g
    with open(config.rel('tiemu.json'), 'w', encoding='utf-8') as f:
        f.write(json.dumps(tiemu_g, ensure_ascii=False, indent=4, separators=(',', ': ')))

@on_command(('ic', 'activate'), only_to_me=False, permission=permission.GROUP_ADMIN)
@config.ErrorHandle
async def activate(session: CommandSession):
    global tiemu_g
    group_id = session.ctx['group_id']
    tiemu = tiemu_g[str(group_id)]
    bot = get_bot()
    if group_id not in config.group_id_dict['tiemu']:
        return
    qq = str(session.get('qq'))
    if qq == "False":
        await session.send('没有at人')
        return
    if qq not in tiemu: # 0: 普通 1: 银幕 2: 铁木大会员
        tiemu[qq] = {"type": 0, "basic": config.tiemu_basic[group_id], 'count': 0}
    d = tiemu[qq]
    time = d['basic'] * [1, 1, 2][d['type']] * (2 ** int(tiemu['tiemu'] / 3))
    if time > 2592000:
        time = 2592000
    await bot.set_group_ban(group_id=session.ctx['group_id'], user_id=qq, duration=time)
    tiemu['tiemu'] += 1
    tiemu[qq]['count'] += 1
    if tiemu[qq]['count'] >= 10 and tiemu[qq]['type'] == 0:
        await session.send([config.cq.text('恭喜'), config.cq.at(qq), config.cq.text('已成为尊贵的银幕会员。')])
        tiemu[qq]['type'] = 1
    await save()

@on_command(('ic', 'deactivate'), only_to_me=False, permission=permission.GROUP_ADMIN)
@config.ErrorHandle
async def deactivate(session: CommandSession):
    global tiemu_g
    group_id = session.ctx['group_id']
    tiemu = tiemu_g[str(group_id)]
    bot = get_bot()
    if group_id not in config.group_id_dict['tiemu']:
        return
    qq = str(session.get('qq'))
    if qq == "False":
        await session.send('没有at人')
        return
    await bot.set_group_ban(group_id=session.ctx['group_id'], user_id=qq, duration=0)

@deactivate.args_parser
@activate.args_parser
async def _(session: CommandSession):
    match = re.search('qq=(\\d+)', str(session.current_arg))
    if match:
        session.args['qq'] = match.group(1)
    else:
        session.args['qq'] = False

@on_command(('ic', 'change'), only_to_me=False, aliases=('银幕尊享',))
@config.ErrorHandle
async def change(session: CommandSession):
    global tiemu_g
    group_id = session.ctx['group_id']
    tiemu = tiemu_g[str(group_id)]
    time = int(session.current_arg_text)
    if time < 30:
        time = 30
    qq = str(session.ctx['user_id'])
    if qq not in tiemu or tiemu[qq]['type'] != 1:
        await session.send('对不起，您尚未成为银幕会员，无法享受银幕尊享')
        return
    tiemu[qq]['basic'] = time * 60
    await save()
    await session.send([config.cq.text('尊敬的银幕会员'), config.cq.at(qq), config.cq.text('，您现在的银幕尊享时间为%i分钟。' % time)])

@scheduler.scheduled_job('cron', hour='06')
async def tiemu_lengjing():
    global tiemu_g
    bot = get_bot()
    for group_id in tiemu_g:
        if tiemu_g[group_id]['tiemu'] != 0:
            tiemu_g[group_id]['tiemu'] = 0
        try:
            await bot.send_group_msg(group_id=group_id, message='铁幕冷静了下来')
        except:
            pass
    await save()
