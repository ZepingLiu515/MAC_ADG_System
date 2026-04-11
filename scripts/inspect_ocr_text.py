import argparse
import json
import os
from typing import Any, Dict, List, Optional

from backend.utils.ocr_rule_parser import OcrRuleParser


def _normalize_doi(value: str) -> str:
    doi = (value or "").strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.lower().startswith(prefix):
            doi = doi[len(prefix) :]
    return doi.strip()


def _resolve_sidecar(doi: Optional[str], sidecar: Optional[str]) -> str:
    if sidecar:
        return sidecar
    if not doi:
        raise ValueError("Provide --doi or --sidecar")
    safe_doi = doi.replace("/", "_")
    return os.path.join("data", "visual_slices", f"{safe_doi}_ocr_sidecar.json")


def _format_lines(lines: List[str], head: int, tail: int, full: bool) -> str:
    if full:
        head = len(lines)
        tail = 0
    out: List[str] = []
    total = len(lines)
    head = max(0, min(head, total))
    tail = max(0, min(tail, total))

    def _emit(start_idx: int, chunk: List[str]) -> None:
        for offset, line in enumerate(chunk):
            line_no = start_idx + offset + 1
            out.append(f"{line_no:04d}: {line}")

    _emit(0, lines[:head])
    if tail > 0 and (total - head) > tail:
        out.append("...")
    if tail > 0:
        _emit(total - tail, lines[-tail:])
    return "\n".join(out)


def _dump_aff_map(ocr_text: str) -> str:
    parser = OcrRuleParser()
    aff_map = parser.extract_affiliation_map(ocr_text)
    if not aff_map:
        return "(no affiliation map found)"
    lines = []
    for k in sorted(aff_map.keys()):
        lines.append(f"{k}: {aff_map[k]}")
    return "\n".join(lines)


def _dump_items(items: Any, limit: int) -> str:
    if not isinstance(items, list):
        return "(no ocr_items list)"
    out: List[str] = []
    for i, it in enumerate(items[:limit], start=1):
        if not isinstance(it, dict):
            continue
        text = str(it.get("text") or "").strip()
        score = it.get("score")
        out.append(f"{i:04d}: {text} (score={score})")
    return "\n".join(out) if out else "(no ocr_items entries)"


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect OCR sidecar text")
    parser.add_argument("--doi", help="DOI like 10.3934/publichealth.2026002")
    parser.add_argument("--sidecar", help="Path to *_ocr_sidecar.json")
    parser.add_argument("--head", type=int, default=60, help="Lines from start")
    parser.add_argument("--tail", type=int, default=0, help="Lines from end")
    parser.add_argument("--full", action="store_true", help="Print full OCR text")
    parser.add_argument("--out", help="Write formatted OCR text to file")
    parser.add_argument("--show-aff-map", action="store_true", help="Show parsed affiliation map")
    parser.add_argument("--show-items", action="store_true", help="Show OCR items (if any)")
    parser.add_argument("--items-limit", type=int, default=30, help="Max items to show")
    args = parser.parse_args()

    doi = _normalize_doi(args.doi) if args.doi else None
    sidecar_path = _resolve_sidecar(doi, args.sidecar)

    if not os.path.exists(sidecar_path):
        raise FileNotFoundError(f"Sidecar not found: {sidecar_path}")

    with open(sidecar_path, "r", encoding="utf-8") as f:
        payload: Dict[str, Any] = json.load(f)

    ocr_text = str(payload.get("ocr_text") or "")
    lines = ocr_text.splitlines()

    print(f"Sidecar: {sidecar_path}")
    print(f"Image: {payload.get('image_path')}")
    print(f"Lines: {len(lines)}")
    print("\n--- OCR TEXT ---")

    formatted = _format_lines(lines, args.head, args.tail, args.full)
    print(formatted)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(formatted)
        print(f"\nSaved to: {args.out}")

    if args.show_aff_map:
        print("\n--- AFFILIATION MAP ---")
        print(_dump_aff_map(ocr_text))

    if args.show_items:
        print("\n--- OCR ITEMS ---")
        print(_dump_items(payload.get("ocr_items"), args.items_limit))


if __name__ == "__main__":
    main()
