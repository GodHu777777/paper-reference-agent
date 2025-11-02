"""
配置文件
"""
import os
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).parent

# 缓存目录
CACHE_DIR = BASE_DIR / "cache"
CACHE_DIR.mkdir(exist_ok=True)

# API 配置
# Semantic Scholar API Key (可选，但建议申请以提高速率限制)
# 申请地址: https://www.semanticscholar.org/product/api
SEMANTIC_SCHOLAR_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")

# 请求超时设置（秒）
REQUEST_TIMEOUT = 30

# 代理设置（如果需要）
# 通过环境变量 PROXIES 设置代理，格式: "http://127.0.0.1:65008"
# 如果不设置或设置为空字符串，则不使用代理（适合服务器部署）
PROXIES_ENV = os.getenv("PROXIES", "").strip()
if PROXIES_ENV and PROXIES_ENV.lower() not in ("none", "false", ""):
    # 如果环境变量设置了代理，使用它
    if "://" in PROXIES_ENV:
        proxy_url = PROXIES_ENV
        PROXIES = {
            "http": proxy_url,
            "https": proxy_url,
        }
    else:
        PROXIES = {}
else:
    # 默认不使用代理（适合服务器直接访问互联网的情况）
    PROXIES = {}

# User-Agent
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# 搜索引擎优先级
SEARCH_ENGINES = [
    "dblp",             # DBLP（计算机科学领域，推荐）
    "google_scholar",   # Google Scholar（跨领域，数据全面）
    "crossref",         # CrossRef（跨领域）
]

# 缓存有效期（天）
CACHE_EXPIRY_DAYS = 30

# 日志配置
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR

# 调试模式（是否显示详细的调试信息）
# DEBUG = os.getenv("DEBUG", "false").lower() == "false"  # 默认关闭，可通过环境变量启用
DEBUG = False

# Selenium 配置（用于绕过 Cloudflare 保护）
USE_SELENIUM = os.getenv("USE_SELENIUM", "false").lower() == "true"  # 默认关闭
SELENIUM_BROWSER = os.getenv("SELENIUM_BROWSER", "chrome")  # chrome, firefox, edge
SELENIUM_HEADLESS = os.getenv("SELENIUM_HEADLESS", "true").lower() == "true"  # 是否无头模式
SELENIUM_WAIT_TIME = int(os.getenv("SELENIUM_WAIT_TIME", "10"))  # 等待时间（秒）
