"""
【WebDriver 适配器】— 处理所有网页驱动相关的操作

职责：
- 网页导航与 URL 管理
- Cookie 与弹窗处理
- 知网选择页面处理
- 截图生成
- （可选）从页面交互中提取作者 hover/mailto 线索

不做任何 OCR 或 AI 处理，纯粹是网页操作的工具层。
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from typing import Any, Dict, List, Optional

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

    def _goto_timeout_ms(self, default: int = 90000) -> int:
        """可配置的 goto 超时（毫秒）。AIMS 等站点偶尔首屏很慢，45s 不够。"""
        raw = os.getenv("PLAYWRIGHT_GOTO_TIMEOUT_MS")
        if raw is None:
            return int(default)
        try:
            v = int(str(raw).strip())
            return v if v > 0 else int(default)
        except Exception:
            return int(default)

    def get_webpage_screenshot(self, doi: str, landing_page_url: Optional[str] = None) -> Optional[str]:
        """导航到 DOI 页面并获取截图。

        输入：DOI（如 "10.3390/nu15204383"）
        输出：截图文件路径，或 None 如果失败

        处理步骤：
        1. 构建 URL: https://doi.org/{doi}
        2. 处理知网选择页面
        3. 关闭 Cookie 弹窗
        4. 获取截图
        """

        if sync_playwright is None:
            print("[WebDriver] ⚠️ Playwright 未安装")
            return None

        doi_url = f"https://doi.org/{doi}"
        safe_doi = doi.replace("/", "_")
        save_path = os.path.join(VISUAL_SLICE_DIR, f"{safe_doi}.png")
        blocked_save_path = os.path.join(VISUAL_SLICE_DIR, f"{safe_doi}_blocked.png")

        print(f"[WebDriver] 🌐 启动浏览器，访问: {doi_url}")

        try:
            with sync_playwright() as p:
                channel = os.getenv("PLAYWRIGHT_CHANNEL")

                proxy_server = os.getenv("PLAYWRIGHT_PROXY")
                proxy_user = os.getenv("PLAYWRIGHT_PROXY_USERNAME")
                proxy_pass = os.getenv("PLAYWRIGHT_PROXY_PASSWORD")
                proxy = None
                if proxy_server:
                    proxy = {"server": proxy_server}
                    if proxy_user and proxy_pass:
                        proxy["username"] = proxy_user
                        proxy["password"] = proxy_pass

                headless_env = os.getenv("PLAYWRIGHT_HEADLESS", "1").strip()
                headless = not (headless_env in {"0", "false", "False", "no", "NO"})

                try:
                    slow_mo = int(os.getenv("PLAYWRIGHT_SLOWMO_MS", "0").strip() or "0")
                except Exception:
                    slow_mo = 0

                browser = p.chromium.launch(
                    headless=headless,
                    channel=channel,
                    proxy=proxy,
                    slow_mo=slow_mo,
                    args=["--disable-blink-features=AutomationControlled"],
                )

                context = browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/121.0.0.0 Safari/537.36"
                    ),
                    extra_http_headers={
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                        "Accept-Encoding": "gzip, deflate, br",
                        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
                        "Cache-Control": "max-age=0",
                        "DNT": "1",
                    },
                    locale="en-US",
                )
                page = context.new_page()
                stealth_sync(page)

                def _is_block_page() -> bool:
                    try:
                        content = page.content() or ""
                        markers = [
                            "There was a problem providing the content you requested",
                            "Reference number",
                            "provide the details below",
                            "Please contact our support team",
                            "Access Denied",
                            "Forbidden",
                        ]
                        return any(m in content for m in markers)
                    except Exception:
                        return False

                print("[WebDriver] 正在导航...")
                goto_timeout = self._goto_timeout_ms(default=90000)
                response = page.goto(doi_url, wait_until="domcontentloaded", timeout=goto_timeout)

                blocked = (response and response.status >= 400) or _is_block_page()
                if blocked:
                    print(f"[WebDriver] ⚠️ HTTP {getattr(response, 'status', None)} 访问被拒绝，尝试重试...")

                    context2 = browser.new_context(
                        viewport={"width": 1920, "height": 1080},
                        user_agent=(
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/121.0.0.0 Safari/537.36"
                        ),
                        extra_http_headers={
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                            "Referer": "https://www.google.com/",
                        },
                    )
                    page = context2.new_page()
                    stealth_sync(page)
                    response = page.goto(doi_url, wait_until="domcontentloaded", timeout=goto_timeout)

                    blocked = (response and response.status >= 400) or _is_block_page()
                    if blocked:
                        print(f"[WebDriver] ⚠️ 重试仍失败 HTTP {getattr(response, 'status', None)}")

                        # 合规降级：如果提供了出版商落地页 URL，则改为访问该页面
                        if landing_page_url and isinstance(landing_page_url, str):
                            landing_page_url = landing_page_url.strip()
                        if landing_page_url and landing_page_url != doi_url:
                            print(f"[WebDriver] ↪️ 尝试改为访问出版商落地页: {landing_page_url}")
                            try:
                                response = page.goto(landing_page_url, wait_until="domcontentloaded", timeout=goto_timeout)
                                blocked2 = (response and response.status >= 400) or _is_block_page()
                                if blocked2:
                                    print(
                                        f"[WebDriver] ⚠️ 落地页也被拒绝 HTTP {getattr(response, 'status', None)}"
                                    )
                                    try:
                                        page.screenshot(path=blocked_save_path)
                                        print(f"[WebDriver] 🧾 已保存拦截页截图: {blocked_save_path}")
                                    except Exception:
                                        pass
                                    browser.close()
                                    return None
                            except Exception as e:
                                print(f"[WebDriver] ⚠️ 落地页访问失败: {e}")
                                try:
                                    page.screenshot(path=blocked_save_path)
                                    print(f"[WebDriver] 🧾 已保存拦截页截图: {blocked_save_path}")
                                except Exception:
                                    pass
                                browser.close()
                                return None
                        else:
                            try:
                                page.screenshot(path=blocked_save_path)
                                print(f"[WebDriver] 🧾 已保存拦截页截图: {blocked_save_path}")
                            except Exception:
                                pass
                            browser.close()
                            return None

                page.wait_for_timeout(3000)
                self._handle_selection_page(page)
                self._close_cookie_popup(page)

                page.screenshot(path=save_path)
                print(f"[WebDriver] 📸 截图已保存: {save_path}")

                browser.close()
                return save_path

        except Exception as e:
            print(f"[WebDriver] ❌ 错误: {e}")
            return None

    def extract_author_hover_data(
        self,
        doi: str,
        landing_page_url: Optional[str] = None,
        max_authors: int = 30,
        save_sidecar_json: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """从网页交互（hover/click）中提取作者单位与权益线索。

        - 强优先使用 `meta[name=citation_author]` 作为白名单，避免抓到导航链接（例如 "On This Site"）。
        - 若页面可见作者名元素存在，尝试 hover/click 抓 tooltip/popover。
        - 若无法 hover，也会返回 meta-only 的作者姓名列表（用于后续对齐/融合）。
        """

        if sync_playwright is None:
            print("[WebDriver] ⚠️ Playwright 未安装")
            return None

        def _env_truthy(name: str, default: str = "1") -> bool:
            raw = os.getenv(name, default).strip()
            return raw not in {"0", "false", "False", "no", "NO"}

        if not _env_truthy("PLAYWRIGHT_EXTRACT_AUTHOR_DETAILS", default="1"):
            return None

        doi_url = f"https://doi.org/{doi}"
        safe_doi = doi.replace("/", "_")
        sidecar_path = os.path.join(VISUAL_SLICE_DIR, f"{safe_doi}_page_author_data.json")

        ignore_name_phrases = {
            "on this site",
            "on google scholar",
            "google scholar",
            "on researchgate",
            "researchgate",
            "orcid",
            "view profile",
            "profile",
            "citation",
        }

        email_re = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)

        def _norm_for_match(s: str) -> str:
            """用于作者名在页面文本中的鲁棒匹配：去重音、去标点、规范空白。"""
            s = str(s or "")
            s = unicodedata.normalize("NFKD", s)
            s = "".join(ch for ch in s if not unicodedata.combining(ch))
            s = s.replace("-", " ")
            s = re.sub(r"[^0-9a-zA-Z\s]", " ", s)
            s = re.sub(r"\s+", " ", s).strip().lower()
            return s

        def _contains_ignored_phrase(name: str) -> bool:
            low = (name or "").strip().lower()
            return bool(low) and any(p in low for p in ignore_name_phrases)

        def _name_key(name: str) -> str:
            return "".join(ch for ch in str(name or "").lower() if ch.isalnum())

        def _xpath_literal(text: str) -> str:
            s = str(text)
            if "'" not in s:
                return f"'{s}'"
            if '"' not in s:
                return f'"{s}"'
            parts = s.split("'")
            return "concat(" + ", \"'\", ".join([f"'{p}'" for p in parts]) + ")"

        def _is_block_page(page) -> bool:
            try:
                content = page.content() or ""
                markers = [
                    "There was a problem providing the content you requested",
                    "Reference number",
                    "provide the details below",
                    "Please contact our support team",
                    "Access Denied",
                    "Forbidden",
                ]
                return any(m in content for m in markers)
            except Exception:
                return False

        def _collect_visible_popover_text(page) -> str:
            js = r"""
