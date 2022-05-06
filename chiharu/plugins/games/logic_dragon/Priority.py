from typing import *
from enum import auto, Enum, IntEnum

class UserEvt(Enum):
    OnUserUseCard = auto()
    BeforeCardUse = auto()
    BeforeCardDraw = auto()
    AfterCardUse = auto()
    AfterCardDraw = auto()
    AfterCardDiscard = auto()
    AfterCardRemove = auto()
    AfterCardGive = auto()
    OnDeath = auto()
    OnAttack = auto()
    OnAttacked = auto()
    OnDodged = auto()
    OnStatusAdd = auto()
    OnStatusRemove = auto()
    AfterStatusRemove = auto()
    CheckJibiSpend = auto()
    OnJibiChange = auto()
    AfterJibiChange = auto()
    CheckEventptSpend = auto()
    OnEventptChange = auto()
    BeforeDragoned = auto()
    CheckSuguri = auto()
    OnKeyword = auto()
    OnHiddenKeyword = auto()
    OnDuplicatedWord = auto()
    OnBombed = auto()
    OnDragoned = auto()
    OnNewDay = auto()

class Priority:  # 依照每个优先级从前往后find，而不是iterate
    class OnUserUseCard(IntEnum):
        zhanxingshu = auto()
        temperance = auto()
        cantuse = auto()
        xingyunhufus = auto()
        xingyunhufu = auto()            # 每天一次
    class BeforeCardDraw(IntEnum):
        laplace = auto()
    class BeforeCardUse(IntEnum):
        fool = auto()
        britian = auto()
    class AfterCardUse(IntEnum):
        bingo = auto()
    class AfterCardDraw(IntEnum):
        imitator = auto()
        assembling = auto()
        bingo = auto()
    class AfterCardDiscard(IntEnum):
        inv_belt = auto()
        belt = auto()
    class AfterCardRemove(IntEnum):
        pass
    class AfterCardGive(IntEnum):
        pass
    class OnDeath(IntEnum):
        vampire = auto()             # 吸血鬼：免疫死亡
        explore = auto()                # 秘史衍生：免疫死亡，以及死亡时间减少
        miansi = auto()                 # 倒吊人：免疫一次死亡
        sihuihuibizhiyao = auto()       # 死秽：消耗击毙免疫一次死亡
        hongsezhihuan = auto()          # 虹环：一半免疫一次死亡
        inv_sihuihuibizhiyao = auto()   # 反转死秽
        death = auto()                  # 死神：死亡时间加倍
        fuhuoguanghuan = auto()         # 因hp归零死亡时间除以12
        absorb = auto()                 # 吸收死亡时间
        changsheng = auto()             # 吸收死亡时间MkII
        tiesuolianhuan = auto()         # 铁索连环：一起下地狱
        lveduozhebopu = auto()          # 掠夺者：被弃
        huiye = auto()                  # 宝箱：抽卡
        inv_huiye = auto()              # 反转宝箱
        shangba = auto()                # 伤疤：+2击毙
        invshangba = auto()
        antimatter = auto()             # 反物质维度：自动使用卡牌
        bingo = auto()                  # bingo任务
    class OnAttack(IntEnum):
        imaginebreaker = auto()         # 幻杀：破防
                                        # imagine breaker is suggested to be the first
        youxianshushi = auto()          # 优先术式：无效，变成击杀
        vector = auto()                 # 矢量：双倍
        youlong = auto()                # 幼龙：造成伤害*1.5
        bizhong = auto()                # 必中：必中并且造成伤害*1.5
        konghe = auto()                 # 恐吓：造成伤害减半
    class OnAttacked(IntEnum):
        McGuffium239 = auto()           # 麦高芬：免疫礼物交换
        shanbi = auto()                 # 闪避：躲避受伤
        imaginebreaker = auto()         # 幻杀：无效
        hudun = auto()                  # 护盾：对龙造成伤害的闪避率+20%
        qiangshenjianti = auto()        # 强身健体：受伤减半
        youlong = auto()                # 幼龙：承担受到伤害的50%
        magnet = auto()                 # 磁力菇：移除攻击者的一件金属制品
        vector = auto()                 # 矢量：反弹
                                        # vector is suggested to be the last
    class OnDodged(IntEnum):
        pass
    class OnStatusAdd(IntEnum):
        jiaodai = auto()                # 胶带：免除负面状态
        inv_jiaodai = auto()            # 反转胶带
        paean = auto()                  # 光阴神：3*胶带
        sunflower = auto()              # 向日葵：检测是否密植
        twinsunflower = auto()
        panjue = auto()                 # contains both a and b
        panjue_activated = auto()       # contains both a and b
        beacon = auto()                 # 速度插件：检测寒冰菇
        beacon1 = auto()                # 全局速度插件
        bingo = auto()
    class OnStatusRemove(IntEnum):
        train = auto()
    class AfterStatusRemove(IntEnum):
        antimatter = auto()             # 反物质维度：自动使用卡牌
    class CheckJibiSpend(IntEnum):
        bianyaqi = auto()
        inv_bianyaqi = auto()
        steamsummer = auto()
        beijingcard = auto()
    class OnJibiChange(IntEnum):
        confession = auto()             # 告解：每获得击毙+1击毙
        inv_confession = auto()         # 反转告解
        bikini = auto()                 # 比基尼：有几率翻倍
        schoolsui = auto()              # 死库水：有几率免单
        beacon = auto()                 # 个人插件-产能：有几率加获得，有上限-节能：有几率降支出，有上限
        beacon0 = auto()                # 分享塔全局插件-产能
        beacon2 = auto()                # 分享塔全局插件-节能
        shuairuo = auto()               # 衰弱：获得击毙降为75%
        bianyaqi = auto()               # 变压器：加倍击毙变动
        inv_bianyaqi = auto()           # 反转变压器
        steamsummer = auto()            # Steam夏季促销：减半购买支出
        beijingcard = auto()            # 一卡通：根据消费总量打折
        excogitation = auto()           # 绿帽：击毙减半则免单
        train = auto()                  # 火车：便乘
        bingo = auto()
    class AfterJibiChange(IntEnum):
        zpm = auto()                    #zpm：检查是否消除
    class CheckEventptSpend(IntEnum):
        pass
    class OnEventptChange(IntEnum):
        pass
    class BeforeDragoned(IntEnum):
        explore = auto()                # 秘史：减少此次接龙的死亡时间
        death = auto()                  # 死人不能接龙
        wufazhandou = auto()            # 死人不能接龙
        shengbing = auto()              # 病人也不能接龙
        nodragon = auto()               # 被乐了不能接龙
        juedou = auto()                 # 不能打扰别人的决斗
        minus1ma = auto()               # ±1马：计算距离
        plus1ma = auto()
        iceshroom = auto()              # 冰/热菇：全局计算距离
        hotshroom = auto()
        lazhuyandong = auto()           # 秘史衍生：计算距离
        invlazhuyandong = auto()
        lieshouzhixue = auto()
        invlieshouzhixue = auto()
        ourostone = auto()              # 衔尾蛇：首尾
                                        # contains two buffs
        ranshefashu = auto()            # **法术：首尾
        inv_ranshefashu = auto()
        jiaotu = auto()                 # 秘史衍生：首尾
        invjiaotu = auto()
        shequn = auto()
        invshequn = auto()
        hierophant = auto()             # 教皇：首尾
        inv_hierophant = auto()
        uncertainty = auto()            # 不确定性原理：修改接龙词
    class CheckSuguri(IntEnum):
        jisuzhuangzhi = auto()
    class OnKeyword(IntEnum):
        pass
    class OnHiddenKeyword(IntEnum):
        cunqianguan = auto()
        inv_cunqianguan = auto()
        huxiangjiaohuan = auto()
        moon = auto()
        inv_moon = auto()
    class OnDuplicatedWord(IntEnum):
        hermit = auto()
        kongzhongcanting = auto()       # 空中餐厅「逻辑」：随机复活
    class OnBombed(IntEnum):
        hermit = auto()
        vector = auto()
        kongzhongcanting = auto()       # 空中餐厅「逻辑」：随机复活
    class OnDragoned(IntEnum):
        mofajiqu = auto()               # 魔法汲取：回复MP
        juedou = auto()                 # 决斗减次数
        queststone = auto()             # 任务：完成+3击毙
        quest = auto()
        bingo = auto()                  # bingo：接龙任务
        hierophant = auto()             # 教皇：+2击毙
        inv_hierophant = auto()         # 反转教皇
        lveduozhebopu = auto()          # 掠夺者：偷窃判定
        bianhua = auto()                # 彼岸花：-1/3击毙
        inv_bianhua = auto()            # 反转
        zpm = auto()                    # ZPM：新手保护，+1击毙
        shendian = auto()               # 秘史衍生：+5击毙
        invshendian = auto()
        beizhizhunze = auto()           # +1击毙
        invbeizhizhunze = auto()
        cashprinter = auto()            # 给前面的人+1击毙
        invcashprinter = auto()         # 给前面的人-1击毙
        plus2 = auto()                  # +2：抽两张牌
        xixuegui = auto()               # ？？？？
        panjue = auto()                 # 判决传播 contains both a and b
        panjuecheck = auto()            # 判决重合 contains both a and b
        jack_in_the_box = auto()        # 玩偶匣：爆炸判定
        star = auto()                   # 星星：奖励词判定
        eruption = auto()               # 地火：埋雷判定
        xixueshashou = auto()           # 吸血杀手：抽卡判定
        forkbomb = auto()               # 叉子炸弹：分叉判定
        timebomb = auto()               # 定时炸弹：计次
        circus = auto()                 # 秘史衍生：被弃
        lazhuyandong = auto()
        invlazhuyandong = auto()
        lieshouzhixue = auto()
        invlieshouzhixue = auto()
        shequn = auto()
        invshequn = auto()
        jiaotu = auto()
        invjiaotu = auto()
        explore = auto()                # 秘史
        kongzhongcanting = auto()       # 空中餐厅「逻辑」：随机回满血/复活
        lecheck = auto()                # 乐不思蜀：某其他人不可从此节点接龙
        mindgap = auto()                # 小心空隙：接龙失败，接龙人需再等待2个节点接龙
    class OnNewDay(IntEnum):
        tarot = auto()
        quest = auto()
        sunflower = auto()
        twinsunflower = auto()
        inv_sunflower = auto()
        inv_twinsunflower = auto()
        timebomb = auto()
        earthquake = auto()

exchange: dict[UserEvt, Type[IntEnum]] = {c: Priority.__dict__[c.name] for c in UserEvt}