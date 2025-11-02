"""
工具函数
"""
import re
from typing import Optional, List


def clean_title(title: str) -> str:
    """清理论文标题"""
    # 移除多余空格
    title = re.sub(r'\s+', ' ', title.strip())
    # 移除特殊字符（保留基本标点）
    title = re.sub(r'[^\w\s\-:,.\u4e00-\u9fff]', '', title)
    return title


def normalize_pages(pages: str) -> Optional[str]:
    """
    标准化页码格式
    支持多种输入格式：
    - "123-145"
    - "123--145"
    - "pages 123-145"
    - "pp. 123-145"
    """
    if not pages:
        return None
    
    # 移除常见前缀
    pages = re.sub(r'^(pages?|pp?\.?)\s*', '', pages, flags=re.IGNORECASE)
    
    # 提取数字
    numbers = re.findall(r'\d+', pages)
    
    if len(numbers) >= 2:
        # 返回 "开始页-结束页" 格式
        return f"{numbers[0]}-{numbers[1]}"
    elif len(numbers) == 1:
        # 只有一页
        return numbers[0]
    
    return None


def extract_year(text: str) -> Optional[int]:
    """从文本中提取年份"""
    match = re.search(r'\b(19|20)\d{2}\b', text)
    if match:
        return int(match.group(0))
    return None


def parse_author_list(authors) -> List[str]:
    """
    解析作者列表
    
    Args:
        authors: 作者信息，可能是列表、字典或字符串
        
    Returns:
        作者名字符串列表
    """
    if not authors:
        return []
    
    # 如果不是列表，转换为列表
    if not isinstance(authors, list):
        authors = [authors]
    
    result = []
    for author in authors:
        name = ''
        
        if isinstance(author, dict):
            # 处理字典格式的作者信息
            # DBLP 可能使用 'text' 字段，Semantic Scholar 可能使用 'name' 字段
            name = author.get('text') or author.get('name') or author.get('@text') or ''
            
            # 如果都没有，尝试组合 given 和 family
            if not name:
                given = author.get('given', '') or author.get('first', '') or ''
                family = author.get('family', '') or author.get('last', '') or author.get('surname', '')
                if given or family:
                    name = f"{given} {family}".strip()
            
            # 如果仍然没有，尝试所有值
            if not name:
                # 获取字典的所有值，过滤掉空值和非字符串值
                values = [str(v).strip() for v in author.values() if v and isinstance(v, (str, int))]
                if values:
                    name = ' '.join(values)
            
            # 最后，如果仍然没有，转换为字符串
            if not name:
                name = str(author)
        elif isinstance(author, str):
            name = author
        else:
            # 其他类型，转换为字符串
            name = str(author)
        
        # 清理并添加
        name = name.strip()
        if name and name not in ['None', 'null', '']:
            result.append(name)
    
    return result


