from copy import copy
import random
import re
from typing import Any, Awaitable, Callable
from nonebot import CommandSession, NLPSession
from ..game import GamePrivate, TRoomPrivate

pig = GamePrivate('pig')
pig.set_types({'3': (3, 3), '4': (4, 4)})

@pig.begin_uncomplete(('play', 'pig', 'begin'))
async def begin_command(session: CommandSession, room: TRoomPrivate):
    # args: -play.maj.begin 'type_str public/private+password' or '友人房id+password(optional)'
    pass

@pig.begin_complete(('play', 'pig', 'confirm'))
async def confirm_command(session: CommandSession, room: TRoomPrivate):
    room['board'] = Pig(room['players'], room['game'].send_private)
    board: Pig = room['board']
    n = '\n'
    room['game'].send(room, f"玩家座位为（逆时针）{n.join(str(q) for q in reversed(board.players))}")
    await board.begin()

@pig.quit(('play', 'pig', 'quit'))
async def quit_command(session: CommandSession, room: TRoomPrivate):
    pass

@pig.process(True)
async def process(session: NLPSession, room: TRoomPrivate, quit_func: Callable[[], Awaitable]):
    command = session.msg_text.strip()
    qq: int = session.ctx['user_id']
    board: Pig = room['board']
    if command == "查看分数":
        await session.send("\n".join(f"玩家{p}：{board.tensu[p]}" for p in board.players))
    elif command == "查看场况":
        await session.send("\n".join(f"玩家{p}：{board.show_pokers(board.tensu_hai[qq])}" for p in board.players) + ("" if len(board.maied) == 0 else "\n已卖：" + "，".join(board.mai_name(i) for i in board.maied)))
    elif command == "查看手牌":
        await room['game'].send_private(qq, board.show_pokers(board.hand_card[qq]))
    else:
        if qq not in board.wait_players:
            return
        if board.step == 0 and "卖" in command:
            if command == "不卖":
                await board.process(qq, 0)
            elif "卖变" in command:
                await board.process(qq, 21)
            elif "卖羊" in command:
                await board.process(qq, 48)
            elif "卖猪" in command:
                await board.process(qq, 10)
            elif "卖红" in command:
                await board.process(qq, 37)
        elif board.step == 1:
            hai = board.find_hai(command)
            if hai is not None:
                await board.process(qq, hai)

