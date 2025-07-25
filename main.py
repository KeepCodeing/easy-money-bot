#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
主程序入口，整合爬虫和数据存储功能
"""

from math import e
import os
from signal import Signals
import time
import json
import logging
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import re
import pandas as pd
import numpy as np

from src.crawler.spider import Spider
from src.storage.database import DatabaseManager
from config import settings
from src.analysis.chart import KLineChart, IndicatorType
from src.analysis.data_cleaner import MarketDataCleaner
from src.utils.file_utils import clean_filename
from src.analysis.signal_summary import SignalSummary
from src.notification.ntfy import send as send_notify
from config import settings

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(f"{settings.LOG_DIR}/main.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("main")

def save_signal_summary(signal_summary):
    """
    保存信号汇总
    
    Args:
        signal_summary: SignalSummary对象
    """
    # 保存为markdown文件
    md_path = signal_summary.save_to_markdown()
    if md_path:
        logger.info(f"信号汇总已保存到: {md_path}")
    else:
        logger.warning("没有信号需要保存")
        
def load_signal_summary() -> Optional[SignalSummary]:
    """
    加载最新的信号汇总
    
    Returns:
        SignalSummary对象，如果没有找到则返回None
    """
    try:
        signals_dir = os.path.join(settings.DATA_DIR, "signals")
        if not os.path.exists(signals_dir):
            logger.warning("信号目录不存在")
            return None
            
        # 获取最新的信号文件
        signal_files = [f for f in os.listdir(signals_dir) if f.endswith('.md')]
        if not signal_files:
            logger.warning("未找到任何信号文件")
            return None
            
        # 按文件修改时间排序，获取最新的
        latest_file = max(signal_files, key=lambda x: os.path.getmtime(os.path.join(signals_dir, x)))
        file_path = os.path.join(signals_dir, latest_file)
        
        signal_summary = SignalSummary()
        
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        # 跳过表头和分隔线
        data_lines = [line.strip() for line in lines if line.strip() and '|' in line]
        if len(data_lines) <= 2:  # 如果只有表头和分隔线
            logger.info("信号文件为空")
            return signal_summary
            
        # 从第三行开始解析（跳过表头和分隔线）
        for line in data_lines[2:]:
            try:
                # 检查是否是分隔线
                if all(c in '-|' for c in line.strip()):
                    continue
                    
                # 解析信号行
                parts = [p.strip() for p in line.split('|')[1:-1]]  # 去掉首尾的|
                if len(parts) < 10:  # 确保有足够的字段
                    continue
                    
                item_id = parts[0]
                name = parts[1]
                signal_type = parts[2]
                price = float(parts[3]) if parts[3] else 0.0
                open_price = float(parts[4]) if parts[4] else 0.0
                close_price = float(parts[5]) if parts[5] else 0.0
                volume = float(parts[6]) if parts[6] else 0.0
                boll_middle = float(parts[7]) if parts[7] else 0.0
                boll_upper = float(parts[8]) if parts[8] else 0.0
                boll_lower = float(parts[9]) if parts[9] else 0.0
                timestamp = parts[10] if len(parts) > 10 else None
                
                # 添加信号
                signal_summary.add_signal(
                    item_id=item_id,
                    item_name=name,
                    signal_type=signal_type,
                    price=price,
                    open_price=open_price,
                    close_price=close_price,
                    volume=volume,
                    boll_values={
                        'middle': boll_middle,
                        'upper': boll_upper,
                        'lower': boll_lower
                    },
                    timestamp=timestamp
                )
                
            except (ValueError, IndexError) as e:
                logger.warning(f"解析信号行失败: {line}, 错误: {e}")
                continue
                
        logger.info(f"从文件 {file_path} 加载了 {len(signal_summary.signals)} 个信号")
        return signal_summary
        
    except Exception as e:
        logger.error(f"加载信号汇总时出错: {e}")
        return None

def save_market_data(data: Dict[str, Dict], filename: Optional[str] = None) -> str:
    """
    保存市场数据到JSON文件
    
    Args:
        data: 市场数据字典
        filename: 可选的文件名，如果不提供则自动生成
        
    Returns:
        保存的文件路径
    """
    # 如果没有提供文件名，使用时间戳生成
    if not filename:
        # 获取第一个商品的名称作为文件名前缀
        first_item = next(iter(data.values()))
        name_prefix = clean_filename(first_item.get('name', 'market_data'))
        # 生成时间戳
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{name_prefix}-{timestamp}.json"
    
    save_path = os.path.join(settings.DATA_DIR, filename)
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"已保存市场数据到 {save_path}")
    return save_path


def get_latest_data_folder() -> Optional[str]:
    """
    获取最新的数据文件夹
    
    Returns:
        最新数据文件夹的路径，如果没有找到则返回None
    """
    try:
        data_dir = settings.DATA_DIR
        if not os.path.exists(data_dir):
            logger.warning("未找到任何时间戳文件夹")
            return None
            
        # 获取所有时间戳文件夹
        folders = [f for f in os.listdir(data_dir) if os.path.isdir(os.path.join(data_dir, f)) and f.isdigit()]
        
        if not folders:
            logger.warning("未找到任何时间戳文件夹")
            return None
            
        # 按时间戳排序，获取最新的
        latest_folder = max(folders, key=lambda x: int(x))
        latest_path = os.path.join(data_dir, latest_folder)
        
        return latest_path
        
    except Exception as e:
        logger.error(f"获取最新数据文件夹时出错: {e}")
        return None

def load_item_data(folder_path: str) -> Dict[str, Dict]:
    """
    从文件夹中加载所有商品数据
    
    Args:
        folder_path: 数据文件夹路径
        
    Returns:
        Dict: 商品数据字典，格式为：
        {
            item_id: {
                'name': str,
                'data': List[Dict],
                'last_updated': str
            }
        }
    """
    result = {}
    try:
        # 获取文件夹中所有JSON文件
        json_files = [f for f in os.listdir(folder_path) if f.endswith('.json')]
        
        for json_file in json_files:
            file_path = os.path.join(folder_path, json_file)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    item_data = json.load(f)
                    # 从文件名获取item_id（移除.json后缀）
                    item_id = json_file[:-5]
                    result[item_id] = item_data
                    
            except Exception as e:
                logger.error(f"加载文件 {json_file} 失败: {e}")
                continue
                
        logger.info(f"成功加载 {len(result)} 个商品的数据")
        return result
        
    except Exception as e:
        logger.error(f"加载商品数据时出错: {e}")
    return result


def process_kline_data(kline_data: List[List], signal_type: str = None) -> List[List]:
    """
    处理K线数据，添加可能触发信号的数据点
    
    Args:
        kline_data: 原始K线数据
        signal_type: 指定生成的信号类型，可选 'buy' 或 'sell'，默认随机选择
        
    Returns:
        处理后的K线数据
    """
    try:
        if not kline_data:
            return []
            
        # 转换为DataFrame
        df = pd.DataFrame(
            kline_data,
            columns=['Time', 'Open', 'Close', 'High', 'Low', 'Volume', 'Amount']
        )
        
        # 转换时间戳为datetime
        df['Time'] = pd.to_datetime(df['Time'].astype(int), unit='s')
        
        # 用0填充NaN和None
        df = df.fillna(0)
        
        # 确保数值类型正确
        numeric_columns = ['Open', 'Close', 'High', 'Low', 'Volume', 'Amount']
        for col in numeric_columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # 按时间升序排序
        df = df.sort_values('Time')
        
        # 获取最新数据用于计算布林带
        latest_data = df.tail(settings.BOLLINGER_PERIOD)
        mean_price = latest_data['Close'].mean()
        std_price = latest_data['Close'].std()
        
        # 计算布林带
        upper_band = mean_price + (std_price * settings.BOLLINGER_STD)
        lower_band = mean_price - (std_price * settings.BOLLINGER_STD)
        
        # 决定信号类型
        if signal_type is None:
            signal_type = np.random.choice(['buy', 'sell'])
        
        # 生成新的数据点
        latest_time = df['Time'].max() + pd.Timedelta(days=1)
        
        if signal_type == 'buy':
            # 创建买入信号：价格接近下轨
            target_price = lower_band * (1 + settings.BOLL_TOLERANCE / 2)
            new_point = {
                'Time': latest_time,
                'Open': target_price * 1.02,
                'Close': target_price * 0.98,
                'Low': target_price * 0.95,
                'High': target_price * 1.03,
                'Volume': latest_data['Volume'].mean(),
                'Amount': latest_data['Amount'].mean()
            }
        else:
            # 创建卖出信号：价格接近上轨
            target_price = upper_band * (1 - settings.BOLL_TOLERANCE / 2)
            new_point = {
                'Time': latest_time,
                'Open': target_price * 0.98,
                'Close': target_price,
                'Low': target_price * 0.97,
                'High': target_price * 1.02,
                'Volume': latest_data['Volume'].mean(),
                'Amount': latest_data['Amount'].mean()
            }
        
        # 添加新数据点
        df = pd.concat([df, pd.DataFrame([new_point])], ignore_index=True)
        
        # 转换回列表格式
        processed_data = []
        for _, row in df.iterrows():
            processed_data.append([
                int(row['Time'].timestamp()),
                float(row['Open']),
                float(row['Close']),
                float(row['High']),
                float(row['Low']),
                float(row['Volume']),
                float(row['Amount'])
            ])
        
        return processed_data
        
    except Exception as e:
        logger.error(f"处理K线数据时出错: {e}")
        return kline_data


def load_market_data(filename: Optional[str] = None) -> dict:
    """
    加载市场数据，从items目录加载所有JSON文件
    
    Args:
        filename: 可选的文件名，如果提供则从指定文件加载（向后兼容）
        
    Returns:
        加载的市场数据
    """
    try:
        if filename:
            # 如果提供了具体文件名，使用旧的加载方式（向后兼容）
            load_path = os.path.join(settings.DATA_DIR, filename)
            with open(load_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.info(f"已从指定文件 {load_path} 加载市场数据")
            return data
        
        # 从items目录加载所有JSON文件
        items_dir = os.path.join(settings.DATA_DIR, 'items')
        if not os.path.exists(items_dir):
            raise FileNotFoundError("未找到items目录")
        
        # 加载所有商品数据
        data = {}
        for file_name in os.listdir(items_dir):
            if file_name.endswith('.json'):
                file_path = os.path.join(items_dir, file_name)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        item_data = json.load(f)
                        item_id = file_name[:-5]  # 移除.json后缀
                        data[item_id] = item_data
                except Exception as e:
                    logger.error(f"加载文件 {file_name} 失败: {e}")
        
        if not data:
            raise FileNotFoundError(f"在目录 {items_dir} 中未找到任何有效的商品数据")
        
        return data
        
    except Exception as e:
        logger.error(f"加载市场数据时出错: {e}")
        return {}


def test_chart_from_local(
    item_id: str = "525873303", 
    filename: Optional[str] = None,
    indicator: str = "all",
    signal_type: Optional[str] = None,
    signal_summary: SignalSummary = None
):
    """从本地JSON文件读取数据并绘制K线图"""
    try:
        # 加载数据
        data = load_market_data(filename)
        
        if item_id not in data:
            logger.error(f"未找到商品 {item_id} 的数据")
            return
            
        # 获取商品名称和数据
        item_data = data[item_id]
        if not isinstance(item_data, dict):  # 如果是旧格式（直接的K线数据列表）
            name = f'Item-{item_id}'
            kline_data = item_data
        else:  # 如果是新格式（带name的字典）
            name = item_data.get('name', f'Item-{item_id}')
            kline_data = item_data.get('data', [])
        
        # 清理数据
        cleaned_data = MarketDataCleaner.clean_kline_data(kline_data)
        
        # 处理数据，添加信号触发点
        processed_data = process_kline_data(cleaned_data, signal_type)
        
        # 确定要显示的指标类型
        indicator_type = IndicatorType.ALL
        if indicator.lower() == "boll":
            indicator_type = IndicatorType.BOLL
        elif indicator.lower() == "vegas":
            indicator_type = IndicatorType.VEGAS
        
        # 创建图表
        chart = KLineChart(signal_summary, days_to_show=settings.CHART_DAYS)
        
        if settings.SAVE_CHART:
            chart.plot_candlestick(
                item_id=item_id,
                raw_data=processed_data,
                title=name,
                indicator_type=indicator_type
            )
        
    except Exception as e:
        logger.error(f"生成图表时出错: {e}")


def test_chart_by_date_range(
    item_id: str = "525873303",
    filename: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    indicator: str = "all",
    signal_type: Optional[str] = None,
    signal_summary: SignalSummary = None
):
    """
    显示指定时间段的K线图

    Args:
        item_id: 商品ID
        filename: 数据文件名，如果不提供则使用最新的数据文件
        start_date: 开始日期，格式：YYYY-MM-DD
        end_date: 结束日期，格式：YYYY-MM-DD
        indicator: 指标类型，可选 'all'、'boll' 或 'vegas'
        signal_type: 指定生成的信号类型，可选 'buy' 或 'sell'
    """
    try:
        # 加载数据
        data = load_market_data(filename)
        
        if item_id not in data:
            logger.error(f"未找到商品 {item_id} 的数据")
            return
            
        # 获取商品名称和数据
        item_data = data[item_id]
        if not isinstance(item_data, dict):  # 如果是旧格式（直接的K线数据列表）
            name = f'Item-{item_id}'
            kline_data = item_data
        else:  # 如果是新格式（带name的字典）
            name = item_data.get('name', f'Item-{item_id}')
            kline_data = item_data.get('data', [])
        
        # 清理数据
        cleaned_data = MarketDataCleaner.clean_kline_data(kline_data)
        
        # 处理数据，添加信号触发点
        processed_data = process_kline_data(cleaned_data, signal_type)
        
        # 确定要显示的指标类型
        indicator_type = IndicatorType.ALL
        if indicator.lower() == "boll":
            indicator_type = IndicatorType.BOLL
        elif indicator.lower() == "vegas":
            indicator_type = IndicatorType.VEGAS
        
        # 创建图表
        chart = KLineChart(signal_summary, days_to_show=settings.CHART_DAYS)
        if settings.SAVE_CHART:
            chart_path = chart.plot_candlestick(
                item_id=item_id,
                raw_data=processed_data,
                title=name,
                indicator_type=indicator_type,
                start_date=start_date,
                end_date=end_date
            )
        
    except Exception as e:
        logger.error(f"生成图表时出错: {e}")


def generate_all_charts(
    filename: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    indicator: str = "all",
    signal_type: Optional[str] = None
):
    """为所有收藏商品生成图表"""
    try:
        # 加载数据
        data = load_market_data(filename)
        signal_summary = SignalSummary()
        
        # 遍历所有商品
        for item_id, item_data in data.items():
            # 获取商品名称
            if not isinstance(item_data, dict):  # 如果是旧格式（直接的K线数据列表）
                name = f'Item-{item_id}'
            else:  # 如果是新格式（带name的字典）
                name = item_data.get('name', f'Item-{item_id}')
                
            logger.info(f"正在生成商品 [{name}] 的K线图")
            
            # 生成图表
            if start_date and end_date:
                test_chart_by_date_range(
                    item_id=item_id,
                    filename=filename,
                    start_date=start_date,
                    end_date=end_date,
                    indicator=indicator,
                    signal_type=signal_type,
                    signal_summary=signal_summary
                )
            else:
                test_chart_from_local(
                    item_id=item_id,
                    filename=filename,
                    indicator=indicator,
                    signal_type=signal_type,
                    signal_summary=signal_summary
                )
            
        save_signal_summary(signal_summary)
        
    except Exception as e:
        logger.error(f"批量生成图表时出错: {e}")


def crawl_and_save(filename: Optional[str] = None, indicator: str = "all", send_notification: bool = True, ntfy_topic: str = settings.NATY_TOPIC_BUY_SELL_NOTIFY):
    """
    爬取数据并保存，同时生成图表
    
    Args:
        filename: 可选的文件名，如果不提供则自动生成
        indicator: 指标类型，可选 'all'、'boll' 或 'vegas'
        send_notification: 是否发送通知
        ntfy_topic: ntfy的主题名称
    """
    logger.info("开始执行爬虫任务")
    start_time = time.time()

    try:
        # 初始化爬虫
        spider = Spider()
        
        # 获取收藏商品列表
        fav_folders = spider.get_favorite_items()
        
        signal_summary = SignalSummary()
    
        # 用于收集所有图表路径
        chart_paths = {}
        
        for fav_data in fav_folders:

            # 爬取数据（数据会被保存到items目录）
            result = spider.crawl_all_items(fav_data.get('items', []))
            fav_name = fav_data.get('name', "Unknown")
            
            if not result:
                logger.error("爬取数据失败，未获取到任何数据")
                return
                
            logger.info(f"开始分析商品数据，检测信号")
            
            # 第一次遍历：分析所有商品数据，检测信号
            for item_id, item_data in result.items():
                try:
                    name = item_data.get('name', f'Item-{item_id}')
                    kline_data = item_data.get('data', [])
                    
                    if not kline_data:
                        logger.warning(f"商品 [{name}] 没有K线数据，跳过分析")
                        continue
                    
                    # 清理数据
                    cleaned_data = MarketDataCleaner.clean_kline_data(kline_data)
                    
                    # 确定要显示的指标类型
                    indicator_type = IndicatorType.ALL
                    if indicator.lower() == "boll":
                        indicator_type = IndicatorType.BOLL
                    elif indicator.lower() == "vegas":
                        indicator_type = IndicatorType.VEGAS
                    
                    # 创建图表对象，用于分析信号
                    # 注意：这里只分析信号，不生成图表
                    chart = KLineChart(signal_summary, days_to_show=settings.CHART_DAYS)
                    
                    # 分析数据，检测信号
                    # 这一步会将检测到的信号添加到signal_summary中
                    df_full = chart.indicators.prepare_dataframe(cleaned_data)
                    middle, upper, lower = chart.indicators.calculate_bollinger_bands(df_full)
                    
                    # 筛选最近数据
                    df = chart._filter_recent_data(df_full)
                    
                    # 手动调用信号检测方法
                    chart._find_bollinger_touches(df, upper[df.index], lower[df.index], item_id, name, fav_name)
                    
                except Exception as e:
                    logger.error(f"分析商品 [{name}] 的数据时出错: {e}")
                    continue
            
            # 保存信号汇总
            # save_signal_summary(signal_summary)
            
            # 如果有信号，只为有信号的商品生成图表
        if signal_summary.signals and settings.SAVE_CHART:
            logger.info(f"检测到 {len(signal_summary.signals)} 个信号，开始生成图表")
            
            for item_id in signal_summary.signals.keys():
                try:
                    # 获取商品数据
                    if item_id not in result:
                        logger.warning(f"商品 {item_id} 不在爬取结果中，跳过图表生成")
                        continue
                        
                    item_data = result[item_id]
                    name = item_data.get('name', f'Item-{item_id}')
                    kline_data = item_data.get('data', [])
                    
                    if not kline_data:
                        logger.warning(f"商品 [{name}] 没有K线数据，跳过图表生成")
                        continue
                    
                    logger.info(f"正在生成商品 [{name}] 的K线图")
                    
                    # 清理数据
                    cleaned_data = MarketDataCleaner.clean_kline_data(kline_data)
                    
                    # 创建图表
                    chart = KLineChart(signal_summary, days_to_show=settings.CHART_DAYS)
                    
                    chart_path = chart.plot_candlestick(
                        item_id=item_id,
                        raw_data=cleaned_data,
                        title=name,
                        indicator_type=indicator_type
                    )
                    
                    # 保存图表路径
                    if chart_path:
                        chart_paths[item_id] = chart_path
                        # 将图表路径也存储到信号数据中，便于后续查找
                        if item_id in signal_summary.signals:
                            signal_summary.signals[item_id]['chart_path'] = chart_path
                    
                    logger.info(f"商品 [{name}] 的K线图生成完成")
                    
                except Exception as e:
                    logger.error(f"生成商品 {item_id} 的图表时出错: {e}")
                    continue

            # 如果需要发送通知
        if send_notification and signal_summary.signals:
            try:
                logger.info(f"开始发送报告到ntfy主题: {ntfy_topic}")
                success = signal_summary.send_report(ntfy_topic, chart_paths)
                if success:
                    logger.info("报告发送成功")
                else:
                    logger.warning("报告发送失败")
            except Exception as e:
                logger.error(f"发送报告时出错: {e}")
        
        # 统计结果
        elapsed_time = time.time() - start_time
        logger.info(f"任务完成，共处理 {len(result)} 个商品")
        logger.info(f"数据保存在: {os.path.join(settings.DATA_DIR, 'items')}")
        logger.info(f"总耗时: {elapsed_time:.2f} 秒")
        
    except Exception as e:
        logger.error(f"执行任务时出错: {e}")
        elapsed_time = time.time() - start_time
        logger.info(f"任务异常终止，耗时: {elapsed_time:.2f} 秒")


def setup_logging():
    """配置日志"""
    # 创建logs目录
    if not os.path.exists("logs"):
        os.makedirs("logs")
        
    # 配置根日志记录器
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("logs/main.log", encoding="utf-8"),
            logging.StreamHandler()
        ]
    )


def handle_chart_command(args):
    """
    处理chart命令，生成K线图并发送通知
    
    Args:
        args: 命令行参数
    """
    logger.info("开始批量分析商品数据，检测信号")
    
    # 直接加载商品数据
    market_data = load_item_data(os.path.join(settings.DATA_DIR, 'items'))
    if not market_data:
        logger.error("未找到任何商品数据")
        return
    
    signal_summary = SignalSummary()
    
    # 用于收集所有图表路径
    chart_paths = {}
            
    # 第一次遍历：分析所有商品数据，检测信号
    for item_id, item_data in market_data.items():
        try:
            name = item_data.get('name', f'Item-{item_id}')
            kline_data = item_data.get('data', [])
            
            if not kline_data:
                logger.warning(f"商品 [{name}] 没有K线数据，跳过分析")
                continue
            
            # 清理数据
            cleaned_data = MarketDataCleaner.clean_kline_data(kline_data)
            
            # 确定要显示的指标类型
            indicator_type = IndicatorType.ALL
            if args.indicator.lower() == "boll":
                indicator_type = IndicatorType.BOLL
            elif args.indicator.lower() == "vegas":
                indicator_type = IndicatorType.VEGAS
            
            # 创建图表对象，用于分析信号
            # 注意：这里只分析信号，不生成图表
            chart = KLineChart(signal_summary, days_to_show=settings.CHART_DAYS)
            # save chart
            # chart_path = chart.plot_candlestick(
            #         item_id=item_id,
            #         raw_data=cleaned_data,
            #         title=name,
            #         indicator_type=indicator_type
            #     )
            
            # 分析数据，检测信号
            # 这一步会将检测到的信号添加到signal_summary中
            df_full = chart.indicators.prepare_dataframe(cleaned_data)
            middle, upper, lower = chart.indicators.calculate_bollinger_bands(df_full)
            
            # 筛选最近数据
            df = chart._filter_recent_data(df_full)
            
            # 手动调用信号检测方法
            chart._find_bollinger_touches(df, upper[df.index], lower[df.index], item_id, name)
            
        except Exception as e:
            logger.error(f"分析商品 [{name}] 的数据时出错: {e}")
            continue
                
    # 保存信号汇总
    # save_signal_summary(signal_summary)
    
    # 如果有信号，只为有信号的商品生成图表
    if settings.SAVE_CHART:
        if signal_summary.signals:
            logger.info(f"检测到 {len(signal_summary.signals)} 个信号，开始生成图表")
            
            for item_id in signal_summary.signals.keys():
                try:
                    # 获取商品数据
                    if item_id not in market_data:
                        logger.warning(f"商品 {item_id} 不在数据中，跳过图表生成")
                        continue
                        
                    item_data = market_data[item_id]
                    name = item_data.get('name', f'Item-{item_id}')
                    kline_data = item_data.get('data', [])
                    
                    if not kline_data:
                        logger.warning(f"商品 [{name}] 没有K线数据，跳过图表生成")
                        continue
                    
                    logger.info(f"正在生成商品 [{name}] 的K线图")
                    
                    # 清理数据
                    cleaned_data = MarketDataCleaner.clean_kline_data(kline_data)
                    
                    # 创建图表
                    chart = KLineChart(signal_summary, days_to_show=settings.CHART_DAYS)
                    
                    chart_path = chart.plot_candlestick(
                        item_id=item_id,
                        raw_data=cleaned_data,
                        title=name,
                        indicator_type=indicator_type
                    )
                    
                    # 保存图表路径
                    if chart_path:
                        chart_paths[item_id] = chart_path
                        # 将图表路径也存储到信号数据中，便于后续查找
                        if item_id in signal_summary.signals:
                            signal_summary.signals[item_id]['chart_path'] = chart_path
                    
                    logger.info(f"商品 [{name}] 的K线图生成完成")
                
                except Exception as e:
                    logger.error(f"生成商品 {item_id} 的图表时出错: {e}")
                    continue
        else:
            logger.info("未检测到任何信号，跳过图表生成")
    
    # 如果需要发送通知
    if args.notify and signal_summary.signals:
        try:
            ntfy_topic = args.ntfy_topic or "cs2market"
            logger.info(f"开始发送报告到ntfy主题: {ntfy_topic}")
            success = signal_summary.send_report(ntfy_topic, chart_paths)
            if success:
                logger.info("报告发送成功")
            else:
                logger.warning("报告发送失败")
        except Exception as e:
            logger.error(f"发送报告时出错: {e}")
        
    # logger.info("所有图表生成完成")

def handle_notify_command(args):
    """
    处理notify命令，发送通知
    
    Args:
        args: 命令行参数
    """
    try:
        # 加载商品数据
        market_data = load_market_data()
        if not market_data:
            logger.error("未找到任何商品数据")
            return
            
        # 加载信号汇总
        signal_summary = load_signal_summary()
        if not signal_summary or not signal_summary.signals:
            logger.error("未找到任何信号数据")
            return
            
        # 收集图表路径 - 只收集有信号的商品的图表
        chart_paths = {}
        charts_dir = os.path.join(settings.DATA_DIR, "charts")
        if os.path.exists(charts_dir):
            # 获取charts目录下的所有PNG文件
            all_chart_files = [f for f in os.listdir(charts_dir) if f.endswith('.png')]
            
            for item_id, signal in signal_summary.signals.items():
                # 首先检查信号数据中是否已经有保存的图表路径
                if 'chart_path' in signal and os.path.exists(signal['chart_path']):
                    chart_paths[item_id] = signal['chart_path']
                    logger.info(f"使用信号中保存的图表路径: {signal['chart_path']}")
                    continue
                    
                # 尝试查找匹配的文件
                matching_files = []
                for chart_file in all_chart_files:
                    # 检查文件名是否以商品ID结尾
                    if chart_file.endswith(f"_{item_id}.png") or chart_file == f"{item_id}.png":
                        matching_files.append(chart_file)
                
                if matching_files:
                    # 如果找到多个匹配文件，使用最新的一个
                    matching_files.sort(key=lambda f: os.path.getmtime(os.path.join(charts_dir, f)), reverse=True)
                    chart_path = os.path.join(charts_dir, matching_files[0])
                    chart_paths[item_id] = chart_path
                    logger.info(f"找到商品 {item_id} 的图表文件: {matching_files[0]}")
                else:
                    logger.warning(f"商品 {item_id} 的图表文件不存在")
        
        # 检查是否有图表可以发送
        if not chart_paths:
            logger.warning("未找到任何有效的图表文件，将只发送文本报告")
        else:
            logger.info(f"找到 {len(chart_paths)} 个图表文件可以发送")
        
        # 发送报告
        if signal_summary and signal_summary.signals:
            logger.info(f"开始发送报告到ntfy主题: {args.topic}")
            success = signal_summary.send_report(args.topic, chart_paths)
            if success:
                logger.info("报告发送成功")
            else:
                logger.warning("报告发送失败")
        else:
            logger.warning("没有信号数据可以发送")
            
    except Exception as e:
        logger.error(f"发送报告时出错: {e}")


def handle_rank_command(args):
    """
    处理rank命令，获取交易量排行榜数据
    
    Args:
        args: 命令行参数
    """
    # 获取交易量排行榜数据
    spider = Spider()
    
    # 获取收藏夹列表
    folders = spider.get_favorite_folders()
    
    if args.fav_id:
        # 获取指定收藏夹的排行榜数据
        rank_data = spider.get_total_buy_rank(args.fav_id)
        folder_name = folders.get(args.fav_id, f"未知收藏夹({args.fav_id})")
        
        if rank_data:
            print(f"\n收藏夹 [{folder_name}] 的交易量排行榜数据:")
            for i, item in enumerate(rank_data, 1):
                print(f"\n{i}. {item['item_name']} (ID: {item['item_id']}):")
                print(f"   等级: {item['item_rarity']}")
                print(f"   存世量: {item['survive_num']}")
                print(f"   在售情况:")
                print(f"     当前: {item['sell_nums']['current']} 个")
                print(f"     1天前: {item['sell_nums']['day1']['nums']} 个 (变化: {item['sell_nums']['day1']['diff']:+d}, {item['sell_nums']['day1']['rate']:+.2f}%)")
                print(f"     3天前: {item['sell_nums']['day3']['nums']} 个 (变化: {item['sell_nums']['day3']['diff']:+d}, {item['sell_nums']['day3']['rate']:+.2f}%)")
                print(f"     7天前: {item['sell_nums']['day7']['nums']} 个 (变化: {item['sell_nums']['day7']['diff']:+d}, {item['sell_nums']['day7']['rate']:+.2f}%)")
                print(f"   价格情况:")
                print(f"     当前: {item['price']['current']:.2f}")
                print(f"     1天前: {item['price']['day1']['price']:.2f} (变化: {item['price']['day1']['diff']:+.2f}, {item['price']['day1']['rate']:+.2f}%)")
                print(f"     3天前: {item['price']['day3']['price']:.2f} (变化: {item['price']['day3']['diff']:+.2f}, {item['price']['day3']['rate']:+.2f}%)")
                print(f"     7天前: {item['price']['day7']['price']:.2f} (变化: {item['price']['day7']['diff']:+.2f}, {item['price']['day7']['rate']:+.2f}%)")
                print(f"   24小时交易:")
                print(f"     成交量: {item['transaction']['count_24h']} 个")
                print(f"     成交额: {item['transaction']['amount_24h']:.2f}")
                print(f"     当日成交量: {item['transaction']['count_1day']} 个")
            # 如果需要发送通知
            if args.notify:
                message = f"收藏夹 [{folder_name}] 交易量排行榜：\n\n"
                for i, item in enumerate(rank_data, 1):
                    message += f"{i}. {item['item_name']} (ID: {item['item_id']})\n"
                    message += f"   等级: {item['item_rarity']}\n"
                    message += f"   存世量: {item['survive_num']}\n"
                    message += f"   在售情况:\n"
                    message += f"     当前: {item['sell_nums']['current']} 个\n"
                    message += f"     1天前: {item['sell_nums']['day1']['nums']} 个 (变化: {item['sell_nums']['day1']['diff']:+d}, {item['sell_nums']['day1']['rate']:+.2f}%)\n"
                    message += f"     3天前: {item['sell_nums']['day3']['nums']} 个 (变化: {item['sell_nums']['day3']['diff']:+d}, {item['sell_nums']['day3']['rate']:+.2f}%)\n"
                    message += f"     7天前: {item['sell_nums']['day7']['nums']} 个 (变化: {item['sell_nums']['day7']['diff']:+d}, {item['sell_nums']['day7']['rate']:+.2f}%)\n"
                    message += f"   价格情况:\n"
                    message += f"     当前: {item['price']['current']:.2f}\n"
                    message += f"     1天前: {item['price']['day1']['price']:.2f} (变化: {item['price']['day1']['diff']:+.2f}, {item['price']['day1']['rate']:+.2f}%)\n"
                    message += f"     3天前: {item['price']['day3']['price']:.2f} (变化: {item['price']['day3']['diff']:+.2f}, {item['price']['day3']['rate']:+.2f}%)\n"
                    message += f"     7天前: {item['price']['day7']['price']:.2f} (变化: {item['price']['day7']['diff']:+.2f}, {item['price']['day7']['rate']:+.2f}%)\n"
                    message += f"   24小时交易:\n"
                    message += f"     成交量: {item['transaction']['count_24h']} 个\n"
                    message += f"     成交额: {item['transaction']['amount_24h']:.2f}\n"
                    message += f"     当日成交量: {item['transaction']['count_1day']} 个\n\n"
                send_notify(args.ntfy_topic, message, settings.NATY_SERVER_URL)
    else:
        # 获取所有收藏夹的排行榜数据
        all_rank_data = spider.get_all_fav_total_buy_rank()
        
        # 控制台输出
        for fav_id, rank_data in all_rank_data.items():
            folder_name = folders.get(fav_id, f"未知收藏夹({fav_id})")
            print(f"\n收藏夹 [{folder_name}] 的交易量排行榜数据:")
            for i, item in enumerate(rank_data, 1):
                print(f"\n{i}. {item['item_name']} (ID: {item['item_id']}):")
                print(f"   等级: {item['item_rarity']}")
                print(f"   存世量: {item['survive_num']}")
                print(f"   在售情况:")
                print(f"     当前: {item['sell_nums']['current']} 个")
                print(f"     1天前: {item['sell_nums']['day1']['nums']} 个 (变化: {item['sell_nums']['day1']['diff']:+d}, {item['sell_nums']['day1']['rate']:+.2f}%)")
                print(f"     3天前: {item['sell_nums']['day3']['nums']} 个 (变化: {item['sell_nums']['day3']['diff']:+d}, {item['sell_nums']['day3']['rate']:+.2f}%)")
                print(f"     7天前: {item['sell_nums']['day7']['nums']} 个 (变化: {item['sell_nums']['day7']['diff']:+d}, {item['sell_nums']['day7']['rate']:+.2f}%)")
                print(f"   价格情况:")
                print(f"     当前: {item['price']['current']:.2f}")
                print(f"     1天前: {item['price']['day1']['price']:.2f} (变化: {item['price']['day1']['diff']:+.2f}, {item['price']['day1']['rate']:+.2f}%)")
                print(f"     3天前: {item['price']['day3']['price']:.2f} (变化: {item['price']['day3']['diff']:+.2f}, {item['price']['day3']['rate']:+.2f}%)")
                print(f"     7天前: {item['price']['day7']['price']:.2f} (变化: {item['price']['day7']['diff']:+.2f}, {item['price']['day7']['rate']:+.2f}%)")
                print(f"   24小时交易:")
                print(f"     成交量: {item['transaction']['count_24h']} 个")
                print(f"     成交额: {item['transaction']['amount_24h']:.2f}")
                print(f"     当日成交量: {item['transaction']['count_1day']} 个")
        # 如果需要发送通知，合并所有收藏夹的数据为一条消息
        if args.notify and all_rank_data:
            message = "交易量排行榜数据汇总：\n"
            for fav_id, rank_data in all_rank_data.items():
                folder_name = folders.get(fav_id, f"未知收藏夹({fav_id})")
                message += f"\n=== 收藏夹 [{folder_name}] ===\n"
                for i, item in enumerate(rank_data, 1):
                    message += f"\n{i}. {item['item_name']} (ID: {item['item_id']})\n"
                    message += f"   等级: {item['item_rarity']}\n"
                    message += f"   存世量: {item['survive_num']}\n"
                    message += f"   在售情况:\n"
                    message += f"     当前: {item['sell_nums']['current']} 个\n"
                    message += f"     1天前: {item['sell_nums']['day1']['nums']} 个 (变化: {item['sell_nums']['day1']['diff']:+d}, {item['sell_nums']['day1']['rate']:+.2f}%)\n"
                    message += f"     3天前: {item['sell_nums']['day3']['nums']} 个 (变化: {item['sell_nums']['day3']['diff']:+d}, {item['sell_nums']['day3']['rate']:+.2f}%)\n"
                    message += f"     7天前: {item['sell_nums']['day7']['nums']} 个 (变化: {item['sell_nums']['day7']['diff']:+d}, {item['sell_nums']['day7']['rate']:+.2f}%)\n"
                    message += f"   价格情况:\n"
                    message += f"     当前: {item['price']['current']:.2f}\n"
                    message += f"     1天前: {item['price']['day1']['price']:.2f} (变化: {item['price']['day1']['diff']:+.2f}, {item['price']['day1']['rate']:+.2f}%)\n"
                    message += f"     3天前: {item['price']['day3']['price']:.2f} (变化: {item['price']['day3']['diff']:+.2f}, {item['price']['day3']['rate']:+.2f}%)\n"
                    message += f"     7天前: {item['price']['day7']['price']:.2f} (变化: {item['price']['day7']['diff']:+.2f}, {item['price']['day7']['rate']:+.2f}%)\n"
                    message += f"   24小时交易:\n"
                    message += f"     成交量: {item['transaction']['count_24h']} 个\n"
                    message += f"     成交额: {item['transaction']['amount_24h']:.2f}\n"
                    message += f"     当日成交量: {item['transaction']['count_1day']} 个\n\n"
            
            send_notify(args.ntfy_topic, message, settings.NATY_SERVER_URL)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="CS2市场数据爬虫与分析工具")
    
    # 子命令
    subparsers = parser.add_subparsers(dest="command", help="子命令")
    
    # 爬虫命令
    crawl_parser = subparsers.add_parser("crawl", help="执行爬虫任务")
    crawl_parser.add_argument("--indicator", type=str, default="boll", choices=["all", "boll", "vegas"], help="要显示的指标类型")
    crawl_parser.add_argument("--notify", action="store_true", default=True, help="发送通知")
    
    # 图表命令
    chart_parser = subparsers.add_parser("chart", help="生成图表")
    chart_parser.add_argument("--indicator", type=str, default="boll", choices=["all", "boll", "vegas"], help="要显示的指标类型")
    chart_parser.add_argument("--notify", action="store_true", default=False, help="发送通知")
    chart_parser.add_argument("--ntfy-topic", type=str, default=settings.NATY_TOPIC_BUY_SELL_NOTIFY, help="ntfy主题名称，默认为cs2market")
    
    # 通知命令
    notify_parser = subparsers.add_parser("notify", help="发送通知")
    notify_parser.add_argument("--topic", type=str, default=settings.NATY_TOPIC_BUY_SELL_NOTIFY, help="ntfy主题名称")
    
    # 交易量排行榜命令
    rank_parser = subparsers.add_parser("rank", help="获取交易量排行榜数据")
    rank_parser.add_argument("--fav-id", type=str, help="指定收藏夹ID，不指定则获取所有配置的收藏夹数据")
    rank_parser.add_argument("--notify", action="store_true", default=False, help="发送通知")
    rank_parser.add_argument("--ntfy-topic", type=str, default=settings.NATY_TOPIC_BUY_SELL_NOTIFY, help="ntfy主题名称")

    args = parser.parse_args()
    
    if args.command == "crawl":
        # 执行爬虫任务
        crawl_and_save(indicator=args.indicator, send_notification=args.notify, ntfy_topic=settings.NATY_TOPIC_BUY_SELL_NOTIFY)
        
    elif args.command == "chart":
        handle_chart_command(args)
        
    elif args.command == "notify":
        handle_notify_command(args)
            
    elif args.command == "rank":
        handle_rank_command(args)
    else:
        # 默认显示帮助信息
        parser.print_help()


if __name__ == "__main__":
    main()