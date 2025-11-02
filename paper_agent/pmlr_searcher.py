"""
PMLR (Proceedings of Machine Learning Research) 搜索引擎
PMLR 是机器学习领域的重要会议论文集，包括 ICML、AISTATS 等
"""
import requests
import re
import time
from typing import Optional, Dict, Any
from urllib.parse import quote, urljoin
from bs4 import BeautifulSoup

import config
from .utils import clean_title, similarity_score, parse_author_list
from .extractors import extract_pages


class PMLRSearcher:
    """PMLR 搜索引擎"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': config.USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
        # 只在代理配置不为空且是有效字典时使用代理
        if config.PROXIES and isinstance(config.PROXIES, dict) and config.PROXIES:
            try:
                if any(v for v in config.PROXIES.values() if v):
                    self.session.proxies.update(config.PROXIES)
            except Exception:
                self.session.proxies = {}
        
        self.base_url = "https://proceedings.mlr.press"
        self.search_url = "https://proceedings.mlr.press"
    
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
            
            if config.DEBUG:
                print(f"  [DEBUG] PMLR 搜索: {cleaned_query}")
            
            # PMLR 没有公开的搜索 API，我们通过以下方法：
            # 方法1: 使用 Google Scholar 的站点搜索（如果可用）
            # 方法2: 从其他搜索引擎的结果中查找 PMLR 链接
            # 方法3: 直接尝试构建可能的 PMLR URL（需要卷号和论文ID）
            
            # 注意：PMLR 搜索最好结合其他引擎使用
            # 因为 PMLR 本身没有搜索 API，通常需要先找到论文的 PMLR URL
            
            # 这里提供一个框架，实际搜索可能需要结合其他引擎
            if config.DEBUG:
                print(f"  [DEBUG] PMLR 搜索：注意 PMLR 需要先知道论文的 URL 或卷号")
                print(f"  [DEBUG] PMLR 搜索：建议通过 DBLP 或 Google Scholar 先找到 PMLR 链接")
            
            # 返回 None，让其他引擎先搜索
            # 如果其他引擎找到了 PMLR URL，会调用 _extract_from_pmlr_url 来提取信息
            return None
            
        except Exception as e:
            if config.DEBUG:
                print(f"  [DEBUG] PMLR 搜索失败: {e}")
            return None
    
    def _extract_from_pmlr_url(self, url: str, query: str) -> Optional[Dict[str, Any]]:
        """
        从 PMLR URL 提取论文信息
        
        Args:
            url: PMLR 论文页面 URL
            query: 原始查询（用于验证）
            
        Returns:
            论文信息字典
        """
        try:
            response = self.session.get(url, timeout=config.REQUEST_TIMEOUT)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'lxml')
            
            # 提取论文信息
            result = {
                'title': '',
                'authors': [],
                'year': None,
                'venue': 'Proceedings of Machine Learning Research',
                'url': url,
                'source': 'pmlr',
            }
            
            # 提取标题
            title_elem = soup.find('h1') or soup.find('title')
            if title_elem:
                result['title'] = title_elem.get_text(strip=True)
            
            # 提取作者（通常在特定标签中）
            authors_elems = soup.find_all(['span', 'div', 'p'], class_=re.compile(r'author', re.I))
            if not authors_elems:
                # 尝试查找包含 "Author" 的文本
                for elem in soup.find_all(['div', 'p']):
                    text = elem.get_text()
                    if 'author' in text.lower() and ':' in text:
                        authors_text = text.split(':')[-1].strip()
                        authors = [a.strip() for a in authors_text.split(',') if a.strip()]
                        if authors:
                            result['authors'] = authors
                            break
            
            # 提取年份（通常在 URL 或页面中）
            year_match = re.search(r'\b(20\d{2})\b', url)
            if year_match:
                result['year'] = int(year_match.group(1))
            
            # 提取卷号和页码
            volume_match = re.search(r'/v(\d+)/', url)
            if volume_match:
                result['volume'] = volume_match.group(1)
            
            # 尝试提取 BibTeX（PMLR 通常提供）
            bibtex = self._extract_bibtex_from_page(soup)
            if bibtex:
                result['bibtex'] = bibtex
                # 从 BibTeX 中提取更多信息
                pages = self._extract_pages_from_bibtex(bibtex)
                if pages:
                    result['pages'] = pages
                
                # 提取年份
                year_match = re.search(r'year\s*=\s*\{(\d+)\}', bibtex)
                if year_match:
                    result['year'] = int(year_match.group(1))
            
            # 验证匹配度
            if result['title']:
                score = similarity_score(query, result['title'])
                if score < 0.3:
                    return None
            
            return result
            
        except Exception as e:
            if config.DEBUG:
                print(f"  [DEBUG] 从 PMLR URL 提取信息失败: {e}")
            return None
    
    def _extract_bibtex_from_page(self, soup: BeautifulSoup) -> Optional[str]:
        """
        从 PMLR 页面提取 BibTeX
        
        Args:
            soup: BeautifulSoup 对象
            
        Returns:
            BibTeX 字符串
        """
        # 查找 BibTeX 链接
        bibtex_links = soup.find_all('a', href=re.compile(r'bibtex|bib', re.I))
        for link in bibtex_links:
            href = link.get('href')
            if href:
                try:
                    if href.startswith('/'):
                        href = urljoin(self.base_url, href)
                    elif not href.startswith('http'):
                        href = urljoin(self.base_url, href)
                    
                    response = self.session.get(href, timeout=config.REQUEST_TIMEOUT)
                    response.raise_for_status()
                    bibtex = response.text
                    
                    if '@' in bibtex and ('inproceedings' in bibtex or 'article' in bibtex):
                        return bibtex
                except Exception:
                    continue
        
        # 查找内嵌的 BibTeX（在 <pre> 或 <code> 标签中）
        pre_tags = soup.find_all(['pre', 'code'])
        for pre in pre_tags:
            text = pre.get_text()
            if '@' in text and ('inproceedings' in text or 'article' in text):
                return text
        
        return None
    
    def _extract_pages_from_bibtex(self, bibtex: str) -> Optional[str]:
        """
        从 BibTeX 中提取页码
        
        Args:
            bibtex: BibTeX 字符串
            
        Returns:
            页码字符串
        """
        if not bibtex:
            return None
        
        # 匹配 pages 字段
        patterns = [
            r'pages\s*=\s*\{(\d+)\s*[-–—]{1,3}\s*(\d+)\}',
            r'pages\s*=\s*(\d+)\s*[-–—]{1,3}\s*(\d+)',
            r'pages\s*=\s*\{(\d+)\}',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, bibtex, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    return f"{groups[0]}-{groups[1]}"
                elif len(groups) >= 1:
                    return groups[0]
        
        return None
    
    def search_by_volume_and_paper(self, volume: int, paper_id: str) -> Optional[Dict[str, Any]]:
        """
        通过卷号和论文 ID 直接访问 PMLR 论文
        
        Args:
            volume: 卷号
            paper_id: 论文 ID
            
        Returns:
            论文信息字典
        """
        url = f"{self.base_url}/v{volume}/{paper_id}.html"
        return self._extract_from_pmlr_url(url, "")

