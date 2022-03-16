from io import TextIOWrapper
from typing import *
from collections import defaultdict
from contextlib import contextmanager
import random, json
from datetime import date, datetime, time, timedelta
from .User import User
from .UserData import UserData
from .Dragon import Tree, DragonState, TreeEncoder
from .Types import TEvent, TGlobalState, Sign, ProtocolData, TWords
from .Helper import Buffer
from .Priority import UserEvt
from .EventListener import IEventListener
from .Card import Card
from ... import config

version = "0.4.0"
changelog = """0.4.0 Changelog:
Change:
再次重构。引入大量新bug。"""

class Game:
    def __init__(self) -> None:
        self.treeForests: List[List[List['Tree']]] = []
        self.treeObjs: List[List['Tree']] = []
        self.treeMaxBranches = 0
        self.InitTree(True)
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
        def _(dt: date):
            return config.rel(rf'log\dragon_log_{dt.isoformat()}.txt')
        self.treeFilePath = _
        self.logSet: dict[str, int] = {}
        self.logFile: Optional[TextIOWrapper] = None
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

    @contextmanager
    def UpdateDragonWords(self):
        with open(config.rel('dragon_words.json'), encoding='utf-8') as f:
            d: TWords = json.load(f)
        yield d
        with open(config.rel('dragon_words.json'), 'w', encoding='utf-8') as f:
            f.write(json.dumps(d, indent=4, ensure_ascii=False))
    def UpdateKeyword(self, if_delete=False) -> ProtocolData:
        with self.UpdateDragonWords() as d:
            s = set(d['keyword'][1]) - self.logSet - set(self.bombs)
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

    def InitTree(self, is_daily: bool):
        if is_daily:
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
            # TODO 额外判断有多个parents的节点
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

    def RegisterEventCheckerInit(self, checker: 'IEventListener') -> None:
        for key, priority in checker.register():
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

    async def PerformDragon(self, user: 'User', parentId: tuple[int, int], word: str) -> ProtocolData:
        user.log.verbose << f"尝试接龙，父节点{parentId}，接龙词{word}。"
        if len(user.data.handCard) > user.data.cardLimit:
            return {"type": "failed", "error_code": 190}
        if not (parent := self.FindTree(parentId)):
            return {"type": "failed", "error_code": 100}
        if parent.right is not None:
            return {"type": "failed", "error_code": 101}
        if parent.left is not None and not parent.fork:
            return {"type": "failed", "error_code": 102}

        # TODO 检测接龙词是否包含不合法字符

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
            user.Send(type="OnDuplicatedWord", word=word})
        
        # 创建节点
        tree = self.AddTree(parent, word, user.qq, kwd, hdkwd)
        # 添加到log里
        self.logSet[word] = user.qq
        self.logFile.write(str(tree) + '\n')
        self.logFile.flush()
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
        user.Send(type="OnDragoned", father_node_id=parent.idStr, node_id=tree.idStr, word=word})
        
        # 增加麻将券
        user.data.majQuan += 1

        return {"type": "succeed"}
    async def UserUseCard(self, user: 'User', cardPos: int, cardId: int) -> ProtocolData:
        card = user.data.handCard[cardPos]
        if card.id != cardId:
            return {"type": "failed", "error_code": 200}
        
        if len(user.data.handCard) > user.data.cardLimit:
            user.state['exceed_limit'] = True
        
        # Event OnUserUseCard
        user.buf.PushBuffer()
        for el in user.IterAllEvent(UserEvt.OnUserUseCard):
            can_use = await el.OnUserUseCard(user, card)
            if not can_use:
                return {"type": "failed", "error_code": 202}

