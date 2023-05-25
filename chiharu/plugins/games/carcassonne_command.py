from typing import Dict, Any, Callable, Awaitable, Literal
import re, random, json, datetime
from .carcassonne import Connectable, Dir, State, CantPutError, all_extensions
from .carcassonne import Board, readPackData
from .carcassonne import TileAddable, Builder
from ..inject import CommandGroup, on_command
from .. import config, game
from nonebot import CommandSession, NLPSession, get_bot
from nonebot.command import call_command

version = (1, 1, 15)
changelog = ""

cacason = game.GameSameGroup('cacason', can_private=True)
config.CommandGroup(('play', 'cacason'), hide=True)
packs = readPackData()["packs"]
config.CommandGroup('cacason', short_des='卡卡颂。', hide_in_parent=True, display_parents='game')
for pack in packs:
    if "help" in pack:
        config.CommandGroup(('cacason', 'ex' + str(pack["id"])), display_id=pack["id"],
                    des=pack.get("full_name", pack["name"]) + "\n" + pack["help"],
                    short_des=[config.cq.img(r"C:\\coolq\\image\\ccs.png")] if pack["id"] == 0 else pack.get("full_name", pack["name"]))

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
    # 选择扩展
    await session.send("请选择想开启或是关闭的扩展，发送如open ex1开启扩展，close ex1关闭，check查询，选择完毕后发送开始游戏即可开始。")

@on_command(('play', 'cacason', 'extension'), only_to_me=False, hide_in_parent=True, display_parents=("cacason",), args=('[check/open/close]', '[ex??]'), short_des="修改卡卡颂对局使用的扩展。", display_id=999)
@config.ErrorHandle
async def ccs_extension(session: CommandSession):
    """修改卡卡颂对局使用的扩展。
    可开关的扩展与小项有（*为包含起始板块）：
1. 旅馆与主教教堂（Inns and Cathedrals）
    (a) 图块；(b) 大跟随者；(c) 旅馆机制；(d) 主教教堂机制。
2. 商人与建筑师（Traders and Builders）
    (a) 图块；(b) 建筑师；(c) 猪；(d) 交易标记。
3. 公主与龙（The Princess and The Dragon）
    (a) 图块；(b) 龙；(c) 仙子；(d) 传送门；(e) 公主。
4. 高塔（The Tower）
    (a) 图块；(b) 高塔。
5. 僧院板块与市长（Abbey and Mayor）
    (a) 图块；(b) 僧院板块；(c) 市长；(d) 马车；(e) 谷仓。
6. 伯爵、国王与小偷（Count, King and Robber）
    (a) 图块；(g) 神龛图块；(h) 神龛。
7. 河流合集
    (a) 河流*；(b) 河流2*；(c) GQ11图块*；(d) 20周年河流*。
12. 一些小扩展合集
    (a) 花园；(b) 修道院长。
13. 另一些小扩展合集
    (a) 飞行器图块；(b) 飞行器；(k) 幽灵。
14. 又新又好的精选小扩展合集
    (a) 礼物卡牌；(b) 护林员；(c) 姜饼人图块；(d) 姜饼人。

使用例：-play.cacason.extension check：查询目前开启了哪些扩展包。
-play.cacason.extension open ex1：开启所有扩展包1的内容。
-play.cacason.extension open ex1b：开启扩展包1，但只开启1中b小项的内容。
-play.cacason.extension close ex1a：关闭扩展包1中a小项的内容。"""
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
    start_names = {0: "默认", 7: "河流"}
    start_no_start = ((7, "c"),)
    if pas:
        if session.current_arg_text.startswith("check"):
            if len(data['extensions']) == 0:
                session.finish("目前未开启任何扩展包。")
            await session.send("目前开启的扩展包有：\n" + '\n'.join(packs[packid]["name"] + "\n\t" + "，".join(packs[packid]["things"][ord(c) - ord('a')] for c in s) for packid, s in data['extensions'].items() if packid != 0) + "\n目前的起始板块是：\n" + start_names[data['starting_tile']])
            return
        if match := re.match(r'(open|close)(( ex\d+[a-z]*)+)', session.current_arg_text):
            command = match.group(1)
            exs = [ex[2:] for ex in match.group(2)[1:].split(' ')]
            exabs: list[tuple[int, str]] = []
            start_to_change: int = -1
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
                    exabs.append((exa, c))
                    if command == "open" and exa in data['extensions'] and c in data['extensions'][exa]:
                        session.finish("扩展" + exas + "的" + c + "小项已被添加过！")
                    if command == "close" and not (exa in data['extensions'] and c in data['extensions'][exa]):
                        session.finish("扩展" + exas + "的" + c + "小项未被添加过！")
                    if command == "open" and (data['starting_tile'] not in (0, exa) or start_to_change not in (-1, exa)) and exa in start_names and (exa, c) not in start_no_start:
                        session.finish("起始板块冲突！")
                    if exa in start_names and (exa, c) not in start_no_start:
                        start_to_change = exa if command == "open" else 0
            ret = ""
            for exa, c in exabs:
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
        session.finish(ccs_extension.__doc__)

