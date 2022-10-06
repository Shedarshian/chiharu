from asyncio import sleep
from ctypes import Union
from distutils.cmd import Command
import random, itertools, more_itertools
from collections import Counter
from enum import Enum, auto
from typing import Callable, Dict, Any, Awaitable
from nonebot import get_bot, CommandSession, NLPSession, permission
import aiocqhttp
from nonebot.command.argfilter import extractors, validators
from .. import config
from ..inject import on_command
from ..game import GameSameGroup
from .achievement import achievement

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
        self.scoreboard: dict[Player.Name, int] = {}
        self._fixed_dice: list[int] = []
        self._float_dice: list[int] = []
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
        t[Player.Name.快艇] = 50 if s_val == {5} else 0
        t[Player.Name.四骰同花] = sum(d, 0) if s_val == {4, 1} or s_val == {5} else 0
        t[Player.Name.葫芦] = sum(d, 0) if s_val == {3, 2} or s_val == {5} else 0
        t[Player.Name.大顺] = 30 if ss == {1, 2, 3, 4, 5} or ss == {2, 3, 4, 5, 6} else 0
        t[Player.Name.小顺] = 15 if {1, 2, 3, 4} <= ss or {2, 3, 4, 5} <= ss or {3, 4, 5, 6} <= ss else 0
        return t
    @property
    def _all_dice(self):
        return sorted(self._fixed_dice + self._float_dice)
    def roll(self):
        self._float_dice = sorted([random.randint(1, 6) for i in range(5 - len(self._fixed_dice))])
        self.rolled_count -= 1
        if self.rolled_count == 0:
            self._fixed_dice += self._float_dice
            self._float_dice = []
        self._fixed_dice.sort()
    def unfix(self, unfixed: list[int]):
        t = self._all_dice
        for c in unfixed:
            try:
                t.remove(c)
            except ValueError:
                return -1
        self._float_dice = list(unfixed)
        self._fixed_dice = t
    def score(self, name: Name):
        if name in self.scoreboard:
            return -1
        self.scoreboard[name] = self.temp_scoreboard[name]
        self.rolled_count = 3
        self._fixed_dice = []
        self._float_dice = []
        return self.scoreboard[name]
    @property
    def wjscore(self):
        return sum(self.scoreboard[Player.Name.__members__[x]] for x in ['一', '二', '三', '四', '五', '六'] if Player.Name.__members__[x] in self.scoreboard)
    @property
    def final_score(self):
        if self.wjscore >= 63:
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

class AI(Player):
    def process(self) -> tuple[str, list[int]]:
        with open(config.rel(f"yahtzeeAI\\exp{12 - len(self.scoreboard)}-{self.rolled_count}.csv"), encoding="uf-8") as f:
            for line in f:
                stat, wjscore, _, els = line.split(",", 4)
                if stat == ''.join("1" if name in self.scoreboard else "0" for name in reversed(Player.Name)) and int(wjscore) == self.wjscore:
                    break
            for name, count, _ in more_itertools.chunked(els.split(","), 3):
                if name == ''.join(str(i) for i in self._all_dice):
                    saved_count = int(count)
                    break
        if self.rolled_count == 0:
            return "计分", [saved_count]
        elif saved_count == 0:
            with open(config.rel(f"yahtzeeAI\\exp{12 - len(self.scoreboard)}-0.csv"), encoding="uf-8") as f:
                for line in f:
                    stat, wjscore, _, els = line.split(",", 4)
                    if stat == ''.join("1" if name in self.scoreboard else "0" for name in reversed(Player.Name)) and int(wjscore) == self.wjscore:
                        break
                for name, count, _ in more_itertools.chunked(els.split(","), 3):
                    if name == ''.join(str(i) for i in self._all_dice):
                        saved_count = int(count)
                        break
            return "计分", [saved_count]
        else:
            return "重扔", [self._all_dice[i] for i, x in enumerate(reversed(f"{saved_count:0>5b}")) if x == "1"]

