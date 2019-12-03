from datetime import datetime, timedelta, date, timezone
import re
import requests
import json
import asyncio
import functools
import more_itertools
import random
from copy import copy
from urllib import parse
from nonebot import on_command, CommandSession, get_bot, permission, scheduler, on_notice, NoticeSession
from nonebot.command import call_command
import aiocqhttp
import chiharu.plugins.config as config
import chiharu.plugins.help as Help

version = "2.2.1"

TRAIL_TIME = 36 * 60
async def change(title=None, description=None):
    cookie_jar = requests.cookies.RequestsCookieJar()
    with open(config.rel('cookie.txt')) as f:
        value = f.readline().strip()
    cookie_jar.set(name="SESSDATA", value=value)
    cookie_jar.set(name="bili_jct", value=config.csrf_thb)
    value = {'room_id': 14055253, 'title': title, 'description': description, 'csrf': config.csrf_thb, 'csrf_token': config.csrf_thb}
    length = len(parse.urlencode(value))
    print('length: ' + str(length))
    headers = copy(config.headers)
    headers['Content-Length'] = str(length)
    loop = asyncio.get_event_loop()
    url = await loop.run_in_executor(None, functools.partial(requests.post,
        'https://api.live.bilibili.com/room/v1/Room/update',
        data=value, cookies=cookie_jar, headers=headers))
    return url.text

async def th_open(is_open=True, area=235):
    cookie_jar = requests.cookies.RequestsCookieJar()
    with open(config.rel('cookie.txt')) as f:
        value = f.readline().strip()
    cookie_jar.set(name="SESSDATA", value=value)
    cookie_jar.set(name="bili_jct", value=config.csrf_thb)
    value = {'room_id': 14055253, 'platform': 'pc', 'csrf': config.csrf_thb, 'csrf_token': config.csrf_thb}
    if is_open:
        value['area_v2'] = area
    length = len(parse.urlencode(value))
    headers = copy(config.headers)
    headers['Content-Length'] = str(length)
    loop = asyncio.get_event_loop()
    ret = await loop.run_in_executor(None, functools.partial(requests.post,
        'https://api.live.bilibili.com/room/v1/Room/startLive' if is_open
            else 'https://api.live.bilibili.com/room/v1/Room/stopLive',
        data=value, cookies=cookie_jar, headers=headers))
    return ret.text

def format_date(dat: datetime, tz=None):
    today = datetime.now(tz=tz).date()
    if dat.date() == today:
        return '今天{0:%H}:{0:%M}'.format(dat)
    elif dat.date() == today + timedelta(days=1):
        return '明天{0:%H}:{0:%M}'.format(dat)
    elif dat.date() == today + timedelta(days=2):
        return '后天{0:%H}:{0:%M}'.format(dat)
    elif dat.date() == today - timedelta(days=1):
        return '昨天{0:%H}:{0:%M}'.format(dat)
    elif dat.year == today.year:
        return '{0:%m}月{0:%d}日{0:%H}:{0:%M}'.format(dat)
    else:
        return '{0:%Y}年{0:%m}月{0:%d}日{0:%H}:{0:%M}'.format(dat)

class Event:
    def __init__(self, *args):
        if len(args) == 6:
            self.begin, self.end, self.qq, self.card, self.name, self.isFloat = args
            self.id = max(-1, -1, *map(lambda e: e.id, l)) + 1
            node = find_whiteforest(qq=self.qq)
            if node is not None and node['trail'] == 0:
                self.supervise = -1
            else:
                self.supervise = 0 # -1: 有权限，0: 无权限
        elif len(args) == 3:
            id, begin, end, qq, supervise = args[0].split(' ')
            self.id = int(id)
            if end == 'float':
                self.end = False
                self.isFloat = True
                self.begin, self.qq = datetime.fromtimestamp(float(begin)), int(qq)
            else:
                self.isFloat = False
                self.begin, self.end, self.qq = datetime.fromtimestamp(float(begin)), datetime.fromtimestamp(float(end)), int(qq)
            self.supervise = int(supervise)
            self.card = args[1]
            self.name = args[2]
        else:
            raise TypeError()
    def __repr__(self):
        begin = str(self.begin.timestamp())
        if self.isFloat:
            end = 'float'
        else:
            end = str(self.end.timestamp())
        return f'{self.id} {begin} {end} {self.qq} {self.supervise}\n{self.card}\n{self.name}'
    def __str__(self):
        begin = format_date(self.begin)
        if self.isFloat:
            end = '自由'
        else:
            end = format_date(self.end)
        return f'id: {self.id} {begin}-{end} 投稿人: {self.card}\n' + \
            ((('【监视人尚无】\n' if self.supervise == 0 else '监视人已有\n')) if self.supervise >= 0 else '') + \
            f'内容: {self.name}'
    def str_tz(self, tz):
        begin = format_date(datetime.combine(self.begin.date(), self.begin.time(), timezone(timedelta(hours=8))).astimezone(tz).replace(tzinfo=None), tz)
        if self.isFloat:
            end = '自由'
        else:
            end = format_date(datetime.combine(self.end.date(), self.end.time(), timezone(timedelta(hours=8))).astimezone(tz).replace(tzinfo=None), tz)
        return f'id: {self.id} {begin}-{end} 投稿人: {self.card}\n' + \
            ((('【监视人尚无】\n' if self.supervise == 0 else '监视人已有\n')) if self.supervise >= 0 else '') + \
            f'内容: {self.name}'
    def str_url(self):
        begin = format_date(self.begin)
        if self.isFloat:
            end = '自由'
        else:
            end = format_date(self.end)
        return f'{begin}-{end} 投稿人: {self.card}<br />内容: {self.name}'
    def str_with_at(self):
        begin = format_date(self.begin)
        if self.isFloat:
            end = '自由'
        else:
            end = format_date(self.end)
        if self.supervise == 0:
            return [config.cq.at(self.qq), config.cq.text(f'十分抱歉，您id为{self.id}时间为{begin}-{end}内容为{self.name}\n的直播监视者已取消')]
        else:
            return [config.cq.at(self.qq), config.cq.text(f'您id为{self.id}时间为{begin}-{end}内容为{self.name}\n的直播已有人监视')]
    def output_with_at(self):
        if self.supervise != 0:
            return [config.cq.text('开播提醒！\n'), config.cq.at(self.qq), config.cq.text('\n内容: %s' % self.name)]
        else:
            return [config.cq.text('开播提醒！\n'), config.cq.at(self.qq), config.cq.text('\n内容: %s\n十分抱歉，您现在的直播尚无监视员，无法直播qwq' % self.name)]
    def overlap(self, other):
        if self.isFloat and other.isFloat:
            return False
        elif self.isFloat:
            return other.begin < self.begin < other.end
        elif other.isFloat:
            return self.begin < other.begin < self.end
        return self.begin < other.end and other.begin < self.end

