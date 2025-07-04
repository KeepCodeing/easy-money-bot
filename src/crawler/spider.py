#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
爬虫核心模块，负责从API获取数据
"""

import time
import random
import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any
from fake_useragent import UserAgent

from config import settings

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"{settings.LOG_DIR}/crawler.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("crawler")


def generate_timestamps(current_timestamp: int, category_month: int = 4, category_days: int = 90) -> List[int]:
    """
    生成多个时间戳，每个时间戳间隔90天
    
    Args:
        current_timestamp: 当前时间戳（秒）
        category_month: 需要生成的时间戳数量，默认为4
        
    Returns:
        时间戳列表，每个时间戳相差90天
    """
    timestamps = []
    # 将时间戳转换为datetime对象，便于计算日期
    current_date = datetime.fromtimestamp(current_timestamp)
    
    for i in range(category_month):
        # 计算90天前的日期
        past_date = current_date - timedelta(days=category_days * i)
        # 转换回时间戳（秒）
        past_timestamp = int(past_date.timestamp())
        timestamps.append(past_timestamp)
    
    logger.info(f"生成了 {len(timestamps)} 个时间戳，间隔90天")
    return timestamps


class CS2MarketSpider:
    """CS2市场数据爬虫类"""

    def __init__(self):
        """初始化爬虫"""
        self.api_url = settings.API_URL
        self.fav_url = settings.FAV_URL
        self.platform = settings.PLATFORM
        self.data_type = settings.DATA_TYPE
        self.timeout = settings.REQUEST_TIMEOUT
        self.max_retries = settings.MAX_RETRIES
        self.retry_delay = settings.RETRY_DELAY
        self.CATEGORY_MONTH = settings.CATEGORY_MONTH
        self.CATEGORY_DAYS = settings.CATEGORY_DAYS
        
        # 尝试使用fake-useragent，如果失败则使用配置中的用户代理列表
        try:
            self.ua = UserAgent()
            logger.info("成功初始化UserAgent")
        except Exception as e:
            logger.warning(f"初始化UserAgent失败: {e}，将使用预设的用户代理列表")
            self.ua = None
    
    def _get_random_user_agent(self) -> str:
        """获取随机用户代理"""
        if self.ua:
            return self.ua.random
        return random.choice(settings.USER_AGENTS)
    
    def _get_headers(self) -> Dict[str, str]:
        """构建请求头"""
        return {
            'User-Agent': self._get_random_user_agent(),
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://xxx.xxx.com/',
            'Origin': 'https://xxx.xxx.com',
            'Connection': 'keep-alive',
        }
    
    def _make_request(self, url: str, params: Dict[str, Any]) -> Optional[Dict]:
        """发送HTTP请求并处理重试逻辑"""
        for attempt in range(self.max_retries + 1):
            try:
                headers = self._get_headers()
                response = requests.get(url, params=params, headers=headers, timeout=self.timeout)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                if attempt < self.max_retries:
                    wait_time = self.retry_delay * (2 ** attempt)  # 指数退避策略
                    logger.warning(f"请求失败，{wait_time}秒后重试 ({attempt+1}/{self.max_retries}): {e}")
                    time.sleep(wait_time)
                else:
                    logger.error(f"请求失败，已达到最大重试次数: {e}")
                    return None
    
    def get_favorite_items(self) -> List[str]:
        """获取收藏商品ID列表"""
        # TODO: 实现从FAV_URL获取商品ID列表的功能
        # 目前使用测试数据
        logger.info("使用测试商品ID列表")
        return settings.TEST_ITEM_IDS
    
    def get_item_data(self, item_id: str, max_time: Optional[int] = None) -> Optional[Dict]:
        """
        获取单个商品的数据
        
        Args:
            item_id: 商品ID
            max_time: 结束时间戳，默认为当前时间
            
        Returns:
            商品数据字典或None（如果请求失败）
        """
        if max_time is None:
            max_time = int(time.time())
        
        params = {
            'timestamp': int(time.time() * 1000),  # 当前时间戳（毫秒）
            'type': self.data_type,
            'maxTime': max_time,
            'typeVal': item_id,
            'platform': self.platform,
            'specialStyle': ''
        }
        
        logger.info(f"开始获取商品 {item_id} 的数据，maxTime={max_time}")
        result = self._make_request(self.api_url, params)
        
        if result:
            logger.info(f"成功获取商品 {item_id} 的数据")
            return result
        return None
    
    def get_item_history(self, item_id: str) -> List[Dict]:
        """
        获取商品的历史数据（多次请求拼接）
        
        Args:
            item_id: 商品ID
            
        Returns:
            商品历史数据列表
        """
        all_data = []
        current_time = int(time.time())
        
        logger.info(f"开始获取商品 {item_id} 的历史数据，目标天数: {self.CATEGORY_DAYS * self.CATEGORY_MONTH}")
        
        # 生成多个时间戳，每个间隔90天
        timestamps = generate_timestamps(current_time, self.CATEGORY_MONTH, self.CATEGORY_DAYS)
        
        for i, timestamp in enumerate(timestamps):
            logger.info(f"获取第 {i+1}/{len(timestamps)} 批数据，时间戳: {timestamp}")
            data = self.get_item_data(item_id, timestamp)
            
            if not data or 'data' not in data or not data['data']:
                logger.warning(f"时间戳 {timestamp} 没有获取到数据")
                continue
                
            # 提取数据并添加到结果列表
            item_data = data['data']
            logger.info(f"获取到 {len(item_data)} 条数据")
            all_data.extend(item_data)
            
            # 添加延迟，避免请求过于频繁
            if i < len(timestamps) - 1:  # 最后一次请求后不需要延迟
                time.sleep(random.uniform(1, 3))
        
        logger.info(f"商品 {item_id} 的历史数据获取完成，共获取 {len(all_data)} 条数据")
        return all_data
    
    def crawl_all_items(self) -> Dict[str, List[Dict]]:
        """
        爬取所有收藏商品的数据
        
        Returns:
            包含所有商品数据的字典，键为商品ID，值为数据列表
        """
        result = {}
        item_ids = self.get_favorite_items()
        
        logger.info(f"开始爬取 {len(item_ids)} 个商品的数据")
        
        for item_id in item_ids:
            item_data = self.get_item_history(item_id)
            if item_data:
                result[item_id] = item_data
            
            # 添加随机延迟，避免请求过于频繁
            time.sleep(random.uniform(2, 5))
        
        logger.info(f"所有商品数据爬取完成，成功获取 {len(result)} 个商品的数据")
        return result


if __name__ == "__main__":
    # 简单测试
    spider = CS2MarketSpider()
    item_ids = spider.get_favorite_items()
    if item_ids:
        test_id = item_ids[0]
        data = spider.get_item_data(test_id)
        print(f"获取到商品 {test_id} 的数据示例：")
        print(data) 