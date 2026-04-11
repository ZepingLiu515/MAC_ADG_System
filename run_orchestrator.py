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
from backend.utils.schemas import DuplicateStrategy
from database.connection import get_db
from database.settings import get_duplicate_strategy, set_duplicate_strategy


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
    # 统一解决 Windows 中文日志乱码：强制把控制台输出切到 UTF-8，并让 Python 也输出 UTF-8。
    # 这样无论是 conda run 还是直接 python 运行，都能稳定显示中文；emoji 无法显示时用 ? 替代。
    try:
        if os.name == "nt":
            try:
                import ctypes

                ctypes.windll.kernel32.SetConsoleOutputCP(65001)
                ctypes.windll.kernel32.SetConsoleCP(65001)
            except Exception:
                pass

        os.environ.setdefault("PYTHONIOENCODING", "utf-8")
        os.environ.setdefault("PYTHONUTF8", "1")

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
        db = next(get_db())
        try:
            prev_strategy = get_duplicate_strategy(db)
            set_duplicate_strategy(db, DuplicateStrategy.OVERWRITE)
        finally:
            db.close()
    else:
        prev_strategy = None

    orchestrator = Orchestrator()

    try:
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
    finally:
        if prev_strategy is not None:
            db = next(get_db())
            try:
                set_duplicate_strategy(db, prev_strategy)
            finally:
                db.close()

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

    def _repair_text(s: str) -> str:
        if not isinstance(s, str) or not s:
            return s

        # Common Windows mojibake: UTF-8 bytes decoded as cp936/cp1252.
        candidates = [s]
        for enc in ("cp936", "cp1252", "latin1"):
            try:
                candidates.append(s.encode(enc, errors="strict").decode("utf-8", errors="strict"))
            except Exception:
                pass

        def score(t: str) -> int:
            # Higher is better.
            if not t:
                return -10**9
            bad = t.count("\ufffd")  # replacement char
            # Penalize CJK characters if the string is mostly Latin.
            cjk = sum(1 for ch in t if "\u4e00" <= ch <= "\u9fff")
            latin = sum(1 for ch in t if ("A" <= ch <= "Z") or ("a" <= ch <= "z"))
            return latin * 2 - cjk * 3 - bad * 20 - len(t) // 500

        best = max(candidates, key=score)
        return best

    def _repair_obj(obj):
        if isinstance(obj, str):
            return _repair_text(obj)
        if isinstance(obj, list):
            return [_repair_obj(x) for x in obj]
        if isinstance(obj, dict):
            return {(_repair_text(k) if isinstance(k, str) else k): _repair_obj(v) for k, v in obj.items()}
        return obj

    print(json.dumps(_repair_obj(out), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
