from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class IpamSubnetBase(SQLModel):
    org_id: Optional[int] = Field(default=None, index=True)
    cidr: str = Field(..., max_length=50)
    name: str = Field(..., max_length=100)
    location: Optional[str] = Field(default=None, max_length=200)
    vlan: Optional[str] = Field(default=None, max_length=50)
    gateway: Optional[str] = Field(default=None, max_length=50)
    dhcp_enabled: bool = Field(default=True)
    notes: Optional[str] = Field(default=None, max_length=1000)


class IpamSubnet(IpamSubnetBase, table=True):
    __tablename__ = "ipam_subnets"
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class IpamAddressBase(SQLModel):
    org_id: Optional[int] = Field(default=None, index=True)
    subnet_id: Optional[int] = Field(default=None, index=True)
    ip_address: str = Field(..., max_length=50, index=True)
    hostname: Optional[str] = Field(default=None, max_length=100)
    mac_address: Optional[str] = Field(default=None, max_length=20, index=True)
    status: str = Field(default="unknown", max_length=20, index=True)
    source: str = Field(default="manual", max_length=20)
    asset_id: Optional[int] = Field(default=None, index=True)
    last_seen_at: Optional[datetime] = Field(default=None)
    notes: Optional[str] = Field(default=None, max_length=1000)


class IpamAddress(IpamAddressBase, table=True):
    __tablename__ = "ipam_addresses"
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class IpamSubnetCreate(IpamSubnetBase):
    pass


class IpamSubnetUpdate(SQLModel):
    cidr: Optional[str] = None
    name: Optional[str] = None
    location: Optional[str] = None
    vlan: Optional[str] = None
    gateway: Optional[str] = None
    dhcp_enabled: Optional[bool] = None
    notes: Optional[str] = None


class IpamSubnetRead(IpamSubnetBase):
    id: int
    created_at: datetime
    updated_at: datetime


class IpamAddressCreate(IpamAddressBase):
    pass


class IpamAddressUpdate(SQLModel):
    subnet_id: Optional[int] = None
    ip_address: Optional[str] = None
    hostname: Optional[str] = None
    mac_address: Optional[str] = None
    status: Optional[str] = None
    source: Optional[str] = None
    asset_id: Optional[int] = None
    last_seen_at: Optional[datetime] = None
    notes: Optional[str] = None


class IpamAddressRead(IpamAddressBase):
    id: int
    created_at: datetime
    updated_at: datetime
