from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field


class AgentComponent(BaseModel):
    """代理组件模型"""
    component_name: str = Field(..., description="组件名称")
    params: Dict[str, Any] = Field({}, description="参数")
    inputs: Optional[List[Any]] = Field([], description="输入")
    output: Optional[Any] = Field(None, description="输出")


class AgentNode(BaseModel):
    """代理节点模型"""
    downstream: List[Any] = Field([], description="下游节点")
    obj: AgentComponent = Field(..., description="组件对象")
    upstream: List[Any] = Field([], description="上游节点")


class AgentDSL(BaseModel):
    """代理DSL模型"""
    answer: List[Any] = Field([], description="答案")
    components: Dict[str, AgentNode] = Field(..., description="组件")
    embed_id: str = Field("", description="嵌入ID")
    graph: Dict[str, Any] = Field(..., description="图形")
    history: List[Any] = Field([], description="历史记录")
    messages: List[Any] = Field([], description="消息")
    path: List[Any] = Field([], description="路径")
    reference: List[Any] = Field([], description="引用")


class Agent(BaseModel):
    """代理模型"""
    id: str = Field(..., description="代理ID")
    title: str = Field(..., description="标题")
    avatar: Optional[str] = Field(None, description="头像")
    description: Optional[str] = Field(None, description="描述")
    canvas_type: Optional[str] = Field(None, description="画布类型")
    dsl: AgentDSL = Field(..., description="DSL")
    user_id: str = Field(..., description="用户ID")
    create_date: datetime = Field(..., description="创建日期")
    update_date: datetime = Field(..., description="更新日期")
    create_time: int = Field(..., description="创建时间戳")
    update_time: int = Field(..., description="更新时间戳")


class AgentSession(BaseModel):
    """代理会话模型"""
    id: str = Field(..., description="会话ID")
    agent_id: str = Field(..., description="代理ID")
    dsl: AgentDSL = Field(..., description="DSL")
    message: List[Dict[str, str]] = Field(..., description="消息")
    source: str = Field("agent", description="来源")
    user_id: str = Field(..., description="用户ID")


class AgentSessionCreate(BaseModel):
    """创建代理会话请求模型"""
    user_id: Optional[str] = Field(None, description="用户ID")
    # 其他参数由Begin组件指定


class AgentCompletionRequest(BaseModel):
    """代理完成请求模型"""
    question: Optional[str] = Field(None, description="问题")
    stream: Optional[bool] = Field(True, description="是否流式输出")
    session_id: Optional[str] = Field(None, description="会话ID")
    user_id: Optional[str] = Field(None, description="用户ID")
    sync_dsl: Optional[bool] = Field(False, description="是否同步DSL")
    # 其他参数由Begin组件指定


class AgentSessionListResponse(BaseModel):
    """代理会话列表响应模型"""
    code: int = Field(0, description="状态码")
    data: List[AgentSession] = Field(..., description="代理会话列表")


class AgentSessionResponse(BaseModel):
    """代理会话响应模型"""
    code: int = Field(0, description="状态码")
    data: AgentSession = Field(..., description="代理会话数据")


class AgentSessionDeleteRequest(BaseModel):
    """删除代理会话请求模型"""
    ids: List[str] = Field(..., description="要删除的会话ID列表")


class AgentCompletionParam(BaseModel):
    """代理完成参数模型"""
    key: str = Field(..., description="键")
    name: str = Field(..., description="名称")
    optional: bool = Field(..., description="是否可选")
    type: str = Field(..., description="类型")
    value: Optional[str] = Field(None, description="值")


class AgentCompletionStreamData(BaseModel):
    """代理完成流式数据模型"""
    answer: str = Field(..., description="回答")
    reference: Union[List[Any], Dict[str, Any]] = Field([], description="引用数据")
    id: Optional[str] = Field(None, description="ID")
    session_id: str = Field(..., description="会话ID")
    param: Optional[List[AgentCompletionParam]] = Field(None, description="参数")


class AgentCompletionStreamResponse(BaseModel):
    """代理完成流式响应模型"""
    code: int = Field(0, description="状态码")
    message: str = Field("", description="消息")
    data: Union[AgentCompletionStreamData, bool] = Field(..., description="数据")


class AgentListResponse(BaseModel):
    """代理列表响应模型"""
    code: int = Field(0, description="状态码")
    data: List[Agent] = Field(..., description="代理列表") 