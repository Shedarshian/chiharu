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

class CMishi140(Card):
    name = "密教残篇"
    id = 140
    positive = 1
    _description = "获得正面状态“探索都城”，该系列效果同一玩家同时只能拥有一个。"
    pack = Pack.secret_history
    async def Use(self, user: 'User') -> None:
        M = user.CheckStatus(SExplore140)
        if len(M) > 0:
            M[0].num = 1
            user.data.SaveStatuses()
            user.SendCardUse(self, overwrite = True)
        else:
            await user.AddStatus(SExplore140(1))
            user.SendCardUse(self, overwrite = False)
class CMishi141(Card):
    name = "鬼祟的真相"
    id = 141
    positive = 1
    _description = "获得正面状态“探索各郡”，该系列效果同一玩家同时只能拥有一个。"
    pack = Pack.secret_history
    async def Use(self, user: 'User') -> None:
        M = user.CheckStatus(SExplore140)
        if len(M) > 0:
            M[0].num = 2
            user.data.SaveStatuses()
            user.SendCardUse(self, overwrite = True)
        else:
            await user.AddStatus(SExplore140(2))
            user.SendCardUse(self, overwrite = False)
class CMishi142(Card):
    name = "被遗忘的史籍"
    id = 142
    positive = 1
    _description = "获得正面状态“探索大陆”，该系列效果同一玩家同时只能拥有一个。"
    pack = Pack.secret_history
    async def Use(self, user: 'User') -> None:
        M = user.CheckStatus(SExplore140)
        if len(M) > 0:
            M[0].num = 3
            user.data.SaveStatuses()
            user.SendCardUse(self, overwrite = True)
        else:
            await user.AddStatus(SExplore140(3))
            user.SendCardUse(self, overwrite = False)
class CMishi143(Card):
    name = "禁断的史诗"
    id = 143
    positive = 1
    _description = "获得正面状态“探索森林尽头之地”，该系列效果同一玩家同时只能拥有一个。"
    pack = Pack.secret_history
    async def Use(self, user: 'User') -> None:
        M = user.CheckStatus(SExplore140)
        if len(M) > 0:
            M[0].num = 4
            user.data.SaveStatuses()
            user.SendCardUse(self, overwrite = True)
        else:
            await user.AddStatus(SExplore140(4))
            user.SendCardUse(self, overwrite = False)
class CMishi144(Card):
    name = "悬而未定的模棱两可"
    id = 144
    positive = 1
    _description = "获得正面状态“探索撕身山脉”，该系列效果同一玩家同时只能拥有一个。"
    pack = Pack.secret_history
    async def Use(self, user: 'User') -> None:
        M = user.CheckStatus(SExplore140)
        if len(M) > 0:
            M[0].num = 5
            user.data.SaveStatuses()
            user.SendCardUse(self, overwrite = True)
        else:
            await user.AddStatus(SExplore140(5))
            user.SendCardUse(self, overwrite = False)
class CMishi145(Card):
    name = "浪游旅人的地图"
    id = 145
    positive = 1
    _description = "获得正面状态“探索荒寂而平阔的沙地”，该系列效果同一玩家同时只能拥有一个。"
    pack = Pack.secret_history
    async def Use(self, user: 'User') -> None:
        M = user.CheckStatus(SExplore140)
        if len(M) > 0:
            M[0].num = 6
            user.data.SaveStatuses()
            user.SendCardUse(self, overwrite = True)
        else:
            await user.AddStatus(SExplore140(6))
            user.SendCardUse(self, overwrite = False)
class CMishi146(Card):
    name = "午港奇闻"
    id = 146
    positive = 1
    _description = "获得正面状态“探索薄暮群屿”，该系列效果同一玩家同时只能拥有一个。"
    pack = Pack.secret_history
    async def Use(self, user: 'User') -> None:
        M = user.CheckStatus(SExplore140)
        if len(M) > 0:
            M[0].num = 7
            user.data.SaveStatuses()
            user.SendCardUse(self, overwrite = True)
        else:
            await user.AddStatus(SExplore140(7))
            user.SendCardUse(self, overwrite = False)
