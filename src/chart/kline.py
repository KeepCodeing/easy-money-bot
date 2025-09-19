#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
图表绘制模块 (重构版)
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
    一个纯粹的K线图绘制器。
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
        indicator_type: IndicatorType = IndicatorType.BOLL,
        signals_to_plot: Optional[List[Dict]] = None
    ) -> Optional[str]:
        if not raw_kline_data:
            logger.warning(f"商品 {item_name} ({item_id}) 没有数据，无法绘制K线图。")
            return None

        df_full = self._prepare_dataframe(raw_kline_data)
        if df_full.empty: return None
        df = df_full.tail(self.days_to_show)

        addplots = []
        # --- 主图指标 ---
        if indicator_type in [IndicatorType.BOLL, IndicatorType.ALL]:
            middle, upper, lower = self.indicators_calculator.calculate_bollinger_bands(df)
            addplots.extend([
                mpf.make_addplot(middle, color='yellow', linestyle='--'),
                mpf.make_addplot(upper, color='red', linestyle='--'),
                mpf.make_addplot(lower, color='green', linestyle='--'),
            ])
        if indicator_type in [IndicatorType.VEGAS, IndicatorType.ALL]:
            ema1, ema2, ema3 = self.indicators_calculator.calculate_vegas_tunnel(df)
            addplots.extend([
                mpf.make_addplot(ema1, color='blue'),
                mpf.make_addplot(ema2, color='magenta'),
                mpf.make_addplot(ema3, color='cyan'),
            ])
            
        # --- 副图指标 ---
        # Panel 1: 成交量MA
        vol_ma1, vol_ma2, vol_ma3 = self.indicators_calculator.calculate_volume_ma(df)
        addplots.extend([
            mpf.make_addplot(vol_ma1, panel=1, color='blue', alpha=0.7),
            mpf.make_addplot(vol_ma2, panel=1, color='orange', alpha=0.7),
            mpf.make_addplot(vol_ma3, panel=1, color='purple', alpha=0.7),
        ])

        # (新增) Panel 2: RSI
        rsi = self.indicators_calculator.calculate_rsi(df)
        if not rsi.empty:
            addplots.append(mpf.make_addplot(rsi, panel=2, color='orange', ylabel='RSI'))
            # 添加超买超卖线
            addplots.append(mpf.make_addplot(pd.Series(70, index=df.index), panel=2, color='r', linestyle=':'))
            addplots.append(mpf.make_addplot(pd.Series(30, index=df.index), panel=2, color='g', linestyle=':'))

        # (新增) Panel 3: MACD
        macd_line, signal_line, histogram = self.indicators_calculator.calculate_macd(df)
        if not macd_line.empty:
            colors = ['green' if v >= 0 else 'red' for v in histogram]
            addplots.append(mpf.make_addplot(histogram, panel=3, type='bar', color=colors, ylabel='MACD'))
            addplots.append(mpf.make_addplot(macd_line, panel=3, color='blue'))
            addplots.append(mpf.make_addplot(signal_line, panel=3, color='orange'))

        # 绘制图表
        title = f"{item_name} ({self.days_to_show}天)"
        panel_ratios = (6, 2, 2, 2)  # 调整面板比例以容纳新图表

        fig, axes = mpf.plot(
            df,
            type="candle",
            style=self.chart_style,
            volume=True,
            addplot=addplots,
            returnfig=True,
            figsize=(16, 10), # 增加图表高度
            panel_ratios=panel_ratios,
            datetime_format="%m/%d",
            title=f"\n{title}",
        )

        # 标注信号点... (保持不变)
        if signals_to_plot:
            # ...
            pass

        # 保存图表
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