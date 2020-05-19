import asyncio
import requests
import re
import html
import paramiko, paramiko_expect
import ncmbot
import json
import random
import traceback
import functools
import difflib
from datetime import datetime, timedelta
from nonebot import on_command, CommandSession, permission, get_bot, scheduler
import chiharu.plugins.config as config

async def Event(year, month, day):
    loop = asyncio.get_event_loop()
    url = await loop.run_in_executor(None, requests.get,
                                     "https://www.eventernote.com/events/search?year=%s&month=%s&day=%s" % (year, month, day))
    text = url.text
    def _f(text):
        class _c:
            pass

        class Actor:
            def __init__(self, url, name):
                self.url = url
                self.name = name
        begin_pos = 0
        while 1:
            match_pos = re.search('<div class="event">', text[begin_pos:])
            if not match_pos:
                break
            begin_pos += match_pos.span()[1]
            name_match = re.search(
                '<h4><a href="(.*?)">(.*?)</a></h4>', text[begin_pos:], re.S)
            if not name_match:
                break
            m = _c()
            m.url = name_match.group(1)
            m.name = name_match.group(2)
            place_match = re.search(
                '<div class="place">(.*?)</div>', text[begin_pos:], re.S)
            if not place_match:
                m.place = None
            else:
                begin_pos += place_match.span()[1]
                m.place = re.sub('\n|\t| ', '', re.sub(
                    '<.*?>', '', place_match.group(1)))
            actors_match = re.search('<div class="actor">', text[begin_pos:])
            m.actor = []
            if actors_match:
                begin_pos += actors_match.span()[1]
                next_match = re.search('<div class="event">', text[begin_pos:])
                if next_match:
                    end_pos = begin_pos + next_match.span()[0]
                else:
                    end_pos = -1
                while 1:
                    actor_match = re.search(
                        '<li><a href="(.*?)">(.*?)</a></li>', text[begin_pos:end_pos], re.S)
                    if not actor_match:
                        break
                    begin_pos += actor_match.span()[1]
                    m.actor.append(
                        Actor(actor_match.group(1), actor_match.group(2)))
            note_match = re.search(
                '<div class="note_count">.*?<p title=".*?">(.*?)</p>.*?</div>', text[begin_pos:], re.S)
            if not note_match:
                m.note = 1
            else:
                m.note = int(note_match.group(1))
                begin_pos += note_match.span()[1]
            yield m
    return list(_f(text))

@on_command(('misc', 'event'), only_to_me=False, short_des="查询Event。", hide=True)
@config.ErrorHandle
async def event(session: CommandSession):
    """查询Event。"""
    g = await Event(session.get('year'), session.get('month'), session.get('day'))
    max_note = session.get('max_note')
    def _():
        for m in filter(lambda x: x.note >= max_note, g):
            if len(m.actor) >= 7:
                actor_str = ', '.join(
                    map(lambda x: x.name, m.actor[:7])) + '...'
            else:
                actor_str = ', '.join(map(lambda x: x.name, m.actor))
            yield "%s\n%s\n出演者: %s" % (m.name, m.place, actor_str)
    l = list(_())
    for strout in l:
        await session.send(strout, auto_escape=True)

@event.args_parser
async def _(session: CommandSession):
    tup = session.current_arg_text.split(' ')
    if len(tup) == 3:
        session.args['year'], session.args['month'], session.args['day'] = tup
        session.args['max_note'] = 100
    else:
        session.args['year'], session.args['month'], session.args['day'], max_note_str = tup
        session.args['max_note'] = int(max_note_str)

interact = None
PROMPT = '.*qity@.*>\s*'
isLoggedin = False
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
with open(config.rel("boss_check.txt")) as f:
    BossCheck = bool(int(f.readline().strip('\n')))
with open(config.rel("QAQ.txt")) as f:
    p = f.readline().strip('\n')
    ssh.connect("lxslc7.ihep.ac.cn", 22, 'qity', p)
