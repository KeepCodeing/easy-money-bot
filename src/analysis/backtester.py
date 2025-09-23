#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
可视化回测模块

负责在全部历史数据上运行策略，并收集所有历史信号点。
"""

import logging
from typing import List, Dict, Any

import pandas as pd

from src.strategy.StrategyCenter import StrategyCenter

logger = logging.getLogger(__name__)

class Backtester:
    """
    一个简单的可视化回测器。
    它不计算盈亏，只负责找出策略在历史上所有可能的信号点。
    """
    def __init__(self):
        self.strategy_center = StrategyCenter()
        # 从策略中心获取数据准备方法
        self._prepare_dataframe = self.strategy_center._prepare_dataframe

    def run(self, raw_kline_data: List[list]) -> List[Dict[str, Any]]:
        """
        在完整的历史数据集上运行所有已配置的策略。

        Args:
            raw_kline_data (List[list]): 完整的原始K线数据。
            min_history_days (int): 策略开始检测前所需的最少历史数据天数。
                                     应大于最长均线周期，例如 MA112。

        Returns:
            List[Dict[str, Any]]: 在整个历史中检测到的所有信号的列表。
        """
        all_historical_signals = []
        df = self._prepare_dataframe(raw_kline_data)

        