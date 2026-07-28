"""
用户管理路由（仅管理员）
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlmodel import Session, select

from app.core.auth import get_current_user, require_admin, hash_password, audit
from app.core.database import get_session
from app.models.user import User, UserCreate, UserUpdate, UserRead, ResetPassword

router = APIRouter()


@router.get("", summary="用户列表")
def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    q = select(User).order_by(User.created_at.desc())
    # org 过滤：非 admin 只返回同 org_id 的用户
    if current_user.role != "admin":
        q = q.where(User.org_id == current_user.org_id)
    if keyword:
        q = q.where(User.username.contains(keyword))
    items = session.exec(q.offset((page - 1) * size).limit(size)).all()
    total = len(session.exec(q).all())
    return {"total": total, "page": page, "size": size, "items": [UserRead.model_validate(u) for u in items]}


@router.post("", response_model=UserRead, status_code=201, summary="创建用户")
def create_user(
    request: Request,
    data: UserCreate,
    admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
):
    # 检查用户名是否重复
    existing = session.exec(select(User).where(User.username == data.username)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在")

    if len(data.password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="密码至少 6 位")

    if data.role not in ("admin", "org_admin", "user"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="角色只能是 admin、org_admin 或 user")

    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        role=data.role,
        org_id=data.org_id,
        must_change_password=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    audit(request, "create", "user", str(user.id), f"创建用户 {user.username} (角色: {user.role})", session=session)
    return UserRead.model_validate(user)


@router.put("/{user_id}", response_model=UserRead, summary="编辑用户")
def update_user(
    request: Request,
    user_id: int,
    data: UserUpdate,
    admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    changes = []
    if data.role is not None and data.role != user.role:
        if data.role not in ("admin", "user"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="角色只能是 admin 或 user")
        changes.append(f"角色: {user.role}→{data.role}")
        user.role = data.role
    if data.is_active is not None and data.is_active != user.is_active:
        changes.append(f"状态: {'启用' if data.is_active else '禁用'}")
        user.is_active = data.is_active

    user.updated_at = datetime.utcnow()
    session.add(user)
    session.commit()
    session.refresh(user)

    if changes:
        audit(request, "update", "user", str(user.id), f"编辑用户 {user.username}: {'; '.join(changes)}", session=session)
    return UserRead.model_validate(user)


@router.post("/{user_id}/reset-password", summary="重置密码")
def reset_password(
    request: Request,
    user_id: int,
    data: ResetPassword,
    admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    if len(data.new_password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="密码至少 6 位")

    user.password_hash = hash_password(data.new_password)
    user.must_change_password = True
    user.updated_at = datetime.utcnow()
    session.add(user)
    session.commit()

    audit(request, "update", "user", str(user.id), f"重置用户 {user.username} 的密码", session=session)
    return {"message": "密码已重置，用户下次登录需修改密码"}


@router.delete("/{user_id}", status_code=204, summary="删除用户")
def delete_user(
    request: Request,
    user_id: int,
    admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
):
    if user_id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能删除自己")

    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    # 检查是否为最后一个管理员
    if user.role == "admin":
        admin_count = len(session.exec(select(User).where(User.role == "admin", User.is_active == True)).all())
        if admin_count <= 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能删除最后一个管理员")

    username = user.username
    session.delete(user)
    session.commit()

    audit(request, "delete", "user", str(user_id), f"删除用户 {username}", session=session)
