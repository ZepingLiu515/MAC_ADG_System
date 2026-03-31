"""
【部门匹配器】- 通用的单位库管理与模糊匹配

职责：
1. 加载用户上传的部门库
2. 提供通用的单位匹配接口
3. 返回(科室, 置信度)而不是简单的True/False
4. 支持英文、中文、别名、拼写错误等

算法：三层匹配
1. 精确匹配 (confidence=1.0)
2. 编辑距离匹配 (confidence=0.7-0.99)
3. 关键字匹配 (confidence=0.5-0.8)
"""

import json
import csv
from typing import List, Dict, Tuple, Optional
from difflib import SequenceMatcher
import re


class DepartmentMatcher:
    """通用部门库管理器"""
    
    def __init__(self, dept_config: Dict):
        """
        初始化部门库
        
        dept_config 应包含：
        {
            "source": "path/to/departments.csv",
            "columns": {
                "dept_id": "部门编码",
                "dept_name_zh": "中文名称",
                "dept_name_en": "英文名称",
                "aliases": "别名（逗号分隔）",
                "keywords": "关键字（用于快速查询）"
            }
        }
        """
        self.departments = {}
        self.load_from_csv(dept_config['source'], dept_config.get('columns', {}))
    
    def load_from_csv(self, csv_path: str, columns: Dict):
        """从CSV加载部门库"""
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    dept_id = row.get(columns.get('dept_id', 'dept_id'), '').strip()
                    
                    if not dept_id:
                        continue
                    
                    self.departments[dept_id] = {
                        'dept_id': dept_id,
                        'name_zh': row.get(columns.get('dept_name_zh', 'dept_name_zh'), '').strip(),
                        'name_en': row.get(columns.get('dept_name_en', 'dept_name_en'), '').strip(),
                        'aliases': self._parse_aliases(
                            row.get(columns.get('aliases', 'aliases'), '')
                        ),
                        'keywords': self._parse_keywords(
                            row.get(columns.get('keywords', 'keywords'), '')
                        )
                    }
            
            print(f"✓ 加载部门库成功: {len(self.departments)} 个部门")
        
        except Exception as e:
            print(f"✗ 加载部门库失败: {e}")
            self.departments = {}
    
    def _parse_aliases(self, aliases_str: str) -> List[str]:
        """解析别名字符串"""
        if not aliases_str:
            return []
        return [a.strip().lower() for a in aliases_str.split(',') if a.strip()]
    
    def _parse_keywords(self, keywords_str: str) -> List[str]:
        """解析关键字字符串"""
        if not keywords_str:
            return []
        return [k.strip().lower() for k in keywords_str.split(',') if k.strip()]
    
    def match_affiliation(self, paper_affiliation: str) -> List[Tuple[str, float]]:
        """
        匹配论文单位到本校部门
        
        参数：
        - paper_affiliation: 论文中的单位名 (可能是中文/英文/混合/有拼写错)
        
        返回：
        - [(dept_id, confidence), ...] 按置信度排序，置信度>0.5的才返回
        
        示例：
        >>> match_affiliation("Southwest Medical University")
        [('clinical_medicine', 0.95), ('affiliated_hospital', 0.65)]
        
        >>> match_affiliation("Sicuan Univ")  # 拼写错误
        [('clinical_medicine', 0.78)]
        """
        if not paper_affiliation or not paper_affiliation.strip():
            return []
        
        aff_lower = paper_affiliation.lower().strip()
        matches = []
        
        for dept_id, dept_info in self.departments.items():
            # 第1层：精确匹配（包括别名）
            exact_score = self._exact_match(aff_lower, dept_info)
            if exact_score >= 1.0:
                matches.append((dept_id, 1.0))
                continue
            
            # 第2层：编辑距离匹配（拼写错）
            edit_score = self._edit_distance_match(aff_lower, dept_info)
            if edit_score >= 0.7:
                matches.append((dept_id, edit_score))
                continue
            
            # 第3层：关键字匹配
            keyword_score = self._keyword_match(aff_lower, dept_info)
            if keyword_score >= 0.5:
                matches.append((dept_id, keyword_score))
        
        # 按置信度降序排序，过滤<0.5的
        matches = sorted(
            [(d, c) for d, c in matches if c >= 0.5],
            key=lambda x: x[1],
            reverse=True
        )
        
        return matches
    
    def _exact_match(self, aff_lower: str, dept_info: Dict) -> float:
        """精确匹配检查"""
        # 完全相等
        if aff_lower == dept_info['name_zh'].lower():
            return 1.0
        if aff_lower == dept_info['name_en'].lower():
            return 1.0
        
        # 别名中有
        if aff_lower in dept_info['aliases']:
            return 0.99
        
        # 包含关系
        if dept_info['name_zh'].lower() in aff_lower or aff_lower in dept_info['name_zh'].lower():
            return 0.95
        if dept_info['name_en'].lower() in aff_lower or aff_lower in dept_info['name_en'].lower():
            return 0.92
        
        for alias in dept_info['aliases']:
            if alias in aff_lower or aff_lower in alias:
                return 0.88
        
        return 0.0
    
    def _edit_distance_match(self, aff_lower: str, dept_info: Dict) -> float:
        """
        编辑距离匹配（处理拼写错误）
        
        例如：
        "Sicuan Medical" vs "Sichuan Medical" (少了h)
        """
        candidates = [
            dept_info['name_zh'].lower(),
            dept_info['name_en'].lower(),
        ] + dept_info['aliases']
        
        best_score = 0.0
        
        for candidate in candidates:
            # 如果两个字符串长度相差太大，直接跳过
            if abs(len(aff_lower) - len(candidate)) > 5:
                continue
            
            # SequenceMatcher计算相似度 (0-1)
            matcher = SequenceMatcher(None, aff_lower, candidate)
            ratio = matcher.ratio()
            
            # 只有相似度>0.7才认为是拼写错误
            if ratio > 0.7:
                # 根据相似度转换为置信度
                # 0.7-0.8 → 0.65-0.75
                # 0.8-0.9 → 0.75-0.85
                # 0.9-1.0 → 0.85-1.0
                confidence = 0.6 + ratio * 0.25
                best_score = max(best_score, confidence)
        
        return best_score
    
    def _keyword_match(self, aff_lower: str, dept_info: Dict) -> float:
        """
        关键字匹配
        
        例如：
        "Southwest" → 匹配到 "Southwest Medical University"
        """
        # 提取论文单位的关键词
        paper_keywords = set(
            w for w in aff_lower.split()
            if len(w) > 2 and w not in ['and', 'of', 'the', 'university', 'school']
        )
        
        if not paper_keywords:
            return 0.0
        
        # 提取部门信息中的关键词
        dept_keywords = set(dept_info['keywords'])
        
        # 添加name_zh和name_en的词
        for name in [dept_info['name_zh'].lower(), dept_info['name_en'].lower()]:
            dept_keywords.update(w for w in name.split() if len(w) > 2)
        
        if not dept_keywords:
            return 0.0
        
        # 计算关键词重叠度
        overlap = len(paper_keywords & dept_keywords)
        max_len = max(len(paper_keywords), len(dept_keywords))
        
        # 重叠比例 → 置信度
        # 50% 重叠 → 0.5 置信
        # 100% 重叠 → 1.0 置信（但通常不会）
        confidence = overlap / max_len if max_len > 0 else 0.0
        
        return min(confidence, 0.8)  # 关键字匹配最高0.8置信
    
    def get_dept_by_id(self, dept_id: str) -> Optional[Dict]:
        """按ID获取部门信息"""
        return self.departments.get(dept_id)
    
    def get_all_depts(self) -> List[Dict]:
        """获取所有部门列表"""
        return list(self.departments.values())
    
    def get_stats(self) -> Dict:
        """获取部门库统计信息"""
        return {
            "total_departments": len(self.departments),
            "with_aliases": sum(1 for d in self.departments.values() if d['aliases']),
            "with_keywords": sum(1 for d in self.departments.values() if d['keywords'])
        }
