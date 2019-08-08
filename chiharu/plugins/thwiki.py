from datetime import datetime, timedelta, date
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
import chiharu.plugins.config as config
import chiharu.plugins.help as Help

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

def format_date(dat: datetime):
    today = date.today()
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
    max_id = 0
    def __init__(self, *args):
        if len(args) == 6:
            self.begin, self.end, self.qq, self.card, self.name, self.isFloat = args
            self.id = Event.max_id
            Event.max_id += 1
        elif len(args) == 3:
            id, begin, end, qq, supervise = args[0].split(' ')
            self.id = int(id)
            Event.max_id = max(Event.max_id, self.id + 1)
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
        self.supervise = 0 # -1: 有权限，0: 无权限
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
        return f'id: {self.id} {begin}-{end}\n投稿人: {self.card}\n内容: {self.name}'
    def str_url(self):
        begin = format_date(self.begin)
        if self.isFloat:
            end = '自由'
        else:
            end = format_date(self.end)
        return f'{begin}-{end}<br />投稿人: {self.card}<br />内容: {self.name}'
    def str_with_at(self):
        begin = format_date(self.begin)
        if self.isFloat:
            end = '自由'
        else:
            end = format_date(self.end)
        return [config.cq.str(f'id: {self.id} {begin}-{end}\n投稿人: '), config.cq.at(self.qq), config.cq.str(f'\n内容: {self.name}')]
    def output_with_at(self):
        if self.supervise == -1:
            return [config.cq.text('开播提醒！\n'), config.cq.at(self.qq), config.cq.text('\n内容: %s' % self.name)]
        elif self.supervise != 0:
            return [config.cq.text('开播提醒！\n'), config.cq.at(self.qq), config.cq.text('\n内容: %s\n请监视者就位' % self.name), config.cq.at(self.supervise)]
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

async def _save(t):
    with open(config.rel("thwiki.txt"), 'w', encoding='utf-8') as f:
        f.write('\n'.join(map(repr, t)))

l = _open()

def polish(l):
    now = datetime.now()
    def _():
        for i, e in enumerate(l):
            if not e.isFloat and e.end < now:
                continue
            if e.isFloat and i != len(l) - 1 and l[i + 1].begin < now:
                continue
            yield e
    return list(_())

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
def find_whiteforest(id=None, qq=None):
    return more_itertools.only([x for x in whiteforest if x['qq'] == qq]) if id is None else more_itertools.only([x for x in whiteforest if x['id'] == id])
def save_whiteforest():
    with open(config.rel("thwiki_whiteforest.json"), 'w', encoding='utf-8') as f:
        f.write(json.dumps(whiteforest, ensure_ascii=False, indent=4, separators=(',', ': ')))
def check_whiteforest(qq):
    ret = find_whiteforest(qq=qq)
    return (ret is not None and ret['trail'] != 0), ret
async def get_card(qq):
    for group in group_id_dict['thwiki_card']:
        c = await get_bot().get_group_member_info(group_id=group, user_id=qq)
        if c['card'] == '':
            return c['nickname']
        else:
            return c['card']
def find_or_new(qq):
    ret = find_whiteforest(qq=qq)
    if ret is None:
        ret = {'id': len(whiteforest), 'qq': qq, 'trail': 1, 'card': None, 'time': 0}
        whiteforest.append(ret)
    return ret
def deprive(qqs, node):
    not_update = []
    updated = []
    for qq in qqs:
        node_c = find_whiteforest(qq=qq)
        if node_c is None:
            not_update.append(config.cq.at(qq))
        elif node_c['trail'] == 0 or node_c['parent'] != node['id']:
            not_update.append(config.cq.at(node_c['qq']))
        else:
            to_do = [node_c]
            node['child'].remove(node_c['id'])
            while len(to_do):
                r = to_do.pop(0)
                r.pop('parent')
                for i in r.pop('child'):
                    f = find_whiteforest(id=i)
                    to_do.append(f)
                r['trail'] = 0
                r['time'] = 0
                updated.append(config.cq.at(r['qq']))
    save_whiteforest()
    return not_update, updated
#need: func add time

