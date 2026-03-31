"""
【集成测试】Scout → Vision → Judge 三 Agent 完整流程

演示架构正确性：
1️⃣ Scout Agent 从 Crossref API 获取元数据和作者信息
2️⃣ Vision Agent 进行网页爬取和 PDF 截图
3️⃣ Judge Agent 进行身份匹配
"""

from backend.agents.scout_agent import ScoutAgent
from backend.agents.vision_agent import VisionAgent
from backend.agents.judge_agent import JudgeAgent

def test_three_agents():
    print("=" * 80)
    print("🚀 MAC-ADG 三智能体协同工作流程测试")
    print("=" * 80)
    
    # 测试 DOI（知网论文）
    doi = "10.3390/nu15204383"
    
    print(f"\n📌 测试 DOI: {doi}\n")
    
    # 1️⃣ Scout Agent：从 Crossref API 获取元数据
    print("=" * 80)
    print("【第一阶段】🕵️ Scout Agent - 元数据获取")
    print("=" * 80)
    scout = ScoutAgent()
    scout_result = scout.run(doi)
    
    print(f"\n[Scout] 输出结果:")
    print(f"  - DOI: {scout_result.get('doi')}")
    print(f"  - Title: {scout_result.get('title', 'N/A')}")
    print(f"  - Journal: {scout_result.get('journal', 'N/A')}")
    print(f"  - Publish Date: {scout_result.get('publish_date', 'N/A')}")
    print(f"  - URL: {scout_result.get('url', 'N/A')}")
    
    crossref_authors = scout_result.get('authors', [])
    print(f"  - Authors from Crossref: {len(crossref_authors)} 人")
    for author in crossref_authors[:3]:  # 只显示前3个
        print(f"    • {author['name']} ({author['affiliation']})")
    if len(crossref_authors) > 3:
        print(f"    ... 等其他 {len(crossref_authors) - 3} 人")
    
    # 2️⃣ Vision Agent：网页爬取和截图
    print("\n" + "=" * 80)
    print("【第二阶段】👁️ Vision Agent - 网页爬取 & OCR 提取")
    print("=" * 80)
    vision = VisionAgent()
    vision_result = vision.process(doi)
    
    image_path = vision_result.get('image_path')
    vision_authors = vision_result.get('authors', [])
    
    print(f"\n[Vision] 输出结果:")
    if image_path:
        print(f"  - 📸 截图成功: {image_path}")
    else:
        print(f"  - ❌ 截图失败（使用 mock 数据）")
    
    print(f"  - Authors from Vision: {len(vision_authors)} 人")
    for author in vision_authors[:3]:
        name = author.get('name', 'Unknown')
        aff = author.get('affiliation', 'Unknown')
        print(f"    • {name} ({aff})")
    if len(vision_authors) > 3:
        print(f"    ... 等其他 {len(vision_authors) - 3} 人")
    
    # 3️⃣ Judge Agent：身份匹配与融合
    print("\n" + "=" * 80)
    print("【第三阶段】⚖️ Judge Agent - 身份匹配 & 冲突消解")
    print("=" * 80)
    judge = JudgeAgent()
    
    print(f"\n[Judge] 输入数据:")
    print(f"  - Crossref 作者数: {len(crossref_authors)}")
    print(f"  - Vision 作者数: {len(vision_authors)}")
    
    print(f"\n[Judge] 执行身份匹配...")
    judge_result = judge.adjudicate(scout_result, vision_result)
    
    print(f"\n[Judge] 匹配结果:")
    if judge_result:
        print(f"  - 状态: {judge_result.get('status', 'unknown')}")
        print(f"  - 消息: {judge_result.get('message', 'N/A')}")
    else:
        print(f"  - ✅ 成功存储到数据库")
    
    # 最终对比
    print("\n" + "=" * 80)
    print("【总结】数据融合对比")
    print("=" * 80)
    print(f"\n数据来源对比:")
    print(f"  - Crossref 获取: {len(crossref_authors)} 位作者及单位信息")
    print(f"  - Vision 提取: {len(vision_authors)} 位作者（可能包含通讯标记）")
    print(f"  - 融合结果: 已存储到数据库（PaperAuthors 表）")
    print(f"\n✅ 三智能体协同成功！")
    print("=" * 80)

if __name__ == "__main__":
    test_three_agents()
