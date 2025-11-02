#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
命令行界面
"""
import argparse
import json
import sys
from pathlib import Path
from typing import List

from colorama import init, Fore, Style
from tqdm import tqdm

from paper_agent import PaperAgent
from paper_agent.utils import format_bibtex_entry
import config

# 初始化 colorama（Windows 需要）
init(autoreset=True)


def print_result(result: dict, query: str = None):
    """打印搜索结果"""
    if not result:
        print(f"{Fore.RED}✗ 未找到论文信息{Style.RESET_ALL}")
        return
    
    # 安全处理作者列表
    authors = result.get('authors', [])
    if authors:
        # 确保所有作者都是字符串
        authors_str = []
        for author in authors:
            if isinstance(author, dict):
                # 如果是字典，尝试提取名字
                name = author.get('text') or author.get('name') or str(author)
                authors_str.append(str(name))
            else:
                authors_str.append(str(author))
        authors_display = ', '.join(authors_str) if authors_str else 'N/A'
    else:
        authors_display = 'N/A'
    
    print(f"\n{Fore.GREEN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}标题:{Style.RESET_ALL} {result.get('title', 'N/A')}")
    print(f"{Fore.CYAN}作者:{Style.RESET_ALL} {authors_display}")
    print(f"{Fore.CYAN}年份:{Style.RESET_ALL} {result.get('year', 'N/A')}")
    print(f"{Fore.CYAN}会议/期刊:{Style.RESET_ALL} {result.get('venue', 'N/A')}")
    
    pages = result.get('pages')
    if pages:
        print(f"{Fore.GREEN}页码:{Style.RESET_ALL} {pages}")
    else:
        print(f"{Fore.YELLOW}页码:{Style.RESET_ALL} 未找到")
    
    if result.get('doi'):
        print(f"{Fore.CYAN}DOI:{Style.RESET_ALL} {result.get('doi')}")
    
    if result.get('url'):
        print(f"{Fore.CYAN}URL:{Style.RESET_ALL} {result.get('url')}")
    
    print(f"{Fore.CYAN}数据源:{Style.RESET_ALL} {result.get('source', 'N/A')}")
    
    # 添加引用格式输出
    from paper_agent.utils import format_citation_reference
    citation_ref = format_citation_reference(result)
    print(f"\n{Fore.YELLOW}{'─'*60}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}引用格式:{Style.RESET_ALL}")
    print(f"{Fore.WHITE}{citation_ref}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}{'─'*60}{Style.RESET_ALL}")
    
    print(f"\n{Fore.GREEN}{'='*60}{Style.RESET_ALL}\n")


def interactive_mode(agent, use_cache=True):
    """交互式对话模式"""
    print(f"\n{Fore.GREEN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}欢迎使用智能文献页码搜索 Agent (交互模式){Style.RESET_ALL}")
    print(f"{Fore.GREEN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}提示:{Style.RESET_ALL}")
    print(f"  - 输入论文标题进行搜索")
    print(f"  - 输入 {Fore.CYAN}q{Style.RESET_ALL}, {Fore.CYAN}quit{Style.RESET_ALL} 或 {Fore.CYAN}exit{Style.RESET_ALL} 退出")
    print(f"  - 输入 {Fore.CYAN}help{Style.RESET_ALL} 显示帮助信息")
    print(f"  - 输入 {Fore.CYAN}clear{Style.RESET_ALL} 清空屏幕")
    print(f"  - 输入 {Fore.CYAN}stats{Style.RESET_ALL} 查看缓存统计")
    print(f"{Fore.GREEN}{'='*60}{Style.RESET_ALL}\n")
    
    while True:
        try:
            # 获取用户输入
            query = input(f"{Fore.CYAN}请输入论文标题: {Style.RESET_ALL}").strip()
            
            # 处理空输入
            if not query:
                continue
            
            # 处理退出命令
            if query.lower() in ['q', 'quit', 'exit']:
                print(f"\n{Fore.GREEN}感谢使用，再见！{Style.RESET_ALL}\n")
                break
            
            # 处理帮助命令
            if query.lower() == 'help':
                print(f"\n{Fore.CYAN}可用命令:{Style.RESET_ALL}")
                print(f"  {Fore.GREEN}q, quit, exit{Style.RESET_ALL}  - 退出程序")
                print(f"  {Fore.GREEN}help{Style.RESET_ALL}         - 显示帮助信息")
                print(f"  {Fore.GREEN}clear{Style.RESET_ALL}        - 清空屏幕")
                print(f"  {Fore.GREEN}stats{Style.RESET_ALL}         - 查看缓存统计")
                print(f"  {Fore.GREEN}nocache{Style.RESET_ALL}      - 切换缓存模式（本次查询不使用缓存）")
                print(f"\n直接输入论文标题即可搜索。\n")
                continue
            
            # 处理清屏命令
            if query.lower() == 'clear':
                import os
                os.system('cls' if os.name == 'nt' else 'clear')
                continue
            
            # 处理统计命令
            if query.lower() == 'stats':
                stats = agent.cache.get_stats()
                print(f"\n{Fore.CYAN}缓存统计:{Style.RESET_ALL}")
                print(f"  总条目数: {stats['total_entries']}")
                print(f"  总大小: {stats['total_size_mb']:.2f} MB")
                print(f"  缓存目录: {stats['cache_dir']}\n")
                continue
            
            # 处理缓存切换（临时）
            no_cache = False
            if query.lower().startswith('nocache '):
                query = query[8:].strip()
                no_cache = True
                if not query:
                    print(f"{Fore.YELLOW}⚠ 请输入论文标题{Style.RESET_ALL}\n")
                    continue
            
            # 执行搜索
            print(f"\n{Fore.YELLOW}正在搜索: {query}{Style.RESET_ALL}\n")
            result = agent.search(query, use_cache=not no_cache if no_cache else use_cache)
            print_result(result, query)
            
        except KeyboardInterrupt:
            print(f"\n\n{Fore.YELLOW}检测到中断信号，退出中...{Style.RESET_ALL}")
            print(f"{Fore.GREEN}感谢使用，再见！{Style.RESET_ALL}\n")
            break
        except EOFError:
            print(f"\n\n{Fore.GREEN}感谢使用，再见！{Style.RESET_ALL}\n")
            break
        except Exception as e:
            print(f"{Fore.RED}✗ 发生错误: {e}{Style.RESET_ALL}\n")
            if config.DEBUG:
                import traceback
                traceback.print_exc()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='智能文献页码搜索 Agent',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python agent.py "Attention is All You Need"
  python agent.py --batch papers.txt
  python agent.py "BERT" --export bibtex
  python agent.py "GPT-3" --json output.json
  python agent.py --interactive  # 交互模式
        """
    )
    
    parser.add_argument(
        'query',
        nargs='?',
        help='论文标题（如果不提供且未使用 --interactive，则显示帮助）'
    )
    
    parser.add_argument(
        '-i', '--interactive',
        action='store_true',
        help='进入交互式对话模式'
    )
    
    parser.add_argument(
        '--batch',
        type=str,
        help='批量查询，从文件读取论文标题（每行一个）'
    )
    
    parser.add_argument(
        '--export',
        choices=['json', 'bibtex', 'both'],
        help='导出格式'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        help='输出文件路径（与 --export 一起使用）'
    )
    
    parser.add_argument(
        '--no-cache',
        action='store_true',
        help='不使用缓存'
    )
    
    parser.add_argument(
        '--clear-cache',
        action='store_true',
        help='清空缓存'
    )
    
    parser.add_argument(
        '--stats',
        action='store_true',
        help='显示缓存统计信息'
    )
    
    args = parser.parse_args()
    
    agent = PaperAgent()
    
    # 清空缓存
    if args.clear_cache:
        agent.cache.clear_all()
        print(f"{Fore.GREEN}✓ 缓存已清空{Style.RESET_ALL}")
        return
    
    # 显示统计信息
    if args.stats:
        stats = agent.cache.get_stats()
        print(f"\n{Fore.CYAN}缓存统计:{Style.RESET_ALL}")
        print(f"  总条目数: {stats['total_entries']}")
        print(f"  总大小: {stats['total_size_mb']:.2f} MB")
        print(f"  缓存目录: {stats['cache_dir']}\n")
        return
    
    # 交互式模式
    if args.interactive:
        interactive_mode(agent, use_cache=not args.no_cache)
        return
    
    # 批量查询
    if args.batch:
        batch_file = Path(args.batch)
        if not batch_file.exists():
            print(f"{Fore.RED}✗ 文件不存在: {batch_file}{Style.RESET_ALL}")
            sys.exit(1)
        
        queries = []
        with open(batch_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    queries.append(line)
        
        if not queries:
            print(f"{Fore.YELLOW}⚠ 文件中没有有效的查询{Style.RESET_ALL}")
            return
        
        print(f"{Fore.CYAN}批量查询 {len(queries)} 篇论文...{Style.RESET_ALL}\n")
        
        results = []
        export_data = []
        
        for query in tqdm(queries, desc="搜索进度"):
            result = agent.search(query, use_cache=not args.no_cache)
            results.append({
                'query': query,
                'result': result,
            })
            
            if result:
                export_data.append(result)
                print_result(result, query)
            else:
                print(f"{Fore.RED}✗ 未找到: {query}{Style.RESET_ALL}\n")
        
        # 导出结果
        if args.export:
            export_results(export_data, args.export, args.output)
        
        # 统计
        found_count = sum(1 for r in results if r['result'])
        print(f"\n{Fore.CYAN}统计:{Style.RESET_ALL}")
        print(f"  总计: {len(results)}")
        print(f"  找到: {found_count}")
        print(f"  未找到: {len(results) - found_count}")
        
        return
    
    # 单个查询
    if not args.query:
        # 如果没有提供任何参数，进入交互模式
        interactive_mode(agent, use_cache=not args.no_cache)
        return
    
    result = agent.search(args.query, use_cache=not args.no_cache)
    print_result(result, args.query)
    
    # 导出结果
    if args.export and result:
        export_results([result], args.export, args.output)


def export_results(results: List[dict], format_type: str, output_file: str = None):
    """导出结果"""
    if not results:
        print(f"{Fore.YELLOW}⚠ 没有结果可导出{Style.RESET_ALL}")
        return
    
    if format_type == 'json' or format_type == 'both':
        if not output_file:
            output_file = 'results.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"{Fore.GREEN}✓ JSON 导出到: {output_file}{Style.RESET_ALL}")
    
    if format_type == 'bibtex' or format_type == 'both':
        if not output_file:
            output_file = 'results.bib'
        bibtex_output = output_file if format_type == 'bibtex' else output_file.replace('.json', '.bib')
        
        with open(bibtex_output, 'w', encoding='utf-8') as f:
            from paper_agent.utils import format_bibtex_entry
            for result in results:
                bibtex = format_bibtex_entry(result)
                f.write(bibtex + '\n\n')
        
        print(f"{Fore.GREEN}✓ BibTeX 导出到: {bibtex_output}{Style.RESET_ALL}")


if __name__ == '__main__':
    main()

