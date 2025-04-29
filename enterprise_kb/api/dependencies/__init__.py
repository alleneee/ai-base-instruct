"""依赖管理模块索引"""
# 从子模块导出常用依赖
from enterprise_kb.api.dependencies.services import (
    DbSession, DocumentRepo, DocumentSvc, SearchSvc, Processor
)
from enterprise_kb.api.dependencies.auth import (
    ActiveUser, UserWithReadPerm, UserWithWritePerm, AdminUser
)
from enterprise_kb.api.dependencies.common import (
    PaginationDep, SortDep
)
from enterprise_kb.api.dependencies.responses import response