@on_command(('thwiki', 'apply'), aliases=('申请',), only_to_me=False)
@config.ErrorHandle
@config.maintain('thwiki')
async def apply(session: CommandSession):
    group_id = session.ctx['group_id']
    if group_id not in config.group_id_dict['thwiki_live']:
        return
    global l
    begin = session.get('begin')
    end = session.get('end')
    float_end = session.get('float_end')
    qq = session.get('qq')
    card = session.get('card')
    name = session.get('name')
    if qq in blacklist:
        return
    if begin == False or (float_end == False and end == False):
        await session.send('时间格式不正确，请使用' '(\\d+年)?(\\d+月)?(\\d+(日|号))?'
        '(' '(\\d+(时|点))' '(\\d+分)?' '|' '\\d+:\\d+' ')，且保证时间有效'
        '\n开始可用now，结束可用float')
        return
    if not float_end:
        if begin > end:
            await session.send('结束需要比开始晚！')
            return
        if end < datetime.now():
            await session.send('结束需要比现在晚')
            return
    if len(name) < 1:
        await session.send('不能没有名字')
        return
    if '\n' in name:
        await session.send('名字不能含有换行符')
        return
    t = list(filter(lambda x: x.name == name, l))
    if len(t) != 0:
        await session.send('已有重名，请换名字')
        return
    if len(l) == 0:
        Event.max_id = 0
    e = Event(begin, end, qq, card, name, float_end)
    for i in l:
        if i.overlap(e):
            await session.send('这个时间段已经有人了\n' + str(i), auto_escape=True)
            return
    l.append(e)
    l.sort(key=lambda x: x.begin)
    l = polish(l)
    await _save(l)
    check = find_or_new(qq)
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
    if session.ctx['sender']['card'] == '':
        session.args['card'] = session.ctx['sender']['nickname']
    else:
        session.args['card'] = session.ctx['sender']['card']
    session.args['float_end'] = False
    now = datetime.now()
    def _default(t, t_default):
        if t is None:
            return t_default
        else:
            return int(t)
    i = session.current_arg_text.find(' ')
    time_begin = session.current_arg_text[:i]
    j = session.current_arg_text.find(' ', i + 1)
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
                session.args['begin'] = datetime(year, month, day, hours, minute)
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
                session.args['end'] = datetime(year, month, day, hours, minute)
            except:
                session.args['end'] = False

@on_command(('thwiki', 'cancel'), aliases=('取消',), only_to_me=False)
@config.ErrorHandle
@config.maintain('thwiki')
async def cancel(session: CommandSession):
    global l
    if int(session.ctx['user_id']) in blacklist:
        return
    l2 = more_itertools.only([x for x in enumerate(l) if x[1].name == session.current_arg_text])
    if l2 is None:
        l2 = more_itertools.only([x for x in enumerate(l) if x[1].id == int(session.current_arg_text)])
        if l2 is None:
            await session.send('未找到')
    else:
        i = l2[0]
        if int(session.ctx['user_id']) == l[i].qq or \
                await permission.check_permission(get_bot(), session.ctx, permission.GROUP_ADMIN):
            l.pop(i)
            await session.send('成功删除')
            await _save(l)
            ret = await change_des_to_list()
            if json.loads(ret)['code'] != 0:
                await session.send('更新到直播间失败')
        else:
            await session.send('非管理员不可删除别人的')

@on_command(('thwiki', 'list'), only_to_me=False)
@config.ErrorHandle
@config.maintain('thwiki')
async def thlist(session: CommandSession):
    global l
    l = polish(l)
    await _save(l)
    if len(l) == 0:
        await session.send('列表为空')
    else:
        await session.send('\n'.join(map(str, l)), auto_escape=True)

