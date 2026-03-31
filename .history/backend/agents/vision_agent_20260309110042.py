import fitz  # PyMuPDF
import os
import re
from config import VISUAL_SLICE_DIR

class VisionAgent:
    """
    [Vision Agent]
    Responsibilities:
    1. Read PDF/HTML files extracted by Scout Agent.
    2. Extract raw text for the Judge Agent.
    3. Generate a visual snapshot (image) of the first page for evidence.
    """

    def __init__(self):
        # Ensure the output directory for images exists
        if not os.path.exists(VISUAL_SLICE_DIR):
            os.makedirs(VISUAL_SLICE_DIR)

    def process(self, file_path):
        """
        Main entry: Detect file type and process.
        Returns: { "text": str, "image_path": str }
        """
        if not file_path:
            # Handle metadata_only case (no file to read)
            return {"text": "", "image_path": None}

        if not os.path.exists(file_path):
            print(f"[Vision] File not found: {file_path}")
            return {"text": "", "image_path": None}

        # Route based on extension
        if file_path.lower().endswith(".pdf"):
            return self._process_pdf(file_path)
        elif file_path.lower().endswith(".html"):
            return self._process_html(file_path)
        else:
            print(f"[Vision] Unsupported format: {file_path}")
            return {"text": "", "image_path": None}

    def _process_pdf(self, pdf_path):
        """
        Extract text from first 2 pages and screenshot the 1st page.
        """
        text_content = ""
        image_path = None
        
        try:
            doc = fitz.open(pdf_path)
            
            # 1. Extract Text (First 2 pages are usually enough for author info)
            # Limit to 2 pages to save time/memory
            for i in range(min(2, len(doc))):
                text_content += doc[i].get_text() + "\n"

            # 2. Generate Snapshot of Page 1
            if len(doc) > 0:
                page = doc[0]
                pix = page.get_pixmap(dpi=150) # 150 DPI is good for screen preview
                
                # Create a unique filename for the image
                base_name = os.path.basename(pdf_path).replace(".pdf", ".png")
                save_path = os.path.join(VISUAL_SLICE_DIR, base_name)
                
                pix.save(save_path)
                image_path = save_path
                print(f"[Vision] Snapshot saved: {image_path}")
            
            doc.close()
            return {"text": text_content, "image_path": image_path}

        except Exception as e:
            print(f"[Vision] PDF Processing Error: {e}")
            return {"text": "", "image_path": None}

    def _process_html(self, html_path):
        """
        Extract text from HTML. No snapshot for HTML (too complex without browser engine).
        """
        text_content = ""
        try:
            with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
                html_code = f.read()
                
                # Simple Regex to strip tags (Robust enough for extracting names)
                # Removes <script>, <style>, and all <tags>
                cleanr = re.compile('<.*?>')
                text_content = re.sub(cleanr, ' ', html_code)
                
                # Cleanup whitespace
                text_content = " ".join(text_content.split())
                
            return {"text": text_content, "image_path": None}

        except Exception as e:
            print(f"[Vision] HTML Processing Error: {e}")
            return {"text": "", "image_path": None}