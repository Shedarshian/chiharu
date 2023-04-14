from typing import Dict, Any, Callable, Awaitable, Literal
import re, random
from .carcassonne import Connectable, Dir, TradeCounter, open_pack, PlayerState, CantPutError, all_extensions
from .carcassonne import Board, Tile, Segment, Object, Feature, Token, Player
from ..inject import CommandGroup, on_command
from .. import config, game
from nonebot import CommandSession, NLPSession

cacason = game.GameSameGroup('cacason', can_private=True)
config.CommandGroup(('play', 'cacason'), hide=True)
config.CommandGroup('cacason', des="""卡卡颂是一款多人对战桌游，玩家轮流放置图块，建造城市、道路、草地，最后拥有分数最多的人获胜。
具体规则如下：
玩家每人手中有7个跟随者，游戏开始时起始图块在版面正中。
玩家依次行动，每回合，玩家需抽取一张图块，然后将其放在版面上。放置的图块必须与已有图块边对边相邻，并且相邻的边必须可以相连。相连的城市、道路、草地算作同一块。
然后，玩家可以选择是否放置一个跟随者在刚刚放置的图块的某部分上。可以放在城市、道路、草地，或是修道院上。已经被自己或其他人的跟随者占据的整座城市、道路、草地不可以放置。
但是，如果两个已有跟随者的部分可能被新放置的图块连起来。
选择是否放置之后，如果城市、道路、修道院完成了，则完成的部分立即计分，并收回其上放置的跟随者。
如果同一个物品上有多个跟随者，则完成时，谁的跟随者较多，得分归属于谁。如果有多人的跟随者数目相同，则这几人每人均获得那么多的分数。
城市的计分规则是每个图块2分，城市上的每个盾徽额外2分。道路是每个图块1分。修道院完成的标志是它和它周围的8个图块均被放置。这时算上修道院自己，共9个图块每块1分，计9分。草地上放置的跟随者无法在游戏进行过程中计分收回。
计分后，轮到下一名玩家的回合。
游戏结束时，未完成的城市、道路、草地、修道院会进行计分。未完成的城市每个图块计1分，每个盾徽额外1分。道路仍是每个图块1分。修道院是它自己所在的图块和周围8个每有一个图块计1分。
对于草地，计分规则是该草地每有一个相邻的完整的城市算3分，这些分数统一给该草地的归属者。
游戏结束时，拥有分数最多的人获胜。""", short_des='卡卡颂。', hide_in_parent=True, display_parents='game')
config.CommandGroup(('cacason', 'ex1'), des="""扩展1：旅馆与主教教堂（Inns and Cathedrals）
(a) 扩展包含17种18个图块，其中有2块含主教教堂，6块含旅馆，1块含修道院。
(b) 大跟随者（big follower）：游戏开始时每人分发一个大跟随者。大跟随者在计算板块归属时算为两个跟随者，除此之外和普通跟随者无区别。注意得分不乘2。
(c) 旅馆（Inn）：旅馆是道路的一部分。包含旅馆的道路在完成时计分改为每个图块2分。游戏结束时若未完成则算0分。
(d) 主教教堂（Cathedrals）：主教教堂是城市的一部分。包含主教教堂的城市在完成时计分改为每个图块3分。游戏结束时若未完成则算0分。""", short_des="扩展1：旅馆与主教教堂（Inns and Cathedrals）")
config.CommandGroup(('cacason', 'ex2'), des="""扩展2：商人与建筑师（Traders and Builders）
(a) 扩展包含24种24个图块，其中有20块含交易标记，1块含修道院。
(b) 建筑师（builder）：游戏开始时每人分发一个建筑师。建筑师不算做跟随者，不参与争夺板块。玩家可以不放置跟随者，而是在一个已包含自己跟随者的城市或是道路上放置建筑师。此后，若玩家延伸此城市或是道路，则玩家获得一个额外的行动回合。此额外回合不可叠加。
(c) 猪（pig）：游戏开始时每人分发一个猪。猪不算做跟随者，不参与争夺板块。玩家可以不放置跟随者，而是在一个已包含自己跟随者的草地上放置猪。此后猪不可收回。游戏结束时，若玩家在有自己的猪的草地上得分，则每座城市额外获得1分（3分变成4分）。
(d) 交易标记：有些城市板块上包含交易标记。包含交易标记的城市完成时，完成该城市的玩家获得城市板块上所有对应的交易标记。注意是完成城市的玩家获得，不是得分的玩家获得。游戏结束时，对于每种交易标记（酒，小麦，布），获得该标记最多的玩家获得10分。若有多名玩家同时最多则均获得10分。""", short_des="扩展2：商人与建筑师（Traders and Builders）")
config.CommandGroup(('cacason', 'ex5'), des="""扩展5：僧院板块与市长（Abbey and Mayor）
(a) 扩展包含12种12个图块，其中有1块含修道院。
(b) 僧院（abbey）：游戏开始时每人分发一个僧院板块。在抽取卡牌之前，玩家可以选择将自己的僧院板块放置在四面都有板块的位置，将四面都完成。此后，玩家可以选择在该板块内的修道院上是否放置跟随者。
(c) 市长（mayor）：游戏开始时每人分发一个市长。市长作为跟随者，只能放在城市中。在判断城市归属时，普通跟随者的强度算作1，大跟随者（扩展1）的强度算作2，市长的强度为该城市内盾徽的个数。
(d) 马车（wagon）：游戏开始时每人分发一个马车。马车作为跟随者，只能放在草地以外的位置。在马车被计分后，玩家可以选择将马车挪到所在板块或相邻8个板块中任何一个未被占据且未完成的城市、道路、修道院内。""", short_des="扩展5：僧院与市长（Abbey and Mayor）")

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
    data["second_turn"] = False
    data['adding_extensions'] = True
    # 选择扩展
    await session.send("请选择想开启或是关闭的扩展，使用指令如-play.cacason.extension open ex1，选择完毕后发送开始游戏即可开始。")

