from typing import Dict, Any, Callable, Awaitable, Literal
import re, random
from .carcassonne import Connectable, Dir, TraderCounter, open_pack, PlayerState, CantPutError
from .carcassonne import Board, Tile, Segment, Object, Feature, Token, Player
from ..inject import CommandGroup, on_command
from .. import config, game
from nonebot import CommandSession, NLPSession

cacason = game.GameSameGroup('cacason', can_private=True)
config.CommandGroup(('play', 'cacason'), hide=True)
config.CommandGroup('cacason', des='卡卡颂是一款多人对战桌游，玩家轮流放置图块，建造城市、道路、草地，最后拥有分数最多的人获胜。\n具体规则如下：\n玩家每人手中有7个跟随者，游戏开始时起始图块在版面正中。\n玩家依次行动，每回合，玩家需抽取一张图块，然后将其放在版面上。放置的图块必须与已有图块边对边相邻，并且相邻的边必须可以相连。相连的城市、道路、草地算作同一块。\n然后，玩家可以选择是否放置一个跟随者在刚刚放置的图块的某部分上。可以放在城市、道路、草地，或是修道院上。已经被自己或其他人的跟随者占据的整座城市、道路、草地不可以放置。\n但是，如果两个已有跟随者的部分可能被新放置的图块连起来。\n选择是否放置之后，如果城市、道路、修道院完成了，则完成的部分立即计分，并收回其上放置的跟随者。\n如果同一个物品上有多个跟随者，则完成时，谁的跟随者较多，得分归属于谁。如果有多人的跟随者数目相同，则这几人每人均获得那么多的分数。\n城市的计分规则是每个图块2分，城市上的每个盾徽额外2分。道路是每个图块1分。修道院完成的标志是它和它周围的8个图块均被放置。这时算上修道院自己，共9个图块每块1分，计9分。草地上放置的跟随者无法在游戏进行过程中计分收回。\n计分后，轮到下一名玩家的回合。\n游戏结束时，未完成的城市、道路、草地、修道院会进行计分。未完成的城市每个图块计1分，每个盾徽额外1分。道路仍是每个图块1分。修道院是它自己所在的图块和周围8个每有一个图块计1分。\n对于草地，计分规则是该草地每有一个相邻的完整的城市算3分，这些分数统一给该草地的归属者。\n游戏结束时，拥有分数最多的人获胜。', short_des='卡卡颂。', hide_in_parent=True, display_parents='game')

@cacason.begin_uncomplete(('play', 'cacason', 'begin'), (1, 6))
async def ccs_begin_uncomplete(session: CommandSession, data: Dict[str, Any]):
    # data: {'players': [qq], 'args': [args], 'anything': anything}
    name = await game.GameSameGroup.get_name(session)
    if 'names' in data:
        data['names'].append(name)
    else:
        data['names'] = [name]
    await session.send(f'玩家{name}已参与匹配，人数足够可使用-play.cacason.confirm开始比赛。')

@cacason.begin_complete(('play', 'cacason', 'confirm'))
async def ccs_begin_complete(session: CommandSession, data: Dict[str, Any]):
    # data: {'players': [qq], 'game': GameSameGroup instance, 'args': [args], 'anything': anything}
    qq = session.ctx['user_id']
    name = await game.GameSameGroup.get_name(session)
    if qq not in data['players']:
        if 'names' in data:
            data['names'].append(name)
        else:
            data['names'] = [name]
        await session.send(f'玩家{name}已参与匹配，游戏开始')
    else:
        await session.send('游戏开始')
    #开始游戏
    board = data['board'] = Board(open_pack()["packs"][0:1], data['names'])
    board.current_player.drawTile()
    await session.send([board.saveImg()])
    await session.send(f'玩家{data["names"][board.current_player_id]}开始行动，请选择放图块的坐标，以及用URDL将指定方向旋转至向上。')

@cacason.end(('play', 'cacason', 'end'))
async def ccs_end(session: CommandSession, data: dict[str, Any]):
    await session.send('已删除')

@cacason.process(only_short_message=True)
@config.ErrorHandle
async def sp2_process(session: NLPSession, data: dict[str, Any], delete_func: Callable[[], Awaitable]):
    command = session.msg_text.strip()
    user_id: int = data['players'].index(session.ctx['user_id'])
    board: Board = data['board']
    if board.current_player_id != user_id:
        return
    player = board.current_player
    next_turn = False
    async def advance(to_send: dict[str, Any] | None=None):
        try:
            if to_send is None:
                ret = next(player.stateGen)
            else:
                ret = player.stateGen.send(to_send)
        except StopIteration as e:
            rete: Literal[-1, -2, -3, 1] = e.value
            if rete == -1:
                await session.send("已有连接！")
            elif rete == -2:
                await session.send("无法连接！")
            elif rete == -3:
                await session.send("没有挨着！")
            else:
                await session.send("玩家回合结束")
                next_turn = True
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
                player.stateGen = player.putTile((x + leftmost - 1, y + uppermost - 1), orient)
                await advance()
        case PlayerState.PuttingFollower:
            if command == "不放":
                await advance({"id": -1})
            elif match := re.match(r"\s*([a-z])\s*(.*)?", command):
                n = ord(match.group(1)) - ord('a') + 1
                name = match.group(2)
                await advance({"id": n, "which": name or "follower"})
        case PlayerState.InturnScoring:
            pass
        case _:
            pass
    if next_turn:
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
