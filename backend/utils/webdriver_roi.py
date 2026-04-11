"""ROI/region screenshots using Playwright.

Primary use: capture a tight "author block" screenshot to improve OCR on
small-font author lines / superscripts.

This is intentionally heuristic and best-effort.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional


def get_author_block_screenshot_sync(
    *,
    sync_playwright: Any,
    stealth_sync: Any,
    visual_slice_dir: str,
    doi: str,
    landing_page_url: Optional[str],
    save_suffix: Optional[str],
    launch_options: Dict[str, Any],
    context_options: Dict[str, Any],
    goto_timeout_ms: int,
    handle_selection_page: Any,
    close_cookie_popup: Any,
    wait_for_network_idle: Any,
    scroll_to_top: Any,
) -> Optional[str]:
    """Capture a screenshot of the best-guess author block element.

    Returns the saved image path, or None.
    """

    if sync_playwright is None:
        print("[WebDriver] Playwright not installed")
        return None

    try:
        os.makedirs(visual_slice_dir, exist_ok=True)
    except Exception:
        pass

    doi_url = f"https://doi.org/{doi}"
    safe_doi = doi.replace("/", "_")
    suffix = str(save_suffix).strip() if save_suffix else "author_roi"
    save_path = os.path.join(visual_slice_dir, f"{safe_doi}_{suffix}.png")

    with sync_playwright() as p:
        browser = p.chromium.launch(**launch_options)
        context = browser.new_context(**context_options)
        page = context.new_page()
        try:
            stealth_sync(page)
        except Exception:
            pass

        response = None
        try:
            response = page.goto(doi_url, wait_until="domcontentloaded", timeout=goto_timeout_ms)
        except Exception:
            if landing_page_url and isinstance(landing_page_url, str):
                landing_page_url = landing_page_url.strip()
            if landing_page_url and landing_page_url != doi_url:
                response = page.goto(landing_page_url, wait_until="domcontentloaded", timeout=goto_timeout_ms)
            else:
                browser.close()
                return None

        page.wait_for_timeout(1500)
        try:
            handle_selection_page(page)
        except Exception:
            pass
        try:
            close_cookie_popup(page)
        except Exception:
            pass

        try:
            wait_for_network_idle(page, timeout_ms=6000)
        except Exception:
            pass

        try:
            scroll_to_top(page)
        except Exception:
            pass

        # Pull meta authors as anchors.
        try:
            meta_names = page.evaluate(
                """
(() => Array.from(document.querySelectorAll('meta[name="citation_author"]'))
  .map(m => (m.getAttribute('content') || '').trim())
  .filter(Boolean)
  .slice(0, 30)
 )();
"""
            )
            if not isinstance(meta_names, list):
                meta_names = []
        except Exception:
            meta_names = []

        if True:

                def _save_top_fallback() -> bool:
                        """Always save a ROI image into visual_slice_dir."""

                        try:
                                vs = page.viewport_size or {"width": 1440, "height": 900}
                                vw = int(vs.get("width") or 1440)
                                vh = int(vs.get("height") or 900)
                                h = max(260, min(1100, vh))
                                page.screenshot(
                                        path=save_path,
                                        clip={"x": 0, "y": 0, "width": max(320, vw), "height": h},
                                )
                                print(f"[WebDriver] ROI (fallback-top) saved: {save_path}")
                                return True
                        except Exception:
                                return False

                # First try: compute a best-effort clip rect for the author+affiliation block.
                # We intentionally compute clip in *viewport coordinates* (no scroll offsets).
                clip = None
                try:
                        clip = page.evaluate(
                                r"""
