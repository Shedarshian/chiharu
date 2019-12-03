from typing import Dict, Any, Tuple, List, Set, Any, Awaitable
import itertools
import more_itertools
import functools
from copy import copy, deepcopy
import json
from PIL import Image, ImageDraw
import base64
from io import BytesIO
from nonebot import on_command, CommandSession, permission, get_bot, NLPSession
from nonebot.command import call_command
import chiharu.plugins.config as config
import chiharu.plugins.game as game

def add(l: Tuple[int, int], r: Tuple[int, int]):
    return (l[0] + r[0], l[1] + r[1])
def sub(l: Tuple[int, int], r: Tuple[int, int]):
    return (l[0] - r[0], l[1] - r[1])
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
class CommandError(Exception):
    pass
class SnakeBird:
    dir = [(-1, 0), (0, 1), (1, 0), (0, -1)]  # dir: 0up 1right 2down 3left
    color = {'0': (159, 223, 255), 'A': (191, 0, 0), 'a': (255, 95, 95), 'B': (0, 0, 191), 'b': (95, 95, 255), 'C': (0, 191, 0), 'c': (95, 255, 95), 'bound': (63, 63, 63), '1': (
        191, 95, 53), 'grass': (121, 191, 75), 'block': (234, 128, 21), 'bar': (194, 106, 18), '2': (191, 0, 191), '3': (127, 127, 127), 'p1': (0, 255, 0), 'p2': (255, 255, 0), 'grid': (175, 207, 223)}
    def __init__(self, id):
        with open(config.rel(f'games\\snakebird\\{id}.txt')) as f:
            self.board = [list(line.strip()) for line in f.readlines()]
        self.border = ((0, len(self.board)), (0, len(self.board[0])))
        # 0: blank 1: wall 2: food 3: spike 8: portal 9: end Aaa: snake IIIJJ: block Z: void T: tail
        _head = dict([(c, more_itertools.only([(i, line.index(c))
                                               for i, line in enumerate(self.board) if c in line])) for c in 'ABC'])
        self.snake = {}  # 蛇头在list尾部
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
        self.win = more_itertools.only(
            [(i, line.index('9')) for i, line in enumerate(self.board) if '9' in line])
        self[self.win] = '0'
        self.portal = functools.reduce(lambda x, y: x + y, [
            [(i, j) for j in more_itertools.locate(line, lambda x: x == '8')] for i, line in enumerate(self.board)])
        assert(len(self.portal) in {0, 2})
        if len(self.portal) == 2:
            self[self.portal[0]] = self[self.portal[1]] = '0'
        _block = [(x, functools.reduce(lambda y, z: y + z, [
            [(i, j) for j in more_itertools.locate(line, lambda y: y == x)]
            for i, line in enumerate(self.board)
            ])
            ) for x in 'IJKLMN']
        self.block = dict([x for x in _block if x[1] != []])
        # divide
        self.bar = {}
        for id, body in self.block.items():
            divide = []
            b = set(body)
            while len(b):
                pos = b.pop()
                divide.append({pos})
                todo = {pos}
                while len(todo):
                    p = todo.pop()
                    for dir in self.dir:
                        q = add(p, dir)
                        if q in b:
                            b -= {q}
                            divide[-1].add(q)
                            todo.add(q)
            if len(divide) <= 1:
                continue
            self.bar[id] = []
            m = min(body)
            for l1, l2 in itertools.combinations(divide, 2):
                for p, q in itertools.product(l1, l2):
                    if p[0] == q[0] or p[1] == q[1] and not (add(p, (0, 1)) in l1 and add(p, (0, -1)) in l1 and add(q, (0, 1)) in l2 and add(q, (0, -1)) in l2):
                        self.bar[id].append(
                            tuple(sorted((sub(p, m), sub(q, m)))))
        self.stack = []
        self.cal_food()
    def cal_food(self):
        self.food = 0
        for line in self.board:
            for c in line:
                if c == '2':
                    self.food += 1
        self.activate = sorted(self.snake.keys())[0]
        self.portal_activate = False if len(
            self.portal) == 0 else self[self.portal[0]] == '0' and self[self.portal[1]] == '0'
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
    def move(self, snake_id=None, dir=None):
        if snake_id is None:
            snake_id = self.activate
        else:
            self.activate = snake_id
        if dir is None:
            return '', True
        assert(snake_id in 'ABC' and dir in range(4))
        if self.snake[snake_id] is None:
            return '未发现此蛇', False
        dir = self.dir[dir]
        snake = self.snake[snake_id]
        pos = add(snake[-1], dir)
        try:
            self.stack.append((deepcopy(self.board), deepcopy(
                self.snake), deepcopy(self.block)))
            if not in_border(pos, self.border):
                return '不能超出边界', False
            elif self[pos] in set('AaBbCcIJKLMN0') - {snake_id, snake_id.lower()}:
                if self[pos] != '0':
                    ret = self.push(dir, self[pos].upper(), snake_id)
                    if ret is None:
                        return '蛇被阻挡，无法前进', False
                    assert(snake_id not in ret)
                self[snake[0]] = '0'
                self.check_portal_activate()
                if self[pos] != '0':
                    self.parallel_move(dir, ret)
                    self.check_portal_activate()
                self[snake[-1]] = snake_id.lower()
                self[pos] = snake_id
                snake.pop(0)
                snake.append(pos)
                self.check_win()
                ret = self.check_portal()
                self.fall()
                return '传送失败，目标被阻挡' if ret == False else '', True
            elif self[pos] == '2':
                self[snake[-1]] = snake_id.lower()
                self[pos] = snake_id
                snake.append(pos)
                self.food -= 1
                ret = self.fall()
                return '传送失败，目标被阻挡' if ret == False else '', True
            else:
                return '蛇被阻挡，无法前进', False
        except SnakeSpike:
            self.undo()
            return '蛇掉到刺上死亡了！自动撤销一步', False
        except SnakeVoid:
            self.undo()
            return '蛇掉入虚空死亡了！自动撤销一步', False
    def check_win(self):
        if self.food != 0:
            return
        t = self[self.win]
        if t in 'ABC':
            for p in self[t]:
                self[p] = '0'
            self.snake.pop(t)
            if self.snake == {}:
                raise SnakeWin()
            self.activate = sorted(self.snake.keys())[0]
            self.check_portal_activate()
    def check_portal(self):
        if not self.portal_activate:
            return True
        if self[self.portal[0]] != '0' and self[self.portal[1]] != '0':
            self.portal_activate = False
            return True
        if self[self.portal[0]] == '0' and self[self.portal[1]] == '0':
            return True
        self.portal_activate = False
        _from, _to = self.portal if self[self.portal[0]] != '0' else reversed(
            self.portal)
        delta = sub(_to, _from)
        body = self[self[_from].upper()]
        for pos in body:
            t = add(pos, delta)
            if not in_border(t, self.border) or self[t] != '0':
                return False
        # fine
        self[self[_from].upper()] = [add(pos, delta) for pos in body]
        for pos in body:
            self[add(pos, delta)] = self[pos]
            self[pos] = '0'
        self.check_win()
        self.fall()
        return True
    def check_portal_activate(self):
        if not self.portal_activate and len(self.portal) == 2 and self[self.portal[0]] == '0' and self[self.portal[1]] == '0':
            self.portal_activate = True
    def support(self, dir: Tuple[int, int], snake_id, tail=None):
        snake = self[snake_id]
        assert(snake is not None)
        s = set()
        for body in snake:
            pos = add(body, dir)
            if not in_border(pos, self.border):
                if dir == (1, 0):
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
        if (set('123Z') | {pusher_id, pusher_id.lower()}) & s:
            return None
        else:
            return s & set('ABCIJKLMN')
    def fall(self):
        ret = None
        while 1:
            s = dict([(id, []) for id, obj in itertools.chain(
                self.snake.items(), self.block.items()) if obj is not None])
            k = set(s.keys())
            s.update(dict([(id, []) for id in '123Z']))
            for id in k:
                for i in self.support(self.dir[2], id):
                    s[i].append(id)
            has_support = set(itertools.chain(s['1'], s['2'])) | (
                set(s['3']) & set('IJKLMN'))
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
                self.check_portal_activate()
                self.check_win()
                ret = bool(ret)
                ret |= self.check_portal()
            else:
                return ret
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
                    if not in_border(body, self.border):
                        self.block.pop(s)
                        break
                    self[body] = s
    def undo(self):
        if len(self.stack) == 0:
            return False
        self.board, self.snake, self.block = self.stack.pop()
        self.cal_food()
        return True
    def image(self):
        img = Image.new(
            'RGB', (16 * len(self.board[0]), 16 * len(self.board)), self.color['0'])
        draw = ImageDraw.Draw(img)
        # first grid
        for i in range(len(self.board)):
            draw.line([0, 16 * i, 16 * len(self.board[0]), 16 * i],
                      self.color['grid'])
            draw.line([0, 16 * i + 15, 16 * len(self.board[0]),
                       16 * i + 15], self.color['grid'])
        for j in range(len(self.board[0])):
            draw.line([16 * j, 0, 16 * j, 16 * len(self.board)],
                      self.color['grid'])
            draw.line([16 * j + 15, 0, 16 * j + 15, 16 *
                       len(self.board)], self.color['grid'])
        # next '9' and '8'
        if self.food == 0:
            i, j = self.win
            f = Image.open(config.rel(f'games\\snakebird\\91.png'))
            img.paste(f, (16 * j - 8, 16 * i - 8), f)
        else:
            i, j = self.win
            f = Image.open(config.rel(f'games\\snakebird\\90.png'))
            img.paste(f, (16 * j + 2, 16 * i + 2), f)
        for pos in self.portal:
            i, j = pos
            draw.arc([16 * j + 4, 16 * i + 4, 16 * j + 12,
                      16 * i + 12], 0, 360, self.color['p1'], 10)
            draw.arc([16 * j + 6, 16 * i + 6, 16 * j + 10,
                      16 * i + 10], 0, 360, self.color['p2'], 10)
        # next block bar
        for id, bars in self.bar.items():
            for bar in bars:
                m = min(self.block[id])
                draw.rectangle([16 * (bar[0][1] + m[1]) + 5, 16 * (bar[0][0] + m[0]) + 5, 16 * (
                    bar[1][1] + m[1]) + 10, 16 * (bar[1][0] + m[0]) + 10], self.color['bar'])
        # next 123 in board
        d = {(-1, 0): [5, 0, 10, 2], (0, 1): [11, 5, 15, 10],
             (1, 0): [5, 11, 10, 15], (0, -1): [0, 5, 2, 10]}
        f = Image.open(config.rel(f'games\\snakebird\\3.png'))
        for i, line in enumerate(self.board):
            for j, block in enumerate(line):
                if block == '1':
                    if i == 0 or self[(i - 1, j)] != '1':
                        draw.rectangle(
                            [16 * j, 16 * i, 16 * j + 15, 16 * i + 3], self.color['grass'])
                        draw.rectangle(
                            [16 * j, 16 * i + 4, 16 * j + 15, 16 * i + 15], self.color['1'])
                    else:
                        draw.rectangle(
                            [16 * j, 16 * i, 16 * j + 15, 16 * i + 15], self.color['1'])
                elif block == '2':
                    draw.polygon([16 * j + 7, 16 * i + 3, 16 * j + 4, 16 *
                                  i + 11, 16 * j + 11, 16 * i + 11], self.color['2'])
                elif block == '3':
                    pos = (i, j)
                    _in = [dir for dir in self.dir if in_border(
                        add(pos, dir), self.border) and self[add(pos, dir)] == '3']
                    if len(_in) == 0:
                        crop = (0, 0, 16, 16)
                        trans = None
                    elif len(_in) == 1:
                        crop = (16, 0, 32, 16)
                        trans = {(-1, 0): Image.ROTATE_180, (1, 0): None, (0, 1)
                                  : Image.ROTATE_90, (0, -1): Image.ROTATE_270}[_in[0]]
                    elif len(_in) == 2 and add(*_in) == (0, 0):
                        crop = (0, 16, 16, 32)
                        trans = [None, Image.ROTATE_90][abs(_in[0][0])]
                    elif len(_in) == 2:
                        crop = (32, 0, 48, 16)
                        trans = {(-1, 1): Image.ROTATE_90, (-1, -1): Image.ROTATE_180,
                                 (1, -1): Image.ROTATE_270, (1, 1): None}[add(*_in)]
                    elif len(_in) == 3:
                        crop = (16, 16, 32, 32)
                        trans = {(-1, 0): Image.ROTATE_180, (1, 0): None, (0, 1): Image.ROTATE_90,
                                 (0, -1): Image.ROTATE_270}[(set(self.dir) - set(_in)).pop()]
                    else:
                        crop = (32, 16, 48, 32)
                        trans = None
                    c = f.crop(crop)
                    if trans is not None:
                        c = c.transpose(trans)
                    img.paste(c, (16 * j, 16 * i), c)
        # next snake
        d = {(-1, 0): [3, 0, 12, 2], (0, 1): [13, 3, 15, 12],
             (1, 0): [3, 13, 12, 15], (0, -1): [0, 3, 2, 12]}
        d4 = {(-1, 0): [5, 0, 10, 4], (0, 1): [11, 5, 15, 10], (1, 0): [5, 11, 10, 15], (0, -1): [0, 5, 4, 10],
              (-1, -1): [0, 0, 4, 4], (-1, 1): [11, 0, 15, 4], (1, -1): [0, 11, 4, 15], (1, 1): [11, 11, 15, 15]}
        for id, body in self.snake.items():
            b = list(reversed(body))
            for i_b, pos in enumerate(b):
                i, j = pos
                color = self.color[id if i_b % 2 == 0 else id.lower()]
                draw.rectangle([16 * j, 16 * i, 16 * j + 15,
                                16 * i + 15], self.color['bound'])
                draw.rectangle([16 * j + 3, 16 * i + 3, 16 *
                                j + 12, 16 * i + 12], color)
                if i_b != 0:
                    draw.rectangle(list(
                        itertools.starmap(lambda x, y: x + y,
                                          zip([16 * j, 16 * i, 16 * j, 16 * i],
                                              d[sub(b[i_b - 1], pos)]
                                              ))
                    ), color)
                else:
                    # draw eye on head
                    if self.activate == id:
                        draw.arc([16 * j + 5, 16 * i + 5, 16 * j + 10,
                                  16 * i + 10], 0, 360, (255, 255, 255), 10)
                        draw.rectangle(
                            [16 * j + 7, 16 * i + 7, 16 * j + 7, 16 * i + 7], (0, 0, 0))
                    else:
                        draw.rectangle(
                            [16 * j + 5, 16 * i + 7, 16 * j + 9, 16 * i + 7], (0, 0, 0))
                if i_b != len(b) - 1:
                    draw.rectangle(list(
                        itertools.starmap(lambda x, y: x + y,
                                          zip([16 * j, 16 * i, 16 * j, 16 * i],
                                              d[sub(b[i_b + 1], pos)]
                                              ))
                    ), color)
        # next block
        for id, body in self.block.items():
            for pos in body:
                i, j = pos
                for r, dr in d4.items():
                    if add(pos, r) not in body or (r[0] != 0 and r[1] != 0 and (add(pos, (r[0], 0)) not in body or add(pos, (0, r[1])) not in body)):
                        draw.rectangle(list(
                            itertools.starmap(lambda x, y: x + y,
                                              zip([16 * j, 16 * i, 16 * j, 16 * i], dr))
                        ), self.color['block'])
        return img
    def base64(self):
        buffered = BytesIO()
        self.image().save(buffered, format="JPEG")
        return 'base64://' + base64.b64encode(buffered.getvalue()).decode()

