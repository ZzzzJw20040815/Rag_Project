"""
实体提取模块 (极速优化版 v2)
优化策略：
1. 合并片段：将多个文本片段合并后一次性发送给 LLM，减少 API 调用次数
2. 并行调用：使用 LangChain batch() 方法并发调用 API
3. 动态采样：针对长文档自动稀疏采样
4. 保持双语输出
"""

import json
import re
import time
from typing import Dict, List, Optional, Any
from collections import Counter
from langchain_openai import ChatOpenAI
from langchain.schema import Document

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from config import (
    SILICONFLOW_BASE_URL,
    LLM_MODEL,
    MAX_KEYWORDS_PER_DOC,
    MAX_METHODS_PER_DOC,
    MAX_DATASETS_PER_DOC,
    get_api_key
)

# 针对合并片段的优化 Prompt
ENTITY_EXTRACTION_PROMPT = """你是一个专业的学术文献分析助手。请从以下文献片段中提取核心实体。

【文本片段】
{text}

【提取要求】
请提取以下 5 类实体。**重要：如果实体是英文，请务必在括号内附上中文翻译**，格式为 `English Term (中文翻译)`。

1. **Keywords** (关键词): 研究的核心主题 (提取 {max_keywords} 个)
2. **Methods** (方法): 算法、模型 (提取 {max_methods} 个)
3. **Fields** (领域): 研究领域 (提取 {max_fields} 个)
4. **Datasets** (数据集): 数据集名称 (提取 {max_datasets} 个)
5. **Applications** (应用): 应用场景 (提取 {max_applications} 个)

【输出格式】
严格返回 JSON 格式：
{{
  "keywords": ["Term A (翻译A)", "Term B (翻译B)"],
  "methods": [],
  "fields": [],
  "datasets": [],
  "applications": []
}}
"""

# ============================================
# 优化配置参数
# ============================================
CHUNKS_PER_BATCH = 4        # 每批合并的片段数量
MAX_CONCURRENT_REQUESTS = 3  # 最大并发请求数（避免触发 RPM 限制）
TARGET_BATCHES = 6          # 目标批次数（原来 25 次调用 -> 6 批并发）


