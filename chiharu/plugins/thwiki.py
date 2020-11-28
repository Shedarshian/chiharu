from datetime import datetime, timedelta, date, timezone
import re
import requests
import json
import asyncio
import functools
import itertools, more_itertools
import random
from collections import namedtuple
from copy import copy
from typing import Optional
from urllib import parse
from nonebot import CommandSession, get_bot, permission, scheduler, on_notice, NoticeSession, RequestSession, on_request, message_preprocessor
from nonebot.command import call_command
import aiocqhttp
from . import config, help
from .inject import on_command
config.logger.open('thwiki')
env = config.Environment('thwiki_live', ret='请在直播群内使用')
env_supervise_only = config.Environment('thwiki_supervise', ret='请在监视群内使用')
def is_supervisor(session):
    qq = session.ctx['user_id']
    node = find_or_new(qq)
    return 'supervisor' in node and node['supervisor']
constraint_supervisor = config.Constraint('thwiki_live', can_respond=is_supervisor)
env_supervise = config.Environment('thwiki_supervise', 'thwiki_live', constraint_supervisor, ret='请在监视群内或直播群管理使用')
env_all_thwiki_live = config.Environment('thwiki_supervise', 'thwiki_live')
env_all_can_private = config.Environment('thwiki_supervise', 'thwiki_live')
env_all_can_private.private = True

config.CommandGroup('thwiki', short_des="THBWiki官方账户直播相关。", des='THBWiki官方账户直播相关。部分指令只可在直播群内使用。', environment=env_all_can_private)

# Version information and changelog
version = "2.3.12"
changelog = """2.3.0-12 Changelog:
Change:
-thwiki.apply：1.支持 明天/明日/后天/后日
2.结束时间默认与起始时间在同一天
3.支持中文冒号
-thwiki.grant：推荐需要获得推荐权。获得推荐权的方法是申请加入“THBWiki直播审核群”。并且不需要被推荐人同意。
若开播后15分钟仍未有人监视，则申请会被自动取消。
Remove:
-thwiki.confirm_grant"""

TRAIL_TIME = 36 * 60
TIME_OUT = 15
FRIENDLY_MAX = 5

# Change title and description on Bilibili livestream room
# title: self-explanatory
# description: self-explanatory
async def change(title=None, description=None, area=None): 
    # Retrieve cookie
    cookie_jar = requests.cookies.RequestsCookieJar()
    with open(config.rel('cookie.txt')) as f:
        value = f.readline().strip()
        csrf = f.readline().strip()
    cookie_jar.set(name="SESSDATA", value=value)
    cookie_jar.set(name="bili_jct", value=csrf)

    # Construct and encode data
    if area is None:
        value = {'room_id': 14055253, 'title': title, 'description': description, 'csrf': csrf, 'csrf_token': csrf}
    else:
        value = {'room_id': 14055253, 'area_id': area, 'csrf': csrf, 'csrf_token': csrf}
    length = len(parse.urlencode(value))
    print('length: ' + str(length))
    headers = copy(config.headers)
    headers['Content-Length'] = str(length)

    # Send request
    loop = asyncio.get_event_loop()
    url = await loop.run_in_executor(None, functools.partial(requests.post,
        'https://api.live.bilibili.com/room/v1/Room/update',
        data=value, cookies=cookie_jar, headers=headers))
    return url.text

# Open or close the Bilibili livestream room
# is_open: indicates the operation, True for open, False for close
# area: type of content, default to 'Games - Other games'
async def th_open(is_open=True, area=235):
    # Retrieve cookie
    cookie_jar = requests.cookies.RequestsCookieJar()
    with open(config.rel('cookie.txt')) as f:
        value = f.readline().strip()
        csrf = f.readline().strip()
    cookie_jar.set(name="SESSDATA", value=value)
    cookie_jar.set(name="bili_jct", value=csrf)
    
    # Construct and encode information
    value = {'room_id': 14055253, 'platform': 'pc', 'csrf': csrf, 'csrf_token': csrf}
    if is_open:
        value['area_v2'] = area
    length = len(parse.urlencode(value))
    headers = copy(config.headers)
    headers['Content-Length'] = str(length)

    # Send request
    loop = asyncio.get_event_loop()
    ret = await loop.run_in_executor(None, functools.partial(requests.post,
        'https://api.live.bilibili.com/room/v1/Room/startLive' if is_open
            else 'https://api.live.bilibili.com/room/v1/Room/stopLive',
        data=value, cookies=cookie_jar, headers=headers))
    return ret.text

# Formats a date to something more human-friendly
# dat: The date and time to be formatted
# tz: Timezone, integer hours relative to GMT/UTC
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

# Event class, encapsulates an application
# Methods:
#   str_tz: construct a string with timezone info
#   str_url: construct a string with HTML formatting tags, intended for change only
#   str_with_at: construct a string to inform an unauthorized applicant that one of their applications is supervised 
#   output_with_at: construct a string of notice to the applicant
#   overlap: checks if an application overlaps with another one
# Fields:
#   begin: begin time
#   end: end time
#   qq: QQ ID of the applicant
#   card: alias of applicant in the QQ group
#   name: the event name
#   isFloat: whether this application has a certain end time
#   id: internal (external??) ID as an identifier
#   supervise: status of application, -1 indicates that the applicant is authorized, 
#     0 indicates that this application is waiting for supervise, other positive value
#     indicates that this application is under supervise
#   msg_id: supervise message_id
class Event:
    def __init__(self, *args):
        if len(args) == 6:
            # On apply, fill fields with arguments
            self.begin, self.end, self.qq, self.card, self.name, self.isFloat = args

            # Assign an ID associated with this application
            self.id = self.gen_id()

            # Check whether this applicant has been authorized
            node = find_whiteforest(qq=self.qq)
            if node is not None and node['trail'] == 0:
                self.supervise = -1
            else:
                self.supervise = 0 # -1: 有权限，0: 无权限
            self.msg_id = -1
            self.has_alarmed = False
        elif len(args) == 1:
            # On read from file, fill fields with the first argument 
            id, begin, end, qq, supervise, msg_id = args[0]['id'], args[0]['begin'], args[0]['end'], args[0]['qq'], args[0]['supervise'], args[0]['msg_id']
            self.id = int(id)

            # Check for endtime
            if end == 'float':
                self.end = False
                self.isFloat = True
                self.begin, self.qq = datetime.fromtimestamp(float(begin)), int(qq)
            else:
                self.isFloat = False
                self.begin, self.end, self.qq = datetime.fromtimestamp(float(begin)), datetime.fromtimestamp(float(end)), int(qq)
            self.supervise = int(supervise)
            self.msg_id = int(msg_id)
            self.card = args[0]['card']
            self.name = args[0]['name']
            self.has_alarmed = args[0].get('has_alarmed', False)
        else:
            raise TypeError()
    def __repr__(self):
        begin = str(self.begin.timestamp())
        if self.isFloat:
            end = 'float'
        else:
            end = str(self.end.timestamp())
        return f'{self.id} {begin} {end} {self.qq} {self.supervise} {self.msg_id}\n{self.card}\n{self.name}'
    def __str__(self):
        begin = format_date(self.begin)
        if self.isFloat:
            end = '自由'
        else:
            end = format_date(self.end)
        return f'id: {self.id} {begin}-{end} CST 投稿人: {self.card}\n' + \
            ((('【监视人尚无】 \n' if self.supervise == 0 else '【监视人已有】 \n')) if self.supervise >= 0 else '') + \
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
        if self.supervise == 0:
            return ''
        begin = format_date(self.begin)
        if self.isFloat:
            end = '自由'
        else:
            end = format_date(self.end)
        return f'时间: {begin}-{end} 投稿人: {self.card} <br />内容: {self.name} <br />'
    def str_with_at(self):
        begin = format_date(self.begin)
        if self.isFloat:
            end = '自由'
        else:
            end = format_date(self.end)
        if self.supervise == 0:
            return [config.cq.at(self.qq), config.cq.text(f'十分抱歉，您id为{self.id}、时间为{begin}-{end} CST、内容为{self.name} \n的直播的监视者取消了监视，您将无法再进行直播')]
        else:
            return [config.cq.at(self.qq), config.cq.text(f'您id为{self.id}、时间为{begin}-{end} CST、内容为{self.name} \n的直播已有人监视')]
    def output_with_at(self):
        if self.supervise != 0:
            return [config.cq.text('开播提醒！\n'), config.cq.at(self.qq), config.cq.text('\n内容: %s' % self.name)]
        else:
            return [config.cq.text('开播提醒！\n'), config.cq.at(self.qq), config.cq.text('\n内容: %s\n十分抱歉，您现在的直播尚无监视员，无法直播qwq，如15分钟之后仍无人监视则会被自动取消' % self.name)]
    def overlap(self, other):
        if self.isFloat and other.isFloat:
            return self.begin == other.begin
        elif self.isFloat:
            return other.begin <= self.begin < other.end
        elif other.isFloat:
            return self.begin <= other.begin < self.end
        return self.begin < other.end and other.begin < self.end # None of them end with uncertain time
    def gen_id(self):
        return more_itertools.first((i2 for i1, i2 in zip(itertools.chain(sorted(e.id for e in l), (-1,)), itertools.count()) if i1 != i2), 0)
    def dump(self):
        return {'id': self.id, 'begin': str(self.begin.timestamp()), 'end': 'float' if self.isFloat else str(self.end.timestamp()), 'qq': self.qq, 'supervise': self.supervise, 'msg_id': self.msg_id, 'card': self.card, 'name': self.name, 'has_alarmed': self.has_alarmed}

# Read from the file and returns a list of applications
def _open():
    with open(config.rel("thwiki.json"), encoding='utf-8') as f:
        return [Event(d) for d in json.load(f)]

# Initializes application list
l = _open()

# Writes current list of applications to the file
# Updates the "occupied_time.json" and alarm OLC's bot
async def _save(t):
    with open(config.rel("thwiki.json"), 'w', encoding='utf-8') as f:
        f.write(json.dumps(list(map(Event.dump, t)), ensure_ascii=False, indent=4))
    _3dayslater = date.today() + timedelta(days=3)
    occupied_time = []
    for i, event in enumerate(t):
        if event.begin.date() <= _3dayslater:
            begin = event.begin.isoformat(' ')
            end = 'float' if event.isFloat else event.end.isoformat(' ')
            if len(occupied_time) != 0 and (occupied_time[-1]['end'] == begin or occupied_time[-1]['end'] == 'float'):
                occupied_time[-1]['end'] = end
            else:
                occupied_time.append({'begin': begin, 'end': end})
    with open(r"C:\thwiki_connect\thwiki\occupied_time.json", 'w') as f:
        f.write(json.dumps(occupied_time))
    await get_bot().send_private_msg(user_id=config.OLC_bot, message='live occupied time updated')