def format_citation_reference(paper_info: dict, reference_number: int = None) -> str:
    """
    格式化论文引用格式
    
    格式：
    - 会议论文：作者+文章名+会议名+年份+页码（例如：[4] Pan Z, Lian H, Hu G, et al. ... [C]//... 2005: 671-672.）
    - 期刊论文：作者+文章名+期刊名+年份+卷期号+页码（例如：[5] Demontis A, Melis M, Biggio B, et al. ... [J]. ... 2017, 16(4):711-724）
    
    Args:
        paper_info: 包含论文信息的字典
        reference_number: 引用编号（可选）
        
    Returns:
        引用格式的字符串
    """
    # 提取信息
    authors = paper_info.get('authors', [])
    title = paper_info.get('title', '')
    venue = paper_info.get('venue', '')
    year = paper_info.get('year')
    pages = paper_info.get('pages', '')
    volume = paper_info.get('volume') or paper_info.get('vol')
    issue = paper_info.get('issue') or paper_info.get('number') or paper_info.get('no')
    
    # 判断是期刊还是会议
    venue_lower = venue.lower()
    is_journal = any(keyword in venue_lower for keyword in [
        'journal', 'transactions', 'magazine', 'review', 'letters', 
        'proceedings of machine learning research'  # PMLR 特殊情况（虽然是 proceedings，但通常按期刊格式引用）
    ])
    
    # 清理作者名（移除末尾的数字，如 "0003", "0011" 等）
    def clean_author_name(author: str) -> str:
        """清理作者名，移除末尾的数字"""
        if not author:
            return author
        # 移除末尾的数字（如 "0003", "0011", "0001"）
        author = author.strip()
        # 匹配末尾的数字模式（如 " 0003", "0011"）
        import re
        author = re.sub(r'\s+\d+$', '', author)
        return author
    
    # 格式化作者
    author_str = ''
    if authors:
        # 先清理所有作者名
        cleaned_authors = [clean_author_name(author) for author in authors]
        
        # 只取前3个作者，超过3个用 et al.
        if len(cleaned_authors) > 3:
            author_list = cleaned_authors[:3]
            # 格式化每个作者：Last Name + First Initial
            formatted_authors = []
            for author in author_list:
                parts = author.split()
                if len(parts) >= 2:
                    # 有姓氏和名字：Last + First Initial
                    last_name = parts[-1]
                    # 过滤掉空字符串，并提取首字母
                    first_initials = ''.join([p[0].upper() for p in parts[:-1] if p and p[0].isalpha()])
                    formatted_authors.append(f"{last_name} {first_initials}")
                else:
                    formatted_authors.append(author)
            author_str = ', '.join(formatted_authors) + ', et al.'
        else:
            # 格式化每个作者
            formatted_authors = []
            for author in cleaned_authors:
                parts = author.split()
                if len(parts) >= 2:
                    last_name = parts[-1]
                    # 过滤掉空字符串和非字母开头的部分
                    first_initials = ''.join([p[0].upper() for p in parts[:-1] if p and p[0].isalpha()])
                    formatted_authors.append(f"{last_name} {first_initials}")
                else:
                    formatted_authors.append(author)
            author_str = ', '.join(formatted_authors)
    else:
        author_str = 'Unknown'
    
    # 构建引用
    citation = ''
    
    # 引用编号（如果提供）
    if reference_number is not None:
        citation += f"[{reference_number}] "
    
    # 作者
    citation += author_str + '. '
    
    # 文章名
    citation += title
    if not title.endswith('.'):
        citation += '.'
    
    # 论文类型标记
    if is_journal:
        citation += ' [J]. '  # Journal
    else:
        citation += ' [C]//'  # Conference
    
    # 会议/期刊名
    citation += venue
    
    # 年份
    if year:
        if is_journal:
            citation += ', ' + str(year)
        else:
            citation += '. ' + str(year)
    
    # 卷期号（仅期刊）
    if is_journal and volume:
        if issue:
            citation += f', {volume}({issue})'
        else:
            citation += f', {volume}'
    elif is_journal and issue:
        citation += f', ({issue})'
    
    # 页码
    if pages:
        if is_journal:
            citation += ':' + pages
        else:
            citation += ': ' + pages
    
    return citation


