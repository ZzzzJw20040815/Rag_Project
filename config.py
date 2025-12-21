"""
配置管理模块
集中管理所有配置项，包括 API 密钥、模型参数、文件路径等
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# ============================================
# 路径配置
# ============================================
# 项目根目录
PROJECT_ROOT = Path(__file__).parent.absolute()
# 数据存储目录
DATA_DIR = PROJECT_ROOT / "data"
# 上传文件目录
UPLOADS_DIR = DATA_DIR / "uploads"
# ChromaDB 持久化目录
CHROMA_DB_DIR = DATA_DIR / "chroma_db"
# 生成的图谱 HTML 文件目录
GRAPHS_DIR = DATA_DIR / "graphs"

# 确保目录存在
for dir_path in [DATA_DIR, UPLOADS_DIR, CHROMA_DB_DIR, GRAPHS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# ============================================
# API 配置
# ============================================
# SiliconFlow API 配置（同时用于 LLM 和 Embedding）
SILICONFLOW_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"

# ============================================
# 模型配置
# ============================================
# LLM 模型配置
LLM_MODEL = "deepseek-ai/DeepSeek-V3.2"  # 硅基流动上的 DeepSeek 模型
LLM_TEMPERATURE = 0.7
LLM_MAX_TOKENS = 8192

# Embedding 模型配置
EMBEDDING_MODEL = "BAAI/bge-m3"  # 中英文双语兼容的 Embedding 模型

# ============================================
# 文档处理配置
# ============================================
# 文本切分参数
CHUNK_SIZE = 600  # 每个 chunk 的最大字符数
CHUNK_OVERLAP = 100  # chunk 之间的重叠字符数

# 支持的文件类型
SUPPORTED_FILE_TYPES = ["pdf", "docx", "doc"]

# ============================================
# RAG 检索配置
# ============================================
# 检索返回的文档数量
RETRIEVAL_K = 12

# ============================================
# 知识图谱配置
# ============================================
# 每篇文档提取的最大关键词数
MAX_KEYWORDS_PER_DOC = 8
# 每篇文档提取的最大方法/技术数
MAX_METHODS_PER_DOC = 5
# 每篇文档提取的最大数据集数
MAX_DATASETS_PER_DOC = 3


def get_api_key():
    """获取 API Key，优先从环境变量读取"""
    return SILICONFLOW_API_KEY


def save_api_key(api_key: str):
    """将 API Key 保存到 .env 文件"""
    env_path = PROJECT_ROOT / ".env"
    
    # 读取现有内容
    existing_lines = []
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            existing_lines = f.readlines()
    
    # 更新或添加 API Key
    key_found = False
    new_lines = []
    for line in existing_lines:
        if line.strip().startswith("DEEPSEEK_API_KEY="):
            new_lines.append(f"DEEPSEEK_API_KEY={api_key}\n")
            key_found = True
        else:
            new_lines.append(line)
    
    if not key_found:
        new_lines.append(f"DEEPSEEK_API_KEY={api_key}\n")
    
    # 写入文件
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    
    # 更新当前进程的环境变量
    os.environ["DEEPSEEK_API_KEY"] = api_key
    global SILICONFLOW_API_KEY
    SILICONFLOW_API_KEY = api_key
