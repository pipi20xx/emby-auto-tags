from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.status import HTTP_302_FOUND
from typing import Optional
from jose import jwt, JWTError
from datetime import datetime, timedelta
from services.config_service import get_config

# 简单的内存存储，用于演示
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

router = APIRouter()

# templates 目录位于 backend/ 目录下
templates = Jinja2Templates(directory="templates")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    config = get_config().get('LOGIN', {})
    secret_key = config.get('secret_key')
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(request: Request):
    config = get_config().get('LOGIN', {})
    if config.get('enabled') != 'true':
        return "guest"  # 如果禁用了登录，则返回一个访客用户

    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        secret_key = config.get('secret_key')
        payload = jwt.decode(token, secret_key, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        return username
    except JWTError:
        return None

@router.get("/", include_in_schema=False)
async def root():
    """
    根路由，重定向到管理页面。
    """
    return RedirectResponse(url="/manage")

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    config = get_config().get('LOGIN', {})
    correct_username = config.get('username')
    correct_password = config.get('password')

    if username == correct_username and password == correct_password:
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": username}, expires_delta=access_token_expires
        )
        response = RedirectResponse(url="/manage", status_code=HTTP_302_FOUND)
        response.set_cookie(key="access_token", value=access_token, httponly=True)
        return response
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid username or password"})

@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie("access_token")
    return response

@router.get("/manage", tags=["Management"])
async def management_page(request: Request, current_user: str = Depends(get_current_user)):
    """
    提供一个功能完善的前端管理和测试页面。
    """
    if not current_user:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("manage.html", {"request": request})
