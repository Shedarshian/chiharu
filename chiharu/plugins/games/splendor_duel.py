from typing import TypedDict
import itertools, more_itertools, random
from collections import Counter
from enum import Enum, auto
from PIL import Image, ImageDraw, ImageChops, ImageFont
import base64
from nonebot import CommandSession
# from .. import config, game
# from ..config import on_command
# from ..game import GameSameGroup
# from .achievement import achievement, cp, cp_add

class Card:
    def __init__(self, c: dict[str, str]) -> None:
        self.id = int(c["id"])
        self.level = int(c["level"])
        self.point = int(c["point"])
        self.color = c["color"]
        self.profit = int(c["profit"])
        self.special: str | None = c["special"]
        self.crown = int(c["crown"] or 0)
        self.price = Counter({r: int(c["cost_" + r.name] or 0) for r in Color.all_board_tokens()})
def ReadCards() -> list[Card]:
    from pathlib import Path
    import csv
    with (Path(__file__).parent / "splendor_duel.csv").open(encoding="utf-8-sig") as f:
        return [Card(row) for row in csv.DictReader(f)] # type: ignore
all_cards = ReadCards()
def GetCard(i: int) -> Card:
    return all_cards[i]
class Color(Enum):
    white = auto()
    blue = auto()
    green = auto()
    red = auto()
    black = auto()
    pink = auto()
    gold = auto()
    gray = auto()
    @classmethod
    def all_gems(cls):
        return Color.white, Color.blue, Color.green, Color.red, Color.black
    @classmethod
    def all_board_tokens(cls):
        return Color.white, Color.blue, Color.green, Color.red, Color.black, Color.pink
    @classmethod
    def all_tokens(cls):
        return Color.white, Color.blue, Color.green, Color.red, Color.black, Color.pink, Color.gold
    @classmethod
    def all_cards(cls):
        return Color.white, Color.blue, Color.green, Color.red, Color.black, Color.gray

def TokenImg(c: Color, num: int=1, isPrice: bool=False, outline: bool=False) -> Image:
    img = Image.new("RGBA", (24, 24), "#00000000")
    dr = ImageDraw.Draw(img)
    color = "#ffa2af" if c == Color.pink else "yellow" if c == Color.gold else c.name
    dr.ellipse((0, 0, 23, 23), fill="#f0cab2", outline=color, width=4)
    if outline:
        dr.ellipse((0, 0, 23, 23), fill=None, outline="black", width=1)
    if num != 1 and not isPrice:
        font = ImageFont.truetype("msyhbd.ttc", 10)
        dr.text((12, 12), str(num), fill="black", font=font, anchor="mm")
    elif c == Color.pink:
        dr.ellipse((8, 8, 15, 15), fill=color, width=0)
    else:
        dr.regular_polygon((12, 12, 5), 4 if c == Color.gold else 3, fill=color)
    return img
def CardImg(c: Card):
    img = Image.new("RGBA", (128, 64), "#00000000")
    dr = ImageDraw.Draw(img)
    color = "#ffa2af" if c.color == "pink" else "yellow" if c.color == "gold" else "gray" if c.color == "imitate" else "silver" if c.color == "white" else c.color
    dr.rounded_rectangle((0, 0, 127, 40), radius=8, fill=color, outline="black", width=1)
    dr.rounded_rectangle((0, 24, 127, 64), radius=8, fill="white", outline="black", width=1)
    dr.rectangle((1, 24, 126, 31), fill=color)
    if c.color == "imitate":
        pass
    else:
        for i in range(c.profit):
            token = TokenImg(Color[c.color], outline=True)
            img.paste(token, (100 - 24 * i, 4))
    return img