(names) => {
    const norm = (s) => (s || '')
        .toLowerCase()
        .replace(/[-_]/g, ' ')
        .replace(/[^a-z0-9\s]/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();

    const nameNorms = (Array.isArray(names) ? names : [])
        .map(norm)
        .filter(Boolean)
        .slice(0, 12);

    const banned = (el) => !!(el && el.closest && el.closest('nav,footer,aside'));

    const looksLikeCitationBlock = (raw) => {
        const t = norm(raw);
        if (!t) return false;
        if (t.startsWith('citation')) return true;
        const i = t.indexOf('citation');
        if (i >= 0 && i <= 20 && t.includes('citation:')) return true;
        return false;
    };

    const countAffiliationNums = (raw) => {
        const s = (raw || '');
        const r = /(?:^|\s)(\d{1,2})\s*(?:[\.)])?\s*(department|university|hospital|institute|school|college|laboratory|centre|center)\b/gi;
        let m;
        const seen = new Set();
        while ((m = r.exec(s)) !== null) {
            const n = (m[1] || '').trim();
            if (n) seen.add(n);
            if (seen.size >= 10) break;
        }
        return seen.size;
    };

    const containers = Array.from(document.querySelectorAll('main,article,section,div'));
    let best = null;
    let bestScore = -1;

    for (const el of containers) {
        if (!el || banned(el)) continue;
        const raw = (el.innerText || el.textContent || '').trim();
        if (!raw) continue;
        if (raw.length < 60 || raw.length > 12000) continue;
        if (looksLikeCitationBlock(raw)) continue;

        const rect = el.getBoundingClientRect();
        if (rect.width < 360 || rect.height < 60) continue;
        if (rect.top > 1800) continue;

        const affCount = countAffiliationNums(raw);
        if (affCount < 2) continue;

        const txt = norm(raw);
        let hits = 0;
        for (const n of nameNorms) {
            if (n && txt.includes(n)) hits++;
        }

        let score = affCount * 80 + hits * 10;
        score += Math.max(0, 50 - rect.top / 30);
        score -= Math.log(Math.max(1, rect.width * rect.height)) / 2;
        score -= raw.length / 250;

        if (score > bestScore) {
            bestScore = score;
            best = el;
        }
    }

    if (!best) return null;
    const r = best.getBoundingClientRect();
    const vw = Math.max(1, window.innerWidth || 1);
    const vh = Math.max(1, window.innerHeight || 1);
    const x0 = Math.max(0, r.left - 10);
    const y0 = Math.max(0, r.top - 10);
    const w0 = Math.max(50, r.width + 20);
    const h0 = Math.max(50, r.height + 20);
    const x = Math.min(x0, vw - 1);
    const y = Math.min(y0, vh - 1);
    const width = Math.max(10, Math.min(w0, vw - x));
    const height = Math.max(10, Math.min(h0, vh - y));
    return { x, y, width, height };
}
""",
                                meta_names,
                        )
                except Exception:
                        clip = None

                if isinstance(clip, dict) and all(k in clip for k in ("x", "y", "width", "height")):
                        try:
                                page.screenshot(path=save_path, clip=clip)
                                print(f"[WebDriver] ROI author block saved: {save_path}")
                                browser.close()
                                return save_path
                        except Exception:
                                pass

        # Find best element in DOM via JS (returns an element handle).
        handle = None
        try:
            handle = page.evaluate_handle(
                                r"""
