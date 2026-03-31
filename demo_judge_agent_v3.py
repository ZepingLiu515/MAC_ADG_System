"""
【演示】Judge Agent V3 - 完整的通用身份匹配系统

展示内容：
1. 加载用户的部门库 + 教职工库
2. 处理5篇不同情况的论文
3. 展示单位匹配、Vision调用、名字匹配、消歧的完整流程
4. 输出结果统计和案例分析
"""

from backend.agents.judge_agent_v3 import JudgeAgentV3
import json


def demo_judge_agent_v3():
    """完整演示"""
    
    print("""
    ╔════════════════════════════════════════════════════════════════════╗
    ║      Judge Agent V3 演示 - 通用科研人员身份匹配系统                ║
    ║                                                                    ║
    ║  架构特点：                                                         ║
    ║  ✓ 通用系统（用户上传部门库 + 教职工库）                           ║
    ║  ✓ 智能Vision调用（基于单位置信度决策）                            ║
    ║  ✓ 分层置信度处理（高/中/低自动分类）                              ║
    ║  ✓ 支持人工审核工作流（导出待审查）                                ║
    ╚════════════════════════════════════════════════════════════════════╝
    """)
    
    # 第1步：初始化系统
    print("\n[1] 初始化系统配置...\n")
    
    config = {
        "department_library": {
            "source": "demo_data/departments.csv",
            "columns": {
                "dept_id": "id",
                "dept_name_zh": "name_zh",
                "dept_name_en": "name_en",
                "aliases": "aliases",
                "keywords": "keywords"
            }
        },
        "faculty_library": {
            "source": "demo_data/faculty.csv",
            "columns": {
                "employee_id": "emp_id",
                "name_zh": "name_zh",
                "dept_id": "dept_id",
                "name_en": "name_en",
                "email": "email",
                "position": "position",
                "research_area": "research_area"
            }
        },
        "matching_rules": {
            "unit_match_confidence_threshold": 0.7,
            "equity_mark_confidence_threshold": 0.85,
            "name_match_threshold": 0.7
        },
        "processing_options": {
            "enable_vision_agent": True,
            "export_uncertain_for_review": True
        }
    }
    
    # 注意：这里使用相对路径，实际需要的CSV文件
    # 由于演示环境可能没有这些文件，下面会用模拟数据
    
    try:
        judge = JudgeAgentV3(config)
    except Exception as e:
        print(f"[!] 无法加载真实数据（{e}），使用演示数据...")
        judge = create_demo_judge_agent()
    
    # 第2步：处理5篇论文（模拟数据）
    print("\n[2] 处理论文样本...\n")
    
    papers = [
        {
            "name": "论文1：本校作者，单位清楚，唯一匹配",
            "data": {
                "doi": "10.1111/paper-1",
                "title": "Clinical Study at Southwest Medical University",
                "authors": [
                    {
                        "name": "李四",
                        "affiliation": "Southwest Medical University, School of Clinical Medicine",
                        "order": 1
                    }
                ]
            }
        },
        {
            "name": "论文2：本校作者，单位拼写错误",
            "data": {
                "doi": "10.1111/paper-2",
                "title": "Medical research at Sicuan Univ",  # 拼写错 Sichuan
                "authors": [
                    {
                        "name": "张三",
                        "affiliation": "Sicuan UniversityMedical School",  # 拼写错
                        "order": 1
                    }
                ]
            }
        },
        {
            "name": "论文3：非本校作者，单位完全不匹配",
            "data": {
                "doi": "10.1111/paper-3",
                "title": "Research at Harvard",
                "authors": [
                    {
                        "name": "John Smith",
                        "affiliation": "Harvard Medical School",
                        "order": 1
                    }
                ]
            }
        },
        {
            "name": "论文4：本校同名作者多个（需要审核）",
            "data": {
                "doi": "10.1111/paper-4",
                "title": "Multi-center Study",
                "authors": [
                    {
                        "name": "王五",  # 假设教职工库有多个王五在临床学院
                        "affiliation": "School of Clinical Medicine, Sichuan University",
                        "order": 1
                    }
                ]
            }
        },
        {
            "name": "论文5：单位模糊（Vision需要决策是否调用）",
            "data": {
                "doi": "10.1111/paper-5",
                "title": "Research Paper",
                "authors": [
                    {
                        "name": "赵六",
                        "affiliation": "Medical Research Institute",  # 模糊单位
                        "order": 1
                    }
                ]
            }
        }
    ]
    
    # 处理论文
    results = []
    for paper_info in papers:
        print(f"\n{'='*70}")
        print(f"📄 {paper_info['name']}")
        print(f"{'='*70}")
        
        result = judge.process_paper(paper_info['data'])
        results.append(result)
        
        # 显示结果摘要
        print(f"\n结果摘要:")
        print(f"  状态: {result['status'].upper()}")
        print(f"  已确认: {len(result['confirmed_authors'])} 位")
        print(f"  待审核: {len(result['review_authors'])} 位")
        print(f"  未匹配: {len(result['unmatched_authors'])} 位")
        print(f"  Vision调用: {'是' if result['vision_called'] else '否'}")
        
        if result['confirmed_authors']:
            print(f"\n  ✅ 已确认作者:")
            for author in result['confirmed_authors']:
                print(f"     - {author['paper_author']['name']} "
                      f"→ {author['matched_faculty']['name_zh']}")
        
        if result['review_authors']:
            print(f"\n  ⚠️ 需要审核:")
            for item in result['review_authors']:
                print(f"     - {item['paper_author']['name']} 有 {len(item['candidates'])} 个候选")
        
        if result['unmatched_authors']:
            print(f"\n  ❌ 未匹配:")
            for author in result['unmatched_authors']:
                print(f"     - {author['name']} ({author['reason']})")
    
    # 第3步：统计总结
    print(f"\n{'='*70}")
    print("📊 处理统计总结")
    print(f"{'='*70}\n")
    
    stats = judge.get_stats()
    
    print(f"总体统计:")
    print(f"  处理论文数: {stats['total_papers']}")
    print(f"  已确认作者: {stats['confirmed_matches']} 位")
    print(f"  待审核作者: {stats['needs_review']} 位")
    print(f"  处理失败: {stats['failed']} 篇")
    print(f"  Vision调用次数: {stats['vision_calls']} 次")
    print(f"\n部门库统计:")
    for k, v in stats['dept_matcher_stats'].items():
        print(f"  {k}: {v}")
    print(f"\n教职工库统计:")
    for k, v in stats['faculty_matcher_stats'].items():
        print(f"  {k}: {v}")
    
    # 第4步：关键指标分析
    print(f"\n{'='*70}")
    print("🎯 关键性能指标分析")
    print(f"{'='*70}\n")
    
    total_authors = sum(
        len(r['confirmed_authors']) + 
        len(r['review_authors']) + 
        len(r['unmatched_authors'])
        for r in results
    )
    
    total_matched = sum(
        len(r['confirmed_authors']) + len(r['review_authors'])
        for r in results
    )
    
    match_rate = (total_matched / total_authors * 100) if total_authors > 0 else 0
    
    print(f"匹配率: {match_rate:.1f}% ({total_matched}/{total_authors})")
    print(f"Vision节省: {100 - (stats['vision_calls'] / stats['total_papers'] * 100):.1f}% 的调用被节省")
    print(f"  - 原来: 每篇论文都调用Vision → {stats['total_papers']}次")
    print(f"  - 现在: 仅在单位置信度足够时调用 → {stats['vision_calls']}次")
    
    print(f"\n审核工作量: {stats['needs_review']} 位作者需要人工审核")
    print(f"  占比: {(stats['needs_review'] / (stats['confirmed_matches'] + stats['needs_review']) * 100) if (stats['confirmed_matches'] + stats['needs_review']) > 0 else 0:.1f}%")
    
    print(f"\n数据质量:")
    print(f"  高置信度（已自动确认）: {stats['confirmed_matches']} 位 ({(stats['confirmed_matches'] / (stats['confirmed_matches'] + stats['needs_review']) * 100) if (stats['confirmed_matches'] + stats['needs_review']) > 0 else 0:.1f}%)")
    print(f"  中等置信度（待人工审核）: {stats['needs_review']} 位")
    print(f"  → 系统诚实、可信、支持人工控制")
    
    print(f"\n{'='*70}\n")


