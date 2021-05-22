from typing import Union, Tuple
from dataclasses import dataclass
import itertools, more_itertools
from PIL import Image, ImageDraw, ImageChops
import base64
from io import BytesIO
from nonebot import CommandSession
from .boxgame import Grid2DSquare as Pos
from .. import config, game
from ..config import on_command
from .achievement import achievement, cp, cp_add
(Up, Down, Left, Right) = Pos.Directions.UP, Pos.Directions.DOWN, Pos.Directions.LEFT, Pos.Directions.RIGHT

# 岸上/水上
# 飞机=/-，云1/0，岸+，目的地P，加油站U，指南针Z，乌云M/N，箭头WASD/IJKL
# 时钟I(奇数阻挡)O(偶数阻挡)/TY，乌云时钟V(奇数阻挡)B(偶数阻挡)/GH
# 传送点aabbccddee/fghij，钥匙X，锁./C，[热气球2/3]，火车站~
# [湍流456/789]，风扇"/'，边界传送_
# 图层：
# 云，未开的锁和时钟，飞机/气流，湍流
# 乌云，未开的乌云时钟
# 热气球
# 箭头以及地面设施物品以及开的锁和时钟
# 海水和陆地
# 传送a紫b绿c蓝

class JetWin(Exception):
    pass
class JetDeath(Exception):
    pass

class UnmoveableObject:
    def __init__(self, board, is_shore):
        self.is_shore = is_shore
        self.board = board
    def canMoveIn(self, isBus: bool):
        return not (isBus and not self.is_shore)
    def moveOn(self, isBus: bool) -> Union[None, Pos, Tuple[Pos]]:
        pass
    def moveOut(self, isBus: bool):
        pass
    def balloonMoveOn(self) -> Union[None, Pos, Tuple[Pos]]:
        pass
    def turn(self):
        pass
    canTurboIn = True
    _crop = None
    layer = 0 # bigger goes upward
    def paste(self, res, img, pos):
        crop = res.crop(self._crop)
        img.paste(crop, pos, crop)

class Cloud(UnmoveableObject):
    def canMoveIn(self, isBus):
        return False
    _crop = (Pos(0, 0), Pos(16, 16))
    layer = 3
class DarkCloud(UnmoveableObject):
    def moveOn(self, isBus):
        raise JetDeath
    def balloonMoveOn(self):
        return Pos(0, 0)
    _crop = (Pos(0, 0), Pos(16, 16))
    _dark_color = '#4f005b'
    def paste(self, res, img, pos):
        crop = res.crop(self._crop)
        img.paste(Image.new('RGBA', (16, 16), self._dark_color), pos, crop)
    canTurboIn = False
    layer = 2
class Destination(UnmoveableObject):
    def moveOn(self, isBus):
        raise JetWin
    def balloonMoveOn(self):
        return Pos(0, 0)
    _crop = (Pos(0, 16), Pos(16, 40))
    def paste(self, res, img, pos):
        crop = res.crop(self._crop)
        img.paste(crop, pos + Pos(0, -8), crop)
class Compass(UnmoveableObject):
    def moveOn(self, isBus):
        return Pos(0, 0)
    def balloonMoveOn(self):
        return Pos(0, 0)
    _crop = (Pos(16, 0), Pos(32, 16))
class GasStation(UnmoveableObject):
    def moveOn(self, isBus):
        self.board.game.clearGas()
    def moveOut(self, isBus):
        self.board.game.clearGas()
    _crop = (Pos(32, 0), Pos(48, 16))
class Arrow(UnmoveableObject):
    def __init__(self, board, is_shore, id):
        self.dir = {'W': Up, 'A': Left, 'S': Down, 'D': Right, 'I': Up, 'J': Left, 'K': Down, 'L': Right}[id]
        self.trans = {Up: Image.ROTATE_90, Left: None, Right: Image.ROTATE_180, Down: Image.ROTATE_270}[self.dir]
        super(Arrow, self).__init__(board, is_shore)
    def moveOn(self, isBus):
        return self.dir
    def balloonMoveOn(self):
        return self.dir
    _crop = (Pos(48, 0), Pos(64, 16))
    def paste(self, res, img, pos):
        if self.trans is not None:
            crop = res.crop(self._crop).transpose(self.trans)
        img.paste(crop, pos, crop)
