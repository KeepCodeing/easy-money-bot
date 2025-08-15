#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
图表绘制模块
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
from .indicators import TechnicalIndicators, IndicatorType
from src.utils.file_utils import clean_filename
from .signal_summary import SignalSummary
from math import ceil
import matplotlib.dates as mdates

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

# 设置中文字体 - 改进的跨平台实现
font = None
platform = sys.platform

try:
    if platform == 'win32':
        # Windows系统
        font_path = r"C:\Windows\Fonts\msyh.ttc"
        if os.path.exists(font_path):
            font = FontProperties(fname=font_path)
            plt.rcParams["font.family"] = ["Microsoft YaHei"]
            logger.info("成功加载微软雅黑字体")
        else:
            logger.warning("未找到微软雅黑字体，将使用系统默认字体")
    elif platform == 'darwin':
        # macOS系统
        plt.rcParams["font.family"] = ["Heiti TC", "PingFang SC"]
        logger.info("使用macOS中文字体")
    else:
        # Linux系统
        # 尝试常见的Linux中文字体
        linux_fonts = ["WenQuanYi Micro Hei", "Noto Sans CJK SC", "Noto Sans CJK TC", "Droid Sans Fallback"]
        plt.rcParams["font.family"] = linux_fonts + ["sans-serif"]
        logger.info(f"使用Linux中文字体: {', '.join(linux_fonts)}")
except Exception as e:
    logger.warning(f"设置中文字体失败: {e}，将使用系统默认字体")
    plt.rcParams["font.family"] = ["sans-serif"]

# 检查是否成功设置了字体
logger.info(f"当前使用的字体家族: {plt.rcParams['font.family']}")

