from abc import ABC
from dataclasses import dataclass
from typing import Generator, TypeVar, Literal
from enum import IntFlag

@dataclass
class HaiConfig:
    hasHua: bool = False            # 是否有花牌
    hasFeng: bool = True            # 是否有风牌
    hasSanYuan: bool = True         # 是否有三元牌
    wangPai: int = 14               # 王牌数量
    shoupaiNum: int = 13            # 手牌数量
    hasBaopai: bool = False         # 是否有宝牌
    hasLibaopai: bool = False       # 是否有里宝牌
    hasGangbaopai: bool = False     # 是否有杠宝牌
    hasHongbaopai: bool = False     # 是否有红宝牌
@dataclass
class RuleConfig:
    class BanMingpai(IntFlag):
        none = 0
        chi = 1 << 0
        peng = 1 << 1
        minggang = 1 << 2
        angang = 1 << 3
        jiagang = 1 << 4
    banMingpai: BanMingpai = 0          # 禁止吃碰杠
    penghougang: bool = False           # 是否允许吃碰后杠牌
    banShiti: bool = False              # 是否禁止食替
    shepaizhenting: bool = False        # 是否存在舍牌振听
    lizhizhenting: bool = False         # 是否存在立直振听
    tongxunzhenting: bool = False       # 是否存在同巡振听
    genzhangmianze: bool = False        # 是否存在跟张免责
    genzhangmianzeUpgrade: bool = False # 是否存在高级版跟张免责
    class Tuzhongliuju(IntFlag):
        none = 0
        jiuzhongjiupai = 1 << 0
        sifenglianda = 1 << 1
        sigangsanliao = 1 << 2
        sijializhi = 1 << 3
        sanjiaheliao = 1 << 4
    tuzhongiuju: Tuzhongliuju = Tuzhongliuju.none
    liujumanguan: bool = False          # 是否存在流局满贯
    angangmingpai: bool = True          # 暗杠是否明牌
    hasQianggang: bool = True           # 是否允许抢杠
    guoshiwushuangQiangangang: bool = False     # 是否允许国士无双抢暗杠
    minggangbaopai: bool = False        # 明杠是否包牌
    fufenxuxing: bool = True            # 是否允许负分续行
@dataclass
class ProcedureConfig:
    playerNum: Literal[3, 4] = 4    # 玩家数量，3人麻将时自动去除北家
    baNum: Literal[1, 2, 4] = 2     # 场数量，1为东风场，2为半庄，4为全庄
    renChan: bool = True            # 是否允许连庄
@dataclass
class SpecialTypeConfig:
    fafu: int = 0                   # 流局罚符
    shiduan: bool = False           # 是否允许食断
    xiru: bool = False              # 是否允许西入
    beiru: bool = False             # 是否允许北入
    kongtingfafu: bool = False      # 空听（听的所有牌都在自己手中）是否罚符
    alllastLianzhuang: bool = False # 是否允许all last连庄
    toutiao: bool = False           # 是否存在头跳
    qihe: bool = 1                  # 起和/番缚
    gangbaopaijifan: bool = False   # （非暗杠的）杠宝牌是否立即翻开
    leijiyiman: bool = False        # 是否存在累计役满

@dataclass
class Config:
    hai: HaiConfig = HaiConfig()
    rule: RuleConfig = RuleConfig()
    procedure: ProcedureConfig = ProcedureConfig()
    special: SpecialTypeConfig = SpecialTypeConfig()

@dataclass
class Send:
    last_err: int
@dataclass
class Recieve:
    pass

T = TypeVar('T')
TAsync = Generator[Send, Recieve, T]