"""
引用溯源视图模块
Citation Source View Module

提供引用标记渲染和源文档高亮显示功能
"""

import re
import html
import streamlit as st
from typing import List, Dict, Optional


# 为不同的 doc_id 分配统一的颜色，确保回答和源文档区颜色一致
# 使用渐变紫色系，保持视觉协调
CITATION_COLORS = [
    "#8B5CF6",  # doc_0: 紫色
    "#06B6D4",  # doc_1: 青色
    "#F59E0B",  # doc_2: 琥珀色
    "#10B981",  # doc_3: 绿色
    "#EC4899",  # doc_4: 粉色
    "#3B82F6",  # doc_5: 蓝色
    "#EF4444",  # doc_6: 红色
    "#84CC16",  # doc_7: 黄绿
    "#F97316",  # doc_8: 橙色
    "#6366F1",  # doc_9: 靛蓝
]


def get_citation_color(doc_id: str) -> str:
    """
    根据 doc_id 获取对应的颜色
    
    Args:
        doc_id: 如 "doc_0", "doc_1" 等
        
    Returns:
        颜色十六进制值
    """
    try:
        idx = int(doc_id.replace("doc_", ""))
        return CITATION_COLORS[idx % len(CITATION_COLORS)]
    except:
        return CITATION_COLORS[0]


def get_citation_css() -> str:
    """
    获取引用溯源相关的 CSS 样式
    
    Returns:
        CSS 样式字符串
    """
    return """
    <style>
        /* 引用标记样式 - 气泡中的 [doc_X] */
        .citation-tag {
            display: inline-block;
            padding: 2px 8px;
            margin: 0 2px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: 600;
            color: white !important;
            text-decoration: none;
            cursor: default;
            vertical-align: middle;
            box-shadow: 0 1px 3px rgba(0,0,0,0.2);
        }
        
        .citation-tag:hover {
            transform: scale(1.05);
            box-shadow: 0 2px 6px rgba(0,0,0,0.3);
        }
        
        /* 源文档卡片标题 */
        .source-header {
            padding: 8px 12px;
            border-radius: 8px 8px 0 0;
            color: white !important;
            font-weight: 600;
            margin-bottom: 0;
        }
        
        .source-header * {
            color: white !important;
        }
        
        /* 源文档内容区域 */
        .source-content {
            background: rgba(0,0,0,0.03);
            padding: 12px;
            border-radius: 0 0 8px 8px;
            border: 1px solid rgba(0,0,0,0.1);
            border-top: none;
            font-size: 0.9em;
            line-height: 1.6;
            max-height: 200px;
            overflow-y: auto;
        }
        
        /* 匹配提示文字 */
        .citation-hint {
            font-size: 0.8em;
            color: #888;
            margin-top: 8px;
            padding: 6px 10px;
            background: rgba(102, 126, 234, 0.1);
            border-radius: 6px;
            border-left: 3px solid #667eea;
        }
    </style>
    """


def render_answer_with_citations(answer: str, sources: List[dict]) -> str:
    """
    将回答中的 [doc_X] 引用标记转换为带颜色的可视化标签
    
    Args:
        answer: AI 的回答文本，可能包含 [doc_0], [doc_1] 等标记
        sources: 源文档列表，用于验证引用是否有效
        
    Returns:
        处理后的 HTML 文本
    """
    # 获取有效的 doc_id 集合
    valid_doc_ids = {s.get("doc_id", f"doc_{i}") for i, s in enumerate(sources)}
    
    def replace_citation(match):
        """替换单个引用标记为彩色标签"""
        doc_id = match.group(1)  # 如 "doc_0"
        
        # 检查是否为有效引用
        if doc_id not in valid_doc_ids:
            return match.group(0)  # 保持原样
        
        color = get_citation_color(doc_id)
        
        # 创建带颜色的标签
        return f'<span class="citation-tag" style="background: {color};" title="查看来源 {doc_id}">{doc_id}</span>'
    
    # 匹配 [doc_X] 格式（支持 [doc_0][doc_1] 连续形式）
    pattern = r'\[(doc_\d+)\]'
    processed_answer = re.sub(pattern, replace_citation, answer)
    
    return processed_answer


def render_source_panel(sources: List[dict], expanded: bool = False):
    """
    渲染源文档面板，带与引用标记匹配的颜色标识
    
    Args:
        sources: 源文档列表，每个元素包含 doc_id, content, page, source_file
        expanded: 是否默认展开（默认折叠以节省空间）
    """
    if not sources:
        return
    
    # 注入 CSS
    st.markdown(get_citation_css(), unsafe_allow_html=True)
    
    # 使用 expander 折叠源文档区域
    expander_label = f"📚 引用来源 ({len(sources)} 个)"
    
    with st.expander(expander_label, expanded=expanded):
        # 提示文字
        st.markdown(
            '<div class="citation-hint">💡 提示：回答中的标记颜色与下方来源标题颜色一致，可快速定位对应内容。</div>',
            unsafe_allow_html=True
        )
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # 渲染所有源文档（不限制数量）
        for idx, source in enumerate(sources):
            doc_id = source.get("doc_id", f"doc_{idx}")
            color = get_citation_color(doc_id)
            
            source_file = source.get("source_file", "未知文件")
            page = source.get("page", "?")
            content = source.get("content", "")
            
            # 截断内容避免过长，并转义 HTML 特殊字符防止渲染错误
            truncated_content = content[:500] + "..." if len(content) > 500 else content
            display_content = html.escape(truncated_content)
            
            # 同样转义文件名（可能含有特殊字符）
            safe_source_file = html.escape(str(source_file))
            
            # 渲染带颜色的标题栏
            st.markdown(
                f'''
                <div class="source-header" style="background: {color};">
                    <strong>[{doc_id}]</strong> {safe_source_file} · 第 {page} 页
                </div>
                <div class="source-content">
                    {display_content}
                </div>
                <br>
                ''',
                unsafe_allow_html=True
            )


def render_chat_answer_with_sources(answer: str, sources: List[dict], is_latest: bool = False):
    """
    渲染带引用标记的完整问答和源文档
    
    整合了 render_answer_with_citations 和 render_source_panel，
    提供完整的引用溯源展示体验。
    
    Args:
        answer: AI 回答文本
        sources: 源文档列表
        is_latest: 是否是最新问答（最新的可以默认展开源文档）
    """
    # 注入 CSS
    st.markdown(get_citation_css(), unsafe_allow_html=True)
    
    # 处理回答中的引用标记
    processed_answer = render_answer_with_citations(answer, sources)
    
    # 使用 Streamlit markdown 渲染（支持原有 markdown 格式）
    st.markdown(processed_answer, unsafe_allow_html=True)
    
    # 渲染源文档面板（最新问答默认展开）
    if sources:
        render_source_panel(sources, expanded=is_latest)
