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
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from config import settings
from .indicators import TechnicalIndicators, IndicatorType
from src.utils.file_utils import clean_filename

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(f"{settings.LOG_DIR}/analysis.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# 设置中文字体
try:
    # 尝试使用微软雅黑（Windows）
    font = FontProperties(fname=r"C:\Windows\Fonts\msyh.ttc")
    plt.rcParams["font.family"] = ["Microsoft YaHei"]
    logger.info("成功加载微软雅黑字体")
except Exception as e:
    try:
        # 尝试使用其他中文字体（Linux/macOS）
        plt.rcParams["font.family"] = [
            "Heiti TC",
            "Heiti SC",
            "STHeiti",
            "SimHei",
            "sans-serif",
        ]
        logger.info("成功加载系统中文字体")
    except Exception as e:
        logger.warning(f"加载中文字体失败: {e}，将使用系统默认字体")


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
                "font.family": plt.rcParams["font.family"],  # 使用全局字体设置
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

        # 定义容差范围（1%）
        tolerance = 0.01

        logger.info(
            f"开始检测触碰点，数据长度：{len(df)}，布林线上轨长度：{len(upper)}，布林线下轨长度：{len(lower)}"
        )

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
            logger.debug(
                f"  实体低点：{body_low_price:.2f}, 布林下轨：{lower_band:.2f}"
            )

            # 检查上轨（保持不变，使用最高价）
            upper_threshold = upper_band * (1 - tolerance)
            if high_price >= upper_threshold:
                upper_touches.append(
                    {"index": idx, "price": high_price, "position": "upper"}
                )
                logger.info(
                    f"检测到上轨触碰点: 日期={idx}, 最高价={high_price:.2f}, 布林上轨={upper_band:.2f}"
                )

            # 检查下轨（只使用实体价格）
            lower_threshold = lower_band * (1 + tolerance)
            if body_low_price <= lower_threshold:
                lower_touches.append(
                    {"index": idx, "price": body_low_price, "position": "lower"}
                )
                logger.info(
                    f"检测到下轨触碰点: 日期={idx}, 实体低点={body_low_price:.2f}, 布林下轨={lower_band:.2f}"
                )

        # 返回所有触碰点
        touches = upper_touches + lower_touches
        logger.info(f"触碰点检测完成，共发现 {len(touches)} 个触碰点")
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
                buy_signals.append(
                    {"index": idx, "price": body_low_price, "signal": "buy"}
                )
                logger.debug(
                    f"检测到买入信号: 日期={idx}, 价格={body_low_price:.2f}, 过滤线={filter_line:.2f}"
                )

            # 检查卖出信号（最低价下穿过滤线）
            if low_price < filter_line * (1 - tolerance):
                sell_signals.append(
                    {"index": idx, "price": low_price, "signal": "sell"}
                )
                logger.debug(
                    f"检测到卖出信号: 日期={idx}, 价格={low_price:.2f}, 过滤线={filter_line:.2f}"
                )

        # 只保留最新的信号
        signals = []
        if buy_signals:
            latest_buy = buy_signals[-1]
            signals.append(latest_buy)
            logger.info(
                f"选择最新买入信号: 日期={latest_buy['index']}, 价格={latest_buy['price']:.2f}"
            )

        if sell_signals:
            latest_sell = sell_signals[-1]
            signals.append(latest_sell)
            logger.info(
                f"选择最新卖出信号: 日期={latest_sell['index']}, 价格={latest_sell['price']:.2f}"
            )

        logger.info(f"Vegas通道触碰点检测完成，保留 {len(signals)} 个最新信号")
        return signals

    def _find_bollinger_middle_touches(
        self, df: pd.DataFrame, middle: pd.Series
    ) -> List[Dict]:
        """
        查找从上方回落到布林线中轨的点

        Args:
            df: K线数据
            middle: 布林线中轨

        Returns:
            触碰点列表，每个点包含：
            - index: 时间索引
            - price: 价格
            - position: 'middle'
        """
        middle_touches = []
        tolerance = 0.005  # 0.5%的容差范围
        
        logger.debug(f"开始检测布林线中轨回落点，数据长度：{len(df)}")
        
        # 需要至少2个数据点来判断趋势
        for i in range(1, len(df)):
            prev_idx = df.index[i-1]
            curr_idx = df.index[i]
            
            prev_close = df.loc[prev_idx, "Close"]
            curr_close = df.loc[curr_idx, "Close"]
            curr_middle = middle[curr_idx]
            
            # 判断是否从上方回落到中轨
            # 1. 前一个收盘价在中轨上方
            # 2. 当前收盘价接近中轨
            if (prev_close > middle[prev_idx] and 
                abs(curr_close - curr_middle) <= curr_middle * tolerance):
                middle_touches.append({
                    "index": curr_idx,
                    "price": curr_close,
                    "position": "middle"
                })
                logger.debug(
                    f"检测到中轨回落点: 日期={curr_idx}, "
                    f"价格={curr_close:.2f}, 中轨={curr_middle:.2f}"
                )
        
        logger.info(f"中轨回落点检测完成，共发现 {len(middle_touches)} 个触碰点")
        return middle_touches

    def _filter_date_range(
        self,
        df: pd.DataFrame,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
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
                filtered_df = filtered_df[
                    filtered_df.index >= pd.to_datetime(start_date)
                ]
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
            title: 图表标题，默认为"name(n天)"
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
            title = f"Item-{item_id} ({self.days_to_show}天)"
        else:
            if start_date and end_date:
                title = f"{title} ({start_date} ~ {end_date})"
            else:
                title = f"{title} ({self.days_to_show}天)"

        # 清理文件名中的特殊字符
        safe_title = clean_filename(title)

        # 准备技术指标数据（确保与显示数据长度匹配）
        addplots = []
        latest_touches = []  # 存储所有类型的最新触点

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

            # 查找布林带触点
            bollinger_touches = self._find_bollinger_touches(
                df, upper, lower
            )
            # 查找中轨回落点
            middle_touches = self._find_bollinger_middle_touches(
                df, middle
            )
            
            # 分类存储触点
            upper_touches = [t for t in bollinger_touches if t["position"] == "upper"]
            lower_touches = [t for t in bollinger_touches if t["position"] == "lower"]
            
            # 收集最新的触点
            if upper_touches:
                latest_touches.append(upper_touches[-1])
                logger.info(
                    f"将显示最新上轨触点: 日期={upper_touches[-1]['index']}, "
                    f"价格={upper_touches[-1]['price']:.2f}"
                )
            if lower_touches:
                latest_touches.append(lower_touches[-1])
                logger.info(
                    f"将显示最新下轨触点: 日期={lower_touches[-1]['index']}, "
                    f"价格={lower_touches[-1]['price']:.2f}"
                )
            if middle_touches:
                latest_touches.append(middle_touches[-1])
                logger.info(
                    f"将显示最新中轨回落点: 日期={middle_touches[-1]['index']}, "
                    f"价格={middle_touches[-1]['price']:.2f}"
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

        # 绘制K线图
        fig, axes = mpf.plot(
            df,
            type="candle",
            style=self.chart_style,
            volume=True,
            addplot=addplots,
            returnfig=True,
            figsize=(15, 10),
            panel_ratios=(3, 1),
            datetime_format="%m/%d",  # 修改日期格式为 MM/DD
            volume_alpha=0.5,
            title=title,
        )

        # 添加所有收集到的触点标注
        for touch in latest_touches:
            position = touch["position"]
            price = touch["price"]
            date = touch["index"]
            
            # 获取日期在数据中的位置索引
            date_idx = df.index.get_loc(date)
            
            # 根据位置确定标注文本和位置
            if position == "upper":
                text = f"¥{price:.2f}"  # 简化文本，只显示价格
                y_offset = price * 0.01  # 减小偏移量到1%
            elif position == "lower":
                text = f"¥{price:.2f}"
                y_offset = -price * 0.01
            else:  # middle
                text = f"¥{price:.2f}"
                y_offset = price * 0.01
            
            # 添加标注
            axes[0].annotate(
                text,
                xy=(date_idx, price),
                xytext=(date_idx, price + y_offset),
                textcoords="data",
                ha="center",
                va="bottom" if y_offset > 0 else "top",
                bbox=None,  # 移除边框
                fontproperties=(
                    font if "font" in globals() else None
                ),
                arrowprops=dict(
                    arrowstyle="-",  # 简化箭头样式
                    connectionstyle="arc3,rad=0",
                    color="gray",
                    alpha=0.6,  # 降低箭头透明度
                ),
                zorder=100,
            )

        # 设置标题
        fig.suptitle(
            title,
            fontsize=12,
            fontweight="bold",
            fontproperties=(
                font if "font" in globals() else None
            ),
        )

        # 调整布局
        fig.subplots_adjust(
            top=0.90,  # 为标题留出空间
            bottom=0.1,  # 底部边距
            right=0.95,  # 右边距
            left=0.1,  # 左边距
            hspace=0.1,  # 子图间距
        )

        # 保存图表
        save_path = os.path.join(self.charts_dir, f"{safe_title}.png")
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
