import itertools, math, sys, more_itertools
from collections import defaultdict
from dataclasses import dataclass
from copy import deepcopy, copy

err = 0.00000001
prec = defaultdict(lambda: 99, {'+': 0, '-': 0, 'm': 1, '*': 2, '/': 2, '^': 3, 'c': -1, '.': -1})
form = {'m': '-{}', 'f': '{}!', 's': '√{}', 'r': '{1}√{0}'}
@dataclass
class Number:
    num: float | int
    native: bool
    prt: str
    represent: str
    precedence: int = -1
    def isint(self):
        if isinstance(self.num, int):
            return True
        if math.fabs(self.num - round(self.num)) < err:
            self.num = round(self.num)
            return True
        return False
    def op2(self, other: 'Number', op):
        num = other.num
        match op:
            case '+':
                self.num += num
            case '-':
                self.num -= num
            case '*':
                self.num *= num
            case '/':
                self.num /= num
                if 0 < self.num < err:
                    raise ValueError
            case '^':
                # if num == -0.5 and self.num == 0.01:
                #     print(self.prt, other.prt)
                if other.isint():
                    if 0 <= num < 1000:
                        self.num **= num
                    else:
                        raise ValueError
                elif not (math.fabs(num * 2520 - round(num * 2520)) < err and -24 < (num if self.num < 1 else -num) <= 10):
                    raise ValueError
                else:
                    self.num **= num
                if 0 < self.num < err:
                    raise ValueError
            case 'r':
                if not math.fabs(2520 / num - round(2520 / num)) < err or num > 24 or 1 / num > 100:
                    raise ValueError
                self.num **= 1 / num
                if 0 < self.num < err:
                    raise ValueError
            case 'c':
                if not other.native or not self.native:
                    raise ValueError
                if self.num == 0 and not other.isint():
                    self.num = other.num / 10
                elif not self.isint() or not other.isint():
                    raise ValueError
                else:
                    self.num = self.num * 10 ** len(str(num)) + num
            case _:
                raise ValueError
        if isinstance(self.num, complex):
            raise ValueError
        if op == 'c':
            self.prt = str(self.num)
        else:
            self.native = False
            if (prec[op] == 99 or self.precedence < prec[op]) and self.precedence != -1 or op == '^' and self.precedence == prec[op]:
                self.prt = '({})'.format(self.prt)
            if (prec[op] == 99 or other.precedence < prec[op]) and other.precedence != -1 or op != '^' and other.precedence == prec[op]:
                otp = '({})'.format(other.prt)
            else:
                otp = other.prt
            if op in '+-*/^':
                self.prt = '{}{}{}'.format(self.prt, op, otp)
            else:
                self.prt = form[op].format(self.prt, otp)
        if math.isinf(self.num):
            raise ValueError
        self.precedence = prec[op]
        self.represent = self.represent + other.represent + op
        return self
    def op1(self, op):
        match op:
            case 's':
                self.num **= 0.5
            case 'm':
                self.num = -self.num
            case '.':
                if not self.native or not self.isint():
                    raise ValueError
                self.num = self.num / 10 ** len(str(self.num))
                if 0 < self.num < err:
                    raise ValueError
            case 'f':
                if not self.isint() or not 0 <= self.num <= 25:
                    raise ValueError
                self.num = math.factorial(round(self.num))
        if math.isinf(self.num):
            raise ValueError
        if op == '.':
            self.prt = str(self.num)
        else:
            self.native = False
            if (prec[op] == 99 or self.precedence < prec[op]) and self.precedence != -1 and not (self.precedence == 99 and (self.prt.startswith('√') and op == 's' or self.prt.startswith('!') and op == 'f')):
                self.prt = '({})'.format(self.prt)
            self.prt = form[op].format(self.prt)
        self.precedence = prec[op]
        self.represent = self.represent + op
        return self
    def __eq__(self, other) -> bool:
        return self is other

def calculate(s: str):
    stack: list[Number] = []
    for c in s:
        if c in '0123456789':
            stack.append(Number(int(c), True, c, c))
        elif c in 'sm.f':
            stack.append(stack.pop().op1(c))
        elif c in '+-*/^rc':
            a = stack.pop()
            stack.append(stack.pop().op2(a, c))
    if len(stack) != 1:
        raise ValueError
    stack[0].isint()
    return stack[0]