def _open():
    def _f():
        with open(config.rel("thwiki.txt"), encoding='utf-8') as f:
            for i, j, k in config.group(3, f):
                yield Event(i.strip(), j.strip(), k.strip())
    return list(_f())
l = _open()

async def _save(t):
    with open(config.rel("thwiki.txt"), 'w', encoding='utf-8') as f:
        f.write('\n'.join(map(repr, t)))

async def change_des_to_list():
    global l
    fut = datetime.now() + timedelta(days=7)
    s = '<h2>THBWiki电视台（大雾）</h2><p>基本上会以直播<strong>东方Project</strong>的游戏为主。日常进行播放的主播不定。</p><h3>*高亮*本直播间欢迎任何人使用，只要直播的内容为东方Project相关<br />具体使用方法，以及粉丝群请戳<strong>807894304</strong>【thbwiki直播不断递纸群】</h3><p>节目单：%s</p>' % \
        '<br />'.join(map(Event.str_url, filter(lambda x: x.begin < fut, l)))
    return await change(description=s)

with open(config.rel("thwiki_blacklist.txt")) as f:
    blacklist = list(map(lambda x: int(x.strip()), f.readlines()))
def _line(s, has_card):
    l = s.split(' ')
    return l.pop(0), l.pop(0), l.pop(0), (' '.join(l) if has_card else None)
with open(config.rel("thwiki_whiteforest.json"), encoding='utf-8') as f:
    whiteforest = json.load(f)
def find_whiteforest(*, id=None, qq=None):
    global whiteforest
    return more_itertools.only([x for x in whiteforest if x['qq'] == qq]) if id is None else more_itertools.only([x for x in whiteforest if x['id'] == id])
def save_whiteforest():
    global whiteforest
    with open(config.rel("thwiki_whiteforest.json"), 'w', encoding='utf-8') as f:
        f.write(json.dumps(whiteforest, ensure_ascii=False, indent=4, separators=(',', ': ')))
async def get_card(qq):
    for group in config.group_id_dict['thwiki_card']:
        try:
            c = await get_bot().get_group_member_info(group_id=group, user_id=qq)
            if c['card'] == '':
                return c['nickname']
            else:
                return c['card']
        except aiocqhttp.exceptions.ActionFailed:
            pass
def find_or_new(qq):
    global whiteforest
    ret = find_whiteforest(qq=qq)
    if ret is None:
        ret = {'id': len(whiteforest), 'qq': qq, 'trail': 1, 'card': None, 'time': 0}
        whiteforest.append(ret)
        save_whiteforest()
    return ret
def deprive(node, if_save=True):
    global whiteforest
    updated = []
    to_do = [node]
    while len(to_do):
        r = to_do.pop(0)
        r.pop('parent')
        for i in r.pop('child'):
            f = find_whiteforest(id=i)
            to_do.append(f)
        r['trail'] = 1
        r['time'] = 0
        updated.append(config.cq.at(r['qq']))
    if if_save:
        save_whiteforest()
    return updated
def add_time(qq, time):
    node = find_or_new(qq)
    if 'time' not in node:
        node['time'] = 0
    node['time'] += int(time)
    b = False
    if node['time'] >= TRAIL_TIME:
        b = node['trail'] != 0
        if node['trail'] != 0 and node['parent'] != -1:
            find_whiteforest(id=node['parent'])['child'].remove(node['id'])
        node['parent'] = -1
        node['trail'] = 0
        # node['child'] = []
    save_whiteforest()
    return b

class ApplyErr(BaseException):
    pass

