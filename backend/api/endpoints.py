from fastapi import APIRouter
from .routers import main, data, config, rules, test

# 主路由，包含所有子路由
api_router = APIRouter()

# 包含来自各个模块的路由
api_router.include_router(main.router)
api_router.include_router(data.router)
api_router.include_router(config.router)
api_router.include_router(rules.router)
api_router.include_router(test.router)
