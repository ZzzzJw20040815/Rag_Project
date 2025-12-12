# 学术文献智能导读系统 - 任务清单

## 阶段一：基础 RAG 问答系统

### 项目结构搭建
- [x] 创建 `requirements.txt` 依赖文件
- [x] 创建 `config.py` 配置管理模块
- [x] 创建 `core/` 目录结构

### 核心模块开发
- [x] `core/document_processor.py` - 文档解析与切分
- [x] `core/embeddings.py` - Embedding 服务封装
- [x] `core/vector_store.py` - ChromaDB 向量存储
- [x] `core/rag_chain.py` - RAG 问答链

### 前端界面
- [x] `app.py` - Streamlit 主应用
- [x] `ui/__init__.py` - 可复用 UI 组件

### 验证测试
- [x] Streamlit 应用启动测试
- [/] 上传 PDF 测试 (待用户手动验证)
- [/] 问答功能测试 (待用户手动验证)

---

## 阶段二：知识图谱构建 (已完成)

- [x] `core/entity_extractor.py` - 实体提取
- [x] `core/knowledge_graph.py` - 图谱构建
- [x] `ui/graph_view.py` - 图谱可视化

---

## 阶段三：引用溯源功能 (待开发)

- [ ] 增强 RAG Chain 的引用标注
- [ ] `ui/source_view.py` - 引用展示界面

---

## 阶段四：系统整合优化 (待开发)

- [ ] UI 美化
- [ ] 多文件支持
- [ ] 对话历史导出
