from typing import *
from datetime import datetime, timedelta
import functools

from chiharu.plugins.games.logic_dragon_file import TEventListener
from .UserData import UserData
from .Helper import ProtocolData, Buffer
from .Card import Card
from .Status import Status, TStatus, TStatusStack
from .Equipment import Equipment
from .EventListener import IEventListener
from .Priority import UserEvt, Priority, exchange
from .Types import TEvent
from .Attack import Attack, AttackType
from .Item import Item
if TYPE_CHECKING:
    from .Game import Game

class User:
    def __init__(self, ud: UserData, buf: Buffer, game: 'Game') -> None:
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
    def dragon(self):
        return self.CreateUser(self.game.dragonQQ)
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
                ret: list[TEventListener] | None = e.get(p)
                if ret is not None:
                    for eln in ret:
                        yield eln
    def Send(self, __data: ProtocolData=None, /, **kwargs):
        __data = __data or {}
        data = {"qq": self.qq, **__data, **kwargs}
        self.buf.AddData(data)
    def SendStatusEffect(self, status: Status, /, **kwargs):
        self.Send(type="status_effect", status=status.DumpData(), **kwargs)
    def SendCardEffect(self, card: Card, /, **kwargs):
        self.Send(type="card_effect", card=card.DumpData(), **kwargs)
    def SendCardUse(self, card: Card, /, **kwargs):
        self.Send(type="card_use", card=card.DumpData(), **kwargs)
    def SendCardOnDraw(self, card: Card, /, **kwargs):
        self.Send(type="card_on_draw", card=card.DumpData(), **kwargs)
    
    def CheckStatus(self, cls: Type[TStatus]):
        return self.data.CheckStatus(cls)
    def CheckStatusStack(self, cls: Type[TStatusStack]):
        return self.data.CheckStatusStack(cls)

    async def choose(self, flush: bool):
        if not self.active:
            self.Send(type="choose_failed", reason="not_active")
            return False
        elif flush:
            await self.buf.Flush()
        return True
    async def AddStatus(self, s: TStatus):
        """添加状态。"""
        dodge = False
        # Event OnStatusAdd
        self.Send(type="begin", name="OnStatusAdd")
        for eln in self.IterAllEvent(UserEvt.OnStatusAdd):
            dodge = await eln.OnStatusAdd(self, s)
            if dodge:
                break
        self.Send(type="OnStatusAdd", status=s.DumpData(), dodge=dodge)
        if dodge:
            return False
        if s.isNull and len(l := self.CheckStatus(type(s))) != 0:
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
    @functools.singledispatchmethod
    async def RemoveStatus(self, s: TStatus, /, remover: 'User' | None=None):
        """移除一个状态。
        如果s是一个状态对象，则移除该对象。该对象需在用户的状态里。
        如果s是状态类型，则移除count层对应id的可堆叠状态。"""
        dodge = False
        # Event OnStatusRemove
        self.Send(type="begin", name="OnStatusRemove")
        for eln in self.IterAllEvent(UserEvt.OnStatusRemove):
            dodge = await eln.OnStatusRemove(self, s, remover=remover)
            if dodge:
                break
        self.Send(type="OnStatusRemove", status=s.DumpData(), dodge=dodge)
        if dodge:
            return False
        self.data.statusesUnchecked.remove(s)
        self.data.deregisterStatus(s)
        self.data.SaveStatuses()
        return True
    @RemoveStatus.register
    async def _(self, s: Type[TStatusStack], count: int=1, /, remover: 'User' | None=None):
        status = s(count)
        dodge = False
        # Event OnStatusRemove
        self.Send(type="begin", name="OnStatusRemove")
        for eln in self.IterAllEvent(UserEvt.OnStatusRemove):
            dodge = await eln.OnStatusRemove(self, status, remover=remover)
            if dodge:
                break
        self.Send(type="OnStatusRemove", status=status.DumpData(), dodge=dodge)
        if dodge:
            return False
        l = self.CheckStatus(s)
        if len(l) == 0:
            return False
        l[0].num -= count
        self.data.SaveStatuses()
        return True
    async def RemoveAllStatus(self, status: Type[TStatus], /, remover: 'User' | None=None):
        """移除全部该id的状态。"""
        l = self.CheckStatus(status)
        for s in l:
            await self.RemoveStatus(s, remover=remover)
    async def AddJibi(self, jibi: int, /, isBuy: bool=False) -> ProtocolData:
        """获取或损失击毙。
        isBuy：是否是购买。"""
        if jibi == 0:
            return {"type": "succeed"}
        current_jibi = self.data.jibi
        if isBuy and jibi < 0:
            jibi = -jibi
            # Event CheckJibiSpend
            self.Send(type="begin", name="CheckJibiSpend")
            for eln in self.IterAllEvent(UserEvt.CheckJibiSpend):
                jibi = await eln.CheckJibiSpend(self, jibi)
            if current_jibi < jibi:
                return {"type": "failed", "error_code": 410}
            self.Send(type="end", name="CheckJibiSpend")
            jibi = -jibi
        
        # Event OnJibiChange
        self.Send(type="begin", name="OnJibiChange")
        for eln in self.IterAllEvent(UserEvt.OnJibiChange):
            jibi = await eln.OnJibiChange(self, jibi, isBuy)
            if jibi == 0:
                break
        self.data.jibi = max(self.data.jibi + jibi, 0)
        self.Send(type="OnJibiChange", jibi_change=jibi, current_jibi=self.data.jibi, is_buy=isBuy)
        if isBuy and jibi < 0:
            self.data.spendShop -= jibi
        return {"type": "succeed"}
    async def AddEventPt(self, eventPt: int, /, isBuy: bool=False) -> ProtocolData:
        """获取或损失活动pt。
        isBuy：是否是购买。"""
        if eventPt == 0:
            return {"type": "succeed"}
        currentEventPt = self.data.eventPt
        if isBuy and eventPt < 0:
            eventPt = -eventPt
            # Event CheckEventPtSpend
            self.Send(type="begin", name="CheckEventPtSpend")
            for eln in self.IterAllEvent(UserEvt.CheckEventptSpend):
                eventPt = await eln.CheckEventptSpend(self, eventPt)
            if currentEventPt < eventPt:
                return {"type": "failed", "error_code": 411}
            self.Send(type="end", name="CheckEventPtSpend")
            eventPt = -eventPt
        
        # Event OnEventPtChange
        self.Send(type="begin", name="OnEventPtChange")
        for eln in self.IterAllEvent(UserEvt.OnEventptChange):
            eventPt = await eln.OnEventptChange(self, eventPt, isBuy)
            if eventPt == 0:
                break
        self.data.eventPt = max(self.data.eventPt + eventPt, 0)
        self.Send(type="OnEventPtChange", eventpt_change=eventPt, current_eventpt=self.data.eventPt,
                is_buy=isBuy)
        return {"type": "succeed"}
    async def Death(self, minute: int=120, killer: Optional['User']=None, c: AttackType=None):
        """玩家死亡。可以没有击杀者。"""
        dodge = False
        if c is None:
            c = AttackType()
        # Event OnDeath
        self.Send(type="begin", name="OnDeath")
        for eln in self.IterAllEvent(UserEvt.OnDeath):
            minute, dodge = await eln.OnDeath(self, killer, minute, c)
            minute = int(minute)
            if dodge:
                break
        self.Send(type="OnDeath", killer=-1 if killer is None else killer.qq, time=minute, dodge=dodge)
        if dodge:
            return
        from .AllCards0 import SDeathN1
        await self.AddStatus(SDeathN1(timedelta(minutes=minute)))
    async def Attacked(self, atk: 'Attack'):
        """玩家受到攻击。"""
        dodge = False
        attackerQQ = atk.attacker.qq
        # Event OnAttack
        atk.attacker.Send(type="begin", name="OnAttack")
        for eln in atk.attacker.IterAllEvent(UserEvt.OnAttack):
            dodge = await eln.OnAttack(atk.attacker, atk)
            if dodge:
                break
        atk.attacker.Send(type="end", name="OnAttack")
        self.Send(type="begin", name="OnAttacked")
        if not dodge:
            # Event OnAttacked
            for eln in self.IterAllEvent(UserEvt.OnAttacked):
                dodge = await eln.OnAttacked(self, atk)
                if dodge:
                    break
            self.Send(type="end", name="OnAttacked")
            if not dodge:
                await atk.action()
        self.Send(type="attacked", name=atk.name, dodge=dodge, attacker=attackerQQ)
    async def Killed(self, killer: 'User', minute: int=120, isAOE = False):
        """玩家被杀。算作一次攻击。"""
        from .AllCards0 import AKill0
        attack = AKill0(killer, self, minute)
        attack.counter.isAOE = isAOE
        await self.Attacked(attack)
    async def DrawCardEffect(self, card: Card):
        """结算卡牌抽取效果。"""
        if card.consumedOnDraw:
            block = None
            # Event BeforeCardUse
            self.Send(type="begin", name="BeforeCardUse")
            for eln in self.IterAllEvent(UserEvt.BeforeCardUse):
                block = await eln.BeforeCardUse(self, card)
                if block is not None:
                    await block
                    return
            self.Send(type="end", name="BeforeCardUse")
            if block is not None:
                return
        
        await card.OnDraw(self)
    async def UseCardEffect(self, card: Card):
        """结算卡牌使用效果。"""
        if not card.consumedOnDraw:
            block = None
            # Event BeforeCardUse
            self.Send(type="begin", name="BeforeCardUse")
            for eln in self.IterAllEvent(UserEvt.BeforeCardUse):
                block = await eln.BeforeCardUse(self, card)
                if block is not None:
                    await block
            self.Send(type="end", name="BeforeCardUse")
            if block is not None:
                return
        
        await card.Use(self)
        # Event AfterCardUse
        self.Send(type="begin", name="AfterCardUse")
        for eln in self.IterAllEvent(UserEvt.AfterCardUse):
            await eln.AfterCardUse(self, card)
        self.Send(type="end", name="AfterCardUse")
    async def DrawAndUse(self, card: Card=None, /, requirement: Callable=None):
        """抽即用卡牌。"""
        if card is None:
            # Event BeforeCardDraw
            self.Send(type="begin", name="BeforeCardDraw")
            for eln in self.IterAllEvent(UserEvt.BeforeCardDraw):
                ret = await eln.BeforeCardDraw(self, 1, requirement)
                if ret is not None:
                    cards = ret
                    break
            else:
                cards = self.game.RandomNewCards(self, 1, requirement)
            self.Send(type="end", name="BeforeCardDraw")
        else:
            cards = [card]
        
        self.Send(type="draw_and_use", cards=[c.DumpData() for c in cards])
        for c in cards:
            await self.DrawCardEffect(c)
            await self.UseCardEffect(c)
            # if c.id not in global_state['used_cards']:
            #     global_state['used_cards'].append(c.id)
            #     save_global_state()
            await c.OnRemove(self)
    async def Draw(self, num: int=0, /, cards: List[Card]=None, requirement: Callable=None):
        """抽取卡牌。"""
        if self.active and self.state.get('exceed_limit'):
            return {"type": "failed", "error_code": 390}

        if cards is None:
            # Event BeforeCardDraw
            self.Send(type="begin", name="BeforeCardDraw")
            for eln in self.IterAllEvent(UserEvt.BeforeCardDraw):
                ret = await eln.BeforeCardDraw(self, num, requirement)
                if ret is not None:
                    cards = ret
                    break
            else:
                cards = self.game.RandomNewCards(self, num, requirement)
            self.Send(type="end", name="BeforeCardDraw")
        # elif Card(-65537) in cards: TODO
        #     if self.qq in global_state["supernova_user"][0] + global_state["supernova_user"][1] + global_state["supernova_user"][2]:
        #         cards.remove(Card(-65537))
        #         if len(cards) == 0:
        #             return False
        #     else:
        #         global_state["supernova_user"][0].append(self.qq)
        
        self.Send(type="draw_cards", cards=[c.DumpData() for c in cards])
        for c in cards:
            if not c.consumedOnDraw:
                self.data.AddCard(c)
            await self.DrawCardEffect(c)
        
        # Event AfterCardDraw
        self.Send(type="begin", name="AfterCardDraw")
        for eln in self.IterAllEvent(UserEvt.AfterCardDraw):
            await eln.AfterCardDraw(self, cards)
        self.Send(type="end", name="AfterCardDraw")

        self.data.SaveCards()
        return True
    async def UseCard(self, card: Card):
        """使用卡牌。从手牌中移除卡牌，然后发动使用效果。"""
        self.Send(type="use_card", card=card.DumpData())
        self.data.RemoveCard(card)
        await self.UseCardEffect(card)
        await card.OnRemove(self)

        self.data.SaveCards()
    async def RemoveCards(self, cards: List[Card]):
        """烧毁卡牌，不结算弃置。"""
        self.Send(type="remove_cards", cards=[c.DumpData() for c in cards])
        for card in cards:
            self.data.RemoveCard(card)
        for card in cards:
            await card.OnRemove(self)
        
        # Event AfterCardRemove
        self.Send(type="begin", name="AfterCardRemove")
        for eln in self.IterAllEvent(UserEvt.AfterCardRemove):
            await eln.AfterCardRemove(self, cards)
        self.Send(type="end", name="AfterCardRemove")

        self.data.SaveCards()
    async def DiscardCards(self, cards: List[Card]):
        """弃置卡牌。"""
        self.Send(type="discard_cards", cards=[c.DumpData() for c in cards])
        for card in cards:
            self.data.RemoveCard(card)
        for card in cards:
            await card.OnDiscard(self)
        
        # Event AfterCardDiscard
        self.Send(type="begin", name="AfterCardDiscard")
        for eln in self.IterAllEvent(UserEvt.AfterCardDiscard):
            await eln.AfterCardDiscard(self, cards)
        self.Send(type="end", name="AfterCardDiscard")

        self.data.SaveCards()
    async def UseEquipment(self, eq: Equipment):
        await eq.use(self)
    async def DrawMaj(self):
        pass # TODO
    async def GiveCard(self, other: 'User', card: Card):
        """将卡牌给予另一玩家。从玩家手牌中移除，再加入另一玩家手牌。"""
        self.data.RemoveCard(card)
        other.data.AddCard(card)
        
        # Event AfterCardGive
        self.Send(type="begin", name="AfterCardGive")
        for eln in self.IterAllEvent(UserEvt.AfterCardGive):
            await eln.AfterCardGive(self, other, card)
        self.Send(type="end", name="AfterCardGive")

        self.data.SaveCards()

    async def Damaged(self, damage: int, attacker: 'User'=None, mustHit: bool=False):
        if attacker is None:
            attacker = self.dragon
        from .AllCards0 import ADamage1
        atk = ADamage1(attacker, self, damage, mustHit)
        await self.Attacked(atk)
    async def ChooseHandCards(self, min: int, max: int, requirement: Callable[[Card], bool]=(lambda *args: True),
        requireCanUse: bool=False):
        """选择手牌。args:
        min: 最少选择的卡牌数目。
        max: 最多选择的卡牌数目。
        requirement: 哪些卡牌可以选择。
        requireCanUse: 是否要求卡牌可以使用。"""
        if not await self.choose(True):
            return None
        
        def getRequest() -> ProtocolData:
            cardsCanChoose = [i for i, c in enumerate(self.data.handCard)
                if requirement(c) and (not requireCanUse or c.CanUse(self, True))]
            return {"type": "choose", "object": "hand_card", "can_choose": cardsCanChoose,
                "min": min, "max": max}
        
        def checkResponse(response: ProtocolData) -> ProtocolData:
            chosen = response.get("chosen")
            if response.get("type") != "choose" or response.get("object") != "hand_card" or not isinstance(chosen, list):
                return {"type": "response_invalid", "error_code": 0}
            if not min <= len(chosen) <= max:
                return {"type": "response_invalid", "error_code": 100}
            if not all(isinstance(i, int) and i < len(self.data.handCard) for i in chosen):
                return {"type": "response_invalid", "error_code": 110}
            return {"type": "succeed"}
        
        response = await self.GetResponse(getRequest, checkResponse)
        chosen: list[int] = response["chosen"]
        if len(chosen) == 0:
            self.Send({"type": "choose_failed", "reason": "cant_choose"})
            return None
        
        return [self.data.handCard[i] for i in chosen]
    async def ChoosePlayers(self, min: int, max: int, range: set[int] | None =None):
        if not await self.choose(True):
            return None
        def getRequest() -> ProtocolData:
            return {"type": "choose", "object": "player", "player_list": None if range is None else list(range),
                "min": min, "max": max}
        
        def checkResponse(response: ProtocolData) -> ProtocolData:
            chosen = response.get("chosen")
            if response.get("type") != "choose" or response.get("object") != "player" or not isinstance(chosen, list):
                return {"type": "response_invalid", "error_code": 0}
            if not min <= len(chosen) <= max:
                return {"type": "response_invalid", "error_code": 100}
            if not all(isinstance(i, int) and (range is None or i in range) for i in chosen):
                return {"type": "response_invalid", "error_code": 110}
            return {"type": "succeed"}
        
        response = await self.GetResponse(getRequest, checkResponse)
        chosen: list[int] = response["chosen"]
        if len(chosen) == 0:
            self.Send({"type": "choose_failed", "reason": "cant_choose"})
            return None
        
        return chosen
    async def HandleExceedDiscard(self):
        if not await self.choose(True):
            return None
        if self.state.get('exceed_limit'):
            return None
        
        idCanNotChoose = (53,)
        requirement = lambda c: c.id not in idCanNotChoose
        x = len(self.data.handCard) - self.data.cardLimit
        toDiscard = await self.ChooseHandCards(x, x, requirement)

        if toDiscard is not None:
            await self.DiscardCards([self.data.handCard[i] for i in toDiscard])
    async def DecreaseDeathTime(self, time: timedelta):
        from .AllCards0 import SDeathN1
        l = self.CheckStatus(SDeathN1)
        if len(l) == 0:
            return True
        ret = True
        for c in l:
            c.time -= time
            if c.valid():
                ret = False
        self.data.statuses
        self.data.SaveStatuses()
        return ret

    async def GetResponse(self,
            getRequest: Callable[[], ProtocolData],
            checkResponse: Callable[[ProtocolData], ProtocolData]) -> ProtocolData:
        while 1:
            request = getRequest()
            response = await self.buf.GetResponse(request)
            # 如果response给出的是查询或者不符合要求的数据则继续循环
            if response.get("type") == "check":
                ret = await self.game.UserCheckData(self, response)
                self.Send(ret)
            else:
                ret = checkResponse(response)
                if ret.get("type") == "succeed":
                    return response
