


class Fancy:
    pass
class FancySun(Fancy):
    """支付类的可在任意回合大行动前发动。
    所有得分类的和可以将火龙替换成2分的可以在任何暂停时发动（即完全不占用iter）。
    放龙时依据同色龙得分的必须在放龙前宣言（可随时）。
    依据shop内龙颜色得分的和金币等于开放槽位的自动结算，也可暂停时发动。"""
    pass
class FancyMoon(Fancy):
    pass

from .flamecraft_resource import Resource
