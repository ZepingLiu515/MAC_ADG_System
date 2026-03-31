"""
【演示】Judge Agent 优化流程 - 快速、准确、无浪费

场景：批量处理100篇论文
- 30篇论文有学校作者 → 需要调用Vision (30次)
- 70篇论文无学校作者 → 直接跳过，不调用Vision ✅ 省70次调用！

原来的流程：每篇都调用Vision → 100次调用
优化后的流程：只调用必要的Vision → 30次调用
性能提升：70%的Vision调用被省略 🚀
"""

from typing import List, Dict

# ============ 模型数据 ============

# 1️⃣ 学校部门列表（从数据库获取）
SCHOOL_DEPARTMENTS = [
    "西南医科大学",
    "西南医科大学 基础医学院",
    "西南医科大学 临床医学院",
    "西南医科大学 计算机学院",
    "西南医科大学 附属医院",
    "Sichuan University",
    "Southwest Medical University",
]

# 2️⃣ 论文样本数据
PAPERS = [
    {
        "doi": "10.1234/paper-1",
        "title": "COVID-19 Research at SWMU",
        "crossref_authors": [
            {"name": "张三", "affiliation": "西南医科大学 基础医学院", "order": 1},
            {"name": "李四", "affiliation": "西南医科大学 临床医学院", "order": 2},
        ],
        "expected_result": "✅ 有学校单位 → 应该调用Vision"
    },
    {
        "doi": "10.1234/paper-2",
        "title": "Machine Learning Study at MIT",
        "crossref_authors": [
            {"name": "John Smith", "affiliation": "MIT", "order": 1},
            {"name": "Jane Doe", "affiliation": "Stanford", "order": 2},
        ],
        "expected_result": "❌ 无学校单位 → 不调用Vision（省略）"
    },
    {
        "doi": "10.1234/paper-3",
        "title": "Medical Research with International Collaboration",
        "crossref_authors": [
            {"name": "王五", "affiliation": "Southwest Medical University", "order": 1},
            {"name": "赵六", "affiliation": "Harvard", "order": 2},
        ],
        "expected_result": "✅ 有学校单位 → 应该调用Vision"
    },
    {
        "doi": "10.1234/paper-4",
        "title": "Physics Study",
        "crossref_authors": [
            {"name": "Peter Brown", "affiliation": "Oxford University", "order": 1},
        ],
        "expected_result": "❌ 无学校单位 → 不调用Vision（省略）"
    },
    {
        "doi": "10.1234/paper-5",
        "title": "Computational Biology at SWMU",
        "crossref_authors": [
            {"name": "孙七", "affiliation": "西南医科大学 计算机学院", "order": 1},
            {"name": "周八", "affiliation": "西南医科大学 附属医院", "order": 2},
        ],
        "expected_result": "✅ 有学校单位 → 应该调用Vision"
    },
]


# ============ 优化后的判断逻辑 ============

def has_school_affiliation(crossref_authors: List[dict], school_depts: List[str]) -> bool:
    """
    【快速筛选】检查是否有学校单位
    
    用途：在调用Vision前快速决定"是否需要调用"
    """
    if not crossref_authors or not school_depts:
        return False
    
    for author in crossref_authors:
        aff = author.get('affiliation', '').lower().strip()
        
        if not aff:
            continue
        
        # 精确匹配
        for school_dept in school_depts:
            if school_dept.lower() in aff or aff in school_dept.lower():
                return True
    
    return False


def judge_agent_optimized_flow(paper: Dict, school_depts: List[str]):
    """
    Judge Agent 优化流程演示
    """
    doi = paper['doi']
    crossref_authors = paper['crossref_authors']
    
    print(f"\n{'='*70}")
    print(f"📄 论文: {doi}")
    print(f"标题: {paper['title'][:50]}...")
    print(f"Crossref 作者数: {len(crossref_authors)}")
    
    # 【关键步骤】快速筛选
    has_school = has_school_affiliation(crossref_authors, school_depts)
    
    # 显示结果
    print(f"\n【筛选结果】")
    for idx, author in enumerate(crossref_authors, 1):
        print(f"  {idx}. {author['name']} @ {author['affiliation']}")
    
    print(f"\n【决策】")
    if has_school:
        print(f"✅ 检测到学校单位")
        print(f"→ 调用 Vision Agent 提取权益标记")
        print(f"→ 调用 Match 进行身份匹配")
        vision_call_needed = True
    else:
        print(f"❌ 无学校单位")
        print(f"→ ⏭️  跳过本论文（不调用Vision）")
        vision_call_needed = False
    
    print(f"\n【预期结果】{paper['expected_result']}")
    
    return {
        'doi': doi,
        'vision_needed': vision_call_needed,
        'author_count': len(crossref_authors)
    }