# Generates an description and update to Bilibili livestream room
# Suggestion: create a new function that encapsulates _save and change_des_to_list as
#   they are almost always called together
async def change_des_to_list(lunbo=False):
    global l
    fut = datetime.now() + timedelta(days=7)
    s = 'THBWiki电视台（大雾）</h2><p>基本上会以直播<strong>东方Project</strong>的游戏为主。日常进行直播的主播不定。</p><h3><strong>本直播间欢迎大家使用，但需要直播的内容为东方Project相关且遵守直播者所在国家与中国相关法律与条约及平台条约。</strong><br />具体使用方法以及粉丝群请戳QQ群：<strong>807894304</strong> 【THBWiki Live】</h3><p>节目单（时间以北京时间为准）：<br />%s</p>' % \
        ''.join(map(Event.str_url, filter(lambda x: x.begin < fut, l)))
    if lunbo:
        s = '<h2>当前轮播中，欢迎查看收藏夹https://space.bilibili.com/362841475/favlist?fid=853928275，轮播视频均在收藏夹中，在直播群（下述）中可以添加轮播视频或推荐视频哦~<br />' + s
    else:
        s = '<h2>' + s
    return await change(description=s)

# Initializes blacklist (blocks user from applying)
with open(config.rel("thwiki_blacklist.txt")) as f:
    blacklist = list(map(lambda x: int(x.strip()), f.readlines()))

# Don't know what this does
def _line(s, has_card):
    l = s.split(' ')
    return l.pop(0), l.pop(0), l.pop(0), (' '.join(l) if has_card else None)

# Initializes the authorized user tree
with open(config.rel("thwiki_whiteforest.json"), encoding = 'utf-8') as f:
    whiteforest = json.load(f)

# Initializes weak blacklist (only blocks user from being the recommendee
with open(config.rel("thwiki_weak_blacklist.txt"), encoding = 'utf-8') as f:
    weak_blacklist = list(map(lambda x: int(x.strip()), f.readlines()))

# Find whether a user is in the authorized user tree
# id: internal ID, takes priority to qq
# qq: QQ ID
def find_whiteforest(*, id=None, qq=None):
    global whiteforest
    return more_itertools.only([x for x in whiteforest if x['qq'] == qq]) if id is None else more_itertools.only([x for x in whiteforest if x['id'] == id])

# Write current authorized user tree to file.
def save_whiteforest():
    global whiteforest
    with open(config.rel("thwiki_whiteforest.json"), 'w', encoding='utf-8') as f:
        f.write(json.dumps(whiteforest, ensure_ascii=False, indent=4, separators=(',', ': ')))

# So after all what is card??
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

# Add new user to the authorized user tree
# qq: QQ ID
def find_or_new(qq):
    global whiteforest
    ret = find_whiteforest(qq=qq)
    if ret is None:
        ret = {'id': len(whiteforest), 'qq': qq, 'trail': 1, 'card': None, 'time': 0}
        whiteforest.append(ret)
        save_whiteforest()
    return ret

# Removes user from the authorized user tree
# node: node of the user to be removed
# if_save: indicates whether the change should be saved now
# clear_time: self-explanatory
def deprive(node, if_save=True, clear_time=True):
    global whiteforest
    global l

    updated = []
    to_do = [node]
    updated_event = []
    while len(to_do):
        r = to_do.pop(0)

        # Put status back to 0 and notify supervisors
        for i in l:
            if i.qq == r['qq']:
                i.supervise = 0
                updated_event.append(i)

        if 'parent' in r:
            r.pop('parent')
        if 'child' in r:
            for i in r.pop('child'):
                f = find_whiteforest(id=i)
                # Add child nodes to the list
                to_do.append(f)

        # Why use trail as key? You mean 'trial' or 'trace'??
        r['trail'] = 1
        if clear_time:
            r['time'] = 0
        config.logger.thwiki << f'用户{r["qq"]} 已被deprive，时间{"清零" if clear_time else ("保留为" + str(r["time"]))}'
        updated.append(config.cq.at(r['qq']))

    if if_save:
        save_whiteforest()

    return updated, updated_event

# Adds time to an user
# qq: QQ ID
# time: the amount of time
def add_time(qq, time):
    # Get the node associated with the QQ ID
    node = find_or_new(qq)

    time = int(time)
    if 'time' not in node:
        node['time'] = 0
    node['time'] += time
    config.logger.thwiki << f'【LOG】用户{qq} {"积累" if time > 0 else "扣除"}时间{abs(time)}，目前时间{node["time"]}'

    b = False # What is the purpose??
    if node['time'] >= TRAIL_TIME and qq not in weak_blacklist:
        b = node['trail'] != 0
        if 'parent' not in node or node['parent'] != -1:
            if node['trail'] != 0:
                config.logger.thwiki << f'【LOG】用户{qq} 已通过试用期转正'
                node['trail'] = 0
            else:
                config.logger.thwiki << f'【LOG】用户{qq} 已通过试用期，节点独立'
            if 'parent' in node:
                find_whiteforest(id=node['parent'])['child'].remove(node['id'])
            if 'child' not in node:
                node['child'] = []
            node['parent'] = -1
            # Also check this fix
        if 'to_confirm' in node:
            node.pop('to_confirm')
    elif node['time'] < TRAIL_TIME and node['time'] - time > TRAIL_TIME:
        config.logger.thwiki << f'【LOG】用户{qq} 已退回试用期'
        node['trail'] = 1
    save_whiteforest()
    return b

def add_supervise_time(qq, time):
    node = find_or_new(qq)

    time = int(time)
    if 'supervise_time' not in node:
        node['supervise_time'] = 0
    node['supervise_time'] += time
    config.logger.thwiki << f'【LOG】监视者{qq} {"积累" if time > 0 else "扣除"}监视时间{abs(time)}，目前监视时间{node["time"]}'
    save_whiteforest()

class ApplyErr(BaseException):
    pass

record_file = open(config.rel(r'log\thwiki_record.txt'), 'a', encoding='utf-8')

class Record(namedtuple('Record', ['qq', 'time', 'msg_id', 'msg'])):
    def __str__(self):
        return f"{self.qq}【{self.time.isoformat(sep=' ')}】{self.msg_id}: {self.msg}"
    @staticmethod
    def construct(line):
        match = re.match('^(\d+)【(.*?)】(\d+): (.*)$', line)
        if not match:
            return None
        qq, time, msg_id, msg = match.groups()
        return Record(int(qq), datetime.fromisoformat(time), int(msg_id), msg.replace('\\', '\\\\').replace('\r', '').replace('\n', '\\n'))

def load_record(lines):
    return [Record.construct(line.strip('\r\n')) for line in lines]

async def add_fav(fav, av=None, bv=None):
    # Retrieve cookie
    cookie_jar = requests.cookies.RequestsCookieJar()
    with open(config.rel('cookie.txt')) as f:
        value = f.readline().strip()
        csrf = f.readline().strip()
    cookie_jar.set(name="SESSDATA", value=value)
    cookie_jar.set(name="bili_jct", value=csrf)

    if bv is None:
        bv = config.AvBvConverter.enc(av)
    if av is None:
        av = config.AvBvConverter.dec(bv)
    # Construct and encode data
    value = {'rid': av, 'type': 2, 'add_media_ids': fav, 'del_media_ids': '', 'jsonp': 'jsonp', 'csrf': csrf}
    length = len(parse.urlencode(value))
    print('length: ' + str(length))
    headers = copy(config.headers)
    headers['Content-Length'] = str(length)
    headers['Host'] = 'api.bilibili.com'
    headers['Referer'] = f'https://www.bilibili.com/video/{bv}'

    # Send request
    loop = asyncio.get_event_loop()
    url = await loop.run_in_executor(None, functools.partial(requests.post,
        'https://api.bilibili.com/x/v3/fav/resource/deal',
        data=value, cookies=cookie_jar, headers=headers))
    return url.text

# ws_connected: Optional[Websocket] = None
# from quart import app
# @websocket('/ws/thwiki')
# async def thwiki_communicate():
#     global ws_connected
#     if ws_connected is None:
#         ws_connected = websocket._get_current_object()
#     msg = await websocket.receive()
#     await websocket.send(msg)
# get_bot()._server_app.add_websocket('/ws/thwiki', strict_slashes=False, view_func=thwiki_communicate)
# await ws_connected.send('begin')

# Handler for '-thwiki.apply'
@on_command(('thwiki', 'apply'), aliases=('申请',), only_to_me=False, short_des='申请直播时段。', args=('begintime', 'endtime', 'title'), environment=env)
@config.maintain('thwiki')
@config.ErrorHandle(config.logger.thwiki)
async def thwiki_apply(session: CommandSession):
    """申请直播时段。只能在直播群内使用。
    时间格式：x年x月x日x点x分或者xx:xx，今日或今年可以省。开始可以用now，结束可以用float。可使用30小时制。
    例：-thwiki.apply 19:00 21:00 东方STG"""
    global l
    
    begin = session.get('begin')
    end = session.get('end')
    float_end = session.get('float_end')
    qq = session.get('qq')
    card = session.get('card')
    name = session.get('name')
    tz = session.get('tz')

    # Check if the applicant is in the blacklist
    if qq in blacklist:
        return
    
    # Do argument check and generates the Event object
    try:
        now = datetime.now()
        if begin == False or (float_end == False and end == False):
            raise ApplyErr('时间格式不正确，请在 -thwiki.apply 开始时间 结束时间 名字\n的时间处使用正则'
            '(\\d+年)?(\\d+月)?(\\d+(日|号))?'
            '(' '(\\d+(时|点))' '(\\d+分)?' '|' '\\d+:\\d+' ')，且保证时间有效'
            '\n开始可用now，结束可用float')
        elif not float_end and begin >= end:
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
        # An invalid argument takes place
        session.finish(err.args[0])
    e = Event(begin, end, qq, card, name, float_end)

    # Time overlapping check
    for i in l:
        if i.overlap(e):
            session.finish('这个时间段已经有人了\n' + (str(i) if tz is None else f"时区：{tz.tzname(datetime.now())}\n{i.str_tz(tz)}"), auto_escape=True)
    
    # Append current event to the list and sort
    l.append(e)
    l.sort(key=lambda x: x.begin)
    config.logger.thwiki << f'【LOG】用户{qq}成功申请：{e}'
    
    check = find_or_new(qq=qq)
    await session.send(f'成功申请，id为{e.id}，您还在试用期，请等待管理员监视，敬请谅解w' if check['trail'] else f'成功申请，id为{e.id}')
    
    # Try to change description in livestream room
    ret = await change_des_to_list()
    if json.loads(ret)['code'] != 0:
        config.logger.thwiki << '【LOG】更新到直播间失败'
        await session.send('更新到直播间失败')

    # Send notification to supervisors
    if check['trail']:
        for group in config.group_id_dict['thwiki_supervise']:
            msg_id = (await get_bot().send_group_msg(group_id=group, message=f'{e}\n等待管理员监视'))['message_id']
        e.msg_id = msg_id
    
    # Save new application list
    await _save(l)

