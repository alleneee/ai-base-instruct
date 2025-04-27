"""文档分段处理API接口"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query, Depends, BackgroundTasks
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import json
import os
import uuid

from enterprise_kb.tasks.document_segment_tasks import (
    process_document_segmented_task,
    batch_process_segmented_task
)
from enterprise_kb.core.celery.task_manager import get_task_manager
from enterprise_kb.storage.document_processor import get_document_processor
from enterprise_kb.core.config.settings import settings

router = APIRouter(prefix="/api/v1/documents/segmented", tags=["文档分段处理"])

class SegmentedTaskResponse(BaseModel):
    """分段处理任务响应模型"""
    task_id: str = Field(..., description="任务ID")
    doc_id: str = Field(..., description="文档ID")
    file_name: str = Field(..., description="文件名")
    status: str = Field(..., description="任务状态")
    meta: Optional[Dict[str, Any]] = Field(None, description="元数据")

class BatchSegmentedTaskResponse(BaseModel):
    """批量分段处理任务响应模型"""
    task_id: str = Field(..., description="任务ID")
    batch_id: str = Field(..., description="批次ID")
    file_count: int = Field(..., description="文件数量")
    status: str = Field(..., description="任务状态")

class SegmentedTaskStatusResponse(BaseModel):
    """分段处理任务状态响应模型"""
    task_id: str = Field(..., description="任务ID")
    doc_id: str = Field(..., description="文档ID")
    status: str = Field(..., description="任务状态")
    progress: Optional[int] = Field(None, description="进度(0-100)")
    stage: Optional[str] = Field(None, description="处理阶段")
    segment_count: Optional[int] = Field(None, description="段落数量")
    success_count: Optional[int] = Field(None, description="成功段落数")
    failed_count: Optional[int] = Field(None, description="失败段落数")
    node_count: Optional[int] = Field(None, description="节点数量")
    error: Optional[str] = Field(None, description="错误信息")
    result: Optional[Dict[str, Any]] = Field(None, description="处理结果")

@router.post("/process", response_model=SegmentedTaskResponse)
async def process_document_segmented(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    datasource: Optional[str] = Form("primary"),
    metadata: Optional[str] = Form(None),
    chunking_type: Optional[str] = Form("hierarchical"),
    chunk_size: int = Form(500),
    chunk_overlap: int = Form(50),
    max_segments: Optional[int] = Form(None),
    max_concurrent: int = Form(10)
):
    """
    使用分段处理方式处理文档
    
    Args:
        file: 上传的文件
        title: 文档标题
        description: 文档描述
        datasource: 数据源名称
        metadata: JSON格式元数据
        chunking_type: 分块类型
        chunk_size: 块大小
        chunk_overlap: 块重叠
        max_segments: 最大段落数，如果为None则不限制
        max_concurrent: 最大并发处理数
        
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
        
        # 确保文件名存在于元数据中
        parsed_metadata["original_filename"] = file.filename
        
        # 确保文档ID存在
        if "doc_id" not in parsed_metadata:
            parsed_metadata["doc_id"] = str(uuid.uuid4())
        
        doc_id = parsed_metadata["doc_id"]
            
        # 提交Celery任务
        task = process_document_segmented_task.delay(
            file_path=file_path,
            metadata=parsed_metadata,
            datasource_name=datasource,
            chunking_type=chunking_type,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            max_segments=max_segments,
            max_concurrent=max_concurrent
        )
        
        return SegmentedTaskResponse(
            task_id=task.id,
            doc_id=doc_id,
            file_name=file.filename,
            status="PENDING",
            meta={
                "file_path": file_path,
                "datasource": datasource,
                "chunking_type": chunking_type,
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap
            }
        )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文档处理失败: {str(e)}")

@router.post("/batch", response_model=BatchSegmentedTaskResponse)
async def batch_process_segmented(
    files: List[UploadFile] = File(...),
    metadata: Optional[str] = Form(None),
    datasource: Optional[str] = Form("primary"),
    chunking_type: Optional[str] = Form("hierarchical"),
    chunk_size: int = Form(500),
    chunk_overlap: int = Form(50),
    max_segments: Optional[int] = Form(None),
    max_concurrent: int = Form(5)
):
    """
    批量分段处理文档
    
    Args:
        files: 上传的文件列表
        metadata: 共享元数据(JSON格式)
        datasource: 数据源名称
        chunking_type: 分块类型
        chunk_size: 块大小
        chunk_overlap: 块重叠
        max_segments: 最大段落数，如果为None则不限制
        max_concurrent: 最大并发处理数
        
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
        
        # 生成批次ID
        batch_id = str(uuid.uuid4())
        shared_metadata["batch_id"] = batch_id
                
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
        task = batch_process_segmented_task.delay(
            file_paths=file_paths,
            shared_metadata=shared_metadata,
            datasource_name=datasource,
            chunking_type=chunking_type,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            max_segments=max_segments,
            max_concurrent=max_concurrent
        )
        
        return BatchSegmentedTaskResponse(
            task_id=task.id,
            batch_id=batch_id,
            file_count=len(files),
            status="PENDING"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量处理文档失败: {str(e)}")

@router.get("/tasks/{task_id}", response_model=SegmentedTaskStatusResponse)
async def get_segmented_task_status(task_id: str):
    """
    获取分段处理任务状态
    
    Args:
        task_id: 任务ID
        
    Returns:
        任务状态和结果
    """
    try:
        # 获取任务管理器
        task_manager = get_task_manager()
        
        # 获取任务信息
        task_info = task_manager.get_task_info(task_id)
        
        # 构建响应
        response = SegmentedTaskStatusResponse(
            task_id=task_id,
            doc_id=task_info.get("meta", {}).get("doc_id", "unknown"),
            status=task_info["status"],
            progress=task_info.get("meta", {}).get("progress"),
            stage=task_info.get("meta", {}).get("stage"),
            segment_count=task_info.get("meta", {}).get("segment_count"),
            success_count=task_info.get("meta", {}).get("success_count"),
            failed_count=task_info.get("meta", {}).get("failed_count"),
            node_count=task_info.get("meta", {}).get("node_count"),
            error=task_info.get("error"),
            result=task_info.get("result")
        )
        
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取任务状态失败: {str(e)}")

@router.post("/tasks/{task_id}/cancel", response_model=Dict[str, Any])
async def cancel_segmented_task(task_id: str):
    """
    取消分段处理任务
    
    Args:
        task_id: 任务ID
        
    Returns:
        取消结果
    """
    try:
        # 获取任务管理器
        task_manager = get_task_manager()
        
        # 取消任务
        success = task_manager.cancel_task(task_id)
        
        return {
            "task_id": task_id,
            "success": success,
            "message": "任务已取消" if success else "取消任务失败"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"取消任务失败: {str(e)}")