@on_command(('thwiki', 'apply'), aliases=('申请',), only_to_me=False)
@config.ErrorHandle
@config.maintain('thwiki')
async def apply(session: CommandSession):
    try:
        group_id = session.ctx['group_id']
        if group_id not in config.group_id_dict['thwiki_live']:
            return
    except KeyError:
        await session.send('请在群内使用')
        return
    global l
    begin = session.get('begin')
    end = session.get('end')
    float_end = session.get('float_end')
    qq = session.get('qq')
    card = session.get('card')
    name = session.get('name')
    tz = session.get('tz')
    if qq in blacklist:
        return
    try:
        now = datetime.now()
        if begin == False or (float_end == False and end == False):
            raise ApplyErr('时间格式不正确，请在 -thwiki.apply 开始时间 结束时间 名字\n的时间处使用正则'
            '(\\d+年)?(\\d+月)?(\\d+(日|号))?'
            '(' '(\\d+(时|点))' '(\\d+分)?' '|' '\\d+:\\d+' ')，且保证时间有效'
            '\n开始可用now，结束可用float')
        elif not float_end and begin > end:
            raise ApplyErr('结束需要比开始晚！')
        elif begin < now - timedelta(minutes=1):
            raise ApplyErr('开始需要比现在晚！')
        elif not float_end and begin + timedelta(hours=24) < end:
            raise ApplyErr('请勿一次申请超过24小时的时段')
        elif not float_end and now + timedelta(days=60) < end:
            if end.year >= 2100:
                raise ApplyErr(f'你能活到{end.year}年吗？我在这里等着你哦')
            raise ApplyErr('暂不受理60天以外的申请')
        elif len(name) < 1:
            raise ApplyErr('不能没有名字')
        elif '\n' in name:
            raise ApplyErr('名字不能含有换行符')
        elif len(list(filter(lambda x: x.name == name, l))) != 0:
            raise ApplyErr('已有重名，请换名字')
    except ApplyErr as err:
        await session.send(err.args[0])
        return
    e = Event(begin, end, qq, card, name, float_end)
    for i in l:
        if i.overlap(e):
            await session.send('这个时间段已经有人了\n' + (str(i) if tz is None else f"时区：{tz.tzname(datetime.now())}\n{i.str_tz(tz)}"), auto_escape=True)
            return
    l.append(e)
    l.sort(key=lambda x: x.begin)
    await _save(l)
    check = find_or_new(qq=qq)
    await session.send(f'成功申请，id为{e.id}，您还在试用期，请等待管理员监视，敬请谅解w' if check['trail'] else f'成功申请，id为{e.id}')
    ret = await change_des_to_list()
    if json.loads(ret)['code'] != 0:
        await session.send('更新到直播间失败')
    if check['trail']:
        for group in config.group_id_dict['thwiki_supervise']:
            await get_bot().send_group_msg(group_id=group, message=f'{e}\n等待管理员监视')

@apply.args_parser
@config.ErrorHandle
async def _(session: CommandSession):
    session.args['qq'] = int(session.ctx['user_id'])
    try:
        if session.ctx['sender']['card'] == '':
            session.args['card'] = session.ctx['sender']['nickname']
        else:
            session.args['card'] = session.ctx['sender']['card']
    except KeyError:
        session.args['card'] = session.ctx['sender']['nickname']
    session.args['float_end'] = False
    check = find_or_new(session.ctx['user_id'])
    if 'timezone' in check and check['timezone'] != 8:
        tz = timezone(timedelta(hours=check['timezone']))
    else:
        tz = None
    session.args['tz'] = tz
    now = datetime.now(tz=tz).date()
    def _default(t, t_default):
        if t is None:
            return t_default
        else:
            return int(t)
    i = session.current_arg_text.find(' ')
    time_begin = session.current_arg_text[:i]
    j = session.current_arg_text.find(' ', i + 1)
    if j == -1:
        time_end = session.current_arg_text[i + 1:]
        session.args['name'] = ""
    else:
        time_end = session.current_arg_text[i + 1:j]
        session.args['name'] = session.current_arg_text[j + 1:]
    r = re.compile('(?:' '(?:(\\d+)年)?' '(?:(\\d+)月)?' '(?:(\\d+)(?:日|号))?'
        '(?:' '(?:(\\d+)(?:时|点))' '(?:(\\d+)分)?' '|' '(\\d+):(\\d+)' '))|(now)|(float)')
    m_begin = re.match(r, time_begin)
    m_end = re.match(r, time_end)
    if m_begin is None:
        session.args['begin'] = False
    else:
        year, month, day, hours1, minute1, hours2, minute2, _now, _float = m_begin.groups()
        if _now is not None:
            session.args['begin'] = datetime.now()
        elif _float is not None:
            session.args['begin'] = False
        else:
            hours = hours1 if hours1 is not None else hours2
            minute = minute1 if minute1 is not None else minute2
            year = _default(year, now.year)
            month = _default(month, now.month)
            day = _default(day, now.day)
            hours = int(hours)
            minute = _default(minute, 0)
            try:
                if 24 <= hours <= 30:
                    hours -= 24
                    begin = datetime(year, month, day, hours, minute, tzinfo=tz) + timedelta(days=1)
                else:
                    begin = datetime(year, month, day, hours, minute, tzinfo=tz)
                if tz is not None:
                    session.args['begin'] = begin.astimezone(timezone(timedelta(hours=8))).replace(tzinfo=None)
                else:
                    session.args['begin'] = begin
            except:
                session.args['begin'] = False
    if m_end is None:
        session.args['end'] = False
    else:
        year, month, day, hours1, minute1, hours2, minute2, _now, _float = m_end.groups()
        if _now is not None:
            session.args['end'] = False
        elif _float is not None:
            session.args['end'] = False
            session.args['float_end'] = True
        else:
            hours = hours1 if hours1 is not None else hours2
            minute = minute1 if minute1 is not None else minute2
            year = _default(year, now.year)
            month = _default(month, now.month)
            day = _default(day, now.day)
            hours = int(hours)
            minute = _default(minute, 0)
            try:
                if 24 <= hours <= 30:
                    hours -= 24
                    end = datetime(year, month, day, hours, minute, tzinfo=tz) + timedelta(days=1)
                else:
                    end = datetime(year, month, day, hours, minute, tzinfo=tz)
                if tz is not None:
                    session.args['end'] = end.astimezone(timezone(timedelta(hours=8))).replace(tzinfo=None)
                else:
                    session.args['end'] = end
            except:
                session.args['end'] = False

