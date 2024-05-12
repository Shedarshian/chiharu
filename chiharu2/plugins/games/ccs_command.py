from typing import Dict, Any, Callable, Awaitable, Literal
import re, random, json, datetime, itertools
from collections import defaultdict
from nonebot.params import Depends, EventMessage
from nonebot.matcher import Matcher
from nonebot.adapters.discord import on_slash_command, Message, MessageSegment, CommandOption
from nonebot.adapters.discord.api import SubCommandOption, StringOption
from ..game import GameSameGroup, GameData, DeleteFunc
from ..helper.helper import getUser, getGroup, DiscordGroup, DiscordUser
from .cacason.ccs_helper import all_extensions
from .cacason.ccs_tile import readPackData
from .cacason.ccs_board import Board

version = (3, 0, 0)
changelog = """ver 3.0.0
· 迁移。"""
cacason = GameSameGroup('cacason', "卡卡颂", (1, 6))

def getSend(matcher: Matcher):
    async def send(prompt, ensure_private: bool=False):
        await matcher.send(prompt)
    return send

@cacason.start()
async def ccs_start(matcher: Matcher,
            data: GameData=Depends(cacason.get_event_data),
            delete_func: DeleteFunc=Depends(cacason.get_delete_func),
            user: DiscordUser=Depends(getUser),
            group: DiscordGroup=Depends(getGroup)):
    # data: {'players': [user], 'game': GameSameGroup instance, 'args': [args], 'anything': anything}
    if len(data['players']) == 1:
        data["waiting_player_num"] = True
        await matcher.send("请输入你想模拟的玩家数")
    else:
        order = list(range(len(data['players'])))
        random.shuffle(order)
        data['players'] = [data['players'][i] for i in order]
        board: Board = Board(data['extensions'], data['names'], data['starting_tile'], group.channel_id)
        send = getSend(matcher)
        await board.advance(send, delete_func)

