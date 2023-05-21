from typing import Dict, Any, Callable, Awaitable, Literal
import re, random, json, datetime
from .carcassonne import Connectable, Dir, TradeCounter, open_pack, State, CantPutError, all_extensions
from .carcassonne import Board, Tile, Segment, Object, Feature, Token, Player
from .carcassonne import DragonType, Builder
from ..inject import CommandGroup, on_command
from .. import config, game
from nonebot import CommandSession, NLPSession, get_bot
from nonebot.command import call_command

version = (1, 1, 15)
changelog = ""

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
(b) 建筑师（builder）：游戏开始时每人分发一个建筑师。建筑师不算做跟随者，不参与争夺板块，无法放在草地上。玩家可以不放置跟随者，而是在一个已包含自己跟随者的城市或是道路上放置建筑师。此后，若玩家延伸此城市或是道路，则玩家获得一个额外的行动回合。此额外回合不可叠加。
(c) 猪（pig）：游戏开始时每人分发一个猪。猪不算做跟随者，不参与争夺板块，只能放在草地上。玩家可以不放置跟随者，而是在一个已包含自己跟随者的草地上放置猪。此后猪不可收回。游戏结束时，若玩家在有自己的猪的草地上得分，则每座城市额外获得1分（3分变成4分）。
(d) 交易标记：有些城市板块上包含交易标记。包含交易标记的城市完成时，完成该城市的玩家获得城市板块上所有对应的交易标记。注意是完成城市的玩家获得，不是得分的玩家获得。游戏结束时，对于每种交易标记（酒，小麦，布），获得该标记最多的玩家获得10分。若有多名玩家同时最多则均获得10分。""", short_des="扩展2：商人与建筑师（Traders and Builders）")
config.CommandGroup(('cacason', 'ex3'), des="""扩展3：公主与龙（The Princess and The Dragon）
(a) 扩展包含29种30个图块，其中6块含火山，11块含龙，6块含传送门，6块含公主，2块含修道院。
(b) 龙：游戏开始时，将龙放在一旁。当玩家抽到含火山的板块时，立即将龙移至该板块上。龙所在的格子不可以放置任何跟随者、建筑师、猪。但是该回合玩家仍然可以放置谷仓或是移动仙子。当玩家抽到含龙图标的板块时，在放置跟随者阶段后，所有玩家立即进入龙的移动阶段。龙总共移动六格，从当前玩家开始依序，每名玩家选择将龙在上下左右四个方向上移动一格。龙不能移动到含仙子的格子，不能移动到此阶段先前走过的格子。若龙无处可动则移动提前结束。龙会吃掉所有经过格子上的肉质米宝。特殊地，若建筑师或猪所在的城市、道路、草地失去了玩家的最后一个跟随者，则建筑师与猪回到原玩家的手里。
(c) 仙子：游戏开始时，将仙子放在一旁。若玩家在放置跟随者阶段未进行任何其他操作，则可选择将仙子移动到自己的一名跟随者旁。玩家的回合开始阶段，如果仙子在该玩家的跟随者旁，玩家就可以获得1分。仙子旁边的跟随者在被计分时，会为该跟随者所属的玩家加3分。跟随者计分后，仙子仍留在该格子上。
(d) 传送门：若玩家抽到包含传送门的板块，玩家可以将一名跟随者通过传送门，放置在整个地图上任何一个未被占据、未完成的图块上。注意仍应遵守该跟随者放置的规则。
(e) 公主：若玩家将一个包含公主图标的城市板块连接到已有的城市上时，玩家可选择不放置跟随者，而是将公主所在的城市板块内的任何一个跟随者移除。""", short_des="扩展3：公主与龙（The Princess and The Dragon）")
config.CommandGroup(('cacason', 'ex4'), des="""扩展4：高塔（The Tower）
(a) 扩展包含18种19个图块，其中19块含高塔塔基，1块含修道院。
(b) 高塔：游戏开始时每人分发一些高塔部分（2人时10个，3人时9个，4人时7个，5人时6个，6人时5个）。在放置跟随者阶段，玩家可以选择不放置跟随者，而是：
  (1) 将自己手里的一个高塔部分放置在一个高塔地基或是一个未完成的高塔上。若如此做，玩家可以将该高塔格子上下左右距离n格内（n为高塔高度）的一名跟随者变为囚犯；
  (2) 将一个普通跟随者或是大跟随者放置在一个未完成的高塔上将其完成，之后除非跟随者被龙吃掉或是被其他高塔捕获则无法收回。高塔上有跟随者时高塔无法继续建造。