# Argument interpretor for '-thwiki.apply'
@thwiki_apply.args_parser
@config.ErrorHandle(config.logger.thwiki)
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

    # Read two times using dirty regex tricks
    i = session.current_arg_text.find(' ')
    time_begin = session.current_arg_text[:i]
    j = session.current_arg_text.find(' ', i + 1)
    if j == -1:
        time_end = session.current_arg_text[i + 1:]
        session.args['name'] = ""
    else:
        time_end = session.current_arg_text[i + 1:j]
        session.args['name'] = session.current_arg_text[j + 1:]
    r = re.compile('(?:' '(?:' '(?:(\\d+)年)?' '(?:(\\d+)月)?' '(?:(\\d+)(?:日|号))?' '|(明|后)(?:天|日))'
        '(?:' '(?:(\\d+)(?:时|点))' '(?:(\\d+)分)?' '|' '(\\d+)(?::|：)(\\d+)' '))|(now)|(float)')
    m_begin = re.match(r, time_begin)
    m_end = re.match(r, time_end)
    if m_begin is None:
        session.args['begin'] = False
        session.args['end'] = False
        return
    else:
        year, month, day, special, hours1, minute1, hours2, minute2, _now, _float = m_begin.groups()
        if _now is not None:
            session.args['begin'] = datetime.now()
            year = now.year
            month = now.month
            day = now.day
        elif _float is not None:
            session.args['begin'] = False
        else:
            hours = hours1 if hours1 is not None else hours2
            minute = minute1 if minute1 is not None else minute2
            if special == '明':
                temp_time = now + timedelta(days=1)
            elif special == '后':
                temp_time = now + timedelta(days=2)
            else:
                temp_time = now
            year = _default(year, temp_time.year)
            month = _default(month, temp_time.month)
            day = _default(day, temp_time.day)
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
        year_end, month_end, day_end, special_end, hours1, minute1, hours2, minute2, _now, _float = m_end.groups()
        if _now is not None:
            session.args['end'] = False
        elif _float is not None:
            session.args['end'] = False
            session.args['float_end'] = True
        else:
            hours = hours1 if hours1 is not None else hours2
            minute = minute1 if minute1 is not None else minute2
            if special_end == '明':
                temp_time = now + timedelta(days=1)
                year = _default(year_end, temp_time.year)
                month = _default(month_end, temp_time.month)
                day = _default(day_end, temp_time.day)
            elif special_end == '后':
                temp_time = now + timedelta(days=2)
                year = _default(year_end, temp_time.year)
                month = _default(month_end, temp_time.month)
                day = _default(day_end, temp_time.day)
            else:
                year = _default(year_end, year)
                month = _default(month_end, month)
                day = _default(day_end, day)
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

# Handler for '-thwiki.cancel'
@on_command(('thwiki', 'cancel'), aliases=('取消',), only_to_me=False, short_des='删除直播申请。', args=('id|title'), environment=env)
@config.maintain('thwiki')
@config.ErrorHandle(config.logger.thwiki)
async def thwiki_cancel(session: CommandSession):
    """删除直播申请。只能在直播群内使用。"""
    global l
    
    # Considerations on editing this piece:
    #   If an non-admin user is in the blacklist, their cancel command can still be parsed 
    #   as they can remove their undeleted applications and do no harm since authority 
    #   check takes place 
    #if int(session.ctx['user_id']) in blacklist:
    #   return

    # Find the corresponding application, ID has lower priority than name 
    l2 = more_itertools.only([x for x in enumerate(l) if x[1].name == session.current_arg_text])
    if l2 is None:
        l2 = more_itertools.only([x for x in enumerate(l) if str(x[1].id) == session.current_arg_text.strip()])
        if l2 is None:
            session.finish('未找到')

    # Check for authority
    i = l2[0]
    uqq = int(session.ctx['user_id'])
    node = find_or_new(qq=uqq)
    if uqq == l[i].qq or 'supervisor' in node and node['supervisor']:
    #        await permission.check_permission(get_bot(), session.ctx, permission.GROUP_ADMIN):
        now = datetime.now()
        e = l.pop(i)
        config.logger.thwiki << f"【LOG】用户{session.ctx['user_id']} 成功删除：{e}"
        
        lunbo = False
        # In this case, a shutdown of room should be performed...?
        if e.supervise != 0 and e.begin < now:
            d = int((now - e.begin).total_seconds() - 1) // 60 + 1
            if e.supervise > 0:
                add_supervise_time(e.supervise, d)
            if add_time(e.qq, d):
                await session.send('您已成功通过试用期转正！')
            lunbo = True

        if e.msg_id != -1:
            config.logger.thwiki << f"【LOG】撤回消息：{e.msg_id}"
            try:
                await get_bot().delete_msg(message_id=e.msg_id)
            except aiocqhttp.exceptions.ActionFailed:
                pass

        await _save(l)
        await session.send('成功删除')

        ret = await change_des_to_list(lunbo=lunbo)
        if json.loads(ret)['code'] != 0:
            config.logger.thwiki << '【LOG】更新到直播间失败'
            await session.send('更新到直播间失败')
        ret = await change(area=33)
        if json.loads(ret)['code'] != 0:
            for id in config.group_id_dict['thwiki_send']:
                await get_bot().send_group_msg(group_id=id, message='轮播分区修改失败')
    else:
        await session.send('非管理员不可删除')

# Handler for '-thwiki.list'
@on_command(('thwiki', 'list'), only_to_me=False, short_des='显示预定直播列表。', args=('["all"]',))
@config.maintain('thwiki')
@config.ErrorHandle(config.logger.thwiki)
async def thwiki_list(session: CommandSession):
    """显示预定直播列表。
    默认显示五天以内的直播申请。若参数为"all"则列出全部。"""
    if_all = session.current_arg_text == 'all'
    global l

    if len(l) == 0:
        await session.send('列表为空')
    else:
        qq = session.ctx['user_id']
        node = find_or_new(qq=qq)

        # Check if there a set timezone
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

# Handler for '-thwiki.listall', equivalent to '-thwiki.listall'
@on_command(('thwiki', 'listall'), only_to_me=False, short_des='显示全部预定直播列表。', args=('["all"]'), hide=True)
@config.maintain('thwiki')
@config.ErrorHandle(config.logger.thwiki)
async def thwiki_listall(session: CommandSession):
    await call_command(get_bot(), session.ctx, ('thwiki', 'list'), current_arg = "all")

# Handler for '-thwiki.term'
@on_command(('thwiki', 'term'), only_to_me=False, short_des='提前终止直播，进入轮播。', environment=env)
@config.maintain('thwiki')
@config.ErrorHandle(config.logger.thwiki)
async def thwiki_term(session: CommandSession):
    '''提前终止直播。只能在直播群内使用。'''
    global l

    # Considerations on editing this piece:
    #   If an non-admin user is in the blacklist, their term command can still be parsed 
    #   as they can remove their undeleted applications and do no harm since authority 
    #   check takes place 
    #if int(session.ctx['user_id']) in blacklist:
    #   return

    now = datetime.now()
    if len(l) == 0:
        session.finish('现在未在播')
    if now < l[0].begin:
        session.finish('现在未在播')
    if l[0].qq != session.ctx['user_id']:
        session.finish('现在不是你在播')
    e = l.pop(0)
    s = ""
    if e.supervise != 0:
        d = int((now - e.begin).total_seconds() - 1) // 60 + 1
        if e.supervise > 0:
            add_supervise_time(e.supervise, d)
        if add_time(e.qq, d):
            await session.send('您已成功通过试用期转正！')
        s = f"，已为您累积直播时间{d}分钟"
    await _save(l)

    # ret = await th_open(is_open=False)
    # if json.loads(ret)['code'] != 0:
    #     config.logger.thwiki << '【LOG】断流失败'
    #     await session.send('成功删除，断流失败' + s)
    # else:
    #     await session.send('成功断流' + s)
    await session.send('已终止，请您将obs断流，将开始空闲时间轮播。')
    ret = await change(title='【东方】轮播中')
    if json.loads(ret)['code'] != 0:
        config.logger.thwiki << f'【LOG】修改标题失败{ret}'
        await session.send('修改标题失败', auto_escape=True)

    ret = await change_des_to_list(lunbo=True)
    if json.loads(ret)['code'] != 0:
        await session.send('更新到直播间失败')
    ret = await change(area=33)
    if json.loads(ret)['code'] != 0:
        for id in config.group_id_dict['thwiki_send']:
            await get_bot().send_group_msg(group_id=id, message='轮播分区修改失败')

# Handler for '-thwiki.terminate', equivalent to '-thwiki.term'
@on_command(('thwiki', 'terminate'), only_to_me=False, short_des='提前终止直播，进入轮播。', environment=env, hide=True)
@config.maintain('thwiki')
@config.ErrorHandle(config.logger.thwiki)
async def thwiki_terminate(session: CommandSession):
    """提前终止直播。只能在直播群内使用。"""
    await call_command(get_bot(), session.ctx, ('thwiki', 'term'), current_arg = "")

