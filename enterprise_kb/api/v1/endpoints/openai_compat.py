"""
OpenAI兼容API端点

提供与OpenAI API兼容的聊天和代理交互功能
"""
from typing import Any, Dict
import time
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from enterprise_kb.core.config.settings import settings
from enterprise_kb.db.database import get_db
from enterprise_kb.db.models.user import User as UserModel
from enterprise_kb.schemas.openai import (
    ChatCompletionRequest,
    ChatCompletion,
    ChatCompletionChunk
)
from enterprise_kb.services.auth import AuthService
from enterprise_kb.services.openai_compat import OpenAICompatService

router = APIRouter()


@router.post("/chats_openai/{chat_id}/chat/completions")
async def chat_openai_completion(
    chat_id: str,
    request: ChatCompletionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(AuthService.get_current_active_user)
) -> Any:
    """
    创建与OpenAI兼容的聊天助手响应
    """
    service = OpenAICompatService(db)
    
    # 检查消息列表
    if not request.messages or len(request.messages) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 102, "message": "消息列表不能为空"}
        )
    
    try:
        # 如果启用流式响应
        if request.stream:
            return StreamingResponse(
                service.stream_chat_completion(
                    chat_id=chat_id,
                    messages=request.messages,
                    model=request.model,
                    user_id=current_user.id,
                    background_tasks=background_tasks
                ),
                media_type="application/json"
            )
        else:
            # 非流式响应
            completion = await service.chat_completion(
                chat_id=chat_id,
                messages=request.messages,
                model=request.model,
                user_id=current_user.id,
                background_tasks=background_tasks
            )
            
            return completion
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 102, "message": str(e)}
        )


@router.post("/agents_openai/{agent_id}/chat/completions")
async def agent_openai_completion(
    agent_id: str,
    request: ChatCompletionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(AuthService.get_current_active_user)
) -> Any:
    """
    创建与OpenAI兼容的代理响应
    """
    service = OpenAICompatService(db)
    
    # 检查消息列表
    if not request.messages or len(request.messages) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 102, "message": "消息列表不能为空"}
        )
    
    try:
        # 如果启用流式响应
        if request.stream:
            return StreamingResponse(
                service.stream_agent_completion(
                    agent_id=agent_id,
                    messages=request.messages,
                    model=request.model,
                    user_id=current_user.id,
                    background_tasks=background_tasks
                ),
                media_type="application/json"
            )
        else:
            # 非流式响应
            completion = await service.agent_completion(
                agent_id=agent_id,
                messages=request.messages,
                model=request.model,
                user_id=current_user.id,
                background_tasks=background_tasks
            )
            
            return completion
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 102, "message": str(e)}
        ) 