snakebird = game.GameSameGroup('snakebird', can_private=True)

@snakebird.begin_uncomplete(('play', 'snakebird', 'begin'), (1, 1))
async def sb_begin_uncomplete(session: CommandSession, data: Dict[str, Any]):
    # data: {'players': [qq], 'args': [args], 'anything': anything}
    pass

@snakebird.begin_complete(('play', 'snakebird', 'confirm'))
async def sb_begin_complete(session: CommandSession, data: Dict[str, Any]):
    # data: {'players': [qq], 'game': GameSameGroup instance, 'args': [args], 'anything': anything}
    # 开始游戏
    try:
        data['level'] = session.current_arg_text.replace('*', '☆')
        board = SnakeBird(data['level'])
    except FileNotFoundError:
        await session.send('关卡未发现')
        await call_command(get_bot(), session.ctx, data['game'].end_command, current_arg="")
    else:
        data['board'] = board
        board.image().save(config.img('snake.png'))
        await session.send([config.cq.img('snake.png')])

@snakebird.process(only_short_message=False)
async def sb_process(session: NLPSession, data: Dict[str, Any], delete_func: Awaitable):
    arg = session.msg_text.strip()
    if len(arg) == 0 or arg[0] not in '红蓝绿上下左右撤':
        return
    board = data['board']
    try:
        for s in arg:
            if s in '红蓝绿':
                st, ret = board.move({'红': 'A', '蓝': 'B', '绿': 'C'}[s])
            elif s in '上下左右':
                st, ret = board.move(None, {'上': 0, '下': 2, '左': 3, '右': 1}[s])
            elif s == '撤':
                ret = board.undo()
                st = '' if ret else '撤回失败'
            elif s in ' 销':
                return
            else:
                raise CommandError('未知字符：' + s)
            if not ret:
                raise CommandError(st + '，指令：' + s)
            elif st != '':
                await session.send(st + '，指令：' + s)
    except CommandError as e:
        await session.send(e.args[0])
        board.image().save(config.img('snake.png'))
        await session.send([config.cq.img('snake.png')])
    except SnakeWin:
        board = None
        qq = session.ctx['user_id']
        d = data['game'].open_data(qq)
        if 'win' not in d:
            d['win'] = [data['level']]
        elif data['level'] not in d['win']:
            d['win'].append(data['level'])
        data['game'].save_data(qq, d)
        await session.send('Level clear!')
        await delete_func()
    else:
        board.image().save(config.img('snake.png'))
        await session.send([config.cq.img('snake.png')])

@snakebird.end(('play', 'snakebird', 'end'))
async def sb_end(session: CommandSession, data: Dict[str, Any]):
    await session.send('已删除')

@on_command(('play', 'snakebird', 'check'), only_to_me=False)
@config.ErrorHandle
async def sb_check(session: CommandSession):
    try:
        with open(config.rel(f'games\\user_data\\{session.ctx["user_id"]}.json'), encoding='utf-8') as f:
            data = json.load(f)
            if 'snakebird' not in data or 'win' not in data['snakebird']:
                await session.send('您还未通过任何一关')
            await session.send('您已通过关卡：' + ', '.join([str(x) for x in sorted(data['snakebird']['win'])]))
    except FileNotFoundError:
        await session.send('您还未通过任何一关')
