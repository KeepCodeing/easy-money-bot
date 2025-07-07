#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
主程序入口，整合爬虫和数据存储功能
"""

import os
import time
import json
import logging
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import re
import pandas as pd
import numpy as np

from src.crawler.spider import CS2MarketSpider
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

def save_signal_summary(signal_summary: SignalSummary):
    """保存信号汇总"""
    signal_file = signal_summary.save_to_markdown()
    if signal_file:
        logger.info(f"信号汇总已保存到: {signal_file}")
    # 清空已保存的信号
    signal_summary.clear_signals()

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
    获取最新的数据文件夹路径
    
    Returns:
        str: 文件夹路径，如果没有找到则返回None
    """
    try:
        data_dir = os.path.join(settings.DATA_DIR, 'items')
        if not os.path.exists(data_dir):
            logger.warning("未找到items目录")
            return None
            
        # 获取所有时间戳文件夹
        folders = [f for f in os.listdir(data_dir) if os.path.isdir(os.path.join(data_dir, f))]
        if not folders:
            logger.warning("未找到任何时间戳文件夹")
            return None
            
        # 按时间戳排序，获取最新的
        latest_folder = max(folders, key=lambda x: int(x))
        folder_path = os.path.join(data_dir, latest_folder)
        
        logger.info(f"找到最新数据文件夹: {folder_path}")
        return folder_path
        
    except Exception as e:
        logger.error(f"获取最新数据文件夹时出错: {e}")
        return None


