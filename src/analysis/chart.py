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
        - 下轨：使用实体(Close/Open)检测和显示
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
        
        # 定义容差范围（0.5%）
        tolerance = 0.005
        
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
            
            # 检查下轨（改用实体价格）
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

    def plot_candlestick(
        self,
        item_id: str,
        raw_data: List[List],
        title: Optional[str] = None,
        indicator_type: IndicatorType = IndicatorType.ALL,
    ) -> Any:
        """
        绘制K线图

        Args:
            item_id: 商品ID
            raw_data: 原始K线数据
            title: 图表标题，默认为"Kline Chart of {item_id}"
            indicator_type: 要显示的指标类型

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

        # 筛选最近N天的数据
        df = self._filter_recent_data(df_full)

        if len(df) == 0:
            logger.warning(f"商品 {item_id} 筛选后没有数据，无法绘制K线图")
            return None

        # 设置图表标题
        if title is None:
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

        # 添加触碰点价格标注
        if indicator_type in [IndicatorType.BOLL, IndicatorType.ALL]:
            logger.debug("开始添加布林线触碰点标注")
            ax = axes[0]
            
            # 在添加标注之前先检查数据
            logger.debug(f"布林线上轨数据：\n{upper}")
            logger.debug(f"布林线下轨数据：\n{lower}")
            
            # 查找触碰点（只在这里调用一次）
            touches = self._find_bollinger_touches(df, upper, lower)
            logger.info(f"准备添加 {len(touches)} 个价格标注")
            
            # 创建数值索引映射
            date_index = list(range(len(df.index)))
            
            for i, touch in enumerate(touches):
                # 获取时间索引对应的数值索引
                idx = df.index.get_loc(touch["index"])
                
                # 根据位置调整偏移量和位置
                if touch["position"] == "upper":
                    # 上轨保持原样
                    y_offset = touch["price"] * 0.01
                    va = "bottom"
                else:
                    # 下轨增加偏移量，确保标注在实体下方足够距离
                    y_offset = -touch["price"] * 0.015
                    va = "top"
                
                # 格式化价格，保留2位小数
                price_text = f"{touch['price']:.0f}"  # 改为整数显示
                
                logger.debug(f"添加标注：位置={touch['position']}, 价格={price_text}, 索引={idx}")
                
                # 使用数值索引进行标注
                ax.annotate(
                    price_text,
                    xy=(idx, touch["price"]),
                    xytext=(idx, touch["price"] + y_offset),
                    color="black",
                    fontsize=8,
                    ha="center",
                    va=va,
                    bbox=None,
                    arrowprops=dict(
                        arrowstyle="->",
                        color="black",
                        alpha=0.6,
                        connectionstyle="arc3,rad=0"
                    ),
                    zorder=100
                )

        # 添加成交量标注
        volume_ax = axes[1]  # 获取成交量子图
        
        # 获取最近7天的数据
        recent_data = df.tail(7)
        
        # 计算当前y轴范围
        y_min, y_max = volume_ax.get_ylim()
        
        # 为标注预留额外空间（当前最大值的30%）
        volume_ax.set_ylim(y_min, y_max * 1.3)
        
        # 遍历最近7天的数据添加成交量标注
        for i, (idx, row) in enumerate(recent_data.iterrows()):
            # 获取时间索引对应的数值索引
            date_idx = df.index.get_loc(idx)
            volume = row["Volume"]
            
            # 格式化成交量，大于1000的显示为k
            if volume >= 1000:
                volume_text = f"{volume/1000:.1f}k"
            else:
                volume_text = f"{volume:.0f}"
            
            # 计算标注位置（在柱状图上方）
            y_pos = volume * 1.05  # 降低偏移量到5%
            
            # 添加成交量标注
            volume_ax.annotate(
                volume_text,
                xy=(date_idx, volume),
                xytext=(date_idx, y_pos),
                color="black",
                fontsize=8,
                ha="center",
                va="bottom",
                bbox=None,
                zorder=100
            )

        # 调整标题位置
        fig.suptitle(title, y=0.95)

        # 调整布局
        fig.tight_layout(rect=[0, 0, 1, 0.95])  # 为标题预留空间

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