class SExplore140(StatusNumed):
    id = 140
    @property
    def name(self):
        if self.num in range(1,9):
            spot = ["都城", "各郡", "大陆", "森林尽头之地", "撕身山脉", "荒寂而平阔的沙地", "薄暮群屿", "薄暮群屿"][self.num - 1]
            return f"探索{spot}"
    def description(self):
        if self.num in range(1,8):
            return "你将会触发一系列随机事件。"
        elif self.num == 8:
            return "你将会触发一系列随机事件。\n\t置身格里克堡：直到失去状态“探索薄暮群屿”，抵御所有死亡效果。"
    def double(self):
        pass
    async def BeforeDragoned(self, user: 'User', state: 'DragonState') -> Tuple[bool, int]:
        user.state['mishi_id'] = i = random.randint(0, 5 if self.num <= 4 else 4)
        user.state['dragon_who'] = user.qq
        if self.num <= 4 and i == 5 or self.num > 4 and i == 4:
            if random.random() < 0.1 * min(user.data.luck, 5):
                user.SendStatusEffect(self, time = 'BeforeDragoned', mid = 'reroll')
                user.state['mishi_id'] = i = random.randint(0, 5 if self.num <= 4 else 4)
        if self.num == 1 and i == 1:
            user.SendStatusEffect(self, time = 'BeforeDragoned', mnum = 1, mid = 1)
        elif self.num == 2 and i == 1:
            user.SendStatusEffect(self, time = 'BeforeDragoned', mnum = 2, mid = 1)
        elif self.num == 4 and i == 1:
            user.SendStatusEffect(self, time = 'BeforeDragoned', mnum = 4, mid = 1)
        elif self.num == 5 and i == 1:
            user.SendStatusEffect(self, time = 'BeforeDragoned', mnum = 5, mid = 1)
        return True, 0
    async def OnDragoned(self, user: 'User', branch: 'Tree', first10: bool) -> None:
        if (i := user.state.get('mishi_id')) is None:
            i = random.randint(0, 5 if self.num <= 4 else 4)
        if self.num == 1:
            if i == 0:
                user.SendStatusEffect(self, time = 'OnDragoned', mnum = 1, mid = 0)
                await user.Draw(cards=[Card.get(94)()])
            elif i == 1:
                pass
            elif i == 2:
                if random.random() < 0.5:
                    jibi = True
                    user.SendStatusEffect(self, time = 'OnDragoned', mnum = 1, mid = 2, jibi = jibi)
                    await user.AddJibi(1)
                else:
                    jibi = False
                    user.SendStatusEffect(self, time = 'OnDragoned', mnum = 1, mid = 2, jibi = jibi)
                    await user.AddJibi(-1)
            elif i == 3:
                user.SendStatusEffect(self, time = 'OnDragoned', mnum = 1, mid = 3)
                user.data.todayJibi += 1
                # config.logger.dragon << f"【LOG】用户{user.qq}增加了接龙击毙上限至{user.data.today_jibi}。"
            elif i == 4:
                user.SendStatusEffect(self, time = 'OnDragoned', mnum = 1, mid = 4)
                await user.AddStatus(SJiaotu) #TODO
            else:
                user.SendStatusEffect(self, time = 'OnDragoned', mnum = 1, mid = -1)
                self.num = 0
                await user.death(15)
                user.data.SaveStatuses()
        elif self.num == 2:
            if i == 0:
                user.SendStatusEffect(self, time = 'OnDragoned', mnum = 2, mid = 0)
                await user.ume.AddStatus(SShequn)#TODO
            elif i == 1:
                pass
            elif i == 2:
                user.SendStatusEffect(self, time = 'OnDragoned', mnum = 2, mid = 2)
                await user.AddStatus(SShangba)#TODO
            elif i == 3:
                user.SendStatusEffect(self, time = 'OnDragoned', mnum = 2, mid = 3)
                await user.AddJibi(5)
                await user.DrawAndUse(requirement=positive({0, -1}))
            elif i == 4:
                user.SendStatusEffect(self, time = 'OnDragoned', mnum = 2, mid = 4)
                if random.random() < 0.25:
                    await user.Draw(1)
            else:
                user.SendStatusEffect(self, time = 'OnDragoned', mnum = 2, mid = -1)
                self.num = 0
                await user.Death(30)
                user.data.SaveStatuses()
        elif self.num == 3:
            if i == 0:
                l = [s for s in user.data.statuses if s.isDebuff]
                if len(l) == 0:
                    tstatus = False
                    user.SendStatusEffect(self, time = 'OnDragoned', mnum = 3, mid = 0, tstatus = tstatus)
                else:
                    c = random.choice(l)
                    tstatus = c.Dumpdata()
                    user.SendStatusEffect(self, time = 'OnDragoned', mnum = 3, mid = 0, tstatus = tstatus)
                    await user.RemoveStatus(c)
            elif i == 1:
                user.SendStatusEffect(self, time = 'OnDragoned', mnum = 3, mid = 1)
                user.AddJibi(-5)
                await user.AddStatus(SBeizhizhunze)#TODO
            elif i == 2:
                if len(cs:=user.game.state['used_cards']) == 0:
                    c = False
                    user.SendStatusEffect(self, time = 'OnDragoned', mnum = 3, mid = 2, tcard = c)
                else:
                    card = Card.get(random.choice(cs))()
                    c = card.DumpData()
                    user.SendStatusEffect(self, time = 'OnDragoned', mnum = 3, mid = 2, tcard = c)
                    await user.UseCardEffect(card)
            elif i == 3:
                cs = [c for c in user.data.handCard if c.positive != 1]
                if len(cs) == 0:
                    c = False
                    user.SendStatusEffect(self, time = 'OnDragoned', mnum = 3, mid = 3, tcard = c)
                    await user.AddJibi(10)
                    await user.Draw(cards=[Card.get(-1)()])
                else:
                    card = random.choice(cs)
                    c = card.DumpData()
                    user.SendStatusEffect(self, time = 'OnDragoned', mnum = 3, mid = 3, tcard = c)
                    await user.AddJibi(10)
                    await user.UseCardEffect(card)
            elif i == 4:
                user.SendStatusEffect(self, time = 'OnDragoned', mnum = 3, mid = 4)
                user.data.todayJibi += 5
                # config.logger.dragon << f"【LOG】用户{user.qq}增加了接龙击毙上限至{user.data.today_jibi}。"
            else:
                user.SendStatusEffect(self, time = 'OnDragoned', mnum = 3, mid = -1)
                self.num = 0
                await user.Death(60)
                user.data.SaveStatuses()
        elif self.num == 4:
            if i == 0:
                user.SendStatusEffect(self, time = 'OnDragoned', mnum = 4, mid = 0)
                await user.AddStatus(SLazhuyandong)#TODO
            elif i == 1:
                pass
            elif i == 2:
                user.SendStatusEffect(self, time = 'OnDragoned', mnum = 4, mid = 2)
                await user.AddStatus(SCircus)#TODO
            elif i == 3: #TODO remember to add statuses into 'global_status', not id.
                if len(user.game.state['global_status']) == 0:
                    tstatus = None
                    user.SendStatusEffect(self, time = 'OnDragoned', mnum = 4, mid = 3, tstatus = tstatus)
                else:
                    ss = user.game.state['global_status'][-1]
                    if user.ume.CheckStatus(ss):
                        tstatus = ss.DumpData()
                        user.SendStatusEffect(self, time = 'OnDragoned', mnum = 4, mid = 3, tstatus = tstatus)
                        await user.ume.RemoveStatus(ss)
                    else:
                        tstatus = False
                        user.SendStatusEffect(self, time = 'OnDragoned', mnum = 4, mid = 3, tstatus = tstatus)
            elif i == 4:
                while True:
                    s = random.choice([st for id, st in Status.id_dict.items() if st.isNull])()
                    if s.isGlobal:
                        break
                tstatus = s.DumpData()
                user.SendStatusEffect(self, time = 'OnDragoned', mnum = 4, mid = 4, tstatus = tstatus)
                await user.ume.AddStatus(s)
            else:
                user.SendStatusEffect(self, time = 'OnDragoned', mnum = 4, mid = -1)
                self.num = 0
                await user.Death(90)
                user.data.SaveStatuses()
        elif self.num == 5:
            if i == 0:
                pq = branch.parent.qq
                if pq != config.selfqq and pq != 0:
                    user.CreateUser(pq).AddStatus(Slieshouzhixue)#TODO
                    notgt = False
                else:
                    notgt = True
                user.SendStatusEffect(self, time = 'OnDragoned', mnum = 5, mid = 0, notgt = notgt)
            elif i == 1:
                if not user.state.get("branch_removed"):
                    user.state["branch_removed"] = True
                    user.game.RemoveTree(branch)
                user.SendStatusEffect(self, time = 'OnDragoned', mnum = 5, mid = 1)
            elif i == 2:#TODO remember to reset in OnNewDay
                if not global_state['observatory']:
                    tword = random.choice(user.game.hiddenKeyword)
                    global_state['observatory'] = True
                else:
                    tword = False
                user.SendStatusEffect(self, time = 'OnDragoned', mnum = 5, mid = 2, tword = tword)
            elif i == 3:
                user.SendStatusEffect(self, time = 'OnDragoned', mnum = 5, mid = 3)
                await user.AddJibi(10)
            else:
                user.SendStatusEffect(self, time = 'OnDragoned', mnum = 5, mid = -1)
                self.num = 0
                await user.Death(120)
                user.data.SaveStatuses()
        elif self.num == 6:
            if i == 0:
                user.SendStatusEffect(self, time = 'OnDragoned', mnum = 6, mid = 0)
                await user.ume.AddStatus(SShendian)#TODO
            elif i == 1:
                pq = branch.parent.qq
                if pq != config.selfqq and pq != 0:
                    notgt = False
                    user.SendStatusEffect(self, time = 'OnDragoned', mnum = 6, mid = 1, notgt = notgt)
                    await user.CreateUser(pq).Death(15)
                else:
                    notgt = True
                    user.SendStatusEffect(self, time = 'OnDragoned', mnum = 6, mid = 1, notgt = notgt)
            elif i == 2:
                user.SendStatusEffect(self, time = 'OnDragoned', mnum = 6, mid = 2)
                await user.AddStatus(Schangsheng(120))#TODO
            elif i == 3:
                user.SendStatusEffect(self, time = 'OnDragoned', mnum = 6, mid = 3)
                await user.add_daily_status(STemple) #TODO
            else:
                user.SendStatusEffect(self, time = 'OnDragoned', mnum = 6, mid = -1)
                self.num = 0
                await user.Death(180)
                user.data.SaveStatuses()
        elif self.num == 7 or self.num == 8:
            if i == 0:
                await user.AddStatus(SQuest3(10, 2, n:=Mission.RandomQuestStoneId()))
                tquest = Mission.get(n).description
                user.SendStatusEffect(self, time = 'OnDragoned', mnum = 7, mid = 0, tquest = tquest)
            elif i == 1:
                user.SendStatusEffect(self, time = 'OnDragoned', mnum = 7, mid = 1)
                self.num = 8
                user.data.SaveStatuses()
            elif i == 2:
                user.SendStatusEffect(self, time = 'OnDragoned', mnum = 7, mid = 2)
                if l := await user.ChooseHandCards(1, 1):
                    await user.DiscardCards(l[0])
                await user.draw(2, requirement=positive({1}))
            elif i == 3:
                j = random.randint(0, 2)
                if j == 0:
                    user.SendStatusEffect(self, time = 'OnDragoned', mnum = 7, mid = 3, flag = 'addjibi')
                    await user.AddJibi(20)
                elif j == 1:
                    user.SendStatusEffect(self, time = 'OnDragoned', mnum = 7, mid = 3, flag = 'drawcard')
                    await user.Draw(1)
                elif len(user.data.handCard) == 0:
                    user.SendStatusEffect(self, time = 'OnDragoned', mnum = 7, mid = 3, flag = 'nocard')
                else:
                    cd = random.choice(user.data.handCard)
                    user.SendStatusEffect(self, time = 'OnDragoned', mnum = 7, mid = 3, flag = 'discardcard', tcard = cd.DumpData())
                    await user.DiscardCards([cd])
            else:
                user.SendStatusEffect(self, time = 'OnDragoned', mnum = 7, mid = -1)
                self.num = 0
                await user.Death(240)
                user.data.SaveStatuses()
        else:
            self.num = 0
            user.data.SaveStatuses()
        user.state.pop('mishi_id')
    async def OnDeath(self, user: 'User', killer: Optional['User'], time: int, c: 'AttackType') -> Tuple[int, bool]:
        i = user.state.get('mishi_id') # maybe None but no problem
        if user.state.get('dragon_who') != user.qq:
            return time, False
        if self.num == 1 and i == 1:
            # if await c.pierce():
            #     user.send_log(f"被遗忘的密特拉寺的效果被幻想杀手消除了{句尾}")
            #     return time, False
            s = random.random() * 0.1
            user.SendStatusEffect(self, time = 'OnDeath', mnum = 1, mid = 1, s = s)
            return (1 - s) * time, False
        elif self.num == 2 and i == 1:
            # if await c.pierce():
            #     user.send_log(f"洛克伍德沼地的效果被幻想杀手消除了{句尾}")
            #     return time, False
            user.SendStatusEffect(self, time = 'OnDeath', mnum = 2, mid = 1)
            return 0.75 * time, False
        elif self.num == 4 and i == 1:
            # if await c.pierce():
            #     user.send_log(f"大公的城塞的效果被幻想杀手消除了{句尾}")
            #     return time, False
            user.SendStatusEffect(self, time = 'OnDeath', mnum = 3, mid = 1)
            return 0.5 * time, False
        elif self.num == 5 and i == 1:
            # if await c.pierce():
            #     user.send_log(f"避雪神庙的效果被幻想杀手消除了{句尾}")
            #     return time, False
            user.SendStatusEffect(self, time = 'OnDeath', mnum = 5, mid = 1)
            return 0, True
        elif self.num == 8:
            # if await c.pierce():
            #     user.send_log(f"堡垒的效果被幻想杀手消除了{句尾}")
            #     self.num = 7
            #     user.data.SaveStatuses()
            #     return time, False
            user.SendStatusEffect(self, time = 'OnDeath', mnum = 8, mid = 0)
            return time, True
        return time, False
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.BeforeDragoned: Priority.BeforeDragoned.explore,
            UserEvt.OnDragoned: Priority.OnDragoned.explore,
            UserEvt.OnDeath: Priority.OnDeath.explore}

