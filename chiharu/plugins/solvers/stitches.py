from typing import Iterable, Tuple
# from chiharu.plugins.games.boxgame import Grid2DSquare as Grid
# UP, DOWN, LEFT, RIGHT = Grid.Directions.UP, Grid.Directions.DOWN, Grid.Directions.LEFT, Grid.Directions.RIGHT

class BoardInitErr(Exception):
    pass

class Board:
    # size: the size of the board (square).
    # side: whether the sides are present for each square. First vertical, second horizontal. First index for row, second column. 0 for not present, 1 for present.
    # count: the count of pins on each row and column. First row, second column.
    def __init__(self, size: int, side: Tuple[Iterable[Iterable[int]], Iterable[Iterable[int]]], count: Tuple[Iterable[int], Iterable[int]]):
        self.size = size
        # divide area
