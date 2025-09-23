#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
爬虫模块接口基类
"""

import abc
import random
import time
from typing import Dict, List, Optional, Any, Set

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 可以考虑将配置项移至 config/settings.py
REQUEST_TIMEOUT = 30  # 请求超时时间（秒）
MAX_RETRIES = 3       # 最大重试次数
RETRY_BACKOFF_FACTOR = 0.5 # 重试退避因子
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36"
]


class SpiderInterface(abc.ABC):
    """
    爬虫接口基类 (Abstract Base Class)。

    定义了所有平台爬虫必须遵循的通用接口和基础功能，
    包括会话管理、请求重试、User-Agent伪装等。
    """

    def __init__(self):
        """初始化爬虫会话和通用配置"""
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """
        创建一个配置了重试机制的requests会话。

        Returns:
            requests.Session: 配置好的会话对象。
        """
        session = requests.Session()
        # 定义重试策略
        retry_strategy = Retry(
            total=MAX_RETRIES,
            status_forcelist=[429, 500, 502, 503, 504], # 针对特定状态码重试
            backoff_factor=RETRY_BACKOFF_FACTOR
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _get_random_user_agent(self) -> str:
        """
        从预设列表中随机选择一个User-Agent。

        Returns:
            str: 一个随机的User-Agent字符串。
        """
        return random.choice(USER_AGENTS)

    def _get_base_headers(self) -> Dict[str, str]:
        """
        获取包含随机User-Agent的基础请求头。
        子类可以重写此方法以添加平台特定的请求头。

        Returns:
            Dict[str, str]: 包含通用请求头的字典。
        """
        return {
            'User-Agent': self._get_random_user_agent(),
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.5',
        }

    def _make_request(
        self,
        url: str,
        method: str = 'GET',
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        extra_headers: Optional[Dict] = None
    ) -> Optional[Any]:
        """
        发送HTTP请求的核心方法，包含完整的错误处理和重试逻辑。

        Args:
            url (str): 请求的目标URL。
            method (str, optional): HTTP请求方法. 默认为'GET'。
            params (Optional[Dict], optional): URL查询参数. 默认为None。
            json_data (Optional[Dict], optional): POST请求的JSON body. 默认为None。
            extra_headers (Optional[Dict], optional): 额外的请求头. 默认为None。

        Returns:
            Optional[Any]: 成功时返回JSON解析后的响应数据，否则返回None。
        """
        headers = self._get_base_headers()
        if extra_headers:
            headers.update(extra_headers)

        try:
            response = self.session.request(
                method,
                url,
                params=params,
                json=json_data,
                headers=headers,
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()  # 如果状态码是4xx或5xx，则抛出异常
            return response.json()
        except requests.exceptions.RequestException as e:
            # logging.error(f"请求失败: URL={url}, Error={e}") # 建议配合logging模块使用
            print(f"请求失败: URL={url}, Error={e}")
            return None

    @abc.abstractmethod
    def get_favorite_items(self) -> List[Dict[str, str]]:
        """
        【抽象方法】获取收藏夹中的所有商品列表。

        每个子类需要根据具体平台的API来实现此方法。

        Returns:
            List[Dict[str, str]]: 商品列表，每个商品是一个字典，
                                  必须包含 'item_id' 和 'name' 两个键。
                                  例如: [{'item_id': '123', 'name': 'AK-47'}]
        """
        raise NotImplementedError("子类必须实现 get_favorite_items 方法")

    @abc.abstractmethod
    def get_item_kline_history(self, item_id: str, days: int = 300) -> List[list]:
        """
        【抽象方法】获取单个商品的K线历史数据。

        每个子类需要根据具体平台的API来实现此方法。

        Args:
            item_id (str): 商品的唯一标识符。
            days (int, optional): 希望获取的历史数据天数. 默认为300。

        Returns:
            List[list]: K线数据列表，每个元素是一条K线记录。
                        格式应统一为:
                        [[timestamp, open, close, high, low, volume, amount], ...]
        """
        raise NotImplementedError("子类必须实现 get_item_kline_history 方法")
    
    @abc.abstractmethod
    def get_inventory_items(self) -> Dict[str, str]:
        """
        【抽象方法】获取库存中的所有商品列表。

        每个子类需要根据具体平台的API来实现此方法。

        Returns:
            List[Dict[str, str]]: 商品列表，每个商品是一个字典，
                                  必须包含 'item_id' 和 'name' 两个键。
                                  例如: [{'item_id': '123', 'name': 'AK-47'}]
        """
        raise NotImplementedError("子类必须实现 get_inventory_items 方法")