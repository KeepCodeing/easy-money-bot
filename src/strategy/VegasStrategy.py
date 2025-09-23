#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
基于维加斯通道（Vegas Tunnel）的趋势跟踪策略 (修改版)。
"""

import logging
import pandas as pd
from typing import List, Dict, Any

from .StrategyInterface import StrategyInterface

logger = logging.getLogger(__name__)

class VegasStrategy(StrategyInterface):
    """
    维加斯通道交易策略 (修改版):
    - 买入信号: 当趋势向上 (EMA12 > EMA144)，且收盘价处于通道区间 (EMA144 和 EMA169 之间) 时，产生'buy'信号。
    - 卖出信号: 当收盘价跌破 EMA12 时，产生'sell'信号。
    """

    def __init__(self):
        """
        初始化维加斯策略。
        """
        super().__init__()
        # 从指标计算器中获取EMA参数，动态生成策略名称
        ema1 = self.indicators_calculator.vegas_ema1
        ema2 = self.indicators_calculator.vegas_ema2
        ema3 = self.indicators_calculator.vegas_ema3
        self.strategy_name = f"Vegas_Modified_{ema1}_{ema2}_{ema3}"

    def detect(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        执行修改版的维加斯通道策略检测。

        Args:
            raw_kline_data (List[list]): 原始K线数据。

        Returns:
            List[Dict[str, Any]]: 信号列表。
        """
        signals = []

        # 确保数据量足以计算最长的EMA
        required_len = self.indicators_calculator.vegas_ema3
        if df.empty or len(df) < required_len:
            logger.warning(f"数据不足 ({len(df)} < {required_len})，无法计算维加斯通道。")
            return signals

        # 1. 计算维加斯通道指标
        ema1, ema2, ema3 = self.indicators_calculator.calculate_vegas_tunnel(df)
        if ema1.isna().all() or ema2.isna().all() or ema3.isna().all():
            return signals

        # 2. 获取最新数据点的信息
        latest_data = df.iloc[-1]
        latest_timestamp = df.index[-1]
        latest_close = latest_data['Close']

        latest_ema1 = ema1.iloc[-1]  # 快线
        latest_ema2 = ema2.iloc[-1]  # 中线
        latest_ema3 = ema3.iloc[-1]  # 慢线/过滤线

        # 3. 判断信号
        signal_type = None

        # ==================== 新的买入逻辑 ====================
        is_uptrend = latest_ema1 > latest_ema2
        # 维加斯通道由EMA144和EMA169组成，正常情况下EMA144在EMA169之上
        tunnel_upper_bound = latest_ema2
        tunnel_lower_bound = latest_ema3
        is_price_in_tunnel = tunnel_lower_bound <= latest_close <= tunnel_upper_bound

        if is_uptrend and is_price_in_tunnel:
            signal_type = 'buy'
        # ======================================================

        # ==================== 新的卖出逻辑 ====================
        price_break_ema12 = latest_close < latest_ema1

        if price_break_ema12:
            signal_type = 'sell'
        # ======================================================

        # 4. 如果有信号，则构建并添加信号字典
        if signal_type:
            signal = {
                'strategy': self.strategy_name,
                'type': signal_type,
                'price': latest_close,  # 使用收盘价作为信号价格
                'timestamp': latest_timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'details': {
                    'close_price': round(latest_close, 2),
                    'ema_fast(12)': round(latest_ema1, 2),
                    'ema_medium(144)': round(latest_ema2, 2),
                    'ema_slow(169)': round(latest_ema3, 2),
                    'is_uptrend': is_uptrend
                }
            }
            signals.append(signal)
            logger.info(f"策略 {self.strategy_name} 检测到信号: {signal}")

        return signals