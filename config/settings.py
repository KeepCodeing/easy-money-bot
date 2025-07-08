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

# 数据存储目录
DATA_DIR = os.path.join(BASE_DIR, "data")
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# 数据库文件路径
DB_PATH = os.path.join(DATA_DIR, "db.sqlite")

# API配置
API_URL = os.getenv(
    "API_URL", "https://sdt-api.ok-skins.com/user/steam/category/v1/kline"
)  # get 请求
FAV_URL = os.getenv(
    "FAV_URL", "https://sdt-api.ok-skins.com/user/collect/skin/v1/page"
)  # post 请求
PLATFORM = os.getenv("PLATFORM", "YOUPIN")  # 平台，主要使用悠悠有品
DATA_TYPE = os.getenv("DATA_TYPE", 2)  # 数据类型，对应K线tab

FAV_LIST_ID = [
    "1414805408485134336",  # 贴纸1
    "1414804544713326592",  # 贴纸2
    "1414804160054743040",  # 探员
    "1414787065409622016",  # 我的关注
    # "1415633294154125312",  # test
]

# 策略参数
CATEGORY_MONTH = int(os.getenv("CATEGORY_MONTH", 4))  # 4 * 90 = 360天
CATEGORY_DAYS = int(os.getenv("CATEGORY_DAYS", 90))  # 360天
BOLLINGER_PERIOD = int(os.getenv("BOLLINGER_PERIOD", 20))  # 布林线周期
BOLLINGER_STD = int(os.getenv("BOLLINGER_STD", 2))  # 布林线标准差
BOLL_TOLERANCE = float(os.getenv("BOLL_TOLERANCE", 0.01))  # 布林线触碰容差（1%）
VEGAS_EMA1 = int(os.getenv("VEGAS_EMA1", 12))  # 维加斯通道EMA1周期
VEGAS_EMA2 = int(os.getenv("VEGAS_EMA2", 144))  # 维加斯通道EMA2周期
VEGAS_EMA3 = int(os.getenv("VEGAS_EMA3", 169))  # 维加斯通道EMA3周期

# 爬虫配置
CRAWL_INTERVAL = int(os.getenv("CRAWL_INTERVAL", 4))  # 小时

# HTTP请求配置
REQUEST_TIMEOUT = 30  # 请求超时时间（秒）
MAX_RETRIES = 3  # 最大重试次数
RETRY_DELAY = 5  # 重试延迟（秒）

# 爬虫延迟配置
PAGE_DELAY_MIN = 2  # 翻页最小延迟（秒）
PAGE_DELAY_MAX = 5  # 翻页最大延迟（秒）
FOLDER_DELAY_MIN = 3  # 收藏夹切换最小延迟（秒）
FOLDER_DELAY_MAX = 8  # 收藏夹切换最大延迟（秒）
ITEM_DELAY_MIN = 2  # 商品爬取最小延迟（秒）
ITEM_DELAY_MAX = 5  # 商品爬取最大延迟（秒）

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
NATY_SERVER_URL = os.getenv("NATY_SERVER_URL", "https://ntfy.sh")
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "")
