from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()

# templates 目录位于 backend/ 目录下
templates = Jinja2Templates(directory="templates")

@router.get("/", include_in_schema=False)
async def root():
    """
    根路由，重定向到管理页面。
    """
    return RedirectResponse(url="/manage")

@router.get("/manage", tags=["Management"])
async def management_page(request: Request):
    """
    提供一个功能完善的前端管理和测试页面。
    """
    return templates.TemplateResponse("manage.html", {"request": request})
