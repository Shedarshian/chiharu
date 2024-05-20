import itertools
import functools
import json
import datetime
import getopt
from functools import singledispatch
import traceback
from nonebot.message import run_postprocessor
from nonebot.matcher import Matcher
from nonebot.adapters.discord import Bot, Event, InteractionCreateEvent, MessageSegment, MessageEvent

@run_postprocessor
async def _(bot: Bot, event: Event, e: Exception):
    if isinstance(event, InteractionCreateEvent):
        channel = MessageSegment.mention_channel(event.channel_id) if event.channel_id else "<no id>"
        user = MessageSegment.mention_user(event.member.user.id) if event.member and event.member.user else "<no id>"
        msg = "An Error occured in channel: " + channel + " by user " + user + ".\n The stack trace is:\n```\n" + ''.join(traceback.format_exception(e)) + "```" # type: ignore
    elif isinstance(event, MessageEvent):
        channel = MessageSegment.mention_channel(event.channel_id)
        user = MessageSegment.mention_user(event.user_id)
        msg = "An Error occured in channel: " + channel + " by user " + user + ".\n The stack trace is:\n```\n" + ''.join(traceback.format_exception(e)) + "```" # type: ignore
    else:
        msg = "An Error occured.\n The stack trace is:\n```\n" + ''.join(traceback.format_exception(e)) + "```"
    from .helper.helper import rel
    import datetime
    with open(rel("error.txt"), '+') as f:
        f.write(datetime.datetime.now().isoformat() + msg + "\n\n")
    await bot.send_to(1237726203029225484, msg)