from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel


# ========== User ==========

class UserBase(SQLModel):
    username: str = Field(..., max_length=50, unique=True)
    role: str = Field(default='user', max_length=20)
    is_active: bool = Field(default=True)
    org_id: Optional[int] = Field(default=None, foreign_key="organizations.id")


class User(UserBase, table=True):
    __tablename__ = 'users'
    id: Optional[int] = Field(default=None, primary_key=True)
    password_hash: str = Field(max_length=200)
    must_change_password: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class UserCreate(SQLModel):
    username: str
    password: str
    role: str = 'user'
    org_id: Optional[int] = None


class UserUpdate(SQLModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None
    org_id: Optional[int] = None


class UserRead(UserBase):
    id: int
    must_change_password: bool
    created_at: datetime
    updated_at: datetime
    org_id: Optional[int]


class ChangePassword(SQLModel):
    old_password: str
    new_password: str


class ResetPassword(SQLModel):
    new_password: str


# ========== AuditLog ==========

class AuditLog(SQLModel, table=True):
    __tablename__ = 'audit_logs'
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None)
    username: str = Field(max_length=50)
    action: str = Field(max_length=30)          # login, logout, create, update, delete
    resource_type: str = Field(max_length=50)    # user, asset, scan_task, ...
    resource_id: Optional[str] = Field(default=None, max_length=100)
    detail: Optional[str] = Field(default=None, max_length=500)
    ip_address: Optional[str] = Field(default=None, max_length=50)
    org_id: Optional[int] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AuditLogRead(SQLModel):
    id: int
    user_id: Optional[int]
    username: str
    action: str
    resource_type: str
    resource_id: Optional[str]
    detail: Optional[str]
    ip_address: Optional[str]
    created_at: datetime
