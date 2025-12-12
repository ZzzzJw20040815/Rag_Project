"""
学术文献智能导读与可视化分析系统
Academic Literature Intelligent Guidance System

主应用入口
"""

import streamlit as st
from pathlib import Path
import sys

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from config import get_api_key
from core.document_processor import DocumentProcessor
from core.vector_store import VectorStoreManager
from core.rag_chain import RAGChain
from core.entity_extractor import EntityExtractor
from core.knowledge_graph import KnowledgeGraph
from ui import (
    init_page_config,
    get_custom_css,
    render_chat_message,
    render_source_documents,
    render_sidebar_api_config,
    render_sidebar_info,
    render_quick_questions
)
from ui.graph_view import (
    render_graph_in_streamlit,
    render_graph_statistics,
    render_legend
)


def init_session_state():
    """初始化 session state"""
    if "vector_store_manager" not in st.session_state:
        st.session_state.vector_store_manager = None
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "documents_loaded" not in st.session_state:
        st.session_state.documents_loaded = False
    if "uploaded_files_info" not in st.session_state:
        st.session_state.uploaded_files_info = []
    if "api_key" not in st.session_state:
        st.session_state.api_key = get_api_key()
    if "current_question" not in st.session_state:
        st.session_state.current_question = ""
    # 知识图谱相关状态
    if "knowledge_graph" not in st.session_state:
        st.session_state.knowledge_graph = KnowledgeGraph()
    if "entities_extracted" not in st.session_state:
        st.session_state.entities_extracted = False
    if "processed_chunks" not in st.session_state:
        st.session_state.processed_chunks = []


def process_uploaded_files(uploaded_files, api_key: str):
    """
    处理上传的文件
    
    Args:
        uploaded_files: Streamlit 上传的文件列表
        api_key: API Key
    """
    if not uploaded_files:
        return
    
    # 初始化处理器
    doc_processor = DocumentProcessor()
    
    # 初始化或获取向量存储管理器
    if st.session_state.vector_store_manager is None:
        st.session_state.vector_store_manager = VectorStoreManager(api_key=api_key)
    
    all_chunks = []
    files_info = []
    
    for uploaded_file in uploaded_files:
        filename = uploaded_file.name
        
        with st.spinner(f"📖 正在处理 {filename}..."):
            try:
                # 处理文件：解析 + 切分
                chunks = doc_processor.process_uploaded_file(
                    uploaded_file,
                    filename,
                    clean=True  # 清洗文本，移除参考文献等
                )
                
                all_chunks.extend(chunks)
                files_info.append({
                    "name": filename,
                    "size": uploaded_file.size,
                    "chunks": len(chunks)
                })
                
                st.success(f"✅ {filename}: 解析完成，生成 {len(chunks)} 个文本块")
                
            except Exception as e:
                st.error(f"❌ 处理 {filename} 时出错: {str(e)}")
    
    if all_chunks:
        with st.spinner("🔢 正在创建向量索引..."):
            try:
                # 创建向量存储
                st.session_state.vector_store_manager.create_from_documents(
                    all_chunks,
                    persist=True
                )
                
                st.session_state.documents_loaded = True
                st.session_state.uploaded_files_info = files_info
                # 保存 chunks 供知识图谱使用
                st.session_state.processed_chunks = all_chunks
                # 重置知识图谱状态（需要重新提取实体）
                st.session_state.knowledge_graph = KnowledgeGraph()
                st.session_state.entities_extracted = False
                
                total_chunks = sum(f["chunks"] for f in files_info)
                st.success(f"✅ 向量索引创建成功！共处理 {len(files_info)} 个文件，{total_chunks} 个文本块")
                
            except Exception as e:
                st.error(f"❌ 创建向量索引时出错: {str(e)}")


def handle_question(question: str, api_key: str):
    """
    处理用户问题
    
    Args:
        question: 用户问题
        api_key: API Key
    """
    if not question.strip():
        return
    
    if not st.session_state.documents_loaded:
        st.warning("请先上传并处理文档")
        return
    
    with st.spinner("🤔 正在思考..."):
        try:
            # 获取检索器
            retriever = st.session_state.vector_store_manager.as_retriever()
            
            # 创建 RAG 链
            rag_chain = RAGChain(retriever, api_key=api_key)
            
            # 执行查询
            result = rag_chain.query(question)
            
            # 保存到历史记录
            st.session_state.chat_history.append({
                "question": question,
                "answer": result["answer"],
                "sources": result["sources"]
            })
            
            # 清空输入框
            st.session_state.current_question = ""
            
            # 刷新页面以显示新消息
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ 回答问题时出错: {str(e)}")


def render_document_status():
    """渲染文档状态信息"""
    if st.session_state.documents_loaded:
        st.success("✅ 文档已加载，可以开始提问！")
        
        # 显示已上传的文件信息
        if st.session_state.uploaded_files_info:
            with st.expander("📋 已加载的文档", expanded=False):
                for f in st.session_state.uploaded_files_info:
                    st.markdown(f"- **{f['name']}** ({f['size']/1024:.1f} KB, {f['chunks']} 个文本块)")
        
        # 清除按钮
        if st.button("🗑️ 清除所有文档", use_container_width=True):
            if st.session_state.vector_store_manager:
                st.session_state.vector_store_manager.clear()
            st.session_state.vector_store_manager = None
            st.session_state.documents_loaded = False
            st.session_state.uploaded_files_info = []
            st.session_state.chat_history = []
            # 清除知识图谱相关状态
            st.session_state.knowledge_graph = KnowledgeGraph()
            st.session_state.entities_extracted = False
            st.session_state.processed_chunks = []
            st.rerun()
    else:
        st.info("⏳ 请上传文档开始使用")


