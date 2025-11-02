# LLM 配置说明

本系统支持使用大语言模型（LLM）从网页内容中提取页码信息，提高提取准确性。

## 功能说明

当传统的 HTML 解析方法无法找到页码时，系统会自动调用大模型 API：
1. 获取网页 HTML 内容
2. 清理并提取文本
3. 发送给大模型 API 进行分析
4. 从大模型的回复中提取页码范围

## 配置方法

### 方法 1: 修改配置文件（推荐）

直接编辑 `llm_config.py` 文件：

```python
# API 配置
BASE_URL = "https://api.openai.com/v1"  # 或你的 API 地址
MODEL_NAME = "gpt-3.5-turbo"  # 或 gpt-4, claude-3 等
API_KEY = "sk-your-api-key-here"
```

### 方法 2: 使用环境变量

#### Windows (PowerShell)
```powershell
$env:LLM_BASE_URL="https://api.openai.com/v1"
$env:LLM_MODEL_NAME="gpt-3.5-turbo"
$env:LLM_API_KEY="sk-your-api-key-here"
```

#### Linux/Mac
```bash
export LLM_BASE_URL="https://api.openai.com/v1"
export LLM_MODEL_NAME="gpt-3.5-turbo"
export LLM_API_KEY="sk-your-api-key-here"
```

## 支持的 API 提供商

### 1. OpenAI

```python
BASE_URL = "https://api.openai.com/v1"
MODEL_NAME = "gpt-3.5-turbo"  # 或 "gpt-4"
API_KEY = "sk-..."  # 从 https://platform.openai.com/api-keys 获取
```

### 2. 本地部署（如 Ollama）

```python
BASE_URL = "http://localhost:11434/v1"
MODEL_NAME = "llama2"  # 或其他本地模型
API_KEY = ""  # 本地部署通常不需要 API Key
```

### 3. 其他兼容 OpenAI 格式的 API

- Azure OpenAI
- Google Gemini (如果支持 OpenAI 格式)
- 其他自定义 API 服务

```python
BASE_URL = "https://your-api-endpoint.com/v1"
MODEL_NAME = "your-model-name"
API_KEY = "your-api-key"
```

## 配置参数说明

| 参数 | 说明 | 默认值 | 示例 |
|------|------|--------|------|
| `BASE_URL` | API 基础 URL | `https://api.openai.com/v1` | `http://localhost:11434/v1` |
| `MODEL_NAME` | 模型名称 | `gpt-3.5-turbo` | `gpt-4`, `llama2` |
| `API_KEY` | API 密钥 | `""` | `sk-...` |
| `TEMPERATURE` | 生成温度（0-2） | `0.3` | 较低值确保准确性 |
| `MAX_TOKENS` | 最大 token 数 | `500` | |
| `TIMEOUT` | 请求超时（秒） | `30` | |
| `ENABLE_LLM_EXTRACTION` | 是否启用 LLM 提取 | `True` | 设为 `False` 禁用 |

## 禁用 LLM 提取

如果你不想使用 LLM 提取，可以：

1. **在配置文件中设置：**
   ```python
   ENABLE_LLM_EXTRACTION = False
   ```

2. **使用环境变量：**
   ```bash
   export LLM_ENABLE="false"
   ```

## 工作流程

1. **传统方法优先**：系统首先尝试传统的 HTML 解析方法（如查找特定 CSS 类）
2. **LLM 后备**：如果传统方法失败，且 `ENABLE_LLM_EXTRACTION=True`，系统会：
   - 下载网页内容
   - 清理 HTML 文本
   - 发送给大模型 API
   - 从回复中提取页码

## 示例

### 使用 OpenAI API

```python
# llm_config.py
BASE_URL = "https://api.openai.com/v1"
MODEL_NAME = "gpt-3.5-turbo"
API_KEY = "sk-your-openai-api-key"
```

### 使用本地 Ollama

```python
# llm_config.py
BASE_URL = "http://localhost:11434/v1"
MODEL_NAME = "llama2"
API_KEY = ""
```

然后启动 Ollama：
```bash
ollama serve
```

### 使用 Azure OpenAI

```python
# llm_config.py
BASE_URL = "https://your-resource.openai.azure.com/v1"
MODEL_NAME = "gpt-35-turbo"  # 部署名称
API_KEY = "your-azure-api-key"
```

## 注意事项

1. **API 费用**：使用 LLM API 可能产生费用，请注意成本
2. **速率限制**：某些 API 提供商有速率限制，可能需要等待
3. **隐私**：网页内容会发送给 LLM API，请确保遵守隐私政策
4. **超时**：如果 API 响应慢，可以调整 `TIMEOUT` 参数

## 故障排除

### API 认证失败（401）
- 检查 `API_KEY` 是否正确
- 确认 API Key 有效且有权限

### 速率限制（429）
- 等待一段时间后重试
- 考虑使用本地部署的模型（如 Ollama）

### 连接超时
- 检查 `BASE_URL` 是否正确
- 确认网络连接正常
- 增加 `TIMEOUT` 值

### LLM 未提取到页码
- 检查网页是否包含页码信息
- 尝试使用更强的模型（如 gpt-4）
- 检查 `ENABLE_LLM_EXTRACTION` 是否为 `True`

## 测试配置

运行以下命令测试 LLM 配置：

```bash
python agent.py "你的论文标题"
```

如果看到 "使用 LLM 从网页提取页码..." 的消息，说明 LLM 配置正常工作。

