import os
import time
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync
from config import VISUAL_SLICE_DIR

class VisionAgent:
    """
    [Vision Agent V2.0 - GUI Web Agent]
    Responsibilities:
    1. Navigate to https://doi.org/{doi}
    2. Wait for redirects (Nature, IEEE, Elsevier, etc.)
    3. Take a screenshot of the top viewport (where authors are).
    4. Pass image to VLM (DeepSeek) for author extraction.
    """

    def __init__(self):
        if not os.path.exists(VISUAL_SLICE_DIR):
            os.makedirs(VISUAL_SLICE_DIR)

    def process(self, doi):
        """
        Main entry point for Vision Agent.
        Takes a DOI, drives the browser, and analyzes the screenshot.
        """
        if not doi:
            return {"text": "", "image_path": None}

        print(f"\n[Vision] Initializing Web Driver for DOI: {doi}")
        
        # 1. Capture Screenshot via Browser Automation
        image_path = self._capture_webpage(doi)

        if not image_path:
            return {"text": "", "image_path": None}

        # 2. Extract Data using Multi-Modal LLM (VLM)
        # Note: We will plug in DeepSeek API here later. 
        # For now, we return a mock string so the pipeline can test the image capture.
        extracted_data = self._mock_vlm_analysis(image_path, doi)

        return extracted_data

    def _capture_webpage(self, doi):
        url = f"https://doi.org/{doi}"
        safe_doi = doi.replace('/', '_')
        save_path = os.path.join(VISUAL_SLICE_DIR, f"{safe_doi}.png")

        try:
            with sync_playwright() as p:
                # Launch Chromium headlessly
                browser = p.chromium.launch(headless=True)
                
                # Create a context that looks like a real 1080p desktop browser
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
                )
                page = context.new_page()

                print(f"[Vision] 🌐 Navigating to: {url}")
                # Wait until network is mostly idle to ensure JS frameworks have rendered authors
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                
                # Explicit wait to let complex publisher sites (like ScienceDirect) finish rendering
                page.wait_for_timeout(4000) 

                # Take screenshot of the visible viewport (Top of the page)
                page.screenshot(path=save_path)
                print(f"[Vision] 📸 Screenshot captured: {save_path}")

                browser.close()
                return save_path

        except Exception as e:
            print(f"[Vision] ❌ Browser Automation Error: {e}")
            return None

    def _mock_vlm_analysis(self, image_path, doi):
        """
        Placeholder for DeepSeek-VL API call.
        Once the image is saved, the VLM will "look" at it and return text.
        """
        print(f"[Vision] 🧠 Sending {image_path} to Multi-Modal LLM...")
        
        # TODO: Implement actual DeepSeek API call here in the future
        # prompt = "Please identify the author list and affiliations. Note * for corresponding and # for co-first."
        
        mock_text = f"[MOCK OCR DATA for {doi}] Authors detected in image. Z.P. Liu*, L. Duan#."
        
        return {
            "text": mock_text,
            "image_path": image_path
        }