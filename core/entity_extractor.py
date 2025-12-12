"""
实体提取模块
使用 LLM 从学术文献中提取关键词、方法和数据集等实体

主要功能：
- 从文档文本中提取核心实体
- 支持批量处理多个文档
- 输出结构化的实体数据
"""

import json
import re
from typing import Dict, List, Optional, Any
from langchain_openai import ChatOpenAI
from langchain.schema import Document

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from config import (
    SILICONFLOW_BASE_URL,
    LLM_MODEL,
    LLM_TEMPERATURE,
    MAX_KEYWORDS_PER_DOC,
    MAX_METHODS_PER_DOC,
    MAX_DATASETS_PER_DOC,
    get_api_key
)


# 实体提取的 Prompt 模板 - 增强版，提取更丰富的实体类型
ENTITY_EXTRACTION_PROMPT = """你是一个学术文献分析专家。请从以下学术文本中全面提取核心实体，构建丰富的知识网络。

【文本内容】
{text}

【提取要求】
请尽可能全面地提取以下类型的实体：

1. **关键词** (Keywords): 提取 {max_keywords} 个核心概念、术语或研究主题
   - 包括：研究对象、核心问题、创新点等
   
2. **方法/技术** (Methods): 提取 {max_methods} 个技术方法
   - 包括：算法、框架、模型、工具、技术手段等
   - 例如：Transformer、BERT、RAG、知识图谱、向量检索等

3. **研究领域** (Fields): 提取 {max_fields} 个相关研究领域
   - 包括：学科方向、研究分支、交叉领域等
   - 例如：自然语言处理、机器学习、信息检索等

4. **数据集** (Datasets): 提取 {max_datasets} 个数据集名称
   - 如果没有明确提到，可以是空数组

5. **应用场景** (Applications): 提取 {max_applications} 个应用场景
   - 包括：实际用途、应用行业、解决的问题等
   - 例如：问答系统、文档检索、智能客服等

【输出格式】
请严格以 JSON 格式输出，不要包含其他任何文字：
{{
  "keywords": ["关键词1", "关键词2", ...],
  "methods": ["方法1", "方法2", ...],
  "fields": ["领域1", "领域2", ...],
  "datasets": ["数据集1", ...],
  "applications": ["应用1", "应用2", ...]
}}

【注意事项】
- 尽量提取具体、有区分度的实体，避免过于宽泛
- 每个类别尽量提取到上限数量，以构建丰富的知识网络
- 确保输出是有效的 JSON 格式"""


