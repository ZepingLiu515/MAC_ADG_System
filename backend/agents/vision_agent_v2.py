"""
【Vision Agent V2.0 - 纯视觉分析】

职责（精简版）：
1. 输入：截图文件路径
2. 过程：OCR/VLM 识别 → 结构化提取
3. 输出：结构化作者数据 {name, affiliation, is_corresponding, is_co_first}

不处理任何网页相关的操作，这些都由 WebDriver 处理。
"""

import os
import json

try:
    from paddleocr import PaddleOCR
except ImportError:
    PaddleOCR = None

import requests
from config import DEEPSEEK_API_KEY, DEEPSEEK_MODEL, DEEPSEEK_BASE_URL


class VisionAgent:
    """纯视觉分析智能体 - 只做 OCR 和结构化提取"""
    
    def __init__(self):
        pass
    
    def analyze_screenshot(self, image_path: str) -> dict:
        """
        分析截图，提取结构化的作者信息
        
        输入：截图文件路径
        输出：{
            'text': 识别的原始文本,
            'authors': [
                {'name': '张三', 'affiliation': '清华大学', 'is_corresponding': False, 'is_co_first': False},
                ...
            ]
        }
        """
        
        if not os.path.exists(image_path):
            print(f"[Vision] ❌ 截图不存在: {image_path}")
            return {'text': '', 'authors': []}
        
        print(f"[Vision] 📸 分析截图: {image_path}")
        
        # 第一步：OCR 识别文本
        ocr_text = self._extract_text(image_path)
        if not ocr_text:
            print(f"[Vision] ⚠️ OCR 识别失败")
            return {'text': '', 'authors': []}
        
        print(f"[Vision] ✅ OCR 识别成功，文本长度: {len(ocr_text)}")
        
        # 第二步：从文本中提取结构化作者信息
        authors = self._extract_authors_structure(ocr_text)
        
        print(f"[Vision] ✅ 提取了 {len(authors)} 位作者")
        
        return {
            'text': ocr_text,
            'authors': authors
        }
    
    def _extract_text(self, image_path: str) -> str or None:
        """
        【核心方法 1】使用 OCR 识别截图中的文本
        
        优先级：
        1. 本地 PaddleOCR（免费、快速、支持中英文）
        2. DeepSeek API（备选）
        """
        
        # 方案 1：本地 PaddleOCR
        if PaddleOCR is not None:
            print(f"[Vision] 📝 使用 PaddleOCR 识别...")
            try:
                ocr = PaddleOCR(use_textline_orientation=True, lang='ch')
                result = ocr.predict(str(image_path))
                
                if result and len(result) > 0:
                    ocr_result = result[0]
                    
                    if 'rec_texts' in ocr_result and 'rec_scores' in ocr_result:
                        texts = ocr_result['rec_texts']
                        scores = ocr_result['rec_scores']
                        
                        # 过滤低置信度的文本
                        filtered_texts = [
                            text for text, score in zip(texts, scores) 
                            if score > 0.3
                        ]
                        
                        ocr_text = '\n'.join(filtered_texts)
                        print(f"[Vision] ✅ PaddleOCR 识别成功")
                        return ocr_text
            
            except Exception as e:
                print(f"[Vision] ⚠️ PaddleOCR 失败: {e}")
        
        # 方案 2：DeepSeek API（备选）
        print(f"[Vision] 🔄 尝试 DeepSeek API...")
        try:
            return self._extract_text_by_deepseek(image_path)
        except Exception as e:
            print(f"[Vision] ⚠️ DeepSeek API 失败: {e}")
        
        return None
    
    def _extract_text_by_deepseek(self, image_path: str) -> str or None:
        """使用 DeepSeek API 识别文本"""
        try:
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            import base64
            image_b64 = base64.b64encode(image_data).decode()
            
            headers = {
                'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'model': DEEPSEEK_MODEL,
                'messages': [{
                    'role': 'user',
                    'content': [
                        {'type': 'text', 'text': 'Please extract all text from this screenshot. Return only the text, nothing else.'},
                        {'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{image_b64}'}}
                    ]
                }]
            }
            
            response = requests.post(
                f'{DEEPSEEK_BASE_URL}/chat/completions',
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                text = result['choices'][0]['message']['content']
                return text
        
        except Exception as e:
            print(f"[Vision] ⚠️ DeepSeek API 异常: {e}")
        
        return None
    
    def _extract_authors_structure(self, ocr_text: str) -> list:
        """
        【核心方法 2】从 OCR 文本中提取结构化的作者信息
        
        识别：
        - 作者名字
        - 单位/机构
        - 通讯作者标记 (*)
        - 共同一作标记 (#)
        """
        
        print(f"[Vision] 🔍 从文本中提取作者结构...")
        
        try:
            # 调用 DeepSeek 做智能结构化提取
            return self._parse_authors_with_llm(ocr_text)
        except Exception as e:
            print(f"[Vision] ⚠️ LLM 解析失败: {e}")
            # 降级到简单正则提取
            return self._parse_authors_simple(ocr_text)
    
    def _parse_authors_with_llm(self, ocr_text: str) -> list:
        """使用 LLM 进行智能结构化提取"""
        
        prompt = """根据以下论文截图识别的文本，提取所有作者的信息。

返回格式必须是 JSON 数组：
[
  {
    "name": "作者名字",
    "affiliation": "单位/机构", 
    "is_corresponding": true/false,  // 是否为通讯作者（*标记）
    "is_co_first": true/false  // 是否为共同一作（#标记）
  },
  ...
]

识别规则：
- 通讯作者通常用 * 或 Corresponding author 标记
- 共同一作通常用 # 或 equal contribution 标记
- 单位信息通常在作者名后或脚注

识别提示：
- 优先查找中英文作者名和所属机构
- 保留原始名字拼写（不要自行修改）
- 不确定的字段用 "Unknown" 表示

OCR 文本：
"""
        
        prompt += ocr_text
        
        headers = {
            'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': DEEPSEEK_MODEL,
            'messages': [{'role': 'user', 'content': prompt}]
        }
        
        response = requests.post(
            f'{DEEPSEEK_BASE_URL}/chat/completions',
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            text = result['choices'][0]['message']['content']
            
            # 尝试解析 JSON
            try:
                # 查找 JSON 数组
                import re
                json_match = re.search(r'\[.*?\]', text, re.DOTALL)
                if json_match:
                    authors_json = json_match.group()
                    authors = json.loads(authors_json)
                    
                    # 验证和标准化格式
                    validated = []
                    for idx, author in enumerate(authors):
                        if isinstance(author, dict) and author.get('name'):
                            validated.append({
                                'name': str(author.get('name', 'Unknown')).strip(),
                                'affiliation': str(author.get('affiliation', 'Unknown')).strip(),
                                'is_corresponding': bool(author.get('is_corresponding', False)),
                                'is_co_first': bool(author.get('is_co_first', False)),
                                'order': idx + 1
                            })
                    
                    return validated
            except Exception as e:
                print(f"[Vision] ⚠️ JSON 解析失败: {e}")
        
        return []
    
    def _parse_authors_simple(self, ocr_text: str) -> list:
        """简单的降级方案 - 基于正则表达式提取"""
        
        import re
        authors = []
        
        lines = ocr_text.split('\n')
        for idx, line in enumerate(lines):
            line = line.strip()
            
            # 简单启发式：通常作者名是独立的一行
            # 这个需要根据实际论文排版调整
            if len(line) > 2 and len(line) < 100:
                is_corresponding = '*' in line
                is_co_first = '#' in line
                
                # 移除标记符
                name = re.sub(r'[\*\#,]+', '', line).strip()
                
                if name and name not in ['Abstract', 'Introduction', '通讯作者']:
                    authors.append({
                        'name': name,
                        'affiliation': 'Unknown',
                        'is_corresponding': is_corresponding,
                        'is_co_first': is_co_first,
                        'order': len(authors) + 1
                    })
        
        return authors[:10]  # 通常只取前 10 个
    
    def get_mock_authors(self, doi: str) -> list:
        """获取 mock 数据（当 OCR/LLM 失败时使用）"""
        return [{
            'name': 'Unknown Author',
            'affiliation': 'Unknown',
            'is_corresponding': False,
            'is_co_first': False,
            'order': 1
        }]
