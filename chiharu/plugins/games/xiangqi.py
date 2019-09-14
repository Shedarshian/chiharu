import abc
import itertools
import functools
from typing import Dict, Any, Callable, Awaitable
import chiharu.plugins.config as config
from chiharu.plugins.game import GameSameGroup, ChessError, ChessWin
from nonebot import on_command, CommandSession, get_bot, permission, NLPSession, IntentCommand

name_dict = {}

def metastr(output):
    def _(class_name, class_parents, class_attr):
        def __str__(self):
            return output
        _isRed = class_name.startswith('Hong')
        def isRed(self):
            return _isRed
        class_attr['__str__'] = __str__
        class_attr['isRed'] = isRed
        name_dict[class_name] = type(class_name, class_parents, class_attr)
        return name_dict[class_name]
    return _

class Chess(abc.ABC):
    """A Abstract Base Class for Cell"""
    row = {"一": 8, "二": 7, "三": 6, "四": 5, "五": 4, "六": 3, "七": 2, "八": 1, "九": 0,
        "1": 0, "2": 1, "3": 2, "4": 3, "5": 4, "6": 5, "7": 6, "8": 7, "9": 8}
    step = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
        "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9}
    def __init__(self, pos, board):
        self.pos = pos
        self.board = board
    @abc.abstractmethod
    def __str__(self):
        pass
    def TestMove(self, command):
        return False
    def Move(self, pos):
        to_delete = ()
        if pos in self.board.board:
            to_delete += ((type(self.board.board[pos]), pos),)
            self.board.pop(pos)
        to_delete += ((type(self), self.pos),)
        to_add = (type(self), pos)
        self.board.Moves.append((to_add, to_delete))
        self.board.board.pop(self.pos)
        self.board.board[pos] = self
        self.pos = pos

class HongChe(Chess, metaclass=metastr("车")):
    def TestMove(self, command):
        if command[0] == 1: #进
            try:
                step = Chess.step[command[1]]
            except KeyError:
                raise ChessError('不明指令')
            if self.pos[0] - step < 0:
                return (False, )
            for i in range(step - 1):
                if not self.board.isBlank((self.pos[0] - i - 1, self.pos[1])):
                    return (False, )
            pos = (self.pos[0] - step, self.pos[1])
            if not self.board.isBlank(pos):
                if self.board[pos].isRed():
                    return (False, )
            return (True, pos)
        elif command[0] == -1: #退
            try:
                step = Chess.step[command[1]]
            except KeyError:
                raise ChessError('不明指令')
            if self.pos[0] + step > 9:
                return (False, )
            for i in range(step - 1):
                if not self.board.isBlank((self.pos[0] + i + 1, self.pos[1])):
                    return (False, )
            pos = (self.pos[0] + step, self.pos[1])
            if not self.board.isBlank(pos):
                if self.board[pos].isRed():
                    return (False, )
            return (True, pos)
        elif command[0] == 0: #平
            try:
                lie = Chess.row[command[1]]
            except KeyError:
                raise ChessError('不明指令')
            if lie == self.pos[1]:
                return (False, )
            small, big = sorted((lie, self.pos[1]))
            for i in range(small + 1, big):
                if not self.board.isBlank((self.pos[0], i)):
                    return (False, )
            pos = (self.pos[0], lie)
            if not self.board.isBlank(pos) and self.board[(self.pos[0], lie)].isRed():
                return (False, )
            return (True, pos)
