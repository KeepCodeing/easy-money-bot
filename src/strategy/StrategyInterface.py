#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
量化交易策略接口基类 (优化版)
"""

import abc
import logging
from typing import List, Dict, Any

import pandas as pd

from src.analysis.indicators import TechnicalIndicators

logger = logging.getLogger(__name__)

class StrategyInterface(abc.ABC):
    """
    量化策略接口基类 (Abstract Base Class)。
    """

    def __init__(self):
        """
        初始化策略。
        每个策略实例都包含一个技术指标计算器。
        """
        self.indicators_calculator = TechnicalIndicators()

    @abc.abstractmethod
    def detect(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        【抽象方法】策略检测入口 (已更新)。

        接收一个预处理好的DataFrame，执行策略逻辑，并返回信号列表。

        Args:
            df (pd.DataFrame): 预处理好的、带有DateTime索引的K线数据。

        Returns:
            List[Dict[str, Any]]: 检测到的信号列表。
        """
        raise NotImplementedError("子类必须实现 detect 方法")