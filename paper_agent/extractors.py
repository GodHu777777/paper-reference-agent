"""
页码提取器
从不同来源提取页码信息
"""
import re
import requests
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup

import config
from .utils import normalize_pages


class PageExtractor:
    """页码提取器基类"""
    
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
    
    def extract(self, paper_info: Dict[str, Any]) -> Optional[str]:
        """
        提取页码
        
        Args:
            paper_info: 论文信息字典
            
        Returns:
            页码字符串，如 "123-145"
        """
        raise NotImplementedError


class SemanticScholarExtractor(PageExtractor):
    """从 Semantic Scholar API 提取页码"""
    
    def extract(self, paper_info: Dict[str, Any]) -> Optional[str]:
        """从 Semantic Scholar 返回的数据中提取页码"""
        # 直接从 API 返回数据中获取
        pages = paper_info.get('pages')
        if pages:
            return normalize_pages(pages)
        
        # 尝试从其他字段获取
        if 'publicationVenue' in paper_info:
            venue = paper_info['publicationVenue']
            if isinstance(venue, dict) and 'pages' in venue:
                return normalize_pages(venue['pages'])
        
        return None


class DBLPExtractor(PageExtractor):
    """从 DBLP 提取页码"""
    
    def __init__(self):
        super().__init__()
        # 延迟导入 LLM 提取器（避免循环依赖）
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
    
    def extract(self, paper_info: Dict[str, Any]) -> Optional[str]:
        """从 DBLP 数据中提取页码"""
        pages = paper_info.get('pages')
        if pages:
            return normalize_pages(pages)
        
        # 如果有 DBLP URL，尝试爬取
        dblp_url = paper_info.get('dblp_url') or paper_info.get('url')
        if dblp_url and 'dblp.org' in dblp_url:
            # 先尝试传统方法
            pages = self._fetch_from_dblp_page(dblp_url)
            if pages:
                return pages
            
            # 如果传统方法失败，尝试使用 LLM 提取
            llm_extractor = self._get_llm_extractor()
            if llm_extractor:
                print("  使用 LLM 从网页提取页码...")
                paper_title = paper_info.get('title', '')
                pages = llm_extractor.extract_from_url(dblp_url, paper_title)
                if pages:
                    return pages
        
        return None
    
    def _fetch_from_dblp_page(self, url: str) -> Optional[str]:
        """从 DBLP 页面爬取页码"""
        try:
            response = self.session.get(url, timeout=config.REQUEST_TIMEOUT)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'lxml')
            
            # 查找页码信息
            # DBLP 通常在 <span class="pages"> 标签中
            pages_elem = soup.find('span', class_='pages')
            if pages_elem:
                return normalize_pages(pages_elem.get_text())
            
            # 或者在 cite 标签中
            cite_elem = soup.find('cite', {'itemprop': 'pagination'})
            if cite_elem:
                return normalize_pages(cite_elem.get_text())
            
        except Exception as e:
            print(f"从 DBLP 页面提取页码失败: {e}")
        
        return None


class CrossRefExtractor(PageExtractor):
    """从 CrossRef API 提取页码"""
    
    def extract(self, paper_info: Dict[str, Any]) -> Optional[str]:
        """从 CrossRef 数据中提取页码"""
        pages = paper_info.get('pages')
        if pages:
            return normalize_pages(pages)
        
        # CrossRef 的页码可能在 'page' 字段
        if 'page' in paper_info:
            return normalize_pages(paper_info['page'])
        
        return None


