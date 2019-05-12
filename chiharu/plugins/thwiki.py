from datetime import datetime, timedelta, date
import re
import requests
import json
import asyncio
import functools
import random
from copy import copy
from urllib import parse
from nonebot import on_command, CommandSession, get_bot, permission, scheduler
import chiharu.plugins.config as config
#from selenium.webdriver import chrome, Chrome

#chrome_options = chrome.options.Options()
#chrome_options.add_argument('--disable-gpu')
#driver = Chrome(options=chrome_options)
#driver.get('https://passport.bilibili.com/login')

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

async def th_open(area=235):
    cookie_jar = requests.cookies.RequestsCookieJar()
    with open(config.rel('cookie.txt')) as f:
        value = f.readline().strip()
    cookie_jar.set(name="SESSDATA", value=value)
    cookie_jar.set(name="bili_jct", value=config.csrf_thb)
    value = {'room_id': 14055253, 'area_v2': area, 'platform': 'pc', 'csrf': config.csrf_thb, 'csrf_token': config.csrf_thb}
    length = len(parse.urlencode(value))
    print('length: ' + str(length))
    headers = copy(config.headers)
    headers['Content-Length'] = str(length)
    loop = asyncio.get_event_loop()
    url = await loop.run_in_executor(None, functools.partial(requests.post,
        'https://api.live.bilibili.com/room/v1/Room/startLive',
        data=value, cookies=cookie_jar, headers=headers))
    return url.text

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
    def __init__(self, *args):
        if len(args) == 6:
            self.begin, self.end, self.qq, self.card, self.name, self.isFloat = args
        elif len(args) == 3:
            begin, end, qq = args[0].split(' ')
            if end == 'float':
                self.end = False
                self.isFloat = True
                self.begin, self.qq = datetime.fromtimestamp(float(begin)), int(qq)
            else:
                self.isFloat = False
                self.begin, self.end, self.qq = datetime.fromtimestamp(float(begin)), datetime.fromtimestamp(float(end)), int(qq)
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
        qq = str(self.qq)
        return '%s %s %s\n%s\n%s' % (begin, end, qq, self.card, self.name)
    def __str__(self):
        begin = format_date(self.begin)
        if self.isFloat:
            end = '自由'
        else:
            end = format_date(self.end)
        return '%s-%s\n投稿人: %s\n内容: %s' % (begin, end, self.card, self.name)
    def str_url(self):
        begin = format_date(self.begin)
        if self.isFloat:
            end = '自由'
        else:
            end = format_date(self.end)
        return '%s-%s<br />投稿人: %s<br />内容: %s' % (begin, end, self.card, self.name)
    def output_with_at(self):
        return [config.cq.text('开播提醒！\n'), config.cq.at(self.qq),
            config.cq.text('\n内容: %s' % self.name)]
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

@on_command(('thwiki', 'apply'), aliases=('申请',), only_to_me=False)
@config.ErrorHandle
async def apply(session: CommandSession):
    group_id = session.ctx['group_id']
    if group_id not in config.group_id_dict['thwiki_live']:
        return
    global l
    begin = session.get('begin')
    end = session.get('end')
    float_end = session.get('float_end')
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
    qq = session.get('qq')
    card = session.get('card')
    name = session.get('name')
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
    e = Event(begin, end, qq, card, name, float_end)
    for i in l:
        if i.overlap(e):
            await session.send('这个时间段已经有人了\n' + str(i), auto_escape=True)
            return
    l.append(e)
    l.sort(key=lambda x: x.begin)
    l = polish(l)
    await _save(l)
    await session.send('成功申请')
    ret = await change_des_to_list()
    if json.loads(ret)['code'] != 0:
        await session.send('更新到直播间失败')
    
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
async def cancel(session: CommandSession):
    global l
    l2 = list(filter(lambda x: x[1].name == session.current_arg_text, enumerate(l)))
    if len(l2) == 0:
        await session.send('未找到')
    #elif len(l2) == 1:
    else:
        i = l2[0][0]
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
async def term(session: CommandSession):
    group_id = session.ctx['group_id']
    if group_id not in config.group_id_dict['thwiki_live']:
        return
    global l
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
            await session.send('成功删除')
            await _save(l)
            ret = await change_des_to_list()
            if json.loads(ret)['code'] != 0:
                await session.send('更新到直播间失败')

@scheduler.scheduled_job('cron', hour='00')
async def _():
    global l
    ret = await change_des_to_list()
    if json.loads(ret)['code'] != 0:
        for id in config.group_id_dict['thwiki_send']:
            await bot.send_group_msg(group_id=id, message='直播间简介更新失败')

@scheduler.scheduled_job('cron', second='00')
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
async def get(session: CommandSession):
    group_id = session.ctx['group_id']
    if group_id not in config.group_id_dict['thwiki_live']:
        return
    #permission check
    now = datetime.now()
    qq = int(session.ctx['user_id'])
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
            if qq == e.qq and \
                    b and e.begin - timedelta(minutes=15) < now:
                return True
        return False
    if not await _():
        await session.send('请在您预约的时间段前后十五分钟内申请获取rtmp')
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
        ret = await th_open(area)
        if json.loads(ret)['code'] == 0:
            await session.send('检测到直播间未开启，现已开启，分区：%s' % \
                {235: '单机·其他', 123: '娱乐·户外', 143: '娱乐·才艺', 34: '娱乐·音乐台', 199: '娱乐·虚拟主播', 98: '手游·其他', 107: '网游·其他', 94: '绘画：同人绘画', 95: '绘画·临摹绘画'} \
                [area])
        else:
            await session.send('检测到直播间未开启，开启直播间失败')

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