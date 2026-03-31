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
import os
from typing import List, Dict, Tuple
from difflib import SequenceMatcher
import requests

from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import Faculty, Paper, PaperAuthor
from config import DEEPSEEK_API_KEY, DEEPSEEK_MODEL, DEEPSEEK_BASE_URL


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
    
    def adjudicate(self, scout_data: dict, vision_data: dict = None) -> dict or None:
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
        
        print(f"\n[Judge] 🔍 处理论文: {doi}")
        print(f"[Judge] 标题: {title[:60]}...")
        
        db: Session = next(get_db())
        
        try:
            # 1️⃣ 获取 Crossref 数据
            crossref_authors = scout_data.get("authors", [])
            print(f"[Judge] 📥 Crossref 作者数: {len(crossref_authors)} 人")
            
            # 2️⃣【快速筛选】检查是否有学校单位
            school_depts = self._get_school_departments(db)
            has_school_aff = self._has_school_affiliation(crossref_authors, school_depts)
            
            # 【优化决策】
            vision_authors = []
            if crossref_authors and len(crossref_authors) > 0:
                # Crossref 有数据
                if has_school_aff:
                    # ✅ 有学校单位 → 调用 Vision 提取权益标记
                    print(f"[Judge] ✅ 检测到本校单位，需要提取权益标记")
                    vision_authors = vision_data.get("authors", []) if vision_data else []
                    print(f"[Judge] 📥 Vision 作者数: {len(vision_authors)} 人")
                else:
                    # ⏭️ 无学校单位 → 直接跳过，不调用 Vision
                    print(f"[Judge] ⏭️ 无学校单位，跳过本论文（不调用Vision）")
                    return {
                        "status": "skipped",
                        "doi": doi,
                        "reason": "无学校相关单位"
                    }
            else:
                # Crossref 为空 → 用 Vision 识别
                print(f"[Judge] 💡 Crossref 为空，用 Vision 识别")
                vision_authors = vision_data.get("authors", []) if vision_data else []
                print(f"[Judge] 📥 Vision 作者数: {len(vision_authors)} 人")
            
            # 如果最终没有任何作者数据，跳过
            if not crossref_authors and not vision_authors:
                print(f"[Judge] ⚠️ 无作者数据，跳过本论文")
                return {"status": "skipped", "doi": doi, "reason": "无作者数据"}
            
            # 3️⃣ 检查或创建论文记录
            paper = self._get_or_create_paper(db, doi, title, journal, pub_date)
            
            # 4️⃣ 融合作者数据
            merged_authors = self._merge_authors(crossref_authors, vision_authors)
            
            # 5️⃣ 获取本校教师名单
            all_faculty = db.query(Faculty).all()
            print(f"[Judge] 📚 本校教师数: {len(all_faculty)} 人")
            
            # 6️⃣ 对每个作者进行身份匹配
            print(f"\n[Judge] 🎯 执行身份匹配:")
            matched_count = 0
            
            for idx, author in enumerate(merged_authors, 1):
                match_result = self._match_author_to_faculty(
                    author, all_faculty, db
                )
                
                if match_result:
                    matched_faculty, confidence = match_result
                    matched_count += 1
                    
                    print(f"  {idx}. {author['name']}")
                    print(f"     ✅ 匹配: {matched_faculty.name_zh} ({matched_faculty.department})")
                    print(f"     📊 置信度: {confidence:.2%}")
                    
                    # 保存匹配结果
                    paper_author = PaperAuthor(
                        paper_doi=doi,
                        raw_name=author['name'],
                        raw_affiliation=author.get('affiliation', 'Unknown'),
                        rank=idx,
                        is_corresponding=author.get('is_corresponding', False),
                        is_co_first=author.get('is_co_first', False),
                        matched_faculty_id=matched_faculty.id,
                        confidence_score=int(confidence * 100)
                    )
                    db.add(paper_author)
                else:
                    print(f"  {idx}. {author['name']} - 未匹配")
            
            # 7️⃣ 更新论文状态
            paper.status = "COMPLETED"
            db.commit()
            
            print(f"\n[Judge] ✅ 论文处理完成，匹配 {matched_count}/{len(merged_authors)} 位作者")
            
            return {
                "status": "success",
                "doi": doi,
                "total_authors": len(merged_authors),
                "matched_authors": matched_count
            }
        
        except Exception as e:
            print(f"[Judge] ❌ 处理失败: {e}")
            db.rollback()
            return None
        
        finally:
            db.close()
    
    def _get_or_create_paper(self, db: Session, doi: str, title: str, 
                            journal: str, pub_date: str) -> Paper:
        """获取或创建论文记录"""
        existing = db.query(Paper).filter(Paper.doi == doi).first()
        
        if existing:
            print(f"[Judge] 📄 论文已存在（重复处理）")
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
        
        print(f"[Judge] ➕ 创建新论文记录")
        return paper
    
    def _get_school_departments(self, db: Session) -> List[str]:
        """
        获取学校所有部门名称列表（用于快速筛选）
        
        返回：部门名称的小写列表，用于快速查询
        """
        departments = set()
        
        all_faculty = db.query(Faculty).all()
        
        for faculty in all_faculty:
            # 添加主部门
            if faculty.department:
                departments.add(faculty.department.lower().strip())
            
            # 添加多部门列表中的部门
            if faculty.departments:
                try:
                    dept_list = json.loads(faculty.departments) if isinstance(faculty.departments, str) else faculty.departments
                    for dept in dept_list:
                        if dept:
                            departments.add(dept.lower().strip())
                except:
                    pass
        
        return list(departments)
    
    def _has_school_affiliation(self, crossref_authors: List[dict], 
                               school_depts: List[str]) -> bool:
        """
        【快速筛选】检查 Crossref 作者中是否有学校单位
        
        原理：
        - 如果Crossref作者都不是学校单位 → 这篇论文与本校无关 → 跳过
        - 如果至少有一个作者是学校单位 → 调用Vision提取权益标记
        
        返回：True 如果有学校单位，False 如果无相关单位
        """
        if not crossref_authors or not school_depts:
            return False
        
        # 关键字匹配（容错处理翻译和简写）
        keywords_map = {
            # 常见中文关键字
            '大学': ['university', 'univ', 'uni'],
            '学院': ['school', 'college'],
            '系': ['department', 'dept', 'division'],
            '所': ['institute', 'inst', 'research'],
            '中心': ['center', 'centre'],
        }
        
        for author in crossref_authors:
            aff = author.get('affiliation', '').lower().strip()
            
            if not aff:
                continue
            
            # 精确匹配：直接对比学校部门列表
            for school_dept in school_depts:
                if school_dept in aff or aff in school_dept:
                    print(f"[Judge] 🎯 匹配到学校单位: {author.get('name')} @ {aff}")
                    return True
            
            # 容错匹配：检查关键字
            for cn_keyword, en_keywords in keywords_map.items():
                if cn_keyword in aff:
                    for en_keyword in en_keywords:
                        if en_keyword in aff:
                            print(f"[Judge] 🎯 关键字匹配到学校相关: {author.get('name')} @ {aff}")
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
        
        # 情况 1：Crossref 有数据 → 以 Crossref 为主
        if crossref_authors and len(crossref_authors) > 0:
            print(f"[Judge] 💡 使用 Crossref 作者列表作为基础（{len(crossref_authors)} 人）")
            
            # 确保所有作者都有权益字段
            for author in crossref_authors:
                if 'is_corresponding' not in author:
                    author['is_corresponding'] = False
                if 'is_co_first' not in author:
                    author['is_co_first'] = False
            
            # 情况 1a：也有 Vision 数据 → 从 Vision 中提取权益标记并合并
            if vision_authors and len(vision_authors) > 0:
                print(f"[Judge] 📝 从 Vision 中提取权益标记（{len(vision_authors)} 人）")
                
                # 建立 Vision 作者的查询表（按名字）
                vision_map = {
                    author['name'].strip().lower(): author
                    for author in vision_authors
                }
                
                # 为 Crossref 作者补充权益标记
                merged_count = 0
                for author in crossref_authors:
                    author_key = author.get('name', '').strip().lower()
                    
                    if author_key in vision_map:
                        vision_author = vision_map[author_key]
                        # 从 Vision 提取权益标记
                        author['is_corresponding'] = vision_author.get('is_corresponding', False)
                        author['is_co_first'] = vision_author.get('is_co_first', False)
                        merged_count += 1
                
                print(f"[Judge] ✅ 成功合并 {merged_count} 位作者的权益标记")
            
            return crossref_authors
        
        # 情况 2：Crossref 为空 → 回退到 Vision
        if vision_authors and len(vision_authors) > 0:
            print(f"[Judge] 💡 Crossref 为空，使用 Vision 作者数据（{len(vision_authors)} 人）")
            
            # 确保 Vision 作者也有权益字段
            for author in vision_authors:
                if 'is_corresponding' not in author:
                    author['is_corresponding'] = False
                if 'is_co_first' not in author:
                    author['is_co_first'] = False
            
            return vision_authors
        
        # 情况 3：都没有数据
        print(f"[Judge] ⚠️ 没有作者数据（Crossref 和 Vision 都为空）")
        return []
    
    def _match_author_to_faculty(self, author: dict, faculty_list: List[Faculty],
                                 db: Session) -> Tuple[Faculty, float] or None:
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
        if faculty.name_en_json:
            try:
                en_names = json.loads(faculty.name_en_json)
                candidates.extend([n.lower() for n in en_names if n])
            except:
                pass
        
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
            except:
                pass
        
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
    
    def _use_llm_for_verification(self, author_name: str, faculty_name: str,
                                  author_aff: str, faculty_aff: str) -> float:
        """
        使用 LLM 进行最终验证（可选的高级特性）
        
        在模棱两可的情况下，用 AI 推理判断是否为同一人
        """
        try:
            prompt = f"""判断以下两个人是否为同一个人（0 = 确定不是，1 = 确定是）：

论文作者：
- 名字: {author_name}
- 单位: {author_aff}

学校教师：
- 名字: {faculty_name}
- 单位: {faculty_aff}

考虑因素：
1. 名字相似度（拼写、缩写、翻译）
2. 单位翻译和别名
3. 常见的名字变体

返回 0-1 之间的置信度。"""
            
            headers = {
                'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'model': DEEPSEEK_MODEL,
                'messages': [{'role': 'user', 'content': prompt}]
            }
            
            response = requests.post(
                f'{DEEPSEEK_BASE_URL}/chat/completions',
                headers=headers,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                text = result['choices'][0]['message']['content']
                
                # 尝试提取数字
                try:
                    score = float([w for w in text.split() if w.replace('.', '').isdigit()][-1])
                    return score / 100 if score > 1 else score
                except:
                    pass
        
        except Exception as e:
            print(f"[Judge] ⚠️ LLM 验证失败: {e}")
        
        return 0.5  # 默认返回中等置信度
