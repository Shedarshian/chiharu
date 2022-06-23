from typing import *
from datetime import timedelta, datetime
from math import ceil
from collections import Counter
import itertools, random
from .Game import Game
from .Card import Card, CardNumed
from .User import User
from .Status import Status, StatusNumed, StatusTimed, StatusNullStack, StatusDailyStack, StatusListInt
from .Attack import Attack, AttackType
from .Priority import UserEvt, Priority
from .Types import Pack
from .Dragon import DragonState, TreeLeaf
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
    async def OnDragoned(self, user: 'User', branch: 'TreeLeaf', first10: bool) -> None:
        if random.random() < 0.3:
            l = [s for s in user.CheckStatus(SNoDragon) if s.length == 3] #TODO
            if len(l) == 0:
                await user.AddStatus(SNoDragon([branch.parent.idStr], 3))
            else:
                l[0].list.append(branch.parent.idStr)
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
            await user.RemoveAllStatus(SSteamSummer151)
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
    id = 152
    name = "Fork Bomb"
    _description = "今天每个接龙词都有5%几率变成分叉点。"
    isGlobal = True
    isMetallic = True
    async def OnDragoned(self, user: 'User', branch: 'TreeLeaf', first10: bool) -> None:
        if (c := random.random()) > (0.95 - 0.005 * user.data.luck) ** self.count:
            lucky = False
            if c < 0.95 ** self.count:
                lucky = True
            user.SendStatusEffect(self, lucky = lucky)
            user.game.ForkTree(branch, True)
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnDragoned: Priority.OnDragoned.forkbomb}

class CBeijingCard153(CardNumed):
    name = "北京市市政交通一卡通"
    id = 153
    positive = 1
    _description = "持有此卡时，你当天在商店总消费达100击毙后商店所有物品变为8折，当天在商店总消费达150击毙后商店所有物品变为5折，当天在商店总消费达400击毙后不再打折。"
    pack = Pack.misc
    async def CheckJibiSpend(self, user: 'User', jibi: int) -> int:
        if 100 <= user.data.spendShop < 150:
            jibi = int(jibi * 0.8 ** self.num)
        elif 150 <= user.data.spendShop < 400:
            jibi = int(jibi * 0.5 ** self.num)
        return jibi
    async def OnJibiChange(self, user: 'User', jibi: int, isBuy: bool) -> int:
        if jibi < 0 and isBuy:
            flag = '0'
            if 100 <= user.data.spendShop < 150:
                jibi = int(jibi * 0.8 ** self.num)
                flag = '8'
            elif 150 <= user.data.spendShop < 400:
                jibi = int(jibi * 0.5 ** self.num)
                flag = '5'
            elif user.data.spendShop >= 400:
                flag = '400'
            user.SendCardEffect(self, jibi = jibi, flag = flag)
        return jibi
    async def OnNewDay(self, user: 'User') -> None:
        self.num = 0 # pylint: disable=attribute-defined-outside-init
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnJibiChange: Priority.OnJibiChange.beijingcard,
            UserEvt.CheckJibiSpend: Priority.CheckJibiSpend.beijingcard,
            UserEvt.OnNewDay: Priority.OnNewDay.beijingcard}

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
    async def OnDragoned(self, user: 'User', branch: 'TreeLeaf', first10: bool) -> None:
        self.num -= 1
        user.data.SaveStatuses()
    async def OnNewDay(self, user: 'User') -> None:
        # pylint: disable=access-member-before-definition,attribute-defined-outside-init
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
    isReversable = True
    def reverse(self):
        return (self, SInvCashPrinter156(self.count))
    async def OnDragoned(self, user: 'User', branch: 'TreeLeaf', first10: bool) -> None:
        pq = branch.parent.qq
        if pq != user.game.managerQQ and pq != 0:
            user.SendStatusEffect(self, success = True)
            await user.CreateUser(pq).AddJibi(1)
            self.num -= 1 # pylint: disable=no-member
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
    isReversable = True
    def reverse(self):
        return (self, SCashPrinter155(self.count))
    async def OnDragoned(self, user: 'User', branch: 'TreeLeaf', first10: bool) -> None:
        pq = branch.parent.qq
        if pq != user.game.managerQQ and pq != 0:
            user.SendStatusEffect(self, success = True)
            await user.CreateUser(pq).AddJibi(-1)
            self.num -= 1 # pylint: disable=no-member
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
        worklist: List[Tuple[Status | None, Status | None]] = []
        for s in user.data.statuses:
            if s.isReversable:
                if (c := s.count) > 1 and s.isNull:
                    n: int = 0
                    for i in range(c):
                        if random.random() > 0.5:
                            n += 1
                    if n > 0 and n <= s.count:
                        worklist.append(s.reverse(n))
                else:
                    if random.random() > 0.5:
                        worklist.append(s.reverse())
        for t1, t2 in worklist:
            if t1 is None:
                continue
            user.SendCardUse(self, tstatus = t1.DumpData())
            if t1.isGlobal:
                await user.ume.RemoveStatus(t1)
                if t2 is not None:
                    await user.ume.AddStatus(t2)
            else:
                await user.RemoveStatus(t1)
                if t2 is not None:
                    await user.AddStatus(t2)

