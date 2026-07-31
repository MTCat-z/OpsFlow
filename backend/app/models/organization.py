from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel


class Organization(SQLModel, table=True):
    __tablename__ = 'organizations'
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(..., max_length=100)
    code: str = Field(..., max_length=50, unique=True)
    probe_url: Optional[str] = Field(default=None, max_length=500)
    probe_key: Optional[str] = Field(default=None, max_length=200)
    # WireGuard 探针 VPN
    wg_private_key: Optional[str] = Field(default=None, max_length=200)
    wg_public_key: Optional[str] = Field(default=None, max_length=200)
    wg_tunnel_ip: Optional[str] = Field(default=None, max_length=50)
    probe_last_heartbeat: Optional[datetime] = Field(default=None)
    dingtalk_webhook: Optional[str] = Field(default=None, max_length=500)
    dingtalk_secret: Optional[str] = Field(default=None, max_length=200)
    zabbix_url: Optional[str] = Field(default=None, max_length=500)
    zabbix_api_token: Optional[str] = Field(default=None, max_length=200)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class OrganizationCreate(SQLModel):
    name: str
    code: str
    dingtalk_webhook: Optional[str] = None
    dingtalk_secret: Optional[str] = None
    zabbix_url: Optional[str] = None
    zabbix_api_token: Optional[str] = None


class OrganizationUpdate(SQLModel):
    name: Optional[str] = None
    code: Optional[str] = None
    probe_url: Optional[str] = None
    dingtalk_webhook: Optional[str] = None
    dingtalk_secret: Optional[str] = None
    zabbix_url: Optional[str] = None
    zabbix_api_token: Optional[str] = None
    is_active: Optional[bool] = None


class OrganizationRead(SQLModel):
    id: int
    name: str
    code: str
    probe_url: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