@scheduler.scheduled_job('cron', id="thwiki_daily", hour='00')
@config.maintain('thwiki')
async def _():
    global l
    await _save(l)
    ret = await change_des_to_list()
    if json.loads(ret)['code'] != 0:
        for id in config.group_id_dict['thwiki_send']:
            await get_bot().send_group_msg(group_id=id, message='直播间简介更新失败')
    for r in whiteforest:
        r['card'] = await get_card(r['qq'])
    save_whiteforest()

    global record_file
    record_file.close()
    record_file = open(config.rel(r'log\thwiki_record.txt'), encoding='utf-8')
    try:
        yesterday = datetime.now() - timedelta(hours=24)
        _l = filter(lambda x: x is not None and x.time >= yesterday, load_record(record_file.readlines()))
    except Exception:
        record_file.close()
        record_file = open(config.rel(r'log\thwiki_record.txt'), 'a', encoding='utf-8')
        for group in config.group_id_dict['log']:
            group.send_group_msg(message='thwiki record delete failed', group_id=group)
        raise
    else:
        record_file.close()
        record_file = open(config.rel(r'log\thwiki_record.txt'), 'w', encoding='utf-8')
        record_file.write('\n'.join([str(r) for r in _l]))

@scheduler.scheduled_job('cron', id="thwiki_minute", second='00')
@config.maintain('thwiki')
async def _():
    global l
    now = datetime.now()
    bot = get_bot()
    for i, e in enumerate(l):
        if e.begin < now + timedelta(seconds=1) and not e.has_alarmed:
            e.has_alarmed = True
            await _save(l)
            for id in config.group_id_dict['thwiki_send']:
                await bot.send_group_msg(group_id=id, message=e.output_with_at())
            ret = await change(title=('【东方】' if '【东方】' not in e.name else '') + e.name)
            if json.loads(ret)['code'] != 0:
                for id in config.group_id_dict['thwiki_send']:
                    await bot.send_group_msg(group_id=id, message='直播间标题修改失败')
            ret = await change_des_to_list()
            if json.loads(ret)['code'] != 0:
                for id in config.group_id_dict['thwiki_send']:
                    await bot.send_group_msg(group_id=id, message='直播间简介更新失败')
            if e.supervise > 0:
                for id in config.group_id_dict['thwiki_supervise']:
                    await bot.send_group_msg(group_id=id, message=[config.cq.at(e.supervise), config.cq.text('\n内容: %s\n请监视者就位' % e.name)])
        elif e.begin + timedelta(minutes=TIME_OUT) < now + timedelta(seconds=1) and e.supervise == 0 and (e.isFloat or now + timedelta(seconds=1) < e.end):
            l.pop(i)
            for id in config.group_id_dict['thwiki_send']:
                await bot.send_group_msg(group_id=id, message=[config.cq.at(e.qq), config.cq.text('您的直播无人监视，已被自动取消')])
            await _save(l)
            return
    for i, e in enumerate(l):
        if e.isFloat and i != len(l) - 1 and l[i + 1].begin < now + timedelta(seconds=1) or not e.isFloat and e.end < now + timedelta(seconds=1):
            d = int(((l[i + 1].begin if e.isFloat else e.end) - e.begin).total_seconds() - 1) // 60 + 1
            l.pop(i)
            if e.supervise != 0:
                if e.supervise > 0:
                    add_supervise_time(e.supervise, d)
                if add_time(e.qq, d):
                    for id in config.group_id_dict['thwiki_send']:
                        await bot.send_group_msg(group_id=id, message=[config.cq.at(e.qq), config.cq.text('已成功通过试用期转正！')], auto_escape=True)
                await _save(l)
                for id in config.group_id_dict['thwiki_send']:
                    await bot.send_group_msg(group_id=id, message=[config.cq.text("已为"), config.cq.at(e.qq), config.cq.text(f"累积直播时间{d}分钟")], auto_escape=True)
                ret = await change_des_to_list(lunbo=True)
                if json.loads(ret)['code'] != 0:
                    for id in config.group_id_dict['thwiki_send']:
                        await bot.send_group_msg(group_id=id, message='直播间简介更新失败')
                ret = await change(area=33)
                if json.loads(ret)['code'] != 0:
                    for id in config.group_id_dict['thwiki_send']:
                        await bot.send_group_msg(group_id=id, message='轮播分区修改失败')
            break

# Handler for command '-thwiki.check'
@on_command(('thwiki', 'check'), only_to_me=False, short_des='查询THBWiki的Bilibili账户当前直播状态。')
@config.maintain('thwiki')
@config.ErrorHandle(config.logger.thwiki)
async def thwiki_check(session: CommandSession):
    """查询THBWiki的Bilibili账户当前直播状态。"""
    # Query Bilibili livestream room
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

# Handler for command '-thwiki.get'
@on_command(('thwiki', 'get'), only_to_me=False, short_des="获取推流码，开启直播间。", args=("[area=单机·其他]",), environment=env)
@config.maintain('thwiki')
@config.ErrorHandle(config.logger.thwiki)
async def thwiki_get(session: CommandSession):
    """获取rtmp与流密码，会以私聊形式发送。只能在直播群内使用。
    只能在自己申请的时段内使用。管理员可随时使用。若直播间未开启则会自动开启。
    可选参数为想开启或修改至的直播分区：
    东方大战争，户外，绘画，手游，网游，vtb，配音，唱见，视频唱见。默认为单机·其他。"""
    # Check permission
    now = datetime.now()
    qq = int(session.ctx['user_id'])
    if qq in blacklist:
        return

    # Considerations: as admins still need the confirmation message when they are livestreaming,
    #   the check priority is reversed
    # async def _():
    #   if await permission.check_permission(get_bot(), session.ctx, permission.GROUP_ADMIN):
    #       return True, None
    #   for i, e in enumerate(l):
    #       if e.isFloat:
    #           if i == len(l) - 1:
    #               b = True
    #           else:
    #               b = now < l[i + 1].begin + timedelta(minutes = 15)
    #       else:
    #           b = now < e.end + timedelta(minutes = 15)
    #       if qq == e.qq and b and e.begin - timedelta(minutes = 15) < now:
    #           return (e.supervise != 0), e
    #   return False, None

    async def _():
        for i, e in enumerate(l):
            if e.isFloat:
                if i == len(l) - 1:
                    b = True
                else:
                    b = now < l[i + 1].begin + timedelta(minutes = 15)
            else:
                b = now < e.end + timedelta(minutes = 15)
            if qq == e.qq and b and e.begin - timedelta(minutes = 15) < now:
                return (e.supervise != 0), e
        
        if await permission.check_permission(get_bot(), session.ctx, permission.GROUP_ADMIN):
            return True, None

        return False, None

    r = await _()
    if not r[0]:
        config.logger.thwiki << f'【LOG】用户{qq} ' + ('于申请时间外get' if r[1] != 0 else '无监视员get') + '失败'
        session.finish('请在您预约的时间段前后十五分钟内申请获取rtmp' if r[1] != 0 else '十分抱歉，您现在的直播尚无监视员，无法直播qwq')

    # Retrieve cookie
    cookie_jar = requests.cookies.RequestsCookieJar()
    with open(config.rel('cookie.txt')) as f:
        value = f.readline().strip()
        csrf = f.readline().strip()
        rtmp = f.readline().strip()
        key = f.readline().strip()
    cookie_jar.set(name="SESSDATA", value=value)

    # Retrieve RTMP and Key
    loop = asyncio.get_event_loop()
    url = await loop.run_in_executor(None, functools.partial(requests.get,
        'http://api.live.bilibili.com/live_stream/v1/StreamList/get_stream_by_roomId?room_id=14055253',
        cookies=cookie_jar))
    response = json.loads(url.text)
    if response['code'] != 0:
        config.logger.thwiki << f'【LOG】用户{qq} get 无法获取rtmp与key'
        await session.send([config.cq.text('无法获取rtmp与key，已将缓存数据发送，如无法推流请联系'),
            config.cq.at('1569603950'), config.cq.text('更新')])
        await session.send('rtmp:\n%s\nkey:\n%s' % (rtmp, key), ensure_private=True, auto_escape=True)
    else:
        rtmp = response['data']['rtmp']
        strout = 'rtmp:\n%s\nkey:\n%s' % (rtmp['addr'], rtmp['code'])
        config.logger.thwiki << f'【LOG】用户{qq} 成功get'
        await session.send(strout, ensure_private=True, auto_escape=True)
        with open(config.rel('cookie.txt'), 'w') as f:
            f.write(value + '\n')
            f.write(csrf + '\n')
            f.write(rtmp['addr'] + '\n')
            f.write(rtmp['code'] + '\n')

    # Check if the livestream room is already open
    url2 = await loop.run_in_executor(None, requests.get, 'https://api.live.bilibili.com/room/v1/Room/room_init?id=14055253')
    areas = {'': 235, '单机·其他': 235, '单机·其他单机': 235, '户外': 368, '生活·户外': 368, '手游': 98, '手游·其他': 98, '手游·其他手游': 98, '网游': 107, '网游·其他': 107, '网游·其他网游': 107, '虚拟主播': 371, 'vtb': 371, '虚拟主播·虚拟主播': 371, '绘画': 373, '学习·绘画': 373, '唱见': 190, '唱见电台': 190, '电台·唱见电台': 190, '东方大战争': 319, '大战争': 319, '视频唱见': 21, '娱乐·视频唱见': 21, '配音': 193, '电台·配音': 193}
    areas_rev = {235: '单机·其他', 368: '生活·户外', 371: '虚拟主播·虚拟主播', 98: '手游·其他', 107: '网游·其他', 373: '学习：绘画', 190: '电台·唱见电台', 319: '单机·东方大战争', 21: '娱乐·视频唱见', 193: '电台·配音'}
    if url2.json()['data']['live_status'] == 1:
        # Categorize
        try:
            area = areas[session.current_arg_text]
        except:
            await session.send('不支持分区：%s，自动转至单机·其他' % session.current_arg_text, auto_escape=True)
            area = 235
        ret = await change(area=area)
        if json.loads(ret)['code'] != 0:
            config.logger.thwiki << '【LOG】直播间分区修改失败'
            await session.send(f'直播间分区修改失败', auto_escape=True)
        else:
            fenqu = areas_rev[area]
            config.logger.thwiki << f'【LOG】用户{qq}修改分区至{fenqu}'
            await session.send(f'已修改直播间分区至{fenqu}', auto_escape=True)
    else:
        # Categorize
        try:
            area = areas[session.current_arg_text]
        except:
            await session.send('不支持分区：%s，自动转至单机·其他' % session.current_arg_text, auto_escape=True)
            area = 235

        # Send title information
        if r[1] is not None:
            t = r[1].name
            if '东方' not in t:
                t = '【东方】' + t
            ret = await change(title=t)
            if json.loads(ret)['code'] != 0:
                config.logger.thwiki << '【LOG】直播间标题修改失败'
                await session.send(f'直播间标题修改失败', auto_escape=True)

        # Send request
        ret = await th_open(area=area)
        if json.loads(ret)['code'] == 0:
            fenqu = areas_rev[area]
            config.logger.thwiki << f'【LOG】用户{qq} 开启直播间，分区：{fenqu}'
            await session.send('检测到直播间未开启，现已开启，分区：%s' % fenqu
                )
        else:
            config.logger.thwiki << f'【LOG】用户{qq} 开启直播间失败'
            await session.send('检测到直播间未开启，开启直播间失败')

