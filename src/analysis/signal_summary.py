#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
信号汇总模块，用于收集和保存交易信号
"""

import os
import logging
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd
from config import settings

logger = logging.getLogger(__name__)

class SignalSummary:
    """信号汇总类"""
    
    def __init__(self):
        """初始化信号汇总"""
        self.signals_dir = os.path.join(settings.DATA_DIR, "signals")
        if not os.path.exists(self.signals_dir):
            os.makedirs(self.signals_dir)
        self.signals: Dict[str, Dict] = {}  # 存储信号数据
    
    def add_signal(self, item_id: str, item_name: str, signal_type: str, 
                  price: float, open_price: float, close_price: float,
                  volume: float, boll_values: Dict[str, float], 
                  timestamp: datetime):
        """
        添加新的信号

        Args:
            item_id: 商品ID
            item_name: 商品名称
            signal_type: 信号类型 ('buy' 或 'sell')
            price: 触发价格
            open_price: 开盘价
            close_price: 收盘价
            volume: 成交量
            boll_values: 布林带值 {'middle': float, 'upper': float, 'lower': float}
            timestamp: 信号时间
        """
        self.signals[item_id] = {
            'name': item_name,
            'signal_type': signal_type,
            'price': price,
            'open': open_price,
            'close': close_price,
            'volume': volume,
            'boll_middle': boll_values['middle'],
            'boll_upper': boll_values['upper'],
            'boll_lower': boll_values['lower'],
            'timestamp': timestamp
        }
        logger.info(f"添加{signal_type}信号: 商品={item_name}({item_id}), 价格={price:.2f}, 时间={timestamp}")
    
    @staticmethod
    def _clean_item_name(name: str) -> str:
        """
        清理商品名称中的特殊字符
        
        Args:
            name: 原始商品名称
            
        Returns:
            清理后的商品名称
        """
        # 移除可能影响markdown表格格式的字符
        special_chars = ['|', '*', '`', '_', '{', '}', '[', ']', '(', ')', '#', '+', '-', '.', '!']
        cleaned_name = name
        for char in special_chars:
            cleaned_name = cleaned_name.replace(char, ' ')
        # 移除多余的空格
        cleaned_name = ' '.join(cleaned_name.split())
        return cleaned_name

    def save_to_markdown(self) -> Optional[str]:
        """
        将信号保存为markdown表格格式

        Returns:
            保存的文件路径
        """
        if not self.signals:
            logger.info("没有需要保存的信号")
            return None
            
        try:
            # 生成文件名（使用日期和时间）
            current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"signals_{current_time}.md"
            file_path = os.path.join(self.signals_dir, file_name)
            
            # 构建markdown内容
            content = ["# 交易信号汇总\n\n"]
            content.append("生成时间: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n\n")
            
            # 添加表格头
            content.append("| 商品ID | 商品名称 | 信号类型 | 触发价格 | 开盘价 | 收盘价 | 布林中轨 | 布林上轨 | 布林下轨 | 成交量 | 触发时间 |\n")
            content.append("|---------|----------|----------|----------|---------|---------|----------|----------|----------|---------|----------|\n")
            
            # 添加表格内容
            for item_id, signal in self.signals.items():
                # 清理商品名称
                cleaned_name = self._clean_item_name(signal['name'])
                content.append(
                    f"| {item_id} | "
                    f"{cleaned_name} | "
                    f"{'买入' if signal['signal_type'] == 'buy' else '卖出'} | "
                    f"{signal['price']:.2f} | "
                    f"{signal['open']:.2f} | "
                    f"{signal['close']:.2f} | "
                    f"{signal['boll_middle']:.2f} | "
                    f"{signal['boll_upper']:.2f} | "
                    f"{signal['boll_lower']:.2f} | "
                    f"{int(signal['volume'])} | "
                    f"{signal['timestamp'].strftime('%Y-%m-%d %H:%M:%S')} |\n"
                )
            
            # 写入文件（由于包含时间戳，每次都创建新文件）
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(content)
            
            logger.info(f"信号汇总已保存至: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"保存信号汇总时出错: {e}")
            return None
    
    def clear_signals(self):
        """清空信号数据"""
        self.signals.clear() 