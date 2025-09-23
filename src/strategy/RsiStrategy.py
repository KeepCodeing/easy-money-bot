#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
基于RSI指标的超买超卖策略 (支持全量历史数据扫描)。
"""

import logging
from typing import List, Dict, Any

import pandas as pd
from .StrategyInterface import StrategyInterface # 假设您已恢复了StrategyInterface.py

logger = logging.getLogger(__name__)

class RsiStrategy(StrategyInterface):
    """
    RSI超买超卖策略：
    - 当RSI < 30 (超卖区)，产生 'buy' 信号。
    - 当RSI > 80 (超买区)，产生 'sell' 信号。
    """

    def __init__(self,
                 oversold_threshold: int = 35,
                 overbought_threshold: int = 75):
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


    def detect(self, df: pd.DataFrame, mode: str = 'newest') -> List[Dict[str, Any]]:
        """
        执行RSI策略检测。

        Args:
            df (pd.DataFrame): 预处理好的K线数据。
            mode (str, optional): 检测模式。
                                  'newest': 只检测最新的数据点 (用于实时信号)。
                                  'full': 检测全部历史数据点 (用于回测)。
                                  默认为 'newest'。

        Returns:
            List[Dict[str, Any]]: 信号列表。
        """
        if df.empty or len(df) < self.indicators_calculator.rsi_period:
            logger.warning("数据不足，无法计算RSI。")
            return []

        # --- 1. 计算RSI指标 (对全量数据一次性计算) ---
        rsi_series = self.indicators_calculator.calculate_rsi(df)
        if rsi_series.empty or rsi_series.isna().all():
            return []
        
        signals = []

        # --- 2. 根据模式执行不同逻辑 ---
        if mode == 'newest':
            # --- 原有逻辑：只处理最新点 ---
            latest_rsi = rsi_series.iloc[-1]
            if pd.isna(latest_rsi): return []

            latest_data = df.iloc[-1]
            signal_type = self._check_signal_condition(latest_rsi)
            
            if signal_type:
                signal = self._create_signal_dict(
                    timestamp=df.index[-1],
                    price=latest_data['Close'],
                    signal_type=signal_type,
                    rsi_value=latest_rsi
                )
                signals.append(signal)

        elif mode == 'full':
            # --- 新逻辑：遍历全量数据 ---
            for i in range(len(rsi_series)):
                current_rsi = rsi_series.iloc[i]
                if pd.isna(current_rsi): continue

                signal_type = self._check_signal_condition(current_rsi)

                if signal_type:
                    current_data = df.iloc[i]
                    signal = self._create_signal_dict(
                        timestamp=df.index[i],
                        price=current_data['Close'],
                        signal_type=signal_type,
                        rsi_value=current_rsi
                    )
                    signals.append(signal)
        
        else:
            logger.warning(f"未知的检测模式: '{mode}'。请使用 'newest' 或 'full'。")

        if signals:
            logger.info(f"策略 {self.strategy_name} 在模式 '{mode}' 下检测到 {len(signals)} 个信号。")
        
        return signals

    def _check_signal_condition(self, rsi_value: float) -> str | None:
        """辅助函数：检查单点的RSI是否触发信号"""
        if rsi_value < self.oversold_threshold:
            return 'buy'
        elif rsi_value > self.overbought_threshold:
            return 'sell'
        return None

    def _create_signal_dict(self, timestamp, price, signal_type, rsi_value) -> Dict[str, Any]:
        """辅助函数：创建标准格式的信号字典"""
        return {
            'strategy': self.strategy_name,
            'type': signal_type,
            'price': price,
            'timestamp': pd.to_datetime(timestamp).strftime('%Y-%m-%d %H:%M:%S'),
            'details': {
                'rsi_value': round(rsi_value, 2),
                'threshold': self.oversold_threshold if signal_type == 'buy' else self.overbought_threshold
            }
        }