from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel

class AssetBase(SQLModel):
    org_id: Optional[int] = Field(default=None, index=True)
    name: str = Field(..., max_length=100)
    ip_address: str = Field(..., max_length=50, index=True)
    device_type: Optional[str] = Field(default=None, max_length=50)
    model: Optional[str] = Field(default=None, max_length=100)
    location: Optional[str] = Field(default=None, max_length=200)
    owner: Optional[str] = Field(default=None, max_length=100)
    purpose: Optional[str] = Field(default=None, max_length=200)
    os: Optional[str] = Field(default=None, max_length=100)
    tags: Optional[str] = Field(default=None, max_length=500)
    notes: Optional[str] = Field(default=None, max_length=2000)
    status: str = Field(default='active', max_length=20, index=True)


class Asset(AssetBase, table=True):
    __tablename__ = 'assets'
    id: Optional[int] = Field(default=None, primary_key=True)
    username_encrypted: Optional[str] = Field(default=None)
    password_encrypted: Optional[str] = Field(default=None)
    enable_password_encrypted: Optional[str] = Field(default=None)
    ssh_private_key_encrypted: Optional[str] = Field(default=None)
    auth_type: str = Field(default='password', max_length=20)
    ssh_port: int = Field(default=22)
    protocol: str = Field(default='ssh', max_length=20)
    created_at: datetime = Field(default_factory=datetime.utcnow)  
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AssetCreate(AssetBase):
    username: Optional[str] = None
    password: Optional[str] = None
    enable_password: Optional[str] = None
    ssh_private_key: Optional[str] = None
    auth_type: str = 'password'
    ssh_port: int = 22
    protocol: str = 'ssh'


class AssetUpdate(SQLModel):
    name: Optional[str] = None
    ip_address: Optional[str] = None
    device_type: Optional[str] = None
    model: Optional[str] = None
    location: Optional[str] = None
    owner: Optional[str] = None
    purpose: Optional[str] = None
    os: Optional[str] = None
    tags: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    enable_password: Optional[str] = None
    ssh_private_key: Optional[str] = None
    auth_type: Optional[str] = None
    ssh_port: Optional[int] = None
    protocol: Optional[str] = None


class AssetRead(AssetBase):
    id: int
    ssh_port: int
    protocol: str
    auth_type: str
    has_credentials: bool = False
    has_ssh_key: bool = False
    created_at: datetime
    updated_at: datetime


class AssetCredentials(SQLModel):
    username: Optional[str] = None
    password: Optional[str] = None
    enable_password: Optional[str] = None
    ssh_private_key: Optional[str] = None
    auth_type: str = 'password'
    ssh_port: int = 22
    protocol: str = 'ssh'
