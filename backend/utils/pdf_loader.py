import os
import requests
from config import PDF_CACHE_DIR, HEADERS


# -----------------------------------------------------------------------------
# Utility helpers for downloading and caching PDF/HTML resources.
# These helpers were originally embedded in ScoutAgent; refactoring them
# here improves reuse (e.g. orchestrator or future downloaders).
# -----------------------------------------------------------------------------

def ensure_cache_dir():
    """Make sure the PDF cache directory exists."""
    if not os.path.exists(PDF_CACHE_DIR):
        os.makedirs(PDF_CACHE_DIR, exist_ok=True)


def download_file(url: str, save_path: str) -> str | None:
    """Download a remote file and save to disk.

    Returns the full path on success or None on failure.  Existing files are
    returned immediately (idempotent behavior).
    """
    try:
        # if the file already exists, return immediately
        if os.path.exists(save_path):
            return save_path

        resp = requests.get(url, headers=HEADERS, stream=True, timeout=30, verify=False)
        if resp.status_code == 200:
            with open(save_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=4096):
                    if chunk:
                        f.write(chunk)
            return save_path
    except Exception:
        pass
    return None


def fetch_pdf_by_doi(doi: str, pdf_url: str) -> str | None:
    """Download a PDF using its DOI to construct a cache filename.

    If the PDF already lives in cache it is returned immediately.  ``pdf_url``
    should be the direct link to the PDF (e.g. from Unpaywall).
    """
    ensure_cache_dir()
    safe_name = doi.replace("/", "_") + ".pdf"
    local_path = os.path.join(PDF_CACHE_DIR, safe_name)
    return download_file(pdf_url, local_path)
