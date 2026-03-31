import requests
from config import HEADERS

class ScoutAgent:
    """
    [Scout Agent V3.0 - 仅元数据]
    职责：
    从 Crossref 获取基本元数据。不再下载 PDF！
    """
    def __init__(self):
        pass

    def run(self, doi):
        print(f"[Scout] 正在获取 DOI 的元数据: {doi}")
        metadata = self.fetch_metadata(doi)

        if not metadata:
            return {"status": "error", "message": "无效的 DOI", "doi": doi}

        return {
            "doi": doi,
            "title": metadata.get("title", "N/A"),
            "journal": metadata.get("journal", "N/A"),
            "publish_date": metadata.get("date", "N/A"),
            "url": metadata.get("url", f"https://doi.org/{doi}"),
            "status": "metadata_ready" 
        }

    def fetch_metadata(self, doi):
        url = f"https://api.crossref.org/works/{doi}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code == 200:
                data = r.json()['message']
                title = data.get('title', ['Unknown'])[0]
                container = data.get('container-title', ['Unknown'])
                journal = container[0] if container else "Unknown"
                issued = data.get('issued', {}).get('date-parts', [[None]])[0]
                date_str = str(issued[0]) if issued[0] else "N/A"
                return {"title": title, "journal": journal, "date": date_str, "url": data.get('URL')}
        except Exception as e:
            print(f"[Scout] 元数据错误: {e}")
        return None