interact = paramiko_expect.SSHClientInteraction(ssh, timeout=10)
@scheduler.scheduled_job('date', id='boss_login', run_date=datetime.now() + timedelta(seconds=15))
async def login():
    global isLoggedin
    interact.expect(PROMPT)
    isLoggedin = True
    for group in config.group_id_dict['boss']:
        await get_bot().send_group_msg(group_id=group, message='boss logged in!')
told_not_logged_in = False

config.CommandGroup('boss', hide=True)

@on_command(('boss', 'login'), only_to_me=False, permission=permission.SUPERUSER, hide=True)
@config.ErrorHandle
async def boss_login(session: CommandSession):
    global interact, ssh
    ssh.connect("lxslc6.ihep.ac.cn", 22, 'qity', session.current_arg_text)
    interact = paramiko_expect.SSHClientInteraction(ssh, timeout=10)
    async def login():
        global isLoggedin
        interact.expect(PROMPT)
        isLoggedin = True
    await asyncio.get_event_loop().run_in_executor(None, login)
    await session.send('Successfully logged in')

# @on_command(('boss', 'begin'), only_to_me=False, hide=True)
@config.ErrorHandle
async def boss_begin(session: CommandSession):
    if not isLoggedin:
        await session.send('not logged in!')
        return
    BossCheck = True
    with open(config.rel("boss_check.txt"), 'w') as f:
        f.write('1')
    await session.send('boss check begin!')

# @on_command(('boss', 'process'), only_to_me=False, permission=permission.SUPERUSER, hide=True)
@config.ErrorHandle
async def boss_process(session: CommandSession):
    if not isLoggedin:
        await session.send('not logged in!')
        return
    def _f(c):
        std = ssh.exec_command(c.strip())
        return '\n'.join([''.join(s.readlines()).strip() for s in std[1:3]])
    output = '\n'.join([_f(c) for c in session.current_arg_text.split('\n')])
    #output = '\n'.join(['\n'.join(['$ ' + '\n'.join([''.join(s.readlines()).strip() for s in std]) for std in ssh.exec_command(c.strip())]) for c in session.current_arg_text.split('\n')])
    await session.send(output)

class Status:
    def __init__(self, groups):
        if groups is None:
            self.valid = False
        else:
            self.valid = True
            (self.all, self.completed, self.removed, self.idle,
             self.running, self.held, self.suspended) = map(int, groups)
            if self.all != self.completed + self.removed + self.idle + self.running + self.held + self.suspended:
                self.valid = False
    def isValid(self):
        return self.valid
    def Running(self):
        return self.valid and (self.idle + self.running != 0)
    def process(self, f):
        if self.held != 0:
            f()
            return "Job held!"
        elif self.all - self.completed - self.removed == 0:
            f()
            return "All of your jobs have ended! func executed."
        else:
            return ""

@scheduler.scheduled_job('cron', id='check_boss', minute='00-57/3')
async def check_boss():
    global BossCheck, isLoggedin, told_not_logged_in, interact
    bot = get_bot()
    if not isLoggedin:
        if not told_not_logged_in:
            for group in config.group_id_dict['boss']:
                await bot.send_group_msg(group_id=group, message='please login: -boss.login password')
            told_not_logged_in = True
        return
    interact.send('submit -c')
    interact.expect(PROMPT)
    output = interact.current_output_clean
    # stdin, stdout, stderr = ssh.exec_command('/workfs/bes/qity/shell/script/submit -c')
    # output = ''.join(stdout.readlines()).strip()
    if output != '':
        for group in config.group_id_dict['boss']:
            await bot.send_group_msg(group_id=group, message=output.strip())
    def _f():
        global interact
        interact.send('hep_q -u qity')
        interact.expect(PROMPT)
        output = interact.current_output_clean
        match = re.search(
            "(\d*) jobs; (\d*) completed, (\d*) removed, (\d*) idle, (\d*) running, (\d*) held, (\d*) suspended", output)
        if not match:
            print("Not found")
            return Status(None)
        return Status(match.groups())
    status = _f()
    if BossCheck:
        if not status.isValid():
            strout = "Error!"
        else:
            with open(config.rel("boss_check.txt")) as f:
                f.readline()
                command = f.readline().strip()
            if command == '':
                def _g():
                    global BossCheck
                    BossCheck = False
                    with open(config.rel("boss_check.txt"), 'w') as f:
                        f.write('0')
            else:
                def _g():
                    # stdin, stdout, stderr = ssh.exec_command(command)
                    # print((stdout.readlines(), stderr.readlines()))
                    with open(config.rel("boss_check.txt"), 'w') as f:
                        f.write('1')
                        f.write('\n')
            strout = status.process(_g)
        if strout != "":
            for group in config.group_id_dict['boss']:
                await bot.send_group_msg(group_id=group, message=strout)
    else:
        if status.Running():
            BossCheck = True
            with open(config.rel("boss_check.txt"), 'w') as f:
                f.write('1')
            for group in config.group_id_dict['boss']:
                await bot.send_group_msg(group_id=group, message='Running job found! Begin boss check')

