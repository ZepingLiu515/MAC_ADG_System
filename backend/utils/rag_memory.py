import re
from typing import Any, Dict, List, Optional

from database.models import CorrectionMemory


def _tokenize(text: str) -> List[str]:
    tokens = re.findall(r"[A-Za-z0-9]+", str(text or "").lower())
    tokens = [t for t in tokens if len(t) >= 3]
    return tokens


def build_layout_fingerprint(vision_data: Dict[str, Any], max_tokens: int = 200) -> List[str]:
    """Build a lightweight layout fingerprint from OCR/vision text."""
    text = ""
    if isinstance(vision_data, dict):
        text = vision_data.get("text") or ""
    tokens = _tokenize(text)
    if len(tokens) > max_tokens:
        tokens = tokens[:max_tokens]
    return tokens


def retrieve_memory_hints(
    db,
    fingerprint_tokens: List[str],
    top_k: int = 3,
    min_score: float = 0.15,
) -> List[Dict[str, Any]]:
    """Return top-K correction hints using Jaccard similarity."""
    if not fingerprint_tokens:
        return []

    query_set = set(fingerprint_tokens)
    if not query_set:
        return []

    rows = db.query(CorrectionMemory).all()
    scored: List[Dict[str, Any]] = []

    for row in rows:
        tokens = row.layout_fingerprint or []
        if isinstance(tokens, str):
            # tolerate bad legacy entries
            tokens = _tokenize(tokens)
        if not isinstance(tokens, list):
            tokens = []
        token_set = set([str(t).lower() for t in tokens if str(t).strip()])
        if not token_set:
            continue
        inter = query_set.intersection(token_set)
        union = query_set.union(token_set)
        score = (len(inter) / len(union)) if union else 0.0
        if score >= min_score:
            scored.append(
                {
                    "id": row.id,
                    "score": score,
                    "error_type": row.error_type,
                    "correction": row.correction,
                    "notes": row.notes,
                }
            )

    scored.sort(key=lambda x: x.get("score", 0), reverse=True)
    return scored[:top_k]


def save_correction_sample(
    db,
    fingerprint_tokens: List[str],
    error_type: str,
    correction: Dict[str, Any],
    source: str = "manual",
    notes: str = "",
    doi: Optional[str] = None,
) -> CorrectionMemory:
    """Persist a correction sample for later retrieval."""
    record = CorrectionMemory(
        doi=doi,
        layout_fingerprint=fingerprint_tokens,
        error_type=error_type,
        correction=correction,
        source=source,
        notes=notes,
    )
    db.add(record)
    db.flush()
    return record
