#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试查询功能的脚本
"""

import requests
import json

def test_query_functionality():
    """测试查询功能"""
    base_url = "http://localhost:5000"
    
    print("=== 测试查询功能 ===")
    
    # 测试1: 访问查询页面
    try:
        response = requests.get(f"{base_url}/query")
        if response.status_code == 200:
            print("✓ 查询页面访问成功")
        else:
            print(f"✗ 查询页面访问失败: {response.status_code}")
    except Exception as e:
        print(f"✗ 无法连接到服务器: {e}")
        return
    
    # 测试2: 测试API接口
    try:
        response = requests.get(f"{base_url}/api/data?table=customer_redemption_details&page=1&per_page=10")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ API接口正常，返回 {data.get('total_records', 0)} 条记录")
        else:
            print(f"✗ API接口失败: {response.status_code}")
    except Exception as e:
        print(f"✗ API接口错误: {e}")
    
    # 测试3: 测试搜索功能
    try:
        response = requests.get(f"{base_url}/api/data?table=customer_redemption_details&search=测试&page=1&per_page=10")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ 