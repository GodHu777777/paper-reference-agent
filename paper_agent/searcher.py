"""
核心搜索引擎
支持多个学术数据源的搜索
"""
import re
import requests
import time
from typing import Optional, Dict, Any, List
from urllib.parse import quote

import config
from .extractors import extract_pages
from .utils import clean_title, similarity_score, parse_author_list


class BaseSearcher:
    """搜索引擎基类"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': config.USER_AGENT})
        if config.PROXIES:
            self.session.proxies.update(config.PROXIES)
    
    def search(self, query: str) -> Optional[Dict[str, Any]]:
        """
        搜索论文
        
        Args:
            query: 论文标题
            
        Returns:
            论文信息字典，如果未找到则返回 None
        """
        raise NotImplementedError


class SemanticScholarSearcher(BaseSearcher):
    """Semantic Scholar 搜索引擎"""
    
    def __init__(self):
        super().__init__()
        # Semantic Scholar API
        self.base_url = "https://api.semanticscholar.org/graph/v1/paper/search"
        self.paper_url = "https://api.semanticscholar.org/graph/v1/paper"
        
        # 设置 API Key（如果提供）
        if config.SEMANTIC_SCHOLAR_API_KEY:
            self.session.headers['x-api-key'] = config.SEMANTIC_SCHOLAR_API_KEY
    
    def search(self, query: str) -> Optional[Dict[str, Any]]:
        """搜索论文"""
        try:
            # 清理查询字符串
            cleaned_query = clean_title(query)
            
            # 搜索参数
            params = {
                'query': cleaned_query,
                'limit': 5,  # 返回前 5 个结果
                'fields': 'title,authors,year,venue,publicationVenue,citationCount,isOpenAccess,openAccessPdf,externalIds,url',
            }
            
            # 发送搜索请求
            response = self.session.get(
                self.base_url,
                params=params,
                timeout=config.REQUEST_TIMEOUT
            )
            response.raise_for_status()
            
            data = response.json()
            papers = data.get('data', [])
            
            if not papers:
                return None
            
            # 找到最匹配的论文（通过标题相似度）
            best_match = None
            best_score = 0.0
            
            for paper in papers:
                score = similarity_score(query, paper.get('title', ''))
                if score > best_score:
                    best_score = score
                    best_match = paper
            
            # 如果相似度太低，认为未找到
            if best_score < 0.3:
                return None
            
            # 获取详细信息
            return self._parse_paper_info(best_match)
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                # 速率限制
                if not config.SEMANTIC_SCHOLAR_API_KEY:
                    print(f"⚠ Semantic Scholar 速率限制（429），建议设置 API Key 以提高速率限制")
                else:
                    print(f"⚠ Semantic Scholar 速率限制（429），请稍后重试")
            else:
                print(f"Semantic Scholar 搜索失败: {e}")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Semantic Scholar 搜索失败: {e}")
            return None
        except Exception as e:
            print(f"解析 Semantic Scholar 结果失败: {e}")
            return None
    
    def _parse_paper_info(self, paper: Dict[str, Any]) -> Dict[str, Any]:
        """解析论文信息"""
        # 提取基本信息
        # 优先使用 publicationVenue 的 name，如果没有则使用 venue
        venue = ''
        pub_venue = paper.get('publicationVenue', {})
        if isinstance(pub_venue, dict):
            # 尝试获取多个可能的字段
            venue = pub_venue.get('name') or pub_venue.get('alternateNames', [None])[0] or venue
        
        if not venue:
            venue = paper.get('venue', '')
        
        # 使用工具函数扩展 venue 名称
        from .utils import expand_venue_name
        venue_full = expand_venue_name(venue)
        
        result = {
            'title': paper.get('title', ''),
            'authors': parse_author_list(paper.get('authors', [])),
            'year': paper.get('year'),
            'venue': venue_full,  # 使用扩展后的全名
            'url': paper.get('url', ''),
            'citation_count': paper.get('citationCount', 0),
            'source': 'semantic_scholar',
        }
        
        # 提取外部 ID
        external_ids = paper.get('externalIds', {})
        if external_ids:
            if 'DOI' in external_ids:
                result['doi'] = external_ids['DOI']
            if 'DBLP' in external_ids:
                result['dblp_id'] = external_ids['DBLP']
                result['dblp_url'] = f"https://dblp.org/rec/{external_ids['DBLP']}"
            if 'ArXiv' in external_ids:
                result['arxiv_id'] = external_ids['ArXiv']
        
        # 提取开放访问 PDF
        open_access = paper.get('openAccessPdf', {})
        if open_access and open_access.get('url'):
            result['pdf_url'] = open_access['url']
        
        # 提取页码
        pages = extract_pages(paper, source='semantic_scholar')
        if pages:
            result['pages'] = pages
        else:
            # 如果没有页码，尝试通过 paperId 获取详细信息
            paper_id = paper.get('paperId')
            if paper_id:
                pages = self._fetch_detailed_info(paper_id)
                if pages:
                    result['pages'] = pages
        
        return result
    
    def _fetch_detailed_info(self, paper_id: str) -> Optional[str]:
        """获取论文详细信息（可能包含页码）"""
        try:
            params = {
                'fields': 'title,citation,citationStyles',
            }
            response = self.session.get(
                f"{self.paper_url}/{paper_id}",
                params=params,
                timeout=config.REQUEST_TIMEOUT
            )
            response.raise_for_status()
            
            data = response.json()
            # 尝试从 citation 中提取页码
            citation = data.get('citation', {})
            if citation:
                # 这里可以解析 BibTeX 格式的引用
                bibtex = citation.get('bibtex', '')
                if bibtex and 'pages' in bibtex:
                    from .extractors import BibTeXExtractor
                    extractor = BibTeXExtractor()
                    return extractor.extract_from_bibtex(bibtex)
            
        except Exception:
            pass
        
        return None


class DBLPSearcher(BaseSearcher):
    """DBLP 搜索引擎"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://dblp.org/search/publ/api"
    
    def search(self, query: str) -> Optional[Dict[str, Any]]:
        """搜索论文"""
        try:
            cleaned_query = clean_title(query)
            
            # DBLP API 参数 - 增加返回结果数以便找到更精确的匹配
            params = {
                'q': cleaned_query,
                'h': 50,  # 增加返回结果数，以便找到更好的匹配
                'format': 'json',
            }
            
            response = self.session.get(
                self.base_url,
                params=params,
                timeout=config.REQUEST_TIMEOUT
            )
            response.raise_for_status()
            
            data = response.json()
            hits = data.get('result', {}).get('hits', {}).get('hit', [])
            
            if not hits:
                if config.DEBUG:
                    print(f"  [DEBUG] DBLP 未返回任何结果")
                return None
            
            if config.DEBUG:
                print(f"  [DEBUG] DBLP 共返回 {len(hits)} 个结果，开始分析...")
            
            # 找到最匹配的结果
            # 收集所有候选结果及其得分，计算详细分数
            candidates = []
            
            for idx, hit in enumerate(hits):
                info = hit.get('info', {})
                title = info.get('title', '')
                year = info.get('year', 'N/A')
                venue = info.get('venue', 'N/A')
                
                # 计算相似度得分
                score = similarity_score(query, title)
                
                # 额外的惩罚：如果标题明显比查询长，降低得分
                query_words = len(query.split())
                title_words = len(title.split())
                word_diff = title_words - query_words
                
                # 如果标题比查询多很多词，降低分数
                original_score = score
                if word_diff > 3:
                    score = score * 0.7  # 减少30%的分数
                elif word_diff > 1:
                    score = score * 0.9  # 减少10%的分数
                
                # 额外的奖励：如果标题长度和查询长度非常接近，增加分数
                if abs(word_diff) <= 1 and score > 0.5:
                    score = min(1.0, score * 1.1)
                
                # 调试输出：打印所有结果
                if config.DEBUG:
                    print(f"    [{idx+1}] {title[:60]}{'...' if len(title) > 60 else ''}")
                    print(f"        年份: {year}, 会议: {venue}")
                    print(f"        原始得分: {original_score:.3f}, 调整后得分: {score:.3f}, 词数差异: {word_diff}")
                
                if score > 0.0:
                    candidates.append({
                        'info': info,
                        'score': score,
                        'title': title,
                        'word_diff': word_diff,
                        'year': year,
                    })
            
            if not candidates:
                if config.DEBUG:
                    print(f"  [DEBUG] 没有有效候选结果")
                return None
            
            # 按得分排序（得分高的在前）
            candidates.sort(key=lambda x: x['score'], reverse=True)
            
            if config.DEBUG:
                print(f"\n  [DEBUG] 排序后的前5个候选:")
                for i, cand in enumerate(candidates[:5]):
                    print(f"    {i+1}. [{cand['year']}] {cand['title'][:60]}{'...' if len(cand['title']) > 60 else ''}")
                    print(f"       得分: {cand['score']:.3f}, 词数差异: {cand['word_diff']}")
            
            # 如果前几个结果得分很接近，优先选择更短、更精确的标题
            best_candidate = candidates[0]
            
            # 检查前3个候选结果
            for i in range(1, min(3, len(candidates))):
                candidate = candidates[i]
                score_diff = best_candidate['score'] - candidate['score']
                
                # 如果得分差异很小（< 0.05），且候选结果更短
                if score_diff < 0.05:
                    # 如果候选结果的标题更短，且所有查询词都在标题中
                    if candidate['word_diff'] < best_candidate['word_diff']:
                        # 检查覆盖率
                        query_words_set = set(query.lower().split())
                        candidate_words_set = set(candidate['title'].lower().split())
                        coverage = len(query_words_set & candidate_words_set) / len(query_words_set) if query_words_set else 0
                        
                        if coverage >= 1.0:  # 所有查询词都在标题中
                            if config.DEBUG:
                                print(f"  [DEBUG] 选择更短的标题: {candidate['title'][:60]}")
                            best_candidate = candidate
            
            if config.DEBUG:
                print(f"\n  [DEBUG] 最终选择: [{best_candidate['year']}] {best_candidate['title']}")
                print(f"  [DEBUG] 最终得分: {best_candidate['score']:.3f}")
            
            if best_candidate['score'] < 0.3:
                if config.DEBUG:
                    print(f"  [DEBUG] 得分低于阈值 0.3，返回 None")
                return None
            
            return self._parse_paper_info(best_candidate['info'])
            
        except requests.exceptions.RequestException as e:
            print(f"DBLP 搜索失败: {e}")
            return None
        except Exception as e:
            print(f"解析 DBLP 结果失败: {e}")
            return None
    
    def _parse_paper_info(self, info: Dict[str, Any]) -> Dict[str, Any]:
        """解析 DBLP 论文信息"""
        # 提取作者信息（DBLP 可能有多种格式）
        authors_raw = info.get('authors', {})
        authors_list = []
        
        if isinstance(authors_raw, list):
            # 如果 authors 直接是列表
            authors_list = authors_raw
        elif isinstance(authors_raw, dict):
            # 如果 authors 是字典，尝试获取 author 字段
            author_value = authors_raw.get('author', [])
            if isinstance(author_value, list):
                authors_list = author_value
            elif isinstance(author_value, str):
                authors_list = [author_value]
            elif isinstance(author_value, dict):
                authors_list = [author_value]
        elif isinstance(authors_raw, str):
            # 如果 authors 直接是字符串
            authors_list = [authors_raw]
        
        # 提取并扩展 venue 名称
        venue = info.get('venue', '')
        from .utils import expand_venue_name
        venue_full = expand_venue_name(venue)
        
        result = {
            'title': info.get('title', ''),
            'authors': parse_author_list(authors_list),  # 使用 parse_author_list 处理
            'year': info.get('year'),
            'venue': venue_full,  # 使用扩展后的全名
            'url': info.get('ee', info.get('url', '')),
            'source': 'dblp',
        }
        
        # 提取页码
        pages = extract_pages(result, source='dblp')
        if pages:
            result['pages'] = pages
        
        return result


