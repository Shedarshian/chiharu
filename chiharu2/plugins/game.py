# mypy: disable-error-code="typeddict-item"
from typing import Tuple, Any, NoReturn, TypeAlias, Callable, ParamSpec, TypedDict
from collections.abc import Coroutine, Awaitable
from functools import wraps
import json, random
from nonebot.dependencies import Param
from nonebot.params import Depends, CommandArg
from nonebot.typing import T_State
from nonebot import on_message, on_notice
from nonebot.adapters.discord import on_slash_command, Event, Bot, Message, MessageSegment, CommandOption
from nonebot.adapters.discord.api import SubCommandOption, SubCommandGroupOption, Interaction, Button, ButtonStyle, ActionRow
from nonebot.adapters.discord.api import AnyCommandOption, StringOption, BooleanOption, IntegerOption
from nonebot.adapters.discord.event import MessageComponentInteractionEvent, InteractionCreateEvent
from nonebot.matcher import Matcher
from .helper.helper import rel, getGroup, getUser, Group, DiscordGroup, User, DiscordUser, requireNoDM, requireDM

# example usage for GameSameGroup:
# xiangqi = GameSameGroup('xiangqi', "象棋", (2, 2)) # need to register into this file
#
# @xiangqi.begin
#
# @xiangqi.start()
# async def chess_begin_complete(data: Annotated[GameData, xiangqi.data], yilaizhuru):
#     # data: {'players': [user], 'game': GameSameGroup instance, 'args': [args], 'anything': anything}
#     #开始游戏
#     #data['board'] = board
#
# @xiangqi.process()
# async def chess_process(data: GameData=xiangqi.data,
#        delete_func: DeleteFunc=xiangqi.delete_func, yilaizhuru):
#     pass

allGames: tuple[tuple[str, str],...] = \
    (('xiangqi', "象棋"),
     ('bw', "黑白棋"),
     ('cacason', "卡卡颂"))
allDMGames: tuple[tuple[str, str],...] = \
    (('maj', "麻将"),)
options: list[AnyCommandOption] = [
        SubCommandGroupOption(name=name,
            description=des,
            options=[
                SubCommandOption(name="begin",
                    description=f"开始{des}"),
                SubCommandOption(name="end",
                    description=f"中止{des}")
            ]) for name, des in allGames
    ]
options += [
        SubCommandGroupOption(name=name,
            description=des,
            options=[
                SubCommandOption(name="open",
                    description=f"创建{des}房间",
                    options=[
                        StringOption(name="type",
                            description="房间类型，默认为空",
                            required=False),
                        StringOption(name="password",
                            description="不输入密码以建立公开房间，输入密码可建立非公开房间",
                            required=False)]),
                SubCommandOption(name="attend",
                    description=f"加入{des}房间",
                    options=[
                        IntegerOption(name="id",
                            description="房间号",
                            required=True),
                        StringOption(name="password",
                            description="密码",
                            required=False)]),
                SubCommandOption(name="confirm",
                    description=f"改变准备状态。如果全员均准备则自动开始游戏"),
                SubCommandOption(name="quit",
                    description=f"退出{des}房间")
            ]) for name, des in allDMGames
    ]
matcher = on_slash_command(name="play",
    description="开始游戏",
    options=options)

class GameData(TypedDict):
    players: list[DiscordUser]
    game: 'GameSameGroup'
    __extra_items__: Any
DeleteFunc: TypeAlias = Callable[[], Awaitable[NoReturn]]
matcher_message = on_message()
click = on_notice()

