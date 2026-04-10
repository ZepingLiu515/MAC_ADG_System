"""
【Judge Agent 身份匹配演示】

演示完整的身份匹配流程：
1. Scout Agent 获取 Crossref 作者
2. Vision Agent 提取视觉作者
3. Judge Agent 执行身份匹配
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.agents.scout_agent import ScoutAgent
from backend.agents.vision_agent import VisionAgent
from backend.agents.judge_agent import JudgeAgent
from database.models import Faculty
from database.connection import get_db


def test_judge_matching():
    print("=" * 80)
    print("🔍 Judge Agent 身份匹配完整演示")
    print("=" * 80)
    
    # 测试数据
    test_doi = "10.3390/nu15204383"
    
    # 1️⃣ Scout Agent 获取 Crossref 数据
    print("\n【第 1 步】Scout Agent - 获取 Crossref 数据")
    print("-" * 80)
    scout = ScoutAgent()
    scout_result = scout.run(test_doi)
    
    authors = scout_result.get('authors', [])
    print(f"\n获取到 {len(authors)} 位作者:\n")
    for idx, author in enumerate(authors[:3], 1):
        print(f"{idx}. {author['name']}")
        print(f"   单位: {author['affiliation']}\n")
    if len(authors) > 3:
        print(f"... 等其他 {len(authors) - 3} 位作者\n")
    
    # 2️⃣ 初始化示例教师数据（演示用）
    print("\n【第 2 步】初始化本校教师数据（演示）")
    print("-" * 80)
    
    db = next(get_db())
    
    # 检查是否已有教师数据
    existing_faculty = db.query(Faculty).count()
    print(f"当前数据库中有 {existing_faculty} 位教师\n")
    
    if existing_faculty == 0:
        print("⚠️ 数据库中没有教师数据，创建示例教师...")
        
        # 创建示例教师（用于演示）
        sample_faculties = [
            Faculty(
                employee_id="STU001",
                name_zh="刘泽萍",
                name_en_json='["Liu Zeping", "Z.P. Liu", "Zeping Liu"]',
                department="计算机学院",
                departments='["计算机学院", "School of Computer Science"]'
            ),
            Faculty(
                employee_id="STU002",
                name_zh="张三",
                name_en_json='["Zhang San", "S. Zhang"]',
                department="电子信息学院",
                departments='["电子信息学院", "School of Electronics"]'
            ),
            Faculty(
                employee_id="STU003",
                name_zh="李四",
                name_en_json='["Li Si", "S. Li"]',
                department="数学学院",
                departments='["数学学院", "School of Mathematics"]'
            ),
        ]
        
        for faculty in sample_faculties:
            db.add(faculty)
        
        db.commit()
        print("✅ 示例教师数据已创建\n")
    
    # 3️⃣ Judge Agent 执行身份匹配
    print("\n【第 3 步】Judge Agent - 执行身份匹配")
    print("-" * 80)
    
    judge = JudgeAgent()
    
    # Mock Vision 数据（可以为空，Judge 会使用 Crossref 数据）
    mock_vision_data = {
        'text': 'Mock extracted text',
        'authors': []  # Crossref 数据会被使用
    }
    
    judge_result = judge.adjudicate(scout_result, mock_vision_data)
    
    if judge_result:
        print(f"\n✅ 匹配完成!")
        print(f"   总作者数: {judge_result['total_authors']}")
        print(f"   匹配数: {judge_result['matched_authors']}")
    else:
        print("\n⚠️ 匹配过程中出错")
    
    # 4️⃣ 查看匹配结果
    print("\n【第 4 步】查看数据库中的匹配结果")
    print("-" * 80)
    
    from database.models import Paper, PaperAuthor
    
    paper = db.query(Paper).filter(Paper.doi == test_doi).first()
    if paper:
        print(f"\n论文: {paper.title}")
        print(f"DOI: {paper.doi}")
        print(f"状态: {paper.status}\n")
        
        paper_authors = db.query(PaperAuthor).filter(
            PaperAuthor.paper_doi == test_doi
        ).all()
        
        print(f"作者匹配结果 ({len(paper_authors)} 条记录):\n")
        for pa in paper_authors[:5]:
            status = "✅ 已匹配" if pa.matched_faculty_id else "⚠️ 未匹配"
            print(f"{pa.rank}. {pa.author_name} {status}")
            if pa.matched_faculty_id:
                faculty = db.query(Faculty).filter(
                    Faculty.employee_id == pa.matched_faculty_id
                ).first()
                if faculty:
                    print(f"   → {faculty.name_zh} ({faculty.department})")
                    print(f"   📊 置信度: {pa.confidence_score:.2%}")
            print()
        
        if len(paper_authors) > 5:
            print(f"... 等其他 {len(paper_authors) - 5} 位作者\n")
    
    # 5️⃣ 总结
    print("\n" + "=" * 80)
    print("【总结】Judge Agent 的作用")
    print("=" * 80)
    print("""
📊 身份匹配算法：
  1. 名字相似度计算（Fuzzy Matching）
     - 精确匹配: 100%
     - 包含匹配: 90%
     - 序列匹配: 70-90%
  
  2. 单位相似度计算
     - 精确匹配: 100%
     - 包含匹配: 90%
     - 关键词重叠: 50-80%
  
  3. 综合置信度
     - 公式: 名字得分 × 70% + 单位得分 × 30%
     - 阈值: 75% 以上才认为匹配

🎯 特性：
  ✓ 处理英文名缩写（Z.P. Liu → Zeping Liu）
  ✓ 处理单位翻译差异（School of XX → XX学院）
  ✓ 识别通讯作者和共同一作标记
  ✓ 生成置信度评分

💾 输出：
  - PaperAuthor 表记录每个作者的匹配结果
  - matched_faculty_id: 匹配的教师工号
  - confidence_score: 匹配置信度
  - is_corresponding/is_co_first: 权益标记
""")
    
    db.close()


if __name__ == "__main__":
    test_judge_matching()