# Handler for '-thwiki.grant'
@on_command(('thwiki', 'grant'), only_to_me=False, short_des="推荐别人进入推荐列表。", args=("[@'s]", '["False"]'), environment=env)
@config.maintain('thwiki')
@config.ErrorHandle(config.logger.thwiki)
async def thwiki_grant(session: CommandSession):
    """推荐别人进入推荐列表。需要被推荐人同意。只能在直播群内使用。
    参数为@群里的人。如参数给False则意为撤回推荐。
    撤回推荐会一同撤回被推荐人推荐的所有人。
    推荐需要获得推荐权。获得推荐权的方法是申请加入“THBWiki直播审核群”。群号请在直播群公告里寻找。"""
    # Check for permission
    sqq = session.ctx['user_id']
    node = find_whiteforest(qq=sqq)
    if node is None or node['trail'] == 1 or 'supervisor' not in node or not node['supervisor']:
        session.finish("您没有推荐权，无法推荐")
    elif sqq in weak_blacklist:
        session.finish("您不可推荐他人")

    # Construct list of QQ ID from @s
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
        session.finish('没有@人')

    # Consideration: what would happen if someone types '-thwiki.grant @A @B false @C @D?
    # s = session.current_arg[session.current_arg.rfind(' ') + 1:]
    # if s == 'false' or s == 'False' or s == 'f' or s == 'F':
    arguments = session.current_arg.split(' ')
    flag = False
    for arg in arguments:
        if arg == 'false' or arg == 'False' or arg == 'f' or arg == 'F':
            flag = True

    if flag:
        not_update = []
        partial_updated = []
        partial_failed = []
        updated = []
        updated_qq = []
        updated_event = []
        for qq in qqs:
            node_c = find_whiteforest(qq=qq)
            # Bugfix at here must be checked!!
            if node_c is None:
                config.logger.thwiki << f'【LOG】用户{sqq} 撤回推荐{qq} 因未被推荐或不存在 失败'
                partial_failed.append(config.cq.at(qq))
            elif node_c['parent'] != node['id']:
                config.logger.thwiki << f'【LOG】用户{sqq} 撤回推荐{qq} 因不是您推荐的用户 失败'
                not_update.append(config.cq.at(node_c['qq']))
            elif node_c['trail'] == 1:
                config.logger.thwiki << f'【LOG】用户{sqq} 撤回推荐{qq} 因未被推荐或不存在 失败'
                partial_failed.append(config.cq.at(node_c['qq']))
            else:
                config.logger.thwiki << f'【LOG】用户{sqq} 撤回推荐{qq} 成功'
                node['child'].remove(node_c['id'])
                u, u2 = deprive(node_c, False)
                updated += u
                updated_event += u2
                updated_qq.append(node_c['qq'])
        save_whiteforest()
        for e in updated_event:
            config.logger.thwiki << f'【LOG】事件权限更新：{e}'
            for group in config.group_id_dict['thwiki_supervise']:
                await get_bot().send_group_msg(group_id=group, message=f'{e}\n等待管理员监视')
        await session.send((updated + [config.cq.text(" 已成功退回推荐！试用期直播时间从0开始计算。")] if len(updated) > 0 else []) + ([config.cq.text("\n")] if len(updated) > 0 and len(partial_updated) > 0 else []) + ((partial_updated + [config.cq.text(" 已成功退回推荐！")]) if len(partial_updated) > 0 else []) + ([config.cq.text("\n")] if len(partial_updated) > 0 and len(partial_failed) > 0 else []) + ((partial_failed + [config.cq.text(" 未被推荐或不存在，删除失败")]) if len(partial_failed) > 0 else []) + ([config.cq.text("\n")] if len(partial_failed) > 0 and len(not_update) > 0 else []) + ((not_update + [config.cq.text(" 不是您推荐的用户，删除失败")]) if len(not_update) > 0 else []), auto_escape=True)
    else:
        not_update = []
        update_failed = []
        updated = []
        updated_qq = []
        to_card = []
        for qq in qqs:
            ret_c = find_or_new(qq)
            if not ret_c['trail']:
                if ret_c['card'] is None:
                    to_card.append(ret_c)
                config.logger.thwiki << f"【LOG】用户{sqq} 推荐{qq} 因是已推荐用户 失败"
                not_update.append(config.cq.at(ret_c['qq']))
            elif qq in blacklist or qq in weak_blacklist:
                config.logger.thwiki << f"【LOG】用户{sqq} 推荐{qq} 因不可被推荐 失败"
                update_failed.append(config.cq.at(ret_c['qq']))
            else:
                if ret_c['card'] is None:
                    to_card.append(ret_c)
                ret_c['parent'] = node['id']
                ret_c['child'] = []	
                ret_c['trail'] = 0	
                node['child'].append(ret_c['id'])
                config.logger.thwiki << f"【LOG】用户{sqq} 推荐{qq} 成功"
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
        await session.send(updated + ([config.cq.text(" 已成功推荐！")] if len(updated) > 0 else []) + ([config.cq.text("\n")] if len(updated) > 0 and len(not_update) > 0 else []) + ((not_update + [config.cq.text(" 是已推荐用户，推荐失败")]) if len(not_update) > 0 else []) + ([config.cq.text("\n")] if len(not_update) > 0 and len(update_failed) > 0 else []) + ((update_failed + [config.cq.text(" 不可被推荐，推荐失败")]) if len(update_failed) > 0 else []), auto_escape=True)

# Handler for command '-thwiki.depart'
@on_command(('thwiki', 'depart'), only_to_me=False, short_des="从推荐树中安全脱离。", environment=env)
@config.maintain('thwiki')
@config.ErrorHandle(config.logger.thwiki)
async def thwiki_depart(session: CommandSession):
    """从推荐树中安全脱离。只能在直播群内使用。"""
    qq = session.ctx['user_id']
    node = find_whiteforest(qq=qq)
    if node is None or node['trail'] == 1:
        session.finish("您还处在试用期，无需脱离")
    elif node['parent'] == -1:
        session.finish("您已超过试用期所需时间，无需脱离")
    find_whiteforest(id=node['parent'])['child'].remove(node['id'])
    updated, updated_event = deprive(node, True, False)
    for e in updated_event:
        config.logger.thwiki << f'【LOG】事件权限更新：{e}'
        for group in config.group_id_dict['thwiki_supervise']:
            await get_bot().send_group_msg(group_id=group, message=f'{e}\n等待管理员监视')
    await session.send([config.cq.text('已成功安全脱离')] + updated)

# Handler for command '-thwiki.deprive'
@on_command(('thwiki', 'deprive'), only_to_me=False, short_des="强制退回推荐。", args=("[@'s]",), environment=env_supervise)
@config.maintain('thwiki')
@config.ErrorHandle(config.logger.thwiki)
async def thwiki_deprive(session: CommandSession):
    """强制退回推荐。直播群管理可用。
    参数为@群里的人。"""
    # Construct QQ list from @s
    def _tmp(str):
        begin = 0
        while 1:
            match = re.search('qq=(\\d+)', str[begin:])
            if not match:
                return
            begin += match.span()[1]
            yield int(match.group(1))
    qqs = list(_tmp(str(session.current_arg)))

    if len(qqs) == 0:
        # Consider swap to PM
        session.finish('没有@人')

    global blacklist
    global weak_blacklist
    global whiteforest

    updated = []
    not_updated = []
    updated_event = []

    for qq in qqs:
        if qq not in blacklist:
            node = find_or_new(qq = qq)
            if node['trail'] == 1:
                if node['card'] is None:
                    node['card'] = await get_card(qq)
                # Consider swap to PM
                config.logger.thwiki << f'【LOG】{session.ctx["user_id"]} deprive {qq}失败'
                not_updated.append(config.cq.at(qq))
                #return
            else:
                node_parent = find_whiteforest(id = node['parent'])
                if node_parent is not None:
                    node_parent['child'].remove(node['id'])
                u, u2 = deprive(node)
                updated += u
                updated_event += u2
            if qq not in weak_blacklist:
                config.logger.thwiki << f'【LOG】{qq}加入weak_blacklist'
                weak_blacklist.append(qq)
    
    save_whiteforest()
    # Save weak blacklist
    with open(config.rel('thwiki_weak_blacklist.txt'), 'w') as f:
        for qq in weak_blacklist:
            f.write(str(qq))
            f.write('\n')

    for e in updated_event:
        config.logger.thwiki << f'【LOG】事件权限更新：{e}'
        for group in config.group_id_dict['thwiki_supervise']:
            await get_bot().send_group_msg(group_id=group, message=f'{e}\n等待管理员监视')

    # Quite unsure for grammar here
    await session.send((([config.cq.text('已成功剥夺')] + updated + [config.cq.text('直播权限并加至不可推荐列表')]) if len(updated) > 0 else []) + (([config.cq.text('\n')]) if len(updated) > 0 and len(not_updated) > 0 else []) + ((not_updated + config.cq.text(' 没有直播权限，剥夺失败！')) if len(not_updated) > 0 else []))

