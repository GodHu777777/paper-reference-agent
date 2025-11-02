"""
NeurIPS (NIPS) 特定的页码提取器
从 NeurIPS 网页下载 BibTeX 并提取页码
"""
import re
import requests
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup

import config
from .utils import normalize_pages


class NeurIPSExtractor:
    """NeurIPS 特定的页码提取器"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': config.USER_AGENT})
        # 只在代理配置不为空且是有效字典时使用代理
        if config.PROXIES and isinstance(config.PROXIES, dict) and config.PROXIES:
            try:
                if any(v for v in config.PROXIES.values() if v):
                    self.session.proxies.update(config.PROXIES)
            except Exception:
                self.session.proxies = {}
        
        # 延迟导入 LLM 提取器
        self._llm_extractor = None
    
    def _get_llm_extractor(self):
        """获取 LLM 提取器（延迟加载）"""
        if self._llm_extractor is None:
            try:
                from .llm_extractor import LLMExtractor
                self._llm_extractor = LLMExtractor()
            except ImportError:
                pass
        return self._llm_extractor
    
    def extract_from_url(self, url: str, paper_title: str = None) -> Optional[str]:
        """
        从 NeurIPS URL 提取页码
        
        Args:
            url: NeurIPS 论文 URL
            paper_title: 论文标题（可选，用于 LLM 提取）
            
        Returns:
            页码字符串，如 "130136-130184"
        """
        if not url or 'neurips.cc' not in url.lower() and 'nips.cc' not in url.lower():
            return None
        
        try:
            # 下载网页
            response = self.session.get(url, timeout=config.REQUEST_TIMEOUT)
            response.raise_for_status()
            
            # 解析 HTML
            soup = BeautifulSoup(response.content, 'lxml')
            
            # 方法1: 尝试从网页中找到 BibTeX 链接或内容
            bibtex = self._extract_bibtex_from_page(soup, url)
            
            if bibtex:
                # 从 BibTeX 中提取页码
                pages = self._extract_pages_from_bibtex(bibtex)
                if pages:
                    return pages
            
            # 方法2: 如果直接提取失败，使用 LLM 从网页文本中提取
            llm_extractor = self._get_llm_extractor()
            if llm_extractor:
                print("  使用 LLM 从 NeurIPS 网页提取 BibTeX 页码...")
                pages = llm_extractor.extract_from_url(url, paper_title)
                if pages:
                    return pages
            
            return None
            
        except Exception as e:
            print(f"从 NeurIPS 网页提取页码失败: {e}")
            return None
    
    def _extract_bibtex_from_page(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        """
        从网页中提取 BibTeX 内容
        
        Args:
            soup: BeautifulSoup 对象
            url: 页面 URL
            
        Returns:
            BibTeX 字符串
        """
        # 方法1: 查找 BibTeX 链接（文本匹配）
        # NeurIPS 通常在页面上有 "BibTeX" 链接
        bibtex_links = soup.find_all('a', href=True)
        
        for link in bibtex_links:
            link_text = link.get_text(strip=True).lower()
            if 'bibtex' in link_text:
                bibtex_url = link.get('href')
                if not bibtex_url:
                    continue
                
                # 处理相对 URL
                from urllib.parse import urljoin
                if not bibtex_url.startswith('http'):
                    bibtex_url = urljoin(url, bibtex_url)
                
                try:
                    response = self.session.get(bibtex_url, timeout=config.REQUEST_TIMEOUT)
                    response.raise_for_status()
                    bibtex = response.text
                    
                    # 验证是否是有效的 BibTeX
                    if '@' in bibtex and ('inproceedings' in bibtex or 'article' in bibtex):
                        return bibtex
                except Exception:
                    continue
        
        # 方法2: 查找 href 中包含 "bib" 的链接
        all_links = soup.find_all('a', href=True)
        for link in all_links:
            href = link.get('href', '').lower()
            if 'bib' in href or 'bibtex' in href:
                from urllib.parse import urljoin
                bibtex_url = urljoin(url, link.get('href'))
                try:
                    response = self.session.get(bibtex_url, timeout=config.REQUEST_TIMEOUT)
                    response.raise_for_status()
                    bibtex = response.text
                    if '@' in bibtex and ('inproceedings' in bibtex or 'article' in bibtex):
                        return bibtex
                except Exception:
                    continue
        
        # 方法3: 查找预标签中的 BibTeX
        pre_tags = soup.find_all('pre')
        for pre in pre_tags:
            text = pre.get_text()
            if '@' in text and ('inproceedings' in text or 'article' in text):
                # 尝试提取完整的 BibTeX 块
                # 匹配从 @inproceedings 到最后一个 }
                match = re.search(r'@(inproceedings|article)\{[^}]+\{[^@]+\}', 
                                 text, re.DOTALL)
                if match:
                    return match.group(0)
                # 如果没有完整匹配，至少返回包含 @inproceedings 的文本块
                return text
        
        # 方法4: 查找 code 标签中的 BibTeX
        code_tags = soup.find_all('code')
        for code in code_tags:
            text = code.get_text()
            if '@' in text and ('inproceedings' in text or 'article' in text):
                match = re.search(r'@(inproceedings|article)\{[^}]+\{[^@]+\}', 
                                 text, re.DOTALL)
                if match:
                    return match.group(0)
        
        # 方法5: 查找脚本中的 BibTeX（某些页面使用 JavaScript 加载）
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                # 查找包含 @inproceedings 的脚本内容
                if '@inproceedings' in script.string or '@article' in script.string:
                    # 尝试提取完整的 BibTeX 块
                    match = re.search(r'@(inproceedings|article)\{[^}]+\{[^@]+\}', 
                                     script.string, re.DOTALL)
                    if match:
                        return match.group(0)
        
        # 方法6: 直接从页面 HTML 文本中查找 BibTeX 模式
        page_text = soup.get_text()
        # 查找包含 @inproceedings 和 pages 的文本
        if '@inproceedings' in page_text or '@article' in page_text:
            # 尝试提取完整的 BibTeX 块
            match = re.search(r'@(inproceedings|article)\{[^}]+\{[^@]+\}', 
                             page_text, re.DOTALL)
            if match:
                return match.group(0)
        
        return None
    
    def _extract_pages_from_bibtex(self, bibtex: str) -> Optional[str]:
        """
        从 BibTeX 字符串中提取页码
        
        Args:
            bibtex: BibTeX 格式的字符串
            
        Returns:
            页码字符串
        """
        if not bibtex:
            return None
        
        # 使用正则表达式提取 pages 字段
        # 匹配多种格式：
        # - pages = {130136--130184}  (NeurIPS 格式，双破折号)
        # - pages = {130136-130184}
        # - pages = 130136--130184
        # - pages = {130136}  (单页)
        
        patterns = [
            # 匹配 pages = {130136--130184} 或 pages = {130136-130184}
            r'pages\s*=\s*[{\"](\d+)\s*[-–—]{1,3}\s*(\d+)[}\"]?',  
            # 匹配 pages = 130136--130184 (无大括号)
            r'pages\s*=\s*(\d+)\s*[-–—]{1,3}\s*(\d+)',
            # 匹配单页 pages = {130136}
            r'pages\s*=\s*[{\"]?(\d+)[}\"]?',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, bibtex, re.IGNORECASE | re.MULTILINE)
            if match:
                groups = match.groups()
                if len(groups) >= 2 and groups[0] and groups[1]:
                    # 返回格式化的页码范围
                    return f"{groups[0]}-{groups[1]}"
                elif len(groups) >= 1 and groups[0]:
                    # 单页
                    return groups[0]
        
        # 如果正则匹配失败，尝试使用 LLM 提取
        llm_extractor = self._get_llm_extractor()
        if llm_extractor:
            try:
                # 使用 LLM 解析 BibTeX 文本
                pages = llm_extractor._parse_llm_response(bibtex)
                if pages:
                    return pages
            except Exception:
                pass
        
        return None
    
    def extract_from_bibtex_text(self, bibtex: str) -> Optional[str]:
        """
        直接从 BibTeX 文本提取页码（不下载网页）
        
        Args:
            bibtex: BibTeX 字符串
            
        Returns:
            页码字符串
        """
        return self._extract_pages_from_bibtex(bibtex)