class SJiaotu141(StatusNullStack):
    name = "置身许伦的圣菲利克斯之会众"
    id = 141
    _description = "被虔诚的教徒们包围，他们追奉启之法则，你下一次接龙需要进行首尾接龙。"
    isDebuff = True
    async def BeforeDragoned(self, user: 'User', state: 'DragonState') -> Tuple[bool, int]:
        if not await state.RequireShouWei(user):
            user.SendStatusEffect(self)
            return False, 0
        return True, 0
    async def OnDragoned(self, user: 'User', branch: 'Tree', first10: bool) -> None:
        await user.RemoveStatus(self)
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.BeforeDragoned: Priority.BeforeDragoned.jiaotu,
            UserEvt.OnDragoned: Priority.OnDragoned.jiaotu}
class SInvJiaotu142(StatusNullStack):
    name = "反转-置身许伦的圣菲利克斯之会众"
    id = 142
    _description = "被虔诚的教徒们包围，他们追奉启之法则，你下一次接龙需要进行尾首接龙。"
    isDebuff = True
    async def BeforeDragoned(self, user: 'User', state: 'DragonState') -> Tuple[bool, int]:
        if not await state.RequireWeiShou(user):
            user.SendStatusEffect(self)
            return False, 0
        return True, 0
    async def OnDragoned(self, user: 'User', branch: 'Tree', first10: bool) -> None:
        await user.RemoveStatus(self)
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.BeforeDragoned: Priority.BeforeDragoned.inv_jiaotu,
            UserEvt.OnDragoned: Priority.OnDragoned.inv_jiaotu}