class EntityExtractor:
    """
    实体提取器
    从文档中提取关键词、方法和数据集
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        max_keywords: int = MAX_KEYWORDS_PER_DOC,
        max_methods: int = MAX_METHODS_PER_DOC,
        max_datasets: int = MAX_DATASETS_PER_DOC
    ):
        """
        初始化实体提取器
        
        Args:
            api_key: 可选的 API Key
            max_keywords: 每篇文档提取的最大关键词数
            max_methods: 每篇文档提取的最大方法数
            max_datasets: 每篇文档提取的最大数据集数
        """
        self.api_key = api_key or get_api_key()
        self.max_keywords = max_keywords
        self.max_methods = max_methods
        self.max_datasets = max_datasets
        # 新增实体类型的数量配置
        self.max_fields = 4  # 研究领域
        self.max_applications = 3  # 应用场景
        self._llm = None
    
    @property
    def llm(self) -> ChatOpenAI:
        """懒加载 LLM"""
        if self._llm is None:
            if not self.api_key:
                raise ValueError("请先配置 API Key！")
            
            self._llm = ChatOpenAI(
                model=LLM_MODEL,
                openai_api_key=self.api_key,
                openai_api_base=SILICONFLOW_BASE_URL,
                temperature=0.3,  # 实体提取使用较低的温度保证一致性
                max_tokens=1024
            )
        return self._llm
    
    def _parse_llm_response(self, response: str) -> Dict[str, List[str]]:
        """
        解析 LLM 返回的 JSON 响应
        
        Args:
            response: LLM 响应文本
            
        Returns:
            解析后的实体字典
        """
        # 默认返回结构
        default_result = {
            "keywords": [],
            "methods": [],
            "datasets": []
        }
        
        try:
            # 尝试直接解析 JSON
            result = json.loads(response)
        except json.JSONDecodeError:
            # 如果解析失败，尝试提取 JSON 部分
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                except json.JSONDecodeError:
                    print(f"⚠️ JSON 解析失败: {response[:100]}...")
                    return default_result
            else:
                print(f"⚠️ 未找到有效 JSON: {response[:100]}...")
                return default_result
        
        # 验证并清理结果 - 支持更多实体类型
        cleaned = {}
        for key in ["keywords", "methods", "fields", "datasets", "applications"]:
            if key in result and isinstance(result[key], list):
                # 过滤空字符串和非字符串元素
                cleaned[key] = [
                    str(item).strip() 
                    for item in result[key] 
                    if item and str(item).strip()
                ]
            else:
                cleaned[key] = []
        
        return cleaned
    
    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """
        从单段文本中提取实体
        
        Args:
            text: 输入文本（通常是论文摘要或首页内容）
            
        Returns:
            包含 keywords, methods, datasets 的字典
        """
        if not text or len(text.strip()) < 50:
            return {"keywords": [], "methods": [], "datasets": []}
        
        # 截取合适长度的文本（避免超长输入）
        max_text_length = 3000
        if len(text) > max_text_length:
            text = text[:max_text_length] + "..."
        
        # 构建 prompt
        prompt = ENTITY_EXTRACTION_PROMPT.format(
            text=text,
            max_keywords=self.max_keywords,
            max_methods=self.max_methods,
            max_fields=self.max_fields,
            max_datasets=self.max_datasets,
            max_applications=self.max_applications
        )
        
        try:
            # 调用 LLM
            response = self.llm.invoke(prompt)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # 解析响应
            entities = self._parse_llm_response(response_text)
            return entities
            
        except Exception as e:
            print(f"❌ 实体提取失败: {e}")
            return {"keywords": [], "methods": [], "datasets": []}
    
    def extract_from_document(self, document: Document) -> Dict[str, Any]:
        """
        从单个 LangChain Document 中提取实体
        
        Args:
            document: LangChain Document 对象
            
        Returns:
            包含文档元信息和提取实体的字典
        """
        # 获取文档来源信息
        source_file = document.metadata.get("source_file", "未知文件")
        page = document.metadata.get("page", 0)
        
        # 提取实体
        entities = self.extract_entities(document.page_content)
        
        return {
            "source_file": source_file,
            "page": page,
            "entities": entities
        }
    
    def extract_from_documents(
        self,
        documents: List[Document],
        aggregate_by_file: bool = True
    ) -> Dict[str, Dict[str, List[str]]]:
        """
        从多个文档中批量提取实体
        
        Args:
            documents: Document 列表
            aggregate_by_file: 是否按文件聚合实体
            
        Returns:
            以文件名为 key，实体字典为 value 的字典
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
            print(f"📄 正在提取: {source_file}")
            
            if aggregate_by_file:
                # 合并同一文件的前几页内容进行提取
                combined_text = "\n\n".join([
                    doc.page_content for doc in docs[:3]  # 只取前3个chunk
                ])
                entities = self.extract_entities(combined_text)
            else:
                # 分别提取每个chunk，然后去重合并
                all_keywords = set()
                all_methods = set()
                all_datasets = set()
                
                for doc in docs[:5]:  # 限制处理的chunk数量
                    result = self.extract_entities(doc.page_content)
                    all_keywords.update(result.get("keywords", []))
                    all_methods.update(result.get("methods", []))
                    all_datasets.update(result.get("datasets", []))
                
                entities = {
                    "keywords": list(all_keywords)[:self.max_keywords],
                    "methods": list(all_methods)[:self.max_methods],
                    "datasets": list(all_datasets)[:self.max_datasets]
                }
            
            results[source_file] = entities
            print(f"  ✅ 关键词: {entities['keywords']}")
            print(f"  ✅ 方法: {entities['methods']}")
            print(f"  ✅ 数据集: {entities['datasets']}")
        
        return results


def create_entity_extractor(api_key: Optional[str] = None) -> EntityExtractor:
    """
    便捷函数：创建实体提取器
    
    Args:
        api_key: 可选的 API Key
        
    Returns:
        EntityExtractor 实例
    """
    return EntityExtractor(api_key=api_key)
