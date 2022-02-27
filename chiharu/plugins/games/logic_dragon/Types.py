from typing import *
from dataclasses import dataclass
if TYPE_CHECKING:
    from .EventListener import IEventListener

TEventListener = TypeVar('TEventListener', bound='IEventListener')
TEvent = dict[int, TEventListener]

async def nothing(): return False
@dataclass
class TCounter:
    pierce: Callable = nothing
    jump: bool = False
    hpzero: bool = False