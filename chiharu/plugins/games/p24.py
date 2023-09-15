import itertools, random, re
from nonebot import CommandSession, get_bot
from ..inject import CommandGroup, on_command
from .. import config

@on_command(('misc', '24p'), only_to_me=False, short_des="新时代24点。")
@config.ErrorHandle
async def p24(session: CommandSession):
    which = ''.join(random.choice(list(itertools.combinations_with_replacement('123456789', 3))))
    with open(f'C:\\24p_save\\{which}.txt', encoding='utf-8') as f:
        s = set(l.split(' ')[0] for l in f)
        g = random.choice(list(s))
    await session.send(f"新时代24点{' '.join(which)}->{g}\n允许使用根号阶乘小数点n次根号，例：1 2 5->(.5√2)!+1=25\n查询答案请输入-misc.24pans {''.join(which)} {g}")

@on_command(('misc', '24pans'), only_to_me=False, short_des="新时代24点对答案。")
@config.ErrorHandle
async def p24ans(session: CommandSession):
    if not (match := re.match(r"^(\d+) (\d+)$", session.current_arg_text)):
        session.finish("请输入例如-misc.24pans 789 24查询如何使用789拼24。")
    which, ans = match.groups()
    which = ''.join(sorted(which))
    try:
        with open(f'C:\\24p_save\\{which}.txt', encoding='utf-8') as f:
            ret = []
            for l in f:
                c0, c1, _ = l.split(' ', 3)
                if c0 == ans:
                    ret.append(c1)
            if len(ret) == 0:
                session.finish("无解或数字过大。")
            n = '\n'
            session.finish(f"答案有：{n.join(ret)}")
    except FileNotFoundError:
        session.finish("未找到此数字组合。")