def create_demo_judge_agent():
    """
    创建演示用的Judge Agent（模拟数据）
    """
    # 创建模拟的matchers
    class MockDepartmentMatcher:
        def match_affiliation(self, aff):
            if 'harvard' in aff.lower():
                return []  # 不是本校
            elif 'sichuan' in aff.lower() or 'sicuan' in aff.lower():
                return [('clinical', 0.75), ('medical', 0.65)]
            elif 'southwest' in aff.lower():
                return [('clinical', 0.95)]
            else:
                return [('unknown', 0.3)]
        
        def get_all_depts(self):
            return [
                {'dept_id': 'clinical', 'name_zh': '临床医学院'},
                {'dept_id': 'medical', 'name_zh': '基础医学系'}
            ]
        
        def get_stats(self):
            return {'total_departments': 2, 'with_aliases': 1, 'with_keywords': 2}
    
    class MockFacultyMatcher:
        def find_in_depts(self, depts, name, threshold):
            if '王五' in name:
                return [
                    {'employee_id': 'E001', 'name_zh': '王五', 'position': '教授'},
                    {'employee_id': 'E002', 'name_zh': '王五', 'position': '讲师'}
                ]
            else:
                return [{'employee_id': 'E123', 'name_zh': name, 'position': '副教授'}]
        
        def get_stats(self):
            return {'total_faculty': 150, 'total_depts': 10, 'with_email': 140}
    
    judge = type('MockJudge', (), {})()
    judge.dept_matcher = MockDepartmentMatcher()
    judge.faculty_matcher = MockFacultyMatcher()
    judge.unit_confidence_threshold = 0.7
    judge.equity_confidence_threshold = 0.85
    judge.name_threshold = 0.7
    judge.enable_vision = True
    judge.stats = {
        'total_papers': 0,
        'confirmed_matches': 0,
        'needs_review': 0,
        'failed': 0,
        'vision_calls': 0
    }
    
    # 绑定方法
    from types import MethodType
    judge.process_paper = MethodType(JudgeAgentV3.process_paper, judge)
    judge._extract_author_vision_marks = MethodType(JudgeAgentV3._extract_author_vision_marks, judge)
    judge._build_match_result = MethodType(JudgeAgentV3._build_match_result, judge)
    judge.get_stats = MethodType(JudgeAgentV3.get_stats, judge)
    
    return judge


if __name__ == "__main__":
    demo_judge_agent_v3()
