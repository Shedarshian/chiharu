from nonebot import on_command, CommandSession, get_bot, permission, plugin
import nonebot
import importlib
import chiharu.plugins.config as config
from os import path

_dict = {"asc": "使用格式：\n-asc check str：转换str的所有字符到ascii码\n-asc trans numbers：转换数字到字符",
    "mbf": "使用格式：-mbf.run instructions \\n console_in\n\n脚本语言modified brainf**k帮助：\n有一个由整数组成的堆栈。从左到右依次读取instruction。堆栈为空时欲取出任何数均为0。\n.\t向堆栈中塞入一个0\n0-9\t堆栈顶数乘以10加输入数。即比如输入一个十进制数135可以使用.135\n+-*/%\t弹出堆栈顶两个数并塞入计算后的数。除法取整数除\n&|^\t按位运算\n><=\t比较栈顶两个数，true视为1，false视为0\n_\t栈顶数取负，即比如输入一个数-120可以使用.120_\n!\t0变为1，非0变为0\n(\t栈顶数+1\n)\t栈顶数-1\n:\t输入stdin的char至栈顶\n;\t输出栈顶的char至stdout，并消耗，超出范围则弹出后不做任何事\n[\t如果堆栈顶数为0则跳转至配对的]，并消耗掉栈顶数\n{\t与[相反，堆栈顶数非0则跳转至配对的}，并消耗掉栈顶数\n]\t如果堆栈顶数非0则跳转回匹配的[，并消耗掉栈顶数\n}\t与]相反，堆栈顶数为0则跳转回配对的{，并消耗掉栈顶数\n\\\t交换栈顶两数\n,\t弹出栈顶数n，并复制栈顶下数第n个数塞回栈顶，n超出范围则弹出n后不做任何事\n$\t塞入当前栈包含的整数总数\n~\tpop掉栈顶数\n\"\t弹出栈顶数n，删除栈顶下数第n个数，n超出范围则弹出n后不做任何事\n@\t弹出栈顶数n1之后n2，将输入序列的第n1个字符修改成n2对应的char，n1或n2超出范围则弹出两数后不做任何事\n?\t弹出栈顶数n，生成一个0至n-1的随机整数塞回堆栈，n非正则弹出n后不做任何事\n#\t复制栈顶数\n`\t弹出栈顶数，执行栈顶数对应的char对应的指令。超出范围则弹出后不做任何事\n'\t弹出栈顶数n，将输入序列第n个字符对应的ascii塞入堆栈\n字母为子程序，使用：\n-mbf.sub alpha string 存入子程序，大写字母的只可存入一次。\n-mbf.str Alpha string 可以给大写字母增加一条描述字符串。\n-mbf.check alpha 查询字母所存内容。\n-mbf.ls 列出所有子程序以及描述\n-mbf.time ins stdin 检查运行时间\n",
    #"eclins": "使用格式：-eclins ins_num\n检索ecl的ins。",
    "birth": "使用格式：-birth.today bandori或LL或imas：查询今天生日的角色",
    "seiyuu": "使用格式：\n-seiyuu.today：查询今天生日的声优列表\n-seiyuu.check seiyuu_name[, count]：返回声优的基本信息，找到多个时可以使用count指明第几个。声优名以日语原文键入，允许假名甚至罗马音。\n-seiyuu.list string[, bound=15]：查询包含string的声优名列表，超过bound时返回前bound个，顺序未指定",
    "chess": "使用格式：-chess.begin：开始对战\n-chess.end：结束对战",
    "misc": "-misc.asc.check str：转换str的所有字符到ascii码\n-misc.asc.trans numbers：转换数字到字符\n-misc.bandori.news：查询bandori新闻\n-misc.maj.ten：日麻算点器\n-misc.maj.train：麻将训练\n-misc.maj.img：天凤牌画\n-misc.maj.ting：听牌计算器\n-misc.token：将输入文本中大括号包含的token转换成latex中包含的unicode字符，使用https://github.com/joom/latex-unicoder.vim/blob/master/autoload/unicoder.vim, https://pastebin.com/jxHsjQK0\n  例：-misc.token f(0)={\\aleph}_0,f({\\alpha}+1)={\\aleph}_{\\alpha}\n-misc.latex：渲染latex公式",
    "event": "使用格式：\n-event year month day [max_note = 100]：按日期在eventernote.com查询该日发生的event，筛选条件为eventernote登录数大于max_note，默认为100，调低时请一定要注意避免刷屏！",
    "thwiki": "使用格式：-thwiki.list：显示预定直播列表\n-thwiki.check：查询thbwiki bilibili账户的直播状态",
    "me": "こんにちは～七海千春です～\n维护者：小大圣\n鸣谢：Python®  酷Q®  nonebot®  阿里云®",
    "default": "指令："
        #"\n-eclins：查询ecl的instruction"
        "\n-seiyuu：查询声优信息"
        "\n-chess：象棋"
        "\n-mbf：调用mbf脚本语言解释器"
        "\n-event：按日期查询event"
        "\n-misc：隐藏指令"
        "\n-help：展示本帮助\n-help command名称：查看该命令帮助\n欢迎加入测试群947279366避免刷屏"}

sp = {"thwiki_live": {"default": "\n-thwiki：thwiki直播申请相关",
        "thwiki": "\n-thwiki.apply [开始时间] [结束时间] [直播项目名称]或者-申请 [开始时间] [结束时间] [直播项目名称]；时间格式：x年x月x日x点x分或者xx:xx，今日或今年可以省，开始可以用now，结束可以用float\n-thwiki.cancel [直播项目名称]或者-取消 [直播项目名称]\n-thwiki.get 获取rtmp与流密码，会以私聊形式发送\n-thwiki.term 提前下播\napply cancel get term只能用于群内"}}

@on_command(name='help', only_to_me=False)
@config.ErrorHandle
async def help(session: CommandSession):
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
        strout = _dict[name] + str_tail
    else:
        strout = str_tail
    #try:
    await session.send(strout, auto_escape=True)
    #except KeyError:
    #    await session.send("请使用-help 命令名 查询命令帮助")

@help.args_parser
async def _(session: CommandSession):
    stripped_arg = session.current_arg_text.strip()
    if stripped_arg:
        session.args['name'] = stripped_arg
    else:
        session.args['name'] = 'default'

@on_command('reload', only_to_me=False)
@config.ErrorHandle
async def reload_plugin(session: CommandSession):
    name = 'chiharu.plugins.' + session.current_arg_text
    l = list(filter(lambda x: x.module.__name__ == name, plugin._plugins))
    print(list(map(lambda x: x.module.__name__, plugin._plugins)))
    if len(l) == 0:
        await session.send('no plugin named ' + session.current_arg_text, auto_escape=True)
    else:
        l[0].module = importlib.reload(l[0].module)
        await session.send('Successfully reloaded ' + session.current_arg_text, auto_escape=True)