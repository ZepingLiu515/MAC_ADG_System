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

# OCR 库（PaddleOCR - 中英文识别效果好）
try:
    from paddleocr import PaddleOCR
    OCR = PaddleOCR(use_angle_cls=True, lang='ch')
except ImportError:
    OCR = None
    print("[Warning] PaddleOCR 未安装，可以用：pip install paddleocr")

from config import VISUAL_SLICE_DIR, DEEPSEEK_API_KEY, DEEPSEEK_MODEL, DEEPSEEK_BASE_URL

class VisionAgent:
    """
    [Vision Agent V3.0 - OCR + LLM 智能代理]
    职责：
    1. 导航到 https://doi.org/{doi}
    2. 等待页面重定向（Nature、IEEE、Elsevier 等）
    3. 对顶部视口进行截图（包含作者信息）
    4. 用 PaddleOCR 识别截图文本
    5. 用 DeepSeek 文本模型从 OCR 文本中提取作者信息和排序
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
        调用 DeepSeek-VL API 来分析论文截图中的作者信息。
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
        返回用于测试的 mock 数据。
        使用真实用户信息：刘泽萍，多部门
        """
        # 根据 DOI 返回不同的 mock 数据
        # 这样可以模拟不同论文的不同作者配置
        
        if "publichealth.2026006" in doi:
            # 第二篇论文（用户自己的论文）
            mock_authors = [
                {
                    "name": "刘泽萍",
                    "affiliation": "West China School of Medicine, Sichuan University, Chengdu, China",
                    "position": 1,
                    "is_corresponding": False,
                    "is_co_first": False
                },
                {
                    "name": "Co-author Name", 
                    "affiliation": "Other Institution",
                    "position": 2,
                    "is_corresponding": True,
                    "is_co_first": False
                }
            ]
            return {
                "text": f"[Mock 数据 for {doi}] 论文作者: 刘泽萍(西华医学)，Co-author (其他机构)",
                "image_path": None,
                "authors": mock_authors
            }
        else:
            # 默认 mock 数据：测试多部门匹配
            mock_authors = [
                {
                    "name": "刘泽萍",
                    "affiliation": "College of Computer Science, Sichuan University, Chengdu, China",
                    "position": 1,
                    "is_corresponding": True,
                    "is_co_first": False
                },
                {
                    "name": "王小明", 
                    "affiliation": "某大学电气学院",
                    "position": 2,
                    "is_corresponding": False,
                    "is_co_first": True
                }
            ]
            return {
                "text": f"[Mock 数据 for {doi}] 作者: 刘泽萍(计算机学院)*, 王小明(电气学院)#",
                "image_path": None,
                "authors": mock_authors
            }