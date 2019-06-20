import asyncio
import requests
import re
import paramiko
import ncmbot
import json
import random
import traceback
import functools
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
            name_match = re.search('<h4><a href="(.*?)">(.*?)</a></h4>', text[begin_pos:], re.S)
            if not name_match:
                break
            m = _c()
            m.url = name_match.group(1)
            m.name = name_match.group(2)
            place_match = re.search('<div class="place">(.*?)</div>', text[begin_pos:], re.S)
            if not place_match:
                m.place = None
            else:
                begin_pos += place_match.span()[1]
                m.place = re.sub('\n|\t| ', '', re.sub('<.*?>', '', place_match.group(1)))
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
                    actor_match = re.search('<li><a href="(.*?)">(.*?)</a></li>', text[begin_pos:end_pos], re.S)
                    if not actor_match:
                        break
                    begin_pos += actor_match.span()[1]
                    m.actor.append(Actor(actor_match.group(1), actor_match.group(2)))
            note_match = re.search('<div class="note_count">.*?<p title=".*?">(.*?)</p>.*?</div>', text[begin_pos:], re.S)
            if not note_match:
                m.note = 1
            else:
                m.note = int(note_match.group(1))
                begin_pos += note_match.span()[1]
            yield m
    return list(_f(text))
    
@on_command('event', only_to_me=False)
@config.ErrorHandle
async def event(session: CommandSession):
    g = await Event(session.get('year'), session.get('month'), session.get('day'))
    max_note = session.get('max_note')
    def _():
        for m in filter(lambda x: x.note >= max_note, g):
            if len(m.actor) >= 7:
                actor_str = ', '.join(map(lambda x: x.name, m.actor[:7])) + '...'
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

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
with open(config.rel("boss_check.txt")) as f:
    BossCheck = bool(int(f.readline().strip('\n')))
with open(config.rel("QAQ.txt")) as f:
    p = f.readline().strip('\n')
    ssh.connect("lxslc6.ihep.ac.cn", 22, 'qity', p)
isLoggedin = True

@on_command(('boss', 'login'), only_to_me=False, permission=permission.SUPERUSER)
@config.ErrorHandle
async def login(session: CommandSession):
    ssh.connect("lxslc6.ihep.ac.cn", 22, 'qity', session.current_arg_text)
    global isLoggedin
    isLoggedin = True
    await session.send('Successfully logged in')

@on_command(('boss', 'begin'), only_to_me=False)
@config.ErrorHandle
async def boss_begin(session: CommandSession):
    if not isLoggedin:
        await session.send('not logged in!')
        return
    BossCheck = True
    with open(config.rel("boss_check.txt"), 'w') as f:
        f.write('1')
    await session.send('boss check begin!')

@on_command(('boss', 'process'), only_to_me=False, permission=permission.SUPERUSER)
@config.ErrorHandle
async def boss_process(session: CommandSession):
    if not isLoggedin:
        await session.send('not logged in!')
        return
    stdin, stdout, stderr = ssh.exec_command(session.current_arg_text)
    output = ''.join(stdout.readlines()).strip()
    err = ''.join(stderr.readlines()).strip()
    await session.send(output + '\n' + err)

class Status:
    def __init__(self, groups):
        if groups is None:
            self.valid = False
        else:
            self.valid = True
            (self.all, self.completed, self.removed, self.idle, self.running, self.held, self.suspended) = map(int, groups)
            if self.all != self.completed + self.removed + self.idle + self.running + self.held + self.suspended:
                self.valid = False
    def isValid(self):
        return self.valid
    def Running(self):
        return self.idle + self.running != 0
    def process(self, f):
        print((self.all, self.completed, self.removed, self.idle, self.running, self.held, self.suspended))
        if self.held != 0:
            f()
            return "Job held!"
        elif self.all - self.completed == 0:
            f()
            return "All of your jobs have ended!"
        else:
            return ""

