from functools import singledispatchmethod
from typing import *
from .UserData import UserData
from .Helper import ProtocolData, Session
from .Card import Card
from .Status import Status
from .Equipment import Equipment
from .EventListener import IEventListener
from .Priority import UserEvt, Priority, exchange
from .Types import TEvent
if TYPE_CHECKING:
    from .Game import Game

class User:
    def __init__(self, ud: UserData, buf: Session, game: 'Game') -> None:
        self.qq = ud.qq
        self.data = ud
        self.buf = buf
        self.game = game
        self.state: dict[str, Any] = {}
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
    @property
    def active(self):
        return self.buf.qq == self.qq
    def IterAllEvent(self, evt: UserEvt, /, no_global: bool=False, extra_listeners: List[TEvent]=None):
        user_lists = [self.data.eventListener[evt]]
        if extra_listeners is not None:
            user_lists += extra_listeners
        if not no_global:
            user_lists.append(self.me.eventListener[evt])
        for p in exchange[evt]:
            for e in user_lists:
                ret = e.get(p)
                if ret is not None:
                    for eln in ret:
                        yield eln
    def Send(self, data: ProtocolData):
        self.buf.addData(data)
    
    def CheckStatus(self, id: int):
        return self.data.CheckStatus(id)
    def CheckStatusStack(self, id: int):
        return self.data.CheckStatusStack(id)

    async def choose(self, flush: bool):
        if not self.active:
            self.Send({"type": "choose_failed"})
            return False
        elif flush:
            await self.buf.flush()
        return True
    async def AddStatus(self, s: Status):
        # Event OnStatusAdd
        for eln in self.IterAllEvent(UserEvt.OnStatusAdd):
            dodge = await eln.OnStatusAdd(self, s)
            if dodge:
                return False
        if s.isNull and len(l := self.CheckStatus(s.id)) != 0:
            l[0].num += s.count
        else:
            self.data.statusesUnchecked.append(s)
            self.data.registerStatus(s)
        if s.isGlobal:
            pass
            #global_state['global_status'].extend([[0, s]] * count)
            #save_global_state()
        return True
    async def RemoveStatus(self, s: Union[Status, int], count: int=1):
        """If s is a Status, remove an object status. s need to be in the status of this user.
        If s is a int, remove a certain amount of count of a nullstack status."""
        if isinstance(s, Status):
            # Event OnStatusRemove
            for eln in self.IterAllEvent(UserEvt.OnStatusRemove):
                dodge = await eln.OnStatusRemove(self, s)
                if dodge:
                    return False
            self.data.statusesUnchecked.remove(s)
            self.data.deregisterStatus(s)
            return True
        elif isinstance(s, int):
            status = Status.get(s)(count)
            # Event OnStatusRemove
            for eln in self.IterAllEvent(UserEvt.OnStatusRemove):
                dodge = await eln.OnStatusRemove(self, status)
                if dodge:
                    return False
            l = self.CheckStatus(s)
            if len(l) == 0:
                return False
            l[0].num -= count
    async def RemoveAllStatus(self, id: int):
        l = self.CheckStatus(id)
        for s in l:
            await self.RemoveStatus(s)


