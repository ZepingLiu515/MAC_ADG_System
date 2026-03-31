import os
from backend.agents.vision_agent import VisionAgent

def test_web_vision():
    print("--- 🚀 Testing Web GUI Vision Agent (with Stealth) ---")
    print("[DEBUG] 仅测试 doi_2: CNKI 论文")
    
    # 初始化视觉智能体
    vision = VisionAgent()
    
    # 仅测试 doi_2
    doi_2 = "10.3390/nu15204383"
    
    test_dois = [doi_2]
    screenshot_count = 0
    authors_count = 0
    
    for doi in test_dois:
        print(f"\n🎯 [Target Locked]: {doi}")
        
        # 呼叫 Vision Agent 执行任务
        result = vision.process(doi)
        
        # 分别检查截图和作者识别
        image_path = result.get("image_path")
        authors = result.get("authors", [])
        
        # 检查截图
        if image_path and os.path.exists(image_path):
            print(f"✅ [SCREENSHOT]: 截图成功！")
            print(f"📂 [File Saved]: {image_path}")
            screenshot_count += 1
        else:
            print(f"❌ [SCREENSHOT]: 截图失败")
        
        # 检查作者识别
        if authors and len(authors) > 0 and authors[0].get("name") != "Unknown Author":
            print(f"✅ [OCR]: 成功识别 {len(authors)} 位作者")
            print(f"   第一作者: {authors[0].get('name', 'N/A')}")
            authors_count += 1
        else:
            print(f"⚠️ [OCR]: 使用 Mock 作者数据（OCR 或 API 失败）")
            
    print(f"\n🎉 测试完成！")
    print(f"📊 统计:")
    print(f"   ✅ 截图成功: {screenshot_count}/{len(test_dois)}")
    print(f"   ✅ 作者识别: {authors_count}/{len(test_dois)}")
    print(f"   📂 请去 data/visual_slices/ 文件夹查看截图!")

if __name__ == "__main__":
    test_web_vision()