# Handler for command '-thwiki.supervise'
@on_command(('thwiki', 'supervise'), only_to_me=False, short_des="提交或取消监视。", args=("id", '["False"]'), environment=env_supervise)
@config.maintain('thwiki')
@config.ErrorHandle(config.logger.thwiki)
async def thwiki_supervise(session: CommandSession):
    """提交或取消监视。监视群可用。
    参数为直播申请的id号。若参数给False则为取消监视。"""

    # Check argument validity
    qq = session.ctx['user_id']
    i = session.current_arg_text.split(' ')
    if len(i) == 1:
        id = int(i[0])
        t = True
    elif len(i) == 2:
        id = int(i[0])
        t = not (i[1] == 'false' or i[1] == 'False' or i[1] == 'f' or i[1] == 'F')
    else:
        session.finish('使用-thwiki.supervise 直播id [可选：True/False]')

    ret = more_itertools.only([x for x in l if x.id == id])
    if ret is None:
        await session.send('未发现此id的直播提交')
    elif ret.supervise == -1:
        await session.send('此直播提交者已有权限')
    elif ret.supervise > 0 and t:
        await session.send('此直播提交已有监视者')
    elif ret.supervise != qq and not t:
        await session.send('本直播监视人不是您，删除失败')
    else:
        if t:
            ret.supervise = qq
            if ret.begin < datetime.now():
                ret.begin = datetime.now()
            config.logger.thwiki << f'【LOG】监视者{qq} 已监视事件：{ret}'
            await _save(l)
            await session.send('成功提交监视')
            for group in config.group_id_dict['thwiki_send']:
                await get_bot().send_group_msg(group_id=group, message=ret.str_with_at())
        else:
            ret.supervise = 0
            config.logger.thwiki << f'【LOG】监视者{qq} 已删除监视事件：{ret}'
            await _save(l)
            await session.send('成功删除监视')
            for group in config.group_id_dict['thwiki_send']:
                await get_bot().send_group_msg(group_id=group, message=ret.str_with_at())
        if x.begin < (datetime.now() + timedelta(days = 7)):
            ret = await change_des_to_list()
            if json.loads(ret)['code'] != 0:
                for id in config.group_id_dict['thwiki_supervise']:
                    await get_bot().send_group_msg(group_id=id, message='直播间简介更新失败')

# Handler for command '-thwiki.time'
@on_command(('thwiki', 'time'), only_to_me=False, short_des="查询直播时长（2019年8月至今）。", args=("[@s]",))
@config.maintain('thwiki')
@config.ErrorHandle(config.logger.thwiki)
async def thwiki_time(session: CommandSession):
    """查询直播时长（2019年8月至今）。
    不加参数为查询自己的直播时间。可加参数@别人查询别人的直播时间。"""
    match = re.search('qq=(\d+)', session.current_arg)
    if match:
        qq = int(match.group(1))
    else:
        qq = session.ctx['user_id']
    node = find_or_new(qq = qq)
    if 'time' not in node:
        node['time'] = 0
    await session.send(f'您{"查询的人" if match else ""}的直播总时长为：{node["time"]}分钟。（2019年8月开始）', auto_escape=True)

# Handler for command '-thwiki.timezone'
@on_command(('thwiki', 'timezone'), only_to_me=False, short_des="查询或修改时区。", args=("[UTC+time]", "[@s]"))
@config.maintain('thwiki')
@config.ErrorHandle(config.logger.thwiki)
async def thwiki_timezone(session: CommandSession):
    """查询或修改时区。
    不加参数时，查询自己的时区。参数为@别人时，查询别人的时区。
    参数为UTC时区信息时，修改自己的时区。"""
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
        if tz_new <= -15 or tz_new >= 15:
            session.finish("UTC时区必须在(-15, +15)以内")
    else:
        tz_new = None
    node = find_or_new(qq = qq)
    if tz_new is not None:
        node['timezone'] = tz_new
        config.logger.thwiki << f'【LOG】用户{qq} 已修改时区为{tz_new}'
        await session.send(f"您的时区已修改为{timezone(timedelta(hours=tz_new)).tzname(datetime.today())}")
        save_whiteforest()
    else:
        tz = node.get('timezone', 8)
        await session.send(("您查询的用户" if other else "您") + f"的时区为{timezone(timedelta(hours=tz)).tzname(datetime.today())}")

# Handler for command '-thwiki.grantlist'
@on_command(('thwiki', 'grantlist'), only_to_me=False, short_des="查询推荐树。", environment=env_supervise)
@config.maintain('thwiki')
@config.ErrorHandle(config.logger.thwiki)
async def thwiki_grantlist(session: CommandSession):
    """查询推荐树。监视群可用。"""
    for node in whiteforest:
        if node['card'] is None:
            node['card'] = await get_card(node['qq'])
    await session.send('\n'.join(
        [f"id: {node['id']} qq: {node['qq']} 名片: {node['card']}\nparent id: {node['parent']}" +
            (f" 名片: {find_whiteforest(id=node['parent'])['card']}" if node['parent'] != -1 else '') +
            (f"\nchilds id: {' '.join(map(str, node['child']))}" if 'child' in node and len(node['child']) > 0 else "")
            for node in whiteforest if node['trail'] == 0]
        ), auto_escape=True, ensure_private=True)

# Handler for command '-thwiki.leaderboard'
@on_command(('thwiki', 'leaderboard'), only_to_me=False, short_des="查看直播排行榜。", args="[me]")
@config.maintain('thwiki')
@config.ErrorHandle(config.logger.thwiki)
async def thwiki_leaderboard(session: CommandSession):
    """查看直播排行榜。
    可选参数：me，查询自己排位。"""
    # for node in whiteforest:
    #     if node['card'] is None:
    #         node['card'] = await get_card(node['qq'])
    if session.current_arg_text == "me":
        node = find_or_new(qq=session.ctx['user_id'])
        if 'time' not in node:
            node['time'] = 0
        al = list(sorted(whiteforest, key=lambda node: ((0 if 'time' not in node else -node['time']), str(node['card']))))
        index = al.index(node)
        print(index)
        await session.send('\n'.join([f"{i + 1} 直播时长：{al[i]['time']}min 用户：{al[i]['card']} {al[i]['qq']}"
            for i in range(max(0, index - 2), min(len(al) - 1, index + 3))]), auto_escape=True)
        return
    _max = 10
    await session.send('\n'.join([f"{i + 1} 直播时长：{node['time']}min 用户：{node['card']} {node['qq']}"
        for i, node in enumerate(more_itertools.take(_max, sorted(whiteforest,
            key=lambda node: (0 if 'time' not in node else node['time']), reverse=True
        )))]), auto_escape=True)

# Handler for command '-thwiki.open'
@on_command(('thwiki', 'open'), only_to_me=False, permission=permission.SUPERUSER, hide=True)
@config.ErrorHandle(config.logger.thwiki)
async def thwiki_open(session: CommandSession):
    ret = await th_open()
    if json.loads(ret)['code'] != 0:
        await session.send('开启直播失败')
    else:
        await session.send('成功开启直播')

# Handler for command '-thwiki.change'
@on_command(('thwiki', 'change'), only_to_me=False, short_des='修改直播间标题。', args=("title",), environment=env)
@config.maintain('thwiki')
@config.ErrorHandle(config.logger.thwiki)
async def thwiki_change(session: CommandSession):
    """修改直播间标题。只能在直播群内使用。"""
   
    # Check permission
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
                return (e.supervise != 0), e # Unused return value??
        return False, None
    r = await _()
    if not r[0]:
        config.logger.thwiki << f'【LOG】用户{qq} ' + ('于申请时间外get' if r[1] != 0 else '无监视员get') + '失败'
        session.finish('请在您预约的时间段前后十五分钟内修改' if r[1] is None or r[1].supervise != 0 else '十分抱歉，您现在的直播尚无监视员，无法直播qwq')
    t = session.current_arg_text.strip()
    if t == "":
        session.finish('请填写您要修改的标题')
    if r[1] is not None:
        r[1].name = t
    if '东方' not in t:
        t = '【东方】' + t
    ret = await change(title=t)
    config.logger.thwiki << f'【LOG】用户{qq} 修改标题至"{t}"'
    if json.loads(ret)['code'] == 0:
        await session.send(f'成功修改标题至"{t}"', auto_escape=True)
    else:
        config.logger.thwiki << f'【LOG】修改标题失败{ret}'
        await session.send(ret, auto_escape=True)

# Handler for command '-thwiki.version'
# This is almost useless to normal users, add permission requirement?
@on_command(('thwiki', 'version'), only_to_me=False, short_des="查看直播小助手版本。", args=("[-c]",))
@config.maintain('thwiki')
@config.ErrorHandle(config.logger.thwiki)
async def thwiki_version(session: CommandSession):
    """查看直播小助手版本。
    可选参数：
    -c：一并输出Changelog。"""
    if session.current_arg_text == '-c':
        await session.send(f"七海千春 THBWiki 直播小助手 ver.{version} 为您服务\n{changelog}")
    else:
        await session.send(f"七海千春 THBWiki 直播小助手 ver.{version} 为您服务")

# Handler for command '-thwiki.des'
@on_command(('thwiki', 'des'), only_to_me=False, permission=permission.SUPERUSER, hide=True)
@config.ErrorHandle(config.logger.thwiki)
async def thwiki_changedes(session: CommandSession):
    ret = await change(description=session.current_arg_text)
    await session.send(ret, auto_escape=True)

# Handler for command '-thwiki.maintain'
@on_command(('thwiki', 'maintain'), only_to_me=False, short_des="开启或关闭维护状态。", args="[description]", environment=env_supervise)
@config.ErrorHandle(config.logger.thwiki)
async def thwiki_maintain(session: CommandSession):
    """开启或关闭维护状态。直播群管理或监视群可用。
    参数为空则为关闭维护状态。否则开启维护状态，参数为维护时显示的消息。"""
    config.maintain_str['thwiki'] = session.current_arg_text
    config.maintain_str_save()
    if session.current_arg_text != "":
        await th_open(is_open=False)
        config.logger.thwiki << f'【LOG】管理者{session.ctx["user_id"]}开启维护状态：{session.current_arg_text}'
        await session.send('已进入维护状态，再次输入空字符串解除')
    else:
        config.logger.thwiki << f'【LOG】管理者{session.ctx["user_id"]}解除维护状态'
        #if await permission.check_permission(get_bot(), session.ctx, permission.GROUP_OWNER | permission.SUPERUSER):
        await session.send('已解除维护状态')

