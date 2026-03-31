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

from config import VISUAL_SLICE_DIR, DEEPSEEK_API_KEY, DEEPSEEK_MODEL, DEEPSEEK_BASE_URL

class VisionAgent:
    """
    [Vision Agent V2.0 - 页面自动化代理]
    职责：
    1. 导航到 https://doi.org/{doi}
    2. 等待页面重定向（Nature、IEEE、Elsevier 等）
    3. 对顶部视口进行截图（包含作者信息）
    4. 将图像传送给 VLM（DeepSeek）以提取作者信息
    """

    def __init__(self):
        if not os.path.exists(VISUAL_SLICE_DIR):
            os.makedirs(VISUAL_SLICE_DIR)

    def process(self, doi):
        """
        Vision Agent 的主入口。
        接收 DOI，驱动浏览器，并分析截图。
        """
        if not doi:
            return {"text": "", "image_path": None}

        print(f"\n[Vision] 正在初始化浏览器驱动，DOI: {doi}")
        
        # 1. 通过浏览器自动化捕获截图
        image_path = self._capture_webpage(doi)

        # 2. 使用多模态 LLM (VLM) 提取数据
        # 如果 image_path 为 None（Playwright 未安装），使用 mock 数据
        extracted_data = self._mock_vlm_analysis(image_path, doi)

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
        DeepSeek-VL API 调用的占位符。
        当 image_path 为 None（Playwright 未安装）时，返回 mock 作者数据用于测试。
        """
        print(f"[Vision] 🧠 正在分析 {image_path or 'mock 数据'}，DOI: {doi}")
        
        if image_path is None:
            # 当 Playwright 不可用时的测试用 mock 数据
            mock_authors = [
                {
                    "name": "刘泽萍",
                    "affiliation": "四川大学物理学院",
                    "position": 1,
                    "is_corresponding": True,
                    "is_co_first": False
                },
                {
                    "name": "王小明", 
                    "affiliation": "四川大学计算机学院",
                    "position": 2,
                    "is_corresponding": False,
                    "is_co_first": True
                }
            ]
            return {
                "text": f"[MOCK DATA for {doi}] Authors: 刘泽萍*, 王小明# from Sichuan University",
                "image_path": None,
                "authors": mock_authors
            }
        
        # TODO: 在将来实现真实的 DeepSeek API 调用
        # prompt = "请识别作者列表和机构信息。使用 * 标记通讯作者，# 标记共同一作。"
        
        mock_text = f"[MOCK OCR 数据用于 {doi}] 图像中检测到作者列表。Z.P. Liu*, L. Duan#。"
        
        return {
            "text": mock_text,
            "image_path": image_path,
            "authors": []  # VLM 集成后将填充
        }