@scheduler.scheduled_job('cron', minute='00-57/3')
async def check_boss():
#@on_command(('boss', 'check'), only_to_me=False)
#@config.ErrorHandle
#async def check_boss(session: CommandSession):
    global BossCheck, isLoggedin
    bot = get_bot()
    if not isLoggedin:
        for group in config.group_id_dict['test']:
            await bot.send_group_msg(group_id=group, message='please login: -boss.login password')
    def _f():
        stdin, stdout, stderr = ssh.exec_command('/afs/ihep.ac.cn/soft/common/sysgroup/hep_job/bin/hep_q -u qity')
        output = stdout.readlines()[-1]
        print(output)
        match = re.match("(\d+) jobs; (\d+) completed, (\d+) removed, (\d+) idle, (\d+) running, (\d+) held, (\d+) suspended", output)
        if not match:
            print("Not found")
            return Status(None)
        return Status(match.groups())
    status = _f()
    print(BossCheck)
    if BossCheck:
        print((status.valid, status.all, status.completed, status.removed, status.idle, status.running, status.held, status.suspended))
        if not status.isValid():
            strout = "Error!"
        else:
            def _g():
                global BossCheck
                BossCheck = False
                with open(config.rel("boss_check.txt"), 'w') as f:
                    f.write('0')
            strout = status.process(_g)
        if strout != "":
            for group in config.group_id_dict['test']:
                await bot.send_group_msg(group_id=group, message=strout)
    else:
        if status.Running():
            BossCheck = True
            with open(config.rel("boss_check.txt"), 'w') as f:
                f.write('1')
            for group in config.group_id_dict['test']:
                await bot.send_group_msg(group_id=group, message='Running job found! Begin boss check')

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
    def __init__(self, timestr):
        self.str = timestr
        assert(len(timestr) >= 7 and len(timestr) <= 9)
        self.minute = int(timestr[0:2])
        assert(timestr[2] == ':')
        self.second = int(timestr[3:5])
        assert(timestr[5] == '.')
        self.milisecond = int(timestr[6:]) * (10 ** (9 - len(timestr)))
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
    def valid(self):
        return self.valid
    def empty(self):
        return self.content == ""
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
    lyric = ncmbot.lyric(id = idx).json()
    with open('test.txt', 'w') as f:
        f.write(json.dumps(lyric, indent = 4, separators = (',', ': ')).decode('unicode_escape').encode('utf-8'))

def getLyric(listid):
    pl = ncmbot.play_list_detail(id = str(listid)).json()
    trks = pl['playlist']['trackIds']
    print(len(trks))
    while 1:
        ran_trk = random.choice(trks)
        lyricl = ncmbot.lyric(id = ran_trk['id']).json()
        if 'lrc' in lyricl:
            break
    song_id = ran_trk['id']
    try:
        lyricstr = lyricl['lrc']['lyric']
        tlyricstr = lyricl['tlyric']['lyric']
        #klyricstr = lyricl['klyric']['lyric']#???
        lyric = list(filter(Line.valid, map(Line, lyricstr.split('['))))
        #print lyric
        if tlyricstr is not None:
            try:
                tlyric = list(filter(Line.valid, map(Line, tlyricstr.split('['))))
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
        #print(blocks)
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
                        #print block[i].content.encode('utf-8')
                        if len(block[i].content) >= 25:
                            yield (block[i], )
                        elif len(block[i].content) >= 8 and i < len(block) - 1:
                            yield (block[i], block[i + 1])
                        elif len(block[i].content) < 8 and i < len(block) - 2:
                            yield (block[i], block[i + 1], block[i + 2])
        pool = tuple(_f(blocks))
        #print len(pool)
        #print(pool)
        t = random.choice(pool)
        lyricrstr = '\n'.join(map(lambda x: x.content, t))
        tlyricrstr = '\n'.join(filter(lambda x: x is not None, map(lambda x: x.trans, t)))
        r = ncmbot.song_detail([ran_trk['id']]).json()
        #print r['songs']#.encode('utf-8')
        #print repr(r['songs'])#.encode('utf-8')
        trk_name = r['songs'][0]['name']
        trk_ar = ', '.join(map(lambda x: x['name'], r['songs'][0]['ar']))
        return { 'lyric': lyricrstr, 'translated': tlyricrstr, 'name': trk_name, 'artists': trk_ar }
    except Exception as err:
        raise anyErrWithId(err, song_id, traceback.format_exc())

@on_command(('misc', 'roll', 'lyric'), only_to_me=False)
@config.ErrorHandle
async def roll_lyric(session: CommandSession):
    args = 'all' if session.current_arg_text == '' else session.current_arg_text
    if args not in idmap:
        await session.send('name not found')
    else:
        d = getLyric(idmap[args])
        await session.send('抽歌词！：\n%s%s\n——《%s》（%s）' % \
                (d['lyric'], (u"\n翻译：\n" + d['translated'] if d['translated'] != "" else u""), d['name'], d['artists']))
