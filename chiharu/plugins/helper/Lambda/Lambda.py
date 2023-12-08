import re
import ply.lex as lex, ply.yacc as yacc

literals = ':()'
tokens = ('ID',)

class ParserError(Exception):
    pass
def ExpressionLexer():
    t_ID = r'[a-zA-Z_][a-zA-Z_0-9]*'
    t_ignore = ' \t\r\n'
    def t_error(t):
        raise ParserError('Illegal character ' + t.value)
    return lex.lex()

class LambdaParser:
    tokens = tokens
    start = 'allexp'
    def p_begin(self, p):
        """allexp : expfunc | expapp | exp"""
        p[0] = p[1]
    def p_func(self, p):
        """expfunc : ID ':' allexp"""
        if p[1] in self.vars:
            raise ParserError("var name repeated!")
        p[0] = Func(p[1], p[3])
    def p_id(self, p):
        """exp : ID"""
        if p[1] not in self.vars:
            raise ParserError("var not found!")
        p[0] = Id(p[1])
    def p_exps(self, p):
        """expapp : expapp exp
                  | exp exp"""
        p[0] = Application(p[1], p[2])
    def p_para(self, p):
        """exp : '(' allexp ')'"""
        p[0] = p[2]
    def reset(self):
        self.vars = set()
    def __init__(self):
        self.reset()
    def build(self, **kwargs):
        self.parser = yacc.yacc(module=self, **kwargs)
parser = LambdaParser()
parser.build()

class Lambda:
    pass
class Id(Lambda):
    def __init__(self, name: str):
        self.name = name
class Application:
    def __init__(self, exp1: 'Lambda', exp2: 'Lambda'):
        self.exp1 = exp1
        self.exp2 = exp2
class Func:
    def __init__(self, name: str, exp: 'Lambda'):
        self.name = name
        self.exp = exp