# Handler for command '-thwiki.shutdown'
@on_command(('thwiki', 'shutdown'), only_to_me=False, short_des="强制关闭直播间。", environment=env_supervise)
@config.ErrorHandle(config.logger.thwiki)
async def thwiki_shutdown(session: CommandSession):
    """强制关闭直播间。直播群管理可用。"""
    qq = session.ctx['user_id']
    node = find_or_new(qq=qq)
    if 'supervisor' in node and node['supervisor']:
        await th_open(is_open=False)
        config.logger.thwiki << f'【LOG】管理者{qq}关闭直播间'
        await session.send('已关闭直播间')

@on_command(('thwiki', 'deduct'), only_to_me=False, short_des="扣除直播时间。", args=("time", "qq", "[\\n desc]"), environment=env_supervise_only)
@config.ErrorHandle(config.logger.thwiki)
async def thwiki_deduct(session: CommandSession):
    """扣除用户直播时间。
    格式为-thwiki.deduct 时间 qq号，并可以换行后加扣除原因。扣除后会在直播群给予用户通知。"""
    qq_text, *els = session.current_arg.split('\n')
    try:
        time_str, qq_str = qq_text.split(' ')
        time = int(time_str)
        qq = int(qq_str)
    except ValueError:
        session.finish("格式为-thwiki.deduct 时间 qq号 换行 扣除原因")
    ret = add_time(qq, -time)
    if ret:
        await session.send('用户已通过试用期转正')
    else:
        await session.send('已成功扣除时间')
    des = '\n'.join(els)
    for group in config.group_id_dict['thwiki_send']:
        await get_bot().send_group_msg(group_id=group, message=[config.cq.at(qq), config.cq.text(f"已{'扣除' if time > 0 else '增加'}您的直播时间{abs(time)}min，理由为：\n{des}")])

# Handler for command '-thwiki.blacklist'
@on_command(('thwiki', 'blacklist'), only_to_me=False, short_des="添加用户至黑名单。", args=("[@s]",), environment=env_supervise)
@config.ErrorHandle(config.logger.thwiki)
async def thwiki_blacklist(session: CommandSession):
    """添加用户至黑名单。直播群管理或监视群可用。"""
    global blacklist
    global weak_blacklist
    global whiteforest
    global l

    # Construct QQ list from @s
    def _tmp(s):
        begin = 0
        while 1:
            match = re.search('qq=(\\d+)', s[begin:])
            if not match:
                return
            begin += match.span()[1]
            yield int(match.group(1))
    qqs = list(_tmp(session.current_arg_text))

    updated_event = []
    for qq in qqs:
        if qq not in blacklist:
            config.logger.thwiki << f'【LOG】管理{session.ctx["user_id"]} 将{qq}加入blacklist'
            blacklist.append(qq)
            node_current = find_or_new(qq = qq)
            u, u2 = deprive(node_current, True, True)
            updated_event += u2
            if qq in weak_blacklist:
                weak_blacklist.pop(qq)

    blacklist.sort()
    weak_blacklist.sort()

    with open(config.rel('thwiki_blacklist.txt'), 'w') as f:
        for qq in blacklist:
            f.write(str(qq))
            f.write('\n')

    with open(config.rel('thwiki_weak_blacklist.txt'), 'w') as f:
        for qq in weak_blacklist:
            f.write(str(qq))
            f.write('\n')
    
    for e in updated_event:
        config.logger.thwiki << f'【LOG】事件权限更新：{e}'
        for group in config.group_id_dict['thwiki_supervise']:
            await get_bot().send_group_msg(group_id=group, message=f'{e}\n等待管理员监视')

    await session.send('已加入黑名单')

# Handler for command '-thwiki.weak_blacklist'
@on_command(('thwiki', 'weak_blacklist'), only_to_me=False, short_des="添加用户至弱黑名单。", args=("[@s]",), environment=env_supervise)
@config.ErrorHandle(config.logger.thwiki)
async def thwiki_weak_blacklist(session: CommandSession):
    """添加用户至弱黑名单。直播群管理或监视群可用。"""
    global blacklist
    global weak_blacklist
    global whiteforest
    global l

    # Construct QQ list from @s
    def _tmp(s):
        begin = 0
        while 1:
            match = re.search('qq=(\\d+)', s[begin:])
            if not match:
                return
            begin += match.span()[1]
            yield int(match.group(1))
    qqs = list(_tmp(session.current_arg))

    updated_event = []
    for qq in qqs:
        if qq not in weak_blacklist:
            if qq in blacklist:
                await session.send('{qq}已在黑名单内，不再被加入弱黑名单')
            else:
                config.logger.thwiki << f'【LOG】管理{session.ctx["user_id"]} 将{qq}加入weak_blacklist'
                weak_blacklist.append(qq)
                node_current = find_or_new(qq = qq)
                u, u2 = deprive(node_current, True, False)
                updated_event += u2

    weak_blacklist.sort()

    with open(config.rel('thwiki_weak_blacklist.txt'), 'w') as f:
        for qq in weak_blacklist:
            f.write(str(qq))
            f.write('\n')

    for e in updated_event:
        config.logger.thwiki << f'【LOG】事件权限更新：{e}'
        for group in config.group_id_dict['thwiki_supervise']:
            await get_bot().send_group_msg(group_id=group, message=f'{e}\n等待管理员监视')

    await session.send('已加入弱黑名单')

@on_command(('thwiki', 'print_blacklist'), only_to_me=False, environment=env_supervise_only)
@config.ErrorHandle(config.logger.thwiki)
async def thwiki_print_blacklist(session: CommandSession):
    """列出黑名单"""
    await session.send('\n'.join((str(find_or_new(i)['card']) + ' ' + str(i)) for i in blacklist))

@on_command(('thwiki', 'print_weak_blacklist'), only_to_me=False, environment=env_supervise_only)
@config.ErrorHandle(config.logger.thwiki)
async def thwiki_print_weak_blacklist(session: CommandSession):
    """列出弱黑名单。"""
    await session.send('\n'.join((str(find_or_new(i)['card']) + ' ' + str(i)) for i in weak_blacklist))

# Handler for command '-thwiki.check_user'
@on_command(('thwiki', 'check_user'), only_to_me=False, short_des="查询直播过的用户数量。", environment=env_supervise)
@config.ErrorHandle(config.logger.thwiki)
async def thwiki_check_user(session: CommandSession):
    """查询直播过的用户数量。直播群管理或监视群可用。"""
    await session.send(str(len([node for node in whiteforest if 'time' in node and node['time'] > 0])))

@on_notice('group_increase')
async def thwiki_greet(session: NoticeSession):
    if session.ctx['group_id'] in config.group_id_dict['thwiki_live']:
        message = ('欢迎来到THBWiki直播群！我是直播小助手，在群里使用指令即可申请直播时间~\n现在群内直播使用推荐，有人推荐可以直接直播，没有推荐的用户直播时需有管理监视，总直播时长36小时之后可以转正。\n不要忘记阅读群文件里的本群须知哦~\n以下为指令列表，欢迎在群里使用与提问~\n' + help.sp['thwiki_live']['thwiki']) % help._dict['thwiki']
        await get_bot().send_private_msg(user_id=session.ctx['user_id'], message=message, auto_escape=True)
    elif session.ctx['group_id'] in config.group_id_dict['thwiki_supervise']:
        node = find_or_new(session.ctx['user_id'])
        node['supervisor'] = True
        save_whiteforest()

@on_notice('group_decrease')
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
        updated, updated_event = deprive(node, True, False)
        node['time'] = 0
        if if_send:
            for group in config.group_id_dict['thwiki_send']:
                await get_bot().send_group_msg(group_id=group, message=[config.cq.text(f"{node['card']} 退群，已自动安全脱离")] + updated)
            for e in updated_event:
                config.logger.thwiki << f'【LOG】事件权限更新：{e}'
                for group in config.group_id_dict['thwiki_supervise']:
                    await get_bot().send_group_msg(group_id=group, message=f'{e}\n等待管理员监视')

@on_command(('thwiki', 'help'), only_to_me=False, hide=True)
@config.ErrorHandle(config.logger.thwiki)
async def thwiki_help(session: CommandSession):
    await call_command(get_bot(), session.ctx, ('help',), current_arg="thwiki")

# Handler for command '-thwiki.cookie'
@on_command(('thwiki', 'cookie'), only_to_me=False, short_des="修改直播cookie。", environment=config.Environment(private=True), hide=True)
@config.ErrorHandle(config.logger.thwiki)
async def thwiki_cookie(session: CommandSession):
    qq = session.ctx['user_id']
    if qq not in config.group_id_dict['thwiki_cookie']:
        return

    try:
        ses, jct = session.current_arg_text.strip().split('\n')
        ses = ses.strip()
        jct = jct.strip()
        if not (re.match('.+%2C.+%2C.+', ses) and re.match('[0-9a-f]+', jct)):
            raise ValueError
    except ValueError:
        session.finish('请用-thwiki.cookie SESSDATA 换行 csrf_token(bili_jct)')
    with open(config.rel('cookie.txt')) as f:
        value = f.readlines()
    value[0] = ses + '\n'
    value[1] = jct + '\n'
    with open(config.rel('cookie.txt'), 'w') as f:
        f.write(''.join(value))
    await session.send('成功写入')

@on_request('group.add')
async def thwiki_group_request(session: RequestSession):
    if session.ctx['group_id'] in config.group_id_dict['thwiki_send']:
        qq = session.ctx["user_id"]
        match = re.search('答案：[^\d]*?(\d+)[^\d]+?(\d+)\s*', session.ctx['comment'])
        if not match:
            for group in config.group_id_dict['thwiki_supervise']:
                await get_bot().send_group_msg(group_id=group, message=f'用户{qq}答案不满足格式')
            return
        user, answer = match.groups()
        if int(user) == config.thwiki_answer:
            user, answer = answer, user
        if int(answer) != config.thwiki_answer:
            await session.reject(reason='答案错误')
            for group in config.group_id_dict['thwiki_supervise']:
                await get_bot().send_group_msg(group_id=group, message=f'用户{qq}答案错误，已拒绝')
        else:
            for group in config.group_id_dict['thwiki_supervise']:
                await get_bot().send_group_msg(group_id=group, message=f'用户{qq}：https://space.bilibili.com/{user}')
            with open(config.rel('thwiki_bilispace.json')) as f:
                a = json.load(f)
            a[str(qq)] = f'https://space.bilibili.com/{user}'
            with open(config.rel('thwiki_bilispace.json'), 'w') as f:
                f.write(json.dumps(a, indent=4, separators=(',', ': ')))
    elif session.ctx['group_id'] in config.group_id_dict['thwiki_supervise']:
        qq = session.ctx["user_id"]
        node = find_or_new(qq)
        message = session.ctx['comment'] or '无'
        if node['card'] is None:
            node['card'] = await get_card(qq)
        with open(config.rel('thwiki_bilispace.json')) as f:
            a = json.load(f)
        c = a[str(qq)] if str(qq) in a else "未记录"
        for group in config.group_id_dict['thwiki_supervise']:
            await get_bot().send_group_msg(group_id=group, message=f'收到审核群加群申请。qq：{qq}，名片：{node["card"]}，直播时间：{node["time"]}min，b站空间：{c}，加群申请信息：{message}')

