"""
代理API端点

提供代理管理功能和与代理交互的功能
"""
from typing import Any, List, Optional
from fastapi import (
    APIRouter, 
    Depends, 
    HTTPException, 
    Query, 
    status, 
    BackgroundTasks,
    UploadFile,
    File,
    Form
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from enterprise_kb.core.config.settings import settings
from enterprise_kb.db.database import get_db
from enterprise_kb.db.models.user import User as UserModel
from enterprise_kb.schemas.agent import (
    AgentListResponse,
    AgentSessionResponse,
    AgentSessionListResponse,
    AgentSessionDeleteRequest,
    AgentCompletionRequest
)
from enterprise_kb.services.auth import AuthService
from enterprise_kb.services.agent import AgentService

router = APIRouter()


@router.get("/agents", response_model=AgentListResponse)
async def list_agents(
    page: int = Query(1, description="页码，默认为1"),
    page_size: int = Query(30, description="每页大小，默认为30"),
    orderby: str = Query("create_time", description="排序字段"),
    desc: bool = Query(True, description="是否降序排序"),
    name: Optional[str] = Query(None, description="代理名称"),
    id: Optional[str] = Query(None, description="代理ID"),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(AuthService.get_current_active_user)
) -> Any:
    """
    获取代理列表
    """
    agent_service = AgentService(db)
    
    try:
        agents = await agent_service.list_agents(
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
            "data": agents
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 102, "message": str(e)}
        )


@router.post("/agents/{agent_id}/sessions", response_model=AgentSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_agent_session(
    agent_id: str,
    user_id: Optional[str] = Query(None, description="用户ID"),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(AuthService.get_current_active_user),
    # 以下是可选的表单参数，将根据代理的Begin组件自动处理
    files: List[UploadFile] = File(None),
    # 其他参数通过表单提交
    **form_data
) -> Any:
    """
    创建代理会话
    """
    agent_service = AgentService(db)
    
    try:
        session = await agent_service.create_session(
            agent_id=agent_id,
            user_id=current_user.id,
            custom_user_id=user_id,
            files=files,
            form_data=form_data
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


@router.get("/agents/{agent_id}/sessions", response_model=AgentSessionListResponse)
async def list_agent_sessions(
    agent_id: str,
    page: int = Query(1, description="页码，默认为1"),
    page_size: int = Query(30, description="每页大小，默认为30"),
    orderby: str = Query("create_time", description="排序字段"),
    desc: bool = Query(True, description="是否降序排序"),
    id: Optional[str] = Query(None, description="会话ID"),
    user_id: Optional[str] = Query(None, description="用户ID"),
    dsl: bool = Query(True, description="是否包含DSL字段"),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(AuthService.get_current_active_user)
) -> Any:
    """
    获取代理会话列表
    """
    agent_service = AgentService(db)
    
    try:
        sessions = await agent_service.list_sessions(
            agent_id=agent_id,
            user_id=current_user.id,
            page=page,
            page_size=page_size,
            orderby=orderby,
            desc=desc,
            session_id=id,
            custom_user_id=user_id,
            include_dsl=dsl
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


@router.delete("/agents/{agent_id}/sessions", status_code=status.HTTP_200_OK)
async def delete_agent_sessions(
    agent_id: str,
    delete_data: AgentSessionDeleteRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(AuthService.get_current_active_user)
) -> Any:
    """
    删除代理会话
    """
    agent_service = AgentService(db)
    
    try:
        await agent_service.delete_sessions(
            agent_id=agent_id,
            session_ids=delete_data.ids,
            user_id=current_user.id
        )
        
        return {"code": 0}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 102, "message": str(e)}
        )


@router.post("/agents/{agent_id}/completions")
async def agent_completion(
    agent_id: str,
    completion_data: AgentCompletionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(AuthService.get_current_active_user)
) -> Any:
    """
    与代理进行对话
    """
    agent_service = AgentService(db)
    
    try:
        # 如果未提供会话ID，则创建新会话
        if not completion_data.session_id:
            # 从请求数据中获取Begin组件所需的参数
            begin_params = {k: v for k, v in completion_data.dict().items() 
                          if k not in ["question", "stream", "session_id", "user_id", "sync_dsl"]}
            
            session = await agent_service.create_session(
                agent_id=agent_id,
                user_id=current_user.id,
                custom_user_id=completion_data.user_id,
                form_data=begin_params
            )
            
            return {
                "code": 0,
                "data": session
            }
        
        # 如果启用流式响应
        if completion_data.stream:
            return StreamingResponse(
                agent_service.stream_agent_completion(
                    agent_id=agent_id,
                    question=completion_data.question,
                    session_id=completion_data.session_id,
                    user_id=current_user.id,
                    sync_dsl=completion_data.sync_dsl,
                    background_tasks=background_tasks
                ),
                media_type="application/json"
            )
        else:
            # 非流式响应
            response = await agent_service.agent_completion(
                agent_id=agent_id,
                question=completion_data.question,
                session_id=completion_data.session_id,
                user_id=current_user.id,
                sync_dsl=completion_data.sync_dsl,
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