class BibTeXExtractor(PageExtractor):
    """从 BibTeX 字符串提取页码"""
    
    def extract_from_bibtex(self, bibtex: str) -> Optional[str]:
        """
        从 BibTeX 字符串提取页码
        
        Args:
            bibtex: BibTeX 格式的字符串
            
        Returns:
            页码字符串
        """
        # 简单的正则匹配 pages 字段
        match = re.search(r'pages\s*=\s*[{\"]([^}\"]+)[}\"]', bibtex, re.IGNORECASE)
        if match:
            return normalize_pages(match.group(1))
        
        return None
    
    def extract_volume_issue_from_bibtex(self, bibtex: str) -> Dict[str, Optional[str]]:
        """
        从 BibTeX 字符串提取卷期号
        
        Args:
            bibtex: BibTeX 格式的字符串
            
        Returns:
            包含 volume 和 issue 的字典
        """
        result = {'volume': None, 'issue': None}
        
        # 提取 volume
        volume_match = re.search(r'volume\s*=\s*[{\"]([^}\"]+)[}\"]', bibtex, re.IGNORECASE)
        if volume_match:
            result['volume'] = volume_match.group(1).strip()
        
        # 提取 issue 或 number
        issue_match = re.search(r'(?:issue|number)\s*=\s*[{\"]([^}\"]+)[}\"]', bibtex, re.IGNORECASE)
        if issue_match:
            result['issue'] = issue_match.group(1).strip()
        
        return result


class DOI2BibExtractor(PageExtractor):
    """使用 doi2bib 命令行工具提取页码（通过 DOI 获取 BibTeX）"""
    
    def extract_from_doi(self, doi: str) -> Optional[str]:
        """
        从 DOI 通过 doi2bib 命令行工具获取 BibTeX 并提取页码
        
        Args:
            doi: DOI 标识符（例如：10.1016/j.trc.2015.04.007）
            
        Returns:
            页码字符串
        """
        import subprocess
        import sys
        import os
        
        try:
            print(f"    → 使用 doi2bib 获取 BibTeX...")
            print(f"    → DOI: {doi}")
            
            bibtex = None
            
            # 方法1: 尝试直接使用 Python API（doi2bib.crossref）
            try:
                import doi2bib.crossref as d2b_crossref
                print(f"    → 尝试使用 doi2bib.crossref Python API...")
                found, bibtex_result = d2b_crossref.get_bib(doi)
                if found and bibtex_result:
                    bibtex = bibtex_result.strip()
                    print(f"    → 通过 Python API 获取到 BibTeX，长度: {len(bibtex)} 字符")
            except ImportError:
                if config.DEBUG:
                    print(f"    [DEBUG] doi2bib.crossref 模块不可用")
            except Exception as e:
                if config.DEBUG:
                    print(f"    [DEBUG] Python API 调用失败: {e}")
            
            # 方法2: 如果 Python API 失败，尝试命令行工具（模拟命令行执行）
            if not bibtex:
                print(f"    → Python API 不可用，尝试命令行工具...")
                commands_to_try = [
                    ['doi2bib', doi],  # 直接命令
                    [sys.executable, '-m', 'doi2bib', doi],  # 使用当前 Python 解释器
                    ['python', '-m', 'doi2bib', doi],  # Python 模块方式（备用）
                ]
                
                for cmd in commands_to_try:
                    try:
                        print(f"    → 尝试执行命令: {' '.join(cmd)}")
                        
                        result = subprocess.run(
                            cmd,
                            capture_output=True,
                            text=True,
                            timeout=config.REQUEST_TIMEOUT,
                            check=False  # 不抛出异常，我们自己处理
                        )
                        
                        if config.DEBUG:
                            print(f"    [DEBUG] 返回码: {result.returncode}")
                            if result.stdout:
                                print(f"    [DEBUG] 标准输出前200字符: {result.stdout.strip()[:200]}")
                            if result.stderr:
                                print(f"    [DEBUG] 标准错误: {result.stderr.strip()[:200]}")
                        
                        # 如果命令成功（返回码为 0）且有输出
                        if result.returncode == 0 and result.stdout.strip():
                            bibtex = result.stdout.strip()
                            print(f"    → 通过命令行获取到 BibTeX，长度: {len(bibtex)} 字符")
                            break
                        elif result.returncode != 0:
                            if config.DEBUG:
                                print(f"    → 命令失败 (返回码: {result.returncode})")
                            continue
                            
                    except FileNotFoundError:
                        # 命令不存在，尝试下一个
                        if config.DEBUG:
                            print(f"    [DEBUG] 命令未找到: {' '.join(cmd)}")
                        continue
                    except subprocess.TimeoutExpired:
                        print(f"    ⚠ doi2bib 命令超时")
                        continue
                    except Exception as e:
                        if config.DEBUG:
                            print(f"    [DEBUG] 执行命令时出错: {e}")
                        continue
            
            if not bibtex:
                print(f"    ⚠ 所有方法尝试均失败")
                print(f"    💡 提示: 请确保已安装 doi2bib 工具: pip install doi2bib")
                print(f"    💡 或者检查是否可以通过命令行直接运行: doi2bib {doi}")
                return None
            
            # 显示 BibTeX 预览（前200字符）
            if config.DEBUG:
                print(f"    [DEBUG] BibTeX 预览: {bibtex[:200]}...")
            
            # 检查是否是错误信息
            if 'error' in bibtex.lower() or 'not found' in bibtex.lower() or 'invalid' in bibtex.lower():
                print(f"    ⚠ doi2bib 返回错误信息")
                if config.DEBUG:
                    print(f"    [DEBUG] 完整响应: {bibtex}")
                return None
            
            # 从 BibTeX 中提取页码
            print(f"    → 开始从 BibTeX 中提取页码...")
            bibtex_extractor = BibTeXExtractor()
            pages = bibtex_extractor.extract_from_bibtex(bibtex)
            
            if pages:
                print(f"    ✓ 成功提取页码: {pages}")
                return pages
            
            print(f"    ⚠ BibTeX 中未找到页码字段")
            
            # 如果启用调试，显示 BibTeX 内容以便排查
            if config.DEBUG:
                print(f"    [DEBUG] 完整 BibTeX 内容:")
                print(f"    {bibtex}")
            
            return None
            
        except Exception as e:
            print(f"    ⚠ 从 doi2bib 提取页码失败: {e}")
            if config.DEBUG:
                import traceback
                print(f"    [DEBUG] 错误详情: {traceback.format_exc()}")
            return None


