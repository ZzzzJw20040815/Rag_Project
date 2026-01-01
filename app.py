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
    render_quick_questions,
    render_chat_qa_item
)
from ui.graph_view import (
    render_graph_in_streamlit,
    render_graph_statistics,
    render_legend
    # [REMOVED] render_entity_source_buttons - 如需恢复，取消注释并取消下方调用处的注释
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
    if "pending_quick_question" not in st.session_state:
        st.session_state.pending_quick_question = None
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


def handle_question(question: str, api_key: str, selected_docs: list = None):
    """
    处理用户问题
    
    Args:
        question: 用户问题
        api_key: API Key
        selected_docs: 选中的文档名称列表（用于过滤检索范围）
    """
    if not question.strip():
        return
    
    if not st.session_state.documents_loaded:
        st.warning("请先上传并处理文档")
        return
    
    with st.spinner("🤔 正在思考..."):
        try:
            # 获取检索器（根据是否有文档选择决定是否过滤）
            all_doc_names = [d.get("name") for d in st.session_state.uploaded_files_info]
            
            # 判断是否需要过滤：只有当选择了部分文档时才过滤
            if selected_docs and set(selected_docs) != set(all_doc_names):
                # 用户选择了部分文档，使用过滤检索器
                retriever = st.session_state.vector_store_manager.as_retriever_filtered(selected_docs)
            else:
                # 全选或未指定，使用普通检索器
                retriever = st.session_state.vector_store_manager.as_retriever()
            
            # 创建 RAG 链
            rag_chain = RAGChain(retriever, api_key=api_key)
            
            # 执行查询
            result = rag_chain.query(question)
            
            # 保存到历史记录（包含选中的文档信息）
            st.session_state.chat_history.append({
                "question": question,
                "answer": result["answer"],
                "sources": result["sources"],
                "selected_docs": selected_docs or []  # 保存提问时选择的文档
            })
            
            
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
    渲染聊天界面（使用原生 st.chat_message 和 st.chat_input）
    
    Args:
        api_key: API Key
    """
    st.subheader("💬 智能问答")
    
    # 检查是否有待处理的快捷问题
    if "pending_quick_question" in st.session_state and st.session_state.pending_quick_question:
        pending_q = st.session_state.pending_quick_question
        selected = st.session_state.get("selected_docs_for_qa", None)
        st.session_state.pending_quick_question = None  # 清除待处理问题
        handle_question(pending_q, api_key, selected)
    
    # 渲染历史消息（使用原生 chat_message 组件）
    for i, chat in enumerate(st.session_state.chat_history):
        render_chat_qa_item(chat, index=i, is_latest=(i == len(st.session_state.chat_history) - 1))
    
    # 问答输入区
    if st.session_state.documents_loaded and api_key:
        # 快捷问题区域（放在聊天消息和输入框之间）
        with st.container():
            quick_q, selected_docs = render_quick_questions(st.session_state.uploaded_files_info)
            
            # 保存当前选中的文档（用于检索过滤）
            st.session_state.selected_docs_for_qa = selected_docs
            
            # 如果点击了快捷问题，保存到 pending 状态并刷新
            if quick_q:
                st.session_state.pending_quick_question = quick_q
                st.rerun()
        
        st.markdown("---")
        
        # 清除对话按钮（放在输入框上方）
        col1, col2 = st.columns([5, 1])
        with col2:
            if st.button("🗑️ 清除对话", use_container_width=True):
                st.session_state.chat_history = []
                st.rerun()
        
        # 使用原生 st.chat_input 替代 text_input + button
        # chat_input 自动固定在页面底部，支持 Enter 提交
        if question := st.chat_input("输入你的问题...", key="chat_input"):
            # 获取当前选中的文档
            selected = st.session_state.get("selected_docs_for_qa", None)
            handle_question(question, api_key, selected)
                
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
                # 使用 st.status 显示实时进度
                with st.status("🔍 正在使用 AI 提取文档实体...", expanded=True) as status:
                    progress_container = st.empty()
                    progress_messages = []
                    
                    def progress_callback(message: str, level: str):
                        """接收进度更新并显示在 UI 上"""
                        # 根据 level 设置样式
                        if level == "file":
                            styled_msg = f"**{message}**"
                        elif level == "success":
                            styled_msg = f"✅ {message}"
                        elif level == "error":
                            styled_msg = f"⚠️ {message}"
                        else:
                            styled_msg = message
                        
                        progress_messages.append(styled_msg)
                        # 只显示最近 10 条消息，避免过长
                        recent_messages = progress_messages[-10:]
                        progress_container.markdown("\n\n".join(recent_messages))
                    
                    try:
                        # 创建实体提取器
                        extractor = EntityExtractor(api_key=api_key)
                        
                        # 从 chunks 中提取实体，传入进度回调
                        extraction_results = extractor.extract_from_documents(
                            st.session_state.processed_chunks,
                            progress_callback=progress_callback
                        )
                        
                        # 更新状态为构建图谱
                        status.update(label="📊 正在构建知识图谱...", state="running")
                        progress_callback("📊 正在构建知识图谱...", "info")
                        
                        # 构建知识图谱
                        st.session_state.knowledge_graph = KnowledgeGraph()
                        st.session_state.knowledge_graph.build_from_extraction_results(
                            extraction_results
                        )
                        
                        # 保存图谱
                        st.session_state.knowledge_graph.save()
                        st.session_state.entities_extracted = True
                        
                        # 完成状态
                        total_entities = sum(
                            sum(len(v) for v in entities.values())
                            for entities in extraction_results.values()
                        )
                        status.update(
                            label=f"✅ 完成！成功从 {len(extraction_results)} 个文档提取 {total_entities} 个实体",
                            state="complete",
                            expanded=False
                        )
                        st.rerun()
                        
                    except Exception as e:
                        status.update(label="❌ 实体提取失败", state="error")
                        st.error(f"❌ 实体提取失败: {str(e)}")
            
            # 显示知识图谱
            if st.session_state.entities_extracted:
                st.markdown("---")
                
                # 图例
                render_legend()
                
                # 图谱统计
                stats = st.session_state.knowledge_graph.get_statistics()
                render_graph_statistics(stats)
                
                # [REMOVED] 实体来源追溯功能 - 如需恢复，取消以下注释：
                # render_entity_source_buttons(stats, st.session_state.knowledge_graph)
                
                # st.markdown("---")
                st.markdown("### 📊 交互式论文地图")
                st.caption("提示：可拖拽节点，悬停查看详情，点击节点查看连接关系")
                
                # 渲染图谱 (使用默认高度750)
                render_graph_in_streamlit(
                    st.session_state.knowledge_graph.graph,
                    key="main_knowledge_graph",
                    doc_entity_map=stats.get("document_entities", {})
                )
    
    # 底部信息
    st.markdown("---")
    st.markdown(
        '<p class="footer">💡 基于 LangChain + ChromaDB + Streamlit 构建的学术文献智能分析系统</p>',
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()