@on_command(('thwiki', 'term'), only_to_me=False)
@config.ErrorHandle
@config.maintain('thwiki')
async def term(session: CommandSession):
    group_id = session.ctx['group_id']
    if group_id not in config.group_id_dict['thwiki_live']:
        return
    global l
    if int(session.ctx['user_id']) in blacklist:
        return
    now = datetime.now()
    def _():
        for i, e in enumerate(l):
            if not e.isFloat and e.end < now:
                continue
            if e.isFloat and i != len(l) - 1 and l[i + 1].begin < now:
                continue
            yield e
    l = list(_())
    if len(l) == 0:
        await session.send('现在未在播')
    else:
        if now < l[0].begin:
            await session.send('现在未在播')
        elif l[0].qq != session.ctx['user_id']:
            await session.send('现在不是你在播')
        else:
            l.pop(0)
            await _save(l)
            ret = await th_open(is_open=False)
            if json.loads(ret)['code'] != 0:
                await session.send('成功删除，断流失败')
            else:
                await session.send('成功断流')
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
            await bot.send_group_msg(group_id=id, message='直播间简介更新失败')
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
    for i, e in enumerate(l):
        if e.isFloat and i != len(l) - 1 and now - timedelta(seconds=59) < l[i + 1].begin < now + timedelta(seconds=1) or \
            not e.isFloat and now - timedelta(seconds=59) < e.end < now + timedelta(seconds=1):
            l.pop(i)
            await _save(l)
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
    group_id = session.ctx['group_id']
    if group_id not in config.group_id_dict['thwiki_live']:
        return
    #permission check
    now = datetime.now()
    qq = int(session.ctx['user_id'])
    if qq in blacklist:
        return
    async def _():
        if await permission.check_permission(get_bot(), session.ctx, permission.GROUP_ADMIN):
            return True
        for i, e in enumerate(l):
            if e.isFloat:
                if i == len(l) - 1:
                    b = True
                else:
                    b = now < l[i + 1].begin + timedelta(minutes=15)
            else:
                b = now < e.end + timedelta(minutes=15)
            if qq == e.qq and b and e.begin - timedelta(minutes=15) < now:
                return (e.supervise != 0), e.supervise
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
        await session.send([config.cq.text('无法获取rtmp与key，可能是cookie过期，已将缓存数据发送，如无法推流请联系'),
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
            await session.send('不支持分区：%s' % session.current_arg_text, auto_escape=True)
            area = 235
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
async def grant(session: CommandSession):
    group_id = session.ctx['group_id']
    if group_id not in config.group_id_dict['thwiki_live']:
        return
    sqq = session.ctx['user_id']
    valid, ret = check_whiteforest(sqq)
    if not valid:
        await session.send("您还处在试用期，无法推荐")
    def _(s):
        begin = 0
        while 1:
            match = re.search('qq=(\\d+)', s[begin:])
            if not match:
                return
            begin += match.span()[1]
            yield int(match.group(1))
    qqs = list(_(str(session.current_arg)))
    s = session.current_arg[session.current_arg.rfind(' ') + 1:]
    if s == 'false' or s == 'False' or s == 'f' or s == 'F':
        not_update, updated = deprive(qqs, ret)
        await session.send(updated + ([config.cq.text(" 已成功退回推荐！试用期直播时间从0开始计算。\n")] if len(updated) > 0 else []) + not_update + ([config.cq.text(" 不是您推荐的用户，删除失败")] if len(not_update) > 0 else []), auto_escape=True)
    else:
        not_update = []
        updated = []
        to_card = []
        for qq in qqs:
            ret_c = find_or_new(qq)
            if not ret_c['trail']:
                if ret_c['card'] is None:
                    to_card.append(ret_c)
                    not_update.append(config.cq.at(ret_c['qq']))
                else:
                    not_update.append(config.cq.at(ret_c['qq']))
            else:
                ret_c['parent'] = ret['id']
                ret_c['child'] = []
                ret_c['trail'] = 0
                ret['child'].append(ret_c['id'])
                updated.append(config.cq.at(ret_c['qq']))
        save_whiteforest()
        for r in to_card:
            c = await get_card(r['qq'])
            r['card'] = c
        if len(to_card) > 0:
            save_whiteforest()
        await session.send(updated + ([config.cq.text(" 已成功推荐！\n")] if len(updated) > 0 else []) + not_update + ([config.cq.text(" 是已推荐用户，推荐失败")] if len(not_update) > 0 else []), auto_escape=True)

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
            await _save(l)
            await session.send('成功提交监视')
            for group in config.group_id_dict['thwiki_send']:
                await get_bot().send_group_msg(group_id=group, message=[config.cq.text(str(ret) + '\n监视者：'), config.cq.at(qq)])
        else:
            ret.supervise = 0
            await _save(l)
            await session.send('成功删除监视')
            for group in config.group_id_dict['thwiki_send']:
                await get_bot().send_group_msg(group_id=group, message=[config.cq.text('十分抱歉，\n' + str(ret) + '\n监视者已取消orz')])

@on_command(('thwiki', 'open'), only_to_me=False, permission=permission.SUPERUSER)
@config.ErrorHandle
async def thwiki_open(session: CommandSession):
    ret = await th_open()
    if json.loads(ret)['code'] != 0:
        await session.send('开启直播失败')
    else:
        await session.send('成功开启直播')

@on_command(('thwiki', 'change'), only_to_me=False, permission=permission.SUPERUSER)
@config.ErrorHandle
async def thwiki_change(session: CommandSession):
    ret = await change(title=session.current_arg_text)
    await session.send(ret, auto_escape=True)

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

@on_notice('group_increase')
@config.maintain('thwiki')
async def thwiki_greet(session: NoticeSession):
    if session.ctx['group_id'] in config.group_id_dict['thwiki_live']:
        message = '欢迎来到THBWiki直播群！我是直播小助手，在群里使用指令即可申请直播时间~以下为指令列表，欢迎在群里使用与提问~\n' + Help.sp['thwiki_live']['thwiki'] % Help._dict['thwiki']
        await get_bot().send_private_msg(user_id=session.ctx['user_id'], message=message, auto_escape=True)