@on_command(('play', 'cacason', 'extension'), only_to_me=False, hide=True, display_parents=("cacason",), args=('[check/open/close]', '[ex??]'), short_des="修改卡卡颂对局使用的扩展。")
@config.ErrorHandle
async def ccs_extension(session: CommandSession):
    """修改卡卡颂对局使用的扩展。
    可开关的扩展与小项有：
1. 旅馆与主教教堂（Inns and Cathedrals）
    (a) 图块；(b) 大跟随者；(c) 旅馆机制；(d) 主教教堂机制。
2. 商人与建筑师（Traders and Builders）
    (a) 图块；(b) 建筑师；(c) 猪；(d) 交易标记。

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
    if pas:
        if session.current_arg_text.startswith("check"):
            if len(data['extensions']) == 0:
                session.finish("目前未开启任何扩展包。")
            pack_names = ["Inns and Cathedrals"]
            thing_names = [["图块", "大米宝", "旅馆机制", "主教教堂机制"]]
            await session.send("目前开启的扩展包有：\n" + '\n'.join(pack_names[packid - 1] + "\n\t" + "，".join(thing_names[packid - 1][ord(c) - ord('a')] for c in s) for packid, s in data['extensions'].items()))
            return
        if match := re.match(r'(open|close) ex(\d+)([a-z]?)', session.current_arg_text):
            command, exas, exbs = match.groups()
            exa = int(exas)
            if exa not in all_extensions:
                session.finish("不存在扩展" + exas + "！")
            exb = exbs or all_extensions[exa]
            if exb not in all_extensions[exa]:
                session.finish("扩展" + exas + "不存在" + exb + "小项！")
            if command == "open":
                if exa not in data['extensions']:
                    data['extensions'][exa] = exb
                elif exb not in data['extensions'][exa]:
                    data['extensions'][exa] = ''.join(sorted(data['extensions'][exa] + exb))
                else:
                    session.finish("此扩展已被添加过！")
            elif exa not in data['extensions'] or exb not in data['extensions'][exa]:
                session.finish("此扩展未被添加过！")
            else:
                data['extensions'][exa] = data['extensions'][exa].replace(exb, "")
            session.finish("已添加。")
        session.finish(ccs_extension.__doc__)

@cacason.end(('play', 'cacason', 'end'))
async def ccs_end(session: CommandSession, data: dict[str, Any]):
    await session.send('已删除')

@cacason.process(only_short_message=True)
@config.ErrorHandle
async def ccs_process(session: NLPSession, data: dict[str, Any], delete_func: Callable[[], Awaitable]):
    command = session.msg_text.strip()
    if data['adding_extensions']:
        if command in ("开始游戏", "游戏开始"):
            # 开始游戏
            board = data['board'] = Board(data['extensions'], data['names'])
            board.current_player.drawTile()
            await session.send([board.saveImg()])
            await session.send(f'玩家{data["names"][board.current_player_id]}开始行动，请选择放图块的坐标，以及用URDL将指定方向旋转至向上。')
        data['adding_extensions'] = False
        return
    user_id: int = data['players'].index(session.ctx['user_id'])
    board = data['board']
    if command.startswith("查询剩余"):
        await session.send([board.saveRemainTileImg()])
    if board.current_player_id != user_id:
        return
    player = board.current_player
    next_turn = False
    async def advance(to_send: dict[str, Any] | None=None):
        nonlocal next_turn
        try:
            if to_send is None:
                ret = next(player.stateGen)
            else:
                ret = player.stateGen.send(to_send)
        except StopIteration as e:
            rete: Literal[-1, -2, -3, 1, 3] = e.value
            if rete == -1:
                await session.send("已有连接！")
            elif rete == -2:
                await session.send("无法连接！")
            elif rete == -3:
                await session.send("没有挨着！")
            elif rete == 1:
                await session.send("玩家回合结束")
                next_turn = True
            elif rete == 3:
                await session.send("玩家继续第二回合")
                next_turn = True
                data['second_turn'] = True
            player.stateGen = None
            return
        if ret["id"] == 2:
            if ret["last_err"] == -1:
                await session.send("没有找到跟随者！")
            elif ret["last_err"] == -2:
                await session.send("无法放置！")
            else:
                await session.send([board.saveImg(ret["last_put"])])
                await session.send("请选择放置跟随者的位置（小写字母）以及放置的特殊跟随者名称（如有需要），回复“不放”跳过。")
    match player.state:
        case PlayerState.TileDrawn:
            if match := re.match(r"\s*([A-Z]+)([0-9]+)\s*([URDL])", command):
                xs = match.group(1); ys = match.group(2); orients = match.group(3)
                x = (ord(xs[0]) - ord('A') + 1) * 26 + ord(xs[1]) - ord('A') if len(xs) == 2 else ord(xs) - ord('A')
                y = int(ys)
                orient = {'U': Dir.UP, 'R': Dir.LEFT, 'D': Dir.DOWN, 'L': Dir.RIGHT}[orients]
                leftmost = min(i for i, j in board.tiles.keys())
                uppermost = min(j for i, j in board.tiles.keys())
                player.stateGen = player.putTile((x + leftmost - 1, y + uppermost - 1), orient, data['second_turn'])
                data['second_turn'] = False
                await advance()
        case PlayerState.PuttingFollower:
            if command == "不放":
                await advance({"id": -1})
            elif match := re.match(r"\s*([a-z])\s*(.*)?$", command):
                n = ord(match.group(1)) - ord('a')
                name = match.group(2)
                await advance({"id": n, "which": name or "follower"})
        case PlayerState.InturnScoring:
            pass
        case _:
            pass
    if next_turn:
        if not data['second_turn']:
            board.nextPlayer()
        if len(board.deck) != 0:
            try:
                board.current_player.drawTile()
                await session.send([board.saveImg()])
                await session.send(f'玩家{data["names"][board.current_player_id]}开始行动，请选择放图块的坐标，以及用URDL将指定方向旋转至向上。')
                return
            except CantPutError:
                await session.send("所有剩余图块均无法放置，提前结束游戏！")
        board.endGameScore()
        await session.send([board.saveImg()])
        score, players = board.winner()
        if len(players) == 1:
            await session.send(f'玩家{players[0].name}以{score}分获胜！')
        else:
            await session.send('玩家' + '，'.join(p.name for p in players) + f'以{score}分获胜！')
        await delete_func()
