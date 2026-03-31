"""
【Judge Agent V3.0 - 完全改进的通用身份匹配算法】

架构改进：
1. 单位匹配 → 返回(部门ID, 置信度)
2. Vision调用 → 基于单位置信度决策
3. 名字匹配 → 在确定的部门内进行
4. 消歧 → 返回候选列表或单一结果
5. 权益标记 → 按置信度分层处理

特点：
✅ 通用系统（不写死学校信息）
✅ 用户上传各自的部门库和教职工库
✅ 最小化Vision调用（节省token）
✅ 诚实可信（所有结果带置信度）
✅ 支持人工审核工作流（导出待审查）
"""

import json
from typing import List, Dict, Tuple, Optional
from datetime import datetime

from backend.utils.department_matcher import DepartmentMatcher
from backend.utils.faculty_matcher import FacultyMatcher


class JudgeAgentV3:
    """
    通用科研人员身份匹配智能体（第3版）
    
    工作流：
    1. 加载用户的部门库 + 教职工库
    2. 对每篇论文（DOI）：
       a) Scout获取Crossref元数据
       b) 单位匹配（可能触发Vision）
       c) 名字匹配
       d) 权益标记识别
       e) 输出结果
    """
    
    def __init__(self, user_config: Dict):
        """
        初始化Judge Agent
        
        user_config 应包含：
        {
            "department_library": {...},
            "faculty_library": {...},
            "matching_rules": {
                "unit_match_confidence_threshold": 0.7,
                "equity_mark_confidence_threshold": 0.85,
                "name_match_threshold": 0.7
            },
            "processing_options": {...}
        }
        """
        print("[Judge V3] 初始化通用身份匹配智能体...")
        
        self.config = user_config
        
        # 加载用户数据库
        self.dept_matcher = DepartmentMatcher(user_config['department_library'])
        self.faculty_matcher = FacultyMatcher(user_config['faculty_library'])
        
        # 配置参数
        rules = user_config.get('matching_rules', {})
        self.unit_confidence_threshold = rules.get('unit_match_confidence_threshold', 0.7)
        self.equity_confidence_threshold = rules.get('equity_mark_confidence_threshold', 0.85)
        self.name_threshold = rules.get('name_match_threshold', 0.7)
        
        # 处理选项
        options = user_config.get('processing_options', {})
        self.enable_vision = options.get('enable_vision_agent', True)
        self.export_uncertain = options.get('export_uncertain_for_review', True)
        
        # 统计信息
        self.stats = {
            'total_papers': 0,
            'confirmed_matches': 0,
            'needs_review': 0,
            'failed': 0,
            'vision_calls': 0
        }
        
        print(f"[Judge V3] ✓ 部门库: {len(self.dept_matcher.get_all_depts())} 个")
        print(f"[Judge V3] ✓ 教职工库已加载")
        print(f"[Judge V3] ✓ 配置: unit_threshold={self.unit_confidence_threshold}, "
              f"equity_threshold={self.equity_confidence_threshold}")
    
    def process_paper(self, paper_data: Dict, vision_data: Optional[Dict] = None) -> Dict:
        """
        处理单篇论文
        
        参数：
        - paper_data: Scout Agent 返回的Crossref元数据
          {
            "doi": "10.xxxx/xxxxx",
            "title": "Paper title",
            "authors": [
              {"name": "John Doe", "affiliation": "University of XXX", "order": 1},
              ...
            ]
          }
        - vision_data: Vision Agent 返回的权益标记（可选）
          {
            "authors": [
              {"name": "John Doe", "is_corresponding": True, "confidence": 0.95},
              ...
            ]
          }
        
        返回：
        {
          "doi": "10.xxxx",
          "status": "success" | "partial" | "failed",
          "confirmed_authors": [...],  # 高置信度，自动确认
          "review_authors": [...],     # 中置信度，需要审核
          "unmatched_authors": [...],  # 未匹配
          "vision_called": bool,       # 是否调用了Vision
          "summary": {...}
        }
        """
        doi = paper_data.get('doi', 'unknown')
        title = paper_data.get('title', '')[:60]
        
        print(f"\n[Judge V3] 处理论文: {doi[:20]}... ({title}...)")
        
        self.stats['total_papers'] += 1
        
        result = {
            'doi': doi,
            'title': paper_data.get('title', ''),
            'confirmed_authors': [],
            'review_authors': [],
            'unmatched_authors': [],
            'vision_called': False,
            'processing_timestamp': datetime.now().isoformat()
        }
        
        # 第1步：提取作者
        authors = paper_data.get('authors', [])
        if not authors:
            print(f"[Judge V3] ⚠️ 无作者数据")
            result['status'] = 'failed'
            result['error'] = '无作者数据'
            self.stats['failed'] += 1
            return result
        
        print(f"[Judge V3] 📥 Crossref 作者数: {len(authors)}")
        
        # 第2步：对每个作者进行匹配
        need_review_authors = []  # 需要人工审核的
        
        for idx, author in enumerate(authors, 1):
            author_name = author.get('name', '').strip()
            author_aff = author.get('affiliation', '').strip()
            author_rank = author.get('order', idx)
            
            print(f"\n[Judge V3]   [{idx}] 处理作者: {author_name} ({author_aff[:30]}...)")
            
            # 第2a步：单位匹配
            dept_matches = self.dept_matcher.match_affiliation(author_aff)
            
            if not dept_matches:
                print(f"[Judge V3]     ⏭️  单位不匹配 → 非本校作者")
                result['unmatched_authors'].append({
                    'name': author_name,
                    'affiliation': author_aff,
                    'rank': author_rank,
                    'reason': '单位不匹配'
                })
                continue
            
            best_dept_id, best_dept_conf = dept_matches[0]
            print(f"[Judge V3]     🎯 单位匹配: {best_dept_id} (conf={best_dept_conf:.2f})")
            
            # 第2b步：单位置信度检查 → 决策是否调用Vision
            if best_dept_conf >= self.unit_confidence_threshold and self.enable_vision:
                print(f"[Judge V3]     → 单位置信度足够，调用Vision提取权益标记")
                vision_marks = self._extract_author_vision_marks(
                    author_name, vision_data
                )
                if vision_marks:
                    self.stats['vision_calls'] += 1
                    result['vision_called'] = True
                    print(f"[Judge V3]     ✓ Vision结果: corresponding={vision_marks.get('is_corresponding')}, "
                          f"co_first={vision_marks.get('is_co_first')}")
            else:
                print(f"[Judge V3]     ⏭️  单位置信度不足({best_dept_conf:.2f}<{self.unit_confidence_threshold}) "
                      f"或Vision未启用，跳过Vision")
                vision_marks = {}
            
            # 第2c步：名字匹配（在确定的部门中）
            faculty_candidates = self.faculty_matcher.find_in_depts(
                [best_dept_id],
                author_name,
                self.name_threshold
            )
            
            if not faculty_candidates:
                print(f"[Judge V3]     ❌ 名字不匹配")
                result['unmatched_authors'].append({
                    'name': author_name,
                    'affiliation': author_aff,
                    'rank': author_rank,
                    'reason': '名字不匹配'
                })
                continue
            
            # 第2d步：消歧处理
            if len(faculty_candidates) == 1:
                # 唯一匹配
                faculty = faculty_candidates[0]
                confidence = 0.92  # 单部门唯一匹配，高置信
                
                print(f"[Judge V3]     ✅ 唯一匹配: {faculty['name_zh']} (conf={confidence:.2f})")
                
                # 添加到已确认列表
                match_result = self._build_match_result(
                    author, faculty, confidence, vision_marks, best_dept_id, best_dept_conf
                )
                result['confirmed_authors'].append(match_result)
                self.stats['confirmed_matches'] += 1
            
            else:
                # 多个同名候选
                print(f"[Judge V3]     ⚠️  多个同名候选({len(faculty_candidates)}人)，需要人工审核")
                
                review_item = {
                    'paper_author': {
                        'name': author_name,
                        'affiliation': author_aff,
                        'rank': author_rank
                    },
                    'candidates': [
                        {
                            'employee_id': f['employee_id'],
                            'name_zh': f['name_zh'],
                            'position': f.get('position', 'N/A'),
                            'email': f.get('email', 'N/A'),
                            'research_area': f.get('research_area', 'N/A')
                        }
                        for f in faculty_candidates
                    ],
                    'vision_marks': vision_marks,
                    'dept_id': best_dept_id
                }
                result['review_authors'].append(review_item)
                self.stats['needs_review'] += 1
        
        # 第3步：确定总体状态
        if result['confirmed_authors'] and not result['review_authors']:
            result['status'] = 'success'
        elif result['confirmed_authors'] or result['review_authors']:
            result['status'] = 'partial'
        else:
            result['status'] = 'failed'
        
        # 第4步：生成摘要
        result['summary'] = {
            'total_authors': len(authors),
            'confirmed': len(result['confirmed_authors']),
            'review_needed': len(result['review_authors']),
            'unmatched': len(result['unmatched_authors']),
            'match_rate': f"{len(result['confirmed_authors']) + len(result['review_authors']) / len(authors) * 100:.1f}%"
        }
        
        return result
    
    def _extract_author_vision_marks(self, author_name: str, 
                                     vision_data: Optional[Dict]) -> Dict:
        """
        从Vision结果中提取特定作者的权益标记
        
        返回：
        {
            'is_corresponding': bool,
            'is_corresponding_confidence': float,
            'is_co_first': bool,
            'is_co_first_confidence': float,
            'source': 'symbol' | 'text' | 'auto_inference'
        }
        """
        if not vision_data or 'authors' not in vision_data:
            return {}
        
        for v_author in vision_data['authors']:
            if v_author.get('name', '').lower() == author_name.lower():
                return {
                    'is_corresponding': v_author.get('is_corresponding', False),
                    'is_corresponding_confidence': v_author.get('is_corresponding_confidence', 0.0),
                    'is_co_first': v_author.get('is_co_first', False),
                    'is_co_first_confidence': v_author.get('is_co_first_confidence', 0.0),
                    'source': v_author.get('equity_mark_source', 'unknown')
                }
        
        return {}
    
    def _build_match_result(self, author: Dict, faculty: Dict, confidence: float,
                           vision_marks: Dict, dept_id: str, dept_conf: float) -> Dict:
        """构建匹配结果"""
        return {
            'paper_author': {
                'name': author.get('name'),
                'affiliation': author.get('affiliation'),
                'rank': author.get('order', 1)
            },
            'matched_faculty': {
                'employee_id': faculty['employee_id'],
                'name_zh': faculty['name_zh'],
                'position': faculty.get('position'),
                'email': faculty.get('email'),
                'research_area': faculty.get('research_area')
            },
            'match_confidence': confidence,
            'unit_confidence': dept_conf,
            'equity_marks': {
                'is_corresponding': (
                    vision_marks.get('is_corresponding', False)
                    if vision_marks.get('is_corresponding_confidence', 0) >= self.equity_confidence_threshold
                    else False
                ),
                'is_co_first': (
                    vision_marks.get('is_co_first', False)
                    if vision_marks.get('is_co_first_confidence', 0) >= self.equity_confidence_threshold
                    else False
                )
            },
            'dept_id': dept_id,
            'uncertain_equity_marks': {
                'is_corresponding': (
                    vision_marks.get('is_corresponding', False)
                    if 0.5 <= vision_marks.get('is_corresponding_confidence', 0) < self.equity_confidence_threshold
                    else None
                ),
                'is_co_first': (
                    vision_marks.get('is_co_first', False)
                    if 0.5 <= vision_marks.get('is_co_first_confidence', 0) < self.equity_confidence_threshold
                    else None
                )
            }
        }
    
    def get_stats(self) -> Dict:
        """获取处理统计"""
        return {
            'timestamp': datetime.now().isoformat(),
            **self.stats,
            'dept_matcher_stats': self.dept_matcher.get_stats(),
            'faculty_matcher_stats': self.faculty_matcher.get_stats()
        }
    
    def export_results(self, output_dir: str):
        """导出结果到文件"""
        print(f"\n[Judge V3] 导出结果到 {output_dir}")
        # 待实现
        pass
