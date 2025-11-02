#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
使用示例
"""
from paper_agent import PaperAgent


def example_single_search():
    """示例 1: 单个论文搜索"""
    print("=" * 60)
    print("示例 1: 单个论文搜索")
    print("=" * 60)
    
    agent = PaperAgent()
    result = agent.search("Attention is All You Need")
    
    if result:
        print(f"\n标题: {result['title']}")
        print(f"作者: {', '.join(result['authors'])}")
        print(f"年份: {result['year']}")
        print(f"会议: {result['venue']}")
        print(f"页码: {result.get('pages', '未找到')}")
        print(f"URL: {result.get('url', 'N/A')}")
    else:
        print("\n未找到论文")


def example_batch_search():
    """示例 2: 批量搜索"""
    print("\n" + "=" * 60)
    print("示例 2: 批量搜索")
    print("=" * 60)
    
    queries = [
        "Attention is All You Need",
        "BERT: Pre-training of Deep Bidirectional Transformers",
        "GPT-3: Language Models are Few-Shot Learners"
    ]
    
    agent = PaperAgent()
    results = agent.batch_search(queries)
    
    for item in results:
        print(f"\n查询: {item['query']}")
        if item['result']:
            result = item['result']
            print(f"  标题: {result['title']}")
            print(f"  页码: {result.get('pages', '未找到')}")
        else:
            print("  未找到")


def example_without_cache():
    """示例 3: 不使用缓存"""
    print("\n" + "=" * 60)
    print("示例 3: 不使用缓存")
    print("=" * 60)
    
    agent = PaperAgent()
    result = agent.search("BERT: Pre-training of Deep Bidirectional Transformers", 
                          use_cache=False)
    
    if result:
        print(f"\n页码: {result.get('pages', '未找到')}")


def example_export_bibtex():
    """示例 4: 导出 BibTeX 格式"""
    print("\n" + "=" * 60)
    print("示例 4: 导出 BibTeX 格式")
    print("=" * 60)
    
    agent = PaperAgent()
    result = agent.search("Attention is All You Need")
    
    if result:
        from paper_agent.utils import format_bibtex_entry
        bibtex = format_bibtex_entry(result)
        print("\nBibTeX 格式:")
        print(bibtex)


if __name__ == '__main__':
    # 运行示例
    example_single_search()
    example_batch_search()
    example_export_bibtex()

