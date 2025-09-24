#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
配置管理模块
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

# 加载.env文件中的环境变量
load_dotenv()

# 项目根目录
BASE_DIR = Path(__file__).parent.parent.absolute()

# 数据存储配置
DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data"
)  # 数据根目录

# 确保必要的子目录存在
os.makedirs(os.path.join(DATA_DIR, "items"), exist_ok=True)  # 商品数据目录
os.makedirs(os.path.join(DATA_DIR, "charts"), exist_ok=True)  # 图表目录
os.makedirs(os.path.join(DATA_DIR, "signals"), exist_ok=True)  # 信号目录

# 数据库文件路径
DB_PATH = os.path.join(DATA_DIR, "db.sqlite")

# API配置
KLINE_URL = os.getenv(
    "KLINE_URL", "https://sdt-api.ok-skins.com/user/steam/category/v1/kline"
)  # get 请求
FAV_URL = os.getenv(
    "FAV_URL", "https://sdt-api.ok-skins.com/user/collect/skin/v1/page"
)  # post 请求
TOTAL_BUY_RANK = os.getenv(
    "TOTAL_BUY_RANK", "https://sdt-api.ok-skins.com/user/ranking/v1/page"
)  # post 请求
FAV_LIST_URL = os.getenv(
    "FAV_LIST_URL", "http://sdt-api.ok-skins.com/user/collect/skin/folder/v1/list"
)  # get 请求

INVENTORY_URL = os.getenv(
    "INVENTORY_URL", "https://api.steamdt.com/user/steam/inventory/v3"
)

INVENTORY_STEAM_ID = os.getenv("INVENTORY_STEAM_ID", "")

TYPE_TREND_URL = os.getenv(
    "TYPE_TREND_URL", "https://sdt-api.ok-skins.com/user/steam/type-trend/v2/item/details"
)  # post 请求

PLATFORM = os.getenv("PLATFORM", "YOUPIN")  # 平台，主要使用悠悠有品
DATA_TYPE = os.getenv("DATA_TYPE", 2)  # 数据类型，对应K线tab

MIN_SELL_NUM = 50  # 最低在售数量

# 交易量排行榜配置
TOP_TOTAL_BUY_COUNT = 10  # 获取前10个数据
TOTAL_BUY_DAY_RANGE = "ONE_DAY"  # 统计时间段
RANK_DATA_FIELD = "transactionCount"  # 排序字段：sellNumsRate（在售数量变化率）或 transactionCount（交易量）
RANK_SORT_TYPE = "DESC"  # 排序方式：ASC（升序）或 DESC（降序）

TOP_TOTAL_SELL_COUNT = 5  # 获取前5个数据
TOTAL_SELL_DAY_RANGE = "ONE_DAY"  # 统计时间段
RANK_SELL_FIELD = "transactionCount"  # sellNumsDiff 在售数量变化
RANK_SELL_SORT_TYPE = "DESC"  # 排序方式：ASC（升序）或 DESC（降序）
SELL_MIN_VAL = 20 # 最低在售价格
SELL_MAX_VAL = 1000 # 最高在售价格
SELL_FILTER_EXTERIOR = "WearCategory0" # 外观：崭新出厂
SELL_FILTER_QUANLITY = "normal" # 类型：普通
SELL_WEAPON_TPYES = [("CSGO_Type_Rifle:weapon_awp", "AWP"), 
                     ("CSGO_Type_Rifle:weapon_ak47", "AK-47"), 
                     ("CSGO_Type_Rifle:weapon_m4a1_silencer", "M4A1"), 
                     ("CSGO_Type_Rifle:weapon_m4a1", "M4A4"), 
                     ("CSGO_Type_Pistol:weapon_deagle", "Deagle"), 
                     ("CSGO_Type_Pistol:weapon_usp_silencer", "USP"), 
                     ("CSGO_Type_Pistol:weapon_glock", "Glock"), 
                     ("Type_CustomPlayer:customplayer_counter_strike", "CounterStrike"),
                     ("Type_CustomPlayer:customplayer_terrorist", "Terrorist")]


FAV_LIST_ID = [
    # "1399917014021996544",  # 手套
    # "1399947806538366976",  # 收藏品
    # "1417735341674864640",  # 刀皮
    # "1414804160054743040",  # 探员
    # "1417733750678888448",  # 千战百战
    # "1418012730076360704",  # 十战个战
    # "1417747830720622592",  # 贴纸
    # "1414787065409622016",  # 鸟狙
    "1415633294154125312",  # test
]

