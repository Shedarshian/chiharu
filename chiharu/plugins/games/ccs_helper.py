from typing import Callable, Sequence, TypeVar, Generator, Any
from enum import Enum, auto
from abc import ABC
from dataclasses import dataclass
from .carcassonne_asset.readTile import Dir

class CantPutError(Exception):
    pass
class NoDeckEnd(Exception):
    pass
class Connectable(Enum):
    City = auto()
    Field = auto()
    Road = auto()
    River = auto()
    @classmethod
    def fromChar(cls, char: str):
        return {"C": Connectable.City, "F": Connectable.Field, "R": Connectable.Road, "S": Connectable.River}[char]
class TileAddable(Enum):
    No = auto()
    Volcano = auto()
    Dragon = auto()
    Portal = auto()
    Gold = auto()
    Gingerbread = auto()
    Festival = auto()
    Hill = auto()
    Vineyard = auto()
    MageWitch = auto()
    Rake = auto()
    Club = auto()
    Shield = auto()
class Addable(Enum):
    No = auto()
    Cathedral = auto()
    Inn = auto()
    Wine = auto()
    Grain = auto()
    Cloth = auto()
    Princess = auto()
    Pigherd = auto()
class Shed(Enum):
    No = auto()
    Farmhouse = auto()
    Cowshed = auto()
    Donkey = auto()
    Pigsty = auto()
    Watertower = auto()
    Highwaymen = auto()
all_extensions = {1: 'abcd', 2: 'abcd', 3: 'abcde', 4: 'ab', 5: 'abcde', 6: 'abcdefgh', 7: 'abcd', 9: 'abcde', 12: 'abcdef', 13: 'abcdefghijk', 14: 'abcdefg'}

T = TypeVar('T')
def findAllMax(items: Sequence[T], key: Callable[[T], int], criteria=None) -> tuple[int, list[T]]:
    maxScore: int = -99
    maxPlayer: list[T] = []
    for player in items:
        if criteria is not None and not criteria(player):
            continue
        if (score := key(player)) > maxScore:
            maxScore = score
            maxPlayer = [player]
        elif score == maxScore:
            maxPlayer.append(player)
    return maxScore, maxPlayer

def turn(pos: tuple[int, int], dir: Dir):
    if dir == Dir.UP:
        return pos
    if dir == Dir.RIGHT:
        return 64 - pos[1], pos[0]
    if dir == Dir.DOWN:
        return 64 - pos[0], 64 - pos[1]
    return pos[1], 64 - pos[0]
def dist2(pos1: tuple[int, int], pos2: tuple[int, int]) -> float:
    return (pos1[0] - pos2[0]) ** 2 + (pos1[1] - pos2[1]) ** 2

class State(Enum):
    End = auto()
    PuttingTile = auto()
    ChoosingPos = auto()
    PuttingFollower = auto()
    ChoosingSegment = auto()
    WagonAsking = auto()
    AbbeyAsking = auto()
    FinalAbbeyAsking = auto()
    MovingDragon = auto()
    ChoosingOwnFollower = auto()
    PrincessAsking = auto()
    CaptureTower = auto()
    ExchangingPrisoner = auto()
    AskingSynod = auto()
    ChoosingTileFigure = auto()
    ChoosingShepherd = auto()
    ChoosingScoreMove = auto()
    ChoosingMessenger = auto()
    ChoosingCropCircle = auto()
    ChoosingAddCropCircle = auto()
    CropAddFollower = auto()
    Error = auto()
@dataclass
class Send(ABC):
    last_err: int
@dataclass
class Recieve(ABC):
    pass
@dataclass
class SendBegin(Send):
    begin: bool
    second_turn: bool
@dataclass
class SendPos(Send):
    pos: tuple[int, int]
@dataclass
class RecievePos(Recieve):
    pos: tuple[int, int]
@dataclass
class RecieveReturn(Recieve):
    pass
@dataclass
class RecieveId(Recieve):
    id: int
@dataclass
class RecieveDir(Recieve):
    dir: Dir

@dataclass
class SendPuttingTile(SendBegin):
    gifted: bool
@dataclass
class RecievePuttingTile(RecievePos):
    orient: Dir
    tilenum: int
@dataclass
class RecieveBuyPrisoner(Recieve):
    player_id: int
    follower: str
@dataclass
class SendChoosingPos(Send):
    special: str = ''
@dataclass
class SendPuttingFollower(Send):
    last_put: tuple[int, int]
    portaled: bool
    rangered: bool
    special: str = ''
@dataclass
class RecievePuttingFollower(RecieveId):
    which: str
    phantom: int
    special: str = ''
    pos: tuple[int, int] = (0, 0)
@dataclass
class SendMovingWagon(SendPos):
    player_id: int
@dataclass
class RecieveWagon(RecievePos):
    seg: int
@dataclass
class SendAbbeyAsking(SendBegin):
    pass
@dataclass
class SendInt(Send):
    num: int
@dataclass
class SendPosSpecial(SendPos):
    special: str = ''
@dataclass
class SendPrincess(Send):
    object: Any
@dataclass
class RecieveWhich(Recieve):
    which: str
@dataclass
class RecievePosWhich(RecievePos):
    which: str
@dataclass
class RecieveChoose(Recieve):
    chosen: bool

@dataclass
class Log(ABC):
    pass
@dataclass
class LogScore(Log):
    player_name: str
    source: str
    num: int
@dataclass
class LogRedraw(Log):
    pass
@dataclass
class LogPutBackBuilder(Log):
    player_name: str
    meeple_name: str
@dataclass
class LogExchangePrisoner(Log):
    player2_name: str
    player1_name: str
@dataclass
class LogTradeCounter(Log):
    trade: list[int]
@dataclass
class LogChallengeFailed(Log):
    name: str
@dataclass
class LogDrawGift(Log):
    gift_name: str
    gifts_text: str
@dataclass
class LogUseGift(Log):
    gift_name: str
    gifts_text: str
@dataclass
class LogTake2NoTile(Log):
    pass
@dataclass
class LogDice(Log):
    result: int
@dataclass
class LogDragonMove(Log):
    player_name: str
    dir: Dir
@dataclass
class LogShepherd(Log):
    player_name: str
    sheep: int
@dataclass
class LogCircus(Log):
    animal: int

