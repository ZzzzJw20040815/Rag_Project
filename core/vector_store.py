"""
向量存储模块
封装 ChromaDB 的操作，提供文档存储和检索功能
"""

import os
from typing import List, Optional
from pathlib import Path

from langchain.schema import Document
from langchain_community.vectorstores import Chroma

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import CHROMA_DB_DIR, RETRIEVAL_K
from .embeddings import get_embedding_model


class VectorStoreManager:
    """
    向量存储管理器
    负责 ChromaDB 的创建、持久化和检索操作
    """
    
    def __init__(
        self,
        collection_name: str = "academic_docs",
        persist_directory: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        """
        初始化向量存储管理器
        
        Args:
            collection_name: ChromaDB 集合名称
            persist_directory: 持久化目录，默认使用配置中的路径
            api_key: 可选的 API Key
        """
        self.collection_name = collection_name
        self.persist_directory = persist_directory or str(CHROMA_DB_DIR)
        self.api_key = api_key
        self._vector_store = None
        self._embeddings = None
    
    @property
    def embeddings(self):
        """懒加载 Embedding 模型"""
        if self._embeddings is None:
            self._embeddings = get_embedding_model(self.api_key)
        return self._embeddings
    
    def create_from_documents(
        self,
        documents: List[Document],
        persist: bool = True
    ) -> Chroma:
        """
        从文档列表创建向量存储
        
        Args:
            documents: Document 列表（通常是切分后的 chunks）
            persist: 是否持久化到磁盘
            
        Returns:
            Chroma 向量存储实例
        """
        import chromadb
        import gc
        
        # ★★★ 重要修复：先清除旧数据，防止新旧文档混合 ★★★
        if persist:
            # 释放旧的引用
            self._vector_store = None
            self._embeddings = None
            gc.collect()
            
            # 使用 ChromaDB 原生 API 删除旧集合
            if os.path.exists(self.persist_directory):
                try:
                    client = chromadb.PersistentClient(path=self.persist_directory)
                    existing_collections = [c.name for c in client.list_collections()]
                    if self.collection_name in existing_collections:
                        client.delete_collection(self.collection_name)
                        print(f"[VectorStore] 创建前已清除旧集合: {self.collection_name}")
                    del client
                    gc.collect()
                except Exception as e:
                    print(f"[VectorStore] 清除旧集合失败: {e}")
        
        # 创建 Chroma 向量存储
        # persist_directory 参数会自动持久化
        self._vector_store = Chroma.from_documents(
            documents=documents,
            embedding=self.embeddings,
            collection_name=self.collection_name,
            persist_directory=self.persist_directory if persist else None
        )
        
        return self._vector_store
    
    def load_existing(self) -> Optional[Chroma]:
        """
        加载已存在的向量存储
        
        Returns:
            Chroma 实例，如果不存在则返回 None
        """
        # 检查持久化目录是否存在且非空
        if not os.path.exists(self.persist_directory):
            return None
        
        if not os.listdir(self.persist_directory):
            return None
        
        try:
            self._vector_store = Chroma(
                collection_name=self.collection_name,
                embedding_function=self.embeddings,
                persist_directory=self.persist_directory
            )
            return self._vector_store
        except Exception:
            return None
    
    def add_documents(self, documents: List[Document]):
        """
        向已有的向量存储添加文档
        
        Args:
            documents: 要添加的 Document 列表
        """
        if self._vector_store is None:
            # 如果还没有向量存储，先尝试加载或创建
            self._vector_store = self.load_existing()
            if self._vector_store is None:
                self._vector_store = self.create_from_documents(documents)
                return
        
        # 添加到现有存储
        self._vector_store.add_documents(documents)
    
    def similarity_search(
        self,
        query: str,
        k: int = RETRIEVAL_K
    ) -> List[Document]:
        """
        相似度搜索
        
        Args:
            query: 查询文本
            k: 返回的文档数量
            
        Returns:
            最相似的 Document 列表
        """
        if self._vector_store is None:
            raise ValueError("向量存储未初始化，请先添加文档")
        
        return self._vector_store.similarity_search(query, k=k)
    
    def similarity_search_with_score(
        self,
        query: str,
        k: int = RETRIEVAL_K
    ) -> List[tuple]:
        """
        带相似度分数的搜索
        
        Args:
            query: 查询文本
            k: 返回的文档数量
            
        Returns:
            (Document, score) 元组列表
        """
        if self._vector_store is None:
            raise ValueError("向量存储未初始化，请先添加文档")
        
        return self._vector_store.similarity_search_with_score(query, k=k)
    
    def as_retriever(self, **kwargs):
        """
        获取检索器对象，用于 LangChain 链
        
        Args:
            **kwargs: 传递给 as_retriever 的参数
            
        Returns:
            Retriever 对象
        """
        if self._vector_store is None:
            raise ValueError("向量存储未初始化，请先添加文档")
        
        # 默认参数
        default_kwargs = {
            "search_type": "similarity",
            "search_kwargs": {"k": RETRIEVAL_K}
        }
        default_kwargs.update(kwargs)
        
        return self._vector_store.as_retriever(**default_kwargs)
    
    def clear(self):
        """清空向量存储"""
        import gc
        import time
        import shutil
        import chromadb
        
        # 方法1：尝试使用 ChromaDB 原生 API 删除集合
        try:
            if self._vector_store is not None:
                # 获取底层 Chroma 客户端并删除集合
                client = chromadb.PersistentClient(path=self.persist_directory)
                try:
                    client.delete_collection(self.collection_name)
                    print(f"[VectorStore] 已删除集合: {self.collection_name}")
                except Exception as e:
                    print(f"[VectorStore] 删除集合失败: {e}")
                
                # 释放客户端连接
                del client
        except Exception as e:
            print(f"[VectorStore] ChromaDB API 清理失败: {e}")
        
        # 释放 Python 引用
        self._vector_store = None
        self._embeddings = None
        
        # 强制垃圾回收
        gc.collect()
        time.sleep(0.5)
        
        # 方法2：如果 API 删除失败，尝试删除文件
        if os.path.exists(self.persist_directory):
            try:
                shutil.rmtree(self.persist_directory)
                print(f"[VectorStore] 已删除目录: {self.persist_directory}")
            except PermissionError:
                # Windows 文件锁定，尝试逐个删除
                print("[VectorStore] 目录被锁定，尝试清空文件...")
                try:
                    for root, dirs, files in os.walk(self.persist_directory, topdown=False):
                        for name in files:
                            try:
                                os.remove(os.path.join(root, name))
                            except:
                                pass
                        for name in dirs:
                            try:
                                os.rmdir(os.path.join(root, name))
                            except:
                                pass
                except Exception as e:
                    print(f"[VectorStore] 清理失败: {e}")
            except Exception as e:
                print(f"[VectorStore] 删除目录失败: {e}")
        
        # 重建目录
        os.makedirs(self.persist_directory, exist_ok=True)
    
    def get_document_count(self) -> int:
        """获取存储的文档数量"""
        if self._vector_store is None:
            return 0
        try:
            return self._vector_store._collection.count()
        except Exception:
            return 0
