#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
基于RSI指标的超买超卖策略。
"""

import logging
import pandas as pd
from typing import List, Dict, Any

from .StrategyInterface import StrategyInterface
from config import settings # 引入配置以获取RSI阈值

logger = logging.getLogger(__name__)

class RsiStrategy(StrategyInterface):
    """
    RSI超买超卖策略：
    - 当RSI < 30 (超卖区)，产生 'buy' 信号。
    - 当RSI > 80 (超买区)，产生 'sell' 信号。
    """

    def __init__(self,
                 oversold_threshold: int = 30,
                 overbought_threshold: int = 80):
        """
        初始化RSI策略的特定参数。

        Args:
            oversold_threshold (int): 超卖阈值。
            overbought_threshold (int): 超买阈值。
        """
        super().__init__()
        self.oversold_threshold = oversold_threshold
        self.overbought_threshold = overbought_threshold
        self.strategy_name = f"RSI_{self.oversold_threshold}_{self.overbought_threshold}"


    def detect(self,  df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        执行RSI策略检测。

        Args:
            raw_kline_data (List[list]): 原始K线数据。

        Returns:
            List[Dict[str, Any]]: 信号列表。
        """
        signals = []

        if df.empty or len(df) < self.indicators_calculator.rsi_period:
            logger.warning("数据不足，无法计算RSI。")
            return signals

        # 1. 计算RSI指标
        rsi_series = self.indicators_calculator.calculate_rsi(df)
        if rsi_series.empty or rsi_series.isna().all():
            return signals
            
        # 2. 获取最新数据点的信息
        latest_data = df.iloc[-1]
        latest_rsi = rsi_series.iloc[-1]
        latest_timestamp = df.index[-1]
        latest_price = latest_data['Close']

        # 3. 判断信号
        signal_type = None
        if latest_rsi < self.oversold_threshold:
            signal_type = 'buy'
        elif latest_rsi > self.overbought_threshold:
            signal_type = 'sell'
        
        # 4. 如果有信号，则构建并添加信号字典
        if signal_type:
            signal = {
                'strategy': self.strategy_name,
                'type': signal_type,
                'price': latest_price,
                'timestamp': latest_timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'details': {
                    'rsi_value': round(latest_rsi, 2),
                    'threshold': self.oversold_threshold if signal_type == 'buy' else self.overbought_threshold
                }
            }
            signals.append(signal)
            logger.info(f"策略 {self.strategy_name} 检测到信号: {signal}")

        return signals