@on_command(('boss', 'hang'), only_to_me=False, permission=permission.SUPERUSER, hide=True)
@config.ErrorHandle
async def boss_hang(session: CommandSession):
    with open(config.rel('boss_check.txt'), 'w') as f:
        f.write('1' if BossCheck else '0')
        f.write('\n')
        f.write(session.current_arg_text)
    await session.send('Successfully saved.')

idmap = {'all': 2503049358,
         'LL': 138461796,
         'll': 138461796,
         'lovelive': 138461796,
         'bandori': 2221214678,
         "mu's": 423336425,
         'Aqours': 449636768,
         'starlight': 2482865249,
         'sphere': 994322013,
         'Sphere': 994322013,
         'aki': 994296036,
         'ML': 50015591,
         'ml': 50015591,
         'KON': 812754,
         'kon': 812754,
         'MH': 46568099,
         'mh': 46568099,
         'VOCALO': 37258756,
         'vocalo': 37258756,
         'cgss': 526680154,
         'CGSS': 526680154}

@functools.total_ordering
class Time:
    match = re.compile('^(\d{1,3}):(\d{1,2})\.(\d{1,3})$')
    def __init__(self, timestr):
        self.str = timestr
        match = re.match(self.match, self.str)
        assert(match)
        self.minute, self.second, self.milisecond = match.groups()
        self.milisecond *= 10 ** (3 - len(match.group(3)))
    def __lt__(self, other):
        return (self.minute, self.second, self.milisecond) < (other.minute, other.second, other.milisecond)
    def __eq__(self, other):
        return (self.minute, self.second, self.milisecond) == (other.minute, other.second, other.milisecond)
    def __str__(self):
        return self.str

class Line:
    def __init__(self, string):
        if string == "":
            self.valid = False
            return
        e = string.find(']')
        if e == -1:
            self.content = string
            self.trans = None
            self.valid = True
            self.time = None
            return
        timestr = string[:e]
        self.content = string[e + 1:].replace('\n', '')
        self.trans = None
        try:
            self.time = Time(timestr)
        except:
            self.time = None
            self.valid = False
        else:
            self.valid = True
    def empty(self):
        return self.content == ""
    def isValid(self):
        return self.valid
    def addTrans(self, string):
        self.trans = string
    def clearTrans(self):
        self.trans = None

class LyricTransErr(Exception):
    def __init__(self, song_id, time):
        self.id = song_id
        self.time = time
    def __str__(self):
        return "Song " + str(self.id) + "'s translated lyric at time " + str(self.time) + " are dislocated"

class anyErrWithId(Exception):
    def __init__(self, err, id, tb):
        self.err = err
        self.id = id
        self.traceback = tb
    def __str__(self):
        return self.err.__class__.__name__ + ": " + str(self.err) + ", song id: " + str(self.id)

def printLyric(idx):
    lyric = ncmbot.lyric(id=idx).json()
    with open('test.txt', 'w') as f:
        f.write(json.dumps(lyric, indent=4, separators=(',', ': ')
                           ).decode('unicode_escape').encode('utf-8'))