class CBloom157(Card):
    id = 157
    name = "绽放"
    positive = 1
    _description = "摸13张牌，然后弃牌至max(4,手牌上限-6)张（最多为10）。（特别的，可以弃置空白卡牌）"
    pack = Pack.misc
    async def Use(self, user: 'User') -> None:
        await user.Draw(13)
        if x := len(user.data.handCard) - min(10, max(4, user.data.cardLimit - 6)) > 0:
            if not await user.choose(True):
                random.shuffle(user.data.handCard)
                user.data.SaveCards()
                await user.DiscardCards(user.data.handCard[max(4, user.data.cardLimit - 6):])
                user.SendCardUse(self, cardnum = x, cards = [c.DumpData() for c in user.data.handCard])
            else:
                user.SendCardUse(self, cardnum = x, choose = True)
                cards = await user.ChooseHandCards(x, x)
                await user.DiscardCards(cards)

class CExcalibur158(Card):
    id = 158
    name = "EX咖喱棒"
    positive = 1
    _description = "只可在胜利时使用。统治不列颠。"
    isMetallic = True
    mass = 1
    pack = Pack.misc
    def CanUse(self, user: User, copy: bool) -> bool:
        from .AllCards2 import SWin81
        return user.CheckStatusStack(SWin81) > 0
    async def use(self, user: User) -> None:
        from .AllCards2 import SWin81
        if user.CheckStatusStack(SWin81) == 0:
            user.SendCardUse(self, success = False)
        else:
            user.SendCardUse(self, success = True)
            await user.AddStatus(SBritian158([]))
class SBritian158(StatusListInt):
    id = 158
    name = "统治不列颠"
    _description = "使用塔罗牌系列牌时，若本效果不包含“魔力 - {该塔罗牌名}”，不发动该牌的原本使用效果，并为本效果增加“魔力 - {该塔罗牌名}”。当拥有所有22种“魔力 - {塔罗牌名}”时，获得装备“塔罗原典”。"
    isRemovable = False
    @property
    def valid(self):
        return True
    def description(self) -> str:
        return self._description + f"\n\t包含：{'，'.join(('“魔力 - ' + Card.get(i)().name[Card.get(i)().name.index(' - ') + 3:] + '”') for i in self.list)}。" if len(self.list) > 0 else ''
    async def BeforeCardUse(self, user: 'User', card: 'Card') -> Optional[Awaitable]:
        if card.id <= 21 and card.id >= 0:
            if card.id not in self.list:
                async def f():
                    user.SendStatusEffect(self, tid = card.id)
                    self.list.append(card.id)
                    self.list.sort()
                    user.SendStatusEffect(self, list = self.list)
                    if len(self.list) == 22:
                        await user.RemoveStatus(self)
                        b = user.data.CheckEquipment(2)
                        user.SendStatusEffect(self, tstar = b)
                        # user.data.equipment[2] = b + 1 #TODO
                        # elif b == 6:
                        #     user.send_log(f"将装备“塔罗原典”升星至{b + 1}星{句尾}")
                        #     user.send_log("仍可继续升级，不过8星以上的塔罗原典将不会有任何额外作用。")
                        # elif b >= 7:
                        #     user.send_log(f"将装备“塔罗原典”升星至{b + 1}星（虽然没有什么作用）{句尾}")
                            # user.send_log(f"将装备“塔罗原典”升星至{b + 1}星{句尾}")
                    user.data.SaveStatuses()
                return f()
        return None
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.BeforeCardUse: Priority.BeforeCardUse.britian}