class KLineChart:
    """K线图绘制类"""

    def __init__(self, signal_summary: SignalSummary = None, days_to_show: int = settings.CHART_DAYS):
        """
        初始化K线图绘制器

        Args:
            signal_summary: 信号汇总器
            days_to_show: 显示最近多少天的数据
        """
        self.days_to_show = days_to_show
        self.charts_dir = os.path.join(settings.DATA_DIR, "charts")
        if not os.path.exists(self.charts_dir):
            os.makedirs(self.charts_dir)

        # 初始化信号汇总器
        if signal_summary is None:
            self.signal_summary = SignalSummary()
        else:
            self.signal_summary = signal_summary

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
        self, df: pd.DataFrame, upper: pd.Series, lower: pd.Series, 
        item_id: str = None, item_name: str = None, fav_name: str = None
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
            item_id: 商品ID（可选）
            item_name: 商品名称（可选）

        Returns:
            触碰点列表，每个点包含：
            - index: 时间索引
            - price: 最高价或收盘价/开盘价
            - position: 'upper' 或 'lower'
        """
        # 分别存储上下轨的触碰点
        upper_touches = []
        lower_touches = []

        # 使用配置中的布林线容差
        tolerance_upper = settings.BOLL_TOLERANCE_UPPER
        tolerance_lower = settings.BOLL_TOLERANCE_LOWER

        logger.info(
            f"开始检测触碰点，数据长度：{len(df)}，布林线上轨长度：{len(upper)}，布林线下轨长度：{len(lower)}"
        )

        item_volume_ma = self.indicators.calculate_volume_ma(df)

        for idx in df.index:
            high_price = float(df.loc[idx, "High"])
            low_price = float(df.loc[idx, "Low"])
            open_price = float(df.loc[idx, "Open"])
            close_price = float(df.loc[idx, "Close"])
            volume = float(df.loc[idx, "Volume"])
            upper_band = float(upper[idx])
            lower_band = float(lower[idx])
            middle_band = float((upper_band + lower_band) / 2)

            # 计算实体上方和下方价格
            body_high_price = max(open_price, close_price)
            body_low_price = min(open_price, close_price)

            logger.debug(f"检查日期 {idx}:")
            logger.debug(f"  实体上方：{body_high_price:.2f}, 布林上轨：{upper_band:.2f}")
            logger.debug(f"  实体下方：{body_low_price:.2f}, 布林下轨：{lower_band:.2f}")

            # 检查上轨（使用实体上方价格）
            upper_threshold = upper_band * (1 - tolerance_upper)
            if body_high_price >= upper_threshold:
                touch = {
                    "index": idx,
                    "price": high_price,
                    "position": "upper",
                    "open": open_price,
                    "close": close_price,
                    "volume": volume
                }
                upper_touches.append(touch)
                
                # 如果是最新的一天且提供了商品ID，添加到信号汇总
                if item_id and idx == df.index[-1]:
                    volume_ma = [round(ma[-1]) for ma in item_volume_ma]
                    
                    # 查找上一次的上轨触碰点
                    previous_upper = None
                    if len(upper_touches) > 1:
                        prev_touch = upper_touches[-2]  # 倒数第二个触碰点
                        days_ago = (pd.to_datetime(idx) - pd.to_datetime(prev_touch['index'])).days
                        previous_upper = {
                            'price': prev_touch['price'],
                            'timestamp': prev_touch['index'].strftime('%Y-%m-%d %H:%M:%S'),
                            'days_ago': days_ago
                        }
                    
                    # 计算3天和7天前的价格变化
                    current_idx = df.index.get_loc(idx)
                    price_changes = {
                        'day3': {'price': 0.0, 'diff': 0.0, 'rate': 0.0},
                        'day7': {'price': 0.0, 'diff': 0.0, 'rate': 0.0}
                    }
                    
                    # 计算3天前的价格变化
                    if current_idx >= 3 and current_idx - 3 >= 0:
                        day3_idx = df.index[current_idx - 3]
                        day3_price = float(df.loc[day3_idx, "Close"])
                        price_changes['day3'] = {
                            'price': day3_price,
                            'diff': high_price - day3_price,
                            'rate': ((high_price - day3_price) / day3_price * 100) if day3_price > 0 else 0.0
                        }
                    
                    # 计算7天前的价格变化
                    if current_idx >= 7 and current_idx - 7 >= 0:
                        day7_idx = df.index[current_idx - 7]
                        day7_price = float(df.loc[day7_idx, "Close"])
                        price_changes['day7'] = {
                            'price': day7_price,
                            'diff': high_price - day7_price,
                            'rate': ((high_price - day7_price) / day7_price * 100) if day7_price > 0 else 0.0
                        }
                    
                    self.signal_summary.add_signal(
                        item_id=str(item_id),
                        item_name=str(item_name or f'Item-{item_id}'),
                        signal_type='sell',
                        price=body_high_price,
                        open_price=open_price,
                        close_price=close_price,
                        volume=volume,
                        boll_values={
                            'middle': middle_band,
                            'upper': upper_band,
                            'lower': lower_band
                        },
                        timestamp=pd.to_datetime(idx),
                        previous_touch=previous_upper,
                        price_changes=price_changes,
                        fav_name=fav_name,
                        volume_ma=volume_ma
                    )
                    
                    logger.info(f"最新 上轨触碰点: {idx}, 最高价={high_price:.2f}, 布林上轨={upper_band:.2f}")
                    
                logger.debug(
                    f"检测到上轨触碰点: 日期={idx}, 最高价={high_price:.2f}, 布林上轨={upper_band:.2f}"
                )

            # 检查下轨（使用实体下方价格）
            lower_threshold = lower_band * (1 + tolerance_lower)
            if body_low_price <= lower_threshold:
                touch = {
                    "index": idx,
                    "price": low_price,
                    "position": "lower",
                    "open": open_price,
                    "close": close_price,
                    "volume": volume
                }
                lower_touches.append(touch)
                
                # 如果是最新的一天且提供了商品ID，添加到信号汇总
                if item_id and idx == df.index[-1]:
                    volume_ma = [round(ma[-1]) for ma in item_volume_ma]

                    # 查找上一次的下轨触碰点
                    previous_lower = None
                    if len(lower_touches) > 1:
                        prev_touch = lower_touches[-2]  # 倒数第二个触碰点
                        days_ago = (pd.to_datetime(idx) - pd.to_datetime(prev_touch['index'])).days
                        previous_lower = {
                            'price': prev_touch['price'],
                            'timestamp': prev_touch['index'].strftime('%Y-%m-%d %H:%M:%S'),
                            'days_ago': days_ago
                        }
                    
                    # 计算3天和7天前的价格变化
                    current_idx = df.index.get_loc(idx)
                    price_changes = {
                        'day3': {'price': 0.0, 'diff': 0.0, 'rate': 0.0},
                        'day7': {'price': 0.0, 'diff': 0.0, 'rate': 0.0}
                    }
                    
                    # 计算3天前的价格变化
                    if current_idx >= 3 and current_idx - 3 >= 0:
                        day3_idx = df.index[current_idx - 3]
                        day3_price = float(df.loc[day3_idx, "Close"])
                        price_changes['day3'] = {
                            'price': day3_price,
                            'diff': low_price - day3_price,
                            'rate': ((low_price - day3_price) / day3_price * 100) if day3_price > 0 else 0.0
                        }
                    
                    # 计算7天前的价格变化
                    if current_idx >= 7 and current_idx - 7 >= 0:
                        day7_idx = df.index[current_idx - 7]
                        day7_price = float(df.loc[day7_idx, "Close"])
                        price_changes['day7'] = {
                            'price': day7_price,
                            'diff': low_price - day7_price,
                            'rate': ((low_price - day7_price) / day7_price * 100) if day7_price > 0 else 0.0
                        }
                    
                    self.signal_summary.add_signal(
                        item_id=str(item_id),
                        item_name=str(item_name or f'Item-{item_id}'),
                        signal_type='buy',
                        price=body_low_price,
                        open_price=open_price,
                        close_price=close_price,
                        volume=volume,
                        boll_values={
                            'middle': middle_band,
                            'upper': upper_band,
                            'lower': lower_band
                        },
                        timestamp=pd.to_datetime(idx),
                        previous_touch=previous_lower,
                        price_changes=price_changes,
                        fav_name=fav_name,
                        volume_ma=volume_ma
                    )
                    logger.info(f"最新 下轨触碰点: {idx}, 最低价={low_price:.2f}, 布林下轨={lower_band:.2f}")
                    
                logger.debug(
                    f"检测到下轨触碰点: 日期={idx}, 最低价={low_price:.2f}, 布林下轨={lower_band:.2f}"
                )

            # 检测买盘力度
            if item_id and idx == df.index[-1]:
                # 获取最后N天的索引位置
                n = settings.VOLUME_MA_FILTER_DAY_RANGE
                last_n_indices = df.index[-n:]
                
                # 获取最后N天的Volume和MA数据
                nearly_vol = df.loc[last_n_indices, 'Volume']
                nearly_vol_ma = [ma[-n:] for ma in item_volume_ma[-n:]]
                
                
                # 打印调试信息
                # logger.info(f"近{n}天成交量:\n{nearly_vol}")
                # logger.info(f"近{n}天MA值:\n{nearly_vol_ma}")
                
                large_order_timeline = {
                    'items': [],
                    'info': {
                        'day_range': settings.VOLUME_MA_FILTER_DAY_RANGE
                    }
                }
                
                # 遍历最后N天
                for i, (date, vol) in enumerate(zip(last_n_indices, nearly_vol)):
                    # 跳过小于最小成交量的数据
                    if vol < settings.MIN_VOLUME_COUNT:
                        continue
                    
                    # 计算MA5得分
                    ma5_value = nearly_vol_ma[0][i]  # 假设第一个MA是MA5
                    ma5_score = round(vol / ma5_value * 100, 2)
                    
                    # 检查是否满足拉盘条件
                    if ma5_score > settings.VOLUME_MA1_FILTER_SCORE:
                        # 正确获取当前行的数据
                        row = df.loc[date]
                        
                        open_price_ = float(row["Open"])
                        close_price_ = float(row["Close"])
                        volume_ = float(row["Volume"])
                        
                        logger.info(f"拉盘信号: {item_name} 于 {date}, score: {ma5_score}")
                        logger.info(f"开盘价: {open_price_}, 收盘价: {close_price_}, 成交量: {volume_}")
                        
                        large_order_timeline['items'].append({
                            'timestamp': date,
                            'score': ma5_score,
                            'ma_ratio': round((vol - ma5_value) / ma5_value * 100, 2),
                            'volume': int(volume_),
                            'price_change': {
                                'open': open_price_,
                                'close': close_price_,
                                'rate': round((close_price_ - open_price_) / open_price_ * 100, 2)
                            },
                        })

                large_order_timeline['info']['neraly_vol'] = list(nearly_vol)                
                large_order_timeline['info']['neraly_ma5'] = list(map(round, [ma for ma in nearly_vol_ma[0]]))      
                
                # logger.info("*" * 100)        
                # logger.info(large_order_timeline)
                # logger.info("*" * 100)        
                
                if len(large_order_timeline['items']) > 0:
                    self.signal_summary.add_signal(
                        item_id=str(item_id),
                        item_name=str(item_name or f'Item-{item_id}'),
                        signal_type='large_order',
                        price=body_high_price,
                        open_price=open_price,
                        close_price=close_price,
                        volume=volume,
                        boll_values={
                            'middle': middle_band,
                            'upper': upper_band,
                            'lower': lower_band
                        },
                        timestamp=pd.to_datetime(idx),
                        fav_name=fav_name,
                        volume_ma=list([ma[-1] for ma in nearly_vol_ma]),
                        large_order_timeline=large_order_timeline
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
            prev_idx = df.index[i - 1]
            curr_idx = df.index[i]

            prev_close = df.loc[prev_idx, "Close"]
            curr_close = df.loc[curr_idx, "Close"]
            curr_middle = middle[curr_idx]

            # 判断是否从上方回落到中轨
            # 1. 前一个收盘价在中轨上方
            # 2. 当前收盘价接近中轨
            if (
                prev_close > middle[prev_idx]
                and abs(curr_close - curr_middle) <= curr_middle * tolerance
            ):
                middle_touches.append(
                    {"index": curr_idx, "price": curr_close, "position": "middle"}
                )
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
    ) -> str:
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
            str: 保存的图表文件路径，如果失败则返回None
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

        volume_ma1, volume_ma2, volume_ma3 = self.indicators.calculate_volume_ma(df)

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
        latest_touches = []

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

            # 查找布林带触点（传入商品ID和名称用于信号汇总）
            bollinger_touches = self._find_bollinger_touches(
                df, upper, lower, item_id, title
            )
            # 查找中轨回落点
            middle_touches = self._find_bollinger_middle_touches(df, middle)

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

        # 添加成交量MA线到addplots
        addplots.extend([
            mpf.make_addplot(
                volume_ma1,
                panel=1,  # 指定在成交量面板（panel 1）绘制
                color='blue',
                width=1,
                alpha=0.7,
                secondary_y=False,
            ),
            mpf.make_addplot(
                volume_ma2,
                panel=1,
                color='orange',
                width=1,
                alpha=0.7,
                secondary_y=False,
            ),
            mpf.make_addplot(
                volume_ma3,
                panel=1,
                color='purple',
                width=1,
                alpha=0.7,
                secondary_y=False,
            ),
        ])

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
                fontproperties=font,  # 使用全局字体变量，可能为None
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
            fontproperties=font,  # 使用全局字体变量，可能为None
        )

        # 调整布局
        fig.subplots_adjust(
            top=0.90,  # 为标题留出空间
            bottom=0.1,  # 底部边距
            right=0.95,  # 右边距
            left=0.1,  # 左边距
            hspace=0.1,  # 子图间距
        )

        # 保存图表 - 使用商品名称和ID组合作为文件名
        # 如果safe_title为空，则使用item_id作为文件名
        if not safe_title:
            file_name = f"{item_id}.png"
        else:
            # 限制文件名长度，避免文件名过长
            max_name_length = 50
            if len(safe_title) > max_name_length:
                safe_title = safe_title[:max_name_length]
            file_name = f"{safe_title}_{item_id}.png"
            
        save_path = os.path.join(self.charts_dir, file_name)
        fig.savefig(save_path, dpi=300, bbox_inches="tight")
        logger.info(f"K线图已保存至: {save_path}")
        
        # 关闭图表，释放内存
        plt.close(fig)

        return save_path

    def plot_sell_quantity(
        self,
        item_id: str,
        raw_data: List[List],
        title: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> str:
        """
        绘制在售数量的柱状图

        Args:
            item_id: 商品ID
            raw_data: 原始数据，格式为：
                [
                    [timestamp, price, sell_quantity, buy_price, buy_quantity, hourly_amount, hourly_volume, survive_num],
                    ...
                ]
            title: 图表标题，默认为"商品ID - 在售数量"
            start_date: 开始日期，格式：YYYY-MM-DD
            end_date: 结束日期，格式：YYYY-MM-DD

        Returns:
            str: 保存的图表文件路径，如果失败则返回None
        """
        if not raw_data:
            logger.warning(f"商品 {item_id} 没有数据，无法绘制在售数量图")
            return None

        # 清理数据：将None或null替换为0
        cleaned_data = []
        for row in raw_data:
            cleaned_row = [0 if x is None else x for x in row]
            cleaned_data.append(cleaned_row)
            
        print('\n'.join(map(str, cleaned_data[-10:])))

        # 转换数据为DataFrame
        df = pd.DataFrame(
            cleaned_data,
            columns=["timestamp", "price", "sell_quantity", "buy_price", "buy_quantity", "hourly_amount", "hourly_volume", "survive_num"]
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
        df.set_index("timestamp", inplace=True)

        df = df.tail(settings.TREAD_FILTER_DAY_RANGE * 24)
        
        print(df)
        
        # 按日期范围筛选数据
        # if start_date or end_date:
        #     df = self._filter_date_range(df, start_date, end_date)
        # else:
        #     # 默认显示最近 settings.TREAD_FILTER_DAY_RANGE 天的数据
        #     df = self._filter_recent_data(df, days=settings.TREAD_FILTER_DAY_RANGE)

        if len(df) == 0:
            logger.warning(f"商品 {item_id} 筛选后没有数据，无法绘制在售数量图")
            return None

        # 设置图表标题
        if title is None:
            title = f"商品 {item_id} - 在售数量"

        # 清理文件名中的特殊字符
        safe_title = clean_filename(title)

        # 创建图表
        fig, ax = plt.subplots(figsize=(15, 6))

        # 绘制柱状图
        ax.bar(
            df.index,
            df["sell_quantity"],
            width=0.8,
            color="skyblue",
            edgecolor="white",
            label="在售数量"
        )

        # 设置图表标题和标签
        ax.set_title(title, fontsize=12, fontweight="bold", fontproperties=font)
        ax.set_xlabel("日期", fontproperties=font)
        ax.set_ylabel("在售数量", fontproperties=font)
        ax.legend(prop=font)

        # 设置x轴日期格式
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
        fig.autofmt_xdate()

        # 保存图表
        # file_name = f"{safe_title}_{item_id}_sell_quantity.png"
        # save_path = os.path.join(self.charts_dir, file_name)
        # fig.savefig(save_path, dpi=300, bbox_inches="tight")
        # logger.info(f"在售数量图已保存至: {save_path}")

        # 关闭图表，释放内存
        # plt.close(fig)

        # return save_path

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
    chart = KLineChart(days_to_show=settings.CHART_DAYS)

    # 绘制K线图
    fig = chart.plot_candlestick("525873303", sample_data["525873303"])
    print(f"K线图已绘制")
