import math, more_itertools
from dataclasses import dataclass

# 能耗，速度，产能，污染
module_data: list[dict[int, tuple[float, float, float, float]]] = [
    {
        #"name": "speed",
        0: (0, 0, 0, 0),
        1: (0.5, 0.2, 0, 0.04),
        2: (0.6, 0.3, 0, 0.06),
        3: (0.8, 0.4, 0, 0.08),
        4: (1.1, 0.5, 0, 0.1),
        5: (1.5, 0.6, 0, 0.12),
        6: (2, 0.7, 0, 0.14),
        7: (2.6, 0.8, 0, 0.16)
    },
    {
        #"name": "efficiency",
        0: (0, 0, 0, 0),
        1: (-0.4, 0, 0, -0.1),
        2: (-0.6, 0, 0, -0.15),
        3: (-1, 0, 0, -0.2),
        4: (-1.7, 0, 0, -0.25),
        5: (-2.7, 0, 0, -0.3),
        6: (-4, 0, 0, -0.35),
        7: (-5.6, 0, 0, -0.4)
    },
    {
        #"name": "productivity",
        0: (0, 0, 0, 0),
        1: (0.5, -0.1, 0.04, 0.05),
        2: (0.6, -0.15, 0.06, 0.06),
        3: (0.8, -0.2, 0.08, 0.08),
        4: (1, -0.25, 0.1, 0.1),
        5: (1.2, -0.3, 0.12, 0.12),
        6: (1.4, -0.35, 0.14, 0.14),
        7: (1.6, -0.4, 0.16, 0.16),
        9: (2, -0.5, 0.2, 0.2)
    }
]

def module_result(input_speed: dict[str, float],
                  output_speed: dict[str, float],
                  target_speed: tuple[str, float],
                  default_num: tuple[int, int, int],
                  module_level: tuple[int, int, int],
                  tower_range: int,
                  tower_slot: int,
                  tower_efficiency: float=0.5,
                  energy: float=1,
                  pollution: float=1,
                  ifprint: bool=True,
                  only_print: int=-1):
    ret = []
    if target_speed[0] in input_speed:
        machine_num = target_speed[1] / input_speed[target_speed[0]]
    elif target_speed[0] in output_speed:
        machine_num = target_speed[1] / output_speed[target_speed[0]] / (1 + default_num[2] * module_data[2][module_level[2]][2])
    else:
        raise ValueError
    if ifprint and only_print < 0:
        print("个数\t能耗\t速度\t产能\t污染\t实能耗\t台数\t总能耗\t总污染\t输出速\t塔台数\t速度数\t效率数")
    for n in range(tower_slot + 1):
        module_num = tuple(a + tower_efficiency * b for a, b in zip(default_num, (n, tower_slot - n, 0)))
        y = [max(sum(z), -0.8) for z in zip(*(
            tuple(n * c for c in module_data[i][module_level[i]]) for i, n in enumerate(module_num)
        ))]
        y += [
            energy * (1 + y[0]),
            machine_num / (1 + y[1]),
            energy * (1 + y[0]) * machine_num / (1 + y[1]),
            pollution * (1 + y[3]) * machine_num / (1 + y[1]),
            (1 + y[1]) * (1 + y[2]) - 1,
            math.ceil(machine_num / (1 + y[1]) / tower_range),
            math.ceil(machine_num / (1 + y[1]) / tower_range) * n,
            math.ceil(machine_num / (1 + y[1]) / tower_range) * (tower_slot - n)
        ]
        ret.append(y)
    if ifprint and only_print < 0:
        for i, y in enumerate(ret):
            print(f"{i}\t" + "\t".join(f"{x * 100:+4.0f}%" for x in y[:4])
                + "\t" + "\t".join(f"{x:.2f}" for x in y[4:8])
                + "\t" + "\t".join(f"{x * 100:+4.0f}%" for x in y[8:9])
                + "\t" + "\t".join(f"{x:d}" for x in y[9:]))
    if only_print >= 0:
        i, y = only_print, ret[only_print]
        print(f"{i}\t" + "\t".join(f"{x * 100:+4.0f}%" for x in y[:4])
            + "\t" + "\t".join(f"{x:.2f}" for x in y[4:8])
            + "\t" + "\t".join(f"{x * 100:+4.0f}%" for x in y[8:9])
            + "\t" + "\t".join(f"{x:d}" for x in y[9:]))
    return ret

@dataclass
class Recipe:
    left: dict[str, float]
    right: dict[str, float]
    speed: float
    prod: float
    def toReal(self):
        for item in self.right:
            if item in self.left:
                if self.left[item] < self.right[item]:
                    self.right[item] = self.left[item] + self.prod * (self.right[item] - self.left[item])
            else:
                self.right[item] *= self.prod
        for item in self.left:
            self.left[item] *= self.speed
        for item in self.right:
            self.right[item] *= self.speed
        return self
    
