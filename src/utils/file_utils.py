#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
文件处理工具模块
"""

import re

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