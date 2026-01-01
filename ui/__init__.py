"""
UI 组件模块
提供可复用的 Streamlit UI 组件
"""

import re
import streamlit as st

# 引用溯源模块
from ui.source_view import (
    render_chat_answer_with_sources,
    render_source_panel,
    get_citation_css
)


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
    # 行内代码：跳过空内容、纯符号、或过短的内容，避免灰色方块
    def process_inline_code(match):
        content = match.group(1)
        # 跳过空白内容
        if not content.strip():
            return content
        # 跳过纯符号内容（如 `...` `、` 等）
        if re.match(r'^[.\s,，、。！？：；\-—_\u2026]+$', content):
            return content
        # 跳过过短的无意义内容
        if len(content.strip()) <= 1 and not content.strip().isalnum():
            return content
        # 正常渲染有意义的代码
        return f'<code style="background: rgba(0,0,0,0.1); padding: 2px 4px; border-radius: 3px;">{content}</code>'
    
    text = re.sub(r'`([^`]*?)`', process_inline_code, text)
    
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


def render_chat_message(role: str, content: str, use_container: bool = True):
    """
    使用 Streamlit 原生 st.chat_message 渲染聊天消息
    
    Args:
        role: 角色 ("user" 或 "assistant")
        content: 消息内容
        use_container: 是否使用 chat_message 容器（在已有容器内可设为 False）
    """
    # 映射角色到 Streamlit 支持的角色名
    avatar = "🧑" if role == "user" else "🤖"
    
    if use_container:
        with st.chat_message(role, avatar=avatar):
            # st.chat_message 内部原生支持 Markdown，直接使用 st.markdown
            st.markdown(content)
    else:
        # 不使用容器时，直接渲染 markdown（用于嵌套场景）
        st.markdown(f"**{'用户' if role == 'user' else '助手'}:** {content}")


def render_source_documents(sources: list, use_expander: bool = True):
    """
    渲染来源文档
    
    Args:
        sources: 来源文档列表，每个元素包含 content, page, source_file
        use_expander: 是否使用 expander 包裹（在已有 expander 内调用时设为 False）
    """
    if not sources:
        return
    
    def render_sources_content():
        """渲染来源内容的内部函数"""
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
    
    if use_expander:
        with st.expander("📚 查看引用来源", expanded=False):
            render_sources_content()
    else:
        st.markdown("---")
        st.markdown("**📚 引用来源详情：**")
        render_sources_content()


def render_chat_qa_item(chat: dict, index: int, is_latest: bool = False):
    """
    渲染单个问答项（使用原生 st.chat_message 组件）
    
    Args:
        chat: 包含 question, answer, sources, selected_docs 的字典
        index: 问答索引（用于生成唯一 key）
        is_latest: 是否是最新的问答（最新的默认展开）
    """
    question = chat.get("question", "")
    answer = chat.get("answer", "")
    sources = chat.get("sources", [])
    selected_docs = chat.get("selected_docs", [])
    
    # 显示引用的文献来源标签（在消息外部显示）
    if selected_docs:
        doc_labels = " · ".join([f"📄 {d}" for d in selected_docs])
        # 使用能同时适配浅色和深色模式的样式
        st.markdown(
            f'<div style="background: linear-gradient(90deg, rgba(102,126,234,0.15), rgba(118,75,162,0.15)); '
            f'padding: 8px 12px; border-radius: 8px; margin-bottom: 8px; '
            f'font-size: 0.85em; border: 1px solid rgba(102,126,234,0.3);">'
            f'<strong>📚 引用文献：</strong>{doc_labels}</div>',
            unsafe_allow_html=True
        )
    
    # 使用原生 st.chat_message 渲染问题
    with st.chat_message("user", avatar="🧑"):
        st.markdown(question)
    
    # 使用原生 st.chat_message 渲染回答（使用引用溯源组件）
    with st.chat_message("assistant", avatar="🤖"):
        # 使用新的引用溯源渲染函数，将 [doc_X] 转为彩色标签
        render_chat_answer_with_sources(answer, sources, is_latest=is_latest)


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


