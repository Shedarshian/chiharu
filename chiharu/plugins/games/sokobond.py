from typing import Tuple, Iterable, Dict
from collections import defaultdict
import itertools
import random
import math
from PIL import Image, ImageDraw, ImageFont
from .boxgame import Grid2DSquare as Grid, IBox, IBoxGame, ISpaceNoOverlap
Dirs = (UP, DOWN, LEFT, RIGHT) = (Grid.Directions.UP, Grid.Directions.DOWN,
                           Grid.Directions.LEFT, Grid.Directions.RIGHT)

class AtomBlocked(Exception):
    pass

class Atom(IBox):
    def __init_subclass__(cls, bond: int):
        cls.name = cls.__name__
        cls.bond_max = bond
        return super().__init_subclass__()
    def __init__(self, pos, space, bonds: Tuple[int, int, int, int] = (0, 0, 0, 0)):
        assert(sum(bonds) <= self.bond_max)
        self.bonds = bonds
        super().__init__(pos, space)
    def is_bond_max(self):
        return sum(self.bonds) == self.bond_max
    def add_bond(self, dir, atom=None):
        if atom is None:
            atom = self.space.getatom(self.pos + dir)
        self.bond[Dirs.index(dir)] += 1
        atom.bond[Dirs.index(-dir)] += 1
    def check_bond(self):
        if self.is_bond_max():
            return
        for dir, num in zip(Dirs, self.bonds):
            if num != 0:
                continue
            pos_new = self.pos + dir
            if not self.space.isPosValid(pos_new):
                continue
            atom = self.space.getatom(pos_new)
            if atom is not None and not atom.is_bond_max():
                self.add_bond(dir, atom)
    def move(self, dir):
        push = {self: dir}
        todo = {(self, dir)}
        try:
            while len(todo):
                atom, d = todo.pop()
                s = set([self.space[atom.pos + bond] for bond in atom.bonds.keys()])
                s -= push.keys()
                # TODO bond break and rotate
                push |= dict([(p, d) for p in s])
                todo |= s
                pos_new = atom.pos + dir
                if not self.space.isPosValid(pos_new):
                    raise AtomBlocked
        except AtomBlocked as e:
            return False
        self.space.move_bunch(push)
        for atom in push:
            atom.check_bond()
        return True

class He(Atom, bond=0):
    pass
class H(Atom, bond=1):
    pass
class O(Atom, bond=2):
    pass
class N(Atom, bond=3):
    pass
class C(Atom, bond=4):
    pass
atom_dict = {'e': He, 'H': H, 'O': O, 'N': N, 'C': C}