class HongMa(Chess, metaclass=metastr("马")):
    def TestMove(self, command):
        try:
            lie = Chess.row[command[1]]
        except KeyError:
            raise ChessError('不明指令')
        if command[0] == 1: #进
            l = {self.pos[1] - 1: ((self.pos[0] - 2, self.pos[1] - 1), (self.pos[0] - 1, self.pos[1])),
                self.pos[1] + 1: ((self.pos[0] - 2, self.pos[1] + 1), (self.pos[0] - 1, self.pos[1])),
                self.pos[1] - 2: ((self.pos[0] - 1, self.pos[1] - 2), (self.pos[0], self.pos[1] - 1)),
                self.pos[1] + 2: ((self.pos[0] - 1, self.pos[1] + 2), (self.pos[0], self.pos[1] + 1))}
        elif command[0] == -1: #退
            l = {self.pos[1] - 1: ((self.pos[0] + 2, self.pos[1] - 1), (self.pos[0] + 1, self.pos[1])),
                self.pos[1] + 1: ((self.pos[0] + 2, self.pos[1] + 1), (self.pos[0] + 1, self.pos[1])),
                self.pos[1] - 2: ((self.pos[0] + 1, self.pos[1] - 2), (self.pos[0], self.pos[1] - 1)),
                self.pos[1] + 2: ((self.pos[0] + 1, self.pos[1] + 2), (self.pos[0], self.pos[1] + 1))}
        elif command[0] == 0: #平
            raise ChessError('不明指令')
        try:
            pos, tui = l[lie]
        except KeyError:
            return (False, )
        if pos[0] < 0 or pos[0] > 9 or pos[1] < 0 or pos[1] > 8:
            return (False, )
        if not self.board.isBlank(tui):
            return (False, )
        if not self.board.isBlank(pos) and self.board[pos].isRed():
            return (False, )
        return (True, pos)
class HongXiang(Chess, metaclass=metastr("相")):
    def TestMove(self, command):
        try:
            lie = Chess.row[command[1]]
        except KeyError:
            raise ChessError('不明指令')
        if command[0] == 1: #进
            l = {self.pos[1] - 2: ((self.pos[0] - 2, self.pos[1] - 2), (self.pos[0] - 1, self.pos[1] - 1)),
                self.pos[1] + 2: ((self.pos[0] - 2, self.pos[1] + 2), (self.pos[0] - 1, self.pos[1] + 1))}
        elif command[0] == -1: #退
            l = {self.pos[1] - 2: ((self.pos[0] + 2, self.pos[1] - 2), (self.pos[0] + 1, self.pos[1] - 1)),
                self.pos[1] + 2: ((self.pos[0] + 2, self.pos[1] + 2), (self.pos[0] + 1, self.pos[1] + 1))}
        elif command[0] == 0: #平
            raise ChessError('不明指令')
        try:
            pos, tui = l[lie]
        except KeyError:
            return (False, )
        if pos[0] < 5 or pos[0] > 9 or pos[1] < 0 or pos[1] > 8:
            return (False, )
        if not self.board.isBlank(tui):
            return (False, )
        if not self.board.isBlank(pos) and self.board[pos].isRed():
            return (False, )
        return (True, pos)
class HongShi(Chess, metaclass=metastr("仕")):
    def TestMove(self, command):
        try:
            lie = Chess.row[command[1]]
        except KeyError:
            raise ChessError('不明指令')
        if command[0] == 1: #进
            l = {self.pos[1] - 1: (self.pos[0] - 1, self.pos[1] - 1),
                self.pos[1] + 1: (self.pos[0] - 1, self.pos[1] + 1)}
        elif command[0] == -1: #退
            l = {self.pos[1] - 1: (self.pos[0] + 1, self.pos[1] - 1),
                self.pos[1] + 1: (self.pos[0] + 1, self.pos[1] + 1)}
        elif command[0] == 0: #平
            raise ChessError('不明指令')
        try:
            pos = l[lie]
        except KeyError:
            return (False, )
        if pos[0] < 7 or pos[0] > 9 or pos[1] < 3 or pos[1] > 5:
            return (False, )
        if not self.board.isBlank(pos) and self.board[pos].isRed():
            return (False, )
        return (True, pos)