@on_command(('play', 'cacason', 'extension'), only_to_me=False, hide_in_parent=True, display_parents=("cacason",), args=('[check/open/close]', '[ex??]'), short_des="修改卡卡颂对局使用的扩展。", display_id=999)
@config.ErrorHandle
async def ccs_extension(session: CommandSession):
    """修改卡卡颂对局使用的扩展。查询扩展列表请使用-cacason.rule。

使用例：-play.cacason.extension check：查询目前开启了哪些扩展包。
-play.cacason.extension open ex1：开启所有扩展包1的内容。
-play.cacason.extension open ex1b：开启扩展包1，但只开启1中b小项的内容。
-play.cacason.extension close ex1a：关闭扩展包1中a小项的内容。
-play.cacason.extension open random1：随机开启2个大扩与4个小扩。
-play.cacason.extension open random2：随机开启3个大扩与6个小扩。"""
    try:
        group_id = int(session.ctx['group_id'])
    except KeyError:
        await session.send("请在群里玩")
        return
    qq = int(session.ctx['user_id'])
    pas: bool = False
    if group_id in cacason.center:
        for dct in cacason.center[group_id]:
            if qq in dct['players']:
                data = dct
                pas = True
    if group_id in cacason.uncomplete:
        if qq in cacason.uncomplete[group_id]['players']:
            data = cacason.uncomplete[group_id]
            pas = True
    start_names = {0: "默认", 6: "卡卡颂城", 7: "河流"}
    start_no_start = ((7, "c"), (6, "a"), (6, "b"), (6, "c"), (6, "d"), (6, "g"), (6, "h"))
    if pas:
        if session.current_arg_text.startswith("check"):
            if len(data['extensions']) == 0:
                session.finish("目前未开启任何扩展包。")
            packs = readPackData()["packs"]
            data['extensions'] = {c: data['extensions'][c] for c in sorted(data['extensions'].keys())}
            await session.send("目前开启的扩展包有：\n" + '\n'.join(packs[packid]["name"] + "\n\t" + "；".join('(' + c + ') ' + packs[packid]["things"][ord(c) - ord('a')] for c in s) for packid, s in data['extensions'].items() if packid != 0) + "\n目前的起始板块是：\n" + start_names[data['starting_tile']])
            return
        if match := re.match(r'(open|close)(( ex\d+[a-z]*)+| random\d+)', session.current_arg_text):
            command = match.group(1)
            exs = [ex[2:] for ex in match.group(2)[1:].split(' ')]
            exabs: defaultdict[int, str] = defaultdict(lambda: "")
            start_to_change: int = -1
            if exs[0].startswith('ndom'):
                packs = readPackData()["packs"]
                n = int(exs[0][4:])
                if n <= 0 or n >= 3:
                    await session.send("random预设只有1，2！")
                    return
                big, small = [(2, 4), (3, 6)][n - 1]
                bigs = [pack for pack in packs if pack.get("big", False)]
                smalls = list(itertools.chain(*([(pack, c) for c in pack.get("small", [])] for pack in packs)))
                random.shuffle(bigs)
                random.shuffle(smalls)
                for i in range(big):
                    p = bigs[i]
                    if isinstance(p["big"], list):
                        exabs[p["id"]] += ''.join(chr(ord('a') + j) for j in p["big"])
                    else:
                        exabs[p["id"]] += all_extensions[p["id"]]
                    if p["id"] in (6, 11):
                        start_to_change = p['id']
                for p, ln in smalls:
                    pb = p.get('has_begin', [])
                    if any(j in pb for j in ln):
                        if start_to_change != -1:
                            continue
                        start_to_change = p['id']
                    exabs[p["id"]] += ''.join(chr(ord('a') + j) for j in ln)
                    small -= 1
                    if small <= 0:
                        break
            else:
                for ex in exs:
                    match2 = re.match(r'(\d+)([a-z]*)', ex)
                    if not match2:
                        continue
                    exas, exbs = match2.groups()
                    exa = int(exas)
                    if exa not in all_extensions:
                        session.finish("不存在扩展" + exas + "！")
                    exb = exbs or all_extensions[exa]
                    for c in exb:
                        if c not in all_extensions[exa]:
                            session.finish("扩展" + exas + "不存在" + c + "小项！")
                        exabs[exa] += c
                        if command == "open" and exa in data['extensions'] and c in data['extensions'][exa]:
                            session.finish("扩展" + exas + "的" + c + "小项已被添加过！")
                        if command == "close" and not (exa in data['extensions'] and c in data['extensions'][exa]):
                            session.finish("扩展" + exas + "的" + c + "小项未被添加过！")
                        if command == "open" and (data['starting_tile'] not in (0, exa) or start_to_change not in (-1, exa)) and exa in start_names and (exa, c) not in start_no_start:
                            session.finish("起始板块冲突！")
                        if exa in start_names and (exa, c) not in start_no_start:
                            start_to_change = exa if command == "open" else 0
            ret = ""
            for exa, c in exabs.items():
                if command == "open":
                    if exa not in data['extensions']:
                        data['extensions'][exa] = c
                    else:
                        data['extensions'][exa] = ''.join(sorted(set(data['extensions'][exa] + c)))
                else:
                    data['extensions'][exa] = data['extensions'][exa].replace(c, "")
            if start_to_change >= 0:
                data['starting_tile'] = start_to_change
                ret = "起始板块已修改为" + start_names[start_to_change] + "。"
            if command == "open":
                session.finish("已开启。" + ret)
            else:
                session.finish("已关闭。" + ret)
    await call_command(get_bot(), session.ctx, ('help',), current_arg="play.cacason.extension")

@cacason.process()
async def ccs_process(matcher: Matcher,
            data: GameData=Depends(cacason.get_event_data),
            delete_func: DeleteFunc=Depends(cacason.get_delete_func),
            message: Message=EventMessage(),
            user: DiscordUser=Depends(getUser),
            group: DiscordGroup=Depends(getGroup)):
    command = message.extract_plain_text().strip()
    send = getSend(matcher)
    if data['waiting_player_num']:
        if command in "23456":
            # 开始游戏
            data['extensions'][0] = "a"
            board: Board = Board(data['extensions'], data['names'], data['starting_tile'], group.channel_id)
            data['board'] = board
            await board.advance(send, delete_func)
            data['waiting_player_num'] = False
        return
    user_id: int = data['players'].index(user)
    board = data['board']
    if command.startswith("查询剩余"):
        await matcher.send(board.saveRemainTileImg())
        return
    if command == "查询礼物":
        await matcher.send("你手中的礼物卡有：" + board.players[user_id].giftsText(), ensure_private=True)
    if command == "重新查询":
        await matcher.send(board.saveImg())
        return
    if board.current_player_id != user_id:
        return
    
    await board.parse_command(command, send, delete_func)