class Space(ISpaceNoOverlap):
    color = {' ': (255, 255, 255), '0': (223, 223, 223)}
    scheme = [(255, 223, 0)]
    font = [None, ImageFont.truetype("arial.ttf", 16), ImageFont.truetype("arial.ttf", 12)]
    def __init__(self, width: int, height: int, blank: Iterable[Grid], wall: Iterable[Grid], extra: Iterable[Tuple[Grid, int]]):
        self.width = width
        self.height = height
        self.blank = set(blank)
        self.wall = set(wall) | self.blank
        self.extra = extra
        self.atoms = defaultdict(lambda: None)
    def isPosValid(self, pos: Grid):
        return 0 <= pos.x < self.width and 0 <= pos.y < self.height and pos not in self.wall
    def getatom(self, pos: Grid):
        return self.atoms[pos]
    def move(self, dir):
        self.active.move(dir)
    def image(self, scheme):
        img = Image.new(
            'RGB', (32 * self.space.width, 32 * self.space.height), self.color[' '])
        draw = ImageDraw.Draw(img)
        for y, x in itertools.product(range(self.space.height), range(self.space.width)):
            pos = Grid(x, y)
            if pos in self.blank:
                continue
            elif pos in self.wall:
                draw.rectangle([32 * pos.x + 2, 32 * pos.y + 2, 32 * pos.x + 30, 32 * pos.y + 30],
                    self.scheme[scheme])
            else:
                draw.rectangle([32 * pos.x + 2, 32 * pos.y + 2, 32 * pos.x + 30, 32 * pos.y + 30],
                    self.color['0'])
            if pos in self.atoms:
                atom = self.atoms[pos]
                if atom.bonds[1] != 0: # DOWN bond
                    # 1: 15-17 2: 13-15&17-19 3: 11-13&15-17&19-21
                    for i in range(17 - 2 * atom.bonds[1], 16 + 2 * atom.bonds[1], 4):
                        draw.rectangle([32 * pos.x + i, 32 * pos.y + 16, 32 * pos.x + i + 1, 32 * pos.y + 48],
                            (0, 0, 0))
                if atom.bonds[3] != 0: # RIGHT bond
                    for i in range(17 - 2 * atom.bonds[3], 16 + 2 * atom.bonds[3], 4):
                        draw.rectangle([32 * pos.x + 16, 32 * pos.y + i, 32 * pos.x + 48, 32 * pos.y + i + 1],
                            (0, 0, 0))
                box = [32 * pos.x + 4, 32 * pos.y + 4, 32 * pos.x + 28, 32 * pos.y + 28]
                draw.arc(box, 0, 360, (255, 255, 255), 10)
                if atom is self.active:
                    for i in range(0, 359, 45):
                        draw.arc(box, i, i + 22.5, (0, 0, 0), 2)
                else:
                    draw.arc(box, 0, 360, (0, 0, 0), 2)
                lost = atom.bond_max - sum(atom.bonds)
                if lost != 0:
                    ini = random.uniform(0, 360)
                    for a in range(ini, ini + 359, 360 / lost):
                        p2 = (32 * pos.x + 16 + 12 * math.cos(math.radian(a)), 32 * pos.y + 16 + 12 * math.sin(math.radian(a)))
                        draw.arc([p2[0] - 2, p2[1] - 2, p2[0] + 2, p2[1] + 2], 0, 360, (0, 0, 0), 2)
                name = atom.__class__.__name__
                draw.text([32 * pos.x + 8, 32 * pos.y + 8], name, (0, 0, 0), font=font[len(name)])

class Sokobond(IBoxGame, space_cls=Space):
    def __init__(self, id):
        if '\\' in id or '/' in id or '.' in id:
            raise FileNotFoundError
        with open(config.rel(f'games\\snakebird\\{id}.txt')) as f:
            self.name, first, *l = [line.strip() for line in f.readlines()]
        active = None
        first_num = int(first[2:])
        first_element = first[0]
        width, height = len(l[0]), len(l)
        # e H O N C, B: blank, W: wall
        blank, wall = set(), set()
        atoms_todo = []
        extra = defaultdict(lambda: None)
        hint = defaultdict(lambda: None)
        for y, s in enumerate(l):
            for x, c in enumerate(more_itertools.chunked(s, 2)):
                if c[0] == 'B':
                    blank.add(Grid(x, y))
                elif c[0] == 'W':
                    wall.add(Grid(x, y))
                elif c[0] in atom_dict:
                    atoms_todo.append((atom_dict[c[0]], Grid(x, y)))
                    if c[0] == first_element:
                        first_num -= 1
                        if first_num == 0:
                            active = Grid(x, y)
                if c[1] in {'+', '-', 'O'}:
                    extra[Grid(x, y)] = c[1]
                elif isdigit(c[1]):
                    hint[Grid(x, y)] = int(c[1])
        self.space = Space(width, height, blank, wall, extra)
        for cl, pos in atoms_todo:
            self.space.atoms[pos] = cl(Grid(*pos), space)
        for cl, pos in atoms_todo:
            if hint[pos] != '0':
                self.space.getatom(pos).check_bond()
        self.space.active = self.space.getatom(active)
    def move(self, dir):
        self.space.move(dir)
    def image(self):
        return self.space.image(0) # TODO