def format_bibtex_entry(paper_info: dict) -> str:
    """
    格式化为 BibTeX 条目
    
    Args:
        paper_info: 包含论文信息的字典
        
    Returns:
        BibTeX 格式的字符串
    """
    # 生成引用键
    first_author = paper_info.get('authors', ['Unknown'])[0].split()[-1]
    year = paper_info.get('year', 'XXXX')
    cite_key = f"{first_author}{year}"
    
    # 确定条目类型
    venue = paper_info.get('venue', '').lower()
    if 'journal' in venue or 'transactions' in venue:
        entry_type = 'article'
    else:
        entry_type = 'inproceedings'
    
    # 构建 BibTeX
    bibtex = f"@{entry_type}{{{cite_key},\n"
    
    # 标题
    if paper_info.get('title'):
        bibtex += f"  title={{{paper_info['title']}}},\n"
    
    # 作者
    if paper_info.get('authors'):
        authors_str = ' and '.join(paper_info['authors'])
        bibtex += f"  author={{{authors_str}}},\n"
    
    # 会议/期刊
    if paper_info.get('venue'):
        if entry_type == 'article':
            bibtex += f"  journal={{{paper_info['venue']}}},\n"
        else:
            bibtex += f"  booktitle={{{paper_info['venue']}}},\n"
    
    # 年份
    if paper_info.get('year'):
        bibtex += f"  year={{{paper_info['year']}}},\n"
    
    # 页码
    if paper_info.get('pages'):
        bibtex += f"  pages={{{paper_info['pages']}}},\n"
    
    # DOI
    if paper_info.get('doi'):
        bibtex += f"  doi={{{paper_info['doi']}}},\n"
    
    # URL
    if paper_info.get('url'):
        bibtex += f"  url={{{paper_info['url']}}},\n"
    
    bibtex += "}\n"
    
    return bibtex