(() => {
  const candidates = [];
  const selectors = [
    '[role="tooltip"]',
    '[role="dialog"] [class*="tooltip" i]',
    '[class*="tooltip" i]',
    '[class*="popover" i]',
    '[class*="tippy" i]',
    '[class*="MuiTooltip" i]',
    '[data-testid*="tooltip" i]',
    '[data-test*="tooltip" i]'
  ];
  for (const sel of selectors) {
    document.querySelectorAll(sel).forEach(el => candidates.push(el));
  }
  const out = [];
  const seen = new Set();
  for (const el of candidates) {
    if (!el) continue;
    const style = window.getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    const isVisible = style && style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 2 && rect.height > 2;
    if (!isVisible) continue;
    const txt = (el.innerText || '').trim();
    if (!txt || txt.length < 3) continue;
    if (seen.has(txt)) continue;
    seen.add(txt);
    out.push(txt);
  }
  return out.slice(0, 5).join('\n---\n');
})();
"""
            try:
                v = page.evaluate(js)
                return v.strip() if isinstance(v, str) else ""
            except Exception:
                return ""

        def _infer_flags_from_text(text: str) -> Dict[str, bool]:
            low = (text or "").lower()
            is_corresponding = any(k in low for k in ["corresponding author", "correspondence", "email", "e-mail"])
            is_co_first = any(k in low for k in ["equal contribution", "contributed equally", "co-first", "co first"])
            return {"is_corresponding": is_corresponding, "is_co_first": is_co_first}

        def _infer_affiliation_from_text(text: str) -> str:
            if not text:
                return ""
            lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines() if ln and ln.strip()]
            keys = [
                "university",
                "college",
                "institute",
                "department",
                "school",
                "hospital",
                "laboratory",
                "centre",
                "center",
            ]
            best = ""
            best_score = -1
            for ln in lines:
                low = ln.lower()
                score = (2 if any(k in low for k in keys) else 0) + (1 if len(ln) >= 15 else 0)
                if score > best_score:
                    best = ln
                    best_score = score
            return best if best and len(best) <= 200 else ""

        try:
            with sync_playwright() as p:
                channel = os.getenv("PLAYWRIGHT_CHANNEL")

                proxy_server = os.getenv("PLAYWRIGHT_PROXY")
                proxy_user = os.getenv("PLAYWRIGHT_PROXY_USERNAME")
                proxy_pass = os.getenv("PLAYWRIGHT_PROXY_PASSWORD")
                proxy = None
                if proxy_server:
                    proxy = {"server": proxy_server}
                    if proxy_user and proxy_pass:
                        proxy["username"] = proxy_user
                        proxy["password"] = proxy_pass

                headless_env = os.getenv("PLAYWRIGHT_HEADLESS", "1").strip()
                headless = not (headless_env in {"0", "false", "False", "no", "NO"})

                try:
                    slow_mo = int(os.getenv("PLAYWRIGHT_SLOWMO_MS", "0").strip() or "0")
                except Exception:
                    slow_mo = 0

                browser = p.chromium.launch(
                    headless=headless,
                    channel=channel,
                    proxy=proxy,
                    slow_mo=slow_mo,
                    args=["--disable-blink-features=AutomationControlled"],
                )

                context = browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/121.0.0.0 Safari/537.36"
                    ),
                    extra_http_headers={
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                        "Accept-Encoding": "gzip, deflate, br",
                        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
                        "Cache-Control": "max-age=0",
                        "DNT": "1",
                    },
                    locale="en-US",
                )

                page = context.new_page()
                stealth_sync(page)

                goto_timeout = self._goto_timeout_ms(default=90000)
                try:
                    response = page.goto(doi_url, wait_until="domcontentloaded", timeout=goto_timeout)
                except Exception:
                    # 某些站点 doi.org 跳转/首屏很慢：直接尝试落地页（若有）
                    if landing_page_url and isinstance(landing_page_url, str):
                        landing_page_url = landing_page_url.strip()
                    if landing_page_url and landing_page_url != doi_url:
                        response = page.goto(landing_page_url, wait_until="domcontentloaded", timeout=goto_timeout)
                    else:
                        raise
                blocked = (response and response.status >= 400) or _is_block_page(page)

                if blocked and landing_page_url and isinstance(landing_page_url, str):
                    landing_page_url = landing_page_url.strip()
                    if landing_page_url and landing_page_url != doi_url:
                        print(f"[WebDriver] ↪️ doi.org 受限，改用落地页提取: {landing_page_url}")
                        response = page.goto(landing_page_url, wait_until="domcontentloaded", timeout=45000)
                        blocked = (response and response.status >= 400) or _is_block_page(page)

                if blocked:
                    print(
                        f"[WebDriver] ⚠️ 页面被拦截，跳过 hover 提取（HTTP={getattr(response, 'status', None)}）"
                    )
                    browser.close()
                    return None

                page.wait_for_timeout(2000)
                self._handle_selection_page(page)
                self._close_cookie_popup(page)
                page.wait_for_timeout(800)

                meta_names: List[str] = []
                meta_institutions: List[str] = []
                meta_emails: List[str] = []

                try:
                    meta_names = page.evaluate(
                        """