@cacason.end(('play', 'cacason', 'end'))
async def ccs_end(session: CommandSession, data: dict[str, Any]):
    await session.send('已删除')

@cacason.process(only_short_message=True)
@config.ErrorHandle
async def ccs_process(session: NLPSession, data: dict[str, Any], delete_func: Callable[[], Awaitable]):
    next_turn = False
    async def advance(board: Board, to_send: dict[str, Any] | None=None):
        nonlocal next_turn
        try:
            if to_send is None:
                ret = next(board.stateGen)
            else:
                ret = board.stateGen.send(to_send)
        except StopIteration as e:
            if e.value:
                await session.send("所有剩余图块均无法放置，提前结束游戏！")
            board.setImageArgs(no_final_score=True)
            await session.send([board.saveImg()])
            score_win, players_win = board.winner()
            if len(players_win) == 1:
                await session.send(f'玩家{players_win[0].name}以{score_win}分获胜！')
            else:
                await session.send('玩家' + '，'.join(p.name for p in players_win) + f'以{score_win}分获胜！')
            # game log
            config.userdata.execute("insert into cacason_gamelog (group_id, users, extensions, time, score, winner, winner_score) values (?, ?, ?, ?, ?, ?, ?)", (session.ctx['group_id'], ','.join(str(q) for q in data['players']), json.dumps(data['extensions']), datetime.datetime.now().isoformat(), ','.join(str(p.score) for p in board.players), ','.join(str(q) for q in players_win), score_win))
            await delete_func()
            return
        if len(board.log) != 0:
            outputs = []
            for d in board.log:
                match d["id"]:
                    case "score":
                        outputs.append(f"玩家{data['names'][d['player'].id]}因" + {"fairy": "仙子", "complete": "已完成建筑", "final": "未完成建筑", "fairy_complete": "已完成建筑中的仙子", "ranger": "护林员", "cash_out": "兑现", "gingerbread": "姜饼人"}[d["source"]] + f"获得{d['num']}分。")
                    case "redraw":
                        outputs.append("牌堆顶卡无法放置，故重抽一张。")
                    case "putbackBuilder":
                        outputs.append(f"玩家{data['names'][d['builder'].player.id]}的{'建筑师' if isinstance(d['builder'], Builder) else '猪'}因所在区域没人而返回。")
                    case "exchangePrisoner":
                        outputs.append(f"玩家{data['names'][d['p2'].player.id]}和玩家{data['names'][d['p1'].player.id]}的囚犯自动互换了。")
                    case "tradeCounter":
                        outputs.append("你获得了" + '，'.join(f"{num}个" + ["酒", "小麦", "布"][i] for i, num in enumerate(d["tradeCounter"]) if num != 0) + '。')
                    case "challengeFailed":
                        outputs.append({"shrine": "神龛", "cloister": "修道院"}[d['type']] + "的挑战失败！")
                    case "drawGift":
                        outputs.append("你抽了一张礼物卡，已通过私聊发送。")
                        await session.send("你抽到了礼物卡：" + d['gift'].name + "\n你手中的礼物卡有：" + d['player'].giftsText(), ensure_private=True)
                    case "useGift":
                        outputs.append("你使用了礼物卡：" + d['gift'].name)
                        await session.send("你现在手中的礼物卡有：" + d['player'].giftsText(), ensure_private=True)
                    case "take2NoTile":
                        outputs.append("并未找到第二张可以放置的板块！")
                    case "dice":
                        outputs.append(f"骰子扔出了{d['result']}点。")
            await session.send("\n".join(outputs))
            board.log = []
        match board.state:
            case State.PuttingTile:
                rete = ret["last_err"]
                if rete == -1:
                    await session.send("已有连接！")
                elif rete == -2:
                    await session.send("无法连接！")
                elif rete == -3:
                    await session.send("没有挨着！")
                elif rete == -4:
                    await session.send("未找到可赎回的囚犯！")
                elif rete == -5:
                    await session.send("余分不足以赎回！")
                elif rete == -6:
                    await session.send("河流不能回环！")
                elif rete == -7:
                    await session.send("河流不能拐弯180度！")
                elif rete == -8:
                    await session.send("修道院不能和多个神龛相连，反之亦然！")
                elif rete == -9:
                    await session.send("必须扩张河流！")
                elif rete == -10:
                    await session.send("河流分叉必须岔开！")
                elif rete == -11:
                    await session.send("未找到礼物卡！")
                elif rete == -12:
                    await session.send("请指定使用哪张手牌！")
                else:
                    if ret["begin"] and ret["second_turn"]:
                        await session.send("玩家继续第二回合")
                    board.setImageArgs()
                    await session.send([board.saveImg()])
                    await session.send((f'玩家{data["names"][board.current_turn_player_id]}开始行动，' if ret["begin"] else "") + '请选择放图块的坐标，以及用URDL将指定方向旋转至向上。' + ("此时可发送“赎回玩家nxxx”花3分赎回囚犯。" if not ret["second_turn"] and board.checkPack(4, "b") else "") + ('回复礼物+第几张使用礼物卡，“查询礼物”查询。' if board.checkPack(14, "a") and not ret["gifted"] else ""))
            case State.ChoosingPos:
                if ret["last_err"] == -1:
                    await session.send("板块不存在！")
                elif ret["last_err"] == -2:
                    await session.send("不符合要求！")
                else:
                    board.setImageArgs()
                    await session.send([board.saveImg()])
                    if ret["special"] == "synod":
                        await session.send("请选择修道院，输入图块坐标。")
                    elif ret["special"] == "road_sweeper":
                        await session.send("请选择未完成道路，输入图块坐标。")
                    elif ret["special"] == "cash_out":
                        await session.send("请选择跟随者兑现，输入图块坐标。")
                    elif ret["special"] == "ranger":
                        await session.send("请选择要将护林员移动到的图块坐标。")
                    elif ret["special"] == "change_position":
                        await session.send("请选择跟随者切换形态，输入图块坐标。")
                    elif ret["special"] == "gingerbread":
                        await session.send("请选择要移动到的城市，输入图块坐标。")
            case State.PuttingFollower:
                if ret["last_err"] == -1:
                    await session.send("没有找到跟随者！")
                elif ret["last_err"] == -2:
                    await session.send("无法放置！")
                elif ret["last_err"] == -3:
                    await session.send("无法移动仙子！")
                elif ret["last_err"] == -4:
                    await session.send("无法使用传送门！")
                elif ret["last_err"] == -5:
                    await session.send("找不到高塔！")
                elif ret["last_err"] == -6:
                    await session.send("高塔有人！")
                elif ret["last_err"] == -7:
                    await session.send("手里没有高塔片段！")
                elif ret["last_err"] == -8:
                    await session.send("找不到修道院长！")
                elif ret["last_err"] == -9:
                    await session.send("无法移动护林员！")
                elif ret["last_err"] == -10:
                    await session.send("未找到幽灵！")
                elif ret["last_err"] == -11:
                    await session.send("幽灵无法放置！")
                elif ret["last_err"] == -12:
                    await session.send("在高塔/传送门/飞行器时不能使用幽灵，请仅仅申请“放幽灵”！")
                elif ret["last_err"] == -13:
                    await session.send("不能重复使用传送门/飞行器！")
                else:
                    board.setImageArgs(draw_tile_seg=ret["last_put"])
                    await session.send([board.saveImg()])
                    if ret.get("special") == "phantom":
                        prompt = "请选择放置幽灵的位置"
                    else:
                        prompt = "请选择放置跟随者的位置（小写字母）以及放置的特殊跟随者名称（如有需要）"
                        if board.checkPack(3, "c"):
                            prompt += "，回复跟随者所在板块位置以及“仙子”移动仙子"
                        if board.checkPack(4, "b"):
                            prompt += "，回复板块位置以及“高塔”以及跟随者名称（可选）放置高塔片段或跟随者"
                        if board.checkPack(12, "b"):
                            prompt += "，回复板块位置以及“修道院长”回收修道院长"
                        if board.checkPack(14, "b") and not ret["rangered"]:
                            prompt += "，回复板块位置以及“护林员”移动护林员"
                        if board.checkPack(13, "k"):
                            prompt += "，后加“放幽灵”申请放幽灵，或直接后加小写字母以及“幽灵”放置幽灵"
                    if not ret["if_portal"] and board.checkPack(3, "d") and board.tiles[ret["last_put"]].addable == TileAddable.Portal:
                        prompt += "，回复板块位置以及“传送门”使用传送门"
                    if ret["if_portal"]:
                        prompt += "，回复“返回”返回原板块" + ("并重新选择幽灵" if board.checkPack(13, "k") and ret.get("special") != "phantom" else "")
                    else:
                        prompt += "，回复“不放”跳过"
                    prompt += "。"
                    await session.send(prompt)
            case State.WagonAsking:
                if ret["last_err"] == -1:
                    await session.send("没有该图块！")
                elif ret["last_err"] == -2:
                    await session.send("图块过远，只能放在本图块或是相邻的8块上！")
                elif ret["last_err"] == -3:
                    await session.send("无法放置！")
                else:
                    pos = ret["pos"]
                    board.setImageArgs(draw_tile_seg=[(pos[0] + i, pos[1] + j) for i in (-1, 0, 1) for j in (-1, 0, 1)])
                    await session.send([board.saveImg()])
                    await session.send("请选择马车要移动到的图块，以及该图块上的位置（小写字母），回复“不放”收回马车。")
            case State.AbbeyAsking | State.FinalAbbeyAsking:
                if ret["last_err"] == -1:
                    await session.send("无法放置！")
                elif ret["last_err"] == -8:
                    await session.send("修道院不能和多个神龛相连！")
                else:
                    if ret["begin"] and ret["second_turn"]:
                        await session.send("玩家继续第二回合")
                    if ret["begin"]:
                        board.setImageArgs()
                        await session.send([board.saveImg()])
                    await session.send((f'玩家{data["names"][board.current_player_id]}' if ret["begin"] or board.state == State.FinalAbbeyAsking else "") + ("开始行动，选择" if ret["begin"] else "选择最后" if board.state == State.FinalAbbeyAsking else "请选择") + "是否放置僧院板块，回复“不放”跳过。")
            case State.MovingDragon:
                if ret["last_err"] == -1:
                    await session.send("无法移动！")
                else:
                    board.setImageArgs()
                    await session.send([board.saveImg()])
                    await session.send(f'玩家{data["names"][board.current_player_id]}第{ret["moved_num"] + 1}次移动龙，请输入URDL移动。')
            case State.ChoosingOwnFollower:
                if ret["last_err"] == -1:
                    await session.send("无法移动！")
                if ret["last_err"] == -2:
                    await session.send("未找到跟随者！")
                if ret["last_err"] == -3:
                    await session.send("不符合要求！")
                else:
                    board.setImageArgs(draw_tile_follower=ret["last_put"])
                    await session.send([board.saveImg()])
                    if ret["special"] == "fairy":
                        await session.send('请额外指定要放置在哪个跟随者旁。')
                    elif ret["special"] == "cash_out":
                        await session.send('请额外指定要兑现哪个跟随者。')
                    elif ret["special"] == "change_position":
                        await session.send('请额外指定要切换哪个跟随者。')
            case State.PrincessAsking:
                if ret["last_err"] == -1:
                    await session.send("未找到跟随者！")
                else:
                    board.setImageArgs(princess=ret["object"])
                    await session.send([board.saveImg()])
                    await session.send('你放置了公主，可以指定公主要移走哪名跟随者，回复“返回”跳过。')
            case State.CaptureTower:
                if ret["last_err"] == -1:
                    await session.send("未找到跟随者！")
                else:
                    board.setImageArgs(tower_pos=ret["pos"])
                    await session.send([board.saveImg()])
                    await session.send('请选择要抓的跟随者，回复“不抓”跳过。')
            case State.ExchangingPrisoner:
                if ret["last_err"] == -1:
                    await session.send("未找到跟随者！")
                else:
                    board.setImageArgs()
                    await session.send([board.saveImg()])
                    await session.send(f'请玩家{data["names"][board.current_player_id]}选择换回的对方的跟随者。')
            case State.ChoosingSegment:
                if ret["last_err"] == -1:
                    await session.send("未找到片段号！")
                if ret["last_err"] == -2:
                    await session.send("不符合要求！")
                else:
                    board.setImageArgs(draw_tile_seg=ret["last_put"], draw_occupied_seg=True)
                    await session.send([board.saveImg()])
                    if ret["special"] == "road_sweeper":
                        await session.send('请选择道路片段。')
                    elif ret["special"] == "change_position":
                        await session.send('请选择切换形态的片段。')
                    elif ret["special"] == "flier":
                        await session.send('请选择放置跟随者的片段。')
                    elif ret["special"] == "gingerbread":
                        await session.send('请选择姜饼人移动到的片段。')
            case State.AskingSynod:
                if ret["last_err"] == -1:
                    await session.send("板块不存在！")
                elif ret["last_err"] == -2:
                    await session.send("不符合要求！")
                elif ret["last_err"] == -3:
                    await session.send("没有跟随者！")
                elif ret["last_err"] == -4:
                    await session.send("无法放置！")
                else:
                    board.setImageArgs()
                    await session.send([board.saveImg()])
                    await session.send('请选择放置的修道院板块坐标以及跟随者。')
    
    command = session.msg_text.strip()
    if data['adding_extensions']:
        if command in ("开始游戏", "游戏开始"):
            # 开始游戏
            data['extensions'][0] = "a"
            board: Board = Board(data['extensions'], data['names'], data['starting_tile'])
            data['board'] = board
            await advance(board)
            data['adding_extensions'] = False
        elif match := re.match(r'(open|close)( ex\d+[a-z]?)+|check', command):
            await call_command(get_bot(), session.ctx, ('play', 'cacason', 'extension'), current_arg=command)
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
    
    match board.state:
        case State.PuttingTile:
            if match := re.match(r"\s*([a-z])?\s*([A-Z]+)([0-9]+)\s*([URDL])$", command):
                tilenum = ord(match.group(1)) - ord('a') if match.group(1) else -1
                xs = match.group(2); ys = match.group(3); orients = match.group(4)
                pos = board.tileNameToPos(xs, ys)
                orient = {'U': Dir.UP, 'R': Dir.LEFT, 'D': Dir.DOWN, 'L': Dir.RIGHT}[orients]
                await advance(board, {"pos": pos, "orient": orient, "tilenum": tilenum})
            elif match := re.match(r"\s*赎回玩家(\d+)(.*)?$", command):
                player_id = int(match.group(1)) - 1
                name = match.group(2)
                await advance(board, {"player_id": player_id, "which": name or "follower", "special": "prisoner"})
            elif match := re.match(r"\s*礼物([0-9]+)$", command):
                ns = match.group(1)
                await advance(board, {"id": int(ns) - 1, "special": "gift"})
        case State.ChoosingOwnFollower | State.ChoosingSegment:
            if match := re.match(r"\s*([a-z])$", command):
                n = ord(match.group(1)) - ord('a')
                await advance(board, {"id": n})
        case State.PrincessAsking | State.CaptureTower:
            if command in ("不放", "返回"):
                await advance(board, {"id": -1})
            elif match := re.match(r"\s*([a-z]+)$", command):
                xs = match.group(1)
                n = (ord(xs[0]) - ord('a') + 1) * 26 + ord(xs[1]) - ord('a') if len(xs) == 2 else ord(xs) - ord('a')
                await advance(board, {"id": n})
        case State.PuttingFollower:
            if command in ("不放", "返回"):
                await advance(board, {"id": -1})
            dct: dict[str, Any] = {}
            if board.checkPack(13, "k") and (match0 := re.match(r"(.*\S)\s*([a-z])\s*(幽灵|phantom)$", command)):
                n = ord(match0.group(2)) - ord('a')
                command = match0.group(1).strip()
                dct = {"phantom": n}
            elif board.checkPack(13, "k") and (match0 := re.match(r"(.*\S)\s*放(幽灵|phantom)$", command)):
                command = match0.group(1).strip()
                dct = {"phantom": -2}
            if match := re.match(r"\s*([a-z])\s*(.*)?$", command):
                n = ord(match.group(1)) - ord('a')
                name = match.group(2)
                await advance(board, {"id": n, "which": name or "follower", **dct})
            elif match := re.match(r"\s*([A-Z]+)([0-9]+)\s*(仙子|fairy|传送门|portal|修道院长|abbot|护林员|ranger)$", command):
                xs = match.group(1); ys = match.group(2)
                pos = board.tileNameToPos(xs, ys)
                special = {"仙子": "fairy", "传送门": "portal", "修道院长": "abbot", "护林员": "ranger"}.get(match.group(3), match.group(3))
                await advance(board, {"id": -2, "pos": pos, "special": special, **dct})
            elif board.checkPack(4, "b") and (match := re.match(r"\s*([A-Z]+)([0-9]+)\s*(高塔|tower)\s*(.*)?$", command)):
                xs = match.group(1); ys = match.group(2); which = match.group(4)
                pos = board.tileNameToPos(xs, ys)
                await advance(board, {"id": -2, "pos": pos, "special": "tower", "which": which, **dct})
        case State.AskingSynod:
            if match := re.match(r"\s*([A-Z]+)([0-9]+)\s*(.*)?$", command):
                xs = match.group(1); ys = match.group(2)
                name = match.group(3)
                pos = board.tileNameToPos(xs, ys)
                await advance(board, {"pos": pos, "which": name or "follower"})
        case State.ExchangingPrisoner:
            if match := re.match(r"\s*(.*)$", command):
                await advance(board, {"which": match.group(1)})
        case State.MovingDragon:
            if command in "URDL":
                dr = {"U": Dir.UP, "R": Dir.RIGHT, "D": Dir.DOWN, "L": Dir.LEFT}[command]
                await advance(board, {"direction": dr})
        case State.WagonAsking:
            if command == "不放":
                await advance(board, {"pos": None})
            elif match := re.match(r"\s*([A-Z]+)([0-9]+)\s*([a-z])$", command):
                xs = match.group(1); ys = match.group(2); n = ord(match.group(3)) - ord('a')
                pos = board.tileNameToPos(xs, ys)
                await advance(board, {"pos": pos, "seg": n})
        case State.AbbeyAsking | State.FinalAbbeyAsking:
            if command == "不放":
                await advance(board, {"put": False})
            elif match := re.match(r"\s*([A-Z]+)([0-9]+)$", command):
                xs = match.group(1); ys = match.group(2)
                pos = board.tileNameToPos(xs, ys)
                await advance(board, {"put": True, "pos": pos})
        case State.ChoosingPos:
            if match := re.match(r"\s*([A-Z]+)([0-9]+)$", command):
                xs = match.group(1); ys = match.group(2)
                pos = board.tileNameToPos(xs, ys)
                await advance(board, {"pos": pos})
        case _:
            pass

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
        from .carcassonne_tile import readTileData
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