def load_item_data(folder_path: str) -> Dict[str, Dict]:
    """
    从文件夹中加载所有商品数据
    
    Args:
        folder_path: 数据文件夹路径
        
    Returns:
        Dict: 商品数据字典
    """
    result = {}
    try:
        # 获取文件夹中所有JSON文件
        json_files = [f for f in os.listdir(folder_path) if f.endswith('.json')]
        
        for json_file in json_files:
            file_path = os.path.join(folder_path, json_file)
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                item_id = data['item_id']
                result[item_id] = {
                    'name': data['name'],
                    'data': data['data']
                }
                
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
    加载市场数据，优先从时间戳文件夹中加载所有JSON文件
    
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
        
        # 获取最新的数据文件夹
        latest_folder = get_latest_data_folder()
        if not latest_folder:
            raise FileNotFoundError("未找到任何数据文件夹")
        
        # 从文件夹中加载所有JSON文件
        data = load_item_data(latest_folder)
        if not data:
            raise FileNotFoundError(f"在文件夹 {latest_folder} 中未找到任何有效的商品数据")
        
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
        chart = KLineChart(signal_summary, days_to_show=30)
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
        chart = KLineChart(signal_summary, days_to_show=30)
        chart.plot_candlestick(
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


def crawl_and_save(filename: Optional[str] = None, indicator: str = "all"):
    """
    爬取数据并保存，同时生成图表
    
    Args:
        filename: 可选的文件名，如果不提供则自动生成
        indicator: 指标类型，可选 'all'、'boll' 或 'vegas'
    """
    logger.info("开始执行爬虫任务")
    start_time = time.time()

    try:
        # 初始化爬虫
        spider = CS2MarketSpider()

        # 爬取数据（此时数据已经保存在时间戳文件夹中）
        spider.crawl_all_items()
        
        # 获取最新的数据文件夹
        latest_folder = get_latest_data_folder()
        if not latest_folder:
            logger.error("未找到数据文件夹")
            return
            
        # 加载商品数据
        result = load_item_data(latest_folder)
        if not result:
            logger.error("加载数据失败，未获取到任何数据")
            return
            
        logger.info(f"开始为所有商品生成图表")
        
        signal_summary = SignalSummary()
        
        # 遍历所有商品生成图表
        for item_id, item_data in result.items():
            try:
                name = item_data.get('name', f'Item-{item_id}')
                kline_data = item_data.get('data', [])
                
                if not kline_data:
                    logger.warning(f"商品 [{name}] 没有K线数据，跳过图表生成")
                    continue
                
                logger.info(f"正在生成商品 [{name}] 的K线图")
                
                # 清理数据
                cleaned_data = MarketDataCleaner.clean_kline_data(kline_data)
                
                # 确定要显示的指标类型
                indicator_type = IndicatorType.ALL
                if indicator.lower() == "boll":
                    indicator_type = IndicatorType.BOLL
                elif indicator.lower() == "vegas":
                    indicator_type = IndicatorType.VEGAS
                
                # 创建图表
                chart = KLineChart(signal_summary, days_to_show=30)
                chart.plot_candlestick(
                    item_id=item_id,
                    raw_data=cleaned_data,
                    title=name,
                    indicator_type=indicator_type
                )
                
                logger.info(f"商品 [{name}] 的K线图生成完成")
                
            except Exception as e:
                logger.error(f"生成商品 [{name}] 的图表时出错: {e}")
                continue
        
        save_signal_summary(signal_summary)
        
        # 统计结果
        elapsed_time = time.time() - start_time
        logger.info(f"任务完成，共处理 {len(result)} 个商品")
        logger.info(f"数据保存在: {latest_folder}")
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


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='CS2市场数据分析工具')
    parser.add_argument('--crawl', action='store_true', help='爬取数据')
    parser.add_argument('--all', action='store_true', help='批量生成所有商品的图表')
    parser.add_argument('--indicator', type=str, default='all', choices=['all', 'boll', 'vegas'], help='指标类型')
    parser.add_argument('--item', type=str, help='指定商品ID')
    parser.add_argument('--name', type=str, help='指定商品名称')
    parser.add_argument('--notify', action='store_true', help='消息推送')
    
    args = parser.parse_args()
    
    try:
        if args.notify:
            send_notify(settings.NATY_TOPIC_BUY_SELL_NOTIFY, "Hello World", settings.NATY_SERVER_URL)
            return
        
        if args.crawl:
            # 爬取并保存数据，同时生成图表
            crawl_and_save(indicator=args.indicator)
            
        elif args.all:
            # 批量生成所有商品的图表
            logger.info("开始批量生成图表")
            
            # 获取最新的数据文件夹
            latest_folder = get_latest_data_folder()
            if not latest_folder:
                logger.error("未找到数据文件夹")
                return
                
            # 加载商品数据
            market_data = load_item_data(latest_folder)
            if not market_data:
                logger.error("未找到任何商品数据")
                return
            
            signal_summary = SignalSummary()
                
            # 遍历生成图表
            for item_id, item_data in market_data.items():
                try:
                    name = item_data.get('name', f'Item-{item_id}')
                    kline_data = item_data.get('data', [])
                    
                    if not kline_data:
                        logger.warning(f"商品 [{name}] 没有K线数据，跳过图表生成")
                        continue
                    
                    logger.info(f"正在生成商品 [{name}] 的K线图")
                    
                    # 清理数据
                    cleaned_data = MarketDataCleaner.clean_kline_data(kline_data)
                    
                    # 确定要显示的指标类型
                    indicator_type = IndicatorType.ALL
                    if args.indicator.lower() == "boll":
                        indicator_type = IndicatorType.BOLL
                    elif args.indicator.lower() == "vegas":
                        indicator_type = IndicatorType.VEGAS
                    
                    # 创建图表
                    chart = KLineChart(signal_summary, days_to_show=30)
                    chart.plot_candlestick(
                        item_id=item_id,
                        raw_data=cleaned_data,
                        title=name,
                        indicator_type=indicator_type
                    )
                    
                    logger.info(f"商品 [{name}] 的K线图生成完成")
                    
                except Exception as e:
                    logger.error(f"生成商品 [{name}] 的图表时出错: {e}")
                    continue
                    
            save_signal_summary(signal_summary)
            
            logger.info("所有图表生成完成")
            
        elif args.item:
            # 生成指定商品的图表
            latest_folder = get_latest_data_folder()
            if not latest_folder:
                logger.error("未找到数据文件夹")
                return
                
            market_data = load_item_data(latest_folder)
            if not market_data:
                logger.error("未找到任何商品数据")
                return
                
            if args.item not in market_data:
                logger.error(f"未找到商品ID: {args.item}")
                return
                
            item_data = market_data[args.item]
            name = item_data.get('name', f'Item-{args.item}')
            kline_data = item_data.get('data', [])
            
            if not kline_data:
                logger.error(f"商品 [{name}] 没有K线数据")
                return
                
            # 清理数据
            cleaned_data = MarketDataCleaner.clean_kline_data(kline_data)
            
            # 确定要显示的指标类型
            indicator_type = IndicatorType.ALL
            if args.indicator.lower() == "boll":
                indicator_type = IndicatorType.BOLL
            elif args.indicator.lower() == "vegas":
                indicator_type = IndicatorType.VEGAS
            
            # 创建图表
            signal_summary = SignalSummary()
            chart = KLineChart(signal_summary, days_to_show=30)
            chart.plot_candlestick(
                item_id=args.item,
                raw_data=cleaned_data,
                title=name,
                indicator_type=indicator_type
            )
            
            save_signal_summary(signal_summary)
            
            logger.info(f"商品 [{name}] 的K线图生成完成")
            
        else:
            parser.print_help()
            
    except Exception as e:
        logger.error(f"批量生成图表时出错: {e}")
        return


if __name__ == "__main__":
    main()