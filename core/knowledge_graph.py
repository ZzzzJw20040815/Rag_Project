"""
知识图谱构建模块
使用 NetworkX 构建文档-实体共现网络

主要功能：
- 构建文档与实体的关联图
- 支持多种实体类型（关键词、方法、数据集）
- 图谱持久化与加载
"""

import json
import os
from typing import Dict, List, Optional, Set, Tuple, Any
from pathlib import Path
import networkx as nx

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import GRAPHS_DIR


# 节点类型常量
NODE_TYPE_DOCUMENT = "document"
NODE_TYPE_KEYWORD = "keyword"
NODE_TYPE_METHOD = "method"
NODE_TYPE_DATASET = "dataset"
NODE_TYPE_FIELD = "field"  # 研究领域
NODE_TYPE_APPLICATION = "application"  # 应用场景

# 边类型常量
EDGE_CONTAINS_KEYWORD = "CONTAINS_KEYWORD"
EDGE_USES_METHOD = "USES_METHOD"
EDGE_USES_DATASET = "USES_DATASET"
EDGE_BELONGS_TO_FIELD = "BELONGS_TO_FIELD"
EDGE_HAS_APPLICATION = "HAS_APPLICATION"


class KnowledgeGraph:
    """
    知识图谱类
    封装 NetworkX 图操作，构建文档-实体共现网络
    """
    
    def __init__(self):
        """初始化知识图谱"""
        # 使用无向图
        self.graph = nx.Graph()
        
        # 存储文档及其实体的映射
        self._document_entities: Dict[str, Dict[str, List[str]]] = {}
        
        # 实体统计 - 支持更多实体类型
        self._entity_counts: Dict[str, Dict[str, int]] = {
            "keywords": {},
            "methods": {},
            "datasets": {},
            "fields": {},
            "applications": {}
        }
    
    def add_document(
        self,
        doc_name: str,
        entities: Dict[str, List[str]]
    ) -> None:
        """
        添加文档及其实体到图谱
        
        Args:
            doc_name: 文档名称
            entities: 实体字典，包含 keywords, methods, datasets
        """
        # 清理文档名（移除路径，只保留文件名）
        doc_name = Path(doc_name).stem if "/" in doc_name or "\\" in doc_name else doc_name
        
        # 存储文档实体映射
        self._document_entities[doc_name] = entities
        
        # 添加文档节点
        self.graph.add_node(
            doc_name,
            node_type=NODE_TYPE_DOCUMENT,
            label=doc_name,
            title=f"📄 {doc_name}"
        )
        
        # 添加关键词节点和边
        for keyword in entities.get("keywords", []):
            self._add_entity_node(keyword, NODE_TYPE_KEYWORD)
            self.graph.add_edge(
                doc_name, keyword,
                edge_type=EDGE_CONTAINS_KEYWORD,
                weight=1.0
            )
            self._entity_counts["keywords"][keyword] = \
                self._entity_counts["keywords"].get(keyword, 0) + 1
        
        # 添加方法节点和边
        for method in entities.get("methods", []):
            self._add_entity_node(method, NODE_TYPE_METHOD)
            self.graph.add_edge(
                doc_name, method,
                edge_type=EDGE_USES_METHOD,
                weight=1.5  # 方法关联权重更高
            )
            self._entity_counts["methods"][method] = \
                self._entity_counts["methods"].get(method, 0) + 1
        
        # 添加数据集节点和边
        for dataset in entities.get("datasets", []):
            self._add_entity_node(dataset, NODE_TYPE_DATASET)
            self.graph.add_edge(
                doc_name, dataset,
                edge_type=EDGE_USES_DATASET,
                weight=1.2
            )
            self._entity_counts["datasets"][dataset] = \
                self._entity_counts["datasets"].get(dataset, 0) + 1
        
        # 添加研究领域节点和边
        for field in entities.get("fields", []):
            self._add_entity_node(field, NODE_TYPE_FIELD)
            self.graph.add_edge(
                doc_name, field,
                edge_type=EDGE_BELONGS_TO_FIELD,
                weight=1.3
            )
            self._entity_counts["fields"][field] = \
                self._entity_counts["fields"].get(field, 0) + 1
        
        # 添加应用场景节点和边
        for app in entities.get("applications", []):
            self._add_entity_node(app, NODE_TYPE_APPLICATION)
            self.graph.add_edge(
                doc_name, app,
                edge_type=EDGE_HAS_APPLICATION,
                weight=1.1
            )
            self._entity_counts["applications"][app] = \
                self._entity_counts["applications"].get(app, 0) + 1
    
    def _add_entity_node(self, entity_name: str, entity_type: str) -> None:
        """
        添加实体节点（如果不存在）
        
        Args:
            entity_name: 实体名称
            entity_type: 实体类型
        """
        if entity_name not in self.graph:
            # 根据类型设置不同的标签图标
            icon_map = {
                NODE_TYPE_KEYWORD: "🏷️",
                NODE_TYPE_METHOD: "⚙️",
                NODE_TYPE_DATASET: "📊",
                NODE_TYPE_FIELD: "📖",
                NODE_TYPE_APPLICATION: "💻"
            }
            icon = icon_map.get(entity_type, "")
            
            self.graph.add_node(
                entity_name,
                node_type=entity_type,
                label=entity_name,
                title=f"{icon} {entity_name}"
            )
    
    def build_from_extraction_results(
        self,
        extraction_results: Dict[str, Dict[str, List[str]]]
    ) -> None:
        """
        从实体提取结果批量构建图谱
        
        Args:
            extraction_results: EntityExtractor.extract_from_documents 的输出
        """
        for doc_name, entities in extraction_results.items():
            self.add_document(doc_name, entities)
    
    def get_document_nodes(self) -> List[str]:
        """获取所有文档节点"""
        return [
            node for node, data in self.graph.nodes(data=True)
            if data.get("node_type") == NODE_TYPE_DOCUMENT
        ]
    
    def get_entity_nodes(self, entity_type: Optional[str] = None) -> List[str]:
        """
        获取实体节点
        
        Args:
            entity_type: 可选，指定实体类型过滤
            
        Returns:
            实体节点列表
        """
        if entity_type:
            return [
                node for node, data in self.graph.nodes(data=True)
                if data.get("node_type") == entity_type
            ]
        else:
            return [
                node for node, data in self.graph.nodes(data=True)
                if data.get("node_type") != NODE_TYPE_DOCUMENT
            ]
    
    def get_shared_entities(self, doc1: str, doc2: str) -> List[str]:
        """
        获取两篇文档的共同实体
        
        Args:
            doc1: 第一篇文档名
            doc2: 第二篇文档名
            
        Returns:
            共同实体列表
        """
        neighbors1 = set(self.graph.neighbors(doc1)) if doc1 in self.graph else set()
        neighbors2 = set(self.graph.neighbors(doc2)) if doc2 in self.graph else set()
        return list(neighbors1 & neighbors2)
    
    def get_related_documents(self, doc_name: str) -> List[Tuple[str, List[str]]]:
        """
        获取与指定文档相关的其他文档及共享实体
        
        Args:
            doc_name: 文档名
            
        Returns:
            [(相关文档名, [共享实体])] 列表，按共享实体数量排序
        """
        if doc_name not in self.graph:
            return []
        
        # 获取该文档的所有实体邻居
        entities = set(self.graph.neighbors(doc_name))
        
        # 查找共享这些实体的其他文档
        related = {}
        for entity in entities:
            for neighbor in self.graph.neighbors(entity):
                if neighbor != doc_name and \
                   self.graph.nodes[neighbor].get("node_type") == NODE_TYPE_DOCUMENT:
                    if neighbor not in related:
                        related[neighbor] = []
                    related[neighbor].append(entity)
        
        # 按共享实体数量排序
        sorted_related = sorted(
            related.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )
        
        return sorted_related
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取图谱统计信息
        
        Returns:
            统计信息字典
        """
        doc_nodes = self.get_document_nodes()
        keyword_nodes = self.get_entity_nodes(NODE_TYPE_KEYWORD)
        method_nodes = self.get_entity_nodes(NODE_TYPE_METHOD)
        dataset_nodes = self.get_entity_nodes(NODE_TYPE_DATASET)
        field_nodes = self.get_entity_nodes(NODE_TYPE_FIELD)
        application_nodes = self.get_entity_nodes(NODE_TYPE_APPLICATION)
        
        # 获取最常见的实体
        top_keywords = sorted(
            self._entity_counts["keywords"].items(),
            key=lambda x: x[1], reverse=True
        )[:5]
        top_methods = sorted(
            self._entity_counts["methods"].items(),
            key=lambda x: x[1], reverse=True
        )[:5]
        top_fields = sorted(
            self._entity_counts["fields"].items(),
            key=lambda x: x[1], reverse=True
        )[:3]
        
        return {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "document_count": len(doc_nodes),
            "keyword_count": len(keyword_nodes),
            "method_count": len(method_nodes),
            "dataset_count": len(dataset_nodes),
            "field_count": len(field_nodes),
            "application_count": len(application_nodes),
            "top_keywords": top_keywords,
            "top_methods": top_methods,
            "top_fields": top_fields,
            "documents": doc_nodes
        }
    
    def save(self, filepath: Optional[str] = None) -> str:
        """
        将图谱保存为 JSON 文件
        
        Args:
            filepath: 保存路径，默认保存到 data/graphs/
            
        Returns:
            保存的文件路径
        """
        if filepath is None:
            filepath = str(GRAPHS_DIR / "knowledge_graph.json")
        
        # 构建可序列化的数据结构
        data = {
            "nodes": [
                {
                    "id": node,
                    **attrs
                }
                for node, attrs in self.graph.nodes(data=True)
            ],
            "edges": [
                {
                    "source": u,
                    "target": v,
                    **attrs
                }
                for u, v, attrs in self.graph.edges(data=True)
            ],
            "document_entities": self._document_entities,
            "entity_counts": self._entity_counts
        }
        
        # 确保目录存在
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 图谱已保存到: {filepath}")
        return filepath
    
    def load(self, filepath: Optional[str] = None) -> bool:
        """
        从 JSON 文件加载图谱
        
        Args:
            filepath: 文件路径
            
        Returns:
            是否加载成功
        """
        if filepath is None:
            filepath = str(GRAPHS_DIR / "knowledge_graph.json")
        
        if not os.path.exists(filepath):
            print(f"⚠️ 图谱文件不存在: {filepath}")
            return False
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # 重建图
            self.graph = nx.Graph()
            
            # 添加节点
            for node_data in data.get("nodes", []):
                node_id = node_data.pop("id")
                self.graph.add_node(node_id, **node_data)
            
            # 添加边
            for edge_data in data.get("edges", []):
                source = edge_data.pop("source")
                target = edge_data.pop("target")
                self.graph.add_edge(source, target, **edge_data)
            
            # 恢复元数据
            self._document_entities = data.get("document_entities", {})
            self._entity_counts = data.get("entity_counts", {
                "keywords": {}, "methods": {}, "datasets": {}
            })
            
            print(f"✅ 图谱已加载: {self.graph.number_of_nodes()} 节点, {self.graph.number_of_edges()} 边")
            return True
            
        except Exception as e:
            print(f"❌ 加载图谱失败: {e}")
            return False
    
    def clear(self) -> None:
        """清空图谱"""
        self.graph.clear()
        self._document_entities.clear()
        self._entity_counts = {
            "keywords": {}, "methods": {}, "datasets": {},
            "fields": {}, "applications": {}
        }
        print("🗑️ 图谱已清空")


def create_knowledge_graph() -> KnowledgeGraph:
    """
    便捷函数：创建知识图谱实例
    
    Returns:
        KnowledgeGraph 实例
    """
    return KnowledgeGraph()
