"""
内网运维集成工具平台 - FastAPI 主入口
"""
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import create_db_and_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库并创建默认管理员"""
    if settings.SECRET_KEY == "change-me-in-production":
        print("[init] ⚠️ 严重安全警告: SECRET_KEY 使用默认值，请立即在 .env 中修改！")
    create_db_and_tables()
    _seed_default_admin()
    yield


def _seed_default_admin():
    """如果不存在 admin 用户，自动创建默认管理员"""
    from sqlmodel import Session, select
    from app.core.database import engine
    from app.core.auth import hash_password
    from app.models.user import User

    with Session(engine) as session:
        admin_count = len(session.exec(select(User).where(User.role == "admin")).all())
        if admin_count == 0:
            password = settings.DEFAULT_ADMIN_PASSWORD or secrets.token_urlsafe(12)
            admin = User(
                username=settings.DEFAULT_ADMIN_USERNAME,
                password_hash=hash_password(password),
                role="admin",
                org_id=None,
                must_change_password=True,
            )
            session.add(admin)
            session.commit()
            print(f"[init] 已创建默认管理员: {settings.DEFAULT_ADMIN_USERNAME}")
            print(f"[init] 默认管理员密码: {password}")
            print(f"[init] ⚠️ 请立即登录并修改默认密码！")


app = FastAPI(
    title="内网运维集成工具平台",
    description="资产台账 + Nmap 内网扫描 + Iperf3 网络性能测试 + 在线终端 + 网络拓扑",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS — 内网环境，允许局域网前端访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由
app.include_router(api_router, prefix="/api/v1")


# WebSocket 终端
@app.websocket("/ws/terminal/{asset_id}")
async def ws_terminal(websocket: WebSocket, asset_id: int):
    from app.api.v1.terminal import terminal_ws_handler
    await terminal_ws_handler(websocket, asset_id)


@app.get("/api/health", tags=["健康检查"])
async def health_check():
    return JSONResponse({"status": "ok", "service": "ops-platform"})