@dataclass
class Tower:
    slot: int
    efficiency: float
    speed_num: int
    speed_level: int=1
    efficiency_level: int=1
    productivity_level: int=1
    def getSpeed(self):
        return module_data[0][self.speed_level][1] * self.speed_num * self.efficiency
    def getSpeedUsingNum(self, num: float):
        return module_data[0][self.speed_level][1] * num
    def getProd(self, num: int):
        return module_data[2][self.productivity_level][2] * num
    def getProdSpeed(self, num: int):
        return module_data[2][self.productivity_level][1] * num

"""4kuang=4fen1sha(x1.4)(+32%),4fen=1jing(+24%),2fen2jing1zhongyou=1bang(+40%)"""
# 不吃prod的如蒸汽=循环的，直接手动算回水
def speed_analysis(input: str, intermediate: list[str], object_goal: tuple[str, float] | list[tuple[str, float]], tower: Tower | None=None, only_print: int=0):
    import copy
    intermediate = copy.copy(intermediate)
    tower = tower or Tower(0, 1, 0)
    sentences = input.replace("，", ",").split(",")
    if isinstance(object_goal, tuple):
        object_goal = [object_goal]
    for g in object_goal:
        if g[0] in intermediate:
            intermediate.remove(g[0])
    import re
    import numpy as np
    from scipy.optimize import nnls
    recipes: list[Recipe] = []
    for s in sentences:
        match = re.match(r"^([^()=+%]+)=([^()=+%]+)(?:\(x([^()=+%]+)\))?(?:\(x\+(\d+(?:\.\d+)?)\))?(?:\(\+([^()=+%]+)%\))?(?:\[\+(\d+)\])?(?:\(/(\d+(?:\.\d+)?)s\))?$", s)
        if not match:
            raise ValueError(s)
        l, r, speed_str, speed_num, prod_str, prod_num, time_str = match.groups()
        speed = 1 if speed_str is None else float(speed_str)
        prod = 1 if prod_str is None else 1 + float(prod_str) / 100
        speed += tower.getSpeed()
        if speed_num is not None:
            speed += tower.getSpeedUsingNum(float(speed_num))
        if prod_num is not None:
            speed += tower.getProdSpeed(int(prod_num))
            prod += tower.getProd(int(prod_num))
        if time_str is not None:
            time = float(time_str)
        else:
            time = 1
        name = r"(\d+(?:\.\d+)?(?:\*\d+(?:\.\d+)?)?(?:/\d+(?:\.\d+)?)?)([^()=+%.0-9]+)"
        left: dict[str, float] = {b: eval(a) / time for a, b in re.findall(name, l)}
        right: dict[str, float] = {b: eval(a) / time for a, b in re.findall(name, r)}
        recipes.append(Recipe(left, right, speed, prod).toReal())
    goal: dict[str, float] = {a: 0 for a in intermediate}
    for g in object_goal:
        goal[g[0]] = g[1]

    # 构建并求解线性方程 S @ x = b，目标由 goal 指定

    # collect all item names (ensure goal keys included)
    items = list(set(goal.keys()))
    item_index = {it: i for i, it in enumerate(items)}
    m, n = len(items), len(recipes)
    all_items = [k for r in recipes for k in (*r.left.keys(), *r.right.keys())]
    all_items = list(more_itertools.unique_everseen(all_items))
    all_item_index = {it: i for i, it in enumerate(all_items)}

    # build stoichiometric matrix S (items x recipes): production - consumption
    S = np.zeros((m, n), dtype=float)
    for j, rec in enumerate(recipes):
        for it, amt in rec.right.items():
            if it in items:
                S[item_index[it], j] += amt
        for it, amt in rec.left.items():
            if it in items:
                S[item_index[it], j] -= amt
    all_S = np.zeros((len(all_items), n), dtype=float)
    for j, rec in enumerate(recipes):
        for it, amt in rec.right.items():
            all_S[all_item_index[it], j] += amt
        for it, amt in rec.left.items():
            all_S[all_item_index[it], j] -= amt

    # build demand vector b from goal (net production required)
    b = np.array([goal.get(it, 0.0) for it in items], dtype=float)

    x = np.linalg.solve(S, b)
    row_matrix = all_S * x
    row_sums = row_matrix.sum(axis=1)
    if only_print in (0, 1):
        for item, s_val in zip(all_items, row_sums):
            if s_val > 1e-10 or s_val < -1e-10:
                print(f"{item}: {s_val:.4f}")

    if only_print in (0, 2):
        for r, num in zip(recipes, x):
            print(f"{num:.3f}\t" + ' + '.join(f"{name} {n * num:.4f}" for name, n in r.left.items()) + " = " + ' + '.join(f"{name} {n * num:.4f}" for name, n in r.right.items()))

    return x

