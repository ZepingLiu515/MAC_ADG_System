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

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional

from .webdriver_hover import extract_author_hover_data as _extract_author_hover_data
from .webdriver_page_actions import (
    close_cookie_popup,
    handle_selection_page,
    scroll_to_top,
    wait_for_academic_elements,
    wait_for_network_idle,
)
from .webdriver_screenshot import (
    get_webpage_screenshot_async as _get_webpage_screenshot_async,
    get_webpage_screenshot_sync as _get_webpage_screenshot_sync,
)
from .webdriver_roi import get_author_block_screenshot_sync as _get_author_block_screenshot_sync

try:
    from playwright.sync_api import sync_playwright
except (ImportError, Exception) as e:
    print(f"[WARNING] Playwright import failed: {e}")
    sync_playwright = None

try:
    from playwright.async_api import async_playwright
except (ImportError, Exception):
    async_playwright = None

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

    def _ensure_windows_event_loop_policy(self) -> None:
        """Ensure Windows event loop policy supports subprocesses (Playwright requirement)."""
        if os.name != "nt":
            return
        try:
            policy = asyncio.get_event_loop_policy()
            if hasattr(asyncio, "WindowsProactorEventLoopPolicy"):
                if not isinstance(policy, asyncio.WindowsProactorEventLoopPolicy):
                    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except Exception:
            pass

    def _get_proxy(self) -> Optional[Dict[str, str]]:
        proxy_server = os.getenv("PLAYWRIGHT_PROXY")
        proxy_user = os.getenv("PLAYWRIGHT_PROXY_USERNAME")
        proxy_pass = os.getenv("PLAYWRIGHT_PROXY_PASSWORD")
        if not proxy_server:
            return None
        proxy: Dict[str, str] = {"server": proxy_server}
        if proxy_user and proxy_pass:
            proxy["username"] = proxy_user
            proxy["password"] = proxy_pass
        return proxy

    def _get_headless(self) -> bool:
        headless_env = os.getenv("PLAYWRIGHT_HEADLESS", "1").strip()
        return not (headless_env in {"0", "false", "False", "no", "NO"})

    def _get_slow_mo(self) -> int:
        try:
            return int(os.getenv("PLAYWRIGHT_SLOWMO_MS", "0").strip() or "0")
        except Exception:
            return 0

    def _get_device_scale_factor(self) -> float:
        """Device pixel ratio for screenshots.

        Higher values increase effective screenshot DPI and often improve OCR accuracy
        (especially for small author lines / superscripts).
        """

        raw = os.getenv("PLAYWRIGHT_DEVICE_SCALE_FACTOR", "2").strip()
        try:
            v = float(raw)
        except Exception:
            return 2.0
        if v <= 0:
            return 2.0
        # Guardrail: avoid huge images by default
        return min(max(v, 1.0), 4.0)

    def _get_launch_options(self) -> Dict[str, Any]:
        opts: Dict[str, Any] = {
            "headless": self._get_headless(),
            "slow_mo": self._get_slow_mo(),
            "args": ["--disable-blink-features=AutomationControlled"],
        }
        channel = os.getenv("PLAYWRIGHT_CHANNEL")
        if channel:
            opts["channel"] = channel
        proxy = self._get_proxy()
        if proxy:
            opts["proxy"] = proxy
        return opts

    def _get_context_options(self) -> Dict[str, Any]:
        return {
            "viewport": {"width": 1440, "height": 1200},
            "device_scale_factor": self._get_device_scale_factor(),
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
            "extra_http_headers": {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
                "Cache-Control": "max-age=0",
                "DNT": "1",
            },
            "locale": "en-US",
        }

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

    def _run_async(self, coro):
        """Run async Playwright safely, even if an event loop is already running."""
        self._ensure_windows_event_loop_policy()
        try:
            return asyncio.run(coro)
        except RuntimeError as exc:
            if "asyncio.run() cannot be called" in str(exc):
                with ThreadPoolExecutor(max_workers=1) as executor:
                    return executor.submit(lambda: asyncio.run(coro)).result()
            raise

    def get_webpage_screenshot(
        self,
        doi: str,
        landing_page_url: Optional[str] = None,
        *,
        full_page: bool = False,
        section: Optional[str] = None,
        save_suffix: Optional[str] = None,
    ) -> Optional[str]:
        """导航到 DOI 页面并获取截图。

        对外 API 保持不变；内部实现已拆分到 `backend/utils/webdriver_screenshot.py`。
        """

        if sync_playwright is None:
            print("[WebDriver] Playwright not installed")
            return None

        self._ensure_windows_event_loop_policy()

        doi_url = f"https://doi.org/{doi}"
        safe_doi = doi.replace("/", "_")
        suffix = str(save_suffix).strip() if save_suffix else ""
        base_name = f"{safe_doi}_{suffix}.png" if suffix else f"{safe_doi}.png"
        save_path = os.path.join(VISUAL_SLICE_DIR, base_name)
        blocked_save_path = os.path.join(VISUAL_SLICE_DIR, f"{safe_doi}_blocked.png")

        try:
            return _get_webpage_screenshot_sync(
                sync_playwright=sync_playwright,
                stealth_sync=stealth_sync,
                visual_slice_dir=VISUAL_SLICE_DIR,
                doi=doi,
                landing_page_url=landing_page_url,
                full_page=bool(full_page),
                section=section,
                save_suffix=save_suffix,
                launch_options=self._get_launch_options(),
                context_options=self._get_context_options(),
                goto_timeout_ms=self._goto_timeout_ms(default=90000),
                handle_selection_page=handle_selection_page,
                close_cookie_popup=close_cookie_popup,
                wait_for_network_idle=wait_for_network_idle,
                scroll_to_top=scroll_to_top,
                wait_for_academic_elements=wait_for_academic_elements,
            )

        except NotImplementedError:
            try:
                return self._run_async(
                    _get_webpage_screenshot_async(
                        async_playwright=async_playwright,
                        doi_url=doi_url,
                        landing_page_url=landing_page_url,
                        save_path=save_path,
                        blocked_save_path=blocked_save_path,
                        launch_options=self._get_launch_options(),
                        context_options=self._get_context_options(),
                        goto_timeout_ms=self._goto_timeout_ms(default=90000),
                    )
                )
            except Exception as exc:
                print(f"[WebDriver] Async screenshot failed: {exc}")
                return None
        except Exception as exc:
            print(f"[WebDriver] Error: {exc}")
            return None

    def extract_author_hover_data(
        self,
        doi: str,
        landing_page_url: Optional[str] = None,
        max_authors: int = 30,
        save_sidecar_json: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """从网页交互（hover/click）中提取作者单位与权益线索。

        对外 API 保持不变；内部实现已拆分到 `backend/utils/webdriver_hover.py`。
        """

        if sync_playwright is None:
            print("[WebDriver] Playwright not installed")
            return None

        self._ensure_windows_event_loop_policy()

        try:
            return _extract_author_hover_data(
                sync_playwright=sync_playwright,
                stealth_sync=stealth_sync,
                visual_slice_dir=VISUAL_SLICE_DIR,
                doi=doi,
                landing_page_url=landing_page_url,
                max_authors=int(max_authors or 30),
                save_sidecar_json=bool(save_sidecar_json),
                launch_options=self._get_launch_options(),
                context_options=self._get_context_options(),
                goto_timeout_ms=self._goto_timeout_ms(default=90000),
                handle_selection_page=handle_selection_page,
                close_cookie_popup=close_cookie_popup,
            )
        except Exception as exc:
            print(f"[WebDriver] Hover extraction failed: {exc}")
            return None

    def get_author_block_screenshot(
        self,
        doi: str,
        landing_page_url: Optional[str] = None,
        *,
        save_suffix: Optional[str] = None,
    ) -> Optional[str]:
        """获取作者区（DOM 元素）的 ROI 截图，用于提升作者行 OCR 准确率。

        这是一个最佳努力的启发式截图：会根据 `meta[name=citation_author]` 在页面中定位
        可能包含作者列表的块级元素，并对该元素进行截图。
        """

        if sync_playwright is None:
            print("[WebDriver] Playwright not installed")
            return None

        self._ensure_windows_event_loop_policy()

        try:
            return _get_author_block_screenshot_sync(
                sync_playwright=sync_playwright,
                stealth_sync=stealth_sync,
                visual_slice_dir=VISUAL_SLICE_DIR,
                doi=doi,
                landing_page_url=landing_page_url,
                save_suffix=save_suffix,
                launch_options=self._get_launch_options(),
                context_options=self._get_context_options(),
                goto_timeout_ms=self._goto_timeout_ms(default=90000),
                handle_selection_page=handle_selection_page,
                close_cookie_popup=close_cookie_popup,
                wait_for_network_idle=wait_for_network_idle,
                scroll_to_top=scroll_to_top,
            )
        except Exception as exc:
            print(f"[WebDriver] Author ROI screenshot failed: {exc}")
            return None
