#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Web 界面
"""
from flask import Flask, render_template, request
from paper_agent import PaperAgent

app = Flask(__name__)
agent = PaperAgent()


@app.route('/', methods=['GET', 'POST'])
def index():
    """主页 - 单篇搜索"""
    error = None
    result = None
    
    if request.method == 'POST':
        try:
            query = request.form.get('query', '').strip()
            
            if not query:
                error = '请输入论文标题'
            else:
                print(f"搜索请求: {query}")
                result = agent.search(query)
                
                if result:
                    # 生成引用格式
                    from paper_agent.utils import format_citation_reference
                    result['citation'] = format_citation_reference(result)
                    print(f"找到结果: {result.get('title', 'N/A')}")
                else:
                    error = '未找到论文信息'
                    
        except Exception as e:
            import traceback
            print(f"搜索错误: {e}")
            print(traceback.format_exc())
            error = f'搜索失败: {str(e)}'
    
    return render_template('index.html', error=error, result=result)


@app.route('/batch', methods=['POST'])
def batch_search():
    """批量搜索"""
    error = None
    batch_results = None
    
    try:
        queries_text = request.form.get('queries', '').strip()
        
        if not queries_text:
            error = '请输入论文标题列表'
        else:
            # 按行分割，过滤空行
            queries = [q.strip() for q in queries_text.split('\n') if q.strip()]
            
            if not queries:
                error = '没有有效的查询'
            else:
                print(f"批量搜索请求: {len(queries)} 篇论文")
                results = agent.batch_search(queries)
                
                # 为每个结果生成引用格式
                from paper_agent.utils import format_citation_reference
                for item in results:
                    if item.get('result'):
                        item['result']['citation'] = format_citation_reference(item['result'])
                
                batch_results = results
                print(f"批量搜索完成: 找到 {sum(1 for r in results if r.get('result'))} 篇")
                
    except Exception as e:
        import traceback
        print(f"批量搜索错误: {e}")
        print(traceback.format_exc())
        error = f'批量搜索失败: {str(e)}'
    
    return render_template('index.html', error=error, batch_results=batch_results)


if __name__ == '__main__':
    print("="*60)
    print("智能文献页码搜索 Agent - Web 界面")
    print("="*60)
    print("访问地址: http://localhost:5000")
    print("按 Ctrl+C 停止服务器")
    print("="*60)
    app.run(debug=True, host='0.0.0.0', port=5000)
