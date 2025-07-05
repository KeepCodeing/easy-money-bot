#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
技术指标计算模块
"""

import logging
from enum import Enum
from typing import List, Dict, Optional, Tuple

import pandas as pd
import numpy as np
import mplfinance as mpf
from config import settings

logger = logging.getLogger(__name__)

class IndicatorType(Enum):
    """指标类型枚举"""
    BOLL = "boll"
    VEGAS = "vegas"
    ALL = "all"

class TechnicalIndicators:
    """技术指标类"""
    
    def __init__(self):
        """初始化指标参数"""
        # 布林带参数
        self.boll_period = settings.BOLLINGER_PERIOD
        self.boll_std = settings.BOLLINGER_STD
        
        # 维加斯通道参数
        self.vegas_ema1 = settings.VEGAS_EMA1
        self.vegas_ema2 = settings.VEGAS_EMA2
        self.vegas_ema3 = settings.VEGAS_EMA3
    
    def calculate_bollinger_bands(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        计算布林带指标
        
        Args:
            df: 包含收盘价的DataFrame
            
        Returns:
            (中轨, 上轨, 下轨)
        """
        try:
            # 计算中轨（简单移动平均线）
            middle = df['Close'].rolling(window=self.boll_period).mean()
            
            # 计算标准差
            std = df['Close'].rolling(window=self.boll_period).std()
            
            # 计算上下轨
            upper = middle + (std * self.boll_std)
            lower = middle - (std * self.boll_std)
            
            return middle, upper, lower
        except Exception as e:
            logger.error(f"计算布林带时出错: {e}")
            return pd.Series(), pd.Series(), pd.Series()
    
    def calculate_vegas_tunnel(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        计算维加斯通道指标
        
        Args:
            df: 包含收盘价的DataFrame
            
        Returns:
            (EMA1, EMA2, EMA3)
        """
        try:
            # 计算三条EMA线
            ema1 = df['Close'].ewm(span=self.vegas_ema1, adjust=False).mean()
            ema2 = df['Close'].ewm(span=self.vegas_ema2, adjust=False).mean()
            ema3 = df['Close'].ewm(span=self.vegas_ema3, adjust=False).mean()
            
            return ema1, ema2, ema3
        except Exception as e:
            logger.error(f"计算维加斯通道时出错: {e}")
            return pd.Series(), pd.Series(), pd.Series()
    
    def add_indicators_to_plot(self, df: pd.DataFrame, ax: any, volume_ax: any = None,
                             indicator_type: IndicatorType = IndicatorType.ALL):
        """
        在图表上添加指标
        
        Args:
            df: 数据DataFrame
            ax: matplotlib主图轴对象
            volume_ax: matplotlib成交量图轴对象（未使用）
            indicator_type: 指标类型，可选 BOLL、VEGAS 或 ALL
        """
        try:
            if indicator_type in [IndicatorType.BOLL, IndicatorType.ALL]:
                # 添加布林带
                middle, upper, lower = self.calculate_bollinger_bands(df)
                ax.plot(df.index, middle, '--', color='yellow', label='BOLL Middle', alpha=0.7, linewidth=1)
                ax.plot(df.index, upper, '--', color='red', label='BOLL Upper', alpha=0.7, linewidth=1)
                ax.plot(df.index, lower, '--', color='green', label='BOLL Lower', alpha=0.7, linewidth=1)
            
            if indicator_type in [IndicatorType.VEGAS, IndicatorType.ALL]:
                # 添加维加斯通道
                ema1, ema2, ema3 = self.calculate_vegas_tunnel(df)
                ax.plot(df.index, ema1, '-', color='blue', label=f'EMA{self.vegas_ema1}', alpha=0.7, linewidth=1)
                ax.plot(df.index, ema2, '-', color='magenta', label=f'EMA{self.vegas_ema2}', alpha=0.7, linewidth=1)
                ax.plot(df.index, ema3, '-', color='cyan', label=f'EMA{self.vegas_ema3}', alpha=0.7, linewidth=1)
            
            # 添加图例
            ax.legend(loc='upper right', bbox_to_anchor=(0.99, 0.99))
            
        except Exception as e:
            logger.error(f"添加指标到图表时出错: {e}")
    
    def get_indicator_plots(self, df: pd.DataFrame,
                          indicator_type: IndicatorType = IndicatorType.ALL) -> List[Dict]:
        """
        获取技术指标的绘图参数
        
        Args:
            df: 数据DataFrame
            indicator_type: 指标类型，可选 BOLL、VEGAS 或 ALL
            
        Returns:
            mplfinance的addplot参数列表
        """
        plots = []
        try:
            if indicator_type in [IndicatorType.BOLL, IndicatorType.ALL]:
                # 添加布林带
                middle, upper, lower = self.calculate_bollinger_bands(df)
                plots.extend([
                    mpf.make_addplot(middle, color='yellow', linestyle='--', width=1, alpha=0.7, secondary_y=False),
                    mpf.make_addplot(upper, color='red', linestyle='--', width=1, alpha=0.7, secondary_y=False),
                    mpf.make_addplot(lower, color='green', linestyle='--', width=1, alpha=0.7, secondary_y=False)
                ])
            
            if indicator_type in [IndicatorType.VEGAS, IndicatorType.ALL]:
                # 添加维加斯通道
                ema1, ema2, ema3 = self.calculate_vegas_tunnel(df)
                plots.extend([
                    mpf.make_addplot(ema1, color='blue', width=1, alpha=0.7, secondary_y=False),
                    mpf.make_addplot(ema2, color='magenta', width=1, alpha=0.7, secondary_y=False),
                    mpf.make_addplot(ema3, color='cyan', width=1, alpha=0.7, secondary_y=False)
                ])
            
        except Exception as e:
            logger.error(f"准备技术指标绘图参数时出错: {e}")
        
        return plots
    
    @staticmethod
    def prepare_dataframe(data: List[List]) -> pd.DataFrame:
        """
        将原始数据转换为DataFrame
        
        Args:
            data: K线数据列表
            
        Returns:
            处理后的DataFrame
        """
        try:
            # 创建DataFrame
            df = pd.DataFrame(data, columns=['Date', 'Open', 'Close', 'High', 'Low', 'Volume', 'Amount'])
            
            # 转换时间戳为日期
            df['Date'] = pd.to_datetime(df['Date'].astype(int), unit='s')
            
            # 设置日期为索引
            df.set_index('Date', inplace=True)
            
            # 确保数值类型
            numeric_columns = ['Open', 'Close', 'High', 'Low', 'Volume', 'Amount']
            df[numeric_columns] = df[numeric_columns].apply(pd.to_numeric)
            
            # 按时间升序排序
            df.sort_index(inplace=True)
            
            return df
        except Exception as e:
            logger.error(f"准备DataFrame时出错: {e}")
            return pd.DataFrame() 