"""
Google Scholar 搜索引擎
通过网页搜索获取论文信息
"""
import requests
import time
import re
from typing import Optional, Dict, Any
from urllib.parse import quote, urljoin
from bs4 import BeautifulSoup

import config
from .utils import clean_title, similarity_score, parse_author_list, expand_venue_name
from .extractors import extract_pages


class GoogleScholarSearcher:
    """Google Scholar 搜索引擎"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': config.USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })
        # 只在代理配置不为空且是有效字典时使用代理
        if config.PROXIES and isinstance(config.PROXIES, dict) and config.PROXIES:
            try:
                if any(v for v in config.PROXIES.values() if v):
                    self.session.proxies.update(config.PROXIES)
            except Exception:
                self.session.proxies = {}
        
        self.base_url = "https://scholar.google.com/scholar"
    
    def search(self, query: str) -> Optional[Dict[str, Any]]:
        """
        搜索论文
        
        Args:
            query: 论文标题
            
        Returns:
            论文信息字典，如果未找到则返回 None
        """
        try:
            cleaned_query = clean_title(query)
            
            # 构建搜索 URL
            params = {
                'q': cleaned_query,
                'hl': 'en',  # 语言设置为英文
            }
            
            # 发送搜索请求
            response = self.session.get(
                self.base_url,
                params=params,
                timeout=config.REQUEST_TIMEOUT
            )
            
            # Google Scholar 可能会返回验证页面或重定向
            if response.status_code != 200:
                print(f"Google Scholar 搜索失败: HTTP {response.status_code}")
                return None
            
            # 检查是否被重定向到验证页面
            if 'sorry' in response.url.lower() or 'captcha' in response.url.lower():
                print("⚠ Google Scholar 返回验证页面，可能需要人工验证或使用代理")
                return None
            
            # 解析搜索结果
            soup = BeautifulSoup(response.content, 'lxml')
            
            # 提取搜索结果
            results = self._parse_search_results(soup, query)
            
            if not results:
                return None
            
            # 找到最匹配的结果
            best_match = None
            best_score = 0.0
            
            for result in results:
                title = result.get('title', '')
                score = similarity_score(query, title)
                if score > best_score:
                    best_score = score
                    best_match = result
            
            # 如果相似度太低，认为未找到
            if best_score < 0.3:
                return None
            
            return best_match
            
        except requests.exceptions.RequestException as e:
            print(f"Google Scholar 搜索失败: {e}")
            return None
        except Exception as e:
            print(f"解析 Google Scholar 结果失败: {e}")
            return None
    
    def _parse_search_results(self, soup: BeautifulSoup, query: str) -> list:
        """
        解析搜索结果页面
        
        Args:
            soup: BeautifulSoup 对象
            query: 原始查询
            
        Returns:
            结果列表
        """
        results = []
        
        # Google Scholar 的结果通常在 class="gs_ri" 的 div 中
        result_divs = soup.find_all('div', class_='gs_ri')
        
        if not result_divs:
            # 尝试其他可能的类名
            result_divs = soup.find_all('div', class_=re.compile(r'gs_scl|gs_r'))
        
        for div in result_divs[:5]:  # 只取前 5 个结果
            result = self._parse_result_item(div)
            if result:
                results.append(result)
        
        return results
    
    def _parse_result_item(self, div) -> Optional[Dict[str, Any]]:
        """
        解析单个搜索结果项
        
        Args:
            div: 结果项的 div 元素
            
        Returns:
            论文信息字典
        """
        try:
            # 提取标题
            title_elem = div.find('h3', class_='gs_rt')
            if not title_elem:
                title_elem = div.find('h3')
            
            if not title_elem:
                return None
            
            title_link = title_elem.find('a')
            title = title_link.get_text(strip=True) if title_link else title_elem.get_text(strip=True)
            
            # 提取 URL
            url = None
            if title_link and title_link.get('href'):
                url = title_link.get('href')
                if url.startswith('/'):
                    url = 'https://scholar.google.com' + url
            
            # 提取作者和来源信息
            author_elem = div.find('div', class_='gs_a')
            authors_str = ''
            venue = ''
            year = None
            
            if author_elem:
                author_text = author_elem.get_text(strip=True)
                # Google Scholar 格式通常为: "作者1, 作者2 - 会议/期刊, 年份"
                # 例如: "A Vaswani, N Shazeer - NIPS, 2017"
                
                # 尝试提取年份
                year_match = re.search(r'\b(19|20)\d{2}\b', author_text)
                if year_match:
                    year = int(year_match.group(0))
                
                # 分割作者和来源
                parts = author_text.split(' - ')
                if len(parts) >= 1:
                    authors_str = parts[0].strip()
                
                if len(parts) >= 2:
                    venue_part = parts[1]
                    # 移除年份
                    venue = re.sub(r'[,\s]*\d{4}.*$', '', venue_part).strip()
            
            # 解析作者列表
            authors = []
            if authors_str:
                authors = [a.strip() for a in authors_str.split(',') if a.strip()]
            
            # 提取摘要（可选）
            snippet_elem = div.find('div', class_='gs_rs')
            abstract = snippet_elem.get_text(strip=True) if snippet_elem else ''
            
            # 提取引用数（可选）
            citation_elem = div.find('div', class_='gs_fl')
            citation_count = 0
            if citation_elem:
                citation_link = citation_elem.find('a', string=re.compile(r'Cited by'))
                if citation_link:
                    citation_text = citation_link.get_text()
                    citation_match = re.search(r'(\d+)', citation_text)
                    if citation_match:
                        citation_count = int(citation_match.group(1))
            
            result = {
                'title': title,
                'authors': authors,
                'year': year,
                'venue': expand_venue_name(venue) if venue else '',
                'url': url,
                'abstract': abstract,
                'citation_count': citation_count,
                'source': 'google_scholar',
            }
            
            # 尝试提取页码（从标题链接的页面或其他信息中）
            # Google Scholar 通常不直接显示页码，需要访问详情页
            
            return result
            
        except Exception as e:
            print(f"解析 Google Scholar 结果项失败: {e}")
            return None
    
    def _extract_pages_from_detail_page(self, url: str) -> Optional[str]:
        """
        从详情页提取页码信息
        
        Args:
            url: 论文详情页 URL
            
        Returns:
            页码字符串
        """
        try:
            response = self.session.get(url, timeout=config.REQUEST_TIMEOUT)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'lxml')
            
            # 查找页码信息
            # Google Scholar 可能在不同位置显示页码
            
            # 方法1: 查找包含 "pages" 的文本
            page_text = soup.get_text()
            pages_match = re.search(r'pages?\s*[:：]?\s*(\d+)\s*[-–—]\s*(\d+)', 
                                   page_text, re.IGNORECASE)
            if pages_match:
                return f"{pages_match.group(1)}-{pages_match.group(2)}"
            
            # 方法2: 查找 BibTeX 信息（如果可用）
            # Google Scholar 有时会提供 BibTeX
            
            return None
            
        except Exception:
            return None

