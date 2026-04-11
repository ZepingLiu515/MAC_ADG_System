from __future__ import annotations

import re
import sys


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception as exc:
        print(f"playwright import failed: {exc}")
        return 2

    doi = sys.argv[1] if len(sys.argv) > 1 else "10.3934/publichealth.2026002"
    url = "https://doi.org/" + doi

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1200}, device_scale_factor=2)
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(3000)
        txt = page.evaluate("""() => document.body ? (document.body.innerText || '') : ''""")
        browser.close()

    s = re.sub(r"\s+", " ", str(txt or "")).strip()
    print(s[:2000])

    # Quick indicators
    print("\n--- indicators ---")
    for pat in [
        r"\bcitation\b",
        r"\bdepartment\b",
        r"\buniversity\b",
        r"(?:^|\s)1\s*[\.)]?\s+",
    ]:
        print(pat, bool(re.search(pat, s, re.I)))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