P = ParamSpec('P')
class GameSameGroup:
    all_games: 'dict[str, GameSameGroup]' = {}
    # group: {'players': [User], 'game': GameSameGroup instance, 'anything': anything}
    uncomplete: 'dict[Group, GameData]' = {}
    center: 'dict[Group, GameData]' = {}
    def __init__(self, name: str, name_zh: str, player: Tuple[int, int], allow_private: bool=False):
        self.name = name
        self.all_games[self.name] = self
        self.name_zh = name_zh
        self.begin_player = player
        self.getMessage: Callable = lambda: None
        self.messageHandle: Callable = lambda: None
        self.allow_private = allow_private

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
    async def delete(cls, bot: Bot, user: DiscordUser, group: DiscordGroup, is_admin: bool=False):
        if group in cls.center:
            if user in cls.center[group]["players"] or is_admin:
                cls.center.pop(group)
                return True
        elif group in cls.uncomplete:
            if user in cls.uncomplete[group]["players"] or is_admin:
                message_id = cls.uncomplete[group]["message_id"]
                await bot.delete_message(channel_id=group.channel_id, message_id=message_id)
                cls.uncomplete.pop(group)
                return True
        return False

    def begin_message(self):
        def deco(f: Callable[P, str | Message | MessageSegment | Awaitable[str | Message | MessageSegment]]):
            self.getMessage = f
            return f
        return deco
    def begin_message_handle(self):
        def deco_handle(f: Callable):
            self.messageHandle = f
            return f
        return deco_handle
    def start(self):
        async def onBegin(bot: Bot, state: T_State, group: DiscordGroup=Depends(getGroup), user: User=Depends(getUser)):
            if group in self.uncomplete:
                await matcher.send_response("本群已有对局邀请！")
                matcher.skip()
            if group in self.center:
                await matcher.send_response("本群已有对局！")
                matcher.skip()
            self.uncomplete[group] = {"players": [user], "game": self}
            if await self.checkToBegin(group, bot):
                matcher.skip()
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
            state["labels"] = labels
            state["buttons"] = buttons
        async def onBegin2(state: T_State, group: DiscordGroup=Depends(getGroup), middle: Any | None=Depends(self.getMessage)):
            labels = state["labels"]
            buttons = state["buttons"]
            if middle is None:
                await matcher.send_response(labels + buttons)
            else:
                await matcher.send_response(labels + middle + buttons)
            msg = await matcher.get_response()
            self.uncomplete[group]["message_id"] = msg.id
            matcher.skip()
        pml = [Depends(onBegin), Depends(onBegin2), Depends(self.checkBegin)]
        if not self.allow_private:
            pml = [Depends(requireNoDM)] + pml
        f1 = matcher.handle_sub_command(self.name, 'begin',
                parameterless=pml)
        f2 = click.handle([Depends(checkClick), Depends(self.messageHandle), Depends(self.checkBegin)])
        return lambda f: f2(f1(f))

    def process(self):
        @matcher.handle_sub_command(self.name, 'end')
        async def play_end(bot: Bot, group: DiscordGroup=Depends(getGroup), user: DiscordUser=Depends(getUser)):
            # if not event.guild_id:
            #     await matcher.send_response("无法结束！")
            #     return
            # member = await bot.get_guild_member(guild_id=event.guild_id, user_id=user.user_id)
            # if not member.permissions:
            #     await matcher.send_response("无法结束！")
            #     return
            # member.permissions & (1 << 3)
            if await GameSameGroup.delete(bot, user, group, False):
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

async def checkClick(bot: Bot, matcher: Matcher, event: MessageComponentInteractionEvent,
        state: T_State, group: DiscordGroup=Depends(getGroup), user: DiscordUser=Depends(getUser)):
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
    elif button == "close":
        if await GameSameGroup.delete(bot, user, group, False):
            await click.send(MessageSegment.mention_user(user.user_id) + "已删除对局。")
        else:
            await click.send(MessageSegment.mention_user(user.user_id) + "不在对局中，无法删除！")
        matcher.skip()
    state["button_id"] = button

class TRoomPrivate(TypedDict, total=False):
    players: list[DiscordUser]
    begin: bool
    public: bool
    id: int
    type: str
    game: 'GamePrivate'
    password: str | None
    begin_message_ids: dict[DiscordUser, tuple[int, int]]
    __extra_items__: Any

