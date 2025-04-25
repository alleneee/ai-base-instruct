"""
聊天助手API端点

提供聊天助手管理功能
"""
from typing import Any, List, Optional
from fastapi import (
    APIRouter, 
    Depends, 
    HTTPException, 
    Query, 
    status, 
    BackgroundTasks
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from enterprise_kb.core.config.settings import settings
from enterprise_kb.db.database import get_db
from enterprise_kb.db.models.user import User as UserModel
from enterprise_kb.schemas.chat import (
    ChatCreate,
    ChatUpdate,
    ChatDeleteRequest,
    ChatResponse,
    ChatListResponse,
    SessionCreate,
    SessionUpdate,
    SessionDeleteRequest,
    SessionResponse,
    SessionListResponse,
    ChatCompletionRequest,
    ChatCompletionStreamResponse,
    RelatedQuestionsRequest,
    RelatedQuestionsResponse
)
from enterprise_kb.services.auth import AuthService
from enterprise_kb.services.chat import ChatService

router = APIRouter()


@router.post("/chats", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
async def create_chat(
    chat_data: ChatCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(AuthService.get_current_active_user)
) -> Any:
    """
    创建聊天助手
    """
    chat_service = ChatService(db)
    
    try:
        chat = await chat_service.create_chat(
            chat_data=chat_data,
            user_id=current_user.id
        )
        
        return {
            "code": 0,
            "data": chat
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 102, "message": str(e)}
        )


@router.put("/chats/{chat_id}", status_code=status.HTTP_200_OK)
async def update_chat(
    chat_id: str,
    chat_data: ChatUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(AuthService.get_current_active_user)
) -> Any:
    """
    更新聊天助手
    """
    chat_service = ChatService(db)
    
    try:
        await chat_service.update_chat(
            chat_id=chat_id,
            chat_data=chat_data,
            user_id=current_user.id
        )
        
        return {"code": 0}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 102, "message": str(e)}
        )


@router.delete("/chats", status_code=status.HTTP_200_OK)
async def delete_chats(
    delete_data: ChatDeleteRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(AuthService.get_current_active_user)
) -> Any:
    """
    删除聊天助手
    """
    chat_service = ChatService(db)
    
    try:
        await chat_service.delete_chats(
            chat_ids=delete_data.ids,
            user_id=current_user.id
        )
        
        return {"code": 0}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 102, "message": str(e)}
        )


@router.get("/chats", response_model=ChatListResponse)
async def list_chats(
    page: int = Query(1, description="页码，默认为1"),
    page_size: int = Query(30, description="每页大小，默认为30"),
    orderby: str = Query("create_time", description="排序字段"),
    desc: bool = Query(True, description="是否降序排序"),
    name: Optional[str] = Query(None, description="聊天助手名称"),
    id: Optional[str] = Query(None, description="聊天助手ID"),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(AuthService.get_current_active_user)
) -> Any:
    """
    获取聊天助手列表
    """
    chat_service = ChatService(db)
    
    try:
        chats = await chat_service.list_chats(
            user_id=current_user.id,
            page=page,
            page_size=page_size,
            orderby=orderby,
            desc=desc,
            name=name,
            id=id
        )
        
        return {
            "code": 0,
            "data": chats
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 102, "message": str(e)}
        )


@router.post("/chats/{chat_id}/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    chat_id: str,
    session_data: SessionCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(AuthService.get_current_active_user)
) -> Any:
    """
    创建聊天助手会话
    """
    chat_service = ChatService(db)
    
    try:
        session = await chat_service.create_session(
            chat_id=chat_id,
            session_data=session_data,
            user_id=current_user.id
        )
        
        return {
            "code": 0,
            "data": session
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 102, "message": str(e)}
        )


@router.put("/chats/{chat_id}/sessions/{session_id}", status_code=status.HTTP_200_OK)
async def update_session(
    chat_id: str,
    session_id: str,
    session_data: SessionUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(AuthService.get_current_active_user)
) -> Any:
    """
    更新聊天助手会话
    """
    chat_service = ChatService(db)
    
    try:
        await chat_service.update_session(
            chat_id=chat_id,
            session_id=session_id,
            session_data=session_data,
            user_id=current_user.id
        )
        
        return {"code": 0}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 102, "message": str(e)}
        )


@router.get("/chats/{chat_id}/sessions", response_model=SessionListResponse)
async def list_sessions(
    chat_id: str,
    page: int = Query(1, description="页码，默认为1"),
    page_size: int = Query(30, description="每页大小，默认为30"),
    orderby: str = Query("create_time", description="排序字段"),
    desc: bool = Query(True, description="是否降序排序"),
    name: Optional[str] = Query(None, description="会话名称"),
    id: Optional[str] = Query(None, description="会话ID"),
    user_id: Optional[str] = Query(None, description="用户ID"),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(AuthService.get_current_active_user)
) -> Any:
    """
    获取聊天助手会话列表
    """
    chat_service = ChatService(db)
    
    try:
        sessions = await chat_service.list_sessions(
            chat_id=chat_id,
            user_id=current_user.id,
            page=page,
            page_size=page_size,
            orderby=orderby,
            desc=desc,
            name=name,
            id=id,
            custom_user_id=user_id
        )
        
        return {
            "code": 0,
            "data": sessions
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 102, "message": str(e)}
        )


@router.delete("/chats/{chat_id}/sessions", status_code=status.HTTP_200_OK)
async def delete_sessions(
    chat_id: str,
    delete_data: SessionDeleteRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(AuthService.get_current_active_user)
) -> Any:
    """
    删除聊天助手会话
    """
    chat_service = ChatService(db)
    
    try:
        await chat_service.delete_sessions(
            chat_id=chat_id,
            session_ids=delete_data.ids,
            user_id=current_user.id
        )
        
        return {"code": 0}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 102, "message": str(e)}
        )


@router.post("/chats/{chat_id}/completions")
async def chat_completion(
    chat_id: str,
    completion_data: ChatCompletionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(AuthService.get_current_active_user)
) -> Any:
    """
    与聊天助手进行对话
    """
    chat_service = ChatService(db)
    
    try:
        # 如果启用流式响应
        if completion_data.stream:
            return StreamingResponse(
                chat_service.stream_chat_completion(
                    chat_id=chat_id,
                    question=completion_data.question,
                    session_id=completion_data.session_id,
                    custom_user_id=completion_data.user_id,
                    user_id=current_user.id,
                    background_tasks=background_tasks
                ),
                media_type="application/json"
            )
        else:
            # 非流式响应
            response = await chat_service.chat_completion(
                chat_id=chat_id,
                question=completion_data.question,
                session_id=completion_data.session_id,
                custom_user_id=completion_data.user_id,
                user_id=current_user.id,
                background_tasks=background_tasks
            )
            
            return {
                "code": 0,
                "data": response
            }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 102, "message": str(e)}
        )


@router.post("/conversation/related_questions", response_model=RelatedQuestionsResponse)
async def generate_related_questions(
    request_data: RelatedQuestionsRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(AuthService.get_current_active_user)
) -> Any:
    """
    根据用户的原始查询生成相关问题
    """
    chat_service = ChatService(db)
    
    try:
        related_questions = await chat_service.generate_related_questions(
            question=request_data.question,
            user_id=current_user.id
        )
        
        return {
            "code": 0,
            "data": related_questions,
            "message": "success"
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 102, "message": str(e)}
        ) 