def getLyric(listid):
    pl = ncmbot.play_list_detail(id=str(listid)).json()
    trks = pl['playlist']['trackIds']
    # print(len(trks))
    while 1:
        ran_trk = random.choice(trks)
        lyricl = ncmbot.lyric(id=ran_trk['id']).json()
        if 'lrc' in lyricl:
            break
    song_id = ran_trk['id']
    try:
        lyricstr = lyricl['lrc']['lyric']
        tlyricstr = lyricl['tlyric']['lyric']
        # klyricstr = lyricl['klyric']['lyric']#???
        lyric = list(filter(Line.isValid, map(Line, lyricstr.split('['))))
        # print lyric
        if tlyricstr is not None:
            try:
                tlyric = list(
                    filter(Line.isValid, map(Line, tlyricstr.split('['))))
                liter = iter(lyric)
                titer = iter(tlyric)
                try:
                    line = next(liter)
                    tl = next(titer)
                    while 1:
                        if line.time == tl.time:
                            line.addTrans(tl.content)
                        elif line.time < tl.time:
                            line = next(liter)
                            continue
                        else:
                            raise LyricTransErr(song_id, tl.time)
                        line = next(liter)
                        tl = next(titer)
                except StopIteration:
                    pass
            except LyricTransErr:
                for line in lyric:
                    line.clearTrans()
        blocks = []
        t = ()
        for line in lyric:
            if line.empty():
                if t != ():
                    if len(t) == 1 and len(blocks) != 0:
                        blocks[-1] += t
                    else:
                        blocks.append(t)
                    t = ()
            else:
                t += (line, )
        if t != ():
            if len(t) == 1 and len(blocks) != 0:
                blocks[-1] += t
            else:
                blocks.append(t)
        # print(blocks)

        def _f(blocks):
            for block in blocks:
                b = len(block) >= 6

                def _v(string):
                    return '作词' not in string.content and '作曲' not in string.content and '编曲' not in string.content and u'词:' not in string.content and u'曲:' not in string.content
                if not b:
                    b = all(map(_v, block))
                else:
                    block = list(filter(_v, block))
                if b:
                    for i in range(len(block)):
                        # print block[i].content.encode('utf-8')
                        if len(block[i].content) >= 25:
                            yield (block[i], )
                        elif len(block[i].content) >= 8 and i < len(block) - 1:
                            yield (block[i], block[i + 1])
                        elif len(block[i].content) < 8 and i < len(block) - 2:
                            yield (block[i], block[i + 1], block[i + 2])
        pool = tuple(_f(blocks))
        # print len(pool)
        # print(pool)
        t = random.choice(pool)
        lyricrstr = '\n'.join(map(lambda x: x.content, t))
        tlyricrstr = '\n'.join(
            filter(lambda x: x is not None, map(lambda x: x.trans, t)))
        r = ncmbot.song_detail([ran_trk['id']]).json()
        # print r['songs']#.encode('utf-8')
        # print repr(r['songs'])#.encode('utf-8')
        trk_name = r['songs'][0]['name']
        trk_ar = ', '.join(map(lambda x: x['name'], r['songs'][0]['ar']))
        return {'lyric': lyricrstr, 'translated': tlyricrstr, 'name': trk_name, 'artists': trk_ar}
    except Exception as err:
        raise anyErrWithId(err, song_id, traceback.format_exc())

config.CommandGroup(('misc', 'roll'), hide=True)

@on_command(('misc', 'roll', 'lyric'), only_to_me=False, short_des="随机歌词。", display_parents='misc')
@config.ErrorHandle
async def roll_lyric(session: CommandSession):
    """随机歌词。
    不加参数则为从全曲库中随机。
    支持曲库：vocalo kon imas ml cgss sphere aki bandori ll mu's Aqours starlight mh"""
    args = 'all' if session.current_arg_text == '' else session.current_arg_text
    if args not in idmap:
        await session.send('name not found')
    else:
        d = getLyric(idmap[args])
        await session.send('抽歌词！：\n%s%s\n——《%s》（%s）' %
                           (d['lyric'], (u"\n翻译：\n" + d['translated'] if d['translated'] != "" else u""), d['name'], d['artists']))

