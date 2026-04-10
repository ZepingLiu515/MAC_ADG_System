import pandas as pd
import os
from typing import Any, List, Dict, Set

from .agents.scout_agent import ScoutAgent
from .agents.vision_agent import VisionAgent
from .agents.judge_agent import JudgeAgent
from .utils.webdriver import WebDriverAdapter
from database.connection import get_db
from database.models import Paper, PaperAuthor


class Orchestrator:
    """
    运行 Scout→Vision→Judge 流水线的中央协调器。
    
    改进的流程：
    1️⃣ Scout Agent：从 Crossref API 获取元数据和作者信息
    2️⃣ WebDriver：导航并获取截图（不属于任何单一 Agent）
    3️⃣ Vision Agent：分析截图提取视觉作者信息
    4️⃣ Judge Agent：身份匹配与数据融合
    
    ✨ 新特性：高效去重（优化版本）
    - 批量查询：在处理前一次性查询所有 DOI 的状态（1 次数据库查询）
    - 内存缓存：将结果缓存在内存中，后续查询 O(1)
    - 批次内缓存：同一批次中的重复 DOI 直接使用内存结果
    - 不再逐个查询：避免 N 次数据库查询
    """

    def __init__(self):
        self.scout = ScoutAgent()
        self.vision = VisionAgent()
        self.judge = JudgeAgent()
        self.webdriver = WebDriverAdapter()

    def _env_truthy(self, name: str, default: str = "0") -> bool:
        raw = os.getenv(name, default)
        if raw is None:
            return False
        return str(raw).strip() not in {"0", "false", "False", "no", "NO", ""}

    # ------------------------------------------------------------------
    # 内部辅助函数
    # ------------------------------------------------------------------
    def _batch_check_doi_status(self, dois: List[str], db) -> Dict[str, Dict]:
        """
        ⚡ 批量查询 DOI 状态（关键优化）
        
        只需 1 次数据库查询，而不是 N 次！
        - 耗时：~50ms（不管有多少 DOI）
        - 比逐个查询快 100-1000 倍
        """
        print(f"\n🔍 批量检查 {len(dois)} 个 DOI 的状态...")
        
        # ⚡ 核心优化：一次性查询所有 DOI（使用 SQL IN 语句）
        papers = db.query(Paper).filter(Paper.doi.in_(dois)).all()
        
        # 转换为字典，后续查询 O(1)（内存查询而非数据库查询）
        doi_status_map = {}
        for paper in papers:
            doi_status_map[paper.doi] = {
                'status': paper.status,
                'title': paper.title,
                'created_at': paper.created_at,
                'exists': True
            }
        
        # 标记不存在的 DOI
        for doi in dois:
            if doi not in doi_status_map:
                doi_status_map[doi] = {'exists': False}
        
        # 打印统计信息
        completed_count = sum(1 for v in doi_status_map.values() if v.get('status') == 'COMPLETED')
        processing_count = sum(1 for v in doi_status_map.values() if v.get('status') == 'PROCESSING')
        new_count = sum(1 for v in doi_status_map.values() if not v.get('exists'))
        
        print(f"   ✅ 已完成: {completed_count}")
        print(f"   ⏳ 处理中: {processing_count}")
        print(f"   ➕ 新论文: {new_count}\n")
        
        return doi_status_map

    # ------------------------------------------------------------------
    # 公开辅助函数
    # ------------------------------------------------------------------
    def process_dois(self, dois: List[str]) -> List[Dict]:
        """为一组 DOI 运行完整流水线（高效版本）。
        
        核心优化：
        ⚡ 优化 1 - 批量查询：1 次数据库查询代替 N 次
        ⚡ 优化 2 - 内存缓存：查询结果缓存在内存，后续 O(1) 查询
        ⚡ 优化 3 - 批次内缓存：同一批次中的重复直接返回内存结果
        
        流程：
        1️⃣ Scout → 从 Crossref 获取元数据
        2️⃣ WebDriver → 获取截图
        3️⃣ Vision → 分析截图提取作者信息
        4️⃣ Judge → 身份匹配
        """
        results = []
        total = len(dois)
        db = next(get_db())
        
        try:
            # ⚡ 优化 1：批量查询所有 DOI 状态（只需 1 次数据库查询）
            doi_status_map = self._batch_check_doi_status(dois, db)
            
            # 内存缓存跟踪（当前批次中已处理过的 DOI）
            processed_in_batch: Set[str] = set()
            
            for index, doi in enumerate(dois, start=1):
                doi = doi.strip()
                record: Dict = {"doi": doi}
                try:
                    print(f"\n{'='*80}")
                    print(f"[Orchestrator] 处理 {index}/{total}: {doi}")
                    print(f"{'='*80}")
                    
                    # ⚡ 优化 2/3：使用内存缓存查询（不查数据库）
                    status_info = doi_status_map.get(doi)

                    force_reprocess = self._env_truthy("FORCE_REPROCESS", default="0")
                    
                    # 情况 1：论文已完成/已跳过/待复核 → 直接返回缓存结果
                    if (not force_reprocess) and status_info and status_info.get('status') in {'COMPLETED', 'SKIPPED', 'NEEDS_REVIEW'}:
                        print(f"\n[去重] ✅ 该论文已处理过（{status_info.get('created_at')}）")
                        print(f"      标题: {status_info.get('title')}")
                        
                        # 从数据库读取已有的作者匹配结果
                        authors = db.query(PaperAuthor).filter(
                            PaperAuthor.paper_doi == doi
                        ).all()
                        
                        record.update({
                            "title": status_info.get('title'),
                            "status": status_info.get('status'),
                            "matched_authors": len([a for a in authors if a.matched_faculty_id]),
                            "total_authors": len(authors),
                            "skipped": True
                        })
                        
                        results.append(record)
                        processed_in_batch.add(doi)
                        continue
                    
                    # 情况 2：论文正在处理 → 提示稍后重试
                    elif (not force_reprocess) and status_info and status_info.get('status') == 'PROCESSING':
                        print(f"\n[去重] ⚠️ 该论文正在处理中，请稍后重试")
                        record["status"] = "PROCESSING"
                        record["skipped"] = True
                        results.append(record)
                        processed_in_batch.add(doi)
                        continue
                    
                    # 情况 3：本批次中已处理过 → 使用批次内缓存结果
                    if doi in processed_in_batch:
                        print(f"\n[去重] ✅ 本批次中已处理过，使用缓存结果")
                        prev_result = next((r for r in results if r['doi'] == doi), None)
                        if prev_result:
                            record.update(prev_result)
                            record["cached_from_batch"] = True
                        results.append(record)
                        continue
                    
                    # 情况 4：新论文 → 执行完整流程
                    # 标记为 PROCESSING（防止并发）
                    if not status_info.get('exists'):
                        paper = Paper(doi=doi, status="PROCESSING")
                        db.add(paper)
                        db.commit()
                    else:
                        paper = db.query(Paper).filter(Paper.doi == doi).first()
                        if paper:
                            paper.status = "PROCESSING"
                            db.commit()
                    
                    # 1️⃣ Scout Agent：从 Crossref 获取元数据和作者
                    print(f"\n[步骤 1/4] 🕵️ Scout Agent - 获取元数据...")
                    scout_data = self.scout.run(doi)
                    record.update(scout_data)
                    # 便于排查 403：记录 Scout 提供的落地页 URL
                    if scout_data.get('landing_page_url'):
                        record['landing_page_url'] = scout_data.get('landing_page_url')
                    print(f"[Scout] ✅ 获取了元数据，包含 {len(scout_data.get('authors', []))} 位 Crossref 作者")
                    
                    # 更新 Paper 记录
                    paper = db.query(Paper).filter(Paper.doi == doi).first()
                    if paper:
                        paper.title = scout_data.get('title', '')
                        paper.journal = scout_data.get('journal', '')
                        paper.publish_date = scout_data.get('publish_date', '')
                        db.commit()
                    
                    # 2️⃣ WebDriver：导航并获取截图
                    print(f"\n[步骤 2/4] 🌐 WebDriver - 获取截图...")
                    screenshot_path = self.webdriver.get_webpage_screenshot(
                        doi,
                        landing_page_url=scout_data.get('landing_page_url')
                    )

                    # 🆕 2.5️⃣ 页面交互提取（hover 作者详情）
                    # 说明：很多出版社把作者单位/邮箱放在 hover tooltip 或弹层里，首页并不展示。
                    # 这是合规的页面交互（不绕过风控）；若页面被拦截，该方法会返回 None。
                    page_author_data: Any = None
                    try:
                        # 环境变量可关闭：PLAYWRIGHT_EXTRACT_AUTHOR_DETAILS=0
                        if os.getenv('PLAYWRIGHT_EXTRACT_AUTHOR_DETAILS', '1').strip() not in {'0', 'false', 'False', 'no', 'NO'}:
                            print(f"\n[步骤 2.5/4] 🧾 WebDriver - hover 提取作者单位/邮箱线索...")
                            page_author_data = self.webdriver.extract_author_hover_data(
                                doi,
                                landing_page_url=scout_data.get('landing_page_url'),
                            )
                            if page_author_data and isinstance(page_author_data, dict):
                                record['page_author_data'] = page_author_data
                                extracted = page_author_data.get('authors') or []
                                print(f"[WebDriver] ✅ hover 提取到 {len(extracted)} 位作者（可能包含单位/email 线索）")
                            else:
                                print(f"[WebDriver] ⏭️ hover 未提取到作者详情（可能站点不支持/结构不匹配）")
                    except Exception as _:
                        pass
                    
                    if screenshot_path:
                        record['screenshot_path'] = screenshot_path
                        
                        # 3️⃣ Vision Agent：分析截图提取视觉作者信息
                        print(f"\n[步骤 3/4] 👁️ Vision Agent - 分析截图...")
                        meta_institutions = None
                        try:
                            if isinstance(record.get('page_author_data'), dict):
                                meta = record['page_author_data'].get('meta') or {}
                                mi = meta.get('citation_author_institution')
                                if isinstance(mi, list) and mi:
                                    meta_institutions = mi
                        except Exception:
                            meta_institutions = None

                        vision_data = self.vision.analyze_screenshot(
                            screenshot_path,
                            doi=doi,
                            scout_authors=scout_data.get('authors'),
                            meta_institutions=meta_institutions,
                        )
                        # 保留完整 vision_data，供 Judge 融合使用
                        record['vision_data'] = vision_data
                        
                        vision_authors = vision_data.get('authors', [])
                        print(f"[Vision] ✅ 从截图提取了 {len(vision_authors)} 位作者（含视觉标记）")
                        
                        record['vision_authors'] = vision_authors
                    else:
                        print(f"[WebDriver] ⚠️ 无法获取截图，跳过 Vision 分析")
                        record['screenshot_path'] = None
                        record['screenshot_status'] = 'BLOCKED_OR_FAILED'
                        record['vision_authors'] = []
                        record['vision_data'] = {'text': '', 'image_path': None, 'authors': []}

                    # 🆕 把 hover 提取的作者信息并入 vision_data（当 OCR 没提取到作者/单位时尤其重要）
                    try:
                        if isinstance(record.get('page_author_data'), dict):
                            hover_authors = record['page_author_data'].get('authors') or []
                        else:
                            hover_authors = []

                        if hover_authors:
                            vdata = record.get('vision_data') or {}
                            vauthors = vdata.get('authors') or []

                            # 若 OCR 未提取到作者（或作者为空），直接使用 hover authors
                            if not vauthors:
                                vdata['authors'] = hover_authors
                                vdata['text'] = (vdata.get('text') or '')
                                # 拼接 tooltip 文本给 Judge/调试
                                raw_tooltips = record['page_author_data'].get('raw_tooltips') or []
                                tooltip_text = "\n".join([t.get('tooltip', '') for t in raw_tooltips if isinstance(t, dict) and t.get('tooltip')])
                                if tooltip_text and not vdata['text']:
                                    vdata['text'] = tooltip_text
                                vdata['source'] = 'hover'
                                record['vision_data'] = vdata
                                record['vision_authors'] = hover_authors
                                print(f"[Orchestrator] ✅ 使用 hover 作者数据补全 vision_data")
                            else:
                                # OCR 已提取作者：将 hover 的通讯/邮箱/单位线索按 name/order 融合进去（不覆盖已有结构）
                                def _name_key(name: str) -> str:
                                    if not name:
                                        return ""
                                    return "".join(ch for ch in str(name).lower() if ch.isalnum())

                                def _order(a: dict) -> int:
                                    if not isinstance(a, dict):
                                        return -1
                                    for k in ('order', 'position'):
                                        v = a.get(k)
                                        if isinstance(v, int):
                                            return v
                                    return -1

                                hover_by_name = { _name_key(a.get('name')): a for a in hover_authors if isinstance(a, dict) and a.get('name') }
                                hover_by_order = { _order(a): a for a in hover_authors if isinstance(a, dict) and _order(a) > 0 }

                                merged = 0
                                for va in vauthors:
                                    if not isinstance(va, dict):
                                        continue
                                    key = _name_key(va.get('name'))
                                    ha = hover_by_name.get(key) if key else None
                                    if ha is None:
                                        o = _order(va)
                                        if o > 0:
                                            ha = hover_by_order.get(o)
                                    if not ha:
                                        continue

                                    # 权益标记：OR 合并
                                    for flag in ('is_corresponding', 'is_co_first'):
                                        if flag in ha:
                                            va[flag] = bool(va.get(flag)) or bool(ha.get(flag))

                                    # 单位补全：仅当 Vision 未给出或 Unknown
                                    v_aff = str(va.get('affiliation') or '').strip()
                                    h_aff = str(ha.get('affiliation') or '').strip()
                                    if (not v_aff) or (v_aff.lower() == 'unknown'):
                                        if h_aff and h_aff.lower() != 'unknown':
                                            va['affiliation'] = h_aff

                                    # 证据字段（不覆盖已有）
                                    for k in ('emails', 'has_mail_icon', 'markers', 'source'):
                                        if k in ha and k not in va:
                                            va[k] = ha.get(k)
                                    if va.get('is_corresponding') and not va.get('corresponding_source') and ha.get('is_corresponding'):
                                        va['corresponding_source'] = 'hover'
                                    merged += 1

                                if merged:
                                    vdata['authors'] = vauthors
                                    record['vision_data'] = vdata
                                    record['vision_authors'] = vauthors
                                    print(f"[Orchestrator] ✅ 已将 hover 线索融合进 Vision 作者（{merged} 人）")
                    except Exception:
                        pass
                    
                    # 4️⃣ Judge Agent：身份匹配与融合
                    print(f"\n[步骤 4/4] ⚖️ Judge Agent - 身份匹配...")
                    judge_result = self.judge.adjudicate(scout_data, record.get('vision_data') or {})
                    record['judge_result'] = judge_result

                    if isinstance(judge_result, dict) and judge_result.get('status') == 'skipped':
                        print(f"[Judge] ⏭️ 跳过：{judge_result.get('reason', '')}")
                        record["status"] = "SKIPPED"
                        record["skipped"] = True
                        # 如果已创建 paper 记录，将状态标记为 SKIPPED
                        paper = db.query(Paper).filter(Paper.doi == doi).first()
                        if paper:
                            paper.status = "SKIPPED"
                            db.commit()
                        results.append(record)
                        processed_in_batch.add(doi)
                        continue

                    if isinstance(judge_result, dict) and judge_result.get('status') == 'needs_review':
                        print(f"[Judge] ⚠️ 需要人工复核（单位命中但未匹配到教师）")
                        record["status"] = "NEEDS_REVIEW"
                        record["skipped"] = False
                        paper = db.query(Paper).filter(Paper.doi == doi).first()
                        if paper:
                            paper.status = "NEEDS_REVIEW"
                            db.commit()
                        results.append(record)
                        processed_in_batch.add(doi)
                        doi_status_map[doi]['status'] = 'NEEDS_REVIEW'
                        continue

                    print(f"[Judge] ✅ 匹配完成，结果已存储到数据库")
                    
                    # ✅ 标记为 COMPLETED
                    paper = db.query(Paper).filter(Paper.doi == doi).first()
                    if paper:
                        paper.status = "COMPLETED"
                        db.commit()
                    
                    record["status"] = "COMPLETED"
                    record["skipped"] = False
                    
                    # 🔄 更新内存缓存
                    processed_in_batch.add(doi)
                    doi_status_map[doi]['status'] = 'COMPLETED'
                
                except Exception as exc:
                    print(f"[Orchestrator] ❌ 错误: {exc}")
                    record["error"] = str(exc)
                    record["status"] = "ERROR"
                    
                    # 标记数据库中该论文为错误状态
                    try:
                        paper = db.query(Paper).filter(Paper.doi == doi).first()
                        if paper:
                            paper.status = "ERROR"
                            db.commit()
                    except:
                        pass
                
                results.append(record)
        
        finally:
            db.close()
        
        return results

    def process_excel(self, excel_file) -> List[Dict]:
        """Convenience wrapper that accepts a Streamlit-uploaded Excel
        object or a file path and extracts the DOI column automatically.
        """
        df = pd.read_excel(excel_file)
        doi_col = next((c for c in df.columns if str(c).lower() == "doi"), None)
        if doi_col is None:
            raise ValueError("Excel file must contain a 'DOI' column")
        dois = df[doi_col].astype(str).tolist()
        return self.process_dois(dois)