from nonebot import CommandSession, get_bot, permission, plugin, command
import nonebot
import importlib
from . import config
from .inject import on_command
from os import path

_dict = {"asc": "使用格式：\n-asc check str：转换str的所有字符到ascii码\n-asc trans numbers：转换数字到字符",
    "mbf": "使用格式：-mbf.run instructions \\n console_in\n\n脚本语言modified brainf**k帮助：\n有一个由整数组成的堆栈。从左到右依次读取instruction。堆栈为空时欲取出任何数均为0。\n.\t向堆栈中塞入一个0\n0-9\t堆栈顶数乘以10加输入数。即比如输入一个十进制数135可以使用.135\n+-*/%\t弹出堆栈顶两个数并塞入计算后的数。除法取整数除\n&|^\t按位运算\n><=\t比较栈顶两个数，true视为1，false视为0\n_\t栈顶数取负，即比如输入一个数-120可以使用.120_\n!\t0变为1，非0变为0\n(\t栈顶数+1\n)\t栈顶数-1\n:\t输入stdin的char至栈顶\n;\t输出栈顶的char至stdout，并消耗，超出范围则弹出后不做任何事\n[\t如果堆栈顶数为0则跳转至配对的]，并消耗掉栈顶数\n{\t与[相反，堆栈顶数非0则跳转至配对的}，并消耗掉栈顶数\n]\t如果堆栈顶数非0则跳转回匹配的[，并消耗掉栈顶数\n}\t与]相反，堆栈顶数为0则跳转回配对的{，并消耗掉栈顶数\n\\\t交换栈顶两数\n,\t弹出栈顶数n，并复制栈顶下数第n个数塞回栈顶，n超出范围则弹出n后不做任何事\n$\t塞入当前栈包含的整数总数\n~\tpop掉栈顶数\n\"\t弹出栈顶数n，删除栈顶下数第n个数，n超出范围则弹出n后不做任何事\n@\t弹出栈顶数n1之后n2，将输入序列的第n1个字符修改成n2对应的char，n1或n2超出范围则弹出两数后不做任何事\n?\t弹出栈顶数n，生成一个0至n-1的随机整数塞回堆栈，n非正则弹出n后不做任何事\n#\t复制栈顶数\n`\t弹出栈顶数，执行栈顶数对应的char对应的指令。超出范围则弹出后不做任何事\n'\t弹出栈顶数n，将输入序列第n个字符对应的ascii塞入堆栈\n字母为子程序，使用：\n-mbf.sub alpha string 存入子程序，大写字母的只可存入一次。\n-mbf.str Alpha string 可以给大写字母增加一条描述字符串。\n-mbf.check alpha 查询字母所存内容。\n-mbf.ls 列出所有子程序以及描述\n-mbf.time ins stdin 检查运行时间\n",
    #"eclins": "使用格式：-eclins ins_num\n检索ecl的ins。",
    "birth": "使用格式：-birth.today bandori或LL或imas：查询今天生日的角色",
    "seiyuu": "使用格式：\n-seiyuu.today：查询今天生日的声优列表\n-seiyuu.check seiyuu_name [count] [-m max=15]：返回声优的基本信息，找到多个时可以使用count指明第几个。声优名以日语原文键入，允许假名甚至罗马音，包含空格请带上引号。可以使用max指定列出的最大数量。",
    "game": "欢迎使用-game 指令访问七海千春游戏大厅~",
    "tools": "-tools.Julia [c的x坐标] [c的y坐标]：绘制Julia集\n-tools.oeis：查询oeis（整数序列在线百科全书），支持查询数列前几项（只返回第一个结果），或oeis的编号如A036057\n-tools.quiz：每月趣题，-t YYYYMM 查看历史趣题\n-tools.quiz_submit：提交答案\n-tools.calculator：计算器。别名：-cal\n-tools.function：绘制函数。",
    "tools.Julia": "-tools.Julia [c的x坐标] [c的y坐标]\n绘制以c=x+yi为参数，z→z^2+c的Julia集。\nJulia集为在复平面上，使得无限迭代z→z^2+c不发散的初值z_0的集合。\nRef：https://en.wikipedia.org/wiki/Julia_set",
    "tools.quiz": "每月趣题。可用选项：\n-t, --time 接六位月份码查看历史趣题。\n-a, --answer 查看答案。\n欢迎提交好的东方化（或其他IP化也欢迎~）的趣题至维护者邮箱shedarshian@gmail.com（难度至少让维护者能看懂解答）",
    "misc": "-misc.asc.check str：转换str的所有字符到ascii码\n-misc.asc.trans numbers：转换数字到字符\n-misc.maj.ten：日麻算点器\n-misc.maj.train：麻将训练\n-misc.maj.ting：听牌计算器\n-misc.maj.voice：雀魂报番语音，第一行番种，换行后为指定角色名\n-misc.token：将输入文本中大括号包含的token转换成latex中包含的unicode字符，使用https://github.com/joom/latex-unicoder.vim/blob/master/autoload/unicoder.vim, https://pastebin.com/jxHsjQK0\n  例：-misc.token f(0)={\\aleph}_0,f({\\alpha}+1)={\\aleph}_{\\alpha}\n-misc.latex：渲染latex公式\n-misc.money：面基算钱小助手 请单独-help misc.money\n-misc.roll.lyric：随机抽歌词，默认从全歌单中抽取，支持参数：vocalo kon imas ml cgss sphere aki bandori ll mu's Aqours starlight mh\n-misc.omikuji：千春酱御神签，每周只能抽一次哦~\n-misc.event year month day [max_note=100]：按日期在eventernote.com查询该日发生的event，筛选条件为eventernote登录数大于max_note，默认为100，调低时请一定要注意避免刷屏！",
    "misc.omikuji": "指令：-misc.omikuji\n千春酱御神签~\n    每周只能抽一次哦~",
    "misc.money": "每行为一条指令。指令：\nclear: 清除所有数据。\nadd [人名]: 增加一个人。\nbill [人名] [金额] [可选：需付费的人名列表]: 增加一个需付费账单，人名列表为空则默认【包括自己的】所有人。\noutput [策略] [参数]: 输出金额交换。策略目前有：\n\toneman [参数：人名]: 所有金额交换全部支付给此人/由此人支付。",
    "thwiki": "使用格式：-thwiki.list：显示五天以内的预定直播列表，使用-thwiki.list all查询全部\n-thwiki.check：查询thbwiki bilibili账户的直播状态\n-thwiki.time 可以@别人 查看自己或别人的直播总时长（2019年8月至今）\n-thwiki.timezone UTC时区 调整自己的时区，只支持整数时区。影响list与apply\n-thwiki.timezone 空或者@别人 查询时区信息\n-thwiki.leaderboard 查看直播排行榜",
    "code": "脚本语言解释器：\nmbf：modified brainf**k\nesulang\n使用如-mbf.run 指令 运行脚本\n使用如-help mbf查看语言解释",
    "esulang": "还在开发中，敬请期待！~",
    "card": """指令列表：-card.draw 卡池id/名字 抽卡次数 可以抽卡！！次数不填默认为单抽
-card.draw5 卡池id/名字 直接进行五连抽卡
-card.check 卡池id/名字 查询卡池具体信息，包含具体卡牌（刷屏预警，建议私聊~）
-card.check 不带参数 查询卡池列表与介绍
-card.check_card 卡片名 查询卡片余量
-card.add 卡片名字 张数 就可以创造卡片加入卡池 张数不填默认为1张 可以换行后加描述文本
-card.add_des 卡片名字 换行后写描述文本 为自己首次创造的卡牌增加描述文本，会在单抽时显示
-card.userinfo 查看个人信息，包含en数，剩余免费抽卡次数等等
-card.storage 查看库存卡片
-card.discard 卡片名 数量 分解卡片获得en，张数不填默认为1张
-card.wishlist 查看愿望单
-card.message 手动查看消息箱
-card.set.属性 改变用户设置，可以使用-help card.set查询可以改变的设置
-card.fav 卡片名 将卡片加入特别喜欢
-card.wish 卡片名 将卡片加入愿望单
-card.comment 给维护者留言~想说的话，想更新的功能，想开启的活动卡池都可以哦~""",
    "card.set": """-card.set.unconfirm 取消今日确认使用en抽卡
-card.set.message 参数 设置消息箱提醒，支持参数：-card.set.message 0：立即私聊
-card.set.message 1：手动收取
-card.set.message 2：凌晨定时发送私聊
-card.set.guide on或off：开启或关闭全部指令引导。指令引导会在使用一次该指令后自动关闭""",
    "snakebird": "snakebird是一款类贪吃蛇的单机解谜游戏，不同的是它引入了重力，每行走一步蛇都会受到重力的限制而下落。游戏目标是吃完所有食物后所有蛇都到达开启的出口处。游戏本身也有刺、方块、传送门等多个机制，解谜性满载哦~游戏本身目前在【安卓】上和steam上都有，欢迎使用-play.snakebird.begin 关卡号(目前包含关卡：0~45, *1~*6, final) 游玩这里的副本关卡，使用-play.snakebird.check查看自己已通过的关卡~\n游戏操作：直接输入上下左右移动以及红蓝绿切换蛇即可，输入撤可撤销一步\n欢迎向维护者提交自定义关卡【bushi",
    "me": "こんにちは～七海千春です～\n维护者：小大圣\n友情协助：Randolph（snakebird关卡信息），小石\n鸣谢：Python®  酷Q®  nonebot®  阿里云®\nContact me：shedarshian@gmail.com",
    "default": "指令："
        #"\n-eclins：查询ecl的instruction"
        "\n-seiyuu：查询声优信息"
        "\n-game：\U0001F6AA七海千春游戏大厅\U0001F6AA"
        "\n-tools：数理小工具"
        "\n-code：语言解释器"
        #"\n-event：按日期查询event"
        "\n-misc：隐藏指令"
        "\n-help：展示本帮助\n-help 指令名：查看该命令帮助\n例：-help tools：查看tools指令的帮助\n欢迎加入测试群947279366避免刷屏",
    "tools.calculator": """计算器。计算给定式子的结果。别名：-cal
    运算过程中只有浮点与布尔两种类型，计算结果必须为浮点数。
    可以使用的运算符：
        C++中的一元与二元运算符 + - * / ^ == != < <= > >= && || !
        括号 ( )
        C++中的三目运算符 ? :
        定义临时变量的运算符 := （使用例：(t:=2^3+1)*(t^2-2)
        求和 sum[变量名](下限，上限，表达式) （使用例：sum[t](1,100,sum[n](1,t,2^n/Gamma(n+1))))
    可以使用的函数名：
        指数函数exp 自然对数ln 常用对数lg 绝对值abs 开根号sqrt 向下取整floor
        六种三角函数（sin等） 六种反三角函数（asin等） 六种双曲三角函数（sinh等） 六种反双曲三角函数（asinh等）
        误差函数erf 伽马函数Gamma 贝塔函数Beta 双伽马函数psi 不完全伽马函数Gammainc
        黎曼zeta函数或赫尔维茨zeta函数zeta（重载）
        雅克比椭圆函数ellipse_sn ellipse_cn ellipse_dn
        贝塞尔函数BesselJ BesselY BesselK BesselI
        球贝塞尔函数Besselj Bessely Besselk Besseli
        艾里函数Airy Biry
    可以使用的常量：
        圆周率pi 自然对数的底e 欧拉常数gamma""",
    'tools.function': """绘制函数。语法见-tools.calculator的帮助。
    可用选项：
        -b, --begin: 起始范围，默认为0。
        -e, --end: 结束范围，默认为10。
        -s, --step: 步长，默认为0.01。
        以上三个选项均可以输入表达式，但是在包含空格时需要用引号包裹。
    函数自变量符号为x。
    函数不可包含换行符。在函数包含空格时，请用引号包裹函数体部分。
    也可以在第一行输入选项，换行后输入函数体。"""}

