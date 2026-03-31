"""
Test 3.4.1: Judge Agent 身份匹配测试
执行: python test_judge.py
"""

from database.models import Faculty, Paper, PaperAuthor
from database.connection import SessionLocal, engine
from backend.agents.scout_agent import ScoutAgent
try:
    from backend.agents.vision_agent import VisionAgent
except ImportError:
    # if playwright is missing, provide a dummy VisionAgent for tests
    class VisionAgent:
        def process(self, doi_or_path):
            return {"text": "", "image_path": None}
from backend.agents.judge_agent import JudgeAgent
import json

def test_judge_simple_matching():
    """测试 Judge Agent 的简单字符串匹配"""
    print("\n" + "=" * 60)
    print("Test 3.4.1: Judge Agent 简单匹配")
    print("=" * 60)
    
    # 1. 向数据库插入测试教师
    print("\n[Step 1] 插入测试教师数据...")
    db = SessionLocal()
    
    test_data = [
        {
            "employee_id": "TEST001",
            "name_zh": "刘泽萍",
            "name_en_list": json.dumps(["Zeping Liu", "Z.P. Liu", "Liu Zeping"]),
            "department": "计算机学院"
        },
        {
            "employee_id": "TEST002",
            "name_zh": "王小明",
            "name_en_list": json.dumps(["Xiaoming Wang", "X.M. Wang"]),
            "department": "电气学院"
        }
    ]
    
    for data in test_data:
        existing = db.query(Faculty).filter(Faculty.employee_id == data["employee_id"]).first()
        if not existing:
            faculty = Faculty(**data)
            db.add(faculty)
            print(f"  ✅ 添加教师: {data['name_zh']} ({data['employee_id']})")
    
    db.commit()
    db.close()
    
    # 2. 运行 Scout Agent 获取元数据
    print("\n[Step 2] Scout Agent 获取论文元数据...")
    scout = ScoutAgent()
    doi = "10.1038/s41586-020-2649-2"
    scout_result = scout.run(doi)
    
    print(f"  ✅ 获取元数据: {scout_result['title'][:50]}...")
    print(f"  期刊: {scout_result['journal']}")
    
    # 3. 运行 Vision Agent 提取文本（使用 DOI，自动截图）
    print("\n[Step 3] Vision Agent 提取文本...")
    vision = VisionAgent()
    vision_result = vision.process(doi)
    
    text_len = len(vision_result.get("text", ""))
    print(f"  ✅ 提取文本长度: {text_len} 字符")
    
    # 4. 运行 Judge Agent 进行匹配
    print("\n[Step 4] Judge Agent 进行身份匹配...")
    judge = JudgeAgent()
    success = judge.adjudicate(scout_result, vision_result)
    
    if success:
        print(f"  ✅ adjudicate 返回 True")
    else:
        print(f"  ⚠️  adjudicate 返回 False (可能未匹配到任何教师)")
    
    # 5. 验证数据库
    print("\n[Step 5] 验证数据库写入...")
    db = SessionLocal()
    
    # 查看 Paper 表
    papers = db.query(Paper).filter(Paper.doi == doi).all()
    if papers:
        print(f"  ✅ Paper 表: {len(papers)} 条记录")
        for p in papers:
            print(f"     - DOI: {p.doi}, Status: {p.status}")
    
    # 查看 PaperAuthor 表
    authors = db.query(PaperAuthor).filter(PaperAuthor.paper_doi == doi).all()
    if authors:
        print(f"  ✅ PaperAuthor 表: {len(authors)} 条记录")
        for a in authors:
            matched_faculty = db.query(Faculty).filter(Faculty.id == a.matched_faculty_id).first()
            name = matched_faculty.name_zh if matched_faculty else "未匹配"
            print(f"     - 原始名字: {a.raw_name}")
            print(f"     - 匹配教师: {name}")
            print(f"     - 通讯作者: {a.is_corresponding}, 共同一作: {a.is_co_first}")
            print(f"     - 置信度: {getattr(a, 'confidence_score', 'N/A')}%, 级别: {getattr(a, 'matched_level', 'N/A')}")
    else:
        print(f"  ℹ️  PaperAuthor 表: 0 条记录 (未匹配到教师)")
    
    db.close()
    
    print("\n" + "=" * 60)
    print("✅ Test 3.4.1 完成")
    print("=" * 60)

def test_judge_marker_detection():
    """测试 Judge Agent 对 * # 标记的识别"""
    print("\n" + "=" * 60)
    print("Test 3.4.2: 标记识别 (* #)")
    print("=" * 60)
    
    print("\n[说明] 此测试验证 Judge Agent 能否检测 * (通讯) 和 # (共同一作) 标记")
    print("      由于需要 Vision Agent 从 PDF 提取标记，这部分功能依赖于")
    print("      DeepSeek-VL 集成，目前是基础实现。\n")
    
    # 模拟 vision 数据中包含标记的情况
    from backend.agents.judge_agent import JudgeAgent
    
    scout_data = {
        "doi": "10.test/12345",
        "title": "Test Paper",
        "journal": "Test Journal",
        "publish_date": "2024-01-01"
    }
    
    # 模拟包含标记的视觉数据
    vision_data = {
        "text": "Zeping Liu*, Xiaoming Wang#, Other Author",
        "image_path": None
    }
    
    print("模拟数据:")
    print(f"  论文文本: {vision_data['text']}")
    print("  其中 * 代表通讯作者，# 代表共同一作\n")
    
    judge = JudgeAgent()
    print("[运行] Judge Agent adjudicate...")
    success = judge.adjudicate(scout_data, vision_data)
    print(f"结果: {success}")
    
    print("\n" + "=" * 60)
    print("✅ Test 3.4.2 完成")
    print("=" * 60)

if __name__ == "__main__":
    print("\n" + "🧪 " * 20)
    print("Judge Agent 测试套件")
    print("🧪 " * 20)
    
    try:
        test_judge_simple_matching()
        test_judge_marker_detection()
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
