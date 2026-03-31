"""
【MAC-ADG 重构后的完整流程测试】

新架构：
1️⃣ Scout Agent - 从 Crossref API 获取元数据
2️⃣ WebDriver - 网页导航和截图（独立工具）
3️⃣ Vision Agent - 纯视觉分析（OCR + 结构化提取）
4️⃣ Judge Agent - 身份匹配
"""

import sys
import os

# 添加根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.agents.scout_agent import ScoutAgent
from backend.agents.vision_agent_v2 import VisionAgent
from backend.agents.judge_agent import JudgeAgent
from backend.utils.webdriver import WebDriverAdapter


def test_complete_workflow():
    print("=" * 80)
    print("🚀 MAC-ADG 重构后的完整工作流程")
    print("=" * 80)
    
    # 测试 DOI
    doi = "10.3390/nu15204383"
    
    print(f"\n📌 测试 DOI: {doi}\n")
    
    # 1️⃣ Scout Agent：获取元数据
    print("=" * 80)
    print("【阶段 1/4】🕵️ Scout Agent - 元数据获取")
    print("=" * 80)
    scout = ScoutAgent()
    scout_result = scout.run(doi)
    
    print(f"\n[Scout] 输出结果:")
    print(f"  - DOI: {scout_result.get('doi')}")
    print(f"  - Title: {scout_result.get('title', 'N/A')}")
    print(f"  - Journal: {scout_result.get('journal', 'N/A')}")
    
    crossref_authors = scout_result.get('authors', [])
    print(f"  - Authors from Crossref: {len(crossref_authors)} 人")
    for author in crossref_authors[:3]:
        print(f"    • {author['name']} ({author['affiliation']})")
    if len(crossref_authors) > 3:
        print(f"    ... 等其他 {len(crossref_authors) - 3} 人")
    
    # 2️⃣ WebDriver：获取截图
    print("\n" + "=" * 80)
    print("【阶段 2/4】🌐 WebDriver - 获取截图")
    print("=" * 80)
    webdriver = WebDriverAdapter()
    screenshot_path = webdriver.get_webpage_screenshot(doi)
    
    if screenshot_path:
        print(f"\n[WebDriver] ✅ 截图成功:")
        print(f"  - 文件路径: {screenshot_path}")
        
        # 3️⃣ Vision Agent：分析截图
        print("\n" + "=" * 80)
        print("【阶段 3/4】👁️ Vision Agent - 视觉分析")
        print("=" * 80)
        vision = VisionAgent()
        vision_result = vision.analyze_screenshot(screenshot_path)
        
        vision_text = vision_result.get('text', '')
        vision_authors = vision_result.get('authors', [])
        
        print(f"\n[Vision] 输出结果:")
        print(f"  - 识别文本长度: {len(vision_text)} 字符")
        print(f"  - 提取的作者数: {len(vision_authors)} 位")
        
        for idx, author in enumerate(vision_authors[:5], 1):
            markers = []
            if author.get('is_corresponding'):
                markers.append('通讯作者*')
            if author.get('is_co_first'):
                markers.append('共同一作#')
            marker_str = f" [{', '.join(markers)}]" if markers else ""
            print(f"    {idx}. {author['name']} ({author['affiliation']}){marker_str}")
        
        if len(vision_authors) > 5:
            print(f"    ... 等其他 {len(vision_authors) - 5} 人")
    else:
        print(f"\n[WebDriver] ⚠️ 无法获取截图")
        vision_authors = []
    
    # 4️⃣ Judge Agent：身份匹配
    print("\n" + "=" * 80)
    print("【阶段 4/4】⚖️ Judge Agent - 身份匹配")
    print("=" * 80)
    judge = JudgeAgent()
    
    print(f"\n[Judge] 输入数据对比:")
    print(f"  - Crossref 作者数: {len(crossref_authors)}")
    print(f"  - Vision 作者数: {len(vision_authors)}")
    
    print(f"\n[Judge] 执行身份匹配算法...")
    judge_result = judge.adjudicate(scout_result, {'authors': vision_authors})
    
    print(f"\n[Judge] 匹配结果已存储到数据库")
    
    # 最终总结
    print("\n" + "=" * 80)
    print("【总结】- 数据融合流程")
    print("=" * 80)
    print(f"""
📊 数据流向：
  Crossref API        → Scout Agent        → {len(crossref_authors)} 位作者
  
  网页 + 截图         → WebDriver          → 截图文件
                          ↓
  OCR + VLM            → Vision Agent       → {len(vision_authors)} 位作者（含标记）
                          ↓
  身份匹配             → Judge Agent        → DB 存储

✅ 改进点：
  ✓ Vision Agent 只负责视觉分析（OCR + 结构化）
  ✓ WebDriver 独立处理网页操作
  ✓ Scout Agent 从 API 获取元数据
  ✓ Judge Agent 负责身份匹配
  
🎯 职责清晰，模块化良好！
""")

if __name__ == "__main__":
    test_complete_workflow()