def expand_venue_name(venue: str) -> str:
    """
    扩展会议/期刊名称缩写为全名
    
    Args:
        venue: 会议/期刊名称（可能是缩写）
        
    Returns:
        扩展后的全名
    """
    if not venue:
        return venue
    
    # 常见的会议/期刊缩写到全名的映射
    venue_mapping = {
        # === 人工智能和机器学习 ===
        'AAAI': 'Proceedings of the AAAI Conference on Artificial Intelligence',
        'ICML': 'International Conference on Machine Learning',
        'NeurIPS': 'Advances in Neural Information Processing Systems',
        'NIPS': 'Advances in Neural Information Processing Systems',  # 旧名称
        'ICLR': 'International Conference on Learning Representations',
        'AISTATS': 'Artificial Intelligence and Statistics',
        'UAI': 'Uncertainty in Artificial Intelligence',
        'IJCAI': 'International Joint Conference on Artificial Intelligence',
        'KR': 'Knowledge Representation and Reasoning',
        'COLT': 'Conference on Learning Theory',
        'ALT': 'Algorithmic Learning Theory',
        
        # === 计算机视觉 ===
        'ICCV': 'International Conference on Computer Vision',
        'CVPR': 'IEEE/CVF Conference on Computer Vision and Pattern Recognition',
        'ECCV': 'European Conference on Computer Vision',
        'BMVC': 'British Machine Vision Conference',
        'WACV': 'Winter Conference on Applications of Computer Vision',
        
        # === 自然语言处理 ===
        'ACL': 'Proceedings of the Annual Meeting of the Association for Computational Linguistics',
        'EMNLP': 'Proceedings of the Conference on Empirical Methods in Natural Language Processing',
        'NAACL': 'Proceedings of the North American Chapter of the Association for Computational Linguistics',
        'EACL': 'Proceedings of the European Chapter of the Association for Computational Linguistics',
        'COLING': 'International Conference on Computational Linguistics',
        'CoNLL': 'Conference on Natural Language Learning',
        'LREC': 'Language Resources and Evaluation Conference',
        'INLG': 'International Conference on Natural Language Generation',
        
        # === 信息检索和数据挖掘 ===
        'SIGIR': 'Proceedings of the International ACM SIGIR Conference on Research and Development in Information Retrieval',
        'KDD': 'Proceedings of the ACM SIGKDD International Conference on Knowledge Discovery and Data Mining',
        'WSDM': 'Web Search and Data Mining',
        'WWW': 'The Web Conference',
        'CIKM': 'Conference on Information and Knowledge Management',
        'RecSys': 'ACM Conference on Recommender Systems',
        'ICTIR': 'International Conference on the Theory of Information Retrieval',
        
        # === 软件工程 ===
        'ICSE': 'International Conference on Software Engineering',
        'FSE': 'ACM SIGSOFT International Symposium on Foundations of Software Engineering',
        'ASE': 'International Conference on Automated Software Engineering',
        'ISSTA': 'International Symposium on Software Testing and Analysis',
        'ICST': 'International Conference on Software Testing, Verification and Validation',
        'ICSME': 'International Conference on Software Maintenance and Evolution',
        'MSR': 'Mining Software Repositories',
        'SANER': 'Software Analysis, Evolution and Reengineering',
        'ICSOC': 'International Conference on Service-Oriented Computing',
        'WICSA': 'Working IEEE/IFIP Conference on Software Architecture',
        'SE': 'Software Engineering',
        
        # === 编程语言和编译器 ===
        'OOPSLA': 'Object-Oriented Programming, Systems, Languages & Applications',
        'PLDI': 'Programming Language Design and Implementation',
        'POPL': 'Symposium on Principles of Programming Languages',
        'ICFP': 'International Conference on Functional Programming',
        'ESOP': 'European Symposium on Programming',
        'CC': 'International Conference on Compiler Construction',
        'SAS': 'Static Analysis Symposium',
        'VMCAI': 'Verification, Model Checking, and Abstract Interpretation',
        'ECOOP': 'European Conference on Object-Oriented Programming',
        
        # === 系统 ===
        'SIGCOMM': 'ACM SIGCOMM Conference',
        'INFOCOM': 'IEEE Conference on Computer Communications',
        'NSDI': 'Symposium on Networked Systems Design and Implementation',
        'OSDI': 'Operating Systems Design and Implementation',
        'SOSP': 'Symposium on Operating Systems Principles',
        'EuroSys': 'European Conference on Computer Systems',
        'ASPLOS': 'Architectural Support for Programming Languages and Operating Systems',
        'MICRO': 'IEEE/ACM International Symposium on Microarchitecture',
        'HPCA': 'IEEE International Symposium on High-Performance Computer Architecture',
        'ISCA': 'International Symposium on Computer Architecture',
        'SoCC': 'ACM Symposium on Cloud Computing',
        'HotOS': 'Workshop on Hot Topics in Operating Systems',
        'HotNets': 'Workshop on Hot Topics in Networks',
        'HotCloud': 'Workshop on Hot Topics in Cloud Computing',
        'HotEdge': 'Workshop on Hot Topics in Edge Computing',
        'HotStorage': 'Workshop on Hot Topics in Storage and File Systems',
        'ATC': 'USENIX Annual Technical Conference',
        'FAST': 'File and Storage Technologies',
        
        # === 实时和嵌入式系统 ===
        'RTSS': 'IEEE Real-Time Systems Symposium',
        'RTAS': 'IEEE Real-Time and Embedded Technology and Applications Symposium',
        'EMSOFT': 'Embedded Software',
        'DAC': 'Design Automation Conference',
        'DATE': 'Design, Automation and Test in Europe',
        'CODES+ISSS': 'Hardware/Software Codesign and System Synthesis',
        'ASP-DAC': 'Asia and South Pacific Design Automation Conference',
        'ISSCC': 'IEEE International Solid-State Circuits Conference',
        
        # === 移动和无线系统 ===
        'MobiSys': 'International Conference on Mobile Systems, Applications, and Services',
        'MobiCom': 'International Conference on Mobile Computing and Networking',
        'MobiHoc': 'International Symposium on Mobile Ad Hoc Networking and Computing',
        'SenSys': 'ACM Conference on Embedded Networked Sensor Systems',
        'IPSN': 'International Conference on Information Processing in Sensor Networks',
        'UbiComp': 'Ubiquitous Computing',
        'Pervasive': 'International Conference on Pervasive Computing',
        
        # === 网络 ===
        'IMC': 'Internet Measurement Conference',
        'CoNEXT': 'Conference on emerging Networking Experiments and Technologies',
        'PAM': 'Passive and Active Measurement',
        'ANCS': 'Architectures for Networking and Communications Systems',
        'ICNP': 'International Conference on Network Protocols',
        'ICC': 'IEEE International Conference on Communications',
        'GLOBECOM': 'IEEE Global Communications Conference',
        
        # === 分布式系统和并行计算 ===
        'PODC': 'Principles of Distributed Computing',
        'DISC': 'International Symposium on Distributed Computing',
        'OPODIS': 'International Conference on Principles of Distributed Systems',
        'SRDS': 'Symposium on Reliable Distributed Systems',
        'HPDC': 'International Symposium on High-Performance Parallel and Distributed Computing',
        'SC': 'International Conference for High Performance Computing, Networking, Storage and Analysis',
        'PPoPP': 'Principles and Practice of Parallel Programming',
        'ICPP': 'International Conference on Parallel Processing',
        'IPDPS': 'International Parallel & Distributed Processing Symposium',
        'CCGrid': 'IEEE/ACM International Symposium on Cluster, Cloud and Grid Computing',
        
        # === 理论和算法 ===
        'STOC': 'Symposium on Theory of Computing',
        'FOCS': 'IEEE Symposium on Foundations of Computer Science',
        'SODA': 'ACM-SIAM Symposium on Discrete Algorithms',
        'ICALP': 'International Colloquium on Automata, Languages, and Programming',
        'ESA': 'European Symposium on Algorithms',
        'SWAT': 'Scandinavian Symposium and Workshops on Algorithm Theory',
        'WADS': 'Algorithms and Data Structures Symposium',
        'IPCO': 'Integer Programming and Combinatorial Optimization',
        'CP': 'Principles and Practice of Constraint Programming',
        'SAT': 'Theory and Applications of Satisfiability Testing',
        
        # === 形式化方法和验证 ===
        'CAV': 'International Conference on Computer Aided Verification',
        'TACAS': 'Tools and Algorithms for the Construction and Analysis of Systems',
        'FM': 'Formal Methods',
        'FMODS': 'Formal Methods for Open Object-Based Distributed Systems',
        'IFM': 'Integrated Formal Methods',
        'VMCAI': 'Verification, Model Checking, and Abstract Interpretation',
        'LICS': 'Logic in Computer Science',
        'CSL': 'Computer Science Logic',
        'MFCS': 'Mathematical Foundations of Computer Science',
        
        # === 安全 ===
        'CCS': 'ACM Conference on Computer and Communications Security',
        'SP': 'IEEE Symposium on Security and Privacy',
        'USENIX Security': 'USENIX Security Symposium',
        'NDSS': 'Network and Distributed System Security Symposium',
        'RAID': 'International Symposium on Research in Attacks, Intrusions and Defenses',
        'ASIACCS': 'ACM Asia Conference on Computer and Communications Security',
        'ESORICS': 'European Symposium on Research in Computer Security',
        'EuroS&P': 'IEEE European Symposium on Security and Privacy',
        'CSF': 'IEEE Computer Security Foundations Symposium',
        'ACNS': 'Applied Cryptography and Network Security',
        'PKC': 'Public Key Cryptography',
        'Crypto': 'International Cryptology Conference',
        'Eurocrypt': 'European Cryptology Conference',
        'Asiacrypt': 'International Conference on the Theory and Application of Cryptology and Information Security',
        'CHES': 'Cryptographic Hardware and Embedded Systems',
        
        # === 可靠性 ===
        'ISSRE': 'IEEE International Symposium on Software Reliability Engineering',
        'DSN': 'IEEE/IFIP International Conference on Dependable Systems and Networks',
        'DSN-W': 'DSN Workshops',
        'DASC': 'Dependable, Autonomic and Secure Computing',
        'PRDC': 'Pacific Rim International Symposium on Dependable Computing',
        
        # === 人机交互 ===
        'CHI': 'ACM Conference on Human Factors in Computing Systems',
        'UIST': 'ACM Symposium on User Interface Software and Technology',
        'CSCW': 'Computer Supported Cooperative Work and Social Computing',
        'DIS': 'Designing Interactive Systems',
        'HCI': 'Human-Computer Interaction',
        'MobileHCI': 'Mobile Human-Computer Interaction',
        'IUI': 'Intelligent User Interfaces',
        'ITS': 'Interactive Tabletops and Surfaces',
        
        # === 数据库和存储 ===
        'VLDB': 'Very Large Data Bases',
        'SIGMOD': 'ACM SIGMOD International Conference on Management of Data',
        'ICDE': 'IEEE International Conference on Data Engineering',
        'EDBT': 'International Conference on Extending Database Technology',
        'ICDT': 'International Conference on Database Theory',
        'PODS': 'Principles of Database Systems',
        'CIDR': 'Conference on Innovative Data Systems Research',
        'DaMoN': 'Data Management on New Hardware',
        'DASFAA': 'Database Systems for Advanced Applications',
        'WAIM': 'Web-Age Information Management',
        
        # === 期刊 ===
        'JMLR': 'Journal of Machine Learning Research',
        'TPAMI': 'IEEE Transactions on Pattern Analysis and Machine Intelligence',
        'TACL': 'Transactions of the Association for Computational Linguistics',
        'TKDE': 'IEEE Transactions on Knowledge and Data Engineering',
        'TOIS': 'ACM Transactions on Information Systems',
        'TOS': 'ACM Transactions on Storage',
        'TOCS': 'ACM Transactions on Computer Systems',
        'TSE': 'IEEE Transactions on Software Engineering',
        'TOSEM': 'ACM Transactions on Software Engineering and Methodology',
        'TSC': 'IEEE Transactions on Services Computing',
        'TC': 'IEEE Transactions on Computers',
        'TPDS': 'IEEE Transactions on Parallel and Distributed Systems',
        'TDSC': 'IEEE Transactions on Dependable and Secure Computing',
        'TIFS': 'IEEE Transactions on Information Forensics and Security',
        'TMC': 'IEEE Transactions on Mobile Computing',
        'TNET': 'IEEE/ACM Transactions on Networking',
        'TON': 'IEEE/ACM Transactions on Networking',
        'TCC': 'IEEE Transactions on Cloud Computing',
        'TSMC': 'IEEE Transactions on Systems, Man, and Cybernetics',
        'TKDD': 'ACM Transactions on Knowledge Discovery from Data',
        'TIST': 'ACM Transactions on Intelligent Systems and Technology',
        'IJCAI': 'International Joint Conference on Artificial Intelligence',
        'AIJ': 'Artificial Intelligence Journal',
        'JAIR': 'Journal of Artificial Intelligence Research',
        'JACM': 'Journal of the ACM',
        'CACM': 'Communications of the ACM',
        'ACM Computing Surveys': 'ACM Computing Surveys',
        'CSUR': 'ACM Computing Surveys',
        'VLDBJ': 'VLDB Journal',
        
        # === DBLP 常见缩写 ===
        'Proc. AAAI': 'Proceedings of the AAAI Conference on Artificial Intelligence',
        'Proc. ICML': 'International Conference on Machine Learning',
        'Proc. NeurIPS': 'Advances in Neural Information Processing Systems',
        'Proc. NIPS': 'Advances in Neural Information Processing Systems',
        'Proc. ICLR': 'International Conference on Learning Representations',
        'Proc. CVPR': 'IEEE/CVF Conference on Computer Vision and Pattern Recognition',
        'Proc. ICCV': 'International Conference on Computer Vision',
        'Proc. ECCV': 'European Conference on Computer Vision',
        'Proc. ACL': 'Proceedings of the Annual Meeting of the Association for Computational Linguistics',
        'Proc. EMNLP': 'Proceedings of the Conference on Empirical Methods in Natural Language Processing',
        'Proc. NAACL': 'Proceedings of the North American Chapter of the Association for Computational Linguistics',
        
        # 其他常见缩写
        'IEEE Trans.': 'IEEE Transactions',
        'ACM Trans.': 'ACM Transactions',
        'Proc.': 'Proceedings',
    }
    
    # 精确匹配
    if venue in venue_mapping:
        return venue_mapping[venue]
    
    # 部分匹配（如果包含缩写）
    venue_upper = venue.upper()
    for abbrev, full_name in venue_mapping.items():
        if abbrev.upper() in venue_upper:
            # 如果缩写是完整的词，替换它
            import re
            pattern = r'\b' + re.escape(abbrev) + r'\b'
            if re.search(pattern, venue, re.IGNORECASE):
                return venue_mapping[abbrev]
    
    # 如果包含 "Proc." 或 "Proceedings"，尝试扩展
    if 'proc.' in venue.lower() or 'proceedings' in venue.lower():
        # 已经包含 "Proceedings"，可能是完整的
        return venue
    
    # 没有匹配，返回原始值
    return venue