(() => Array.from(document.querySelectorAll('meta[name="citation_author"]'))
  .map(m => (m.getAttribute('content') || '').trim())
  .filter(Boolean)
  .slice(0, 50)
 )();
"""
                    )
                    if not isinstance(meta_names, list):
                        meta_names = []
                except Exception:
                    meta_names = []

                meta_name_keys = {_name_key(n) for n in meta_names if n}

                try:
                    meta_institutions = page.evaluate(
                        """
(() => Array.from(document.querySelectorAll('meta[name="citation_author_institution"]'))
  .map(m => (m.getAttribute('content') || '').trim())
  .filter(Boolean)
  .slice(0, 200)
 )();
"""
                    )
                    if not isinstance(meta_institutions, list):
                        meta_institutions = []
                except Exception:
                    meta_institutions = []

                try:
                    meta_emails = page.evaluate(
                        """
(() => Array.from(document.querySelectorAll('meta[name="citation_author_email"], meta[name="citation_email"]'))
  .map(m => (m.getAttribute('content') || '').trim())
  .filter(Boolean)
  .slice(0, 200)
 )();
"""
                    )
                    if not isinstance(meta_emails, list):
                        meta_emails = []
                except Exception:
                    meta_emails = []

                authors: List[Dict[str, Any]] = []
                raw_tooltips: List[Dict[str, Any]] = []

                meta_aff_map: Dict[int, str] = {}
                try:
                    for i, aff in enumerate(meta_institutions, start=1):
                        s = str(aff or '').strip()
                        if s:
                            meta_aff_map[i] = s
                except Exception:
                    meta_aff_map = {}

                def _extract_signals(el, author_name: str = "") -> Dict[str, Any]:
                    # 避免从导航/页眉页脚误抓
                    try:
                        if bool(el.evaluate("(node) => !!node.closest('nav, header, footer, aside')")):
                            return {"skip": True}
                    except Exception:
                        pass

                    markers = ""
                    aff_nums: List[int] = []
                    try:
                        sup_info = el.evaluate(
                            """
