import os
import time
import base64
import requests
import json

# playwright 在某些环境中可能未安装（测试环境）
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

# playwright_stealth 是可选的（反爬虫检测）
try:
    from playwright_stealth import stealth_sync
except ImportError:
    def stealth_sync(页面):
        pass

# V3.5: 移除本地 PaddleOCR，仅使用 DeepSeek OCR（远端）以避免环境问题

from config import VISUAL_SLICE_DIR, DEEPSEEK_API_KEY, DEEPSEEK_MODEL, DEEPSEEK_BASE_URL

class VisionAgent:
    """
    [Vision Agent V3.5 - DeepSeek OCR + LLM 智能代理]
    职责：
    1. 导航到 https://doi.org/{doi}
    2. 等待页面重定向（Nature、IEEE、Elsevier 等）
    3. 对顶部视口进行截图（包含作者信息）
    4. 用 DeepSeek OCR API 识别截图文本（远端）
    5. 用 DeepSeek 文本模型从 OCR 文本中提取作者信息和排序
    6. 若 OCR 失败，回退到 mock 数据
    """

    def __init__(self):
        if not os.path.exists(VISUAL_SLICE_DIR):
            os.makedirs(VISUAL_SLICE_DIR)

    def process(self, doi):
        """
        Vision Agent 的主入口。
        流程：Playwright 截图 → OCR 识别 → LLM 解析 → 返回作者列表
        """
        if not doi:
            return {"text": "", "image_path": None, "authors": []}

        print(f"\n[Vision] 正在初始化浏览器驱动，DOI: {doi}")
        
        # 1. 通过浏览器自动化捕获截图
        image_path = self._capture_webpage(doi)

        # 2. 如果有截图，用 OCR 识别文本，然后用 LLM 解析
        if image_path:
            extracted_data = self._ocr_and_parse(image_path, doi)
        else:
            # 没有截图，使用 mock 数据
            print(f"[Vision] ⚠️  无法获取截图，使用 mock 数据")
            extracted_data = self._get_mock_authors(doi)

        return extracted_data

    def _capture_webpage(self, doi):
        # 检查 Playwright 是否可用
        if sync_playwright is None:
            print(f"[Vision] ⚠️  Playwright 未安装，使用 mock 数据，DOI: {doi}")
            return None  # 将触发 mock 分析
        
        url = f"https://doi.org/{doi}"
        safe_doi = doi.replace('/', '_')
        save_path = os.path.join(VISUAL_SLICE_DIR, f"{safe_doi}.png")

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
                )
                page = context.new_page()

                # 【核心防御升级】：为页面注入隐身特征，伪装成真实人类浏览器
                stealth_sync(page)

                print(f"[Vision] 🌐 正在导航到: {url}")
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                
                page.wait_for_timeout(4000) 

                page.screenshot(path=save_path)
                print(f"[Vision] 📸 截图已保存: {save_path}")

                browser.close()
                return save_path

        except Exception as e:
            print(f"[Vision] ❌ 浏览器自动化错误: {e}")
            return None

    def _mock_vlm_analysis(self, image_path, doi):
        """
        [已弃用] 调用 DeepSeek-VL API 来分析论文截图中的作者信息。
        现已改用 OCR + LLM 方案
        """
        print(f"[Vision] 🧠 正在分析 {image_path or 'mock 数据'}，DOI: {doi}")
        
        # 如果没有截图或没有 API 密钥，使用 mock 数据
        if image_path is None or not DEEPSEEK_API_KEY:
            return self._get_mock_authors(doi)
        
        # 调用真实的 DeepSeek VLM API
        try:
            return self._call_deepseek_vlm(image_path, doi)
        except Exception as e:
            print(f"[Vision] ⚠️  DeepSeek VLM 错误: {e}，回退到 mock 数据")
            return self._get_mock_authors(doi)
    
    def _ocr_and_parse(self, image_path, doi):
        """
        新流程：OCR 识别 → DeepSeek 文本模型解析
        """
        print(f"[Vision] 🔍 使用 OCR 识别截图文本...")
        
        # 第一步：OCR 识别截图中的文本
        ocr_text = self._extract_text_by_ocr(image_path)
        
        if not ocr_text:
            print(f"[Vision] ⚠️  OCR 识别失败，回退到 mock 数据")
            return self._get_mock_authors(doi)
        
        # 第二步：用 DeepSeek 文本模型从 OCR 文本中提取作者信息
        print(f"[Vision] 📝 OCR 识别的文本长度: {len(ocr_text)} 字符")
        
        authors = self._parse_authors_from_text(ocr_text, doi)
        
        return {
            "text": ocr_text[:500] + "..." if len(ocr_text) > 500 else ocr_text,
            "image_path": image_path,
            "authors": authors
        }
    
    def _extract_text_by_ocr(self, image_path):
        """
        使用 DeepSeek OCR API 从截图中识别文本（远端，无本地依赖）
        """
        # 仅调用 DeepSeek OCR，不使用本地 PaddleOCR
        print("[Vision] 📡 调用 DeepSeek OCR API...")
        ocr_text = self._call_deepseek_ocr(image_path)
        
        if ocr_text:
            print(f"[Vision] ✅ DeepSeek OCR 成功，提取了 {len(ocr_text)} 字符")
            return ocr_text
        else:
            print(f"[Vision] ❌ DeepSeek OCR 无法识别文本")
            return None
    
    def _parse_authors_from_text(self, ocr_text, doi):
        """
        使用 DeepSeek 文本模型从 OCR 文本中提取作者信息和排序
        """
        if not DEEPSEEK_API_KEY:
            print("[Vision] ⚠️  未配置 DeepSeek API KEY，无法解析作者")
            return []
        
        try:
            headers = {
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            }
            
            prompt = f"""根据以下论文文本（通过 OCR 识别），请识别所有作者信息，包括名字、所属机构、作者顺序（作者排序）。

OCR 识别的文本：
---
{ocr_text[:2000]}
---

请返回 JSON 格式的结果：
{{
  "authors": [
    {{"name": "作者名称", "affiliation": "所属机构", "position": 1, "is_corresponding": false, "is_co_first": false}},
    ...
  ]
}}

重要提示：
- position 字段必须是作者在论文中出现的顺序（从 1 开始）
- 通讯作者（带 * 或标记为 Corresponding Author）设置 is_corresponding 为 true
- 共同一作（带 # 或标记为 Co-first）设置 is_co_first 为 true
- 只返回有效的 JSON（不要额外文本）"""
            
            payload = {
                "model": "deepseek-chat",  # 用文本模型，不用 VLM
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "response_format": {"type": "json_object"},
                "max_tokens": 2048,
                "temperature": 0.3  # 低温度，更稳定的 JSON 输出
            }
            
            print(f"[Vision] 🤖 调用 DeepSeek 解析作者信息...")
            response = requests.post(
                f"{DEEPSEEK_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            content = result['choices'][0]['message']['content']
            
            # 尝试解析 JSON
            try:
                data = json.loads(content)
                authors = data.get('authors', [])
                print(f"[Vision] ✅ 成功识别 {len(authors)} 名作者")
                return authors
            except json.JSONDecodeError:
                print(f"[Vision] ⚠️  返回内容不是有效 JSON: {content[:100]}")
                return []
        
        except Exception as e:
            print(f"[Vision] ❌ DeepSeek 解析错误: {e}")
            return []
    
    def _call_deepseek_vlm(self, image_path, doi):
        """
        调用 DeepSeek VLM API 从截图中提取作者信息。
        """
        # 读取截图并转换为 base64
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": DEEPSEEK_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_data}"
                            }
                        },
                        {
                            "type": "text",
                            "text": """请仔细识别论文中的所有作者信息（作者名字、所属机构）。

请返回 JSON 格式的结果，每个作者的信息仅需要以下字段：
{
  "authors": [
    {"name": "作者名称（中文或英文）", "affiliation": "所属机构", "position": 1, "is_corresponding": false, "is_co_first": false},
    {"name": "另一个作者", "affiliation": "机构名", "position": 2, "is_corresponding": true, "is_co_first": false},
    ...
  ],
  "notes": "任何有用的补充说明"
}

重要提示：
- 通讯作者（Corresponding Author）通常带有 * 符号、邮件图标或 "Corresponding" 字样，设置 is_corresponding 为 true
- 共同一作（Co-first Author）通常带有 # 符号或 "Co-first" 标注，设置 is_co_first 为 true
- position 字段是作者在作者列表中的位置顺序（从 1 开始）
- 如果机构信息不可用或需要点击展开，请在 affiliation 字段中标注，如"需展开详情"
- 只返回 JSON（不要额外文本）"""
        }
                    ]
                }
            ],
            "max_tokens": 2048
        }
        
        response = requests.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        response.raise_for_status()
        result = response.json()
        
        # 解析模型回复
        content = result['choices'][0]['message']['content']
        
        # 尝试解析 JSON
        try:
            data = json.loads(content)
            authors = data.get('authors', [])
            notes = data.get('notes', '')
            text = f"从论文截图中提取的作者信息。{notes if notes else ''}"
        except json.JSONDecodeError:
            # 如果不是 JSON，直接使用文本
            authors = []
            text = content
        
        return {
            "text": text,
            "image_path": image_path,
            "authors": authors
        }
    
    def _get_mock_authors(self, doi):
        """
        返回 fallback 测试数据。
        
        当 OCR 或实际作者提取失败时，返回多样化的测试作者数据。
        这样可以验证系统的匹配逻辑，而不会所有论文都匹配到同一个人。
        
        在实际应用中：
        - 如果论文的作者信息可以正确提取（OCR + LLM），就用真实数据
        - 如果失败，至少可以用这些 fallback 数据来测试系统功能
        """
        # 根据 DOI 的哈希值来"伪随机"选择 fallback 数据
        # 这样即使不备 OCR，多个论文也会有不同的 mock 作者
        
        import hashlib
        doi_hash = int(hashlib.md5(doi.encode()).hexdigest(), 16)
        choice = doi_hash % 3  # 循环选择 3 种 fallback 数据
        
        fallback_datasets = [
            # 选项 1: 你自己的信息 - 多部门
            {
                "text": "[Fallback 1] 你的论文作者",
                "authors": [
                    {
                        "name": "刘泽萍",
                        "affiliation": "West China School of Medicine, Sichuan University, Chengdu, China",
                        "position": 1,
                        "is_corresponding": False,
                        "is_co_first": False
                    }
                ]
            },
            # 选项 2: 其他机构的教师（测试多部门匹配）
            {
                "text": "[Fallback 2] 其他论文作者 - 计算机学院",
                "authors": [
                    {
                        "name": "刘泽萍",
                        "affiliation": "College of Computer Science, Sichuan University, Chengdu, China",
                        "position": 1,
                        "is_corresponding": True,
                        "is_co_first": False
                    }
                ]
            },
            # 选项 3: 完全不同的作者（测试无匹配情况）
            {
                "text": "[Fallback 3] 未知作者论文",
                "authors": [
                    {
                        "name": "李明",
                        "affiliation": "北京大学计算机学院",
                        "position": 1,
                        "is_corresponding": False,
                        "is_co_first": False
                    },
                    {
                        "name": "王涛",
                        "affiliation": "清华大学",
                        "position": 2,
                        "is_corresponding": True,
                        "is_co_first": False
                    }
                ]
            }
        ]
        
        selected = fallback_datasets[choice]
        
        return {
            "text": selected["text"],
            "image_path": None,
            "authors": selected["authors"]
        }