@on_command(('thwiki', 'cancel'), aliases=('取消',), only_to_me=False)
@config.ErrorHandle
@config.maintain('thwiki')
async def cancel(session: CommandSession):
    global l
    if int(session.ctx['user_id']) in blacklist:
        return
    try:
        group_id = session.ctx['group_id']
        if group_id not in config.group_id_dict['thwiki_live']:
            return
    except KeyError:
        await session.send('请在群内使用')
        return
    l2 = more_itertools.only([x for x in enumerate(l) if x[1].name == session.current_arg_text])
    if l2 is None:
        l2 = more_itertools.only([x for x in enumerate(l) if str(x[1].id) == session.current_arg_text.strip()])
        if l2 is None:
            await session.send('未找到')
            return
    i = l2[0]
    if int(session.ctx['user_id']) == l[i].qq or \
            await permission.check_permission(get_bot(), session.ctx, permission.GROUP_ADMIN):
        now = datetime.now()
        e = l.pop(i)
        await _save(l)
        # print((e.isFloat, e.begin, now, e.end, i, len(l)))
        if e.supervise != 0 and e.begin < now:
            d = ((now - e.begin).total_seconds() - 1) // 60 + 1
            if add_time(e.qq, d):
                await session.send('您已成功通过试用期转正！')
        await _save(l)
        await session.send('成功删除')
        ret = await change_des_to_list()
        if json.loads(ret)['code'] != 0:
            await session.send('更新到直播间失败')
    else:
        await session.send('非管理员不可删除别人的')

@on_command(('thwiki', 'list'), only_to_me=False)
@config.ErrorHandle
@config.maintain('thwiki')
async def thlist(session: CommandSession):
    if_all = session.current_arg_text == 'all'
    global l
    if len(l) == 0:
        await session.send('列表为空')
    else:
        qq = session.ctx['user_id']
        node = find_or_new(qq=qq)
        if 'timezone' not in node or node['timezone'] == 8:
            if if_all:
                await session.send('\n'.join([str(x) for x in l]), auto_escape=True)
            else:
                end = datetime.now() + timedelta(days=5)
                l_show = [str(x) for x in l if x.begin < end]
                await session.send('\n'.join(l_show) + (f'\n{len(l) - len(l_show)}条五天以后的预约已被折叠' if len(l) != len(l_show) else ""), auto_escape=True)
        else:
            tz = timezone(timedelta(hours=node['timezone']))
            if if_all:
                await session.send(f"您的时区为{tz.tzname(datetime.now())}\n" + '\n'.join([x.str_tz(tz) for x in l]), auto_escape=True)
            else:
                end = datetime.now() + timedelta(days=5)
                l_show = [str(x) for x in l if x.begin < end]
                await session.send(f"您的时区为{tz.tzname(datetime.now())}\n" + '\n'.join([x.str_tz(tz) for x in l if x.begin < end]) + (f'\n{len(l) - len(l_show)}条五天以后的预约已被折叠' if len(l) != len(l_show) else ""), auto_escape=True)

@on_command(('thwiki', 'listall'), only_to_me=False)
@config.ErrorHandle
@config.maintain('thwiki')
async def thlistall(session: CommandSession):
    await call_command(get_bot(), session.ctx, ('thwiki', 'list'), current_arg="all")

@on_command(('thwiki', 'term'), only_to_me=False)
@config.ErrorHandle
@config.maintain('thwiki')
async def term(session: CommandSession):
    try:
        group_id = session.ctx['group_id']
        if group_id not in config.group_id_dict['thwiki_live']:
            return
    except KeyError:
        await session.send('请在群内使用')
        return
    global l
    if int(session.ctx['user_id']) in blacklist:
        return
    now = datetime.now()
    if len(l) == 0:
        await session.send('现在未在播')
    else:
        if now < l[0].begin:
            await session.send('现在未在播')
        elif l[0].qq != session.ctx['user_id']:
            await session.send('现在不是你在播')
        else:
            e = l.pop(0)
            s = ""
            if e.supervise != 0:
                d = ((now - e.begin).total_seconds() - 1) // 60 + 1
                if add_time(e.qq, d):
                    await session.send('您已成功通过试用期转正！')
                s = f"，已为您累积直播时间{d}分钟"
            await _save(l)
            ret = await th_open(is_open=False)
            if json.loads(ret)['code'] != 0:
                await session.send('成功删除，断流失败' + s)
            else:
                await session.send('成功断流' + s)
            ret = await change_des_to_list()
            if json.loads(ret)['code'] != 0:
                await session.send('更新到直播间失败')

@scheduler.scheduled_job('cron', hour='00')
@config.maintain('thwiki')
async def _():
    global l
    ret = await change_des_to_list()
    if json.loads(ret)['code'] != 0:
        for id in config.group_id_dict['thwiki_send']:
            await get_bot().send_group_msg(group_id=id, message='直播间简介更新失败')
    for r in whiteforest:
        r['card'] = await get_card(r['qq'])
    save_whiteforest()

