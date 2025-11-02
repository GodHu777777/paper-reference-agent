"""
使用大模型 API 从网页内容提取页码信息
"""
import requests
import json
import re
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup

import llm_config
import config
from .utils import normalize_pages

# 尝试导入 cloudscraper（用于绕过 Cloudflare 保护）
try:
    import cloudscraper
    CLOUDSCRAPER_AVAILABLE = True
except ImportError:
    CLOUDSCRAPER_AVAILABLE = False

# 尝试导入 Selenium（用于执行 JavaScript，绕过 Cloudflare）
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.firefox.options import Options as FirefoxOptions
    from selenium.webdriver.firefox.service import Service as FirefoxService
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException
    from webdriver_manager.chrome import ChromeDriverManager
    from webdriver_manager.firefox import GeckoDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


class LLMExtractor:
    """使用大模型从网页内容提取页码"""
    
    def __init__(self):
        # API 请求用的 session（用于调用 LLM API）
        self.api_session = requests.Session()
        # 只在 LLM 代理配置不为空时使用
        if llm_config.PROXIES and isinstance(llm_config.PROXIES, dict) and llm_config.PROXIES:
            try:
                if any(v for v in llm_config.PROXIES.values() if v):
                    self.api_session.proxies.update(llm_config.PROXIES)
            except Exception:
                self.api_session.proxies = {}
        
        # 设置 API Key（如果有）
        if llm_config.API_KEY:
            self.api_session.headers.update({
                'Authorization': f'Bearer {llm_config.API_KEY}'
            })
        
        self.api_session.headers.update({
            'Content-Type': 'application/json',
        })
        
        # 网页访问用的 session（使用 config.PROXIES）
        # 对于受 Cloudflare 保护的网站（如 ACM），使用 cloudscraper
        if CLOUDSCRAPER_AVAILABLE:
            # 使用 cloudscraper 创建 session（可以绕过 Cloudflare）
            self.web_session = cloudscraper.create_scraper(
                browser={
                    'browser': 'chrome',
                    'platform': 'windows',
                    'desktop': True
                }
            )
            # 设置代理（如果配置了且有效）
            if config.PROXIES and isinstance(config.PROXIES, dict) and config.PROXIES:
                try:
                    if any(v for v in config.PROXIES.values() if v):
                        self.web_session.proxies.update(config.PROXIES)
                except Exception:
                    self.web_session.proxies = {}
        else:
            # 如果没有 cloudscraper，使用普通 requests
            self.web_session = requests.Session()
            # 设置更真实的浏览器请求头，避免被网站阻止
            self.web_session.headers.update({
                'User-Agent': config.USER_AGENT,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Cache-Control': 'max-age=0',
            })
            # 只有当 PROXIES 不为空且有效时才设置代理
            if config.PROXIES and isinstance(config.PROXIES, dict) and config.PROXIES:
                try:
                    if any(v for v in config.PROXIES.values() if v):
                        self.web_session.proxies.update(config.PROXIES)
                except Exception:
                    self.web_session.proxies = {}
        
        # Selenium WebDriver（延迟初始化）
        self.driver = None
    
    def extract_from_url(self, url: str, paper_title: str = None) -> Optional[str]:
        """
        从 URL 获取网页内容，使用大模型提取页码
        
        Args:
            url: 网页 URL
            paper_title: 论文标题（可选，帮助大模型理解上下文）
            
        Returns:
            页码字符串，如 "123-145"，如果未找到则返回 None
        """
        if not llm_config.ENABLE_LLM_EXTRACTION:
            return None
        
        try:
            # 获取网页内容（使用 web_session，使用 config.PROXIES）
            response = self.web_session.get(
                url,
                timeout=config.REQUEST_TIMEOUT
            )
            response.raise_for_status()
            
            # 解析 HTML
            soup = BeautifulSoup(response.content, 'lxml')
            
            # 提取文本内容（去除脚本和样式）
            for script in soup(["script", "style", "meta", "link"]):
                script.decompose()
            
            text = soup.get_text(separator=' ', strip=True)
            
            # 限制文本长度（避免 token 过多）
            if len(text) > 8000:
                text = text[:8000] + "..."
            
            # 使用大模型提取页码
            return self._extract_with_llm(text, url, paper_title)
            
        except Exception as e:
            print(f"LLM 提取页码失败 ({url}): {e}")
            return None
    
    def _extract_with_llm(self, webpage_text: str, url: str, 
                         paper_title: str = None) -> Optional[str]:
        """
        调用大模型 API 提取页码信息
        
        Args:
            webpage_text: 网页文本内容
            url: 网页 URL
            paper_title: 论文标题
            
        Returns:
            页码字符串
        """
        try:
            # 构建提示词
            prompt = self._build_prompt(webpage_text, url, paper_title)
            
            # 调用 API
            messages = [
                {
                    "role": "system",
                    "content": "你是一个专业的学术论文信息提取助手。你的任务是从网页内容中准确提取论文的页码范围信息。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            
            # 构建请求
            api_url = f"{llm_config.BASE_URL}/chat/completions"
            
            payload = {
                "model": llm_config.MODEL_NAME,
                "messages": messages,
                "temperature": llm_config.TEMPERATURE,
                "max_tokens": llm_config.MAX_TOKENS,
            }
            
            # 发送请求（使用 api_session，使用 llm_config.PROXIES）
            response = self.api_session.post(
                api_url,
                json=payload,
                timeout=llm_config.TIMEOUT
            )
            response.raise_for_status()
            
            # 解析响应
            result = response.json()
            
            # 提取回复内容
            if 'choices' in result and len(result['choices']) > 0:
                content = result['choices'][0]['message']['content'].strip()
                
                # 从回复中提取页码
                pages = self._parse_llm_response(content)
                
                if pages:
                    return normalize_pages(pages)
            
            return None
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                print(f"⚠ LLM API 认证失败，请检查 API Key")
            elif e.response.status_code == 429:
                print(f"⚠ LLM API 速率限制，请稍后重试")
            else:
                print(f"⚠ LLM API 错误: {e}")
            return None
        except Exception as e:
            print(f"⚠ LLM 调用失败: {e}")
            return None
    
    def _build_prompt(self, webpage_text: str, url: str, 
                     paper_title: str = None) -> str:
        """构建提示词"""
        prompt = f"""请从以下网页内容中提取论文的页码范围信息。

网页 URL: {url}
"""
        
        if paper_title:
            prompt += f"论文标题: {paper_title}\n"
        
        prompt += f"""
网页内容:
{webpage_text}

请仔细查找以下信息：
1. 页码范围（如 "123-145", "pages 123-145", "pp. 123-145" 等）
2. 会议或期刊的页码信息
3. 论文在会议集中的页码范围

如果找到了页码信息，请只返回页码范围（格式：开始页-结束页，例如 "123-145"）。
如果没有找到，请只返回 "未找到"。

只返回页码信息，不要返回其他内容。
"""
        return prompt
    
    def _parse_llm_response(self, response: str) -> Optional[str]:
        """
        解析大模型的回复，提取页码信息
        
        Args:
            response: 大模型的回复文本
            
        Returns:
            页码字符串，如果未找到则返回 None
        """
        # 移除常见的前缀和说明文字
        response = response.lower().strip()
        
        # 检查是否包含"未找到"或类似表述
        if any(keyword in response for keyword in ['未找到', 'not found', '没有找到', '无']):
            return None
        
        # 尝试提取页码模式
        import re
        
        # 匹配各种页码格式
        patterns = [
            r'(\d+)\s*[-–—]\s*(\d+)',  # 123-145, 123–145, 123—145
            r'pages?\s*[:：]\s*(\d+)\s*[-–—]\s*(\d+)',  # pages: 123-145
            r'pp\.?\s*[:：]?\s*(\d+)\s*[-–—]\s*(\d+)',  # pp. 123-145
            r'页码范围[：:]\s*(\d+)\s*[-–—]\s*(\d+)',  # 页码范围: 123-145
        ]
        
        for pattern in patterns:
            match = re.search(pattern, response)
            if match:
                if len(match.groups()) >= 2:
                    return f"{match.group(1)}-{match.group(2)}"
        
        # 如果模式匹配失败，尝试直接提取数字对
        numbers = re.findall(r'\d+', response)
        if len(numbers) >= 2:
            return f"{numbers[0]}-{numbers[1]}"
        
        return None
    
    def extract_from_html(self, html_content: str, url: str = None, 
                         paper_title: str = None) -> Optional[str]:
        """
        直接从 HTML 内容提取页码（不重新下载）
        
        Args:
            html_content: HTML 内容
            url: 网页 URL（可选）
            paper_title: 论文标题（可选）
            
        Returns:
            页码字符串
        """
        if not llm_config.ENABLE_LLM_EXTRACTION:
            return None
        
        try:
            # 解析 HTML
            soup = BeautifulSoup(html_content, 'lxml')
            
            # 提取文本内容
            for script in soup(["script", "style", "meta", "link"]):
                script.decompose()
            
            text = soup.get_text(separator=' ', strip=True)
            
            # 限制文本长度
            if len(text) > 8000:
                text = text[:8000] + "..."
            
            # 使用大模型提取
            return self._extract_with_llm(text, url or "", paper_title)
            
        except Exception as e:
            print(f"LLM 从 HTML 提取页码失败: {e}")
            return None
    
    def extract_from_doi_url(self, doi_url: str, paper_title: str = None) -> Optional[str]:
        """
        专门从 DOI URL 提取页码
        
        Args:
            doi_url: DOI URL（例如 https://doi.org/10.18653/v1/2023.acl-long.782）
            paper_title: 论文标题（可选）
            
        Returns:
            页码字符串
        """
        if not llm_config.ENABLE_LLM_EXTRACTION:
            return None
        
        try:
            print(f"  正在访问 DOI 网页: {doi_url}")
            
            # 提取 DOI 标识符（例如：10.1145/3539618.3591695）
            doi_match = re.search(r'doi\.org/([^/]+/?.*)', doi_url)
            if not doi_match:
                print(f"  ⚠ 无法从 URL 提取 DOI")
                return None
            
            doi_identifier = doi_match.group(1)
            
            # 检查是否是 ACM DOI（前缀为 10.1145）
            if doi_identifier.startswith('10.1145/'):
                # 直接构造 ACM 的 URL，避免通过 doi.org 重定向
                acm_url = f"https://dl.acm.org/doi/{doi_identifier}"
                if config.DEBUG:
                    print(f"  [DEBUG] 检测到 ACM DOI，直接访问: {acm_url}")
                
                # 首先尝试使用 Selenium（如果启用）
                if config.USE_SELENIUM and SELENIUM_AVAILABLE:
                    print(f"  使用 Selenium 访问 ACM 网站...")
                    html_content = self._extract_with_selenium(acm_url)
                    if html_content:
                        # 检查是否是 Cloudflare 挑战页面
                        if 'just a moment' in html_content.lower() or 'checking your browser' in html_content.lower():
                            print(f"  ⚠ 仍然遇到 Cloudflare 保护，可能需要手动验证")
                            return None
                        # 使用 LLM 提取
                        return self._extract_from_html_with_llm(html_content, acm_url, paper_title)
                
                # 尝试直接访问 ACM URL（使用 cloudscraper 或 requests）
                try:
                    headers = {}
                    if hasattr(self.web_session, 'headers'):
                        headers = self.web_session.headers.copy()
                    headers['Referer'] = 'https://www.google.com/'
                    headers['Origin'] = 'https://www.google.com'
                    
                    response = self.web_session.get(
                        acm_url,
                        timeout=config.REQUEST_TIMEOUT,
                        headers=headers,
                        allow_redirects=True
                    )
                    
                    # 检查是否是 Cloudflare 保护
                    if response.status_code == 403 or ('just a moment' in response.text.lower()):
                        # 如果启用了 Selenium，再尝试一次
                        if config.USE_SELENIUM and SELENIUM_AVAILABLE:
                            print(f"  普通请求失败，尝试使用 Selenium...")
                            html_content = self._extract_with_selenium(acm_url)
                            if html_content and 'just a moment' not in html_content.lower():
                                return self._extract_from_html_with_llm(html_content, acm_url, paper_title)
                        print(f"  ⚠ ACM 网站受 Cloudflare 保护，无法自动访问")
                        print(f"  💡 提示: 建议使用其他搜索引擎（如 DBLP、Google Scholar）获取页码")
                        return None
                    
                    response.raise_for_status()
                    
                    # 解析 HTML
                    html_content = response.text
                    
                    # 检查是否是 Cloudflare 挑战页面
                    if 'just a moment' in html_content.lower() or 'checking your browser' in html_content.lower():
                        # 如果启用了 Selenium，再尝试一次
                        if config.USE_SELENIUM and SELENIUM_AVAILABLE:
                            print(f"  检测到 Cloudflare 保护，尝试使用 Selenium...")
                            html_content = self._extract_with_selenium(acm_url)
                            if html_content and 'just a moment' not in html_content.lower():
                                return self._extract_from_html_with_llm(html_content, acm_url, paper_title)
                        print(f"  ⚠ 网站使用了 Cloudflare 保护，无法自动访问")
                        print(f"  💡 提示: 建议使用其他搜索引擎（如 DBLP、Google Scholar）获取页码")
                        return None
                    
                    # 使用 LLM 提取
                    return self._extract_from_html_with_llm(html_content, acm_url, paper_title)
                    
                except requests.exceptions.HTTPError as e:
                    if e.response.status_code == 403:
                        # 如果启用了 Selenium，再尝试一次
                        if config.USE_SELENIUM and SELENIUM_AVAILABLE:
                            print(f"  遇到 403 错误，尝试使用 Selenium...")
                            html_content = self._extract_with_selenium(acm_url)
                            if html_content:
                                return self._extract_from_html_with_llm(html_content, acm_url, paper_title)
                        print(f"  ⚠ ACM 网站访问被拒绝 (403)")
                        print(f"  💡 提示: 建议使用其他搜索引擎（如 DBLP、Google Scholar）获取页码")
                    return None
                except Exception as e:
                    if config.DEBUG:
                        print(f"  [DEBUG] 直接访问 ACM URL 失败: {e}")
            
            # 对于其他 DOI，使用标准的重定向处理
            # 第一次请求：不跟随重定向，手动处理
            response = self.web_session.get(
                doi_url,
                timeout=config.REQUEST_TIMEOUT,
                allow_redirects=False  # 不自动跟随重定向
            )
            
            final_url = None
            
            # 处理不同的响应情况
            if response.status_code in [301, 302, 303, 307, 308]:
                # 标准重定向：从 Location 头获取 URL
                final_url = response.headers.get('Location')
                if not final_url:
                    # 如果没有 Location 头，可能是相对 URL
                    final_url = response.url
                if final_url and not final_url.startswith('http'):
                    # 相对 URL，拼接完整 URL
                    from urllib.parse import urljoin
                    final_url = urljoin(doi_url, final_url)
            elif response.status_code == 200:
                # 可能是重定向页面（HTML 中的重定向）
                html_content = response.text
                
                # 检查是否是 Handle Redirect 页面（DOI.org 的特殊重定向格式）
                if 'Handle Redirect' in html_content or '<a href=' in html_content:
                    soup = BeautifulSoup(html_content, 'lxml')
                    # 查找链接
                    link = soup.find('a', href=True)
                    if link:
                        final_url = link.get('href')
                        if not final_url.startswith('http'):
                            from urllib.parse import urljoin
                            final_url = urljoin(doi_url, final_url)
                    else:
                        # 尝试从文本中提取 URL
                        url_match = re.search(r'https?://[^\s<>"]+', html_content)
                        if url_match:
                            final_url = url_match.group(0)
                else:
                    # 直接是内容页面
                    final_url = response.url
                    html_content = response.text
                    return self._extract_from_html_with_llm(html_content, final_url, paper_title)
            
            if not final_url:
                print(f"  ⚠ 无法获取重定向后的 URL")
                return None
            
            if config.DEBUG:
                print(f"  [DEBUG] DOI 重定向到: {final_url}")
            
            # 检查是否是已知的受保护网站（但 ACM 已经在上面处理了）
            protected_domains = ['aclanthology.org', 'ieee.org']
            final_domain = final_url.split('/')[2] if '/' in final_url else ''
            
            if any(domain in final_domain.lower() for domain in protected_domains):
                print(f"  ⚠ 检测到受 Cloudflare 保护的网站 ({final_domain})，跳过访问")
                print(f"  💡 提示: 建议使用其他搜索引擎（如 DBLP、Google Scholar）获取页码")
                return None
            
            # 访问实际的目标 URL
            # 添加 Referer 头，表明来自 doi.org
            headers = {}
            if hasattr(self.web_session, 'headers'):
                headers = self.web_session.headers.copy()
            headers['Referer'] = doi_url
            headers['Origin'] = 'https://doi.org'
            
            response = self.web_session.get(
                final_url,
                timeout=config.REQUEST_TIMEOUT,
                headers=headers,
                allow_redirects=True
            )
            
            # 如果是 403 错误，可能是 Cloudflare 保护
            if response.status_code == 403:
                # 检查响应内容是否是 Cloudflare 挑战
                if 'just a moment' in response.text.lower() or 'checking your browser' in response.text.lower():
                    print(f"  ⚠ 网站使用了 Cloudflare 保护，无法自动访问")
                    print(f"  💡 提示: 建议使用其他搜索引擎（如 DBLP、Google Scholar）获取页码")
                    return None
                
                if config.DEBUG:
                    print(f"  [DEBUG] 遇到 403 错误，尝试改进请求头")
                
                # 尝试更真实的浏览器头
                headers.update({
                    'Referer': 'https://www.google.com/',
                    'Origin': 'https://www.google.com',
                })
                
                response = self.web_session.get(
                    final_url,
                    timeout=config.REQUEST_TIMEOUT,
                    headers=headers
                )
            
            response.raise_for_status()
            
            # 解析 HTML
            html_content = response.text
            
            # 检查是否是 Cloudflare 挑战页面
            if 'just a moment' in html_content.lower() or 'checking your browser' in html_content.lower():
                print(f"  ⚠ 网站使用了 Cloudflare 保护，无法自动访问")
                print(f"  💡 提示: 建议使用其他搜索引擎（如 DBLP、Google Scholar）获取页码")
                return None
            
            # 检查是否是错误页面或需要登录
            if 'access denied' in html_content.lower() or 'forbidden' in html_content.lower():
                print(f"  ⚠ 网页可能要求登录或访问被拒绝")
                if config.DEBUG:
                    print(f"  [DEBUG] 网页内容前 500 字符: {html_content[:500]}")
                return None
            
            # 使用 LLM 提取（传入完整 HTML，让 LLM 自己解析）
            return self._extract_from_html_with_llm(html_content, final_url, paper_title)
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                print(f"  ⚠ 访问被拒绝 (403): 网站可能阻止了自动化访问")
                print(f"  ⚠ 建议: 对于 ACM 等网站，可能需要使用代理或浏览器访问")
            elif e.response.status_code == 404:
                print(f"  ⚠ 网页不存在 (404)")
            else:
                print(f"  ⚠ HTTP 错误 {e.response.status_code}: {e}")
            return None
        except Exception as e:
            print(f"从 DOI URL 提取页码失败: {e}")
            if config.DEBUG:
                import traceback
                print(f"  [DEBUG] 错误详情: {traceback.format_exc()}")
            return None
    
    def _extract_from_html_with_llm(self, html_content: str, url: str, 
                                   paper_title: str = None) -> Optional[str]:
        """
        使用 LLM 从 HTML 内容中提取页码
        
        Args:
            html_content: 完整的 HTML 内容
            url: 网页 URL
            paper_title: 论文标题
            
        Returns:
            页码字符串
        """
        try:
            # 解析 HTML，提取关键信息
            soup = BeautifulSoup(html_content, 'lxml')
            
            # 移除脚本和样式
            for script in soup(["script", "style", "meta", "link", "nav", "footer", "header"]):
                script.decompose()
            
            # 提取可能包含页码的部分
            # 1. 查找包含 "pages" 或 "page" 的元素
            pages_elements = []
            for elem in soup.find_all(['div', 'span', 'p', 'td', 'li'], 
                                     string=re.compile(r'pages?|page\s*[:：]', re.I)):
                text = elem.get_text(strip=True)
                if text:
                    pages_elements.append(text)
            
            # 2. 提取主要文本内容
            main_text = soup.get_text(separator=' ', strip=True)
            
            # 构建发送给 LLM 的内容
            # 优先发送包含 "pages" 的元素，然后发送主要文本
            if pages_elements:
                text_content = '\n'.join(pages_elements[:10])  # 最多前10个相关元素
                if len(main_text) > 2000:
                    text_content += '\n\n主要内容:\n' + main_text[:5000]
            else:
                text_content = main_text[:8000]
            
            # 使用 LLM 提取
            pages = self._extract_with_llm(text_content, url, paper_title)
            
            if pages:
                return pages
            
            # 如果第一次失败，尝试发送更多上下文
            if len(main_text) > 8000:
                return self._extract_with_llm(main_text[:12000], url, paper_title)
            
            return None
            
        except Exception as e:
            print(f"LLM 从 HTML 提取页码失败: {e}")
            return None
    
    def _get_selenium_driver(self):
        """
        获取或创建 Selenium WebDriver
        
        Returns:
            WebDriver 实例
        """
        if self.driver is not None:
            return self.driver
        
        if not SELENIUM_AVAILABLE:
            return None
        
        try:
            browser = config.SELENIUM_BROWSER.lower()
            
            if browser == 'chrome':
                options = ChromeOptions()
                if config.SELENIUM_HEADLESS:
                    options.add_argument('--headless')
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                options.add_argument('--disable-blink-features=AutomationControlled')
                options.add_experimental_option("excludeSwitches", ["enable-automation"])
                options.add_experimental_option('useAutomationExtension', False)
                
                # 设置代理（如果配置了且有效）
                if config.PROXIES and isinstance(config.PROXIES, dict) and config.PROXIES:
                    try:
                        proxy_url = config.PROXIES.get('https') or config.PROXIES.get('http')
                        if proxy_url and proxy_url.strip():
                            options.add_argument(f'--proxy-server={proxy_url}')
                    except Exception:
                        pass  # 代理设置失败，继续执行
                
                # 使用 webdriver_manager 自动管理驱动
                try:
                    service = ChromeService(ChromeDriverManager().install())
                    self.driver = webdriver.Chrome(service=service, options=options)
                except Exception:
                    # 如果自动安装失败，尝试使用系统 PATH 中的驱动
                    self.driver = webdriver.Chrome(options=options)
                    
            elif browser == 'firefox':
                options = FirefoxOptions()
                if config.SELENIUM_HEADLESS:
                    options.add_argument('--headless')
                
                # 设置代理（如果配置了且有效）
                if config.PROXIES and isinstance(config.PROXIES, dict) and config.PROXIES:
                    try:
                        proxy_url = config.PROXIES.get('https') or config.PROXIES.get('http')
                        if proxy_url and proxy_url.strip():
                            from urllib.parse import urlparse
                            parsed = urlparse(proxy_url)
                            proxy_host = parsed.hostname
                            proxy_port = parsed.port or (8080 if parsed.scheme == 'http' else 443)
                            if proxy_host:
                                options.set_preference("network.proxy.type", 1)
                                options.set_preference("network.proxy.http", proxy_host)
                                options.set_preference("network.proxy.http_port", proxy_port)
                                options.set_preference("network.proxy.ssl", proxy_host)
                                options.set_preference("network.proxy.ssl_port", proxy_port)
                    except Exception:
                        pass  # 代理设置失败，继续执行
                
                try:
                    service = FirefoxService(GeckoDriverManager().install())
                    self.driver = webdriver.Firefox(service=service, options=options)
                except Exception:
                    self.driver = webdriver.Firefox(options=options)
            else:
                print(f"  ⚠ 不支持的浏览器: {browser}")
                return None
            
            # 设置窗口大小
            self.driver.set_window_size(1920, 1080)
            
            if config.DEBUG:
                print(f"  [DEBUG] Selenium WebDriver 初始化成功")
            
            return self.driver
            
        except Exception as e:
            print(f"  ⚠ Selenium WebDriver 初始化失败: {e}")
            print(f"  💡 提示: 请确保已安装浏览器驱动（ChromeDriver 或 GeckoDriver）")
            return None
    
    def _extract_with_selenium(self, url: str) -> Optional[str]:
        """
        使用 Selenium 访问网页并获取 HTML 内容
        
        Args:
            url: 网页 URL
            
        Returns:
            HTML 内容字符串
        """
        if not config.USE_SELENIUM:
            return None
        
        driver = self._get_selenium_driver()
        if not driver:
            return None
        
        try:
            if config.DEBUG:
                print(f"  [DEBUG] 使用 Selenium 访问: {url}")
            
            # 访问网页
            driver.get(url)
            
            # 等待页面加载（等待 Cloudflare 挑战完成或页面内容出现）
            wait = WebDriverWait(driver, config.SELENIUM_WAIT_TIME)
            
            try:
                # 等待 Cloudflare 挑战完成（检测到不再有 "Just a moment"）
                wait.until_not(
                    EC.presence_of_element_located((By.XPATH, "//title[contains(text(), 'Just a moment')]"))
                )
            except TimeoutException:
                # 如果超时，可能仍然在 Cloudflare 挑战页面
                if config.DEBUG:
                    print(f"  [DEBUG] 等待 Cloudflare 挑战超时")
                pass
            
            # 额外等待几秒，确保页面完全加载
            import time
            time.sleep(2)
            
            # 获取页面源码
            html_content = driver.page_source
            
            # 检查是否还在 Cloudflare 挑战页面
            if 'just a moment' in html_content.lower():
                print(f"  ⚠ 仍然在 Cloudflare 挑战页面，可能需要更长时间")
                # 再等待一段时间
                time.sleep(5)
                html_content = driver.page_source
            
            return html_content
            
        except TimeoutException:
            print(f"  ⚠ Selenium 访问超时")
            return None
        except WebDriverException as e:
            print(f"  ⚠ Selenium WebDriver 错误: {e}")
            return None
        except Exception as e:
            print(f"  ⚠ Selenium 访问失败: {e}")
            if config.DEBUG:
                import traceback
                print(f"  [DEBUG] 错误详情: {traceback.format_exc()}")
            return None
    
    def __del__(self):
        """清理资源：关闭 WebDriver"""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
