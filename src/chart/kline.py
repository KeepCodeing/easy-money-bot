#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
图表绘制模块 (已修复指标计算问题并支持分面板信号绘制)
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
from src.analysis.indicators import TechnicalIndicators, IndicatorType

# --- 日志和字体配置 ---
logger = logging.getLogger(__name__)

try:
    if sys.platform == 'win32':
        font_path = r"C:\\Windows\\Fonts\\msyh.ttc"
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

    def plot_candlestick(
        self,
        item_id: str,
        item_name: str,
        raw_kline_data: List[list],
        indicator_type: IndicatorType = IndicatorType.ALL,
        signals_to_plot: Optional[List[Dict]] = None
    ) -> Optional[str]:
        if not raw_kline_data:
            logger.warning(f"商品 {item_name} ({item_id}) 没有数据，无法绘制。")
            return None

        # --- 1. 数据准备 ---
        df_full = self._prepare_dataframe(raw_kline_data)
        if df_full.empty: return None

        # --- 2. 核心修复：在全量数据上计算所有指标 ---
        logger.debug(f"在 {len(df_full)} 条完整数据上计算指标...")
        
        # 主图指标
        middle_full, upper_full, lower_full = self.indicators_calculator.calculate_bollinger_bands(df_full)
        vegas_ema1, vegas_ema2, vegas_ema3 = self.indicators_calculator.calculate_vegas_tunnel(df_full)
        
        # 副图指标
        vol_ma1_full, vol_ma2_full, vol_ma3_full = self.indicators_calculator.calculate_volume_ma(df_full)
        rsi_full = self.indicators_calculator.calculate_rsi(df_full)
        macd_line_full, signal_line_full, histogram_full = self.indicators_calculator.calculate_macd(df_full)
        
        # --- 3. 截取用于显示的数据 ---
        df = df_full.tail(self.days_to_show)
        logger.debug(f"截取最近 {len(df)} 天的数据用于显示。")

        # --- 4. 准备 addplots，并从全量指标中截取对应部分 ---
        addplots = []
        if indicator_type in [IndicatorType.BOLL, IndicatorType.ALL]:
            addplots.extend([
                mpf.make_addplot(middle_full[df.index], color='yellow', linestyle='--'),
                mpf.make_addplot(upper_full[df.index], color='red', linestyle='--'),
                mpf.make_addplot(lower_full[df.index], color='green', linestyle='--'),
            ])
            
        if indicator_type in [IndicatorType.VEGAS, IndicatorType.ALL]:
            addplots.extend([
                mpf.make_addplot(vegas_ema1[df.index], color='red', linestyle='-'),
                mpf.make_addplot(vegas_ema2[df.index], color='blue', linestyle='-'),
                mpf.make_addplot(vegas_ema3[df.index], color='green', linestyle='-'),
            ])
        
        # Panel 1: 成交量MA
        addplots.extend([
            mpf.make_addplot(vol_ma1_full[df.index], panel=1, color='blue', alpha=0.7),
            mpf.make_addplot(vol_ma2_full[df.index], panel=1, color='orange', alpha=0.7),
            mpf.make_addplot(vol_ma3_full[df.index], panel=1, color='purple', alpha=0.7),
        ])
        # Panel 2: RSI
        addplots.append(mpf.make_addplot(rsi_full[df.index], panel=2, color='orange', ylabel='RSI'))
        addplots.append(mpf.make_addplot(pd.Series(70, index=df.index), panel=2, color='r', linestyle=':'))
        addplots.append(mpf.make_addplot(pd.Series(30, index=df.index), panel=2, color='g', linestyle=':'))
        # Panel 3: MACD
        colors = ['green' if v >= 0 else 'red' for v in histogram_full[df.index]]
        addplots.append(mpf.make_addplot(histogram_full[df.index], panel=3, type='bar', color=colors, ylabel='MACD'))
        addplots.append(mpf.make_addplot(macd_line_full[df.index], panel=3, color='blue'))
        addplots.append(mpf.make_addplot(signal_line_full[df.index], panel=3, color='orange'))

        # --- 5. 绘制图表 ---
        chart_title = f"{item_name} ({len(df)}天)"
        panel_ratios = (6, 2, 2, 2)
        fig, axes = mpf.plot(
            df, type="candle", style=self.chart_style, volume=True,
            addplot=addplots, returnfig=True, figsize=(16, 10),
            panel_ratios=panel_ratios, datetime_format="%m/%d", title=f"\n{chart_title}"
        )

        # 6. 智能绘制信号
        if signals_to_plot:
            self._plot_signals_on_axes(df, signals_to_plot, axes)

        # 7. 保存图表
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
        # ... (此方法无需修改，保持原样) ...
        logger.info(f"开始在图表上智能绘制 {len(signals)} 个信号点...")
        strategy_panel_map = {'RSI': 2, 'MACD': 3, 'Bollinger': 0, 'Vegas': 0, 'CsMa': 0}
        panel_to_ax_map = {0: axes[0], 1: axes[2], 2: axes[4], 3: axes[6]}

        for signal in signals:
            try:
                signal_date = pd.to_datetime(signal['timestamp'])
                if signal_date not in df.index:
                    continue

                date_idx = df.index.get_loc(signal_date)
                signal_type = signal['type'].upper()
                strategy_name = signal['strategy']
                
                panel_idx = 0
                for key, idx in strategy_panel_map.items():
                    if key.lower() in strategy_name.lower():
                        panel_idx = idx
                        break
                
                ax = panel_to_ax_map.get(panel_idx)
                if not ax: continue
                
                y_coord = 0
                if panel_idx == 0:
                    y_coord = signal['price']
                elif panel_idx == 2 and 'rsi_value' in signal['details']:
                    y_coord = signal['details']['rsi_value']
                elif panel_idx == 3 and 'macd_line' in signal['details']:
                    y_coord = signal['details']['macd_line']

                marker_color = 'red' if signal_type == 'BUY' else 'green'
                marker_shape = '^' if signal_type == 'BUY' else 'v'
                
                ax.scatter(
                    date_idx, y_coord, color=marker_color, marker=marker_shape,
                    s=120, edgecolors='white', zorder=10
                )
            except Exception as e:
                logger.warning(f"绘制信号点失败: {signal}, 错误: {e}")