class Pig:
    suit = '♠♣♥♦'
    @classmethod
    def name(cls, i: int):
        return str(i) if i <= 9 else 'JQKA'[i - 10]
    has_point = {10, 21, 48} | set(range(26, 39))
    can_mai = {21, 48, 10, 37}
    @classmethod
    def mai_name(cls, i: int):
        return {21: "变压器", 48: "羊", 10: "猪", 37: "红心"}[i]

    hai_re = re.compile(r'(?:(♠|黑桃)|(♣|梅花|草花)|(♥|红心|红桃)|(♦|方块|方片))(A|\d+|J|Q|K)')
    @classmethod
    def find_hai(cls, s: str):
        match = cls.hai_re.search(s)
        if match is None:
            return None
        a, b, c, d, n = match.groups()
        base = 0 if a else 13 if b else 26 if c else 39
        num = 9 + 'JQKA'.index(n) if n in 'JQKA' else int(n) - 2
        return base + num
    
    def __init__(self, players: list[int], send: Callable[[int, str], Awaitable]) -> None:
        self.players = copy(players)
        random.shuffle(self.players)
        self.tensu = {p: 0 for p in self.players}
        self.if3 = len(self.players) == 3
        self.hand_card: dict[int, list[int]] = {p: [] for p in self.players}
        self.tensu_hai: dict[int, list[int]] = {p: [] for p in self.players}
        self.step: int = 0 # 0：询问卖阶段
        self.wait_players: list[int] = []
        self.maied: list[int] = []
        self.this_round: list[int] = []
        self.last_pig: int | None = None
        self.send = send
        self.init_poker()
    def init_poker(self):
        if self.if3:
            l = list(range(53))
            l.remove(13)
        else:
            l = list(range(53))
        random.shuffle(l)
        if self.if3:
            self.hand_card[self.players[0]] = sorted(l[0:18])
            self.hand_card[self.players[1]] = sorted(l[18:35])
            self.hand_card[self.players[2]] = sorted(l[35:52])
        else:
            self.hand_card[self.players[0]] = sorted(l[0:14])
            self.hand_card[self.players[1]] = sorted(l[14:27])
            self.hand_card[self.players[2]] = sorted(l[27:40])
            self.hand_card[self.players[3]] = sorted(l[40:53])
        self.tensu_hai = {p: [] for p in self.players}
    @classmethod
    def show_poker(cls, poker: int):
        return cls.suit[poker // 13] + cls.name(poker % 13)
    @classmethod
    def show_pokers(cls, pokers: list[int]):
        s = ''
        for i in pokers:
            c = cls.suit[i // 13]
            if c not in s:
                s += c
            s += cls.name(i % 13)
        return s
    def add_tensu_hai(self, player: int, hai: int):
        self.tensu_hai[player].append(hai)
        self.tensu_hai[player].sort()
    async def begin(self):
        for p in self.players:
            await self.send(p, "你的手牌为：" + self.show_pokers(self.hand_card[p]))
        await self.ask_mai()
    async def ask_mai(self):
        self.step = 0
        self.maied = []
        can_mai: dict[int, set[int]] = {p: set(self.hand_card[p]) & self.can_mai for p in self.players}
        self.wait_players = [p for p, s in can_mai.items() if len(s) != 0]
        for p, s in can_mai.items():
            if len(s) == 0:
                await self.send(p, "等待其他玩家卖...")
            else:
                await self.send(p, "是否要卖？请回答“不卖”或是“卖xxx”。")
    async def begin_step1(self):
        self.step == 1
        if self.last_pig is None:
            self.wait_players = [[p for p, s in self.hand_card.items() if 0 in s][0]]
        else:
            self.wait_players = [self.last_pig]
        for p in self.players:
            if p in self.wait_players:
                await self.send(p, "请出一张牌。")
            else:
                await self.send(p, f"游戏开始，等待玩家{self.wait_players[0]}出牌...")
    async def process(self, player: int, choose: int):
        if self.step == 0:
            if choose == 0:
                self.wait_players.pop(player)
                await self.send(player, "已不卖。")
                if len(self.wait_players) == 0:
                    await self.begin_step1()
            elif choose in self.hand_card[player]:
                self.maied.append(choose)
                await self.send(player, "已卖。")
                for p in self.players:
                    if p != player:
                        await self.send(p, f"玩家{player}已卖{self.mai_name(choose)}。")
                if len(self.maied) == 3:
                    s = list(self.can_mai - set(self.maied))[0]
                    remain = [p for p, c in self.hand_card.items() if s in c][0]
                    await self.send(remain, f"其余三个均已被卖，已自动为你卖{self.mai_name(s)}。")
                    for p in self.players:
                        if p != remain:
                            await self.send(p, f"其余三个均已被卖，玩家{remain}已自动卖{self.mai_name(s)}。")
                    self.maied = list(self.can_mai)
                    self.wait_players = []
                    await self.begin_step1()
                else:
                    can_mai = (set(self.hand_card[player]) & self.can_mai) - set(self.maied)
                    if len(can_mai):
                        await self.send(player, "是否继续卖？请回答“不卖”或是“卖xxx”。")
                    else:
                        self.wait_players.pop(player)
                        if len(self.wait_players) == 0:
                            await self.begin_step1()
        elif self.step == 1:
            if choose not in self.hand_card[player]:
                await self.send(player, "该牌不在你手牌里。")
                return
            # check self.this_round
            self.this_round.append(choose)
            for p in self.players:
                if p in self.wait_players:
                    await self.send(p, f"你出了{self.show_poker(choose)}。")
                else:
                    await self.send(p, f"玩家{self.wait_players[0]}出了{self.show_poker(choose)}。")
            self.wait_players = [(p := self.players[self.players.index(player) - 1])]
            await self.send(p, "请出一张牌。")

