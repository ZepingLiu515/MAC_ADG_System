import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from config import HEADERS, CROSSREF_TIMEOUT, CROSSREF_RETRIES
from typing import Any, Dict, List, Optional


OPENALEX_TIMEOUT = 20
OPENALEX_RETRIES = 2

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
            "landing_page_url": metadata.get("landing_page_url"),
            "authors": metadata.get("authors", []),
            "openalex_used": bool(metadata.get("openalex_used")),
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
                landing_page_url = self._extract_landing_page_url(data)

                openalex_used = False

                # Crossref 的单位信息经常缺失：尝试用 OpenAlex 补全单位/通讯线索/落地页
                try:
                    openalex_work = self._fetch_openalex_work(doi)
                    if openalex_work:
                        authors = self._enrich_authors_from_openalex(authors, openalex_work)
                        if not landing_page_url:
                            landing_page_url = self._extract_landing_page_url_from_openalex(openalex_work)
                        openalex_used = True
                except Exception as _:
                    pass
                
                return {
                    "title": title, 
                    "journal": journal, 
                    "date": date_str, 
                    "url": data.get('URL'),
                    "landing_page_url": landing_page_url,
                    "authors": authors,
                    "openalex_used": openalex_used,
                }
        except Exception as e:
            print(f"[Scout] 元数据错误: {e}")
        return None

    def _extract_landing_page_url(self, crossref_data) -> Optional[str]:
        """从 Crossref 元数据里尽量提取出版商落地页 URL（HTML 页面）。

        说明：Crossref 的 message['URL'] 往往仍是 doi.org；而某些记录会在
        message['resource']['primary']['URL'] 或 message['link'] 中提供出版商页面。
        """
        try:
            resource = crossref_data.get('resource') or {}
            primary = resource.get('primary') or {}
            url = primary.get('URL')
            if isinstance(url, str) and url.strip():
                return url.strip()

            links = crossref_data.get('link') or []
            if isinstance(links, list):
                # 优先 HTML，其次任何可用 URL
                html_links = []
                other_links = []
                for item in links:
                    if not isinstance(item, dict):
                        continue
                    link_url = item.get('URL')
                    if not isinstance(link_url, str) or not link_url.strip():
                        continue
                    content_type = str(item.get('content-type') or '').lower()
                    if 'html' in content_type:
                        html_links.append(link_url.strip())
                    else:
                        other_links.append(link_url.strip())

                if html_links:
                    return html_links[0]
                if other_links:
                    return other_links[0]
        except Exception:
            return None

        return None

    def _fetch_openalex_work(self, doi: str) -> Optional[dict]:
        """从 OpenAlex 获取 work 元数据（无需 API Key）。

        用途：
        - Crossref 缺失作者单位时补全
        - 提供出版商落地页 URL（landing_page_url）
        """
        if not doi:
            return None

        # OpenAlex 的 works 端点支持用 DOI URL 查询
        openalex_url = f"https://api.openalex.org/works/https://doi.org/{doi}"

        # OpenAlex 推荐使用 mailto 参数（用于更高的稳定性/配额友好）
        mailto = os.getenv("OPENALEX_MAILTO") or HEADERS.get("mailto") or "researcher@university.edu.cn"
        params = {"mailto": mailto}

        # 避免 br 压缩导致某些环境下 JSON 解码异常
        headers = dict(HEADERS)
        headers["Accept-Encoding"] = "gzip, deflate"

        session = requests.Session()
        retry = Retry(
            total=OPENALEX_RETRIES,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('https://', adapter)

        try:
            resp = session.get(openalex_url, headers=headers, params=params, timeout=OPENALEX_TIMEOUT)
            if resp.status_code == 200:
                try:
                    return resp.json()
                except Exception as e:
                    print(f"[Scout] OpenAlex JSON 解析失败: {e}")
                    return None

            # 可观测性：返回非 200 时给出原因（不会抛异常阻断 Crossref）
            if resp.status_code in (403, 429):
                print(f"[Scout] OpenAlex 请求受限 HTTP {resp.status_code}（可能频率/网络限制）")
            else:
                print(f"[Scout] OpenAlex 请求失败 HTTP {resp.status_code}")
            return None
        except Exception as e:
            print(f"[Scout] OpenAlex 请求异常: {e}")
            return None

        return None

    def _extract_landing_page_url_from_openalex(self, openalex_work: dict) -> Optional[str]:
        try:
            primary_location = openalex_work.get('primary_location') or {}
            url = primary_location.get('landing_page_url')
            if isinstance(url, str) and url.strip():
                return url.strip()
        except Exception:
            return None
        return None

    def _extract_authors_from_openalex(self, openalex_work: dict) -> List[Dict[str, Any]]:
        """将 OpenAlex authorships 转换为统一的 authors 列表。

        OpenAlex 往往比 Crossref 更容易给出作者单位（institutions/raw_affiliation_strings），
        且可能提供 is_corresponding。
        """
        out: List[Dict[str, Any]] = []
        authorships = openalex_work.get('authorships') or []
        if not isinstance(authorships, list):
            return out

        for idx, a in enumerate(authorships, start=1):
            author_obj = a.get('author') or {}
            name = str(author_obj.get('display_name') or '').strip()
            if not name:
                continue

            insts = a.get('institutions') or []
            inst_names: List[str] = []
            if isinstance(insts, list):
                for inst in insts:
                    if not isinstance(inst, dict):
                        continue
                    inst_name = inst.get('display_name')
                    if inst_name:
                        inst_names.append(str(inst_name).strip())

            raw_affs = a.get('raw_affiliation_strings') or []
            if isinstance(raw_affs, str):
                raw_affs = [raw_affs]
            if not isinstance(raw_affs, list):
                raw_affs = []
            raw_affs = [str(x).strip() for x in raw_affs if x and str(x).strip()]

            affiliation = "; ".join([n for n in inst_names if n]) if inst_names else (raw_affs[0] if raw_affs else "")

            is_corr = bool(a.get('is_corresponding'))

            out.append(
                {
                    "name": name,
                    "affiliation": affiliation or "Unknown",
                    "affiliations": inst_names or raw_affs,
                    "order": idx,
                    "is_corresponding": is_corr,
                    "is_co_first": False,
                    "source": "openalex",
                }
            )

        return out

    def _enrich_authors_from_openalex(self, authors: list, openalex_work: dict) -> list:
        """用 OpenAlex authorships 补全作者单位/通讯线索。

        策略：
        - 若 Crossref authors 为空：直接返回 OpenAlex authors 列表（至少保证有单位与对应顺序）。
        - 若 Crossref authors 有名字但 affiliation=Unknown：按 order 对齐补单位；并补 is_corresponding。
        """
        try:
            openalex_authors = self._extract_authors_from_openalex(openalex_work)
            if not openalex_authors:
                return authors

            # Crossref authors 为空：直接用 OpenAlex
            if not isinstance(authors, list) or not authors:
                return openalex_authors

            # 如果 Crossref 作者存在但几乎全是 Unknown，也允许直接“用 OpenAlex 为主”
            try:
                known = 0
                for a in authors:
                    if not isinstance(a, dict):
                        continue
                    aff = str(a.get('affiliation') or '').strip().lower()
                    if aff and aff != 'unknown':
                        known += 1
                if known == 0:
                    # 保留 Crossref 的作者顺序/姓名，但用 OpenAlex 补单位/通讯线索（按 order 对齐）
                    pass
            except Exception:
                pass

            by_order: Dict[int, Dict[str, Any]] = {a.get('order'): a for a in openalex_authors if isinstance(a, dict)}
            by_name: Dict[str, Dict[str, Any]] = {}
            for a in openalex_authors:
                if not isinstance(a, dict):
                    continue
                n = str(a.get('name') or '').strip()
                if not n:
                    continue
                key = "".join(ch for ch in n.lower() if ch.isalnum())
                by_name[key] = a

            for author in authors:
                if not isinstance(author, dict):
                    continue

                current_aff = str(author.get('affiliation') or '').strip()
                needs_aff = (not current_aff) or (current_aff.lower() == 'unknown')

                # order 优先
                oa = None
                order = author.get('order')
                if isinstance(order, int):
                    oa = by_order.get(order)

                # fallback：按名字 key
                if oa is None:
                    n = str(author.get('name') or '').strip()
                    if n:
                        key = "".join(ch for ch in n.lower() if ch.isalnum())
                        oa = by_name.get(key)

                if not oa:
                    continue

                if needs_aff:
                    oa_aff = str(oa.get('affiliation') or '').strip()
                    if oa_aff and oa_aff.lower() != 'unknown':
                        author['affiliation'] = oa_aff
                # 始终尽量补 affiliations 列表
                oa_affs = oa.get('affiliations')
                if oa_affs and isinstance(oa_affs, list):
                    author['affiliations'] = oa_affs

                # 通讯线索：Crossref 不给时，用 OpenAlex 的 is_corresponding
                if not author.get('is_corresponding') and oa.get('is_corresponding'):
                    author['is_corresponding'] = True
                    author['corresponding_source'] = 'openalex'

            return authors

        except Exception:
            return authors
    
    def _extract_authors_from_crossref(self, crossref_data):
        """【新增】从 Crossref 数据中提取结构化的作者和单位信息"""
        authors = []
        
        try:
            author_list = crossref_data.get('author', [])
            
            for author in author_list:
                name = f"{author.get('given', '')} {author.get('family', '')}".strip()
                if not name:
                    continue

                author_dict = {
                    "name": name,
                    "affiliation": "Unknown",
                    "order": len(authors) + 1,
                    "is_corresponding": False,
                    "is_co_first": False,
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
                
                authors.append(author_dict)
                print(f"[Scout] 作者 {author_dict['order']}: {author_dict['name']} ({author_dict['affiliation']})")
        
        except Exception as e:
            print(f"[Scout] 作者提取异常: {e}")
        
        print(f"[Scout] ✅ 从 Crossref 提取了 {len(authors)} 位作者")
        return authors