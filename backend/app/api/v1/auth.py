"""
认证相关路由：登录、修改密码
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session

from app.core.auth import (
    verify_password, create_access_token, get_current_user,
    hash_password, check_lockout, record_failed_login, clear_failed_login,
    audit,
)
from app.core.database import get_session
from app.models.user import User, ChangePassword

router = APIRouter()


@router.post("/login", summary="登录")
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
):
    username = form_data.username
    # 检查锁定
    check_lockout(username)

    from sqlmodel import select
    user = session.exec(select(User).where(User.username == username)).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        record_failed_login(username)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用")

    clear_failed_login(username)
    token = create_access_token(user)

    # 记录登录审计
    request.state.current_user = user
    audit(request, "login", "auth", detail=f"用户 {username} 登录成功", session=session)

    return {
        "access_token": token,
        "token_type": "bearer",
        "username": user.username,
        "role": user.role,
        "org_id": user.org_id,
        "must_change_password": user.must_change_password,
    }


@router.post("/change-password", summary="修改密码")
def change_password(
    request: Request,
    data: ChangePassword,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if not verify_password(data.old_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="原密码错误")

    if len(data.new_password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="新密码至少 6 位")

    user.password_hash = hash_password(data.new_password)
    user.must_change_password = False
    from datetime import datetime
    user.updated_at = datetime.utcnow()
    session.add(user)
    session.commit()

    audit(request, "update", "user", str(user.id), f"用户 {user.username} 修改密码", session=session)
    return {"message": "密码修改成功"}
