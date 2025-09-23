#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
基于布林带（Bollinger Bands）的通道突破策略 (支持全量历史数据扫描)。
"""

import logging
from typing import List, Dict, Any

import pandas as pd
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
        """
        super().__init__()
        self.upper_tolerance = upper_tolerance
        self.lower_tolerance = lower_tolerance
        
        period = self.indicators_calculator.boll_period
        std = self.indicators_calculator.boll_std
        self.strategy_name = f"Bollinger_{period}_{std}"

    def detect(self, df: pd.DataFrame, mode: str = 'newest') -> List[Dict[str, Any]]:
        """
        执行布林带策略检测。

        Args:
            df (pd.DataFrame): 预处理好的K线数据。
            mode (str, optional): 检测模式。
                                  'newest': 只检测最新的数据点。
                                  'full': 检测全部历史数据点。
                                  默认为 'newest'。
        Returns:
            List[Dict[str, Any]]: 信号列表。
        """
        if df.empty or len(df) < self.indicators_calculator.boll_period:
            logger.warning("数据不足，无法计算布林带。")
            return []

        # 1. 对全量数据一次性计算布林带指标
        middle, upper, lower = self.indicators_calculator.calculate_bollinger_bands(df)
        if upper.isna().all() or lower.isna().all():
            return []
        
        signals = []

        # 2. 根据模式执行不同逻辑
        if mode == 'newest':
            # --- 原有逻辑：只处理最新点 ---
            if upper.isna().iloc[-1] or lower.isna().iloc[-1]: return []
            
            latest_data = df.iloc[-1]
            signal_type, details = self._check_signal_condition(
                latest_data, middle.iloc[-1], upper.iloc[-1], lower.iloc[-1]
            )
            
            if signal_type:
                signal = self._create_signal_dict(
                    timestamp=df.index[-1],
                    price=latest_data['Close'],
                    signal_type=signal_type,
                    details=details
                )
                signals.append(signal)

        elif mode == 'full':
            # --- 新逻辑：遍历全量数据 ---
            for i in range(len(df)):
                # 跳过指标无效的早期数据
                if pd.isna(upper.iloc[i]) or pd.isna(lower.iloc[i]):
                    continue

                current_data = df.iloc[i]
                signal_type, details = self._check_signal_condition(
                    current_data, middle.iloc[i], upper.iloc[i], lower.iloc[i]
                )

                if signal_type:
                    signal = self._create_signal_dict(
                        timestamp=df.index[i],
                        price=current_data['Close'],
                        signal_type=signal_type,
                        details=details
                    )
                    signals.append(signal)
        
        else:
            logger.warning(f"未知的检测模式: '{mode}'。请使用 'newest' 或 'full'。")

        if signals:
            logger.info(f"策略 {self.strategy_name} 在模式 '{mode}' 下检测到 {len(signals)} 个信号。")
        
        return signals

    def _check_signal_condition(self, data_point, middle_band, upper_band, lower_band) -> (str | None, Dict | None):
        """辅助函数：检查单个数据点的价格是否触碰布林带轨道"""
        high_price = data_point['High']
        low_price = data_point['Low']
        
        signal_type = None
        
        # 检查卖出信号 (触碰上轨)
        upper_threshold = upper_band * (1 - self.upper_tolerance)
        if high_price >= upper_threshold:
            signal_type = 'sell'

        # 检查买入信号 (触碰下轨)
        lower_threshold = lower_band * (1 + self.lower_tolerance)
        if low_price <= lower_threshold:
            # 在宽幅震荡日，可能同时触碰上下轨，这里让买入信号优先
            signal_type = 'buy'
            
        if signal_type:
            details = {
                'close_price': data_point['Close'],
                'high_price': high_price,
                'low_price': low_price,
                'upper_band': round(upper_band, 2),
                'middle_band': round(middle_band, 2),
                'lower_band': round(lower_band, 2)
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