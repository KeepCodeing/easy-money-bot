#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
基于布林带（Bollinger Bands）的通道突破策略。
"""

import logging
import pandas as pd
from typing import List, Dict, Any

from .StrategyInterface import StrategyInterface
from config import settings

logger = logging.getLogger(__name__)

class BollingerStrategy(StrategyInterface):
    """
    布林带通道策略：
    - 当价格触碰或跌破下轨时，产生 'buy' 信号。
    - 当价格触碰或涨破上轨时，产生 'sell' 信号。
    """

    def __init__(self,
                 upper_tolerance: float = settings.BOLL_TOLERANCE_UPPER,
                 lower_tolerance: float = settings.BOLL_TOLERANCE_LOWER):
        """
        初始化布林带策略的特定参数。

        Args:
            upper_tolerance (float): 上轨的触碰容差百分比 (例如, 0.01 代表 1%)。
            lower_tolerance (float): 下轨的触碰容差百分比。
        """
        super().__init__()
        self.upper_tolerance = upper_tolerance
        self.lower_tolerance = lower_tolerance
        
        # 从指标计算器中获取布林带参数，动态生成策略名称
        period = self.indicators_calculator.boll_period
        std = self.indicators_calculator.boll_std
        self.strategy_name = f"Bollinger_{period}_{std}"

    def detect(self,  df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        执行布林带策略检测。

        Args:
            raw_kline_data (List[list]): 原始K线数据。

        Returns:
            List[Dict[str, Any]]: 信号列表。
        """
        signals = []

        if df.empty or len(df) < self.indicators_calculator.boll_period:
            logger.warning("数据不足，无法计算布林带。")
            return signals

        # 1. 计算布林带指标
        middle, upper, lower = self.indicators_calculator.calculate_bollinger_bands(df)
        if upper.isna().all() or lower.isna().all():
            return signals

        # 2. 获取最新数据点的信息
        latest_data = df.iloc[-1]
        latest_timestamp = df.index[-1]
        
        # 为了更精确地判断触碰，我们同时考虑最高/最低价和收盘价
        latest_high = latest_data['High']
        latest_low = latest_data['Low']
        latest_close = latest_data['Close']
        
        latest_upper_band = upper.iloc[-1]
        latest_lower_band = lower.iloc[-1]

        # 3. 判断信号
        signal_type = None
        price_at_signal = 0.0

        # 判断卖出信号 (触碰上轨)
        # 只要最高价超过上轨减去容差的阈值，就认为触碰
        upper_threshold = latest_upper_band * (1 - self.upper_tolerance)
        if latest_high >= upper_threshold:
            signal_type = 'sell'
            price_at_signal = latest_close # 使用收盘价作为信号价格

        # 判断买入信号 (触碰下轨)
        # 只要最低价低于下轨加上容差的阈值，就认为触碰
        lower_threshold = latest_lower_band * (1 + self.lower_tolerance)
        if latest_low <= lower_threshold:
            # 如果同时满足买入和卖出条件（例如在极宽的K线中），通常以买入优先或根据具体规则
            # 这里我们简单地让买入信号覆盖卖出信号
            signal_type = 'buy'
            price_at_signal = latest_close

        # 4. 如果有信号，则构建并添加信号字典
        if signal_type:
            signal = {
                'strategy': self.strategy_name,
                'type': signal_type,
                'price': price_at_signal,
                'timestamp': latest_timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'details': {
                    'close_price': latest_close,
                    'high_price': latest_high,
                    'low_price': latest_low,
                    'upper_band': round(latest_upper_band, 2),
                    'middle_band': round(middle.iloc[-1], 2),
                    'lower_band': round(latest_lower_band, 2)
                }
            }
            signals.append(signal)
            logger.info(f"策略 {self.strategy_name} 检测到信号: {signal}")

        return signals