from typing import *
import re

class DragonState:
    pass

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
    @classmethod
    def strToId(cls, str):
        match = re.match(r'(\d+)([a-z])?', str)
        return cls.matchToId(match)
    @classmethod
    def matchToId(cls, match: re.Match):
        return int(match.group(1)), (0 if match.group(2) is None else ord(match.group(2)) - 96)
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