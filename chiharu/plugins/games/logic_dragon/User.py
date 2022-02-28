from typing import *
from .UserData import UserData
from .Helper import Session
if TYPE_CHECKING:
    from .Game import Game

class User:
    def __init__(self, ud: UserData, buf: Session, game: 'Game') -> None:
        self.qq = ud.qq
        self.data = ud
        self.buf = buf
        self.game = game
    def __del__(self):
        self.data.DecreaseRef()
    def CreateUser(self, qq):
        return self.game.CreateUser(qq, self.buf)
    @property
    def me(self):
        return self.game.me
    @property
    def ume(self):
        return User(self.game.me, self.buf, self.game)