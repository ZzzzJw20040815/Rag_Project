"""
知识图谱可视化模块
使用 PyVis 生成可交互的知识图谱 HTML 可视化

主要功能：
- 将 NetworkX 图转换为 PyVis 可视化
- 生成交互式 HTML 图谱
- 支持 Streamlit 嵌入展示
"""

import os
from typing import Optional, Dict, Any
from pathlib import Path
import networkx as nx
from pyvis.network import Network

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import GRAPHS_DIR


# 节点类型对应的可视化配置
NODE_STYLE_CONFIG = {
    "document": {
        "color": "#4A90D9",  # 蓝色
        "shape": "dot",
        "size": 40,
        "font_color": "#FFFFFF",
        "border_width": 3,
        "border_color": "#2E5A8C"
    },
    "keyword": {
        "color": "#E74C3C",  # 红色
        "shape": "diamond",
        "size": 22,
        "font_color": "#333333",
        "border_width": 2,
        "border_color": "#A93226"
    },
    "method": {
        "color": "#27AE60",  # 绿色
        "shape": "triangle",
        "size": 24,
        "font_color": "#333333",
        "border_width": 2,
        "border_color": "#1E8449"
    },
    "dataset": {
        "color": "#F39C12",  # 黄色
        "shape": "square",
        "size": 20,
        "font_color": "#333333",
        "border_width": 2,
        "border_color": "#B7950B"
    },
    "field": {
        "color": "#9B59B6",  # 紫色 - 研究领域
        "shape": "star",
        "size": 26,
        "font_color": "#333333",
        "border_width": 2,
        "border_color": "#7D3C98"
    },
    "application": {
        "color": "#1ABC9C",  # 青色 - 应用场景
        "shape": "hexagon",
        "size": 22,
        "font_color": "#333333",
        "border_width": 2,
        "border_color": "#16A085"
    }
}


def create_pyvis_graph(
    nx_graph: nx.Graph,
    height: str = "600px",
    width: str = "100%",
    bgcolor: str = "#ffffff",
    font_color: str = "#333333"
) -> Network:
    """
    将 NetworkX 图转换为 PyVis Network 对象
    
    Args:
        nx_graph: NetworkX 图对象
        height: 图谱高度
        width: 图谱宽度
        bgcolor: 背景颜色
        font_color: 默认字体颜色
        
    Returns:
        PyVis Network 对象
    """
    # 创建 PyVis 网络
    net = Network(
        height=height,
        width=width,
        bgcolor=bgcolor,
        font_color=font_color,
        notebook=False,
        directed=False
    )
    
    # 配置物理引擎和交互设置
    # 降低滚轮灵敏度，优化物理效果
    net.set_options("""
    {
        "physics": {
            "enabled": true,
            "barnesHut": {
                "gravitationalConstant": -6000,
                "centralGravity": 0.25,
                "springLength": 100,
                "springConstant": 0.03,
                "damping": 0.12
            },
            "stabilization": {
                "enabled": true,
                "iterations": 200
            }
        },
        "interaction": {
            "hover": true,
            "tooltipDelay": 100,
            "hideEdgesOnDrag": true,
            "zoomSpeed": 0.3,
            "zoomView": true
        },
        "nodes": {
            "font": {
                "size": 13,
                "face": "Microsoft YaHei, Arial, sans-serif",
                "color": "#333333"
            }
        },
        "edges": {
            "smooth": {
                "type": "continuous"
            },
            "color": {
                "opacity": 0.7
            },
            "width": 1.5
        }
    }
    """)
    
    # 添加节点
    for node, attrs in nx_graph.nodes(data=True):
        node_type = attrs.get("node_type", "keyword")
        style = NODE_STYLE_CONFIG.get(node_type, NODE_STYLE_CONFIG["keyword"])
        
        # 计算节点大小（根据连接数调整）
        degree = nx_graph.degree(node)
        base_size = style["size"]
        size = base_size + min(degree * 2, 15)  # 最多增加15
        
        net.add_node(
            node,
            label=attrs.get("label", node),
            title=attrs.get("title", node),
            color=style["color"],
            shape=style["shape"],
            size=size,
            font={"color": style["font_color"]},
            borderWidth=style["border_width"],
            borderWidthSelected=style["border_width"] + 2
        )
    
    # 添加边
    for u, v, attrs in nx_graph.edges(data=True):
        edge_type = attrs.get("edge_type", "")
        weight = attrs.get("weight", 1.0)
        
        # 根据边类型设置颜色 - 支持更多边类型
        edge_colors = {
            "CONTAINS_KEYWORD": "#E74C3C",
            "USES_METHOD": "#27AE60",
            "USES_DATASET": "#F39C12",
            "BELONGS_TO_FIELD": "#9B59B6",
            "HAS_APPLICATION": "#1ABC9C"
        }
        color = edge_colors.get(edge_type, "#888888")
        
        net.add_edge(
            u, v,
            color=color,
            width=weight,
            title=edge_type.replace("_", " ").title()
        )
    
    return net


