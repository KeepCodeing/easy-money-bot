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
from typing import List, Dict, Union
import pandas as pd

# 添加项目根目录到系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.analysis.backtest import BollingerStrategy, BollingerMidlineStrategy, VegasStrategy
from config import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_market_data() -> dict:
    """
    从data目录下最新的时间戳文件夹中加载所有json文件数据
    
    Returns:
        所有商品数据的字典，格式为：
        {
            'item_id': {
                'name': str,
                'data': List[List[Union[int, float]]]  # [[timestamp, open, close, high, low, volume, amount], ...]
            }
        }
    """
    try:
        # 获取data目录下所有文件夹
        data_dir = settings.DATA_DIR
        if not os.path.exists(data_dir):
            logger.error(f"数据目录不存在: {data_dir}")
            return {}
            
        # 获取所有时间戳文件夹
        timestamp_dirs = [
            d for d in os.listdir(data_dir)
            if os.path.isdir(os.path.join(data_dir, d)) and d.isdigit()
        ]
        
        if not timestamp_dirs:
            logger.error(f"未找到时间戳文件夹在: {data_dir}")
            return {}
            
        # 获取最新的时间戳文件夹
        latest_dir = max(timestamp_dirs)
        latest_path = os.path.join(data_dir, latest_dir)
        logger.info(f"使用最新的数据目录: {latest_path}")
        
        # 读取所有json文件
        all_data = {}
        json_files = [f for f in os.listdir(latest_path) if f.endswith('.json')]
        
        if not json_files:
            logger.error(f"目录中没有找到JSON文件: {latest_path}")
            return {}
            
        for json_file in json_files:
            file_path = os.path.join(latest_path, json_file)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                # 验证数据格式
                if not isinstance(data, dict):
                    logger.error(f"文件格式错误 {json_file}: 根对象必须是字典")
                    continue
                    
                item_id = data.get('item_id')
                name = data.get('name')
                kline_data = data.get('data', [])
                
                if not item_id or not name or not kline_data:
                    logger.error(f"文件数据不完整 {json_file}: 缺少必要字段")
                    continue
                
                # 验证K线数据格式
                if not isinstance(kline_data, list):
                    logger.error(f"文件数据格式错误 {json_file}: K线数据必须是列表")
                    continue
                
                # 验证每个K线数据点
                valid_data = []
                for point in kline_data:
                    if not isinstance(point, list) or len(point) != 7:
                        logger.warning(f"跳过无效的K线数据点: {point}")
                        continue
                    try:
                        # 转换数据类型
                        timestamp = int(point[0])
                        open_price = float(point[1])
                        close = float(point[2])
                        high = float(point[3])
                        low = float(point[4])
                        volume = float(point[5])
                        amount = float(point[6])
                        valid_data.append([timestamp, open_price, close, high, low, volume, amount])
                    except (ValueError, TypeError) as e:
                        logger.warning(f"数据点转换失败: {e}")
                        continue
                
                if not valid_data:
                    logger.error(f"文件 {json_file} 没有有效的K线数据")
                    continue
                
                # 保存有效数据
                all_data[item_id] = {
                    'name': name,
                    'data': valid_data
                }
                logger.info(f"已加载商品数据: {name} (ID: {item_id}), 共 {len(valid_data)} 个K线")
                
            except Exception as e:
                logger.error(f"加载文件失败 {json_file}: {e}")
                continue
        
        if not all_data:
            logger.error("没有成功加载任何商品数据")
            return {}
            
        logger.info(f"共加载了 {len(all_data)} 个商品的数据")
        return all_data
        
    except Exception as e:
        logger.error(f"加载市场数据失败: {e}")
        return {}

def run_strategy_backtest(strategy_class, raw_data: List, item_name: str, show_days: int = settings.CHART_DAYS) -> Dict:
    """
    运行策略回测
    
    Args:
        strategy_class: 策略类
        raw_data: K线数据列表，格式为 [[timestamp, open, close, high, low, volume, amount], ...]
        item_name: 商品名称
        show_days: 图表显示的天数（默认30天）
        
    Returns:
        回测结果统计
    """
    try:
        # 创建策略实例
        strategy = strategy_class(
            lookback_days=360,  # 回测周期
            cooldown_days=8,    # 冷却期
            tolerance=settings.BOLL_TOLERANCE,    # 触碰容差
            show_days=show_days # 图表显示天数
        )
        
        # 准备数据
        df = strategy.prepare_data(raw_data)
        if df.empty:
            logger.error(f"商品 {item_name} 的数据准备失败")
            return {
                'name': item_name,
                'win_rate': 0.0,
                'total_trades': 0,
                'total_profit': 0.0,
                'midline_score': 0
            }
        
        # 运行回测
        results = strategy.run_backtest(df)
        
        # 打印结果
        strategy.print_results(results)
        
        # 返回统计结果
        stats = results['stats']
        stats['name'] = item_name
        return stats
        
    except Exception as e:
        logger.error(f"运行回测失败 {item_name}: {e}")
        return {
            'name': item_name,
            'win_rate': 0.0,
            'total_trades': 0,
            'total_profit': 0.0,
            'midline_score': 0
        }

