"""改进的Celery任务API接口"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query, Depends, BackgroundTasks
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import json
import os

from enterprise_kb.tasks.document_tasks_v2 import (
    process_document_task, 
    batch_process_documents_task,
    process_large_document_task,
    cleanup_task
)
from enterprise_kb.core.celery.task_manager import get_task_manager
from enterprise_kb.storage.document_processor import get_document_processor
from enterprise_kb.core.config.settings import settings

router = APIRouter(prefix="/api/v1/celery/v2", tags=["Celery任务V2"])

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
    group_id: Optional[str] = Field(None, description="任务组ID")
    file_count: int = Field(..., description="文件数量")
    status: str = Field(..., description="任务状态")

class TaskGroupResponse(BaseModel):
    """任务组响应模型"""
    group_id: str = Field(..., description="任务组ID")
    status: str = Field(..., description="任务组状态")
    task_count: int = Field(..., description="任务数量")
    completed: int = Field(..., description="已完成任务数")
    failed: int = Field(..., description="失败任务数")
    progress: int = Field(..., description="进度(0-100)")
    tasks: Optional[List[TaskResponse]] = Field(None, description="任务列表")

class WorkerStatsResponse(BaseModel):
    """Worker统计信息响应模型"""
    workers: Dict[str, Any] = Field(..., description="Worker统计信息")
    active_tasks: int = Field(..., description="活动任务数")
    scheduled_tasks: int = Field(..., description="计划任务数")

@router.post("/process", response_model=TaskResponse)
async def process_document_with_celery(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    datasource: Optional[str] = Form("primary"),
    metadata: Optional[str] = Form(None),
    use_parallel: Optional[bool] = Form(None),
    use_semantic_chunking: Optional[bool] = Form(None),
    use_incremental: Optional[bool] = Form(None),
    chunking_type: Optional[str] = Form(None)
):
    """
    使用Celery异步处理文档
    
    Args:
        file: 上传的文件
        title: 文档标题
        description: 文档描述
        datasource: 数据源名称
        metadata: JSON格式元数据
        use_parallel: 是否使用并行处理
        use_semantic_chunking: 是否使用语义分块
        use_incremental: 是否使用增量更新
        chunking_type: 分块类型
        
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
            
        # 提交Celery任务
        task = process_document_task.delay(
            file_path=file_path,
            metadata=parsed_metadata,
            datasource_name=datasource,
            use_parallel=use_parallel,
            use_semantic_chunking=use_semantic_chunking,
            use_incremental=use_incremental,
            chunking_type=chunking_type
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

@router.post("/process/large", response_model=TaskResponse)
async def process_large_document_with_celery(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    datasource: Optional[str] = Form("primary"),
    metadata: Optional[str] = Form(None),
    chunk_size: int = Form(1000000),  # 默认1MB
    chunking_type: Optional[str] = Form("hierarchical")
):
    """
    使用Celery异步处理大型文档
    
    Args:
        file: 上传的文件
        title: 文档标题
        description: 文档描述
        datasource: 数据源名称
        metadata: JSON格式元数据
        chunk_size: 块大小（字节）
        chunking_type: 分块类型
        
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
            
        # 提交Celery任务
        task = process_large_document_task.delay(
            file_path=file_path,
            metadata=parsed_metadata,
            datasource_name=datasource,
            chunk_size=chunk_size,
            chunking_type=chunking_type
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
        raise HTTPException(status_code=500, detail=f"大型文档处理失败: {str(e)}")

@router.post("/batch", response_model=BatchTaskResponse)
async def batch_process_with_celery(
    files: List[UploadFile] = File(...),
    metadata: Optional[str] = Form(None),
    datasource: Optional[str] = Form("primary"),
    use_parallel: Optional[bool] = Form(None),
    use_semantic_chunking: Optional[bool] = Form(None),
    use_incremental: Optional[bool] = Form(None),
    chunking_type: Optional[str] = Form(None),
    max_concurrent: int = Form(5)
):
    """
    使用Celery批量处理文档
    
    Args:
        files: 上传的文件列表
        metadata: 共享元数据(JSON格式)
        datasource: 数据源名称
        use_parallel: 是否使用并行处理
        use_semantic_chunking: 是否使用语义分块
        use_incremental: 是否使用增量更新
        chunking_type: 分块类型
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
            datasource_name=datasource,
            use_parallel=use_parallel,
            use_semantic_chunking=use_semantic_chunking,
            use_incremental=use_incremental,
            chunking_type=chunking_type,
            max_concurrent=max_concurrent
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
    try:
        # 获取任务管理器
        task_manager = get_task_manager()
        
        # 获取任务信息
        task_info = task_manager.get_task_info(task_id)
        
        return TaskResponse(
            task_id=task_id,
            status=task_info["status"],
            result=task_info.get("result"),
            error=task_info.get("error"),
            progress=task_info.get("progress"),
            meta=task_info.get("meta", {})
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取任务状态失败: {str(e)}")

@router.get("/groups/{group_id}", response_model=TaskGroupResponse)
async def get_group_status(group_id: str, include_tasks: bool = False):
    """
    获取任务组状态
    
    Args:
        group_id: 任务组ID
        include_tasks: 是否包含任务列表
        
    Returns:
        任务组状态和结果
    """
    try:
        # 获取任务管理器
        task_manager = get_task_manager()
        
        # 获取任务组信息
        group_info = task_manager.get_group_info(group_id)
        
        # 构建响应
        response = TaskGroupResponse(
            group_id=group_id,
            status=group_info["status"],
            task_count=group_info["task_count"],
            completed=group_info["completed"],
            failed=group_info["failed"],
            progress=group_info["progress"]
        )
        
        # 如果需要包含任务列表
        if include_tasks:
            tasks = []
            for task_info in group_info["tasks"]:
                tasks.append(TaskResponse(
                    task_id=task_info["task_id"],
                    status=task_info["status"],
                    result=task_info.get("result"),
                    error=task_info.get("error"),
                    progress=task_info.get("progress"),
                    meta=task_info.get("meta", {})
                ))
            response.tasks = tasks
        
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取任务组状态失败: {str(e)}")

@router.post("/tasks/{task_id}/cancel", response_model=Dict[str, Any])
async def cancel_task(task_id: str):
    """
    取消任务
    
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

@router.post("/groups/{group_id}/cancel", response_model=Dict[str, Any])
async def cancel_group(group_id: str):
    """
    取消任务组
    
    Args:
        group_id: 任务组ID
        
    Returns:
        取消结果
    """
    try:
        # 获取任务管理器
        task_manager = get_task_manager()
        
        # 取消任务组
        success = task_manager.cancel_group(group_id)
        
        return {
            "group_id": group_id,
            "success": success,
            "message": "任务组已取消" if success else "取消任务组失败"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"取消任务组失败: {str(e)}")

@router.post("/tasks/{task_id}/retry", response_model=Dict[str, Any])
async def retry_task(task_id: str):
    """
    重试任务
    
    Args:
        task_id: 任务ID
        
    Returns:
        重试结果
    """
    try:
        # 获取任务管理器
        task_manager = get_task_manager()
        
        # 重试任务
        new_task_id = task_manager.retry_failed_task(task_id)
        
        if new_task_id:
            return {
                "original_task_id": task_id,
                "new_task_id": new_task_id,
                "success": True,
                "message": "任务已重试"
            }
        else:
            return {
                "original_task_id": task_id,
                "success": False,
                "message": "重试任务失败，可能任务未失败或无法获取任务信息"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重试任务失败: {str(e)}")

@router.get("/stats", response_model=WorkerStatsResponse)
async def get_worker_stats():
    """
    获取Worker统计信息
    
    Returns:
        Worker统计信息
    """
    try:
        # 获取任务管理器
        task_manager = get_task_manager()
        
        # 获取Worker统计信息
        worker_stats = task_manager.get_worker_stats()
        
        # 获取活动任务
        active_tasks = task_manager.get_active_tasks()
        
        # 获取计划任务
        scheduled_tasks = task_manager.get_scheduled_tasks()
        
        return WorkerStatsResponse(
            workers=worker_stats,
            active_tasks=len(active_tasks),
            scheduled_tasks=len(scheduled_tasks)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取Worker统计信息失败: {str(e)}")

@router.get("/active", response_model=List[Dict[str, Any]])
async def get_active_tasks():
    """
    获取活动任务列表
    
    Returns:
        活动任务列表
    """
    try:
        # 获取任务管理器
        task_manager = get_task_manager()
        
        # 获取活动任务
        active_tasks = task_manager.get_active_tasks()
        
        return active_tasks
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取活动任务失败: {str(e)}")

@router.get("/scheduled", response_model=List[Dict[str, Any]])
async def get_scheduled_tasks():
    """
    获取计划任务列表
    
    Returns:
        计划任务列表
    """
    try:
        # 获取任务管理器
        task_manager = get_task_manager()
        
        # 获取计划任务
        scheduled_tasks = task_manager.get_scheduled_tasks()
        
        return scheduled_tasks
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取计划任务失败: {str(e)}")

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
