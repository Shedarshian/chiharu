from typing import TypedDict
from datetime import datetime, time, date
import json, re
from nonebot import CommandSession
from . import config
from .config import 句尾
from .inject import on_command

config.CommandGroup(('misc', 'alarm'), short_des='闹钟与备忘录。')

class TAlarm(TypedDict):
    name: str
    time: datetime | time
    routine: str # once, daily, weekly, monthly
    routine_num: list[int]
    description: str
    qq: int
    group: int | None
with open(config.rel("alarm.json"), encoding='utf-8') as f:
    alarm: list[TAlarm] = [{**a, "time": (datetime.fromisoformat(a["time"]) if a["routine"] == "once" else
            time.fromisoformat(a["time"]))} for a in json.load(f)]
def save_alarm():
    with open(config.rel("alarm.json"), 'w', encoding='utf-8') as f:
        f.write(json.dumps([{**a, "time": a["time"].isoformat()} for a in alarm], ensure_ascii=False, indent=4))

@on_command(('misc', 'alarm', 'set'), only_to_me=False, short_des="设置闹钟。")
@config.ErrorHandle
async def alarmset(session: CommandSession):
    """设置闹钟。
    直接输入-alarm.set YY-MM-DD HH:MM，然后按提示输入名称描述循环即可。"""
    try:
        group = int(session.ctx["group_id"])
    except KeyError:
        group = None
    user = int(session.ctx["user_id"])
    match = re.search(r"(?:([0-9]{1,2})-([0-9]{1,2})-([0-9]{1,2}) )?([0-9]{1,2}):([0-9]{1,2})", session.current_arg_text)
    if not match:
        session.finish("请输入合法的时间。")
    if match.group(1) is not None:
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))
        d: date | None = date(year=year, month=month, day=day)
    else:
        d = None
    shi = int(match.group(4))
    fen = int(match.group(5))
    routines = await session.aget(prompt="是否循环？请输入“无”“每日”“每周几周几”“每月几日几日”等。")
    match = re.search(r"每日|每((?:周一|周二|周三|周四|周五|周六|周日)+)|每月((?:\d+(?:日|号))+)", routines)
    if not match:
        routine = "once"
        routine_num: list[int] = []
        ret = "一次性"
    elif match.group(0) == "每日":
        routine = "daily"
        routine_num = []
        ret = "每日循环"
    elif match.group(1) is not None:
        routine = "weekly"
        routine_num = ["日一二三四五六".index(x) for x in match.group(1)[1:].split("周")]
        ret = "每周循环，" + ''.join(("周" + "日一二三四五六"[i]) for i in routine_num)
    elif match.group(2) is not None:
        routine = "monthly"
        routine_num = [int(x) for x in re.findall("\d+", match.group(2))]
        ret = "每月循环，" + ''.join((str(i) + "日") for i in routine_num)
    else:
        routine = "once"
        routine_num = []
        ret = "一次性"
    if routine == "once" and d is None:
        session.finish("选择一次性时需提前输入年月日。")
    name_des: str = await session.aget(prompt=f"您选择了{ret}。\n请输入闹钟名称，换行后可选择是否加闹钟简介。")
    l = name_des.split("\n", 2)
    if len(l) == 1:
        name = name_des.strip()
        des = ""
    else:
        name = l[0].strip()
        des = l[1].strip()
    alarm.append({"name": name, "description": des, "group": group, "qq": user, "routine": routine,
            "routine_num": routine_num, "time": (datetime(year=d.year, month=d.month, day=d.day, hour=shi, minute=fen)
            if routine == "once" and d is not None else time(hour=shi, minute=fen))})
    save_alarm()
    await session.send("成功添加闹钟" + name + 句尾)

@on_command(('misc', 'alarm', 'check'), only_to_me=False, short_des="查询闹钟。")
@config.ErrorHandle
async def alarmcheck(session: CommandSession):
    try:
        group = int(session.ctx["group_id"])
    except KeyError:
        group = None
    user = int(session.ctx["user_id"])
    l = [d for d in alarm if d["group"] == group and d["qq"] == user]
    beg = "您在" + ("此群" if group is not None else "私聊")
    if len(l) == 0:
        session.finish(beg + "没有建立闹钟" + 句尾)
    def r(d: TAlarm):
        if d['routine'] == "daily":
            return "每日循环"
        if d['routine'] == "weekly":
            return "每周循环，" + ''.join(("周" + "日一二三四五六"[i]) for i in d["routine_num"])
        if d["routine"] == "monthly":
            return "每月循环，" + ''.join((str(i) + "日") for i in d["routine_num"])
        return "一次性"
    await session.send(beg + "的闹钟有：\n" + '\n'.join(f"{d['name']}：{d['time'].isoformat()}，{r(d)}" + ("" if d['description'] is None else "\n" + d['description']) for d in l))