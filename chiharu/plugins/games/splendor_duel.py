from typing import Any, Awaitable, Callable, Literal, Generator, Annotated
import itertools, random, math, re
from collections import Counter
from enum import Enum, auto
from PIL import Image, ImageDraw, ImageFont
import base64, aiocqhttp
from nonebot import CommandSession, NLPSession
from .. import config, game
from ..config import on_command
from ..game import GameSameGroup
from .achievement import achievement, cp, cp_add

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
    @property
    def code(self):
        return "#ffa2af" if self == Color.pink else "yellow" if self == Color.gold else self.name
    @classmethod
    def choose(cls, c: str):
        return {"白": Color.white, "黑": Color.black, "红": Color.red, "绿": Color.green, "蓝": Color.blue, "金": Color.gold, "粉": Color.pink, "珍珠": Color.pink, "钻石": Color.white}[c]
class Card:
    def __init__(self, c: dict[str, str]) -> None:
        self.id = int(c["id"])
        self.level = int(c["level"])
        self.point = int(c["point"])
        self.color = c["color"]
        self.profit = int(c["profit"])
        self.special = c["special"]
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

def TokenImg(c: Color, num: int=1, isPrice: bool=False, outline: bool=True, size: int=1):
    img = Image.new("RGBA", (24 * size, 24 * size), "#00000000")
    dr = ImageDraw.Draw(img)
    if c == Color.gray:
        for i, d in enumerate(Color.all_gems()):
            dr.pieslice((3 * size, 3 * size, 21 * size - 1, 21 * size - 1), start=72 * i, end=72 * (i + 1), fill=d.code)
    dr.ellipse((0, 0, 24 * size - 1, 24 * size - 1), fill="#f0cab2", outline=c.code, width=(5, 8)[size - 1])
    if outline:
        dr.ellipse((0, 0, 24 * size - 1, 24 * size - 1), fill=None, outline="black", width=1)
    if num != 1 or isPrice:
        font = ImageFont.truetype("msyhbd.ttc", 10 * size)
        dr.text((12 * size, 12 * size), str(num), fill="black", font=font, anchor="mm")
    elif c == Color.pink:
        dr.ellipse((8 * size, 8 * size, 16 * size - 1, 16 * size - 1), fill=c.code, width=0)
    else:
        dr.regular_polygon((12 * size, 12 * size, 5 * size), 4 if c == Color.gold else 3, fill=c.code)
    return img
CARDHEIGHT = 64
CARDWIDTH = 128
def CardImg(c: Card):
    img = Image.new("RGBA", (CARDWIDTH, CARDHEIGHT), "#00000000")
    dr = ImageDraw.Draw(img)
    color = "#ffa2af" if c.color == "pink" else "yellow" if c.level == 3 else "gray" if c.color == "imitate" else "silver" if c.color == "white" else c.color
    dr.rounded_rectangle((0, 0, 127, 40), radius=8, fill=color, outline="black", width=1)
    dr.rounded_rectangle((0, 24, 127, 63), radius=8, fill="white", outline="black", width=1)
    dr.rectangle((1, 24, 126, 31), fill=color)
    # upper right corner: profit
    for i in range(c.profit):
        token = TokenImg(Color.gray if c.color == "imitate" else Color[c.color])
        img.alpha_composite(token, (100 - 20 * i, 4))
    # upper middle: crown
    if c.crown != 0:
        dr.regular_polygon((64, 16, 12), 5, fill="yellow")
        if c.crown != 1:
            font = ImageFont.truetype("msyhbd.ttc", 10)
            dr.text((64, 16), str(c.crown), "black", font, anchor="mm")
    # upper left corner: point
    if c.point != 0:
        font = ImageFont.truetype("msyhbd.ttc", 24)
        dr.text((16, 16), str(c.point), "white" if c.color in ("black", "blue") else "black", font, anchor="mm")
    # lower left corner: special
    if c.special != "":
        dr.ellipse((4, 36, 28, 60), "purple")
        font = ImageFont.truetype("msyhbd.ttc", 18)
        match c.special:
            case "steal":
                dr.text((17, 48), "S", "white", font, anchor="mm")
            case "scroll":
                dr.text((16, 48), "P", "white", font, anchor="mm")
            case "gem":
                dr.regular_polygon((16, 48, 6), 3, fill="white")
            case "turn":
                dr.text((17, 48), "T", "white", font, anchor="mm")
    # lower right: cost
    for i, (d, n) in enumerate(reversed([(e, n) for e, n in c.price.items() if n != 0])):
        token = TokenImg(d, n, True)
        img.alpha_composite(token, (100 - 28 * i, 36))
    # lower right: 3/6 crown
    if c.level == 3:
        font = ImageFont.truetype("msyhbd.ttc", 10)
        dr.regular_polygon((114, 50, 12), 5, fill="yellow", outline="black")
        dr.regular_polygon((86, 50, 12), 5, fill="yellow", outline="black")
        dr.text((114, 50), "6", "black", font, anchor="mm")
        dr.text((86, 50), "3", "black", font, anchor="mm")
        dr.line((103, 38, 95, 62), "black", 1)
    return img