class Teleporter(UnmoveableObject):
    color_list = ['#ff00ff', '#00ff00', '#0000ff', '#ff0000', '#00ffff']
    def __init__(self, board, is_shore, id):
        self.teleport: Pos = None # the teleport position
        self.color = 'abcdefghij'.index(id) % 5
        super().__init__(board, is_shore)
    def moveOn(self, isBus):
        if self.board[self.teleport].canMoveIn():
            return (self.teleport,)
    def balloonMoveOn(self):
        if self.board[self.teleport].canMoveIn():
            return (self.teleport,)
    _crop = (Pos(64, 0), Pos(80, 16))
    _crop2 = (Pos(80, 0), Pos(96, 16))
    def paste(self, res, img, pos):
        crop = ImageChops.overlay(res.crop(self._crop),
            ImageChops.multiply(
                Image.new('RGBA', (16, 16), self.color_list[self.color]),
                res.crop(self._crop2)))
        img.paste(crop, pos, crop)
class Key(UnmoveableObject):
    def moveOn(self, isBus):
        self.board.game.open()
    _crop = (Pos(96, 0), Pos(112, 16))
class Lock(UnmoveableObject):
    def canMoveIn(self, isBus):
        return self.board.game.isOpen
    @property
    def layer(self):
        return 0 if self.board.game.isOpen else 3
    _crop = (Pos(112, 0), Pos(128, 16))
    _crop_cloud = (Pos(0, 0), Pos(16, 16))
    def paste(self, res, img, pos):
        crop = ImageChops.overlay(res.crop(self._crop_cloud),
            res.crop(self._crop))
        img.paste(crop, pos, crop)
class Clock(UnmoveableObject):
    def __init__(self, board, is_shore, id):
        if id not in 'IT':
            board.game.open_status.append(self)
        super().__init__(board, is_shore)
    def canMoveIn(self, isBus):
        return self in self.board.game.open_status
    canTurboIn = False
    @property
    def layer(self):
        return 0 if self in self.board.game.open_status else 3
    _crop = (Pos(16, 16), Pos(32, 32))
    _crop_cloud = (Pos(0, 0), Pos(16, 16))
    def paste(self, res, img, pos):
        crop = res.crop(self._crop)
        if self in self.board.game.open_status:
            img.paste(Image.new('RGBA', (16, 16), '#ffffff'), pos, crop)
        else:
            crop = ImageChops.overlay(res.crop(self._crop_cloud), crop)
            img.paste(crop, pos, crop)
class DarkClock(UnmoveableObject):
    def __init__(self, board, is_shore, id):
        if id not in 'VG':
            board.game.open_status.append(self)
        super().__init__(board, is_shore)
    def moveOn(self, isBus):
        if self not in self.board.game.open_status:
            raise JetDeath
    canTurboIn = False
    @property
    def layer(self):
        return 0 if self in self.board.game.open_status else 2
    _crop = (Pos(16, 16), Pos(32, 32))
    _crop_cloud = (Pos(0, 0), Pos(16, 16))
    _dark_color = '#4f005b'
    def paste(self, res, img, pos):
        if self in self.board.game.open_status:
            crop = res.crop(self._crop)
            img.paste(Image.new('RGBA', (16, 16), self._dark_color), pos, crop)
        else:
            crop = res.crop(self._crop_cloud)
            crop.paste(Image.new('RGBA', (16, 16), self._dark_color), None, crop)
            crop = ImageChops.overlay(Image.new('RGBA', (16, 16), '#ffffff'), res.crop(self._crop))
            img.paste(crop, pos, crop)
class Station(UnmoveableObject):
    def moveOn(self, isBus):
        self.board.game.transfer()
    _crop = (Pos(32, 16), Pos(48, 32))
class Fan(UnmoveableObject):
    def moveOn(self, isBus):
        self.board.game.blow()
    _crop = (Pos(48, 16), Pos(64, 32))

UnmoveableDict = dict(itertools.chain(*[[(c, cl) for c in s] for s, cl in (('-=+23456789', UnmoveableObject), ('01', Cloud), ('MN', DarkCloud), ('P', Destination), ('Z', Compass), ('U', GasStation), ('WASDIJKL', Arrow), ('abcdefghij', Teleporter), ('X', Key), ('C', Lock), ('IOTY', Clock), ('VBGH', DarkClock), ('~', Station), ('\'"', Fan))]))
def Unmoveable(board, id):
    if id in 'WASDIJKLIOTYVBGHabcdefghij':
        return UnmoveableDict[id](board, id in 'IOVBWASDabcde', id)
    return UnmoveableDict[id](board, id in '=1+PUZM2456\'')