class Player:
    def __init__(self, board: 'Board', id: int) -> None:
        self.board = board
        self.id = id
        self.tokens: Counter[Color] = Counter({key: 0 for key in Color.all_tokens()})
        self.scroll = 0
        self.cards: dict[Color, list[Card]] = {key: [] for key in Color.all_cards()}
        self.reserve_cards: list[Card] = []
    @property
    def opponent(self):
        return self.board.players[1 - self.id]
    @property
    def crown(self) -> int:
        return sum(c.crown or 0 for c in itertools.chain(*self.cards.values()))
    @property
    def points(self) -> Counter[Color]:
        return Counter({c: sum(x.point for x in l) for c, l in self.cards.items()})
    @property
    def sum_points(self) -> int:
        return sum(c.point for c in itertools.chain(*self.cards.values()))
    @property
    def card_tokens(self) -> Counter[Color]:
        return Counter({c: sum(x.profit for x in l) for c, l in self.cards.items() if c != Color.gray})
    @property
    def total_tokens(self) -> int:
        return self.tokens.total()
    
    def GetScroll(self):
        if self.board.scroll >= 1:
            self.board.scroll -= 1
        elif self.scroll < 3:
            self.opponent.scroll -= 1
        else:
            return -1
        self.scroll += 1
        return 1
    def GetToken(self, i: int, j: int):
        t = self.board.popToken(i, j)
        if t is None:
            return -1
        self.tokens[t] += 1
        return t
    
    def UseScroll(self, l: list[tuple[int, int]]):
        """-1: 卷轴数量不够，-2: 无法拿取空格子或金币。"""
        if len(l) > self.scroll:
            return -1
        for i, j in l:
            if self.board.board_tokens[i][j] in (None, Color.gold):
                return -2
        self.scroll -= len(l)
        self.board.scroll += len(l)
        for i, j in l:
            self.GetToken(i, j)
        return 1
    def RefillToken(self):
        self.board.RefillToken()
        self.opponent.GetScroll()
        return 1
    def GetLineToken(self, i: int, j: int, i2: int=-1, j2: int=-1, i3: int=-1, j3: int=-1):
        """-1: 下标越界或不在一条线上，2: 对手获得一个卷轴。"""
        if i2 == j2 == i3 == j3 == -1:
            return -1 if self.GetToken(i, j) == -1 else 1
        if not self.board.checkLine(i, j, i2, j2, i3, j3):
            return -1
        t1 = self.GetToken(i, j)
        t2 = self.GetToken(i2, j2)
        c = (1 if t1 == Color.pink else 0) + (1 if t2 == Color.pink else 0)
        if not i3 == j3 == -1:
            t3 = self.GetToken(i3, j3)
            if t1 == t2 == t3:
                self.opponent.GetScroll()
                return 2
            c += (1 if t3 == Color.pink else 0)
        if c == 2:
            self.opponent.GetScroll()
            return 2
        return 1
    def BuyCard(self, i: int, j: int):
        """购买已预订卡时i为3。-1: 下标越界，-2: 货币不足，-3: 无法模仿，2: 选择模仿颜色，3: 选择偷取颜色，4: 选择获取token，5: 选择皇冠卡。"""
        if not (0 <= i < 3 and 0 <= j < len(self.board.pyramid[i]) or i == 3 and 0 <= j < len(self.reserve_cards)):
            return -1
        card = self.board.pyramid[i][j] if i < 3 else self.reserve_cards[j]
        if card.color == "imitate" and all(len(l) == 0 for l in self.cards.values()):
            return -3
        remain = Counter(self.tokens + self.card_tokens)
        remain.subtract(card.price)
        lack = sum(-n for c, n in remain.items() if n < 0)
        if lack > remain[Color.gold]:
            return -2
        for c in remain:
            if remain[c] < 0:
                remain[Color.gold] += remain[c]
                remain[c] = 0
        self.board.tokens.extend((self.tokens - remain).elements())
        self.tokens = remain
        if i < 3:
            if len(self.board.cards[i]) > 0:
                self.board.pyramid[i][j] = self.board.cards[i].pop()
            else:
                self.reserve_cards.pop(j)
        else:
            self.reserve_cards.pop(j)
        if card.color == "imitate":
            while 1:
                st = yield 2
                if st not in Color or (c := Color[st]) not in Color.all_cards() or len(self.cards[c]) == 0:
                    continue
                break
        else:
            c = Color[card.color]
        for num in range(2):
            self.cards[c].append(card)
            sp = card.special
            if sp == "turn":
                self.board.next_player_id = self.id
            elif sp == "scroll":
                self.GetScroll()
            elif sp == "steal":
                if not all(x == 0 for c, x in self.opponent.tokens.items() if c != Color.gold):
                    while 1:
                        st = yield 3
                        if st not in Color or (c := Color[st]) not in Color.all_board_tokens() or self.opponent.tokens[c] == 0:
                            continue
                        break
                    self.opponent.tokens[c] -= 1
                    self.tokens[c] += 1
            elif sp == "gem":
                if not all(x != card.color for x in self.board.board_tokens):
                    while 1:
                        it, jt = yield 4
                        if not isinstance(it, int) or not isinstance(jt, int) or not (0 <= it < 5 and 0 <= jt < 5 and self.board.board_tokens[i][j] == card.color):
                            continue
                        break
                    t = self.board.popToken(i, j)
                    if t is not None:
                        self.tokens[t] += 1
            if num == 1:
                break
            crown = self.crown
            curr = len(list(c for c in self.cards[Color.gray] if c.level == 3))
            if curr == 0 and crown >= 3 or curr == 1 and crown >= 6:
                while 1:
                    ic = yield 5
                    if not isinstance(ic, int) or not 0 <= ic < len(self.board.pyramid[3]):
                        continue
                    break
                card = self.board.pyramid[3].pop(ic)
                c = Color.gray
                continue
            break
        return 1
    def ReserveCard(self, i: int, j: int, ic: int, jc: int):
        """盲抽时jc为-1。-1: 下标越界或所选中的不是金币，-2: 栏位不足"""
        if not (0 <= i < 5 and 0 <= j < 5 and self.board.board_tokens[i][j] == Color.gold and 0 <= ic < 3 and -1 <= jc < len(self.board.pyramid[ic])):
            return -1
        if len(self.reserve_cards) == 3:
            return -2
        if jc == -1:
            if len(self.board.cards[ic]) == 0:
                return -1
            card = self.board.cards[ic].pop()
        else:
            card = self.board.pyramid[ic][jc]
            if len(self.board.cards[ic]) > 0:
                self.board.pyramid[ic][jc] = self.board.cards[ic].pop()
            else:
                self.board.pyramid[ic].pop(jc)
        token = self.board.popToken(i, j)
        self.tokens[Color.gold] += 1
        self.reserve_cards.append(card)
        return 1
    def DiscardToken(self, l: list[Color]):
        c = Counter(l)
        if not c <= self.tokens:
            return -1
        self.tokens.subtract(c)
        return 1
    def CheckWin(self):
        return max(self.points.values()) >= 10 or self.crown >= 10 or self.sum_points >= 20

