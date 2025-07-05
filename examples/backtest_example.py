#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
策略回测示例
"""

import sys
import os
import json
import logging
from datetime import datetime, timedelta
from typing import List

# 添加项目根目录到系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.analysis.backtest import BollingerStrategy, VegasStrategy
from config import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_market_data(filename: str = "market_data_shuli.json") -> dict:
    """从JSON文件加载市场数据"""
    load_path = os.path.join(settings.DATA_DIR, filename)
    with open(load_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    logger.info(f"已从 {load_path} 加载市场数据")
    return data

def run_strategy_backtest(strategy_class, raw_data: List, strategy_name: str):
    """
    运行策略回测
    
    Args:
        strategy_class: 策略类
        raw_data: 原始数据
        strategy_name: 策略名称
    """
    # 创建策略实例
    strategy = strategy_class(
        lookback_days=360,  # 回测周期
        cooldown_days=8,    # 冷却期
        tolerance=0.005     # 触碰容差
    )
    
    # 准备数据
    df = strategy.prepare_data(raw_data)
    
    # 运行回测
    results = strategy.run_backtest(df)
    
    # 打印结果
    strategy.print_results(results)

def main():
    """运行回测示例"""
    try:
        # 从JSON文件加载数据
        data = load_market_data()
        
        # 获取第一个商品的数据进行回测
        item_id = next(iter(data))
        raw_data = data[item_id]
        
        if not raw_data:
            logger.error("未获取到数据")
            return
        
        # 运行布林线策略回测
        print("\n=== 运行布林线策略回测 ===")
        run_strategy_backtest(BollingerStrategy, raw_data, "布林线策略")
        
        # 运行维加斯通道策略回测
        print("\n=== 运行维加斯通道策略回测 ===")
        run_strategy_backtest(VegasStrategy, raw_data, "维加斯通道策略")
        
    except Exception as e:
        logger.error(f"回测过程出错: {e}")

if __name__ == "__main__":
    main() 