@scheduler.scheduled_job('cron', second='00')
@config.maintain('thwiki')
async def _():
    global l
    now = datetime.now()
    bot = get_bot()
    for e in l:
        if now - timedelta(seconds=59) < e.begin < now + timedelta(seconds=1):
            for id in config.group_id_dict['thwiki_send']:
                await bot.send_group_msg(group_id=id, message=e.output_with_at())
            ret = await change(title=('【东方】' if '【东方】' not in e.name else '') + e.name)
            if json.loads(ret)['code'] != 0:
                for id in config.group_id_dict['thwiki_send']:
                    await bot.send_group_msg(group_id=id, message='直播间标题修改失败')
            if e.supervise > 0:
                for id in config.group_id_dict['thwiki_supervise']:
                    await bot.send_group_msg(group_id=id, message=[config.cq.text('\n内容: %s\n请监视者就位' % e.name), config.cq.at(e.supervise)])
    for i, e in enumerate(l):
        if e.isFloat and i != len(l) - 1 and l[i + 1].begin < now + timedelta(seconds=1) or not e.isFloat and e.end < now + timedelta(seconds=1):
            l.pop(i)
            d = (((l[i + 1].begin if e.isFloat else e.end) - e.begin).total_seconds() - 1) // 60 + 1
            if e.supervise != 0:
                if add_time(e.qq, d):
                    for id in config.group_id_dict['thwiki_send']:
                        await bot.send_group_msg(group_id=id, message=[config.cq.at(e.qq), config.cq.text('已成功通过试用期转正！')], auto_escape=True)
                await _save(l)
                for id in config.group_id_dict['thwiki_send']:
                    await bot.send_group_msg(group_id=id, message=[config.cq.text("已为"), config.cq.at(e.qq), config.cq.text(f"累积直播时间{d}分钟")], auto_escape=True)
                ret = await change_des_to_list()
                if json.loads(ret)['code'] != 0:
                    for id in config.group_id_dict['thwiki_send']:
                        await bot.send_group_msg(group_id=id, message='直播间简介更新失败')
            break

@on_command(('thwiki', 'check'), only_to_me=False)
@config.ErrorHandle
@config.maintain('thwiki')
async def check(session: CommandSession):
    loop = asyncio.get_event_loop()
    url = await loop.run_in_executor(None, requests.get, 'https://api.live.bilibili.com/room/v1/Room/room_init?id=14055253')
    response = json.loads(url.text)
    if response['data']['live_status'] == 1:
        url2 = await loop.run_in_executor(None, requests.get,
            'https://api.live.bilibili.com/room/v1/Room/get_info?room_id=14055253')
        response = url2.json()
        title = response['data']['title']
        await session.send('少女直播中......\n标题：%s' % title, auto_escape=True)
    else:
        await session.send('没有人直播' + random.choice(('qwq', '♪～(´ε｀　)', '.(*´▽`*).', 'ヾ(Ő∀Ő๑)ﾉ', '(≧ڡ≦*)', '(╯‵□′)╯︵┻━┻', '(╬ﾟдﾟ)▄︻┻┳═一', 'QAQ', '(╥╯^╰╥)', '(´；ω；`)', '(╥﹏╥)', '(-_-;)')))

@on_command(('thwiki', 'get'), only_to_me=False)
@config.ErrorHandle
@config.maintain('thwiki')
async def get(session: CommandSession):
    try:
        group_id = session.ctx['group_id']
        if group_id not in config.group_id_dict['thwiki_live']:
            return
    except KeyError:
        await session.send('请在群内使用')
        return
    #permission check
    now = datetime.now()
    qq = int(session.ctx['user_id'])
    if qq in blacklist:
        return
    async def _():
        if await permission.check_permission(get_bot(), session.ctx, permission.GROUP_ADMIN):
            return True, None
        for i, e in enumerate(l):
            if e.isFloat:
                if i == len(l) - 1:
                    b = True
                else:
                    b = now < l[i + 1].begin + timedelta(minutes=15)
            else:
                b = now < e.end + timedelta(minutes=15)
            if qq == e.qq and b and e.begin - timedelta(minutes=15) < now:
                return (e.supervise != 0), e
        return False, None
    r = await _()
    if not r[0]:
        await session.send('请在您预约的时间段前后十五分钟内申请获取rtmp' if r[1] != 0 else '十分抱歉，您现在的直播尚无监视员，无法直播qwq')
        return
    cookie_jar = requests.cookies.RequestsCookieJar()
    with open(config.rel('cookie.txt')) as f:
        value = f.readline().strip()
        rtmp = f.readline().strip()
        key = f.readline().strip()
    cookie_jar.set(name="SESSDATA", value=value)
    loop = asyncio.get_event_loop()
    url = await loop.run_in_executor(None, functools.partial(requests.get,
        'http://api.live.bilibili.com/live_stream/v1/StreamList/get_stream_by_roomId?room_id=14055253',
        cookies=cookie_jar))
    response = json.loads(url.text)
    if response['code'] != 0:
        await session.send([config.cq.text('无法获取rtmp与key，已将缓存数据发送，如无法推流请联系'),
            config.cq.at('1569603950'), config.cq.text('更新')])
        await session.send('rtmp:\n%s\nkey:\n%s' % (rtmp, key), ensure_private=True, auto_escape=True)
    else:
        rtmp = response['data']['rtmp']
        strout = 'rtmp:\n%s\nkey:\n%s' % (rtmp['addr'], rtmp['code'])
        await session.send(strout, ensure_private=True, auto_escape=True)
        with open(config.rel('cookie.txt'), 'w') as f:
            f.write(value + '\n')
            f.write(rtmp['addr'] + '\n')
            f.write(rtmp['code'] + '\n')
    url2 = await loop.run_in_executor(None, requests.get, 'https://api.live.bilibili.com/room/v1/Room/room_init?id=14055253')
    if url2.json()['data']['live_status'] != 1:
        try:
            area = {'': 235, '单机·其他': 235, '单机·其他单机': 235, '户外': 123, '娱乐·户外': 123, '演奏': 143, '才艺': 143, '娱乐·才艺': 143, '手游': 98, '手游·其他': 98, '手游·其他手游': 98, '网游': 107, '网游·其他': 107, '网游·其他网游': 107, '音乐台': 34, '娱乐·音乐台': 34, '虚拟主播': 199, 'vtb': 199, '娱乐·虚拟主播': 199, '绘画': 94, '同人绘画': 94, '临摹绘画': 95, '绘画·同人绘画': 94, '绘画·临摹绘画': 95}[session.current_arg_text]
        except:
            await session.send('不支持分区：%s，自动转至单机·其他' % session.current_arg_text, auto_escape=True)
            area = 235
        if r[1] is not None:
            t = r[1].name
            if '东方' not in t:
                t = '【东方】' + t
            ret = await change(title=t)
            if json.loads(ret)['code'] != 0:
                await session.send(f'直播间标题修改失败', auto_escape=True)
        ret = await th_open(area=area)
        if json.loads(ret)['code'] == 0:
            await session.send('检测到直播间未开启，现已开启，分区：%s' % \
                {235: '单机·其他', 123: '娱乐·户外', 143: '娱乐·才艺', 34: '娱乐·音乐台', 199: '娱乐·虚拟主播', 98: '手游·其他', 107: '网游·其他', 94: '绘画：同人绘画', 95: '绘画·临摹绘画'} \
                [area])
        else:
            await session.send('检测到直播间未开启，开启直播间失败')

