"""
【WebDriver 适配器】— 处理所有网页驱动相关的操作

职责：
- 网页导航与 URL 管理
- Cookie 与弹窗处理
- 知网选择页面处理
- 截图生成

不做任何 OCR 或 AI 处理，纯粹是网页操作的工具层。
"""

import os
import time

try:
    from playwright.sync_api import sync_playwright
except (ImportError, Exception) as e:
    print(f"[WARNING] Playwright import failed: {e}")
    sync_playwright = None

try:
    from playwright_stealth import stealth_sync
except ImportError:
    def stealth_sync(page):
        pass

from config import VISUAL_SLICE_DIR


class WebDriverAdapter:
    """网页自动化驱动适配器 - 纯粹的工具类"""
    
    def __init__(self):
        self.playwright = None
        self.browser = None
    
    def get_webpage_screenshot(self, doi: str) -> str or None:
        """
        导航到 DOI 页面并获取截图
        
        输入：DOI（如 "10.3390/nu15204383"）
        输出：截图文件路径，或 None 如果失败
        
        处理步骤：
        1. 构建 URL: https://doi.org/{doi}
        2. 处理知网选择页面
        3. 关闭 Cookie 弹窗
        4. 获取截图
        """
        
        if sync_playwright is None:
            print(f"[WebDriver] ⚠️ Playwright 未安装")
            return None
        
        url = f"https://doi.org/{doi}"
        safe_doi = doi.replace('/', '_')
        save_path = os.path.join(VISUAL_SLICE_DIR, f"{safe_doi}.png")
        
        print(f"[WebDriver] 🌐 启动浏览器，访问: {url}")
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                    extra_http_headers={
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
                        'Cache-Control': 'max-age=0',
                        'DNT': '1',
                    },
                    locale='en-US'
                )
                page = context.new_page()
                stealth_sync(page)
                
                # 导航到页面
                print(f"[WebDriver] 正在导航...")
                response = page.goto(url, wait_until="domcontentloaded", timeout=45000)
                
                # 检查 HTTP 状态
                if response and response.status >= 400:
                    print(f"[WebDriver] ⚠️ HTTP {response.status} 访问被拒绝，尝试重试...")
                    
                    # 重试：添加 Referer
                    context2 = browser.new_context(
                        viewport={'width': 1920, 'height': 1080},
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                        extra_http_headers={
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                            'Referer': 'https://www.google.com/',
                        },
                    )
                    page = context2.new_page()
                    stealth_sync(page)
                    response = page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    
                    if response and response.status >= 400:
                        print(f"[WebDriver] ⚠️ 重试仍失败 HTTP {response.status}")
                        browser.close()
                        return None
                
                page.wait_for_timeout(3000)
                
                # 处理知网选择页面
                self._handle_selection_page(page)
                
                # 关闭 Cookie 弹窗
                self._close_cookie_popup(page)
                
                # 获取截图
                page.screenshot(path=save_path)
                print(f"[WebDriver] 📸 截图已保存: {save_path}")
                
                browser.close()
                return save_path
        
        except Exception as e:
            print(f"[WebDriver] ❌ 错误: {e}")
            return None
    
    def _handle_selection_page(self, page):
        """处理知网"多重解析地址选择页面" - 自动选择境内链接"""
        try:
            title = page.title()
            content = page.content()
            
            selection_keywords = ["多重解析", "选择", "重定向", "镜像"]
            is_selection_page = any(keyword in title or keyword in content for keyword in selection_keywords)
            
            if not is_selection_page:
                return
            
            print(f"[WebDriver] 🔀 检测到选择页面，自动选择境内链接...")
            
            current_url = page.url
            clicked = False
            
            # 方案 1：查找包含"(境内)"的链接
            try:
                links = page.query_selector_all('a[href^="http"]')
                
                domestic_marked = []
                other_safe = []
                
                skip_keywords = [
                    'mirror', 'abroad', 'international', 'overseas', 'oversea',
                    'foreign', 'external', 'proxy', '境外', '国际', 'english'
                ]
                
                for link in links:
                    href = link.get_attribute('href')
                    text = link.inner_text()
                    
                    if not href or not href.strip():
                        continue
                    
                    if '(境内)' in text or '(境内' in text:
                        domestic_marked.append((link, href, text))
                    else:
                        should_skip = False
                        combined = (href + text).lower()
                        for keyword in skip_keywords:
                            if keyword in combined:
                                should_skip = True
                                break
                        
                        if not should_skip:
                            other_safe.append((link, href, text))
                
                # 优先选择(境内)链接
                selection = domestic_marked if domestic_marked else other_safe
                
                if selection:
                    link, href, text = selection[0]
                    marker = "✅ [境内]" if domestic_marked else "✅"
                    print(f"[WebDriver] {marker} 点击链接: {text}")
                    link.click()
                    page.wait_for_navigation(timeout=30000)
                    page.wait_for_timeout(2000)
                    clicked = True
            
            except Exception as e:
                print(f"[WebDriver] ⚠️ 选择页面处理失败: {e}")
        
        except Exception as e:
            print(f"[WebDriver] ⚠️ 选择页面检测失败: {e}")
    
    def _close_cookie_popup(self, page):
        """自动关闭 Cookie 弹窗"""
        try:
            print("[WebDriver] 🍪 尝试关闭 Cookie 弹窗...")
            
            accept_selectors = [
                'button[id*="accept"]',
                'button[class*="accept"]',
                'button:has-text("Accept")',
                'button:has-text("接受")',
                'button:has-text("同意")',
            ]
            
            for selector in accept_selectors:
                try:
                    element = page.query_selector(selector)
                    if element:
                        print(f"[WebDriver] ✅ 找到接受按钮")
                        element.click()
                        page.wait_for_timeout(1000)
                        return
                except Exception:
                    continue
            
            # 方案2：用 JavaScript 隐藏
            hide_scripts = [
                """
                document.querySelectorAll('[role="dialog"], .cookie, .gdpr, .consent').forEach(el => {
                    el.style.display = 'none';
                });
                """
            ]
            
            for script in hide_scripts:
                try:
                    page.evaluate(script)
                    print("[WebDriver] ✅ 通过 JavaScript 关闭弹窗")
                    page.wait_for_timeout(500)
                    return
                except Exception:
                    continue
            
            print("[WebDriver] ⏳ 等待弹窗自动消失...")
            page.wait_for_timeout(2000)
        
        except Exception as e:
            print(f"[WebDriver] ⚠️ Cookie 处理失败: {e}")
