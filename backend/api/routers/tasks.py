from fastapi import APIRouter, Body, BackgroundTasks, Request, HTTPException
from typing import Dict, Any, Literal
from services import emby_service
from core import config as core_config
import uuid
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

async def _run_tag_all_media_task(task_id: str, mode: Literal['merge', 'overwrite'], task_manager: Dict[str, Any]):
    """
    实际执行打标签任务的后台函数。
    """
    try:
        task_manager[task_id]["status"] = "running"
        logger.info(f"任务 {task_id}: 开始对所有媒体进行打标签操作 (模式: {mode})...")
        result = await emby_service.tag_all_media_items(mode=mode)
        task_manager[task_id].update(result)
        task_manager[task_id]["status"] = "completed"
        logger.info(f"任务 {task_id}: 打标签任务完成。结果: {result}")
    except Exception as e:
        task_manager[task_id]["status"] = "failed"
        task_manager[task_id]["error"] = str(e)
        logger.error(f"任务 {task_id}: 打标签任务失败: {e}")

@router.post("/tag_all_media", tags=["Tasks"])
async def tag_all_media(
    request: Request,
    background_tasks: BackgroundTasks,
    mode: Literal['merge', 'overwrite'] = Body('merge', embed=True)
):
    """
    触发对所有 Emby 媒体库中的电影和剧集进行打标签操作。
    操作将在后台执行。
    """
    task_id = str(uuid.uuid4())
    task_manager = request.app.state.task_manager
    task_manager[task_id] = {
        "task_id": task_id,
        "status": "pending",
        "mode": mode,
        "processed_count": 0,
        "updated_count": 0,
        "failed_count": 0,
        "start_time": core_config.get_current_time()
    }
    
    logger.info(f"收到请求：启动后台打标签任务 {task_id} (模式: {mode})...")
    background_tasks.add_task(_run_tag_all_media_task, task_id, mode, task_manager)
    return {"message": "打标签任务已在后台启动。", "task_id": task_id}

@router.get("/tag_all_media/status/{task_id}", tags=["Tasks"])
async def get_tag_all_media_status(request: Request, task_id: str):
    """
    获取指定打标签任务的当前状态。
    """
    task_manager = request.app.state.task_manager
    task_status = task_manager.get(task_id)
    if not task_status:
        raise HTTPException(status_code=404, detail="Task not found.")
    return task_status