class EntityExtractor:
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        max_keywords: int = MAX_KEYWORDS_PER_DOC,
        max_methods: int = MAX_METHODS_PER_DOC,
        max_datasets: int = MAX_DATASETS_PER_DOC
    ):
        self.api_key = api_key or get_api_key()
        self.max_keywords = max_keywords
        self.max_methods = max_methods
        self.max_datasets = max_datasets
        self.max_fields = 4
        self.max_applications = 4
        self._llm = None
    
    @property
    def llm(self) -> ChatOpenAI:
        if self._llm is None:
            if not self.api_key:
                raise ValueError("请先配置 API Key！")
            self._llm = ChatOpenAI(
                model=LLM_MODEL,
                openai_api_key=self.api_key,
                openai_api_base=SILICONFLOW_BASE_URL,
                temperature=0.3,
                max_tokens=2048
            )
        return self._llm
    
    def _parse_llm_response(self, response: str) -> Dict[str, List[str]]:
        """解析 LLM 返回的 JSON 响应"""
        default_result = {k: [] for k in ["keywords", "methods", "fields", "datasets", "applications"]}
        try:
            cleaned_response = response.replace("```json", "").replace("```", "").strip()
            result = json.loads(cleaned_response)
        except json.JSONDecodeError:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                except:
                    return default_result
            else:
                return default_result
        
        final_result = {}
        for key in default_result.keys():
            items = result.get(key, [])
            if isinstance(items, list):
                final_result[key] = list(set([str(i).strip() for i in items if i]))
            else:
                final_result[key] = []
        return final_result

    def _merge_chunks(self, chunks: List[str], max_chars_per_chunk: int = 1500) -> str:
        """
        合并多个文本片段为一个超级片段
        每个片段截取前 max_chars_per_chunk 个字符，用分隔符连接
        """
        merged_parts = []
        for i, chunk in enumerate(chunks):
            truncated = chunk[:max_chars_per_chunk].strip()
            if truncated:
                merged_parts.append(f"[片段 {i+1}]\n{truncated}")
        return "\n\n---\n\n".join(merged_parts)

    def _select_representative_chunks(self, docs: List[Document]) -> List[List[str]]:
        """
        智能选择代表性片段并分组
        返回：分组后的片段列表，每组 CHUNKS_PER_BATCH 个片段
        """
        total_chunks = len(docs)
        
        # 目标：选取 TARGET_BATCHES * CHUNKS_PER_BATCH 个片段
        target_samples = TARGET_BATCHES * CHUNKS_PER_BATCH  # 6 * 4 = 24 个片段
        
        # 始终包含开头的几个片段（通常包含摘要和介绍）
        selected_indices = [0, 1, 2]
        
        if total_chunks > 3:
            # 动态步长采样
            remaining_samples = target_samples - 3
            step = max(1, (total_chunks - 3) // remaining_samples)
            selected_indices.extend(range(3, total_chunks, step))
        
        # 限制最大采样数
        selected_indices = selected_indices[:target_samples]
        
        # 过滤掉太短的片段，并提取文本
        valid_chunks = []
        for idx in selected_indices:
            if idx < total_chunks:
                text = docs[idx].page_content
                if len(text) >= 100:  # 过滤太短的片段
                    valid_chunks.append(text)
        
        # 分组：每 CHUNKS_PER_BATCH 个片段为一组
        batches = []
        for i in range(0, len(valid_chunks), CHUNKS_PER_BATCH):
            batch = valid_chunks[i:i + CHUNKS_PER_BATCH]
            if batch:
                batches.append(batch)
        
        return batches

    def extract_from_documents(
        self,
        documents: List[Document],
        aggregate_by_file: bool = True
    ) -> Dict[str, Dict[str, List[str]]]:
        """
        从文档列表中提取实体（优化版）
        
        优化策略：
        1. 合并片段：每 4 个片段合并为 1 个超级片段
        2. 并行调用：使用 batch() 并发发送请求
        """
        if not documents:
            return {}
        
        # 按文件分组
        file_docs = {}
        for doc in documents:
            source_file = doc.metadata.get("source_file", "未知文件")
            if source_file not in file_docs:
                file_docs[source_file] = []
            file_docs[source_file].append(doc)
        
        results = {}
        
        for source_file, docs in file_docs.items():
            start_time = time.time()
            total_chunks = len(docs)
            
            # 获取分组后的片段
            chunk_batches = self._select_representative_chunks(docs)
            
            print(f"📄 分析: {source_file}")
            print(f"   📊 总页数: {total_chunks} | 采样片段: {sum(len(b) for b in chunk_batches)} | 合并为 {len(chunk_batches)} 批")
            
            # 构建所有 prompts
            all_prompts = []
            for batch in chunk_batches:
                merged_text = self._merge_chunks(batch)
                prompt = ENTITY_EXTRACTION_PROMPT.format(
                    text=merged_text,
                    max_keywords=8,  # 合并片段后可以多提取一些
                    max_methods=6,
                    max_fields=4,
                    max_datasets=4,
                    max_applications=4
                )
                all_prompts.append(prompt)
            
            # 实体聚合器
            aggregator = {k: Counter() for k in ["keywords", "methods", "fields", "datasets", "applications"]}
            
            # 分批并行调用（每批最多 MAX_CONCURRENT_REQUESTS 个请求）
            for i in range(0, len(all_prompts), MAX_CONCURRENT_REQUESTS):
                batch_prompts = all_prompts[i:i + MAX_CONCURRENT_REQUESTS]
                batch_num = i // MAX_CONCURRENT_REQUESTS + 1
                total_batches = (len(all_prompts) + MAX_CONCURRENT_REQUESTS - 1) // MAX_CONCURRENT_REQUESTS
                
                print(f"   🚀 并行请求批次 {batch_num}/{total_batches} ({len(batch_prompts)} 个请求)...")
                
                try:
                    # 使用 LangChain 的 batch() 方法并发调用
                    responses = self.llm.batch(batch_prompts)
                    
                    for response in responses:
                        chunk_result = self._parse_llm_response(response.content)
                        for key in aggregator:
                            aggregator[key].update(chunk_result.get(key, []))
                            
                except Exception as e:
                    print(f"   ⚠️ 批次 {batch_num} 部分失败: {str(e)[:50]}")
                    # 降级：逐个请求
                    for prompt in batch_prompts:
                        try:
                            response = self.llm.invoke(prompt)
                            chunk_result = self._parse_llm_response(response.content)
                            for key in aggregator:
                                aggregator[key].update(chunk_result.get(key, []))
                        except:
                            pass
            
            # 汇总最终结果
            final_entities = {}
            for key, counter in aggregator.items():
                limit = self.max_keywords * 2 if key == "keywords" else self.max_methods * 2
                most_common = [item for item, count in counter.most_common(limit)]
                final_entities[key] = most_common
            
            elapsed = time.time() - start_time
            results[source_file] = final_entities
            
            # 统计信息
            entity_count = sum(len(v) for v in final_entities.values())
            print(f"   ✅ 完成！耗时 {elapsed:.1f}s | 提取 {entity_count} 个实体")
        
        return results


def create_entity_extractor(api_key: Optional[str] = None) -> EntityExtractor:
    """创建实体提取器实例"""
    return EntityExtractor(api_key=api_key)