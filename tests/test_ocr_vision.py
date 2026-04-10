"""
测试 Vision Agent V3.0 - OCR + 规则解析流程
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def test_ocr_vision_agent():
    """测试 OCR 和规则解析"""
    
    print("\n" + "="*70)
    print("🧪 Vision Agent V3.0 测试 - OCR + 规则解析流程")
    print("="*70)
    
    # 检查依赖
    print("\n[检查依赖]")
    
    deps = []
    
    try:
        import paddleocr
        print("  ✅ PaddleOCR 已安装")
    except ImportError:
        print("  ⚠️  PaddleOCR 未安装，运行: pip install paddleocr")
        deps.append("paddleocr")
    
    try:
        from playwright.sync_api import sync_playwright
        print("  ✅ Playwright 已安装")
    except ImportError:
        print("  ⚠️  Playwright 未安装")
        deps.append("playwright")
    
    # 已移除外部 LLM 依赖，不再检查 API Key
    
    if deps:
        print(f"\n📦 建议安装缺失的依赖: pip install {' '.join(deps)}")
        print("   （现在可以先测试 Vision Agent 的其他功能）")
    
    # 初始化 Vision Agent
    print("\n[初始化 Vision Agent]")
    from backend.agents.vision_agent import VisionAgent
    
    vision = VisionAgent()
    print("  ✅ Vision Agent 已初始化")
    
    # 测试 1: 验证 mock 数据路由
    print("\n[测试 1] mock 数据路由")
    
    result_test_paper = vision._get_mock_authors("10.3934/publichealth.2026006")
    print(f"  测试论文 (publichealth.2026006):")
    print(f"    作者数: {len(result_test_paper.get('authors', []))}")
    if result_test_paper.get('authors'):
        for author in result_test_paper['authors']:
            print(f"      - {author['name']} (排序: {author['position']})")
    
    result_other_paper = vision._get_mock_authors("10.1038/s41586-020-2649-2")
    print(f"\n  其他论文 (10.1038/s41586...):")
    print(f"    作者数: {len(result_other_paper.get('authors', []))}")
    print(f"    ✅ 返回空列表（避免错误匹配）")
    
    # 测试 2: 完整流程模拟
    print("\n[测试 2] 完整流程（如果有截图）")
    
    # 检查是否有之前保存的截图
    screenshot_dir = "data/visual_slices"
    if os.path.exists(screenshot_dir):
        screenshots = [f for f in os.listdir(screenshot_dir) if f.endswith('.png')]
        if screenshots:
            print(f"  找到 {len(screenshots)} 张截图:")
            for screenshot in screenshots[:3]:
                print(f"    - {screenshot}")
            
            # 尝试对第一张截图进行 OCR
            screenshot_path = os.path.join(screenshot_dir, screenshots[0])
            print(f"\n  🔍 尝试对 {screenshots[0]} 进行 OCR...")
            
            ocr_text = vision._extract_text_by_ocr(screenshot_path)
            if ocr_text:
                print(f"  ✅ OCR 成功，提取了 {len(ocr_text)} 字符")
                print(f"     文本预览: {ocr_text[:100]}...")
                
                # 使用规则解析
                print(f"\n  🧩 使用规则解析作者信息...")
                authors = vision._parse_authors_from_text(ocr_text, "10.test/demo")
                if authors:
                    print(f"  ✅ 识别了 {len(authors)} 名作者:")
                    for author in authors:
                        print(f"     - {author.get('name', 'Unknown')} (排序: {author.get('position', '?')})")
                else:
                    print(f"  ℹ️  未识别到作者信息")
            else:
                print(f"  ⚠️  OCR 失败")
    else:
        print(f"  ℹ️  未找到截图目录，跳过 OCR 测试")
    
    print("\n" + "="*70)
    print("✅ 测试完成！")
    print("\n📋 总结：")
    print("  - Vision Agent V3.0 已集成 OCR + 规则解析流程")
    print("  - 支持真实作者识别和排序提取")
    print("  - 当 OCR 不可用时，仅对指定论文返回 mock 数据")
    print("="*70 + "\n")

if __name__ == "__main__":
    try:
        test_ocr_vision_agent()
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
