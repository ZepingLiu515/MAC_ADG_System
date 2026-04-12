"""Screenshot capture implementation used by `WebDriverAdapter`.

Kept separate to keep `webdriver.py` small and focused.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, Optional


def try_expand_common_sections(page: Any) -> None:
    """Best-effort expand for common 'see more/show more' prompts.

    This is intentionally lightweight and safe. It runs before screenshots/ROI capture so
    OCR doesn't ingest UI metric text that is hidden behind expandable blocks.
    """

    js = r"""
(() => {
    const norm = (s) => (s || '').toLowerCase().replace(/\s+/g, ' ').trim();
    const isVisible = (el) => {
        try {
            if (!el) return false;
            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            return style && style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 2 && rect.height > 2;
        } catch (e) { return false; }
    };
    const banned = (el) => {
        try { return !!(el && el.closest && el.closest('nav,footer,header,aside')); } catch (e) { return false; }
    };
    const getText = (el) => {
        try { return (el.innerText || el.textContent || '').trim(); } catch (e) { return ''; }
    };
    const hasVisibleTextMarker = (needle) => {
        const candidates = [];
        const sels = ['button','a','summary','[role="button"]','[aria-expanded]'];
        for (const sel of sels) {
            try { document.querySelectorAll(sel).forEach(el => candidates.push(el)); } catch (e) {}
        }
        for (const el of candidates) {
            if (!isVisible(el) || banned(el)) continue;
            const t = norm(getText(el));
            if (!t) continue;
            if (t.includes(needle)) return true;
        }
        return false;
    };

    const moreMarkers = ['see more','show more','view more','read more','show all','see all'];
    const candidates = [];
    const sels = ['button','a','summary','[role="button"]','[aria-expanded]'];
    for (const sel of sels) {
        try { document.querySelectorAll(sel).forEach(el => candidates.push(el)); } catch (e) {}
    }
    let clicks = 0;

    // 1) Try to open author/affiliation panels (avoid collapsing if already open).
    const alreadyOpen = hasVisibleTextMarker('hide author information');
    if (!alreadyOpen) {
        for (const el of candidates) {
            if (clicks >= 2) break;
            if (!isVisible(el) || banned(el)) continue;
            const t = norm(getText(el));
            if (!t) continue;
            const isAuthorInfo = (t.includes('author information') && (t.includes('affiliation') || t.includes('affiliations')));
            const isAuthorsAff = (t.includes('authors') && (t.includes('affiliation') || t.includes('affiliations')));
            if (!(isAuthorInfo || isAuthorsAff)) continue;
            try { el.click(); clicks++; } catch (e) {}
        }
    }

    // 2) Expand "see more/show more" style controls.
    for (const el of candidates) {
        if (clicks >= 3) break;
        if (!isVisible(el) || banned(el)) continue;
        const t = norm(getText(el));
        if (!t) continue;
        if (!moreMarkers.some(m => t === m || t.includes(m))) continue;
        try {
            el.click();
            clicks++;
        } catch (e) {}
    }
    return clicks;
})();
"""

    try:
        page.evaluate(js)
    except Exception:
        pass


async def get_webpage_screenshot_async(
    *,
    async_playwright: Any,
    doi_url: str,
    landing_page_url: Optional[str],
    save_path: str,
    blocked_save_path: str,
    launch_options: Dict[str, Any],
    context_options: Dict[str, Any],
    goto_timeout_ms: int,
) -> Optional[str]:
    """Async fallback for Playwright screenshot capture."""
    if async_playwright is None:
        return None

    async with async_playwright() as p:
        browser = await p.chromium.launch(**launch_options)
        context = await browser.new_context(**context_options)

        page = await context.new_page()
        response = None
        try:
            response = await page.goto(doi_url, wait_until="domcontentloaded", timeout=goto_timeout_ms)
        except Exception:
            if landing_page_url and isinstance(landing_page_url, str):
                landing_page_url = landing_page_url.strip()
            if landing_page_url and landing_page_url != doi_url:
                response = await page.goto(
                    landing_page_url,
                    wait_until="domcontentloaded",
                    timeout=goto_timeout_ms,
                )
            else:
                await browser.close()
                return None

        if response and response.status >= 400:
            try:
                await page.screenshot(path=blocked_save_path)
            except Exception:
                pass
            await browser.close()
            return None

        try:
            await page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
        await page.wait_for_timeout(3000)

        selectors = [
            "meta[name='citation_title']",
            "h1",
            "header h1",
            ".article-title",
            "#title",
            "#abstract",
            "section[aria-label*='abstract' i]",
            ".abstract",
            "div.abstract",
            "article",
        ]
        per_wait = max(int(8000 / max(len(selectors), 1)), 500)
        for sel in selectors:
            try:
                await page.wait_for_selector(sel, timeout=per_wait)
                break
            except Exception:
                continue

        try:
            await page.evaluate("window.scrollTo(0, 0)")
        except Exception:
            pass

        try:
            await page.screenshot(path=save_path)
        finally:
            await browser.close()
        return save_path


def try_activate_section(page: Any, section: Optional[str]) -> None:
    """Best-effort activation of a page section/tab without relying on scrolling."""

    sec = str(section or "").strip().lower()
    if not sec:
        return

    if sec in {"authors", "author"}:
        try:
            page.get_by_role("tab", name=re.compile(r"^Authors$", re.IGNORECASE)).first.click(timeout=1500)
            return
        except Exception:
            pass

        js = r"""