class HongShuai(Chess, metaclass=metastr("帅")):
    def TestMove(self, command):
        if command[0] == 0: #平
            try:
                lie = Chess.row[command[1]]
            except KeyError:
                raise ChessError('不明指令')
            if lie != self.pos[1] + 1 and lie != self.pos[1] - 1:
                raise ChessError('不明指令')
            pos = (self.pos[0], lie)
            if lie < 3 or lie > 5:
                return (False, )
        else: #进退
            try:
                step = Chess.step[command[1]]
            except KeyError:
                raise ChessError('不明指令')
            if step != 1:
                raise ChessError('不明指令')
            pos = (self.pos[0] - step * command[0], self.pos[1])
            if pos[0] < 7 or pos[0] > 9:
                return (False, )
        if not self.board.isBlank(pos) and self.board[pos].isRed():
            return (False, )
        return (True, pos)
class HongPao(Chess, metaclass=metastr("炮")):
    def TestMove(self, command):
        if command[0] == 1: #进
            try:
                step = Chess.step[command[1]]
            except KeyError:
                raise ChessError('不明指令')
            if self.pos[0] - step < 0:
                return (False, )
            num = 0
            for i in range(step - 1):
                if not self.board.isBlank((self.pos[0] - i - 1, self.pos[1])):
                    num += 1
            pos = (self.pos[0] - step, self.pos[1])
            if not self.board.isBlank(pos):
                if self.board[pos].isRed():
                    return (False, )
                else:
                    if num != 1:
                        return (False, )
            elif num != 0:
                return (False, )
            return (True, pos)
        elif command[0] == -1: #退
            try:
                step = Chess.step[command[1]]
            except KeyError:
                raise ChessError('不明指令')
            if self.pos[0] + step > 9:
                return (False, )
            num = 0
            for i in range(step - 1):
                if not self.board.isBlank((self.pos[0] + i + 1, self.pos[1])):
                    num += 1
            pos = (self.pos[0] + step, self.pos[1])
            if not self.board.isBlank(pos):
                if self.board[pos].isRed():
                    return (False, )
                else:
                    if num != 1:
                        return (False, )
            elif num != 0:
                return (False, )
            return (True, pos)
        elif command[0] == 0: #平
            try:
                lie = Chess.row[command[1]]
            except KeyError:
                raise ChessError('不明指令')
            if lie == self.pos[1]:
                return (False, )
            small, big = sorted((lie, self.pos[1]))
            num = 0
            for i in range(small + 1, big):
                if not self.board.isBlank((self.pos[0], i)):
                    num += 1
            pos = (self.pos[0], lie)
            if not self.board.isBlank(pos):
                if self.board[pos].isRed():
                    return (False, )
                else:
                    if num != 1:
                        return (False, )
            elif num != 0:
                return (False, )
            return (True, pos)
class HongBing(Chess, metaclass=metastr("兵")):
    def TestMove(self, command):
        if command[0] == 0: #平
            try:
                lie = Chess.row[command[1]]
            except KeyError:
                raise ChessError('不明指令')
            if lie != self.pos[1] + 1 and lie != self.pos[1] - 1:
                return (False,)
            if self.pos[0] >= 5:
                return (False,)
            pos = (self.pos[0], lie)
        elif command[0] == 1: #进
            try:
                step = Chess.step[command[1]]
            except KeyError:
                raise ChessError('不明指令')
            if step != 1:
                return (False,)
            pos = (self.pos[0] - step, self.pos[1])
            if pos[0] < 0:
                return (False, )
        elif command[0] == -1: #退
            raise ChessError('不明指令')
        if not self.board.isBlank(pos) and self.board[pos].isRed():
            return (False, )
        return (True, pos)
