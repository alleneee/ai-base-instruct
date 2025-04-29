"""API响应处理工具模块"""
from typing import Any, Dict, Generic, Optional, Type, TypeVar
from pydantic import BaseModel
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse

# 泛型类型变量
T = TypeVar('T')

class StandardResponse(BaseModel, Generic[T]):
    """标准API响应格式"""
    code: int = 200
    message: str = "操作成功"
    data: Optional[T] = None

class ErrorDetail(BaseModel):
    """错误详情模型"""
    loc: Optional[list[str]] = None
    msg: str
    type: Optional[str] = None

class ErrorResponse(BaseModel):
    """标准错误响应格式"""
    code: int
    message: str
    details: Optional[list[ErrorDetail]] = None
    
class ResponseHandler:
    """API响应处理器"""
    
    @staticmethod
    def success(data: Any = None, message: str = "操作成功", status_code: int = 200) -> JSONResponse:
        """
        创建成功响应
        
        Args:
            data: 响应数据
            message: 响应消息
            status_code: HTTP状态码
            
        Returns:
            JSON响应对象
        """
        return JSONResponse(
            status_code=status_code,
            content=StandardResponse(
                code=status_code,
                message=message,
                data=data
            ).dict()
        )
    
    @staticmethod
    def error(
        message: str, 
        status_code: int = 400, 
        details: Optional[list[ErrorDetail]] = None
    ) -> JSONResponse:
        """
        创建错误响应
        
        Args:
            message: 错误消息
            status_code: HTTP状态码
            details: 错误详情
            
        Returns:
            JSON响应对象
        """
        return JSONResponse(
            status_code=status_code,
            content=ErrorResponse(
                code=status_code,
                message=message,
                details=details
            ).dict()
        )
    
    @staticmethod
    def handle_exception(exception: Exception) -> HTTPException:
        """
        处理异常并转换为HTTP异常
        
        Args:
            exception: 异常对象
            
        Returns:
            HTTP异常对象
        """
        if isinstance(exception, HTTPException):
            return exception
            
        status_code = getattr(exception, "status_code", status.HTTP_500_INTERNAL_SERVER_ERROR)
        detail = str(exception)
        
        return HTTPException(
            status_code=status_code,
            detail=detail
        )

# 创建全局处理器实例
response = ResponseHandler() 