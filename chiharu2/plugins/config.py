import itertools
import functools
import json
import datetime
import getopt
from functools import singledispatch
from os import path
import traceback
from nonebot.message import run_postprocessor
from nonebot.matcher import Matcher
from nonebot.adapters.discord import Bot, Event, InteractionCreateEvent, MessageSegment, MessageEvent

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

selfqq = 2711644761
is_chinatsu = True

@run_postprocessor
async def _(bot: Bot, event: Event, e: Exception):
    if isinstance(event, InteractionCreateEvent):
        channel = MessageSegment.mention_channel(event.channel_id) if event.channel_id else "<no id>"
        user = MessageSegment.mention_user(event.member.user.id) if event.member and event.member.user else "<no id>"
        await bot.send_to(1237726203029225484, "An Error occured in channel: " + channel + " by user " + user + ".\n The stack trace is:\n```\n" + ''.join(traceback.format_exception(e)) + "```")
    elif isinstance(event, MessageEvent):
        channel = MessageSegment.mention_channel(event.channel_id)
        user = MessageSegment.mention_user(event.user_id)
        await bot.send_to(1237726203029225484, "An Error occured in channel: " + channel + " by user " + user + ".\n The stack trace is:\n```\n" + ''.join(traceback.format_exception(e)) + "```")
    else:
        await bot.send_to(1237726203029225484, "An Error occured.\n The stack trace is:\n```\n" + ''.join(traceback.format_exception(e)) + "```")