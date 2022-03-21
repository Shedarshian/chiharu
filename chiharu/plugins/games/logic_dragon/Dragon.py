from typing import *
import re
from .Types import ProtocolData

class DragonState:
    def __init__(self, word: str, parent: 'Tree'):
        self.word = word
        self.parent = parent
        self.shouwei = parent.word == '' or word == '' or parent.word[-1] == word[0]
        self.weishou = parent.word == '' or word == '' or parent.word[0] == word[-1]
    async def OnShouWei(self, user): # changable in card USB Type-A
        pass
    async def OnWeiShou(self, user): # changable in card USB Type-A
        pass
    async def RequireShouwei(self, user):
        await self.OnShouWei(user)
        return self.shouwei
    async def RequireWeishou(self, user):
        await self.OnWeiShou(user)
        return self.weishou

class Tree:
    __slots__ = ('id', 'parent', 'left', 'right', 'word', 'fork', 'kwd', 'hdkwd', 'qq')
    def __init__(self, parent: 'Tree', word: str, qq: int, kwd: str, hdkwd: str, id: Tuple[int, int], fork: bool=False):
        self.parent = parent
        self.id = id
        self.left = None
        self.right = None
        self.word = word
        self.fork = fork
        self.qq = qq
        self.kwd = kwd
        self.hdkwd = hdkwd
    @property
    def idStr(self):
        return str(self.id[0]) + ('' if self.id[1] == 0 else chr(96 + self.id[1]))
    id_re = re.compile(r"(\d+)([a-z]*)")
    @classmethod
    def strToId(cls, s):
        match = cls.id_re.match(s)
        return cls.matchToId(match)
    @classmethod
    def matchToId(cls, match: re.Match):
        t = 0
        for c in match.group(2):
            t = t * 26 + ord(c) - 96
        return int(match.group(1)), t
    def __repr__(self):
        return f"<id: {self.id}, parent_id: {'None' if self.parent is None else self.parent.id}, word: \"{self.word}\">"
    def __str__(self):
        return f"{self.idStr}{'+' if self.fork else ''}<{'-1' if self.parent is None else self.parent.idStr}/{self.qq}/{self.kwd}/{self.hdkwd}/ {self.word}"
    def before(self, n):
        node = self
        for i in range(n):
            node = node and node.parent
        return node
    def getParentQQList(self, n: int):
        parent_qqs: List[int] = []
        begin = self
        for j in range(n):
            parent_qqs.append(begin.qq)
            begin = begin.parent
            if begin is None:
                break
        return parent_qqs
    @classmethod
    def saveFork(cls, node: 'Tree'):
        return f"/fork/" + node.idStr + ('+' if node.fork else '-')
    @classmethod
    def saveDelete(cls, node: 'Tree'):
        return f"/delete/" + node.idStr
    @classmethod
    def saveNew(cls):
        return f"/new/"
    command_re = re.compile(r"/(fork)/(\d+[a-z]*)(\+|-)|/(delete)/(\d+[a-z]*)|/(new)/")
    tree_re = re.compile(r"(?:(\d+[a-z]*)(?:(\+)?<(-?\d+[a-z]*))?(?:/(\d+)/([^/]*)/([^/]*)/)?) (.*)")
    @classmethod
    def load(cls, s: str):
        match = cls.command_re.match(s)
        if match:
            if match.group(1) is not None:
                return {"type": "fork", "id": Tree.strToId(match.group(2)), "fork": match.group(3) == '+'}
            elif match.group(2) is not None:
                return {"type": "delete", "id": Tree.strToId(match.group(2))}
            else:
                return {"type": "new"}
        match2 = cls.tree_re.match(s)
        if match2:
            return {"type": "tree", "id": Tree.strToId(match2.group(1)), "fork": match2.group(2) == "+",
                "parentId": Tree.strToId(match2.group(3)),
                "qq": int(match2.group(4)), "keyword": match2.group(5), "hiddenKeyword": match2.group(6),
                "word": match2.group(7)}
        return None
        

