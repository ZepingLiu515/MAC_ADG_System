import os
from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import Faculty, Paper, PaperAuthor
import json
from typing import List, Dict

class JudgeAgent:
    """
    [Judge Agent - 审判代理]
    职责：
    1. 将提取的作者与本地教职员库进行交叉引用。
    2. 将最终的论文和作者记录持久化到 SQLite。
    3. 判断「此论文对我们的大学有效吗？」
    """

    def __init__(self):
        pass

    def adjudicate(self, scout_data, vision_data):
        """
        主入口。
        输入： 
          - scout_data (dict): 来自 Crossref/Unpaywall 的元数据
          - vision_data (dict): 从 PDF/HTML 提取的文本
        """
        doi = scout_data.get("doi")
        title = scout_data.get("title")
        journal = scout_data.get("journal")
        pub_date = scout_data.get("publish_date")
        
        print(f"[Judge] 正在处理案例: {doi}")

        # 1. Database Session
        db: Session = next(get_db())
        
        try:
            # 2. 检查论文是否已存在（避免重复）
            existing_paper = db.query(Paper).filter(Paper.doi == doi).first()
            if existing_paper:
                print(f"[Judge] 论文已存在，更新状态。")
                # 重用现有的论文记录
                paper = existing_paper
            else:
                # 创建新的论文记录
                paper = Paper(
                    doi=doi,
                    title=title,
                    journal=journal,
                    publish_date=pub_date,
                    # Save local path if available
                    pdf_path=scout_data.get("pdf_path") or scout_data.get("html_path"), 
                    status="COMPLETED"
                )
                db.add(paper)
                db.flush() # 刷新以获取 ID

            # 3. 身份匹配策略（增强型 L1+L2）
            full_text = vision_data.get("text", "").lower()
            all_faculty = db.query(Faculty).all()
            matched_count = 0

            # 下面定义辅助函数
            def _quick_match(name, faculty_obj):
                from difflib import SequenceMatcher
                variants = []
                if faculty_obj.name_en_list:
                    try:
                        variants = json.loads(faculty_obj.name_en_list)
                    except:
                        variants = []
                candidates = []
                if faculty_obj.name_zh:
                    candidates.append(faculty_obj.name_zh)
                candidates.extend(variants)

                best = 0.0
                for variant in candidates:
                    if not variant:
                        continue
                    var = variant.lower()
                    nm = name.lower()
                    if var == nm:
                        return 1.0
                    if var in nm:
                        return 0.95
                    score = SequenceMatcher(None, var, nm).ratio()
                    if score > best:
                        best = score
                return best

            def _get_affiliation_synonyms(dept):
                # load synonyms from JSON resource (cached for performance)
                import json
                path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'affiliation_synonyms.json')
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        syn_map = json.load(f)
                except Exception:
                    return []
                # normalize keys
                lower_map = {k.lower(): [s.lower() for s in v] for k, v in syn_map.items()}
                return lower_map.get(dept.lower(), [])

            def _affiliation_match(paper_aff, faculty_obj):
                """
                支持多部门匹配（V2.0）
                策略：'任意匹配' - 只要作者的单位与教师的任何一个部门匹配即可
                """
                if not paper_aff:
                    return 0.5
                
                paper_aff_lower = paper_aff.lower()
                
                # V2.0: 优先检查 departments 列表（多部门）
                depts_to_check = []
                if faculty_obj.departments:
                    try:
                        dept_list = json.loads(faculty_obj.departments) if isinstance(faculty_obj.departments, str) else faculty_obj.departments
                        depts_to_check = [d.lower() for d in dept_list if d]
                    except json.JSONDecodeError as e:
                        print(f"[Judge] ⚠️ departments JSON 解析失败: {e}，回退到单个department字段")
                        if isinstance(faculty_obj.department, str):
                            depts_to_check = [faculty_obj.department.lower()]
                    except Exception as e:
                        print(f"[Judge] ⚠️ departments 处理异常: {e}")
                        depts_to_check = []
                
                # 向后兼容：如果没有 departments，使用单个 department 字段
                if not depts_to_check and faculty_obj.department:
                    depts_to_check = [faculty_obj.department.lower()]
                
                if not depts_to_check:
                    return 0.5
                
                # 对每个部门进行匹配，取最高分数（'任意匹配'策略）
                best_score = 0.0
                for dept in depts_to_check:
                    # 精确匹配
                    if paper_aff_lower == dept:
                        return 1.0
                    # 包含匹配（论文单位包含部门名）
                    if dept in paper_aff_lower:
                        best_score = max(best_score, 0.9)
                    # 同义词匹配
                    for syn in _get_affiliation_synonyms(dept):
                        if syn in paper_aff_lower:
                            best_score = max(best_score, 0.85)
                    # 关键词匹配（部门被拆分为多个关键词，计算匹配数量）
                    kws = [w for w in dept.replace(',', ' ').split() if len(w) > 1]
                    if kws:
                        matched = sum(1 for kw in kws if kw in paper_aff_lower)
                        if matched > 0:
                            kw_score = 0.5 + 0.2 * min(matched / len(kws), 1.0)
                            best_score = max(best_score, kw_score)
                
                return best_score

            def _calculate_confidence(name, aff, coauthors, faculty_obj, score_l1):
                # weights: name 0.5, aff 0.4, coauthor 0.1
                s_name = score_l1
                s_aff = _affiliation_match(aff, faculty_obj)
                s_co = 0.5
                if coauthors:
                    matchc = 0
                    for ca in coauthors:
                        if _quick_match(ca, faculty_obj) > 0.8:
                            matchc += 1
                    s_co = 0.5 + 0.5 * min(matchc / len(coauthors), 1.0)
                return min(1.0, 0.5 * s_name + 0.4 * s_aff + 0.1 * s_co), {
                    'name': s_name, 'aff': s_aff, 'coauthor': s_co
                }

            # parse author list from vision_data
            vision_authors = vision_data.get("authors", [])
            if not vision_authors:
                # fallback: extract from text if no structured authors
                vision_authors = self._extract_authors_from_text(vision_data.get("text", ""))

            for pa in vision_authors:
                pname = pa.get('name', '')
                paff = pa.get('affiliation', '')
                prank = pa.get('position', 999)
                coauthors = [x.get('name') for x in vision_authors if x.get('name') != pname]
                is_corr = pa.get('is_corresponding', False)
                is_cofst = pa.get('is_co_first', False)

                # L1 filtering
                candidates = []
                for faculty in all_faculty:
                    score1 = _quick_match(pname, faculty)
                    if score1 > 0.6:
                        candidates.append((faculty, score1))
                if not candidates:
                    continue

                # L2 scoring
                scored = []
                for faculty, s1 in candidates:
                    conf, signals = _calculate_confidence(pname, paff, coauthors, faculty, s1)
                    scored.append((faculty, conf, s1, signals))
                scored.sort(key=lambda t: t[1], reverse=True)

                best_faculty, best_conf, best_s1, best_signals = scored[0]
                level = 'L1' if best_conf >= 0.8 else 'L2'
                # in future we may add L3

                existing_link = db.query(PaperAuthor).filter(
                    PaperAuthor.paper_doi == doi,
                    PaperAuthor.matched_faculty_id == best_faculty.id
                ).first()

                if not existing_link:
                    author_record = PaperAuthor(
                        paper_doi=doi,
                        rank=prank,
                        raw_name=pname,
                        raw_affiliation=paff,
                        matched_faculty_id=best_faculty.id,
                        is_corresponding=is_corr,
                        is_co_first=is_cofst,
                        confidence_score=int(best_conf * 100),
                        matched_level=level,
                        match_signals=best_signals
                    )
                    db.add(author_record)
                    matched_count += 1

            db.commit()
            print(f"[Judge] 案例已关闭。匹配了 {matched_count} 名教职员。")
            return True

        except Exception as e:
            db.rollback()
            print(f"[Judge] 错误: {e}")
            return False
        finally:
            db.close()

    def _extract_authors_from_text(self, text: str) -> List[Dict]:
        """Extract authors from raw text as fallback"""
        # Simple extraction: split by common separators
        lines = text.split('\n')
        authors = []
        for i, line in enumerate(lines):
            line = line.strip()
            if line and len(line) > 2 and len(line) < 100:  # reasonable name length
                authors.append({
                    'name': line,
                    'affiliation': '',
                    'position': i + 1
                })
        return authors[:10]  # limit to first 10 authors