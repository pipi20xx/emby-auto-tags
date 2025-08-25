from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from core import config
from api.routers import manage, tasks, webhook, config as config_router, rules, data, test
import logging
import sys

# 配置日志
logging.basicConfig(
    level=logging.DEBUG, # 将日志级别改为 DEBUG
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Emby Auto Tags",
    version="1.0.0",
    description="通过 Emby Webhook 自动为媒体打标签"
)

# 全局任务管理器，用于存储后台任务的状态
# 键为 task_id (str), 值为任务状态字典 (dict)
app.state.task_manager = {}

# 挂载静态文件目录
app.mount("/static", StaticFiles(directory="static"), name="static")

# 包含 API 路由
API_PREFIX = "/api"
app.include_router(manage.router)
app.include_router(tasks.router, prefix=API_PREFIX)
app.include_router(webhook.router, prefix=API_PREFIX)
app.include_router(config_router.router, prefix=API_PREFIX)
app.include_router(rules.router, prefix=API_PREFIX)
app.include_router(data.router, prefix=API_PREFIX)
app.include_router(test.router, prefix=API_PREFIX)

@app.on_event("startup")
async def startup_event():
    logger.info(f"'Emby Auto Tags' 应用启动...")
    if not config.EMBY_SERVER_URL or not config.EMBY_API_KEY or not config.TMDB_API_KEY:
        logger.warning("警告：配置不完整，请检查 config/config.ini 文件。")
    else:
        logger.info("配置加载成功。")