class HeiChe(Chess, metaclass=metastr("車")):
    def TestMove(self, command):
        if command[0] == -1: #退
            try:
                step = Chess.step[command[1]]
            except KeyError:
                raise ChessError('不明指令')
            if self.pos[0] - step < 0:
                return (False, )
            for i in range(step - 1):
                if not self.board.isBlank((self.pos[0] - i - 1, self.pos[1])):
                    return (False, )
            pos = (self.pos[0] - step, self.pos[1])
            if not self.board.isBlank(pos):
                if not self.board[pos].isRed():
                    return (False, )
            return (True, pos)
        elif command[0] == 1: #进
            try:
                step = Chess.step[command[1]]
            except KeyError:
                raise ChessError('不明指令')
            if self.pos[0] + step > 9:
                return (False, )
            for i in range(step - 1):
                if not self.board.isBlank((self.pos[0] + i + 1, self.pos[1])):
                    return (False, )
            pos = (self.pos[0] + step, self.pos[1])
            if not self.board.isBlank(pos):
                if not self.board[pos].isRed():
                    return (False, )
            return (True, pos)
        elif command[0] == 0: #平
            try:
                lie = Chess.row[command[1]]
            except KeyError:
                raise ChessError('不明指令')
            if lie == self.pos[1]:
                return (False, )
            small, big = sorted((lie, self.pos[1]))
            for i in range(small + 1, big):
                if not self.board.isBlank((self.pos[0], i)):
                    return (False, )
            pos = (self.pos[0], lie)
            if not self.board.isBlank(pos) and not self.board[(self.pos[0], lie)].isRed():
                return (False, )
            return (True, pos)
class HeiMa(Chess, metaclass=metastr("馬")):
    def TestMove(self, command):
        try:
            lie = Chess.row[command[1]]
        except KeyError:
            raise ChessError('不明指令')
        if command[0] == -1: #退
            l = {self.pos[1] - 1: ((self.pos[0] - 2, self.pos[1] - 1), (self.pos[0] - 1, self.pos[1])),
                self.pos[1] + 1: ((self.pos[0] - 2, self.pos[1] + 1), (self.pos[0] - 1, self.pos[1])),
                self.pos[1] - 2: ((self.pos[0] - 1, self.pos[1] - 2), (self.pos[0], self.pos[1] - 1)),
                self.pos[1] + 2: ((self.pos[0] - 1, self.pos[1] + 2), (self.pos[0], self.pos[1] + 1))}
        elif command[0] == 1: #进
            l = {self.pos[1] - 1: ((self.pos[0] + 2, self.pos[1] - 1), (self.pos[0] + 1, self.pos[1])),
                self.pos[1] + 1: ((self.pos[0] + 2, self.pos[1] + 1), (self.pos[0] + 1, self.pos[1])),
                self.pos[1] - 2: ((self.pos[0] + 1, self.pos[1] - 2), (self.pos[0], self.pos[1] - 1)),
                self.pos[1] + 2: ((self.pos[0] + 1, self.pos[1] + 2), (self.pos[0], self.pos[1] + 1))}
        elif command[0] == 0: #平
            raise ChessError('不明指令')
        try:
            pos, tui = l[lie]
        except KeyError:
            return (False, )
        if pos[0] < 0 or pos[0] > 9 or pos[1] < 0 or pos[1] > 8:
            return (False, )
        if not self.board.isBlank(tui):
            return (False, )
        if not self.board.isBlank(pos) and not self.board[pos].isRed():
            return (False, )
        return (True, pos)
class HeiXiang(Chess, metaclass=metastr("象")):
    def TestMove(self, command):
        try:
            lie = Chess.row[command[1]]
        except KeyError:
            raise ChessError('不明指令')
        if command[0] == -1: #退
            l = {self.pos[1] - 2: ((self.pos[0] - 2, self.pos[1] - 2), (self.pos[0] - 1, self.pos[1] - 1)),
                self.pos[1] + 2: ((self.pos[0] - 2, self.pos[1] + 2), (self.pos[0] - 1, self.pos[1] + 1))}
        elif command[0] == 1: #进
            l = {self.pos[1] - 2: ((self.pos[0] + 2, self.pos[1] - 2), (self.pos[0] + 1, self.pos[1] - 1)),
                self.pos[1] + 2: ((self.pos[0] + 2, self.pos[1] + 2), (self.pos[0] + 1, self.pos[1] + 1))}
        elif command[0] == 0: #平
            raise ChessError('不明指令')
        try:
            pos, tui = l[lie]
        except KeyError:
            return (False, )
        if pos[0] < 0 or pos[0] > 4 or pos[1] < 0 or pos[1] > 8:
            return (False, )
        if not self.board.isBlank(tui):
            return (False, )
        if not self.board.isBlank(pos) and not self.board[pos].isRed():
            return (False, )
        return (True, pos)
