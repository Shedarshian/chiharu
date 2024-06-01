from typing import TypeVar, Generic
from .maj import MajHai, FuuRo, HaiHoStatus

H = TypeVar("H", bound=MajHai)

class Player(Generic[H]):
    hai: type[H]
    def __init_subclass__(cls, hai: type[H], **kwargs):
        super().__init_subclass__(**kwargs)
        cls.hai = hai
    def __init__(self, board: "Board[H]", pos: int) -> None:
        self.board = board
        self.pos = pos
        self.tehai: list[H] = []
        self.fuuro: list[FuuRo] = []
        # self.ho: list[tuple[H, HaiHoStatus]] = []
        self.ten: dict[int, list[dict[int, tuple[tuple[int, ...], ...]]]] = {}
        self.tensu: int = 0
        

class Board(Generic[H]):
    def __init__(self) -> None:
        self.players: list[Player[H]] = []