@on_command(('thwiki', 'grant'), only_to_me=False)
@config.ErrorHandle
@config.maintain('thwiki')
async def thwiki_grant(session: CommandSession):
    try:
        group_id = session.ctx['group_id']
        if group_id not in config.group_id_dict['thwiki_live']:
            return
    except KeyError:
        await session.send('请在群内使用')
        return
    sqq = session.ctx['user_id']
    node = find_whiteforest(qq=sqq)
    if node is None or node['trail'] == 1:
        await session.send("您还处在试用期，无法推荐")
        return
    def _(s):
        begin = 0
        while 1:
            match = re.search('qq=(\\d+)', s[begin:])
            if not match:
                return
            begin += match.span()[1]
            yield int(match.group(1))
    qqs = list(_(str(session.current_arg)))
    if len(qqs) == 0:
        await session.send('没有@人')
        return
    s = session.current_arg[session.current_arg.rfind(' ') + 1:]
    if s == 'false' or s == 'False' or s == 'f' or s == 'F':
        not_update = []
        updated = []
        updated_qq = []
        for qq in qqs:
            node_c = find_whiteforest(qq=qq)
            if node_c is None:
                not_update.append(config.cq.at(qq))
            elif node_c['trail'] == 1 or node_c['parent'] != node['id']:
                not_update.append(config.cq.at(node_c['qq']))
            else:
                node['child'].remove(node_c['id'])
                updated += deprive(node_c, False)
                updated_qq.append(node_c['qq'])
        save_whiteforest()
        for e in l:
            if e.qq in updated_qq and e.supervise == -1:
                e.supervise = 0
        await session.send(updated + ([config.cq.text(" 已成功退回推荐！试用期直播时间从0开始计算。")] if len(updated) > 0 else []) + ([config.cq.text("\n")] if len(updated) > 0 and len(not_update) > 0 else []) + ((not_update + [config.cq.text(" 不是您推荐的用户，删除失败")]) if len(not_update) > 0 else []), auto_escape=True)
    else:
        not_update = []
        updated = []
        updated_qq = []
        to_card = []
        for qq in qqs:
            ret_c = find_or_new(qq)
            if not ret_c['trail']:
                if ret_c['card'] is None:
                    to_card.append(ret_c)
                not_update.append(config.cq.at(ret_c['qq']))
            else:
                if ret_c['card'] is None:
                    to_card.append(ret_c)
                ret_c['parent'] = node['id']
                ret_c['child'] = []
                ret_c['trail'] = 0
                node['child'].append(ret_c['id'])
                updated.append(config.cq.at(ret_c['qq']))
                updated_qq.append(ret_c['qq'])
        save_whiteforest()
        for e in l:
            if e.qq in updated_qq and e.supervise >= 0:
                e.supervise = -1
        for r in to_card:
            c = await get_card(r['qq'])
            r['card'] = c
        if len(to_card) > 0:
            save_whiteforest()
        await session.send(updated + ([config.cq.text(" 已成功推荐！")] if len(updated) > 0 else []) + ([config.cq.text("\n")] if len(updated) > 0 and len(not_update) > 0 else []) + ((not_update + [config.cq.text(" 是已推荐用户，推荐失败")]) if len(not_update) > 0 else []), auto_escape=True)

@on_command(('thwiki', 'deprive'), only_to_me=False, permission=permission.GROUP_ADMIN)
@config.ErrorHandle
@config.maintain('thwiki')
async def thwiki_deprive(session: CommandSession):
    group_id = session.ctx['group_id']
    if group_id not in config.group_id_dict['thwiki_live']:
        return
    match = re.search('qq=(\\d+)', session.current_arg)
    if not match:
        await session.send('没有@人')
        return
    qq = int(match.group(1))
    node = find_or_new(qq=qq)
    if node['trail'] == 1:
        if node['card'] is None:
            node['card'] = await get_card(qq)
        await session.send('此人仍在试用期，删除失败')
        return
    node_parent = find_whiteforest(id=node['parent'])
    if node_parent is not None:
        node_parent['child'].remove(node['id'])
    updated = deprive(node)
    save_whiteforest()
    await session.send([config.cq.text('已成功删除')] + updated)

