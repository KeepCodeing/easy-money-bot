#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
图表绘制模块 (支持分面板信号绘制)
"""

import os
import sys
import logging
from typing import List, Dict, Optional, Any

import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

from config import settings
from src.utils.file_utils import clean_filename
from .indicators import TechnicalIndicators, IndicatorType

# --- 日志和字体配置 (保持不变) ---
logger = logging.getLogger(__name__)

try:
    if sys.platform == 'win32':
        font_path = r"C:\Windows\Fonts\msyh.ttc"
        font = FontProperties(fname=font_path) if os.path.exists(font_path) else None
    else:
        font = None
except Exception:
    font = None

plt.rcParams['font.family'] = [font.get_name() if font else 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False

class KLineChart:
    """
    一个纯粹的K线图绘制器，支持在主图和副图上绘制不同策略的信号。
    """
    def __init__(self, days_to_show: int = 90, save_dir: Optional[str] = None):
        # ... (__init__, _create_chart_style, _prepare_dataframe 方法保持不变) ...
        self.days_to_show = days_to_show
        self.charts_dir = save_dir or os.path.join(settings.DATA_DIR, "charts")
        if not os.path.exists(self.charts_dir):
            os.makedirs(self.charts_dir)
        self.chart_style = self._create_chart_style()
        self.indicators_calculator = TechnicalIndicators()

    def _create_chart_style(self):
        return mpf.make_mpf_style(
            base_mpf_style="charles", gridstyle=":", y_on_right=False,
            marketcolors=mpf.make_marketcolors(
                up="red", down="green", edge="inherit", wick="inherit",
                volume={"up": "red", "down": "green"},
            ),
            rc={"font.family": plt.rcParams['font.family'], "axes.labelsize": 10,
                "xtick.labelsize": 8, "ytick.labelsize": 8},
        )

    def _prepare_dataframe(self, raw_kline_data: List[list]) -> pd.DataFrame:
        if not raw_kline_data: return pd.DataFrame()
        df = pd.DataFrame(raw_kline_data, columns=['Time', 'Open', 'Close', 'High', 'Low', 'Volume', 'Amount'])
        df['Time'] = pd.to_datetime(df['Time'].astype(int), unit='s')
        df.set_index('Time', inplace=True)
        numeric_cols = ['Open', 'Close', 'High', 'Low', 'Volume', 'Amount']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        df.sort_index(inplace=True)
        return df

    def plot_candlestick(
        self,
        item_id: str,
        item_name: str,
        raw_kline_data: List[list],
        indicator_type: IndicatorType = IndicatorType.ALL,
        signals_to_plot: Optional[List[Dict]] = None
    ) -> Optional[str]:
        """
        绘制K线图，并根据策略类型在相应面板上标注信号。
        """
        if not raw_kline_data:
            logger.warning(f"商品 {item_name} ({item_id}) 没有数据，无法绘制。")
            return None

        # --- 1. 数据和指标准备 ---
        df_full = self._prepare_dataframe(raw_kline_data)
        if df_full.empty: return None
        df = df_full.tail(self.days_to_show)

        addplots = []
        # 主图指标
        if indicator_type in [IndicatorType.BOLL, IndicatorType.ALL]:
            middle, upper, lower = self.indicators_calculator.calculate_bollinger_bands(df)
            addplots.extend([
                mpf.make_addplot(middle, color='yellow', linestyle='--'),
                mpf.make_addplot(upper, color='red', linestyle='--'),
                mpf.make_addplot(lower, color='green', linestyle='--'),
            ])
        if indicator_type in [IndicatorType.VEGAS, IndicatorType.ALL]:
            # ... Vegas, CsMa 等均线指标绘制 ...
            pass
            
        # 副图指标
        vol_ma1, vol_ma2, vol_ma3 = self.indicators_calculator.calculate_volume_ma(df)
        addplots.extend([
            mpf.make_addplot(vol_ma1, panel=1, color='blue', alpha=0.7),
            mpf.make_addplot(vol_ma2, panel=1, color='orange', alpha=0.7),
            mpf.make_addplot(vol_ma3, panel=1, color='purple', alpha=0.7),
        ])
        rsi = self.indicators_calculator.calculate_rsi(df)
        addplots.append(mpf.make_addplot(rsi, panel=2, color='orange', ylabel='RSI'))
        addplots.append(mpf.make_addplot(pd.Series(70, index=df.index), panel=2, color='r', linestyle=':'))
        addplots.append(mpf.make_addplot(pd.Series(30, index=df.index), panel=2, color='g', linestyle=':'))
        macd_line, signal_line, histogram = self.indicators_calculator.calculate_macd(df)
        colors = ['green' if v >= 0 else 'red' for v in histogram]
        addplots.append(mpf.make_addplot(histogram, panel=3, type='bar', color=colors, ylabel='MACD'))
        addplots.append(mpf.make_addplot(macd_line, panel=3, color='blue'))
        addplots.append(mpf.make_addplot(signal_line, panel=3, color='orange'))

        # --- 2. 绘制图表 ---
        chart_title = f"{item_name} ({len(df)}天)"
        panel_ratios = (6, 2, 2, 2)
        fig, axes = mpf.plot(
            df, type="candle", style=self.chart_style, volume=True,
            addplot=addplots, returnfig=True, figsize=(16, 10),
            panel_ratios=panel_ratios, datetime_format="%m/%d", title=f"\n{chart_title}"
        )

        # --- 3. 智能绘制信号 ---
        if signals_to_plot:
            self._plot_signals_on_axes(df, signals_to_plot, axes)

        # --- 4. 保存图表 ---
        try:
            safe_title = clean_filename(item_name)
            file_name = f"{safe_title}_{item_id}.png"
            save_path = os.path.join(self.charts_dir, file_name)
            fig.savefig(save_path, dpi=200, bbox_inches="tight")
            logger.info(f"K线图已保存至: {save_path}")
            plt.close(fig)
            return save_path
        except Exception as e:
            logger.error(f"保存图表失败: {e}")
            plt.close(fig)
            return None

    def _plot_signals_on_axes(self, df: pd.DataFrame, signals: List[Dict], axes: List[plt.Axes]):
        """
        辅助函数：根据策略类型将信号绘制到正确的面板上。
        """
        logger.info(f"开始在图表上智能绘制 {len(signals)} 个信号点...")
        
        # 定义策略与面板的映射关系
        # Key: 策略名中包含的关键字, Value: 对应的面板索引 (axes index)
        strategy_panel_map = {
            'RSI': 2,       # RSI 信号绘制在 panel 2 (axes[2])
            'MACD': 3,      # MACD 信号绘制在 panel 3 (axes[4] - 因为vol副图占了axes[1], mplfinance的axes索引比较特殊)
            'Bollinger': 0, # 布林带信号绘制在主图 (axes[0])
            'Vegas': 0,
            'CsMa': 0
        }
        
        # mplfinance的axes索引比较特殊,副图从偶数位开始: 0=主图, 2=Panel1(vol), 4=Panel2(rsi), 6=Panel3(macd)
        # 我们需要一个转换
        panel_to_ax_map = {0: axes[0], 1: axes[2], 2: axes[4], 3: axes[6]}

        for signal in signals:
            try:
                signal_date = pd.to_datetime(signal['timestamp'])
                if signal_date not in df.index:
                    continue # 如果信号不在当前显示范围，则跳过

                date_idx = df.index.get_loc(signal_date)
                signal_type = signal['type'].upper()
                strategy_name = signal['strategy']

                # 确定信号应绘制在哪个面板
                panel_idx = 0 # 默认为主图
                for key, idx in strategy_panel_map.items():
                    if key.lower() in strategy_name.lower():
                        panel_idx = idx
                        break
                
                ax = panel_to_ax_map.get(panel_idx)
                if not ax:
                    logger.warning(f"找不到策略 '{strategy_name}' 对应的绘图面板。")
                    continue
                
                # 确定信号的Y轴坐标
                y_coord = 0
                if panel_idx == 0: # 主图信号
                    y_coord = signal['price']
                elif panel_idx == 2: # RSI
                    y_coord = signal['details']['rsi_value']
                elif panel_idx == 3: # MACD
                    y_coord = signal['details']['macd_line']

                # 绘制标记
                marker_color = 'red' if signal_type == 'BUY' else 'green'
                marker_shape = '^' if signal_type == 'BUY' else 'v'
                
                ax.scatter(
                    date_idx, y_coord, color=marker_color, marker=marker_shape,
                    s=120, edgecolors='white', zorder=10
                )

            except Exception as e:
                logger.warning(f"绘制信号点失败: {signal}, 错误: {e}")