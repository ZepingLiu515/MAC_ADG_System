"""Page-level helper actions for Playwright pages.

This module contains small, reusable, side-effectful helpers used by
`WebDriverAdapter` screenshot and hover extraction.

It must not import project modules with heavy dependencies.
"""

from __future__ import annotations

from typing import Any


def scroll_to_top(page: Any) -> None:
    try:
        page.evaluate("window.scrollTo(0, 0)")
    except Exception:
        pass


def wait_for_network_idle(page: Any, timeout_ms: int = 8000) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except Exception:
        pass


def wait_for_academic_elements(page: Any, timeout_ms: int = 8000) -> bool:
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
    per_wait = max(int(timeout_ms / max(len(selectors), 1)), 500)
    for sel in selectors:
        try:
            handle = page.wait_for_selector(sel, timeout=per_wait)
            if handle:
                return True
        except Exception:
            continue
    return False


def handle_selection_page(page: Any) -> None:
    """Handle CNKI multi-link selection page by choosing domestic/safe link."""
    try:
        title = page.title()
        content = page.content()

        selection_keywords = ["多重解析", "选择", "重定向", "镜像"]
        is_selection_page = any(keyword in title or keyword in content for keyword in selection_keywords)

        if not is_selection_page:
            return

        print("[WebDriver] Selection page detected; choosing a safe link...")

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
                marker = "[domestic]" if domestic_marked else "[selected]"
                print(f"[WebDriver] {marker} Clicking link: {text}")
                link.click()
                page.wait_for_navigation(timeout=30000)
                page.wait_for_timeout(2000)
                clicked = True

        except Exception as exc:
            print(f"[WebDriver] Selection page handling failed: {exc}")

        if clicked and page.url == current_url:
            print("[WebDriver] Selection click did not change URL")

    except Exception as exc:
        print(f"[WebDriver] Selection page detection failed: {exc}")


def _cookie_overlay_present(page: Any) -> bool:
    js = """
(() => {
  const keys = ['cookie', 'consent', 'privacy'];
  const nodes = Array.from(document.querySelectorAll('div, section'));
  for (const el of nodes) {
    const text = (el.innerText || '').toLowerCase();
    const meta = ((el.id || '') + ' ' + (el.className || '') + ' ' + (el.getAttribute('aria-label') || '')).toLowerCase();
    const hit = keys.some(k => text.includes(k) || meta.includes(k));
    if (!hit) continue;
    const style = window.getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    const visible = style && style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 10 && rect.height > 10;
    if (visible) return true;
  }
  return false;
})();
"""
    try:
        return bool(page.evaluate(js))
    except Exception:
        return False


def _hide_cookie_overlays(page: Any) -> None:
    css = """
div[class*="cookie" i],
div[id*="cookie" i],
div[class*="consent" i],
div[id*="consent" i],
div[class*="privacy" i],
div[id*="privacy" i],
div[aria-label*="cookie" i],
div[aria-label*="consent" i],
div[aria-label*="privacy" i],
section[class*="cookie" i],
section[id*="cookie" i],
section[class*="consent" i],
section[id*="consent" i],
section[class*="privacy" i],
section[id*="privacy" i],
section[aria-label*="cookie" i],
section[aria-label*="consent" i],
section[aria-label*="privacy" i] {
  display: none !important;
  visibility: hidden !important;
  pointer-events: none !important;
}
"""
    try:
        page.add_style_tag(content=css)
    except Exception:
        pass


def close_cookie_popup(page: Any) -> None:
    """Best-effort cookie consent dismissal + overlay hiding."""
    try:
        print("[WebDriver] Closing cookie popup (best-effort)...")
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
            '[aria-label*="consent" i]',
            '[aria-label*="cookie" i]',
        ]

        clicked = False
        for sel in selectors:
            try:
                locator = page.locator(sel)
                if locator.count() > 0:
                    locator.first.click(timeout=1500, force=True, no_wait_after=True)
                    clicked = True
                    page.wait_for_timeout(200)
            except Exception:
                continue

        if (not clicked) or _cookie_overlay_present(page):
            _hide_cookie_overlays(page)
    except Exception:
        pass