class CrossRefSearcher(BaseSearcher):
    """CrossRef 搜索引擎"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://api.crossref.org/works"
    
    def search(self, query: str) -> Optional[Dict[str, Any]]:
        """搜索论文"""
        try:
            cleaned_query = clean_title(query)
            
            params = {
                'query.title': cleaned_query,
                'rows': 5,
            }
            
            response = self.session.get(
                self.base_url,
                params=params,
                timeout=config.REQUEST_TIMEOUT
            )
            response.raise_for_status()
            
            data = response.json()
            items = data.get('message', {}).get('items', [])
            
            if not items:
                return None
            
            # 找到最匹配的结果
            best_match = None
            best_score = 0.0
            
            for item in items:
                title = item.get('title', [])
                title_str = title[0] if title else ''
                score = similarity_score(query, title_str)
                
                if score > best_score:
                    best_score = score
                    best_match = item
            
            if best_score < 0.3:
                return None
            
            return self._parse_paper_info(best_match)
            
        except requests.exceptions.RequestException as e:
            print(f"CrossRef 搜索失败: {e}")
            return None
        except Exception as e:
            print(f"解析 CrossRef 结果失败: {e}")
            return None
    
    def _parse_paper_info(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """解析 CrossRef 论文信息"""
        # 提取 venue（container-title 通常是全名，但我们也尝试扩展）
        venue = item.get('container-title', [])[0] if item.get('container-title') else ''
        from .utils import expand_venue_name
        venue_full = expand_venue_name(venue)
        
        # 提取卷期号（如果可用）
        volume = item.get('volume')
        issue = item.get('issue') or item.get('number')
        
        result = {
            'title': item.get('title', [])[0] if item.get('title') else '',
            'authors': [f"{a.get('given', '')} {a.get('family', '')}".strip() 
                       for a in item.get('author', [])],
            'year': item.get('published-print', {}).get('date-parts', [[None]])[0][0],
            'venue': venue_full,  # 使用扩展后的全名
            'url': item.get('URL', ''),
            'doi': item.get('DOI', ''),
            'source': 'crossref',
        }
        
        # 添加卷期号（如果存在）
        if volume:
            result['volume'] = str(volume)
        if issue:
            result['issue'] = str(issue)
        
        # 提取页码
        pages = extract_pages(result, source='crossref')
        if pages:
            result['pages'] = pages
        
        return result


class PaperAgent:
    """智能文献页码搜索 Agent"""
    
    def __init__(self):
        """初始化 Agent"""
        # 延迟导入其他搜索引擎（避免循环依赖）
        try:
            from .google_scholar_searcher import GoogleScholarSearcher
            google_scholar = GoogleScholarSearcher()
        except ImportError:
            google_scholar = None
        
        try:
            from .pmlr_searcher import PMLRSearcher
            pmlr_searcher = PMLRSearcher()
        except ImportError:
            pmlr_searcher = None
        
        self.searchers = {
            'semantic_scholar': SemanticScholarSearcher(),
            'dblp': DBLPSearcher(),
            'crossref': CrossRefSearcher(),
        }
        
        # 如果 PMLR 可用，添加到搜索引擎列表（优先）
        if pmlr_searcher:
            self.searchers['pmlr'] = pmlr_searcher
        
        # 如果 Google Scholar 可用，添加到搜索引擎列表
        if google_scholar:
            self.searchers['google_scholar'] = google_scholar
        
        # 导入缓存管理器（延迟导入避免循环依赖）
        from .cache import CacheManager
        self.cache = CacheManager()
    
    def search(self, query: str, use_cache: bool = True, 
               search_engines: List[str] = None) -> Optional[Dict[str, Any]]:
        """
        搜索论文并获取页码信息
        
        Args:
            query: 论文标题
            use_cache: 是否使用缓存
            search_engines: 要使用的搜索引擎列表，默认使用 config.SEARCH_ENGINES
            
        Returns:
            包含论文信息和页码的字典，如果未找到则返回 None
        """
        # 检查缓存
        if use_cache:
            cached_result = self.cache.get(query)
            if cached_result:
                print(f"✓ 从缓存获取: {query}")
                return cached_result
        
        # 确定使用的搜索引擎
        engines = search_engines or config.SEARCH_ENGINES
        
        # 按优先级尝试各个搜索引擎
        for engine_name in engines:
            if engine_name not in self.searchers:
                continue
            
            print(f"搜索中 ({engine_name}): {query}...")
            
            searcher = self.searchers[engine_name]
            result = searcher.search(query)
            
            if result:
                # 如果有 DOI，优先使用 doi2bib.org 获取页码
                doi = result.get('doi')
                if doi:
                    print(f"  ✓ 检测到 DOI: {doi}")
                    if not result.get('pages'):
                        try:
                            from .extractors import DOI2BibExtractor
                            doi2bib_extractor = DOI2BibExtractor()
                            print(f"  尝试使用 doi2bib.org 获取页码...")
                            pages = doi2bib_extractor.extract_from_doi(doi)
                            if pages:
                                result['pages'] = pages
                                result['pages_source'] = 'doi2bib'
                                print(f"  ✓ 从 doi2bib.org 成功获取页码: {pages}")
                            else:
                                print(f"  ⚠ doi2bib.org 未找到页码")
                        except Exception as e:
                            print(f"  ⚠ doi2bib.org 提取失败: {e}")
                            if config.DEBUG:
                                import traceback
                                print(f"  [DEBUG] 错误详情: {traceback.format_exc()}")
                    else:
                        print(f"  ℹ 已有页码信息，跳过 DOI 提取")
                else:
                    if config.DEBUG:
                        print(f"  [DEBUG] 未检测到 DOI")
                
                # 如果没有页码，尝试其他搜索引擎补充
                if not result.get('pages'):
                    result = self._supplement_pages(result, engines)
                
                # 保存到缓存
                if use_cache:
                    self.cache.set(query, result)
                
                return result
            
            # 避免请求过快
            time.sleep(0.5)
        
        print(f"✗ 未找到: {query}")
        return None
    
    def _supplement_pages(self, result: Dict[str, Any], 
                         engines: List[str]) -> Dict[str, Any]:
        """
        如果主搜索引擎未找到页码，尝试从其他来源补充
        
        Args:
            result: 已有的论文信息
            engines: 可用的搜索引擎列表
            
        Returns:
            更新后的论文信息
        """
        url = result.get('url') or result.get('dblp_url') or result.get('pdf_url')
        paper_title = result.get('title', '')
        
        # 首先检查是否是 NeurIPS URL
        if url and ('neurips.cc' in url.lower() or 'nips.cc' in url.lower()):
            try:
                from .neurips_extractor import NeurIPSExtractor
                print("  尝试从 NeurIPS 网页提取 BibTeX 页码...")
                neurips_extractor = NeurIPSExtractor()
                pages = neurips_extractor.extract_from_url(url, paper_title)
                if pages:
                    result['pages'] = pages
                    result['pages_source'] = 'neurips_bibtex'
                    return result
            except Exception as e:
                print(f"  NeurIPS 提取失败: {e}")
        
        # 如果有 DBLP URL，尝试从 DBLP 获取页码
        dblp_url = result.get('dblp_url') or result.get('url')
        if dblp_url and ('dblp.org' in dblp_url or 'dblp' in engines):
            print("  尝试从网页补充页码信息...")
            from .extractors import DBLPExtractor
            extractor = DBLPExtractor()
            # 使用 extract 方法，它会自动尝试传统方法和 LLM 方法
            pages = extractor.extract({
                'dblp_url': dblp_url,
                'url': dblp_url,
                'title': paper_title,
            })
            if pages:
                result['pages'] = pages
                result['pages_source'] = 'web_extraction'
                return result
        
        # 检查是否是 PMLR URL，如果是，使用 PMLR 提取器
        if url and 'proceedings.mlr.press' in url.lower():
            try:
                from .pmlr_searcher import PMLRSearcher
                print("  尝试从 PMLR 网页提取详细信息...")
                pmlr_searcher = PMLRSearcher()
                pmlr_result = pmlr_searcher._extract_from_pmlr_url(url, paper_title)
                if pmlr_result:
                    # 补充页码等信息
                    if pmlr_result.get('pages') and not result.get('pages'):
                        result['pages'] = pmlr_result['pages']
                        result['pages_source'] = 'pmlr'
                    
                    # 补充 BibTeX（如果有）
                    if pmlr_result.get('bibtex') and not result.get('bibtex'):
                        result['bibtex'] = pmlr_result['bibtex']
            except Exception as e:
                if config.DEBUG:
                    print(f"  [DEBUG] PMLR 提取失败: {e}")
        
        # 如果没有页码，优先处理 DOI URL
        if not result.get('pages') and url:
            # 检查是否是受 Cloudflare 严格保护的网站（直接跳过）
            protected_domains = ['dl.acm.org', 'aclanthology.org', 'ieee.org']
            is_protected = any(domain in url.lower() for domain in protected_domains)
            
            if is_protected:
                print(f"  ⚠ 检测到受 Cloudflare 保护的网站，跳过自动提取")
                print(f"  💡 提示: 对于 {url.split('/')[2]}，建议使用其他搜索引擎（如 DBLP、Google Scholar）获取页码")
                return result
            
            # 检查是否是 DOI URL
            if 'doi.org' in url.lower() or url.startswith('https://doi.org/') or url.startswith('http://doi.org/'):
                # 首先尝试使用 doi2bib.org（更快速、可靠）
                try:
                    # 提取 DOI 标识符
                    doi_match = re.search(r'doi\.org/([^/]+/?.*)', url)
                    if doi_match:
                        doi_identifier = doi_match.group(1).rstrip('/')
                        
                        # 使用 doi2bib.org 获取 BibTeX 并提取页码
                        from .extractors import DOI2BibExtractor
                        doi2bib_extractor = DOI2BibExtractor()
                        print(f"  尝试使用 doi2bib.org 获取页码...")
                        pages = doi2bib_extractor.extract_from_doi(doi_identifier)
                        
                        if pages:
                            result['pages'] = pages
                            result['pages_source'] = 'doi2bib'
                            return result
                        else:
                            if config.DEBUG:
                                print(f"  [DEBUG] doi2bib.org 未找到页码")
                except Exception as e:
                    if config.DEBUG:
                        print(f"  [DEBUG] doi2bib.org 提取失败: {e}")
                
                # 如果 doi2bib.org 失败，尝试 LLM 提取
                try:
                    from .llm_extractor import LLMExtractor
                    llm_extractor = LLMExtractor()
                    
                    # 尝试获取重定向后的 URL（不访问内容）
                    import requests
                    response = requests.head(url, allow_redirects=True, timeout=5)
                    redirected_url = response.url
                    
                    # 检查重定向后的域名
                    redirected_domain = redirected_url.split('/')[2] if '/' in redirected_url else ''
                    if any(domain in redirected_domain.lower() for domain in protected_domains):
                        print(f"  ⚠ DOI 重定向到受保护的网站 ({redirected_domain})，跳过 LLM 提取")
                        print(f"  💡 提示: 建议使用其他搜索引擎（如 DBLP、Google Scholar）获取页码")
                        return result
                    
                    # 如果不受保护，尝试提取
                    print(f"  尝试使用 LLM 从 DOI 网页提取页码...")
                    pages = llm_extractor.extract_from_doi_url(url, paper_title)
                    if pages:
                        result['pages'] = pages
                        result['pages_source'] = 'llm_doi_extraction'
                        return result
                    else:
                        # DOI 提取失败
                        print(f"  ⚠ DOI 网页提取失败")
                except Exception as e:
                    if config.DEBUG:
                        print(f"  [DEBUG] DOI LLM 提取失败: {e}")
            
            # 如果不是 DOI URL 或其他方法都失败，尝试通用 LLM 提取
            # 但跳过已知的受保护网站（避免重复失败）
            if not any(domain in url.lower() for domain in protected_domains):
                try:
                    from .llm_extractor import LLMExtractor
                    llm_extractor = LLMExtractor()
                    print(f"  尝试使用 LLM 从网页提取页码...")
                    pages = llm_extractor.extract_from_url(url, paper_title)
                    if pages:
                        result['pages'] = pages
                        result['pages_source'] = 'llm_extraction'
                except Exception:
                    pass
        
        return result
    
    def batch_search(self, queries: List[str], 
                    use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        批量搜索
        
        Args:
            queries: 论文标题列表
            use_cache: 是否使用缓存
            
        Returns:
            结果列表（每个查询一个结果）
        """
        results = []
        for query in queries:
            result = self.search(query, use_cache=use_cache)
            results.append({
                'query': query,
                'result': result,
            })
        return results

