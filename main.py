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
from typing import Dict, List, Optional
import re

from src.crawler.spider import CS2MarketSpider
from src.storage.database import DatabaseManager
from config import settings
from src.analysis.chart import KLineChart, IndicatorType
from src.analysis.data_cleaner import MarketDataCleaner

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


def clean_filename(name: str) -> str:
    """
    清理文件名，移除或替换不合法字符
    
    Args:
        name: 原始文件名
        
    Returns:
        清理后的文件名
    """
    # 替换Windows文件名中不允许的字符
    invalid_chars = r'[<>:"/\\|?*]'
    # 将特殊字符替换为下划线
    cleaned_name = re.sub(invalid_chars, '_', name)
    # 移除多余的空格和下划线
    cleaned_name = re.sub(r'[\s_]+', '_', cleaned_name)
    # 移除首尾的空格和下划线
    cleaned_name = cleaned_name.strip('_')
    return cleaned_name


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


def load_market_data(filename: Optional[str] = None) -> dict:
    """
    从JSON文件加载市场数据
    
    Args:
        filename: 可选的文件名，如果不提供则加载最新的数据文件
        
    Returns:
        加载的市场数据
    """
    if not filename:
        # 获取数据目录下所有的JSON文件
        json_files = [f for f in os.listdir(settings.DATA_DIR) if f.endswith('.json')]
        if not json_files:
            raise FileNotFoundError("未找到任何数据文件")
        
        # 按文件修改时间排序，获取最新的文件
        latest_file = max(
            json_files,
            key=lambda f: os.path.getmtime(os.path.join(settings.DATA_DIR, f))
        )
        filename = latest_file
    
    load_path = os.path.join(settings.DATA_DIR, filename)
    with open(load_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    logger.info(f"已从 {load_path} 加载市场数据")
    return data


def test_chart_from_local(item_id: str = "525873303", 
                         filename: Optional[str] = None,
                         indicator: str = "all"):
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
        
        # 确定要显示的指标类型
        indicator_type = IndicatorType.ALL
        if indicator.lower() == "boll":
            indicator_type = IndicatorType.BOLL
        elif indicator.lower() == "vegas":
            indicator_type = IndicatorType.VEGAS
        
        # 创建图表
        chart = KLineChart()
        chart.plot_candlestick(
            item_id=item_id,
            raw_data=cleaned_data,
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
    indicator: str = "all"
):
    """
    显示指定时间段的K线图

    Args:
        item_id: 商品ID
        filename: 数据文件名，如果不提供则使用最新的数据文件
        start_date: 开始日期，格式：YYYY-MM-DD
        end_date: 结束日期，格式：YYYY-MM-DD
        indicator: 指标类型，可选 'all'、'boll' 或 'vegas'
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
        
        # 确定要显示的指标类型
        indicator_type = IndicatorType.ALL
        if indicator.lower() == "boll":
            indicator_type = IndicatorType.BOLL
        elif indicator.lower() == "vegas":
            indicator_type = IndicatorType.VEGAS
        
        # 创建图表
        chart = KLineChart()
        chart.plot_candlestick(
            item_id=item_id,
            raw_data=cleaned_data,
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
    indicator: str = "all"
):
    """为所有收藏商品生成图表"""
    try:
        # 加载数据
        data = load_market_data(filename)
        
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
                    indicator=indicator
                )
            else:
                test_chart_from_local(
                    item_id=item_id,
                    filename=filename,
                    indicator=indicator
                )
            
    except Exception as e:
        logger.error(f"批量生成图表时出错: {e}")


def crawl_and_save(filename: Optional[str] = None):
    """爬取数据并保存到数据库"""
    logger.info("开始执行爬虫任务")
    start_time = time.time()

    # 初始化爬虫和数据库
    spider = CS2MarketSpider()

    # 爬取数据
    result = spider.crawl_all_items()
    
    # 保存数据到JSON
    save_market_data(result, filename)
    
    exit(0)

    # 清理数据
    cleaned_data = MarketDataCleaner.clean_kline_data(result["525873303"])
    
    # 创建并显示图表
    chart = KLineChart(days_to_show=30)
    fig = chart.plot_candlestick("525873303", cleaned_data)
    
    if fig:
        fig.show()
        fig.waitforbuttonpress()
    
    exit(0)

    db = DatabaseManager()

    # 获取收藏商品列表
    item_ids = spider.get_favorite_items()
    logger.info(f"获取到 {len(item_ids)} 个商品ID")

    # 爬取每个商品的数据并保存
    total_items = len(item_ids)
    success_count = 0
    total_records = 0

    for i, item_id in enumerate(item_ids):
        logger.info(f"正在处理商品 {i+1}/{total_items}: {item_id}")

        try:
            # 爬取商品历史数据
            item_data = spider.get_item_history(item_id)

            exit(0)

            if item_data:
                # 保存商品信息
                db.save_item(item_id, name=f"Item-{item_id}")

                # 保存价格历史
                saved_count = db.save_price_history(item_id, item_data)
                total_records += saved_count

                # 导出为JSON备份
                db.export_to_json(item_id)

                success_count += 1
                logger.info(f"商品 {item_id} 处理完成，保存了 {saved_count} 条价格记录")
            else:
                logger.warning(f"商品 {item_id} 没有获取到数据")

        except Exception as e:
            logger.error(f"处理商品 {item_id} 时出错: {e}")

    # 统计结果
    elapsed_time = time.time() - start_time
    logger.info(
        f"爬虫任务完成，处理成功 {success_count}/{total_items} 个商品，共保存 {total_records} 条价格记录"
    )
    logger.info(f"总耗时: {elapsed_time:.2f} 秒")

    return success_count, total_records


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
    # 设置日志
    setup_logging()
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="CS2行情数据爬虫和分析工具")
    parser.add_argument("--crawl", action="store_true", help="爬取数据")
    parser.add_argument("--test", action="store_true", help="测试图表")
    parser.add_argument("--date-range", action="store_true", help="按日期范围显示图表")
    parser.add_argument("--all", action="store_true", help="生成所有收藏商品的图表")
    parser.add_argument("--item-id", type=str, default="525873303", help="指定商品ID")
    parser.add_argument("--data-file", type=str, help="指定数据文件名（可选，默认使用最新的数据文件）")
    parser.add_argument("--indicator", type=str, choices=["all", "boll", "vegas"], 
                       default="all", help="指定要显示的技术指标")
    parser.add_argument("--start-date", type=str, help="开始日期 (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, help="结束日期 (YYYY-MM-DD)")
    args = parser.parse_args()
    
    if args.crawl:
        # 爬取数据
        crawl_and_save(args.data_file)
    elif args.test:
        # 测试图表
        test_chart_from_local(
            item_id=args.item_id,
            filename=args.data_file,
            indicator=args.indicator
        )
    elif args.date_range:
        # 按日期范围显示图表
        test_chart_by_date_range(
            item_id=args.item_id,
            filename=args.data_file,
            start_date=args.start_date,
            end_date=args.end_date,
            indicator=args.indicator
        )
    elif args.all:
        # 生成所有收藏商品的图表
        generate_all_charts(
            filename=args.data_file,
            start_date=args.start_date,
            end_date=args.end_date,
            indicator=args.indicator
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