class Board:
    def __init__(self, board_init, game):
        self.game = game
        self.width = len(board_init[0]) - 2
        self.height = len(board_init) - 2
        board_inner = [x[1:-1] for x in board_init[1:-1]]
        self.border_row = [c == '_' for c in board_init[0][1:-1]]
        self.border_column = [c[0] == '_' for c in board_init[1:-1]]
        self.board = [[Unmoveable(self, x) for x in l] for l in board_inner]
        teleport = {}
        for j, l in enumerate(board_inner):
            for i, x in enumerate(l):
                if x in 'abcdefghij':
                    xx = 'abcdefghij'.index(x)
                    if xx not in teleport:
                        teleport[xx] = Pos(i, j)
                    else:
                        pos = Pos(i, j)
                        pos2 = teleport.pop(x)
                        self[pos].teleport = pos2
                        self[pos2].teleport = pos
    def circular(self, pos: Pos):
        if pos[0] < 0 and self.border_column[pos[1]]:
            return Pos(self.width - 1, pos[1])
        elif pos[0] >= self.width and self.border_column[pos[1]]:
            return Pos(0, pos[1])
        elif pos[1] < 0 and self.border_row[pos[0]]:
            return Pos(pos[0], self.height - 1)
        elif pos[1] >= self.height and self.border_row[pos[0]]:
            return Pos(pos[0], 0)
        return pos
    def __getitem__(self, pos: Pos):
        if 0 <= pos[0] < self.width and 0 <= pos[1] <= self.height:
            return self.board[pos[1]][pos[0]]
        else:
            return None
    __setitem__ = None
    def open(self):
        for l in self.board:
            for x in l:
                x.open()
    @property
    def size(self):
        return Pos(self.width, self.height)
    def grids(self):
        for j, i in itertools.product(range(self.height), range(self.width)):
            yield Pos(i, j)

class Jet:
    def __init__(self, game, pos):
        self.direction = Right
        self.lastMoveDir = Right
        self.isJet = True
        self.pos = pos
        self.game = game
    def moveOne(self, dir):
        pos_new = self.game.board.circular(self.pos + dir)
        tile = self.game.board[pos_new]
        if not tile or not tile.canMoveIn(False):
            return False
        obj = self.game.objects[pos_new]
        if isinstance(obj, Balloon):
            if not obj.canMoveOne(dir):
                return False
        elif obj != set():
            return False
        # move
        self.game.board[self.pos].moveOut()
        self.game.objects.addStream(self.pos, -dir)
        self.pos = pos_new
        ret = self.game.board[pos_new].moveOn()
        self.lastMoveDir = dir
        if isinstance(obj, Balloon):
            obj.move(dir)
        if ret is None:
            pass
        elif isinstance(ret, Pos):
            dir = ret
        else:
            self.pos = ret[0]
            self.lastMoveDir = Pos(0, 0)
        self.game.objects.addStream(self.pos, -dir)
        self.direction = dir
        # We assert that if jet stays in the balloon's position
        # where it is an arrow, then the jet turn direction
        # and move. But not teleporter.
        if isinstance(obj, Balloon) and not isinstance(ret, Pos):
            return Pos(0, 0)
        return dir
    _crop = (Pos(64, 16), Pos(80, 32))
    _crop_bus = (Pos(80, 16), Pos(96, 32))
    _trans = {Up: Image.ROTATE_90, Left: None, Right: Image.ROTATE_180, Down: Image.ROTATE_270}
    def paste(self, res, img, pos):
        if self.isJet:
            crop = res.crop(self._crop)
        else:
            crop = res.crop(self._crop_bus)
        trans = self._trans[self.direction]
        if trans is not None:
            crop = crop.transpose(trans)
        img.paste(crop, pos, crop)

class Balloon:
    def __init__(self,games, pos):
        self.pos = pos
        self.game = game
    def canMoveOne(self, dir):
        tile_same = self.game.board[self.pos]
        if isinstance(tile_same, DarkCloud) or isinstance(tile_same, DarkClock) and tile_same not in self.game.open_status:
            return False
        pos_new = self.game.board.circular(self.pos + dir)
        tile = self.game.board[pos_new]
        if not tile or not tile.canMoveIn(False):
            return False
        obj = self.game.objects[pos_new]
        if obj != set():
            return False
        return True
    def moveOne(self, dir):
        pos_new = self.game.board.circular(self.pos + dir)
        tile = self.game.board[pos_new]
        self.pos = pos_new
        ret = tile.balloonMoveOn()
        if ret is None:
            return dir
        elif isinstance(ret, Pos):
            return ret
        else:
            self.pos = ret[0]
            return dir
    def move(self, dir):
        while 1:
            ret = self.canMoveOne(dir) and self.moveOne(dir)
            if ret == Pos(0, 0):
                return True
            elif ret == False:
                return False
            else:
                dir = ret
    layer = 1
    def paste(self, res, img, pos, color):
        pass # TODO
class Turbo:
    def __init__(self, game, pos, size):
        self.size = size
        self.pos = pos
        self.game = game
    def paste(self, res, img, pos):
        pass # TODO