class GamePrivate:
    center: dict[int, TRoomPrivate] = {}
    players_status: dict[DiscordUser, tuple[bool, TRoomPrivate]] = {}  # qq: [bool: ready, room]
    def __init__(self, name: str, name_zh: str, player: Tuple[int, int], allow_group_live: bool = True):
        self.allow_group_live = allow_group_live
        self.name = name
        self.name_zh = name_zh
        self.begin_player = player
        self.types: dict[str, tuple[int, int]] = {'': (0, 32767)}
    def set_types(self, types: dict[str, tuple[int, int]]):
        self.types = types
    def get_event_data(self, user: DiscordUser=Depends(getUser)):
        data = self.players_status.get(user)
        if data:
            return data[1]
    @property
    def data(self):
        return Depends(self.get_event_data)
    def get_delete_func(self, user: DiscordUser=Depends(getUser)):
        async def _h():
            room = self.get_event_data(user)
            if room:
                self.end_room(room)
        return _h
    @property
    def delete_func(self):
        return Depends(self.get_delete_func)
    async def checkInGame(self, matcher: Matcher, user: DiscordUser=Depends(getUser)):
        room = self.get_event_data(user)
        if room is None or not room["begin"] or room["game"] is not self:
            matcher.skip()

    def open(self):
        async def onOpen(type: CommandOption[str], password: CommandOption[str],
                group: DiscordGroup=Depends(getGroup), user: DiscordUser=Depends(getUser)):
            if type not in self.types:
                await matcher.send_response('未发现此分类，支持分类：\n' + '，'.join(self.types))
                matcher.skip()
            private = (password == "")
            if user in self.players_status:
                await matcher.send_response('不能同时进行两个同一游戏')
                matcher.skip()
            elif password is not None and not password.isalnum():
                await matcher.send_response('密码只能包含字母与数字！')
                matcher.skip()
            else:
                prefix = 100
                while 1:
                    r = [i for i in range(
                        prefix, prefix + 100) if i not in self.center]
                    if len(r) == 0:
                        prefix += 100
                    else:
                        break
                room_id = random.choice(r)
                room = self.center[room_id] = {'players': [
                    user], 'public': not private, 'type': type, 'game': self, 'id': room_id, 'password': password,
                    "begin_message_ids": [], "begin": False}
                self.players_status[user] = (False, room)
                msg = self.get_room_status(room)
                await matcher.send_response(msg)
                room["begin_message_ids"][user] = (group.channel_id, (await matcher.get_response()).id)
        return matcher.handle_sub_command(self.name, "open", parameterless=[Depends(onOpen)])
    def attend(self):
        @matcher.handle_sub_command(self.name, "quit")
        async def onQuit(bot: Bot, user: DiscordUser=Depends(getUser)):
            if user not in self.players_status:
                await matcher.send_response("只有在未开始游戏的房间内时才可以退出")
                return
            ready, room = self.players_status[user]
            if room["id"] in self.center:
                await matcher.send_response("只有在未开始游戏的房间内时才可以退出")
            elif len(room['players']) == 1:
                self.end_room(room)
                await matcher.send_response("已退出房间。房间已关闭。")
            else:
                room['players'].remove(user)
                self.players_status.pop(user)
                channel_id, msg_id = room["begin_message_ids"].pop(user)
                await matcher.send_response("已退出房间。")
                await bot.delete_message(channel_id=channel_id, message_id=msg_id)
                await self.update_room_status(room, bot)

        async def onAttend(bot: Bot, id: CommandOption[int], password: CommandOption[str],
            user: DiscordUser=Depends(getUser)):
            # 加入房间
            room = self.center.get(id)
            if room is None:
                await matcher.send_response('未发现此房间')
                matcher.skip()
            elif room["begin"]:
                await matcher.send_response('此房间对战已开始')
                matcher.skip()
            elif not room['public'] and password is None:
                await matcher.send_response('此房间为非公开房间，请输入密码')
                matcher.skip()
            elif not room['public'] and password != room['password']:
                await matcher.send_response('密码错误！')
                matcher.skip()
            elif len(room['players']) == self.types[room['type']][1]:
                await matcher.send_response('房间已满！')
                matcher.skip()
            else:
                room['players'].append(user)
                self.players_status[user] = (False, room)
                await self.update_room_status(room, bot)
        return matcher.handle_sub_command(self.name, "attend", parameterless=[Depends(onAttend)])
    def start(self):
        async def onConfirm(bot: Bot, user: DiscordUser=Depends(getUser)):
            if user not in self.players_status:
                await matcher.send_response("只有在未开始游戏的房间内时才可以准备")
                matcher.skip()
            before, room = self.players_status[user]
            if room["begin"]:
                await matcher.send_response("只有在未开始游戏的房间内时才可以准备")
                matcher.skip()
            self.players_status[user] = (not before, room)
            await matcher.send_response("已取消准备。" if before else "已准备。")
            await self.update_room_status(room, bot)
            if len(room["players"]) < self.begin_player[0] or not all(self.players_status[u][0] for u in room["players"]):
                matcher.skip()
            room["begin"] = True

        return matcher.handle_sub_command(self.name, "confirm", parameterless=[Depends(onConfirm)])
    def process(self):
        return matcher_message.handle([Depends(requireDM), Depends(self.checkInGame)])
    def end_room(self, room: TRoomPrivate):
        for p in room['players']:
            self.players_status.pop(p)
        room_id = room['id']
        if room_id in self.center:
            self.center.pop(room_id)
    def get_room_status(self, room: TRoomPrivate):
        labels = f"## {self.name_zh}游戏对局"
        if room["type"] != "":
            labels += " 类型：" + room["type"]
        labels += "\n    房间号 {id}"
        if room["public"]:
            labels += "   **公开**\n"
        else:
            labels += "   **非公开**\n"
        if self.begin_player[0] == self.begin_player[1]:
            labels += f"游戏人数：{self.begin_player[0]}"
        else:
            labels += f"游戏人数：{self.begin_player[0]}~{self.begin_player[1]}"
        full = len(room["players"]) == self.types[room['type']][1]
        labels += ('  **已满**' if full else '')
        labels += f'\n* ' + "\n* ".join(u.name + ("，**已准备**" if self.players_status[u][0] else "") for u in room['players'])
        return labels
    async def update_room_status(self, room: TRoomPrivate, bot: Bot):
        msg = self.get_room_status(room)
        import asyncio
        await asyncio.gather(bot.edit_message(channel_id=channel_id, message_id=msg_id, content=msg)
                for channel_id, msg_id in room["begin_message_ids"].values())
    async def send(self, bot: Bot, room: TRoomPrivate, msg: str | Message | MessageSegment):
        import asyncio
        await asyncio.gather(bot.send_to(channel_id=channel_id, message=msg)
                for channel_id, _ in room["begin_message_ids"].values())
    async def send_private(self, bot: Bot, room: TRoomPrivate, player: DiscordUser, msg: str | Message | MessageSegment):
        if player not in room["begin_message_ids"]:
            return
        channel_id = room["begin_message_ids"][player][0]
        await bot.send_to(channel_id=channel_id, message=msg)
