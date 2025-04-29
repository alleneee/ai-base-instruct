"""测试依赖注入优化"""
from fastapi import FastAPI, Depends
import uvicorn
from typing import Annotated, Dict, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

app = FastAPI(title="依赖注入测试")

# 模拟服务
class UserService:
    def __init__(self):
        self.users = {
            "1": {"id": "1", "name": "张三", "role": "admin"},
            "2": {"id": "2", "name": "李四", "role": "user"}
        }
    
    def get_user(self, user_id: str):
        return self.users.get(user_id)
    
    def list_users(self):
        return list(self.users.values())

# 依赖提供者
def get_user_service():
    return UserService()

# 使用 Annotated 类型简化依赖注入
UserSvc = Annotated[UserService, Depends(get_user_service)]

# 定义路由
router = APIRouter(prefix="/users", tags=["用户"])

@router.get("/{user_id}")
async def get_user(user_id: str, user_service: UserSvc):
    user = user_service.get_user(user_id)
    if not user:
        return {"code": 404, "message": "用户不存在"}
    return {"code": 200, "data": user}

@router.get("")
async def list_users(user_service: UserSvc):
    users = user_service.list_users()
    return {"code": 200, "data": users}

# 注册路由
app.include_router(router)

# 主页
@app.get("/")
async def root():
    return {"message": "依赖注入测试应用"}

if __name__ == "__main__":
    uvicorn.run("test_dependency:app", host="0.0.0.0", port=8001, reload=True) 