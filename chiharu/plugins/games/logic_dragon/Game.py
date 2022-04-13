from multiprocessing import Event
from typing import *
from copy import copy
from io import TextIOWrapper
from collections import defaultdict
from contextlib import contextmanager
import random, json, re
from datetime import date, datetime, time, timedelta
import unicodedata
from .User import User
from .UserData import UserData
from .Dragon import Tree, DragonState
from .Types import TEvent, TGlobalState, Sign, ProtocolData, TWords
from .Helper import Buffer
from .Priority import UserEvt
from .EventListener import IEventListener
from .Card import Card
from .Item import Item, JibiShopItem, EventShopItem
from .Equipment import Equipment
from ... import config

VERSION = "0.4.0"
CHANGELOG = """0.4.0 Changelog:
Change:
再次重构。引入大量新bug。"""

class Game:
    def __init__(self) -> None:
        self.treeForests: List[List[List['Tree']]] = []
        self.treeObjs: List[List['Tree']] = []
        self.treeMaxBranches = 0
        self.managerQQ = config.selfqq
        self.dragonQQ = 1
        self.me = UserData(self.managerQQ, self)
        self.eventListenerInit: defaultdict[UserEvt, TEvent] = defaultdict(lambda: defaultdict(list))
        self.userdatas: Dict[int, 'UserData'] = {}
        with open(config.rel('dragon_state.json'), encoding='utf-8') as f:
            self.state: TGlobalState = json.load(f)
        with open(config.rel('dragon_words.json'), encoding='utf-8') as f:
            d: TWords = json.load(f)
            self.keyword = d["keyword"][0]
            self.hiddenKeyword = d["hidden"][0]
            self.bombs = d["bombs"]
            self.lastUpdateDate = d["last_update_date"]
        self.logSet: dict[str, int] = {}
        self.logFile: TextIOWrapper | None = None
        self.LoadLogSet()
        self.LoadTree()
        self.logFile = open(self.treeFilePath(self.getToday()), 'a', encoding='utf-8')
    def __del__(self):
        if self.logFile is not None:
            self.logFile.close()

    @classmethod
    def getToday(cls):
        dt = date.today()
        if datetime.now().time() < time(15, 59):
            dt -= timedelta(days=1)
        return dt
    @classmethod
    def treeFilePath(cls, dt: date):
        return config.rel(rf'log\dragon_log_{dt.isoformat()}.txt')

    def LoadDragonWords(self):
        with open(config.rel('dragon_words.json'), encoding='utf-8') as f:
            d: TWords = json.load(f)
        return d
    @contextmanager
    def UpdateDragonWords(self):
        d = self.LoadDragonWords()
        yield d
        with open(config.rel('dragon_words.json'), 'w', encoding='utf-8') as f:
            f.write(json.dumps(d, indent=4, ensure_ascii=False))
    def UpdateKeyword(self, if_delete=False) -> ProtocolData:
        with self.UpdateDragonWords() as d:
            s = set(d['keyword'][1]) - set(self.logSet.keys()) - set(self.bombs)
            if len(s) == 0:
                keyword = ""
                return {"type": "failed", "error_code": 451}
            keyword = random.choice(list(s))
            d['keyword'][1].remove(keyword)
            if not if_delete:
                d['keyword'][1].append(d['keyword'][0])
            d['keyword'][0] = keyword
            return {"type": "update_keyword", "keyword": keyword}
    def AddHiddenKeyword(self, count=1) -> ProtocolData:
        with self.UpdateDragonWords() as d:
            if len(d['hidden'][1]) < count:
                return {"type": "failed", "error_code": 452}
            for i in range(count):
                new = random.choice(d['hidden'][1])
                d['hidden'][1].remove(new)
                self.hiddenKeyword.append(new)
                d['hidden'][0].append(new)
            return {"type": "update_hidden_keyword", "keywords": list(self.hiddenKeyword)}
    def RemoveHiddenKeyword(self, count=1, if_delete=False) -> ProtocolData:
        with self.UpdateDragonWords() as d:
            for i in range(count):
                old = self.hiddenKeyword.pop()
                if not if_delete:
                    d['hidden'][1].append(old)
                d['hidden'][0].remove(old)
            return {"type": "update_hidden_keyword", "keywords": list(self.hiddenKeyword)}
    def UpdateHiddenKeyword(self, which, if_delete=False) -> ProtocolData:
        with self.UpdateDragonWords() as d:
            if which == -1:
                n = {0, 1, 2}
            elif isinstance(which, int):
                n = {which}
            else:
                n = {self.hiddenKeyword.index(which)}
            if len(d['hidden'][1]) < len(n):
                return {"type": "failed", "error_code": 452}
            for i in n:
                self.hiddenKeyword[i] = random.choice(d['hidden'][1])
                d['hidden'][1].remove(self.hiddenKeyword[i])
                if not if_delete:
                    d['hidden'][1].append(d['hidden'][0][i])
                d['hidden'][0][i] = self.hiddenKeyword[i]
            return {"type": "update_hidden_keyword", "keywords": list(self.hiddenKeyword)}
    def RemoveBomb(self, word: str):
        with self.UpdateDragonWords() as d:
            d["bombs"].remove(word)
            self.bombs.remove(word)
    def AddBomb(self, word: str):
        with self.UpdateDragonWords() as d:
            d["bombs"].append(word)
            self.bombs.append(word)
    def AddBegin(self, word: str):
        with self.UpdateDragonWords() as d:
            d['begin'].append(word)
    def AddKeyword(self, word: str):
        with self.UpdateDragonWords() as d:
            d['keyword'][1].append(word)
    def AddHidden(self, word: str):
        with self.UpdateDragonWords() as d:
            d['hidden'][1].append(word)
    def UpdateBeginWord(self, isDailyUpdate: bool):
        with self.UpdateDragonWords() as d:
            c = random.choice(d['begin'])
            if isDailyUpdate:
                d['last_update_date'] = self.lastUpdateDate = date.today().isoformat()
            d['begin'].remove(c)
            config.logger.dragon.log << f"更新了起始词：{c}。"
            if len(d['begin']) == 0:
                config.logger.dragon.error << "起始词库已空！"
        word_stripped = re.sub(r'\[CQ:image,file=.*\]', '', c).strip()
        pic: str | None = match.group(1) if (match := re.match(r'.*\[CQ:image,file=(.*)\]', c)) is not None else None
        self.logSet[word_stripped] = self.managerQQ
        if not isDailyUpdate:
            self.logFile.write(Tree.saveNew()) # type: ignore[union-attr]
        self.InitTree(isDailyUpdate)
        self.AddTree(None, word_stripped, self.managerQQ, '', '')
        return word_stripped, pic

    def InitTree(self, isDailyUpdate: bool):
        if isDailyUpdate:
            self.treeForests = []
        else:
            self.treeForests.append(self.treeObjs)
        self.treeObjs = []
        self.treeMaxBranches = 0
    def FindTree(self, id: Tuple[int, int]):
        if id is None:
            return None
        try:
            if len(self.treeObjs[id[1]]) == 0:
                return None
            return self.treeObjs[id[1]][id[0] - self.treeObjs[id[1]][0].id[0]]
        except IndexError:
            return None
    def AddTree(self, parent: Optional[Tree], word: str, qq: int, kwd: str, hdkwd: str, fork: bool=False,
            /, id: tuple[int, int]=None):
        if id is None:
            if parent:
                id = (parent.id[0] + 1, parent.id[1])
            else:
                id = (0, 0)
            if self.FindTree(id):
                id = (id[0], self.treeMaxBranches)
                if parent:
                    parent.fork = True
        tree = Tree(parent, word, qq, kwd, hdkwd, id=id, fork=fork)
        if parent and parent.left is None:
            parent.left = tree
        elif parent and parent.right is None:
            parent.right = tree
        if self.treeMaxBranches <= id[1]:
            for i in range(id[1] + 1 - self.treeMaxBranches):
                self.treeObjs.append([])
            self.treeMaxBranches = id[1] + 1
        return tree
    def RemoveTree(self, tree: Tree):
        id = tree.id
        begin = id[0] - self.treeObjs[id[1]][0].id[0]
        to_remove = set(self.treeObjs[id[1]][begin:])
        self.treeObjs[id[1]] = self.treeObjs[id[1]][:begin]
        while True:
            count = 0
            for s in self.treeObjs:
                if len(s) == 0 or (parent := s[0].parent) is None:
                    continue
                if parent in to_remove:
                    to_remove.update(self.treeObjs[s[0].id[1]])
                    self.treeObjs[s[0].id[1]] = []
                    count += 1
            if count == 0:
                break
        if tree.parent is not None:
            if tree.parent.left is self:
                tree.parent.left = tree.parent.right
            tree.parent.right = None
    def LoadLogSet(self):
        if self.logFile is not None:
            self.logFile.close()
            self.logFile = None
        d = self.getToday()
        for i in range(7):
            try:
                with open(self.treeFilePath(d), encoding='utf-8') as f:
                    for s in f.readlines():
                        ret = Tree.load(s.strip())
                        if ret is None:
                            continue
                        elif ret["type"] == "tree":
                            self.logSet[ret["word"]] = ret["qq"]
            except FileNotFoundError:
                pass
            d -= timedelta(days=1)
    def LoadTree(self):
        if self.logFile is not None:
            self.logFile.close()
            self.logFile = None
        try:
            with open(self.treeFilePath(self.getToday()), encoding='utf-8') as f:
                for s in f.readlines():
                    ret = Tree.load(s.strip())
                    if ret is None:
                        continue
                    elif ret["type"] == "fork":
                        self.FindTree(ret["id"]).fork = ret["fork"]
                    elif ret["type"] == "delete":
                        self.RemoveTree(self.FindTree(ret["id"]))
                    elif ret["type"] == "new":
                        self.InitTree(False)
                    elif ret["type"] == "tree":
                        self.AddTree(self.FindTree(ret["parentId"]), ret["word"], ret["qq"], ret["keyword"], ret["hiddenKeyword"], ret["fork"], id=ret["id"])
        except FileNotFoundError:
            pass
    def TreeActiveNodes(self, have_fork=True):
        words = [s[-1] for s in self.treeObjs if len(s) != 0 and s[-1].left is None]
        if have_fork:
            for s in self.treeObjs:
                for word in s:
                    if word.fork and word.left is not None and word.right is None:
                        words.append(word)
        return words

    def AllUserQQs(self, sqlRequirement: str="") -> list[int]:
        if sqlRequirement == "":
            l = config.userdata.execute("select qq from dragon_data where dead=false").fetchall()
        else:
            l = config.userdata.execute("select qq from dragon_data where dead=false and " + sqlRequirement).fetchall()
        return [c["qq"] for c in l]
    def RegisterEventCheckerInit(self, checker: 'IEventListener') -> None:
        for key, priority in checker.register().items():
            self.eventListenerInit[key][priority].append(checker)
    def CreateUser(self, qq: int, buf: Buffer):
        if qq == self.managerQQ:
            return User(self.me, buf, self)
        elif qq in self.userdatas:
            self.userdatas[qq].AddRef()
        else:
            ud = UserData(qq, self)
            self.userdatas[qq] = ud
        return User(self.userdatas[qq], buf, self)
    def DisposeUserData(self) -> None:
        for qq in list(self.userdatas.keys()):
            if not self.userdatas[qq].valid:
                self.userdatas.pop(qq)
    def RandomNewCards(self, user: 'User', num: int=1, requirement: Callable[[Type['Card']], bool]=None) -> List['Card']:
        cards = [c for c in Card.idDict.values() if requirement and requirement(c)]
        packs = Sign(self.state.get("sign", 0)).pack()
        weights = [(c.weight(user) if callable(c.weight) else c.weight) + (4 if c.pack in packs else 0) for c in cards]
        l = random.choices(cards, weights, k=num)
        l2: List[Card] = []
        for c in l:
            l2.append(c())
        return l2
    def SaveState(self):
        with open(config.rel('dragon_state.json'), 'w', encoding='utf-8') as f:
            json.dump(self.state, f, ensure_ascii=False, indent=4, sort_keys=True)

    async def Process(self, request: ProtocolData, buf: Buffer) -> ProtocolData:
        typ = request.get("type")
        qq = request.get("qq")
        if typ is None or qq is None or not isinstance(typ, str) or not isinstance(qq, int):
            return {"type": "failed", "error_code": 1}
        user = self.CreateUser(qq, buf)
        match typ:
            case "construct":
                id = request.get("node_id")
                word = request.get("word")
                if id is None or word is None or not isinstance(id, str) or not isinstance(word, str):
                    return {"type": "failed", "error_code": 1}
                
                return await self.UserPerformDragon(user, id, word)

            case "use_card":
                id = request.get("id")
                data = request.get("data", "")
                if id is None or not isinstance(id, int) or not isinstance(data, str):
                    return {"type": "failed", "error_code": 1}
                l = [c for c in user.data.handCard if c.id == id and c.packData() == data]
                if len(l) == 0:
                    return {"type": "failed", "error_code": 200}
                
                return await self.UserUseCard(user, l[0])
            
            case "use_equipment":
                id = request.get("id")
                if id is None or not isinstance(id, int):
                    return {"type": "failed", "error_code": 1}
                
                return await self.UserUseEquipment(user, id)

            case "use":
                pass # TODO

            case "draw":
                num = request.get("num")
                if num is None:
                    num = 1
                if not isinstance(num, int):
                    return {"type": "failed", "error_code": 1}

                return await self.UserDrawCards(user, num)

            case "discard":
                cards = request.get("cards")
                if cards is None or not isinstance(cards, list) or not all(isinstance(c, dict) for c in cards):
                    return {"type": "failed", "error_code": 1}
                handCardWithData = [(c.id, c.packData()) for c in user.data.handCard]
                handCards: list[Card] = []
                for c in cards:
                    te = c.get("id"), c.get("data", "")
                    if te[0] is None or not isinstance(te[0], int) or not isinstance(te[1], str):
                        return {"type": "failed", "error_code": 1}
                    if te not in handCardWithData:
                        return {"type": "failed", "error_code": 500}
                    handCards.append(user.data.handCard[handCardWithData.index(te)])

                return await self.UserDiscardCards(user, handCards)
            
            case "check":
                return await self.UserCheckData(user, request)
            
            case "buy" | "buy_event":
                return await self.UserBuyItem(user, request)
            
            case "fork":
                id = request.get("node_id")
                if id is None or not isinstance(id, str):
                    return {"type": "failed", "error_code": 1}
                return await self.UserFork(user, id)
            
            case "add_begin":
                pass # TODO
            
            case "add_keyword":
                pass # TODO
            
            case "add_hidden":
                pass # TODO
            
            case "compensate":
                pass # TODO
            
            case "kill":
                pass # TODO

            case "choose" | _:
                return {"type": "failed", "error_code": 1}

    async def UserPerformDragon(self, user: 'User', parentIdStr: str, word: str) -> ProtocolData:
        user.log.verbose << f"尝试接龙，父节点{parentIdStr}，接龙词{word}。"
        parentId = Tree.strToId(parentIdStr)
        if parentId is None:
            return {"type": "failed", "error_code": 100}
        if len(user.data.handCard) > user.data.cardLimit:
            return {"type": "failed", "error_code": 190}
        if not (parent := self.FindTree(parentId)):
            return {"type": "failed", "error_code": 100}
        if parent.right is not None:
            return {"type": "failed", "error_code": 101}
        if parent.left is not None and not parent.fork:
            return {"type": "failed", "error_code": 102}

        word = unicodedata.normalize("NFC", word)
        if any(unicodedata.category(c) == "Cc" for c in word):
            return {"type": "failed", "error_code": 110}

        dist = 2
        dragonState = DragonState(word, parent)
        # Event BeforeDragoned
        user.Send(type="begin", name="BeforeDragoned")
        for eln in user.IterAllEvent(UserEvt.BeforeDragoned):
            allowed, dist_mod = await eln.BeforeDragoned(user, dragonState)
            if not allowed:
                return {"type": "failed", "error_code": 121}
            dist += dist_mod
        user.Send(type="end", name="BeforeDragoned")
        
        dist = max(dist, 1)
        if user.qq in parent.getParentQQList(dist):
            # Event CheckSuguri
            user.Send(type="begin", name="CheckSuguri")
            for eln in user.IterAllEvent(UserEvt.CheckSuguri):
                allowed = await eln.CheckSuguri(user, dragonState)
                if allowed:
                    break
            else:
                return {"type": "failed", "error_code": 120}
            user.Send(type="end", name="CheckSuguri")
        word = dragonState.word
        kwd = hdkwd = ""

        # 检测奖励词
        if word == self.keyword:
            kwd = self.keyword
            jibiToAdd = 0
            if user.data.todayKeywordJibi > 0:
                user.data.todayKeywordJibi -= 10
                jibiToAdd = 10
            # Event OnKeyword
            user.Send(type="begin", name="OnKeyword")
            for eln in user.IterAllEvent(UserEvt.OnKeyword):
                jibi = await eln.OnKeyword(user, word, parent, kwd)
                jibiToAdd += jibi
            user.Send(type="OnKeyword", keyword=kwd, jibi=jibiToAdd, left=user.data.todayKeywordJibi)
            await user.AddJibi(jibiToAdd)
            ret = self.UpdateKeyword(if_delete=True)
            user.Send(ret)

        # 检测隐藏奖励词
        for i, k in enumerate(self.hiddenKeyword):
            if k in word:
                hdkwd = k
                jibiToAdd = 10
                # Event OnHiddenKeyword
                user.Send(type="begin", name="OnHiddenKeyword")
                for eln in user.IterAllEvent(UserEvt.OnHiddenKeyword):
                    jibi = await eln.OnHiddenKeyword(user, word, parent, hdkwd)
                    jibiToAdd += jibi
                user.Send(type="OnHiddenKeyword", keyword=kwd, jibi=jibiToAdd)
                await user.AddJibi(jibiToAdd)
                ret = self.UpdateHiddenKeyword(i, True)
                user.Send(ret)
                break
        
        # 检测重复词
        if word in self.logSet:
            # Event OnDuplicatedWord
            user.Send(type="begin", name="OnDuplicatedWord")
            for eln in user.IterAllEvent(UserEvt.OnDuplicatedWord):
                dodged = await eln.OnDuplicatedWord(user, word, self.logSet[word])
                if dodged:
                    break
            else:
                await user.Death()
            user.Send(type="OnDuplicatedWord", word=word)
        
        # 创建节点
        tree = self.AddTree(parent, word, user.qq, kwd, hdkwd)
        # 添加到log里
        self.logSet[word] = user.qq
        self.logFile.write(str(tree) + '\n')    # type: ignore
        self.logFile.flush()                    # type: ignore
        user.data.lastDragonTime = datetime.now().isoformat()
        if first10 := user.data.todayJibi > 0:
            user.data.todayJibi -= 1
            await user.AddJibi(1)
            if user.data.todayJibi == 9:
                user.data.drawTime += 1
        
        # 结算炸弹
        if word in self.bombs:
            self.RemoveBomb(word)
            # Event OnBombed
            user.Send(type="begin", name="OnBombed")
            for eln in user.IterAllEvent(UserEvt.OnBombed):
                dodged = await eln.OnBombed(user, word)
                if dodged:
                    break
            else:
                await user.Death()
            user.Send(type="OnBombed", word=word)
        
        # 泳装活动
        # if self.state.get("current_event") == "swim" and first10:
        #     n = random.randint(1, 6)
        #     await user.EventMove(n)
        
        # Event OnDragoned
        user.Send(type="begin", name="OnDragoned")
        for eln in user.IterAllEvent(UserEvt.OnDragoned):
            await eln.OnDragoned(user, tree, first10)
        user.Send(type="OnDragoned", father_node_id=parent.idStr, node_id=tree.idStr, word=word)
        
        # 增加麻将券
        user.data.majQuan += 1
        if user.data.majQuan % 3 == 0:
            from .AllItems import MajQuan
            user.Send({"type": "get_item", "count": 1, "item": MajQuan().DumpData()})
        return {"type": "succeed"}
    async def UserUseCard(self, user: 'User', card: Card) -> ProtocolData:
        if len(user.data.handCard) > user.data.cardLimit:
            user.state['exceed_limit'] = True
        
        # Event OnUserUseCard
        user.Send(type="begin", name="OnUserUseCard")
        for el in user.IterAllEvent(UserEvt.OnUserUseCard):
            can_use = await el.OnUserUseCard(user, card)
            if not can_use:
                return {"type": "failed", "error_code": 202}
        if not card.CanUse(user, False):
            return {"type": "failed", "error_code": 202}
        user.Send(type="end", name="OnUserUseCard")

        await user.UseCard(card)
        user.data.majQuan += 1
        if user.data.majQuan % 3 == 0:
            from .AllItems import MajQuan
            user.Send({"type": "get_item", "count": 1, "item": MajQuan().DumpData()})
        await user.HandleExceedDiscard()

        self.state["last_card_user"] = user.qq
        return {"type": "succeed"}
    async def UserDiscardCards(self, user: 'User', cards: list[Card]) -> ProtocolData:
        if len(user.data.handCard) <= user.data.cardLimit:
            return {"type": "failed", "error_code": 510}
        if not all(c.CanDiscard(user) for c in cards):
            return {"type": "failed", "error_code": 502}
        user.state['exceed_limit'] = True

        await user.DiscardCards(cards)
        await user.HandleExceedDiscard()
        return {"type": "succeed"}
    async def UserDrawCards(self, user: 'User', num: int) -> ProtocolData:
        if len(user.data.handCard) > user.data.cardLimit:
            return {"type": "failed", "error_code": 390}
        if user.data.drawTime < num:
            return {"type": "failed", "error_code": 300}
        
        user.data.drawTime -= num
        await user.Draw(num)
        await user.HandleExceedDiscard()
        return {"type": "succeed"}
    async def UserCheckData(self, user: 'User', request: ProtocolData) -> ProtocolData:
        if request.get("type") != "check":
            return {"type": "failed", "error_code": -1, "error_msg": "type is not check in calling UserCheckData"}
        d = self.LoadDragonWords()
        ret = copy(request)
        match request["arg"]:
            case "keyword_pool":
                ret["pool"] = len(d['keyword'][1])
            case "begin_pool":
                ret["pool"] = len(d['begin'])
            case "hidden_keyword_pool":
                ret["pool"] = len(d["hidden"][1])
            case "card_pool":
                ret["pool"] = len(Card.idDict)
            case "keyword":
                ret["keyword"] = self.keyword
            case "active":
                pass # TODO
            case "profile":
                ret["jibi_time"] = user.data.todayJibi
                ret["keyword_jibi"] = user.data.todayKeywordJibi
                ret["draw_time"] = user.data.drawTime
                ret["card_limit"] = user.data.cardLimit
                ret["shop_card"] = user.data.shopDrawnCard
            case "global_profile":
                ret["sign"] = Sign(self.state["sign"]).DumpData()
            case "hand_cards":
                ret["cards"] = [c.DumpData() for c in user.data.handCard]
            case "status":
                ret["status"] = [c.DumpData() for c in user.data.statuses]
            case "global_status":
                ret["status"] = [c.DumpData() for c in self.me.statuses]
            case "equipments":
                ret["equipments"] = [c.DumpData() for c in user.data.equipments]
            case "useable_items":
                pass # TODO
            case "quests":
                pass # TODO
            case "maj":
                pass # TODO
            case "jibi":
                ret["jibi"] = user.data.jibi
            case "shop":
                pass # TODO
            case "bingo":
                pass # TODO
            case _:
                return {"type": "failed", "error_code": 700}
        return ret
    async def UserBuyItem(self, user: 'User', request: ProtocolData) -> ProtocolData:
        match request.get("type"):
            case "buy":
                item: Type[Item] | None = JibiShopItem.idDict.get(request.get("id")) # type: ignore[arg-type]
                if item is None:
                    return {"type": "failed", "error_code": 400}
            case "buy_event":
                item = EventShopItem.idDict.get(request.get("id")) # type: ignore[arg-type]
                if item is None:
                    return {"type": "failed", "error_code": 400}
            case _:
                return {"type": "failed", "error_code": -1, "error_msg": "type not starts with buy in calling UserBuyItem"}
        t = item()
        ret = await t.HandleCost(user)
        if ret.get("type") == "succeed":
            await t.Use(user)
            return {"type": "succeed"}
        return ret
    async def UserUseEquipment(self, user: 'User', equipmentId: int) -> ProtocolData:
        if len(user.data.handCard) > user.data.cardLimit:
            return {"type": "failed", "error_code": 390}
        if equipmentId not in Equipment.idDict:
            return {"type": "failed", "error_code": 210}
        equipment = user.data.CheckEquipment(Equipment.get(equipmentId))
        if equipment is None:
            return {"type": "failed", "error_code": 211}
        if not equipment.canUse(user):
            return {"type": "failed", "error_code": 212}
        
        await user.UseEquipment(equipment)
        await user.HandleExceedDiscard()
        return {"type": "succeed"}
    async def UserUseItem(self, user: 'User', itemName: int) -> ProtocolData:
        pass
    async def UserFork(self, user: 'User', nodeIdStr: str) -> ProtocolData:
        pass

