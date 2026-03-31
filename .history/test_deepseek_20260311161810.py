#!/usr/bin/env python
"""测试 DeepSeek API 连接"""
import os
import base64
import requests
from dotenv import load_dotenv
from PIL import Image
import io

load_dotenv()

print("=" * 70)
print("🧪 DeepSeek VLM API 测试")
print("=" * 70)

# 1. 检查配置
api_key = os.getenv('DEEPSEEK_API_KEY')
model = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
base_url = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com/v1')

print(f"\n✅ 配置检查:")
print(f"  API Key: {api_key[:20]}..." if api_key else "  ❌ API Key 未设置")
print(f"  模型: {model}")
print(f"  Base URL: {base_url}")

# 2. 创建测试图片
print(f"\n🖼️  创建测试图片...")
img = Image.new('RGB', (100, 100), color='white')
buf = io.BytesIO()
img.save(buf, format='PNG')
image_data = base64.b64encode(buf.getvalue()).decode('utf-8')
print(f"  图片大小: {len(image_data)} 字符")

# 3. 调用 API
print(f"\n🌐 调用 DeepSeek API...")
headers = {
    'Authorization': f'Bearer {api_key}',
    'Content-Type': 'application/json'
}

payload = {
    'model': model,
    'messages': [{
        'role': 'user',
        'content': [
            {
                'type': 'image_url',
                'image_url': {
                    'url': f'data:image/png;base64,{image_data}'
                }
            },
            {
                'type': 'text',
                'text': '这是什么？'
            }
        ]
    }],
    'max_tokens': 100
}

try:
    url = f"{base_url}/chat/completions"
    print(f"  调用 URL: {url}")
    
    r = requests.post(url, headers=headers, json=payload, timeout=30)
    
    print(f"\n📊 响应:")
    print(f"  状态码: {r.status_code}")
    
    if r.status_code == 200:
        print(f"  ✅ API 调用成功!")
        data = r.json()
        reply = data['choices'][0]['message']['content']
        print(f"  回复: {reply[:100]}")
    else:
        print(f"  ❌ API 错误 ({r.status_code}):")
        print(f"  {r.text[:300]}")
        
except Exception as e:
    print(f"\n❌ 异常: {e}")

print("\n" + "=" * 70)
