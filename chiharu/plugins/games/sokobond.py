from typing import Tuple, Iterable, Dict
from chiharu.plugins.games.boxgame import Grid2DSquare, IBox, IBoxGame, ISpaceNoOverlap
(UP, DOWN, LEFT, RIGHT) = (Grid2DSquare.Directions.UP, Grid2DSquare.Directions.DOWN,
                           Grid2DSquare.Directions.LEFT, Grid2DSquare.Directions.RIGHT)

class AtomBlocked(Exception):
    pass

class Atom(IBox):
    def __init_subclass__(cls, name: str, bond: int):
        cls.name = cls.__name__
        cls.bond_max = bond
        return super().__init_subclass__()
    def __init__(self, pos, space, bonds: Dict[Grid2DSquare, int] = {}):
        assert(len(bonds) <= self.bond_max)
        self.bonds = bonds
        super().__init__(pos, space)
    def move(self, dir):
        push = {self: dir}
        # add bond
        todo = {(self, dir)}
        try:
            while len(todo):
                atom, d = todo.pop()
                s = set([atom.space[atom.pos + bond] for bond in atom.bonds.keys()])
                s -= push.keys()
                # TODO bond break and rotate
                push |= dict([(p, d) for p in s])
                todo |= s
                pos_new = atom.pos + dir
                if not atom.space.isPosValid(pos_new):
                    raise AtomBlocked
        except AtomBlocked as e:
            pass

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

class Space(ISpaceNoOverlap):
    def __init__(self, width: int, height: int, wall: Iterable[Grid2DSquare], extra: Iterable[Tuple[Grid2DSquare, int]]):
        self.width = width
        self.height = height
        self.wall = set(wall)
        self.extra = extra
    def isPosValid(self, pos: Grid2DSquare):
        return 0 <= pos.x < self.width and 0 <= pos.y < self.height and pos not in self.wall

class Sokobond(IBoxGame):
    pass
