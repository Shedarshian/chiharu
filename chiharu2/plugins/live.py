import asyncio, requests, json, re, os
from typing import Any
from nonebot import require
from .helper.helper import rel
from nonebot import get_bot
from nonebot.adapters.discord import Bot, InteractionCreateEvent, ReadyEvent
from nonebot.adapters.discord.commands import CommandOption, on_slash_command
from nonebot.adapters.discord.api import StringOption, IntegerOption, SubCommandOption
from nonebot.message import event_postprocessor
from apscheduler.triggers.interval import IntervalTrigger
from nonebot.log import logger

require("nonebot_plugin_apscheduler")

from nonebot_plugin_apscheduler import scheduler

matcher = on_slash_command(
    name="live_monitor",
    description="直播监控",
    options=[
        SubCommandOption(
        name="add",
        description="添加直播间监控",
        options=[
             IntegerOption(
                name="room_id",
                description="直播间ID"
            )
        ]
    ),
    SubCommandOption(
        name="list",
        description="列出正在监控的直播间"
    ),
    SubCommandOption(
        name="remove",
        description="移除直播间监控",
        options=[
             IntegerOption(
                name="room_id",
                description="直播间ID"
            )
        ]
     )
    ]
)

def search_ret(ret):
    match = re.search(r'\{.*\}', ret)
    return "{}" if not match else match.group(0)

async def get_live_status(room_id: int) -> dict[str, Any] | None:
    loop = asyncio.get_event_loop()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
    }
    url = await loop.run_in_executor(None, lambda url: requests.get(url, headers=headers), f'https://api.live.bilibili.com/xlive/web-room/v1/index/getRoomPlayInfo?room_id={room_id}')
    response = json.loads(search_ret(url.text))
    if response['data']['live_status'] == 1:
        return {}
    return None

@event_postprocessor
async def ready(bot: Bot, event: ReadyEvent):
    id = bot.self_id
    scheduler.add_job(monitor_live_status,
                      IntervalTrigger(seconds=60),
                      id=0, max_instances=1, coalesce=True,
                      kwargs={"bot_id": id})

async def monitor_live_status(bot_id: str):
    bot = get_bot(bot_id)
    if not os.path.exists(rel("live.json")):
        with open(rel("live.json"), 'w') as f:
            json.dump({}, f)
    with open(rel("live.json"), 'r') as f:
        live_status: dict[str, Any] = json.load(f)
    updated: list[tuple[int, str, dict[str, Any]]] = []
    for channel_id, channel in live_status.items():
        for room_id, room in channel.items():
            try:
                is_live = await get_live_status(int(room_id))
                pass_live = room["streaming"]
                room["streaming"] = is_live is not None
                if is_live is not None and not pass_live:
                    updated.append((room_id, channel_id, is_live))
            except Exception as e:
                import traceback
                logger.error(f"Error while checking live status: {e.__class__.__name__} {e.args} {traceback.format_exc()}")
    with open(rel("live.json"), 'w') as f:
        json.dump(live_status, f)
    for room_id, channel, info in updated:
        await bot.send_to(channel, f"Room https://live.bilibili.com/{room_id} is now live!")

@matcher.handle_sub_command("add")
async def handle_add_live_monitor(room_id: CommandOption[int], event: InteractionCreateEvent):
    if not os.path.exists(rel("live.json")):
        with open(rel("live.json"), 'w') as f:
            json.dump({}, f)
    with open(rel("live.json"), 'r') as f:
        live_status: dict[str, Any] = json.load(f)
    if str(event.channel_id) not in live_status:
        live_status[str(event.channel_id)] = {}
    status = await get_live_status(room_id)
    live_status[str(event.channel_id)][str(room_id)] = {
        "streaming": status is not None,
        "channel": event.channel_id
    }
    with open(rel("live.json"), 'w') as f:
        json.dump(live_status, f)
    this_live_status = "Live" if status is not None else "Offline"
    await matcher.send_response(f"Room https://live.bilibili.com/{room_id} is now being monitored!\nCurrent status: {this_live_status}")

@matcher.handle_sub_command("list")
async def handle_list_live_monitor(event: InteractionCreateEvent):
    if not os.path.exists(rel("live.json")):
        with open(rel("live.json"), 'w') as f:
            json.dump({}, f)
    with open(rel("live.json"), 'r') as f:
        live_status: dict[str, Any] = json.load(f)
    if not live_status or str(event.channel_id) not in live_status:
        await matcher.send_response("No rooms are being monitored.")
    else:
        response = "Currently monitored rooms:\n"
        for room_id, info in live_status[str(event.channel_id)].items():
            if info["channel"] != event.channel_id:
                continue
            status = await get_live_status(int(room_id))
            this_live_status = "Live" if status is not None else "Offline"
            response += f"- Room https://live.bilibili.com/{room_id} {this_live_status}\n"
        await matcher.send_response(response)

@matcher.handle_sub_command("remove")
async def handle_remove_live_monitor(room_id: CommandOption[int], event: InteractionCreateEvent):
    if not os.path.exists(rel("live.json")):
        with open(rel("live.json"), 'w') as f:
            json.dump({}, f)
    with open(rel("live.json"), 'r') as f:
        live_status: dict[str, Any] = json.load(f)
    if str(event.channel_id) in live_status and str(room_id) in live_status[str(event.channel_id)]:
        del live_status[str(event.channel_id)][str(room_id)]
        with open(rel("live.json"), 'w') as f:
            json.dump(live_status, f)
        await matcher.send_response(f"Room https://live.bilibili.com/{room_id} is no longer being monitored.")
    else:
        await matcher.send_response(f"Room https://live.bilibili.com/{room_id} was not being monitored.")