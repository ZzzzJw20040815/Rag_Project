"""
文档处理模块
负责 PDF/Word 文档的解析和文本切分
"""

import os
import re
import tempfile
from pathlib import Path
from typing import List, Optional, BinaryIO

from langchain.schema import Document
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import CHUNK_SIZE, CHUNK_OVERLAP, UPLOADS_DIR


class DocumentProcessor:
    """文档处理器：解析和切分文档"""
    
    def __init__(
        self,
        chunk_size: int = CHUNK_SIZE,
        chunk_overlap: int = CHUNK_OVERLAP
    ):
        """
        初始化文档处理器
        
        Args:
            chunk_size: 每个文本块的最大字符数
            chunk_overlap: 文本块之间的重叠字符数
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # 初始化文本切分器
        # 使用多种分隔符递归切分，优先保持段落和句子完整性
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=[
                "\n\n",  # 段落分隔
                "\n",    # 换行
                "。",    # 中文句号
                "！",    # 中文感叹号
                "？",    # 中文问号
                ".",     # 英文句号
                "!",     # 英文感叹号
                "?",     # 英文问号
                ";",     # 分号
                "；",    # 中文分号
                " ",     # 空格
                ""       # 字符级别（最后手段）
            ]
        )
    
    def load_pdf(self, file_path: str) -> List[Document]:
        """
        加载 PDF 文件
        
        Args:
            file_path: PDF 文件路径
            
        Returns:
            Document 列表，每页一个 Document
        """
        loader = PyPDFLoader(file_path)
        documents = loader.load()
        
        # 为每个文档添加文件名元数据
        file_name = Path(file_path).name
        for doc in documents:
            doc.metadata["source_file"] = file_name
            # 页码从 1 开始（原始是从 0 开始）
            if "page" in doc.metadata:
                doc.metadata["page"] = doc.metadata["page"] + 1
        
        return documents
    
    def load_pdf_from_upload(self, uploaded_file: BinaryIO, filename: str) -> List[Document]:
        """
        从上传的文件对象加载 PDF
        
        Args:
            uploaded_file: Streamlit 上传的文件对象
            filename: 原始文件名
            
        Returns:
            Document 列表
        """
        # 创建临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name
        
        try:
            documents = self.load_pdf(tmp_path)
            # 更新 source_file 为原始文件名
            for doc in documents:
                doc.metadata["source_file"] = filename
            return documents
        finally:
            # 删除临时文件
            os.unlink(tmp_path)
    
    def load_word(self, file_path: str) -> List[Document]:
        """
        加载 Word 文档 (.docx)
        
        Args:
            file_path: Word 文件路径
            
        Returns:
            Document 列表
        """
        try:
            from docx import Document as DocxDocument
        except ImportError:
            raise ImportError("请安装 python-docx: pip install python-docx")
        
        docx_doc = DocxDocument(file_path)
        file_name = Path(file_path).name
        
        # 提取所有段落文本
        full_text = []
        for para in docx_doc.paragraphs:
            if para.text.strip():
                full_text.append(para.text)
        
        # 创建一个 Document 对象
        content = "\n\n".join(full_text)
        document = Document(
            page_content=content,
            metadata={
                "source_file": file_name,
                "page": 1  # Word 文档不分页，统一设为 1
            }
        )
        
        return [document]
    
    def load_word_from_upload(self, uploaded_file: BinaryIO, filename: str) -> List[Document]:
        """
        从上传的文件对象加载 Word 文档
        
        Args:
            uploaded_file: Streamlit 上传的文件对象
            filename: 原始文件名
            
        Returns:
            Document 列表
        """
        suffix = ".docx" if filename.endswith(".docx") else ".doc"
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name
        
        try:
            documents = self.load_word(tmp_path)
            for doc in documents:
                doc.metadata["source_file"] = filename
            return documents
        finally:
            os.unlink(tmp_path)
    
    def clean_text(self, text: str) -> str:
        """
        清洗文本：移除参考文献、致谢、页眉页脚等噪音
        """
        # 移除常见的页眉页脚模式
        text = re.sub(r'第\s*\d+\s*页', '', text)
        text = re.sub(r'(?i)page\s*\d+\s*(of\s*\d+)?', '', text)
        
        # 移除多余的空白行
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()

    def remove_references_section(self, documents: List[Document]) -> List[Document]:
        """
        【新增方法】宏观截断：
        识别文档尾部的 'References' 或 'Bibliography' 标题，
        并丢弃该页面之后的所有内容。
        """
        cutoff_index = -1
        
        # 倒序检查最后几页（通常参考文献在最后）
        # 限制检查范围在最后 40% 的页面，防止误删目录中的 References
        check_start_idx = max(0, int(len(documents) * 0.6))
        
        for i in range(len(documents) - 1, check_start_idx - 1, -1):
            content = documents[i].page_content
            # 检查页面是否以 References 开头（允许少量干扰字符）
            # 许多论文 References 是独立的大标题
            lines = content.split('\n')
            for line in lines[:8]: # 检查前几行
                clean_line = line.strip().lower()
                
                # 匹配纯文本标题
                if clean_line in ['references', 'bibliography', 'reference']:
                    cutoff_index = i
                    break
                    
                # 匹配带编号的标题 (如 "6. References", "V. References")
                if re.match(r'^(\d+|[ivx]+)\.?\s*references$', clean_line):
                    cutoff_index = i
                    break
            
            if cutoff_index != -1:
                break
        
        # 如果找到了参考文献页，截断该页及其之后的所有页面
        if cutoff_index != -1:
            print(f"[DocumentProcessor] 检测到参考文献起始于第 {cutoff_index + 1} 页，已截断后续内容。")
            # 保留到 cutoff_index 之前，或者包含该页的一小部分（通常直接丢弃该页最安全）
            return documents[:cutoff_index]
            
        return documents
    
    def is_reference_chunk(self, text: str) -> bool:
        """
        【修改方法】微观过滤：
        判断一个文本块是否主要是参考文献内容
        """
        # 引用标记模式：[1], [23]
        citation_pattern = r'\[\d+(?:,\s*\d+)*\]'
        citations = re.findall(citation_pattern, text)
        
        # arXiv 引用模式
        arxiv_refs = re.findall(r'arXiv', text, re.IGNORECASE)
        
        # 年份模式 (如 2023, 2021) - 参考文献中年份密度很高
        year_pattern = r'\b(19|20)\d{2}\b'
        years = re.findall(year_pattern, text)
        
        # 关键会议/期刊名称 (增加更多关键词)
        venue_keywords = [
            'IEEE', 'ACM', 'CVPR', 'ICCV', 'ECCV', 'NeurIPS', 'ICML', 'ICLR',
            'AAAI', 'IJCAI', 'preprint', 'Proceedings', 'Conference', 'Journal',
            'Transactions', 'vol.', 'pp.', 'eds.', 'Research', 'Review'
        ]
        venue_count = sum(1 for kw in venue_keywords if kw.lower() in text.lower())
        
        text_length = len(text)
        if text_length < 50: return False # 太短的不处理

        # --- 增强后的判断逻辑 ---
        
        # 1. 组合特征：只要包含大量年份和会议名，即便没有 [1] 也是参考文献
        if len(years) >= 3 and venue_count >= 2:
            return True
            
        # 2. 降低引用计数阈值 (从 5 降到 3)
        if len(citations) >= 3:
            return True
            
        # 3. 极高密度的 arXiv 引用
        if len(arxiv_refs) >= 2:
            return True
            
        # 4. 传统的密度判断 (放宽阈值)
        # 计算密度：(引用数 + 年份数/2 + arXiv数) / (文本长度/100)
        # 这里把年份也算作半个引用特征
        density_score = (len(citations) + len(arxiv_refs) + len(years) * 0.5) / (text_length / 100)
        
        if density_score > 1.0: # 只要每100字有超过1个引用特征，就认为是引用
            return True
            
        return False
    
    def split_documents(
        self,
        documents: List[Document],
        clean: bool = True
    ) -> List[Document]:
        """
        切分文档为小块
        
        Args:
            documents: 原始 Document 列表
            clean: 是否先清洗文本
            
        Returns:
            切分后的 Document 列表（chunks）
        """
        if clean:
            # 1. 【宏观截断】先尝试去掉整个参考文献章节
            documents = self.remove_references_section(documents)
            
            # 2. 清洗每个文档的文本
            for doc in documents:
                doc.page_content = self.clean_text(doc.page_content)
        
        # 使用 text_splitter 切分
        chunks = self.text_splitter.split_documents(documents)
        
        # 3. 【微观过滤】过滤掉残留的参考文献内容的 chunks
        filtered_chunks = []
        removed_count = 0
        for chunk in chunks:
            if clean and self.is_reference_chunk(chunk.page_content):
                removed_count += 1
                continue  # 跳过参考文献块
            filtered_chunks.append(chunk)
        
        if removed_count > 0:
            print(f"[DocumentProcessor] 已过滤 {removed_count} 个参考文献块")
        
        # 为每个 chunk 添加索引
        for i, chunk in enumerate(filtered_chunks):
            chunk.metadata["chunk_index"] = i
        
        return filtered_chunks
    
    def process_uploaded_file(
        self,
        uploaded_file: BinaryIO,
        filename: str,
        clean: bool = True
    ) -> List[Document]:
        """
        处理上传的文件：加载 + 切分
        
        Args:
            uploaded_file: 上传的文件对象
            filename: 文件名
            clean: 是否清洗文本
            
        Returns:
            切分后的 Document 列表
        """
        # 根据文件类型选择加载方法
        if filename.lower().endswith(".pdf"):
            documents = self.load_pdf_from_upload(uploaded_file, filename)
        elif filename.lower().endswith((".docx", ".doc")):
            documents = self.load_word_from_upload(uploaded_file, filename)
        else:
            raise ValueError(f"不支持的文件类型: {filename}")
        
        # 切分文档
        chunks = self.split_documents(documents, clean=clean)
        
        return chunks