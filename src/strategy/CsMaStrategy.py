#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
基于三条移动平均线 (MA) 的自定义交叉策略 (支持全量历史数据扫描)。
"""

import logging
from typing import List, Dict, Any

import pandas as pd
from .StrategyInterface import StrategyInterface

logger = logging.getLogger(__name__)

class CsMaStrategy(StrategyInterface):
    """
    自定义均线交叉策略 (CsMaStrategy):
    1. 趋势过滤: 仅在 MA56 > MA112 时考虑买入。
    2. 买入信号 1 (金叉): MA7 上穿 MA56。
    3. 买入信号 2 (回调支撑): 价格上穿 MA112。
    4. 卖出信号 (跌破快线): 价格下穿 MA7。
    """

    def __init__(self):
        """初始化CsMa策略。"""
        super().__init__()
        fast = self.indicators_calculator.cs_ma_fast
        medium = self.indicators_calculator.cs_ma_medium
        slow = self.indicators_calculator.cs_ma_slow
        self.strategy_name = f"CsMaStrategy_{fast}_{medium}_{slow}"

    def detect(self, df: pd.DataFrame, mode: str = 'newest') -> List[Dict[str, Any]]:
        """执行CsMa策略检测。"""
        required_len = self.indicators_calculator.cs_ma_slow
        if df.empty or len(df) < required_len:
            logger.warning(f"数据不足 ({len(df)} < {required_len})，无法计算 CsMa。")
            return []

        # 1. 计算指标
        ma7, ma56, ma112 = self.indicators_calculator.calculate_cs_ma(df)
        if ma7.isna().all() or ma56.isna().all() or ma112.isna().all():
            return []
        
        signals = []

        # 2. 根据模式执行
        if mode == 'newest':
            # --- 核心修复：使用 .isna().any() 来检查NaN ---
            if len(df) < 2 or any(s.iloc[-2:].isna().any() for s in [df['Close'], ma7, ma56, ma112]):
                return []
            
            signal_type, details = self._check_signal_condition(
                df['Close'].iloc[-2], df['Close'].iloc[-1],
                ma7.iloc[-2], ma7.iloc[-1],
                ma56.iloc[-2], ma56.iloc[-1],
                ma112.iloc[-2], ma112.iloc[-1]
            )
            if signal_type:
                signals.append(self._create_signal_dict(df.index[-1], df['Close'].iloc[-1], signal_type, details))

        elif mode == 'full':
            df_merged = pd.DataFrame({
                'Close': df['Close'], 'ma7': ma7, 'ma56': ma56, 'ma112': ma112
            }).dropna()
            
            for i in range(1, len(df_merged)):
                prev = df_merged.iloc[i-1]
                curr = df_merged.iloc[i]
                
                signal_type, details = self._check_signal_condition(
                    prev['Close'], curr['Close'],
                    prev['ma7'], curr['ma7'],
                    prev['ma56'], curr['ma56'],
                    prev['ma112'], curr['ma112']
                )
                if signal_type:
                    signals.append(self._create_signal_dict(curr.name, curr['Close'], signal_type, details))

        if signals:
            logger.info(f"策略 {self.strategy_name} 在模式 '{mode}' 下检测到 {len(signals)} 个信号。")
        return signals

    def _check_signal_condition(self, prev_price, curr_price, prev_ma7, curr_ma7, prev_ma56, curr_ma56, prev_ma112, curr_ma112) -> (str | None, Dict | None):
        signal_type, details = None, None

        # 卖出信号 (最高优先级)
        if prev_price > prev_ma7 and curr_price < curr_ma7:
            signal_type = 'sell'
            details = {'condition': 'Price crosses below MA7', 'price': curr_price, 'ma7': round(curr_ma7, 2)}
            return signal_type, details

        # 趋势过滤
        is_uptrend_filter = curr_ma56 > curr_ma112
        if is_uptrend_filter:
            # 买入信号 1 (金叉)
            if prev_ma7 < prev_ma56 and curr_ma7 > curr_ma56:
                signal_type = 'buy'
                details = {'condition': 'MA7 crosses above MA56', 'ma7': round(curr_ma7, 2), 'ma56': round(curr_ma56, 2)}
            # 买入信号 2 (回调支撑)
            elif prev_price < prev_ma112 and curr_price > curr_ma112:
                signal_type = 'buy'
                details = {'condition': 'Price crosses above MA112', 'price': curr_price, 'ma112': round(curr_ma112, 2)}
        
        return signal_type, details

    def _create_signal_dict(self, timestamp, price, signal_type, details) -> Dict[str, Any]:
        return {
            'strategy': self.strategy_name,
            'type': signal_type,
            'price': price,
            'timestamp': pd.to_datetime(timestamp).strftime('%Y-%m-%d %H:%M:%S'),
            'details': details
        }