from typing import *
from datetime import timedelta, datetime
from math import ceil
from collections import Counter
import itertools, random
from .Game import Game
from .Card import Card
from .User import User
from .Status import Status, StatusNumed, StatusTimed, StatusNullStack, StatusDailyStack
from .Attack import Attack, AttackType
from .Priority import UserEvt, Priority
from .Types import Pack
from .Dragon import DragonState, Tree
from .Mission import Mission
from .EventListener import IEventListener
from .Helper import positive
from ... import config
log = config.logger.dragon

class CMindgap150(Card):
    id = 150
    name = "小心空隙"
    _description = "今天接龙时有20%几率被神隐，被神隐的词消失，接龙人需再等待两个词才可接龙。"
    positive = 0
    pack = Pack.misc
    async def Use(self, user: 'User') -> None:
        await user.ume.AddStatus(SMindgap150())
class SMindgap150(StatusDailyStack):
    id = 150
    name = "小心空隙"
    _description = "今天接龙时有20%几率被神隐，被神隐的词消失，接龙人需再等待两个词才可接龙。"
    isGlobal = True
    async def OnDragoned(self, user: 'User', branch: 'Tree', first10: bool) -> None:
        if random.random() < 0.3:
            l = [s for s in user.CheckStatus(SNoDragon) if s.length == 3] #TODO
            if len(l)==0:
                await user.AddStatus(SNoDragon([branch.parent.id_str], 3))
            else:
                l[0].list.append(branch.parent.id_str)
            user.data.SaveStatuses()
            if not user.state.get('branch_removed'):
                user.state['branch_removed'] = True
                user.game.RemoveTree(branch)
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnDragoned: Priority.OnDragoned.mindgap}

class CSteamSummer151(Card):
    name = "Steam夏季特卖"
    id = 151
    positive = 1
    _description = "你下一次购物花费减少50%。"
    pack = Pack.misc
    async def Use(self, user: 'User') -> None:
        await user.AddStatus(SSteamSummer151())
class SSteamSummer151(StatusNullStack):
    name = "Steam夏季特卖"
    id = 151
    _description = "你下一次购物花费减少50%。"
    async def CheckJibiSpend(self, user: 'User', jibi: int) -> int:
        return jibi // 2 ** self.count
    async def OnJibiChange(self, user: 'User', jibi: int, isBuy: bool) -> int:
        if isBuy:
            await user.RemoveAllStatuses(self)
            return jibi // 2 ** self.count
        return jibi
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.CheckJibiSpend: Priority.CheckJibiSpend.steamsummer,
            UserEvt.OnJibiChange: Priority.OnJibiChange.steamsummer}

class CForkbomb152(Card):
    name = "Fork Bomb"
    id = 152
    positive = 0
    _description = "今天每个接龙词都有5%几率变成分叉点。"
    isMetallic = True
    mass = 0.2
    pack = Pack.misc
    async def Use(self, user: 'User') -> None:
        await user.ume.AddStatus(SForkbomb152())
class SForkbomb152(StatusDailyStack):
    id = 'b'
    _description = "Fork Bomb：今天每个接龙词都有5%几率变成分叉点。"
    isGlobal = True
    isMetallic = True
    async def OnDragoned(self, user: 'User', branch: 'Tree', first10: bool) -> None:
        if (c := random.random()) > (0.95 - 0.005 * user.data.luck) ** self.count:
            lucky = False
            if c < 0.95 ** self.count:
                lucky = True
            user.SendStatusEffect(self, lucky = lucky)
            branch.fork = True
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnDragoned: Priority.OnDragoned.forkbomb}

