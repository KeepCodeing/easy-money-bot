#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
策略回测模块
"""

import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from .indicators import TechnicalIndicators

logger = logging.getLogger(__name__)

class BollingerStrategy:
    """布林线策略回测"""

    def __init__(
        self,
        lookback_days: int = 100,
        cooldown_days: int = 8,
        tolerance: float = 0.03  # 修改默认容差为3%
    ):
        """
        初始化布林线策略回测器

        Args:
            lookback_days: 回测时间窗口（天）
            cooldown_days: 买入后的冷却期（天）
            tolerance: 触碰判定的容差范围（默认3%）
        """
        self.lookback_days = lookback_days
        self.cooldown_days = cooldown_days
        self.tolerance = tolerance
        self.indicators = TechnicalIndicators()

    def prepare_data(self, raw_data: List[List]) -> pd.DataFrame:
        """
        准备回测数据

        Args:
            raw_data: 原始K线数据

        Returns:
            处理后的DataFrame，包含技术指标
        """
        try:
            # 转换为DataFrame
            df_full = self.indicators.prepare_dataframe(raw_data)
            if df_full.empty:
                return df_full
            
            # 在全量数据上计算布林线指标
            middle, upper, lower = self.indicators.calculate_bollinger_bands(df_full)
            
            # 添加指标到DataFrame
            df_full['middle'] = middle
            df_full['upper'] = upper
            df_full['lower'] = lower
            
            # 获取回测范围
            total_days = len(df_full)
            start_idx = max(0, total_days - self.lookback_days)
            
            # 返回回测窗口的数据
            df = df_full.iloc[start_idx:]
            logger.info(f"准备回测数据: 总数据长度={total_days}, 回测窗口长度={len(df)}")
            
            return df
            
        except Exception as e:
            logger.error(f"数据准备失败: {e}")
            return pd.DataFrame()

    def detect_signals(
        self,
        df: pd.DataFrame,
        start_idx: int,
        end_idx: int,
        in_position: bool = False,
        buy_date: Optional[datetime] = None
    ) -> Tuple[bool, bool, float, float]:
        """
        检测买入和卖出信号

        Args:
            df: 数据
            start_idx: 开始位置
            end_idx: 结束位置
            in_position: 是否持仓
            buy_date: 买入日期（用于计算冷却期）

        Returns:
            (买入信号, 卖出信号, 买入价格, 卖出价格)
        """
        try:
            if df.empty:
                return False, False, 0.0, 0.0
                
            current_data = df.iloc[end_idx]
            current_date = pd.to_datetime(df.index[end_idx])
            
            # 获取当前的开盘价、收盘价和最高价
            open_price = float(current_data['Open'])
            close_price = float(current_data['Close'])
            high_price = float(current_data['High'])
            
            # 获取实体的较低价格（开盘价和收盘价中的较小值）
            body_low_price = min(open_price, close_price)
            
            # 获取布林线值
            upper_band = float(current_data['upper'])
            lower_band = float(current_data['lower'])
            middle_band = float(current_data['middle'])
            
            # 初始化信号和价格
            buy_signal = False
            sell_signal = False
            buy_price = 0.0
            sell_price = 0.0
            
            # 检查是否在冷却期
            in_cooldown = False
            if in_position and buy_date:
                days_since_buy = (current_date - buy_date).days
                in_cooldown = days_since_buy < self.cooldown_days
            
            # 检测买入信号（未持仓时）
            if not in_position:
                # 计算布林带下轨的容差范围
                lower_threshold = lower_band * (1 + self.tolerance)
                
                # 检查是否满足买入条件：
                # 1. K线实体低点触碰或接近下轨
                # 2. 收盘价高于开盘价（阳线，表示价格企稳）
                # 3. 收盘价不能高于中轨（避免追高）
                if (body_low_price <= lower_threshold and  # 触碰下轨
                    close_price > open_price and  # 阳线
                    close_price <= middle_band):  # 不超过中轨
                    buy_signal = True
                    buy_price = body_low_price
                    logger.debug(
                        f"检测到买入信号: 实体低点={body_low_price:.2f}, "
                        f"布林下轨={lower_band:.2f}, 收盘价={close_price:.2f}"
                    )
            
            # 检测卖出信号（持仓且不在冷却期时）
            elif not in_cooldown:
                # 检查上轨触碰
                upper_threshold = upper_band * (1 - self.tolerance)
                if high_price >= upper_threshold:
                    sell_signal = True
                    sell_price = high_price
                    logger.debug(f"检测到卖出信号: 最高价={high_price:.2f}, 布林上轨={upper_band:.2f}")
            
            return buy_signal, sell_signal, buy_price, sell_price
            
        except Exception as e:
            logger.error(f"信号检测失败: {e}")
            return False, False, 0.0, 0.0

    def run_backtest(self, df: pd.DataFrame) -> Dict:
        """
        运行回测

        Args:
            df: 包含技术指标的数据

        Returns:
            回测结果统计
        """
        # 初始化结果记录
        trades = []
        current_trade = None
        in_position = False
        buy_date = None
        
        # 获取回测范围
        total_days = len(df)
        start_idx = max(0, total_days - self.lookback_days)
        
        # 遍历每一天
        for i in range(start_idx, total_days):
            # 检测信号
            buy_signal, sell_signal, buy_price, sell_price = self.detect_signals(
                df, start_idx, i, in_position, buy_date
            )
            
            # 处理买入信号
            if buy_signal and not in_position:
                current_trade = {
                    'buy_date': df.index[i],
                    'buy_price': buy_price,
                    'sell_date': None,
                    'sell_price': None,
                    'profit': None,
                    'profit_percent': None
                }
                in_position = True
                buy_date = df.index[i]
                logger.info(f"买入信号: 日期={buy_date}, 价格={buy_price:.2f}")
            
            # 处理卖出信号
            elif sell_signal and in_position:
                current_trade['sell_date'] = df.index[i]
                current_trade['sell_price'] = sell_price
                # 计算收益
                profit = sell_price - current_trade['buy_price']
                profit_percent = (profit / current_trade['buy_price']) * 100
                current_trade['profit'] = profit
                current_trade['profit_percent'] = profit_percent
                
                trades.append(current_trade)
                current_trade = None
                in_position = False
                buy_date = None
                
                logger.info(
                    f"卖出信号: 日期={df.index[i]}, 价格={sell_price:.2f}, "
                    f"收益率={profit_percent:.2f}%"
                )
        
        # 计算统计信息
        stats = self._calculate_stats(trades)
        
        return {
            'trades': trades,
            'stats': stats
        }

    def _calculate_stats(self, trades: List[Dict]) -> Dict:
        """
        计算回测统计信息

        Args:
            trades: 交易记录列表

        Returns:
            统计信息
        """
        if not trades:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'avg_profit': 0,
                'total_profit': 0,
                'max_profit': 0,
                'max_loss': 0,
                'avg_hold_days': 0
            }
        
        # 计算基本统计
        total_trades = len(trades)
        winning_trades = len([t for t in trades if t['profit'] > 0])
        win_rate = (winning_trades / total_trades) * 100
        
        # 计算收益统计
        profits = [t['profit'] for t in trades]
        profit_percents = [t['profit_percent'] for t in trades]
        total_profit = sum(profits)
        avg_profit = sum(profit_percents) / total_trades
        max_profit = max(profit_percents)
        max_loss = min(profit_percents)
        
        # 计算平均持仓天数
        hold_days = [(t['sell_date'] - t['buy_date']).days for t in trades]
        avg_hold_days = sum(hold_days) / total_trades
        
        return {
            'total_trades': total_trades,
            'win_rate': win_rate,
            'avg_profit': avg_profit,
            'total_profit': total_profit,
            'max_profit': max_profit,
            'max_loss': max_loss,
            'avg_hold_days': avg_hold_days
        }

    def print_results(self, results: Dict):
        """
        打印回测结果

        Args:
            results: 回测结果
        """
        trades = results['trades']
        stats = results['stats']
        
        print("\n=== 布林线策略回测结果 ===")
        print(f"\n交易明细 (共{stats['total_trades']}笔):")
        print("-" * 80)
        for trade in trades:
            print(
                f"买入: {trade['buy_date'].strftime('%Y-%m-%d %H:%M:%S')} "
                f"价格: {trade['buy_price']:.2f}"
            )
            print(
                f"卖出: {trade['sell_date'].strftime('%Y-%m-%d %H:%M:%S')} "
                f"价格: {trade['sell_price']:.2f}"
            )
            print(
                f"收益: {trade['profit']:.2f} ({trade['profit_percent']:.2f}%)"
            )
            print("-" * 80)
        
        print("\n统计信息:")
        print(f"总交易次数: {stats['total_trades']}")
        print(f"胜率: {stats['win_rate']:.2f}%")
        print(f"平均收益率: {stats['avg_profit']:.2f}%")
        print(f"总收益: {stats['total_profit']:.2f}")
        print(f"最大单笔收益: {stats['max_profit']:.2f}%")
        print(f"最大单笔亏损: {stats['max_loss']:.2f}%")
        print(f"平均持仓天数: {stats['avg_hold_days']:.1f}天")

class VegasStrategy:
    """维加斯通道策略回测"""

    def __init__(
        self,
        lookback_days: int = 300,
        cooldown_days: int = 8,
        tolerance: float = 0.005,
        warmup_days: int = 169  # 添加预热期，至少等于最长的EMA周期
    ):
        """
        初始化维加斯通道策略回测器

        Args:
            lookback_days: 回测时间窗口（天）
            cooldown_days: 买入后的冷却期（天）
            tolerance: 触碰判定的容差范围
            warmup_days: 数据预热期（天），用于确保EMA计算的准确性
        """
        self.lookback_days = lookback_days
        self.cooldown_days = cooldown_days
        self.tolerance = tolerance
        self.warmup_days = warmup_days
        self.indicators = TechnicalIndicators()

    def prepare_data(self, raw_data: List[List]) -> pd.DataFrame:
        """
        准备回测数据，在全量数据上计算指标

        Args:
            raw_data: 原始K线数据

        Returns:
            处理后的DataFrame，包含技术指标
        """
        try:
            # 转换为DataFrame
            df_full = self.indicators.prepare_dataframe(raw_data)
            if df_full.empty:
                return df_full
            
            # 在全量数据上计算维加斯通道指标
            ema1, ema2, ema3 = self.indicators.calculate_vegas_tunnel(df_full)
            
            # 添加指标到DataFrame
            df_full['ema1'] = ema1  # 快线 EMA12
            df_full['ema2'] = ema2  # 中线 EMA144
            df_full['ema3'] = ema3  # 慢线 EMA169（过滤线）
            
            # 获取回测范围（包含预热期）
            total_days = len(df_full)
            start_idx = max(0, total_days - self.lookback_days - self.warmup_days)
            
            # 返回包含预热期的数据
            return df_full.iloc[start_idx:]
            
        except Exception as e:
            logger.error(f"数据准备失败: {e}")
            return pd.DataFrame()

    def detect_signals(
        self,
        df: pd.DataFrame,
        start_idx: int,
        end_idx: int,
        in_position: bool = False,
        buy_date: Optional[datetime] = None
    ) -> Tuple[bool, bool, float, float]:
        """
        检测买入和卖出信号

        Args:
            df: 数据
            start_idx: 开始位置
            end_idx: 结束位置
            in_position: 是否持仓
            buy_date: 买入日期（用于计算冷却期）

        Returns:
            (买入信号, 卖出信号, 买入价格, 卖出价格)
        """
        try:
            if df.empty:
                return False, False, 0.0, 0.0
                
            current_data = df.iloc[end_idx]
            current_date = pd.to_datetime(df.index[end_idx])
            
            # 获取当前的价格数据
            open_price = float(current_data['Open'])
            close_price = float(current_data['Close'])
            low_price = float(current_data['Low'])
            
            # 获取实体的较低价格（开盘价和收盘价中的较小值）
            body_low_price = min(open_price, close_price)
            
            # 获取通道值
            ema1_value = float(current_data['ema1'])  # 快线
            ema2_value = float(current_data['ema2'])  # 中线
            ema3_value = float(current_data['ema3'])  # 慢线（过滤线）
            
            # 初始化信号和价格
            buy_signal = False
            sell_signal = False
            buy_price = 0.0
            sell_price = 0.0
            
            # 检查是否在冷却期
            in_cooldown = False
            if in_position and buy_date:
                days_since_buy = (current_date - buy_date).days
                in_cooldown = days_since_buy < self.cooldown_days
            
            # 检测买入信号（未持仓时）
            if not in_position:
                # 检查实体低点是否触碰到通道，且价格处于上升趋势（快线在中线上方）
                if (body_low_price <= ema3_value * (1 + self.tolerance) and
                    ema1_value > ema2_value):
                    buy_signal = True
                    buy_price = body_low_price
                    logger.debug(
                        f"检测到买入信号: 实体低点={body_low_price:.2f}, "
                        f"过滤线={ema3_value:.2f}, 快线={ema1_value:.2f}, "
                        f"中线={ema2_value:.2f}"
                    )
            
            # 检测卖出信号（持仓且不在冷却期时）
            elif not in_cooldown:
                # 检查最低价是否下穿过滤线，或快线下穿中线
                if (low_price < ema3_value * (1 - self.tolerance) or
                    ema1_value < ema2_value):
                    sell_signal = True
                    sell_price = low_price
                    logger.debug(
                        f"检测到卖出信号: 最低价={low_price:.2f}, "
                        f"过滤线={ema3_value:.2f}, 快线={ema1_value:.2f}, "
                        f"中线={ema2_value:.2f}"
                    )
            
            return buy_signal, sell_signal, buy_price, sell_price
            
        except Exception as e:
            logger.error(f"信号检测失败: {e}")
            return False, False, 0.0, 0.0

    def run_backtest(self, df: pd.DataFrame) -> Dict:
        """
        运行回测

        Args:
            df: 包含技术指标的数据

        Returns:
            回测结果统计
        """
        try:
            if df.empty:
                return {'trades': [], 'stats': self._calculate_stats([])}
                
            # 初始化结果记录
            trades = []
            current_trade = None
            in_position = False
            buy_date = None
            
            # 获取回测范围
            total_days = len(df)
            start_idx = max(0, total_days - self.lookback_days)
            
            # 遍历每一天
            for i in range(start_idx, total_days):
                # 检测信号
                buy_signal, sell_signal, buy_price, sell_price = self.detect_signals(
                    df, start_idx, i, in_position, buy_date
                )
                
                # 处理买入信号
                if buy_signal and not in_position:
                    buy_date = pd.to_datetime(df.index[i])
                    current_trade = {
                        'buy_date': buy_date,
                        'buy_price': buy_price,
                        'sell_date': None,
                        'sell_price': None,
                        'profit': None,
                        'profit_percent': None
                    }
                    in_position = True
                    logger.info(f"买入信号: 日期={buy_date}, 价格={buy_price:.2f}")
                
                # 处理卖出信号
                elif sell_signal and in_position and current_trade:
                    sell_date = pd.to_datetime(df.index[i])
                    current_trade['sell_date'] = sell_date
                    current_trade['sell_price'] = sell_price
                    # 计算收益
                    profit = sell_price - current_trade['buy_price']
                    profit_percent = (profit / current_trade['buy_price']) * 100
                    current_trade['profit'] = profit
                    current_trade['profit_percent'] = profit_percent
                    
                    trades.append(current_trade)
                    current_trade = None
                    in_position = False
                    buy_date = None
                    
                    logger.info(
                        f"卖出信号: 日期={sell_date}, 价格={sell_price:.2f}, "
                        f"收益率={profit_percent:.2f}%"
                    )
            
            # 计算统计信息
            stats = self._calculate_stats(trades)
            
            return {
                'trades': trades,
                'stats': stats
            }
            
        except Exception as e:
            logger.error(f"回测执行失败: {e}")
            return {'trades': [], 'stats': self._calculate_stats([])}

    def _calculate_stats(self, trades: List[Dict]) -> Dict:
        """
        计算回测统计信息

        Args:
            trades: 交易记录列表

        Returns:
            统计信息
        """
        if not trades:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'avg_profit': 0,
                'total_profit': 0,
                'max_profit': 0,
                'max_loss': 0,
                'avg_hold_days': 0
            }
        
        try:
            # 计算基本统计
            total_trades = len(trades)
            winning_trades = len([t for t in trades if t['profit'] > 0])
            win_rate = (winning_trades / total_trades) * 100
            
            # 计算收益统计
            profits = [t['profit'] for t in trades]
            profit_percents = [t['profit_percent'] for t in trades]
            total_profit = sum(profits)
            avg_profit = sum(profit_percents) / total_trades
            max_profit = max(profit_percents)
            max_loss = min(profit_percents)
            
            # 计算平均持仓天数
            hold_days = [(t['sell_date'] - t['buy_date']).days for t in trades]
            avg_hold_days = sum(hold_days) / total_trades
            
            return {
                'total_trades': total_trades,
                'win_rate': win_rate,
                'avg_profit': avg_profit,
                'total_profit': total_profit,
                'max_profit': max_profit,
                'max_loss': max_loss,
                'avg_hold_days': avg_hold_days
            }
            
        except Exception as e:
            logger.error(f"统计计算失败: {e}")
            return {
                'total_trades': len(trades),
                'win_rate': 0,
                'avg_profit': 0,
                'total_profit': 0,
                'max_profit': 0,
                'max_loss': 0,
                'avg_hold_days': 0
            }

    def print_results(self, results: Dict):
        """
        打印回测结果

        Args:
            results: 回测结果
        """
        trades = results['trades']
        stats = results['stats']
        
        print("\n=== 维加斯通道策略回测结果 ===")
        print(f"\n交易明细 (共{stats['total_trades']}笔):")
        print("-" * 80)
        for trade in trades:
            print(
                f"买入: {trade['buy_date'].strftime('%Y-%m-%d %H:%M:%S')} "
                f"价格: {trade['buy_price']:.2f}"
            )
            print(
                f"卖出: {trade['sell_date'].strftime('%Y-%m-%d %H:%M:%S')} "
                f"价格: {trade['sell_price']:.2f}"
            )
            print(
                f"收益: {trade['profit']:.2f} ({trade['profit_percent']:.2f}%)"
            )
            print("-" * 80)
        
        print("\n统计信息:")
        print(f"总交易次数: {stats['total_trades']}")
        print(f"胜率: {stats['win_rate']:.2f}%")
        print(f"平均收益率: {stats['avg_profit']:.2f}%")
        print(f"总收益: {stats['total_profit']:.2f}")
        print(f"最大单笔收益: {stats['max_profit']:.2f}%")
        print(f"最大单笔亏损: {stats['max_loss']:.2f}%")
        print(f"平均持仓天数: {stats['avg_hold_days']:.1f}天") 