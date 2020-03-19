import random
import itertools
from typing import Dict, Any, Callable, Awaitable
import chiharu.plugins.config as config
from chiharu.plugins.game import GameSameGroup, ChessError, ChessWin
from nonebot import on_command, CommandSession, get_bot, permission, NLPSession, IntentCommand

class ChessCantMove(ChessError):
    pass

class BwBoard:
    def __init__(self):
        height_half = 4
        self.height = height_half * 2
        self.board = list(map(lambda x: list(map(lambda y: 0, range(height_half * 2))), range(height_half * 2)))
        self.board[height_half - 1][height_half - 1] = 2
        self.board[height_half - 1][height_half] = 1
        self.board[height_half][height_half] = 2
        self.board[height_half][height_half - 1] = 1
    def __str__(self):
        row = 'ＡＢＣＤＥＦＧＨＩＪ'
        f = lambda x, i, j: '●○'[x - 1] if x != 0 else '┌┬┐├┼┤└┴┘'[(1 - int(j == 0) + int(j == self.height - 1)) + \
                3 * (1 - int(i == 0) + int(i == self.height - 1))]
        s = '\n'.join(itertools.starmap(lambda i, a, b: a + ''.join( \
                itertools.starmap(lambda j, y: f(y, i, j), enumerate(b))), \
                zip(itertools.count(0), row, self.board)))
        return '┏１２３４５６７８\n' + s
    def process(self, i, j, isBlack: bool):
        if self.board[i][j] != 0:
            raise ChessError('此处已有棋子')
        todo_all = [(i, j)]
        black_need = 2 - int(isBlack) # 己方
        for (di, dj) in ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)):
            i2, j2 = i + di, j + dj
            todo = []
            while 0 <= i2 <= self.height - 1 and 0 <= j2 <= self.height - 1:
                if self.board[i2][j2] == 0:
                    break
                if self.board[i2][j2] != black_need:
                    todo.append((i2, j2))
                else:
                    todo_all.extend(todo)
                    break
                i2 += di
                j2 += dj
        if len(todo_all) == 1:
            raise ChessError('行棋必须吃掉对方的子')
        for i2, j2 in todo_all:
            self.board[i2][j2] = black_need
        white_need = 3 - black_need # 对方
        safe = [False, False]
        for i, x in enumerate(self.board):
            for j, y in enumerate(x):
                if y == white_need:
                    for (di, dj) in ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)):
                        i2, j2 = i + di, j + dj
                        todo = []
                        while 0 <= i2 <= self.height - 1 and 0 <= j2 <= self.height - 1:
                            if self.board[i2][j2] == 0:
                                if len(todo) >= 1:
                                    safe[1] = True
                                break
                            if self.board[i2][j2] == black_need:
                                todo.append((i2, j2))
                            else:
                                break
                            i2 += di
                            j2 += dj
                elif y == black_need:
                    for (di, dj) in ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)):
                        i2, j2 = i + di, j + dj
                        todo = []
                        while 0 <= i2 <= self.height - 1 and 0 <= j2 <= self.height - 1:
                            if self.board[i2][j2] == 0:
                                if len(todo) >= 1:
                                    safe[0] = True
                                break
                            if self.board[i2][j2] == white_need:
                                todo.append((i2, j2))
                            else:
                                break
                            i2 += di
                            j2 += dj
                if safe == [True, True]:
                    return
        #unsafe!
        if safe == [False, False]:
            num = [0, 0, 0]
            for x in self.board:
                for y in x:
                    num[y] += 1
            if num[1] > num[2]:
                raise ChessWin("黑方胜出")
            elif num[1] < num[2]:
                raise ChessWin("白方胜出")
            else:
                raise ChessWin("平局！")
        if not safe[1]:
            raise ChessCantMove("黑白"[int(isBlack)] + "方无法移动，" + "白黑"[int(isBlack)] + "方继续移动")

bw = GameSameGroup('bw')
config.CommandGroup(('play', 'bw'), hide=True)

@bw.begin_uncomplete(('play', 'bw', 'begin'), (2, 2))
async def chess_begin_uncomplete(session: CommandSession, data: Dict[str, Any]):
    # data: {'players': [qq], 'anything': anything}
    await session.send('等候玩家2')

@bw.begin_complete(('play', 'bw', 'confirm'))
async def chess_begin_complete(session: CommandSession, data: Dict[str, Any]):
    # data: {'players': [qq], 'game': GameSameGroup instance, 'anything': anything}
    black = random.randint(0, 1)
    await session.send([config.cq.at(data['players'][black]), config.cq.text('执黑，请先走')])
    data['black'] = data['players'][black]
    data['board'] = BwBoard()
    data['nowBlack'] = True
    await session.send(str(data['board']), auto_escape=True)

@bw.end(('play', 'bw', 'end'))
async def chess_end(session: CommandSession, data: Dict[str, Any]):
    await session.send('已删除')

str_all = 'ABCDEFGHabcdefgh12345678'
@bw.process(only_short_message=True)
async def chess_process(session: NLPSession, data: Dict[str, Any], delete_func: Awaitable):
    command = session.msg_text
    qq = int(session.ctx['user_id'])
    board = data['board']
    if command in {"认输", "认负", "我认输", "我认负"}:
        isRed = data['black'] == qq
        await session.send(('黑' if not isRed else '白') + '方胜出')
        await delete_func()
    if len(command) != 2:
        return
    c1 = str_all.find(command[0])
    c2 = str_all.find(command[1])
    c1, c2 = max(c1, c2), min(c1, c2)
    if c1 >= 16 and c2 < 16:
        if (data['black'] == qq) != data['nowBlack']:
            await session.send('现在应该' + ('黑' if data['nowBlack'] else '白') + '方走')
            return
        def _not_black():
            data['nowBlack'] = not data['nowBlack']
        return IntentCommand(100.0, ('play', 'bw', 'process'),
            args={'args': (c2 % 8, c1 % 8), 'isBlack': data['nowBlack'], 'board': data['board'],
            'ifSuccess': _not_black, 'ifWin': delete_func})

@on_command(('play', 'bw', 'process'), only_to_me=False, hide=True)
@config.ErrorHandle
async def chess_test(session: CommandSession):
    board = session.get('board')
    try:
        board.process(*session.get('args'), session.get('isBlack'))
        session.get('ifSuccess')()
        await session.send(str(board), auto_escape=True)
    except ChessCantMove as e:
        await session.send(str(board), auto_escape=True)
        await session.send(e.args[0], auto_escape=True)
    except ChessWin as e:
        await session.send(str(board), auto_escape=True)
        await session.send(e.args[0], auto_escape=True)
        await session.get('ifWin')()
    except ChessError as e:
        await session.send(e.args[0], auto_escape=True)