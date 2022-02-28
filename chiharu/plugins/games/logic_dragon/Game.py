from typing import *
from collections import defaultdict
from .User import User
from .UserData import UserData
from .Dragon import Tree
from .Types import TEvent
from .Helper import Session
from ... import config
if TYPE_CHECKING:
    from .EventListener import IEventListener

class Game:
    def __init__(self) -> None:
        self.initTree(True)
        self.managerQQ = config.selfqq
        self.me = UserData(self.managerQQ, self)
        self.eventListenerInit: defaultdict[int, TEvent] = defaultdict(lambda: defaultdict(list))
        self.userdatas: Dict[int, 'UserData'] = {}
    def initTree(self, is_daily: bool):
        if is_daily:
            self.treeForests: List[List[List['Tree']]] = []
        self.treeObjs: List[List['Tree']] = [] # [[wd0, wd1, wd2], [wd2a], [wd2b]]
        self.treeMaxBranches = 0
    def FindTree(self, id: Tuple[int, int]):
        try:
            if len(self.treeObjs[id[1]]) == 0:
                return None
            return self.treeObjs[id[1]][id[0] - self.treeObjs[id[1]][0].id[0]]
        except IndexError:
            return None
    def AddTree(self, parent: Optional[Tree], word: str, qq: int, kwd: str, hdkwd: str):
        if parent:
            id = (parent.id[0] + 1, parent.id[1])
        else:
            id = (0, 0)
        if self.FindTree(id):
            id = (id[0], self.treeMaxBranches)
            if parent:
                parent.fork = True
        tree = Tree(parent, word, qq, kwd, hdkwd, id=id)
        if parent and parent.left is None:
            parent.left = tree
        elif parent and parent.right is None:
            parent.right = tree
        if self.treeMaxBranches <= id[1]:
            for i in range(id[1] + 1 - self.treeMaxBranches):
                self.treeObjs.append([])
            self.treeMaxBranches = id[1] + 1
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
    def CreateUser(self, qq: int, buf: Session):
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
