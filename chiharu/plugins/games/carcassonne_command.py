from typing import Dict, Any, Callable, Awaitable, Literal
import re, random
from .carcassonne import Connectable, Dir, TraderCounter, open_pack, PlayerState
from .carcassonne import Board, Tile, Segment, Object, Feature, Token, Player
from ..inject import CommandGroup, on_command
from .. import config, game
from nonebot import CommandSession, NLPSession

cacason = game.GameSameGroup('cacason', can_private=True)
config.CommandGroup(('play', 'cacason'), hide=True)
config.CommandGroup('cacason', des='', short_des='卡卡颂。', hide_in_parent=True, display_parents='game')

@cacason.begin_uncomplete(('play', 'cacason', 'begin'), (2, 6))
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
                orient = {'U': Dir.UP, 'R': Dir.RIGHT, 'D': Dir.DOWN, 'L': Dir.LEFT}[orients]
                leftmost = min(i for i, j in board.tiles.keys())
                uppermost = min(j for i, j in board.tiles.keys())
                player.stateGen = player.putTile((x + leftmost, y + uppermost), orient)
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
            board.current_player.drawTile()
            await session.send([board.saveImg()])
            await session.send(f'玩家{data["names"][board.current_player_id]}开始行动，请选择放图块的坐标，以及用URDL将指定方向旋转至向上。')
        else:
            board.endGameScore()
            await session.send([board.saveImg()])
            score, players = board.winner()
            if len(players) == 1:
                await session.send(f'玩家{players[0].name}以{score}分获胜！')
            else:
                await session.send('玩家' + '，'.join(p.name for p in players) + f'以{score}分获胜！')
