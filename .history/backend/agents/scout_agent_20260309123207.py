import requests
import os
from config import PDF_CACHE_DIR, HTML_CACHE_DIR, HEADERS
from backend.utils.pdf_loader import fetch_pdf_by_doi

class ScoutAgent:
    """
    [Scout Agent V2.2 - Final Fix]
    Strategy:
    1. Fetch Metadata.
    2. Try PDF -> Try HTML.
    3. If files fail but metadata exists -> Return 'metadata_only' (NOT FAILED).
    """

    def __init__(self):
        if not os.path.exists(PDF_CACHE_DIR): os.makedirs(PDF_CACHE_DIR)
        if not os.path.exists(HTML_CACHE_DIR): os.makedirs(HTML_CACHE_DIR)
            
    def run(self, doi):
        print(f"[Scout] Processing DOI: {doi}")
        
        # 1. Fetch Metadata
        metadata = self.fetch_metadata(doi)
        if not metadata:
            return {"status": "error", "message": "Invalid DOI", "doi": doi}

        # 2. Try PDF Download
        pdf_path = self.download_pdf_process(doi)
        
        # 3. Fallback to HTML
        html_path = None
        if not pdf_path:
            landing_url = metadata.get("url") or f"https://doi.org/{doi}"
            print(f"[Scout] PDF missing. Trying HTML fallback: {landing_url}")
            html_path = self.download_html_process(landing_url, doi)
        
        # 4. Determine Status
        status = "failed"
        if pdf_path:
            status = "success_pdf"
        elif html_path:
            status = "success_html"
        else:
            status = "metadata_only"
            print(f"[Scout] Content missing, keeping metadata for: {doi}")
            
        result = {
            "doi": doi,
            "title": metadata.get("title", "N/A"),
            "journal": metadata.get("journal", "N/A"),     # 确保前端能拿到
            "publish_date": metadata.get("date", "N/A"),   # 确保前端能拿到
            "pdf_path": pdf_path,
            "html_path": html_path,
            "status": status
        }
        return result

    def fetch_metadata(self, doi):
        url = f"https://api.crossref.org/works/{doi}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                data = r.json()['message']
                title = data.get('title', ['Unknown'])[0]
                container = data.get('container-title', ['Unknown Journal'])
                journal = container[0] if container else "Unknown"
                issued = data.get('issued', {}).get('date-parts', [[None]])[0]
                date_str = str(issued[0]) if issued[0] else "N/A"
                return {"title": title, "journal": journal, "date": date_str, "url": data.get('URL')}
        except Exception:
            pass
        return None

    def download_pdf_process(self, doi):
        safe_name = doi.replace("/", "_") + ".pdf"
        local_path = os.path.join(PDF_CACHE_DIR, safe_name)
        if os.path.exists(local_path): return local_path
        
        # Unpaywall Logic
        email = "demo@mac_adg.com"
        url = f"https://api.unpaywall.org/v2/{doi}?email={email}"
        try:
            r = requests.get(url, timeout=20)
            if r.status_code == 200:
                data = r.json()
                pdf_url = data.get('best_oa_location', {}).get('url_for_pdf')
                if pdf_url: return self._download_file(pdf_url, local_path)
        except: pass
        return None

    def download_html_process(self, url, doi):
        safe_name = doi.replace("/", "_") + ".html"
        local_path = os.path.join(HTML_CACHE_DIR, safe_name)
        if os.path.exists(local_path): return local_path
        return self._download_file(url, local_path)

    def _download_file(self, url, save_path):
        try:
            r = requests.get(url, headers=HEADERS, stream=True, timeout=30, verify=False) 
            if r.status_code == 200:
                with open(save_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=1024):
                        if chunk: f.write(chunk)
                return save_path
        except: pass
        return None