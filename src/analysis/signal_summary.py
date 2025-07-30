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
        self.signals: Dict[str, list] = {}  # 存储信号数据
    
    def add_signal(self, item_id: str, item_name: str, signal_type: str, 
                  price: float, open_price: float, close_price: float,
                  volume: float, boll_values: Dict[str, float], 
                  timestamp: Optional[str] = None,
                  previous_touch: Optional[Dict] = None,
                  price_changes: Optional[Dict] = None,
                  fav_name: str = None,
                  volume_ma: list = []):
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
            timestamp: 信号时间（可选），如果不提供则使用当前时间
            previous_touch: 上一次触碰点信息（可选）
                {
                    'price': float,  # 价格
                    'timestamp': str,  # 时间
                    'days_ago': int,  # 几天前
                }
            price_changes: 价格变化信息（可选）
                {
                    'day3': {'price': float, 'diff': float, 'rate': float},
                    'day7': {'price': float, 'diff': float, 'rate': float}
                }
        """
        if timestamp is None:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
        if not self.signals.get(fav_name):
            self.signals[fav_name] = []
        
        self.signals[fav_name].append({
            'name': item_name,
            'signal_type': signal_type,
            'price': price,
            'open_price': open_price,
            'close_price': close_price,
            'volume': volume,
            'boll_values': boll_values,
            'timestamp': timestamp,
            'previous_touch': previous_touch,
            'price_changes': price_changes or {
                'day3': {'price': 0.0, 'diff': 0.0, 'rate': 0.0},
                'day7': {'price': 0.0, 'diff': 0.0, 'rate': 0.0}
            },
            'item_id': item_id,
            'volume_ma': volume_ma
        })
        
        logger.info(f"添加{signal_type}信号: 商品={item_name}({item_id}), 价格={price:.2f}, 时间={timestamp}")
        # if previous_touch:
        #     logger.info(f"上一次触碰: 价格={previous_touch['price']:.2f}, 时间={previous_touch['timestamp']}, {previous_touch['days_ago']}天前")
        # if price_changes:
        #     logger.info(f"价格变化: 3天前={price_changes['day3']['price']:.2f} ({price_changes['day3']['rate']:+.2f}%), "
        #                f"7天前={price_changes['day7']['price']:.2f} ({price_changes['day7']['rate']:+.2f}%)")
    
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
        将信号汇总保存为Markdown格式
        
        Returns:
            str: 保存的文件路径，如果保存失败则返回None
        """
        try:
            if not self.signals:
                logger.warning("没有信号需要保存")
                return None
                
            # 创建signals目录
            signals_dir = os.path.join(settings.DATA_DIR, "signals")
            os.makedirs(signals_dir, exist_ok=True)
            
            # 生成文件名
            current_time = datetime.now()
            filename = f"signals_{current_time.strftime('%Y%m%d_%H%M%S')}.md"
            filepath = os.path.join(signals_dir, filename)
            
            with open(filepath, "w", encoding="utf-8") as f:
                # 写入表头
                f.write("| 商品ID | 商品名称 | 信号类型 | 触发价格 | 开盘价 | 收盘价 | 成交量 | 布林中轨 | 布林上轨 | 布林下轨 | 3天前价格 | 3天涨跌幅 | 7天前价格 | 7天涨跌幅 | 上次触碰价格 | 上次触碰时间 | 间隔天数 | 触发时间 |\n")
                f.write("|---------|----------|----------|----------|---------|---------|----------|----------|----------|---------|------------|------------|------------|------------|--------------|--------------|----------|----------|\n")
                
                # 写入每个信号
                for item_id, signal in self.signals.items():
                    # 获取历史触碰点信息，确保previous_touch存在
                    prev_touch = signal.get('previous_touch') or {}
                    price_changes = signal.get('price_changes') or {
                        'day3': {'price': 0.0, 'diff': 0.0, 'rate': 0.0},
                        'day7': {'price': 0.0, 'diff': 0.0, 'rate': 0.0}
                    }
                    
                    # 安全地获取价格并格式化
                    try:
                        prev_price = f"{prev_touch.get('price', 0):.2f}" if prev_touch.get('price') is not None else '-'
                    except (TypeError, ValueError):
                        prev_price = '-'
                    
                    # 安全地获取其他信息
                    prev_time = prev_touch.get('timestamp', '-')
                    days_ago = str(prev_touch.get('days_ago', '-'))
                    
                    f.write(
                        f"| {item_id} | "
                        f"{signal['name']} | "
                        f"{signal['signal_type']} | "
                        f"{signal['price']:.2f} | "
                        f"{signal['open_price']:.2f} | "
                        f"{signal['close_price']:.2f} | "
                        f"{signal['volume']:.2f} | "
                        f"{signal['boll_values']['middle']:.2f} | "
                        f"{signal['boll_values']['upper']:.2f} | "
                        f"{signal['boll_values']['lower']:.2f} | "
                        f"{price_changes['day3']['price']:.2f} | "
                        f"{price_changes['day3']['rate']:+.2f}% | "
                        f"{price_changes['day7']['price']:.2f} | "
                        f"{price_changes['day7']['rate']:+.2f}% | "
                        f"{prev_price} | "
                        f"{prev_time} | "
                        f"{days_ago} | "
                        f"{signal['timestamp']} |\n"
                    )
                
            logger.info(f"信号汇总已保存到: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"保存信号汇总时出错: {e}")
            return None
    
    def clear_signals(self):
        """清空信号数据"""
        self.signals.clear() 
        
    def _sort_signals_by_price_change(self, signals: list[dict], signal_type: str = None) -> List[tuple]:
        """
        按7天价格变化率对信号进行排序
        
        Args:
            signals: 信号字典
            signal_type: 可选的信号类型过滤 ('buy' 或 'sell')
            
        Returns:
            排序后的信号列表，每个元素为 (item_id, signal_dict) 元组
        """
        
        # 过滤信号类型（如果指定）
        filtered_signals = []
        for item in signals:
            if signal_type and item['signal_type'] != signal_type:
                continue
            filtered_signals.append((item['item_id'], item))
        
        # 按7天价格变化率排序（降幅越大越靠前）
        return sorted(
            filtered_signals,
            key=lambda x: x[1]['price_changes']['day7']['rate']
        )

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
            # 构建消息内容（使用简单的文本列表格式）
            title = "CS2 Market Trading Signals"
            
            message_parts = []
            message_parts.append(f"📊 {title}")
            message_parts.append(f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            message_parts.append("")
            
            # 分类并排序信号
            buy_signals = []
            sell_signals = []
            
            for fav_name, item in self.signals: 
                message_parts.append(f"❤ Fav List {fav_name}")
                
                # 获取排序后的买入和卖出信号
                sorted_buy_signals = self._sort_signals_by_price_change(item, 'buy')
                sorted_sell_signals = self._sort_signals_by_price_change(item, 'sell')
                
                # 处理买入信号
                for item_id, signal in sorted_buy_signals:
                    # 清理商品名称
                    cleaned_name = self._clean_item_name(signal['name'])
                    
                    # 获取价格变化信息
                    price_changes = signal.get('price_changes', {
                        'day3': {'price': 0.0, 'diff': 0.0, 'rate': 0.0},
                        'day7': {'price': 0.0, 'diff': 0.0, 'rate': 0.0}
                    })
                    
                    # 构建信号信息
                    signal_info = (
                        f"📌 {cleaned_name}\n"
                        f"   ID: {item_id}\n"
                        f"   Price: {signal['price']:.2f}\n"
                        f"   Volume: {int(signal['volume'])}\n"
                        f"   BOLL: {signal['boll_values']['middle']:.2f} | {signal['boll_values']['upper']:.2f} | {signal['boll_values']['lower']:.2f}\n"
                        f"   3days ago: {price_changes['day3']['price']:.2f} ({price_changes['day3']['rate']:+.2f}%)\n"
                        f"   7days ago: {price_changes['day7']['price']:.2f} ({price_changes['day7']['rate']:+.2f}%)\n"
                    )
                    buy_signals.append(signal_info)
                
                # 处理卖出信号
                for item_id, signal in sorted_sell_signals:
                    # 清理商品名称
                    cleaned_name = self._clean_item_name(signal['name'])
                    
                    # 获取价格变化信息
                    price_changes = signal.get('price_changes', {
                        'day3': {'price': 0.0, 'diff': 0.0, 'rate': 0.0},
                        'day7': {'price': 0.0, 'diff': 0.0, 'rate': 0.0}
                    })
                    
                    # 构建信号信息
                    signal_info = (
                        f"📌 {cleaned_name}\n"
                        f"   ID: {item_id}\n"
                        f"   Price: {signal['price']:.2f}\n"
                        f"   Volume: {int(signal['volume'])}\n"
                        f"   BOLL: {signal['boll_values']['middle']:.2f} | {signal['boll_values']['upper']:.2f} | {signal['boll_values']['lower']:.2f}\n"
                        f"   3days ago: {price_changes['day3']['price']:.2f} ({price_changes['day3']['rate']:+.2f}%)\n"
                        f"   7days ago: {price_changes['day7']['price']:.2f} ({price_changes['day7']['rate']:+.2f}%)\n"
                    )
                    sell_signals.append(signal_info)
            
                # 添加买入信号
                if buy_signals:
                    message_parts.append("📈 Buy Signals:")
                    message_parts.extend(buy_signals)
                    message_parts.append("")
                    
                # 添加卖出信号
                if sell_signals:
                    message_parts.append("📉 Sell Signals:")
                    message_parts.extend(sell_signals)
                    message_parts.append("")
            
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
            
    @staticmethod
    def merge_images_vertically(image_paths: List[str]) -> Optional[str]:
        """
        将多张图片垂直合并为一张长图
        
        Args:
            image_paths: 图片路径列表
            
        Returns:
            合并后的图片路径，如果失败则返回None
        """
        try:
            from PIL import Image
            import os
            
            # 确保至少有一张图片
            if not image_paths:
                return None
                
            # 读取所有图片
            images = []
            for path in image_paths:
                if os.path.exists(path):
                    img = Image.open(path)
                    images.append(img)
                    
            if not images:
                return None
                
            # 计算合并后图片的尺寸
            total_height = sum(img.height for img in images)
            max_width = max(img.width for img in images)
            
            # 创建新图片
            merged_image = Image.new('RGB', (max_width, total_height), 'white')
            
            # 从上到下粘贴图片
            y_offset = 0
            for img in images:
                # 如果图片宽度小于最大宽度，居中放置
                x_offset = (max_width - img.width) // 2
                merged_image.paste(img, (x_offset, y_offset))
                y_offset += img.height
                img.close()
            
            # 保存合并后的图片
            output_path = os.path.join(os.path.dirname(image_paths[0]), 'merged_charts.png')
            merged_image.save(output_path, 'PNG')
            merged_image.close()
            
            return output_path
            
        except Exception as e:
            logger.error(f"合并图片时出错: {e}")
            return None
            
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
            
        try:
            # 获取所有有效的图片路径
            valid_paths = []
            for item_id, chart_path in chart_paths.items():
                if os.path.exists(chart_path):
                    valid_paths.append(chart_path)
                else:
                    logger.warning(f"图表文件不存在: {chart_path}")
            
            if not valid_paths:
                logger.warning("没有有效的图表文件")
                return False
            
            # 合并所有图片
            merged_path = self.merge_images_vertically(valid_paths)
            if not merged_path:
                logger.error("合并图片失败")
                return False
            
            try:
                # 读取合并后的图片
                with open(merged_path, 'rb') as f:
                    image_data = f.read()
                
                # 设置图片消息头
                image_headers = {
                    "Title": "K Line Image",
                    "Tags": "CS2",
                    "Filename": "charts_summary.png",
                    "Content-Type": "image/png; charset=utf-8"
                }
                
                # 发送合并后的图片
                send_ntfy(topic_name, image_data, url=settings.NATY_SERVER_URL, headers=image_headers)
                logger.info("已发送合并后的K线图")
                
                # 删除临时的合并图片
                os.remove(merged_path)
                
                return True
                
            except Exception as e:
                logger.error(f"发送合并图片时出错: {e}")
                if os.path.exists(merged_path):
                    os.remove(merged_path)
                return False
                
        except Exception as e:
            logger.error(f"处理图表时出错: {e}")
            return False

    @staticmethod
    def _encode_header_value(value: str) -> str:
        """
        对header值进行编码，处理非ASCII字符和特殊字符
        
        Args:
            value: 原始字符串
            
        Returns:
            编码后的字符串
        """
        import base64
        # 将字符串转换为base64编码
        encoded = base64.b64encode(value.encode('utf-8')).decode('ascii')
        return f"=?UTF-8?B?{encoded}?="
        
    def send_report(self, topic_name: str = "cs2market", chart_paths: Dict[str, str] = None) -> bool:
        """
        发送信号汇总报告
        
        Args:
            topic_name: ntfy的主题名称，默认为'cs2market'
        Returns:
            发送是否成功
        """
        # self.signals = {'test': [{'name': '印花 | 谷哥之眼（透镜）', 'signal_type': 'buy', 'price': 67.0, 'open_price': 66.31, 'close_price': 67.0, 'volume': 18.0, 'boll_values': {'middle': 76.9025, 'upper': 87.96084835864086, 'lower': 65.84415164135915}, 'timestamp': 111111111111, 'previous_touch': {'price': 65.0, 'timestamp': '2025-07-23 16:00:00', 'days_ago': 1}, 'price_changes': {'day3': {'price': 73.41, 'diff': -8.409999999999997, 'rate': -11.456204876719788}, 'day7': {'price': 74.76, 'diff': -9.760000000000005, 'rate': -13.055109684323174}}, 'item_id': '1315838090516619264'}]}
        
        if not self.signals:
            logger.info("没有需要发送的信号")
            return False
            
        try:
            # 构建消息内容（使用简单的文本列表格式）
            title = "CS2 Market Trading Signals"
            
            message_parts = []
            message_parts.append(f"📊 {title}")
            message_parts.append(f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            message_parts.append("")
            
            for fav_name, item in self.signals.items(): 
                # 分类并排序信号
                buy_signals = []
                sell_signals = []
                message_parts.append(f"==========={fav_name or 'Unknown'}===========")
                
                # 获取排序后的买入和卖出信号
                sorted_buy_signals = self._sort_signals_by_price_change(item, 'buy')
                sorted_sell_signals = self._sort_signals_by_price_change(item, 'sell')
                
                # 处理买入信号
                for item_id, signal in sorted_buy_signals:
                    # 清理商品名称
                    cleaned_name = self._clean_item_name(signal['name'])
                    
                    # 构建信号信息
                    signal_info = [
                        f"📌 {cleaned_name}",
                        f"   ID: {item_id}",
                        f"   Price: ¥{signal['price']:.2f}",
                        f"   Volume: {int(signal['volume'])}",
                        f"   Volume MA(5/10/20): {'/'.join(map(str, signal['volume_ma']))}",
                        f"   BOLL: ¥{signal['boll_values']['middle']:.2f} | ¥{signal['boll_values']['upper']:.2f} | ¥{signal['boll_values']['lower']:.2f}",
                        f"   3days ago: ¥{signal['price_changes']['day3']['price']:.2f} ({signal['price_changes']['day3']['rate']:+.2f}%)",
                        f"   7days ago: ¥{signal['price_changes']['day7']['price']:.2f} ({signal['price_changes']['day7']['rate']:+.2f}%)"
                    ]
                    
                    # 添加历史触碰点信息
                    if signal.get('previous_touch'):
                        prev = signal['previous_touch']
                        signal_info.append(f"   Previous Touch: ¥{prev['price']:.2f} ({prev['days_ago']} days ago)")
                    
                    signal_info = "\n".join(signal_info)
                    buy_signals.append(signal_info)
                
                # 处理卖出信号
                for item_id, signal in sorted_sell_signals:
                    # 清理商品名称
                    cleaned_name = self._clean_item_name(signal['name'])
                    
                    # 构建信号信息
                    signal_info = [
                        f"📌 {cleaned_name}",
                        f"   ID: {item_id}",
                        f"   Price: ¥{signal['price']:.2f}",
                        f"   Volume: {int(signal['volume'])}",
                        f"   Volume MA(5/10/20): {'/'.join(map(str, signal['volume_ma']))}",
                        f"   BOLL: ¥{signal['boll_values']['middle']:.2f} | ¥{signal['boll_values']['upper']:.2f} | ¥{signal['boll_values']['lower']:.2f}",
                        f"   3days ago: ¥{signal['price_changes']['day3']['price']:.2f} ({signal['price_changes']['day3']['rate']:+.2f}%)",
                        f"   7days ago: ¥{signal['price_changes']['day7']['price']:.2f} ({signal['price_changes']['day7']['rate']:+.2f}%)"
                    ]
                    
                    # 添加历史触碰点信息
                    if signal.get('previous_touch'):
                        prev = signal['previous_touch']
                        signal_info.append(f"   Previous Touch: ¥{prev['price']:.2f} ({prev['days_ago']} days ago)")
                    
                    signal_info = "\n".join(signal_info)
                    sell_signals.append(signal_info)
                
                # 添加买入信号
                if buy_signals:
                    message_parts.append("📈 Buy Signals:")
                    message_parts.extend(buy_signals)
                    message_parts.append("")
                    
                # 添加卖出信号
                if sell_signals:
                    message_parts.append("📉 Sell Signals:")
                    message_parts.extend(sell_signals)
                    message_parts.append("")
            
            # 组合消息内容
            message = "\n".join(message_parts) + "\n"
            
            priority = "3"
            
            headers = {
                "Title": title,
                "Tags": "CS2",
                "Priority": priority
            }
            
            logger.info(message)

            response = send_ntfy(topic_name, message, url=settings.NATY_SERVER_URL, headers=headers)
            # 同时保存为markdown文件
            # self.save_to_markdown()
            
            return True
            
        except Exception as e:
            logger.error(f"生成报告时出错: {e}")
            return False 
        
    def send_report_and_chart(self, topic_name: str = "cs2market", chart_paths: Dict[str, str] = None) -> bool:
        """
        发送完整的报告，包括信号汇总和K线图
        
        Args:
            topic_name: ntfy的主题名称，默认为'cs2market'
            chart_paths: 图表路径字典，键为商品ID，值为图表文件路径
            
        Returns:
            发送是否成功
        """
        if not self.signals:
            logger.info("没有需要发送的信号")
            return False
            
        try:
            # 构建消息内容（使用简单的文本列表格式）
            title = "CS2 Market Trading Signals"
            
            message_parts = []
            message_parts.append(f"📊 {title}")
            message_parts.append(f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            message_parts.append("")
            
            # 分类信号
            buy_signals = []
            sell_signals = []
            
            for item_id, signal in self.signals.items():
                # 清理商品名称
                cleaned_name = self._clean_item_name(signal['name'])
                signal_type = signal['signal_type']
                
                # 构建信号信息
                signal_info = (
                    f"📌 {cleaned_name}\n"
                    f"   ID: {item_id}\n"
                    f"   Price: {signal['price']:.2f}\n"
                    f"   Volume: {int(signal['volume'])}\n"
                    f"   BOLL: {signal['boll_values']['middle']:.2f} | {signal['boll_values']['upper']:.2f} | {signal['boll_values']['lower']:.2f}\n"
                )
                
                if signal_type == 'buy':
                    buy_signals.append(signal_info)
                else:
                    sell_signals.append(signal_info)
            
            # 添加买入信号
            if buy_signals:
                message_parts.append("📈 Buy Signals:")
                message_parts.extend(buy_signals)
                message_parts.append("")
                
            # 添加卖出信号
            if sell_signals:
                message_parts.append("📉 Sell Signals:")
                message_parts.extend(sell_signals)
                message_parts.append("")
            
            # 组合消息内容
            message = "\n".join(message_parts)
            
            # 处理图片
            merged_path = None
            if chart_paths:
                # 获取所有有效的图片路径
                valid_paths = []
                for item_id, chart_path in chart_paths.items():
                    if os.path.exists(chart_path):
                        valid_paths.append(chart_path)
                    else:
                        logger.warning(f"图表文件不存在: {chart_path}")
                
                if valid_paths:
                    # 合并所有图片
                    merged_path = self.merge_images_vertically(valid_paths)
                    if not merged_path:
                        logger.error("合并图片失败")
            
            try:
                priority = "3"
                
                # 如果有图片，发送图片作为附件
                if merged_path and os.path.exists(merged_path):
                    with open(merged_path, 'rb') as f:
                        image_data = f.read()
                        
                    # 设置消息头
                    headers = {
                        "Title": title,
                        "Tags": "CS2",
                        "Priority": priority,
                        "Filename": "charts_summary.png",  # 指定文件名
                        "Content-Type": "image/png",  # 指定内容类型
                        "Message": self._encode_header_value(message),  # 对消息进行编码
                    }
                    
                    # 使用PUT请求发送图片数据
                    response = send_ntfy(topic_name, image_data, url=settings.NATY_SERVER_URL, headers=headers, method="PUT")
                else:
                    # 如果没有图片，只发送文本消息
                    headers = {
                        "Title": title,
                        "Tags": "CS2",
                        "Priority": priority
                    }
                    response = send_ntfy(topic_name, message, url=settings.NATY_SERVER_URL, headers=headers)
                
                # 清理临时文件
                if merged_path and os.path.exists(merged_path):
                    os.remove(merged_path)
                
                # 同时保存为markdown文件
                self.save_to_markdown()
                
                logger.info(f"已发送完整报告到主题: {topic_name}")
                return True
                
            except Exception as e:
                logger.error(f"发送报告时出错: {e}")
                # 清理临时文件
                if merged_path and os.path.exists(merged_path):
                    os.remove(merged_path)
                return False
                
        except Exception as e:
            logger.error(f"生成报告时出错: {e}")
            return False 