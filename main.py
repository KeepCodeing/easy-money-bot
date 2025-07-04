#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
主程序入口，整合爬虫和数据存储功能
"""

import os
import time
import logging
import argparse
from datetime import datetime

from src.crawler.spider import CS2MarketSpider
from src.storage.database import DatabaseManager
from config import settings

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"{settings.LOG_DIR}/main.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("main")


def crawl_and_save():
    """爬取数据并保存到数据库"""
    logger.info("开始执行爬虫任务")
    start_time = time.time()
    
    # 初始化爬虫和数据库
    spider = CS2MarketSpider()
    
    spider.crawl_all_items()
    
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
    logger.info(f"爬虫任务完成，处理成功 {success_count}/{total_items} 个商品，共保存 {total_records} 条价格记录")
    logger.info(f"总耗时: {elapsed_time:.2f} 秒")
    
    return success_count, total_records


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="CS2市场数据爬虫")
    parser.add_argument("--crawl", action="store_true", help="执行爬虫任务")
    parser.add_argument("--export", action="store_true", help="导出数据为JSON")
    parser.add_argument("--item-id", type=str, help="指定商品ID")
    
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
    else:
        # 默认执行爬虫任务
        crawl_and_save()


if __name__ == "__main__":
    main() 