class HeiShi(Chess, metaclass=metastr("士")):
    def TestMove(self, command):
        try:
            lie = Chess.row[command[1]]
        except KeyError:
            raise ChessError('不明指令')
        if command[0] == -1: #退
            l = {self.pos[1] - 1: (self.pos[0] - 1, self.pos[1] - 1),
                self.pos[1] + 1: (self.pos[0] - 1, self.pos[1] + 1)}
        elif command[0] == 1: #进
            l = {self.pos[1] - 1: (self.pos[0] + 1, self.pos[1] - 1),
                self.pos[1] + 1: (self.pos[0] + 1, self.pos[1] + 1)}
        elif command[0] == 0: #平
            raise ChessError('不明指令')
        try:
            pos = l[lie]
        except KeyError:
            return (False, )
        if pos[0] < 0 or pos[0] > 2 or pos[1] < 3 or pos[1] > 5:
            return (False, )
        if not self.board.isBlank(pos) and not self.board[pos].isRed():
            return (False, )
        return (True, pos)
class HeiShuai(Chess, metaclass=metastr("将")):
    def TestMove(self, command):
        if command[0] == 0: #平
            try:
                lie = Chess.row[command[1]]
            except KeyError:
                raise ChessError('不明指令')
            if lie != self.pos[1] + 1 and lie != self.pos[1] - 1:
                raise ChessError('不明指令')
            pos = (self.pos[0], lie)
            if lie < 3 or lie > 5:
                return (False, )
        else: #进退
            try:
                step = Chess.step[command[1]]
            except KeyError:
                raise ChessError('不明指令')
            if step != 1:
                raise ChessError('不明指令')
            pos = (self.pos[0] + step * command[0], self.pos[1])
            if pos[0] < 0 or pos[0] > 2:
                return (False, )
        if not self.board.isBlank(pos) and self.board[pos].isRed():
            return (False, )
        return (True, pos)
class HeiPao(Chess, metaclass=metastr("砲")):
    def TestMove(self, command):
        if command[0] == -1: #退
            try:
                step = Chess.step[command[1]]
            except KeyError:
                raise ChessError('不明指令')
            if self.pos[0] - step < 0:
                return (False, )
            num = 0
            for i in range(step - 1):
                if not self.board.isBlank((self.pos[0] - i - 1, self.pos[1])):
                    num += 1
            pos = (self.pos[0] - step, self.pos[1])
            if not self.board.isBlank(pos):
                if not self.board[pos].isRed():
                    return (False, )
                else:
                    if num != 1:
                        return (False, )
            elif num != 0:
                return (False, )
            return (True, pos)
        elif command[0] == 1: #进
            try:
                step = Chess.step[command[1]]
            except KeyError:
                raise ChessError('不明指令')
            if self.pos[0] + step > 9:
                return (False, )
            num = 0
            for i in range(step - 1):
                if not self.board.isBlank((self.pos[0] + i + 1, self.pos[1])):
                    num += 1
            pos = (self.pos[0] + step, self.pos[1])
            if not self.board.isBlank(pos):
                if not self.board[pos].isRed():
                    return (False, )
                else:
                    if num != 1:
                        return (False, )
            elif num != 0:
                return (False, )
            return (True, pos)
        elif command[0] == 0: #平
            try:
                lie = Chess.row[command[1]]
            except KeyError:
                raise ChessError('不明指令')
            if lie == self.pos[1]:
                return (False, )
            small, big = sorted((lie, self.pos[1]))
            num = 0
            for i in range(small + 1, big):
                if not self.board.isBlank((self.pos[0], i)):
                    num += 1
            pos = (self.pos[0], lie)
            if not self.board.isBlank(pos):
                if not self.board[pos].isRed():
                    return (False, )
                else:
                    if num != 1:
                        return (False, )
            elif num != 0:
                return (False, )
            return (True, pos)