if __name__ == "__main__":
    tower = Tower(15, 0.5, 7, 6, 6, 6)
    ret = module_result(input_speed={"A": 20},
                    output_speed={"C": 0.04},
                    target_speed=("A", 400),
                    default_num=(0, 0, 4),
                    module_level=(6, 6, 6),
                    tower_range=3,
                    tower_slot=15,
                    energy=1)

    # s = ("1目录A=1纳米工程1寂介素结构1寂介素能量1星际虚空，1目录B=1奇点1超晶格1时空异常1湮灭，1目录C=4寂介素板4显著数据，1目录D=1星际旅行1传送1虫洞1现实超图分析，2瓶子A=10寂介素板1显著数据1目录A5高级神经凝胶，4瓶子B=1寂介素立方体1显著数据1目录B2瓶子A5高级神经凝胶，6瓶子C=1寂介素超正方体1显著数据1目录C4瓶子B5高级神经凝胶，8瓶子D=1寂介素处理器1显著数据1目录D6瓶子C5高级神经凝胶，1纳米材料=1纳米工程0.05纳米材料，1寂介素锭=1寂介素结构，1寂介素晶1离子罐=1寂介素能量，20纳米材料=1000星际虚空，1寂介素锭=10寂介素板，1纳米材料12寂介素板=1寂介素立方体，1寂介素立方体=0.5奇点0.5寂介素立方体，1纳米材料24寂介素板=6超晶格，1寂介素立方体=0.6时空异常，1寂介素立方体16寂介素板=1寂介素超正方体，2寂介素立方体1时空异常1奇点=4传送，1寂介素立方体=1虫洞，1寂介素处理器=50现实超图分析，1寂介素超正方体4高级神经凝胶=1寂介素处理器，1目标=1瓶子A1瓶子B1瓶子C1瓶子D")
    # zero = ["目录A", "目录B", "目录C", "目录D", "纳米工程", "寂介素结构", "寂介素能量", "星际虚空", "寂介素板", "寂介素立方体", "寂介素超正方体", "奇点", "超晶格", "时空异常", "虫洞", "传送", "现实超图分析", "寂介素处理器", "瓶子A", "瓶子B", "瓶子C", "瓶子D"]
    # speed_analysis(s, zero, ("目标", 0.25), tower)

    s = ("1a1b1e1f=1c1d1g1h,1a1h=1b1d,1c1f=1e1g,1d1e=1f1h,1a1d=1c1e,1b1c=1d1f,1e1h=1g1a")
    zero = list("bcdefgh")
    speed_analysis(s, zero, ("h", 1))

    # 3478 -> 1256
    # (1256 -> 3478)
    ## 27 -> 13
    ## (18 -> 24)
    ## (36 -> 57)
    ## (45 -> 68)
    # (14 -> 35)
    # (23 -> 46)
    # (58 -> 71)
    # 67 -> 82
    # 1 lambda 2 xi 3 zeta 4 theta 5 epsilon 6 phi 7 gamma 8 omega

    # a->b [0] [0 3 1 2] [1 0 0 1]
    # a->c [1] [1 2 0 1] [2 0 0 0]
    # a->d [1] [0 2 0 0] [1 2 0 1]
    # a->e [0] [0 1 1 0] [3 2 0 1]
    # a->f [0] [0 2 0 2] [2 2 0 0]
    # a->g [1] [0 2 2 2] [2 1 1 0]
    # a->h [1] [0 1 1 2] [2 2 0 2]

    # s = ("10维生质=1木材2石矿20维生质块[+4](/5s)，15沙子30维生质块300水=15维生质花[+3](/15s)，1火成岩块200维生质花=40维生质香料0.1维生质提取5甲烷气体[+5](/25s)，30维生质香料1维生质提取=20维生质香料6维生质提取1轻油[+3](/15s)")
    # zero = ["维生质块", "维生质花", "维生质香料"]
    # speed_analysis(s, zero, ("维生质提取", 9.726), tower)

    # s = ("25*1.25/15绿板25*1.25/15玻璃=1.25/15产能插件一(x+4)，25*1.25/15红板2*1.25/15产能插件一50*1.25/15硫磺=1*1.25/15产能插件二(x+4)，25*1.25/20蓝板2*1.25/20产能插件二50*1.25/20火成岩块=1.25/20产能插件三(x+4)，20*1.25/15绿板10*1.25/15固体燃料=1.25/15速度插件一(x+4)，20*1.25/15红板2*1.25/15速度插件一20*1.25/15电动机=1*1.25/15速度插件二(x+4)，20*1.25/20蓝板2*1.25/20速度插件二20*1.25/20大型电动机=1.25/20速度插件三(x+4)，15*1.25/15绿板15*1.25/15铜线A=1.25/15节能插件一(x+4)，15*1.25/15红板2*1.25/15节能插件一15*1.25/15电池=1*1.25/15节能插件二(x+4)，15*1.25/20蓝板2*1.25/20节能插件二30*1.25/20冰晶石棒=1.25/20节能插件三(x+4)，1速度插件三1产能插件三1节能插件三=1插件们，2.5铜板=5铜线A[+4]，5铁板=2.5铁齿轮[+4]，2.5铜板=5铜线B[+4]，1*1.25/0.8铁齿轮6*1.25/0.8铜线B1*1.25/0.8铁板=1电动机[+4]，0.25电动机0.25绿板B0.25钢5润滑油=0.125大型电动机[+4]，0.25铁板0.25铜板5硫酸=0.25电池[+3]，5硫磺1铁板100水=50硫酸[+3]")
    # zero = ["节能插件一", "节能插件二", "速度插件一", "速度插件二", "产能插件一", "产能插件二", "节能插件三", "产能插件三", "速度插件三", "铜线A", "铁齿轮", "铜线B", "电动机", "大型电动机", "电池", "硫酸"]
    # speed_analysis(s, zero, [("插件们", 0.2), ("电动机", 6.12), ("大型电动机", 0.62)], tower)
    # s = ("2.5铜板=5铜线A[+4]，5铁板=2.5铁齿轮[+4]，2.5铜板=5铜线B[+4]，1*1.25/0.8铁齿轮6*1.25/0.8铜线B1*1.25/0.8铁板=1电动机[+4]，0.25电动机0.25绿板B0.25钢5润滑油=0.125大型电动机[+4]")
    # zero = ["铜线A", "铁齿轮", "铜线B", "电动机", "大型电动机"]
    # speed_analysis(s, zero, ("大型电动机", 4.62), tower)
    # s = ("2.5铜板=5铜线A[+4]，5铁板=2.5铁齿轮[+4]，2.5铜板=5铜线B[+4]，1*1.25/0.8铁齿轮6*1.25/0.8铜线B1*1.25/0.8铁板=1电动机[+4]")
    # zero = ["铜线A", "铁齿轮", "铜线B"]
    # speed_analysis(s, zero, ("电动机", 8), tower)
    # s = ("2.5铜板=5铜线A[+4]，5铁板=2.5铁齿轮[+4]，2.5铜板=5铜线B[+4]，1*1.25/0.8铁齿轮6*1.25/0.8铜线B1*1.25/0.8铁板=1电动机[+4]")
    # zero = ["铜线A", "铁齿轮", "铜线B"]
    # speed_analysis(s, zero, ("电动机", 2.111), tower)

    # s = ("5铁板=2.5铁齿轮[+4]，2.5铜板=5铜线[+4]，1*1.25/0.8铁齿轮6*1.25/0.8铜线1*1.25/0.8铁板=1电动机[+4]")
    # zero = ["铁齿轮", "铜线"]
    # speed_analysis(s, zero, ("电动机", 8), tower)

    # s = ("1/4铁齿轮1/4铜板=1/4红瓶[+4]，5铁板=2.5铁齿轮[+4]")
    # zero = ["铁齿轮"]
    # speed_analysis(s, zero, ("红瓶", 3.63), tower)
    # s = ("1/4基础传送带1/8电力机械臂=1/4绿瓶[+4]，5铁板=2.5铁齿轮[+4]，5铁棒2.5单缸发动机=2.5热能机械臂(x+4)，2.5铁板=5铁棒[+4]，25/12铁板25/12铁齿轮=25/12单缸发动机[+4]，2.5电动机2.5热能机械臂=2.5电力机械臂(x+4)")
    # zero = ["铁齿轮", "电力机械臂", "单缸发动机", "铁棒", "热能机械臂"]
    # speed_analysis(s, zero, ("绿瓶", 3.63), tower)
    # s = ("1/8穿甲弹夹1/8手雷1/4石墙=1/4灰瓶[+4]，5/24钢5/12铜板5/12弹夹=5/12穿甲弹夹(x+4)，5铁板=1.25弹夹(x+4)，12.5石砖=2.5石墙(x+4)，50/32煤25/32铁板=5/32手雷(x+4)")
    # zero = ["手雷", "穿甲弹夹", "石墙", "弹夹"]
    # speed_analysis(s, zero, ("灰瓶", 3.63), tower)
    # s = ("1.25/36多缸发动机1.25/12红板1.25/18硫磺=1.25/12蓝瓶[+4]，1/4铁齿轮1/4单缸发动机1/4钢=1/8多缸发动机[+4]")
    # zero = ["多缸发动机"]
    # speed_analysis(s, zero, ("蓝瓶", 3.63), tower)
    # s = ("1.25/80电炉1.25/80速度插件一1.25/80卫星遥测数据=1.25/10黄瓶[+4]，1.25红板0.25钢炉0.25隔热瓦1.25钢=0.25电炉，2.5石砖2.5/6石炉2.5钢=2.5/6钢炉，12.5石矿=2.5石炉，20*1.25/15绿板10*1.25/15固体燃料=1.25/15速度插件一")
    # zero = ["石炉", "钢炉", "电炉", "速度插件一"]
    # speed_analysis(s, zero, ("黄瓶", 3.63), tower)

    # cailiao = ["" for _ in range(16)]
    # s = '，'.join(f"1显著数据1{a}目录A1{a}见解=2{a}包A，1显著数据1{a}目录B1{a}见解2{a}包A=4{a}包B，1显著数据1{a}目录C1{a}见解4{a}包B=6{a}包C，1显著数据1{a}目录D1{a}见解6{a}包C=8{a}包D" for a in "天生能材")
    # s += "，" + '，'.join(f"1{a}目录A1{a}目录B1{a}目录C1{a}目录D=32{a}见解" for a in "天生能材") # 4级
    # # s += "，" + '，'.join(f"1{a}目录A1{a}目录B1{a}目录C=18{a}见解" for a in "天生能材") # 3级
    # s += "，" + ''.join(f"1{a}包{b}" for a in "天生能材" for b in "ABCD")
    # s += "=1目标"
    # s += "，" + ''.join(f"9{a}见解" for a in "天生能材") + "=10显著数据"
    # zero = [a + "包" + b for a in "天生能材" for b in "ABCD"] + [f"{a}见解" for a in "天生能材"] + ["显著数据"]
    # speed_analysis(s, zero, ("目标", 0.5))
    # 0.6646 0.4146 0.2896 0.2063 = 0.5

    # s = ("1红外1可见光1紫外1天体测量=1目录A，1微波1X射线1引力透镜1引力波=1目录B，1无线电1伽马射线1暗物质1负压=1目录C，1暗能量1微型黑洞1零点能1星岩带=1目录D，1天体测量=0.95引力透镜，1天体测量=0.3引力波，1引力透镜1负压=0.9暗物质，1航空框架支架1天体测量=0.9负压，1天体测量1负压=0.75暗能量，1负压=0.4零点能0.4负压，0.6646目录A0.4146目录B0.2896目录C0.2063目录D=0.5目标，1红外1可见光1紫外1微波1X射线1无线电1伽马射线=20天体测量") # 10红外框架=0.85红外，12可见光框架=0.98可见光，10紫外框架=0.9紫外，8微波框架=0.75微波，4X射线框架=0.85X射线，6无线电框架=0.6无线电，3伽马射线框架=0.85伽马射线
    # zero = ["天体测量", "引力透镜", "引力波", "暗物质", "负压", "暗能量", "零点能", "目录A", "目录B", "目录C", "目录D"]
    # speed_analysis(s, zero, ("目标", 0.5))

    # s = "1铱板8寂介素矿=2粉碎的寂介素矿0.1铱粉0.8铱板10水[+4](/2s)，1阴离子交换珠10粉碎的寂介素矿1冰晶石浆2氢氧化铍=0.5阳离子交换珠0.2铍粉6精制寂介素矿4寂介素粉1水[+3](/10s)，1钬线缆2阳离子交换珠20粉碎的寂介素矿1维他命酸=1阴离子交换珠0.2钬粉6精制寂介素矿13寂介素粉1硫酸[+3](/20s)，1维生质试剂8精制寂介素矿10寂介素粉=0.618寂介素晶3.5寂介素粉2.5精制寂介素矿0.382维生质试剂[+2](/16s)，8精制寂介素矿8寂介素粉2寂介素晶25热熔剂25甲烷气体=1寂介素锭[+5](/37.5s)"
    # # s = "1铱板8寂介素矿=2粉碎的寂介素矿0.1铱粉0.8铱板10水[+4](/2s)，1阴离子交换珠10粉碎的寂介素矿1冰晶石浆2氢氧化铍=0.5阳离子交换珠0.2铍粉6精制寂介素矿4寂介素粉1水[+3](/10s)，1钬线缆2阳离子交换珠20粉碎的寂介素矿1维他命酸=1阴离子交换珠0.2钬粉6精制寂介素矿13寂介素粉1硫酸[+3](/20s)，1维生质试剂8精制寂介素矿10寂介素粉=0.618寂介素晶3.5寂介素粉2.5精制寂介素矿0.382维生质试剂[+2](/16s)，8精制寂介素矿8寂介素粉2寂介素晶25热熔剂25甲烷气体=1寂介素锭[+5](/37.5s)，0.05富化火成岩1铱粉=0.2铱炸饼[+2]，0.8铱炸饼0.4热熔剂=0.08铱锭0.4蒸汽[+5]，1铱锭=10铱板，8/3钬粉8/15热熔剂=40/3熔融钬[+5]，0.08沙子10熔融钬=0.04钬锭(x1.8)，1钬锭=10钬板"
    # zero = ["粉碎的寂介素矿", "精制寂介素矿", "寂介素粉", "寂介素晶"]
    # # zero = ["粉碎的寂介素矿", "精制寂介素矿", "寂介素粉", "寂介素晶", "铱粉", "铱炸饼", "铱锭", "钬粉", "熔融钬", "钬锭"]
    # speed_analysis(s, zero, [("寂介素锭", 0.226)], tower)

    # s = "1电导率1电磁场1极化1辐射=1目录A，1量子现象1原子1亚原子1力场=1目录B，1超导1夸克1纠缠1轻子=1目录C，1玻色子1聚变1磁单极子1恒星=1目录D，0.6646目录A0.4146目录B0.2896目录C0.2063目录D=0.5目标，1电磁场1极化=0.5力场，1力场=1聚变，1电磁场=0.3磁单极子"
    # zero = ["力场", "聚变", "磁单极子", "目录A", "目录B", "目录C", "目录D"]
    # speed_analysis(s, zero, ("目标", 0.5))

    # s = ("2绿柱石1/2硫酸=1/2硫酸铍0.125沙子0.5水[+3]，1/15冰晶石棒25/15硫酸铍25/15水=50/15氢氧化铍[+3]，4氢氧化铍=4铍粉1水[+3]，200/75铍粉40/75热熔剂=1000/75熔融铍[+5]，2/25沙子250/25熔融铍=1/25铍锭，5硫磺1铁板100水=50硫酸[+3]，1沙子1火成岩=10热熔剂[+3]")
    # zero = ["硫酸铍", "氢氧化铍", "铍粉", "熔融铍", "硫酸", "热熔剂"]
    # # speed_analysis(s, zero, ("绿柱石", -45), tower)
    # speed_analysis(s, zero, ("铍锭", 500*100), tower)

    # s = ("1材料测试包5沙子100等离子流=200粒子流，1石矿10化学凝胶=100等离子流，10宇宙水100石油气=20化学凝胶，99水1润滑油=100宇宙水，1塑料1石矿1铁板1铜板=1材料测试包[+4]，1聚变实验数据50粒子流25超低温导热液=10铁矿1污料0.99聚变实验数据0.01垃圾数据卡25高温导热液，1聚变实验数据50粒子流25超低温导热液=10铜矿1污料0.99聚变实验数据0.01垃圾数据卡25高温导热液，1聚变实验数据50粒子流25超低温导热液=10石矿1污料0.99聚变实验数据0.01垃圾数据卡25高温导热液，1石矿=3沙子[+4]，24铁矿10热熔剂=900熔融铁[+4]，24铜矿10热熔剂=900熔融铜[+4]，250熔融铁=10铁板，250熔融铜=10铜板，1沙子1火成岩块=10热熔剂[+3]，1聚变实验数据50粒子流25超低温导热液=1火成岩1污料0.99聚变实验数据0.01垃圾数据卡25高温导热液，6火成岩=0.25石矿3粉碎的火成岩0.1富化火成岩[+4]，1硫磺10粉碎的火成岩1富化火成岩=0.2沙子4富化火成岩4粉碎的火成岩[+2]，1粉碎的火成岩2富化火成岩5水1石油气=1火成岩块3.96水[+5]，1力场数据50质子流=1聚变实验数据，4钬电缆1电磁场数据1极化数据10超低温导热液=0.5力场数据1空白数据卡0.49垃圾数据卡1污料10高温导热液，1空白数据卡50离子流10低温导热液=0.95电磁场数据0.04垃圾数据卡10高温导热液，2多光谱镜10空白数据卡10低温导热液=9极化数据1垃圾数据卡2废料10中温导热液，80中温导热液1冰晶石浆=60低温导热液20高温导热液，60低温导热液1冰晶石浆=40超低温导热液20高温导热液，500高温导热液=499中温导热液，1硫磺1铁板1铜板20重油5化学凝胶=10高温导热液，1铁板100等离子流=100质子流，1聚变实验数据50粒子流25超低温导热液=1冰晶石1污料0.99聚变实验数据0.01垃圾数据卡25高温导热液，1冰晶石=1冰晶石粉0.25沙子[+4]，4冰晶石粉20蒸汽=1冰晶石晶体2水[+3]，2冰晶石粉2冰晶石晶体1重油=1冰晶石棒[+5]，1冰晶石棒1硫酸=10冰晶石浆[+3]，5硫磺1铁板100水=50硫酸[+3]，1聚变实验数据50粒子流25超低温导热液=1钬矿1污料0.99聚变实验数据0.01垃圾数据卡25高温导热液，2钬矿=1粉碎的钬矿石0.25石矿[+4]，1阴离子交换珠1粉碎的钬矿石2水=0.25氯化钬0.5阴离子交换珠0.5粉碎的钬矿石0.1沙子[+3]，1铜线5氯化钬=10钬粉[+2]，50钬粉10热熔剂=250熔融钬[+5]，2沙子250熔融钬=10钬板，1塑料2钬板=2钬电缆[+4]，1塑料1冰晶石棒5硫酸5蒸汽=10阴离子交换珠[+3]，1铜板100等离子流=100离子流，1轻质框架2玻璃2铱板5润滑油5化学凝胶=1多光谱镜5废料，32沙子10热熔剂=12玻璃[+5]，1铜板=2铜线[+4]，1航空框架支架2塑料2玻璃2钢=2轻质框架[+4]，500熔融铁8煤矿=10钢，4航空框架杆1冰晶石棒=1航空框架支架[+4]，1铁棒2铍板=1航空框架杆[+4]，1铁板=2铁棒[+4]，100生化污泥=99生化软泥0.01污料，100宇宙污水=0.01污料99宇宙水1生化污泥，20污料2宇宙水=20废料1宇宙污水1生化污泥，1废料=0.1铁矿0.1铜矿0.1石矿0.1重油，1聚变实验数据50粒子流25超低温导热液=1铱矿1污料0.99聚变实验数据0.01垃圾数据卡25高温导热液，1聚变实验数据50粒子流25超低温导热液=1绿柱石1污料0.99聚变实验数据0.01垃圾数据卡25高温导热液，1铱矿=0.4铱矿0.3粉碎的铱矿石0.1沙子[+4]，1阳离子交换珠1粉碎的铱矿石2水=0.5铱粉2/3阳离子交换珠0.5粉碎的铱矿石0.1沙子[+3]，1富化火成岩20铱粉=4铱炸饼[+2]，10铱炸饼5热熔剂=10铱板5蒸汽[+5]，1塑料1火成岩5硫酸5蒸汽=10阳离子交换珠[+3]，4绿柱石1硫酸=1硫酸铍0.25沙子1水[+3]，1冰晶石棒25硫酸铍25水=50氢氧化铍[+3]，4氢氧化铍=4铍粉1水[+3]，50铍粉10热熔剂=250熔融铍[+5]，2沙子250熔融铍=10铍板，1煤矿20石油气=2塑料[+3]，30水30石油气=2硫磺[+3]，10冰晶石浆1重油=20润滑油[+3]，1垃圾数据卡1超低温导热液=0.9空白数据卡0.09损坏的数据卡1高温导热液，1损坏的数据卡=5废料，3红板6铜板4抛光的数据存储基板=1空白数据卡，1粗糙的数据存储基板1化学凝胶=1抛光的数据存储基板，2玻璃4铁板=1粗糙的数据存储基板0.5废料[+4]，4铜线2绿板2塑料=1红板[+4]，3铜线1石板=1绿板[+4]，1石砖=4石板[+4]，2石矿=1石砖[+2]")
    # zero = ["等离子流", "化学凝胶", "宇宙水", "材料测试包", "沙子", "铁矿", "铜矿", "熔融铁", "熔融铜", "粒子流", "铁板", "铜板", "石矿", "热熔剂", "火成岩块", "火成岩", "粉碎的火成岩", "富化火成岩", "聚变实验数据", "力场数据", "电磁场数据", "极化数据", "超低温导热液", "低温导热液", "中温导热液", "高温导热液", "质子流", "冰晶石棒", "冰晶石", "冰晶石粉", "冰晶石晶体", "冰晶石浆", "硫酸", "钬矿", "粉碎的钬矿石", "氯化钬", "钬粉", "熔融钬", "钬板", "钬电缆", "阴离子交换珠", "离子流", "多光谱镜", "玻璃", "铜线", "轻质框架", "钢", "航空框架支架", "航空框架杆", "铁棒", "污料", "废料", "生化污泥", "宇宙污水", "铱矿", "粉碎的铱矿石", "铱粉", "铱板", "铱炸饼", "阳离子交换珠", "绿柱石", "硫酸铍", "氢氧化铍", "铍粉", "熔融铍", "铍板", "塑料", "硫磺", "润滑油", "垃圾数据卡", "损坏的数据卡", "空白数据卡", "抛光的数据存储基板", "粗糙的数据存储基板", "红板", "绿板", "石板", "石砖"]
    # for x in ("铁板", "铜板", "石矿", "火成岩块", "冰晶石棒", "钬板", "铍板", "铱板"):
    #     speed_analysis(s, zero, (x, 1), tower, only_print=1)
    #     print("----------------   =1" + x)

    # s = ("10水20原油=4重油14轻油6石油气[+3]，15水20重油=15轻油[+3]，15水15轻油=10石油气[+3]，30水30石油气=2硫磺[+3]")
    # zero = ["重油", "轻油", "石油气"]
    # speed_analysis(s, zero, ("硫磺", 15), tower)
    # s = ("10水20原油=4重油14轻油6石油气[+3]，15水20重油=15轻油[+3]，15水15轻油=10石油气[+3]，1煤矿20石油气=2塑料[+3]")
    # zero = ["重油", "轻油", "石油气"]
    # speed_analysis(s, zero, ("塑料", 15/20*30), tower)
    # s = ("10水20原油=4重油14轻油6石油气[+3]，15水20重油=15轻油[+3]，20轻油=2固体燃料[+3]，10轻油10固体燃料=1固态火箭燃料[+3]")
    # zero = ["重油", "轻油", "固体燃料"]
    # speed_analysis(s, zero, ("原油", -320), tower)

    # s = ("2铱矿=0.8铱矿0.6粉碎的铱矿石0.2沙子(x1.4)[+3]，1阳离子交换珠1粉碎的铱矿石2水=0.5铱粉2/3阳离子交换珠0.5粉碎的铱矿石0.1沙子[+3]，0.1塑料0.1火成岩0.5硫酸0.5蒸汽=1阳离子交换珠[+3]，0.05富化火成岩1铱粉=0.2铱炸饼[+2]，0.8铱炸饼0.4热熔剂=0.08铱锭0.4蒸汽[+5]，1沙子1火成岩=10热熔剂[+3]，0.1硫酸1铱矿脉=1铱矿，5硫磺1铁板100水=50硫酸[+3]")
    # zero = ["粉碎的铱矿石", "阳离子交换珠", "铱粉", "铱炸饼", "热熔剂", "铱矿", "硫酸"]
    # speed_analysis(s, zero, ("铱锭", 1.5), tower)

    # s = ("4钬矿=2粉碎的钬矿石0.5石矿[+4]，1阴离子交换珠1粉碎的钬矿石2水=0.25氯化钬0.5阴离子交换珠0.5粉碎的钬矿石0.1沙子[+2]，0.1塑料0.1冰晶石0.5硫酸0.5蒸汽=1阴离子交换珠[+2]，1铜线5氯化钬=10钬粉[+2]，8/3钬粉8/15热熔剂=40/3熔融钬[+5]，0.08沙子10熔融钬=0.04钬锭(x1.8)，1沙子1火成岩块=10热熔剂[+2]，2.5铜板=5铜线[+4]")
    # zero = ["粉碎的钬矿石", "阴离子交换珠", "氯化钬", "钬粉", "熔融钬", "热熔剂", "铜线"]
    # speed_analysis(s, zero, ("钬矿", -45), tower)

    # s = ("50甲烷5化学凝胶10生化软泥20宇宙水=50营养凝胶"
    # s = ("1煤4化学凝胶20生化软泥25宇宙水=50营养凝胶"
    #       + "，1玻璃1铁板50营养凝胶=5营养物池，10营养物池5维生质香料10遗传学数据50生化软泥=10生物培养9遗传学数据1垃圾数据卡，1空白数据卡10生化软泥=1遗传学数据9宇宙污水，10生物培养100营养凝胶=10生物质30生化污泥20宇宙污水，100生化污泥=99生化软泥0.01污料，100宇宙污水=0.01污料99宇宙水1生化污泥，20污料2宇宙水=20废料1宇宙污水1生化污泥，1生物质10宇宙水=1污料30生化软泥")
    # zero = ["营养凝胶", "遗传学数据", "营养物池", "生物培养", "生化污泥", "宇宙污水", "污料", "生化软泥"]
    # speed_analysis(s, zero, ("生物质", 5))
    # s = ("1煤4化学凝胶20生化软泥25宇宙水=50营养凝胶"
    #       + "，1玻璃1铁板50营养凝胶=5营养物池，10营养物池5维生质香料10遗传学数据50生化软泥=10生物培养9遗传学数据1垃圾数据卡，1空白数据卡10生化软泥=1遗传学数据9宇宙污水，20污料2宇宙水=20废料1宇宙污水1生化污泥，1营养物池1维生质提取1实验遗传学数据10生化软泥=1实验生物培养1垃圾数据卡，10实验生物培养100营养凝胶=7.5实验生物质2.5生物质30生化污泥20宇宙污水")
    # zero = ["营养凝胶", "遗传学数据", "营养物池", "生物培养", "污料", "实验生物培养"]
    # speed_analysis(s, zero, ("实验生物质", 2.5))

    # s = "2wsz=0.2mu0.4shi4kuai(x0.8)(+32%),1sha2kuai20shui=1hua(x1.2)(+16%),0.04huo8hua=1.6xiang0.004ti0.2jia(x0.6)(+40%),2xiang1/15ti=4/3xiang0.4ti1/15you(x1.2)(+16%),1shi=3sha(x0.8)(+32%),10jiang100jia=10bing(x2.8)"
    # speed_analysis(s, ["kuai", "hua", "xiang", "sha", "jia"], ("ti", 50000))
    # s = "1sha2kuai20shui=1hua(x1.2)(+16%),0.04huo8hua=1.6xiang0.004ti0.2jia(x0.6)(+40%),2xiang1/15ti=4/3xiang0.4ti1/15you(x1.2)(+16%)"
    # speed_analysis(s, ["hua", "xiang"], ("kuai", -90))
    # s = "2wsz=0.2mu0.4shi4kuai(x0.8)(+32%)"
    # speed_analysis(s, [], ("kuai", 90))