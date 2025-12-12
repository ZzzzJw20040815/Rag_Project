"""
UI 组件模块
提供可复用的 Streamlit UI 组件
"""

import re
import streamlit as st


def parse_table_alignment(separator_row: str) -> list:
    """
    解析表格分隔行，获取每列的对齐方式
    
    Args:
        separator_row: 分隔行，如 "| :--- | :---: | ---: |"
        
    Returns:
        对齐方式列表 ['left', 'center', 'right', ...]
    """
    cells = [c.strip() for c in separator_row.strip().strip('|').split('|')]
    alignments = []
    for cell in cells:
        cell = cell.strip()
        if cell.startswith(':') and cell.endswith(':'):
            alignments.append('center')
        elif cell.endswith(':'):
            alignments.append('right')
        else:
            alignments.append('left')
    return alignments


def parse_table(lines: list, start_idx: int) -> tuple:
    """
    解析 Markdown 表格并转换为 HTML
    
    Args:
        lines: 所有行
        start_idx: 表格起始行索引
        
    Returns:
        (html_string, end_idx) 表格 HTML 和结束行索引
    """
    table_lines = []
    i = start_idx
    
    # 收集所有表格行（以 | 开头的连续行）
    while i < len(lines) and lines[i].strip().startswith('|'):
        table_lines.append(lines[i])
        i += 1
    
    if len(table_lines) < 2:
        # 不是有效的表格（至少需要表头和分隔行）
        return None, start_idx
    
    # 检查第二行是否是分隔行（包含 --- 模式）
    separator_pattern = r'^[\s|:-]+$'
    if not re.match(separator_pattern, table_lines[1].replace('-', '')):
        # 如果移除短横线后只剩空格、|、和冒号，说明是分隔行
        pass
    
    # 检查分隔行是否有效
    sep_row = table_lines[1]
    if '---' not in sep_row and '--' not in sep_row:
        return None, start_idx
    
    # 解析对齐方式
    alignments = parse_table_alignment(sep_row)
    
    # 构建 HTML 表格
    html = '<table class="markdown-table"><thead><tr>'
    
    # 表头
    header_cells = [c.strip() for c in table_lines[0].strip().strip('|').split('|')]
    for j, cell in enumerate(header_cells):
        align = alignments[j] if j < len(alignments) else 'left'
        html += f'<th style="text-align: {align};">{cell}</th>'
    html += '</tr></thead><tbody>'
    
    # 数据行（跳过分隔行）
    for row in table_lines[2:]:
        html += '<tr>'
        cells = [c.strip() for c in row.strip().strip('|').split('|')]
        for j, cell in enumerate(cells):
            align = alignments[j] if j < len(alignments) else 'left'
            html += f'<td style="text-align: {align};">{cell}</td>'
        html += '</tr>'
    
    html += '</tbody></table>'
    
    return html, i - 1  # 返回最后处理的行索引


