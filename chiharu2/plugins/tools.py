import asyncio
from pebble import concurrent, ThreadPool
from concurrent.futures import TimeoutError, ThreadPoolExecutor, _base
from nonebot.adapters.discord.commands import CommandOption, on_slash_command
from nonebot.adapters.discord.api import SubCommandGroupOption, SubCommandOption, StringOption
from nonebot.adapters.discord import Bot, MessageEvent, MessageSegment, Message
from nonebot import on_command
from nonebot.params import CommandArg
from .helper.function.function import parser, ParserError

matcher = on_slash_command(name="tools",
    description="数理小工具",
    options=[
        SubCommandOption(name="cal",
            description="计算器",
            options=[StringOption(
                name="formula",
                description="算式",
                required=True,
            )])
    ])

@concurrent.process(timeout=30)
def calculate(s):
    parser.reset()
    parser.max_sum = 10000
    try:
        return parser.parse(s)
    except ParserError as e:
        return 'SyntaxError: ' + str(e)
    except Exception as e:
        return type(e).__name__ + ': ' + str(e)

async def calculator(formula: str):
    """计算器。计算给定式子的结果。别名：-cal
    运算过程中有浮点布尔列表三种类型，计算结果必须为浮点数。
    可以使用的运算符：
        列表 {1,2,3,4}
        C++中的一元与二元运算符 + - * / ^ == != < <= > >= && || ! 下标[] 下标slice[i:j]
        括号 ( )
        C++中的三目运算符 ? :
        定义临时变量的运算符 := （使用例：(t:=2^3+1)*(t^2-2)
        优先级最低的分隔符 $
        求和 sum[变量名](下限，上限，表达式)或者sum[变量名](列表，表达式) （使用例：sum[t](1,100,sum[n](1,t,2^n/Gamma(n+1)))+sum[t](L:={2,3,5,7},t)/sum[t](L,1))
    可以使用的函数名：
        指数函数exp 自然对数ln 常用对数lg 绝对值abs 开根号sqrt 向下取整floor
        六种三角函数（sin等） 六种反三角函数（asin等） 六种双曲三角函数（sinh等） 六种反双曲三角函数（asinh等）
        误差函数erf 伽马函数Gamma 贝塔函数Beta 双伽马函数psi 不完全伽马函数Gammainc
        黎曼zeta函数或赫尔维茨zeta函数zeta（重载）
        雅克比椭圆函数ellipse_sn ellipse_cn ellipse_dn
        贝塞尔函数BesselJ BesselY BesselK BesselI
        球贝塞尔函数Besselj Bessely Besselk Besseli
        艾里函数Airy Biry
        均匀分布随机数random 高斯分布随机数gauss
    可以使用的常量：
        圆周率pi 自然对数的底e 欧拉常数gamma"""
    try:
        loop = asyncio.get_event_loop()
        future = calculate(formula) # type: ignore
        with ThreadPoolExecutor() as pool:
            result = await loop.run_in_executor(pool, future.result)
    except (TimeoutError, _base.CancelledError):
        return "time out!"
    if type(result) is float:
        return str(result)
    elif type(result) is str:
        return result
    else:
        return 'TypeError ' + str(result)

@matcher.handle_sub_command("cal")
async def cal1(formula: CommandOption[str]):
    await matcher.send_response(f"您想要计算的式子是：{formula}\n少女计算中...")
    try:
        ret = await calculator(formula)
    except (TimeoutError, _base.CancelledError):
        await matcher.edit_response(f"您想要计算的式子是：{formula}\ntime out!")
        return
    await matcher.edit_response(f"您想要计算的式子是：{formula}\n{ret}")

# matcher_console = on_command(("tools"))
# @matcher_console.handle()
# async def calculator2():
# # async def calculator2(bot: Bot, event: MessageEvent, msg: Message = CommandArg()):
#     await matcher_console.send("begin")
#     # ret = await calculator(msg.extract_plain_text())
#     # await matcher_console.send(ret)
