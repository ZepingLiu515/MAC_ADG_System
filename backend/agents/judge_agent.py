"""
【Judge Agent V2.0 - 完整身份匹配算法】

职责：
1. 身份融合：匹配论文作者 vs 学校教师名单
2. 冲突消解：Crossref vs Vision 数据融合
3. 权益认定：识别通讯作者、共同一作
4. 数据持久化：保存到数据库

核心算法：贝叶斯模糊匹配 + 规则融合
"""

import json
import logging
import os
import re
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import Faculty, Paper, PaperAuthor
from config import SCHOOL_AFFILIATION_KEYWORDS
from ..utils.ocr_rule_parser import OcrRuleParser
from ..utils.rag_memory import build_layout_fingerprint, retrieve_memory_hints

logger = logging.getLogger(__name__)


class JudgeAgent:
    """
    仲裁智能体 - 身份匹配与权益认定
    
    算法：
    1. 名字相似度匹配（Fuzzy String Matching / Sequence Matching）
    2. 单位信息融合（处理翻译和同义词）
    3. 权益标记识别（通讯作者、共同一作）
    4. 置信度评估（贝叶斯论证）
    """
    
    def __init__(self):
        self.name_threshold = 0.7  # 名字相似度阈值
        self.affiliation_threshold = 0.6  # 单位相似度阈值
        self.match_threshold = 0.75  # 综合匹配阈值
        self.ocr_rule_parser = OcrRuleParser()

    def _extract_affiliation_map(self, vision_data: dict) -> Dict[int, str]:
        if not isinstance(vision_data, dict):
            return {}

        raw_map = vision_data.get("affiliation_map") or vision_data.get("affiliation_dict")
        if isinstance(raw_map, dict):
            cleaned: Dict[int, str] = {}
            for key, val in raw_map.items():
                try:
                    num = int(key)
                except Exception:
                    continue
                text = str(val or "").strip()
                if text:
                    cleaned[num] = text
            if cleaned:
                return cleaned

        text = vision_data.get("full_text") or vision_data.get("ocr_text") or vision_data.get("text") or ""
        if text:
            return self.ocr_rule_parser.extract_affiliation_map(text)
        return {}

    def _enforce_affiliation_mapping(self, authors: List[dict], vision_data: dict) -> None:
        """Enforce strict affiliation mapping for authors with markers."""
        if not authors:
            return

        aff_map = self._extract_affiliation_map(vision_data)
        strict = str(os.getenv("JUDGE_STRICT_AFFILIATION_MAPPING", "1")).strip().lower() in {
            "1",
            "true",
            "yes",
            "y",
        }

        for author in authors:
            if not isinstance(author, dict):
                continue
            nums = author.get("affiliation_numbers")
            if not isinstance(nums, list) or not nums:
                continue

            norm_nums: List[int] = []
            for n in nums:
                try:
                    num = int(n)
                except Exception:
                    continue
                if num > 0:
                    norm_nums.append(num)

            if not norm_nums:
                continue

            mapped: List[str] = []
            missing = 0
            for num in norm_nums:
                aff = aff_map.get(num)
                if aff:
                    mapped.append(aff)
                else:
                    missing += 1

            if mapped:
                author["affiliations"] = mapped
                author["affiliation"] = "; ".join(mapped)
                author["affiliation_map_status"] = "partial" if missing else "mapped"
            else:
                author["affiliation_map_status"] = "missing"
                if strict:
                    author["affiliations"] = []
                    author["affiliation"] = "Unknown"
                    logger.debug("[Judge] Missing affiliation map for %s", author.get("name"))
    
    def adjudicate(self, scout_data: dict, vision_data: dict = None) -> Optional[dict]:
        """
        主入口 - 完整的身份匹配流程【优化版】
        
        【优化策略】快速、准确、无浪费：
        1. 先用 Crossref 数据检查单位 ← 快速筛选
        2. IF 有学校单位 → 调用 Vision 提取权益标记 ✅
        3. ELSE 无学校单位 → 直接跳过，不调用 Vision ⏭️（省略无谓步骤）
        4. IF Crossref 为空 → 用 Vision 识别
        
        输入：
        - scout_data: 来自 Crossref 的元数据 + 作者列表
        - vision_data: 来自 Vision Agent 的截图分析结果（可选）
        
        输出：
        - 匹配结果已保存到数据库（仅本校相关的论文）
        """
        doi = scout_data.get("doi")
        title = scout_data.get("title")
        journal = scout_data.get("journal")
        pub_date = scout_data.get("publish_date")
        
        logger.info("[Judge] Processing DOI: %s", doi)
        if isinstance(title, str):
            logger.info("[Judge] Title: %s", title[:60])
        
        db: Session = next(get_db())
        
        try:
            # 1️⃣ 获取 Crossref 数据
            crossref_authors = scout_data.get("authors", [])
            logger.info("[Judge] Crossref authors: %s", len(crossref_authors))
            
            # 2️⃣【快速筛选】检查是否有学校单位
            school_kws = self._get_school_affiliation_keywords(db)
            has_school_aff = self._has_school_affiliation(crossref_authors, school_kws)

            def _affiliations_mostly_unknown(authors: List[dict]) -> bool:
                if not authors:
                    return True
                known = 0
                for a in authors:
                    if not isinstance(a, dict):
                        continue
                    aff = str(a.get('affiliation') or '').strip().lower()
                    if aff and aff != 'unknown':
                        known += 1
                # 80% 以上 unknown 视为“单位信息缺失”，不要用它做强跳过
                return known / max(len(authors), 1) < 0.2
            
            # 【优化决策】
            vision_authors = []
            if crossref_authors and len(crossref_authors) > 0:
                # Crossref 有数据
                if has_school_aff:
                    # ✅ 有学校单位 → 调用 Vision 提取权益标记
                    logger.info("[Judge] School affiliation detected, using vision markers")
                    vision_authors = vision_data.get("authors", []) if vision_data else []
                    logger.info("[Judge] Vision authors: %s", len(vision_authors))
                else:
                    # ⏭️ 无学校单位：
                    # - 若单位信息本身大量缺失（Unknown），不能据此强跳过；允许使用 Vision/hover 来补单位与权益线索。
                    # - 若单位信息明确但不相关，才跳过。
                    if vision_data and isinstance(vision_data, dict):
                        vision_authors = vision_data.get("authors", []) or []

                    # 如果 Vision/hover 已经给出了明确单位信息（尤其是按角标映射的多单位），不要因为 Crossref/OpenAlex
                    # 没命中“本校单位”而直接跳过；先进入后续匹配/落库（由匹配结果决定是否有本校作者）。
                    has_any_aff_from_vision = False
                    try:
                        for a in vision_authors:
                            if not isinstance(a, dict):
                                continue
                            aff = str(a.get('affiliation') or '').strip().lower()
                            if aff and aff != 'unknown':
                                has_any_aff_from_vision = True
                                break
                    except Exception as exc:
                        has_any_aff_from_vision = False
                        logger.debug("[Judge] Vision affiliation scan failed: %s", exc)

                    if (has_any_aff_from_vision and vision_authors) or (_affiliations_mostly_unknown(crossref_authors) and vision_authors):
                        logger.info("[Judge] Using vision/hover affiliations to avoid false skip")
                    else:
                        # 现实情况：Crossref 往往不给单位，且“学校单位”可能只有英文/缩写，
                        # 用 departments 做快速筛选容易误伤。这里不再提前跳过，交给后续
                        # “姓名+单位”匹配来决定是否有本校作者。
                        logger.info("[Judge] No school affiliation detected; continue matching")
            else:
                # Crossref 为空 → 用 Vision 识别
                logger.info("[Judge] Crossref empty, using vision authors")
                vision_authors = vision_data.get("authors", []) if vision_data else []
                logger.info("[Judge] Vision authors: %s", len(vision_authors))

            # 严格角标映射：要求先有 affiliation_map，再由 Python 映射到作者
            if vision_authors and vision_data:
                self._enforce_affiliation_mapping(vision_authors, vision_data)
            
            # 如果最终没有任何作者数据，跳过
            if not crossref_authors and not vision_authors:
                logger.warning("[Judge] No authors detected, skipping DOI: %s", doi)
                return {"status": "skipped", "doi": doi, "reason": "无作者数据"}
            
            # 3️⃣ 检查或创建论文记录
            paper = self._get_or_create_paper(db, doi, title, journal, pub_date)

            # Force/重复处理时：避免作者表累计重复数据，先清理旧记录
            try:
                db.query(PaperAuthor).filter(PaperAuthor.paper_doi == doi).delete(synchronize_session=False)
                db.flush()
            except Exception as exc:
                logger.debug("[Judge] Failed to clear PaperAuthor for %s: %s", doi, exc)
            
            # 4️⃣ 融合作者数据
            merged_authors = self._merge_authors(crossref_authors, vision_authors)

            # 4.5️⃣ 轻量 RAG 记忆检索（仅提供提示信号，不改变主逻辑）
            memory_tokens = build_layout_fingerprint(vision_data or {})
            memory_hints = retrieve_memory_hints(db, memory_tokens)
            memory_hint_count = len(memory_hints)
            memory_top_score = memory_hints[0].get("score", 0.0) if memory_hints else 0.0
            if memory_hints:
                logger.info(
                    "[Judge] Memory hints: %s (top score=%.2f)",
                    memory_hint_count,
                    memory_top_score,
                )
            
            # 5️⃣ 获取本校教师名单
            all_faculty = db.query(Faculty).all()
            logger.info("[Judge] Faculty count: %s", len(all_faculty))
            faculty_loaded = len(all_faculty) > 0

            # ✅ 测试友好：尚未导入教师/单位库时，不应直接 SKIPPED。
            # 该模式会把作者落库并标记 NEEDS_REVIEW，便于你验证“识别作者+单位+通讯/共一”的主链路。
            if not faculty_loaded:
                logger.info("[Judge] Faculty table empty; entering test mode")
            
            # 6️⃣ 对每个作者进行身份匹配
            logger.info("[Judge] Running identity matching")
            matched_count = 0
            saved_count = 0
            needs_review_count = 0

            def _name_key(name: str) -> str:
                if not name:
                    return ""
                return "".join(ch for ch in str(name).lower() if ch.isalnum())

            crossref_keys = {_name_key(a.get("name")) for a in crossref_authors if isinstance(a, dict)}
            vision_keys = {_name_key(a.get("name")) for a in vision_authors if isinstance(a, dict)}

            def _has_structured_aff(author: dict) -> bool:
                if not isinstance(author, dict):
                    return False
                affs = author.get("affiliations")
                if isinstance(affs, list) and any(str(x).strip() for x in affs):
                    return True
                src = str(author.get("source") or "").lower().strip()
                return src in {"meta-guided", "hover", "meta:citation_author", "ocr-rule", "ocr"}

            def _evidence_for(author: dict) -> tuple[float, List[str]]:
                if not isinstance(author, dict):
                    return 0.0, []
                sources: List[str] = []
                score = 0.0
                key = _name_key(author.get("name"))
                if key and key in crossref_keys:
                    score += 0.4
                    sources.append("crossref")
                if key and key in vision_keys:
                    score += 0.4
                    sources.append("vision")
                if _has_structured_aff(author):
                    score += 0.1
                    sources.append("structured_aff")
                has_mark = bool(author.get("has_mail_icon")) or bool(author.get("emails"))
                has_mark = has_mark or ("*" in str(author.get("markers") or ""))
                if has_mark:
                    score += 0.1
                    sources.append("correspondence_marker")
                return min(score, 1.0), sources

            def _author_hits_school_aff(author: dict) -> bool:
                """作者单位是否命中本校单位/部门关键词。

                规则：命中 Faculty.departments / Faculty.department 的任意字符串（包含/反包含），
                或命中常见中英文关键词组合。
                """
                if not isinstance(author, dict):
                    return False
                if not school_kws:
                    return False

                aff_candidates: List[str] = []
                aff_main = author.get('affiliation')
                if isinstance(aff_main, str) and aff_main.strip():
                    aff_candidates.append(aff_main)
                affs = author.get('affiliations')
                if isinstance(affs, list):
                    for a in affs:
                        if isinstance(a, str) and a.strip():
                            aff_candidates.append(a)

                # 去重/过滤 Unknown
                uniq: List[str] = []
                seen = set()
                for a in aff_candidates:
                    key = str(a).strip().lower()
                    if not key or key == 'unknown':
                        continue
                    if key in seen:
                        continue
                    seen.add(key)
                    uniq.append(str(a).strip())

                if not uniq:
                    return False

                keywords_map = {
                    '大学': ['university', 'univ', 'uni'],
                    '学院': ['school', 'college'],
                    '系': ['department', 'dept', 'division'],
                    '所': ['institute', 'inst', 'research'],
                    '中心': ['center', 'centre'],
                }

                for aff_raw in uniq:
                    aff = aff_raw.lower().strip()
                    if not aff:
                        continue

                    for kw in school_kws:
                        if kw in aff or aff in kw:
                            return True

                    for cn_keyword, en_keywords in keywords_map.items():
                        if cn_keyword in aff:
                            for en_keyword in en_keywords:
                                if en_keyword in aff:
                                    return True

                return False
            
            def _author_aff_is_unknown(author: dict) -> bool:
                if not isinstance(author, dict):
                    return True
                aff_candidates: List[str] = []
                aff_main = author.get('affiliation')
                if isinstance(aff_main, str) and aff_main.strip():
                    aff_candidates.append(aff_main)
                affs = author.get('affiliations')
                if isinstance(affs, list):
                    for a in affs:
                        if isinstance(a, str) and a.strip():
                            aff_candidates.append(a)
                for a in aff_candidates:
                    s = str(a).strip().lower()
                    if s and s != 'unknown':
                        return False
                return True

            for idx, author in enumerate(merged_authors, 1):
                hits_school_aff = _author_hits_school_aff(author)
                aff_unknown = _author_aff_is_unknown(author)

                evidence_score, evidence_sources = _evidence_for(author)

                matched_faculty = None
                confidence = 0.0

                # ✅ 先单位再姓名：
                # - 有教师库：只有“单位命中”或“单位缺失（unknown）”才进入姓名匹配（避免无谓匹配、也符合你的验证逻辑）
                # - 无教师库：不做姓名匹配（直接落库供测试）
                if faculty_loaded and (hits_school_aff or aff_unknown):
                    match_result = self._match_author_to_faculty(author, all_faculty, db)
                    if match_result:
                        matched_faculty, confidence = match_result
                        matched_count += 1

                # 打印
                if matched_faculty:
                    logger.info(
                        "[Judge] %s. %s matched %s (%s) confidence=%.2f",
                        idx,
                        author.get("name"),
                        matched_faculty.name_zh,
                        matched_faculty.department,
                        confidence,
                    )
                else:
                    logger.info("[Judge] %s. %s unmatched", idx, author.get("name"))

                # ✅ 落库决策：
                # - 有教师库：只落“匹配到本校教师 / 或单位命中本校关键词”的作者
                # - 无教师库：全部落库（测试模式）
                if faculty_loaded:
                    if (matched_faculty is None) and (not hits_school_aff):
                        logger.info("[Judge] Skipped non-school author: %s", author.get("name"))
                        continue

                paper_author = PaperAuthor(
                    paper_doi=doi,
                    raw_name=author.get('name') or author.get('raw_name') or 'Unknown',
                    raw_affiliation=(author.get('affiliation') or 'Unknown'),
                    raw_affiliations=author.get('affiliations') if isinstance(author.get('affiliations'), list) else None,
                    rank=idx,
                    is_corresponding=author.get('is_corresponding', False),
                    is_co_first=author.get('is_co_first', False),
                    matched_faculty_id=(matched_faculty.id if matched_faculty else None),
                    confidence_score=(int(confidence * 100) if matched_faculty else 0),
                    match_signals={
                        "relevance": (
                            "matched_faculty" if matched_faculty else (
                                "school_affiliation_hit" if hits_school_aff else "no_faculty_loaded"
                            )
                        ),
                        "source": author.get("source"),
                        "evidence_score": evidence_score,
                        "evidence_sources": evidence_sources,
                        "memory_hint_count": memory_hint_count,
                        "memory_top_score": memory_top_score,
                    },
                )
                db.add(paper_author)
                saved_count += 1

                if matched_faculty is None:
                    # 无法精确匹配到教师：要么是单位命中但名单缺失/不全，要么是测试模式
                    needs_review_count += 1
            
            # 7️⃣ 更新论文状态
            if saved_count <= 0:
                paper.status = "SKIPPED"
                db.commit()
                logger.info("[Judge] Skipped DOI %s; no school-related authors", doi)
                return {
                    "status": "skipped",
                    "doi": doi,
                    "reason": "无本校相关作者",
                    "total_authors": len(merged_authors),
                    "saved_authors": 0,
                    "matched_authors": 0,
                }

            # 没有教师库时：统一进入 NEEDS_REVIEW，避免误标 COMPLETED
            if not faculty_loaded:
                paper.status = "NEEDS_REVIEW"
            else:
                paper.status = "NEEDS_REVIEW" if needs_review_count > 0 else "COMPLETED"
            db.commit()

            logger.info(
                "[Judge] Completed DOI %s: saved=%s matched=%s/%s",
                doi,
                saved_count,
                matched_count,
                len(merged_authors),
            )

            return {
                "status": "needs_review" if needs_review_count > 0 else "success",
                "doi": doi,
                "total_authors": len(merged_authors),
                "saved_authors": saved_count,
                "matched_authors": matched_count,
                "needs_review_authors": needs_review_count,
            }
        
        except Exception as e:
            logger.exception("[Judge] Failed to process DOI %s: %s", doi, e)
            db.rollback()
            return {"status": "error", "doi": doi, "reason": str(e)}
        
        finally:
            db.close()
    
    def _get_or_create_paper(self, db: Session, doi: str, title: str, 
                            journal: str, pub_date: str) -> Paper:
        """获取或创建论文记录"""
        existing = db.query(Paper).filter(Paper.doi == doi).first()
        
        if existing:
            logger.info("[Judge] Paper already exists: %s", doi)
            return existing
        
        paper = Paper(
            doi=doi,
            title=title,
            journal=journal,
            publish_date=pub_date,
            status="PROCESSING"
        )
        db.add(paper)
        db.flush()
        
        logger.info("[Judge] Created new paper record: %s", doi)
        return paper
    
    def _get_school_departments(self, db: Session) -> List[str]:
        """
        获取学校所有部门名称列表（用于快速筛选）
        
        返回：部门名称的小写列表，用于快速查询
        """
        departments = set()
        
        all_faculty = db.query(Faculty).all()

        def _add_dept_variant(v: str) -> None:
            if not v:
                return
            s = str(v).strip().lower()
            if not s:
                return
            departments.add(s)
            # 拆分片段：很多 affiliations 是 "Dept, School, University"，拆分后更容易命中
            for seg in re.split(r"[,;\/\|]", s):
                seg = seg.strip()
                if seg and len(seg) >= 3:
                    departments.add(seg)

        for faculty in all_faculty:
            if faculty.department:
                _add_dept_variant(faculty.department)

            if faculty.departments:
                try:
                    dept_list = json.loads(faculty.departments) if isinstance(faculty.departments, str) else faculty.departments
                    for dept in dept_list:
                        if dept:
                            _add_dept_variant(dept)
                except Exception as exc:
                    logger.debug("[Judge] Failed to parse departments for %s: %s", faculty.employee_id, exc)
        
        return list(departments)
    
    def _get_school_affiliation_keywords(self, db: Session) -> List[str]:
        """返回用于判断“本校相关单位”的关键词集合。

        组成：
        - Faculty 表中出现过的 department/departments（含拆分片段）
        - 配置的 SCHOOL_AFFILIATION_KEYWORDS（用于学校名/英文名等）
        """
        kws = set()
        for x in self._get_school_departments(db):
            if x:
                kws.add(str(x).strip().lower())
        if isinstance(SCHOOL_AFFILIATION_KEYWORDS, list):
            for x in SCHOOL_AFFILIATION_KEYWORDS:
                if x:
                    kws.add(str(x).strip().lower())
        return [k for k in kws if k]

    def _has_school_affiliation(self, crossref_authors: List[dict], school_kws: List[str]) -> bool:
        """
        【快速筛选】检查 Crossref 作者中是否有学校单位
        
        原理：
        - 如果Crossref作者都不是学校单位 → 这篇论文与本校无关 → 跳过
        - 如果至少有一个作者是学校单位 → 调用Vision提取权益标记
        
        返回：True 如果有学校单位，False 如果无相关单位
        """
        if not crossref_authors or not school_kws:
            return False
        
        for author in crossref_authors:
            aff = author.get('affiliation', '').lower().strip()
            
            if not aff:
                continue
            
            for kw in school_kws:
                if kw in aff or aff in kw:
                    logger.info("[Judge] School affiliation hit: %s @ %s", author.get("name"), aff)
                    return True
        
        return False
    
    def _merge_authors(self, crossref_authors: List[dict], 
                      vision_authors: List[dict]) -> List[dict]:
        """
        融合来自两个来源的作者数据
        
        策略：Crossref 优先 + Vision 补充
        
        原因：
        1. Crossref 是官方结构化数据，更完整可靠 ✅
        2. Vision 来自截图，可能不完整，但包含权益标记 📝
        3. 所以：用 Crossref 作者列表 + 从 Vision 中提取权益标记
        
        流程：
        1️⃣ 使用 Crossref 作为主要作者列表
        2️⃣ 从 Vision 中提取权益标记（通讯作者、共同一作）
        3️⃣ 将权益标记并入 Crossref 数据
        4️⃣ 如果 Crossref 为空才回退到 Vision
        """
        
        def _name_key(name: str) -> str:
            if not name:
                return ""
            return "".join(ch for ch in str(name).lower() if ch.isalnum())

        def _author_order(a: dict) -> Optional[int]:
            if not isinstance(a, dict):
                return None
            v = a.get('order')
            if isinstance(v, int):
                return v
            v = a.get('position')
            if isinstance(v, int):
                return v
            return None

        def _is_unknown_aff(aff: str) -> bool:
            if aff is None:
                return True
            s = str(aff).strip()
            return (not s) or (s.lower() == 'unknown')

        def _is_structured_aff_source(a: dict) -> bool:
            """Vision/hover 的单位若来自页面结构（角标/元信息），可信度高于 OpenAlex 历史单位。"""
            if not isinstance(a, dict):
                return False
            src = str(a.get('source') or '').strip().lower()
            return src in {'meta-guided', 'hover', 'meta:citation_author', 'ocr-rule', 'ocr'}

        # 情况 1：Crossref 有数据 → 以 Crossref 为主
        if crossref_authors and len(crossref_authors) > 0:
            logger.info("[Judge] Using Crossref authors (%s)", len(crossref_authors))
            
            # 确保所有作者都有权益字段
            for author in crossref_authors:
                if 'is_corresponding' not in author:
                    author['is_corresponding'] = False
                if 'is_co_first' not in author:
                    author['is_co_first'] = False
            
            # 情况 1a：也有 Vision 数据 → 从 Vision 中提取权益标记并合并
            if vision_authors and len(vision_authors) > 0:
                logger.info("[Judge] Merging vision markers (%s)", len(vision_authors))
                
                # 建立 Vision 作者的查询表（按名字归一化 + 按顺序）
                vision_map = {}
                vision_by_order = {}
                for va in vision_authors:
                    if not isinstance(va, dict):
                        continue
                    vname = str(va.get('name') or '').strip()
                    if vname:
                        vision_map[_name_key(vname)] = va
                    vorder = _author_order(va)
                    if isinstance(vorder, int):
                        vision_by_order[vorder] = va
                
                # 为 Crossref 作者补充权益标记
                merged_count = 0
                for author in crossref_authors:
                    author_name = str(author.get('name') or '').strip()
                    author_key = _name_key(author_name)
                    vision_author = None
                    matched_vision = False

                    if author_key and author_key in vision_map:
                        vision_author = vision_map[author_key]
                    else:
                        order = _author_order(author)
                        if isinstance(order, int) and order in vision_by_order:
                            vision_author = vision_by_order[order]

                    if vision_author:
                        matched_vision = True
                        # 从 Vision/hover 合并权益标记（用 OR，避免覆盖 OpenAlex 已给出的 True）
                        author['is_corresponding'] = bool(author.get('is_corresponding')) or bool(vision_author.get('is_corresponding'))
                        author['is_co_first'] = bool(author.get('is_co_first')) or bool(vision_author.get('is_co_first'))

                        # 合并单位信息：若 Crossref/OpenAlex 仍缺失单位，用 Vision/hover 补全
                        cross_aff = author.get('affiliation')
                        vision_aff = vision_author.get('affiliation')

                        vision_affs = vision_author.get('affiliations')
                        has_structured_affs = isinstance(vision_affs, list) and len(vision_affs) > 0

                        if has_structured_affs and _is_structured_aff_source(vision_author):
                            # 结构化单位（角标映射）优先，覆盖 OpenAlex 的“历史多单位”
                            author['affiliations'] = vision_affs
                            author['affiliation'] = '; '.join([str(x).strip() for x in vision_affs if str(x).strip()])
                        else:
                            # 否则：仅在 Unknown 时补全
                            if _is_unknown_aff(cross_aff) and (not _is_unknown_aff(vision_aff)):
                                author['affiliation'] = str(vision_aff).strip()
                            if (not author.get('affiliations')) and isinstance(vision_affs, list):
                                author['affiliations'] = vision_affs

                        # 合并“证据字段”（若存在）供调试/后续决策
                        for k in ['emails', 'has_mail_icon', 'markers', 'source']:
                            if k in vision_author and k not in author:
                                author[k] = vision_author.get(k)

                        # 如果 Vision 明确给了通讯标记，标注来源（强于 openalex）
                        if bool(vision_author.get('is_corresponding')):
                            if author.get('corresponding_source') in (None, '', 'openalex'):
                                author['corresponding_source'] = vision_author.get('corresponding_source') or 'vision'

                        # 若通讯标记仅来自 OpenAlex，且 Vision 对齐作者并未给出通讯线索，则降级该弱证据
                        if author.get('corresponding_source') == 'openalex' and matched_vision:
                            has_strong_hover = bool(author.get('has_mail_icon')) or bool(author.get('emails')) or ('*' in str(author.get('markers') or ''))
                            if not has_strong_hover and not bool(vision_author.get('is_corresponding')):
                                author['is_corresponding'] = False
                        merged_count += 1
                
                logger.info("[Judge] Merged %s author markers", merged_count)
            
            return crossref_authors
        
        # 情况 2：Crossref 为空 → 回退到 Vision
        if vision_authors and len(vision_authors) > 0:
            logger.info("[Judge] Crossref empty, using vision authors (%s)", len(vision_authors))
            
            # 确保 Vision 作者也有权益字段
            for author in vision_authors:
                if 'is_corresponding' not in author:
                    author['is_corresponding'] = False
                if 'is_co_first' not in author:
                    author['is_co_first'] = False
            
            return vision_authors
        
        # 情况 3：都没有数据
        logger.warning("[Judge] No authors from Crossref or Vision")
        return []
    
    def _match_author_to_faculty(
        self, author: dict, faculty_list: List[Faculty], db: Session
    ) -> Optional[Tuple[Faculty, float]]:
        """
        匹配单个作者到教师
        
        返回：(matched_faculty, confidence_score) 或 None
        """
        author_name = author.get('name', '').strip()
        author_aff = author.get('affiliation', '').strip()
        
        if not author_name:
            return None
        
        best_match = None
        best_score = 0.0
        
        for faculty in faculty_list:
            # 计算名字相似度
            name_score = self._name_similarity(author_name, faculty)
            
            if name_score < self.name_threshold:
                continue
            
            # 计算单位相似度
            aff_score = self._affiliation_similarity(author_aff, faculty)
            
            # 综合得分（名字权重 0.7，单位权重 0.3）
            total_score = name_score * 0.7 + aff_score * 0.3
            
            if total_score > best_score:
                best_score = total_score
                best_match = faculty
        
        # 只在达到置信度阈值时返回匹配
        if best_score >= self.match_threshold:
            return (best_match, best_score)
        
        return None
    
    def _name_similarity(self, paper_name: str, faculty: Faculty) -> float:
        """
        计算论文作者名与教师名的相似度
        
        考虑因素：
        1. 完整名字匹配
        2. 中文名匹配
        3. 英文名变体匹配（缩写等）
        """
        paper_name_lower = paper_name.lower().strip()
        
        # 候选名字列表
        candidates = []
        
        # 中文名
        if faculty.name_zh:
            candidates.append(faculty.name_zh.lower())
        
        # 英文名变体
        name_en_list = getattr(faculty, "name_en_list", None)
        if isinstance(name_en_list, list):
            candidates.extend([str(n).lower() for n in name_en_list if n])
        elif isinstance(name_en_list, str) and name_en_list.strip():
            try:
                en_names = json.loads(name_en_list)
                candidates.extend([str(n).lower() for n in en_names if n])
            except Exception as exc:
                logger.debug("[Judge] Failed to parse name_en_list for %s: %s", faculty.employee_id, exc)

        # Backward compatibility for legacy field name
        name_en_json = getattr(faculty, "name_en_json", None)
        if isinstance(name_en_json, str) and name_en_json.strip():
            try:
                en_names = json.loads(name_en_json)
                candidates.extend([str(n).lower() for n in en_names if n])
            except Exception as exc:
                logger.debug("[Judge] Failed to parse name_en_json for %s: %s", faculty.employee_id, exc)
        
        if not candidates:
            return 0.0
        
        # 计算最高相似度
        best_score = 0.0
        
        for candidate in candidates:
            # 完全匹配
            if paper_name_lower == candidate:
                return 1.0
            
            # 包含匹配
            if paper_name_lower in candidate or candidate in paper_name_lower:
                best_score = max(best_score, 0.9)
                continue
            
            # 序列匹配（处理拼写变体）
            score = SequenceMatcher(None, paper_name_lower, candidate).ratio()
            best_score = max(best_score, score)
        
        return best_score
    
    def _affiliation_similarity(self, paper_aff: str, faculty: Faculty) -> float:
        """
        计算论文作者单位与教师部门的相似度
        
        考虑因素：
        1. 部门名称匹配
        2. 关键词重叠
        3. 同义词匹配
        """
        if not paper_aff or not paper_aff.strip():
            # 如果论文没有单位信息，给予中等置信度
            return 0.5
        
        paper_aff_lower = paper_aff.lower()
        
        # 获取教师的部门列表
        depts = []
        if faculty.department:
            depts.append(faculty.department.lower())
        
        if faculty.departments:
            try:
                dept_list = json.loads(faculty.departments)
                depts.extend([d.lower() for d in dept_list if d])
            except Exception as exc:
                logger.debug("[Judge] Failed to parse departments for %s: %s", faculty.employee_id, exc)
        
        if not depts:
            return 0.5
        
        best_score = 0.0
        
        for dept in depts:
            # 完全匹配
            if paper_aff_lower == dept:
                return 1.0
            
            # 包含匹配
            if dept in paper_aff_lower or paper_aff_lower in dept:
                best_score = max(best_score, 0.9)
                continue
            
            # 关键词匹配
            paper_kws = set(w for w in paper_aff_lower.replace(',', ' ').split() if len(w) > 2)
            dept_kws = set(w for w in dept.replace(',', ' ').split() if len(w) > 2)
            
            if paper_kws and dept_kws:
                overlap = len(paper_kws & dept_kws)
                keyword_score = overlap / max(len(paper_kws), len(dept_kws))
                best_score = max(best_score, keyword_score * 0.8)
        
        return best_score
    
    # 外部 LLM 验证逻辑已移除（本项目不依赖外部 LLM 服务）