def markdown_to_html(text: str) -> str:
    """
    将 Markdown 文本转换为 HTML
    用于在 Streamlit 中使用 unsafe_allow_html 渲染
    
    支持的格式：
    - 标题 (#, ##, ###)
    - 粗体 (**text**)
    - 斜体 (*text*)
    - 行内代码 (`code`)
    - 代码块 (```)
    - 表格 (| col1 | col2 |)
    - 无序列表 (-, *)
    - 有序列表 (1., 2.)
    - 引用块 (>)
    - 链接 ([text](url))
    - 分隔线 (---, ***)
    
    Args:
        text: Markdown 格式的文本
        
    Returns:
        HTML 格式的文本
    """
    lines = text.split('\n')
    result_lines = []
    i = 0
    in_code_block = False
    code_block_content = []
    
    while i < len(lines):
        line = lines[i]
        
        # 处理代码块
        if line.strip().startswith('```'):
            if not in_code_block:
                in_code_block = True
                code_block_content = []
                # 获取语言标识（如果有）
                lang = line.strip()[3:].strip()
            else:
                in_code_block = False
                code_html = '<pre class="markdown-code-block"><code>'
                code_html += '\n'.join(code_block_content).replace('<', '&lt;').replace('>', '&gt;')
                code_html += '</code></pre>'
                result_lines.append(code_html)
            i += 1
            continue
        
        if in_code_block:
            code_block_content.append(line)
            i += 1
            continue
        
        # 处理表格（以 | 开头的行）
        if line.strip().startswith('|'):
            table_html, end_idx = parse_table(lines, i)
            if table_html:
                result_lines.append(table_html)
                i = end_idx + 1
                continue
        
        # 处理引用块
        if line.strip().startswith('>'):
            quote_content = line.strip()[1:].strip()
            result_lines.append(f'<blockquote class="markdown-quote">{quote_content}</blockquote>')
            i += 1
            continue
        
        # 标题转换（注意：必须从多到少匹配，#### 要在 ### 之前）
        if line.startswith('#### '):
            line = f'<h5 style="margin: 0.5em 0; font-size: 1.0em; font-weight: 600;">{line[5:]}</h5>'
        elif line.startswith('### '):
            line = f'<h4 style="margin: 0.5em 0; font-size: 1.1em;">{line[4:]}</h4>'
        elif line.startswith('## '):
            line = f'<h3 style="margin: 0.5em 0; font-size: 1.2em;">{line[3:]}</h3>'
        elif line.startswith('# '):
            line = f'<h2 style="margin: 0.5em 0; font-size: 1.3em;">{line[2:]}</h2>'
        # 无序列表
        elif line.strip().startswith('- ') or line.strip().startswith('* '):
            indent = len(line) - len(line.lstrip())
            content = line.strip()[2:]
            line = f'<div style="margin-left: {indent + 20}px;">• {content}</div>'
        # 有序列表
        elif re.match(r'^\s*\d+\.\s', line):
            match = re.match(r'^(\s*)(\d+)\.\s(.*)$', line)
            if match:
                indent = len(match.group(1))
                num = match.group(2)
                content = match.group(3)
                line = f'<div style="margin-left: {indent + 20}px;">{num}. {content}</div>'
        # 分隔线
        elif line.strip() == '---' or line.strip() == '***':
            line = '<hr style="margin: 0.5em 0; border: none; border-top: 1px solid #ccc;">'
        else:
            if line.strip():
                line = line + '<br>'
            else:
                line = '<br>'
        
        result_lines.append(line)
        i += 1
    
    text = ''.join(result_lines)
    
    # 行内格式转换
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)  # 粗体
    text = re.sub(r'(?<!\*)\*([^*\n]+?)\*(?!\*)', r'<em>\1</em>', text)  # 斜体
    text = re.sub(
        r'`([^`]+?)`',
        r'<code style="background: rgba(0,0,0,0.1); padding: 2px 4px; border-radius: 3px;">\1</code>',
        text
    )  # 行内代码
    
    # 链接转换 [text](url)
    text = re.sub(
        r'\[([^\]]+)\]\(([^)]+)\)',
        r'<a href="\2" target="_blank" style="color: #667eea; text-decoration: underline;">\1</a>',
        text
    )
    
    # 清理多余的换行
    text = re.sub(r'(<br>\s*)+', '<br>', text)
    text = re.sub(r'^<br>', '', text)
    text = re.sub(r'<br>$', '', text)
    
    return text


def render_chat_message(role: str, content: str):
    """
    渲染聊天消息
    
    Args:
        role: 角色 ("user" 或 "assistant")
        content: 消息内容
    """
    if role == "user":
        st.markdown(
            f'<div class="chat-message user-message">🧑 <strong>用户</strong>: {markdown_to_html(content)}</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f'<div class="chat-message assistant-message">🤖 <strong>助手</strong>: {markdown_to_html(content)}</div>',
            unsafe_allow_html=True
        )


def render_source_documents(sources: list):
    """
    渲染来源文档
    
    Args:
        sources: 来源文档列表，每个元素包含 content, page, source_file
    """
    if not sources:
        return
    
    with st.expander("📚 查看引用来源", expanded=False):
        # 每行 2 个来源
        for row_start in range(0, len(sources), 2):
            row_sources = sources[row_start:row_start + 2]
            cols = st.columns(len(row_sources))
            
            for col_idx, source in enumerate(row_sources):
                with cols[col_idx]:
                    i = row_start + col_idx + 1
                    page_num = source.get('page', '?')
                    file_name = source.get('source_file', '未知文件')
                    content = source.get('content', '')[:400]
                    
                    st.markdown(f"**📄 来源 {i}** · {file_name} · 第 {page_num} 页")
                    st.info(content + "..." if len(source.get('content', '')) > 400 else content)


