import contextlib
from dataclasses import dataclass
from os import path
from nonebot.adapters.discord.commands.matcher import ApplicationCommandMatcher
from nonebot.adapters.discord import Event, MessageEvent, DirectMessageCreateEvent, GuildMessageCreateEvent
from nonebot.adapters.discord.api import Interaction
from nonebot.matcher import Matcher

PATH = "C:\\coolq_data\\"
PATH_IMG = "C:\\go\\data\\images"
PATH_REC = "C:\\Users\\Administrator\\Downloads\\CQP-xiaoi\\酷Q Pro\\data\\record"
PATH_PAGE = "C:\\games"

def rel(rel_path: str):
    return path.join(PATH, rel_path)
def img(rel_path: str):
    return path.join(PATH_IMG, rel_path)
def rec(rel_path: str):
    return path.join(PATH_REC, rel_path)
def pag(rel_path: str):
    return path.join(PATH_PAGE, rel_path)

@contextlib.asynccontextmanager
async def Waiting(matcher: type[ApplicationCommandMatcher]):
    try:
        await matcher.send_deferred_response()
        yield
    except Exception:
        await matcher.edit_response("出现了异常，没有返回！")
        raise

@dataclass(frozen=True)
class Group:
    pass
@dataclass(frozen=True)
class QQGroup(Group):
    group_id: int
    def __str__(self):
        return f"qq:{self.group_id}"
@dataclass(frozen=True)
class DiscordGroup(Group):
    channel_id: int
    def __str__(self):
        return f"discord:{self.channel_id}"
@dataclass(frozen=True)
class User:
    pass
@dataclass(frozen=True)
class QQUser(User):
    user_id: int
    def __str__(self):
        return f"qq:{self.user_id}"
@dataclass(frozen=True)
class DiscordUser(User):
    user_id: int
    name: str
    def __hash__(self) -> int:
        return hash(self.user_id)
    def __str__(self):
        return f"discord:{self.user_id}, name={self.name}"

async def getGroup(event: Event, matcher: Matcher):
    if isinstance(event, (Interaction, MessageEvent)) and (channel_id := event.channel_id):
        return DiscordGroup(channel_id)
    matcher.skip()
async def getUser(event: Event, matcher: Matcher):
    if isinstance(event, Interaction) and event.member and event.member.user:
        return DiscordUser(event.member.user.id, event.member.user.username)
    if isinstance(event, MessageEvent):
        return DiscordUser(event.author.id, event.author.username)
    matcher.skip()
async def requireNoDM(event: Event, matcher: Matcher):
    if isinstance(event, Interaction) and event.channel:
        from nonebot.adapters.discord.api.types import ChannelType
        if event.channel.type != ChannelType.GUILD_TEXT:
            await matcher.send("本指令不允许DM。")
            matcher.skip()
    if isinstance(event, DirectMessageCreateEvent):
        await matcher.send("本指令不允许DM。")
        matcher.skip()
async def requireDM(event: Event, matcher: Matcher):
    if isinstance(event, Interaction) and event.channel:
        from nonebot.adapters.discord.api.types import ChannelType
        if event.channel.type != ChannelType.GROUP_DM:
            await matcher.send("本指令只允许DM。")
            matcher.skip()
    if isinstance(event, GuildMessageCreateEvent):
        await matcher.send("本指令只允许DM。")
        matcher.skip()
# @contextlib.asynccontextmanager
# async def WaitingMessage(matcher: type[Matcher]):
#     try:
#         await matcher.send()
#         yield
#     except Exception:
#         await matcher.edit_response("出现了异常，没有返回！")
#         raise
