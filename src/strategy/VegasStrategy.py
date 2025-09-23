#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
基于维加斯通道（Vegas Tunnel）的趋势跟踪策略 (趋势过滤增强版)。
"""

import logging
from typing import List, Dict, Any

import pandas as pd
from .StrategyInterface import StrategyInterface

logger = logging.getLogger(__name__)

class VegasStrategy(StrategyInterface):
    """
    维加斯通道交易策略 (趋势过滤增强版):
    - 核心过滤: 当通道处于空头排列 (EMA144 < EMA169) 时，不进行任何操作。
    - 买入信号: 当通道处于多头排列 (EMA144 > EMA169 且 EMA12 > EMA144)，
                且收盘价处于通道区间 (EMA144 和 EMA169 之间) 时，产生'buy'信号。
    - 卖出信号: 当价格跌破 EMA12 时，产生'sell'信号 (仅在非空头排列时有效)。
    """

    def __init__(self):
        """
        初始化维加斯策略。
        """
        super().__init__()
        ema1 = self.indicators_calculator.vegas_ema1
        ema2 = self.indicators_calculator.vegas_ema2
        ema3 = self.indicators_calculator.vegas_ema3
        self.strategy_name = f"Vegas_TrendFilter_{ema1}_{ema2}_{ema3}"

    def detect(self, df: pd.DataFrame, mode: str = 'newest') -> List[Dict[str, Any]]:
        """
        执行趋势过滤增强版的维加斯通道策略检测。
        """
        required_len = self.indicators_calculator.vegas_ema3
        if df.empty or len(df) < required_len:
            logger.warning(f"数据不足 ({len(df)} < {required_len})，无法计算维加斯通道。")
            return []

        # 1. 对全量数据一次性计算维加斯通道指标
        ema1, ema2, ema3 = self.indicators_calculator.calculate_vegas_tunnel(df)
        if ema1.isna().all() or ema2.isna().all() or ema3.isna().all():
            return []
        
        # 为了方便遍历，将所有需要的数据合并到一个DataFrame中
        df_merged = df.copy()
        df_merged['ema12'] = ema1
        df_merged['ema144'] = ema2
        df_merged['ema169'] = ema3
        df_merged.dropna(inplace=True)

        if df_merged.empty:
            return []

        signals = []
        
        # 2. 根据模式选择要处理的数据范围
        if mode == 'newest':
            # 只处理最后一行数据
            rows_to_process = [df_merged.iloc[-1]]
        elif mode == 'full':
            # 处理所有有效数据
            rows_to_process = [df_merged.iloc[i] for i in range(len(df_merged))]
        else:
            logger.warning(f"未知的检测模式: '{mode}'。")
            return []

        # 3. 遍历并执行策略逻辑
        for row in rows_to_process:
            signal_type, details = self._check_signal_condition(row)
            if signal_type:
                signal = self._create_signal_dict(
                    timestamp=row.name, # .name是索引(即时间戳)
                    price=row['Close'],
                    signal_type=signal_type,
                    details=details
                )
                signals.append(signal)

        if signals:
            logger.info(f"策略 {self.strategy_name} 在模式 '{mode}' 下检测到 {len(signals)} 个信号。")
        
        return signals

    def _check_signal_condition(self, data_point) -> (str | None, Dict | None):
        """辅助函数：检查单个数据点是否满足维加斯策略条件"""
        open_price = data_point['Open']
        close_price = data_point['Close']
        ema12 = data_point['ema12']
        ema144 = data_point['ema144']
        ema169 = data_point['ema169']
        
        signal_type = None
        details = None

        # --- 核心趋势过滤 ---
        # 检查是否为空头排列
        is_downtrend_tunnel = ema144 < ema169
        if is_downtrend_tunnel:
            return None, None # 空头排列，不进行任何操作

        # --- 在非空头排列下，检查买卖信号 ---
        
        # 新的买入逻辑
        # is_full_uptrend = ema12 > ema144 # 此时 ema144 >= ema169 已被确认
        # is_price_in_tunnel = ema169 <= close_price <= ema144

        # if is_full_uptrend and is_price_in_tunnel:
        #     signal_type = 'buy'
        is_price_in_tunnel = open_price <= ema169 and close_price >= ema144

        if is_price_in_tunnel:
            signal_type = 'buy'

        # 新的卖出逻辑
        if signal_type == None:
            price_break_ema12 = close_price < open_price and close_price < ema12
            if price_break_ema12:
                signal_type = 'sell'

        if signal_type:
            details = {
                'close_price': round(close_price, 2),
                'ema_fast(12)': round(ema12, 2),
                'ema_medium(144)': round(ema144, 2),
                'ema_slow(169)': round(ema169, 2),
                'is_downtrend_tunnel': is_downtrend_tunnel
            }
            return signal_type, details
            
        return None, None

    def _create_signal_dict(self, timestamp, price, signal_type, details) -> Dict[str, Any]:
        """辅助函数：创建标准格式的信号字典"""
        return {
            'strategy': self.strategy_name,
            'type': signal_type,
            'price': price,
            'timestamp': pd.to_datetime(timestamp).strftime('%Y-%m-%d %H:%M:%S'),
            'details': details
        }