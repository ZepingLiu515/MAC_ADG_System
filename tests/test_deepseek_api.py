#!/usr/bin/env python3
"""测试 DeepSeek API 连通性和端点有效性"""

import os
import sys
import requests
import base64
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('DEEPSEEK_API_KEY')
BASE_URL = 'https://api.deepseek.com/v1'

def test_api_key():
    """测试 API Key 是否有效"""
    print("=" * 60)
    print("测试 1: API Key 配置")
    print("=" * 60)
    
    if not API_KEY:
        print("❌ 错误: DEEPSEEK_API_KEY 未设置")
        return False
    
    print(f"✅ API Key 已配置: {API_KEY[:20]}...")
    return True

def test_chat_endpoint():
    """测试 chat/completions 端点"""
    print("\n" + "=" * 60)
    print("测试 2: DeepSeek Chat 端点")
    print("=" * 60)
    
    if not API_KEY:
        print("❌ 跳过: API Key 未配置")
        return False
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "user", "content": "Hello, 请返回 'OK'"}
        ],
        "max_tokens": 100,
        "temperature": 0.3
    }
    
    url = f"{BASE_URL}/chat/completions"
    print(f"📡 发送请求到: {url}")
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        print(f"📊 状态码: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Chat 端点可用")
            result = response.json()
            content = result['choices'][0]['message']['content']
            print(f"✅ 响应内容: {content[:100]}")
            return True
        else:
            print(f"❌ 请求失败: {response.status_code}")
            print(f"📋 响应: {response.text[:500]}")
            return False
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False

def test_vision_endpoint():
    """测试 chat 端点是否支持 vision"""
    print("\n" + "=" * 60)
    print("测试 3: DeepSeek Vision 支持 (chat 端点)")
    print("=" * 60)
    
    if not API_KEY:
        print("❌ 跳过: API Key 未配置")
        return False
    
    # 尝试使用本地一个小图片
    test_image_path = Path("data/visual_slices/10.1038_s41586-020-2649-2.png")
    if not test_image_path.exists():
        print(f"⚠️  测试图片不存在: {test_image_path}")
        # 创建一个简单的 1x1 PNG 用于测试
        import base64
        # 这是一个 1x1 的透明 PNG
        png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        image_base64 = base64.b64encode(png_data).decode('utf-8')
    else:
        with open(test_image_path, 'rb') as f:
            image_base64 = base64.b64encode(f.read()).decode('utf-8')
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "user", 
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
                    {"type": "text", "text": "这是什么图片? 仅返回'PNG'或'图片'"}
                ]
            }
        ],
        "max_tokens": 100,
        "temperature": 0.0
    }
    
    url = f"{BASE_URL}/chat/completions"
    print(f"📡 发送 vision 请求到: {url}")
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        print(f"📊 状态码: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Vision 功能可用")
            result = response.json()
            content = result['choices'][0]['message']['content']
            print(f"✅ 响应内容: {content[:100]}")
            return True
        else:
            print(f"❌ Vision 请求失败: {response.status_code}")
            print(f"📋 响应: {response.text[:500]}")
            return False
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False

def test_ocr_endpoints():
    """测试 OCR 专用端点"""
    print("\n" + "=" * 60)
    print("测试 4: DeepSeek OCR 端点")
    print("=" * 60)
    
    if not API_KEY:
        print("❌ 跳过: API Key 未配置")
        return False
    
    # 尝试加载测试图片
    test_image_path = Path("data/visual_slices/10.1038_s41586-020-2649-2.png")
    if not test_image_path.exists():
        print(f"⚠️  测试图片不存在: {test_image_path}")
        return False
    
    with open(test_image_path, 'rb') as f:
        image_base64 = base64.b64encode(f.read()).decode('utf-8')
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    ocr_endpoints = [
        f"{BASE_URL}/vision/ocr",
        f"{BASE_URL}/ocr",
        f"{BASE_URL}/v1/ocr",
        f"{BASE_URL}/images/ocr"
    ]
    
    payload = {
        "image": f"data:image/png;base64,{image_base64}",
        "language": "auto"
    }
    
    for endpoint in ocr_endpoints:
        print(f"\n  📡 尝试: {endpoint}")
        try:
            response = requests.post(endpoint, headers=headers, json=payload, timeout=10)
            print(f"  📊 状态码: {response.status_code}")
            if response.status_code == 200:
                print(f"  ✅ 成功!")
                print(f"  📋 响应: {response.json()}")
                return True
            else:
                print(f"  ❌ 失败: {response.text[:200]}")
        except Exception as e:
            print(f"  ❌ 异常: {str(e)[:100]}")
    
    print("\n❌ 所有 OCR 端点都不可用")
    return False

if __name__ == '__main__':
    results = []
    
    results.append(("API Key 配置", test_api_key()))
    results.append(("Chat 端点", test_chat_endpoint()))
    results.append(("Vision 功能", test_vision_endpoint()))
    results.append(("OCR 端点", test_ocr_endpoints()))
    
    print("\n" + "=" * 60)
    print("📊 测试总结")
    print("=" * 60)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name:20} {status}")
    
    passed = sum(1 for _, r in results if r)
    print(f"\n总体: {passed}/{len(results)} 通过")
    
    sys.exit(0 if passed > 0 else 1)
