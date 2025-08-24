from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from core import config
from api import endpoints

app = FastAPI(
    title="Emby Auto Tags",
    version="1.0.0",
    description="通过 Emby Webhook 自动为媒体打标签"
)

# 包含 API 路由
API_PREFIX = "/api"
app.include_router(endpoints.api_router, prefix=API_PREFIX)

@app.get("/")
async def root_redirect():
    return RedirectResponse(url="/api/manage")

@app.on_event("startup")
async def startup_event():
    print(f"'Emby Auto Tags' 应用启动...")
    if not config.EMBY_SERVER_URL or not config.EMBY_API_KEY or not config.TMDB_API_KEY:
        print("警告：配置不完整，请检查 config/config.ini 文件。")
    else:
        print("配置加载成功。")
