from abc import ABC
from dataclasses import dataclass
from typing import Generator, TypeVar

@dataclass
class Send:
    last_err: int
@dataclass
class Recieve:
    pass

T = TypeVar('T')
TAsync = Generator[Send, Recieve, T]