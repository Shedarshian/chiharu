import itertools, more_itertools

class Recipe:
    def __init__(self, input: dict[str, int],
                 output: dict[str, int],
                 time: float,
                 electricity: float,
                 can_prod: bool):
        pass

class Step:
    def __init__(self, name: str,
                 time: float,
                 electricity: float):
        self.electricity = electricity
    def require(self) -> 'list[Step]':
        return []
class StepResearch(Step):
    pass
class StepMachine(Step):
    pass
class StepElectricity(Step):
    pass