class SShequn143(StatusNullStack):
    name = "置身格拉德温湖"
    id = 142
    _description = "此处有蛇群把守。下一个接龙的人需要进行首尾接龙。"
    isDebuff = True
    isGlobal = True
    async def BeforeDragoned(self, user: 'User', state: 'DragonState') -> Tuple[bool, int]:
        if not await state.RequireShouWei(user):
            user.SendStatusEffect(self)
            return False, 0
        return True, 0
    async def OnDragoned(self, user: 'User', branch: 'Tree', first10: bool) -> None:
        await user.RemoveStatus(self)
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.BeforeDragoned: Priority.BeforeDragoned.shequn,
            UserEvt.OnDragoned: Priority.OnDragoned.shequn}
class SInvShequn144(StatusNullStack):
    name = "反转-置身格拉德温湖"
    id = 144
    _description = "此处有蛇群把守。下一个接龙的人需要进行尾首接龙。"
    isDebuff = True
    isGlobal = True
    async def BeforeDragoned(self, user: 'User', state: 'DragonState') -> Tuple[bool, int]:
        if not await state.RequireWeiShou(user):
            user.SendStatusEffect(self)
            return False, 0
        return True, 0
    async def OnDragoned(self, user: 'User', branch: 'Tree', first10: bool) -> None:
        await user.RemoveStatus(self)
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.BeforeDragoned: Priority.BeforeDragoned.inv_shequn,
            UserEvt.OnDragoned: Priority.OnDragoned.inv_shequn}

