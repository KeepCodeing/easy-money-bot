from typing import Dict, Any, List
from collections import defaultdict

def get_strategy_shorthand(strategy_name: str) -> str:
    """将完整的策略名称转换为简写。"""
    if 'vegas' in strategy_name.lower():
        return 'Vegas'
    if 'macd' in strategy_name.lower():
        return 'MACD'
    if 'bollinger' in strategy_name.lower():
        return 'Boll'
    if 'rsi' in strategy_name.lower():
        return 'RSI'
    if 'csma' in strategy_name.lower():
        return 'CsMa'
    return 'Unknown'

def format_signals_to_simplified_table(data: Dict[str, Any]) -> str:
    """将信号字典格式化为简化的字符串表格。"""
    output_lines = []

    for fav_name, signals_by_type in data.items():
        output_lines.append(f"========== 收藏夹: {fav_name} ==========")
        
        for signal_type, items in signals_by_type.items():
            # 1. 聚合处理：按商品名称分组，合并策略和价格
            aggregated_items = defaultdict(lambda: {'strategies': set(), 'prices': []})
            for item_name, signals in items.items():
                if not signals:
                    continue
                for signal in signals:
                    shorthand = get_strategy_shorthand(signal['strategy'])
                    aggregated_items[item_name]['strategies'].add(shorthand)
                    aggregated_items[item_name]['prices'].append(signal['price'])
            
            if not aggregated_items:
                continue

            type_str = "📈 买入信号 (Buy Signals)" if signal_type == 'buy' else "📉 卖出信号 (Sell Signals)"
            output_lines.append(f"\n--- {type_str} ---\n")

            # 2. 准备表格数据并计算列宽
            header = ["商品名称", "策略组合", "触发价格"]
            rows = []
            for item_name, agg_data in aggregated_items.items():
                # 将策略集合拼接成字符串
                strategy_str = "/".join(sorted(list(agg_data['strategies'])))
                # 将价格列表拼接成字符串
                price_str = ", ".join(f"{p:.2f}" for p in agg_data['prices'])
                rows.append([item_name, strategy_str, price_str])

            # 3. 动态计算列宽 (处理中文字符)
            def get_str_width(s):
                width = 0
                for char in s:
                    width += 2 if '\u4e00' <= char <= '\u9fff' else 1
                return width
            
            col_widths = [get_str_width(h) for h in header]
            for row in rows:
                for i, cell in enumerate(row):
                    col_widths[i] = max(col_widths[i], get_str_width(cell))

            # 4. 格式化并输出表格
            header_line = " | ".join(header[i].ljust(col_widths[i] - (get_str_width(header[i]) - len(header[i]))) for i in range(len(header)))
            separator = "-+-".join("-" * col_widths[i] for i in range(len(header)))
            output_lines.append(header_line)
            output_lines.append(separator)

            for row in rows:
                row_line = " | ".join(row[i].ljust(col_widths[i] - (get_str_width(row[i]) - len(row[i]))) for i in range(len(row)))
                output_lines.append(row_line)

    return "\n".join(output_lines)