# @scheduler.scheduled_job('cron', minute='00-57/3')
# async def check_bicaf():
#     with open(config.rel('bicaf.html'), encoding='utf-8') as f:
#         l = f.readlines()
#     loop = asyncio.get_event_loop()
#     url = await loop.run_in_executor(None, requests.get,
#         "https://bicaf.com.cn/news")
#     text = url.text.splitlines(keepends=True)
#     d = list(difflib.ndiff(l, text))
#     if any([x.startswith('+ ') or x.startswith('- ') for x in d]):
#         with open(config.rel('bicaf.html'), 'w', encoding='utf-8') as f:
#             f.write(url.text)
#         for group in config.group_id_dict['boss']:
#             await get_bot().send_group_msg(group_id=group, message=''.join([x for x in d if not x.startswith('  ')]))
#     with open(config.rel('bicaf_ticket.html'), encoding='utf-8') as f:
#         l = f.readlines()
#     url = await loop.run_in_executor(None, requests.get,
#         "https://bicaf.com.cn/ticket")
#     text = url.text.splitlines(keepends=True)
#     d = list(difflib.ndiff(l, text))
#     if any([x.startswith('+ ') or x.startswith('- ') for x in d]):
#         with open(config.rel('bicaf_ticket.html'), 'w', encoding='utf-8') as f:
#             f.write(url.text)
#         for group in config.group_id_dict['boss']:
#             await get_bot().send_group_msg(group_id=group, message=''.join([x for x in d if not x.startswith('  ')]))

bibtex_url = {'pra': 'https://journals.aps.org/pra/export/10.1103/PhysRevA.{}.{}', 'prb': 'https://journals.aps.org/prb/export/10.1103/PhysRevB.{}.{}', 'prc': 'https://journals.aps.org/prc/export/10.1103/PhysRevC.{}.{}', 'prd': 'https://journals.aps.org/prd/export/10.1103/PhysRevD.{}.{}', 'pre': 'https://journals.aps.org/pre/export/10.1103/PhysRevE.{}.{}',
              'prl': 'https://journals.aps.org/prl/export/10.1103/PhysRevLett.{}.{}', 'cpc': 'https://iopscience.iop.org/export?articleId=1674-1137/{}/{}/{}&exportFormat=iopexport_bib&exportType=abs&navsubmit=Export+abstract', 'cpb': 'https://iopscience.iop.org/export?articleId=1674-1056/{}/{}/{}&exportFormat=iopexport_bib&exportType=abs&navsubmit=Export+abstract'}
@on_command(('tools', 'bibtex'), only_to_me=False, short_des="查询文章的bibtex。", args=("journal", "volume", "pages"))
@config.ErrorHandle
async def bibtex(session: CommandSession):
    """查询文章的bibtex。
    目前支持期刊：pra prb prc prd pre prl cpb cpc"""
    args = session.current_arg_text.split(' ')
    if len(args) == 0 or args[0].lower() not in bibtex_url:
        session.finish('支持期刊：pra prb prc prd pre prl cpb cpc')
    elif len(args) < 3:
        session.finish('请使用：-tools.bibtex 期刊名 卷数 首页页码')
    name = args.pop(0).lower()
    loop = asyncio.get_event_loop()
    try:
        if int(args[0]) <= 0 or int(args[1]) <= 0:
            raise ValueError
        if name in ('cpc', 'cpb'):
            args = args[0], str(int(args[1][0:2])), args[1]
        url = await asyncio.wait_for(loop.run_in_executor(None, requests.get, bibtex_url[name].format(*args)), timeout=60)
        if url.status_code != 200:
            await session.send('not found!')
        else:
            if len(url.text) >= 2000:
                await session.send(url.text[0:2000], auto_escape=True)
                await session.send(url.text[2000:], auto_escape=True)
            else:
                await session.send(url.text, auto_escape=True)
    except ValueError:
        await session.send('请输入合理的期刊卷数与页码。')
    except asyncio.TimeoutError:
        await session.send('time out!')

config.CommandGroup('steam', hide=True)