class HeiBing(Chess, metaclass=metastr("卒")):
    def TestMove(self, command):
        if command[0] == 0: #平
            try:
                lie = Chess.row[command[1]]
            except KeyError:
                raise ChessError('不明指令')
            if lie != self.pos[1] + 1 and lie != self.pos[1] - 1:
                return (False,)
            if self.pos[0] <= 4:
                return (False,)
            pos = (self.pos[0], lie)
        elif command[0] == 1: #进
            try:
                step = Chess.step[command[1]]
            except KeyError:
                raise ChessError('不明指令')
            if step != 1:
                return (False,)
            pos = (self.pos[0] + step, self.pos[1])
            if pos[0] > 9:
                return (False, )
        elif command[0] == -1: #退
            raise ChessError('不明指令')
        if not self.board.isBlank(pos) and not self.board[pos].isRed():
            return (False, )
        return (True, pos)
name_dict['HeiJiang'] = HeiShuai
name_dict['HongJiang'] = HongShuai
name_dict['HeiZu'] = HeiBing
name_dict['HongZu'] = HongBing

class ChessBoard:
    insert_dict = {HeiChe: ("车", "車"), HeiMa: ("马", "馬"), HeiXiang: ("象",), HeiShi: ("仕", "士"), HeiShuai: ("将"), HeiPao: ("砲", "炮"), HeiBing: ("卒",), HongBing: ("兵",), HongPao: ("砲", "炮"), HongChe: ("车", "車"), HongMa: ("马", "馬"), HongXiang: ("相",), HongShi: ("仕", "士"), HongShuai: ("帅",)}
    def __init__(self):
        self.board = {}
        self.find = {}
        self.insert((0, 0), HeiChe)
        self.insert((0, 1), HeiMa)
        self.insert((0, 2), HeiXiang)
        self.insert((0, 3), HeiShi)
        self.insert((0, 4), HeiShuai)
        self.insert((0, 5), HeiShi)
        self.insert((0, 6), HeiXiang)
        self.insert((0, 7), HeiMa)
        self.insert((0, 8), HeiChe)
        self.insert((2, 1), HeiPao)
        self.insert((2, 7), HeiPao)
        self.insert((3, 0), HeiBing)
        self.insert((3, 2), HeiBing)
        self.insert((3, 4), HeiBing)
        self.insert((3, 6), HeiBing)
        self.insert((3, 8), HeiBing)
        self.insert((6, 0), HongBing)
        self.insert((6, 2), HongBing)
        self.insert((6, 4), HongBing)
        self.insert((6, 6), HongBing)
        self.insert((6, 8), HongBing)
        self.insert((7, 1), HongPao)
        self.insert((7, 7), HongPao)
        self.insert((9, 0), HongChe)
        self.insert((9, 1), HongMa)
        self.insert((9, 2), HongXiang)
        self.insert((9, 3), HongShi)
        self.insert((9, 4), HongShuai)
        self.insert((9, 5), HongShi)
        self.insert((9, 6), HongXiang)
        self.insert((9, 7), HongMa)
        self.insert((9, 8), HongChe)
        self.Moves = []
    def insert(self, pos, Name):
        if pos in self.board:
            raise ChessError('已有棋子')
        chess = Name(pos, self)
        self.board[pos] = chess
        key = ChessBoard.insert_dict[Name]
        for s in key:
            if s not in self.find:
                self.find[s] = []
            self.find[s].append(chess)
    def pop(self, pos):
        chess_to_remove = self.board[pos]
        if str(chess_to_remove) == '帅':
            raise ChessWin("黑方胜出")
        if str(chess_to_remove) == '将':
            raise ChessWin("红方胜出")
        for key, val in self.find.items():
            if chess_to_remove in val:
                val.remove(chess_to_remove)
        self.find = dict(filter(lambda x: len(x[1]) != 0, self.find.items()))
        self.board.pop(pos)
    def isBlank(self, pos):
        return pos not in self.board
    def __str__(self):
        def _():
            for i in range(10):
                def _():
                    for j in range(9):
                        if (i, j) not in self.board:
                            yield '　'
                        else:
                            yield str(self.board[(i, j)])
                yield '┣' + ''.join(list(_())) + '┫'
        return '┏１２３４５６７８９┓\n' + '\n'.join(list(_())) + '\n┗九八七六五四三二一┛'
    def __getitem__(self, key):
        return self.board[key]
    def __delitem__(self, key):
        self.board.pop(key)
    def __setitem__(self, key, val):
        self.board[key] = val
    def checkDuiJiang(self):
        jiang = self.find['将'][0].pos[1]
        shuai = self.find['帅'][0].pos[1]
        if jiang != shuai:
            return
        l = []
        for pos, chess in self.board.items():
            if pos[1] == jiang and chess is not self.find['将'][0] and chess is not self.find['帅'][0]:
                l.append(chess)
        if len(l) == 1:
            return l[0]
    def process(self, command, isRed):
        """command: 4 char"""
        if command[0] in ['前', '中', '后']:
            if len(command) != 4 and len(command) != 5:
                raise ChessError("需要四/五个汉字作为指令")
            try:
                chess_list = self.find[command[1]]
            except KeyError:
                raise ChessError("已无该棋子")
            chess_list = list(filter(lambda x: x.isRed() == isRed, chess_list))
            if len(command) == 5:
                #选取指定列数
                try:
                    lie = Chess.row[command[2]]
                except KeyError:
                    raise ChessError("不明指令")
                chess_list = list(filter(lambda x: x.pos[1] == lie, chess_list))
            chess_lie = {}
            for chess in chess_list:
                if chess.pos[1] not in chess_lie:
                    chess_lie[chess.pos[1]] = []
                chess_lie[chess.pos[1]].append(chess)
            chess_list = []
            for lie, l in chess_lie.items():
                l.sort(key=lambda x: x.pos[0], reverse=not isRed)
                if len(l) == 1:
                    continue
                elif len(l) == 2:
                    try:
                        chess_list.append({'前': l[0], '后': l[1]}[command[0]])
                    except KeyError:
                        continue
                elif len(l) == 3:
                    chess_list.append({'前': l[0], '中': l[1], '后': l[2]}[command[0]])
                elif len(l) == 4:
                    for x in {'前': (l[0],), '中': (l[1], l[2]), '后': (l[3],)}[command[0]]:
                        chess_list.append(x)
                elif len(l) == 5:
                    for x in {'前': (l[0],), '中': (l[1], l[2], l[3]), '后': (l[3],)}[command[0]]:
                        chess_list.append(x)
        else:
            if len(command) != 4:
                raise ChessError("需要四个汉字作为指令")
            try:
                chess_list = self.find[command[0]]
            except KeyError:
                raise ChessError("已无该棋子")
            chess_list = list(filter(lambda x: x.isRed() == isRed, chess_list))
            #选取指定列数
            try:
                lie = Chess.row[command[1]]
            except KeyError:
                raise ChessError("不明指令")
            chess_list = list(filter(lambda x: x.pos[1] == lie, chess_list))
        try:
            move_command = ({'进': 1, '平': 0, '退': -1}[command[-2]], command[-1])
        except KeyError:
            raise ChessError("不明指令")
        if len(chess_list) != 1:
            #TestMove returns (True, pos_mubiao) or (False, )
            chess_list2 = list(filter(lambda x: x[1], list(map(lambda x: (x,) + \
                x.TestMove(move_command), chess_list))))
            if len(chess_list2) > 1:
                raise ChessError("棋子不唯一")
            if len(chess_list2) == 0:
                raise ChessError("未找到棋子")
            duijiang = self.checkDuiJiang()
            if duijiang is not None and chess_list2[0][0] is duijiang and duijiang.pos[1] != chess_list2[0][2][1]:
                raise ChessError("对将")
            chess_list2[0][0].Move(chess_list2[0][2])
        else:
            #TestMove returns (True, pos_mubiao) or (False, )
            p = chess_list[0].TestMove(move_command)
            if not p[0]:
                raise ChessError("无法移动")
            duijiang = self.checkDuiJiang()
            if duijiang is not None and chess_list[0] is duijiang and duijiang.pos[1] != p[1][1]:
                raise ChessError("对将")
            chess_list[0].Move(p[1])
    def redo(self):
        if len(self.Moves) == 0:
            raise ChessError('已回到最初')
        (to_add, to_delete) = self.Moves.pop()
        self.pop(to_add[1])
        for i in to_delete:
            self.insert(i[1], i[0])

