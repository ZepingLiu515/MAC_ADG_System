import os

# Base Directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Data Directories
DATA_DIR = os.path.join(BASE_DIR, 'data')
DB_PATH = os.path.join(DATA_DIR, 'mac_adg.db')

# File Caches
PDF_CACHE_DIR = os.path.join(DATA_DIR, 'pdf_cache')
HTML_CACHE_DIR = os.path.join(DATA_DIR, 'html_cache')
VISUAL_SLICE_DIR = os.path.join(DATA_DIR, 'visual_slices')
EXPORT_DIR = os.path.join(DATA_DIR, 'exports')

# Enhanced Headers (Mimic Real Chrome Browser to bypass 403)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-US,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "mailto": "researcher@university.edu.cn"
}

# =================================================================
# DeepSeek VLM API 配置
# =================================================================
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
DEEPSEEK_MODEL = os.getenv('DEEPSEEK_MODEL', 'deepseek-vl')
DEEPSEEK_BASE_URL = 'https://api.deepseek.com/v1'

# Crossref API 配置
CROSSREF_TIMEOUT = int(os.getenv('CROSSREF_TIMEOUT', '30'))
CROSSREF_RETRIES = int(os.getenv('CROSSREF_RETRIES', '3'))