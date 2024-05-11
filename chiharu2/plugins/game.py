from typing import Tuple, Any, NoReturn, TypeAlias, Callable
from collections.abc import Coroutine, Awaitable
from functools import wraps
import json
from nonebot.dependencies import Param
from nonebot.params import Depends
from nonebot.params import CommandArg
from nonebot import on_message, on_notice
from nonebot.adapters.discord import on_slash_command, Event, Bot, Message, MessageSegment, ReadyEvent
from nonebot.adapters.discord.api import SubCommandOption, SubCommandGroupOption, Interaction, Button, ButtonStyle, ActionRow, StringOption
from nonebot.adapters.discord.event import MessageComponentInteractionEvent, InteractionCreateEvent
from nonebot.matcher import Matcher
from .helper.helper import rel, getGroup, getUser, Group, DiscordGroup, User, DiscordUser

# example usage for GameSameGroup:
# xiangqi = GameSameGroup('xiangqi', "象棋", (2, 2)) # need to register into this file
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

GameData: TypeAlias = dict[str, Any]
DeleteFunc: TypeAlias = Callable[[], Awaitable[NoReturn]]
matcher_message = on_message()
click = on_notice()

class GameSameGroup:
    all_games: 'dict[str, GameSameGroup]' = {}
    # group: {'players': [User], 'game': GameSameGroup instance, 'anything': anything}
    uncomplete: 'dict[Group, dict[str, Any]]' = {}
    center: 'dict[Group, dict[str, Any]]' = {}
    def __init__(self, name: str, name_zh: str, player: Tuple[int, int]):
        self.name = name
        self.all_games[self.name] = self
        self.name_zh = name_zh
        self.begin_player = player

    async def get_event_data(self, channel: DiscordGroup=Depends(getGroup)):
        data = self.uncomplete.get(channel) or self.center.get(channel)
        if data and data['game'] is self:
            return data
    @property
    def data(self):
        return Depends(self.get_event_data)
    async def get_delete_func(self, channel: DiscordGroup=Depends(getGroup)):
        async def _h():
            self.center.pop(channel)
        return _h
    @property
    def delete_func(self):
        return Depends(self.get_delete_func)
    @classmethod
    async def check_all_game(cls, bot: Bot, event: Interaction, msg: Message = CommandArg(), group: Group=Depends(getGroup), user: User=Depends(getUser)):
        # 以后可能搁到一起？
        if (data := cls.center.get(group)) is None:
            return
        if user not in data['players']:
            return
    async def checkInGroup(self, matcher: Matcher, group: DiscordGroup=Depends(getGroup)):
        if group not in self.center or self.center[group]["game"] is not self:
            matcher.skip()

    async def checkToBegin(self, group: DiscordGroup, bot: Bot) -> bool:
        "True表示成功开始游戏"
        if group not in self.uncomplete:
            return False
        if self.uncomplete[group]["game"] is not self:
            return False
        n = len(self.uncomplete[group]["players"])
        if n >= self.begin_player[1]:
            if n > self.begin_player[1]:
                await bot.send_to(group.channel_id, "因同步原因，参与游戏人数已超过上限，最后点击按钮的玩家无法参与对局。")
            self.uncomplete[group]["players"] = self.uncomplete[group]["players"][:self.begin_player[1]]
            self.uncomplete[group]["toBegin"] = True
            return True
        return False
    def checkBegin(self, matcher: Matcher):
        for group, data in self.uncomplete.items():
            if data["game"] is not self:
                continue
            if data.get("toBegin", False):
                data.pop("toBegin")
                break
        else:
            matcher.skip()
        self.uncomplete.pop(group)
        self.center[group] = data
    @classmethod
    def delete(cls, user: DiscordUser, group: DiscordGroup, is_admin: bool=False):
        if group in cls.center:
            if user in cls.center[group]["players"] or is_admin:
                cls.center.pop(group)
                return True
        elif group in cls.uncomplete:
            if user in cls.uncomplete[group]["players"] or is_admin:
                cls.uncomplete.pop(group)
                return True
        return False
    def begin(self):
        from pydantic import Field
        async def onBegin(bot: Bot, group: DiscordGroup=Depends(getGroup), user: User=Depends(getUser)):
            if group in self.uncomplete:
                await matcher.send_response("本群已有对局邀请！")
                matcher.skip()
            if group in self.center:
                await matcher.send_response("本群已有对局！")
                matcher.skip()
            self.uncomplete[group] = {"players": [user], "game": self}
            if not await self.checkToBegin(group, bot):
                labels = f"## {self.name_zh}游戏对局\n"
                if self.begin_player[0] == self.begin_player[1]:
                    labels += f"游戏人数：{self.begin_player[0]}"
                else:
                    labels += f"游戏人数：{self.begin_player[0]}~{self.begin_player[1]}"
                buttons = MessageSegment.component(
                    ActionRow(components=[
                        Button(label='参加',
                            custom_id='attend',
                            style=ButtonStyle.Primary),
                        Button(label='立即开始',
                            custom_id='begin',
                            style=ButtonStyle.Success),
                        Button(label='关闭',
                            custom_id='close',
                            style=ButtonStyle.Danger)]))
                await matcher.send_response(labels + buttons)
                msg = await matcher.get_response()
                self.uncomplete[group]["message_id"] = msg.id
                matcher.skip()
        f1 = matcher.handle_sub_command(self.name, 'begin',
                parameterless=[Depends(onBegin), Depends(self.checkBegin)])
        f2 = click.handle([Depends(checkClick), Depends(self.checkBegin)])
        return lambda f: f2(f1(f))

    def process(self):
        @matcher.handle_sub_command(self.name, 'end')
        async def play_end(bot: Bot, event: InteractionCreateEvent, group: DiscordGroup=Depends(getGroup), user: DiscordUser=Depends(getUser)):
            if group is None or not event.guild_id or not event.user or not event.user.id or not event.channel_id:
                await matcher.send_response("无法结束！")
                return
            member = await bot.get_guild_member(guild_id=event.guild_id, user_id=event.user.id)
            # if not member.permissions:
            #     await matcher.send_response("无法结束！")
            #     return
            # member.permissions & (1 << 3)
            if self.delete(user, group, False):
                await matcher.send_response("对局已结束。")
            else:
                await matcher.send_response("无法结束！")

        return matcher_message.handle([Depends(self.checkInGroup)])
    def open_data(self, qq):
        try:
            with open(rel(f'games\\user_data\\{qq}.json'), encoding='utf-8') as f:
                data = json.load(f)
                if self.name not in data:
                    return {}
                return data[self.name]
        except FileNotFoundError:
            return {}
    def save_data(self, qq, data_given):
        try:
            with open(rel(f'games\\user_data\\{qq}.json'), encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            data = {}
        data[self.name] = data_given
        with open(rel(f'games\\user_data\\{qq}.json'), 'w', encoding='utf-8') as f:
            f.write(json.dumps(data, ensure_ascii=False,
                               indent=4, separators=(',', ': ')))

async def checkClick(bot: Bot, matcher: Matcher, event: MessageComponentInteractionEvent, group: DiscordGroup=Depends(getGroup), user: DiscordUser=Depends(getUser)):
    if group not in GameSameGroup.uncomplete:
        matcher.skip()
    if event.message.id != GameSameGroup.uncomplete[group]["message_id"]:
        matcher.skip()
    button = event.data.custom_id
    game: GameSameGroup = GameSameGroup.uncomplete[group]["game"]
    if button == "attend":
        if user in GameSameGroup.uncomplete[group]["players"]:
            await click.send(MessageSegment.mention_user(user.user_id) + "已在对局中！")
            matcher.skip()
        GameSameGroup.uncomplete[group]["players"].append(user)
        message_id = GameSameGroup.uncomplete[group]["message_id"]
        await click.send(MessageSegment.mention_user(user.user_id) + "已成功加入对局！")
        if await game.checkToBegin(group, bot):
            await bot.delete_message(channel_id=group.channel_id, message_id=message_id)
        else:
            matcher.skip()
    elif button == "begin":
        if user not in GameSameGroup.uncomplete[group]["players"]:
            await click.send(MessageSegment.mention_user(user.user_id) + "不在对局中，无法启动游戏！")
            matcher.skip()
        if len(GameSameGroup.uncomplete[group]["players"]) < game.begin_player[0]:
            await click.send("匹配人数未达下限，请耐心等待！")
            matcher.skip()
        message_id = GameSameGroup.uncomplete[group]["message_id"]
        await bot.delete_message(channel_id=group.channel_id, message_id=message_id)
        GameSameGroup.uncomplete[group]["toBegin"] = True
        return
    elif button == "close":
        message_id = GameSameGroup.uncomplete[group]["message_id"]
        if GameSameGroup.delete(user, group, False):
            await bot.delete_message(channel_id=group.channel_id, message_id=message_id)
            await click.send(MessageSegment.mention_user(user.user_id) + "已删除对局。")
        else:
            await click.send(MessageSegment.mention_user(user.user_id) + "不在对局中，无法删除！")
        matcher.skip()