ls = [''.join(s) for s in itertools.chain(*[itertools.product('sf', repeat=i) for i in range(5)])]
def cal(ip):
    cc = 0
    l: list[list[Number]] = [[Number(int(c), True, c, c) for c in ip]]
    newl: list[list[Number]] = []
    trylists: list[list[Number]] = []
    newnum: list[Number] = [i for i in l[0]]
    newnewnum: list[Number] = []
    result: list[Number] = []
    ll = len(l[0])
    ret2 = l[0][0]
    for _r in range(ll):
        prelast = _r == ll - 2
        last = _r == ll - 1
        print("---updating trylist---")
        print('{}/{}'.format(len(trylists), len(newnum)))
        # print(newnum)
        for ni in range(len(trylists), len(newnum)):
            if ni % 10000 == 0:
                print(f"{ni}/{len(newnum)}")
            num = newnum[ni]
            trylist: list[Number] = []
            if num.prt == '0.01^(-0.5)':
                print(num)
            if not (ni2 := num.isint()) and last:
                continue
            n = num.native and ni2
            for xd in range(2 if n else 1):
                if n and xd == 1:
                    if num.num == 0:
                        continue
                    try:
                        ret2 = copy(num).op1('.')
                    except Exception:
                        continue
                ret0 = copy((num, ret2)[xd])
                if ret0.num < 0:
                    if last:
                        result.append(ret0)
                    else:
                        trylist.append(ret0)
                    ret0 = copy(ret0).op1('m')
                for li in ls:
                    bk = False
                    ret = copy(ret0)
                    for t in li:
                        if ret.num in (1, 2) and t == 'f' or ret.num in (0, 1) and t == 's' or ret.num >= 1000000:
                            bk = True
                            break
                        try:
                            ret = ret.op1(t)
                        except Exception:
                            bk = True
                            break
                    if not bk:
                        if last:
                            result.append(ret)
                        else:
                            trylist.append(ret)
                        ret = copy(ret).op1('m')
                        if last:
                            result.append(ret)
                        else:
                            trylist.append(ret)
            if not last:
                trylists.append(trylist)
        if last:
            break
        print("---calculating op2---")
        al = len(l) * 12 * len(l[0]) * (len(l[0]) - 1) // 2
        print(al)
        print(sum(len(x) for x in trylists) / len(trylists))
        ci = 0
        for i in l:
            for c in itertools.product('+-*/^rc', 'lr'):
                if c[1] == 'r' and c[0] in '+*':
                    continue
                for d in itertools.combinations(i, 2):
                    ci += 1
                    if ci % 10000 == 0:
                        print(f"{ci}/{al}")
                    e = [[x] if x not in newnum else trylists[newnum.index(x)] for x in d]
                    for g in itertools.product(*e):
                        if c[0] in '+-*/' and (g[1] if c[1] == 'r' else g[0]).prt[0] == '-':
                            continue
                        try:
                            if c[1] == 'r':
                                r = copy(g[0]).op2(g[1], c[0])
                            else:
                                r = copy(g[1]).op2(g[0], c[0])
                        except Exception:
                            continue
                        # if (d[0].num, d[1].num) in ((5, 0.01), (0.01, 5)) and c[0] == '^' and r.num == 10:
                        #     print(r)
                        i2 = [ic for ic in i if ic not in d]
                        i2.append(r)
                        newl.append(i2)
                        newnewnum.append(r)
                        # if (lll := more_itertools.first((x for x in newnewnum if x.num == r.num), default=None)) is None:
                        #     newnewnum.append(r)
                        # elif len(lll.prt) > len(r.prt):
                        #     newnewnum.remove(lll)
                        #     newnewnum.append(r)
        l = newl
        newl = []
        # if prelast:
        #     newnum += newnewnum
        #     newnewnum = []
        # else:
        saved: dict[float | int, Number] = {}
        for r in newnewnum:
            if r.num not in saved or len(saved[r.num].represent) > len(r.represent):
                saved[r.num] = r
        newnum += list(saved.values())
        newnewnum = []
    out: dict[int, list[Number]] = defaultdict(lambda: [], {})
    for ret in result:
        if not (ret.isint() and 0 <= ret.num < 100000):
            continue
        out[int(ret.num)].append(ret)
    with open(f"E:\\【S】Undergraduate\\pyworkspace\\24p_save\\{ip}.txt", 'w', encoding='utf-8') as f:
        # for nm in sorted(out):
        #     out[nm].sort(key=lambda x: len(x.represent))
        #     f.write(f'{nm} {out[nm][0].prt}\t\t{out[nm][0].represent}\n')
        # f.write('\n')
        for nm in sorted(out):
            out[nm].sort(key=lambda x: len(x.represent))
            lm = len(out[nm][0].represent)
            for ret in out[nm]:
                if len(ret.represent) > lm:
                    break
                f.write(f'{nm} {ret.prt}\t\t{ret.represent}\n')

if __name__ == '__main__':
    # cal('015')
    for ip in itertools.combinations_with_replacement('0123456789', 3):
        print("---begin---")
        print("【" + ''.join(ip) + "】")
        cal(''.join(ip))