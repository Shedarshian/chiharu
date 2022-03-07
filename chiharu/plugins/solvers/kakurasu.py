

class Kakurasu:
    def __init__(self) -> None:
        self.max = 11
        self.known = [[0 for i in range(self.max)] for j in range(self.max)]
        self.row_num = list(range(1, self.max + 1))
        self.col_num = list(range(1, self.max + 1))
        self.row_sum = [25, 57, 56, 21, 16, 52, 45, 39, 48, 37, 22]
        self.col_sum = [3, 26, 57, 65, 27, 54, 55, 29, 36, 15, 38]