def render_quick_questions(docs_info: list = None):
    """
    渲染快捷问题按钮
    
    Args:
        docs_info: 已上传的文档信息列表 [{"name": "文件名", ...}, ...]
    
    Returns:
        (selected_question, selected_docs): 选中的问题和选中的文档名称列表
    """
    # 单文献问题
    single_doc_questions = [
        "这篇文档的主要内容是什么？",
        "文档中提到了哪些关键概念？",
        "总结一下文档的核心观点",
        "文档使用了哪些研究方法？"
    ]
    
    # 多文献问题
    multi_doc_questions = [
        "这些文献的共同主题是什么？",
        "各文献的研究方法有何异同？",
        "总结各文献的核心观点及关联",
        "这些文献在该领域的发展脉络？"
    ]
    
    docs_info = docs_info or []
    num_docs = len(docs_info)
    selected_question = None
    selected_docs = []
    
    # 多文献场景：显示文献选择器
    if num_docs >= 2:
        st.markdown("**📂 选择分析范围:**")
        
        # 初始化 session state 用于保存选择状态
        if "selected_doc_indices" not in st.session_state:
            st.session_state.selected_doc_indices = list(range(num_docs))  # 默认全选
        
        # 创建选择器布局
        selector_cols = st.columns([3, 1])
        
        with selector_cols[0]:
            # 使用 multiselect 让用户选择文档
            doc_names = [d.get("name", f"文档{i+1}") for i, d in enumerate(docs_info)]
            
            # 获取当前选中的文档名称
            default_selected = [doc_names[i] for i in st.session_state.selected_doc_indices 
                               if i < len(doc_names)]
            
            selected_doc_names = st.multiselect(
                "选择要分析的文献（可多选）",
                options=doc_names,
                default=default_selected,
                key="doc_selector",
                placeholder="请选择文献...",
                label_visibility="collapsed"
            )
            
            # 更新 session state
            st.session_state.selected_doc_indices = [doc_names.index(n) for n in selected_doc_names]
            selected_docs = selected_doc_names
        
        with selector_cols[1]:
            # 快捷操作按钮
            if st.button("全选", key="select_all_docs", use_container_width=True):
                st.session_state.selected_doc_indices = list(range(num_docs))
                st.rerun()
        
        # 显示选择状态提示
        if len(selected_docs) == 0:
            st.warning("⚠️ 请至少选择一篇文献")
            return None, []
        elif len(selected_docs) == 1:
            st.caption(f"📄 已选择 1 篇文献，显示单文献问题")
            questions = single_doc_questions
        else:
            st.caption(f"📚 已选择 {len(selected_docs)} 篇文献，显示多文献对比问题")
            questions = multi_doc_questions
    else:
        # 单文献场景
        questions = single_doc_questions
        if docs_info:
            selected_docs = [docs_info[0].get("name", "文档1")]
    
    # 添加自定义 CSS 让按钮文字可以换行显示 + 文档选择器完整显示
    st.markdown("""
    <style>
        /* 快捷问题按钮换行 */
        div[data-testid="stHorizontalBlock"] .stButton > button {
            white-space: normal !important;
            word-wrap: break-word !important;
            height: auto !important;
            min-height: 45px !important;
            padding: 8px 12px !important;
            line-height: 1.3 !important;
        }
        
        /* 文档选择器：完整显示文档名称 */
        div[data-testid="stMultiSelect"] span[data-baseweb="tag"] {
            max-width: none !important;
        }
        div[data-testid="stMultiSelect"] span[data-baseweb="tag"] span {
            max-width: none !important;
            overflow: visible !important;
            text-overflow: clip !important;
        }
        /* 下拉选项也完整显示 */
        ul[role="listbox"] li {
            white-space: normal !important;
            word-wrap: break-word !important;
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("**💡 快捷问题:**")
    
    # 使用 2x2 布局让问题更好地显示
    row1_cols = st.columns(2)
    row2_cols = st.columns(2)
    all_cols = row1_cols + row2_cols
    
    for i, q in enumerate(questions):
        with all_cols[i]:
            if st.button(q, key=f"quick_q_{i}", use_container_width=True):
                selected_question = q
    
    return selected_question, selected_docs
