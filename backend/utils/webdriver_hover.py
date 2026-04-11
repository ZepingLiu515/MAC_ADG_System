"""Author hover/mailto extraction implementation used by `WebDriverAdapter`.

This module is intentionally self-contained to keep `webdriver.py` small.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from typing import Any, Dict, List, Optional


def extract_author_hover_data(
    *,
    sync_playwright: Any,
    stealth_sync: Any,
    visual_slice_dir: str,
    doi: str,
    landing_page_url: Optional[str],
    max_authors: int,
    save_sidecar_json: bool,
    launch_options: Dict[str, Any],
    context_options: Dict[str, Any],
    goto_timeout_ms: int,
    handle_selection_page: Any,
    close_cookie_popup: Any,
) -> Optional[Dict[str, Any]]:
    """Extract author signals from page DOM interactions (hover/click).

    Returns a dict containing authors + meta, or None if extraction disabled/failed.
    """

    if sync_playwright is None:
        print("[WebDriver] Playwright not installed")
        return None

    def _env_truthy(name: str, default: str = "1") -> bool:
        raw = os.getenv(name, default).strip()
        return raw not in {"0", "false", "False", "no", "NO"}

    if not _env_truthy("PLAYWRIGHT_EXTRACT_AUTHOR_DETAILS", default="1"):
        return None

    doi_url = f"https://doi.org/{doi}"
    safe_doi = doi.replace("/", "_")
    sidecar_path = os.path.join(visual_slice_dir, f"{safe_doi}_page_author_data.json")

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

    def _is_block_page(page: Any) -> bool:
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

    def _collect_visible_popover_text(page: Any) -> str:
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
  return out.slice(0, 5).join('\\n---\\n');
})();
"""
        try:
            v = page.evaluate(js)
            return v.strip() if isinstance(v, str) else ""
        except Exception:
            return ""

    def _collect_visible_author_detail_text(page: Any, author_hint: str = "") -> str:
        """Extract author details shown after clicking an author."""

        js = r"""
(params) => {
  const hint = (params && params.hint) ? String(params.hint) : '';
  const norm = (s) => (s || '')
    .toLowerCase()
    .replace(/[-_]/g, ' ')
    .replace(/[^a-z0-9\\s]/g, ' ')
    .replace(/\\s+/g, ' ')
    .trim();

  const hintN = norm(hint);
  const keys = ['affiliation', 'affiliations', 'department', 'university', 'institute', 'school', 'hospital', 'email', 'e-mail', 'correspondence'];

  const isVisible = (el) => {
    try {
      if (!el) return false;
      const style = window.getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      return style && style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 2 && rect.height > 2;
    } catch (e) {
      return false;
    }
  };

  const selectors = [
    '[role="dialog"]',
    '[aria-modal="true"]',
    'aside',
    '[class*="drawer" i]',
    '[class*="modal" i]',
    '[class*="panel" i]',
    '[class*="sidebar" i]',
    '[class*="author" i][class*="info" i]',
    '[class*="author" i][class*="detail" i]',
    '[data-test*="author" i]',
    '[data-testid*="author" i]',
    '[id*="author" i]'
  ];

  const candidates = [];
  for (const sel of selectors) {
    try { document.querySelectorAll(sel).forEach(el => candidates.push(el)); } catch (e) {}
  }

  const scored = [];
  for (const el of candidates) {
    if (!isVisible(el)) continue;
    let txt = '';
    try { txt = (el.innerText || el.textContent || '').trim(); } catch (e) { txt = ''; }
    if (!txt || txt.length < 10) continue;
    if (txt.length > 8000) continue;

    const tN = norm(txt);
    let score = 0;
    if (hintN && tN.includes(hintN)) score += 6;
    for (const k of keys) {
      if (tN.includes(k)) score += 2;
    }
    if (/@/.test(txt)) score += 6;
    if (/corresponding/i.test(txt)) score += 3;
    if (/affiliat/i.test(txt)) score += 3;
    if (txt.length >= 50 && txt.length <= 2500) score += 2;
    scored.push({ score, txt });
  }

  scored.sort((a, b) => (b.score - a.score) || (a.txt.length - b.txt.length));
  const out = [];
  const seen = new Set();
  for (const s of scored.slice(0, 3)) {
    const t = (s.txt || '').trim();
    if (!t) continue;
    if (seen.has(t)) continue;
    seen.add(t);
    out.push(t);
  }
  return out.join('\\n---\\n');
}
"""

        try:
            v = page.evaluate(js, {"hint": author_hint or ""})
            return v.strip() if isinstance(v, str) else ""
        except Exception:
            return ""

    def _close_author_detail_ui(page: Any) -> None:
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
        try:
            page.evaluate(
                r"""
(() => {
  const sels = [
    'button[aria-label*="close" i]',
    'button[title*="close" i]',
    '[data-test*="close" i]',
    '[data-testid*="close" i]',
    'button:has-text("Close")',
    'button:has-text("close")'
  ];
  for (const sel of sels) {
    try {
      const els = Array.from(document.querySelectorAll(sel));
      for (const el of els) {
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        const vis = style && style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 2 && rect.height > 2;
        if (!vis) continue;
        el.click();
        return true;
      }
    } catch (e) {}
  }
  return false;
})();
"""
            )
        except Exception:
            pass

    def _infer_flags_from_text(text: str) -> Dict[str, bool]:
        low = (text or "").lower()
        is_corresponding = any(k in low for k in ["corresponding author", "correspondence", "email", "e-mail"])
        is_co_first = any(k in low for k in ["equal contribution", "contributed equally", "co-first", "co first"])
        return {"is_corresponding": is_corresponding, "is_co_first": is_co_first}

    def _infer_affiliation_from_text(text: str) -> str:
        if not text:
            return ""
        lines = [re.sub(r"\\s+", " ", ln).strip() for ln in text.splitlines() if ln and ln.strip()]
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
            "affiliation",
            "affiliations",
        ]
        best = ""
        best_score = -1
        for ln in lines:
            low = ln.lower()
            score = (2 if any(k in low for k in keys) else 0) + (1 if len(ln) >= 15 else 0)
            if score > best_score:
                best = ln
                best_score = score
        return best if best and len(best) <= 240 else ""
    with sync_playwright() as p:
        browser = p.chromium.launch(**launch_options)
        context = browser.new_context(**context_options)

        page = context.new_page()
        try:
            stealth_sync(page)
        except Exception:
            pass

        try:
            response = page.goto(doi_url, wait_until="domcontentloaded", timeout=goto_timeout_ms)
        except Exception:
            if landing_page_url and isinstance(landing_page_url, str):
                landing_page_url = landing_page_url.strip()
            if landing_page_url and landing_page_url != doi_url:
                response = page.goto(landing_page_url, wait_until="domcontentloaded", timeout=goto_timeout_ms)
            else:
                browser.close()
                raise

        blocked = (response and response.status >= 400) or _is_block_page(page)

        if blocked and landing_page_url and isinstance(landing_page_url, str):
            landing_page_url = landing_page_url.strip()
            if landing_page_url and landing_page_url != doi_url:
                print(f"[WebDriver] doi.org blocked; trying landing page: {landing_page_url}")
                response = page.goto(landing_page_url, wait_until="domcontentloaded", timeout=45000)
                blocked = (response and response.status >= 400) or _is_block_page(page)

        if blocked:
            print(
                f"[WebDriver] Page blocked; skip hover extraction (HTTP={getattr(response, 'status', None)})"
            )
            browser.close()
            return None

        page.wait_for_timeout(2000)
        handle_selection_page(page)
        close_cookie_popup(page)
        page.wait_for_timeout(800)

        meta_names: List[str] = []
        meta_institutions: List[str] = []
        meta_emails: List[str] = []

        try:
            meta_names = page.evaluate(
                """
(() => Array.from(document.querySelectorAll('meta[name=\"citation_author\"]'))
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
(() => Array.from(document.querySelectorAll('meta[name=\"citation_author_institution\"]'))
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
(() => Array.from(document.querySelectorAll('meta[name=\"citation_author_email\"], meta[name=\"citation_email\"]'))
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
                s = str(aff or "").strip()
                if s:
                    meta_aff_map[i] = s
        except Exception:
            meta_aff_map = {}

        # 1) meta 引导：按 citation_author 精确找文本节点
        seen = set()
        unique_meta: List[str] = []
        for n in meta_names:
            s = str(n or "").strip()
            if not s or s in seen:
                continue
            seen.add(s)
            unique_meta.append(s)

        def _best_author_element(author_name: str):
            if not author_name:
                return None
            literal = _xpath_literal(author_name)
            candidates = []
            try:
                el0 = page.query_selector(f"xpath=//*[normalize-space(text())={literal}]")
                if el0:
                    candidates.append(el0)
            except Exception:
                pass

            try:
                els = page.query_selector_all(f"xpath=//*[contains(normalize-space(.), {literal})]")
                if isinstance(els, list):
                    candidates.extend(els[:30])
            except Exception:
                pass

            if not candidates:
                return None

            best = None
            best_score = -1
            for el in candidates:
                try:
                    info = el.evaluate(
                                                r"""
(node) => {
  const root = node.closest('li, div, span, p, a, section, article') || node;
  if (!root) return { score: 0 };
  if (root.closest('nav, header, footer, aside')) return { score: 0 };
  const sups = Array.from(root.querySelectorAll('sup')).map(s => (s.textContent||'').trim()).join(' ');
  const hasSupDigit = /\b\d{1,2}\b/.test(sups);
  const hasAnySup = !!root.querySelector('sup');
  const txt = (root.textContent || '').slice(0, 2000);
  const sepScore = (txt.includes(',') ? 1 : 0) + (txt.includes(';') ? 1 : 0) + (/\band\b/i.test(txt) ? 1 : 0);
  return { hasSupDigit, hasAnySup, sepScore, txt };
}
"""
                    )
                except Exception:
                    continue

                has_sup_digit = bool(info.get("hasSupDigit")) if isinstance(info, dict) else False
                has_any_sup = bool(info.get("hasAnySup")) if isinstance(info, dict) else False
                sep_score = int(info.get("sepScore") or 0) if isinstance(info, dict) else 0
                txt = str(info.get("txt") or "") if isinstance(info, dict) else ""

                score = 0
                if has_sup_digit:
                    score += 10
                elif has_any_sup:
                    score += 4
                score += min(sep_score, 3)
                try:
                    hits = 0
                    for other in unique_meta[:6]:
                        if other and other != author_name and _norm_for_match(other) in _norm_for_match(txt):
                            hits += 1
                    score += hits * 2
                except Exception:
                    pass

                if score > best_score:
                    best_score = score
                    best = el

            return best

        def _extract_signals(el: Any, author_name: str = "") -> Dict[str, Any]:
            try:
                if bool(el.evaluate("(node) => !!node.closest('nav, header, footer, aside')")):
                    return {"skip": True}
            except Exception:
                pass

            markers = ""
            aff_nums: List[int] = []
            sup_info = None
            try:
                sup_info = el.evaluate(
                    r"""
(node, params) => {
    const authorName = (params && params.authorName) || '';
    const otherNames = (params && params.otherNames) || [];
    const norm = (s) => (s || '')
        .toLowerCase()
        .replace(/[-_]/g, ' ')
        .replace(/[^a-z0-9\s]/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();

    const an = norm(authorName);
    const others = (otherNames || []).map(norm).filter(Boolean);

    let primary = node.closest('a,span,strong,em,li,div,p') || node.parentElement || node;
    let root = primary;

    // Prefer a small container that contains THIS author but not OTHER authors.
    let cur = primary;
    for (let depth = 0; depth < 6 && cur; depth++) {
        const txt = (cur.innerText || cur.textContent || '').trim();
        const n = norm(txt);
        if (an && n.includes(an)) {
            let hitOther = false;
            for (const o of others) {
                if (!o) continue;
                if (n.includes(o)) { hitOther = true; break; }
            }
            if (!hitOther && txt.length > 0 && txt.length <= 600) {
                root = cur;
                break;
            }
        }
        cur = cur.parentElement;
    }

    const grabSupText = (x) => {
        const out = [];
        try {
            if (!x) return out;
            if (x.tagName && x.tagName.toLowerCase() === 'sup') {
                const t = (x.textContent || '').trim();
                if (t) out.push(t);
            }
            if (x.querySelectorAll) {
                // Only take direct-child superscripts to avoid grabbing the whole affiliations list.
                x.querySelectorAll(':scope > sup').forEach(s => {
                    const t = (s.textContent || '').trim();
                    if (t) out.push(t);
                });
            }
        } catch (e) {}
        return out;
    };

    const sups = [];
    grabSupText(root).forEach(t => sups.push(t));
    grabSupText(node.nextElementSibling).forEach(t => sups.push(t));
    grabSupText(node.previousElementSibling).forEach(t => sups.push(t));

    const sup = sups.join(' ');
    const txt = ((root && (root.innerText || root.textContent)) || (primary && (primary.innerText || primary.textContent)) || (node.innerText || node.textContent) || '').trim();

    let unsafeOtherHit = false;
    try {
        const n2 = norm(txt);
        for (const o of others) {
            if (o && n2.includes(o)) { unsafeOtherHit = true; break; }
        }
    } catch (e) { unsafeOtherHit = false; }

    let hasMail = false;
    const mails = [];
    try {
        const emailRe = /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/ig;

        const sels = [
            // direct mailto links
            'a[href^="mailto:"]',
            // common accessibility / tooltip hints
            '[aria-label*="mail" i]',
            '[aria-label*="email" i]',
            '[title*="mail" i]',
            '[title*="email" i]',
            // icons (AIMS often uses font icons without aria/title)
            'i[class*="envelope" i]',
            'i[class*="mail" i]',
            'span[class*="envelope" i]',
            'span[class*="mail" i]',
            'svg[aria-label*="mail" i]',
            'svg[aria-label*="email" i]',
            'img[alt*="mail" i]',
            'img[alt*="email" i]'
        ];

        const scanOne = (container) => {
            if (!container) return;
            if (!container.querySelectorAll) return;

            // If this is a huge multi-author container, skip text scanning but still allow icon scan.
            let raw = '';
            try { raw = (container.innerText || container.textContent || ''); } catch (e) { raw = ''; }
            const rawLen = (raw || '').length;

            // Collect mailto + data-email style attributes.
            try {
                const links = Array.from(container.querySelectorAll('a[href],a[data-email],a[data-mail],a[data-mailto]'));
                for (const a of links) {
                    const href = (a.getAttribute('href') || '').trim();
                    if (href && /^mailto:/i.test(href)) {
                        const v = href.replace(/^mailto:/i, '').split('?')[0].trim();
                        if (v) mails.push(v);
                    }
                    const dataEmail = (a.getAttribute('data-email') || a.getAttribute('data-mail') || a.getAttribute('data-mailto') || '').trim();
                    if (dataEmail) {
                        const m = dataEmail.match(emailRe);
                        if (m) m.forEach(x => mails.push(x));
                    }
                    const title = (a.getAttribute('title') || a.getAttribute('aria-label') || '').trim();
                    if (title) {
                        const m = title.match(emailRe);
                        if (m) m.forEach(x => mails.push(x));
                    }
                }
            } catch (e) {}

            // Light text scan for emails if the container is small-ish.
            if (rawLen > 0 && rawLen <= 600) {
                try {
                    const m = raw.match(emailRe);
                    if (m) m.forEach(x => mails.push(x));
                } catch (e) {}
            }

            // Icon/selector scan (always allowed).
            for (const sel of sels) {
                try {
                    if (container.querySelector(sel)) { hasMail = true; break; }
                } catch (e) {}
            }
        };

        // Even if root contains multiple authors (unsafeOtherHit), mail icon is usually adjacent to the name.
        // Scan a few nearby nodes instead of relying solely on root.
        const nodes = [];
        const pushNode = (x) => { if (x && nodes.indexOf(x) < 0) nodes.push(x); };
        pushNode(root);
        pushNode(primary);
        pushNode(node);
        pushNode(node && node.nextElementSibling);
        pushNode(node && node.previousElementSibling);
        pushNode(primary && primary.parentElement);
        pushNode(root && root.parentElement);

        for (const c of nodes) {
            scanOne(c);
            if (hasMail && mails.length >= 1) break;
        }

        // If we extracted at least one email, treat as having mail signal.
        if (mails.length > 0) hasMail = true;
    } catch (e) {}

    return {
        sup,
        txt: txt.slice(0, 800),
        hasMail,
        mails: mails.slice(0, 5)
    };
}
""",
                    {
                        "authorName": author_name or "",
                        "otherNames": [x for x in unique_meta[:12] if x and x != author_name],
                    },
                )
            except Exception:
                sup_info = None

            if isinstance(sup_info, dict):
                sup_text = str(sup_info.get("sup") or "")
                markers = "".join(re.findall(r"[\*#†‡]", sup_text))
                sup_nums = re.findall(r"(?<!\d)(\d{1,2})(?!\d)", sup_text)
                for x in sup_nums:
                    try:
                        n = int(x)
                        if 1 <= n <= 99:
                            aff_nums.append(n)
                    except Exception:
                        continue

                got_sup_digits = bool(sup_nums)

                near_txt = str(sup_info.get("txt") or "")
                if near_txt and (not got_sup_digits):
                    scope = near_txt
                    if author_name:
                        near_norm = _norm_for_match(near_txt)
                        an_norm = _norm_for_match(author_name)
                        pos = near_norm.find(an_norm) if an_norm else -1

                        if pos < 0 and an_norm:
                            parts = [p for p in an_norm.split() if p]
                            if len(parts) >= 2:
                                key2 = " ".join(parts[-2:])
                                pos = near_norm.find(key2)
                            elif len(parts) == 1:
                                pos = near_norm.find(parts[0])

                        if pos >= 0:
                            tail_norm = near_norm[pos + len(an_norm) :]
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
                            scope_norm = re.split(r"\b(doi|volume|issue)\b", scope_norm, maxsplit=1)[0]
                            scope = scope_norm

                    extra = re.findall(r"(?<!\d)(\d{1,2})(?!\d)", str(scope))
                    for x in extra:
                        try:
                            n = int(x)
                            if 1 <= n <= 99:
                                aff_nums.append(n)
                        except Exception:
                            continue

                    if scope:
                        markers = (markers + "".join(re.findall(r"[\*#†‡]", scope))).strip()

                dedup = []
                seen_n = set()
                for x in aff_nums:
                    if x in seen_n:
                        continue
                    seen_n.add(x)
                    dedup.append(x)
                aff_nums = dedup

                if meta_aff_map:
                    try:
                        max_meta = max(meta_aff_map.keys())
                    except Exception:
                        max_meta = 0
                    if max_meta > 0:
                        aff_nums = [n for n in aff_nums if 1 <= int(n) <= max_meta]
                        try:
                            if max_meta <= 8 and set(aff_nums) == set(range(1, max_meta + 1)):
                                aff_nums = []
                        except Exception:
                            pass

                if meta_aff_map and len(aff_nums) >= max(len(meta_aff_map) - 1, 6):
                    aff_nums = []

            tip = ""
            try:
                tip_parts: List[str] = []

                try:
                    el.hover(timeout=2500)
                    page.wait_for_timeout(250)
                    t1 = _collect_visible_popover_text(page)
                    if t1:
                        tip_parts.append(t1)
                except Exception:
                    pass

                # Always attempt a safe click to open author details UI (Nature et al.).
                url_before = ""
                try:
                    url_before = page.url
                except Exception:
                    url_before = ""

                clicked = False
                try:
                    el.click(timeout=1800)
                    clicked = True
                except Exception:
                    try:
                        el.click(timeout=1800, force=True)
                        clicked = True
                    except Exception:
                        try:
                            el.evaluate(
                                """
(node) => {
  const t = node.closest('button,a,[role="button"],[role="link"]') || node;
  try { t.click(); return true; } catch (e) {}
  try { t.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true })); return true; } catch (e2) {}
  return false;
}
"""
                            )
                            clicked = True
                        except Exception:
                            clicked = False

                if clicked:
                    page.wait_for_timeout(450)

                    # If click navigated away (author profile), go back.
                    try:
                        url_after = page.url
                    except Exception:
                        url_after = ""

                    try:
                        if url_before and url_after and (url_after != url_before) and ("#" not in url_after):
                            page.go_back(timeout=45000)
                            page.wait_for_timeout(600)
                            url_after = url_before
                    except Exception:
                        pass

                    t2 = _collect_visible_author_detail_text(page, author_hint=author_name or "")
                    if t2:
                        tip_parts.append(t2)
                    else:
                        t3 = _collect_visible_popover_text(page)
                        if t3:
                            tip_parts.append(t3)

                    _close_author_detail_ui(page)

                # Dedup + join
                seen_txt = set()
                merged: List[str] = []
                for part in tip_parts:
                    p2 = str(part or "").strip()
                    if not p2 or p2 in seen_txt:
                        continue
                    seen_txt.add(p2)
                    merged.append(p2)

                tip = "\n---\n".join(merged)
            except Exception:
                tip = ""

            flags = _infer_flags_from_text(tip)
            affiliation = _infer_affiliation_from_text(tip)

            has_mail_icon = False
            emails: List[str] = []

            if isinstance(sup_info, dict):
                try:
                    has_mail_icon = bool(sup_info.get("hasMail"))
                except Exception:
                    has_mail_icon = False
                try:
                    emails = sup_info.get("mails") if isinstance(sup_info.get("mails"), list) else []
                    emails = [str(e).strip() for e in emails if e and str(e).strip()]
                except Exception:
                    emails = []

            if has_mail_icon or emails:
                flags["is_corresponding"] = True

            if "*" in markers:
                flags["is_corresponding"] = True

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

        for n in unique_meta[:max_authors]:
            if _contains_ignored_phrase(n):
                continue
            el = None
            try:
                el = _best_author_element(n)
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
            elements: List[Any] = []
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
                        raw_name = (
                            el.get_attribute("aria-label")
                            or el.get_attribute("title")
                            or ""
                        ).strip()
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

                aff_nums = info.get("affiliation_numbers") or []
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
                        "markers": (markers + (info.get("markers") or "")).strip(),
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

        if meta_name_keys:
            filtered = []
            for a in authors:
                k = _name_key(a.get("name"))
                if k and k in meta_name_keys:
                    filtered.append(a)
            authors = filtered

        if meta_aff_map and authors:
            for a in authors:
                nums = a.get("affiliation_numbers") or []
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
                    a["affiliations"] = affs
                    a["affiliation"] = "; ".join(affs)

        # Equal contribution note
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
                a
                for a in authors
                if any(sym in str(a.get("markers") or "") for sym in ["#", "†", "‡"])
            ]
            if marked:
                for a in marked:
                    a["is_co_first"] = True
            elif len(authors) >= 2:
                authors[0]["is_co_first"] = True
                authors[1]["is_co_first"] = True

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
                os.makedirs(visual_slice_dir, exist_ok=True)
                with open(sidecar_path, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                print(f"[WebDriver] Saved hover author data: {sidecar_path}")
            except Exception:
                pass

        browser.close()
        return result if authors else None
