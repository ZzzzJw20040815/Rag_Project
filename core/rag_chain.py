"""
RAG 问答链模块
封装 LangChain 的检索增强生成逻辑
"""

from typing import Dict, List, Optional, Any
from langchain_openai import ChatOpenAI
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain.schema import Document

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from config import (
    SILICONFLOW_BASE_URL,
    LLM_MODEL,
    LLM_TEMPERATURE,
    LLM_MAX_TOKENS,
    RETRIEVAL_K,
    get_api_key
)


# RAG 问答的 Prompt 模板
# 优化设计：区分「找具体信息」和「总结全文」两种场景
RAG_PROMPT_TEMPLATE = """你是一个专业的学术文献分析助手。请基于以下检索到的文献内容，回答用户的问题。

【检索到的文献内容】
{context}

【用户问题】
{question}

【回答要求】
1. **优先引用原文**：如果检索内容中包含问题所需的信息，请直接引用或总结原文回答。
2. **区分问题类型**：
   - 如果用户询问**具体事实**（如"有哪些方法"、"数据是多少"），而检索内容中确实没有相关信息，请明确回答"根据已检索的内容，文档中未提及相关具体信息"。
   - 如果用户询问**宏观总结**（如"这篇文章讲了什么"、"总结一下主要内容"），请综合检索内容进行概括。
3. **保持客观准确**：完全基于检索到的内容回答，不要编造或臆测。
4. **格式清晰**：使用 Markdown 格式组织回答，适当使用标题、列表等提高可读性。
5. **表格格式**：如果需要展示表格数据，**必须使用标准 Markdown 表格语法**，格式如下：
   ```
   | 列1 | 列2 | 列3 |
   | --- | --- | --- |
   | 数据1 | 数据2 | 数据3 |
   ```
   - 每行以 `|` 开头和结尾
   - 表头和数据之间必须有分隔行 `| --- | --- |`
   - **禁止使用空格对齐的纯文本表格**

【回答】"""


def get_llm(api_key: Optional[str] = None) -> ChatOpenAI:
    """
    获取 LLM 实例
    
    使用 SiliconFlow API 调用 DeepSeek 模型
    
    Args:
        api_key: 可选的 API Key
        
    Returns:
        ChatOpenAI 实例
        
    Raises:
        ValueError: 如果没有配置 API Key
    """
    key = api_key or get_api_key()
    
    if not key:
        raise ValueError(
            "请先配置 API Key！\n"
            "可以在侧边栏输入，或在 .env 文件中设置 DEEPSEEK_API_KEY"
        )
    
    llm = ChatOpenAI(
        model=LLM_MODEL,
        openai_api_key=key,
        openai_api_base=SILICONFLOW_BASE_URL,
        temperature=LLM_TEMPERATURE,
        max_tokens=LLM_MAX_TOKENS
    )
    
    return llm


class RAGChain:
    """
    RAG 问答链
    封装检索增强生成的完整流程
    """
    
    def __init__(
        self,
        retriever,
        api_key: Optional[str] = None,
        prompt_template: str = RAG_PROMPT_TEMPLATE
    ):
        """
        初始化 RAG 问答链
        
        Args:
            retriever: LangChain Retriever 对象
            api_key: 可选的 API Key
            prompt_template: 自定义 Prompt 模板
        """
        self.retriever = retriever
        self.api_key = api_key
        self.prompt_template = prompt_template
        self._chain = None
        self._llm = None
    
    @property
    def llm(self) -> ChatOpenAI:
        """懒加载 LLM"""
        if self._llm is None:
            self._llm = get_llm(self.api_key)
        return self._llm
    
    @property
    def chain(self) -> RetrievalQA:
        """懒加载问答链"""
        if self._chain is None:
            self._chain = self._create_chain()
        return self._chain
    
    def _create_chain(self) -> RetrievalQA:
        """创建 RetrievalQA 链"""
        prompt = PromptTemplate(
            template=self.prompt_template,
            input_variables=["context", "question"]
        )
        
        chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",  # 将所有检索结果塞入 context
            retriever=self.retriever,
            return_source_documents=True,  # 返回引用的原文
            chain_type_kwargs={"prompt": prompt}
        )
        
        return chain
    
    def query(self, question: str) -> Dict[str, Any]:
        """
        执行问答
        
        Args:
            question: 用户问题
            
        Returns:
            包含答案和来源文档的字典:
            {
                "answer": str,
                "source_documents": List[Document],
                "sources": List[dict]  # 格式化后的来源信息
            }
        """
        # 执行查询
        result = self.chain.invoke({"query": question})
        
        # 提取答案
        answer = result.get("result", "")
        source_docs = result.get("source_documents", [])
        
        # 格式化来源信息
        sources = self._format_sources(source_docs)
        
        return {
            "answer": answer,
            "source_documents": source_docs,
            "sources": sources
        }
    
    def _format_sources(self, documents: List[Document]) -> List[dict]:
        """
        格式化来源文档信息
        
        Args:
            documents: Document 列表
            
        Returns:
            格式化后的来源信息列表
        """
        sources = []
        for doc in documents:
            source = {
                "content": doc.page_content,
                "page": doc.metadata.get("page", "?"),
                "source_file": doc.metadata.get("source_file", "未知文件"),
                "chunk_index": doc.metadata.get("chunk_index", "?")
            }
            sources.append(source)
        return sources
    
    def query_with_retrieval_info(self, question: str) -> Dict[str, Any]:
        """
        执行问答，并返回详细的检索信息（用于调试和展示）
        
        Args:
            question: 用户问题
            
        Returns:
            包含答案、来源和检索详情的字典
        """
        # 先单独执行检索，获取检索结果
        retrieved_docs = self.retriever.get_relevant_documents(question)
        
        # 执行完整的问答
        result = self.query(question)
        
        # 添加检索信息
        result["retrieved_count"] = len(retrieved_docs)
        
        return result


def create_rag_chain(
    retriever,
    api_key: Optional[str] = None,
    custom_prompt: Optional[str] = None
) -> RAGChain:
    """
    便捷函数：创建 RAG 问答链
    
    Args:
        retriever: LangChain Retriever 对象
        api_key: 可选的 API Key
        custom_prompt: 可选的自定义 Prompt 模板
        
    Returns:
        RAGChain 实例
    """
    prompt = custom_prompt or RAG_PROMPT_TEMPLATE
    return RAGChain(retriever, api_key, prompt)
