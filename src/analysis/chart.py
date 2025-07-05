#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
图表绘制模块
"""

import os
import logging
from typing import List, Dict, Optional, Any

import pandas as pd
import mplfinance as mpf
from config import settings
from .indicators import TechnicalIndicators, IndicatorType

logger = logging.getLogger(__name__)

class KLineChart:
    """K线图绘制类"""
    
    def __init__(self, days_to_show: int = 30):
        """
        初始化K线图绘制器
        
        Args:
            days_to_show: 显示最近多少天的数据
        """
        self.days_to_show = days_to_show
        self.charts_dir = os.path.join(settings.DATA_DIR, 'charts')
        if not os.path.exists(self.charts_dir):
            os.makedirs(self.charts_dir)
            
        # 设置图表样式
        self.chart_style = mpf.make_mpf_style(
            base_mpf_style='charles',
            gridstyle=':',
            y_on_right=False,
            marketcolors=mpf.make_marketcolors(
                up='red',
                down='green',
                edge='inherit',
                wick='inherit',
                volume={'up': 'red', 'down': 'green'},
                ohlc='inherit'
            ),
            rc={
                'axes.labelsize': 10,
                'axes.titlesize': 12,
                'xtick.labelsize': 8,
                'ytick.labelsize': 8,
                'grid.linestyle': ':',
                'grid.alpha': 0.3
            }
        )
        
        # 初始化技术指标
        self.indicators = TechnicalIndicators()
    
    def plot_candlestick(self, item_id: str, raw_data: List[List], 
                        title: Optional[str] = None,
                        indicator_type: IndicatorType = IndicatorType.ALL) -> Any:
        """
        绘制K线图
        
        Args:
            item_id: 商品ID
            raw_data: 原始K线数据
            title: 图表标题，默认为"Kline Chart of {item_id}"
            indicator_type: 要显示的指标类型
            
        Returns:
            matplotlib figure 对象
        """
        if not raw_data:
            logger.warning(f"商品 {item_id} 没有数据，无法绘制K线图")
            return None
        
        # 转换数据格式
        df = self.indicators.prepare_dataframe(raw_data)
        
        # 筛选最近N天的数据
        df = self._filter_recent_data(df)
        
        if len(df) == 0:
            logger.warning(f"商品 {item_id} 筛选后没有数据，无法绘制K线图")
            return None
        
        # 设置图表标题
        if title is None:
            title = f"Kline Chart of {item_id} (Last {self.days_to_show} days)"
        
        # 获取技术指标的绘图参数
        addplots = self.indicators.get_indicator_plots(df, indicator_type)
        
        # 创建子图，为技术指标预留空间
        fig, axes = mpf.plot(
            df,
            type='candle',
            style=self.chart_style,
            volume=True,
            volume_alpha=0.5,
            figsize=(12, 8),
            panel_ratios=(3, 1),
            addplot=addplots,
            returnfig=True,
            tight_layout=False,  # 关闭自动布局以手动调整标题
            show_nontrading=False,
            datetime_format='%m/%d'  # 设置日期格式为MM/DD
        )
        
        # 调整标题位置
        fig.suptitle(title, y=0.95)
        
        # 调整布局
        fig.tight_layout(rect=[0, 0, 1, 0.95])  # 为标题预留空间
        
        return fig
    
    def _filter_recent_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        筛选最近N天的数据
        
        Args:
            df: 原始DataFrame
            
        Returns:
            筛选后的DataFrame
        """
        if len(df) <= self.days_to_show:
            return df
            
        # 由于在prepare_dataframe中已经按时间排序，直接取最后N天数据即可
        return df.tail(self.days_to_show)


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
    chart = KLineChart(days_to_show=30)
    
    # 绘制K线图
    fig = chart.plot_candlestick('525873303', sample_data['525873303'])
    print(f"K线图已绘制") 