class SShangba145(StatusDailyStack):
    name = "伤疤"
    id = 145
    _description = "今天你每死亡一次便获得2击毙。"
    async def OnDeath(self, user: 'User', killer: Optional['User'], time: int, c: 'AttackType') -> Tuple[int, bool]:
        # if await c.pierce():
        #     user.send_log(f"伤疤的效果被幻想杀手消除了{句尾}")
        #     await user.remove_status('S', remover=killer)
        user.SendStatusEffect(self, count = self.count)
        await user.AddJibi(2*self.count)
        return time, False
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnDeath: Priority.OnDeath.shangba}
class SInvShangba146(StatusDailyStack):
    name = "反转-伤疤"
    id = 145
    _description = "今天你每死亡一次便失去2击毙。"
    async def OnDeath(self, user: 'User', killer: Optional['User'], time: int, c: 'AttackType') -> Tuple[int, bool]:
        # if await c.pierce():
        #     user.send_log(f"反转-伤疤的效果被幻想杀手消除了{句尾}")
        #     await user.remove_status('S', remover=killer)
        user.SendStatusEffect(self, count = self.count)
        await user.AddJibi(-2*self.count)
        return time, False
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnDeath: Priority.OnDeath.inv_shangba}

class SBeizhizhunze76(StatusDailyStack):
    name = "杯之准则"
    id = 76
    _description = "你今天每次接龙额外获得1击毙。"
    async def OnDragoned(self, user: 'User', branch: 'Tree', first10: bool) -> None:
        user.SendStatusEffect(self, count = self.count)
        await user.AddJibi(self.count)
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnDragoned: Priority.OnDragoned.beizhizhunze}
class SBeizhizhunze62(StatusDailyStack):
    name = "反转-杯之准则"
    id = 62
    _description = "你今天每次接龙额外失去1击毙。"
    async def OnDragoned(self, user: 'User', branch: 'Tree', first10: bool) -> None:
        user.SendStatusEffect(self, count = self.count)
        await user.AddJibi(-1*self.count)
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnDragoned: Priority.OnDragoned.inv_beizhizhunze}

