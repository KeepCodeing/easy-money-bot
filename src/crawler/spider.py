#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
爬虫核心模块，负责从API获取数据
"""

import os
import time
import json
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
        logging.FileHandler(f"{settings.LOG_DIR}/crawler.log", encoding='utf-8'),
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
        self.data_dir = settings.DATA_DIR  # 数据存储目录
        
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
        windows_user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/106.0.0.0",
        ]
        
        return {
            'User-Agent': random.choice(windows_user_agents),
            'Accept': 'application/json',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Content-Type': 'application/json',
            'access-token': '3951fea7-44e3-4368-8099-36d1b1ed86ee', # 暂时不知道这个参数怎么计算出来的，但是GET请求不需要
            'Origin': 'https://steamdt.com',
            'Referer': 'https://steamdt.com/',
            'Connection': 'keep-alive',
            'x-app-version': '1.0.0',
            'x-currency': 'CNY',
            'x-device': '1',
            'x-device-id': 'c98ca51c-7431-430a-b198-7c11ca0a74df',
            'language': 'zh_CN',
            'DNT': '1',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'cross-site',
            'sec-ch-ua': '"Microsoft Edge";v="129", "Not=A?Brand";v="8", "Chromium";v="129"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"'
        }
    
    def _make_request(self, url: str, method: str = 'GET', params: Optional[Dict] = None, json_data: Optional[Dict] = None) -> Optional[Dict]:
        """
        发送HTTP请求并处理重试逻辑
        
        Args:
            url: 请求URL
            method: 请求方法（GET或POST）
            params: URL参数（用于GET请求）
            json_data: JSON数据（用于POST请求）
            
        Returns:
            响应数据（JSON）或None（如果请求失败）
        """
        headers = self._get_headers()
        
        # 打印请求信息
        logger.info(f"发送请求:")
        logger.info(f"Method: {method}")
        logger.info(f"Headers: {headers}")
        
        for attempt in range(settings.MAX_RETRIES + 1):
            try:
                if method.upper() == 'GET':
                    # 准备请求
                    req = requests.Request('GET', url, params=params, headers=headers)
                    prepared_req = req.prepare()
                    # 打印完整URL
                    logger.info(f"完整URL: {prepared_req.url}")
                    
                    # 发送请求
                    session = requests.Session()
                    response = session.send(prepared_req, timeout=settings.REQUEST_TIMEOUT)
                else:
                    # 对于POST请求，将timestamp作为URL参数
                    if json_data and 'timestamp' in json_data:
                        params = {'timestamp': json_data['timestamp']}
                        # 从json_data中移除timestamp
                        json_data = {k: v for k, v in json_data.items() if k != 'timestamp'}
                    
                    # 准备请求
                    req = requests.Request('POST', url, params=params, json=json_data, headers=headers)
                    prepared_req = req.prepare()
                    # 打印完整URL和JSON数据
                    logger.info(f"完整URL: {prepared_req.url}")
                    if json_data:
                        logger.info(f"JSON Data: {json_data}")
                    
                    # 发送请求
                    session = requests.Session()
                    response = session.send(prepared_req, timeout=settings.REQUEST_TIMEOUT)
                
                # 打印响应信息
                logger.info(f"Response Status: {response.status_code}")
                logger.info(f"Response Headers: {dict(response.headers)}")
                logger.info(f"Response Body: {response.text[:1000]}...")  # 只打印前1000个字符
                
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.RequestException as e:
                if attempt < settings.MAX_RETRIES:
                    wait_time = settings.RETRY_DELAY * (2 ** attempt)  # 指数退避策略
                    logger.warning(f"请求失败，{wait_time}秒后重试 ({attempt+1}/{settings.MAX_RETRIES}): {e}")
                    time.sleep(wait_time)
                else:
                    logger.error(f"请求失败，已达到最大重试次数: {e}")
                    return None
    
    def get_favorite_items(self) -> List[Dict]:
        """
        获取收藏商品信息列表
        
        Returns:
            商品信息列表，每个商品包含：
            - item_id: 商品ID
            - name: 商品名称
        """
        items = []
        
        try:
            # 遍历收藏夹ID
            for fav_id in settings.FAV_LIST_ID:
                logger.info(f"正在获取收藏夹 {fav_id} 的商品信息")
                page_num = 1
                
                while True:
                    # 准备请求数据
                    json_data = {
                        "pageSize": 50,
                        "pageNum": page_num,
                        "folder": {
                            "folderId": fav_id,
                            "expected": ""
                        },
                        "platform": settings.PLATFORM,
                        "timestamp": int(time.time() * 1000)
                    }
                    
                    # 发送POST请求
                    response = self._make_request(settings.FAV_URL, method='POST', json_data=json_data)
                    if not response or not response.get('success'):
                        logger.error(f"获取收藏夹 {fav_id} 第 {page_num} 页数据失败")
                        break
                    
                    # 解析数据
                    data = response['data']
                    item_list = data.get('list', [])
                    
                    # 添加商品信息
                    for item in item_list:
                        items.append({
                            'item_id': str(item['itemId']),
                            'name': str(item['name'])
                        })
                    
                    # 检查是否还有下一页
                    total = int(data.get('total', 0))
                    page_size = 50
                    total_pages = (total + page_size - 1) // page_size  # 向上取整计算总页数
                    
                    if page_num >= total_pages:
                        logger.info(f"已到达最后一页（当前第{page_num}页，共{total_pages}页）")
                        break
                    
                    page_num += 1
                    # 随机延迟5-8秒
                    delay = random.uniform(5, 8)
                    logger.info(f"等待 {delay:.1f} 秒后继续...")
                    time.sleep(delay)
                
                # 收藏夹之间随机延迟5-10秒
                if fav_id != settings.FAV_LIST_ID[-1]:
                    delay = random.uniform(5, 10)
                    logger.info(f"等待 {delay:.1f} 秒后继续...")
                    time.sleep(delay)
            
            logger.info(f"共获取到 {len(items)} 个商品信息")
            return items
            
        except Exception as e:
            logger.error(f"获取收藏商品信息失败: {e}")
            return []
    
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
            'type': settings.DATA_TYPE,  # 使用settings中的配置
            'maxTime': max_time,
            'typeVal': item_id,  # 直接使用item_id
            'platform': settings.PLATFORM,  # 使用settings中的配置
            'specialStyle': ''
        }
        
        logger.info(f"开始获取商品 {item_id} 的数据，maxTime={max_time}")
        result = self._make_request(settings.API_URL, params=params)  # 使用settings中的API_URL
        
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
                delay = random.uniform(5, 8)  # 随机延迟5-8秒
                logger.info(f"等待 {delay:.1f} 秒后继续...")
                time.sleep(delay)
        
        if all_data:
            logger.info(f"商品 {item_id} 的历史数据获取完成，共获取 {len(all_data)} 条数据")
        else:
            logger.warning(f"商品 {item_id} 没有获取到任何有效数据")
            
        return all_data
    
    def _create_timestamp_folder(self) -> str:
        """
        创建以当前时间戳命名的文件夹
        
        Returns:
            str: 创建的文件夹路径
        """
        timestamp = int(time.time())
        folder_path = os.path.join(self.data_dir, str(timestamp))
        
        try:
            os.makedirs(folder_path, exist_ok=True)
            logger.info(f"创建数据文件夹: {folder_path}")
            return folder_path
        except Exception as e:
            logger.error(f"创建数据文件夹失败: {e}")
            raise
    
    def _save_item_to_json(self, folder_path: str, item_id: str, name: str, data: List[Dict]) -> bool:
        """
        将单个商品数据保存为JSON文件
        
        Args:
            folder_path: 保存文件夹路径
            item_id: 商品ID
            name: 商品名称
            data: 商品数据
            
        Returns:
            bool: 是否保存成功
        """
        try:
            # 构建文件名（使用商品名称，去除不合法字符）
            safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()
            if not safe_name:  # 如果名称都是不合法字符，使用item_id
                safe_name = f"item_{item_id}"
            
            file_path = os.path.join(folder_path, f"{safe_name}.json")
            
            # 准备数据
            json_data = {
                'item_id': item_id,
                'name': name,
                'timestamp': int(time.time()),
                'data': data
            }
            
            # 保存为JSON文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"成功保存商品数据到文件: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"保存商品 [{name}]({item_id}) 数据到JSON文件失败: {e}")
            return False
    
    def crawl_all_items(self) -> Dict[str, Dict]:
        """
        爬取所有收藏商品的数据并保存为独立的JSON文件
        
        Returns:
            包含所有商品数据的字典，格式为：
            {
                item_id: {
                    name: str,  # 商品名称
                    data: List[Dict]  # 商品数据列表
                }
            }
        """
        result = {}
        items = self.get_favorite_items()
        
        if not items:
            logger.warning("没有获取到任何收藏商品信息")
            return result
        
        logger.info(f"开始爬取 {len(items)} 个商品的数据")
        
        try:
            # 创建时间戳文件夹
            folder_path = self._create_timestamp_folder()
            
            for item in items:
                item_id = item['item_id']
                name = item['name']
                logger.info(f"开始获取商品 [{name}]({item_id}) 的数据")
                
                item_data = self.get_item_history(item_id)
                if item_data:
                    # 保存到内存中的结果字典
                    result[item_id] = {
                        'name': name,
                        'data': item_data
                    }
                    
                    # 保存为独立的JSON文件
                    self._save_item_to_json(folder_path, item_id, name, item_data)
                    logger.info(f"成功获取并保存商品 [{name}]({item_id}) 的数据")
                else:
                    logger.warning(f"获取商品 [{name}]({item_id}) 的数据失败")
                
                # 添加随机延迟，避免请求过于频繁
                if item != items[-1]:  # 如果不是最后一个商品
                    delay = random.uniform(5, 10)  # 随机延迟5-10秒
                    logger.info(f"等待 {delay:.1f} 秒后继续...")
                    time.sleep(delay)
            
            logger.info(f"所有商品数据爬取完成，成功获取 {len(result)} 个商品的数据")
            return result
            
        except Exception as e:
            logger.error(f"爬取过程中发生错误: {e}")
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