class CBeijingCard153(Card):
    name = "北京市市政交通一卡通"
    id = 153
    positive = 1
    _description = "持有此卡时，你当天在商店总消费达100击毙后商店所有物品变为8折，当天在商店总消费达150击毙后商店所有物品变为5折，当天在商店总消费达400击毙后不再打折。"
    # hold_des = "北京市市政交通一卡通：你当天在商店总消费达100击毙后商店所有物品变为8折，当天在商店总消费达150击毙后商店所有物品变为5折，当天在商店总消费达400击毙后不再打折。"
    pack = Pack.misc
    async def CheckJibiSpend(self, user: 'User', jibi: int) -> int:
        if 100 <= user.data.spendShop < 150:
            jibi = int(jibi * 0.8 ** self.count)
        elif 150 <= user.data.spendShop < 400:
            jibi = int(jibi * 0.5 ** self.count)
        return jibi
    async def OnJibiChange(self, user: 'User', jibi: int, isBuy: bool) -> int:
        if jibi < 0 and is_buy:
            flag = '0'
            if 100 <= user.data.spendShop < 150:
                jibi = int(jibi * 0.8 ** self.count)
                flag = '8'
            elif 150 <= user.data.spendShop < 400:
                jibi = int(jibi * 0.5 ** self.count)
                flag = '5'
            elif user.data.spendShop >= 400:
                flag = '400'
            user.SendCardEffect(self, jibi = jibi, flag = flag)
        return jibi
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnJibiChange: Priority.OnJibiChange.beijingcard,
            UserEvt.CheckJibiSpend: Priority.CheckJibiSpend.beijingcard}

class CTimebomb154(Card):
    name = "定时炸弹"
    id = 154
    positive = -1
    _description = "抽到时附加buff：需要此后在今日内完成10次接龙，否则在跨日时扣除2*剩余次数的击毙。"
    consumedOnDraw = True
    isMetallic = True
    pack = Pack.misc
    async def Use(self, user: 'User') -> None:
        await user.ume.AddStatus(STimebomb154(10))
class STimebomb154(StatusNumed):
    name = "定时炸弹"
    id = 154
    _description = "需要此后在今日内完成10次接龙，否则在跨日时扣除2*剩余次数的击毙。"
    isDebuff = True
    isMetallic = True
    async def OnDragoned(self, user: 'User', branch: 'Tree', first10: bool) -> None:
        self.num -= 1
        user.data.SaveStatuses()
    async def OnNewDay(self, user: 'User') -> None:
        b = 2 * self.num
        user.SendStatusEffect(self, jibi = b)
        await user.AddJibi(-b)
        self.num = 0
        user.data.SaveStatuses()
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnDragoned: Priority.OnDragoned.timebomb,
            UserEvt.OnNewDay: Priority.OnNewDay.timebomb}

class CCashPrinter155(Card):
    name = "印钞机"
    id = 155
    positive = 1
    _description = "使用后，你接下来10次接龙时会奖励接了上一个词的人1击毙。如果上一个词是起始词则不消耗生效次数。"
    isMetallic = True
    mass = 0.25
    pack = Pack.misc
    async def Use(self, user: 'User') -> None:
        await user.ume.AddStatus(SCashPrinter155(10))
class SCashPrinter155(StatusNumed):
    name = "印钞机"
    id = 155
    _description = "你接下来接龙时会奖励接了上一个词的人1击毙。如果上一个词是起始词则不消耗生效次数。"
    isMetallic = True
    async def OnDragoned(self, user: 'User', branch: 'Tree', first10: bool) -> None:
        pq = branch.parent.qq
        if pq != user.game.managerQQ and pq != 0:
            user.SendStatusEffect(self, success = True)
            await user.CreateUser(pq).AddJibi(1)
            self.num -= 1
            user.data.SaveStatuses()
        else:
            user.SendStatusEffect(self, success = False)
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnDragoned: Priority.OnDragoned.cashprinter}
class SInvCashPrinter156(StatusNumed):
    name = "反转·印钞机"
    id = 156
    _description = "你接下来接龙时会扣除接了上一个词的人1击毙。如果上一个词是起始词则不消耗生效次数。"
    isMetallic = True
    async def OnDragoned(self, user: 'User', branch: 'Tree', first10: bool) -> None:
        pq = branch.parent.qq
        if pq != user.game.managerQQ and pq != 0:
            user.SendStatusEffect(self, success = True)
            await user.CreateUser(pq).AddJibi(-1)
            self.num -= 1
            user.data.SaveStatuses()
        else:
            user.SendStatusEffect(self, success = False)
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnDragoned: Priority.OnDragoned.inv_cashprinter}

class CUpsideDown156(Card):
    name = "天下翻覆"
    id = 156
    positive = 0
    _description = "每条全局状态和你的状态有50%的概率反转，除了那些不能反转的以外。"
    weight = 5
    pack = Pack.misc
    async def Use(self, user: 'User') -> None:
        pass