class SLazhuyandong57(StatusNullStack):
    name = "置身蜡烛岩洞"
    id = 57
    _description = "下一次接龙可以少间隔一个人。"
    async def BeforeDragoned(self, user: 'User', state: 'DragonState') -> Tuple[bool, int]:
        return True, -1
    async def OnDragoned(self, user: 'User', branch: 'Tree', first10: bool) -> None:
        await user.RemoveStatus(self)
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.BeforeDragoned: Priority.BeforeDragoned.lazhuyandong,
            UserEvt.OnDragoned: Priority.OnDragoned.lazhuyandong}
class SInvLazhuyandong56(StatusNullStack):
    name = "反转-置身蜡烛岩洞"
    id = 57
    _description = "下一次接龙需要多间隔一个人。"
    async def BeforeDragoned(self, user: 'User', state: 'DragonState') -> Tuple[bool, int]:
        return True, 1
    async def OnDragoned(self, user: 'User', branch: 'Tree', first10: bool) -> None:
        await user.RemoveStatus(self)
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.BeforeDragoned: Priority.BeforeDragoned.inv_lazhuyandong,
            UserEvt.OnDragoned: Priority.OnDragoned.inv_lazhuyandong}

class SCircus55(StatusNullStack):
    name = "置身格吕内瓦尔德的常驻马戏团"
    id = 55
    _description = "下一次接龙不受全局状态的影响。"
    async def OnDragoned(self, user: 'User', branch: 'Tree', first10: bool) -> None:
        user.SendStatusEffect(self)
        await user.RemoveStatus(self)
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnDragoned: Priority.OnDragoned.circus}

