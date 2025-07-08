#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
信号汇总模块，用于收集和保存交易信号
"""

import os
import logging
import json
import base64
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd
from config import settings
from src.notification.ntfy import send as send_ntfy

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
        
    def send_ntfy_notification(self, topic_name: str = "cs2market") -> bool:
        """
        使用ntfy的原生功能发送带有格式的消息和图片
        
        Args:
            topic_name: ntfy的主题名称，默认为'cs2market'
            
        Returns:
            发送是否成功
        """
        if not self.signals:
            logger.info("没有需要发送的信号")
            return False
            
        try:
            # 构建消息标题 - 使用ASCII安全的字符
            title = "CS2 Market Trading Signals"  # 使用纯ASCII字符
            
            # 构建消息内容（使用Markdown格式）
            message_parts = []
            message_parts.append(f"## {title}")
            message_parts.append(f"Generated Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            message_parts.append("\n### Signal Summary")
            
            # 添加信号表格（使用Markdown格式）
            message_parts.append("\n| Item ID | Item Name | Signal | Price | Middle | Upper | Lower | Volume |")
            message_parts.append("| ------ | -------- | -------- | -------- | -------- | -------- | -------- | ------ |")
            
            # 添加买入信号
            buy_signals = []
            sell_signals = []
            
            for item_id, signal in self.signals.items():
                # 清理商品名称
                cleaned_name = self._clean_item_name(signal['name'])
                signal_type = signal['signal_type']
                
                # 构建表格行 - 使用ASCII安全的字符
                row = (
                    f"| {item_id} "
                    f"| {cleaned_name} "
                    f"| **{signal_type}** "
                    f"| {signal['price']:.2f} "
                    f"| {signal['boll_middle']:.2f} "
                    f"| {signal['boll_upper']:.2f} "
                    f"| {signal['boll_lower']:.2f} "
                    f"| {int(signal['volume'])} |"
                )
                
                # 根据信号类型分类
                if signal_type == 'buy':
                    buy_signals.append(row)
                else:
                    sell_signals.append(row)
            
            # 添加买入信号
            if buy_signals:
                message_parts.append("\n#### Buy Signals")
                message_parts.extend(buy_signals)
                
            # 添加卖出信号
            if sell_signals:
                message_parts.append("\n#### Sell Signals")
                message_parts.extend(sell_signals)
            
            # 组合消息内容
            message = "\n".join(message_parts)
            
            # 设置消息标签和优先级
            tags = "chart,money,cs2"
            priority = 3  # 默认优先级
            
            # 设置附加的HTTP头
            headers = {
                "Title": title,
                "Tags": tags,
                "Priority": str(priority),
                "Content-Type": "text/markdown; charset=utf-8"  # 明确指定UTF-8编码
            }
            
            # 发送ntfy消息
            response = send_ntfy(topic_name, message, url=settings.NATY_SERVER_URL, headers=headers)
            
            logger.info(f"已通过ntfy发送交易信号报告到主题: {topic_name}")
            return True
                
        except Exception as e:
            logger.error(f"发送ntfy通知时出错: {e}")
            return False 
            
    def send_chart_images(self, topic_name: str = "cs2market", chart_paths: Dict[str, str] = None) -> bool:
        """
        发送K线图作为附件
        
        Args:
            topic_name: ntfy的主题名称，默认为'cs2market'
            chart_paths: 图表路径字典，键为商品ID，值为图表文件路径
            
        Returns:
            发送是否成功
        """
        if not chart_paths:
            logger.info("没有图表需要发送")
            return False
            
        success_count = 0
        total_count = len(chart_paths)
        
        for item_id, chart_path in chart_paths.items():
            try:
                if not os.path.exists(chart_path):
                    logger.warning(f"图表文件不存在: {chart_path}")
                    continue
                    
                # 读取图片文件
                with open(chart_path, 'rb') as f:
                    image_data = f.read()
                
                # 获取商品名称
                item_name = "未知商品"
                if item_id in self.signals:
                    item_name = self.signals[item_id].get('name', f"商品-{item_id}")
                
                # 清理商品名称，避免编码问题
                clean_name = self._clean_item_name(item_name)
                
                # 设置消息标题和标签 - 使用ASCII安全的字符
                title = f"CS2 Market - Item {item_id} Chart"  # 使用纯ASCII字符
                tags = "chart,cs2"
                
                # 设置附加的HTTP头
                headers = {
                    "Title": title,
                    "Tags": tags,
                    "Filename": f"{item_id}_chart.png",  # 使用安全的文件名
                    "Content-Type": "image/png"
                }
                
                # 发送ntfy消息
                response = send_ntfy(topic_name, image_data, url=settings.NATY_SERVER_URL, headers=headers)
                
                logger.info(f"已发送商品 {item_id} 的K线图")
                success_count += 1
                
            except Exception as e:
                logger.error(f"发送商品 {item_id} 的K线图时出错: {e}")
        
        logger.info(f"K线图发送完成，成功: {success_count}/{total_count}")
        return success_count > 0 

    def send_report(self, topic_name: str = "cs2market", chart_paths: Dict[str, str] = None) -> bool:
        """
        发送完整的报告，包括信号汇总和K线图
        
        Args:
            topic_name: ntfy的主题名称，默认为'cs2market'
            chart_paths: 图表路径字典，键为商品ID，值为图表文件路径
            
        Returns:
            发送是否成功
        """
        # 首先发送信号汇总
        text_success = self.send_ntfy_notification(topic_name)
        
        # 然后发送K线图
        image_success = False
        if chart_paths:
            image_success = self.send_chart_images(topic_name, chart_paths)
            
        # 同时保存为markdown文件
        md_path = self.save_to_markdown()
        
        return text_success or image_success 