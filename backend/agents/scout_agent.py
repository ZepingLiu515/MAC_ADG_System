import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from config import HEADERS, CROSSREF_TIMEOUT, CROSSREF_RETRIES

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
            "authors": metadata.get("authors", []),  # 【新增】从 Crossref 提取的作者列表
            "status": "metadata_ready" 
        }

    def fetch_metadata(self, doi):
        """【改进】从 Crossref API 提取完整元数据，包括所有作者和单位"""
        url = f"https://api.crossref.org/works/{doi}"
        
        # 配置网络辅助：重试机制（处理 SSL 错误）
        session = requests.Session()
        retry = Retry(
            total=CROSSREF_RETRIES,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('https://', adapter)
        
        try:
            r = session.get(url, headers=HEADERS, timeout=CROSSREF_TIMEOUT)
            if r.status_code == 200:
                data = r.json()['message']
                title = data.get('title', ['Unknown'])[0]
                container = data.get('container-title', ['Unknown'])
                journal = container[0] if container else "Unknown"
                issued = data.get('issued', {}).get('date-parts', [[None]])[0]
                date_str = str(issued[0]) if issued[0] else "N/A"
                
                # 【新增】提取所有作者和单位信息
                authors = self._extract_authors_from_crossref(data)
                
                return {
                    "title": title, 
                    "journal": journal, 
                    "date": date_str, 
                    "url": data.get('URL'),
                    "authors": authors  # 【新增】返回作者列表
                }
        except Exception as e:
            print(f"[Scout] 元数据错误: {e}")
        return None
    
    def _extract_authors_from_crossref(self, crossref_data):
        """【新增】从 Crossref 数据中提取结构化的作者和单位信息"""
        authors = []
        
        try:
            author_list = crossref_data.get('author', [])
            
            for idx, author in enumerate(author_list):
                author_dict = {
                    "name": f"{author.get('given', '')} {author.get('family', '')}".strip(),
                    "affiliation": "Unknown",
                    "order": idx + 1,
                    "is_corresponding": False,
                    "is_co_first": False
                }
                
                # 提取单位信息
                affiliations = author.get('affiliation', [])
                if affiliations:
                    if isinstance(affiliations, list) and len(affiliations) > 0:
                        aff_info = affiliations[0]
                        if isinstance(aff_info, dict):
                            author_dict["affiliation"] = aff_info.get('name', 'Unknown')
                        else:
                            author_dict["affiliation"] = str(aff_info)
                
                if author_dict["name"] and author_dict["name"].strip():
                    authors.append(author_dict)
                    print(f"[Scout] 作者 {idx+1}: {author_dict['name']} ({author_dict['affiliation']})")
        
        except Exception as e:
            print(f"[Scout] 作者提取异常: {e}")
        
        print(f"[Scout] ✅ 从 Crossref 提取了 {len(authors)} 位作者")
        return authors