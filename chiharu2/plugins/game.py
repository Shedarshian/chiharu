from typing import Callable, Iterable, Tuple, Any, Awaitable, Annotated, TypeVar, NoReturn, Optional, Literal
from typing_extensions import override, get_origin, get_args
from collections.abc import Coroutine
from dataclasses import dataclass
from functools import wraps
import json, inspect
import random
from nonebot.dependencies import Param
from nonebot.params import Depends
from nonebot.params import CommandArg
from nonebot import on_message
from nonebot.adapters.discord import on_slash_command, Event, Bot, Message
from nonebot.adapters.discord.api import SubCommandOption, SubCommandGroupOption, Interaction, MessageGet

# example usage for GameSameGroup:
# xiangqi = GameSameGroup('xiangqi', (2, 2)) # need to register into this file
#
# @xiangqi.begin_uncomplete()
# async def chess_begin_uncomplete(data: Gamedata=xiangqi.data, yilaizhuru):
#     # data: {'players': [qq], 'args': [args], 'anything': anything}
#     await session.send('已为您安排红方，等候黑方')
#
# @xiangqi.begin_complete()
# async def chess_begin_complete(data: Annotated[GameData, xiangqi.data], yilaizhuru):
#     # data: {'players': [qq], 'game': GameSameGroup instance, 'args': [args], 'anything': anything}
#     await session.send('已为您安排黑方')
#     #开始游戏
#     #data['board'] = board
#
# @xiangqi.end()
# async def chess_end(data: Annotated[GameData, xiangqi.data], yilaizhuru):
#     await session.send('已删除')
#
# @xiangqi.process()
# async def chess_process(data: GameData=xiangqi.data,
#        delete_func: DeleteFunc=xiangqi.delete_func, yilaizhuru):
#     pass

allGames = (('xiangqi', "象棋"), ('bw', "黑白棋"))

@dataclass
class Group:
    pass
@dataclass
class QQGroup(Group):
    group_id: int
    def __str__(self):
        return f"qq:{self.group_id}"
@dataclass
class DiscordGroup(Group):
    channel_id: int
    def __str__(self):
        return f"discord:{self.channel_id}"
@dataclass
class User:
    pass
@dataclass
class QQUser(User):
    user_id: int
    def __str__(self):
        return f"qq:{self.user_id}"
@dataclass
class DiscordUser(User):
    user_id: int
    def __str__(self):
        return f"discord:{self.user_id}"

matcher = on_slash_command(name="play",
    description="开始游戏",
    options=[
        SubCommandGroupOption(name=name,
            description=des,
            options=[
                SubCommandOption(name="begin",
                    description=f"开始{des}"),
                SubCommandOption(name="end",
                    description=f"中止{des}")
            ]) for name, des in allGames
    ])

GameData = dict[str, Any]
DeleteFunc = Coroutine[Any, Any, NoReturn]

def get_group(event: Event):
    if isinstance(event, (Interaction, MessageGet)) and (channel_id := event.channel_id):
        return DiscordGroup(channel_id)
    return None