(node) => {
    const primary = node.closest('li, div, span, p, a') || node.parentElement || node;
    const pool = [];
    const push = (x) => { if (x && !pool.includes(x)) pool.push(x); };

    push(node);
    push(primary);
    push(primary && primary.parentElement);
    push(primary && primary.parentElement && primary.parentElement.parentElement);
    push(node.nextElementSibling);
    push(node.previousElementSibling);

    // 同级容器：有些站点把 sup 放在作者名旁边（兄弟节点）
    if (primary && primary.parentElement) {
        push(primary.parentElement);
        Array.from(primary.parentElement.children || []).slice(0, 12).forEach(ch => push(ch));
    }

    const sups = [];
    for (const x of pool) {
        try {
            if (!x) continue;
            if (x.tagName && x.tagName.toLowerCase() === 'sup') {
                const t = (x.textContent || '').trim();
                if (t) sups.push(t);
            }
            if (x.querySelectorAll) {
                x.querySelectorAll('sup').forEach(s => {
                    const t = (s.textContent || '').trim();
                    if (t) sups.push(t);
                });
            }
        } catch (e) {}
    }

    const sup = sups.join(' ');
    const txt = ((primary && primary.textContent) || (node.textContent) || '').trim();
    return { sup, txt: txt.slice(0, 500) };
}
"""
                        )
                        if isinstance(sup_info, dict):
                            sup_text = str(sup_info.get('sup') or '')
                            # 只从 sup_text 里保留符号（不要取数字，避免跨作者污染）
                            markers = "".join(re.findall(r"[\*#†‡]", sup_text))

                            # 有些站点不会把数字放进 <sup>，而是直接跟在名字后面（如 "Zeping Liu 12"）
                            near_txt = str(sup_info.get('txt') or '')
                            if near_txt:
                                # 只在“当前作者名附近”抽数字，避免一个容器里多个作者互相污染
                                scope = near_txt
                                if author_name:
                                    near_norm = _norm_for_match(near_txt)
                                    an_norm = _norm_for_match(author_name)
                                    pos = near_norm.find(an_norm) if an_norm else -1

                                    # 兜底：用姓氏/前两词定位（应对页面把连字符/空白改写）
                                    if pos < 0 and an_norm:
                                        parts = [p for p in an_norm.split() if p]
                                        if len(parts) >= 2:
                                            key2 = " ".join(parts[-2:])
                                            pos = near_norm.find(key2)
                                        elif len(parts) == 1:
                                            pos = near_norm.find(parts[0])

                                    if pos >= 0:
                                        tail_norm = near_norm[pos + len(an_norm) :]
                                        # 截到下一个作者名之前（在规范化文本中定位）
                                        stop = len(tail_norm)
                                        for other in unique_meta:
                                            if not other:
                                                continue
                                            other_norm = _norm_for_match(other)
                                            if not other_norm or other_norm == an_norm:
                                                continue
                                            op = tail_norm.find(other_norm)
                                            if 0 <= op < stop:
                                                stop = op
                                        scope_norm = tail_norm[:stop]
                                        # 再截到分隔符前（逗号/分号/换行在 norm 后可能变成空格，用关键词截断）
                                        scope_norm = re.split(r"\b(doi|volume|issue)\b", scope_norm, maxsplit=1)[0]
                                        scope = scope_norm

                                extra = re.findall(r"(?<!\d)(\d{1,2})(?!\d)", str(scope))
                                for x in extra:
                                    try:
                                        n = int(x)
                                        # 限制范围，避免把年份等误当角标
                                        if 1 <= n <= 99:
                                            aff_nums.append(n)
                                    except Exception:
                                        continue

                                # 同样在 scope 中补抓常见权益角标（*, #, †, ‡）
                                if scope:
                                    markers = (markers + "".join(re.findall(r"[\*#†‡]", scope))).strip()

                            # 去重且保序
                            dedup = []
                            seen_n = set()
                            for x in aff_nums:
                                if x in seen_n:
                                    continue
                                seen_n.add(x)
                                dedup.append(x)
                            aff_nums = dedup

                            # 保护：如果提取到了“几乎全部单位编号”，大概率是容器污染，直接清空
                            if meta_aff_map and len(aff_nums) >= max(len(meta_aff_map) - 1, 6):
                                aff_nums = []
                    except Exception:
                        pass

                    tip = ""
                    try:
                        el.hover(timeout=3000)
                        page.wait_for_timeout(300)
                        tip = _collect_visible_popover_text(page)
                    except Exception:
                        try:
                            el.click(timeout=2000)
                            page.wait_for_timeout(300)
                            tip = _collect_visible_popover_text(page)
                        except Exception:
                            tip = ""

                    flags = _infer_flags_from_text(tip)
                    affiliation = _infer_affiliation_from_text(tip)

                    has_mail_icon = False
                    emails: List[str] = []

                    try:
                        has_mail_icon = bool(
                            el.evaluate(
                                """
