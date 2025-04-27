"""Celery任务API接口"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query, Depends
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import json
import os

from enterprise_kb.tasks.document_tasks import (
    process_document_task, 
    batch_process_documents_task,
    cleanup_task
)
from enterprise_kb.storage.document_processor import get_document_processor
from enterprise_kb.core.config.settings import settings

router = APIRouter(prefix="/api/v1/celery", tags=["Celery任务"])

class TaskResponse(BaseModel):
    """任务响应模型"""
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="任务状态")
    result: Optional[Dict[str, Any]] = Field(None, description="任务结果")
    error: Optional[str] = Field(None, description="错误信息")
    progress: Optional[int] = Field(None, description="进度(0-100)")
    meta: Optional[Dict[str, Any]] = Field(None, description="元数据")

class BatchTaskResponse(BaseModel):
    """批量任务响应模型"""
    task_id: str = Field(..., description="任务ID")
    file_count: int = Field(..., description="文件数量")
    status: str = Field(..., description="任务状态")

@router.post("/process", response_model=TaskResponse)
async def process_document_with_celery(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    metadata: Optional[str] = Form(None),
    convert_to_markdown: Optional[bool] = Form(None),
    auto_process: bool = Form(True)
):
    """
    使用Celery异步处理文档
    
    Args:
        file: 上传的文件
        title: 文档标题
        description: 文档描述
        metadata: JSON格式元数据
        convert_to_markdown: 是否转换为Markdown(None为自动决定)
        auto_process: 是否自动分析并处理
        
    Returns:
        任务ID和状态
    """
    try:
        # 获取文档处理器
        document_processor = get_document_processor()
        
        # 读取上传的文件内容
        file_content = await file.read()
        
        # 保存文件
        file_path = document_processor.save_uploaded_file(file_content, file.filename)
        
        # 解析元数据
        parsed_metadata = {}
        if metadata:
            try:
                parsed_metadata = json.loads(metadata)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="元数据必须是有效的JSON格式")
                
        # 设置基本元数据
        if title:
            parsed_metadata["title"] = title
        if description:
            parsed_metadata["description"] = description
        
        # 添加自动分析标志
        parsed_metadata["auto_analyze"] = auto_process
        
        # 确保文件名存在于元数据中
        parsed_metadata["original_filename"] = file.filename
            
        # 提交Celery任务
        task = process_document_task.delay(
            file_path=file_path,
            metadata=parsed_metadata,
            convert_to_md=convert_to_markdown
        )
        
        return TaskResponse(
            task_id=task.id,
            status="PENDING",
            meta={
                "file_name": file.filename, 
                "file_path": file_path
            }
        )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文档处理失败: {str(e)}")

@router.post("/batch", response_model=BatchTaskResponse)
async def batch_process_with_celery(
    files: List[UploadFile] = File(...),
    metadata: Optional[str] = Form(None),
    auto_process: bool = Form(True),
    convert_to_markdown: Optional[bool] = Form(None)
):
    """
    使用Celery批量处理文档
    
    Args:
        files: 上传的文件列表
        metadata: 共享元数据(JSON格式)
        auto_process: 是否自动分析处理
        convert_to_markdown: 是否转换为Markdown(None为自动决定)
        
    Returns:
        批处理任务ID和状态
    """
    try:
        # 获取文档处理器
        document_processor = get_document_processor()
        
        # 解析元数据
        shared_metadata = {}
        if metadata:
            try:
                shared_metadata = json.loads(metadata)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="元数据必须是有效的JSON格式")
                
        # 保存所有文件
        file_paths = []
        file_names = []
        for file in files:
            file_content = await file.read()
            file_path = document_processor.save_uploaded_file(file_content, file.filename)
            file_paths.append(file_path)
            file_names.append(file.filename)
        
        # 添加批次信息到元数据
        shared_metadata["batch_size"] = len(files)
        shared_metadata["file_names"] = file_names
                
        # 提交批处理任务
        task = batch_process_documents_task.delay(
            file_paths=file_paths,
            shared_metadata=shared_metadata,
            auto_process=auto_process,
            convert_to_md=convert_to_markdown
        )
        
        return BatchTaskResponse(
            task_id=task.id,
            file_count=len(files),
            status="PENDING"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量处理文档失败: {str(e)}")

@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task_status(task_id: str):
    """
    获取任务状态
    
    Args:
        task_id: 任务ID
        
    Returns:
        任务状态和结果
    """
    from celery.result import AsyncResult
    
    task = AsyncResult(task_id)
    
    response = TaskResponse(
        task_id=task_id,
        status=task.status
    )
    
    if task.failed():
        response.error = str(task.result) if task.result else "任务失败"
    elif task.successful():
        response.result = task.result
    elif task.state == 'PROCESSING' and task.info:
        response.progress = task.info.get('progress', 0)
        response.meta = task.info
    
    return response

@router.post("/cleanup", response_model=TaskResponse)
async def cleanup_files(
    file_paths: List[str],
    keep_original: bool = True
):
    """
    清理临时文件
    
    Args:
        file_paths: 文件路径列表
        keep_original: 是否保留原始文件
        
    Returns:
        清理任务状态
    """
    # 提交清理任务
    task = cleanup_task.delay(
        file_paths=file_paths,
        keep_original=keep_original
    )
    
    return TaskResponse(
        task_id=task.id,
        status="PENDING",
        meta={"file_count": len(file_paths)}
    ) 