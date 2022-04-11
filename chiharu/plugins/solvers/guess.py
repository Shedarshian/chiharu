import itertools
import more_itertools
import json
from copy import copy, deepcopy
from typing import Tuple

def test(p: Tuple[int, ...], q: Tuple[int, ...]) -> Tuple[int, int]:
    b = len(set(p) & set(q))
    a = len([0 for i, j in zip(p, q) if i == j])
    return (a, b - a)

class Status:
    def __init__(self, base=10, num=4):
        assert(base ** num <= 16777216)
        self.base = base
        self.num = num
        self.same = [set(range(base))]
        self.history = []
        self.same_stack = []
    def set(self, p: Tuple[int, ...], result: Tuple[int, int]):
        self.same_stack.append(deepcopy(self.same))
        self.history.append((p, result))
        same2 = []
        if len(self.same) == 1 and self.base != self.num:
            self.same = [set(p), self.same[0] - set(p)]
        else:
            if len(self.same) == 2:
                self.same = [{x} for x in self.same[0]] + self.same[1:]
            self.same[-1] -= set(p)
            self.same = [{x} for x in p] + self.same
            self.same = [s for s in self.same if len(s) != 0]
            self.same.sort(key=min)
            self.same = list(more_itertools.unique_justseen(self.same))
    def unset(self):
        self.same = self.same_stack.pop()
        self.history.pop()
    def space_gen(self):
        if len(self.history) == 0:
            self.space = list(itertools.permutations(range(self.base), self.num))
        else:
            self.space = [t for t in itertools.permutations(range(self.base), self.num)
                if all(
                    [result == test(p, t) for p, result in self.history])]
    def all(self):
        if len(self.same) == self.base:
            yield from itertools.permutations(range(self.base), self.num)
        else:
            for t in itertools.product(range(len(self.same)), repeat=self.num):
                if all([len([0 for j in t if i == j]) <= len(self.same[i])
                    for i in set(t)]):
                    t2 = []
                    for i in t:
                        j = copy(self.same[i])
                        while len(j):
                            if min(j) not in t2:
                                t2.append(min(j))
                                break
                            j.remove(min(j))
                    yield tuple(t2)
    def check(self, strategy=0):
        # 0: 最坏情况候选项最少
        # 1: 总情况数最多
        m = ([], -1 if strategy==1 else len(self.space))
        if strategy == 0:
            for t in self.all():
                d = {}
                for p in self.space:
                    res = test(t, p)
                    if res not in d:
                        d[res] = 1
                    else:
                        d[res] += 1
                s = max(d.items(), key=lambda x: x[1])[1]
                if s < m[1]:
                    m = ([t], s)
                elif s == m[1]:
                    m[0].append(t)
        elif strategy == 1:
            for t in self.all():
                s = len(self.valid_result(t))
                if s > m[1]:
                    m = ([t], s)
                elif s == m[1]:
                    m[0].append(t)
        return m
    def all_result(self):
        for a in range(self.num + 1):
            for b in range(self.num - a + 1):
                if a + b >= 2 * self.num - self.base and (a, b) != (self.num - 1, 1):
                    yield (a, b)
    def valid_result(self, t: Tuple[int, ...]):
        return set(test(t, p) for p in self.space)
    def tree(self, max=10, strategy=0):
        assert(len(self.history) == 0)
        self.space_gen()
        todo = [((0, 1, 2, 3), list(self.valid_result((0, 1, 2, 3))), 0)]
        tree = [{'id': 0, 'history': [], 'space_len': len(self.space), 'do': (0, 1, 2, 3), 'results': {}}]
        # {'id': int, 'history': list, 'space_len': int, 'do': list, 'results': dict, 'success': tuple}
        max_id = 1
        print('todo {}'.format((0, 1, 2, 3)))
        while len(todo):
            if len(todo[-1][1]) == 0:
                # 回溯
                todo.pop()
                if len(self.history) == 0:
                    return tree
                self.unset()
            else:
                r = todo[-1]
                t = r[0]
                res = r[1].pop(0)
                self.set(t, res)
                self.space_gen()
                if len(self.space) == 1:
                    # 结束
                    tree.append({'id': max_id, 'history': deepcopy(self.history), 'space_len': len(self.space), 'success': self.space[0]})
                    print('{} success'.format(self.history))
                    self.unset()
                else:
                    m = self.check(strategy)
                    s2 = set(m[0]) & set(self.space)
                    if len(s2) != 0:
                        m2 = min(s2)
                    else:
                        m2 = m[0][0]
                    if len(self.history) <= max:
                        todo.append((m2, list(self.valid_result(m2)), max_id))
                    else:
                        todo.append((m2, [], max_id))
                    tree.append({'id': max_id, 'history': deepcopy(self.history), 'space_len': len(self.space), 'do': m2, 'results': {}})
                    print('{} todo'.format(self.history))
                tree[r[2]]['results'][str(res)] = max_id
                max_id += 1

if __name__ == '__main__':
    # s = Status()
    # with open('result.json', 'w', encoding='utf-8') as f:
    #     f.write(json.dumps(s.tree(), indent=4, separators=(',', ': ')))
    with open('result.json', encoding='utf-8') as f:
        result = json.load(f)
    