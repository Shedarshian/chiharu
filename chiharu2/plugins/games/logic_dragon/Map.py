from enum import IntEnum, auto
from chiharu2.plugins.helper.boxgame import *

class Map:
    def __init__(self, left: int, right: int, down: int, up: int) -> None:
        self.left = left
        self.right = right
        self.down = down
        self.up = up
        self.terrian: dict[int, dict[int, Terrian]] = {y: {} for y in range(down, up + 1)}
        self.cells: dict[int, dict[int, Cell]] = {y: {} for y in range(down, up + 1)}

    def Encode(self) -> dict:
        return {
            "left": self.left,
            "right": self.right,
            "down": self.down,
            "up": self.up,
            "terrian": "{" + ", ".join(f"""{y}: {{{
                ', '.join(f'{x}: {t.value}' for x, t in it.items())
                }}}""" for y, it in self.terrian.items()) + "}",
            "cells": "{" + ", ".join(f"""{y}: {{{
                ', '.join(f'{x}: {t.__class__.__name__}({t.Encode()})' for x, t in it.items())
                }}}""" for y, it in self.cells.items()) + "}",
        }
    @classmethod
    def Decode(cls, o: dict) -> "Map":
        m = Map(o["left"], o["right"], o["down"], o["up"])
        m.terrian = eval(o["terrian"])
        m.cells = eval(o["cells"])
        return m
    def CheckPosInBound(self, pos: Grid2D):
        return self.left <= pos.x <= self.right and self.down <= pos.y <= self.up
    def GetTerrain(self, pos: Grid2D):
        if not self.CheckPosInBound(pos):
            return None
        return self.terrian[pos.y].get(pos.x)
    def GetCell(self, pos: Grid2D):
        if not self.CheckPosInBound(pos):
            return None
        return self.cells[pos.y].get(pos.x)

class Cell:
    def Encode(self) -> str:
        return "Cell()"
class Terrian(IntEnum):
    Wall = auto()