@on_command(('thwiki', 'supervise'), only_to_me=False)
@config.ErrorHandle
@config.maintain('thwiki')
async def thwiki_supervise(session: CommandSession):
    group_id = session.ctx['group_id']
    if group_id not in config.group_id_dict['thwiki_supervise']:
        return
    qq = session.ctx['user_id']
    i = session.current_arg_text.split(' ')
    if len(i) == 1:
        id = int(i[0])
        t = True
    elif len(i) == 2:
        id = int(i[0])
        t = not (i[1] == 'false' or i[1] == 'False' or i[1] == 'f' or i[1] == 'F')
    else:
        await session.send('使用-thwiki.supervise 直播id [可选：True/False]')
        return
    ret = more_itertools.only([x for x in l if x.id == id])
    if ret is None:
        await session.send('未发现此id的直播提交')
    elif ret.supervise == -1:
        await session.send('此直播提交者已有权限')
    elif ret.supervise > 0 and t:
        await session.send('此直播提交已有监视者')
    elif ret.supervise != qq and not t:
        await session.send('删除失败')
    else:
        if t:
            ret.supervise = qq
            if ret.begin < datetime.now():
                ret.begin = datetime.now()
            await _save(l)
            await session.send('成功提交监视')
            for group in config.group_id_dict['thwiki_send']:
                await get_bot().send_group_msg(group_id=group, message=ret.str_with_at())
        else:
            ret.supervise = 0
            await _save(l)
            await session.send('成功删除监视')
            for group in config.group_id_dict['thwiki_send']:
                await get_bot().send_group_msg(group_id=group, message=ret.str_with_at())

@on_command(('thwiki', 'time'), only_to_me=False)
@config.ErrorHandle
@config.maintain('thwiki')
async def thwiki_time(session: CommandSession):
    match = re.search('qq=(\d+)', session.current_arg)
    if match:
        qq = int(match.group(1))
    else:
        qq = session.ctx['user_id']
    node = find_or_new(qq=qq)
    if 'time' not in node:
        node['time'] = 0
    await session.send(f'您{"查询的人" if match else ""}的直播总时长为：{node["time"]}分钟。（2019年8月开始）', auto_escape=True)

@on_command(('thwiki', 'timezone'), only_to_me=False)
@config.ErrorHandle
@config.maintain('thwiki')
async def thwiki_timezone(session: CommandSession):
    match = re.search('qq=(\d+)', session.current_arg)
    if match:
        qq = int(match.group(1))
        other = True
    else:
        qq = session.ctx['user_id']
        other = False
    match = re.fullmatch('(UTC)?(\+\d+|-\d+|\d+)(:00)?', session.current_arg_text.strip())
    if match and not other:
        tz_new = int(match.group(2))
        if tz_new <= -24 or tz_new >= 24:
            await session.send("UTC时区必须在(-24, +24)以内")
            return
    else:
        tz_new = None
    node = find_or_new(qq=qq)
    if tz_new is not None:
        node['timezone'] = tz_new
        await session.send(f"您的时区已修改为{timezone(timedelta(hours=tz_new)).tzname(datetime.today())}")
        save_whiteforest()
    else:
        tz = node.get('timezone', 8)
        await session.send(("您查询的用户" if other else "您") + f"的时区为{timezone(timedelta(hours=tz)).tzname(datetime.today())}")

@on_command(('thwiki', 'grantlist'), only_to_me=False)
@config.ErrorHandle
@config.maintain('thwiki')
async def thwiki_grantlist(session: CommandSession):
    for node in whiteforest:
        if node['card'] is None:
            node['card'] = await get_card(node['qq'])
    await session.send('\n'.join([f"id: {node['id']} qq: {node['qq']} 名片: {node['card']}\nparent id: {node['parent']}" + (f" 名片: {find_whiteforest(id=node['parent'])['card']}" if node['parent'] != -1 else '') + (f"\nchilds id: {' '.join(map(str, node['child']))}" if len(node['child']) > 0 else "") for node in whiteforest if node['trail'] == 0]), auto_escape=True, ensure_private=True)

@on_command(('thwiki', 'leaderboard'), only_to_me=False)
@config.ErrorHandle
@config.maintain('thwiki')
async def thwiki_leaderboard(session: CommandSession):
    for node in whiteforest:
        if node['card'] is None:
            node['card'] = await get_card(node['qq'])
    await session.send('\n'.join([f"{i + 1} 直播时长：{node['time']}min 用户：{node['card']} {node['qq']}" for i, node in enumerate(more_itertools.take(10, sorted(whiteforest, key=lambda node: (0 if 'time' not in node else node['time']), reverse=True)))]), auto_escape=True)

@on_command(('thwiki', 'open'), only_to_me=False, permission=permission.SUPERUSER)
@config.ErrorHandle
async def thwiki_open(session: CommandSession):
    ret = await th_open()
    if json.loads(ret)['code'] != 0:
        await session.send('开启直播失败')
    else:
        await session.send('成功开启直播')

