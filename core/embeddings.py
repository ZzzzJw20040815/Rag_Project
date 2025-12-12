"""
Embedding 服务模块
封装 SiliconFlow API 的 Embedding 调用

使用的模型: BAAI/bge-m3 (中英文双语兼容)
配置位置: config.py -> EMBEDDING_MODEL
"""

import time
from typing import Optional, List
from langchain_openai import OpenAIEmbeddings
from langchain.embeddings.base import Embeddings

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from config import (
    SILICONFLOW_API_KEY,
    SILICONFLOW_BASE_URL,
    EMBEDDING_MODEL,  # = "BAAI/bge-m3"
    get_api_key
)


class RateLimitedEmbeddings(Embeddings):
    """
    带轻量级速率保护的 Embedding 封装类
    已完成实名认证的账号可以使用较快的设置
    """
    
    def __init__(
        self,
        api_key: str,
        model: str = EMBEDDING_MODEL,
        base_url: str = SILICONFLOW_BASE_URL,
        batch_size: int = 20,  # 每批处理的文档数（认证后可以调大）
        delay_between_batches: float = 0.2,  # 批次之间的延迟（秒），认证后可以很小
        max_retries: int = 3,  # 保留重试机制以防万一
        retry_delay: float = 3.0  # 重试延迟（秒）
    ):
        """
        初始化 Embedding
        
        Args:
            api_key: API Key
            model: Embedding 模型名称 (默认 BAAI/bge-m3)
            base_url: API 基础 URL
            batch_size: 每批处理的文档数量
            delay_between_batches: 批次之间的延迟秒数
            max_retries: 遇到错误时的最大重试次数
            retry_delay: 重试前的等待秒数
        """
        self.batch_size = batch_size
        self.delay_between_batches = delay_between_batches
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.model_name = model  # 保存模型名称便于查看
        
        # 创建底层的 OpenAI Embeddings
        self._embeddings = OpenAIEmbeddings(
            model=model,
            openai_api_key=api_key,
            openai_api_base=base_url,
            check_embedding_ctx_length=False
        )
    
    def _call_with_retry(self, func, *args, **kwargs):
        """带重试的 API 调用（保留以防网络抖动）"""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_str = str(e)
                last_error = e
                
                # 遇到可重试的错误时等待后重试
                if "RPM limit" in error_str or "rate limit" in error_str.lower() or "403" in error_str or "timeout" in error_str.lower():
                    wait_time = self.retry_delay * (attempt + 1)
                    print(f"⚠️ 遇到错误，等待 {wait_time}s 后重试 ({attempt + 1}/{self.max_retries})...")
                    time.sleep(wait_time)
                else:
                    raise e
        
        raise last_error
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        批量嵌入文档
        
        Args:
            texts: 文本列表
            
        Returns:
            嵌入向量列表
        """
        all_embeddings = []
        total_batches = (len(texts) + self.batch_size - 1) // self.batch_size
        
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            batch_num = i // self.batch_size + 1
            
            batch_embeddings = self._call_with_retry(
                self._embeddings.embed_documents,
                batch
            )
            all_embeddings.extend(batch_embeddings)
            
            # 批次之间添加短暂延迟（最后一批不需要）
            if i + self.batch_size < len(texts) and self.delay_between_batches > 0:
                time.sleep(self.delay_between_batches)
        
        return all_embeddings
    
    def embed_query(self, text: str) -> List[float]:
        """嵌入单个查询"""
        return self._call_with_retry(self._embeddings.embed_query, text)


def get_embedding_model(api_key: Optional[str] = None) -> Embeddings:
    """
    获取 Embedding 模型实例
    
    模型: BAAI/bge-m3 (在 config.py 中配置)
    - 1024 维向量
    - 中英文双语兼容
    - 适合学术文献检索
    
    Args:
        api_key: 可选的 API Key，如果不提供则从配置中读取
        
    Returns:
        Embeddings 实例
    """
    key = api_key or get_api_key()
    
    if not key:
        raise ValueError(
            "请先配置 API Key！\n"
            "可以在侧边栏输入，或在 .env 文件中设置 DEEPSEEK_API_KEY"
        )
    
    # 已完成实名认证，使用较快的设置
    return RateLimitedEmbeddings(
        api_key=key,
        model=EMBEDDING_MODEL,  # BAAI/bge-m3
        base_url=SILICONFLOW_BASE_URL,
        batch_size=20,  # 大批量处理
        delay_between_batches=0.1,  # 很短的延迟
        max_retries=3,  # 保留重试
        retry_delay=3.0
    )


class EmbeddingService:
    """Embedding 服务类，提供更灵活的 Embedding 功能"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or get_api_key()
        self._model = None
    
    @property
    def model(self) -> Embeddings:
        """懒加载 Embedding 模型"""
        if self._model is None:
            self._model = get_embedding_model(self.api_key)
        return self._model
    
    def embed_query(self, text: str) -> list:
        """对单个查询文本进行向量化"""
        return self.model.embed_query(text)
    
    def embed_documents(self, texts: list) -> list:
        """对多个文档文本进行向量化"""
        return self.model.embed_documents(texts)
