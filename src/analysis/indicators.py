#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
技术指标计算模块
"""

import logging
from enum import Enum
from typing import List, Tuple

import pandas as pd
import pandas_ta as ta  # 导入pandas-ta库
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

        # 成交量MA参数
        self.volume_ma1 = settings.VOLUME_MA1
        self.volume_ma2 = settings.VOLUME_MA2
        self.volume_ma3 = settings.VOLUME_MA3

        # (新增) RSI 参数
        self.rsi_period = getattr(settings, 'RSI_PERIOD', 14)

        # (新增) MACD 参数
        self.macd_fast = getattr(settings, 'MACD_FAST', 12)
        self.macd_slow = getattr(settings, 'MACD_SLOW', 26)
        self.macd_signal = getattr(settings, 'MACD_SIGNAL', 9)
        
        # (新增) CsMa 参数
        self.cs_ma_fast = getattr(settings, 'CS_MA_FAST', 7)
        self.cs_ma_medium = getattr(settings, 'CS_MA_MEDIUM', 56)
        self.cs_ma_slow = getattr(settings, 'CS_MA_SLOW', 112)
    
    def calculate_bollinger_bands(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """计算布林带指标"""
        try:
            middle = df['Close'].rolling(window=self.boll_period).mean()
            std = df['Close'].rolling(window=self.boll_period).std()
            upper = middle + (std * self.boll_std)
            lower = middle - (std * self.boll_std)
            return middle, upper, lower
        except Exception as e:
            logger.error(f"计算布林带时出错: {e}")
            return pd.Series(), pd.Series(), pd.Series()
    
    def calculate_vegas_tunnel(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """计算维加斯通道指标"""
        try:
            ema1 = df['Close'].ewm(span=self.vegas_ema1, adjust=False).mean()
            ema2 = df['Close'].ewm(span=self.vegas_ema2, adjust=False).mean()
            ema3 = df['Close'].ewm(span=self.vegas_ema3, adjust=False).mean()
            return ema1, ema2, ema3
        except Exception as e:
            logger.error(f"计算维加斯通道时出错: {e}")
            return pd.Series(), pd.Series(), pd.Series()
    
    def calculate_volume_ma(self, df: pd.DataFrame) -> List[pd.Series]:
        """计算成交量的移动平均线"""
        try:
            ma1 = df['Volume'].rolling(window=self.volume_ma1, min_periods=1).mean()
            ma2 = df['Volume'].rolling(window=self.volume_ma2, min_periods=1).mean()
            ma3 = df['Volume'].rolling(window=self.volume_ma3, min_periods=1).mean()
            return [ma1, ma2, ma3]
        except Exception as e:
            logger.error(f"计算成交量MA时出错: {e}")
            return [pd.Series(), pd.Series(), pd.Series()]

    # --- 新增方法 ---
    def calculate_rsi(self, df: pd.DataFrame) -> pd.Series:
        """
        计算相对强弱指数 (RSI)。
        
        Args:
            df: 包含'Close'列的DataFrame。
            
        Returns:
            pd.Series: RSI指标序列。
        """
        try:
            rsi = df.ta.rsi(length=self.rsi_period)
            return rsi
        except Exception as e:
            logger.error(f"计算RSI时出错: {e}")
            return pd.Series(dtype=float)

    def calculate_macd(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        计算移动平均收敛散度 (MACD)。
        
        Args:
            df: 包含'Close'列的DataFrame。
            
        Returns:
            Tuple[pd.Series, pd.Series, pd.Series]: (MACD线, 信号线, 柱状图)。
        """
        try:
            macd_df = df.ta.macd(fast=self.macd_fast, slow=self.macd_slow, signal=self.macd_signal)
            # pandas-ta返回的列名格式为 'MACD_12_26_9', 'MACDh_12_26_9', 'MACDs_12_26_9'
            macd_line = macd_df[f'MACD_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}']
            histogram = macd_df[f'MACDh_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}']
            signal_line = macd_df[f'MACDs_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}']
            return macd_line, signal_line, histogram
        except Exception as e:
            logger.error(f"计算MACD时出错: {e}")
            return pd.Series(dtype=float), pd.Series(dtype=float), pd.Series(dtype=float)
        
    def calculate_cs_ma(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        计算CsMa策略所需的三条移动平均线 (MA)。

        Args:
            df: 包含'Close'列的DataFrame。

        Returns:
            Tuple[pd.Series, pd.Series, pd.Series]: (MA快线, MA中线, MA慢线)。
        """
        try:
            ma_fast = df['Close'].rolling(window=self.cs_ma_fast).mean()
            ma_medium = df['Close'].rolling(window=self.cs_ma_medium).mean()
            ma_slow = df['Close'].rolling(window=self.cs_ma_slow).mean()
            return ma_fast, ma_medium, ma_slow
        except Exception as e:
            logger.error(f"计算CS MA时出错: {e}")
            return pd.Series(dtype=float), pd.Series(dtype=float), pd.Series(dtype=float)