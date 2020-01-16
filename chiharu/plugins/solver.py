import getopt
import more_itertools
from . import config
from nonebot import on_command, CommandSession, get_bot, permission, on_natural_language, NLPSession, IntentCommand
from .solvers import guess

def change(a):
    if type(a) is str:
        def _(a):
            for c in a:
                if c.isdigit():
                    yield int(c)
                else:
                    yield ord(c.lower()) - 87
        return tuple(_(a))
    else:
        def _(a):
            for c in a:
                if c <= 9:
                    yield str(c)
                else:
                    yield chr(c + 87)
        return ''.join(list(_(a)))
def changeab(i):
    a = i.index('a')
    b = i.index('b')
    return (int(i[:a]), int(i[a+1:b]))

@on_command(('solver', 'guess'), only_to_me=False, permission=permission.SUPERUSER, shell_like=True)
@config.ErrorHandle
async def guess_solver(session: CommandSession):
    opts, args = getopt.gnu_getopt(session.args['argv'], 'b:d:s', ['base=', 'digits=', 'strategy=', 'space'])
    base, digit, strategy, space = 10, 4, 0, False
    for o, a in opts:
        try:
            if o in ('-b', '--base'):
                base = int(a)
            elif o in ('-d', '--digit'):
                digit = int(a)
            elif o == '--strategy':
                strategy = int(a)
            elif o in ('-s', '--space'):
                space = True
        except ValueError:
            await session.send('请输入十进制数。')
            return
    if base > 36:
        await session.send('基数不能大于36。')
        return
    s = guess.Status(base=base, num=digit)
    for i, a in more_itertools.chunked(args, 2):
        s.set(change(i), changeab(a))
    s.space_gen()
    if space:
        if len(s.space) <= 1000:
            await session.send(' '.join([change(p) for p in s.space]))
        else:
            await session.send('too long')
    elif len(s.space) != 1:
        m = s.check(strategy)
        await session.send(' '.join([change(p) for p in m[0]]) + '\n' + str(m[1]))
    else:
        await session.send(change(s.space[0]) + '\n1')