@on_command(('steam', 'price'), only_to_me=False, hide=True)
@config.ErrorHandle
async def steam_price(session: CommandSession):
    name = session.current_arg_text.strip()
    loop = asyncio.get_event_loop()
    try:
        headers = {'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.108 Safari/537.36'
                    ,'Cookies':'__cfduid=d86e702d95c9f19d5f33c5ae30ded8d881572688847; _ga=GA1.2.940923473.1572688859; __Host-cc=cn; cf_clearance=e13ec0c58bb63cfa52ea085e2424466fdc3213c3-1574825182-0-150; _gid=GA1.2.1066487208.1574825186'
                    ,'Sec-Fetch-Mode': 'navigate'
                    ,'Sec-Fetch-Site': 'none'
                    ,'Sec-Fetch-User': '?1'
                    ,'Upgrade-Insecure-Requests': '1'
                    ,'Accept-Language': 'zh-CN,zh;q=0.9'
                    ,'Cache-Control': 'max-age=0'
                    }
        cookies = {'__cfduid':'d86e702d95c9f19d5f33c5ae30ded8d881572688847','_ga':'GA1.2.940923473.1572688859','__Host-cc':'cn','cf_clearance':'e13ec0c58bb63cfa52ea085e2424466fdc3213c3-1574825182-0-150','_gid':'GA1.2.1066487208.1574825186'}
        url = await asyncio.wait_for(loop.run_in_executor(None, functools.partial(requests.get, 'https://steamdb.info/search/?a=app&q=' + name, cookies=cookies)), timeout=60)
        if url.status_code != 200:
            await session.send('url error!')
            return
        begin = re.search('<tbody hidden>', url.text)
        if not begin:
            await session.send('url error!')
            return
        begin_pos = begin.span()[1]
        match = re.search(
            '<tr class="app" data-appid="(\d+)">', url.text[begin_pos:])
        if not match:
            await session.send('未找到此游戏。')
        else:
            app_id = match.group(1)
            url = await asyncio.wait_for(loop.run_in_executor(None, functools.partial(requests.get, f'https://steamdb.info/app/{app_id}/', headers=headers)), timeout=60)
            if url.status_code != 200:
                await session.send('url error!')
                return
            title = re.search(
                '<td>Name</td>\s*<td itemprop="name">([^<>]+?)</td>', url.text)
            if not title:
                await session.send('url error!')
                return
            name = html.unescape(title.group(1))
            store = f'https://store.steampowered.com/app/{app_id}/'
            price_match = re.search(
                'Chinese Yuan Renminbi\s*</td>\s*¥ (\d+)(?: at <span class="price-discount">-(\d+)%</span>)?</td>\s*<td [^<>]*?>.*?</td>\s*<td data-sort=".*?">¥ (\d+)</td>', url.text)
            if not price_match:
                await session.send('未找到价格信息。')
                return
            price, discount, price_lowest = price_match.groups()
            await session.send(f'游戏名称：{name}\nSteam store链接：{store}\n现价：¥ {price}{f"(-{discount}%)" if discount is not None else ""}\n史低：¥ {price_lowest}')
    except asyncio.TimeoutError:
        await session.send('time out!')

with open(config.rel('thtk_github_last_update.txt')) as f:
    thtk_time = datetime.fromisoformat(f.read())

# @scheduler.scheduled_job('cron', minute='00-40/20')
async def check_github_thtk():
    global thtk_time
    loop = asyncio.get_event_loop()
    ret = await loop.run_in_executor(None, functools.partial(requests.get, 'https://api.github.com/repos/thpatch/thtk/commits'))
    j = ret.json()
    for i, d in enumerate(j):
        if datetime.fromisoformat(d['commit']['committer']['date'][:-1]) <= thtk_time:
            break
    if i != 0:
        t = j[0]['commit']['committer']['date'][:-1]
        thtk_time = datetime.fromisoformat(t)
        with open(config.rel('thtk_github_last_update.txt'), 'w') as f:
            f.write(t)
        for group in config.group_id_dict['thtk_update']:
            await get_bot().send_group_msg(message='Thtk commit detected.\n' + '\n'.join(f"Commit in {d['commit']['committer']['date']}:\n{d['commit']['message']}" for d in j[:i]), group_id=group, auto_escape=True)
