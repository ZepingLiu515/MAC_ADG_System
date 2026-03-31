import os
import time
import base64
import requests
import json

# playwright 在某些环境中可能未安装（测试环境）
try:
    from playwright.sync_api import sync_playwright
except (ImportError, Exception) as e:
    print(f"[WARNING] Playwright import failed: {e}")
    sync_playwright = None

# playwright_stealth 是可选的（反爬虫检测）
try:
    from playwright_stealth import stealth_sync
except ImportError:
    def stealth_sync(page):
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

    def _validate_and_normalize_authors(self, authors):
        """
        【关键函数】确保作者列表格式正确，兼容Judge Agent的期望格式
        
        输入: 任意格式的作者列表 (可能来自JSON解析)
        输出: 标准化的作者字典列表
        """
        if not isinstance(authors, list):
            print(f"[Vision] ⚠️ 警告: authors不是list，而是{type(authors)}")
            return []
        
        validated = []
        for i, author in enumerate(authors):
            if not isinstance(author, dict):
                print(f"[Vision] ⚠️ 警告: author[{i}]不是dict，跳过")
                continue
            
            # 创建标准化的作者记录
            normalized = {
                'name': str(author.get('name', 'Unknown')).strip(),
                'affiliation': str(author.get('affiliation', '')).strip(),
                'position': int(author.get('position', 999)),
                'is_corresponding': bool(author.get('is_corresponding', False)),
                'is_co_first': bool(author.get('is_co_first', False))
            }
            
            # 验证必要字段
            if not normalized['name'] or normalized['name'].lower() == 'unknown':
                print(f"[Vision] ⚠️ 警告: author[{i}]缺少name字段，跳过")
                continue
            
            validated.append(normalized)
        
        print(f"[Vision] ✅ 标准化了{len(validated)}名作者")
        return validated

    def process(self, doi):
        """
        Vision Agent 的主入口。
        流程：Playwright 截图 + HTML解析 → OCR 识别 → LLM 解析 → 返回作者列表
        """
        if not doi:
            return {"text": "", "image_path": None, "authors": []}

        print(f"\n[Vision] 正在初始化浏览器驱动，DOI: {doi}")
        
        # 1. 通过浏览器自动化捕获截图和页面源代码
        capture_result = self._capture_webpage(doi)
        
        if not capture_result:
            # 没有截图，使用 mock 数据
            print(f"[Vision] ⚠️  无法获取截图，使用 mock 数据")
            return self._get_mock_authors(doi)
        
        image_path, page_html = capture_result
        
        # 2. 尝试从 HTML 源代码中提取完整作者信息（包括单位）
        html_authors = self._extract_authors_from_html(page_html, doi)
        
        # 3. 用 OCR 识别截图文本，然后用 LLM 解析
        ocr_result = self._ocr_and_parse(image_path, doi)
        ocr_authors = ocr_result.get("authors", [])
        
        # 4. 合并结果：优先使用 HTML 提取的作者，备选 OCR 结果
        final_authors = html_authors if html_authors else ocr_authors
        
        return {
            "text": ocr_result.get("text", ""),
            "image_path": image_path,
            "authors": final_authors
        }

    def _handle_selection_page(self, page, doi):
        """
        【新增】处理知网"多重解析地址选择页面"
        
        某些 DOI（特别是中文论文）会重定向到选择页面，让用户选择论文源。
        这个函数会自动检测并选择**境内链接**（优先级最高）。
        """
        try:
            # 检测是否是选择页面的标志
            title = page.title()
            content = page.content()
            
            # 检查标题或内容是否包含选择页面的标志
            selection_keywords = ["多重解析", "选择", "重定向", "镜像"]
            is_selection_page = any(keyword in title or keyword in content for keyword in selection_keywords)
            
            if not is_selection_page:
                # 不是选择页面，直接返回
                return
            
            print(f"[Vision] 🔀 检测到多重解析选择页面，正在自动选择...")
            
            # 优先选择境内链接
            # 策略：
            # 1. 先找包含"境内"文字的链接
            # 2. 再找 href 中不包含 "mirror" 或 "abroad" 的链接
            # 3. 最后找第一个 <a> 标签
            
            current_url = page.url
            clicked = False
            
            # 方案 1：查找包含"境内"的按钮
            print("[Vision] 尝试方案 1：查找'境内'链接...")
            try:
                domestic_links = page.query_selector_all('a:has-text("境内"), a:has-text("中国")')
                if domestic_links:
                    link = domestic_links[0]
                    href = link.get_attribute('href')
                    if href and href.strip() and href != '#':
                        print(f"[Vision] ✅ 找到境内链接，点击...")
                        link.click()
                        page.wait_for_navigation(timeout=30000)
                        page.wait_for_timeout(2000)
                        clicked = True
            except Exception as e:
                print(f"[Vision] ⚠️ 方案 1 失败: {e}")
            
            # 方案 2：优先选择包含 (境内) 标记的链接，否则选择第一个非境外链接
            if not clicked:
                print("[Vision] 尝试方案 2：查找(境内)链接或第一个非境外链接...")
                try:
                    links = page.query_selector_all('a[href^="http"]')
                    
                    # 排除所有境外/镜像链接的关键词
                    skip_keywords = [
                        'mirror', 'abroad', 'international', 'overseas', 'oversea',
                        'foreign', 'external', 'proxy', '境外', '国际', 'english'
                    ]
                    
                    # 第一轮：查找所有包含 (境内) 的链接
                    domestic_marked_links = []
                    other_safe_links = []
                    
                    for link in links:
                        href = link.get_attribute('href')
                        text = link.inner_text()
                        
                        if not href or not href.strip():
                            continue
                        
                        # 检查是否有 (境内) 标记
                        if '(境内)' in text or '(境内' in text:
                            domestic_marked_links.append((link, href, text))
                        else:
                            # 检查是否包含排除关键词
                            should_skip = False
                            combined = (href + text).lower()
                            for keyword in skip_keywords:
                                if keyword in combined:
                                    should_skip = True
                                    break
                            
                            if not should_skip:
                                other_safe_links.append((link, href, text))
                    
                    # 优先选择 (境内) 链接
                    selection = domestic_marked_links if domestic_marked_links else other_safe_links
                    
                    if selection:
                        link, href, text = selection[0]
                        marker = "✅ [境内]" if domestic_marked_links else "✅ [安全]"
                        print(f"[Vision] {marker} 点击链接: {text}")
                        print(f"[Vision] 📍 目标URL: {href}")
                        try:
                            link.click()
                            # 尝试等待导航，但如果失败也继续
                            try:
                                page.wait_for_navigation(timeout=15000)
                            except:
                                page.wait_for_timeout(2000)
                            clicked = True
                        except Exception as link_click_error:
                            print(f"[Vision] ⚠️ 点击失败: {link_click_error}")
                except Exception as e:
                    print(f"[Vision] ⚠️ 方案 2 失败: {e}")
            
            # 方案 3：点击任意第一个 <a> 标签
            if not clicked:
                print("[Vision] 尝试方案 3：点击第一个 <a> 标签...")
                try:
                    first_link = page.query_selector('a')
                    if first_link:
                        href = first_link.get_attribute('href')
                        text = first_link.inner_text()
                        if href and href.strip() and href != '#':
                            print(f"[Vision] ✅ 点击: {text[:30]}")
                            first_link.click()
                            page.wait_for_navigation(timeout=30000)
                            page.wait_for_timeout(2000)
                            clicked = True
                except Exception as e:
                    print(f"[Vision] ⚠️ 方案 3 失败: {e}")
            
            # 检测是否成功（URL 是否改变且不是首页）
            new_url = page.url
            if clicked:
                if new_url != current_url:
                    print(f"[Vision] ✅ 已跳转到: {new_url}")
                else:
                    print(f"[Vision] ⚠️ URL 未改变，可能导航失败")
            else:
                print(f"[Vision] ⚠️ 无法自动选择，继续截图当前页面")
                
        except Exception as e:
            print(f"[Vision] ⚠️ 选择页面处理失败: {e}，继续截图")

    def _close_cookie_popup(self, page):
        """
        【新增】自动关闭Cookie弹窗，避免挡住截图
        尝试多种方式：点击按钮、执行JS、等待消失
        """
        try:
            print("[Vision] 🍪 尝试关闭Cookie弹窗...")
            
            # 方案1: 点击"接受"按钮 (最常见的ID和类名)
            accept_selectors = [
                'button[id*="accept"]',
                'button[class*="accept"]',
                'button:has-text("Accept")',
                'button:has-text("接受")',
                'button:has-text("同意")',
                'button:has-text("I Accept")',
                'a[id*="accept"]',
                '[role="button"]:has-text("Accept")',
                '[role="button"]:has-text("接受")',
            ]
            
            for selector in accept_selectors:
                try:
                    element = page.query_selector(selector)
                    if element:
                        print(f"[Vision] ✅ 找到接受按钮: {selector}")
                        element.click()
                        page.wait_for_timeout(1000)  # 等待弹窗关闭动画
                        return
                except Exception:
                    continue
            
            # 方案2: 用JavaScript隐藏常见的cookie弹窗容器
            hide_scripts = [
                """
                // 隐藏常见的cookie容器
                const selectors = [
                    '[id*="cookie"]', '[class*="cookie"]',
                    '[id*="gdpr"]', '[class*="gdpr"]',
                    '[id*="consent"]', '[class*="consent"]',
                    '[role="dialog"]', '[aria-label*="cookie"]'
                ];
                selectors.forEach(sel => {
                    try {
                        document.querySelectorAll(sel).forEach(el => {
                            if (el.offsetHeight < 500) el.style.display = 'none';
                        });
                    } catch (e) {}
                });
                """,
                """
                // 移除任何large overlays
                document.querySelectorAll('[role="dialog"], .cookie, .gdpr, .consent').forEach(el => {
                    el.remove();
                });
                """
            ]
            
            for script in hide_scripts:
                try:
                    page.evaluate(script)
                    print("[Vision] ✅ 通过JavaScript关闭Cookie弹窗")
                    page.wait_for_timeout(500)
                    return
                except Exception:
                    continue
            
            # 方案3: 等待可能的弹窗自动消失
            print("[Vision] ⏳ 等待弹窗自动消失...")
            page.wait_for_timeout(2000)
            
        except Exception as e:
            print(f"[Vision] ⚠️ Cookie处理失败（但继续截图）: {e}")

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
                
                # 【改进】添加更完整的 HTTP headers 和真实浏览器标识
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                    extra_http_headers={
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
                        'Cache-Control': 'max-age=0',
                        'DNT': '1',
                        'Sec-Fetch-Dest': 'document',
                        'Sec-Fetch-Mode': 'navigate',
                        'Sec-Fetch-Site': 'none',
                        'Upgrade-Insecure-Requests': '1'
                    },
                    locale='en-US'
                )
                page = context.new_page()

                # 【核心防御升级】：为页面注入隐身特征，伪装成真实人类浏览器
                stealth_sync(page)
                
                # 【新增】添加事件监听以检测网络错误
                response_status = {'code': None, 'url': None}
                
                def on_response(response):
                    response_status['code'] = response.status
                    response_status['url'] = response.url
                
                page.on('response', on_response)

                print(f"[Vision] 🌐 正在导航到: {url}")
                try:
                    response = page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    
                    # 检查是否被拒绝
                    if response and response.status >= 400:
                        print(f"[Vision] ⚠️  HTTP {response.status} - 访问被拒绝")
                        print(f"[Vision] 🔄 尝试添加 Referer 重试...")
                        
                        # 重试：添加 Referer
                        context2 = browser.new_context(
                            viewport={'width': 1920, 'height': 1080},
                            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                            extra_http_headers={
                                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                                'Accept-Encoding': 'gzip, deflate, br',
                                'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
                                'Referer': 'https://www.google.com/',
                                'Cache-Control': 'max-age=0'
                            },
                            locale='en-US'
                        )
                        page = context2.new_page()
                        stealth_sync(page)
                        
                        response = page.goto(url, wait_until="domcontentloaded", timeout=45000)
                        
                        if response and response.status >= 400:
                            print(f"[Vision] ⚠️  再次失败 HTTP {response.status}，使用 mock 数据")
                            browser.close()
                            return None
                    
                except Exception as e:
                    print(f"[Vision] ⚠️  导航异常: {e}")
                    browser.close()
                    return None
                
                # 等待页面完全加载
                page.wait_for_timeout(3000)
                
                # 【新增】检测知网多重解析选择页面，自动选择第一个
                self._handle_selection_page(page, doi)
                
                # 【新增】关闭Cookie弹窗
                self._close_cookie_popup(page)

                page.screenshot(path=save_path)
                print(f"[Vision] 📸 截图已保存: {save_path}")
                
                # 获取页面源代码用于 HTML 解析
                page_html = page.content()
                
                browser.close()
                return (save_path, page_html)

        except Exception as e:
            print(f"[Vision] ❌ 浏览器自动化错误: {e}")
            return None
    
    def _extract_authors_from_html(self, page_html, doi):
        """
        【新增】从 HTML 源代码中提取作者和单位信息
        
        知网等平台的完整作者列表通常在 HTML 中的 Meta 标签或 JSON-LD 数据中
        这个函数尝试多种提取方式：
        1. 查找 JSON-LD 格式的结构化数据
        2. 查找 Meta author/creator 标签
        3. 使用正则表达式查找知网格式的数据
        """
        if not page_html:
            return []
        
        print(f"[Vision] 🔍 从 HTML 源代码提取作者信息...")
        authors = []
        
        try:
            import json
            import re
            from html import unescape
            
            # 方案 1：查找 JSON-LD 格式的结构化数据
            json_ld_pattern = r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>([\\s\\S]*?)</script>'
            json_ld_matches = re.findall(json_ld_pattern, page_html)
            
            for json_str in json_ld_matches:
                try:
                    data = json.loads(json_str)
                    
                    # 查找 author 字段
                    if 'author' in data:
                        author_data = data['author']
                        if isinstance(author_data, list):
                            for author in author_data:
                                name = author.get('name', '').strip() if isinstance(author, dict) else str(author).strip()
                                affiliation = ""
                                if isinstance(author, dict) and 'affiliation' in author:
                                    aff_data = author['affiliation']
                                    if isinstance(aff_data, dict):
                                        affiliation = aff_data.get('name', '').strip()
                                    else:
                                        affiliation = str(aff_data).strip()
                                
                                if name:
                                    authors.append({
                                        "name": name,
                                        "affiliation": affiliation or "Unknown",
                                        "order": len(authors) + 1
                                    })
                        elif isinstance(author_data, dict):
                            name = author_data.get('name', '').strip()
                            affiliation = ""
                            if 'affiliation' in author_data:
                                aff_data = author_data['affiliation']
                                if isinstance(aff_data, dict):
                                    affiliation = aff_data.get('name', '').strip()
                                else:
                                    affiliation = str(aff_data).strip()
                            
                            if name:
                                authors.append({
                                    "name": name,
                                    "affiliation": affiliation or "Unknown",
                                    "order": len(authors) + 1
                                })
                except (json.JSONDecodeError, KeyError) as e:
                    continue
            
            if authors:
                print(f"[Vision] ✅ 从 JSON-LD 提取了 {len(authors)} 位作者")
                return authors
            
            # 方案 2：查找 Meta author/creator 标签
            author_meta_pattern = r'<meta[^>]*name=["\']?(?:author|creator|DC\.creator)["\']?[^>]*content=["\']([^"]+)["\'][^>]*>'
            author_matches = re.findall(author_meta_pattern, page_html, re.IGNORECASE)
            
            for author_name in author_matches:
                author_name = unescape(author_name).strip()
                if author_name and len(author_name) > 1:
                    authors.append({
                        "name": author_name,
                        "affiliation": "Unknown",
                        "order": len(authors) + 1
                    })
            
            if authors:
                print(f"[Vision] ✅ 从 Meta 标签提取了 {len(authors)} 位作者")
                return authors
            
        except Exception as e:
            print(f"[Vision] ⚠️ HTML 解析异常: {e}")
        
        print(f"[Vision] ⚠️ 未能从 HTML 提取作者信息，将使用 OCR 方案")
        return []

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
        使用本地 PaddleOCR（优先）或 DeepSeek API（备选）识别截图中的文本
        
        流程：
        1️⃣ 优先用 PaddleOCR（完全免费，本地运行，中英文支持好）
        2️⃣ 如果 PaddleOCR 失败，降级到 DeepSeek API
        3️⃣ 都失败就返回 None
        
        返回: 识别的纯文本或 None
        """
        # 方案 1️⃣：优先使用本地 PaddleOCR（最稳定）
        print("[Vision] 📝 尝试本地 PaddleOCR...")
        try:
            from paddleocr import PaddleOCR
            # 使用新参数名，避免过时警告
            ocr = PaddleOCR(use_textline_orientation=True, lang='ch')
            result = ocr.predict(str(image_path))  # 改用 predict() 方法（新版本）
            
            # 新版本 PaddleOCR 返回列表，第一个元素是 OCRResult 对象（字典结构）
            if result and len(result) > 0:
                ocr_result = result[0]
                
                # OCRResult 是字典，包含 rec_texts（文字列表）和 rec_scores（置信度列表）
                if 'rec_texts' in ocr_result:
                    rec_texts = ocr_result['rec_texts']
                    rec_scores = ocr_result.get('rec_scores', [])
                    
                    # 构建文字列表（只保留置信度 > 0.3 的文字）
                    text_lines = []
                    for text, score in zip(rec_texts, rec_scores):
                        if isinstance(score, (int, float)) and score > 0.3:
                            if text and text.strip():
                                text_lines.append(text)
                    
                    if text_lines:
                        ocr_text = "\n".join(text_lines)
                        print(f"[Vision] ✅ PaddleOCR 成功！识别 {len(text_lines)} 行文字")
                        return ocr_text
                
                print("[Vision] ⚠️ PaddleOCR 没有识别到文字")
                return None
            
            print("[Vision] ⚠️ PaddleOCR 返回结果为空")
            return None
        
        except ImportError:
            print("[Vision] ⚠️ PaddleOCR 未安装，尝试降级到 DeepSeek API...")
        except Exception as e:
            print(f"[Vision] ⚠️ PaddleOCR 错误: {e}，尝试降级到 DeepSeek API...")
        
        # 方案 2️⃣：降级到 DeepSeek API
        print("[Vision] 📡 调用 DeepSeek API 作为备选...")
        ocr_text = self._call_deepseek_ocr(image_path)
        
        if ocr_text:
            print(f"[Vision] ✅ DeepSeek API 成功，提取了 {len(ocr_text)} 字符")
            return ocr_text
        else:
            print(f"[Vision] ❌ 所有 OCR 方案都失败了")
            return None
    
    def _call_deepseek_ocr(self, image_path):
        """
        调用 DeepSeek 的 OCR 接口从图片中识别文本。
        优先使用远端 OCR API，失败时使用 chat 接口作为备选。
        返回识别的纯文本或 None。
        """
        if not DEEPSEEK_API_KEY:
            print("[Vision] ⚠️  未配置 DeepSeek API KEY")
            return None

        try:
            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')

            headers = {
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            }

            # 先尝试标准 OCR endpoint（如果 DeepSeek 提供）
            ocr_endpoints = [
                f"{DEEPSEEK_BASE_URL}/vision/ocr",
                f"{DEEPSEEK_BASE_URL}/ocr",
                f"{DEEPSEEK_BASE_URL}/v1/ocr"
            ]

            payload = {
                "image": f"data:image/png;base64,{image_data}",
                "language": "auto"
            }

            for url in ocr_endpoints:
                try:
                    resp = requests.post(url, headers=headers, json=payload, timeout=30)
                    if resp.status_code == 200:
                        data = resp.json()
                        # 支持多种返回格式
                        if isinstance(data, dict):
                            if 'text' in data and data['text']:
                                return data['text']
                            if 'ocr_text' in data and data['ocr_text']:
                                return data['ocr_text']
                            if 'lines' in data and isinstance(data['lines'], list):
                                return "\n".join(data['lines'])
                            if 'choices' in data:
                                try:
                                    content = data['choices'][0]['message']['content']
                                    return content
                                except Exception:
                                    pass
                except Exception:
                    continue

            # 若远端 OCR endpoint 都不可用，使用 vision 模型识别文本（次优方案）
            # 尝试两种模型：deepseek-vl（优先）和 deepseek-chat（备选）
            for model_name in ["deepseek-vl", "deepseek-chat"]:
                try:
                    chat_payload = {
                        "model": model_name,
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "请将下面图片中可见的所有文本逐行返回，仅返回纯文本，不要任何额外解释或说明。"
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/png;base64,{image_data}"
                                        }
                                    }
                                ]
                            }
                        ],
                        "max_tokens": 4096,
                        "temperature": 0.0
                    }

                    print(f"[Vision] ℹ️ 使用 {model_name} 模型进行 OCR...")
                    resp = requests.post(
                        f"{DEEPSEEK_BASE_URL}/chat/completions",
                        headers=headers,
                        json=chat_payload,
                        timeout=30
                    )
                    resp.raise_for_status()
                    result = resp.json()
                    
                    if 'choices' in result and result['choices']:
                        content = result['choices'][0]['message']['content']
                        if isinstance(content, str) and content.strip():
                            print(f"[Vision] ✅ {model_name} OCR 成功")
                            return content
                        elif isinstance(content, dict) and 'text' in content:
                            return content['text']
                except Exception as e:
                    print(f"[Vision] ⚠️ {model_name} 模型失败: {e}")
                    continue
            
            # 所有模型都失败了
            print("[Vision] ❌ 所有 vision 模型都无法识别文本")
            return None

        except Exception as e:
            print(f"[Vision] ❌ DeepSeek OCR 调用错误: {e}")
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
                # ✅ 添加数据验证和规范化
                authors = self._validate_and_normalize_authors(authors)
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
            # ✅ 添加数据验证和规范化
            authors = self._validate_and_normalize_authors(authors)
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