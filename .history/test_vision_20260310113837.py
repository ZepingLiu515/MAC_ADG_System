import os
from backend.agents.vision_agent import VisionAgent

def test_web_vision():
    print("--- 🚀 Testing Web GUI Vision Agent (with Stealth) ---")
    
    # 初始化视觉智能体
    vision = VisionAgent()
    
    # 准备两个测试靶标
    # 靶标 1: Nature (相对容易，重定向快)
    doi_1 = "10.1038/s41586-020-2649-2"
    # 靶标 2: Science 或 IEEE (有时会有简单的防爬虫拦截)
    doi_2 = "10.1126/science.1257601"
    
    test_dois = [doi_1, doi_2]
    
    for doi in test_dois:
        print(f"\n🎯 [Target Locked]: {doi}")
        
        # 呼叫 Vision Agent 执行任务
        result = vision.process(doi)
        
        # 检查结果
        image_path = result.get("image_path")
        
        if image_path and os.path.exists(image_path):
            print(f"✅ [SUCCESS]: 成功穿透防护并截图！")
            print(f"📂 [File Saved]: {image_path}")
        else:
            print(f"❌ [FAILED]: 截图失败，可能被强力拦截或网络超时。")
            
    print("\n🎉 测试结束，请去 data/visual_slices/ 文件夹验收战果！")

if __name__ == "__main__":
    test_web_vision()