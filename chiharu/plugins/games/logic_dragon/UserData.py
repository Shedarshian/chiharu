from atexit import register
from copy import copy
from typing import *
from collections import defaultdict
import struct
from ... import config
from .Types import TUserData, TEvent
from .Helper import Saveable, indexer
from .Card import Card
from .Status import Status
from .Equipment import Equipment
from .EventListener import IEventListener
from .Priority import UserEvt
if TYPE_CHECKING:
    from .Game import Game
log = config.logger.dragon

class Wrapper:
    def __init__(self, qq):
        self.qq = qq
    def __lshift__(self, log):
        log << f"【LOG】用户{self.qq}" + log
class UserData:
    _fileSize = 1024
    def __init__(self, qq: int, game: 'Game') -> None:
        self.qq = qq
        self.game = game
        self.refCount = 1
        log << f"【DEBUG】创建用户{qq}的UserData。"
        if qq == 0:
            log << "【WARNING】试图find qq=0的node。"
        t = config.userdata.execute("select * from dragon_data2 where qq=?", (qq,)).fetchone()
        if t is None:
            config.userdata.execute("""insert into dragon_data2
                    (qq, jibi, card, status, equipment, card_limit, event_pt, event_stage, dead,
                    flags, assembling, hp, mp, maj_quan, event_skill) values
                    (?, 0, '', '', '', 4, 0, 0, 0,
                    0, 0, 0, 0, 0, 0)""", (qq,))
            t = config.userdata.execute("select * from dragon_data2 where qq=?", (qq,)).fetchone()
        self.node: TUserData = dict(t)
        self._save_file = None
        self.handCard = Card.unpackAllData(self.node['card'])
        self.statusesUnchecked = Status.unpackAllData(self.node['status'])
        self.equipments = Equipment.unpackAllData(self.node['equipment'])
        self.eventListener : defaultdict[UserEvt, TEvent] = defaultdict(lambda: defaultdict(list))
    def AddRef(self):
        self.refCount += 1
    def DecreaseRef(self):
        self.refCount -= 1
    @property
    def valid(self):
        return True
    @property
    def log(self):
        return Wrapper(self.qq)

    @property
    def saveFile(self):
        if self._save_file is None:
            import os
            path = config.rel(f"games\\logic_dragon\\saves\\{self.qq}")
            if not os.path.exists(path):
                self._save_file = open(path, 'br+')
                self._save_file.write(bytearray(self._fileSize))
            else:
                self._save_file = open(path, 'br+')
        return self._save_file
    def readFileByte(self, pos: int, length: int):
        self.saveFile.seek(pos)
        return self.saveFile.read(length)
    def readFileInt(self, pos: int):
        return struct.unpack('!i', self.readFileByte(pos, 4))[0]
    def readFileLong(self, pos: int):
        return struct.unpack('!l', self.readFileByte(pos, 8))[0]
    def setFileInt(self, pos: int, value: int):
        self.saveFile.seek(pos)
        self.saveFile.write(struct.pack('!i', value))
    def setFileLong(self, pos: int, value: int):
        self.saveFile.seek(pos)
        self.saveFile.write(struct.pack('!l', value))
    @property
    def jibi(self):
        return self.node['jibi']
    @jibi.setter
    def jibi(self, value):
        config.userdata.execute("update dragon_data2 set jibi=? where qq=?", (value, self.qq))
        self.node['jibi'] = value
    @property
    def cardLimitRaw(self):
        return self.node['card_limit']
    @cardLimitRaw.setter
    def cardLimitRaw(self, value):
        config.userdata.execute("update dragon_data2 set card_limit=? where qq=?", (value, self.qq))
        self.node['card_limit'] = value
    @property
    def eventPt(self):
        return self.node['event_pt']
    @eventPt.setter
    def eventPt(self, value):
        config.userdata.execute("update dragon_data2 set event_pt=? where qq=?", (value, self.qq))
        self.node['event_pt'] = value
    @property
    def eventStage(self):
        return self.node['event_stage']
    @eventStage.setter
    def eventStage(self, value: int):
        self.node['event_stage'] = value
        config.userdata.execute("update dragon_data2 set event_stage=? where qq=?", (value, self.qq))
    @property
    def eventSkill(self):
        return self.node['event_skill']
    @eventSkill.setter
    def eventSkill(self, value):
        config.userdata.execute("update dragon_data2 set event_skill=? where qq=?", (value, self.qq))
        self.node['event_skill'] = value
    @property
    def assembling(self):
        return self.node['assembling']
    @assembling.setter
    def assembling(self, value):
        config.userdata.execute("update dragon_data2 set assembling=? where qq=?", (value, self.qq))
        self.node['assembling'] = value
    @property
    def hp(self):
        return self.node['hp']
    @hp.setter
    def hp(self, value):
        config.userdata.execute("update dragon_data2 set hp=? where qq=?", (value, self.qq))
        self.node['hp'] = value
    @property
    def mp(self):
        return self.node['mp']
    @mp.setter
    def mp(self, value):
        config.userdata.execute("update dragon_data2 set mp=? where qq=?", (value, self.qq))
        self.node['mp'] = value
    @property
    def majQuan(self):
        return self.node['maj_quan']
    @majQuan.setter
    def majQuan(self, value):
        config.userdata.execute("update dragon_data2 set maj_quan=? where qq=?", (value, self.qq))
        self.node['maj_quan'] = value

    @property
    def drawTime(self):
        return self.readFileInt(0)
    @drawTime.setter
    def drawTime(self, value):
        self.setFileInt(0, value)
    @property
    def todayJibi(self):
        return self.readFileInt(4)
    @todayJibi.setter
    def todayJibi(self, value):
        self.setFileInt(4, value)
    @property
    def todayKeywordJibi(self):
        return self.readFileInt(8)
    @todayKeywordJibi.setter
    def todayKeywordJibi(self, value):
        self.setFileInt(8, value)
    @property
    def shopDrawnCard(self):
        return self.readFileInt(12)
    @shopDrawnCard.setter
    def shopDrawnCard(self, value):
        self.setFileInt(12, value)
    @property
    def spendShop(self):
        return self.readFileInt(16)
    @spendShop.setter
    def spendShop(self, value):
        self.setFileInt(16, value)
    @property
    def tarotTime(self):
        return self.readFileInt(20)
    @tarotTime.setter
    def tarotTime(self, value):
        self.setFileInt(20, value)
    @property
    def mangan(self):
        return self.readFileInt(24)
    @mangan.setter
    def mangan(self, value):
        self.setFileInt(24, value)
    @property
    def yakuman(self):
        return self.readFileInt(28)
    @yakuman.setter
    def yakuman(self, value):
        self.setFileInt(28, value)
    @property
    def eventShop(self):
        return self.readFileInt(32)
    @eventShop.setter
    def eventShop(self, value):
        self.setFileInt(32, value)
    
    @property
    def cardLimitAssembling(self):
        return 0
    @property
    def cardLimit(self):
        return self.cardLimitRaw + self.cardLimitAssembling
    @property
    def dragonEventExp(self):
        return self.node['event_stage']
    @dragonEventExp.setter
    def dragonEventExp(self, value):
        config.userdata.execute("update dragon_data2 set event_stage=? where qq=?", (value, self.qq))
        self.node['event_stage'] = value
    @property
    def dragonLevel(self):
        """begin from 0."""
        if self.qq == 1:
            return self.dragonEventExp
        if self.dragonEventExp >= 55:
            return (self.dragonEventExp - 55) // 10 + 10
        else:
            return int((self.dragonEventExp * 2 + 0.25) ** 0.5 - 0.5)
    @property
    def hpMax(self):
        return 500 + 25 * self.dragonLevel
    @property
    def mpMax(self):
        return 500 + 25 * self.dragonLevel
    @indexer
    def dragonEventSkill(self, index):
        return (self.eventSkill // 10 ** index) % 10
    @dragonEventSkill.setter
    def dragonEventSkill(self, index, item):
        if not 0 <= item <= 4:
            raise ValueError
        self.eventSkill += (item - (self.eventSkill // 10 ** index) % 10) * 10 ** index
    @property
    def ifRichi(self):
        return bool(self.node['flags'] & 1)
    @ifRichi.setter
    def ifRichi(self, value):
        self.node['flags'] = (self.node['flags'] & ~1) + int(bool(value)) * 1
        config.userdata.execute("update dragon_data2 set flags=? where qq=?", (self.node['flags'], self.qq))
    @property
    def notFirstRound(self):
        return bool(self.node['flags'] & 2)
    @notFirstRound.setter
    def notFirstRound(self, value):
        self.node['flags'] = (self.node['flags'] & ~2) + int(bool(value)) * 2
        config.userdata.execute("update dragon_data2 set flags=? where qq=?", (self.node['flags'], self.qq))

    def reregisterAll(self):
        self.eventListener = defaultdict(lambda: defaultdict(list))
        for key, value in self.game.eventListenerInit.items():
            self.eventListener[key] = {k: list(v) for k, v in value.items()}
        for card in self.handCard:
            self.register(card)
        for status in self.statusesUnchecked:
            self.registerStatus(status)
        for equipment in self.equipments:
            self.register(equipment)
    def register(self, eln: IEventListener):
        for key, priority in eln.register():
            self.eventListener[key][priority].append(eln)
    def registerStatus(self, status: Status):
        if status.isGlobal == (self.qq == self.game.managerQQ):
            self.register(status)
    def deregister(self, eln: IEventListener):
        for key, priority in eln.register():
            self.eventListener[key][priority].remove(eln)
            if len(self.eventListener[key][priority]) == 0:
                self.eventListener[key].pop(priority)
    def deregisterStatus(self, status: Status):
        if status.isGlobal == (self.qq == self.game.managerQQ):
            self.deregister(status)
    
    @property
    def statuses(self):
        i = 0
        while i < len(self.statusesUnchecked):
            t = self.statusesUnchecked[i]
            if not t.valid:
                self.deregisterStatus(t)
                self.statusesUnchecked.pop(i)
            else:
                i += 1
        return self.statusesUnchecked
    def CheckStatus(self, id: int):
        return [s for s in self.statuses if s.id == id]
    def CheckStatusStack(self, id: int):
        l = self.CheckStatus(id)
        if len(l) == 0:
            return 0
        return l[0].count
    def CheckEquipment(self, id: int):
        l = [s for s in self.equipments if s.id == id]
        if len(l) == 0:
            return None
        return l[0]

    def addCard(self, c: Card):
        self.handCard.append(c)
        self.register(c)
    def removeCard(self, c: Card):
        self.handCard.remove(c)
        self.deregister(c)