sp = {"thwiki_live": {"default": "%s\n-thwiki：thwiki直播申请相关",
    "thwiki": """%s
-thwiki.apply [开始时间] [结束时间] [直播项目名称]或者-申请 [开始时间] [结束时间] [直播项目名称]；时间格式：x年x月x日x点x分或者xx:xx，今日或今年可以省，开始可以用now，结束可以用float
例：-thwiki.apply 19:00 21:00 东方STG
-thwiki.cancel [直播项目名称或id]或者-取消 [直播项目名称或id]
-thwiki.get 获取rtmp与流密码，会以私聊形式发送，若直播间未开启则会自动开启，可以后跟想开启的直播分区如绘画，演奏，户外，vtb等，不指定则默认是单机·其他
-thwiki.change 更改当前直播标题，只可在自己直播时间段内，同样会修改列表里的名字
-thwiki.term 或terminate提前下播
-thwiki.grant @别人 可多个@ 可加false 推荐别人进入推荐列表，需要对方同意，请慎重推荐！结尾加false代表撤回推荐，撤回推荐会一同撤回被推荐人推荐的所有人
-thwiki.depart 自行安全脱离推荐树，会保留直播时间
-thwiki.bookmark av号 提交视频加入轮播清单，需管理员审核
-thwiki.recommend av号 提交视频加入推荐列表
apply cancel get term grant change depart只能用于群内"""},
    "thwiki_supervise": {"thwiki": """%s
-thwiki.deprive @别人 剥夺别人的推荐/转正，管理员在直播群使用
-thwiki.supervise id号 可加false 监视别人的直播申请，结尾加false代表撤回监视
-thwiki.grantlist 输出推荐树"""}}

