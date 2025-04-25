"""
检索API端点

提供从指定数据集检索内容的功能
"""
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from enterprise_kb.core.config.settings import settings
from enterprise_kb.db.database import get_db
from enterprise_kb.db.models.user import User as UserModel
from enterprise_kb.schemas.retrieval import (
    RetrievalRequest,
    RetrievalResponse
)
from enterprise_kb.services.auth import AuthService
from enterprise_kb.services.retrieval import RetrievalService

router = APIRouter(prefix="/retrieval", tags=["检索"])


@router.post("", response_model=RetrievalResponse)
async def retrieve_chunks(
    retrieval_data: RetrievalRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(AuthService.get_current_active_user)
) -> Any:
    """
    从指定数据集检索块
    """
    retrieval_service = RetrievalService(db)
    
    try:
        # 检查请求参数
        if not retrieval_data.dataset_ids and not retrieval_data.document_ids:
            raise ValueError("必须提供dataset_ids或document_ids")
        
        # 执行检索
        results = await retrieval_service.retrieve_chunks(
            question=retrieval_data.question,
            dataset_ids=retrieval_data.dataset_ids,
            document_ids=retrieval_data.document_ids,
            user_id=current_user.id,
            page=retrieval_data.page,
            page_size=retrieval_data.page_size,
            similarity_threshold=retrieval_data.similarity_threshold,
            vector_similarity_weight=retrieval_data.vector_similarity_weight,
            top_k=retrieval_data.top_k,
            rerank_id=retrieval_data.rerank_id,
            keyword=retrieval_data.keyword,
            highlight=retrieval_data.highlight
        )
        
        return {
            "code": 0,
            "data": results
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 102, "message": str(e)}
        ) 