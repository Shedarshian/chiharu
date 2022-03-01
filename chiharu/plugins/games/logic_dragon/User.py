from functools import singledispatchmethod
from typing import *
from datetime import datetime, timedelta
from .UserData import UserData
from .Helper import ProtocolData, Session
from .Card import Card
from .Status import Status
from .Equipment import Equipment
from .EventListener import IEventListener
from .Priority import UserEvt, Priority, exchange
from .Types import TEvent
from .Attack import Attack, AttackType
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
    @property
    def log(self):
        return self.data.log
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
        self.data.SaveStatuses()
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
            self.data.SaveStatuses()
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
            self.data.SaveStatuses()
            return True
    async def RemoveAllStatus(self, id: int):
        l = self.CheckStatus(id)
        for s in l:
            await self.RemoveStatus(s)
    async def AddJibi(self, jibi: int, /, isBuy: bool=False):
        if jibi == 0:
            return True
        current_jibi = self.data.jibi
        if isBuy and jibi < 0:
            jibi = -jibi
            # Event CheckJibiSpend
            for eln in self.IterAllEvent(UserEvt.CheckJibiSpend):
                jibi = await eln.CheckJibiSpend(self, jibi)
            if current_jibi < jibi:
                return False
            jibi = -jibi
        # Event OnJibiChange
        for eln in self.IterAllEvent(UserEvt.OnJibiChange):
            jibi = await eln.OnJibiChange(self, jibi, isBuy)
            if jibi == 0:
                break
        self.data.jibi = max(self.data.jibi + jibi, 0)
        if isBuy and jibi < 0:
            self.data.spendShop -= jibi
        return True
    async def AddEventPt(self, eventPt: int, /, isBuy: bool=False):
        if eventPt == 0:
            return True
        currentEventPt = self.data.eventPt
        if isBuy and eventPt < 0:
            eventPt = -eventPt
            # Event CheckEventPtSpend
            for eln in self.IterAllEvent(UserEvt.CheckEventptSpend):
                eventPt = await eln.CheckEventptSpend(self, eventPt)
            if currentEventPt < eventPt:
                return False
            eventPt = -eventPt
        # Event OnEventPtChange
        for eln in self.IterAllEvent(UserEvt.OnEventptChange):
            eventPt = await eln.OnEventptChange(self, eventPt, isBuy)
            if eventPt == 0:
                break
        self.data.eventPt = max(self.data.eventPt + eventPt, 0)
        return True
    async def Death(self, minute: int=120, killer: 'User'=None, c: AttackType=None):
        dodge = False
        if c is None:
            c = AttackType()
        # Event OnDeath
        for eln in self.IterAllEvent(UserEvt.OnDeath):
            minute, dodge = await eln.OnDeath(self, killer, minute, c)
            minute = int(minute)
            if dodge:
                break
        else:
            from .AllCards import SDeath
            await self.AddStatus(SDeath(timedelta(minutes=minute)))
    async def Attacked(self, atk: 'Attack'):
        dodge = False
        # Event OnAttack
        for eln in atk.attacker.IterAllEvent(UserEvt.OnAttack):
            dodge = await eln.OnAttack(atk.attacker, atk)
            if dodge:
                return
        # Event OnAttacked
        for eln in self.IterAllEvent(UserEvt.OnAttacked):
            dodge = await eln.OnAttacked(self, atk)
            if dodge:
                return
        await atk.action()
    async def Killed(self, killer: 'User', minute: int=120):
        from .AllCards import AKill
        attack = AKill(killer, self, minute)
        await self.Attacked(attack)
    async def DrawCardEffect(self, card: Card):
        if card.consumedOnDraw:
            # Event BeforeCardUse
            for eln in self.IterAllEvent(UserEvt.BeforeCardUse):
                block = await eln.BeforeCardUse(self, card)
                if block is not None:
                    await block
                    return
        await card.OnDraw(self)
    async def UseCardEffect(self, card: Card):
        if not card.consumedOnDraw:
            # Event BeforeCardUse
            for eln in self.IterAllEvent(UserEvt.BeforeCardUse):
                block = await eln.BeforeCardUse(self, card)
                if block is not None:
                    await block
                    return
        await card.Use(self)
        # Event AfterCardUse
        for eln in self.IterAllEvent(UserEvt.AfterCardUse):
            await eln.AfterCardUse(self, card)
    async def DrawAndUse(self, card: Card=None, /, requirement: Callable=None):
        if card is None:
            # Event BeforeCardDraw
            for eln in self.IterAllEvent(UserEvt.BeforeCardDraw):
                ret = await eln.BeforeCardDraw(self, 1, requirement)
                if ret is not None:
                    cards = ret
                    break
            else:
                cards = Card.RandomNewCards(self, 1, requirement)
        else:
            cards = [card]
        for c in cards:
            await self.DrawCardEffect(c)
            await self.UseCardEffect(c)
            # if c.id not in global_state['used_cards']:
            #     global_state['used_cards'].append(c.id)
            #     save_global_state()
            await c.OnRemove(self)
    async def Draw(self, /, num: int=0, cards: List[Card]=None, requirement: Callable=None):
        # if self.active and self.buf.state.get('exceed_limit'): TODO
        #     self.send_log(f"因手牌超出上限，不可摸牌{句尾}")
        #     return False
        if cards is None:
            # Event BeforeCardDraw
            for eln in self.IterAllEvent(UserEvt.BeforeCardDraw):
                ret = await eln.BeforeCardDraw(self, num, requirement)
                if ret is not None:
                    cards = ret
                    break
            else:
                cards = Card.RandomNewCards(self, num, requirement)
        # elif Card(-65537) in cards: TODO
        #     if self.qq in global_state["supernova_user"][0] + global_state["supernova_user"][1] + global_state["supernova_user"][2]:
        #         cards.remove(Card(-65537))
        #         if len(cards) == 0:
        #             return False
        #     else:
        #         global_state["supernova_user"][0].append(self.qq)
        for c in cards:
            if not c.consumedOnDraw:
                self.data.AddCard(c)
            await self.DrawCardEffect(c)
        # Event AfterCardDraw
        for eln in self.IterAllEvent(UserEvt.AfterCardDraw):
            await eln.AfterCardDraw(self, cards)
        self.data.SaveCards()
        return True
    async def UseCard(self, card: Card):
        self.data.RemoveCard(card)
        await self.UseCardEffect(card)
        await card.OnRemove(self)
        self.data.SaveCards()
    async def RemoveCards(self, cards: List[Card]):
        for card in cards:
            self.data.RemoveCard(card)
        for card in cards:
            await card.OnRemove(self)
        # Event AfterCardRemove
        for eln in self.IterAllEvent(UserEvt.AfterCardRemove):
            await eln.AfterCardRemove(self, cards)
        self.data.SaveCards()
    async def DiscardCards(self, cards: List[Card]):
        for card in cards:
            self.data.RemoveCard(card)
        for card in cards:
            await card.OnDiscard(self)
        # Event AfterCardDiscard
        for eln in self.IterAllEvent(UserEvt.AfterCardDiscard):
            await eln.AfterCardDiscard(self, cards)
        self.data.SaveCards()
    async def UseEquipment(self, eq: Equipment):
        await eq.use(self)
    

    