import random, itertools, more_itertools
from collections import Counter
from enum import Enum, auto
from typing import Dict, Any, Awaitable
from nonebot import get_bot, CommandSession, NLPSession
import aiocqhttp
from ..game import GameSameGroup

class Player:
    class Name(Enum):
        一 = auto()
        二 = auto()
        三 = auto()
        四 = auto()
        五 = auto()
        六 = auto()
        全选 = auto()
        四骰同花 = auto()
        葫芦 = auto()
        小顺 = auto()
        大顺 = auto()
        快艇 = auto()
    def __init__(self):
        self.scoreboard = {}
        self._fixed_dice = []
        self._float_dice = []
        self.rolled_count = 3
    @property
    def temp_scoreboard(self):
        d = list(sorted(self._float_dice + self._fixed_dice))
        t = {}
        t[Player.Name.一] = sum((c for c in d if c == 1), 0)
        t[Player.Name.二] = sum((c for c in d if c == 2), 0)
        t[Player.Name.三] = sum((c for c in d if c == 3), 0)
        t[Player.Name.四] = sum((c for c in d if c == 4), 0)
        t[Player.Name.五] = sum((c for c in d if c == 5), 0)
        t[Player.Name.六] = sum((c for c in d if c == 6), 0)
        t[Player.Name.全选] = sum(d, 0)
        ss = set(d)
        s = Counter(d)
        s_val = set(s.values())
        t[Player.Name.快艇] = sum(d, 0) if s_val == {5} else 0
        t[Player.Name.四骰同花] = sum(d, 0) if s_val == {4, 1} or s_val == {5} else 0
        t[Player.Name.葫芦] = sum(d, 0) if s_val == {3, 2} or s_val == {5} else 0
        t[Player.Name.大顺] = 30 if ss == {1, 2, 3, 4, 5} or ss == {2, 3, 4, 5, 6} else 0
        t[Player.Name.小顺] = 15 if {1, 2, 3, 4} <= ss or {2, 3, 4, 5} <= ss or {3, 4, 5, 6} <= ss else 0
        return t
    def roll(self):
        self._float_dice = sorted([random.randint(1, 6) for i in range(5 - len(self._fixed_dice))])
        self.rolled_count -= 1
        if self.rolled_count == 0:
            self._fixed_dice += self._float_dice
            self._float_dice = []
        self._fixed_dice.sort()
    def unfix(self, unfixed):
        t = self._fixed_dice + self._float_dice
        for c in unfixed:
            try:
                t.remove(c)
            except ValueError:
                return -1
        self._float_dice = list(unfixed)
        self._fixed_dice = t
    def score(self, name):
        if name in self.scoreboard:
            return -1
        self.scoreboard[name] = self.temp_scoreboard[name]
        self.rolled_count = 3
        self._fixed_dice = []
        self._float_dice = []
        return self.scoreboard[name]
    @property
    def final_score(self):
        if sum(self.scoreboard[Player.Name.__members__[x]] for x in ['一', '二', '三', '四', '五', '六'] if Player.Name.__members__[x] in self.scoreboard) >= 63:
            return sum(self.scoreboard.values()) + 35
        else:
            return sum(self.scoreboard.values())
    def __repr__(self):
        return str(self.__dict__)
    @property
    def fixed_dice(self):
        return '无' if len(self._fixed_dice) == 0 else ",".join(map(str, self._fixed_dice))
    @property
    def float_dice(self):
        return '无' if len(self._float_dice) == 0 else ",".join(map(str, self._float_dice))
    @property
    def str_scoreboard(self):
        return '  '.join(f'{name.name}：{self.scoreboard[name]}分' for name in Player.Name if name in self.scoreboard) + f'\n总分：{self.final_score}分'
    @property
    def str_temp_scoreboard(self):
        t = self.temp_scoreboard
        return '  '.join(f'{name.name}：{t[name]}分' for name in Player.Name if name not in self.scoreboard)

yahtzee = GameSameGroup('yahtzee')

@yahtzee.begin_uncomplete(('play', 'yahtzee', 'begin'), (2, 4))
async def yahtzee_begin_uncomplete(session: CommandSession, data: Dict[str, Any]):
    # data: {'players': [qq], 'args': [args], 'anything': anything}
    qq = session.ctx['user_id']
    group = session.ctx['group_id']
    try:
        c = await get_bot().get_group_member_info(group_id=group, user_id=qq)
        if c['card'] == '':
            name = c['nickname']
        else:
            name = c['card']
    except aiocqhttp.exceptions.ActionFailed:
        name = str(qq)
    if 'names' in data:
        data['names'].append(name)
    else:
        data['names'] = [name]
    await session.send(f'玩家{name}已参与匹配，人数足够可使用-play.yahtzee.confirm开始比赛。')