class PDFMetadataExtractor(PageExtractor):
    """从 PDF 元数据提取页码（需要下载 PDF）"""
    
    def extract_from_pdf_url(self, pdf_url: str) -> Optional[Dict[str, Any]]:
        """
        从 PDF URL 提取元数据
        注意：这个方法需要下载 PDF，可能较慢
        
        Args:
            pdf_url: PDF 文件的 URL
            
        Returns:
            包含元数据的字典
        """
        # 这里只是示例，实际使用时需要 PyPDF2 或 pdfplumber
        # 由于下载和解析 PDF 较慢，建议作为后备方案
        
        try:
            # 首先尝试从 PDF 响应头获取页数
            response = self.session.head(pdf_url, timeout=config.REQUEST_TIMEOUT)
            content_length = response.headers.get('content-length')
            
            # 这里可以添加更复杂的 PDF 解析逻辑
            # 但需要安装额外的依赖包
            
            return None
            
        except Exception as e:
            print(f"从 PDF 提取元数据失败: {e}")
            return None


def extract_pages(paper_info: Dict[str, Any], source: str = 'auto') -> Optional[str]:
    """
    智能提取页码
    
    Args:
        paper_info: 论文信息字典
        source: 数据源类型 ('semantic_scholar', 'dblp', 'crossref', 'auto')
        
    Returns:
        页码字符串
    """
    # 检查是否是 NeurIPS URL
    url = paper_info.get('url') or paper_info.get('dblp_url')
    if url and ('neurips.cc' in url.lower() or 'nips.cc' in url.lower()):
        # 使用 NeurIPS 特定的提取器
        try:
            from .neurips_extractor import NeurIPSExtractor
            neurips_extractor = NeurIPSExtractor()
            paper_title = paper_info.get('title', '')
            pages = neurips_extractor.extract_from_url(url, paper_title)
            if pages:
                return pages
        except ImportError:
            pass
    
    extractors = {
        'semantic_scholar': SemanticScholarExtractor(),
        'dblp': DBLPExtractor(),
        'crossref': CrossRefExtractor(),
    }
    
    if source != 'auto' and source in extractors:
        # 使用指定的提取器
        return extractors[source].extract(paper_info)
    
    # 自动模式：尝试所有提取器
    for extractor in extractors.values():
        pages = extractor.extract(paper_info)
        if pages:
            return pages
    
    return None

