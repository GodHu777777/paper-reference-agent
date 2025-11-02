"""
LLM 配置示例文件

复制此文件为 llm_config.py 并修改配置
"""
import os

# ==========================================
# API 配置
# ==========================================

# OpenAI API 示例
BASE_URL = "https://api.openai.com/v1"
MODEL_NAME = "gpt-3.5-turbo"
API_KEY = os.getenv("OPENAI_API_KEY", "")

# 本地 Ollama 示例
# BASE_URL = "http://localhost:11434/v1"
# MODEL_NAME = "llama2"
# API_KEY = ""

# Azure OpenAI 示例
# BASE_URL = "https://your-resource.openai.azure.com/v1"
# MODEL_NAME = "gpt-35-turbo"
# API_KEY = "your-azure-api-key"

# ==========================================
# 生成参数
# ==========================================

TEMPERATURE = 0.3  # 较低温度确保提取准确性
MAX_TOKENS = 500
TIMEOUT = 30  # 请求超时（秒）

# ==========================================
# 功能开关
# ==========================================

ENABLE_LLM_EXTRACTION = True  # 设为 False 禁用 LLM 提取

# ==========================================
# 代理设置（可选）
# ==========================================

PROXIES = None  # 不需要代理时设为 None
# PROXIES = {
#     "http": "http://127.0.0.1:7890",
#     "https": "http://127.0.0.1:7890",
# } if os.getenv("LLM_USE_PROXY", "false").lower() == "true" else None

