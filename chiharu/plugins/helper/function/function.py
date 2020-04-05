import re
import math
import ply.lex as lex, ply.yacc as yacc

re_x = re.compile(r'^x(\d*)$')
re_dy = re.compile(r'^(?:(?:D|d)(\d+)|((?:D|d)*))y(\d*)$')
tokens = ('NUMBER', 'ID', 'EQ', 'NEQ', 'GE', 'LE', 'AND', 'OR', 'DEFINE', 'SUM')
literals = '+-*/^(),<>?:[]'

class ParserError(Exception):
    pass

def ExpressionLexer():
    t_EQ = r'=='
    t_NEQ = r'!='
    t_GE = r'>='
    t_LE = r'<='
    t_AND = r'&&'
    t_OR = r'\|\|'
    t_DEFINE = r':='
    t_ignore = ' \t'
    def t_NUMBER(t):
        r'\d+(\.\d+)?'
        t.value = float(t.value)
        return t
    def t_ID(t):
        r'[a-zA-Z_][a-zA-Z_0-9]*'
        if t.value.lower() == 'sum':
            t.type = 'SUM'
        return t
    def t_newline(t):
        r'\n+'
        t.lexer.lineno += len(t.value)
    def t_error(t):
        raise ParserError('Illegal character ' + t.value)
    return lex.lex()
lexer = ExpressionLexer()

def inv(f):
    return lambda x: 1 / f(x)
def ainv(f):
    return lambda x: f(1 / x)
def get(f, i):
    return lambda *args: f(*args)[i]

def _func():
    from math import exp, log, log10, fabs, sqrt, sin, cos, tan, asin, acos, atan, sinh, cosh, tanh, asinh, acosh, atanh, erf, floor
    from scipy.special import gamma, beta, psi, gammainc, airy, ellipj, jv, yv, kv, iv, spherical_jn, spherical_yn, spherical_in, spherical_kn, zeta

    return {'exp': exp, 'ln': log, 'lg': log10, 'abs': fabs, 'sqrt': sqrt, 'floor': floor,
        'sin': sin, 'cos': cos, 'tan': tan, 'cot': inv(tan), 'sec': inv(cos), 'csc': inv(sin),
        'asin': asin, 'acos': acos, 'atan': atan, 'acot': ainv(atan), 'asec': ainv(acos), 'acsc': ainv(asin),
        'sinh': sinh, 'cosh': cosh, 'tanh': tanh, 'coth': inv(tanh), 'sech': inv(cosh), 'csch': inv(sinh),
        'asinh': asinh, 'acosh': acosh, 'atanh': atanh, 'acoth': ainv(atanh), 'asech': ainv(acosh), 'acsch': ainv(asinh),
        'erf': erf, 'Gamma': gamma, 'Beta': beta, 'psi': psi, 'Gammainc': gammainc,
        'Airy': get(airy, 0), 'Biry': get(airy, 2), 'zeta': zeta,
        'ellipse_sn': get(ellipj, 0), 'ellipse_cn': get(ellipj, 1), 'ellipse_dn': get(ellipj, 2),
        'BesselJ': jv, 'BesselY': yv, 'BesselK': kv, 'BesselI': iv,
        'Besselj': spherical_jn, 'Bessely': spherical_yn, 'Besseli': spherical_in, 'Besselk': spherical_kn
        }
functions = _func()
def _nums():
    from numpy import euler_gamma
    return {'pi': math.pi, 'e': math.e, 'gamma': euler_gamma}
nums = _nums()

