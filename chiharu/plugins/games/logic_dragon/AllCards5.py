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

class CMishi140(_card):
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
            await user.add_limited_status(Sexplore(1))
            user.SendCardUse(self, overwrite = False)
class CMishi141(_card):
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
            await user.add_limited_status(Sexplore(2))
            user.SendCardUse(self, overwrite = False)
class CMishi142(_card):
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
            await user.add_limited_status(Sexplore(3))
            user.SendCardUse(self, overwrite = False)
class CMishi143(_card):
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
            await user.add_limited_status(Sexplore(4))
            user.SendCardUse(self, overwrite = False)
class CMishi144(_card):
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
            await user.add_limited_status(Sexplore(5))
            user.SendCardUse(self, overwrite = False)
class CMishi145(_card):
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
            await user.add_limited_status(Sexplore(6))
            user.SendCardUse(self, overwrite = False)
class CMishi146(_card):
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
            await user.add_limited_status(SExplore140(7))
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
        user.buf.state['mishi_id'] = i = random.randint(0, 5 if count[0].num <= 4 else 4)
        user.buf.state['dragon_who'] = user.qq
        if count[0].num <= 4 and i == 5 or count[0].num > 4 and i == 4:
            if random.random() < 0.1 * min(user.data.luck, 5):
                user.send_log("随机到了死亡，重新随机" + 句尾)
                user.buf.state['mishi_id'] = i = random.randint(0, 5 if count[0].num <= 4 else 4)
        if count[0].num == 1 and i == 1:
            user.send_log("置身被遗忘的密特拉寺：")
            user.buf.send("你在此地进行了虔诚（）的祈祷。如果你此次接龙因各种原因被击毙，减少0～10%的死亡时间。")
        elif count[0].num == 2 and i == 1:
            user.send_log("置身洛克伍德沼地：")
            user.buf.send("成真的神明或是在守望此地。如果你此次接龙被击毙，减少25%死亡时间。")
        elif count[0].num == 4 and i == 1:
            user.send_log("置身大公的城塞：")
            user.buf.send("他平复了许多人的干渴，最终又败给了自己的干渴。若你因本次接龙被击毙，减少50%的死亡时间。")
        elif count[0].num == 5 and i == 1:
            user.send_log("置身避雪神庙：")
            user.buf.send("神庙可以回避一些袭击。本次接龙不会因为一周内接龙过或是踩雷而被击毙，但也没有接龙成功。")
        return True, 0