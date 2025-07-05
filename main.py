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

from src.crawler.spider import CS2MarketSpider
from src.storage.database import DatabaseManager
from config import settings
from src.analysis.chart import KLineChart
from src.analysis.data_cleaner import MarketDataCleaner
from src.analysis.indicators import IndicatorType

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


def save_market_data(data: dict, filename: str = "market_data.json"):
    """保存市场数据到JSON文件"""
    save_path = os.path.join("data", filename)
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"市场数据已保存到: {save_path}")


def load_market_data(filename: str = "market_data.json") -> dict:
    """从JSON文件加载市场数据"""
    load_path = os.path.join("data", filename)
    with open(load_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    logger.info(f"已从 {load_path} 加载市场数据")
    return data


def test_chart_from_local(item_id: str = "525873303", 
                         filename: str = "market_data.json",
                         indicator: str = "all"):
    """从本地JSON文件读取数据并绘制K线图"""
    try:
        # 加载数据
        data = load_market_data(filename)
        
        if item_id not in data:
            logger.error(f"未找到商品 {item_id} 的数据")
            return
            
        # 清理数据
        cleaned_data = MarketDataCleaner.clean_kline_data(data[item_id])
        
        # 确定要显示的指标类型
        indicator_type = IndicatorType.ALL
        if indicator.lower() == "boll":
            indicator_type = IndicatorType.BOLL
        elif indicator.lower() == "vegas":
            indicator_type = IndicatorType.VEGAS
        
        # 创建并显示图表
        chart = KLineChart(days_to_show=30)
        fig = chart.plot_candlestick(
            item_id, 
            cleaned_data,
            indicator_type=indicator_type
        )
        
        if fig:
            fig.show()
            fig.waitforbuttonpress()
        else:
            logger.error("创建图表失败")
            
    except Exception as e:
        logger.error(f"测试图表时出错: {e}")


def crawl_and_save():
    """爬取数据并保存到数据库"""
    logger.info("开始执行爬虫任务")
    start_time = time.time()

    # 初始化爬虫和数据库
    spider = CS2MarketSpider()

    # 爬取数据
    result = spider.crawl_all_items()
    
    # 保存数据到JSON
    save_market_data(result)
    
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


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="CS2市场数据爬虫")
    parser.add_argument("--crawl", action="store_true", help="执行爬虫任务")
    parser.add_argument("--export", action="store_true", help="导出数据为JSON")
    parser.add_argument("--test-chart", action="store_true", help="从本地数据测试K线图")
    parser.add_argument("--item-id", type=str, help="指定商品ID")
    parser.add_argument("--data-file", type=str, default="market_data.json", help="指定数据文件名")
    parser.add_argument("--indicator", type=str, choices=["all", "boll", "vegas"], 
                       default="all", help="指定要显示的技术指标")

    args = parser.parse_args()

    if args.crawl:
        crawl_and_save()
    elif args.export and args.item_id:
        db = DatabaseManager()
        success = db.export_to_json(args.item_id)
        if success:
            logger.info(f"商品 {args.item_id} 数据导出成功")
        else:
            logger.error(f"商品 {args.item_id} 数据导出失败")
    elif args.test_chart:
        item_id = args.item_id if args.item_id else "525873303"
        test_chart_from_local(item_id, args.data_file, args.indicator)
    else:
        # 默认执行爬虫任务
        crawl_and_save()


if __name__ == "__main__":
    main()
