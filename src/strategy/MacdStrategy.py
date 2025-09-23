#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
基于MACD指标的交叉策略 (支持全量历史数据扫描)。
"""

import logging
from typing import List, Dict, Any

import pandas as pd
from .StrategyInterface import StrategyInterface

logger = logging.getLogger(__name__)

class MacdStrategy(StrategyInterface):
    """
    MACD交叉策略：
    - 当MACD快线 (DIF) 上穿其信号线 (DEA) 时，产生 'buy' 信号 (金叉)。
    - 当MACD快线 (DIF) 下穿其信号线 (DEA) 时，产生 'sell' 信号 (死叉)。
    """

    def __init__(self):
        """
        初始化MACD策略。
        """
        super().__init__()
        fast = self.indicators_calculator.macd_fast
        slow = self.indicators_calculator.macd_slow
        signal = self.indicators_calculator.macd_signal
        self.strategy_name = f"MACD_Cross_{fast}_{slow}_{signal}"

    def detect(self, df: pd.DataFrame, mode: str = 'newest') -> List[Dict[str, Any]]:
        """
        执行MACD交叉策略检测。

        Args:
            df (pd.DataFrame): 预处理好的K线数据。
            mode (str, optional): 检测模式。
                                  'newest': 只检测最新的数据点。
                                  'full': 检测全部历史数据点。
                                  默认为 'newest'。

        Returns:
            List[Dict[str, Any]]: 信号列表。
        """
        required_len = self.indicators_calculator.macd_slow + self.indicators_calculator.macd_signal
        if df.empty or len(df) < required_len:
            logger.warning(f"数据不足 ({len(df)} < {required_len})，无法计算 MACD交叉。")
            return []

        # 1. 对全量数据一次性计算MACD指标
        macd_line, signal_line, _ = self.indicators_calculator.calculate_macd(df)
        if macd_line.isna().all() or signal_line.isna().all():
            return []
        
        signals = []
        
        # 2. 根据模式执行不同逻辑
        if mode == 'newest':
            # --- 原有逻辑：只处理最新点 ---
            # 确保有至少两个点可以比较
            valid_macd = macd_line.dropna()
            valid_signal = signal_line.dropna()
            if len(valid_macd) < 2 or len(valid_signal) < 2:
                return []
            
            signal_type, details = self._check_cross_condition(
                macd_line.iloc[-2], macd_line.iloc[-1],
                signal_line.iloc[-2], signal_line.iloc[-1]
            )
            
            if signal_type:
                signal = self._create_signal_dict(
                    timestamp=df.index[-1],
                    price=df['Close'].iloc[-1],
                    signal_type=signal_type,
                    details=details
                )
                signals.append(signal)

        elif mode == 'full':
            # --- 新逻辑：遍历全量数据 ---
            # 将指标合并到DataFrame中以便对齐和遍历
            df_merged = df.copy()
            df_merged['macd'] = macd_line
            df_merged['signal'] = signal_line
            df_merged.dropna(inplace=True) # 去掉无法计算指标的早期数据

            # 从第二个有效数据点开始遍历，以便和前一个点比较
            for i in range(1, len(df_merged)):
                prev_row = df_merged.iloc[i-1]
                curr_row = df_merged.iloc[i]
                
                signal_type, details = self._check_cross_condition(
                    prev_row['macd'], curr_row['macd'],
                    prev_row['signal'], curr_row['signal']
                )

                if signal_type:
                    signal = self._create_signal_dict(
                        timestamp=curr_row.name, # .name是索引(即时间戳)
                        price=curr_row['Close'],
                        signal_type=signal_type,
                        details=details
                    )
                    signals.append(signal)
        
        else:
            logger.warning(f"未知的检测模式: '{mode}'。请使用 'newest' 或 'full'。")

        if signals:
            logger.info(f"策略 {self.strategy_name} 在模式 '{mode}' 下检测到 {len(signals)} 个信号。")
        
        return signals

    def _check_cross_condition(self, prev_macd, curr_macd, prev_signal, curr_signal) -> (str | None, Dict | None):
        """辅助函数：检查两个时间点的MACD线和信号线是否发生交叉"""
        details = None
        # 金叉
        if prev_macd < prev_signal and curr_macd > curr_signal:
            details = {
                'cross_type': 'Golden Cross',
                'macd_line': round(curr_macd, 2),
                'signal_line': round(curr_signal, 2)
            }
            return 'buy', details
        # 死叉
        elif prev_macd > prev_signal and curr_macd < curr_signal:
            details = {
                'cross_type': 'Death Cross',
                'macd_line': round(curr_macd, 2),
                'signal_line': round(curr_signal, 2)
            }
            return 'sell', details
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