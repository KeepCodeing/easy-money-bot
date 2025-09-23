#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
基于MACD指标的交叉策略。
"""

import logging
import pandas as pd
from typing import List, Dict, Any

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
        # 从指标计算器中获取MACD参数，动态生成策略名称
        fast = self.indicators_calculator.macd_fast
        slow = self.indicators_calculator.macd_slow
        signal = self.indicators_calculator.macd_signal
        self.strategy_name = f"MACD_Cross_{fast}_{slow}_{signal}"

    def detect(self,  df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        执行MACD交叉策略检测。

        Args:
            raw_kline_data (List[list]): 原始K线数据。

        Returns:
            List[Dict[str, Any]]: 信号列表。
        """
        signals = []

        # 需要足够的数据来计算MACD并判断交叉，至少需要慢线周期+信号线周期
        required_len = self.indicators_calculator.macd_slow + self.indicators_calculator.macd_signal
        if df.empty or len(df) < required_len:
            logger.warning(f"数据不足 ({len(df)} < {required_len})，无法计算MACD交叉。")
            return signals

        # 1. 计算MACD指标
        macd_line, signal_line, _ = self.indicators_calculator.calculate_macd(df)
        if macd_line.empty or signal_line.empty or macd_line.isna().all():
            return signals
            
        # 2. 获取最新和次新的数据点以判断交叉
        # 我们需要至少两个非NaN值来比较
        macd_line = macd_line.dropna()
        signal_line = signal_line.dropna()
        
        if len(macd_line) < 2 or len(signal_line) < 2:
            return signals

        latest_macd = macd_line.iloc[-1]
        prev_macd = macd_line.iloc[-2]
        
        latest_signal_line = signal_line.iloc[-1]
        prev_signal_line = signal_line.iloc[-2]

        latest_timestamp = df.index[-1]
        latest_price = df.iloc[-1]['Close']

        # 3. 判断信号
        signal_type = None
        # 判断金叉 (Buy Signal)
        if prev_macd < prev_signal_line and latest_macd > latest_signal_line:
            signal_type = 'buy'
        # 判断死叉 (Sell Signal)
        elif prev_macd > prev_signal_line and latest_macd < latest_signal_line:
            signal_type = 'sell'
        
        # 4. 如果有信号，则构建并添加信号字典
        if signal_type:
            signal = {
                'strategy': self.strategy_name,
                'type': signal_type,
                'price': latest_price,
                'timestamp': latest_timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'details': {
                    'cross_type': 'Golden Cross' if signal_type == 'buy' else 'Death Cross',
                    'macd_line': round(latest_macd, 2),
                    'signal_line': round(latest_signal_line, 2)
                }
            }
            signals.append(signal)
            logger.info(f"策略 {self.strategy_name} 检测到信号: {signal}")

        return signals