def CardBack(lv: int):
    img = Image.new("RGBA", (CARDWIDTH, CARDHEIGHT), "#00000000")
    dr = ImageDraw.Draw(img)
    color = {0: "darkseagreen", 1: "darkorange", 2: "darkslateblue"}.get(lv, "white")
    dr.rounded_rectangle((0, 0, 127, 63), radius=8, fill=color, outline="black", width=1)
    for i in range(lv + 1):
        dr.ellipse((60 + 12 * i - 6 * lv, 36, 67 + 12 * i - 6 * lv, 43), fill="white")
    return img
def GemCorr(s: str | None):
    if s is None or len(s) < 2 or s[0] not in 'ABCDE' or s[1] not in '12345':
        return (-1, -1)
    return ('12345'.index(s[1]), 'ABCDE'.index(s[0]))

class Player:
    def __init__(self, board: 'Board', id: int) -> None:
        self.board = board
        self.id = id
        self.tokens: Counter[Color] = Counter({key: 0 for key in Color.all_tokens()})
        self.scroll = 0
        self.cards: dict[Color, list[Card]] = {key: [] for key in Color.all_cards()}
        self.reserve_cards: list[Card] = []
        self.state: Literal[0, 1, 2, 3, 4, 5] = 0 # 0: begin, 1: discard, 2-5: buying
        self.buyCardState: Generator[Literal[2, 3, 4, 5], Any, Literal[-1, -3, -2, 1]] | None = None
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
    @property
    def max_card_len(self):
        return max(len(l) for l in self.cards.values())
    
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
        """-1: 卷轴数量不够，-2: 无法拿取空格子或金子。"""
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
        if self.board.RefillToken() == -1:
            return -1
        self.opponent.GetScroll()
        return 1
    def GetLineToken(self, pos1: tuple[int, int], pos2: tuple[int, int]=(-1, -1), pos3: tuple[int, int]=(-1, -1)):
        """-1: 下标越界或不在一条线上，2: 对手获得一个卷轴。"""
        i, j = pos1; i2, j2 = pos2; i3, j3 = pos3
        if i2 == j2 == i3 == j3 == -1:
            return -1 if self.GetToken(i, j) == -1 else 1
        if not self.board.checkLine(pos1, pos2, pos3):
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
    def BuyCard(self, i: int, j: int) -> Generator[Literal[2, 3, 4, 5], Any, Literal[-1, -3, -2, 1]]:
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
        for cr in remain:
            if remain[cr] < 0:
                remain[Color.gold] += remain[cr]
                remain[cr] = 0
        self.board.tokens.extend((self.tokens - remain).elements())
        self.tokens = self.tokens - (self.tokens - remain)
        if i < 3:
            if len(self.board.cards[i]) > 0:
                self.board.pyramid[i][j] = self.board.cards[i].pop()
            else:
                self.reserve_cards.pop(j)
        else:
            self.reserve_cards.pop(j)
        if card.color == "imitate":
            while 1:
                c: Color = yield 2
                if c not in Color.all_cards() or len(self.cards[c]) == 0:
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
                        c = yield 3
                        if c not in Color.all_board_tokens() or self.opponent.tokens[c] == 0:
                            continue
                        break
                    self.opponent.tokens[c] -= 1
                    self.tokens[c] += 1
            elif sp == "gem":
                if any(any(y == card.color for y in x) for x in self.board.board_tokens):
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
        """盲抽时jc为-1。-1: 下标越界或所选中的不是金子，-2: 栏位不足"""
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
        self.board.tokens.extend(c.elements())
        return 1
    def CheckWin(self):
        return max(n for i, n in self.points.items() if i != Color.gray) >= 10 or self.crown >= 10 or self.sum_points >= 20

    def TokenImg(self):
        img = Image.new("RGBA", (8 * 64, 2 * 64), "#00000000")
        # 512, 128
        m = math.ceil(self.tokens.total() / 2)
        x = 4
        j = 0
        for c, n in self.tokens.items():
            length = 28 * (n + 1)
            if x + length >= 7 * 64:
                x = 4
                j = 1
            if n != 0:
                x += length
            for i in range(n):
                img.alpha_composite(TokenImg(c, size=2), (x - 28 * (i + 1), j * 64))
        return img
    def ReserveImg(self):
        dist = 24
        img = Image.new("RGBA", (3 * (CARDHEIGHT + dist), 128), "#00000000")
        # 264, 128 无右侧空间
        dr = ImageDraw.Draw(img)
        for i, c in enumerate(self.reserve_cards):
            t = CardImg(c).rotate(90, expand=1).crop((0, 0, 64, 128))
            img.alpha_composite(t, (i * (CARDHEIGHT + dist) + dist, 0))
            dr.text((i * (CARDHEIGHT + dist) + dist - 1, 21), "pqr"[i], "black", self.board.alpha_font, "rt")
        return img
    def ScrollImg(self):
        img = Image.new("RGBA", (32, 128), "#00000000")
        # 32, 128
        if self.scroll == 0:
            return img
        dr = ImageDraw.Draw(img)
        font = ImageFont.truetype("msyhbd.ttc", 18)
        for i in range(self.scroll):
            dr.ellipse((4, 4 + 32 * i, 28, 28 + 32 * i), "purple")
            dr.text((16, 16 + 32 * i), "P", "white", font, anchor="mm")
        return img
    def CardImg(self):
        wdist = 4
        hdist = 4
        def pos(w: float, h: float, offset: tuple[int, int]=(0, 0)):
            return int(w * (CARDWIDTH + wdist) + wdist) + offset[0], int(h * (CARDHEIGHT // 2 + hdist) + hdist) + offset[1]
        # 下方没有空像素
        img = Image.new("RGBA", pos(6, 9, (0, CARDHEIGHT // 2)), "#00000000")
        # 796, 328
        dr = ImageDraw.Draw(img)
        for i, (c, l) in enumerate(self.cards.items()):
            for j, card in enumerate(l):
                img.alpha_composite(CardImg(card), pos(i, j))
        return img
    def Img(self):
        color = ["lightblue", "lightpink"][self.id]
        img = Image.new("RGBA", (810, 464), color)
        img.alpha_composite(self.CardImg(), (7, 0))
        img.alpha_composite(self.ReserveImg(), (0, 334))
        img.alpha_composite(self.ScrollImg(), (266, 334))
        img.alpha_composite(self.TokenImg(), (298, 334))
        return img

class Board:
    def __init__(self) -> None:
        self.tokens: list[Color] = list(Color.all_gems()) * 4 + [Color.pink] * 2 + [Color.gold] * 3
        self.board_tokens: list[list[Color | None]] = [[None] * 5 for i in range(5)]
        self.scroll = 3
        self.cards = [all_cards[:30], all_cards[30:54], all_cards[54:67], all_cards[67:]]
        for i in range(3):
            random.shuffle(self.cards[i])
        self.pyramid: list[list[Card]] = [[], [], [], []]
        for j in range(3):
            for i in range(5 - j):
                self.pyramid[j].append(self.cards[j].pop())
        self.pyramid[3] = [c for c in self.cards[3]]
        self.players = (Player(self, 0), Player(self, 1))
        self.current_player_id = 0
        self.next_player_id = 1
        self.RefillToken()
        self.players[1].GetScroll()
        self.alpha_font = ImageFont.truetype("msyhbd.ttc", 16)
    @property
    def current_player(self):
        return self.players[self.current_player_id]
    @property 
    def has_gem(self):
        return not all(all(c in (None, Color.gold) for c in x) for x in self.board_tokens)
    @property 
    def has_gold(self):
        return any(any(c == Color.gold for c in x) for x in self.board_tokens)
    def popToken(self, i: int, j: int):
        if 0 <= i < 5 and 0 <= j < 5:
            t = self.board_tokens[i][j]
            self.board_tokens[i][j] = None
            return t
        return None
    def checkLine(self, pos1: tuple[int, int], pos2: tuple[int, int], pos3: tuple[int, int]=(-1, -1)):
        i, j = pos1; i2, j2 = pos2; i3, j3 = pos3
        if not (0 <= i < 5 and 0 <= j < 5 and 0 <= i2 < 5 and 0 <= j2 < 5 and (0 <= i3 < 5 and 0 <= j3 < 5 or (i3, j3) == (-1, -1))):
            return False
        if self.board_tokens[i][j] in (None, Color.gold) or self.board_tokens[i2][j2] in (None, Color.gold) or ((i3, j3) != (-1, -1) and self.board_tokens[i3][j3] in (None, Color.gold)):
            return False
        a = sorted([(i, j), (i2, j2), (i3, j3)])
        d1 = (a[2][0] - a[1][0], a[2][1] - a[1][1])
        d2 = d1 if (i3, j3) == (-1, -1) else (a[1][0] - a[0][0], a[1][1] - a[0][1])
        if d1 == d2 and d1 in ((1, 0), (0, 1), (1, 1), (1, -1)):
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
        pass#self.current_player_id = self.next_player_id
        #self.next_player_id = 1 - self.current_player_id

    def BoardImg(self):
        def pos(w: int, h: int, offset: tuple[int, int]=(0, 0)):
            return w * 64 + offset[0] + 16, h * 64 + offset[1] + 112
        img = Image.new("RGBA", pos(5, 5), "#00000000")
        # 336, 440
        dr = ImageDraw.Draw(img)
        dr.rounded_rectangle((pos(0, 0), pos(5, 5)), radius=16, fill="saddlebrown", outline="black", width=1)
        for i in range(5):
            for j in range(5):
                dr.rounded_rectangle((pos(i, j, (4, 4)), pos(i + 1, j + 1, (-4, -4))), radius=8, fill="antiquewhite")
        curr = (2, 2)
        for n in (1, 2, 3, 3, 0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3, 3, 0, 0, 0, 0, 1, 1, 1, 1):
            dr.regular_polygon(pos(*curr, (32, 32)) + (8,), 3, 270 - 90 * n, "black")
            next = curr[0] + (a := [(1, 0), (0, 1), (-1, 0), (0, -1)][n])[0], curr[1] + a[1]
            dr.line(pos(*curr, (32, 32)) + pos(*next, (32, 32)), "black", 3)
            curr = next
        for i in range(5):
            for j in range(5):
                if self.board_tokens[j][i] is None:
                    continue
                token = TokenImg(self.board_tokens[j][i], size=2) # type: ignore
                img.alpha_composite(token, pos(i, j, (9, 9)))
            dr.text(pos(0, i, (-1, 21)), str(i + 1), "black", self.alpha_font, "rt")
            dr.text(pos(i, 0, (21, -1)), "ABCDE"[i], "black", self.alpha_font, "lb")
        # TODO 右上角剩余币数
        return img
    def PyramidImg(self):
        wdist = 20
        hdist = 8
        def pos(w: float, h: float, offset: tuple[int, int]=(0, 0)):
            return int(w * (CARDWIDTH + wdist) + wdist) + offset[0], int(h * (CARDHEIGHT + hdist) + hdist) + offset[1]
        img = Image.new("RGBA", pos(3, 6), "#00000000")
        # 464, 440
        dr = ImageDraw.Draw(img)
        for i in range(3):
            for j, card in enumerate(self.pyramid[i]):
                img.alpha_composite(CardImg(card), pos(2 - i, j + 0.5 * i))
                dr.text(pos(2 - i, j + 0.5 * i, (-1, 21)), ("jklmn", "efgh", "abc")[i][j], "black", self.alpha_font, "rt")
        for i in range(3):
            if len(self.cards[i]) == 0:
                continue
            img.alpha_composite(CardBack(i), pos(2 - i, 5))
            dr.text(pos(2 - i, 5, (-1, 21)), "oid"[i], "black", self.alpha_font, "rt")
        return img
    def MiddleImg(self):
        hdist = 20
        img = Image.new("RGBA", (810, 64), "#00000000")
        dr = ImageDraw.Draw(img)
        for i, c in enumerate(self.pyramid[3]):
            img.alpha_composite(CardImg(c), (i * (CARDWIDTH + hdist) + hdist, 0))
            dr.text((i * (CARDWIDTH + hdist) + hdist - 1, 21), "stuv"[i], "black", self.alpha_font, "rt")
        font = ImageFont.truetype("msyhbd.ttc", 18)
        for i in range(self.scroll):
            dr.ellipse((616 + 32 * i, 12, 640 + 32 * i, 36), "purple")
            dr.text((628 + 32 * i, 24), "P", "white", font, anchor="mm")
        return img
    def Img(self, player_id: int, vertical: bool):
        if vertical:
            img = Image.new("RGBA", (810, 1440), "antiquewhite")
            img.alpha_composite(self.players[1 - player_id].Img().rotate(180), (0, 0))
            img.alpha_composite(self.MiddleImg(), (0, 466))
            img.alpha_composite(self.PyramidImg(), (0, 532))
            img.alpha_composite(self.BoardImg(), (464, 532))
            img.alpha_composite(self.players[player_id].Img(), (0, 974))
        else:
            img = Image.new("RGBA", (1274, 996), "antiquewhite")
            img.alpha_composite(self.players[1 - player_id].Img().rotate(180), (472, 0))
            img.alpha_composite(self.MiddleImg(), (472, 466))
            img.alpha_composite(self.players[player_id].Img(), (472, 532))
            img.alpha_composite(self.PyramidImg(), (0, 12))
            img.alpha_composite(self.BoardImg(), (52, 544))
        return img
    def SaveImg(self, player_id: int, vertical: bool):
        self.Img(player_id, vertical).save(config.img('sp2.png'))
        return config.cq.img('sp2.png')

sp2 = GameSameGroup('splendor2')
config.CommandGroup(('play', 'splendor2'), hide=True)
config.CommandGroup('splendor2', des='璀璨宝石：对决。', short_des='璀璨宝石：对决。', hide_in_parent=True, display_parents='game')

@sp2.begin_uncomplete(('play', 'splendor2', 'begin'), (2, 2))
async def sp2_begin_uncomplete(session: CommandSession, data: dict[str, Any]):
    # data: {'players': [qq], 'args': [args], 'anything': anything}
    name = await GameSameGroup.get_name(session)
    data['names'] = [name]
    await session.send(f'玩家{name}已参与匹配，等待第二人。')

@sp2.begin_complete(('play', 'splendor2', 'confirm'))
async def sp2_begin_complete(session: CommandSession, data: dict[str, Any]):
    # data: {'players': [qq], 'game': GameSameGroup instance, 'args': [args], 'anything': anything}
    qq = session.ctx['user_id']
    name = await GameSameGroup.get_name(session)
    data['names'].append(name)
    data['vertical'] = [True, True]
    await session.send(f'玩家{name}已参与匹配，游戏开始。游戏时可随时使用“切换横向”或“切换纵向”来切换ui排布。')
    # 开始游戏
    data['board'] = board = Board()
    await session.send([board.SaveImg(0, data['vertical'][0])])
    await session.send(f"玩家{data['names'][0]}先手，请选择操作：使用特权、填充宝石、拿宝石、买卡、预购卡。回复“帮助”查询如何使用指令。")

@sp2.end(('play', 'splendor2', 'end'))
async def sp2_end(session: CommandSession, data: dict[str, Any]):
    await session.send('已删除')

@sp2.process(only_short_message=True)
@config.ErrorHandle
async def sp2_process(session: NLPSession, data: dict[str, Any], delete_func: Callable[[], Awaitable]):
    command = session.msg_text.strip()
    user_id: Literal[0] | Literal[1] = data['players'].index(session.ctx['user_id'])
    if command.startswith("帮助"):
        await session.send("例1：使用特权B2；使用卷轴B4 C1\n例2：填充宝石；填充\n例3：拿A1 B2 C3；拿宝石A4 B4\n例4：买j；买卡r\n例5：预购a C2；预购卡i 宝石B3")
    elif command == "切换横向":
        data['vertical'][user_id] = False
        await session.send("已切换。")
    elif command == "切换纵向":
        data['vertical'][user_id] = True
        await session.send("已切换。")
    else:
        board: Board = data['board']
        if user_id != board.current_player_id:
            return
        player = board.current_player
        next_turn = False
        async def proceed_buy(buying: Callable[[], Literal[2, 3, 4, 5]], this: int):
            try:
                ret = buying()
                player.state = ret
                if ret == 2:
                    await session.send("请模仿你已有的颜色！" if this == 2 else "请选择模仿卡所模仿的颜色。")
                elif ret == 3:
                    await session.send("请偷取对手有的颜色！" if this == 3 else "请选择偷取的宝石颜色。")
                elif ret == 4:
                    await session.send("请从板中正确拿取对应颜色的宝石！" if this == 4 else "请选择拿取宝石的位置。")
                elif ret == 5:
                    await session.send("请正确拿取已有的皇冠卡！" if this == 5 else "请选择拿取的皇冠卡。")
            except StopIteration as e:
                rete: Literal[-1, -3, -2, 1] = e.value
                if rete == -1:
                    await session.send("购买失败！")
                elif rete == -2:
                    await session.send("货币不足！")
                elif rete == -3:
                    await session.send("不可先购买模仿卡！")
                else:
                    player.state = 1
                player.buyCardState = None
        begin_state = player.state
        if player.state == 0:
            if command.startswith("使用特权") or command.startswith("使用卷轴"):
                lm = re.findall(r"([A-Z][0-9])", command[4:].strip())
                if len(lm) == 0:
                    await session.send("请正确输入宝石坐标！")
                    return
                l = [GemCorr(x) for x in lm]
                if (-1, -1) in l:
                    await session.send("请输入正确的宝石坐标！")
                    return
                ret = player.UseScroll(l)
                if ret == -1:
                    await session.send("卷轴数量不够！")
                elif ret == -2:
                    await session.send("无法拿取空格子或金子！")
                else:
                    await session.send([board.SaveImg(player.id, data['vertical'][player.id])])
                    await session.send("请继续您的动作。")
            elif command.startswith("填充"):
                ret = player.RefillToken()
                if ret == -1:
                    await session.send("没有剩余宝石，无法重填！")
                else:
                    await session.send([board.SaveImg(player.id, data['vertical'][player.id])])
                    await session.send("请继续您的动作。")
            elif command.startswith("拿"):
                lm = re.findall(r"([A-Z][0-9])", command[4:].strip())
                if len(lm) == 0 or len(lm) > 3:
                    await session.send("请正确输入至多三个宝石坐标！")
                    return
                l = [GemCorr(x) for x in lm]
                if (-1, -1) in l:
                    await session.send("请输入正确的宝石坐标！")
                    return
                ret = player.GetLineToken(*l)
                if ret == -1:
                    await session.send("请拿在同一条直线上的三个宝石！")
                elif ret == 2:
                    await session.send("对手已拿取一个卷轴。")
                    player.state = 1
                else:
                    player.state = 1
            elif command.startswith("买") or command.startswith("购买"):
                match = re.search(r"[a-ce-hj-np-r]", command[1:].strip())
                if not match:
                    await session.send("请正确输入卡牌编号！")
                    return
                pos = [(i, s.index(c)) for i, s in enumerate(("jklmn", "efgh", "abc", "pqr")) if (c := match.group(0)) in s][0]
                buy = player.BuyCard(*pos)
                player.buyCardState = buy
                await proceed_buy(lambda: next(buy), this=0)
            elif command.startswith("预购"):
                match = re.search(r"[a-o]", command[2:].strip())
                if not match:
                    await session.send("请正确输入卡牌编号！")
                    return
                match2 = re.search(r"[A-E][1-5]", command[2:].strip())
                if not match2:
                    await session.send("请正确输入宝石编号！")
                    return
                pos = [(i, -1 if c in "dio" else s.index(c)) for i, s in enumerate(("jklmno", "efghi", "abcd")) if (c := match.group(0)) in s][0]
                corr = GemCorr(match2.group(0))
                if corr == (-1, -1):
                    await session.send("请正确输入宝石编号！")
                    return
                ret = player.ReserveCard(*corr, *pos)
                if ret == -1:
                    await session.send("请选择正确的卡牌与金子！")
                elif ret == -2:
                    await session.send("预购栏位不足！")
                else:
                    player.state = 1
        elif player.state == 1:
            lc: list[str] = re.findall(r"白|黑|红|绿|蓝|金|粉|珍珠|钻石", command)
            if player.total_tokens - len(lc) <= 10:
                await session.send("请弃至恰好10个宝石，使用宝石颜色指定，如红绿蓝金粉。")
                return
            colors = [Color.choose(i) for i in lc]
            ret = player.DiscardToken(colors)
            if ret == -1:
                await session.send("你弃了你没有的宝石！")
            else:
                player.state = 0
                next_turn = True
        elif player.state == 2: # 2: 选择模仿颜色
            match = re.search(r"白|黑|红|绿|蓝|钻石", command)
            if not match:
                await session.send("请正确选择模仿颜色，使用宝石颜色指定，如红。")
                return
            color = Color.choose(match.group(0))
            await proceed_buy(lambda: player.buyCardState.send(color), this=2)
        elif player.state == 3: # 3: 选择偷取颜色
            match = re.search(r"白|黑|红|绿|蓝|粉|珍珠|钻石", command)
            if not match:
                await session.send("请正确选择偷取宝石颜色，如红绿蓝金粉。")
                return
            color = Color.choose(match.group(0))
            await proceed_buy(lambda: player.buyCardState.send(color), this=3)
        elif player.state == 4: # 4: 选择获取token
            match = re.search(r"[A-E][1-5]", command)
            if not match:
                await session.send("请正确选择拿取宝石位置，如A1 C5。")
                return
            corr = GemCorr(match.group(0))
            await proceed_buy(lambda: player.buyCardState.send(corr), this=4)
        elif player.state == 5: # 5: 选择皇冠卡
            match = re.search(r"[s-v]", command)
            if not match:
                await session.send("请正确选择皇冠卡，如卡t。")
                return
            k = "stuv".index(match.group(0))
            await proceed_buy(lambda: player.buyCardState.send(k), this=5)
        if player.state != begin_state:
            if player.state > 1:
                await session.send([board.SaveImg(player.id, data['vertical'][player.id])])
            elif player.state == 1:
                if player.total_tokens > 10:
                    await session.send("你需要将宝石弃至10枚，请选择要弃的宝石。")
                    await session.send([board.SaveImg(player.id, data['vertical'][player.id])])
                else:
                    player.state = 0
                    next_turn = True
        if next_turn:
            if player.CheckWin():
                await session.send("恭喜你，你赢了！")
                await session.send([board.SaveImg(player.id, data['vertical'][player.id])])
                await delete_func()
                return
            await session.send("你的回合已结束。")
            await session.send([board.SaveImg(player.id, data['vertical'][player.id])])
            board.NextTurn()
            player = board.current_player
            await session.send(f"轮到玩家{data['names'][player.id]}的回合，请选择操作：使用特权、填充宝石、拿宝石、买卡、预购卡。回复“帮助”查询如何使用指令。")
            await session.send([board.SaveImg(player.id, data['vertical'][player.id])])