@on_command(('thwiki', 'change'), only_to_me=False)
@config.ErrorHandle
@config.maintain('thwiki')
async def thwiki_change(session: CommandSession):
    try:
        group_id = session.ctx['group_id']
        if group_id not in config.group_id_dict['thwiki_live']:
            return
    except KeyError:
        await session.send('请在群内使用')
        return
    #permission check
    now = datetime.now()
    qq = int(session.ctx['user_id'])
    async def _():
        if await permission.check_permission(get_bot(), session.ctx, permission.GROUP_ADMIN):
            return True, None
        for i, e in enumerate(l):
            if e.isFloat:
                if i == len(l) - 1:
                    b = True
                else:
                    b = now < l[i + 1].begin
            else:
                b = now < e.end
            if qq == e.qq and b and e.begin < now:
                return (e.supervise != 0), e
        return False, None
    r = await _()
    if not r[0]:
        await session.send('请在您预约的时间段前后十五分钟内修改' if r[1] is None or r[1].supervise != 0 else '十分抱歉，您现在的直播尚无监视员，无法直播qwq')
        return
    t = session.current_arg_text.strip()
    if t == "":
        await session.send('请填写您要修改的标题')
        return
    if r[1] is not None:
        r[1].name = t
    if '东方' not in t:
        t = '【东方】' + t
    ret = await change(title=t)
    if json.loads(ret)['code'] == 0:
        await session.send(f'成功修改标题至"{t}"', auto_escape=True)
    else:
        await session.send(ret, auto_escape=True)

@on_command(('thwiki', 'version'), only_to_me=False)
@config.ErrorHandle
@config.maintain('thwiki')
async def thwiki_version(session: CommandSession):
    await session.send(f"七海千春 THBWiki直播小助手 ver.{version} 为您服务")

@on_command(('thwiki', 'des'), only_to_me=False, permission=permission.SUPERUSER)
@config.ErrorHandle
async def thwiki_changedes(session: CommandSession):
    ret = await change(description=session.current_arg_text)
    await session.send(ret, auto_escape=True)

@on_command(('thwiki', 'maintain'), only_to_me=False, permission=permission.GROUP_ADMIN)
@config.ErrorHandle
async def thwiki_maintain(session: CommandSession):
    group_id = session.ctx['group_id']
    if group_id not in config.group_id_dict['thwiki_live']:
        return
    config.maintain_str['thwiki'] = session.current_arg_text
    config.maintain_str_save()
    if session.current_arg_text != "":
        await th_open(is_open=False)
        await session.send('已进入维护状态，再次输入空字符串解除')
    else:
        #if await permission.check_permission(get_bot(), session.ctx, permission.GROUP_OWNER | permission.SUPERUSER):
        await session.send('已解除维护状态')

@on_command(('thwiki', 'shutdown'), only_to_me=False, permission=permission.GROUP_ADMIN)
@config.ErrorHandle
async def thwiki_shutdown(session: CommandSession):
    group_id = session.ctx['group_id']
    if group_id not in config.group_id_dict['thwiki_live']:
        return
    await th_open(is_open=False)
    await session.send('已关闭直播间')

@on_command(('thwiki', 'blacklist'), only_to_me=False, permission=permission.GROUP_ADMIN)
@config.ErrorHandle
async def thwiki_blacklist(session: CommandSession):
    group_id = session.ctx['group_id']
    if group_id not in config.group_id_dict['thwiki_live']:
        return
    global blacklist
    qq = int(session.current_arg_text)
    blacklist.append(qq)
    with open(config.rel('thwiki_blacklist.txt'), 'w') as f:
        for qq in blacklist:
            f.write(str(qq))
            f.write('\n')
    await session.send('successfully added to blacklist')

@on_command(('thwiki', 'check_user'), only_to_me=False, permission=permission.GROUP_ADMIN)
@config.ErrorHandle
async def thwiki_check_user(session: CommandSession):
    group_id = session.ctx['group_id']
    if group_id not in config.group_id_dict['thwiki_live']:
        return
    await session.send(str(len([node for node in whiteforest if 'time' in node and node['time'] > 0])))

@on_notice('group_increase')
@config.maintain('thwiki')
async def thwiki_greet(session: NoticeSession):
    if session.ctx['group_id'] in config.group_id_dict['thwiki_live']:
        message = '欢迎来到THBWiki直播群！我是直播小助手，在群里使用指令即可申请直播时间~\n现在群内直播使用推荐，有人推荐可以直接直播，没有推荐的用户直播时需有管理监视，总直播时长36小时之后可以转正。\n以下为指令列表，欢迎在群里使用与提问~\n' + Help.sp['thwiki_live']['thwiki'] % Help._dict['thwiki']
        await get_bot().send_private_msg(user_id=session.ctx['user_id'], message=message, auto_escape=True)

@on_notice('group_decrease')
@config.maintain('thwiki')
async def thwiki_decrease(session: NoticeSession):
    if session.ctx['group_id'] not in config.group_id_dict['thwiki_live']:
        return
    qq = session.ctx['user_id']
    node = find_whiteforest(qq=qq)
    if node is not None and node['trail'] == 0:
        node_parent = find_whiteforest(id=node['parent'])
        if node_parent is not None:
            node_parent['child'].remove(node['id'])
        if_send = len(node['child']) != 0
        updated = deprive(node)
        if if_send:
            for group in config.group_id_dict['thwiki_send']:
                await get_bot().send_group_msg(group_id=group, message=[config.cq.text(f"{node['card']} 退群，已自动退回推荐")] + updated + [config.cq.text("！试用期直播时间从0开始计算。\n")])

@on_command(('thwiki', 'test'), only_to_me=False, permission=permission.GROUP_ADMIN)
@config.ErrorHandle
async def thwiki_test(session: CommandSession):
    for node in whiteforest:
        if 'parent' in node:
            parent = find_whiteforest(id=node['parent'])
            if parent is not None and node['id'] not in parent['child']:
                parent['child'].append(node['id'])
    save_whiteforest()