@yahtzee.begin_complete(('play', 'yahtzee', 'confirm'))
async def yahtzee_begin_complete(session: CommandSession, data: Dict[str, Any]):
    # data: {'players': [qq], 'game': GameSameGroup instance, 'args': [args], 'anything': anything}
    qq = session.ctx['user_id']
    group = session.ctx['group_id']
    try:
        c = await get_bot().get_group_member_info(group_id=group, user_id=qq)
        if c['card'] == '':
            name = c['nickname']
        else:
            name = c['card']
    except aiocqhttp.exceptions.ActionFailed:
        name = str(qq)
    if 'names' in data:
        data['names'].append(name)
    else:
        data['names'] = [name]
    await session.send(f'玩家{name}已参与匹配，游戏开始，任何时候输入"查看分数"可以查看全部玩家当前分数')
    #开始游戏
    data['boards'] = [Player() for qq in data['players']]
    data['current_player'] = 0
    p = data['boards'][0]
    p.roll()
    await session.send(f'玩家{data["names"][data["current_player"]]}扔出骰子{p.float_dice}，已固定骰子{p.fixed_dice}\n剩余重扔次数：{p.rolled_count}\n输入如"重扔 5,5,6"重扔，如"计分 快艇"计分')

@yahtzee.end(('play', 'yahtzee', 'end'))
async def yahtzee_end(session: CommandSession, data: Dict[str, Any]):
    await session.send('已删除')

@yahtzee.process(only_short_message=True)
async def yahtzee_process(session: NLPSession, data: Dict[str, Any], delete_func: Awaitable):
    p = data['boards'][data['current_player']]
    command = session.msg_text.strip()
    if command.startswith('重扔') and session.ctx['user_id'] == data['players'][data['current_player']]:
        if p.unfix([int(c) for c in command[2:].strip().split(',')]) == -1:
            await session.send('未发现骰子，请重新输入')
            return
        p.roll()
        if p.rolled_count == 0:
            await session.send(f'玩家{data["names"][data["current_player"]]}骰子为{p.fixed_dice}\n可选计分项为：{p.str_temp_scoreboard}，\n输入如"计分 快艇"计分')
        else:
            await session.send(f'玩家{data["names"][data["current_player"]]}扔出骰子{p.float_dice}，已固定骰子{p.fixed_dice}\n剩余重扔次数：{p.rolled_count}\n输入如"重扔 5,5,6"重扔，如"计分 快艇"计分')
    elif command.startswith('计分') and session.ctx['user_id'] == data['players'][data['current_player']]:
        c = command[2:].strip()
        if c not in Player.Name.__members__:
            await session.send('未发现此计分项，请重新输入')
            return
        ret = p.score(Player.Name.__members__[c])
        if ret == -1:
            await session.send(f'计分项{c}已计过，请重新输入')
            return
        await session.send(f'玩家{data["names"][data["current_player"]]}计分 {c}，{ret}点。')
        data['current_player'] += 1
        if data['current_player'] >= len(data['players']):
            data['current_player'] = 0
            if len(data['boards'][data['current_player']].scoreboard) == 12:
                await session.send('游戏结束，计分板如下：\n' + '\n'.join(f'玩家{name}分数：\n{board.str_scoreboard}\n总分为：{board.final_score}分' for (name, board) in zip(data['names'], data['boards'])))
                f = [board.final_score for board in data['boards']]
                m = max(f)
                await session.send('玩家' + '，'.join([data['names'][i] for i, x in enumerate(f) if x == m]) + '胜出！')
                await delete_func()
                return
        p = data['boards'][data['current_player']]
        p.roll()
        await session.send(f'轮到玩家{data["names"][data["current_player"]]}，扔出骰子{p.float_dice}，已固定骰子{p.fixed_dice}\n剩余重扔次数：{p.rolled_count}\n输入如"重扔 5,5,6"重扔，如"计分 快艇"计分')
    elif command == '查看分数':
        await session.send('\n'.join(f'玩家{name}分数：\n{board.str_scoreboard}' for (name, board) in zip(data['names'], data['boards'])))