class Objects:
    def __init__(self, board_init, game):
        self.game = game
        self.board = game.board
        self.balloons = []
        self.turbos = {}
        for j, l in enumerate(board_init):
            for i, x in enumerate(l):
                pos = Pos(i, j)
                if x in '-=':
                    self.jet = Jet(self.game, pos)
                elif x in '23':
                    self.balloons.append(Balloon(self.game, pos))
                elif x in '456789':
                    self.turbos[pos] = Turbo(self.game, pos, (int(x) - 4) % 3)
        self.stream = [[set() for x in self.board.width] for l in self.board.height]
    def __getitem__(self, pos):
        if pos == self.jet.pos:
            return self.jet
        if pos in self.turbos:
            return self.turbos[pos]
        b = more_itertools.only([x for x in self.balloons if x.pos == pos])
        if b:
            return b
        return self.stream[pos[1]][pos[0]]
    __setitem__ = None
    def addStream(self, pos, dir):
        self.stream[pos[1]][pos[0]].add(dir)

class Jetstream:
    color = {'sea': (111, 183, 174), 'shore': (138, 174, 85), 'cloud': (255, 255, 255)}
    def __init__(self, id):
        if '\\' in id or '/' in id or '.' in id:
            raise FileNotFoundError
        with open(config.rel(f'games\\jetstream\\{id}.txt')) as f:
            board_init = [list(line.strip()) for line in f.readlines()]
        self.open_status = [] # opened
        self.board = Board(board_init, self)
        self.objects = Objects(board_init, self)
        self.jet = self.objects.jet
        self.isOpen = False
        # self._to_backup = {'objects', 'turn', 'isOpen', 'open_status', 'jet'}
    def open(self):
        self.isOpen = True
    def clearGas(self):
        self.objects.stream = [[set() for x in self.board.width] for l in self.board.height]
    def transfer(self):
        self.jet.isJet = not self.jet.isJet
    def blow(self):
        self.objects.turbos = {}
    def move(self, dir):
        # jet move
        continue_move = 1
        while continue_move:
            ret = self.jet.moveOne(dir)
            if ret == False:
                if continue_move == 1:
                    return False
                else:
                    break
            elif ret == Pos(0, 0):
                break
            elif ret is None:
                continue_move = self.jet.isJet
            else:
                dir = ret
                continue_move = True
        # turbo spread
        for pos in self.board.grids():
            tile = self.board[pos]
            if not tile.canTurboIn or not tile.canMoveIn(False):
                continue
            obj = self.objects[pos]
            if obj == set():
                for dir in (Up, Left, Down, Right):
                    pos_new = self.board.circular(pos + dir)
                    if isinstance(obj_new := self.objects[pos_new], Turbo) and obj_new.size == 2:
                        self.objects.turbos[pos] = Turbo(self, pos, -1)
                if isinstance(tile, Teleporter):
                    pos_new = tile.teleport
                    if isinstance(obj_new := self.objects[pos_new], Turbo) and obj_new.size == 2:
                        self.objects.turbos[pos] = Turbo(self, pos, -1)
        for obj in self.objects.turbos.values():
            if obj.size < 2:
                obj.size += 1
        # add turn
        for pos in self.board.grids():
            tile = self.board[pos]
            if self.objects[pos] == set() and isinstance(tile, (Clock, DarkClock)):
                if tile in self.open_status[0]:
                    self.open_status[0].remove(tile)
                    self.open_status[1].append(tile)
                else:
                    self.open_status[1].remove(tile)
                    self.open_status[0].append(tile)
    def image(self):
        sz = 16
        of = Pos(8, 8)
        m = Pos(sz, sz)
        img = Image.new('RGB', sz * self.board.size + Pos(sz, sz), self.color['cloud'])
        draw = ImageDraw.Draw(img)
        res = Image.open(config.rel(f'games\\snakebird\\resources.png'))
        draw_layer = {0: [], 1: [], 2: [], 3: []}
        for pos in self.board.grids():
            tile = self.board[pos]
            # sea and shore
            draw.rectangle((sz * pos + of, sz * pos + of + m), self.color['shore' if tile.is_shore else 'sea'])
            # board resources
            if tile.crop is not None:
                draw_layer[tile.layer].append(lambda: tile.paste(res, img, sz * pos + of))
        # balloon
        for i, balloon in enumerate(self.objects.balloons):
            draw_layer[balloon.layer].append(lambda: balloon.paste(res, img, sz * pos + of, i))
        # draw
        for ls in draw_layer.values():
            for lmd in ls:
                lmd()
        # turbo
        for pos, turbo in self.objects.turbos.items():
            turbo.paste(res, img, sz * pos + of)
        # jet
        self.jet.paste(res, img, sz * pos + of)
        # stream
        # TODO