class Board:
    def __init__(self) -> None:
        self.tokens: list[Color] = Color.all_gems() * 4 + [Color.pink] * 2 + [Color.gold] * 3
        self.board_tokens: list[list[Color | None]] = [[None] * 5] * 5
        self.scroll = 3
        self.cards = [all_cards[:30], all_cards[30:54], all_cards[54:67], all_cards[67:]]
        for i in range(4):
            random.shuffle(self.cards[i])
        self.pyramid: list[list[Card]] = [[], [], [], []]
        for j in range(3):
            for i in range(5 - j):
                self.pyramid[j].append(self.cards[j].pop())
        self.pyramid[4] = [c for c in self.cards[3]]
        self.players = (Player(self, 0), Player(self, 1))
        self.current_player_id = 0
        self.next_player_id = 0
        self.RefillToken()
        self.players[1].GetScroll()
    @property
    def current_player(self):
        return self.players[self.current_player_id]
    def popToken(self, i: int, j: int):
        if 0 <= i < 5 and 0 <= j < 5:
            t = self.board_tokens[i][j]
            self.board_tokens[i][j] = None
            return t
        return None
    def checkLine(self, i: int, j: int, i2: int, j2: int, i3: int=-1, j3: int=-1):
        if not (0 <= i < 5 and 0 <= j < 5 and 0 <= i2 < 5 and 0 <= j2 < 5 and (0 <= i3 < 5 and 0 <= j3 < 5 or (i3, j3) == (-1, -1))):
            return False
        if self.board_tokens[i][j] in (None, Color.gold) or self.board_tokens[i2][j2] in (None, Color.gold) or ((i3, j3) != (-1, -1) and self.board_tokens[i3][j3] in (None, Color.gold)):
            return False
        a = sorted([(i, j), (i2, j2), (i3, j3)])
        d1 = (a[2][0] - a[1][0], a[2][1] - a[1][1])
        d2 = d1 if (i3, j3) == (-1, -1) else (a[1][0] - a[0][0], a[1][1] - a[0][1])
        if d1 == d2 and d1 in ((1, 0), (0, 1), (1, 1)):
            return True
        return False
    
    def RefillToken(self):
        if len(self.tokens) == 0:
            return -1
        random.shuffle(self.tokens)
        for n in (33, 43, 42, 32, 22, 23, 24, 34, 44, 54, 53, 52, 51, 41, 31, 21, 11, 12, 13, 14, 15, 25, 35, 45, 55):
            if len(self.tokens) == 0:
                return 1
            i = n // 10 - 1
            j = n % 10 - 1
            if self.board_tokens[i][j] is None:
                self.board_tokens[i][j] = self.tokens.pop()
        return 1
    def NextTurn(self):
        self.current_player_id = self.next_player_id
        self.next_player_id = 1 - self.current_player_id


# sp2 = GameSameGroup('splendor_duel')
# config.CommandGroup(('play', 'splendor_duel'), hide=True)
# config.CommandGroup('splendor_duel', des='璀璨宝石：对决。', short_des='璀璨宝石：对决。', hide_in_parent=True, display_parents='game')




