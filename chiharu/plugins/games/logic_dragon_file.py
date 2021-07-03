import random, more_itertools
from functools import reduce
from pypinyin import pinyin, Style

mission = []
def add_mission(doc):
    def _(f):
        global mission
        mission.append((len(mission), doc, f))
        return f
    return _
def get_mission():
    return random.randint(0, len(mission) - 1)

for i in range(2, 9):
    add_mission(f"字数为{i}。")((lambda i: lambda s: len([c for c in s if c != ' ']) == i)(i))
add_mission("包含一个亿或以下的常用单汉字数字或阿拉伯数字。")(lambda s: len(set(s) & set('0123456789零一二三四五六七八九十百千万亿兆壹贰叁肆伍陆柒捌玖拾佰仟卅')) != 0)
add_mission("包含一个常用的人称代词。")(lambda s: len(set(s) & set('我你他她它祂您怹咱俺恁')) != 0)
@add_mission("包含一个中国的省级行政单位的全称。")
def _(s):
    for c in ("黑龙江", "吉林", "辽宁", "河北", "河南", "山东", "山西", "安徽", "江西", "江苏", "浙江", "福建", "台湾", "广东", "湖南", "湖北", "海南", "云南", "贵州", "四川", "青海", "甘肃", "陕西", "内蒙古自治区", "新疆维吾尔自治区", "广西壮族自治区", "宁夏回族自治区", "西藏自治区", "北京", "天津", "上海", "重庆", "香港特别行政区", "澳门特别行政区"):
        if c in s:
            return True
    return False
add_mission("包含的/地/得。")(lambda s: len(set(s) & set('的地得')) != 0)
add_mission("包含叠字。")(lambda s: any(a == b and ord(a) > 255 for a, b in more_itertools.windowed(s, 2)))
for c in ("人", "大", "小", "方", "龙"):
    add_mission(f"包含“{c}”。")((lambda c: lambda s: c in s)(c))
@add_mission("包含国际单位制的七个基本单位制之一。")
def _(s):
    for c in ("米", "千克", "公斤", "秒", "安", "开", "摩尔", "坎德拉"):
        if c in s:
            return True
    return False
add_mission("前两个字的声母相同。")(lambda s: len(p := pinyin(s[0:2], style=Style.INITIALS, strict=True, errors='ignore', heteronym=True)) >= 2 and len(set(p[0]) & set(p[1])) != 0)
add_mission("前两个字的韵母相同。")(lambda s: len(p := pinyin(s[0:2], style=Style.FINALS, strict=True, errors='ignore', heteronym=True)) >= 2 and len(set(p[0]) & set(p[1])) != 0)
add_mission("首字没有声母。")(lambda s: len(p := pinyin(s[0:1], style=Style.INITIALS, strict=True, errors='ignore', heteronym=True)) >= 1 and '' in p[0])
add_mission("首字是多音字。")(lambda s: len(p := pinyin(s[0:1], style=Style.INITIALS, strict=True, errors='ignore', heteronym=True)) >= 1 and len(p[0]) > 1)
add_mission("所有字音调相同且至少包含两个字。")(lambda s: len(p := pinyin(s, style=Style.FINALS_TONE3, neutral_tone_with_five=True, strict=True, errors='ignore', heteronym=True)) > 1 and len(reduce(lambda x, y: x & y, (set(c[-1] for c in s) for s in p))) != 0)