def similarity_score(str1: str, str2: str) -> float:
    """
    计算两个字符串的相似度（改进版本）
    返回 0-1 之间的分数
    
    改进点：
    1. 精确匹配得分最高
    2. 考虑词顺序匹配
    3. 偏好完全包含查询词的标题（不多不少最好）
    4. 考虑长度相似度
    """
    str1 = str1.lower().strip()
    str2 = str2.lower().strip()
    
    # 精确匹配
    if str1 == str2:
        return 1.0
    
    # 包含匹配（查询完全包含在标题中）
    if str1 in str2:
        # 如果标题只比查询稍长一些，得分较高
        len_ratio = len(str1) / len(str2) if len(str2) > 0 else 0
        
        # 检查词数量差异
        words1_count = len(str1.split())
        words2_count = len(str2.split())
        word_diff = words2_count - words1_count
        
        if word_diff == 0:  # 词数完全一致
            return 0.98
        elif word_diff <= 1 and len_ratio > 0.8:  # 长度接近，只多1-2个词
            return 0.95
        elif word_diff <= 2 and len_ratio > 0.7:  # 长度接近，多2-3个词
            return 0.85
        elif word_diff <= 3:  # 多3-4个词
            return 0.75
        else:
            return 0.6  # 标题明显更长
    
    words1 = str1.split()
    words2 = str2.split()
    
    if not words1 or not words2:
        return 0.0
    
    # 词集合
    set1 = set(words1)
    set2 = set(words2)
    
    # 交集大小
    intersection = len(set1 & set2)
    
    # 方法1: Jaccard 相似度（词交集）
    union = len(set1 | set2)
    jaccard_score = intersection / union if union > 0 else 0.0
    
    # 方法2: 覆盖率（查询词有多少在标题中）
    coverage_score = intersection / len(set1) if len(set1) > 0 else 0.0
    
    # 方法3: 长度相似度（偏好长度接近的标题）
    len_diff = abs(len(words1) - len(words2))
    max_len = max(len(words1), len(words2))
    length_score = 1.0 - (len_diff / max_len) if max_len > 0 else 0.0
    
    # 方法4: 顺序匹配（检查查询词在标题中的顺序）
    order_score = 0.0
    if intersection > 0:
        # 检查查询词的顺序是否在标题中保持
        words1_list = [w for w in words1 if w in set2]
        words2_list = [w for w in words2 if w in set1]
        
        if len(words1_list) > 1:
            # 检查顺序匹配
            try:
                indices1 = [words2_list.index(w) for w in words1_list if w in words2_list]
                if len(indices1) > 1:
                    is_ordered = all(indices1[i] < indices1[i+1] for i in range(len(indices1)-1))
                    order_score = 0.3 if is_ordered else 0.1
            except ValueError:
                order_score = 0.0
    
    # 综合评分
    # 覆盖率最重要（查询的所有词都应该在标题中）
    # 然后考虑长度相似度（偏好完全匹配或接近的匹配）
    # 顺序匹配作为加分项
    final_score = (
        coverage_score * 0.5 +      # 覆盖率权重 50%
        jaccard_score * 0.3 +       # Jaccard 权重 30%
        length_score * 0.15 +       # 长度相似度权重 15%
        order_score * 0.05          # 顺序匹配权重 5%
    )
    
    # 如果查询的所有词都在标题中，给予奖励
    if coverage_score >= 1.0:
        final_score = min(1.0, final_score * 1.1)
    
    return final_score