matcher_cacason = on_slash_command(name="cacason",
    description="卡卡颂",
    options=[
        SubCommandOption(name="version",
            description="查询卡卡颂版本"),
        SubCommandOption(name="changelog",
            description="查询changelog"),
        SubCommandOption(name="help",
            description="卡卡颂帮助"),
        SubCommandOption(name="rule",
            description="查询卡卡颂扩展及其规则"),
        SubCommandOption(name="check",
            description="查询卡卡颂图块内容",
            options=[StringOption(name="extension",
                description="扩展编号")])
    ])

matcher_cacason.handle("version")
async def ccs_version():
    await matcher_cacason.send_response("千春桌游大厅：卡卡颂 version" + ".".join(str(c) for c in version) + "。")

matcher_cacason.handle("changelog")
async def ccs_changelog():
    await matcher_cacason.send_response("千春桌游大厅：卡卡颂 changelog\n" + changelog)

async def ccs_rule():
    if match := re.match(r'ex(\d+)', session.current_arg_text):
        exa = int(match.group(1))
        packs = readPackData()["packs"]
        for pack in packs:
            if pack["id"] == exa and "help" in pack:
                await session.send(pack.get("full_name", pack["name"]) + "\n" + pack["help"])
                return
    await call_command(get_bot(), session.ctx, ('help',), current_arg="cacason.rule")
packs = readPackData()["packs"]
ccs_rule.__doc__ = "查看卡卡颂规则（*为包含起始板块）。\n" + \
    '\n'.join((f"ex{pack['id']}. " + pack.get("full_name", pack["name"]) + "\n    " +
        '；'.join(f"({chr(ord('a') + i)}) {name}" for i, name in enumerate(pack["things"]) if i not in pack.get("undone", [])) + '。')
        for pack in packs if "things" in pack)
matcher_cacason.handle_sub_command('rule')(ccs_rule)
del packs

@matcher_cacason.handle_sub_command('check')
async def ccs_check(extension: CommandOption[str]):
    """查询卡卡颂图块内容。"""
    if match := re.match(r'ex(\d+)([a-z]*)', extension):
        exa, exb = int(match.group(1)), match.group(2)
        if not exb:
            if exa == 0:
                exb = "a"
            elif exa not in all_extensions:
                await matcher_cacason.send_response("未找到扩展" + str(exa))
                return
            else:
                exb = all_extensions[exa]
        from PIL import Image, ImageDraw, ImageFont
        from .cacason.ccs_tile import readTileData
        def pos(w: int, h: int, *offsets: tuple[int, int]):
            return w * (64 + 8) + sum(c[0] for c in offsets) + 8, h * (64 + 20) + sum(c[1] for c in offsets) + 20
        all_packs = readTileData({exa: exb})
        if len(all_packs) == 0:
            await matcher_cacason.send_response("此扩展无图块！")
            return
        ss = list(sorted(set(tileData.serialNumber for tileData in all_packs)))
        s2: dict[str, list[tuple[Image.Image, int]]] = {}
        font_name = ImageFont.truetype("msyhbd.ttc", 16)
        for s in ss:
            if s[1] not in s2:
                s2[s[1]] = []
            l = [tileData.img for tileData in all_packs if tileData.serialNumber == s]
            s2[s[1]].append((l[0], len(l)))
        height = sum((len(x) + 4) // 5 for x in s2.values())
        img = Image.new("RGBA", pos(5, height), "LightCyan")
        dr = ImageDraw.Draw(img)
        y: int = 0
        for l in s2.values():
            for i, (timg, num) in enumerate(l):
                p = (i % 5, y + i // 5)
                img.paste(timg, pos(*p))
                dr.text(pos(*p, (32, 65)), str(num), "black", font_name, "mt")
            y += (len(l) + 4) // 5
        from ..helper.helper import img
        name = 'ccs' + str(random.randint(0, 9)) + '.png'
        img.save(img(name))
        await matcher_cacason.send_response(MessageSegment.attachment(name))
    else:
        await matcher_cacason.send_response("请发送扩展编号如ex1ab")

