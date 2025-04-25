import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, Dict, Any, List

class Settings(BaseSettings):
    # 应用配置
    APP_NAME: str = "企业知识库平台"
    API_PREFIX: str = "/api/v1"
    DEBUG: bool = False
    
    # LlamaIndex配置
    LLAMA_INDEX_CHUNK_SIZE: int = 1024
    LLAMA_INDEX_CHUNK_OVERLAP: int = 20
    
    # Milvus配置
    MILVUS_HOST: str = os.getenv("MILVUS_HOST", "localhost")
    MILVUS_PORT: int = int(os.getenv("MILVUS_PORT", "19530"))
    MILVUS_COLLECTION: str = os.getenv("MILVUS_COLLECTION", "enterprise_kb")
    MILVUS_DIMENSION: int = 1536  # 默认嵌入向量维度
    
    # 文档处理配置
    UPLOAD_DIR: str = "data/uploads"
    PROCESSED_DIR: str = "data/processed"
    SUPPORTED_DOCUMENT_TYPES: List[str] = [
        ".pdf", ".docx", ".doc", ".txt", ".md", 
        ".ppt", ".pptx", ".csv", ".xlsx", ".xls"
    ]
    
    # 数据库配置
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql+asyncpg://postgres:postgres@localhost:5432/enterprise_kb"
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
    MAIL_TLS: bool = True
    MAIL_SSL: bool = False
    
    # Redis配置（用于缓存和限速）
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")
    REDIS_URL: str = os.getenv(
        "REDIS_URL", 
        f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    )
    
    # 缓存配置
    CACHE_EXPIRE: int = 60 * 15  # 15分钟
    
    # API限流配置
    RATE_LIMIT_SECOND: int = 10  # 每秒请求数量限制
    
    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings() 