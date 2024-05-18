import asyncio, math, random
from typing import Annotated
from pebble import concurrent, ThreadPool
from concurrent.futures import TimeoutError, ThreadPoolExecutor, _base
from nonebot.adapters.discord.commands import CommandOption, on_slash_command, CommandOptionType
from nonebot.adapters.discord.api import SubCommandGroupOption, SubCommandOption, IntegerOption, StringOption, BooleanOption, NumberOption, OptionChoice
from nonebot.adapters.discord import Bot, MessageEvent, MessageSegment, Message, InteractionCreateEvent
from nonebot import on_command
from nonebot.params import CommandArg
from .games import maj
from .helper.function.function import parser, ParserError

matcher = on_slash_command(name="tools",
    description="小工具",
    options=[
        SubCommandOption(
            name="cal",
            description="计算器",
            options=[StringOption(
                name="formula",
                description="算式",
                required=True,
            )]),
        SubCommandGroupOption(
            name="asc",
            description="Unicode字符翻译",
            options=[
                SubCommandOption(
                    name="check",
                    description="转换字符串到Unicode码",
                    options=[
                        StringOption(
                            name="string",
                            description="字符串",
                            required=True,),
                        BooleanOption(
                            name="hex",
                            description="是否使用十六进制",),
                    ]),
                SubCommandOption(
                    name="trans",
                    description="转换多个数字到Unicode字符",
                    options=[
                        StringOption(
                            name="number_list",
                            description="用空格分隔的数字",
                            required=True,)])
            ]
        ),
        SubCommandGroupOption(
            name="maj",
            description="麻将",
            options=[
                SubCommandOption(
                    name="ten",
                    description="日麻算点器",
                    options=[
                        IntegerOption(
                            name="han",
                            description="和牌的番数",
                            required=True
                        ),
                        IntegerOption(
                            name="pu",
                            description="和牌的符数",
                            min_value=20,
                            required=True
                        ),
                        BooleanOption(
                            name="qin",
                            description="是否为亲家",
                            required=True
                        ),
                        BooleanOption(
                            name="zi",
                            description="是否为子家",
                            required=True
                        )
                    ]
                ),
                SubCommandOption(
                    name="train",
                    description="麻将训练",
                    options=[
                        IntegerOption(
                            name="choice",
                            description="使用数字指定练习题",
                            required=True,
                            choices=[
                                OptionChoice(name="tingpai",value=int(0)),
                                OptionChoice(name="jiaqiangtingpai",value=int(2))
                            ],
                        ),
                        BooleanOption(
                            name="past_answer",
                            description="是否查看上题答案",
                            required=True,
                        )
                    ]
                ),
            ]
        ),
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
    except (TimeoutError, asyncio.exceptions.TimeoutError, _base.CancelledError):
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
    except (TimeoutError, asyncio.exceptions.TimeoutError, _base.CancelledError):
        await matcher.edit_response(f"您想要计算的式子是：{formula}\ntime out!")
        return
    await matcher.edit_response(f"您想要计算的式子是：{formula}\n{ret}")

@matcher.handle_sub_command('asc', 'check')
async def AscCheck(string: CommandOption[str], hex: CommandOption[bool]):
    '''转换输入字符串的所有字符到unicode码。
    可用选项：
        转换至U+xxxxx十六进制输出'''
    await matcher.send_response("少女转换中...")
    h = hex if hex else False
    await matcher.edit_response('现在h的值是{}'.format(h))
    format_string = "U+{:x}" if h else "{}"
    strout = ' '.join([format_string.format(ord(x)) for x in string])
    await matcher.edit_response('对应数字是：\n' + strout)

@matcher.handle_sub_command('asc', 'trans')
async def AscTrans(number_list: CommandOption[str]):
    '''转换多个数字到unicode字符。'''
    await matcher.send_response("少女转换中...")
    strin = number_list.split(' ')
    def _(x):
        if x.startswith('U+'):
            return int(x[2:], 16)
        return int(x)
    try:
        strout = ''.join([chr(_(i)) for i in strin])
        await matcher.edit_response('对应字符是：\n' + strout)
    except ValueError:
        await matcher.edit_response('请输入十进制数字或U+xxx十六进制数字。')

@matcher.handle_sub_command('maj', 'ten')
async def maj_ten(han: CommandOption[int], pu: CommandOption[int], qin: CommandOption[bool], zi: CommandOption[bool]):
    '''日麻算点器。
    输入几番几符，可计算得点。可额外指定亲家或子家。'''
    await matcher.send_response("少女计算中...")
    def ceil(x, base = 100):
        return base * math.ceil(x / base)
    if pu % 10 != 0 and pu != 25:
        pu = ceil(pu, 10)
    if han <= 5:
        ten_base = pu * 2 ** (han + 2)
        ten_qin = ceil(6 * ten_base)
        ten_zi = ceil(4 * ten_base)
        if ten_qin >= 12000:
            str_qin = '満贯，12000点，4000ALL'
        else:
            str_qin = '%i点，%iALL' % (ten_qin, ceil(ten_qin / 3))
        if ten_zi >= 8000:
            str_zi = '満贯，8000点，2000，4000'
        else:
            str_zi = '%i点，%i，%i' % (ten_zi, ceil(ten_base), ceil(2 * ten_base))
    else:
        if han >= 13:
            i = 3
        else:
            i = {6: 0, 7: 0, 8: 1, 9: 1, 10: 1, 11: 2, 12: 2}[han]
        str_i = ['跳満', '倍満', '三倍満', '役満'][i]
        int_i = [3000, 4000, 6000, 8000][i]
        str_qin = '%s，%i点，%iALL' % (str_i, int_i * 6, int_i * 2)
        str_zi = '%s，%i点，%i，%i' % (str_i, int_i * 4, int_i, int_i * 2)
    if qin and zi:
        await matcher.edit_response('親家：%s\n子家：%s' % (str_qin, str_zi))
    elif qin:
        await matcher.edit_response(str_qin)
    elif zi:
        await matcher.edit_response(str_zi)

daan = {}

@matcher.handle_sub_command('maj', 'train')
async def maj_train(choice: CommandOption[int], past_answer: CommandOption[bool], event: InteractionCreateEvent):
    """麻将训练。
    使用数字指定练习题，-a为查看上题答案。
    0：清一色听牌训练（排序，无暗杠，无鸣牌，不含七对）
    2：清一色加强型听牌训练（排序，无暗杠，无鸣牌，不含七对）
    可用选项：
    -a：查看上题答案。"""
    global daan
    try:
        group_id = event.member.user.id.__str__()
    except:
        await matcher.send_response('找不到当前用户')
        return
    text = str(choice)
    if past_answer:
        if group_id not in daan:
            await matcher.send_response('没有当前题目')
        else:
            await matcher.send_response('答案为：' + str(daan.pop(group_id)))
    elif text == '0':
        str_title = '清一色听牌训练（排序，无暗杠，无鸣牌，不含七对）\n'
        _continue = True
        while _continue:
            stack = []
            for i in range(4):
                if random.random() < 0.3:
                    a = random.randint(1, 9)
                    stack.append(a)
                    stack.append(a)
                    stack.append(a)
                else:
                    a = random.randint(1, 7)
                    stack.append(a)
                    stack.append(a + 1)
                    stack.append(a + 2)
            a = random.randint(1, 9)
            stack.append(a)
            stack.append(a)
            stack.sort()
            stack.pop(random.randint(0, len(stack) - 1))
            test = [0, 0, 0, 0, 0, 0, 0, 0, 0]
            for i in stack:
                test[i - 1] += 1
            _continue = False
            for i in test:
                if i > 4:
                    _continue = True
        strout = str_title + ''.join(map(str, stack))
        await matcher.send_response(strout)
        result = maj.MajHai.getTenOneColor(map(lambda x: x - 1, stack))
        daan[group_id] = \
            ''.join(map(lambda x: str(x[0] + 1), filter(lambda x: x[1] > 0, enumerate(map(len, result)))))
    elif text == '2':
        str_title = '清一色加强型听牌训练（排序，无暗杠，无鸣牌，不含七对）\n'
        stack = []
        for i in range(random.randint(5, 8)):
            if random.random() < 0.3:
                a = random.randint(1, 9)
                stack.append(a)
                stack.append(a)
                stack.append(a)
            else:
                a = random.randint(1, 7)
                stack.append(a)
                stack.append(a + 1)
                stack.append(a + 2)
        a = random.randint(1, 9)
        stack.append(a)
        stack.append(a)
        stack.sort()
        stack.pop(random.randint(0, len(stack) - 1))
        strout = str_title + ''.join(map(str, stack))
        await matcher.send_response(strout)
        result = maj.MajHai.getTenOneColor(map(lambda x: x - 1, stack))
        daan[group_id] = \
            ''.join(map(lambda x: str(x[0] + 1), filter(lambda x: x[1] > 0, enumerate(map(len, result)))))
    else:
        pass
        # await matcher.send_response('使用数字指定练习题，-a为查看上题答案。\n0：清一色听牌训练（排序，无暗杠，无鸣牌，不含七对）\n2：清一色加强型听牌训练（排序，无暗杠，无鸣牌，不含七对）')


# matcher_console = on_command(("tools"))
# @matcher_console.handle()
# async def calculator2():
# # async def calculator2(bot: Bot, event: MessageEvent, msg: Message = CommandArg()):
#     await matcher_console.send("begin")
#     # ret = await calculator(msg.extract_plain_text())
#     # await matcher_console.send(ret)