(node) => {
  const root = node.closest('li, div, span, p') || node.parentElement || node;
  if (!root) return false;
  const sels = [
    'a[href^="mailto:"]',
    '[aria-label*="mail" i]',
    '[aria-label*="email" i]',
    '[title*="mail" i]',
    '[title*="email" i]',
    'svg[aria-label*="mail" i]',
    'svg[aria-label*="email" i]'
  ];
  for (const sel of sels) {
    if (root.querySelector(sel)) return true;
  }
  return false;
}
"""
                            )
                        )
                    except Exception:
                        has_mail_icon = False

                    try:
                        emails = el.evaluate(
                            """
(node) => {
  const root = node.closest('li, div, span, p') || node.parentElement || node;
  if (!root) return [];
  const links = Array.from(root.querySelectorAll('a[href^="mailto:"]'));
  const out = [];
  for (const a of links) {
    const href = (a.getAttribute('href') || '').trim();
    if (!href) continue;
    const v = href.replace(/^mailto:/i, '').split('?')[0].trim();
    if (v) out.push(v);
  }
  return out.slice(0, 5);
}
"""
                        )
                        if not isinstance(emails, list):
                            emails = []
                        emails = [str(e).strip() for e in emails if e and str(e).strip()]
                    except Exception:
                        emails = []

                    if has_mail_icon or emails:
                        flags["is_corresponding"] = True

                    # '*' 角标常代表通讯作者
                    if '*' in markers:
                        flags["is_corresponding"] = True

                    # meta email 作为弱线索
                    if meta_emails and len(authors) < len(meta_emails):
                        try:
                            maybe_email = str(meta_emails[len(authors)]).strip()
                            if maybe_email and email_re.search(maybe_email):
                                flags["is_corresponding"] = True
                        except Exception:
                            pass

                    return {
                        "tooltip": tip,
                        "affiliation": affiliation,
                        "affiliation_numbers": aff_nums,
                        "is_corresponding": bool(flags.get("is_corresponding")),
                        "is_co_first": bool(flags.get("is_co_first")),
                        "has_mail_icon": has_mail_icon,
                        "emails": emails,
                        "markers": markers,
                    }

                # 1) meta 引导：按 citation_author 精确找文本节点
                seen = set()
                unique_meta: List[str] = []
                for n in meta_names:
                    s = str(n or "").strip()
                    if not s or s in seen:
                        continue
                    seen.add(s)
                    unique_meta.append(s)

                for n in unique_meta[:max_authors]:
                    if _contains_ignored_phrase(n):
                        continue
                    el = None
                    try:
                        el = page.query_selector(f"xpath=//*[normalize-space(text())={_xpath_literal(n)}]")
                        if not el:
                            el = page.query_selector(f"xpath=//*[contains(normalize-space(.), {_xpath_literal(n)})]")
                    except Exception:
                        el = None
                    if not el:
                        continue

                    info = _extract_signals(el, author_name=n)
                    if info.get("skip"):
                        continue

                    authors.append(
                        {
                            "name": n,
                            "affiliation": info.get("affiliation") or "",
                            "affiliations": [],
                            "position": len(authors) + 1,
                            "is_corresponding": bool(info.get("is_corresponding")),
                            "is_co_first": bool(info.get("is_co_first")),
                            "markers": info.get("markers") or "",
                            "affiliation_numbers": info.get("affiliation_numbers") or [],
                            "has_mail_icon": bool(info.get("has_mail_icon")),
                            "emails": info.get("emails") or [],
                            "source": "meta-guided",
                        }
                    )
                    raw_tooltips.append(
                        {
                            "name": n,
                            "tooltip": info.get("tooltip") or "",
                            "markers": info.get("markers") or "",
                            "has_mail_icon": bool(info.get("has_mail_icon")),
                            "emails": info.get("emails") or [],
                        }
                    )

                # 2) meta-guided 没命中时才启发式扫描
                if not authors:
                    selectors = [
                        '[data-test="author-name"]',
                        '[data-testid*="author" i]',
                        'a[class*="author" i]',
                        'span[class*="author" i]',
                        'li[class*="author" i] a',
                    ]
                    elements = []
                    for sel in selectors:
                        try:
                            elements.extend(page.query_selector_all(sel) or [])
                        except Exception:
                            continue

                    seen_names = set()
                    for el in elements[: max_authors * 3]:
                        if len(authors) >= max_authors:
                            break
                        try:
                            raw_name = (el.inner_text() or "").strip()
                            if not raw_name:
                                raw_name = (el.get_attribute("aria-label") or el.get_attribute("title") or "").strip()
                        except Exception:
                            raw_name = ""
                        raw_name = re.sub(r"\s+", " ", raw_name).strip()
                        if not raw_name or len(raw_name) < 2:
                            continue

                        markers_found = re.findall(r"[\*#†‡]+", raw_name)
                        markers = "".join(markers_found) if markers_found else ""
                        name = re.sub(r"[\*#†‡]+", "", raw_name).strip()
                        if not name or len(name) < 2:
                            continue
                        if _contains_ignored_phrase(name):
                            continue
                        if any(k in name.lower() for k in ["author", "authors", "view", "download", "share"]):
                            continue
                        if name in seen_names:
                            continue

                        if meta_name_keys:
                            k = _name_key(name)
                            if k and k not in meta_name_keys:
                                continue

                        info = _extract_signals(el, author_name=name)
                        if info.get("skip"):
                            continue

                        corr = bool(info.get("is_corresponding")) or ("*" in markers) or bool(info.get("emails"))
                        cofirst = bool(info.get("is_co_first")) or ("#" in markers) or ("†" in markers) or ("‡" in markers)

                        aff_nums = info.get('affiliation_numbers') or []
                        if not isinstance(aff_nums, list):
                            aff_nums = []

                        authors.append(
                            {
                                "name": name,
                                "affiliation": info.get("affiliation") or "",
                                "affiliations": [],
                                "position": len(authors) + 1,
                                "is_corresponding": bool(corr),
                                "is_co_first": bool(cofirst),
                                "markers": (markers + (info.get('markers') or '')).strip(),
                                "affiliation_numbers": aff_nums,
                                "has_mail_icon": bool(info.get("has_mail_icon")),
                                "emails": info.get("emails") or [],
                                "source": "hover",
                            }
                        )
                        raw_tooltips.append(
                            {
                                "name": name,
                                "tooltip": info.get("tooltip") or "",
                                "markers": markers,
                                "has_mail_icon": bool(info.get("has_mail_icon")),
                                "emails": info.get("emails") or [],
                            }
                        )
                        seen_names.add(name)

                # 3) 白名单过滤 + meta-only 兜底
                if meta_name_keys:
                    filtered = []
                    for a in authors:
                        k = _name_key(a.get("name"))
                        if k and k in meta_name_keys:
                            filtered.append(a)
                    authors = filtered

                # 3.5) 用 meta 机构（1..N）按角标数字映射到作者
                if meta_aff_map and authors:
                    for a in authors:
                        nums = a.get('affiliation_numbers') or []
                        if not isinstance(nums, list):
                            nums = []
                        affs: List[str] = []
                        for num in nums:
                            try:
                                n = int(num)
                            except Exception:
                                continue
                            v = meta_aff_map.get(n)
                            if v and v not in affs:
                                affs.append(v)
                        if affs:
                            a['affiliations'] = affs
                            a['affiliation'] = '; '.join(affs)

                # 3.6) 共一作者：页面出现 “contributed equally” 时尽量标记
                try:
                    equal_note = bool(
                        page.evaluate(
                            """