class GameSameGroup:
    all_games: 'dict[str, GameSameGroup]' = {}
    # group: [{'players': [User], 'game': GameSameGroup instance, 'anything': anything}]
    def __init__(self, name: str, player: Tuple[int, int]):
        # group: {'players': [qq], 'anything': anything}
        self.uncomplete: dict[Group, dict[str, Any]] = {}
        self.center: dict[Group, dict[str, Any]] = {}
        self.all_games[self.name] = self
        self.name = name
        self.begin_player = player

    def get_event_data(self, event: Event):
        if channel := get_group(event):
            data = self.uncomplete.get(channel) or self.center.get(channel)
            return data
        return None
    @property
    def data(self):
        return Depends(self.get_event_data)
    def get_delete_func(self, event: Event):
        if channel := get_group(event):
            async def _h():
                self.center.pop(channel)
            return _h
        return None
    @property
    def delete_func(self):
        return Depends(self.get_delete_func)
    @classmethod
    async def check_all_game(cls, bot: Bot, event: Interaction, msg: Message = CommandArg(), group: Group | None=Depends(get_group)):
        # 以后可能搁到一起？
        if group is None:
            return
        for game in cls.all_games.values():
            if group in game.center:
                this_game = game
                break
        else:
            return
        if not event.guild_id or not event.user or not event.user.id or not event.channel_id:
            return
        center = this_game.center[group]
        user = DiscordUser(event.user.id)
        if user not in center['players']:
            return
    @property
    def check_game(self):
        pass

    def process(self):
        matcher.handle_sub_command('play', self.name, 'begin')

        # async def _g():
        #     try:
        #         group_id = int(session.ctx['group_id'])
        #     except KeyError:
        #         if self.can_private:
        #             group_id = int(session.ctx['user_id'])
        #         else:
        #             await session.send("请在群里玩")
        #             return
        #     qq = int(session.ctx['user_id'])
        #     if group_id in self.center:
        #         for dct in self.center[group_id]:
        #             if self is dct['game']:
        #                 await session.send('本群已有本游戏进行中')
        #                 return
        #             elif qq in dct['players']:
        #                 await session.send('您在本群正在游戏中')
        #                 return
        #     if group_id in self.uncomplete:
        #         if qq in self.uncomplete[group_id]['players']:
        #             await session.send('您已参加本游戏匹配，请耐心等待')
        #             return
        #         self.uncomplete[group_id]['players'].append(qq)
        #         self.uncomplete[group_id]['args'].append(
        #             session.current_arg_text)
        #     else:
        #         self.uncomplete[group_id] = {'players': [
        #             qq], 'args': [session.current_arg_text]}
        #     # 已达上限，开始游戏
        #     if len(self.uncomplete[group_id]['players']) == self.begin_player[1]:
        #         dct = self.uncomplete.pop(group_id)
        #         dct['game'] = self
        #         try:
        #             await _f(session, dct)  # add data to dct
        #         except ChessError:
        #             return
        #         if group_id in self.center:
        #             self.center[group_id].append(dct)
        #         else:
        #             self.center[group_id] = [dct]
        #         bot = get_bot()
        #         for group in config.group_id_dict['log']:
        #             await bot.send_group_msg(group_id=group, message='%s begin in group %s' % (self.name, group_id))
        #         return
        #     await self.uncomplete_func(session, self.uncomplete[group_id])

        #     @on_command(confirm_command, only_to_me=False, hide=True)
        #     @config.ErrorHandle
        #     async def _h(session: CommandSession):
        #         try:
        #             group_id = int(session.ctx['group_id'])
        #         except KeyError:
        #             if self.can_private:
        #                 group_id = int(session.ctx['user_id'])
        #             else:
        #                 await session.send("请在群里玩")
        #                 return
        #         qq = int(session.ctx['user_id'])
        #         if group_id not in self.uncomplete:
        #             return
        #         if len(self.uncomplete[group_id]['players']) < self.begin_player[0]:
        #             await session.send('匹配人数未达下限，请耐心等待')
        #         else:
        #             dct = self.uncomplete.pop(group_id)
        #             dct['game'] = self
        #             try:
        #                 await _f(session, dct)  # add data to dct
        #             except ChessError:
        #                 return
        #             if group_id in self.center:
        #                 self.center[group_id].append(dct)
        #             else:
        #                 self.center[group_id] = [dct]
        #             bot = get_bot()
        #             for group in config.group_id_dict['log']:
        #                 await bot.send_group_msg(group_id=group, message='%s begin in group %s' % (self.name, group_id))
        #     return _f
        # return _

        @matcher.handle_sub_command('play', self.name, 'end')
        async def play_end(bot: Bot, event: Interaction, group: Group | None=Depends(self.get_group)):
            if group is None or not event.guild_id or not event.user or not event.user.id or not event.channel_id:
                await matcher.send_response("无法结束！")
                return
            group = DiscordGroup(event.channel_id)
            user = DiscordUser(event.user.id)
            member = await bot.get_guild_member(guild_id=event.guild_id, user_id=event.user.id)
            if not member.permissions:
                await matcher.send_response("无法结束！")
                return
            member.permissions & (1 << 3)
            is_admin = await permission.check_permission(get_bot(), session.ctx, permission.GROUP_ADMIN)
            if_in = False
            if group_id in self.center:
                l = list(
                    filter(lambda x: x['game'] is self, self.center[group_id]))
                if_in = is_admin or (len(l) != 0 and qq in l[0]['players'])
            if if_in and len(l) != 0:
                await _f(session, l[0])
                self.center[group_id].remove(l[0])  # delete 函数？
                bot = get_bot()
                for group in config.group_id_dict['log']:
                    await bot.send_group_msg(group_id=group, message='%s end in group %s' % (self.name, group_id))
            elif group_id in self.uncomplete and (is_admin or qq in self.uncomplete[group_id]['players']):
                await _f(session, self.uncomplete[group_id])
                self.uncomplete.pop(group_id)

        matcher_message = on_message()
        @matcher_message.handle()
        

        return _g
        return _
    def open_data(self, qq):
        try:
            with open(config.rel(f'games\\user_data\\{qq}.json'), encoding='utf-8') as f:
                data = json.load(f)
                if self.name not in data:
                    return {}
                return data[self.name]
        except FileNotFoundError:
            return {}
    def save_data(self, qq, data_given):
        try:
            with open(config.rel(f'games\\user_data\\{qq}.json'), encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            data = {}
        data[self.name] = data_given
        with open(config.rel(f'games\\user_data\\{qq}.json'), 'w', encoding='utf-8') as f:
            f.write(json.dumps(data, ensure_ascii=False,
                               indent=4, separators=(',', ': ')))
    @classmethod
    async def get_username(cls, session: CommandSession):
        import aiocqhttp
        qq = session.ctx['user_id']
        group = session.ctx['group_id']
        try:
            c = await get_bot().get_group_member_info(group_id=group, user_id=qq)
            if c['card'] == '':
                name = c['nickname']
            else:
                name = c['card']
        except aiocqhttp.exceptions.ActionFailed:
            name = str(qq)
        return name