@on_command(("play", "yahtzee", "aishow"), hide=True, display_parents='game', permission=permission.GROUP_ADMIN | permission.GROUP_OWNER, only_to_me=False)
@config.ErrorHandle
async def yahtzee_aishow(session: CommandSession):
    """快艇骰子AI表演，仅限管理员使用。操作间隔可加在指令后。"""
    try:
        time = 2 if session.current_arg_text.strip() == "" else float(session.current_arg_text.strip())
    except ValueError:
        time = 2
    if time < 0.5:
        session.finish("操作间隔不可小于0.5s" + config.句尾)
    if await session.aget(prompt=f"将开始快艇骰子AI表演，操作间隔为{time}s，输入确认继续，输入返回退出。", arg_filters=[extractors.extract_text]) != "继续":
        session.finish("已退出。")
    ai = AI()
    for i0 in range(12):
        ai.roll()
        for _ in range(3):
            await session.send(f'AI扔出骰子{ai.float_dice}，已固定骰子{ai.fixed_dice}\n剩余重扔次数：{ai.rolled_count}')
            await sleep(time)
            do, which = ai.process()
            if do == "计分":
                choose = Player.Name(which[0])
                ai.score(choose)
                await session.send("AI计分" + choose.name + ("。" if i0 == 11 else "，当前得分：\n" + ai.str_scoreboard))
                break
            else:
                await session.send("AI重扔" + ",".join(str(i) for i in which) + "。")
                ai.unfix(which)
                ai.roll()
    await session.send("最终得分：\n" + ai.str_scoreboard)

yahtzee = GameSameGroup('yahtzee')
config.CommandGroup(('play', 'yahtzee'), hide=True)
config.CommandGroup('yahtzee', des='快艇骰子是一个有趣的骰子游戏。游戏限2~6名玩家，玩家每轮扔5个骰子，并且可以重新扔任意数目的骰子至多三次，以凑出特定形状的组合赢得分数。计分板上共有12项：一到六为记扔出的骰子中所有该点数的总和；全选为全部骰子之和；四骰同花为扔出的五个骰子有四个相同，则记全部骰子之和的分数；葫芦为三个骰子点数相同，另外两个点数也相同的形状，记全部骰子之和的分数；小顺为有四个骰子成顺，记15分；大顺为五个骰子成顺，记30分；快艇为五个骰子全部相等，记50分。不满足形状的组合也可以在该项记0分。游戏共有12回合，每回合玩家扔完骰子后，必须从计分板里选择一项计分。特别的是，一到六这六项的分数总和若大于等于63分，则会额外奖励35分。12回合后计算总分，总分高者胜出。', short_des='快艇骰子。', hide_in_parent=True, display_parents='game')

@yahtzee.begin_uncomplete(('play', 'yahtzee', 'begin'), (2, 6))
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
async def yahtzee_process(session: NLPSession, data: Dict[str, Any], delete_func: Callable[[], Awaitable]):
    p: Player = data['boards'][data['current_player']]
    command = session.msg_text.strip()
    if command.startswith('重扔') and session.ctx['user_id'] == data['players'][data['current_player']]:
        if p.rolled_count <= 0:
            await session.send("您没有重扔次数！")
            return
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
                if m > 200:
                    for i, x in enumerate(f):
                        if x == m:
                            if achievement.yahtzee.get(str(data['players'][i])):
                                await session.send(achievement.yahtzee.get_str())
                await delete_func()
                return
        p = data['boards'][data['current_player']]
        p.roll()
        await session.send(f'轮到玩家{data["names"][data["current_player"]]}，扔出骰子{p.float_dice}，已固定骰子{p.fixed_dice}\n剩余重扔次数：{p.rolled_count}\n输入如"重扔 5,5,6"重扔，如"计分 快艇"计分')
    elif command == '查看分数' or command == '查询分数':
        await session.send('\n'.join(f'玩家{name}分数：\n{board.str_scoreboard}' for (name, board) in zip(data['names'], data['boards'])))
    elif command == '重新查询':
        await session.send(f'您当前扔出骰子{p.float_dice}，已固定骰子{p.fixed_dice}\n剩余重扔次数：{p.rolled_count}\n输入如"重扔 5,5,6"重扔，如"计分 快艇"计分')
