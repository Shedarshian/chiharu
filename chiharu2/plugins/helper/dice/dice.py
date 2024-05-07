import random
import re
import math
import ply.lex as lex, ply.yacc as yacc

tokens = ('NUMBER', 'EOF')
literals = '+-*()d$'

class ParserError(Exception):
    pass
class ProxyLexer(object):
    def __init__(self, lexer, eoftoken):
        self.end = False
        self.lexer = lexer
        self.eof = eoftoken
    def token(self):
        tok = self.lexer.token()
        if tok is None:
            if self.end :
                self.end = False
            else:
                self.end = True
                tok = lex.LexToken()
                tok.type = self.eof
                tok.value = None
                tok.lexpos = self.lexer.lexpos
                tok.lineno = self.lexer.lineno
        return tok
    def __getattr__(self, name):
        return getattr(self.lexer, name)

# from ..function import ProxyLexer, ParserError
def ExpressionLexer():
    # t_DEFINE = ':='
    t_ignore = ' \t'
    def t_NUMBER(t):
        r'\d+'
        t.value = int(t.value)
        return t
    def t_newline(t):
        r'\n+'
        t.lexer.lineno += len(t.value)
    def t_error(t):
        raise ParserError('Illegal character ' + t.value)
    return lex.lex()
lexer = ProxyLexer(ExpressionLexer(), 'EOF')

class DiceTree:
    precedence = {"+": 0, "-": 0, "*": 1, "d": 2, "--": 3}
    def __init__(self, token: str, left: 'DiceTree | int | None', right: 'DiceTree | int | None') -> None:
        self.token = token
        self.left = left
        self.right = right
        left_depth = left.depth if isinstance(left, DiceTree) else 0
        right_depth = right.depth if isinstance(right, DiceTree) else 0
        self.depth: int = max(left_depth, right_depth) + 1
    def __str__(self):
        if self.left is None:
            lstr = ""
        elif isinstance(self.left, DiceTree) and (DiceTree.precedence[self.left.token] < DiceTree.precedence[self.token] or self.token == "d"):
            lstr = "(" + str(self.left) + ")"
        else:
            lstr = str(self.left)
        mstr = "-" if self.token == "--" else self.token
        if isinstance(self.right, DiceTree) and (DiceTree.precedence[self.right.token] <= DiceTree.precedence[self.token] or self.token == "d"):
            rstr = "(" + str(self.right) + ")"
        else:
            rstr = str(self.right)
        return lstr + mstr + rstr
    def compute(self):
        l = [str(self)]
        try:
            while not isinstance(i := self.collapse(), int):
                l.append(str(self))
        except ParserError as e:
            l.append(e.args[0])
            i = 0
        l.append(str(i))
        return l
    def collapse(self) -> 'int | DiceTree':
        if isinstance(self.left, int) and isinstance(self.right, int):
            match self.token:
                case '+':
                    return self.left + self.right
                case '-':
                    return self.left - self.right
                case '*':
                    return self.left * self.right
                case 'd':
                    if self.left < 0:
                        raise ParserError("Error! Left operand < 0")
                    if self.left == 0:
                        return 0
                    if self.right <= 0:
                        raise ParserError("Error! Right operand < 0")
                    if self.left >= 100:
                        raise ParserError("Error! Left operand too large")
                    if self.right == 1:
                        return self.left
                    if self.left == 1:
                        return random.randint(1, self.right)
                    beg = DiceTree('+', random.randint(1, self.right), random.randint(1, self.right))
                    for i in range(self.left - 2):
                        beg = DiceTree('+', beg, random.randint(1, self.right))
                    self.left = beg.left
                    self.right = beg.right
                    self.token = '+'
                    return self
                case _:
                    raise ParserError("Error! Operator not found")
        if self.left is None and isinstance(self.right, int):
            return -self.right
        if isinstance(self.right, DiceTree):
            self.right = self.right.collapse()
        if isinstance(self.left, DiceTree):
            if isinstance(self.right, int) and DiceTree.precedence[self.token] == DiceTree.precedence[self.left.token] and self.token != 'd':
                self.left = self.left.collapse()
                if isinstance(self.left, int):
                    return self.collapse()
            else:
                self.left = self.left.collapse()
        return self

class ExpressionParser:
    tokens = tokens
    precedence = (
        ('right', '$'),
        ('left', '+', '-'),
        ('left', '*'),
        ('nonassoc', 'd'),
        ('right', 'UMINUS')
    )
    start = 'final'
    def p_start(self, p):
        """final : expression EOF"""
        p[0] = p[1]
    def p_binary_operator(self, p):
        """expression : expression '+' expression
                      | expression '-' expression
                      | expression '*' expression
                      | expression 'd' expression"""
        p[0] = DiceTree(p[2], p[1], p[3])
    def p_d100(self, p):
        """expression : expression 'd' """
        p[0] = DiceTree(p[2], p[1], 100)
    def p_1d(self, p):
        """expression : 'd' expression """
        p[0] = DiceTree(p[1], 1, p[2])
    def p_unary_operator(self, p):
        """expression : '-' expression    %prec UMINUS"""
        if isinstance(p[2], int):
            p[0] = -p[2]
        else:
            p[0] = DiceTree('--', None, p[2])
    def p_paren(self, p):
        """expression : '(' expression ')'
                      | '$' expression"""
        p[0] = p[2]
    def p_number(self, p):
        """expression : NUMBER"""
        p[0] = p[1]
    def p_error(self, p):
        # logger += "Error"
        if not p or p.type == "EOF":
            raise ParserError("Unexpected end of file.")
        else:
            raise ParserError(str(p))
    def build(self, **kwargs):
        self.parser = yacc.yacc(module=self, **kwargs)
    def parse(self, string, lexer=lexer) -> DiceTree:
        return self.parser.parse(string, lexer=lexer)
parser = ExpressionParser()
parser.build()