class CEnvelop160(Card):
    id = 160
    name = "信封"
    _description = "花费2击毙，选择一张手牌，将其寄给一名指定的玩家，50%概率使该玩家再获得一张信封。"
    positive = 1
    failure_message = "你的击毙不足" + 句尾
    pack = Pack.misc
    @property
    def CanUse(self, user: User, copy: bool) -> bool:
        return user.data.jibi >= 2
    async def use(self, user: User) -> None:
        if not await user.AddJibi(-2, isBuy=True):
            user.SendCardUse(self, success = False)
            return
        if await user.choose():
            async with user.ChooseHandCards(1, 1) as l:
                if (players := await user.ChoosePlayers(1, 1)) is not None:
                    u = user.CreateUser(players[0])
                    c = Card(l[0])
                    await user.RemoveCards([c])
                    a = random.random()
                    lucky = False
                    if a > 0.5 + 0.02 * min(u.data.luck, 5) + 0.02 * min(user.data.luck, 5):
                        cards = [c]
                    else:
                        if a > 0.5:
                            lucky = True
                        cards=[c, envelop]
                    user.SendCardUse(self, success = True, tqq = target.qq, cards = [c.Dumpdata() for c in cards], lucky = lucky)
                    await target.Draw(cards = cards)

class CVoiceControl161(Card):
    id = 161
    name = "声控"
    description = "摸一张指定的麻将牌，然后50%概率抽一张牌。"
    positive = 1
    pack = Pack.misc
    async def use(self, user: User) -> None:
        f"{await MajOneHai.draw_maj([MajOneHai(s) for s in user.data.maj[0]], [MajOneHai(s).hai for s in user.data.maj[1]])}"
        if await user.choose():
            hai = (await user.buf.aget(prompt=f"你的麻将牌是：{await MajOneHai.draw_maj([MajOneHai(s) for s in user.data.maj[0]], [MajOneHai(s).hai for s in user.data.maj[1]])}，请指定任意一张麻将牌摸取：\n",
                arg_filters=[
                        lambda s: [r for r in re.findall(r'\d[spmz]', str(s))],
                        validators.fit_size(1, 1, message="请输入一张牌。")
                    ]))[0]
            h = MajOneHai(hai)
            await user.draw_maj(h)
        b = random.random()
        if b < 0.5 + 0.02 * user.data.luck:
            await user.draw(1, replace_prompt=user.char + f"声控的很大声，一张牌{'幸运地' if b > 0.5 else ''}从天花板上掉了下来，竟然是：")

class zhanxingshu(_card):
    id = 162
    name = "占星术"
    _description = "一周之内只能使用一次本卡牌。使用后可以自选一个星座，将本周的星座改变。"
    positive = 1
    pack = Pack.misc
    async def use(self, user: User) -> None:
        if await user.choose():
            user.SendCardUse(self, choose = True)
            await user.buf.flush()
            num = (await user.buf.aget(prompt="", arg_filters=[
                extractors.extract_text,
                check_handcard(user),
                lambda s: [int(c) for c in re.findall(r'\-?\d+', str(s))],
                validators.fit_size(1, 1, message="请输入正确的数目。"),
                validators.ensure_true(lambda l: l[0] in list(Sign), message="请输入存在的星座编号。")
            ]))[0]
            user.log << f"选择了{num}。"
            global_state["sign"] = num
            user.send_log(f"改变了当前星座至{Sign(num).name_ch}{句尾}")
            save_global_state()
            await Userme(user).add_status('\\')
class zhanxingshu_exhaust(_statusnull):
    id = 102
    name = "星象已尽"
    _description = "本周星座已被改变。"
    isDebuff = True
    isRemoveable = False
    async def OnUserUseCard(self, user: 'User', card: 'Card') -> Tuple[bool, bool]:
        if card is zhanxingshu:
            return False, False
        return True, False
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnUserUseCard: Priority.OnUserUseCard.zhanxingshu}
