import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, Dict, Any, List, Literal

class Settings(BaseSettings):
    # 应用配置
    APP_NAME: str = "企业知识库平台"
    API_PREFIX: str = "/api/v1"
    DEBUG: bool = False
    
    # LlamaIndex配置 - Renamed to avoid conflict with LlamaIndex Settings class attributes
    LLAMA_INDEX_CHUNK_SIZE: int = int(os.getenv("LLAMA_INDEX_CHUNK_SIZE", "1024"))
    LLAMA_INDEX_CHUNK_OVERLAP: int = int(os.getenv("LLAMA_INDEX_CHUNK_OVERLAP", "20"))
    
    # Milvus配置
    MILVUS_HOST: str = os.getenv("MILVUS_HOST", "localhost")
    MILVUS_PORT: int = int(os.getenv("MILVUS_PORT", "19530"))
    MILVUS_COLLECTION: str = os.getenv("MILVUS_COLLECTION", "enterprise_kb")
    MILVUS_DIMENSION: int = int(os.getenv("MILVUS_DIMENSION", "1536")) # 从环境变量或默认值读取
    MILVUS_URI: str = os.getenv("MILVUS_URI", f"http://{MILVUS_HOST}:{MILVUS_PORT}") # Added for consistency
    MILVUS_USER: str = os.getenv("MILVUS_USER", "") # Added for potential auth
    MILVUS_PASSWORD: str = os.getenv("MILVUS_PASSWORD", "") # Added for potential auth
    MILVUS_INDEX_MANAGEMENT: str = os.getenv("MILVUS_INDEX_MANAGEMENT", "CREATE_IF_NOT_EXISTS") # e.g., CREATE_IF_NOT_EXISTS, NO_VALIDATION
    MILVUS_OVERWRITE: bool = os.getenv("MILVUS_OVERWRITE", "False").lower() == "true"
    MILVUS_TEXT_FIELD: str = os.getenv("MILVUS_TEXT_FIELD", "text")
    MILVUS_EMBEDDING_FIELD: str = os.getenv("MILVUS_EMBEDDING_FIELD", "embedding")
    MILVUS_METADATA_FIELD: str = os.getenv("MILVUS_METADATA_FIELD", "metadata")
    MILVUS_ID_FIELD: str = os.getenv("MILVUS_ID_FIELD", "id") # Milvus primary key field
    
    # 文档处理配置
    UPLOAD_DIR: str = "data/uploads"
    PROCESSED_DIR: str = "data/processed"
    SUPPORTED_DOCUMENT_TYPES: List[str] = [
        ".pdf", ".docx", ".doc", ".txt", ".md", 
        ".ppt", ".pptx", ".csv", ".xlsx", ".xls"
    ]
    
    # 数据库配置 (Assuming PostgreSQL for metadata store)
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "enterprise_kb")
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    )
    
    # 安全配置
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 天
    JWT_ALGORITHM: str = "HS256"
    
    # 邮件配置
    MAIL_USERNAME: str = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD: str = os.getenv("MAIL_PASSWORD", "")
    MAIL_FROM: str = os.getenv("MAIL_FROM", "noreply@example.com")
    MAIL_PORT: int = int(os.getenv("MAIL_PORT", "587"))
    MAIL_SERVER: str = os.getenv("MAIL_SERVER", "")
    MAIL_FROM_NAME: str = os.getenv("MAIL_FROM_NAME", "企业知识库平台")
    MAIL_TLS: bool = os.getenv("MAIL_TLS", "True").lower() == "true"
    MAIL_SSL: bool = os.getenv("MAIL_SSL", "False").lower() == "true"
    
    # Redis配置（用于缓存和限速）
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")
    REDIS_URL: str = os.getenv(
        "REDIS_URL",
        f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}" if REDIS_PASSWORD else f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    )
    
    # Reranker 配置
    RERANKER_MODEL_NAME: str = os.getenv("RERANKER_MODEL_NAME", "cross-encoder/ms-marco-MiniLM-L-6-v2")
    RERANK_TOP_N: int = int(os.getenv("RERANK_TOP_N", "25")) # 只对初步检索的前 N 个结果进行重排

    # --- Provider Selection --- (Added)
    EMBEDDING_PROVIDER: Literal["openai", "dashscope"] = os.getenv("EMBEDDING_PROVIDER", "openai") # 从环境变量或默认值读取
    LLM_PROVIDER: Literal["openai", "dashscope"] = os.getenv("LLM_PROVIDER", "openai") # 从环境变量或默认值读取

    # --- OpenAI Settings --- (Added)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_EMBED_MODEL_NAME: str = os.getenv("OPENAI_EMBED_MODEL_NAME", "text-embedding-ada-002")
    OPENAI_CHAT_MODEL_NAME: str = os.getenv("OPENAI_CHAT_MODEL_NAME", "gpt-3.5-turbo")

    # --- DashScope Settings --- (Added)
    DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "")
    DASHSCOPE_EMBED_MODEL_NAME: str = os.getenv("DASHSCOPE_EMBED_MODEL_NAME", "text-embedding-v2")
    DASHSCOPE_CHAT_MODEL_NAME: str = os.getenv("DASHSCOPE_CHAT_MODEL_NAME", "qwen-plus")

    # 缓存配置
    CACHE_EXPIRE: int = 900
    
    # API限流配置
    RATE_LIMIT_SECOND: int = int(os.getenv("RATE_LIMIT_SECOND", "10")) # 每秒请求数量限制
    
    # 日志配置
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

