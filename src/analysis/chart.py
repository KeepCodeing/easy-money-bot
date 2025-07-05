#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
图表绘制模块
"""

import os
import logging
from typing import List, Dict, Optional, Any

import pandas as pd
import mplfinance as mpf
from config import settings
from .indicators import TechnicalIndicators, IndicatorType

logger = logging.getLogger(__name__)


class KLineChart:
    """K线图绘制类"""

    def __init__(self, days_to_show: int = 30):
        """
        初始化K线图绘制器

        Args:
            days_to_show: 显示最近多少天的数据
        """
        self.days_to_show = days_to_show
        self.charts_dir = os.path.join(settings.DATA_DIR, "charts")
        if not os.path.exists(self.charts_dir):
            os.makedirs(self.charts_dir)

        # 设置图表样式
        self.chart_style = mpf.make_mpf_style(
            base_mpf_style="charles",
            gridstyle=":",
            y_on_right=False,
            marketcolors=mpf.make_marketcolors(
                up="red",
                down="green",
                edge="inherit",
                wick="inherit",
                volume={"up": "red", "down": "green"},
                ohlc="inherit",
            ),
            rc={
                "axes.labelsize": 10,
                "axes.titlesize": 12,
                "xtick.labelsize": 8,
                "ytick.labelsize": 8,
                "grid.linestyle": ":",
                "grid.alpha": 0.3,
            },
        )

        # 初始化技术指标
        self.indicators = TechnicalIndicators()

    def _find_bollinger_touches(
        self, df: pd.DataFrame, upper: pd.Series, lower: pd.Series
    ) -> List[Dict]:
        """
        查找触碰布林线的点，并返回对应时间点的价格
        - 上轨：使用最高价(High)检测和显示
        - 下轨：使用实体(Close/Open)检测和显示，不使用下影线
        对于多个触碰点，只返回最新的一个

        Args:
            df: K线数据
            upper: 布林线上轨
            lower: 布林线下轨

        Returns:
            触碰点列表，每个点包含：
            - index: 时间索引
            - price: 最高价或收盘价/开盘价
            - position: 'upper' 或 'lower'
        """
        # 分别存储上下轨的触碰点
        upper_touches = []
        lower_touches = []
        
        # 定义容差范围（3%）
        tolerance = 0.03
        
        logger.debug(f"开始检测触碰点，数据长度：{len(df)}，布林线上轨长度：{len(upper)}，布林线下轨长度：{len(lower)}")
        
        for idx in df.index:
            high_price = df.loc[idx, "High"]
            open_price = df.loc[idx, "Open"]
            close_price = df.loc[idx, "Close"]
            upper_band = upper[idx]
            lower_band = lower[idx]
            
            # 获取实体的较低价格（开盘价和收盘价中的较小值）
            body_low_price = min(open_price, close_price)
            
            logger.debug(f"检查日期 {idx}:")
            logger.debug(f"  最高价：{high_price:.2f}, 布林上轨：{upper_band:.2f}")
            logger.debug(f"  实体低点：{body_low_price:.2f}, 布林下轨：{lower_band:.2f}")
            
            # 检查上轨（保持不变，使用最高价）
            upper_threshold = upper_band * (1 - tolerance)
            if high_price >= upper_threshold:
                upper_touches.append(
                    {"index": idx, "price": high_price, "position": "upper"}
                )
                logger.debug(f"检测到上轨触碰点: 日期={idx}, 最高价={high_price:.2f}, 布林上轨={upper_band:.2f}")
            
            # 检查下轨（只使用实体价格）
            lower_threshold = lower_band * (1 + tolerance)
            if body_low_price <= lower_threshold:
                lower_touches.append(
                    {"index": idx, "price": body_low_price, "position": "lower"}
                )
                logger.debug(f"检测到下轨触碰点: 日期={idx}, 实体低点={body_low_price:.2f}, 布林下轨={lower_band:.2f}")
        
        # 只保留最新的触碰点
        touches = []
        if upper_touches:
            latest_upper = upper_touches[-1]  # 取最后一个（最新的）上轨触碰点
            touches.append(latest_upper)
            logger.info(f"选择最新上轨触碰点: 日期={latest_upper['index']}, 价格={latest_upper['price']:.2f}")
            
        if lower_touches:
            latest_lower = lower_touches[-1]  # 取最后一个（最新的）下轨触碰点
            touches.append(latest_lower)
            logger.info(f"选择最新下轨触碰点: 日期={latest_lower['index']}, 价格={latest_lower['price']:.2f}")
        
        logger.info(f"触碰点检测完成，保留 {len(touches)} 个最新触碰点")
        return touches

    def _find_vegas_touches(
        self, df: pd.DataFrame, ema1: pd.Series, ema2: pd.Series, ema3: pd.Series
    ) -> List[Dict]:
        """
        查找触碰Vegas通道的点，并返回对应时间点的价格
        - 买入信号：K线下轨（实体低点）触碰到通道
        - 卖出信号：K线底部下穿过滤线

        Args:
            df: K线数据
            ema1: 快速EMA（上轨）
            ema2: 中速EMA（中轨）
            ema3: 慢速EMA（下轨/过滤线）

        Returns:
            触碰点列表，每个点包含：
            - index: 时间索引
            - price: 价格
            - signal: 'buy' 或 'sell'
        """
        # 分别存储买入和卖出信号
        buy_signals = []
        sell_signals = []
        
        # 定义容差范围（0.5%）
        tolerance = 0.005
        
        logger.debug(f"开始检测Vegas通道触碰点，数据长度：{len(df)}")
        
        for idx in df.index:
            open_price = df.loc[idx, "Open"]
            close_price = df.loc[idx, "Close"]
            low_price = df.loc[idx, "Low"]
            
            # 获取实体的较低价格（开盘价和收盘价中的较小值）
            body_low_price = min(open_price, close_price)
            
            # 获取当前的通道值
            filter_line = ema3[idx]  # 过滤线
            
            # 检查买入信号（实体低点触碰通道）
            if body_low_price <= filter_line * (1 + tolerance):
                buy_signals.append({
                    "index": idx,
                    "price": body_low_price,
                    "signal": "buy"
                })
                logger.debug(f"检测到买入信号: 日期={idx}, 价格={body_low_price:.2f}, 过滤线={filter_line:.2f}")
            
            # 检查卖出信号（最低价下穿过滤线）
            if low_price < filter_line * (1 - tolerance):
                sell_signals.append({
                    "index": idx,
                    "price": low_price,
                    "signal": "sell"
                })
                logger.debug(f"检测到卖出信号: 日期={idx}, 价格={low_price:.2f}, 过滤线={filter_line:.2f}")
        
        # 只保留最新的信号
        signals = []
        if buy_signals:
            latest_buy = buy_signals[-1]
            signals.append(latest_buy)
            logger.info(f"选择最新买入信号: 日期={latest_buy['index']}, 价格={latest_buy['price']:.2f}")
            
        if sell_signals:
            latest_sell = sell_signals[-1]
            signals.append(latest_sell)
            logger.info(f"选择最新卖出信号: 日期={latest_sell['index']}, 价格={latest_sell['price']:.2f}")
        
        logger.info(f"Vegas通道触碰点检测完成，保留 {len(signals)} 个最新信号")
        return signals

    def _filter_date_range(self, df: pd.DataFrame, start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
        """
        按日期范围筛选数据

        Args:
            df: 原始DataFrame
            start_date: 开始日期，格式：YYYY-MM-DD
            end_date: 结束日期，格式：YYYY-MM-DD

        Returns:
            筛选后的DataFrame
        """
        try:
            filtered_df = df.copy()
            if start_date:
                filtered_df = filtered_df[filtered_df.index >= pd.to_datetime(start_date)]
            if end_date:
                filtered_df = filtered_df[filtered_df.index <= pd.to_datetime(end_date)]
            return filtered_df
        except Exception as e:
            logger.error(f"按日期范围筛选数据时出错: {e}")
            return df

    def plot_candlestick(
        self,
        item_id: str,
        raw_data: List[List],
        title: Optional[str] = None,
        indicator_type: IndicatorType = IndicatorType.ALL,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Any:
        """
        绘制K线图

        Args:
            item_id: 商品ID
            raw_data: 原始K线数据
            title: 图表标题，默认为"Kline Chart of {item_id}"
            indicator_type: 要显示的指标类型
            start_date: 开始日期，格式：YYYY-MM-DD
            end_date: 结束日期，格式：YYYY-MM-DD

        Returns:
            matplotlib figure 对象
        """
        if not raw_data:
            logger.warning(f"商品 {item_id} 没有数据，无法绘制K线图")
            return None

        # 转换数据格式
        df_full = self.indicators.prepare_dataframe(raw_data)

        # 在全量数据上计算技术指标
        middle, upper, lower = self.indicators.calculate_bollinger_bands(df_full)
        ema1, ema2, ema3 = self.indicators.calculate_vegas_tunnel(df_full)

        # 按日期范围筛选数据
        if start_date or end_date:
            df = self._filter_date_range(df_full, start_date, end_date)
        else:
            df = self._filter_recent_data(df_full)

        if len(df) == 0:
            logger.warning(f"商品 {item_id} 筛选后没有数据，无法绘制K线图")
            return None

        # 设置图表标题
        if title is None:
            if start_date and end_date:
                title = f"Kline Chart of {item_id} ({start_date} to {end_date})"
            elif start_date:
                title = f"Kline Chart of {item_id} (from {start_date})"
            elif end_date:
                title = f"Kline Chart of {item_id} (until {end_date})"
            else:
                title = f"Kline Chart of {item_id} (Last {self.days_to_show} days)"

        # 准备技术指标数据（确保与显示数据长度匹配）
        addplots = []
        if indicator_type in [IndicatorType.BOLL, IndicatorType.ALL]:
            # 添加布林带（使用与df相同的时间范围）
            middle = middle[df.index]
            upper = upper[df.index]
            lower = lower[df.index]
            addplots.extend(
                [
                    mpf.make_addplot(
                        middle,
                        color="yellow",
                        linestyle="-",
                        width=1,
                        alpha=0.7,
                        secondary_y=False,
                    ),
                    mpf.make_addplot(
                        upper,
                        color="red",
                        linestyle="-",
                        width=1,
                        alpha=0.7,
                        secondary_y=False,
                    ),
                    mpf.make_addplot(
                        lower,
                        color="green",
                        linestyle="-",
                        width=1,
                        alpha=0.7,
                        secondary_y=False,
                    ),
                ]
            )

        if indicator_type in [IndicatorType.VEGAS, IndicatorType.ALL]:
            # 添加维加斯通道（使用与df相同的时间范围）
            ema1 = ema1[df.index]
            ema2 = ema2[df.index]
            ema3 = ema3[df.index]
            addplots.extend(
                [
                    mpf.make_addplot(
                        ema1, color="blue", width=1, alpha=0.7, secondary_y=False
                    ),
                    mpf.make_addplot(
                        ema2, color="magenta", width=1, alpha=0.7, secondary_y=False
                    ),
                    mpf.make_addplot(
                        ema3, color="cyan", width=1, alpha=0.7, secondary_y=False
                    ),
                ]
            )

        # 创建子图，为技术指标预留空间
        fig, axes = mpf.plot(
            df,
            type="candle",
            style=self.chart_style,
            volume=True,
            volume_alpha=0.5,
            figsize=(12, 8),
            panel_ratios=(5, 1),  # 调整主图和成交量图的比例为5:1
            addplot=addplots,
            returnfig=True,
            tight_layout=False,  # 关闭自动布局以手动调整标题
            show_nontrading=False,
            datetime_format="%m/%d",  # 设置日期格式为MM/DD
        )

        # 获取主图对象
        ax = axes[0]

        # 添加标注
        if indicator_type in [IndicatorType.VEGAS, IndicatorType.ALL]:
            # 添加Vegas通道触碰点标注
            # 获取y轴范围
            y_min, y_max = ax.get_ylim()
            y_range = y_max - y_min
            
            # 查找触碰点
            touches = self._find_vegas_touches(df, ema1, ema2, ema3)
            logger.info(f"准备添加 {len(touches)} 个Vegas通道信号标注")

            for touch in touches:
                idx = touch["index"]
                price = touch["price"]
                signal = touch["signal"]
                
                # 获取x轴位置
                x_pos = df.index.get_loc(idx)
                
                # 根据信号类型调整标注位置和样式
                if signal == "buy":
                    y_offset = -y_range * 0.02  # 下方偏移2%
                    va = "top"
                    text = f"{price:,.0f}"  # 只显示价格
                else:
                    y_offset = -y_range * 0.02  # 下方偏移2%
                    va = "top"
                    text = f"{price:,.0f}"  # 只显示价格
                
                # 添加价格标注
                ax.annotate(
                    text,
                    xy=(x_pos, price),
                    xytext=(x_pos, price + y_offset),
                    fontsize=8,
                    color="black",
                    va=va,
                    ha="center",
                    bbox=None,  # 移除背景框
                    arrowprops=dict(
                        arrowstyle="->",
                        color="black",
                        alpha=0.6,
                        connectionstyle="arc3,rad=0"
                    ),
                    zorder=100
                )

        # 设置标题
        fig.suptitle(
            title,
            y=0.95,  # 调整标题位置
            fontsize=12,
            fontweight="bold"
        )

        # 调整布局
        fig.subplots_adjust(
            top=0.90,      # 为标题留出空间
            bottom=0.1,    # 底部边距
            right=0.95,    # 右边距
            left=0.1,      # 左边距
            hspace=0.1     # 子图间距
        )

        # 保存图表
        save_path = os.path.join(self.charts_dir, f"{item_id}_candlestick.png")
        fig.savefig(save_path, dpi=300, bbox_inches="tight")
        logger.info(f"K线图已保存至: {save_path}")

        return fig

    def _filter_recent_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        筛选最近N天的数据

        Args:
            df: 原始DataFrame

        Returns:
            筛选后的DataFrame
        """
        if len(df) <= self.days_to_show:
            return df

        # 由于在prepare_dataframe中已经按时间排序，直接取最后N天数据即可
        return df.tail(self.days_to_show)


# 使用示例
if __name__ == "__main__":
    # 示例数据
    sample_data = {
        "525873303": [
            ["1743782400", 47388.0, 47495.0, 47750.0, 47000.0, 7, 331881.0],
            ["1743868800", 47495.0, 48000.0, 48000.0, 46900.0, 25, 1187979.5],
            ["1743955200", 48000.0, 47500.0, 48500.0, 47500.0, 15, 714750.0],
            ["1744041600", 47500.0, 47800.0, 48000.0, 47200.0, 10, 478000.0],
            ["1744128000", 47800.0, 48200.0, 48500.0, 47500.0, 12, 574800.0],
        ]
    }

    # 创建K线图显示类
    chart = KLineChart(days_to_show=30)

    # 绘制K线图
    fig = chart.plot_candlestick("525873303", sample_data["525873303"])
    print(f"K线图已绘制")
