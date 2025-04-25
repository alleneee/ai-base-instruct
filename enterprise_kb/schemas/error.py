from enum import Enum
from typing import Optional, Any, Dict, List, Union
from pydantic import BaseModel, Field


class ErrorCode(int, Enum):
    """错误码枚举"""
    SUCCESS = 0
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    INTERNAL_SERVER_ERROR = 500
    INVALID_CHUNK_ID = 1001
    CHUNK_UPDATE_FAILED = 1002


class BaseResponse(BaseModel):
    """基础响应模型"""
    code: int = Field(0, description="状态码，0表示成功")
    message: str = Field("", description="错误消息")
    data: Optional[Any] = Field(None, description="响应数据")


class ErrorResponse(BaseModel):
    """错误响应模型"""
    code: int = Field(..., description="错误码")
    message: str = Field(..., description="错误消息") 