@message_preprocessor
async def thwiki_record(bot, ctx):
    try:
        if ctx['group_id'] not in config.group_id_dict['thwiki_live']:
            return
    except KeyError:
        return
    r = Record(ctx['user_id'], datetime.now(), ctx['message_id'], ctx['raw_message'])
    record_file.write(str(r) + '\n')
    record_file.flush()

@on_command(('thwiki', 'punish'), only_to_me=False, short_des="惩罚不当发言。", environment=env_supervise)
@config.ErrorHandle(config.logger.thwiki)
async def thwiki_punish(session: CommandSession):
    """惩罚不当发言。
    格式为：-thwiki.punish qq 换行 YYYY-MM-DD HH:MM[:SS] [换行 关键词]
    检索给定时间前后1分钟内距离该时间最近的包含关键词的发言。（可不给关键字）
    如确认，则将该发言撤回，并扣除友善度。友善度上限为5，扣至1或2点则禁言1h，扣至零则踢出。
    并告知友善度剩余几点。"""
    if session.get('confirmed'):
        record = session.get('record')
        if not session.get('deleted'):
            try:
                await get_bot().delete_msg(message_id=record.msg_id)
            except aiocqhttp.exceptions.ActionFailed:
                session.args['confirmed'] = False
                session.pause('消息撤回失败，请联系管理员手动撤回消息后，在此处回复“完毕”，以执行下一步指令。回复返回退出。')
        node = find_or_new(record.qq)
        if 'punish' not in node:
            node['punish'] = session.get('severity')
        else:
            node['punish'] += session.get('severity')
        save_whiteforest()
        group = list(config.group_id_dict['thwiki_punish'])[0]
        if 3 <= node['punish'] < FRIENDLY_MAX:
            await get_bot().set_group_ban(group_id=group, user_id=node['qq'], duration=3600)
        reason = session.get('reason')
        await get_bot().send_group_msg(group_id=group, message=[config.cq.text('管理员认为'), config.cq.at(record.qq), config.cq.text(f'于{record.time.strftime("%H:%M:%S")} CST{node["card"]}作出了不妥当的发言，扣除该群员{session.get("severity")}点友善度' + ('，理由为：' + reason + '\n' if reason else '') + f'剩余{max(0, FRIENDLY_MAX - node["punish"])}友善度' + ('，已移出群聊。' if node['punish'] >= FRIENDLY_MAX else '。'))])
        if node['punish'] >= FRIENDLY_MAX:
            await get_bot().set_group_kick(group_id=group, user_id=node['qq'])
        session.finish('已撤回')
    global record_file
    record_file.close()
    record_file = open(config.rel(r'log\thwiki_record.txt'), encoding='utf-8')
    qq, word, time = session.get('qq'), session.get('word'), session.get('time')
    try:
        if word is None:
            l = [record for record in load_record(record_file.readlines()) if record is not None and abs(record.time - time) < timedelta(minutes=1) and record.qq == qq]
        else:
            l = [record for record in load_record(record_file.readlines()) if record is not None and abs(record.time - time) < timedelta(minutes=1) and record.qq == qq and word in record.msg]
    finally:
        record_file.close()
        record_file = open(config.rel(r'log\thwiki_record.txt'), 'a', encoding='utf-8')
    if len(l) == 0:
        session.finish('未找到消息。')
    session.args['record'] = r = min(l, key=lambda record: abs(record.time - time))
    session.pause(f'消息内容为：{r.msg}，输入“确认 [\\严重等级] [理由]”确认此发言（如：确认 \\1 不要迫害），输入“返回”取消')

@thwiki_punish.args_parser
async def _(session: CommandSession):
    if session.current_arg.startswith('确认'):
        session.args['confirmed'] = True
        session.args['deleted'] = False
        severity, *els = session.current_arg[3:].split(' ')
        if severity.startswith('\\'):
            try:
                session.args['severity'] = int(severity[1:])
            except:
                session.finish('严重等级读取失败，请输入数字。')
            session.args['reason'] = ' '.join(els).strip()
        else:
            session.args['severity'] = 1
            session.args['reason'] = session.current_arg[3:].strip()
        return
    elif session.current_arg == '返回':
        session.finish('已取消')
    elif session.current_arg == '完毕':
        session.args['confirmed'] = True
        session.args['deleted'] = True
        return
    session.args['confirmed'] = False
    l = list(map(str.strip, session.current_arg_text.replace('\r', '').split('\n')))
    if len(l) == 2:
        qq_str, time_str = l
        session.args['word'] = None
    elif len(l) == 3:
        qq_str, time_str, word = l
        session.args['word'] = word.strip()
    else:
        session.finish('格式为：-thwiki.punish qq 换行 YYYY-MM-DD HH:MM[:SS] [换行 关键词]')
    session.args['qq'] = int(qq_str)
    try:
        session.args['time'] = datetime.fromisoformat(time_str)
    except ValueError:
        session.finish('时间不符合格式')

@on_command(('thwiki', 'punish_check'), only_to_me=False, args=('qq=qq号'), environment=env_supervise)
@config.ErrorHandle(config.logger.thwiki)
async def thwiki_punish_check(session: CommandSession):
    "查询用户被惩罚次数。"
    match = re.search('qq=(\d+)', session.current_arg)
    if match:
        qq = int(match.group(1))
    else:
        session.finish('请输入如qq=1569603950')
    def _(qq):
        node = find_or_new(qq)
        if 'punish' not in node:
            return 0
        else:
            return node['punish']
    await session.send(f'此用户友善度剩余{FRIENDLY_MAX - _(qq)}点。')

@on_command(('thwiki', 'kick'), only_to_me=False, short_des="踢出群聊。", environment=env_supervise_only)
@config.ErrorHandle(config.logger.thwiki)
async def thwiki_kick(session: CommandSession):
    qq = int(session.current_arg_text)
    group = list(config.group_id_dict['thwiki_punish'])[0]
    await get_bot().set_group_kick(group_id=group, user_id=qq)
    await session.send('已踢出。')

@on_command(('thwiki', 'bookmark'), only_to_me=False, short_des="将视频加入轮播列表。", environment=env_all_thwiki_live)
@config.ErrorHandle(config.logger.thwiki)
async def thwiki_bookmark(session: CommandSession):
    """提交视频加入轮播列表。
    需经过管理审核。"""
    qq = session.ctx['user_id']
    av = session.get('av')
    bv = session.get('bv')
    if await env_supervise.test(session):
        ret = await add_fav(bv=bv, fav=853928275)
        if json.loads(ret)['code'] == 0:
            config.logger.thwiki << f'【LOG】用户{qq}添加书签{bv}'
            await session.send('成功增加视频')
        else:
            config.logger.thwiki << f'【LOG】用户{qq}添加书签{bv}失败'
            await session.send('视频增加失败')
    else:
        config.logger.thwiki << f'【LOG】用户{qq}提交书签{bv}，待审核'
        for group in config.group_id_dict['thwiki_supervise']:
            await get_bot().send_group_msg(group_id=group, message=f"-thwiki.bookmark {bv}\n用户{qq}试图添加 b23.tv/{bv}，同意请+1，不同意请忽略")
            await get_bot().send_group_msg(group_id=group, message=f"-thwiki.bookmark {bv}\n用户{qq}试图添加 b23.tv/{bv}，同意请+1，不同意请忽略")
        await session.send('已提交，请等待管理审核')

@on_command(('thwiki', 'recommend'), only_to_me=False, environment=env)
@config.ErrorHandle(config.logger.thwiki)
async def thwiki_recommend(session: CommandSession):
    """提交视频加入推荐列表。"""
    qq = session.ctx['user_id']
    av = session.get('av')
    bv = session.get('bv')
    ret = await add_fav(bv=bv, fav=426047475)
    if json.loads(ret)['code'] == 0:
        config.logger.thwiki << f'【LOG】用户{qq}添加推荐{bv}'
        await session.send('成功加入推荐视频列表')
    else:
        config.logger.thwiki << f'【LOG】用户{qq}添加推荐{bv}失败'
        await session.send('推荐视频列表加入失败')

@thwiki_bookmark.args_parser
@thwiki_recommend.args_parser
@config.ErrorHandle(config.logger.thwiki)
async def _(session: CommandSession):
    match = re.match('^av(\d+)', session.current_arg_text)
    if not match:
        match = re.match('^(?:bv|BV)([0-9A-Za-z]+)', session.current_arg_text)
        if not match:
            session.finish('请输入视频av号或BV号。')
        bv = 'BV' + match.group(1)
        av = config.AvBvConverter.dec(bv)
    else:
        av = int(match.group(1))
        bv = config.AvBvConverter.enc(av)
    session.args['av'] = av
    session.args['bv'] = bv

# Handler for command '-thwiki.test'
# Yet another undocumented command...?
@on_command(('thwiki', 'test'), only_to_me=False, permission=permission.SUPERUSER, hide=True)
@config.ErrorHandle(config.logger.thwiki)
async def thwiki_test(session: CommandSession):
    updated, updated_event = [], []
    for node in whiteforest:
        if 'supervisor' not in node or not node['supervisor']:
            if 'child' in node:
                for c in node['child']:
                    u = deprive(find_whiteforest(id=c), False, False)
                    updated += u[0]
                    updated_event += u[1]
                node.pop('child')
    save_whiteforest()
    await _save(l)
    for e in updated_event:
        config.logger.thwiki << f'【LOG】事件权限更新：{e}'
        for group in config.group_id_dict['thwiki_supervise']:
            await get_bot().send_group_msg(group_id=group, message=f'{e}\n等待管理员监视')
    for group in config.group_id_dict['thwiki_send']:
        await get_bot().send_group_msg(group_id=group, message=[config.cq.text('已成功安全脱离')] + updated)