() => {
  const t = (document.body && (document.body.innerText || document.body.textContent) || '').toLowerCase();
  return t.includes('contributed equally') || t.includes('equal contribution');
}
"""
                        )
                    )
                except Exception:
                    equal_note = False

                if equal_note and authors:
                    marked = [
                        a for a in authors
                        if any(sym in str(a.get('markers') or '') for sym in ['#', '†', '‡'])
                    ]
                    if marked:
                        for a in marked:
                            a['is_co_first'] = True
                    elif len(authors) >= 2:
                        authors[0]['is_co_first'] = True
                        authors[1]['is_co_first'] = True

                if not authors and meta_names:
                    seen_names = set()
                    for n in meta_names[:max_authors]:
                        s = str(n or "").strip()
                        if not s or s in seen_names:
                            continue
                        seen_names.add(s)
                        authors.append(
                            {
                                "name": s,
                                "affiliation": "",
                                "affiliations": [],
                                "position": len(authors) + 1,
                                "is_corresponding": False,
                                "is_co_first": False,
                                "source": "meta:citation_author",
                            }
                        )

                result: Dict[str, Any] = {
                    "doi": doi,
                    "final_url": page.url,
                    "authors": authors,
                    "raw_tooltips": raw_tooltips,
                    "meta": {
                        "citation_author": meta_names,
                        "citation_author_institution": meta_institutions,
                        "citation_author_email": meta_emails,
                    },
                }

                if save_sidecar_json:
                    try:
                        os.makedirs(VISUAL_SLICE_DIR, exist_ok=True)
                        with open(sidecar_path, "w", encoding="utf-8") as f:
                            json.dump(result, f, ensure_ascii=False, indent=2)
                        print(f"[WebDriver] 🧾 已保存 hover 作者数据: {sidecar_path}")
                    except Exception:
                        pass

                browser.close()
                return result if authors else None

        except Exception as e:
            print(f"[WebDriver] ❌ hover 提取失败: {e}")
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

            print("[WebDriver] 🔀 检测到选择页面，自动选择境内链接...")

            current_url = page.url
            clicked = False

            try:
                links = page.query_selector_all('a[href^="http"]')

                domestic_marked = []
                other_safe = []

                skip_keywords = [
                    "mirror",
                    "abroad",
                    "international",
                    "overseas",
                    "oversea",
                    "foreign",
                    "external",
                    "proxy",
                    "境外",
                    "国际",
                    "english",
                ]

                for link in links:
                    href = link.get_attribute("href")
                    text = link.inner_text()

                    if not href or not href.strip():
                        continue

                    if "(境内)" in text or "(境内" in text:
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

            if clicked and page.url == current_url:
                print("[WebDriver] ⚠️ 选择页面点击后 URL 未变化")

        except Exception as e:
            print(f"[WebDriver] ⚠️ 选择页面检测失败: {e}")

    def _close_cookie_popup(self, page):
        """自动关闭 Cookie 弹窗（尽力而为，不保证每站点都有效）"""
        try:
            print("[WebDriver] 🍪 尝试关闭 Cookie 弹窗...")

            selectors = [
                'button:has-text("Accept")',
                'button:has-text("I agree")',
                'button:has-text("Agree")',
                'button:has-text("OK")',
                'button:has-text("Got it")',
                'button:has-text("接受")',
                'button:has-text("同意")',
                'button:has-text("确定")',
                '[aria-label*="accept" i]',
            ]

            for sel in selectors:
                try:
                    btn = page.query_selector(sel)
                    if btn:
                        btn.click(timeout=1500)
                        page.wait_for_timeout(500)
                        return
                except Exception:
                    continue

        except Exception:
            pass