@on_command('helpold', only_to_me=False, hide=True)
@config.ErrorHandle
async def help_f(session: CommandSession):
    """查询指令帮助。"""
    stripped_arg = session.current_arg_text.strip()
    if stripped_arg:
        session.args['name'] = stripped_arg
    else:
        session.args['name'] = 'default'
    global _dict, sp
    name = session.get('name')
    try:
        group_id = session.ctx['group_id']
    except KeyError:
        group_id = 0
    def _f():
        for key, val in sp.items():
            if group_id in config.group_id_dict[key] and name in val:
                yield val[name]
    str_tail = ''.join(_f())
    if name in _dict:
        if str_tail != "":
            strout = str_tail % _dict[name]
        else:
            strout = _dict[name]
    else:
        strout = str_tail
    # if name == 'thwiki' and str_tail != '' and group_id in config.group_id_dict['thwiki_live']:
    #     await session.send(strout, auto_escape=True, ensure_private=True)
    # else:
    #     await session.send(strout, auto_escape=True)
    await session.send(strout, auto_escape=True)

@on_command('reload', only_to_me=False, permission=permission.SUPERUSER, hide=True)
@config.ErrorHandle
async def reload_plugin(session: CommandSession):
    name = 'chiharu.plugins.' + session.current_arg_text
    if plugin.reload_plugin(name):
        await session.send('Successfully reloaded ' + session.current_arg_text)
    else:
        await session.send('Failed to reload plugin')

