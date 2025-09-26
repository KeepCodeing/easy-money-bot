#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
SteamDt (steamdt) 平台爬虫实现。
继承自 SpiderInterface，负责从该平台获取市场数据。
"""

import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set

import random
from .spider_interface import SpiderInterface

# 从项目配置中导入设置
from config import settings

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"{settings.LOG_DIR}/crawler.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("crawler")

class SteamDtSpider(SpiderInterface):
    """
    针对SteamDt (ok-skins.com) 平台的爬虫实现。
    """

    def __init__(self):
        """初始化平台特定的API地址"""
        super().__init__()
        self.KLINE_URL = settings.KLINE_URL
        self.FAV_URL = settings.FAV_URL
        self.FAV_LIST_ID = settings.FAV_LIST_ID
        self.PLATFORM = settings.PLATFORM
        # 数据类别配置
        self.CATEGORY_MONTH = settings.CATEGORY_MONTH
        self.CATEGORY_DAYS = settings.CATEGORY_DAYS

    def _get_base_headers(self) -> Dict[str, str]:
        """
        重写基类方法，提供SteamDt平台专用的请求头。
        """
        base_headers = super()._get_base_headers()
        steam_dt_headers = {
            'Accept': 'application/json',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'Content-Type': 'application/json',
            'access-token': settings.ACCESS_TOKEN,
            'Origin': 'https://steamdt.com',
            'Referer': 'https://steamdt.com/',
            'x-app-version': '1.0.0',
            'x-currency': 'CNY',
            'x-device': '1',
            'x-device-id': 'c98ca51c-7431-430a-b198-7c11ca0a74df',
            'language': 'zh_CN',
        }
        base_headers.update(steam_dt_headers)
        return base_headers
    
    def _get_favorite_folders_names(self) -> Dict[str, str]:
        """
        获取收藏夹列表
        
        Returns:
            Dict[str, str]: 以收藏夹ID为key，收藏夹名称为value的字典
        """
        try:
            logger.info("开始获取收藏夹列表")
            
            # 准备请求参数
            params = {
                'timestamp': int(time.time() * 1000),  # 当前时间戳（毫秒）
                'platform': settings.PLATFORM
            }
            
            # 发送请求
            response = self._make_request(settings.FAV_LIST_URL, method='GET', params=params)
            
            if not response or not response.get('success'):
                logger.error("获取收藏夹列表失败")
                return {}
            
            # 解析数据
            folders = response.get('data', [])
            result = {
                folder['folderId']: folder['folderName']
                for folder in folders
                if 'folderId' in folder and 'folderName' in folder
            }
            
            logger.info(f"成功获取到 {len(result)} 个收藏夹信息")
            return result
            
        except Exception as e:
            logger.error(f"获取收藏夹列表时发生错误: {e}")
            return {}

    def get_favorite_items(self) -> List[Dict[str, str]]:
        """
        获取所有已配置收藏夹中的商品列表。
        """
        fav_list = []

        fav_list_names = self._get_favorite_folders_names()

        logger.info(f"开始从 {len(self.FAV_LIST_ID)} 个收藏夹中获取商品列表...")

        for fav_id in self.FAV_LIST_ID:
            logger.info(f"正在处理收藏夹 ID: {fav_id}")
            page_num = 1
            items = []
            while True:
                json_data = {
                    "pageSize": 50,
                    "pageNum": page_num,
                    "folder": {"folderId": fav_id, "expected": ""},
                    "platform": self.PLATFORM,
                    "timestamp": int(time.time() * 1000)
                }

                response = self._make_request(self.FAV_URL, method='POST', json_data=json_data)

                if not response or not response.get('success'):
                    logger.error(f"获取收藏夹 {fav_id} 第 {page_num} 页数据失败。")
                    break

                data = response.get('data', {})
                item_list = data.get('list', [])

                if not item_list:
                    logger.info(f"收藏夹 {fav_id} 已无更多商品。")
                    break

                for item in item_list:
                    items.append({
                            'item_id': str(item['itemId']),
                            'name': str(item['name'])
                        })
                
                total = int(data.get('total', 0))
                total_pages = (total + 49) // 50  # 向上取整
                if page_num >= total_pages:
                    fav_list.append({ 'name': fav_list_names[fav_id], 'id': fav_id, 'items': items })
                    break
                
                page_num += 1
                time.sleep(random.uniform(settings.PAGE_DELAY_MIN, settings.PAGE_DELAY_MAX))
        
        # logger.info(f"成功获取到 {len(all_items)} 个不重复的收藏商品。")
        return fav_list


    def _generate_timestamps(self, current_timestamp: int, category_month: int = 4, category_days: int = 90) -> List[int]:
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
        
        return timestamps

    def _get_item_data(self, item_id: str, max_time: Optional[int] = None) -> Optional[Dict]:
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
            'type': settings.DATA_TYPE,  # 使用settings中的配置
            'maxTime': max_time,
            'typeVal': item_id,  # 直接使用item_id
            'platform': settings.PLATFORM,  # 使用settings中的配置
            'specialStyle': ''
        }
        
        logger.info(f"开始获取商品 {item_id} 的数据，maxTime={max_time}")
        result = self._make_request(settings.KLINE_URL, params=params)  # 使用settings中的KLINE_URL
        
        if result:
            logger.info(f"成功获取商品 {item_id} 的数据")
            return result
        return None

    def get_item_kline_history(self, item_id: str) -> List[list]:
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
        timestamps = self._generate_timestamps(current_time, self.CATEGORY_MONTH, self.CATEGORY_DAYS)
        
        for i, timestamp in enumerate(timestamps):
            logger.info(f"获取第 {i+1}/{len(timestamps)} 批数据，时间戳: {timestamp}")
            data = self._get_item_data(item_id, timestamp)
            
            if not data or 'data' not in data or not data['data']:
                logger.warning(f"时间戳 {timestamp} 没有获取到数据，由于是按时间顺序请求，终止后续请求")
                break  # 如果某个时间段没有数据，更早的时间段也不会有数据，直接结束
                
            # 提取数据并添加到结果列表
            item_data = data['data']
            logger.info(f"获取到 {len(item_data)} 条数据")
            
            # 检查是否有实际的价格数据
            valid_data = [d for d in item_data if any(float(x) > 0 for x in d[1:5])]  # 检查OHLC是否都为0
            if not valid_data:
                logger.warning(f"时间戳 {timestamp} 的数据全部为0，可能是无效数据，终止后续请求")
                break
            
            all_data.extend(item_data)
            
            # 添加延迟，避免请求过于频繁
            if i < len(timestamps) - 1:  # 最后一次请求后不需要延迟
                delay = random.uniform(settings.ITEM_DELAY_MIN, settings.ITEM_DELAY_MAX)  # 使用配置的翻页延迟
                logger.info(f"等待 {delay:.1f} 秒后继续...")
                time.sleep(delay)
        
        if all_data:
            logger.info(f"商品 {item_id} 的历史数据获取完成，共获取 {len(all_data)} 条数据")
        else:
            logger.warning(f"商品 {item_id} 没有获取到任何有效数据")
            
        return all_data
    
    def get_inventory_items(self) -> Dict[str, str]:
        """
        获取库存内饰品列表
        """
        try:
            logger.info("开始获取库存饰品列表")
            
            # 准备请求参数
            params = {
                'timestamp': int(time.time() * 1000),  # 当前时间戳（毫秒）
                'app_id': 730, # 魔法数字
                'sticker_evaluate': 0, 
                'steam_id': settings.INVENTORY_STEAM_ID
            }
            
            # 发送请求
            response = self._make_request(settings.INVENTORY_URL, method='GET', params=params)
            
            if not response or not response.get('success'):
                logger.error("获取库存饰品列表失败")
                return {}
            
            # 解析数据
            inventory = response.get('data', []).get('inventory', [])
            
            assets = inventory.get('assets', [])
            classinfos = inventory.get('classinfos', {})
            
            item_ids = {}
            
            for item in assets:
                classinfoKey = item['classinfoKey']
                item_ids[item['itemId']] = classinfos[classinfoKey]['name']
            
            logger.info(f"成功获取到 {len(item_ids)} 饰品信息")
            return item_ids
            
        except Exception as e:
            logger.error(f"获取库存饰品列表时发生错误: {e}")
            return {}