from __future__ import annotations

import json
import sys


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception as exc:
        print(f"playwright import failed: {exc}")
        return 2

    doi = sys.argv[1] if len(sys.argv) > 1 else "10.3934/publichealth.2026002"
    url = "https://doi.org/" + doi

    js = r"""
() => {
  const norm = (s) => (s || '')
    .toLowerCase()
    .replace(/[-_]/g, ' ')
    .replace(/[^a-z0-9\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

  const looksLikeCitationBlock = (raw) => {
    const t = norm(raw);
    if (!t) return false;
    if (t.startsWith('citation')) return true;
    const i = t.indexOf('citation');
    if (i >= 0 && i <= 20 && t.includes('citation:')) return true;
    return false;
  };

  const countAffiliationLines = (raw) => {
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
  const out = [];
  for (const el of containers) {
    const raw = (el.innerText || el.textContent || '').trim();
    if (!raw) continue;
    if (raw.length < 60 || raw.length > 12000) continue;
    const rect = el.getBoundingClientRect();
    if (rect.width < 360 || rect.height < 60) continue;
    if (rect.top > 1800) continue;

    const affCount = countAffiliationLines(raw);
    if (affCount < 2) continue;

    const t = norm(raw);
    const isCite = looksLikeCitationBlock(raw);

    let score = affCount * 80;
    score += Math.max(0, 50 - rect.top / 30);
    score -= Math.log(Math.max(1, rect.width * rect.height)) / 2;
    score -= raw.length / 250;
    if (isCite) score -= 500;

    out.push({
      score,
      top: rect.top,
      left: rect.left,
      width: rect.width,
      height: rect.height,
      textLen: raw.length,
      affCount,
      isCite,
      preview: raw.slice(0, 120).replace(/\s+/g, ' '),
    });
  }

  out.sort((a,b) => b.score - a.score);
  return out.slice(0, 8);
}
"""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 1200}, device_scale_factor=2)
        page = ctx.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(3000)
        candidates = page.evaluate(js)
        browser.close()

    print(json.dumps(candidates, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
