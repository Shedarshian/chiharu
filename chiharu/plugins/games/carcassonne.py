import random, itertools

class Tile:
    def __init__(self) -> None:
        self.segments: list[Segment] = []
        self.features: list[Feature] = []
        self.tokens: list[Token] = []
class Segment:
    def __init__(self) -> None:
        self.features: list[Feature] = []
        self.tokens: list[Token] = []
class Object:
    def __init__(self) -> None:
        self.segments: list[Segment] = []
        self.tokens: list[Token] = []
class Feature:
    def __init__(self) -> None:
        self.tokens: list[Token] = []
class Token:
    pass


