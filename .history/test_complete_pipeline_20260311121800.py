"""
端到端集成测试：验证完整的 Scout -> Vision -> Judge 流水线
执行: python test_complete_pipeline.py
"""

from backend.orchestrator import Orchestrator
from database.connection import SessionLocal
from database.models import Paper, Faculty, PaperAuthor
import json
from datetime import datetime
from backend.orchestrator import Orchestrator; print('Import successful')

def print_section(title):
    """打印分隔符"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def test_complete_pipeline():
    """完整端到端验证"""
    
    print_section("🧪 端到端集成测试")
    
    # 第一步：准备测试数据
    print("\n[1️⃣  准备阶段] 设置测试环境")
    print("-" * 70)
    
    # 插入测试教师
    db = SessionLocal()
    test_faculty_id = None
    
    existing = db.query(Faculty).filter(Faculty.employee_id == "E-TEST-2024").first()
    if not existing:
        test_faculty = Faculty(
            employee_id="E-TEST-2024",
            name_zh="测试教师",
            name_en_list=json.dumps(["Test Faculty" , "T.F.", "Faculty Test"]),
            department="测试学院"
        )
        db.add(test_faculty)
        db.commit()
        test_faculty_id = test_faculty.id
        print("  ✅ 插入测试教师: 测试教师 (E-TEST-2024)")
    else:
        test_faculty_id = existing.id
        print("  ℹ️  测试教师已存在: 测试教师 (E-TEST-2024)")
    
    db.close()
    
    # 第二步：选择测试 DOI
    print("\n[2️⃣  采样阶段] 选择测试 DOI")
    print("-" * 70)
    
    # 使用真实存在的开放获取论文
    test_dois = [
        "10.1038/s41586-020-2649-2",  # Nature - Event Horizon Telescope
        "10.3934/publichealth.2026006",  # Public Health (如果可用)
    ]
    
    print(f"  测试 DOI 列表:")
    for doi in test_dois:
        print(f"    - {doi}")
    
    # 第三步：初始化 Orchestrator
    print("\n[3️⃣  初始化] 创建 Orchestrator")
    print("-" * 70)
    
    try:
        orchestrator = Orchestrator()
        print("  ✅ Orchestrator 创建成功")
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        return
    
    # 第四步：运行流水线
    print("\n[4️⃣  执行] 运行 Scout → Vision → Judge 流水线")
    print("-" * 70)
    
    start_time = datetime.now()
    results = orchestrator.process_dois(test_dois)
    elapsed = (datetime.now() - start_time).total_seconds()
    
    print(f"  ✅ 流水线执行完成 (耗时: {elapsed:.2f} 秒)")
    
    # 第五步：分析结果
    print("\n[5️⃣  分析] 结果汇总")
    print("-" * 70)
    
    for idx, result in enumerate(results, 1):
        doi = result.get("doi")
        status = result.get("status")
        title = result.get("title", "N/A")
        journal = result.get("journal", "N/A")
        
        status_emoji = {
            "success_pdf": "📄",
            "success_html": "🌐",
            "metadata_only": "📋",
            "error": "❌",
            "failed": "❌"
        }.get(status, "❓")
        
        print(f"\n  {idx}. {status_emoji} {doi}")
        print(f"     标题: {title[:60]}{'...' if len(title) > 60 else ''}")
        print(f"     期刊: {journal}")
        print(f"     状态: {status}")
        
        if "vision_text_length" in result:
            print(f"     提取文本: {result['vision_text_length']} 字符")
        
        if "error" in result:
            print(f"     错误: {result['error']}")
    
    # 第六步：数据库验证
    print("\n[6️⃣  验证] 数据库状态")
    print("-" * 70)
    
    db = SessionLocal()
    
    # 统计 Papers 表
    paper_count = db.query(Paper).count()
    print(f"  Papers 表总记录数: {paper_count}")
    
    # 统计此流水线处理的论文
    processed_dois = [r.get("doi") for r in results]
    processed_papers = db.query(Paper).filter(Paper.doi.in_(processed_dois)).count()
    print(f"  本次处理的论文: {processed_papers} 篇")
    
    # 统计 PaperAuthor 表
    author_count = db.query(PaperAuthor).count()
    print(f"  PaperAuthor 表总记录数: {author_count}")
    
    # 统计匹配到的教师
    matched_records = db.query(PaperAuthor).filter(
        PaperAuthor.paper_doi.in_(processed_dois)
    ).all()
    matched_faculty_ids = set(r.matched_faculty_id for r in matched_records if r.matched_faculty_id)
    print(f"  本次匹配的教师: {len(matched_faculty_ids)} 人")
    
    # 统计标记识别
    corresponding_count = sum(1 for r in matched_records if r.is_corresponding)
    cofirst_count = sum(1 for r in matched_records if r.is_co_first)
    print(f"  通讯作者标记: {corresponding_count} 条")
    print(f"  共同一作标记: {cofirst_count} 条")
    
    # 第七步：性能指标
    print("\n[7️⃣  性能] 关键指标")
    print("-" * 70)
    
    success_count = sum(1 for r in results if r.get("status") != "error")
    success_rate = 100 * success_count / len(results) if results else 0
    avg_time_per_doi = elapsed / len(results) if results else 0
    
    print(f"  成功率: {success_rate:.1f}% ({success_count}/{len(results)})")
    print(f"  平均时间/DOI: {avg_time_per_doi:.2f} 秒")
    print(f"  总耗时: {elapsed:.2f} 秒")
    
    # 第八步：最终验证
    print("\n[8️⃣  检查清单]")
    print("-" * 70)
    
    checks = [
        ("Scout Agent 功能", results and any(r.get("status") != "error" for r in results)),
        ("Vision Agent 功能", results and any("vision_text_length" in r and r["vision_text_length"] > 0 for r in results)),
        ("Judge Agent 功能", author_count > 0),
        ("数据库写入", paper_count > 0),
        ("批量处理", len(results) >= len(test_dois)),
        ("错误隔离", success_count > 0 or all("error" in r for r in results)),
    ]
    
    all_pass = True
    for check_name, result in checks:
        status = "✅" if result else "❌"
        print(f"  {status} {check_name}")
        if not result:
            all_pass = False
    
    db.close()
    
    # 最终总结
    print("\n" + "=" * 70)
    if all_pass and success_count > 0:
        print("  🎉 端到端集成测试全部通过!")
    else:
        print("  ⚠️  部分检查未通过，请查看上面的详细信息")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    try:
        test_complete_pipeline()
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
    except Exception as e:
        print(f"\n\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
