from functools import singledispatch
import traceback
from nonebot.message import run_postprocessor
from nonebot.matcher import Matcher
from nonebot.adapters.discord import Bot, Event, InteractionCreateEvent, MessageSegment, MessageEvent

@run_postprocessor
async def _(bot: Bot, event: Event, e: Exception):
    err = ''.join(traceback.format_exception(e))
    if (ind := err.find("await self.simple_run")) != -1:
        err = err[ind - 4:]
    if isinstance(event, InteractionCreateEvent):
        channel = MessageSegment.mention_channel(event.channel_id) if event.channel_id else "<no id>"
        user = MessageSegment.mention_user(event.member.user.id) if event.member and event.member.user else "<no id>"
        msg = "An Error occured in channel: " + channel + " by user " + user + ".\n The stack trace is:\n```\n" + err + "```" # type: ignore
    elif isinstance(event, MessageEvent):
        channel = MessageSegment.mention_channel(event.channel_id)
        user = MessageSegment.mention_user(event.user_id)
        msg = "An Error occured in channel: " + channel + " by user " + user + ".\n The stack trace is:\n```\n" + err + "```" # type: ignore
    else:
        msg = "An Error occured.\n The stack trace is:\n```\n" + err + "```"
    from .helper.helper import rel
    import datetime
    await bot.send_to(1237726203029225484, msg)
    with open(rel("error.txt"), 'r+') as f:
        f.write(datetime.datetime.now().isoformat() + ''.join(traceback.format_exception(e)) + "\n\n")