class ExpressionParser:
    tokens = tokens
    precedence = (
        ('left', 'DEFINE'),
        ('right', ':'),
        ('left', 'OR'),
        ('left', 'AND'),
        ('right', '!'),
        ('nonassoc', 'EQ', 'NEQ', 'LE', 'GE', '<', '>'),
        ('left', '+', '-'),
        ('left', '*', '/'),
        ('left', '^'),
        ('right', 'UMINUS')
    )
    binary_operator = {'+': lambda x, y: x + y, '-': lambda x, y: x - y, '*': lambda x, y: x * y, '/': lambda x, y: x / y, '^': lambda x, y: x ** y, '==': lambda x, y: x == y, '!=': lambda x, y: x != y, '>=': lambda x, y: x >= y, '<=': lambda x, y: x <= y, '>': lambda x, y: x > y, '<': lambda x, y: x < y, '&&': lambda x, y: x and y, '||': lambda x, y: x or y}
    @staticmethod
    def optimize(f, *args, typ=float):
        if all([type(x) is float or type(x) is bool for x in args]):
            return typ(f(*args))
        else:
            return lambda *a, **ka: f(*[(x if type(x) is float or type(x) is bool else x(*a, **ka)) for x in args])
    start = 'expression'
    def p_binary_operator(self, p):
        """expression : expression '+' expression
                      | expression '-' expression
                      | expression '*' expression
                      | expression '/' expression
                      | expression '^' expression"""
        p[0] = ExpressionParser.optimize(ExpressionParser.binary_operator[p[2]], p[1], p[3], typ=float)
    def p_logic_operator(self, p):
        """logic : expression EQ expression
                | expression NEQ expression
                | expression LE expression
                | expression GE expression
                | expression '<' expression
                | expression '>' expression
                | logic AND logic
                | logic OR logic"""
        p[0] = ExpressionParser.optimize(ExpressionParser.binary_operator[p[2]], p[1], p[3], typ=bool)
    def p_logic_unary_operator(self, p):
        """logic : '!' logic"""
        p[0] = ExpressionParser.optimize(lambda x: not x, p[2], typ=bool)
    def p_unary_operator(self, p):
        """expression : '-' expression    %prec UMINUS"""
        p[0] = ExpressionParser.optimize(lambda x: -x, p[2], typ=float)
    def p_whether(self, p):
        """expression : logic '?' expression ':' expression"""
        p[0] = ExpressionParser.optimize(lambda x, y, z: (y if x else z), p[1], p[3], p[5], typ=float)
    def p_paren(self, p):
        """expression : '(' expression ')'
           logic : '(' logic ')'"""
        p[0] = p[2]
    def p_id(self, p):
        """expression : ID"""
        if p[1] in self.temp_var:
            t = str(p[1])
            p[0] = lambda *args, **kwargs: kwargs[t]
            return
        if p[1] in self.define_dict:
            p[0] = self.define_dict[p[1]]
            return
        if p[1] in nums:
            p[0] = nums[p[1]]
            return
        if self.state == 'x':
            match = re_x.match(p[1])
            if match:
                y = match.group(1)
                n = 0 if y is '' else int(y)
                p[0] = lambda *args, **kwargs: args[n]
                return
        elif self.state == 'dy':
            # Dmyn: args[n][m]
            match = re_dy.match(p[1])
            if match:
                d1, d2, y = match.groups()
                n = 0 if y is '' else int(y)
                m = len(d2) if d1 is None else int(d1)
                p[0] = lambda *args, **kwargs: args[n][m]
                return
        raise ParserError(p[1] + ' not found')
    def p_number(self, p):
        """expression : NUMBER"""
        p[0] = p[1]
    def p_function(self, p):
        """expression : ID '(' list ')'"""
        if p[1] not in functions:
            raise ParserError(p[1] + ' not found')
        p[0] = ExpressionParser.optimize(functions[p[1]], *p[3], typ=float)
    def p_sum(self, p):
        """expression : SUM '[' ID ']' seen_sum '(' list ')'"""
        if len(p[7]) != 3:
            raise TypeError('sum takes 3 positional argument but %i is given' % len(p[7]))
        b, e, func = p[7]
        c = str(p[3])
        def result(*a, **ka):
            begin = b if type(b) is float else b(*a, **ka)
            end = e if type(e) is float else e(*a, **ka)
            if end - begin >= self.max_sum:
                raise ValueError("sum range could not exceed %i" % self.max_sum)
            if type(func) is float:
                return func * len(range(int(begin), int(end + 1)))
            else:
                return sum(func(*a, **{c: t, **ka}) for t in range(int(begin), int(end + 1)))
        try:
            p[0] = float(result())
        except KeyError:
            p[0] = result
        except IndexError:
            p[0] = result
        except TypeError:
            p[0] = result
        self.temp_var.remove(p[3])
    def p_seen_sum(self, p):
        """seen_sum : """
        if p[-2] in self.temp_var or p[-2] in self.define_dict:
            raise ParserError(p[-2] + ' repeated')
        self.temp_var.add(p[-2])
    def p_define(self, p):
        """expression : ID DEFINE expression"""
        if p[1] in self.define_dict or p[1] in self.temp_var:
            raise ParserError(p[1] + ' already defined')
        self.define_dict[p[1]] = p[3]
        p[0] = p[3]
    def p_list(self, p):
        """list : expression
                | expression ',' list"""
        if len(p) == 2:
            p[0] = [p[1]]
        else:
            p[0] = [p[1], *p[3]]
    def p_error(self, p):
        # logger += "Error"
        raise ParserError('')
    def reset(self):
        self.define_dict = {}
        self.temp_var = set()
        self.state = ''
        self.max_sum = 1000
    def setstate(self, s):
        self.state = s
    def build(self, **kwargs):
        self.parser = yacc.yacc(module=self, **kwargs)
    def parse(self, string, lexer=lexer):
        return self.parser.parse(string, lexer=lexer)
    def __init__(self):
        self.reset()
parser = ExpressionParser()
parser.build()
