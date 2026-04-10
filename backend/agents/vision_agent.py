import os
import base64
import requests
import json
from typing import Any, Dict, List, Optional
import re

from ..utils.ocr_rule_parser import OcrRuleParser
from ..utils.webdriver import WebDriverAdapter

from config import VISUAL_SLICE_DIR, DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL

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

    def analyze_screenshot(
        self,
        image_path: str,
        doi: Optional[str] = None,
        scout_authors: Optional[List[Dict[str, Any]]] = None,
        meta_institutions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        兼容旧接口：对已有截图执行 OCR+解析，返回与 process 相同的数据结构。
        """
        if not image_path or not os.path.exists(image_path):
            print(f"[Vision] ⚠️ 无效的截图路径: {image_path}")
            return {"text": "", "image_path": None, "authors": []}

        # 回填 DOI，便于 mock/fallback 路由
        doi_for_analysis = doi or os.path.splitext(os.path.basename(image_path))[0].replace('_', '/')
        try:
            return self._ocr_and_parse(
                image_path,
                doi_for_analysis,
                scout_authors=scout_authors,
                meta_institutions=meta_institutions,
            )
        except Exception as exc:
            print(f"[Vision] ⚠️ analyze_screenshot 失败: {exc}")
            return self._get_mock_authors(doi_for_analysis)

    def _validate_and_normalize_authors(self, authors: Any) -> List[Dict[str, Any]]:
        """
        【关键函数】确保作者列表格式正确，兼容Judge Agent的期望格式
        
        输入: 任意格式的作者列表 (可能来自JSON解析)
        输出: 标准化的作者字典列表
        """
        if not isinstance(authors, list):
            print(f"[Vision] ⚠️ 警告: authors不是list，而是{type(authors)}")
            return []
        
        validated: List[Dict[str, Any]] = []
        for i, author in enumerate(authors):
            if not isinstance(author, dict):
                print(f"[Vision] ⚠️ 警告: author[{i}]不是dict，跳过")
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
            for k in ('emails', 'has_mail_icon', 'markers', 'source', 'corresponding_source'):
                if k in author:
                    normalized[k] = author.get(k)
            
            # 验证必要字段
            if not normalized['name'] or normalized['name'].lower() == 'unknown':
                print(f"[Vision] ⚠️ 警告: author[{i}]缺少name字段，跳过")
                continue
            
            validated.append(normalized)
        
        print(f"[Vision] ✅ 标准化了{len(validated)}名作者")
        return validated

    def process(self, doi):
        """
        Vision Agent 的主入口。
        流程：WebDriver 截图 → OCR 识别 →（LLM 或 ocr-rule）解析 → 返回作者列表
        """
        if not doi:
            return {"text": "", "image_path": None, "authors": []}

        print(f"\n[Vision] 📸 通过 WebDriver 获取截图，DOI: {doi}")
        image_path = self.webdriver.get_webpage_screenshot(doi)
        if not image_path:
            print("[Vision] ⚠️ 无法获取截图，使用 mock 数据")
            return self._get_mock_authors(doi)

        return self.analyze_screenshot(image_path, doi=doi)
    
    def _ocr_and_parse(
        self,
        image_path: str,
        doi: str,
        scout_authors: Optional[List[Dict[str, Any]]] = None,
        meta_institutions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        新流程：OCR 识别 → DeepSeek 文本模型解析
        """
        print(f"[Vision] 🔍 使用 OCR 识别截图文本...")
        
        # 第一步：OCR 识别截图中的文本（若可用，先尝试带 BBox 的 OCR 以便做 ROI 切片）
        ocr_text = None
        ocr_items: List[Dict[str, Any]] = []
        if os.getenv("OCR_ENABLE_ROI", "1").strip().lower() not in {"0", "false", "no"}:
            ocr_text, ocr_items = self._extract_text_and_boxes_by_ocr(image_path)

        if not ocr_text:
            ocr_text = self._extract_text_by_ocr(image_path)
        
        if not ocr_text:
            # OCR 失败时不要回退到 mock（会污染后续融合/输出）。
            # 让 Orchestrator 用 hover authors 兜底（或至少保留 Scout authors）。
            print(f"[Vision] ⚠️  OCR 识别失败，返回空 authors，等待 hover/scout 兜底")
            return {"text": "", "image_path": image_path, "authors": [], "ocr_failed": True}
        
        # ROI 切片：从整页 OCR 中定位作者块和单位块，减少噪声
        if ocr_text and ocr_items and scout_authors:
            roi_text = self._build_roi_text(image_path, ocr_items, scout_authors)
            if roi_text:
                ocr_text = roi_text

        # 第二步：用 DeepSeek 文本模型从 OCR 文本中提取作者信息
        print(f"[Vision] 📝 OCR 识别的文本长度: {len(ocr_text)} 字符")
        
        authors = self._parse_authors_from_text(
            ocr_text,
            doi,
            scout_authors=scout_authors,
            meta_institutions=meta_institutions,
        )
        
        return {
            "text": ocr_text[:500] + "..." if len(ocr_text) > 500 else ocr_text,
            "image_path": image_path,
            "authors": authors
        }
    
    def _extract_text_by_ocr(self, image_path):
        """
        使用本地 PaddleOCR（优先）或 DeepSeek API（备选）识别截图中的文本
        
        流程：
        1️⃣ 优先用 PaddleOCR（完全免费，本地运行，中英文支持好）
        2️⃣ 如果 PaddleOCR 失败，降级到 DeepSeek API
        3️⃣ 都失败就返回 None
        
        返回: 识别的纯文本或 None
        """
        # 方案 1️⃣：优先使用本地 PaddleOCR（最稳定）
        print("[Vision] 📝 尝试本地 PaddleOCR...")
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
            result = ocr.predict(str(image_path))  # 改用 predict() 方法（新版本）
            
            # 新版本 PaddleOCR 返回列表，第一个元素是 OCRResult 对象（字典结构）
            if result and len(result) > 0:
                ocr_result = result[0]
                
                # OCRResult 是字典，包含 rec_texts（文字列表）和 rec_scores（置信度列表）
                if 'rec_texts' in ocr_result:
                    rec_texts = ocr_result['rec_texts']
                    rec_scores = ocr_result.get('rec_scores', [])
                    
                    # 构建文字列表（只保留置信度 > 0.3 的文字）
                    text_lines = []
                    for text, score in zip(rec_texts, rec_scores):
                        if isinstance(score, (int, float)) and score > 0.3:
                            if text and text.strip():
                                text_lines.append(text)
                    
                    if text_lines:
                        ocr_text = "\n".join(text_lines)
                        print(f"[Vision] ✅ PaddleOCR 成功！识别 {len(text_lines)} 行文字")
                        return ocr_text
                
                print("[Vision] ⚠️ PaddleOCR 没有识别到文字")
                return None
            
            print("[Vision] ⚠️ PaddleOCR 返回结果为空")
            return None
        
        except ImportError:
            print("[Vision] ⚠️ PaddleOCR 未安装，尝试降级到 DeepSeek API...")
        except Exception as e:
            print(f"[Vision] ⚠️ PaddleOCR 错误: {e}，尝试降级到 DeepSeek API...")
        
        # 方案 2️⃣：降级到 DeepSeek API
        print("[Vision] 📡 调用 DeepSeek API 作为备选...")
        ocr_text = self._call_deepseek_ocr(image_path)
        
        if ocr_text:
            print(f"[Vision] ✅ DeepSeek API 成功，提取了 {len(ocr_text)} 字符")
            return ocr_text
        else:
            print(f"[Vision] ❌ 所有 OCR 方案都失败了")
            return None

    def _extract_text_and_boxes_by_ocr(self, image_path: str) -> tuple[Optional[str], List[Dict[str, Any]]]:
        """OCR + BBox 信息（用于 ROI 切片）。失败时返回 (None, [])."""
        print("[Vision] 🧩 尝试 OCR+BBox (ROI)")
        try:
            # 保守执行路径，避免 PIR/oneDNN 报错
            os.environ.setdefault("FLAGS_enable_pir_api", "0")
            os.environ.setdefault("FLAGS_enable_pir_in_executor", "0")
            os.environ.setdefault("FLAGS_use_mkldnn", "0")
            os.environ.setdefault("FLAGS_use_onednn", "0")

            from paddleocr import PaddleOCR  # type: ignore[import-not-found]
            ocr = PaddleOCR(use_textline_orientation=True, lang='ch')
            result = ocr.ocr(str(image_path), cls=True)

            def _is_line_entry(x: Any) -> bool:
                return isinstance(x, (list, tuple)) and len(x) >= 2 and isinstance(x[0], (list, tuple))

            lines = []
            if isinstance(result, list) and result:
                if _is_line_entry(result[0]):
                    lines = result
                elif isinstance(result[0], list) and result[0] and _is_line_entry(result[0][0]):
                    lines = result[0]

            items: List[Dict[str, Any]] = []
            text_lines: List[str] = []
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
                    if text:
                        items.append({"text": text, "score": score, "box": box})
                        if score is None or score > 0.3:
                            text_lines.append(text)
                except Exception:
                    continue

            if text_lines:
                return "\n".join(text_lines), items
        except Exception:
            pass

        return None, []

    def _build_roi_text(
        self,
        image_path: str,
        ocr_items: List[Dict[str, Any]],
        scout_authors: List[Dict[str, Any]],
    ) -> Optional[str]:
        """基于 OCR BBox 切片作者块与单位块，减少噪声。"""
        if not ocr_items or not scout_authors:
            return None

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
            return None

        try:
            from PIL import Image
            img = Image.open(image_path)
            w, h = img.size

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
                p = _crop_to(author_bb, "roi_author")
                if p:
                    t = self._extract_text_by_ocr(p)
                    if t:
                        roi_texts.append(t)

            aff_bb = _union_bbox(aff_boxes)
            if aff_bb:
                p = _crop_to(aff_bb, "roi_aff")
                if p:
                    t = self._extract_text_by_ocr(p)
                    if t:
                        roi_texts.append(t)

            if roi_texts:
                return "\n".join(roi_texts)
        except Exception:
            return None

        return None
    
    def _call_deepseek_ocr(self, image_path):
        """
        调用 DeepSeek 的 OCR 接口从图片中识别文本。
        优先使用远端 OCR API，失败时使用 chat 接口作为备选。
        返回识别的纯文本或 None。
        """
        if not DEEPSEEK_API_KEY:
            print("[Vision] ⚠️  未配置 DeepSeek API KEY")
            return None

        try:
            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')

            headers = {
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            }

            # 先尝试标准 OCR endpoint（如果 DeepSeek 提供）
            ocr_endpoints = [
                f"{DEEPSEEK_BASE_URL}/vision/ocr",
                f"{DEEPSEEK_BASE_URL}/ocr",
                f"{DEEPSEEK_BASE_URL}/v1/ocr"
            ]

            payload = {
                "image": f"data:image/png;base64,{image_data}",
                "language": "auto"
            }

            for url in ocr_endpoints:
                try:
                    resp = requests.post(url, headers=headers, json=payload, timeout=30)
                    if resp.status_code == 200:
                        data = resp.json()
                        # 支持多种返回格式
                        if isinstance(data, dict):
                            if 'text' in data and data['text']:
                                return data['text']
                            if 'ocr_text' in data and data['ocr_text']:
                                return data['ocr_text']
                            if 'lines' in data and isinstance(data['lines'], list):
                                return "\n".join(data['lines'])
                            if 'choices' in data:
                                try:
                                    content = data['choices'][0]['message']['content']
                                    return content
                                except Exception:
                                    pass
                except Exception:
                    continue

            # 若远端 OCR endpoint 都不可用，使用 vision 模型识别文本（次优方案）
            # 尝试两种模型：deepseek-vl（优先）和 deepseek-chat（备选）
            for model_name in ["deepseek-vl", "deepseek-chat"]:
                try:
                    chat_payload = {
                        "model": model_name,
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "请将下面图片中可见的所有文本逐行返回，仅返回纯文本，不要任何额外解释或说明。"
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/png;base64,{image_data}"
                                        }
                                    }
                                ]
                            }
                        ],
                        "max_tokens": 4096,
                        "temperature": 0.0
                    }

                    print(f"[Vision] ℹ️ 使用 {model_name} 模型进行 OCR...")
                    resp = requests.post(
                        f"{DEEPSEEK_BASE_URL}/chat/completions",
                        headers=headers,
                        json=chat_payload,
                        timeout=30
                    )
                    resp.raise_for_status()
                    result = resp.json()
                    
                    if 'choices' in result and result['choices']:
                        content = result['choices'][0]['message']['content']
                        if isinstance(content, str) and content.strip():
                            print(f"[Vision] ✅ {model_name} OCR 成功")
                            return content
                        elif isinstance(content, dict) and 'text' in content:
                            return content['text']
                except Exception as e:
                    print(f"[Vision] ⚠️ {model_name} 模型失败: {e}")
                    continue
            
            # 所有模型都失败了
            print("[Vision] ❌ 所有 vision 模型都无法识别文本")
            return None

        except Exception as e:
            print(f"[Vision] ❌ DeepSeek OCR 调用错误: {e}")
            return None
    
    def _parse_authors_from_text(
        self,
        ocr_text: str,
        doi: str,
        scout_authors: Optional[List[Dict[str, Any]]] = None,
        meta_institutions: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        使用 DeepSeek 文本模型从 OCR 文本中提取作者信息和排序
        """
        if not DEEPSEEK_API_KEY:
            print("[Vision] ℹ️ 未配置 DeepSeek API KEY，使用规则解析作者/单位")
            authors = self.ocr_rule_parser.parse_authors_rule_based(
                ocr_text,
                doi,
                scout_authors=scout_authors,
                meta_institutions=meta_institutions,
            )
            return self._validate_and_normalize_authors(authors)
        
        try:
            headers = {
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            }
            
            prompt = f"""根据以下论文文本（通过 OCR 识别），请识别所有作者信息，包括名字、所属机构、作者顺序（作者排序）。

OCR 识别的文本：
---
{ocr_text[:2000]}
---

请返回 JSON 格式的结果：
{{
  "authors": [
    {{"name": "作者名称", "affiliation": "所属机构", "position": 1, "is_corresponding": false, "is_co_first": false}},
    ...
  ]
}}

重要提示：
- position 字段必须是作者在论文中出现的顺序（从 1 开始）
- 通讯作者（带 * 或标记为 Corresponding Author）设置 is_corresponding 为 true
- 共同一作（带 # 或标记为 Co-first）设置 is_co_first 为 true
- 只返回有效的 JSON（不要额外文本）"""
            
            payload = {
                "model": "deepseek-chat",  # 用文本模型，不用 VLM
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "response_format": {"type": "json_object"},
                "max_tokens": 2048,
                "temperature": 0.3  # 低温度，更稳定的 JSON 输出
            }
            
            print(f"[Vision] 🤖 调用 DeepSeek 解析作者信息...")
            response = requests.post(
                f"{DEEPSEEK_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            content = result['choices'][0]['message']['content']
            
            # 尝试解析 JSON
            try:
                data = json.loads(content)
                authors = data.get('authors', [])
                # ✅ 添加数据验证和规范化
                authors = self._validate_and_normalize_authors(authors)
                # 方案A：规则优先。若规则提取到角标/单位，则覆盖 LLM 的单位信息。
                authors = self._merge_rule_affiliations(
                    authors,
                    ocr_text,
                    scout_authors=scout_authors,
                    meta_institutions=meta_institutions,
                )
                print(f"[Vision] ✅ 成功识别 {len(authors)} 名作者")
                return authors
            except json.JSONDecodeError:
                print(f"[Vision] ⚠️  返回内容不是有效 JSON: {content[:100]}")
                authors = self.ocr_rule_parser.parse_authors_rule_based(
                    ocr_text,
                    doi,
                    scout_authors=scout_authors,
                    meta_institutions=meta_institutions,
                )
                return self._validate_and_normalize_authors(authors)
        
        except Exception as e:
            print(f"[Vision] ❌ DeepSeek 解析错误: {e}")
            authors = self.ocr_rule_parser.parse_authors_rule_based(
                ocr_text,
                doi,
                scout_authors=scout_authors,
                meta_institutions=meta_institutions,
            )
            return self._validate_and_normalize_authors(authors)

    def _merge_rule_affiliations(
        self,
        llm_authors: List[Dict[str, Any]],
        ocr_text: str,
        scout_authors: Optional[List[Dict[str, Any]]] = None,
        meta_institutions: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Rule-first merge for affiliations.

        If ocr-rule extracted affiliation numbers or affiliations, use them.
        Otherwise keep LLM output.
        """
        if not llm_authors:
            return llm_authors

        rule_authors = self.ocr_rule_parser.parse_authors_rule_based(
            ocr_text,
            doi="",
            scout_authors=scout_authors,
            meta_institutions=meta_institutions,
        )
        rule_authors = self._validate_and_normalize_authors(rule_authors)

        def _name_key(name: str) -> str:
            return "".join(ch for ch in str(name or "").lower() if ch.isalnum())

        def _order(a: Dict[str, Any]) -> int:
            v = a.get("position")
            if isinstance(v, int):
                return v
            v = a.get("order")
            if isinstance(v, int):
                return v
            return -1

        rule_by_name = { _name_key(a.get("name")): a for a in rule_authors if isinstance(a, dict) and a.get("name") }
        rule_by_order = { _order(a): a for a in rule_authors if isinstance(a, dict) and _order(a) > 0 }

        merged: List[Dict[str, Any]] = []
        for la in llm_authors:
            if not isinstance(la, dict):
                continue
            key = _name_key(la.get("name"))
            ra = rule_by_name.get(key) if key else None
            if ra is None:
                o = _order(la)
                if o > 0:
                    ra = rule_by_order.get(o)

            if ra:
                # Only override when rule has signals
                if ra.get("affiliation_numbers"):
                    la["affiliation_numbers"] = ra.get("affiliation_numbers")
                if ra.get("affiliations"):
                    la["affiliations"] = ra.get("affiliations")
                    la["affiliation"] = "; ".join(ra.get("affiliations") or [])
                elif ra.get("affiliation"):
                    la["affiliation"] = ra.get("affiliation")
                if ra.get("markers"):
                    la["markers"] = ra.get("markers")
            merged.append(la)

        return merged
    
    def _get_mock_authors(self, doi):
        """
        返回 fallback 测试数据。
        
        当 OCR 或实际作者提取失败时，返回多样化的测试作者数据。
        这样可以验证系统的匹配逻辑，而不会所有论文都匹配到同一个人。
        
        在实际应用中：
        - 如果论文的作者信息可以正确提取（OCR + LLM），就用真实数据
        - 如果失败，至少可以用这些 fallback 数据来测试系统功能
        """
        # 根据 DOI 的哈希值来"伪随机"选择 fallback 数据
        # 这样即使不备 OCR，多个论文也会有不同的 mock 作者
        
        import hashlib
        doi_hash = int(hashlib.md5(doi.encode()).hexdigest(), 16)
        choice = doi_hash % 3  # 循环选择 3 种 fallback 数据
        
        fallback_datasets = [
            # 选项 1: 你自己的信息 - 多部门
            {
                "text": "[Fallback 1] 你的论文作者",
                "authors": [
                    {
                        "name": "刘泽萍",
                        "affiliation": "West China School of Medicine, Sichuan University, Chengdu, China",
                        "position": 1,
                        "is_corresponding": False,
                        "is_co_first": False
                    }
                ]
            },
            # 选项 2: 其他机构的教师（测试多部门匹配）
            {
                "text": "[Fallback 2] 其他论文作者 - 计算机学院",
                "authors": [
                    {
                        "name": "刘泽萍",
                        "affiliation": "College of Computer Science, Sichuan University, Chengdu, China",
                        "position": 1,
                        "is_corresponding": True,
                        "is_co_first": False
                    }
                ]
            },
            # 选项 3: 完全不同的作者（测试无匹配情况）
            {
                "text": "[Fallback 3] 未知作者论文",
                "authors": [
                    {
                        "name": "李明",
                        "affiliation": "北京大学计算机学院",
                        "position": 1,
                        "is_corresponding": False,
                        "is_co_first": False
                    },
                    {
                        "name": "王涛",
                        "affiliation": "清华大学",
                        "position": 2,
                        "is_corresponding": True,
                        "is_co_first": False
                    }
                ]
            }
        ]
        
        selected = fallback_datasets[choice]
        
        return {
            "text": selected["text"],
            "image_path": None,
            "authors": selected["authors"]
        }