def save_results_to_markdown(results: List[Dict], output_file: str):
    """
    将回测结果保存为markdown文件
    
    Args:
        results: 回测结果列表
        output_file: 输出文件路径
    """
    # 创建markdown表格
    markdown = "# 策略回测结果\n\n"
    markdown += "## 布林线策略回测结果\n\n"
    markdown += "| 商品名称 | 胜率 | 交易次数 | 总收益 | 中轨触碰得分 |\n"
    markdown += "|---------|------|----------|--------|------------|\n"
    
    # 添加每个商品的结果
    for result in results:
        # 处理商品名称中的特殊字符
        name = result['name'].replace('|', '&#124;')  # 转义竖线字符
        
        # 格式化数字
        win_rate = f"{result['win_rate']:.1f}" if result['win_rate'] > 0 else "0.0"
        total_trades = str(result['total_trades'])
        total_profit = f"{result['total_profit']:.2f}" if result['total_profit'] != 0 else "0.00"
        midline_score = str(result.get('midline_score', 0))
        
        # 构建表格行
        markdown += (
            f"| {name} | "
            f"{win_rate}% | "
            f"{total_trades} | "
            f"{total_profit} | "
            f"{midline_score} |\n"
        )
    
    # 添加统计信息
    if results:
        markdown += "\n### 汇总统计\n\n"
        total_items = len(results)
        avg_win_rate = sum(r['win_rate'] for r in results) / total_items
        total_trades = sum(r['total_trades'] for r in results)
        total_profit = sum(r['total_profit'] for r in results)
        total_scores = sum(r.get('midline_score', 0) for r in results)
        
        markdown += f"- 总商品数: {total_items}\n"
        markdown += f"- 平均胜率: {avg_win_rate:.1f}%\n"
        markdown += f"- 总交易次数: {total_trades}\n"
        markdown += f"- 总收益: {total_profit:.2f}\n"
        markdown += f"- 总中轨触碰得分: {total_scores}\n"
    
    # 保存到文件
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(markdown)
    logger.info(f"回测结果已保存到: {output_file}")

def main():
    """运行回测示例"""
    try:
        # 从JSON文件加载数据
        data = load_market_data()
        if not data:
            logger.error("未能加载任何数据，退出程序")
            return
            
        results = []
        
        # 遍历每个商品进行回测
        for item_id, raw_data in data.items():
            if not raw_data:
                logger.warning(f"商品 {item_id} 没有数据")
                continue
            
            item_name = raw_data.get('name', item_id)
            item_data = raw_data.get('data', [])
            
            if not item_data:
                logger.warning(f"商品 {item_name} 没有交易数据")
                continue
            
            print(f"\n=== 商品: {item_name} ===")
            
            # 运行布林线策略回测
            print("\n--- 运行布林线策略回测 ---")
            bollinger_stats = run_strategy_backtest(
                BollingerStrategy,
                item_data,
                item_name,
                show_days=settings.CHART_DAYS  # 显示60天的数据
            )

            exit(0)
            
            # 运行布林线中轨触碰策略回测
            print("\n--- 运行布林线中轨触碰策略回测 ---")
            midline_stats = run_strategy_backtest(
                BollingerMidlineStrategy,
                item_data,
                item_name,
                show_days=settings.CHART_DAYS  # 显示60天的数据
            )
            
            # 合并结果
            results.append(midline_stats)  # 使用带有中轨触碰得分的结果
        
        if results:
            # 保存结果到markdown文件
            output_file = os.path.join(settings.DATA_DIR, "backtest_results.md")
            save_results_to_markdown(results, output_file)
        else:
            logger.error("没有生成任何回测结果")
        
    except Exception as e:
        logger.error(f"回测过程出错: {e}")

if __name__ == "__main__":
    main() 