import os
from typing import Optional, Dict, Any, List, Union, AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pydantic import validator

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
    
    # Milvus新配置
    MILVUS_URI: str = os.getenv("MILVUS_URI", "http://localhost:19530")
    MILVUS_USER: str = os.getenv("MILVUS_USER", "")
    MILVUS_PASSWORD: str = os.getenv("MILVUS_PASSWORD", "")
    MILVUS_TEXT_FIELD: str = os.getenv("MILVUS_TEXT_FIELD", "text")
    MILVUS_EMBEDDING_FIELD: str = os.getenv("MILVUS_EMBEDDING_FIELD", "embedding")
    MILVUS_METADATA_FIELD: str = os.getenv("MILVUS_METADATA_FIELD", "metadata")
    MILVUS_ID_FIELD: str = os.getenv("MILVUS_ID_FIELD", "id")
    
    # PostgreSQL配置
    POSTGRES_CONNECTION_STRING: str = os.getenv("POSTGRES_CONNECTION_STRING", "postgresql+asyncpg://postgres:postgres@localhost:5432/enterprise_kb")
    POSTGRES_SCHEMA_NAME: str = os.getenv("POSTGRES_SCHEMA_NAME", "public")
    POSTGRES_TABLE_NAME: str = os.getenv("POSTGRES_TABLE_NAME", "kb_vectors")
    POSTGRES_VECTOR_COLUMN: str = os.getenv("POSTGRES_VECTOR_COLUMN", "embedding")
    POSTGRES_CONTENT_COLUMN: str = os.getenv("POSTGRES_CONTENT_COLUMN", "content")
    POSTGRES_METADATA_COLUMN: str = os.getenv("POSTGRES_METADATA_COLUMN", "metadata")
    POSTGRES_DIMENSION: int = int(os.getenv("POSTGRES_DIMENSION", "1536"))
    
    # MySQL数据库配置
    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER: str = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "password")
    MYSQL_DB: str = os.getenv("MYSQL_DB", "enterprise_kb")
    MYSQL_URL: str = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"
    
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
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 天
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30  # 30 天
    JWT_ALGORITHM: str = "HS256"
    
    # 鉴权配置
    AUTH_ENABLED: bool = os.getenv("AUTH_ENABLED", "true").lower() == "true"
    AUTH_TOKEN_URL: str = "/api/v1/auth/token"
    AUTH_PUBLIC_ENDPOINTS: List[str] = [
        "/api/health",
        "/api/docs",
        "/api/redoc",
        "/api/openapi.json",
        "/api/v1/auth/token",
        "/api/v1/auth/register"
    ]
    
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
    
    # CORS配置
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        """处理CORS来源"""
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

@lru_cache()
def get_settings() -> Settings:
    """获取应用设置的缓存实例"""
    return Settings()

settings = get_settings() 