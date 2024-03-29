from os import path

import nonebot
import config

if __name__ == '__main__':
    nonebot.init(config)
    nonebot.load_plugins(path.join(path.dirname(__file__), 'chiharu', 'plugins'), 'chiharu.plugins')
    nonebot.load_plugins(path.join(path.dirname(__file__), 'chiharu', 'plugins', 'games'), 'chiharu.plugins.games')
    nonebot.run(host='127.0.0.1', port=8000)