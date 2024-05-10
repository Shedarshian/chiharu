from typing import Tuple, Any, NoReturn
from collections.abc import Coroutine
import json
from nonebot.dependencies import Param
from nonebot.params import Depends
from nonebot.params import CommandArg
from nonebot.matcher import Matcher
from nonebot import on_message, on_notice
from nonebot.adapters.discord import on_slash_command, Event, Bot, Message, MessageSegment
from nonebot.adapters.discord.api import SubCommandOption, SubCommandGroupOption, Interaction, Button, ButtonStyle, ActionRow, StringOption
from nonebot.adapters.discord.event import MessageComponentInteractionEvent
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

GameData = dict[str, Any]
DeleteFunc = Coroutine[Any, Any, NoReturn]

class GameSameGroup:
    all_games: 'dict[str, GameSameGroup]' = {}
    # group: {'players': [User], 'game': GameSameGroup instance, 'anything': anything}
    uncomplete: 'dict[Group, dict[str, Any]]' = {}
    center: 'dict[Group, dict[str, Any]]' = {}
    def __init__(self, name: str, name_zh: str, player: Tuple[int, int]):
        self.all_games[self.name] = self
        self.name = name
        self.name_zh = name_zh
        self.begin_player = player

    async def get_event_data(self, event: Event, matcher: Matcher):
        if channel := await getGroup(event, matcher):
            data = self.uncomplete.get(channel) or self.center.get(channel)
            if data and data['game'].name == self.name:
                return data
        return None
    @property
    def data(self):
        return Depends(self.get_event_data)
    async def get_delete_func(self, event: Event, matcher: Matcher):
        if channel := await getGroup(event, matcher):
            async def _h():
                self.center.pop(channel)
            return _h
        return None
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
    @property
    def check_game(self):
        pass

    async def checkBegin(self, group: DiscordGroup, bot: Bot) -> bool:
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
            await self.begin(group)
            return True
        return False
    async def begin(self, group: DiscordGroup):
        if group not in self.uncomplete:
            return False
        if self.uncomplete[group]["game"] is not self:
            return False
        data = self.uncomplete.pop(group)
        self.center[group] = data
        # 执行效果
        pass
    def process(self):
        @matcher.handle_sub_command('play', self.name, 'begin')
        async def begin(bot: Bot, group: DiscordGroup=Depends(getGroup), user: User=Depends(getUser)):
            if group in self.uncomplete:
                await matcher.send_response("本群已有对局邀请！")
                return
            if group in self.center:
                await matcher.send_response("本群已有对局！")
                return
            self.uncomplete[group] = {"player": [user], "game": self}
            if not await self.checkBegin(group, bot):
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

        click = on_notice()
        @click.handle()
        async def checkClick(bot: Bot, event: MessageComponentInteractionEvent, group: DiscordGroup=Depends(getGroup), user: DiscordUser=Depends(getUser)):
            if group not in self.uncomplete:
                return
            if event.message.id != self.uncomplete[group]["message_id"]:
                return
            button = event.data.custom_id
            if button == "attend":
                if user in self.uncomplete[group]["player"]:
                    await click.send(MessageSegment.mention_user(user.user_id) + "已在对局中！")
                    return
                self.uncomplete[group]["player"].append(user)
                message_id = self.uncomplete[group]["message_id"]
                await click.send(MessageSegment.mention_user(user.user_id) + "已成功加入对局！")
                if await self.checkBegin(group, bot):
                    await bot.delete_message(channel_id=group.channel_id, message_id=message_id)
            elif button == "begin":
                if user not in self.uncomplete[group]["player"]:
                    await click.send(MessageSegment.mention_user(user.user_id) + "不在对局中，无法启动游戏！")
                    return
                if len(self.uncomplete[group]["players"]) < self.begin_player[0]:
                    await click.send("匹配人数未达下限，请耐心等待！")
                    return
                message_id = self.uncomplete[group]["message_id"]
                await bot.delete_message(channel_id=group.channel_id, message_id=message_id)
                await self.begin(group)
            elif button == "close":
                pass

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

        matcher_message = on_message()
        return matcher_message.handle()
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

