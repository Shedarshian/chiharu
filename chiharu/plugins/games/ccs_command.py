from typing import Dict, Any, Callable, Awaitable, Literal
import re, random, json, datetime, itertools
from collections import defaultdict
from .ccs_helper import all_extensions
from .ccs_tile import readPackData
from .ccs_board import Board
from ..inject import CommandGroup, on_command
from .. import config, game
from nonebot import CommandSession, NLPSession, get_bot
from nonebot.command import call_command

version = (2, 1, 0)
changelog = """ver 2.0.0
· 重构板块结构。
ver 2.1.0
· 重构通信数据。"""

cacason = game.GameSameGroup('cacason', can_private=True)
config.CommandGroup(('play', 'cacason'), hide=True)
config.CommandGroup('cacason', short_des='卡卡颂。', hide_in_parent=True, display_parents='game')

@on_command(("cacason", "version"), hide=True, only_to_me=False)
@config.ErrorHandle
async def ccs_version(session: CommandSession):
    await session.send("千春桌游大厅：卡卡颂 version" + ".".join(str(c) for c in version) + "。")

@on_command(("cacason", "changelog"), hide=True, only_to_me=False)
@config.ErrorHandle
async def ccs_changelog(session: CommandSession):
    await session.send("千春桌游大厅：卡卡颂 changelog\n" + changelog)

@cacason.begin_uncomplete(('play', 'cacason', 'begin'), (1, 6))
async def ccs_begin_uncomplete(session: CommandSession, data: Dict[str, Any]):
    # data: {'players': [qq], 'args': [args], 'anything': anything}
    name = await game.GameSameGroup.get_name(session)
    if 'names' in data:
        data['names'].append(name)
    else:
        data['names'] = [name]
    if 'extensions' not in data:
        data['extensions'] = {}
        data['starting_tile'] = 0
    await session.send(f'玩家{name}已参与匹配，人数足够可使用-play.cacason.confirm开始比赛。')

@cacason.begin_complete(('play', 'cacason', 'confirm'))
async def ccs_begin_complete(session: CommandSession, data: Dict[str, Any]):
    # data: {'players': [qq], 'game': GameSameGroup instance, 'args': [args], 'anything': anything}
    qq = session.ctx['user_id']
    name = await game.GameSameGroup.get_name(session)
    if qq not in data['players']:
        data['players'].append(qq)
        if 'names' in data:
            data['names'].append(name)
        else:
            data['names'] = [name]
        await session.send(f'玩家{name}已参与匹配，游戏开始')
    else:
        await session.send('游戏开始')
    order = list(range(len(data['players'])))
    random.shuffle(order)
    data['players'] = [data['players'][i] for i in order]
    data['names'] = [data['names'][i] for i in order]
    data['adding_extensions'] = True
    import os, shutil
    group_id = session.ctx['group_id']
    if not os.path.isfile(config.pag(f"cacason\\{group_id}.html")):
        with open(config.pag(f"cacason\\{group_id}.html"), "w", encoding='utf-8') as f:
            with open(config.pag("cacason\\index.html"), encoding='utf-8') as f2:
                f.write(f2.read().replace("test", str(group_id)))
        shutil.copy(config.pag("cacason\\test.json"), config.pag(f"cacason\\{group_id}.json"))
        shutil.copy(config.pag("cacason\\test.png"), config.pag(f"cacason\\{group_id}.png"))
    # 选择扩展
    await session.send("请选择想开启或是关闭的扩展，发送如open ex1开启扩展，close ex1关闭，check查询，选择完毕后发送开始游戏即可开始。")

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
    start_no_start = ((7, "c"),)
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

@cacason.end(('play', 'cacason', 'end'))
async def ccs_end(session: CommandSession, data: dict[str, Any]):
    await session.send('已删除')

@cacason.process(only_short_message=True)
@config.ErrorHandle
async def ccs_process(session: NLPSession, data: dict[str, Any], delete_func: Callable[[], Awaitable]):
    async def send(prompt, ensure_private: bool=False):
        if isinstance(prompt, str):
            board.prompts.append(prompt)
            if len(board.prompts) >= 6:
                board.prompts.pop(0)
        with open(config.pag(f"cacason\\{board.group_id}.json"), 'w', encoding='utf-8') as f:
            f.write(json.dumps({"lastTime": datetime.datetime.now().isoformat(), "prompt": '· ' + '\n· '.join(board.prompts)}))
        await session.send(prompt, ensure_private=ensure_private)
    next_turn = False
    command = session.msg_text.strip()
    if data['adding_extensions']:
        if command in ("开始游戏", "游戏开始"):
            # 开始游戏
            data['extensions'][0] = "a"
            board: Board = Board(data['extensions'], data['names'], data['starting_tile'], session.ctx["group_id"])
            data['board'] = board
            await board.advance(send, delete_func)
            data['adding_extensions'] = False
        elif match := re.match(r'(open|close)(( ex\d+[a-z]?)+| random\d+)|check', command):
            await call_command(get_bot(), session.ctx, ('play', 'cacason', 'extension'), current_arg=command)
        elif command.startswith('open') or command.startswith('close'):
            await session.send(ccs_extension.__doc__.replace("-play.cacason.extension ", ""))
        return
    user_id: int = data['players'].index(session.ctx['user_id'])
    board = data['board']
    if command.startswith("查询剩余"):
        await session.send([board.saveRemainTileImg()])
        return
    if command == "查询礼物":
        await session.send("你手中的礼物卡有：" + board.players[user_id].giftsText(), ensure_private=True)
    if board.current_player_id != user_id:
        return
    if command == "重新查询":
        await session.send([board.saveImg()])
        return
    
    await board.parse_command(command, send, delete_func)
    
@config.ErrorHandle
async def ccs_rule(session: CommandSession):
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
on_command(('cacason', 'rule'), only_to_me=False, short_des="查询卡卡颂扩展列表与扩展规则。", args=("[ex?]",))(ccs_rule)
del packs

@on_command(('cacason', 'check'), only_to_me=False, display_id=998)
@config.ErrorHandle
async def ccs_check(session: CommandSession):
    """查询卡卡颂图块内容。"""
    if match := re.match(r'ex(\d+)([a-z]*)', session.current_arg_text):
        exa, exb = int(match.group(1)), match.group(2)
        if not exb:
            if exa == 0:
                exb = "a"
            elif exa not in all_extensions:
                session.finish("未找到扩展" + str(exa))
            else:
                exb = all_extensions[exa]
        from PIL import Image, ImageDraw, ImageFont
        from .ccs_tile import readTileData
        def pos(w: int, h: int, *offsets: tuple[int, int]):
            return w * (64 + 8) + sum(c[0] for c in offsets) + 8, h * (64 + 20) + sum(c[1] for c in offsets) + 20
        all_packs = readTileData({exa: exb})
        if len(all_packs) == 0:
            session.finish("此扩展无图块！")
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
        from .. import config
        name = 'ccs' + str(random.randint(0, 9)) + '.png'
        img.save(config.img(name))
        await session.send(config.cq.img(name))
    else:
        await session.send("请发送扩展编号如ex1ab")

