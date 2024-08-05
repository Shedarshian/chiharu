from typing import TypeVar, Generic, TypeAlias
from .maj import MajHai, FuuRo, HaiHoStatus, PlayerPos, MajZjHai

H = TypeVar("H", bound=MajHai)

class Player(Generic[H]):
    hai: type[H]
    def __init_subclass__(cls, hai: type[H], **kwargs):
        super().__init_subclass__(**kwargs)
        cls.hai = hai
    def __init__(self, board: "Board[H]", pos: PlayerPos) -> None:
        self.board = board
        self.pos = pos
        self.tehai: list[H] = []
        self.fuuro: list[FuuRo] = []
        self.ho: list[tuple[H, HaiHoStatus]] = []
        self.ten: dict[int, list[dict[int, tuple[tuple[int, ...], ...]]]] = {}
        self.tensu: int = 0
    TDoable: TypeAlias = tuple[str,...]
    doable_dahai: TDoable = ('kiri', 'ankan', 'kakan', 'tsumo')
    doable_naku_shang: TDoable = ('qi', 'pon', 'daiminkan', 'ron')
    doable_naku_all: TDoable = ('pon', 'daiminkan', 'ron')
    doable_kakan: TDoable = ('ron',)
    doable_ankan: TDoable = ()

class Board(Generic[H]):
    player_type: type[H]
    def __init_subclass__(cls, player: type[Player], **kwargs):
        super().__init_subclass__(**kwargs)
        cls.player_type = player
    def __init__(self) -> None:
        self.players: list[Player[H]] = [Player(self, PlayerPos(i)) for i in range(4)]

class ZjPlayer(Player[MajZjHai], hai=MajZjHai):
    def __init__(self, board: Board[MajZjHai], pos: PlayerPos) -> None:
        super().__init__(board, pos)

class ZjBoard(Board[MajZjHai], player=ZjPlayer):
    def __init__(self) -> None:
        super().__init__()