#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
数据清理模块
"""

import logging
from typing import List, Dict, Union, Any

logger = logging.getLogger(__name__)

class MarketDataCleaner:
    """市场数据清理类"""
    
    @staticmethod
    def clean_kline_data(raw_data: List[Union[List, Dict]], remove_none: bool = True) -> List[List]:
        """
        清理K线数据
        
        Args:
            raw_data: 原始K线数据，可以是字典列表或列表的列表
            remove_none: 是否移除包含None的数据项
            
        Returns:
            清理后的数据列表
        """
        if not raw_data:
            logger.warning("输入数据为空")
            return []
            
        cleaned_data = []
        
        for item in raw_data:
            # 跳过包含None的数据
            if remove_none and (
                (isinstance(item, dict) and None in item.values()) or
                (isinstance(item, list) and None in item)
            ):
                continue
                
            # 转换数据格式
            if isinstance(item, dict):
                cleaned_data.append(list(item.values()))
            elif isinstance(item, list):
                cleaned_data.append(item)
            else:
                logger.warning(f"跳过未知格式的数据: {item}")
                continue
                
        return cleaned_data
        
    @staticmethod
    def clean_market_data(raw_data: Dict[str, List[Union[List, Dict]]], 
                         remove_none: bool = True) -> Dict[str, List[List]]:
        """
        清理完整的市场数据
        
        Args:
            raw_data: 原始市场数据，键为商品ID，值为该商品的K线数据
            remove_none: 是否移除包含None的数据项
            
        Returns:
            清理后的市场数据字典
        """
        if not isinstance(raw_data, dict):
            logger.error("输入数据必须是字典格式")
            return {}
            
        cleaned_data = {}
        
        for item_id, kline_data in raw_data.items():
            cleaned_data[item_id] = MarketDataCleaner.clean_kline_data(kline_data, remove_none)
            
        return cleaned_data 