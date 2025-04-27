# FastAPI 生命周期事件管理

本文档描述了企业知识库平台中使用的 FastAPI 应用生命周期事件管理方法。

## 现代 FastAPI Lifespan 管理

从 FastAPI 0.89.0 版本开始，推荐使用 `@app.lifespan` 装饰器来管理应用的生命周期事件，这是 FastAPI 官方推荐的方式，取代了旧的 `@app.on_event("startup")` 和 `@app.on_event("shutdown")` 装饰器方法。

### 基本使用方法

```python
from fastapi import FastAPI

app = FastAPI()

@app.lifespan
async def lifespan(app: FastAPI):
    # 应用启动时执行的代码
    print("应用启动")
    
    yield  # 分隔启动和关闭逻辑
    
    # 应用关闭时执行的代码
    print("应用关闭")
```

### 在本项目中的实现

本项目采用模块化的方式实现了多个 lifespan 管理器：

1. **缓存管理**（`enterprise_kb/core/cache.py`）：
   - 在应用启动时初始化 Redis 缓存
   - 在应用关闭时关闭 Redis 连接

2. **速率限制**（`enterprise_kb/core/limiter.py`）：
   - 在应用启动时初始化限速器
   - 在应用关闭时关闭 Redis 连接

3. **应用级生命周期管理**（`enterprise_kb/main.py`）：
   - 提供全局应用级的生命周期事件处理

### 多个 Lifespan 的处理顺序

FastAPI 允许在同一个应用中注册多个 lifespan 函数，执行顺序如下：

- **启动时**：按照注册顺序执行（从上到下）
- **关闭时**：按照注册顺序的逆序执行（从下到上）

这确保了资源的正确初始化和清理，特别是当某些资源依赖于其他资源时。

### 示例：模块化 Lifespan 管理

```python
# 在模块中定义 lifespan
def setup_feature(app: FastAPI) -> None:
    redis_client = redis.Redis.from_url(settings.REDIS_URL)
    
    @app.lifespan
    async def lifespan(app: FastAPI):
        # 初始化（启动时）
        print("初始化功能")
        
        yield
        
        # 清理（关闭时）
        await redis_client.close()
        print("清理功能")

# 在应用中注册
app = FastAPI()
setup_feature(app)
```

## 与旧版本的区别

### 旧版本写法

```python
@app.on_event("startup")
async def startup_event():
    # 启动时执行的代码
    
@app.on_event("shutdown")
async def shutdown_event():
    # 关闭时执行的代码
```

### 现代写法的优势

1. **代码组织**：将相关的启动和关闭逻辑放在同一个函数中
2. **资源管理**：更容易确保资源在启动时创建，在关闭时被正确释放
3. **异常处理**：更好的异常处理机制
4. **可测试性**：更易于测试
5. **上下文传递**：启动逻辑中创建的变量可直接在关闭逻辑中使用

## 最佳实践

1. 为不同的资源或功能创建独立的 lifespan 函数
2. 按照依赖关系注册 lifespan 函数（被依赖的先注册）
3. 确保所有资源在关闭时被正确释放
4. 使用日志记录生命周期事件
5. 优雅处理异常，确保即使在异常情况下资源也能被正确释放
