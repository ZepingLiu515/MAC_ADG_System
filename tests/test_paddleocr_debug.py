#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
from pathlib import Path

# 修复 Windows 编码问题
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 测试 PaddleOCR 识别第一张截图
screenshot_dir = Path('data/visual_slices')
screenshots = list(screenshot_dir.glob('*.png'))

if not screenshots:
    print("[ERROR] 没有找到截图文件！")
    print(f"截图目录: {screenshot_dir}")
    exit(1)

test_image = screenshots[0]
print(f"[TEST] 测试图片: {test_image}")
print(f"[FILE] 文件大小: {test_image.stat().st_size / 1024:.2f} KB")

# 尝试用 PaddleOCR 识别
print("\n[INIT] 初始化 PaddleOCR...")
try:
    from paddleocr import PaddleOCR
    ocr = PaddleOCR(use_textline_orientation=True, lang='ch')
    print("[OK] PaddleOCR 初始化成功")
except Exception as e:
    print(f"[ERROR] PaddleOCR 初始化失败: {e}")
    exit(1)

# 执行识别
print(f"\n[OCR] 正在识别 {test_image}...")
try:
    result = ocr.predict(str(test_image))  # 改用 predict()
    print(f"\n[OK] 识别完成！")
    print(f"[TYPE] 返回结果类型: {type(result)}")
    print(f"[LEN] 返回结果长度: {len(result)}")
    
    if result:
        ocr_result = result[0]
        print(f"\n[OBJ] 第一个元素类型: {type(ocr_result)}")
        print(f"[OBJ] 元素长度: {len(ocr_result)}")
        
        # 探索 OCRResult 对象的结构
        print(f"\n[EXPLORE] OCRResult 对象的属性和方法:")
        print(f"[ATTRS] dir(ocr_result):")
        attrs = dir(ocr_result)
        for attr in attrs:
            if not attr.startswith('_'):
                print(f"  - {attr}")
        
        # 尝试获取数据
        print(f"\n[DATA] 尝试访问常见属性:")
        for attr_name in ['data', 'results', 'boxes', 'texts', 'predictions', '__dict__']:
            if hasattr(ocr_result, attr_name):
                try:
                    val = getattr(ocr_result, attr_name)
                    print(f"  [FOUND] {attr_name}: {type(val)} = {str(val)[:200]}")
                except Exception as e:
                    print(f"  [SKIP] {attr_name}: 获取失败 - {e}")
        
        # 尝试迭代得到结果
        print(f"\n[ITER] OCRResult 是字典对象，打印所有键值:")
        try:
            all_keys = list(ocr_result.keys())
            print(f"  [KEYS] 共 {len(all_keys)} 个键：")
            for key in all_keys:
                val = ocr_result[key]
                val_str = str(val)[:150] if not isinstance(val, (list, dict)) else f"<{type(val).__name__}>"
                print(f"    {key}: {type(val).__name__} = {val_str}")
            
            # 针对性检查可能包含文本的键
            print(f"\n[TEXT] 检查可能包含文字的键:")
            text_keys = ['ocr_text', 'text', 'rec_res', 'results', 'texts', 'recognition_result']
            for key in text_keys:
                if key in ocr_result:
                    val = ocr_result[key]
                    print(f"  [FOUND] {key}: {type(val).__name__}")
                    if isinstance(val, list) and len(val) > 0:
                        print(f"    第一项: {val[0]}")
                    elif isinstance(val, dict):
                        print(f"    键: {list(val.keys())[:5]}")
                    else:
                        print(f"    值: {str(val)[:200]}")
        
        except Exception as e:
            print(f"  [FAIL] 遍历失败: {e}")
            import traceback
            traceback.print_exc()
        
        # 如果 OCRResult 有 to_dict 或 to_json
        print(f"\n[CONVERT] 尝试转换为字典或 JSON:")
        if hasattr(ocr_result, 'to_dict'):
            try:
                data_dict = ocr_result.to_dict()
                print(f"  [OK] to_dict 成功:")
                for key in list(data_dict.keys())[:5]:
                    print(f"      {key}: {type(data_dict[key])}")
            except Exception as e:
                print(f"  [FAIL] to_dict 失败: {e}")
    
except Exception as e:
    print(f"[ERROR] 识别失败: {e}")
    import traceback
    traceback.print_exc()
