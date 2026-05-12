from nonebot.adapters.discord.commands import on_slash_command, CommandOption
from nonebot.adapters.discord.api import (
    SubCommandOption,
    IntegerOption,
    BooleanOption,
    StringOption,
)
from nonebot.adapters.discord import MessageSegment
from nonebot import logger
import more_itertools
from .solvers import guess

def change_str(a: str):
    def _(a):
        for c in a:
            if c.isdigit():
                yield int(c)
            else:
                yield ord(c.lower()) - 87
    return tuple(_(a))
def change(a: tuple[int,...]):
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
    return (int(i[:a]), int(i[a + 1:b]))

matcher = on_slash_command(
    name="solver",
    description="猜数字求解器",
    options=[
        SubCommandOption(
            name="guess",
            description="猜数字求解",
            options=[
                StringOption(
                    name="history",
                    description=(
                        "历史记录，格式例如：1234 1a2b 5678 0a1b"
                    ),
                    required=True,
                ),
                IntegerOption(
                    name="base",
                    description="进制，默认10",
                    required=False,
                    min_value=2,
                    max_value=36,
                ),
                IntegerOption(
                    name="digit",
                    description="位数，默认4",
                    required=False,
                    min_value=1,
                ),
                IntegerOption(
                    name="strategy",
                    description="策略编号，默认0",
                    required=False,
                    min_value=0,
                ),
                BooleanOption(
                    name="space",
                    description="是否输出所有可能解",
                    required=False,
                ),
            ],
        )
    ],
)

@matcher.handle_sub_command("guess")
async def guess_solver(
    history: CommandOption[str],
    base: CommandOption[int] = 10,
    digit: CommandOption[int] = 4,
    strategy: CommandOption[int] = 0,
    space: CommandOption[bool] = False,
):
    if base > 36:
        await matcher.finish('基数不能大于36。')
    s = guess.Status(base=base, num=digit)
    args = history.split()
    for i, a in more_itertools.chunked(history, 2):
        s.set(change_str(i), changeab(a))
    s.space_gen()
    if space:
        if len(s.space) <= 1000:
            await matcher.send_response(' '.join([change(p) for p in s.space]))
        else:
            await matcher.send_response('too long')
    elif len(s.space) != 1:
        m = s.check(strategy)
        await matcher.send_response(' '.join([change(p) for p in m[0]]) + '\n' + str(m[1]))
    else:
        await matcher.send_response(change(s.space[0]) + '\n1')