from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from core import config
from api.routers import manage, tasks, webhook, config as config_router, rules, data, test
import logging
import sys
import asyncio
from asyncio import Queue

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

async def webhook_consumer(queue: Queue):
    """
    从队列中取出 webhook payload 并进行处理的消费者任务。
    """
    while True:
        payload = await queue.get()
        logger.info("消费者：从队列中取出 Webhook payload。")
        try:
            await webhook._process_webhook_payload(payload)
        except Exception as e:
            logger.error(f"消费者：处理 Webhook payload 时发生错误: {e}", exc_info=True)
        finally:
            queue.task_done()

@app.on_event("startup")
async def startup_event():
    logger.info(f"'Emby Auto Tags' 应用启动...")
    if not config.EMBY_SERVER_URL or not config.EMBY_API_KEY or not config.TMDB_API_KEY:
        logger.warning("警告：配置不完整，请检查 config/config.ini 文件。")
    else:
        logger.info("配置加载成功。")
    
    # 初始化 Webhook 队列
    webhook.webhook_queue = asyncio.Queue()
    logger.info("Webhook 队列已初始化。")

    # 启动 Webhook 消费者任务
    # 可以根据需要启动多个消费者来增加并发处理能力
    app.state.webhook_consumer_task = asyncio.create_task(webhook_consumer(webhook.webhook_queue))
    logger.info("Webhook 消费者任务已启动。")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("应用关闭中...")
    if webhook.webhook_queue:
        # 等待队列中的所有任务完成
        await webhook.webhook_queue.join()
        logger.info("Webhook 队列中的所有任务已处理完毕。")
    
    # 取消消费者任务
    if hasattr(app.state, 'webhook_consumer_task') and app.state.webhook_consumer_task:
        app.state.webhook_consumer_task.cancel()
        try:
            await app.state.webhook_consumer_task
        except asyncio.CancelledError:
            logger.info("Webhook 消费者任务已取消。")
    logger.info("应用已关闭。")
