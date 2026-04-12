import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from ..utils.ocr_rule_parser import OcrRuleParser
from ..utils.webdriver import WebDriverAdapter

from config import VISUAL_SLICE_DIR

logger = logging.getLogger(__name__)

class VisionAgent:
    """
    [Vision Agent]
    职责：
    - 对论文截图执行 OCR → 解析作者/单位/标记
    - 当 LLM 不可用时，使用规则解析（ocr-rule）保证主链路可跑通
    - `process(doi)` 会通过 WebDriver 获取截图后调用 `analyze_screenshot`
    """

    def __init__(self):
        if not os.path.exists(VISUAL_SLICE_DIR):
            os.makedirs(VISUAL_SLICE_DIR)

        self.webdriver = WebDriverAdapter()
        self.ocr_rule_parser = OcrRuleParser()

    def _load_bgr_image(self, image_path: str) -> Any:
        """Load image as BGR array when possible; fall back to path string."""
        try:
            import cv2  # type: ignore[import-not-found]

            img = cv2.imread(image_path)
            if img is not None:
                return img
        except Exception as exc:
            logger.debug("[Vision] cv2 load failed: %s", exc)

        try:
            from PIL import Image  # type: ignore[import-not-found]
            import numpy as np  # type: ignore[import-not-found]

            img = Image.open(image_path).convert("RGB")
            arr = np.array(img)
            return arr[:, :, ::-1].copy()
        except Exception as exc:
            logger.debug("[Vision] PIL/numpy load failed: %s", exc)

        logger.debug("[Vision] Falling back to image path for OCR input")
        return image_path

    def _normalize_ocr_result(self, result: Any) -> tuple[List[str], List[Dict[str, Any]]]:
        """Normalize OCR outputs (PaddleOCR/PaddleX) into text lines + box items."""
        items: List[Dict[str, Any]] = []
        text_lines: List[str] = []

        def _add_line(text: str, score: Any = None, box: Any = None) -> None:
            text_s = str(text or "").strip()
            if not text_s:
                return
            items.append({"text": text_s, "score": score, "box": box})
            if score is None or (isinstance(score, (int, float)) and score > 0.3):
                text_lines.append(text_s)

        def _handle_dict(res: Dict[str, Any]) -> None:
            rec_texts = res.get("rec_texts") or []
            rec_scores = res.get("rec_scores") or []
            dt_polys = res.get("dt_polys") or res.get("det_polys") or []

            if isinstance(rec_texts, str):
                rec_texts = [rec_texts]
            if not isinstance(rec_texts, list):
                rec_texts = []
            if not isinstance(rec_scores, list):
                rec_scores = []
            if not isinstance(dt_polys, list):
                dt_polys = []

            for idx, text in enumerate(rec_texts):
                score = rec_scores[idx] if idx < len(rec_scores) else None
                box = dt_polys[idx] if idx < len(dt_polys) else None
                _add_line(text, score=score, box=box)

        def _is_line_entry(x: Any) -> bool:
            return isinstance(x, (list, tuple)) and len(x) >= 2 and isinstance(x[0], (list, tuple))

        if isinstance(result, dict):
            _handle_dict(result)
            return text_lines, items

        if isinstance(result, list) and result:
            if isinstance(result[0], dict):
                for res in result:
                    if isinstance(res, dict):
                        _handle_dict(res)
                return text_lines, items

            lines = []
            if _is_line_entry(result[0]):
                lines = result
            elif isinstance(result[0], list) and result[0] and _is_line_entry(result[0][0]):
                lines = result[0]

            for line in lines:
                try:
                    box = line[0]
                    rec = line[1]
                    text = ""
                    score = None
                    if isinstance(rec, (list, tuple)) and rec:
                        text = str(rec[0] or "").strip()
                        if len(rec) > 1 and isinstance(rec[1], (int, float)):
                            score = float(rec[1])
                    _add_line(text, score=score, box=box)
                except Exception as exc:
                    logger.debug("[Vision] OCR line parse failed: %s", exc)
                    continue

        return text_lines, items

    def analyze_screenshot(
        self,
        image_path: str,
        doi: Optional[str] = None,
        scout_authors: Optional[List[Dict[str, Any]]] = None,
        meta_institutions: Optional[List[str]] = None,
        author_roi_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        兼容旧接口：对已有截图执行 OCR+解析，返回与 process 相同的数据结构。
        """
        if not image_path or not os.path.exists(image_path):
            logger.warning("[Vision] Invalid image path: %s", image_path)
            return {"text": "", "image_path": None, "authors": [], "error": "invalid_image_path"}

        # 回填 DOI，便于 mock/fallback 路由
        doi_for_analysis = doi or os.path.splitext(os.path.basename(image_path))[0].replace('_', '/')
        def _author_quality_score(authors: Any) -> int:
            if not isinstance(authors, list) or not authors:
                return 0
            with_aff = 0
            with_nums = 0
            for a in authors:
                if not isinstance(a, dict):
                    continue
                aff = str(a.get("affiliation") or "").strip()
                affs = a.get("affiliations")
                nums = a.get("affiliation_numbers")
                if aff:
                    with_aff += 1
                elif isinstance(affs, list) and any(str(x).strip() for x in affs):
                    with_aff += 1
                if isinstance(nums, list) and any(isinstance(x, int) and x > 0 for x in nums):
                    with_nums += 1
            # Strongly prefer having the right number of authors; then prefer richer structure.
            return len(authors) * 10 + with_aff * 2 + with_nums

        try:
            base = self._ocr_and_parse(
                image_path,
                doi_for_analysis,
                scout_authors=scout_authors,
                meta_institutions=meta_institutions,
            )

            base["author_roi_path"] = author_roi_path if author_roi_path else None
            base["author_roi_used"] = False

            if (
                author_roi_path
                and os.path.exists(author_roi_path)
                and os.getenv("VISION_ENABLE_AUTHOR_ROI", "1").strip().lower() not in {"0", "false", "no"}
            ):
                base_authors = base.get("authors") or []
                scout_len = len(scout_authors or [])

                force_roi = os.getenv("VISION_FORCE_AUTHOR_ROI", "0").strip().lower() not in {
                    "0",
                    "false",
                    "no",
                    "",
                }

                # Only spend the extra OCR pass if the base result looks weak.
                base_looks_weak = (not base_authors) or (
                    scout_len > 0 and isinstance(base_authors, list) and len(base_authors) < max(1, int(scout_len * 0.6))
                )

                if base_looks_weak or force_roi:
                    roi = self._ocr_and_parse(
                        author_roi_path,
                        doi_for_analysis,
                        scout_authors=scout_authors,
                        meta_institutions=meta_institutions,
                    )
                    roi_authors = roi.get("authors") or []
                    if _author_quality_score(roi_authors) > _author_quality_score(base_authors):
                        base["authors"] = roi_authors
                        base["author_roi_used"] = True
                        # Keep the full-page text as evidence, but expose ROI text for debugging.
                        base["author_roi_text"] = roi.get("text")

            return base
        except Exception as exc:
            logger.exception("[Vision] analyze_screenshot failed: %s", exc)
            return {
                "text": "",
                "image_path": image_path,
                "authors": [],
                "ocr_failed": True,
                "error": str(exc),
            }

    def _validate_and_normalize_authors(self, authors: Any) -> List[Dict[str, Any]]:
        """
        【关键函数】确保作者列表格式正确，兼容Judge Agent的期望格式
        
        输入: 任意格式的作者列表 (可能来自JSON解析)
        输出: 标准化的作者字典列表
        """
        if not isinstance(authors, list):
            logger.warning("[Vision] authors is not list: %s", type(authors))
            return []
        
        validated: List[Dict[str, Any]] = []
        for i, author in enumerate(authors):
            if not isinstance(author, dict):
                logger.warning("[Vision] author[%s] is not dict, skipped", i)
                continue
            
            # 创建标准化的作者记录
            normalized: Dict[str, Any] = {
                'name': str(author.get('name', 'Unknown')).strip(),
                'affiliation': str(author.get('affiliation', '')).strip(),
                'position': int(author.get('position', 999)),
                'is_corresponding': bool(author.get('is_corresponding', False)),
                'is_co_first': bool(author.get('is_co_first', False))
            }

            # 保留可选证据/结构化字段（Judge 可利用）
            if isinstance(author.get('affiliations'), list):
                normalized['affiliations'] = [str(x).strip() for x in author.get('affiliations') if str(x).strip()]
            if isinstance(author.get('affiliation_numbers'), list):
                nums = []
                for x in author.get('affiliation_numbers'):
                    try:
                        xi = int(x)
                        if xi > 0:
                            nums.append(xi)
                    except Exception:
                        continue
                normalized['affiliation_numbers'] = nums
            for k in ('has_mail_icon', 'markers', 'source', 'corresponding_source'):
                if k in author:
                    normalized[k] = author.get(k)
            
            # 验证必要字段
            if not normalized['name'] or normalized['name'].lower() == 'unknown':
                logger.warning("[Vision] author[%s] missing name, skipped", i)
                continue
            
            validated.append(normalized)
        
        logger.info("[Vision] Normalized %s authors", len(validated))
        return validated

    def process(self, doi):
        """
        Vision Agent 的主入口。
        流程：WebDriver 截图 → OCR 识别 →（LLM 或 ocr-rule）解析 → 返回作者列表
        """
        if not doi:
            return {"text": "", "image_path": None, "authors": []}

        logger.info("[Vision] Capturing screenshot for DOI: %s", doi)
        image_path = self.webdriver.get_webpage_screenshot(doi)
        if not image_path:
            logger.warning("[Vision] Screenshot unavailable for DOI: %s", doi)
            return {"text": "", "image_path": None, "authors": [], "error": "screenshot_failed"}

        return self.analyze_screenshot(image_path, doi=doi)
    
    def _ocr_and_parse(
        self,
        image_path: str,
        doi: str,
        scout_authors: Optional[List[Dict[str, Any]]] = None,
        meta_institutions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        新流程：OCR 识别 → 规则解析
        """
        logger.info("[Vision] Running OCR for %s", doi)
        
        # 第一步：OCR 识别截图中的文本（若可用，先尝试带 BBox 的 OCR 以便做 ROI 切片）
        ocr_text = None
        ocr_items: List[Dict[str, Any]] = []
        roi_meta: Optional[Dict[str, Any]] = None
        if os.getenv("OCR_ENABLE_ROI", "1").strip().lower() not in {"0", "false", "no"}:
            ocr_text, ocr_items = self._extract_text_and_boxes_by_ocr(image_path)

        if not ocr_text:
            ocr_text = self._extract_text_by_ocr(image_path)
        
        if not ocr_text:
            # OCR 失败时不要回退到 mock（会污染后续融合/输出）。
            # 让 Orchestrator 用 hover authors 兜底（或至少保留 Scout authors）。
            logger.warning("[Vision] OCR failed, returning empty authors")
            return {"text": "", "image_path": image_path, "authors": [], "ocr_failed": True}
        
        # ROI 切片：从整页 OCR 中定位作者块和单位块，减少噪声
        if ocr_text and ocr_items and scout_authors:
            roi_text, roi_meta = self._build_roi_text(image_path, ocr_items, scout_authors)
            if roi_text:
                ocr_text = roi_text

        # Persist OCR + BBox + ROI info for audit/debug
        self._save_ocr_sidecar(
            image_path,
            doi,
            ocr_text,
            ocr_items,
            roi_meta,
        )

        # 第二步：用规则解析从 OCR 文本中提取作者信息
        logger.info("[Vision] OCR text length: %s", len(ocr_text))
        
        authors = self._parse_authors_from_text(
            ocr_text,
            doi,
            scout_authors=scout_authors,
            meta_institutions=meta_institutions,
        )

        aff_map = self.ocr_rule_parser.extract_affiliation_map(ocr_text)

        # JMIR-like pages often show affiliation details under an 'Authors' tab.
        # If we only captured the article top, we may have superscript numbers but no affiliation list,
        # which leads Judge to output Unknown. Do one best-effort retry to capture the Authors section.
        if not aff_map:
            low = ocr_text.lower()
            looks_like_jmir = ("jmir" in low) or ("j med internet res" in low)
            has_superscripts = bool(re.search(r"\b\w+\s*\d+(?:\s*,\s*\d+)*\b", ocr_text))
            if looks_like_jmir and has_superscripts:
                try:
                    logger.info("[Vision] No affiliation map; retrying JMIR Authors section capture")
                    alt_path = self.webdriver.get_webpage_screenshot(
                        doi,
                        full_page=True,
                        section="authors",
                        save_suffix="authors_full",
                    )
                    if alt_path and os.path.exists(alt_path):
                        alt_text, alt_items = self._extract_text_and_boxes_by_ocr(alt_path)
                        if not alt_text:
                            alt_text = self._extract_text_by_ocr(alt_path)
                            alt_items = []
                        if alt_text:
                            self._save_ocr_sidecar(alt_path, doi, alt_text, alt_items, None)
                            aff_map2 = self.ocr_rule_parser.extract_affiliation_map(alt_text)
                            if aff_map2:
                                aff_map = aff_map2
                                # Keep full_text as combined evidence (top + authors tab)
                                ocr_text = ocr_text + "\n\n" + alt_text
                except Exception as exc:
                    logger.debug("[Vision] JMIR Authors retry failed: %s", exc)
        
        return {
            "text": ocr_text[:500] + "..." if len(ocr_text) > 500 else ocr_text,
            "full_text": ocr_text,
            "affiliation_map": aff_map,
            "meta_institutions": meta_institutions or [],
            "image_path": image_path,
            "authors": authors
        }
    
    def _extract_text_by_ocr(self, image_path):
        """
        使用本地 PaddleOCR 识别截图中的文本
        
        流程：
        1️⃣ 优先用 PaddleOCR（完全免费，本地运行，中英文支持好）
        2️⃣ 失败就返回 None
        
        返回: 识别的纯文本或 None
        """
        # 方案 1️⃣：优先使用本地 PaddleOCR（最稳定）
        logger.info("[Vision] Running PaddleOCR text extraction")
        try:
            # Paddle/PaddleOCR 在部分版本组合下会触发 PIR/oneDNN 执行器的不兼容错误。
            # 默认使用更保守的执行路径，提升稳定性（用户可自行通过环境变量覆盖）。
            os.environ.setdefault("FLAGS_enable_pir_api", "0")
            os.environ.setdefault("FLAGS_enable_pir_in_executor", "0")
            os.environ.setdefault("FLAGS_use_mkldnn", "0")
            os.environ.setdefault("FLAGS_use_onednn", "0")

            from paddleocr import PaddleOCR  # type: ignore[import-not-found]
            # 使用新参数名，避免过时警告
            ocr = PaddleOCR(use_textline_orientation=True, lang='ch')
            image_input = self._load_bgr_image(image_path)
            result = ocr.predict(image_input)

            text_lines, _items = self._normalize_ocr_result(result)
            if not text_lines:
                try:
                    result = ocr.ocr(image_input, cls=True)
                    text_lines, _items = self._normalize_ocr_result(result)
                except Exception as exc:
                    logger.debug("[Vision] OCR fallback failed: %s", exc)
            
            if text_lines:
                ocr_text = "\n".join(text_lines)
                logger.info("[Vision] PaddleOCR extracted %s lines", len(text_lines))
                return ocr_text

            logger.warning("[Vision] PaddleOCR returned no text")
            return None
        
        except ImportError:
            logger.warning("[Vision] PaddleOCR not installed")
        except Exception as e:
            logger.warning("[Vision] PaddleOCR error: %s", e)

        logger.warning("[Vision] OCR failed")
        return None

    def _extract_text_and_boxes_by_ocr(self, image_path: str) -> tuple[Optional[str], List[Dict[str, Any]]]:
        """OCR + BBox 信息（用于 ROI 切片）。失败时返回 (None, [])."""
        logger.info("[Vision] Running OCR+BBox for ROI")
        try:
            # 保守执行路径，避免 PIR/oneDNN 报错
            os.environ.setdefault("FLAGS_enable_pir_api", "0")
            os.environ.setdefault("FLAGS_enable_pir_in_executor", "0")
            os.environ.setdefault("FLAGS_use_mkldnn", "0")
            os.environ.setdefault("FLAGS_use_onednn", "0")

            from paddleocr import PaddleOCR  # type: ignore[import-not-found]
            ocr = PaddleOCR(use_textline_orientation=True, lang='ch')
            image_input = self._load_bgr_image(image_path)
            result = ocr.ocr(image_input, cls=True)
            text_lines, items = self._normalize_ocr_result(result)

            if not text_lines:
                try:
                    result = ocr.predict(image_input)
                    text_lines, items = self._normalize_ocr_result(result)
                except Exception as exc:
                    logger.debug("[Vision] OCR predict fallback failed: %s", exc)

            if text_lines:
                return "\n".join(text_lines), items
        except ImportError:
            logger.warning("[Vision] PaddleOCR not installed")
        except Exception as exc:
            logger.debug("[Vision] OCR+BBox failed: %s", exc)

        return None, []

    def _build_roi_text(
        self,
        image_path: str,
        ocr_items: List[Dict[str, Any]],
        scout_authors: List[Dict[str, Any]],
    ) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
        """基于 OCR BBox 切片作者块与单位块，减少噪声。"""
        if not ocr_items or not scout_authors:
            return None, None

        def _name_tokens(name: str) -> List[str]:
            tokens = re.findall(r"[A-Za-z]+", str(name or ""))
            return [t.lower() for t in tokens if len(t) >= 3]

        name_tokens = set()
        for a in scout_authors:
            if isinstance(a, dict):
                for t in _name_tokens(a.get("name")):
                    name_tokens.add(t)
            elif isinstance(a, str):
                for t in _name_tokens(a):
                    name_tokens.add(t)

        def _box_points(box: Any) -> List[tuple[float, float]]:
            if not box:
                return []
            if isinstance(box, (list, tuple)) and box and isinstance(box[0], (int, float)):
                pts = []
                for i in range(0, len(box) - 1, 2):
                    pts.append((float(box[i]), float(box[i + 1])))
                return pts
            if isinstance(box, (list, tuple)) and box and isinstance(box[0], (list, tuple)):
                return [(float(p[0]), float(p[1])) for p in box if isinstance(p, (list, tuple)) and len(p) >= 2]
            return []

        def _union_bbox(boxes: List[Any]) -> Optional[tuple[int, int, int, int]]:
            xs: List[float] = []
            ys: List[float] = []
            for b in boxes:
                for x, y in _box_points(b):
                    xs.append(x)
                    ys.append(y)
            if not xs or not ys:
                return None
            return (int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys)))

        author_boxes = []
        aff_boxes = []
        for it in ocr_items:
            text = str(it.get("text") or "").strip()
            text_l = text.lower()
            if not text_l:
                continue
            if name_tokens and any(tok in text_l for tok in name_tokens):
                author_boxes.append(it.get("box"))
            if re.match(r"^\s*\d{1,2}\s*[\.\)]\s+", text_l) or re.search(
                r"\b(university|hospital|institute|department|school|center|centre|college)\b",
                text_l,
            ):
                aff_boxes.append(it.get("box"))

        if not author_boxes and not aff_boxes:
            return None, None

        try:
            from PIL import Image
            img = Image.open(image_path)
            w, h = img.size

            roi_meta: Dict[str, Any] = {
                "author_bbox": None,
                "aff_bbox": None,
                "author_roi_image": None,
                "aff_roi_image": None,
                "roi_texts": [],
            }

            def _crop_to(box: tuple[int, int, int, int], suffix: str) -> Optional[str]:
                x1, y1, x2, y2 = box
                margin = 12
                x1 = max(0, x1 - margin)
                y1 = max(0, y1 - margin)
                x2 = min(w, x2 + margin)
                y2 = min(h, y2 + margin)
                if x2 <= x1 or y2 <= y1:
                    return None
                crop = img.crop((x1, y1, x2, y2))
                base = os.path.splitext(os.path.basename(image_path))[0]
                out_path = os.path.join(VISUAL_SLICE_DIR, f"{base}_{suffix}.png")
                crop.save(out_path)
                return out_path

            roi_texts: List[str] = []
            author_bb = _union_bbox(author_boxes)
            if author_bb:
                roi_meta["author_bbox"] = list(author_bb)
                p = _crop_to(author_bb, "roi_author")
                if p:
                    roi_meta["author_roi_image"] = p
                    t = self._extract_text_by_ocr(p)
                    if t:
                        roi_texts.append(t)

            aff_bb = _union_bbox(aff_boxes)
            if aff_bb:
                roi_meta["aff_bbox"] = list(aff_bb)
                p = _crop_to(aff_bb, "roi_aff")
                if p:
                    roi_meta["aff_roi_image"] = p
                    t = self._extract_text_by_ocr(p)
                    if t:
                        roi_texts.append(t)

            if roi_texts:
                roi_meta["roi_texts"] = roi_texts
                return "\n".join(roi_texts), roi_meta
        except Exception:
            return None, None

        return None, None

    def _save_ocr_sidecar(
        self,
        image_path: str,
        doi: str,
        ocr_text: str,
        ocr_items: List[Dict[str, Any]],
        roi_meta: Optional[Dict[str, Any]],
    ) -> None:
        """Save OCR output and BBox/ROI metadata for tracing."""
        if not image_path or not ocr_text:
            return
        base = os.path.splitext(os.path.basename(image_path))[0]
        sidecar_path = os.path.join(VISUAL_SLICE_DIR, f"{base}_ocr_sidecar.json")

        try:
            max_items = int(os.getenv("OCR_SIDECAR_MAX_ITEMS", "500").strip() or "500")
        except Exception:
            max_items = 500
        try:
            max_text = int(os.getenv("OCR_SIDECAR_MAX_TEXT", "4000").strip() or "4000")
        except Exception:
            max_text = 4000

        def _normalize_box(box: Any) -> Any:
            if not box:
                return None
            if isinstance(box, (list, tuple)) and box and isinstance(box[0], (int, float)):
                out = []
                for i in range(0, len(box) - 1, 2):
                    try:
                        out.append([float(box[i]), float(box[i + 1])])
                    except Exception:
                        continue
                return out
            if isinstance(box, (list, tuple)) and box and isinstance(box[0], (list, tuple)):
                out = []
                for pt in box:
                    if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                        try:
                            out.append([float(pt[0]), float(pt[1])])
                        except Exception:
                            continue
                return out
            return None

        items_out: List[Dict[str, Any]] = []
        for it in ocr_items[:max_items]:
            if not isinstance(it, dict):
                continue
            items_out.append(
                {
                    "text": str(it.get("text") or ""),
                    "score": it.get("score"),
                    "box": _normalize_box(it.get("box")),
                }
            )

        payload = {
            "doi": doi,
            "image_path": image_path,
            "ocr_text": (ocr_text[:max_text] if isinstance(ocr_text, str) else ""),
            "ocr_items": items_out,
            "roi": roi_meta or {},
        }

        try:
            with open(sidecar_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=True, indent=2)
        except Exception as exc:
            logger.debug("[Vision] Failed to save OCR sidecar: %s", exc)
    
    
    def _parse_authors_from_text(
        self,
        ocr_text: str,
        doi: str,
        scout_authors: Optional[List[Dict[str, Any]]] = None,
        meta_institutions: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        使用规则解析从 OCR 文本中提取作者信息和排序
        """
        authors = self.ocr_rule_parser.parse_authors_rule_based(
            ocr_text,
            doi,
            scout_authors=scout_authors,
            meta_institutions=meta_institutions,
        )
        return self._validate_and_normalize_authors(authors)
    
