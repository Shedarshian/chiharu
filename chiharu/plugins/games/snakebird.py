from typing import Dict, Any, Tuple, List, Set
import itertools
import more_itertools
import functools
from copy import copy, deepcopy
# from nonebot import on_command, CommandSession
# import chiharu.plugins.config as config
# from .. import game

def add(l: Tuple[int, int], r: Tuple[int, int]):
    return (l[0] + r[0], l[1] + r[1])
def in_border(pos: Tuple[int, int], border: Tuple[Tuple[int, int], Tuple[int, int]]):
    return border[0][0] <= pos[0] < border[0][1] and border[1][0] <= pos[1] < border[1][1]
def methdispatch(func):
    dispatcher = functools.singledispatch(func)
    def wrapper(*args, **kw):
        return dispatcher.dispatch(args[1].__class__)(*args, **kw)
    wrapper.register = dispatcher.register
    functools.update_wrapper(wrapper, func)
    return wrapper

class SnakeSpike(Exception):
    pass
class SnakeVoid(Exception):
    pass
class SnakeWin(Exception):
    pass
class SnakeBird:
    dir = [(-1, 0), (0, 1), (1, 0), (0, -1)]
    def __init__(self, id):
        #with open(config.rel(f'games\\snakebird\\{id}.txt')) as f:
        with open(f'C:\\\coolq_data\\games\\snakebird\\{id}.txt') as f:
            self.board = [list(line.strip()) for line in f.readlines()]
        self.border = ((0, len(self.board)), (0, len(self.board[0])))
        # 0: blank 1: wall 2: food 3: spike 8: portal 9: end Aaa: snake IIIJJ: block Z: void T: tail
        _head = dict([(c, more_itertools.only([(i, line.index(c)) for i, line in enumerate(self.board) if c in line])) for c in 'ABC'])
        self.snake = {} # 蛇头在list尾部
        for c, head in _head.items():
            if head is None:
                continue
            self.snake[c] = [head]
            t = head
            while 1:
                for dir in self.dir:
                    s = add(t, dir)
                    if in_border(s, self.border) and self[s] == c.lower() and s not in self.snake[c]:
                        self.snake[c] = [s] + self.snake[c]
                        t = s
                        break
                else:
                    break
        self.cal_food()
        self.win = more_itertools.only([(i, line.index('9')) for i, line in enumerate(self.board) if '9' in line])
        self[self.win] = '0'
        self.portal = functools.reduce(lambda x, y: x + y, [[(i, j) for j in more_itertools.locate(line, lambda x: x == '8')] for i, line in enumerate(self.board)])
        assert(len(self.portal) in {0, 2})
        if len(self.portal) == 2:
            self[self.portal[0]] = self[self.portal[1]] = '0'
        self.block = {} # TODO
        self.stack = []
        self.activate = 'A'
    def cal_food(self):
        self.food = 0
        for line in self.board:
            for c in line:
                if c == '2':
                    self.food += 1
    @methdispatch
    def __getitem__(self, pos):
        raise IndexError('list index out of range')
    @__getitem__.register(tuple)
    def _(self, pos):
        return self.board[pos[0]][pos[1]]
    @__getitem__.register(str)
    def _(self, pos):
        if pos in 'ABC':
            return self.snake[pos]
        elif pos in 'IJKLMN':
            return self.block[pos]
        else:
            raise IndexError('list index out of range')
    @methdispatch
    def __setitem__(self, pos, item):
        raise IndexError('list assignment index out of range')
    @__setitem__.register(tuple)
    def _(self, pos, item):
        self.board[pos[0]][pos[1]] = item
    @__setitem__.register(str)
    def _(self, pos, item):
        if pos in 'ABC':
            self.snake[pos] = item
        elif pos in 'IJKLMN':
            self.block[pos] = item
        else:
            raise IndexError('list assignment index out of range')
    def __str__(self):
        return '\n'.join([''.join([('9' if (i, j) == self.win and b == '0' else b) for j, b in enumerate(x)]) for i, x in enumerate(self.board)])
    def move(self, snake_id, dir):
        # dir: 0up 1right 2down 3left
        if snake_id is None:
            snake_id = self.activate
        else:
            self.activate = snake_id
        assert(snake_id in 'ABC' and dir in range(4))
        if self.snake[snake_id] is None:
            return '未发现此蛇', False
        dir = self.dir[dir]
        snake = self.snake[snake_id]
        pos = add(snake[-1], dir)
        try:
            self.stack.append((deepcopy(self.board), deepcopy(self.snake)))
            if not in_border(pos, self.border):
                return '不能超出边界', False
            elif self[pos] in set('AaBbCcIJKLMN0') - {snake_id, snake_id.lower()}:
                if self[pos] != '0':
                    ret = self.push(dir, self[pos].upper(), snake_id)
                    assert(snake_id not in ret)
                    if ret is None:
                        return '蛇被阻挡，无法前进', False
                self[snake[0]] = '0'
                if self[pos] != '0':
                    self.parallel_move(dir, ret)
                self[snake[-1]] = snake_id.lower()
                self[pos] = snake_id
                snake.pop(0)
                snake.append(pos)
                self.check_win()
                self.fall()
            elif self[pos] == '2':
                self[snake[-1]] = snake_id.lower()
                self[pos] = snake_id
                snake.append(pos)
                self.food -= 1
            # elif pos in self.portal:
            else:
                return '蛇被阻挡，无法前进', False
            return '', True
        except SnakeSpike:
            self.undo()
            return '蛇掉到刺上死亡了！自动撤销一步', True
        except SnakeVoid:
            self.undo()
            return '蛇掉入虚空死亡了！自动撤销一步', True
    def check_win(self):
        if self.food != 0:
            return
        t = self[self.win]
        if t in 'ABC':
            for p in self[t]:
                self[p] = '0'
            self[t] = None
            if functools.reduce(lambda x, y: x and y, [val is None for id, val in self.snake.items()]):
                raise SnakeWin()
    def support(self, dir: Tuple[int, int], snake_id, tail=None):
        snake = self[snake_id]
        assert(snake is not None)
        s = set()
        for body in snake:
            pos = add(body, dir)
            if not in_border(pos, self.border):
                if dir == (0, 1):
                    s.add('Z')
                else:
                    s.add('1')
            elif self[pos] not in {snake_id, '0'}:
                if pos == tail:
                    s.add('T')
                elif self[pos] != snake_id.lower():
                    s.add(self[pos].upper())
        return s
    def push(self, dir: Tuple[int, int], snake_id, pusher_id):
        if add(self[pusher_id][-1], dir) == self[pusher_id][0]:
            return None
        s = {snake_id}
        t = {snake_id}
        while len(t):
            r = set()
            for p in t:
                if p in 'ABCIJKLMN':
                    r |= self.support(dir, p, self[pusher_id][0])
            r -= s
            t = r
            s |= t
        if (set('123Z') | {pusher_id, pusher_id.lower()}) & t:
            return None
        else:
            return s & set('ABCIJKLMN')
    def fall(self):
        while 1:
            s = dict([(id, []) for id, obj in itertools.chain(self.snake.items(), self.block.items()) if obj is not None])
            k = set(s.keys())
            s.update(dict([(id, []) for id in '123Z']))
            for id in k:
                for i in self.support(self.dir[2], id):
                    s[i].append(id)
            has_support = set(itertools.chain(s['1'], s['2'])) | (set(s['3']) & set('IJKLMN'))
            todo = copy(has_support)
            while len(todo):
                t = []
                for i in todo:
                    t += s[i]
                todo = set(t) - has_support
                has_support |= todo
            f = k - has_support
            if len(f) > 0:
                self.parallel_move(self.dir[2], f, True)
                self.check_win()
            else:
                return
    def parallel_move(self, dir: Tuple[int, int], snakes: Set[str], if_death=False):
        for s in snakes:
            snake_s = self[s]
            for body in snake_s:
                self[body] = '0'
            self[s] = [add(x, dir) for x in snake_s]
        for s in snakes:
            if s in 'ABC':
                for body in self[s]:
                    if if_death:
                        if not in_border(body, self.border):
                            raise SnakeVoid()
                        if self[body] == '3':
                            raise SnakeSpike()
                    self[body] = s.lower()
                self[self[s][-1]] = s
            else:
                for body in self[s]:
                    self[body] = s
    def undo(self):
        if len(self.stack) == 0:
            return False
        self.board, self.snake = self.stack.pop()
        self.cal_food()
        return True

# @on_command(('snake', 'test'), only_to_me=False)
# @config.ErrorHandle
# async def test(session: CommandSession):
#     await session.send(str(SnakeBird(0).board))

# snakebird = game.GameSameGroup('snakebird')

# @snakebird.begin_uncomplete(('play', 'snakebird', 'begin'), (1, 1))
# async def sb_begin_uncomplete(session: CommandSession, data: Dict[str, Any]):
#     # data: {'players': [qq], 'args': [args], 'anything': anything}
#     pass
    
# @snakebird.begin_complete(('play', 'snakebird', 'confirm'))
# async def sb_begin_complete(session: CommandSession, data: Dict[str, Any]):
#     # data: {'players': [qq], 'game': GameSameGroup instance, 'args': [args], 'anything': anything}
#     #开始游戏
#     #data['board'] = board
#     pass