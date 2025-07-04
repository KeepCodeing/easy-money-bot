#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
数据存储模块，负责数据的持久化存储
"""

import os
import json
import sqlite3
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from config import settings

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"{settings.LOG_DIR}/storage.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("storage")


class DatabaseManager:
    """数据库管理类，处理SQLite数据库操作"""
    
    def __init__(self, db_path: str = settings.DB_PATH):
        """
        初始化数据库管理器
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self._initialize_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 使查询结果可以通过列名访问
        return conn
    
    def _initialize_db(self) -> None:
        """初始化数据库表结构"""
        logger.info(f"初始化数据库: {self.db_path}")
        
        # 确保数据库目录存在
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 创建商品表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id TEXT PRIMARY KEY,
            name TEXT,
            last_updated INTEGER,
            extra_info TEXT
        )
        ''')
        
        # 创建价格历史表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id TEXT,
            timestamp INTEGER,
            price REAL,
            volume INTEGER,
            FOREIGN KEY (item_id) REFERENCES items (id),
            UNIQUE (item_id, timestamp)
        )
        ''')
        
        # 创建交易信号表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS trading_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id TEXT,
            timestamp INTEGER,
            signal_type TEXT,
            strategy TEXT,
            price REAL,
            confidence REAL,
            FOREIGN KEY (item_id) REFERENCES items (id)
        )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("数据库初始化完成")
    
    def save_item(self, item_id: str, name: Optional[str] = None, extra_info: Optional[Dict] = None) -> bool:
        """
        保存或更新商品信息
        
        Args:
            item_id: 商品ID
            name: 商品名称
            extra_info: 额外信息（将被转换为JSON存储）
            
        Returns:
            操作是否成功
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # 转换额外信息为JSON字符串
            extra_info_json = json.dumps(extra_info) if extra_info else None
            
            # 更新或插入商品信息
            cursor.execute('''
            INSERT OR REPLACE INTO items (id, name, last_updated, extra_info)
            VALUES (?, ?, ?, ?)
            ''', (item_id, name, int(datetime.now().timestamp()), extra_info_json))
            
            conn.commit()
            conn.close()
            logger.info(f"商品信息保存成功: {item_id}")
            return True
        except Exception as e:
            logger.error(f"保存商品信息失败: {e}")
            return False
    
    def save_price_history(self, item_id: str, price_data: List[Dict]) -> int:
        """
        保存价格历史数据
        
        Args:
            item_id: 商品ID
            price_data: 价格历史数据列表，每个元素应包含timestamp和price字段
            
        Returns:
            成功保存的记录数量
        """
        if not price_data:
            logger.warning(f"没有价格数据需要保存: {item_id}")
            return 0
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # 确保商品存在
            cursor.execute("SELECT id FROM items WHERE id = ?", (item_id,))
            if cursor.fetchone() is None:
                self.save_item(item_id)
            
            # 插入价格历史数据
            saved_count = 0
            for data in price_data:
                try:
                    timestamp = data.get('time')
                    price = data.get('price')
                    volume = data.get('volume', 0)
                    
                    if timestamp and price is not None:
                        cursor.execute('''
                        INSERT OR IGNORE INTO price_history (item_id, timestamp, price, volume)
                        VALUES (?, ?, ?, ?)
                        ''', (item_id, timestamp, price, volume))
                        
                        if cursor.rowcount > 0:
                            saved_count += 1
                except Exception as e:
                    logger.error(f"保存单条价格数据失败: {e}, 数据: {data}")
            
            conn.commit()
            conn.close()
            logger.info(f"价格历史数据保存成功: {item_id}, 新增 {saved_count} 条记录")
            return saved_count
        except Exception as e:
            logger.error(f"保存价格历史数据失败: {e}")
            return 0
    
    def save_trading_signal(self, item_id: str, signal_type: str, strategy: str, 
                           price: float, timestamp: Optional[int] = None, 
                           confidence: float = 1.0) -> bool:
        """
        保存交易信号
        
        Args:
            item_id: 商品ID
            signal_type: 信号类型（如'buy', 'sell', 'hold'）
            strategy: 策略名称
            price: 信号触发时的价格
            timestamp: 时间戳，默认为当前时间
            confidence: 信号置信度（0-1）
            
        Returns:
            操作是否成功
        """
        if timestamp is None:
            timestamp = int(datetime.now().timestamp())
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            INSERT INTO trading_signals 
            (item_id, timestamp, signal_type, strategy, price, confidence)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (item_id, timestamp, signal_type, strategy, price, confidence))
            
            conn.commit()
            conn.close()
            logger.info(f"交易信号保存成功: {item_id}, 类型: {signal_type}, 策略: {strategy}")
            return True
        except Exception as e:
            logger.error(f"保存交易信号失败: {e}")
            return False
    
    def get_item_price_history(self, item_id: str, start_time: Optional[int] = None, 
                              end_time: Optional[int] = None) -> List[Dict]:
        """
        获取商品价格历史
        
        Args:
            item_id: 商品ID
            start_time: 开始时间戳
            end_time: 结束时间戳
            
        Returns:
            价格历史数据列表
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            query = "SELECT timestamp, price, volume FROM price_history WHERE item_id = ?"
            params = [item_id]
            
            if start_time is not None:
                query += " AND timestamp >= ?"
                params.append(start_time)
            
            if end_time is not None:
                query += " AND timestamp <= ?"
                params.append(end_time)
            
            query += " ORDER BY timestamp ASC"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            result = [dict(row) for row in rows]
            conn.close()
            
            logger.info(f"获取商品价格历史成功: {item_id}, 共 {len(result)} 条记录")
            return result
        except Exception as e:
            logger.error(f"获取商品价格历史失败: {e}")
            return []
    
    def get_latest_signals(self, limit: int = 10) -> List[Dict]:
        """
        获取最新的交易信号
        
        Args:
            limit: 返回的最大记录数
            
        Returns:
            最新的交易信号列表
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT ts.*, i.name as item_name
            FROM trading_signals ts
            JOIN items i ON ts.item_id = i.id
            ORDER BY ts.timestamp DESC
            LIMIT ?
            ''', (limit,))
            
            rows = cursor.fetchall()
            result = [dict(row) for row in rows]
            conn.close()
            
            logger.info(f"获取最新交易信号成功: {len(result)} 条记录")
            return result
        except Exception as e:
            logger.error(f"获取最新交易信号失败: {e}")
            return []
    
    def export_to_json(self, item_id: str, file_path: Optional[str] = None) -> bool:
        """
        将商品数据导出为JSON文件
        
        Args:
            item_id: 商品ID
            file_path: 导出文件路径，默认为data/{item_id}.json
            
        Returns:
            操作是否成功
        """
        if file_path is None:
            file_path = os.path.join(settings.DATA_DIR, f"{item_id}.json")
        
        try:
            # 获取商品信息
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM items WHERE id = ?", (item_id,))
            item = cursor.fetchone()
            
            if not item:
                logger.warning(f"商品不存在: {item_id}")
                return False
            
            # 获取价格历史
            cursor.execute(
                "SELECT timestamp, price, volume FROM price_history WHERE item_id = ? ORDER BY timestamp ASC", 
                (item_id,)
            )
            price_history = [dict(row) for row in cursor.fetchall()]
            
            # 获取交易信号
            cursor.execute(
                "SELECT timestamp, signal_type, strategy, price, confidence FROM trading_signals WHERE item_id = ? ORDER BY timestamp ASC", 
                (item_id,)
            )
            trading_signals = [dict(row) for row in cursor.fetchall()]
            
            conn.close()
            
            # 构建导出数据
            export_data = {
                "item_id": item_id,
                "name": item["name"],
                "last_updated": item["last_updated"],
                "extra_info": json.loads(item["extra_info"]) if item["extra_info"] else None,
                "price_history": price_history,
                "trading_signals": trading_signals
            }
            
            # 写入JSON文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"数据成功导出到: {file_path}")
            return True
        except Exception as e:
            logger.error(f"导出数据失败: {e}")
            return False


# 初始化数据库的辅助函数
def init_db():
    """初始化数据库"""
    db = DatabaseManager()
    logger.info("数据库初始化完成")
    return db


if __name__ == "__main__":
    # 简单测试
    db = init_db()
    print("数据库初始化完成") 