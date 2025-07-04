#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
K线图显示模块
"""

import os
import logging
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import mplfinance as mpf
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Union, Any
import sys
from pathlib import Path

# 添加项目根目录到Python路径
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(ROOT_DIR))

from config import settings

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"{settings.LOG_DIR}/analysis.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("analysis")


class KLineChart:
    """K线图显示类"""
    
    def __init__(self, days_to_show: int = 30):
        """
        初始化K线图显示类
        
        Args:
            days_to_show: 显示的天数，默认为30天
        """
        self.days_to_show = days_to_show
        self.chart_style = mpf.make_mpf_style(
            base_mpf_style='yahoo',
            gridstyle='--',
            y_on_right=False,
            marketcolors=mpf.make_marketcolors(
                up='red',
                down='green',
                edge='inherit',
                wick='inherit',
                volume='inherit'
            )
        )
        
        # 创建图表保存目录
        self.charts_dir = os.path.join(settings.DATA_DIR, 'charts')
        os.makedirs(self.charts_dir, exist_ok=True)
    
    def _convert_data_format(self, raw_data: List[List]) -> pd.DataFrame:
        """
        转换原始数据为pandas DataFrame格式
        
        Args:
            raw_data: 原始K线数据列表
            
        Returns:
            格式化后的DataFrame，包含OHLCV数据
        """
        # 创建空的DataFrame
        df = pd.DataFrame(columns=['Date', 'Open', 'High', 'Low', 'Close', 'Volume', 'Amount'])
        
        # 填充数据
        for item in raw_data:
            if len(item) >= 7:
                timestamp = int(item[0])
                date = datetime.fromtimestamp(timestamp)
                
                # 数据结构: [时间戳, 底部(开盘), 顶部(收盘), 上影线(最高), 下影线(最低), 成交量, 成交额]
                row = {
                    'Date': date,
                    'Open': float(item[1]),    # 开盘价
                    'Close': float(item[2]),   # 收盘价
                    'High': float(item[3]),    # 最高价
                    'Low': float(item[4]),     # 最低价
                    'Volume': float(item[5]),  # 成交量
                    'Amount': float(item[6])   # 成交额
                }
                df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        
        # 按日期排序
        df = df.sort_values('Date')
        
        # 设置日期为索引
        df.set_index('Date', inplace=True)
        
        return df
    
    def _filter_recent_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        筛选最近N天的数据
        
        Args:
            df: 原始数据DataFrame
            
        Returns:
            筛选后的DataFrame
        """
        if len(df) <= self.days_to_show:
            return df
        
        return df.tail(self.days_to_show)
    
    def plot_candlestick(self, item_id: str, raw_data: List[List], 
                        title: Optional[str] = None, 
                        save_path: Optional[str] = None) -> str:
        """
        绘制K线图
        
        Args:
            item_id: 商品ID
            raw_data: 原始K线数据
            title: 图表标题，默认为"商品ID的K线图"
            save_path: 保存路径，默认为charts目录下的item_id.png
            
        Returns:
            图表保存路径
        """
        if not raw_data:
            logger.warning(f"商品 {item_id} 没有数据，无法绘制K线图")
            return ""
        
        # 转换数据格式
        df = self._convert_data_format(raw_data)
        
        # 筛选最近N天的数据
        df = self._filter_recent_data(df)
        
        if len(df) == 0:
            logger.warning(f"商品 {item_id} 筛选后没有数据，无法绘制K线图")
            return ""
        
        # 设置图表标题
        if title is None:
            title = f"商品 {item_id} 的K线图 (最近{self.days_to_show}天)"
        
        # 设置保存路径
        if save_path is None:
            save_path = os.path.join(self.charts_dir, f"{item_id}_candlestick.png")
        
        # 绘制K线图
        try:
            fig, axes = mpf.plot(
                df,
                type='candle',
                style=self.chart_style,
                title=title,
                ylabel='价格',
                volume=True,
                figsize=(12, 8),
                returnfig=True
            )
            
            # 保存图表
            fig.savefig(save_path)
            plt.close(fig)
            
            logger.info(f"K线图已保存到: {save_path}")
            return save_path
        except Exception as e:
            logger.error(f"绘制K线图失败: {e}")
            return ""
    
    def plot_multiple_items(self, data_dict: Dict[str, List[List]], 
                           save_dir: Optional[str] = None) -> Dict[str, str]:
        """
        批量绘制多个商品的K线图
        
        Args:
            data_dict: 商品数据字典，键为商品ID，值为K线数据列表
            save_dir: 保存目录，默认为charts目录
            
        Returns:
            图表路径字典，键为商品ID，值为图表保存路径
        """
        if save_dir is None:
            save_dir = self.charts_dir
        
        os.makedirs(save_dir, exist_ok=True)
        
        result = {}
        for item_id, raw_data in data_dict.items():
            save_path = os.path.join(save_dir, f"{item_id}_candlestick.png")
            chart_path = self.plot_candlestick(item_id, raw_data, save_path=save_path)
            if chart_path:
                result[item_id] = chart_path
        
        logger.info(f"已绘制 {len(result)} 个商品的K线图")
        return result


# 使用示例
if __name__ == "__main__":
    # 示例数据
    sample_data = {
        '525873303': [
            ['1743782400', 47388.0, 47495.0, 47750.0, 47000.0, 7, 331881.0],
            ['1743868800', 47495.0, 48000.0, 48000.0, 46900.0, 25, 1187979.5],
            ['1743955200', 48000.0, 47500.0, 48500.0, 47500.0, 15, 714750.0],
            ['1744041600', 47500.0, 47800.0, 48000.0, 47200.0, 10, 478000.0],
            ['1744128000', 47800.0, 48200.0, 48500.0, 47500.0, 12, 574800.0]
        ]
    }
    
    # 创建K线图显示类
    chart = KLineChart(days_to_show=5)
    
    # 绘制K线图
    chart_path = chart.plot_candlestick('525873303', sample_data['525873303'])
    print(f"K线图已保存到: {chart_path}") 