class SLieshouzhixue31(StatusNullStack):
    name = "置身猎手之穴"
    id = 31
    _description = "下一次接龙需要多间隔一个人。"
    async def BeforeDragoned(self, user: 'User', state: 'DragonState') -> Tuple[bool, int]:
        return True, 1
    async def OnDragoned(self, user: 'User', branch: 'Tree', first10: bool) -> None:
        await user.RemoveStatus(self)
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.BeforeDragoned: Priority.BeforeDragoned.lieshouzhixue,
            UserEvt.OnDragoned: Priority.OnDragoned.lieshouzhixue}
class SInvLieshouzhixue29(StatusNullStack):
    name = "反转-置身猎手之穴"
    id = 29
    _description = "下一次接龙可以少间隔一个人。"
    async def BeforeDragoned(self, user: 'User', state: 'DragonState') -> Tuple[bool, int]:
        return True, -1
    async def OnDragoned(self, user: 'User', branch: 'Tree', first10: bool) -> None:
        await user.RemoveStatus(self)
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.BeforeDragoned: Priority.BeforeDragoned.inv_lieshouzhixue,
            UserEvt.OnDragoned: Priority.OnDragoned.inv_lieshouzhixue}

class SShendian153(StatusNullStack):
    name = "置身被星辰击碎的神殿"
    id = 153
    _description = "之后接龙的一个人会额外获得5击毙。"
    isGlobal = True
    async def OnDragoned(self, user: 'User', branch: 'Tree', first10: bool) -> None:
        user.SendStatusEffect(self, count = self.count)
        await user.AddJibi(5*self.count)
        await user.ume.RemoveStatus(self)
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnDragoned: Priority.OnDragoned.shendian}
class SInvShendian157(StatusNullStack):
    name = "反转-置身被星辰击碎的神殿"
    id = 157
    _description = "之后接龙的一个人会额外失去5击毙。"
    isGlobal = True
    async def OnDragoned(self, user: 'User', branch: 'Tree', first10: bool) -> None:
        user.SendStatusEffect(self, count = self.count)
        await user.AddJibi(-5*self.count)
        await user.ume.RemoveStatus(self)
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnDragoned: Priority.OnDragoned.inv_shendian}

class SChangsheng(StatusNumed):#TODO
    name = "长生的宴席"
    id = ?
    _description = "可抵消死亡时间。"
    @property
    def description(self):
        return f"{self._description}\n\t剩余{self.num}分钟。"
    async def OnDeath(self, user: 'User', killer: Optional['User'], time: int, c: 'AttackType') -> Tuple[int, bool]:
        # if await c.pierce():
        m = min(self.num, time)
        self.num -= m
        time -= m
        user.SendStatusEffect(self, time = m, dead = (time == 0))
        return time, (time == 0)
    def register(self) -> Dict[UserEvt, int]:
        return {UserEvt.OnDeath: Priority.OnDeath.changsheng}

class STemple160(StatusDailyStack):
    name = "置身七蟠寺"
    id = 160
    _description = "今天结束的非负面状态延长至明天。"
class SInvTemple161(StatusDailyStack):
    name = "反转-置身七蟠寺"
    id = 161
    _description = "今天结束的负面状态延长至明天。"