# ============ 批处理模拟 ============

def batch_processing_simulation():
    """
    模拟批量处理100篇论文
    """
    print("""
    
╔════════════════════════════════════════════════════════════════════╗
║       Judge Agent 优化流程演示                                     ║
║       场景：批量处理5篇论文样本                                     ║
╚════════════════════════════════════════════════════════════════════╝
    """)
    
    vision_called = 0
    vision_skipped = 0
    
    for paper in PAPERS:
        result = judge_agent_optimized_flow(paper, SCHOOL_DEPARTMENTS)
        
        if result['vision_needed']:
            vision_called += 1
        else:
            vision_skipped += 1
    
    # 统计
    total_papers = len(PAPERS)
    print(f"\n{'='*70}")
    print(f"📊 【批处理统计】")
    print(f"  总论文数: {total_papers} 篇")
    print(f"  ✅ 需要Vision: {vision_called} 篇 ({vision_called/total_papers*100:.1f}%)")
    print(f"  ⏭️  跳过Vision: {vision_skipped} 篇 ({vision_skipped/total_papers*100:.1f}%)")
    print(f"\n🚀 【性能提升】")
    print(f"  原来: 每篇都调用 Vision → {total_papers * 1} 次 Vision 调用")
    print(f"  优化: 只在需要时调用 → {vision_called * 1} 次 Vision 调用")
    print(f"  节省: {vision_skipped} 次无谓的 Vision 调用 (节省 {vision_skipped/total_papers*100:.0f}%)")
    print(f"  效率提升: {(1 - vision_called/total_papers) * 100:.0f}%")
    

# ============ 性能对比 ============

def performance_comparison():
    """
    展示性能对比
    """
    print(f"\n{'='*70}")
    print(f"⚡ 【性能对比】")
    print(f"{'='*70}")
    
    # 假设Vision调用平均耗时2秒
    VISION_TIME = 2.0
    
    # 实际场景：1000篇论文，30%有学校单位
    total_papers = 1000
    school_rate = 0.30
    school_papers = int(total_papers * school_rate)
    non_school_papers = total_papers - school_papers
    
    # 原方法：全部调用Vision
    old_time = total_papers * VISION_TIME
    
    # 优化后：只调用需要的Vision
    new_time = school_papers * VISION_TIME
    
    time_saved = old_time - new_time
    
    print(f"\n场景：处理 {total_papers} 篇论文（{school_rate*100:.0f}% 有学校单位）")
    print(f"假设：每次 Vision 调用耗时 {VISION_TIME} 秒")
    print(f"\n📌 原方法（每篇都调用Vision）:")
    print(f"   Vision 调用次数: {total_papers}")
    print(f"   总耗时: {old_time:.0f} 秒 ({old_time/60:.1f} 分钟)")
    print(f"\n✨ 优化方法（快速筛选）:")
    print(f"   Vision 调用次数: {school_papers}")
    print(f"   总耗时: {new_time:.0f} 秒 ({new_time/60:.1f} 分钟)")
    print(f"\n🚀 提升效果:")
    print(f"   省略调用: {non_school_papers} 次")
    print(f"   节省时间: {time_saved:.0f} 秒 ({time_saved/60:.1f} 分钟 / 约{time_saved/3600:.2f} 小时)")
    print(f"   效率提升: {(time_saved/old_time)*100:.0f}%")
    print(f"\n💡 结论: 用快速筛选代替盲目调用，省时 {(1-school_rate)*100:.0f}%！")


if __name__ == "__main__":
    batch_processing_simulation()
    performance_comparison()
    print(f"\n{'='*70}\n")
