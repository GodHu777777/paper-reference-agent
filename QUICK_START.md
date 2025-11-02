# 快速开始指南

## 安装

```bash
# 安装依赖
pip install -r requirements.txt
```

## 使用方式

### 1. 命令行使用（推荐）

#### 单个查询
```bash
python agent.py "Attention is All You Need"
```

#### 批量查询
创建一个文件 `papers.txt`，每行一个论文标题：
```
Attention is All You Need
BERT: Pre-training of Deep Bidirectional Transformers
GPT-3: Language Models are Few-Shot Learners
```

然后运行：
```bash
python agent.py --batch papers.txt
```

#### 导出为 BibTeX
```bash
python agent.py "BERT: Pre-training of Deep Bidirectional Transformers" --export bibtex --output bert.bib
```

#### 导出为 JSON
```bash
python agent.py "Attention is All You Need" --export json --output result.json
```

#### 查看缓存统计
```bash
python agent.py --stats
```

#### 清空缓存
```bash
python agent.py --clear-cache
```

### 2. Python API 使用

```python
from paper_agent import PaperAgent

# 创建 Agent
agent = PaperAgent()

# 搜索单篇论文
result = agent.search("Attention is All You Need")

if result:
    print(f"标题: {result['title']}")
    print(f"作者: {', '.join(result['authors'])}")
    print(f"年份: {result['year']}")
    print(f"会议: {result['venue']}")
    print(f"页码: {result.get('pages', '未找到')}")
    print(f"URL: {result.get('url', 'N/A')}")

# 批量搜索
queries = [
    "Attention is All You Need",
    "BERT: Pre-training of Deep Bidirectional Transformers"
]
results = agent.batch_search(queries)
```

### 3. Web 界面

```bash
python web_app.py
```

然后打开浏览器访问：http://localhost:5000

## 配置

### Semantic Scholar API Key（推荐）

为了提高查询速度，建议申请 Semantic Scholar API Key：

1. 访问 https://www.semanticscholar.org/product/api
2. 注册并申请 API Key
3. 设置环境变量：
   ```bash
   # Windows (PowerShell)
   $env:SEMANTIC_SCHOLAR_API_KEY="your_api_key_here"
   
   # Linux/Mac
   export SEMANTIC_SCHOLAR_API_KEY="your_api_key_here"
   ```

或者在 `config.py` 文件中直接设置（不推荐，可能泄露密钥）。

### 代理设置

如果需要使用代理，编辑 `config.py`：

```python
PROXIES = {
    "http": "http://127.0.0.1:7890",
    "https": "http://127.0.0.1:7890",
}
```

## 常见问题

### 1. 为什么有些论文找不到页码？

- 页码信息依赖于数据源（DBLP、Semantic Scholar 等）是否有相关信息
- 某些较新的论文或预印本可能没有页码
- 建议尝试多个搜索引擎

### 2. 查询速度慢怎么办？

- 使用缓存：默认启用缓存，重复查询会很快
- 申请 Semantic Scholar API Key 以提高速率限制
- 批量查询时使用缓存避免重复请求

### 3. 如何提高准确性？

- 使用完整的论文标题
- 确保标题拼写正确
- 如果第一次搜索未找到，可以尝试去掉副标题或特殊字符

### 4. 支持哪些会议/期刊？

理论上支持所有在以下数据库中收录的会议/期刊：
- DBLP（计算机科学领域）
- Semantic Scholar（跨领域）
- CrossRef（跨领域）

常见支持的会议：
- AAAI
- NeurIPS (NIPS)
- ICML
- ICLR
- CVPR
- ICCV
- ACL
- EMNLP

## 示例

查看 `examples.py` 文件了解更多使用示例。

```bash
python examples.py
```

## 输出格式

### 控制台输出示例

```
搜索中 (semantic_scholar): Attention is All You Need...
============================================================
标题: Attention Is All You Need
作者: Ashish Vaswani, Noam Shazeer, Niki Parmar, ...
年份: 2017
会议/期刊: NIPS
页码: 5998-6008
URL: https://papers.nips.cc/paper/7181-attention-is-all-you-need
数据源: semantic_scholar
============================================================
```

### JSON 格式

```json
{
  "title": "Attention Is All You Need",
  "authors": ["Ashish Vaswani", "Noam Shazeer", ...],
  "year": 2017,
  "venue": "NIPS",
  "pages": "5998-6008",
  "url": "https://papers.nips.cc/paper/7181-attention-is-all-you-need",
  "source": "semantic_scholar"
}
```

### BibTeX 格式

```bibtex
@inproceedings{Vaswani2017,
  title={Attention Is All You Need},
  author={Vaswani, Ashish and Shazeer, Noam and ...},
  booktitle={NIPS},
  year={2017},
  pages={5998-6008},
  url={https://papers.nips.cc/paper/7181-attention-is-all-you-need},
}
```

## 高级用法

### 自定义搜索引擎顺序

编辑 `config.py`：

```python
SEARCH_ENGINES = [
    "dblp",             # 优先使用 DBLP
    "semantic_scholar",  # 备用
    "crossref",         # 最后尝试
]
```

### 禁用缓存

```python
from paper_agent import PaperAgent

agent = PaperAgent()
result = agent.search("论文标题", use_cache=False)
```

## 许可证

MIT License