# --- Dynamically configure LlamaIndex Settings --- (Added Block)
from llama_index.core import Settings as LlamaSettings
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.dashscope import DashScopeEmbedding
from llama_index.llms.dashscope import DashScopeLLM
import logging

logger = logging.getLogger(__name__)

# Configure Embedding Model
embed_model_name_for_log = "Unknown"
try:
    if settings.EMBEDDING_PROVIDER == "dashscope":
        embed_model_name_for_log = settings.DASHSCOPE_EMBED_MODEL_NAME
        if not settings.DASHSCOPE_API_KEY:
            logger.warning("DASHSCOPE_API_KEY is not set. DashScope Embedding will likely fail.")
        LlamaSettings.embed_model = DashScopeEmbedding(
            model_name=settings.DASHSCOPE_EMBED_MODEL_NAME,
            api_key=settings.DASHSCOPE_API_KEY
        )
        logger.info(f"Configured LlamaIndex Embedding with DashScope: {embed_model_name_for_log}")
        # TODO: 添加维度匹配检查 (需要知道各模型的维度)
        # expected_dim = get_embedding_dimension(settings.EMBEDDING_PROVIDER, embed_model_name_for_log)
        # if expected_dim and settings.MILVUS_DIMENSION != expected_dim:
        #     logger.error(f"CRITICAL: MILVUS_DIMENSION ({settings.MILVUS_DIMENSION}) does NOT match detected dimension ({expected_dim}) for model {embed_model_name_for_log}!")

    elif settings.EMBEDDING_PROVIDER == "openai":
        embed_model_name_for_log = settings.OPENAI_EMBED_MODEL_NAME
        if not settings.OPENAI_API_KEY:
             logger.warning("OPENAI_API_KEY is not set. OpenAI Embedding will likely fail.")
        LlamaSettings.embed_model = OpenAIEmbedding(
            model=settings.OPENAI_EMBED_MODEL_NAME,
            api_key=settings.OPENAI_API_KEY
        )
        logger.info(f"Configured LlamaIndex Embedding with OpenAI: {embed_model_name_for_log}")
        # Example Check for ada-002:
        # if settings.MILVUS_DIMENSION != 1536:
        #     logger.error(f"CRITICAL: MILVUS_DIMENSION ({settings.MILVUS_DIMENSION}) may not match OpenAI model {embed_model_name_for_log} dimension (1536)!")
    else:
        logger.error(f"Unsupported EMBEDDING_PROVIDER: {settings.EMBEDDING_PROVIDER}. No embedding model configured.")
        LlamaSettings.embed_model = None # Or raise error

except Exception as e:
    logger.error(f"Failed to initialize Embedding model '{embed_model_name_for_log}' for provider '{settings.EMBEDDING_PROVIDER}': {e}", exc_info=True)
    LlamaSettings.embed_model = None # Ensure it's None on error


# Configure LLM (Chat Model)
llm_model_name_for_log = "Unknown"
try:
    if settings.LLM_PROVIDER == "dashscope":
        llm_model_name_for_log = settings.DASHSCOPE_CHAT_MODEL_NAME
        if not settings.DASHSCOPE_API_KEY:
            logger.warning("DASHSCOPE_API_KEY is not set. DashScope LLM will likely fail.")
        LlamaSettings.llm = DashScopeLLM(
            model_name=settings.DASHSCOPE_CHAT_MODEL_NAME,
            api_key=settings.DASHSCOPE_API_KEY
            # Add other parameters like temperature, max_tokens if needed
        )
        logger.info(f"Configured LlamaIndex LLM with DashScope: {llm_model_name_for_log}")

    elif settings.LLM_PROVIDER == "openai":
        llm_model_name_for_log = settings.OPENAI_CHAT_MODEL_NAME
        if not settings.OPENAI_API_KEY:
             logger.warning("OPENAI_API_KEY is not set. OpenAI LLM will likely fail.")
        LlamaSettings.llm = OpenAI(
            model=settings.OPENAI_CHAT_MODEL_NAME,
            api_key=settings.OPENAI_API_KEY
            # Add other parameters like temperature, max_tokens if needed
        )
        logger.info(f"Configured LlamaIndex LLM with OpenAI: {llm_model_name_for_log}")
    else:
        logger.error(f"Unsupported LLM_PROVIDER: {settings.LLM_PROVIDER}. No LLM configured.")
        LlamaSettings.llm = None # Or raise error

except Exception as e:
    logger.error(f"Failed to initialize LLM '{llm_model_name_for_log}' for provider '{settings.LLM_PROVIDER}': {e}", exc_info=True)
    LlamaSettings.llm = None # Ensure it's None on error


# Configure other global LlamaIndex settings from our Settings class
# Note: Renamed settings fields to avoid conflict with LlamaIndex's own Settings attributes
LlamaSettings.chunk_size = settings.LLAMA_INDEX_CHUNK_SIZE
LlamaSettings.chunk_overlap = settings.LLAMA_INDEX_CHUNK_OVERLAP

# Make sure tokenizer corresponds to the chosen LLM if needed, or use default
# LlamaSettings.tokenizer = ...

logger.info(f"LlamaIndex global settings configured: chunk_size={LlamaSettings.chunk_size}, chunk_overlap={LlamaSettings.chunk_overlap}")

# --- End of Added Block --- 