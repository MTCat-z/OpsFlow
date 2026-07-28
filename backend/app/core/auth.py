"""
JWT 认证、角色校验、审计日志 — FastAPI 依赖
"""
import time
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlmodel import Session, select

from app.core.config import settings
from app.core.database import get_session
from app.models.user import User, AuditLog

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

# 登录失败计数 {username: [(timestamp, ...)] }
_login_attempts: dict[str, list[float]] = {}
LOCKOUT_THRESHOLD = 5
LOCKOUT_SECONDS = 15 * 60


def hash_password(password: str) -> str:
    # bcrypt 5.x 要求手动截断到 72 字节
    pwd_bytes = password.encode("utf-8")[:72]
    return bcrypt.hashpw(pwd_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    pwd_bytes = plain.encode("utf-8")[:72]
    return bcrypt.checkpw(pwd_bytes, hashed.encode("utf-8"))


def check_lockout(username: str):
    """检查账号是否被锁定"""
    now = time.time()
    attempts = _login_attempts.get(username, [])
    # 清除过期记录
    attempts = [t for t in attempts if now - t < LOCKOUT_SECONDS]
    _login_attempts[username] = attempts
    if len(attempts) >= LOCKOUT_THRESHOLD:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"登录失败次数过多，请 {LOCKOUT_SECONDS // 60} 分钟后重试",
        )


def record_failed_login(username: str):
    _login_attempts.setdefault(username, []).append(time.time())


def clear_failed_login(username: str):
    _login_attempts.pop(username, None)


def create_access_token(user: User) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "org_id": user.org_id,
        "must_change_password": user.must_change_password,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> User:
    """解析 JWT 并返回当前用户（所有需认证的路由都依赖此函数）"""
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 无效或已过期")

    user = session.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已禁用")
    # 把 request 挂上 user 供审计日志使用
    request.state.current_user = user
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """要求管理员角色"""
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return user


def get_current_org(user: User = Depends(get_current_user)) -> Optional[int]:
    """返回当前用户的 org_id，admin 返回 None（不过滤）"""
    if user.role == "admin":
        return None
    return user.org_id


def require_org_admin(user: User = Depends(get_current_user)) -> User:
    """要求管理员或场地管理员角色"""
    if user.role not in ("admin", "org_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return user


def audit(
    request: Request,
    action: str,
    resource_type: str,
    resource_id: str = None,
    detail: str = None,
    session: Session = None,
):
    """记录审计日志（非依赖函数，直接调用）"""
    user = getattr(request.state, "current_user", None)
    log = AuditLog(
        user_id=user.id if user else None,
        username=user.username if user else "anonymous",
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id else None,
        detail=detail,
        ip_address=request.client.host if request.client else None,
    )
    if session:
        session.add(log)
        session.commit()
