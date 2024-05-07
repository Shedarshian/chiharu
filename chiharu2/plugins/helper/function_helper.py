from pebble import concurrent, ThreadPool
from .function.function import parser, ParserError

@concurrent.process(timeout=30)
def calculate(s):
    parser.reset()
    parser.max_sum = 10000
    try:
        return parser.parse(s)
    except ParserError as e:
        return 'SyntaxError: ' + str(e)
    except Exception as e:
        return type(e).__name__ + ': ' + str(e)