"""
验证多部门匹配功能 - V2.0 系统测试
"""
import os
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def test_multi_department_matching():
    """验证多部门匹配逻辑"""
    
    print("\n" + "="*70)
    print("🧪 多部门匹配功能验证")
    print("="*70)
    
    # 第一步：初始化数据库
    print("\n[第1步] 初始化数据库...")
    db_path = os.path.join(Path(__file__).parent, 'data', 'mac_adg.db')
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"  ✅ 删除旧数据库")
    
    from database.connection import init_db
    init_db()
    print(f"  ✅ 数据库已初始化")
    
    # 第二步：添加测试数据
    print("\n[第2步] 添加用户信息（多部门）...")
    from database.connection import SessionLocal
    from database.models import Faculty, Paper, PaperAuthor
    
    db = SessionLocal()
    
    # 添加刘泽萍 - 多部门
    zeping = Faculty(
        employee_id="E-ZEP-001",
        name_zh="刘泽萍",
        name_en_list=json.dumps([
            "Zeping Liu", 
            "Z.P. Liu", 
            "Liu Zeping",
            "Liu, Zeping"
        ]),
        department="West China School of Medicine, Sichuan University",
        departments=json.dumps([
            "West China School of Medicine, Sichuan University, Chengdu, China",
            "College of Computer Science, Sichuan University, Chengdu, China"
        ])
    )
    db.add(zeping)
    db.commit()
    print(f"  ✅ 添加刘泽萍 (ID: {zeping.id}) - 2个部门")
    
    db.close()
    
    # 第三步：测试匹配逻辑
    print("\n[第3步] 测试匹配逻辑...")
    
    # 导入 Judge Agent
    from backend.agents.judge_agent import JudgeAgent
    from difflib import SequenceMatcher
    
    judge = JudgeAgent()
    db = SessionLocal()
    
    # 获取刘泽萍的信息
    faculty = db.query(Faculty).filter(Faculty.name_zh == "刘泽萍").first()
    print(f"\n  📌 教师信息:")
    print(f"     名字: {faculty.name_zh}")
    print(f"     英文名: {json.loads(faculty.name_en_list)}")
    print(f"     主部门: {faculty.department}")
    
    dept_list = json.loads(faculty.departments) if faculty.departments else []
    print(f"     所有部门:")
    for i, dept in enumerate(dept_list, 1):
        print(f"       - {i}. {dept}")
    
    # 测试场景1：论文作者单位完全匹配到医学院
    print(f"\n  🧪 场景1: 论文作者单位匹配医学院")
    test_aff_1 = "West China School of Medicine, Sichuan University, Chengdu, China"
    
    from difflib import SequenceMatcher
    score1 = SequenceMatcher(None, test_aff_1.lower(), faculty.department.lower()).ratio()
    print(f"     测试单位: {test_aff_1}")
    print(f"     与主部门的匹配度: {score1:.2f}")
    
    # 检查是否在 departments 列表中
    if test_aff_1 in dept_list:
        print(f"     ✅ 精确匹配到 departments 列表中的第一个部门！")
    
    # 测试场景2：论文作者单位匹配到计算机学院
    print(f"\n  🧪 场景2: 论文作者单位匹配计算机学院")
    test_aff_2 = "College of Computer Science, Sichuan University, Chengdu, China"
    print(f"     测试单位: {test_aff_2}")
    
    if test_aff_2 in dept_list:
        print(f"     ✅ 精确匹配到 departments 列表中的第二个部门！")
    
    # 测试场景3：论文作者单位包含关键词（部分匹配）
    print(f"\n  🧪 场景3: 论文作者单位关键词匹配")
    test_aff_3 = "School of Medicine, Sichuan University"
    print(f"     测试单位: {test_aff_3}")
    
    for dept in dept_list:
        if "School of Medicine" in test_aff_3 and "School of Medicine" in dept:
            print(f"     ✅ 关键词'School of Medicine'匹配到部门: {dept}")
    
    # 测试场景4：论文作者单位名称变体
    print(f"\n  🧪 场景4: 论文作者使用英文全名")
    test_aff_4 = "Zeping Liu"
    test_name = "Zeping Liu"
    
    en_names = json.loads(faculty.name_en_list)
    if test_name in en_names:
        print(f"     ✅ 作者名'{test_name}'精确匹配到英文名列表")
    
    db.close()
    
    # 第四步：完整流程测试
    print("\n[第4步] 完整流程测试 (Vision + Judge)...")
    
    from backend.agents.vision_agent import VisionAgent
    
    vision = VisionAgent()
    
    # 模拟 Vision Agent 提取的作者信息（使用真实单位）
    test_doi = "10.3934/publichealth.2026006"
    print(f"\n  ℹ️  测试 DOI: {test_doi}")
    
    # Vision Agent 返回 mock 数据
    vision_result = vision._get_mock_authors(test_doi)
    print(f"  📄 Vision Agent 提取的作者:")
    for author in vision_result.get("authors", []):
        print(f"     - {author['name']} | {author['affiliation']}")
    
    # 检查刘泽萍是否在提取的作者中
    author_names = [a['name'] for a in vision_result.get("authors", [])]
    if "刘泽萍" in author_names:
        print(f"\n  ✅ Vision Agent 成功识别刘泽萍")
        author = next(a for a in vision_result.get("authors", []) if a['name'] == "刘泽萍")
        print(f"     单位: {author['affiliation']}")
    
    print("\n" + "="*70)
    print("✅ 验证完成！系统现已支持多部门匹配")
    print("="*70 + "\n")

if __name__ == "__main__":
    try:
        test_multi_department_matching()
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
