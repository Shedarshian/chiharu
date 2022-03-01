from typing import *
from dataclasses import dataclass
from enum import Enum
if TYPE_CHECKING:
    from .EventListener import IEventListener

TEventListener = TypeVar('TEventListener', bound='IEventListener')
TEvent = dict[int, list[TEventListener]]

class TUserData(TypedDict):
    qq: int
    jibi: int
    card: str
    status: str
    equipment: str
    card_limit: int
    event_pt: int
    event_stage: int
    event_skill: int
    dead: int
    flags: int
    assembling: int
    hp: int
    mp: int
    maj_quan: int