# 策略参数
CATEGORY_MONTH = int(os.getenv("CATEGORY_MONTH", 4))  # 4 * 90 = 360天
CATEGORY_DAYS = int(os.getenv("CATEGORY_DAYS", 90))  # 360天

BOLLINGER_PERIOD = int(os.getenv("BOLLINGER_PERIOD", 20))  # 布林线周期
BOLLINGER_STD = int(os.getenv("BOLLINGER_STD", 2))  # 布林线标准差

# 布林线触碰容差值（上轨和下轨分别设置）
BOLL_TOLERANCE_UPPER = 0.01  # 上轨容差 0.5%
BOLL_TOLERANCE_LOWER = 0.01  # 下轨容差 0.5%

VEGAS_EMA1 = int(os.getenv("VEGAS_EMA1", 12))  # 维加斯通道EMA1周期
VEGAS_EMA2 = int(os.getenv("VEGAS_EMA2", 144))  # 维加斯通道EMA2周期
VEGAS_EMA3 = int(os.getenv("VEGAS_EMA3", 169))  # 维加斯通道EMA3周期

VOLUME_MA1 = int(os.getenv("VOLUME_MA1", 5))  # 成交量MA1周期
VOLUME_MA2 = int(os.getenv("VOLUME_MA2", 10))  # 成交量MA2周期
VOLUME_MA3 = int(os.getenv("VOLUME_MA3", 20))  # 成交量MA3周期

VOLUME_MA1_FILTER_SCORE = int(os.getenv("VOLUME_MA1_FILTER_SCORE", 150)) # 成交量 / MA1 > FILTER，认为有吸筹迹象
VOLUME_MA_FILTER_DAY_RANGE = int(os.getenv("VOLUME_MA_FILTER_DAY_RANGE", 5)) # 计算近N天内的吸筹迹象
MIN_VOLUME_COUNT = int(os.getenv("MIN_VOLUME_COUNT", 50)) # 最低成交量

TREAD_FILTER_DAY_RANGE = int(os.getenv("TREAD_FILTER_DAY_RANGE", 14)) # 趋势过滤天数

# 爬虫配置
CRAWL_INTERVAL = int(os.getenv("CRAWL_INTERVAL", 4))  # 小时

# 图表配置
CHART_DAYS = int(os.getenv("CHART_DAYS", 30))  # 图表显示天数
SAVE_CHART = os.getenv("SAVE_CHART", False )  # 是否保存图表

# 存储配置
SAVE_JSON = os.getenv("SAVE_JSON", True)  # 是否保存json

# HTTP请求配置
REQUEST_TIMEOUT = 30  # 请求超时时间（秒）
MAX_RETRIES = 3  # 最大重试次数
RETRY_DELAY = 5  # 重试延迟（秒）

# 爬虫延迟配置
PAGE_DELAY_MIN = 1  # 翻页最小延迟（秒）
PAGE_DELAY_MAX = 4  # 翻页最大延迟（秒）
FOLDER_DELAY_MIN = 2  # 收藏夹切换最小延迟（秒）
FOLDER_DELAY_MAX = 5  # 收藏夹切换最大延迟（秒）
ITEM_DELAY_MIN = 5 # 商品爬取最小延迟（秒）
ITEM_DELAY_MAX = 10  # 商品爬取最大延迟（秒）

# 用户代理列表
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
]

# 测试商品ID列表（实际应从FAV_URL获取）
TEST_ITEM_IDS = [
    # '525873303', # 树篱
    "1315938982167306240",  # 怪B
]

# 日志配置
LOG_DIR = os.path.join(BASE_DIR, "logs")
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# 消息推送配置
NATY_TOPIC_BUY_SELL_NOTIFY = os.getenv("NATY_TOPIC_BUY_SELL_NOTIFY", "catch_money")
NATY_SERVER_URL = os.getenv("NATY_SERVER_URL", "https://ntfy.sh")  # change it on .env
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "")  # change it on .env
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN", "") # chang it on .env

STRATEGYS = ['RSI', 'MACD', 'Bollinger', 'Vegas', 'CsMa']
INVENTORY_STRATEGYS = ['RSI', 'Bollinger']