若玩家将自己的跟随者变为囚犯，则立即收回手中；若两名玩家互相拥有对方的囚犯，则囚犯立即自动交换。如果有其中一人有多名跟随者在另一人手中，则另一人可以自由选择交还哪名跟随者。另外，在放置板块之前，玩家可选择向对方支付3分购买回对方手中自己的囚犯。""", short_des="扩展4：高塔（The Tower）")
config.CommandGroup(('cacason', 'ex5'), des="""扩展5：僧院板块与市长（Abbey and Mayor）
(a) 扩展包含12种12个图块，其中有1块含修道院。
(b) 僧院（abbey）：游戏开始时每人分发一个僧院板块。在抽取卡牌之前，玩家可以选择将自己的僧院板块放置在四面都有板块的位置，将四面都完成。此后，玩家可以选择在该板块内的修道院上是否放置跟随者。
(c) 市长（mayor）：游戏开始时每人分发一个市长。市长作为跟随者，只能放在城市中。在判断城市归属时，普通跟随者的强度算作1，大跟随者（扩展1）的强度算作2，市长的强度为该城市内盾徽的个数。
(d) 马车（wagon）：游戏开始时每人分发一个马车。马车作为跟随者，只能放在草地以外的位置。在马车被计分后，玩家可以选择将马车挪到所在板块或相邻8个板块中任何一个未被占据且未完成的城市、道路、修道院内。
(e) 谷仓（barn）：游戏开始时每人分发一个谷仓。谷仓不算作跟随者，只能放在四面都是草地的四个板块的交界处，并且该片草地不能有其他谷仓。谷仓放下的一刻，将该片草地上所有的跟随者按照正常的分数（每座城3分）计分并收回。谷仓所在的草地不能有跟随者，此后若有新的有跟随者的草地被连接进来，则立即将该草地计分，但是只按照每座城1分的分数计分并收回。游戏结束时，谷仓所在的草地上每有一座相邻的城，谷仓的所有者计4分。若草地上有多个谷仓则都计分。""", short_des="扩展5：僧院与市长（Abbey and Mayor）")
config.CommandGroup(('cacason', 'ex6'), des="""
(a) 扩展包含5种5个图块，其中1块含修道院。
(b) 国王
(c) 小偷
(d) 卡卡颂城起始
(e) 卡卡颂城
(f) 伯爵
(g) 神龛图块：扩展包含5个含神龛的图块，神龛与修道院作用相同。
(h) 神龛：任何时候神龛不能与多于1个修道院相邻（包含对角相邻），反之亦然。当1个有跟随者的神龛与1个有跟随者的修道院相邻时，即为挑战开始，即使两个跟随者是同一个玩家的也是这样。两个中哪一个先被完成，则视为挑战成功，挑战失败的跟随者获得0分，并同时收回手中。游戏结束时，若挑战未完成，则两者均按1块1分的分数计分。""")
config.CommandGroup(('cacason', 'ex7'), des="""河流合集
(a) 河流
(b) 河流2：河流2包含12种12个图块，其中1块为河流源头，1块为河流分叉，2块为河流终点（其中1块含火山（扩展3）），另8块为普通河流（其中1块含修道院，1块含猪圈（扩展2），1块含旅馆（扩展1））。河流源头为起始板块。游戏开始时，河流分叉和含火山的河流终点放在一旁，剩余的河流板块洗混。第一名玩家先放置河流分叉，此后每名玩家依次抽取一张河流板块放置，延长河流。河流不得回环，也不得出现临近的180度转弯。当河流板块放完后，下一名玩家放置含火山的河流终点，然后该玩家立即抽取一张普通板块继续游戏。
(c) GQ11图块：GQ11扩展包含12种12个图块，其中1块为河流2源头的替代，另1块含河流，1块含修道院。
(d) 20周年河流""")
config.CommandGroup(('cacason', 'ex12'), des="""小扩展合集
(a) 花园：花园只能放置修道院长。除此之外花园与修道院相同。
(b) 修道院长（abbot）：游戏开始时，每人分发一个修道院长。修道院长作为跟随者，只能放置在修道院或是花园中。在放置跟随者阶段，若玩家选择不放置跟随者，则可以将自己的修道院长按照当前获得的分数计分，然后收回。
(c) 圣旨
(d) 摆渡人
(e) 麦田怪圈图块
(f) 麦田怪圈""")
config.CommandGroup(('cacason', 'ex13'), des="""另一些小扩展合集
(a) 飞行器图块：扩展包含8个图块，其中8块含飞行器图标。
(b) 飞行器：当玩家放置含有飞行器图标的图块后，玩家可选择在飞行器上选择一个米宝放置。若如此做，扔一个1到3点的骰子，玩家的米宝向飞行器方向飞行那么多格，然后玩家需将该米宝放置在目标格上的一个未完成的可放置的片段上（可以被别人占据），并且不能放在草地上。若不包含这样的片段，则玩家收回米宝。
(c) 金子图块：扩展包含8个图块，其中8块含金子图标，4块含修道院。
(d) 金子：当玩家放置含有金子图标的图块时，玩家在该图块上放置一块金块，然后在该图块周围8格内选择一格放置一块金块。当玩家完成建筑计分时，若建筑所在图块上有金块，则玩家获得之。若计分涉及多名玩家，则从当前玩家开始依序，每人选择一块拿走，直至拿完。游戏结束时，玩家手中的每块金块计(手中的金块数除以3向上取整，最多为4)分。
(e) 法师与女巫图块
(f) 法师与女巫
(g) 强盗图块
(h) 强盗
(i) 节日图块
(j) 节日
(k) 幽灵""")
config.CommandGroup(('cacason', 'ex14'), des="""又新又好的精选小扩展合集
(a) 礼物卡牌：放置板块时，玩家每延长一个不属于玩家自己的道路或是城市时，可以抽一张礼物卡。礼物卡在自己手中，其他玩家看不到。在抽取板块并在放置板块之前，玩家可以使用一张礼物卡。礼物卡共有5种，每种5张，用完的礼物卡进入弃牌堆，当礼物卡牌堆用完后，将弃牌堆的礼物卡洗混放入牌堆。五种礼物卡分别是：
  (1) 教会会议：将你的一个跟随者放置在任何一个未完成的修道院上（可以被别人占据）。
  (2) 马路清扫者：选择一条未完成的道路，将其计分并收回其上的所有跟随者。
  (3) 兑现：选择一个你的跟随者，你获得等同于其所在的城市/道路/草地/修道院上所有米宝数量两倍的分数，并将其收回手中。
  (4) 切换形态：选择一个你的跟随者，如果它在一个城市/道路/修道院上，你将其放到同一板块内的草地上，反之也可（可以被别人占据，但必须是未完成的）。
  (5) 再来一张：你可以额外抽一张板块，然后选择其中一块放置，之后将另一块洗回牌堆。