def get_custom_css() -> str:
    """
    获取自定义 CSS 样式
    
    Returns:
        CSS 样式字符串
    """
    return """
    <style>
        /* 主标题样式 */
        .main-header {
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-align: center;
            margin-bottom: 1rem;
        }
        
        /* 副标题 */
        .sub-header {
            text-align: center;
            color: #666;
            margin-bottom: 2rem;
        }
        
        /* 聊天消息样式 */
        .chat-message {
            padding: 1rem;
            border-radius: 10px;
            margin-bottom: 1rem;
        }
        
        .user-message {
            background-color: #e3f2fd;
            border-left: 4px solid #2196f3;
            color: #1a1a2e !important;
        }
        
        .user-message * {
            color: #1a1a2e !important;
        }
        
        .assistant-message {
            background-color: #f3e5f5;
            border-left: 4px solid #9c27b0;
            color: #1a1a2e !important;
        }
        
        .assistant-message * {
            color: #1a1a2e !important;
        }
        
        /* 按钮样式 */
        .stButton > button {
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            padding: 0.5rem 2rem;
            font-weight: 600;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        
        .stButton > button:hover {
            background: linear-gradient(90deg, #764ba2 0%, #667eea 100%);
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }
        
        /* 文件上传区域 */
        .upload-section {
            background: linear-gradient(135deg, #f5f7fa 0%, #e4e8ed 100%);
            padding: 1.5rem;
            border-radius: 15px;
            margin-bottom: 1rem;
            border: 2px dashed #ccc;
        }
        
        /* 状态卡片 */
        .status-card {
            background: white;
            padding: 1rem;
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        
        /* Tab 样式优化 */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }
        
        .stTabs [data-baseweb="tab"] {
            border-radius: 8px;
            padding: 8px 16px;
        }
        
        /* 底部信息 */
        .footer {
            text-align: center;
            color: #888;
            padding: 2rem 0;
            border-top: 1px solid #eee;
            margin-top: 2rem;
        }
        
        /* Markdown 表格样式 */
        .markdown-table {
            width: 100%;
            border-collapse: collapse;
            margin: 1em 0;
            font-size: 0.9em;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        
        .markdown-table thead {
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            color: white !important;
        }
        
        .markdown-table thead th {
            color: white !important;
            padding: 12px 15px;
            font-weight: 600;
            text-align: left;
        }
        
        .markdown-table tbody tr {
            border-bottom: 1px solid #eee;
        }
        
        .markdown-table tbody tr:nth-of-type(even) {
            background-color: #f8f9fa;
        }
        
        .markdown-table tbody tr:hover {
            background-color: #e8e9ff;
        }
        
        .markdown-table td {
            padding: 10px 15px;
            color: #1a1a2e !important;
        }
        
        /* Markdown 代码块样式 */
        .markdown-code-block {
            background: #2d2d2d;
            color: #f8f8f2;
            padding: 1em;
            border-radius: 8px;
            overflow-x: auto;
            margin: 1em 0;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 0.9em;
            line-height: 1.5;
        }
        
        .markdown-code-block code {
            background: transparent !important;
            padding: 0 !important;
            color: #f8f8f2 !important;
        }
        
        /* Markdown 引用块样式 */
        .markdown-quote {
            border-left: 4px solid #667eea;
            padding: 0.5em 1em;
            margin: 1em 0;
            background: #f8f9ff;
            font-style: italic;
            border-radius: 0 8px 8px 0;
            color: #1a1a2e !important;
        }
    </style>
    """


def init_page_config():
    """初始化页面配置"""
    st.set_page_config(
        page_title="📚 学术文献智能导读系统",
        page_icon="📚",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # 注入自定义 CSS
    st.markdown(get_custom_css(), unsafe_allow_html=True)


def render_sidebar_api_config():
    """
    渲染侧边栏的 API 配置区域
    
    Returns:
        当前配置的 API Key
    """
    import os
    from config import get_api_key, save_api_key
    
    st.sidebar.header("⚙️ 系统配置")
    
    # API Key 配置
    st.sidebar.subheader("🔑 API 配置")
    
    saved_key = get_api_key()
    
    api_key = st.sidebar.text_input(
        "SiliconFlow API Key",
        type="password",
        value=saved_key,
        help="输入你的硅基流动 API Key（同时用于 LLM 和 Embedding）"
    )
    
    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button("💾 保存", use_container_width=True):
            if api_key:
                save_api_key(api_key)
                st.sidebar.success("✅ 已保存!")
            else:
                st.sidebar.error("请输入 Key")
    
    # 状态显示
    if api_key:
        st.sidebar.success("✅ API Key 已配置")
    else:
        st.sidebar.warning("⚠️ 请配置 API Key")
        st.sidebar.markdown("""
        **获取 API Key:**
        1. 访问 [硅基流动](https://siliconflow.cn/)
        2. 注册并登录
        3. 在控制台获取 Key
        """)
    
    return api_key


def render_sidebar_info():
    """渲染侧边栏的使用说明和技术栈信息"""
    st.sidebar.markdown("---")
    
    st.sidebar.subheader("📖 使用说明")
    st.sidebar.markdown("""
    1. 配置 API Key
    2. 上传 PDF/Word 文档
    3. 等待文档处理完成
    4. 在聊天框中提问
    5. 查看回答和引用来源
    """)
    
    st.sidebar.markdown("---")
    
    st.sidebar.subheader("🛠️ 技术栈")
    st.sidebar.markdown("""
    - **前端**: Streamlit
    - **LLM**: DeepSeek V3
    - **Embedding**: BGE-M3
    - **向量库**: ChromaDB
    - **框架**: LangChain
    """)


def render_quick_questions():
    """
    渲染快捷问题按钮
    
    Returns:
        选中的问题，如果没有选中则返回 None
    """
    st.markdown("**💡 快捷问题:**")
    
    questions = [
        "这篇文档的主要内容是什么？",
        "文档中提到了哪些关键概念？",
        "总结一下文档的核心观点",
        "文档使用了哪些研究方法？"
    ]
    
    cols = st.columns(len(questions))
    selected = None
    
    for i, q in enumerate(questions):
        with cols[i]:
            if st.button(q[:8] + "...", key=f"quick_q_{i}", use_container_width=True):
                selected = q
    
    return selected