def render_chat_interface(api_key: str):
    """
    渲染聊天界面
    
    Args:
        api_key: API Key
    """
    st.subheader("💬 智能问答")
    
    # 渲染历史消息
    for chat in st.session_state.chat_history:
        render_chat_message("user", chat["question"])
        render_chat_message("assistant", chat["answer"])
        render_source_documents(chat.get("sources", []))
    
    # 问答输入区
    if st.session_state.documents_loaded and api_key:
        # 快捷问题
        quick_q = render_quick_questions()
        if quick_q:
            st.session_state.current_question = quick_q
            # 强制刷新以更新输入框
            st.rerun()
        
        st.markdown("---")
        
        # 输入框
        # 使用 callback 会更好，但这里简单起见，利用 session_state 绑定
        if "current_question" not in st.session_state:
            st.session_state.current_question = ""
            
        question = st.text_input(
            "输入你的问题",
            value=st.session_state.current_question,
            placeholder="请输入关于文档的问题...",
            key="question_input"
        )
        
        # 输入框的值变化时，可能会更新 key 对应的 state，但不会自动同步到 current_question
        # 所以我们需要把 input 的值回写到 logic state (如果需要的话)
        # 但这里主要就是为了让 quick_q 点击后填充进去。
        
        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("🔍 提问", use_container_width=True):
                handle_question(question, api_key)
        with col2:
            if st.button("🗑️ 清除对话", use_container_width=True):
                st.session_state.chat_history = []
                st.session_state.current_question = ""
                st.rerun()
                
    elif not st.session_state.documents_loaded:
        st.info("👆 请先上传并处理文档")
    elif not api_key:
        st.warning("👈 请在侧边栏配置 API Key")


def main():
    """主函数"""
    # 初始化页面配置
    init_page_config()
    
    # 初始化 session state
    init_session_state()
    
    # 渲染侧边栏
    api_key = render_sidebar_api_config()
    st.session_state.api_key = api_key
    render_sidebar_info()
    
    # 主标题
    st.markdown('<h1 class="main-header">📚 学术文献智能导读系统</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">基于知识图谱增强的 RAG 文档问答与可视化分析</p>', unsafe_allow_html=True)
    
    # 使用 Tab 组织界面
    tab1, tab2, tab3 = st.tabs(["📤 文档上传", "💬 智能问答", "🌐 知识图谱"])
    
    with tab1:
        st.subheader("📤 上传文档")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # 文件上传
            uploaded_files = st.file_uploader(
                "选择 PDF 或 Word 文件",
                type=["pdf", "docx", "doc"],
                accept_multiple_files=True,
                help="支持同时上传多个文件"
            )
            
            if uploaded_files:
                st.write(f"📄 已选择 {len(uploaded_files)} 个文件")
                for f in uploaded_files:
                    st.write(f"  - {f.name} ({f.size/1024:.1f} KB)")
                
                if st.button("🚀 处理文档", use_container_width=True):
                    if not api_key:
                        st.error("请先在侧边栏配置 API Key")
                    else:
                        process_uploaded_files(uploaded_files, api_key)
        
        with col2:
            st.subheader("📊 状态")
            render_document_status()
    
    with tab2:
        render_chat_interface(api_key)
    
    with tab3:
        st.subheader("🗺️ 论文地图 - 知识图谱")
        
        if not st.session_state.documents_loaded:
            st.info("👆 请先在「文档上传」页面上传并处理文档")
        else:
            # 实体提取按钮
            col1, col2 = st.columns([1, 3])
            with col1:
                extract_btn = st.button(
                    "🔍 提取实体" if not st.session_state.entities_extracted else "🔄 重新提取",
                    use_container_width=True
                )
            with col2:
                if st.session_state.entities_extracted:
                    st.success("✅ 实体已提取，图谱已生成")
                else:
                    st.info("点击「提取实体」按钮开始构建知识图谱")
            
            # 执行实体提取
            if extract_btn and api_key:
                with st.spinner("🔍 正在使用 AI 提取文档实体..."):
                    try:
                        # 创建实体提取器
                        extractor = EntityExtractor(api_key=api_key)
                        
                        # 从 chunks 中提取实体
                        extraction_results = extractor.extract_from_documents(
                            st.session_state.processed_chunks
                        )
                        
                        # 构建知识图谱
                        st.session_state.knowledge_graph = KnowledgeGraph()
                        st.session_state.knowledge_graph.build_from_extraction_results(
                            extraction_results
                        )
                        
                        # 保存图谱
                        st.session_state.knowledge_graph.save()
                        st.session_state.entities_extracted = True
                        
                        st.success(f"✅ 成功提取 {len(extraction_results)} 个文档的实体！")
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ 实体提取失败: {str(e)}")
            
            # 显示知识图谱
            if st.session_state.entities_extracted:
                st.markdown("---")
                
                # 图例
                render_legend()
                
                # 图谱统计
                stats = st.session_state.knowledge_graph.get_statistics()
                render_graph_statistics(stats)
                
                st.markdown("---")
                st.markdown("### 📊 交互式论文地图")
                st.caption("提示：可拖拽节点，悬停查看详情")
                
                # 渲染图谱
                render_graph_in_streamlit(
                    st.session_state.knowledge_graph.graph,
                    height=550,
                    key="main_knowledge_graph"
                )
    
    # 底部信息
    st.markdown("---")
    st.markdown(
        '<p class="footer">💡 基于 LangChain + ChromaDB + Streamlit 构建的学术文献智能分析系统</p>',
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()
