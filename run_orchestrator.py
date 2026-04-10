"""CLI runner for Orchestrator.

Usage examples:
  python run_orchestrator.py --doi 10.1038/s41586-020-2649-2
  python run_orchestrator.py --doi 10.1038/s41586-020-2649-2 --doi 10.3390/nu15204383
  python run_orchestrator.py --doi-file data/dois.txt
  python run_orchestrator.py --excel tests/test_doi.xlsx

This intentionally runs only the Orchestrator pipeline (Scout→WebDriver→Vision→Judge).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List

from backend.orchestrator import Orchestrator


def _read_dois_from_file(path: Path) -> List[str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    dois: List[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        dois.append(line)
    return dois


def main() -> int:
    # Windows PowerShell 默认可能是 GBK，打印 emoji 会触发 UnicodeEncodeError。
    # 这里强制 stdout/stderr 使用 UTF-8，避免因为日志导致脚本退出码=1。
    try:
        os.environ.setdefault("PYTHONUTF8", "1")
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="Run MAC-ADG Orchestrator for one or more DOIs.")
    parser.add_argument("--doi", action="append", default=[], help="DOI to process (can be repeated)")
    parser.add_argument("--doi-file", type=str, default=None, help="Text file with one DOI per line")
    parser.add_argument("--excel", type=str, default=None, help="Excel file containing a 'DOI' column")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force reprocess even if DOI is marked COMPLETED/PROCESSING in DB",
    )

    args = parser.parse_args()

    if args.force:
        os.environ["FORCE_REPROCESS"] = "1"

    orchestrator = Orchestrator()

    if args.excel:
        results = orchestrator.process_excel(args.excel)
    else:
        dois: List[str] = []
        if args.doi_file:
            dois.extend(_read_dois_from_file(Path(args.doi_file)))
        if args.doi:
            dois.extend([d.strip() for d in args.doi if d and d.strip()])

        if not dois:
            dois = ["10.1038/s41586-020-2649-2"]

        results = orchestrator.process_dois(dois)

    # 默认只输出“最终作者结果”，避免把完整调试包刷屏。
    # 优先使用 Vision/hover 融合后的 vision_authors；否则退回 authors。
    def _pick_authors(r: dict):
        if not isinstance(r, dict):
            return []
        v = r.get("vision_authors")
        if isinstance(v, list):
            return v
        a = r.get("authors")
        if isinstance(a, list):
            return a
        return []

    if isinstance(results, list) and len(results) == 1:
        out = _pick_authors(results[0])
    elif isinstance(results, list):
        out = [
            {
                "doi": (r.get("doi") if isinstance(r, dict) else None),
                "status": (r.get("status") if isinstance(r, dict) else None),
                "authors": _pick_authors(r if isinstance(r, dict) else {}),
            }
            for r in results
        ]
    else:
        out = results

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