xiangqi = GameSameGroup('xiangqi')

@xiangqi.begin_uncomplete(('play', 'xiangqi', 'begin'), (2, 2))
async def chess_begin_uncomplete(session: CommandSession, data: Dict[str, Any]):
    # data: {'players': [qq], 'anything': anything}
    await session.send('已为您安排红方，等候黑方')

@xiangqi.begin_complete(('play', 'xiangqi', 'confirm'))
async def chess_begin_complete(session: CommandSession, data: Dict[str, Any]):
    # data: {'players': [qq], 'game': GameSameGroup instance, 'anything': anything}
    await session.send('已为您安排黑方')
    data['red'] = data['players'][0]
    data['board'] = ChessBoard()
    data['nowRed'] = True
    await session.send(str(data['board']), auto_escape=True)

@xiangqi.end(('play', 'xiangqi', 'end'))
async def chess_end(session: CommandSession, data: Dict[str, Any]):
    await session.send('已删除')

all_name = set('车車马馬象相士仕将帅炮砲兵卒')
@xiangqi.process(only_short_message=True)
async def chess_process(session: NLPSession, data: Dict[str, Any], delete_func: Awaitable):
    command = session.msg_text
    qq = int(session.ctx['user_id'])
    board = data['board']
    if command in {"认输", "认负", "我认输", "我认负"}:
        isRed = data['red'] == qq
        await session.send(('红' if not isRed else '黑') + '方胜出')
        await delete_func()
    if len(command) != 4 and len(command) != 5:
        return
    if command[0] in '前中后' and command[1] in all_name or command[0] in all_name:
        if command[-2] in '进平退':
            if (data['red'] == qq) != data['nowRed']:
                await session.send('现在应该' + ('红' if data['nowRed'] else '黑') + '方走')
                return
            def _not_red():
                data['nowRed'] = not data['nowRed']
            return IntentCommand(100.0, ('play', 'xiangqi', 'process'),
                args={'args': command, 'isRed': data['nowRed'], 'board': data['board'],
                'ifSuccess': _not_red, 'ifWin': delete_func})

@on_command(('play', 'xiangqi', 'process'), only_to_me=False)
@config.ErrorHandle
async def chess_test(session: CommandSession):
    board = session.get('board')
    try:
        board.process(session.get('args'), session.get('isRed'))
        session.get('ifSuccess')()
        await session.send(str(board), auto_escape=True)
    except ChessWin as e:
        await session.send(e.args[0], auto_escape=True)
        await session.get('ifWin')()
    except ChessError as e:
        await session.send(e.args[0], auto_escape=True)

@on_command(('xiangqi', 'check'), only_to_me=False)
@config.ErrorHandle
async def chess_check(session: CommandSession):
    await session.send(' '.join(map(str, filter(lambda x: xiangqi.center[x]['game'] is xiangqi, xiangqi.center.keys()))), auto_escape=True)