(b) 护林员：在你的回合，你可以不放置跟随者，而是将护林员移动至任意一个板块相邻的空格子上。放置板块时，如果你放在了护林员所在的位置上，则你获得3分，并可以移动护林员至任意一个板块相邻的空格子上。
(c) 姜饼人图块：扩展包含6个图块，其中6块含姜饼人标志。
(d) 姜饼人
(e) 20周年图块
(f) 20周年
(g) 城市大门""")

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

@on_command(('play', 'cacason', 'extension'), only_to_me=False, hide_in_parent=True, display_parents=("cacason",), args=('[check/open/close]', '[ex??]'), short_des="修改卡卡颂对局使用的扩展。")
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
7. 河流合集
    (a) 河流*；(b) 河流2*；(c) GQ11图块*；(d) 20周年河流*。
12. 一些小扩展合集
    (a) 花园；(b) 修道院长。
14. 又新又好的精选小扩展合集
    (a) 礼物卡牌；(b) 护林员。

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
    pack_names = ["Inns and Cathedrals", "Traders and Builders", "The Princess and The Dragon", "The Tower", "Abbey and Mayor", "", "河流合集", "", "", "", "", "小扩展合集", "", "又新又好的精选小扩展合集"]
    thing_names = [["图块", "跟随者", "旅馆机制", "主教教堂机制"], ["图块", "建筑师", "猪", "交易标记"], ["图块", "龙", "仙子", "传送门", "公主"], ["图块", "高塔"], ["图块", "僧院板块", "市长", "马车", "谷仓"], [], ["河流", "河流2", "GQ11图块", "20周年河流"], [], [], [], [], ["花园", "修道院长"], ["飞行器图块", "飞行器", "金子图块", "金块", "", "", "", "幽灵"], ["礼物卡牌", "护林员"]]
    start_names = {0: "默认", 7: "河流"}
    start_no_start = ((7, "c"),)
    if pas:
        if session.current_arg_text.startswith("check"):
            if len(data['extensions']) == 0:
                session.finish("目前未开启任何扩展包。")
            await session.send("目前开启的扩展包有：\n" + '\n'.join(pack_names[packid - 1] + "\n\t" + "，".join(thing_names[packid - 1][ord(c) - ord('a')] for c in s) for packid, s in data['extensions'].items()) + "\n目前的起始板块是：\n" + start_names[data['starting_tile']])
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
                        outputs.append(f"骰子扔出了f{d['result']}点。")
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
                    if not ret["if_portal"] and board.checkPack(3, "d") and board.tiles[ret["last_put"]].dragon == DragonType.Portal:
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
