from __future__ import annotations

import os
import re
import unicodedata
from typing import Any, Dict, List, Optional


class OcrRuleParser:
    """Rule-based parser for extracting authors + affiliation mapping from OCR text.

    This is used as a fallback when LLM parsing is unavailable or unreliable.
    """

    def strip_accents(self, s: str) -> str:
        if not s:
            return ""
        return "".join(
            ch for ch in unicodedata.normalize("NFKD", str(s)) if not unicodedata.combining(ch)
        )

    def digit_to_int(self, ch: str) -> Optional[int]:
        """Convert a single digit-like character (ASCII, superscripts, etc.) to int."""
        try:
            if not ch:
                return None
            if ch.isdigit():
                return int(unicodedata.digit(ch))
        except Exception:
            return None
        return None

    def parse_int_from_digit_string(self, s: str) -> Optional[int]:
        """Parse a (possibly unicode) digit string like '12' or '³4' into int."""
        if not s:
            return None
        digits: List[str] = []
        for ch in str(s).strip():
            if ch.isdigit():
                v = self.digit_to_int(ch)
                if v is None:
                    return None
                digits.append(str(v))
            else:
                return None
        if not digits:
            return None
        try:
            return int("".join(digits))
        except Exception:
            return None

    def normalize_ws(self, s: str) -> str:
        return re.sub(r"\s+", " ", str(s or "")).strip()

    def normalize_for_match(self, s: str) -> str:
        s = self.strip_accents(s)
        s = s.lower()
        s = re.sub(r"[^a-z0-9\s\-\.]", " ", s)
        return self.normalize_ws(s)

    def extract_affiliation_map(self, ocr_text: str) -> Dict[int, str]:
        """Extract affiliation list like '1. ...' from OCR text."""
        if not ocr_text:
            return {}

        lines = [self.normalize_ws(x) for x in str(ocr_text).splitlines()]
        lines = [x for x in lines if x]

        aff_map: Dict[int, str] = {}
        current_num: Optional[int] = None
        buffer: List[str] = []

        def _flush() -> None:
            nonlocal current_num, buffer
            if current_num is None:
                return
            text = self.normalize_ws(" ".join(buffer))
            if text:
                aff_map[current_num] = text
            current_num = None
            buffer = []

        def _maybe_add_aff(n: int, rest: str) -> bool:
            if not rest:
                return False
            if not (1 <= n <= 30):
                return False
            looks_like_aff = ("," in rest) or bool(
                re.search(
                    r"\b(university|hospital|institute|department|school|center|centre|laboratory|college)\b",
                    rest,
                    re.I,
                )
            )
            if not (looks_like_aff or len(rest) >= 15):
                return False
            return True

        for line in lines:
            if re.match(r"^\d{4}\b", line):
                if current_num is not None:
                    buffer.append(line)
                continue

            # 支持同一行多个编号："1. ... 2. ... 3. ..."（AIMS 有时会这样）
            inline = re.findall(r"(\d{1,2})\s*[\.|\)]\s*([^\d]{5,200}?)(?=(?:\d{1,2}\s*[\.|\)]|$))", line)
            if inline and len(inline) >= 2:
                _flush()
                for n_raw, rest_raw in inline:
                    n = self.parse_int_from_digit_string(n_raw)
                    if n is None:
                        continue
                    rest = self.normalize_ws(rest_raw)
                    if _maybe_add_aff(n, rest):
                        aff_map[n] = rest
                continue

            m = re.match(r"^(\d{1,2})\s*[\.|\)]\s*(.+)$", line)
            if not m:
                m = re.match(r"^(\d{1,2})\s+(.+)$", line)

            if m:
                n = self.parse_int_from_digit_string(m.group(1))
                if n is None:
                    continue
                rest = self.normalize_ws(m.group(2))
                if _maybe_add_aff(n, rest):
                    _flush()
                    current_num = n
                    buffer = [rest]
                    continue

            if current_num is not None:
                buffer.append(line)

        _flush()
        return aff_map

    def split_marker_numbers(
        self,
        marker_text: str,
        max_aff_num: int,
        known_aff_nums: Optional[set[int]] = None,
        prefer_split_hint: Optional[bool] = None,
    ) -> List[int]:
        """Parse marker numbers after author name.

        Supports: '1,2' '1 2' '12'.
        NOTE: When OCR glues markers (e.g. '1²' -> '12'), we only split when it's safe:
        - If affiliation list contains 12, keep [12]
        - Else if affiliation list contains 1 and 2, split to [1,2]
        """
        if not marker_text:
            return []
        t = str(marker_text).strip()
        if not t:
            return []

        cleaned_chars: List[str] = []
        for ch in t:
            if ch.isdigit():
                v = self.digit_to_int(ch)
                if v is None:
                    continue
                cleaned_chars.append(str(v))
                continue
            if ch in {",", ";", " ", "-", "–"}:
                cleaned_chars.append(ch)
                continue

        t = self.normalize_ws("".join(cleaned_chars))
        # OCR 常把角标后面的逗号/分号一起吞进来，例如 "1²," -> "12,"
        # 这里先做一次首尾标点清理，避免把它当成一个整体数字 12。
        t = t.strip(" ,;")
        if not t:
            return []

        nums: List[int] = []

        prefer_split = (
            bool(prefer_split_hint)
            or str(os.getenv("OCR_PREFER_SPLIT_GLUE_MARKERS", "0")).strip().lower()
            in {"1", "true", "yes", "y"}
        )

        def _deglue_digit_string(part: str) -> List[int]:
            """Try to recover glued affiliation markers like '12' -> [1,2] or [12].

            Priority:
            1) If part as-is is a known affiliation number, keep it.
            2) Try 2-way split into (1-2 digit chunks) that are known.
            3) If max_aff_num<=9 and all digits individually look valid, split into digits.
            4) Fallback to treating it as a whole number.
            """
            if not part or not part.isdigit():
                return []

            try:
                whole = int(part)
            except Exception:
                whole = None

            # 若开启“激进拆分”，优先尝试拆成已知编号组合（即使 whole 也存在）
            if known_aff_nums and len(part) >= 2:
                for i in range(1, len(part)):
                    try:
                        left = int(part[:i])
                        right = int(part[i:])
                    except Exception:
                        continue
                    if left in known_aff_nums and right in known_aff_nums:
                        if prefer_split:
                            return [left, right]
                        # 保守模式：如果 whole 本身也存在，则优先 whole（避免把真实 12 误拆成 1+2）
                        if whole is not None and whole in known_aff_nums:
                            return [whole]
                        return [left, right]

            if known_aff_nums and whole is not None and whole in known_aff_nums:
                return [whole]

            if max_aff_num <= 9 and len(part) >= 2:
                digits = [int(ch) for ch in part if ch.isdigit() and ch != "0"]
                if digits and all(1 <= d <= max_aff_num for d in digits):
                    return digits

            if whole is not None and whole > 0:
                return [whole]
            return []

        if (
            re.fullmatch(r"\d+", t)
            and ("," not in t)
            and (" " not in t)
            and ("-" not in t)
            and ("–" not in t)
        ):
            nums = _deglue_digit_string(t)
        else:
            for part in re.split(r"[,;\s]+", t):
                part = part.strip()
                if not part:
                    continue

                if part.isdigit():
                    nums.extend(_deglue_digit_string(part))
                    continue

                m = re.match(r"^(\d{1,2})\s*[-–]\s*(\d{1,2})$", part)
                if m:
                    a = self.parse_int_from_digit_string(m.group(1))
                    b = self.parse_int_from_digit_string(m.group(2))
                    if a is None or b is None:
                        continue
                    if 1 <= a <= b <= 30 and (b - a) <= 10:
                        nums.extend(list(range(a, b + 1)))
                    continue

                try:
                    v = int(part)
                    if v > 0:
                        nums.append(v)
                except Exception:
                    continue

        out: List[int] = []
        seen = set()
        for n in nums:
            if n in seen:
                continue
            seen.add(n)
            out.append(n)
        return out

    def clean_affiliation_text(self, s: str) -> str:
        if not s:
            return ""
        t = self.normalize_ws(s)
        t = re.sub(r"\bPDF\s+Downloads\s*\(\s*\d+\s*\)\b", "", t, flags=re.I)
        t = re.sub(r"\bMetrics\b", "", t, flags=re.I)
        t = re.sub(r"\b(Received|Accepted|Published)\b\s*[:\-]?\s*\w+.*$", "", t, flags=re.I)
        t = self.normalize_ws(t)
        t = re.sub(r"[\s\|·•\-–]*\d+\s*$", "", t)
        return self.normalize_ws(t)

    def _extract_emails(self, ocr_text: str) -> List[str]:
        if not ocr_text:
            return []
        # 容错：OCR 可能把 @ 识别成 (at) 或空格
        text = str(ocr_text)
        text = text.replace("(at)", "@").replace("[at]", "@").replace(" at ", "@")
        emails = re.findall(r"\b[\w.\-+]+\s*@\s*[\w.\-]+\.[A-Za-z]{2,}\b", text)
        out: List[str] = []
        seen = set()
        for e in emails:
            e2 = self.normalize_ws(e).replace(" ", "")
            if e2.lower() in seen:
                continue
            seen.add(e2.lower())
            out.append(e2)
        return out

    def _find_name_span(
        self,
        search_text: str,
        name: str,
        start_pos: int = 0,
        end_pos: Optional[int] = None,
    ) -> Optional[re.Match]:
        """Find a tolerant match span for a scout author name within OCR text."""
        if not search_text or not name:
            return None

        name_literal = self.strip_accents(name)

        if end_pos is None:
            end_pos = len(search_text)
        start_pos = max(0, int(start_pos or 0))
        end_pos = min(len(search_text), int(end_pos))
        if start_pos >= end_pos:
            start_pos = 0
            end_pos = len(search_text)

        # 1) Token-based tolerant match for English names (handles Z.P. Liu vs Z. P. Liu)
        # IMPORTANT:
        # - Publishers often render affiliation markers immediately after the name (e.g. "Yang1²").
        # - OCR may glue the previous author's markers into the next author's name (e.g. "Yang12Yuan").
        # So we avoid using \b boundaries that fail between digit↔letter.
        tokens = re.findall(r"[A-Za-z]+", name_literal)
        if len(tokens) >= 2:
            pat = r"(?<![A-Za-z])" + r"[\\s\\W_]{0,3}".join(re.escape(t) for t in tokens) + r"(?![A-Za-z])"
            try:
                rx = re.compile(pat, re.I)
                m = rx.search(search_text, start_pos, end_pos)
                if m:
                    return m
            except Exception:
                pass

            # 1b) Relaxed fallback: match only first+last token (tolerate middle token OCR errors)
            try:
                first = tokens[0]
                last = tokens[-1]
                pat2 = r"(?<![A-Za-z])" + re.escape(first) + r"[\\s\\W_]{0,20}" + re.escape(last) + r"(?![A-Za-z])"
                rx2 = re.compile(pat2, re.I)
                m = rx2.search(search_text, start_pos, end_pos)
                if m:
                    return m
            except Exception:
                pass

        # 2) Fallback: exact-ish match (useful for Chinese names)
        try:
            return re.search(re.escape(name_literal), search_text, re.I)
        except Exception:
            return None

    def parse_authors_rule_based(
        self,
        ocr_text: str,
        doi: str,
        scout_authors: Optional[List[Dict[str, Any]]] = None,
        meta_institutions: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Parse authors + affiliations without any LLM."""
        if not ocr_text:
            return []

        aff_map = self.extract_affiliation_map(ocr_text)
        max_aff_num = max(aff_map.keys()) if aff_map else 9

        debug = str(os.getenv("OCR_RULE_DEBUG", "0")).strip().lower() in {"1", "true", "yes", "y"}

        search_text = self.strip_accents(ocr_text)
        # 用于定位“同一行”范围，避免角标解析跨行吃到机构列表的 "1." 编号
        lines_raw = str(search_text).splitlines()
        line_starts: List[int] = []
        _pos = 0
        for ln in lines_raw:
            line_starts.append(_pos)
            _pos += len(ln) + 1  # +1 for the removed newline

        def _line_bounds(idx: int) -> tuple[int, int]:
            if idx < 0:
                return (0, len(search_text))
            # find rightmost line_start <= idx
            lo = 0
            hi = len(line_starts) - 1
            best = 0
            while lo <= hi:
                mid = (lo + hi) // 2
                if line_starts[mid] <= idx:
                    best = mid
                    lo = mid + 1
                else:
                    hi = mid - 1
            start = line_starts[best]
            end = line_starts[best + 1] - 1 if best + 1 < len(line_starts) else len(search_text)
            return (start, end)

        author_names: List[str] = []
        if isinstance(scout_authors, list):
            for a in scout_authors:
                if isinstance(a, dict) and a.get("name"):
                    author_names.append(str(a.get("name")).strip())
                elif isinstance(a, str) and a.strip():
                    author_names.append(a.strip())

        if not author_names:
            top_lines = [self.normalize_ws(x) for x in str(ocr_text).splitlines()[:5]]
            blob = " ".join([x for x in top_lines if x])
            candidates = re.findall(r"\b[A-Z][A-Za-z\-\.]+\s+[A-Z][A-Za-z\-\.]+\b", blob)
            author_names = list(dict.fromkeys(candidates))

        cofirst = bool(re.search(r"contributed\s+equally", search_text, re.I))

        emails_global = self._extract_emails(ocr_text)

        authors_out: List[Dict[str, Any]] = []

        spans: List[Optional[tuple[int, int]]] = []
        cursor = 0
        for name in author_names:
            if not name:
                spans.append(None)
                continue
            name_pat = self.normalize_for_match(name)
            if not name_pat:
                spans.append(None)
                continue

            # 在原始（仅 strip accents）文本中找 span，避免“点号/空格/换行”导致完全找不到。
            # 关键：按作者顺序从上一个作者之后开始找，减少 OCR 粘连/重复匹配导致的漏检。
            m2 = self._find_name_span(search_text, name, start_pos=cursor, end_pos=min(len(search_text), cursor + 2500))
            if not m2 and cursor > 0:
                m2 = self._find_name_span(search_text, name)

            if m2:
                cursor = max(cursor, m2.end())
                spans.append((m2.start(), m2.end()))
            else:
                spans.append(None)

        def _next_span(idx: int) -> Optional[tuple[int, int]]:
            for j in range(idx + 1, len(spans)):
                if spans[j]:
                    return spans[j]
            return None

        for idx, name in enumerate(author_names, start=1):
            span = spans[idx - 1] if idx - 1 < len(spans) else None

            if debug:
                print(f"[ocr-rule] name={name!r} span={'Y' if span else 'N'}")

            marker_numbers: List[int] = []
            markers = ""

            if span:
                _, span_end = span
                # 只在“作者所在行”抓角标，避免跨行把机构列表编号（1. 2. 3.）吃进去
                lb, le = _line_bounds(span_end)
                tail = search_text[span_end : min(le, span_end + 160)]
                tail = tail.lstrip(" \t")
                collected: List[str] = []
                collected_markers: List[str] = []
                raw_digit_like: List[str] = []
                for ch in tail:
                    if ch.isdigit() or ch in {",", ";", " ", "-", "–"}:
                        collected.append(ch)
                        if ch.isdigit():
                            raw_digit_like.append(ch)
                    elif ch in {"*", "#", "†", "‡", "✉"}:
                        collected_markers.append(ch)
                    else:
                        if str(ch).isalpha():
                            break
                        break

                # 如果抓到的是上标数字（例如 ²³），更倾向于“多角标粘连”而不是第 12 个单位
                prefer_split_hint = any((d not in "0123456789") for d in raw_digit_like)

                known = set(aff_map.keys()) if aff_map else None
                marker_numbers = self.split_marker_numbers(
                    "".join(collected),
                    max_aff_num=max_aff_num,
                    known_aff_nums=known,
                    prefer_split_hint=prefer_split_hint,
                )
                markers = "".join(collected_markers)

                if debug:
                    print(f"[ocr-rule]  markers_raw={''.join(collected)!r} -> nums={marker_numbers}")

                # 兜底：若同一行没抓到（OCR 换行/断字常见），允许跨行再抓一次，
                # 但遇到机构列表的 "\n12." 这类编号就截断，避免粘连。
                if not marker_numbers:
                    tail2 = search_text[span_end : span_end + 160]
                    cut = re.search(r"\r?\n\s*\d{1,2}\s*[\.\)]\s*", tail2)
                    if cut:
                        tail2 = tail2[: cut.start()]
                    tail2 = tail2.lstrip(" \t\r\n")
                    collected2: List[str] = []
                    for ch in tail2:
                        if ch in {"\r", "\n", "\t"}:
                            collected2.append(" ")
                            continue
                        if ch.isdigit() or ch in {",", ";", " ", "-", "–"}:
                            collected2.append(ch)
                        else:
                            if str(ch).isalpha():
                                break
                            break
                    known2 = set(aff_map.keys()) if aff_map else None
                    marker_numbers = self.split_marker_numbers(
                        "".join(collected2),
                        max_aff_num=max_aff_num,
                        known_aff_nums=known2,
                        prefer_split_hint=prefer_split_hint,
                    )

                    if debug:
                        print(f"[ocr-rule]  markers_raw_fallback={''.join(collected2)!r} -> nums={marker_numbers}")

                # 再兜底：使用“当前作者 → 下一作者”的窗口抽取角标
                if not marker_numbers:
                    next_span = _next_span(idx - 1)
                    if next_span:
                        window = search_text[span_end : next_span[0]]
                    else:
                        window = search_text[span_end : span_end + 200]
                    cut3 = re.search(r"\r?\n\s*\d{1,2}\s*[\.\)]\s*", window)
                    if cut3:
                        window = window[: cut3.start()]
                    window = window.lstrip(" \t\r\n")
                    collected3: List[str] = []
                    collected_markers3: List[str] = []
                    for ch in window:
                        if ch in {"\r", "\n", "\t"}:
                            collected3.append(" ")
                            continue
                        if ch.isdigit() or ch in {",", ";", " ", "-", "–"}:
                            collected3.append(ch)
                        elif ch in {"*", "#", "†", "‡", "✉"}:
                            collected_markers3.append(ch)
                        else:
                            if str(ch).isalpha():
                                break
                            break

                    known3 = set(aff_map.keys()) if aff_map else None
                    marker_numbers = self.split_marker_numbers(
                        "".join(collected3),
                        max_aff_num=max_aff_num,
                        known_aff_nums=known3,
                        prefer_split_hint=prefer_split_hint,
                    )
                    if not markers:
                        markers = "".join(collected_markers3)
                    if debug:
                        print(f"[ocr-rule]  markers_raw_window={''.join(collected3)!r} -> nums={marker_numbers}")

            if not marker_numbers:
                try:
                    name_literal = self.strip_accents(name)
                    m3 = re.search(rf"{re.escape(name_literal)}\s*([\d][\d,;\s\-–]{{0,20}})", search_text, re.I)
                    if m3:
                        chunk = m3.group(1) or ""
                        # 同样防止吃到机构列表的 "1." 起始编号
                        cut2 = re.search(r"(?:\r?\n|\s)1\s*[\.\)]\s*", chunk)
                        if cut2:
                            chunk = chunk[: cut2.start()]
                        known = set(aff_map.keys()) if aff_map else None
                        marker_numbers = self.split_marker_numbers(
                            chunk,
                            max_aff_num=max_aff_num,
                            known_aff_nums=known,
                            prefer_split_hint=None,
                        )
                except Exception:
                    pass

            affs: List[str] = []
            if marker_numbers:
                if aff_map:
                    for n in marker_numbers:
                        if n in aff_map:
                            affs.append(aff_map[n])
                elif isinstance(meta_institutions, list) and meta_institutions:
                    for n in marker_numbers:
                        i = n - 1
                        if 0 <= i < len(meta_institutions):
                            affs.append(str(meta_institutions[i]).strip())

            uniq_affs: List[str] = []
            seen_aff = set()
            for a in affs:
                a = self.clean_affiliation_text(a)
                if not a:
                    continue
                if a in seen_aff:
                    continue
                seen_aff.add(a)
                uniq_affs.append(a)

            authors_out.append(
                {
                    "name": str(name).strip(),
                    "position": idx,
                    "is_corresponding": ("*" in markers) or ("✉" in markers),
                    "is_co_first": bool(cofirst and idx <= 2),
                    "affiliation_numbers": marker_numbers,
                    "affiliations": uniq_affs,
                    "affiliation": "; ".join(uniq_affs) if uniq_affs else "",
                    "markers": markers,
                    "source": "ocr-rule",
                    "emails": emails_global,
                }
            )

        return authors_out