(names) => {
  const norm = (s) => (s || '')
    .toLowerCase()
    .replace(/[-_]/g, ' ')
    .replace(/[^a-z0-9\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

  const nameNorms = (Array.isArray(names) ? names : [])
    .map(norm)
    .filter(Boolean)
    .slice(0, 12);

    const banned = (el) => !!(el && el.closest && el.closest('nav,footer,aside'));

    const looksLikeCitationBlock = (raw) => {
        const t = norm(raw);
        if (!t) return false;
        // Only treat as citation block when it clearly looks like the reference paragraph.
        if (t.startsWith('citation')) return true;
        const i = t.indexOf('citation');
        if (i >= 0 && i <= 20 && t.includes('citation:')) return true;
        return false;
    };

    const hasAffiliationListStart = (raw) => {
        // Match lines like:
        // 1. Department of ...
        // 1 Department of ...
        // 2) University ...
        const r = /(?:^|\s)\d{1,2}\s*(?:[\.)])?\s*(department|university|hospital|institute|school|college|laboratory|centre|center)\b/i;
        return r.test(raw || '');
    };

    const countAffiliationLines = (raw) => {
        const s = (raw || '');
        // Count occurrences that look like numbered affiliations, even when the DOM
        // collapses line breaks into spaces.
        const r = /(?:^|\s)(\d{1,2})\s*(?:[\.)])?\s*(department|university|hospital|institute|school|college|laboratory|centre|center)\b/gi;
        let m;
        const seen = new Set();
        while ((m = r.exec(s)) !== null) {
            const n = (m[1] || '').trim();
            if (n) seen.add(n);
            if (seen.size >= 8) break;
        }
        return seen.size;
    };

    const hasInlineAffMarkers = (raw) => {
        // Match short inline markers near names like "Liu 1,2" but avoid years by limiting length.
        const s = (raw || '');
        if (s.length > 220) return false;
        return /\b\d{1,2}(?:\s*,\s*\d{1,2}){1,4}\b/.test(s);
    };

  const candidates = Array.from(document.querySelectorAll('p,li,div,span,section,article'));
  let best = null;
  let bestScore = -1;

    // Pass 1 (AIMS-friendly): anchor on the numbered affiliation list near top.
    // This avoids accidentally matching the "Citation" paragraph which lists all author names.
    try {
        const containers = Array.from(document.querySelectorAll('main,article,section,div'));
        let bestC = null;
        let bestCScore = -1;

        for (const el of containers) {
            if (!el || banned(el)) continue;
            const raw = (el.innerText || el.textContent || '').trim();
            if (!raw) continue;
            if (raw.length < 60 || raw.length > 8000) continue;
            if (looksLikeCitationBlock(raw)) continue;

            const rect = el.getBoundingClientRect();
            if (rect.width < 360 || rect.height < 60) continue;
            if (rect.top > 1400) continue;

            const affCount = countAffiliationLines(raw);
            if (affCount < 2) continue;

            const txt = norm(raw);
            let hits = 0;
            for (const n of nameNorms) {
                if (n && txt.includes(n)) hits++;
            }

            // Score: prioritize affiliation-list presence, then author-name hits, then proximity to top.
            let score = affCount * 80 + hits * 10;
            score += Math.max(0, 50 - rect.top / 30);
            score -= Math.log(Math.max(1, rect.width * rect.height)) / 2;
            score -= raw.length / 250;

            if (score > bestCScore) {
                bestCScore = score;
                bestC = el;
            }
        }

        if (bestC) return bestC;
    } catch (e) {
        // ignore and fall back
    }

  for (const el of candidates) {
    if (!el || banned(el)) continue;
    const txtRaw = (el.innerText || el.textContent || '').trim();
    if (!txtRaw) continue;
        // Some sites wrap authors + numbered affiliations in a larger container.
        // Allow bigger blocks, but they will be penalized by area/text heuristics.
        if (txtRaw.length < 10 || txtRaw.length > 3500) continue;

    // Avoid obvious citation blocks.
    if (looksLikeCitationBlock(txtRaw)) continue;

    const txt = norm(txtRaw);
    if (!txt) continue;

    let hits = 0;
    for (const n of nameNorms) {
      if (n && txt.includes(n)) hits++;
    }
    if (hits < 2) continue;

    const hasSup = !!el.querySelector('sup');
    const supText = hasSup ? Array.from(el.querySelectorAll('sup')).map(s => (s.textContent||'').trim()).join(' ') : '';
    const hasSupDigit = /\b\d{1,2}\b/.test(supText);
    const hasMail = !!el.querySelector('a[href^="mailto:"]');

    const hasAffList = hasAffiliationListStart(txtRaw);
    const affLineCount = countAffiliationLines(txtRaw);
    const hasInlineMarkers = hasInlineAffMarkers(txtRaw);

    // Critical: to avoid capturing "Citation: ..." blocks that list all names,
    // require at least some marker/affiliation evidence.
    if (!(hasSupDigit || hasInlineMarkers || hasAffList)) continue;

    const rect = el.getBoundingClientRect();
    const area = Math.max(1, rect.width * rect.height);
    if (rect.width < 200 || rect.height < 20) continue;

    // Author block is almost always near the top. Avoid deep page matches.
    if (rect.top > 2000) continue;

    // Score: name co-occurrence dominates; prefer superscript digits / mailto; penalize huge blocks.
    let score = hits * 20;
    if (hasSupDigit) score += 25;
    else if (hasSup) score += 10;
    // On AIMS-like pages, the *best* ROI usually includes the numbered affiliation list.
    if (hasAffList) score += 18;
    if (affLineCount >= 2) score += Math.min(60, affLineCount * 20);
    if (hasInlineMarkers) score += 10;
    if (hasMail) score += 15;

    // Prefer elements closer to the top of the page.
    score += Math.max(0, 40 - rect.top / 40);

    // Penalize blocks that look like abstract/body sections.
    const low = txt;
    if (low.includes('abstract') || low.includes('keywords') || low.includes('received') || low.includes('accepted')) score -= 25;
    if (low.includes('download') || low.includes('full text') || low.includes('pdf')) score -= 10;

    // Prefer moderate-sized blocks (authors line area).
    const areaPenalty = Math.log(area) / 2;
    score -= areaPenalty;

    if (score > bestScore) {
      bestScore = score;
      best = el;
    }
  }

  return best;
}
""",
                meta_names,
            )
        except Exception:
            handle = None

        el = None
        try:
            if handle is not None:
                el = handle.as_element()
        except Exception:
            el = None

        if not el:
            ok = _save_top_fallback()
            browser.close()
            return save_path if ok else None

        try:
            # Element screenshot is usually the cleanest ROI for OCR.
            el.screenshot(path=save_path)
            print(f"[WebDriver] ROI author block saved: {save_path}")
            browser.close()
            return save_path
        except Exception:
            ok = _save_top_fallback()
            browser.close()
            return save_path if ok else None
