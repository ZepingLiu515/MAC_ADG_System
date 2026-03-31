"""
【教职工匹配器】- 通用的教职工库管理与查询

职责：
1. 加载用户上传的教职工库
2. 支持"在指定部门中查教师"
3. 支持模糊名字匹配处理拼写错
4. 返回候选教师列表

核心：
- 教职工库由用户上传（不写死）
- 支持中文名、英文名、别名
- 按部门组织（加速查询）
"""

import csv
from typing import List, Dict, Optional
from difflib import SequenceMatcher


class FacultyMatcher:
    """通用教职工库管理器"""
    
    def __init__(self, faculty_config: Dict):
        """
        初始化教职工库
        
        faculty_config 应包含：
        {
            "source": "path/to/faculty.csv",
            "columns": {
                "employee_id": "工号",
                "name_zh": "姓名",
                "dept_id": "所属部门",
                "name_en": "英文名（可选）",
                "email": "邮箱（可选）",
                "position": "职位（可选）",
                "research_area": "研究方向（可选）"
            }
        }
        """
        self.faculty_list = []
        self.faculty_by_dept = {}  # {dept_id: [faculty1, faculty2, ...]}
        self.load_from_csv(faculty_config['source'], faculty_config.get('columns', {}))
    
    def load_from_csv(self, csv_path: str, columns: Dict):
        """从CSV加载教职工库"""
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    employee_id = row.get(columns.get('employee_id', 'employee_id'), '').strip()
                    
                    if not employee_id:
                        continue
                    
                    faculty = {
                        'employee_id': employee_id,
                        'name_zh': row.get(columns.get('name_zh', 'name_zh'), '').strip(),
                        'dept_id': row.get(columns.get('dept_id', 'dept_id'), '').strip().lower(),
                        'name_en': row.get(columns.get('name_en', 'name_en'), '').strip() or None,
                        'email': row.get(columns.get('email', 'email'), '').strip() or None,
                        'position': row.get(columns.get('position', 'position'), '').strip() or None,
                        'research_area': row.get(columns.get('research_area', 'research_area'), '').strip() or None
                    }
                    
                    self.faculty_list.append(faculty)
                    
                    # 按部门索引
                    dept_id = faculty['dept_id']
                    if dept_id not in self.faculty_by_dept:
                        self.faculty_by_dept[dept_id] = []
                    self.faculty_by_dept[dept_id].append(faculty)
            
            print(f"✓ 加载教职工库成功: {len(self.faculty_list)} 人")
            print(f"  涉及部门数: {len(self.faculty_by_dept)}")
        
        except Exception as e:
            print(f"✗ 加载教职工库失败: {e}")
            self.faculty_list = []
            self.faculty_by_dept = {}
    
    def find_in_depts(self, dept_ids: List[str], paper_name: str, 
                      name_threshold: float = 0.7) -> List[Dict]:
        """
        在指定部门中查询教师
        
        参数：
        - dept_ids: 部门ID列表（从DepartmentMatcher获得）
        - paper_name: 论文中的作者名
        - name_threshold: 名字相似度阈值
        
        返回：
        - 候选教师列表（按相似度降序）
        
        示例：
        >>> find_in_depts(['clinical_medicine'], 'Li Si', 0.7)
        [
            {'employee_id': 'E12345', 'name_zh': '李四', 'position': '教授', ...},
            {'employee_id': 'E54321', 'name_zh': '李思', 'position': '副教授', ...}
        ]
        """
        if not dept_ids:
            return []
        
        candidates = []
        
        # 在指定部门中查
        for dept_id in dept_ids:
            faculty_in_dept = self.faculty_by_dept.get(dept_id, [])
            
            for faculty in faculty_in_dept:
                # 计算名字相似度
                name_score = self._name_similarity(paper_name, faculty)
                
                if name_score >= name_threshold:
                    candidates.append({
                        'faculty': faculty,
                        'name_score': name_score,
                        'dept_id': dept_id
                    })
        
        # 按相似度排序
        candidates.sort(key=lambda x: x['name_score'], reverse=True)
        
        # 返回faculty对象列表
        return [c['faculty'] for c in candidates]
    
    def _name_similarity(self, paper_name: str, faculty: Dict) -> float:
        """
        计算论文作者名与教职工名的相似度
        
        考虑：
        1. 中文名完全匹配
        2. 英文名完全匹配
        3. 序列匹配（处理拼写变异）
        """
        paper_name_lower = paper_name.lower().strip()
        
        # 候选名字列表
        candidates = []
        
        # 中文名
        if faculty.get('name_zh'):
            candidates.append(faculty['name_zh'].lower())
        
        # 英文名
        if faculty.get('name_en'):
            candidates.append(faculty['name_en'].lower())
        
        if not candidates:
            return 0.0
        
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
    
    def get_faculty_by_id(self, employee_id: str) -> Optional[Dict]:
        """按工号获取教职工信息"""
        for faculty in self.faculty_list:
            if faculty['employee_id'] == employee_id:
                return faculty
        return None
    
    def get_faculty_in_dept(self, dept_id: str) -> List[Dict]:
        """获取指定部门的所有教职工"""
        return self.faculty_by_dept.get(dept_id.lower(), [])
    
    def get_stats(self) -> Dict:
        """获取教职工库统计信息"""
        return {
            "total_faculty": len(self.faculty_list),
            "total_depts": len(self.faculty_by_dept),
            "with_email": sum(1 for f in self.faculty_list if f.get('email')),
            "with_position": sum(1 for f in self.faculty_list if f.get('position')),
            "with_research_area": sum(1 for f in self.faculty_list if f.get('research_area'))
        }
