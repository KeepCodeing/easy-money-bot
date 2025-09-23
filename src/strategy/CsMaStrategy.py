#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
基于三条移动平均线 (MA) 的自定义交叉策略。
"""

import logging
import pandas as pd
from typing import List, Dict, Any

from .StrategyInterface import StrategyInterface

logger = logging.getLogger(__name__)

class CsMaStrategy(StrategyInterface):
    """
    自定义均线交叉策略 (CsMaStrategy):
    1. 趋势过滤: 仅在 MA56 > MA112 时考虑买入。
    2. 买入信号 1 (金叉): MA7 上穿 MA56。
    3. 买入信号 2 (回调支撑): 价格上穿 MA112。
    4. 卖出信号 (跌破快线): 价格下穿 MA7。
    注意：目前看起来适用于炒作品的信号检测。像印花集A1这种热门品，可能会给出错误信号，或者增加交易磨损。
    采用的7，56，112分别是7天交易冷却的不同周期。MA7上穿MA56认为有大量买入信号，趋势可能改变；MA112穿行价格，
    认为价格超跌，可能处于短期底部。
    """

    def __init__(self):
        """初始化CsMa策略。"""
        super().__init__()
        # 动态生成策略名称
        fast = self.indicators_calculator.cs_ma_fast
        medium = self.indicators_calculator.cs_ma_medium
        slow = self.indicators_calculator.cs_ma_slow
        self.strategy_name = f"CsMaStrategy_{fast}_{medium}_{slow}"

    def detect(self,  df: pd.DataFrame) -> List[Dict[str, Any]]:
        """执行CsMa策略检测。"""
        signals = []

        required_len = self.indicators_calculator.cs_ma_slow
        if df.empty or len(df) < required_len:
            logger.warning(f"数据不足 ({len(df)} < {required_len})，无法计算 CsMa。")
            return signals

        # 1. 计算所需指标
        ma7, ma56, ma112 = self.indicators_calculator.calculate_cs_ma(df)
        if ma7.isna().all() or ma56.isna().all() or ma112.isna().all():
            return signals

        # 2. 获取最新和次新的数据点以判断交叉
        if len(ma7.dropna()) < 2 or len(ma56.dropna()) < 2 or len(ma112.dropna()) < 2:
            return signals

        # 最新值
        latest_data = df.iloc[-1]
        latest_price = latest_data['Close']
        latest_ma7 = ma7.iloc[-1]
        latest_ma56 = ma56.iloc[-1]
        latest_ma112 = ma112.iloc[-1]
        latest_price_open = latest_data['Open']
        latest_price_close = latest_data['Close']
        
        # 前一个时间点的值
        prev_price = df['Close'].iloc[-2]
        prev_ma7 = ma7.iloc[-2]
        prev_ma56 = ma56.iloc[-2]
        prev_ma112 = ma112.iloc[-2]
        
        latest_timestamp = df.index[-1]

        # 3. 执行策略规则
        # 规则 1: 趋势过滤
        is_uptrend_filter = latest_ma56 > latest_ma112
        
        signal_type = None
        details = {}

        # 规则 5: 卖出信号 (最高优先级)
        # 价格下穿 MA7
        if prev_price > prev_ma7 and latest_price < latest_ma7:
            signal_type = 'sell'
            details = {
                'condition': 'Price crosses below MA7',
                'price': latest_price, 'ma7': round(latest_ma7, 2)
            }
        
        # 只有在卖出信号未触发时，才考虑买入信号
        if not signal_type:
            # 规则 2: 趋势过滤
            if is_uptrend_filter:
                # 规则 3: 买入信号 1 (金叉)
                # MA7 上穿 MA56
                if prev_ma7 < prev_ma56 and latest_ma7 > latest_ma56 and is_uptrend_filter:
                    signal_type = 'buy'
                    details = {
                        'condition': 'MA7 crosses above MA56',
                        'ma7': round(latest_ma7, 2), 'ma56': round(latest_ma56, 2)
                    }
                
            # 规则 4: 买入信号 2 (回调支撑) - 只有在金叉未发生时才检查
            # 价格上穿 MA112
            if latest_price_open < latest_ma112 and latest_ma112 < latest_price_close:
                signal_type = 'buy'
                details = {
                    'condition': 'Price crosses MA112',
                    'price': latest_price, 'ma112': round(latest_ma112, 2)
                }

        # 4. 如果有信号，则构建并添加信号字典
        if signal_type:
            signal = {
                'strategy': self.strategy_name,
                'type': signal_type,
                'price': latest_price,
                'timestamp': latest_timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'details': details
            }
            signals.append(signal)
            logger.info(f"策略 {self.strategy_name} 检测到信号: {signal}")

        return signals