#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
爬虫模块测试脚本
"""

import unittest
import json
import os
import time
from unittest.mock import patch, MagicMock

from src.crawler.spider import CS2MarketSpider
from src.storage.database import DatabaseManager
from config import settings


class MockResponse:
    """模拟请求响应"""
    def __init__(self, json_data, status_code=200):
        self.json_data = json_data
        self.status_code = status_code
        self.text = json.dumps(json_data)
    
    def json(self):
        return self.json_data
    
    def raise_for_status(self):
        if self.status_code != 200:
            raise Exception(f"HTTP错误: {self.status_code}")


def generate_mock_data(item_id, count=10):
    """生成模拟数据"""
    current_time = int(time.time())
    data = []
    
    for i in range(count):
        timestamp = current_time - (i * 86400)  # 每天一条数据
        data.append({
            'time': timestamp,
            'price': 100 + (i * 5),  # 模拟价格变化
            'volume': 10 + i
        })
    
    return {
        'code': 0,
        'message': 'success',
        'data': data
    }


class TestCrawler(unittest.TestCase):
    """爬虫模块测试类"""
    
    def setUp(self):
        """测试前的准备工作"""
        # 使用临时数据库文件
        self.test_db_path = os.path.join(settings.DATA_DIR, 'test_db.sqlite')
        
        # 确保测试目录存在
        os.makedirs(settings.DATA_DIR, exist_ok=True)
        
        # 如果测试数据库已存在，则删除
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
        
        # 初始化测试数据库
        self.db = DatabaseManager(self.test_db_path)
        
        # 初始化爬虫
        self.spider = CS2MarketSpider()
        
        # 测试商品ID
        self.test_item_id = '12345'
    
    def tearDown(self):
        """测试后的清理工作"""
        # 删除测试数据库
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
    
    @patch('requests.get')
    def test_get_item_data(self, mock_get):
        """测试获取商品数据"""
        # 模拟请求响应
        mock_data = generate_mock_data(self.test_item_id)
        mock_get.return_value = MockResponse(mock_data)
        
        # 调用被测试的方法
        result = self.spider.get_item_data(self.test_item_id)
        
        # 验证结果
        self.assertIsNotNone(result)
        self.assertEqual(result['code'], 0)
        self.assertEqual(len(result['data']), 10)
    
    @patch('requests.get')
    def test_get_item_history(self, mock_get):
        """测试获取商品历史数据"""
        # 模拟多次请求响应
        mock_data1 = generate_mock_data(self.test_item_id, 10)
        mock_data2 = generate_mock_data(self.test_item_id, 5)
        mock_data3 = {'code': 0, 'message': 'success', 'data': []}  # 空数据，结束循环
        
        mock_get.side_effect = [
            MockResponse(mock_data1),
            MockResponse(mock_data2),
            MockResponse(mock_data3)
        ]
        
        # 设置较小的目标天数，以便测试
        self.spider.CATEGORY_MONTH = 15
        
        # 调用被测试的方法
        result = self.spider.get_item_history(self.test_item_id)
        
        # 验证结果
        self.assertEqual(len(result), 15)  # 10 + 5 = 15条数据
    
    def test_save_and_retrieve_data(self):
        """测试数据保存和检索"""
        # 生成测试数据
        test_data = generate_mock_data(self.test_item_id)['data']
        
        # 保存商品信息
        self.db.save_item(self.test_item_id, name=f"TestItem-{self.test_item_id}")
        
        # 保存价格历史
        saved_count = self.db.save_price_history(self.test_item_id, test_data)
        
        # 验证保存结果
        self.assertEqual(saved_count, 10)
        
        # 检索价格历史
        retrieved_data = self.db.get_item_price_history(self.test_item_id)
        
        # 验证检索结果
        self.assertEqual(len(retrieved_data), 10)
        
        # 测试导出功能
        export_path = os.path.join(settings.DATA_DIR, f"test_export_{self.test_item_id}.json")
        export_success = self.db.export_to_json(self.test_item_id, export_path)
        
        # 验证导出结果
        self.assertTrue(export_success)
        self.assertTrue(os.path.exists(export_path))
        
        # 清理导出文件
        if os.path.exists(export_path):
            os.remove(export_path)


if __name__ == '__main__':
    unittest.main() 