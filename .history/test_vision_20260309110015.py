from backend.agents.vision_agent import VisionAgent
from backend.agents.scout_agent import ScoutAgent
import os

def test_vision():
    print("--- Testing Vision Agent ---")
    
    # 1. First, we need a file. Let's ask Scout to fetch one (or use cached).
    print("Step 1: Scout getting a file...")
    scout = ScoutAgent()
    # Use a DOI we know works (Nature paper)
    doi = "10.1038/s41586-020-2649-2" 
    scout_result = scout.run(doi)
    
    file_path = scout_result.get("pdf_path") or scout_result.get("html_path")
    
    if not file_path:
        print("❌ Scout failed to get file. Cannot test Vision.")
        return

    print(f"✅ File ready: {file_path}")

    # 2. Now Test Vision
    print("\nStep 2: Vision Agent processing...")
    vision = VisionAgent()
    vision_result = vision.process(file_path)
    
    # 3. Check Text
    text = vision_result["text"]
    print(f"\n[Extracted Text Preview]: {text[:200]}...") # Print first 200 chars
    
    if len(text) > 50:
        print("✅ Text Extraction: PASS")
    else:
        print("❌ Text Extraction: FAIL (Too short)")

    # 4. Check Image (Only for PDF)
    img = vision_result["image_path"]
    if img and os.path.exists(img):
        print(f"✅ Image Snapshot: PASS ({img})")
    else:
        if file_path.endswith(".pdf"):
            print("❌ Image Snapshot: FAIL")
        else:
            print("ℹ️ No image for HTML (Expected)")

if __name__ == "__main__":
    test_vision()