(() => {
  const candidates = Array.from(document.querySelectorAll('a,button,[role="tab"],[role="button"],li'));
  for (const el of candidates) {
    const txt = (el.innerText || el.textContent || '').trim();
    if (!txt) continue;
    if (txt.toLowerCase() !== 'authors') continue;
    try { el.click(); return true; } catch (e) {}
    try { el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true })); return true; } catch (e2) {}
  }
  return false;
})();
"""
        try:
            page.evaluate(js)
        except Exception:
            pass


def get_webpage_screenshot_sync(
    *,
    sync_playwright: Any,
    stealth_sync: Any,
    visual_slice_dir: str,
    doi: str,
    landing_page_url: Optional[str],
    full_page: bool,
    section: Optional[str],
    save_suffix: Optional[str],
    launch_options: Dict[str, Any],
    context_options: Dict[str, Any],
    goto_timeout_ms: int,
    handle_selection_page: Any,
    close_cookie_popup: Any,
    wait_for_network_idle: Any,
    scroll_to_top: Any,
    wait_for_academic_elements: Any,
) -> Optional[str]:
    """Navigate to DOI page and capture a screenshot."""

    if sync_playwright is None:
        print("[WebDriver] Playwright not installed")
        return None

    try:
        os.makedirs(visual_slice_dir, exist_ok=True)
    except Exception:
        pass

    doi_url = f"https://doi.org/{doi}"
    safe_doi = doi.replace("/", "_")
    suffix = str(save_suffix).strip() if save_suffix else ""
    base_name = f"{safe_doi}_{suffix}.png" if suffix else f"{safe_doi}.png"
    save_path = os.path.join(visual_slice_dir, base_name)
    blocked_save_path = os.path.join(visual_slice_dir, f"{safe_doi}_blocked.png")

    def _use_cached_screenshot(reason: str) -> Optional[str]:
        if os.path.exists(save_path):
            print(f"[WebDriver] Using cached screenshot ({reason}): {save_path}")
            return save_path
        return None

    print(f"[WebDriver] Launching browser: {doi_url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(**launch_options)
        context = browser.new_context(**context_options)
        page = context.new_page()
        try:
            stealth_sync(page)
        except Exception:
            pass

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

        print("[WebDriver] Navigating...")
        response = None
        try:
            response = page.goto(doi_url, wait_until="domcontentloaded", timeout=goto_timeout_ms)
        except Exception as exc:
            print(f"[WebDriver] doi.org navigation failed: {exc}")
            if landing_page_url and isinstance(landing_page_url, str):
                landing_page_url = landing_page_url.strip()
            if landing_page_url and landing_page_url != doi_url:
                try:
                    print(f"[WebDriver] Trying landing page: {landing_page_url}")
                    response = page.goto(landing_page_url, wait_until="domcontentloaded", timeout=goto_timeout_ms)
                except Exception as exc2:
                    print(f"[WebDriver] Landing page navigation failed: {exc2}")
            if response is None:
                cached = _use_cached_screenshot("navigation failed")
                browser.close()
                return cached

        blocked = (response and response.status >= 400) or _is_block_page()
        if blocked:
            print(f"[WebDriver] HTTP {getattr(response, 'status', None)} blocked; retrying...")

            context2 = browser.new_context(
                viewport={"width": 1440, "height": 1200},
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
            try:
                stealth_sync(page)
            except Exception:
                pass

            response = page.goto(doi_url, wait_until="domcontentloaded", timeout=goto_timeout_ms)
            blocked = (response and response.status >= 400) or _is_block_page()

            if blocked:
                print(f"[WebDriver] Retry failed HTTP {getattr(response, 'status', None)}")

                if landing_page_url and isinstance(landing_page_url, str):
                    landing_page_url = landing_page_url.strip()
                if landing_page_url and landing_page_url != doi_url:
                    print(f"[WebDriver] Trying publisher landing page: {landing_page_url}")
                    try:
                        response = page.goto(landing_page_url, wait_until="domcontentloaded", timeout=goto_timeout_ms)
                        blocked2 = (response and response.status >= 400) or _is_block_page()
                        if blocked2:
                            print(f"[WebDriver] Landing page blocked HTTP {getattr(response, 'status', None)}")
                            try:
                                page.screenshot(path=blocked_save_path)
                                print(f"[WebDriver] Saved blocked-page screenshot: {blocked_save_path}")
                            except Exception:
                                pass
                            cached = _use_cached_screenshot("blocked landing page")
                            browser.close()
                            return cached
                    except Exception as exc3:
                        print(f"[WebDriver] Landing page navigation failed: {exc3}")
                        try:
                            page.screenshot(path=blocked_save_path)
                            print(f"[WebDriver] Saved blocked-page screenshot: {blocked_save_path}")
                        except Exception:
                            pass
                        cached = _use_cached_screenshot("landing page failed")
                        browser.close()
                        return cached
                else:
                    try:
                        page.screenshot(path=blocked_save_path)
                        print(f"[WebDriver] Saved blocked-page screenshot: {blocked_save_path}")
                    except Exception:
                        pass
                    cached = _use_cached_screenshot("blocked doi.org")
                    browser.close()
                    return cached

        page.wait_for_timeout(3000)
        handle_selection_page(page)
        close_cookie_popup(page)
        wait_for_network_idle(page, timeout_ms=8000)
        scroll_to_top(page)
        wait_for_academic_elements(page, timeout_ms=8000)

        # Expand common collapsed blocks before capturing the screenshot.
        try_expand_common_sections(page)

        if section:
            try:
                try_activate_section(page, section)
            except Exception:
                pass

        # Some sites only reveal the 'see more' controls after switching tabs.
        try_expand_common_sections(page)

        scroll_to_top(page)
        page.screenshot(path=save_path, full_page=bool(full_page))
        print(f"[WebDriver] Screenshot saved: {save_path}")

        browser.close()
        return save_path
