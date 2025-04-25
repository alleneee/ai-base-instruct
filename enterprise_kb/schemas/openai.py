from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """聊天消息模型"""
    role: str = Field(..., description="角色")
    content: str = Field(..., description="内容")


class CompletionUsage(BaseModel):
    """完成用量模型"""
    prompt_tokens: int = Field(..., description="输入令牌数")
    completion_tokens: int = Field(..., description="完成令牌数")
    total_tokens: int = Field(..., description="总令牌数")


class CompletionTokenDetails(BaseModel):
    """完成令牌详情模型"""
    accepted_prediction_tokens: int = Field(..., description="接受的预测令牌数")
    reasoning_tokens: int = Field(..., description="推理令牌数")
    rejected_prediction_tokens: int = Field(..., description="拒绝的预测令牌数")


class CompletionUsageDetails(BaseModel):
    """完成用量详情模型"""
    prompt_tokens: int = Field(..., description="输入令牌数")
    completion_tokens: int = Field(..., description="完成令牌数")
    completion_tokens_details: Optional[CompletionTokenDetails] = Field(None, description="完成令牌详情")
    total_tokens: int = Field(..., description="总令牌数")


class ChatCompletionRequest(BaseModel):
    """聊天完成请求模型"""
    model: str = Field(..., description="模型")
    messages: List[ChatMessage] = Field(..., description="消息列表")
    stream: Optional[bool] = Field(False, description="是否流式输出")


class ChatCompletionMessage(BaseModel):
    """聊天完成消息模型"""
    content: str = Field(..., description="内容")
    role: str = Field("assistant", description="角色")
    function_call: Optional[Any] = Field(None, description="函数调用")
    tool_calls: Optional[Any] = Field(None, description="工具调用")


class ChatCompletionChoice(BaseModel):
    """聊天完成选择模型"""
    finish_reason: Optional[str] = Field(None, description="完成原因")
    index: int = Field(0, description="索引")
    logprobs: Optional[Any] = Field(None, description="日志概率")
    message: ChatCompletionMessage = Field(..., description="消息")


class ChatCompletion(BaseModel):
    """聊天完成模型"""
    choices: List[ChatCompletionChoice] = Field(..., description="选择列表")
    created: int = Field(..., description="创建时间戳")
    id: str = Field(..., description="ID")
    model: str = Field(..., description="模型")
    object: str = Field("chat.completion", description="对象类型")
    usage: Optional[CompletionUsageDetails] = Field(None, description="用量")


class ChatCompletionChunkDelta(BaseModel):
    """聊天完成块增量模型"""
    content: Optional[str] = Field(None, description="内容")
    role: Optional[str] = Field("assistant", description="角色")
    function_call: Optional[Any] = Field(None, description="函数调用")
    tool_calls: Optional[Any] = Field(None, description="工具调用")


class ChatCompletionChunkChoice(BaseModel):
    """聊天完成块选择模型"""
    delta: ChatCompletionChunkDelta = Field(..., description="增量")
    finish_reason: Optional[str] = Field(None, description="完成原因")
    index: int = Field(0, description="索引")
    logprobs: Optional[Any] = Field(None, description="日志概率")


class ChatCompletionChunk(BaseModel):
    """聊天完成块模型"""
    id: str = Field(..., description="ID")
    choices: List[ChatCompletionChunkChoice] = Field(..., description="选择列表")
    created: int = Field(..., description="创建时间戳")
    model: str = Field(..., description="模型")
    object: str = Field("chat.completion.chunk", description="对象类型")
    system_fingerprint: str = Field("", description="系统指纹")
    usage: Optional[CompletionUsage] = Field(None, description="用量") 