def render_graph_html(
    nx_graph: nx.Graph,
    output_path: Optional[str] = None,
    **kwargs
) -> str:
    """
    将 NetworkX 图渲染为 HTML 文件
    
    Args:
        nx_graph: NetworkX 图对象
        output_path: 输出文件路径，默认保存到 data/graphs/
        **kwargs: 传递给 create_pyvis_graph 的参数
        
    Returns:
        HTML 文件路径
    """
    if output_path is None:
        output_path = str(GRAPHS_DIR / "knowledge_graph.html")
    
    # 确保目录存在
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # 创建 PyVis 图
    net = create_pyvis_graph(nx_graph, **kwargs)
    
    # 保存 HTML
    net.save_graph(output_path)
    
    # 修复 HTML 中的中文编码问题
    _fix_html_encoding(output_path)
    
    print(f"✅ 图谱 HTML 已生成: {output_path}")
    return output_path


def _fix_html_encoding(filepath: str) -> None:
    """
    修复 PyVis 生成的 HTML 的编码问题
    
    Args:
        filepath: HTML 文件路径
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 确保 HTML 声明了 UTF-8 编码
        if '<meta charset="utf-8">' not in content.lower():
            content = content.replace(
                "<head>",
                '<head>\n    <meta charset="utf-8">',
                1
            )
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        print(f"⚠️ 修复 HTML 编码时出错: {e}")


def render_graph_in_streamlit(
    nx_graph: nx.Graph,
    height: int = 600,
    key: str = "knowledge_graph"
) -> None:
    """
    在 Streamlit 中嵌入展示知识图谱
    
    Args:
        nx_graph: NetworkX 图对象
        height: 图谱显示高度（像素）
        key: Streamlit 组件的唯一 key
    """
    import streamlit as st
    import streamlit.components.v1 as components
    
    if nx_graph is None or nx_graph.number_of_nodes() == 0:
        st.info("📊 暂无知识图谱数据。请先上传文档并进行实体提取。")
        return
    
    # 生成 HTML 文件 - 使用浅色背景保证深色/浅色模式都可见
    html_path = str(GRAPHS_DIR / f"{key}.html")
    render_graph_html(nx_graph, html_path, height=f"{height}px", bgcolor="#f8f9fa")
    
    # 读取并嵌入 HTML
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        
        components.html(html_content, height=height + 50, scrolling=True)
        
    except Exception as e:
        st.error(f"❌ 加载图谱失败: {e}")


def render_graph_statistics(stats: Dict[str, Any]) -> None:
    """
    在 Streamlit 中展示图谱统计信息
    
    Args:
        stats: KnowledgeGraph.get_statistics() 的返回值
    """
    import streamlit as st
    
    # 基础统计 - 6列显示所有实体类型
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        st.metric("📄 文档", stats.get("document_count", 0))
    with col2:
        st.metric("🏷️ 关键词", stats.get("keyword_count", 0))
    with col3:
        st.metric("⚙️ 方法", stats.get("method_count", 0))
    with col4:
        st.metric("📖 领域", stats.get("field_count", 0))
    with col5:
        st.metric("💻 应用", stats.get("application_count", 0))
    with col6:
        st.metric("📊 数据集", stats.get("dataset_count", 0))
    
    # 高频实体展示
    st.markdown("---")
    
    col_left, col_mid, col_right = st.columns(3)
    
    with col_left:
        st.markdown("**🔥 高频关键词**")
        top_keywords = stats.get("top_keywords", [])
        if top_keywords:
            for kw, count in top_keywords:
                st.write(f"• {kw} ({count})")
        else:
            st.write("暂无数据")
    
    with col_mid:
        st.markdown("**🔥 高频方法**")
        top_methods = stats.get("top_methods", [])
        if top_methods:
            for method, count in top_methods:
                st.write(f"• {method} ({count})")
        else:
            st.write("暂无数据")
    
    with col_right:
        st.markdown("**📖 研究领域**")
        top_fields = stats.get("top_fields", [])
        if top_fields:
            for field, count in top_fields:
                st.write(f"• {field} ({count})")
        else:
            st.write("暂无数据")


def render_legend() -> None:
    """在 Streamlit 中渲染图例说明 - 支持更多实体类型"""
    import streamlit as st
    
    st.markdown("""
    <div style="display: flex; gap: 15px; flex-wrap: wrap; padding: 10px; 
                background: #f8f9fa; border-radius: 8px; margin-bottom: 15px;">
        <div style="display: flex; align-items: center; gap: 5px;">
            <div style="width: 16px; height: 16px; background: #4A90D9; border-radius: 50%;"></div>
            <span style="color: #333;">文档</span>
        </div>
        <div style="display: flex; align-items: center; gap: 5px;">
            <div style="width: 14px; height: 14px; background: #E74C3C; transform: rotate(45deg);"></div>
            <span style="color: #333;">关键词</span>
        </div>
        <div style="display: flex; align-items: center; gap: 5px;">
            <div style="width: 0; height: 0; border-left: 8px solid transparent; 
                        border-right: 8px solid transparent; border-bottom: 14px solid #27AE60;"></div>
            <span style="color: #333;">方法</span>
        </div>
        <div style="display: flex; align-items: center; gap: 5px;">
            <div style="width: 14px; height: 14px; background: #F39C12;"></div>
            <span style="color: #333;">数据集</span>
        </div>
        <div style="display: flex; align-items: center; gap: 5px;">
            <div style="width: 16px; height: 16px; background: #9B59B6; 
                        clip-path: polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%);"></div>
            <span style="color: #333;">研究领域</span>
        </div>
        <div style="display: flex; align-items: center; gap: 5px;">
            <div style="width: 14px; height: 14px; background: #1ABC9C; border-radius: 3px;"></div>
            <span style="color: #333;">应用场景</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