from nonebot.command import Command
from .config import find_help

@on_command('help', only_to_me=False, args='指令名', short_des='查看该命令帮助。\n例：-help tools：查看tools指令的帮助。\n欢迎加入测试群947279366避免刷屏', display_id=999)
@config.ErrorHandle
async def help_reflection(session: CommandSession):
    """查询指令帮助。指令名不需要前缀"-"。"""
    if session.current_arg_text != '':
        cmd_name = tuple(session.current_arg_text.split('.'))
    else:
        cmd_name = ()
    ret = await find_help(cmd_name, session)
    if ret:
        await session.send(ret, ensure_private=('.'.join(cmd_name) == 'thwiki' and session.ctx['group_id'] in config.group_id_dict['thwiki_send']))
    else:
        await session.send('未发现指令。')

config.CommandGroup('me', short_des='关于我®', des='こんにちは～七海千春です～\n维护者：小大圣\n献给：yuyu♥\n友情协助：Randolph（snakebird关卡信息），小石\n鸣谢：Python®  c\u0336o\u0336o\u0336l\u0336q\u0336  m\u0336i\u0336r\u0336a\u0336i\u0336 go-cqhttp® cqhttp®  nonebot®  阿里云®\nContact me：shedarshian@gmail.com', display_id=998)
config.CommandGroup((), des="指令：")