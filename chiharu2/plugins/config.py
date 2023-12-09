import itertools
import functools
import json
import datetime
import getopt
from functools import singledispatch
from os import path
import traceback

PATH = "C:\\coolq_data\\"
PATH_IMG = "C:\\go\\data\\images"
PATH_REC = "C:\\Users\\Administrator\\Downloads\\CQP-xiaoi\\酷Q Pro\\data\\record"
PATH_PAGE = "C:\\games"

def rel(rel_path):
    return path.join(PATH, rel_path)
def img(rel_path):
    return path.join(PATH_IMG, rel_path)
def rec(rel_path):
    return path.join(PATH_REC, rel_path)
def pag(rel_path):
    return path.join(PATH_PAGE, rel_path)

selfqq = 2711644761
is_chinatsu = True
