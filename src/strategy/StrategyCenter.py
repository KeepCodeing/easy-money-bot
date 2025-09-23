#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
策略中心 (Strategy Center) (优化版)

负责管理、调度和执行所有已注册的量化交易策略。
"""

import logging
from typing import List, Dict, Any

import pandas as pd
from config import settings
from .StrategyInterface import StrategyInterface
from .RsiStrategy import RsiStrategy
from .MacdStrategy import MacdStrategy
from .BollingerStrategy import BollingerStrategy
from .VegasStrategy import VegasStrategy
from .CsMaStrategy import CsMaStrategy

logger = logging.getLogger(__name__)

class StrategyCenter:
    """
    策略中心 (优化版)。
    数据预处理仅执行一次，然后将DataFrame分发给所有策略。
    """

    def __init__(self):
        """
        初始化策略中心，注册所有可用的策略。
        """
        self._strategies = {
            "RSI": RsiStrategy,
            "MACD": MacdStrategy,
            "Bollinger": BollingerStrategy,
            "Vegas": VegasStrategy,
            "CsMa": CsMaStrategy,
        }
        
        self.configured_strategies = settings.STRATEGYS
        
        logger.info(f"策略中心已初始化，已注册策略: {list(self._strategies.keys())}")
        logger.info(f"将按顺序执行以下策略: {self.configured_strategies}")

    def _prepare_dataframe(self, raw_kline_data: List[list]) -> pd.DataFrame:
        """
        将原始K线数据列表转换为格式正确的DataFrame。
        (此方法从策略基类移至此处)
        """
        if not raw_kline_data:
            return pd.DataFrame()
        try:
            df = pd.DataFrame(
                raw_kline_data,
                columns=['Time', 'Open', 'Close', 'High', 'Low', 'Volume', 'Amount']
            )
            df['Time'] = pd.to_datetime(df['Time'].astype(int), unit='s')
            df.set_index('Time', inplace=True)
            numeric_cols = ['Open', 'Close', 'High', 'Low', 'Volume', 'Amount']
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            df.sort_index(inplace=True)
            return df
        except Exception as e:
            logger.error(f"在策略中心准备DataFrame时出错: {e}")
            return pd.DataFrame()

    def run_strategies(self, raw_kline_data: List[list]) -> List[Dict[str, Any]]:
        """
        统一的策略执行入口 (已优化)。
        """
        # configured_strategies = getattr(settings, 'STRATEGIES', [])
        if not self.configured_strategies:
            logger.warning("配置文件中未指定任何策略 (STRATEGIES)，不执行任何操作。")
            return []

        # --- 核心优化：数据只处理一次 ---
        df = self._prepare_dataframe(raw_kline_data)
        if df.empty:
            logger.warning("原始数据为空或处理失败，无法执行策略。")
            return []
        # --------------------------------

        all_signals = []

        for strategy_name in self.configured_strategies:
            strategy_class = self._strategies.get(strategy_name)
            if not strategy_class:
                logger.warning(f"策略 '{strategy_name}' 未在策略中心注册，已跳过。")
                continue

            try:
                strategy_instance: StrategyInterface = strategy_class()
                # 将预处理好的DataFrame传递给每个策略
                signals = strategy_instance.detect(df) 
                if signals:
                    all_signals.extend(signals)
            except Exception as e:
                logger.error(f"执行策略 '{strategy_name}' 时出错: {e}", exc_info=True)

        logger.info(f"所有策略执行完毕，共产生 {len(all_signals)} 个信号。")
        return all_signals