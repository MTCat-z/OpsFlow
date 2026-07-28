from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel


# ---------- 拓扑节点 ----------

class TopologyNodeBase(SQLModel):
    org_id: Optional[int] = Field(default=None, index=True)
    name: str = Field(..., max_length=100)
    ip_address: Optional[str] = Field(default=None, max_length=50)
    mac_address: Optional[str] = Field(default=None, max_length=20)
    device_type: str = Field(default='unknown', max_length=30)
    vendor: Optional[str] = Field(default=None, max_length=100)
    subnet: Optional[str] = Field(default=None, max_length=50)
    position_x: float = Field(default=0.0)
    position_y: float = Field(default=0.0)
    asset_id: Optional[int] = Field(default=None)
    is_manual: bool = Field(default=False)
    discovery_task_id: Optional[int] = Field(default=None)
    icon: Optional[str] = Field(default=None, max_length=50)
    metadata_json: Optional[str] = Field(default=None)


class TopologyNode(TopologyNodeBase, table=True):
    __tablename__ = 'topology_nodes'
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class TopologyNodeCreate(SQLModel):
    name: str
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    device_type: str = 'unknown'
    vendor: Optional[str] = None
    subnet: Optional[str] = None
    position_x: float = 0.0
    position_y: float = 0.0
    icon: Optional[str] = None
    metadata_json: Optional[str] = None


class TopologyNodeUpdate(SQLModel):
    name: Optional[str] = None
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    device_type: Optional[str] = None
    vendor: Optional[str] = None
    subnet: Optional[str] = None
    position_x: Optional[float] = None
    position_y: Optional[float] = None
    asset_id: Optional[int] = None
    icon: Optional[str] = None
    metadata_json: Optional[str] = None


class TopologyNodeRead(TopologyNodeBase):
    id: int
    created_at: datetime
    updated_at: datetime


# ---------- 拓扑连线 ----------

class TopologyEdgeBase(SQLModel):
    org_id: Optional[int] = Field(default=None, index=True)
    source_node_id: int
    target_node_id: int
    link_type: str = Field(default='ethernet', max_length=30)
    bandwidth_mbps: Optional[float] = Field(default=None)
    interface_source: Optional[str] = Field(default=None, max_length=50)
    interface_target: Optional[str] = Field(default=None, max_length=50)
    is_manual: bool = Field(default=False)
    discovery_task_id: Optional[int] = Field(default=None)
    style: Optional[str] = Field(default='solid', max_length=30)


class TopologyEdge(TopologyEdgeBase, table=True):
    __tablename__ = 'topology_edges'
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TopologyEdgeCreate(SQLModel):
    source_node_id: int
    target_node_id: int
    link_type: str = 'ethernet'
    bandwidth_mbps: Optional[float] = None
    interface_source: Optional[str] = None
    interface_target: Optional[str] = None
    style: Optional[str] = 'solid'


class TopologyEdgeRead(TopologyEdgeBase):
    id: int
    created_at: datetime


# ---------- 发现任务 ----------

class TopologyDiscoveryTaskBase(SQLModel):
    target_subnet: str = Field(..., max_length=100)
    scan_type: str = Field(default='discovery', max_length=20)
    org_id: Optional[int] = Field(default=None, index=True)


class TopologyDiscoveryTask(TopologyDiscoveryTaskBase, table=True):
    __tablename__ = 'topology_discovery_tasks'
    id: Optional[int] = Field(default=None, primary_key=True)
    celery_task_id: Optional[str] = Field(default=None, max_length=100)
    status: str = Field(default='pending', max_length=20)
    progress: int = Field(default=0)
    nodes_discovered: int = Field(default=0)
    edges_inferred: int = Field(default=0)
    result_json: Optional[str] = Field(default=None)
    error_message: Optional[str] = Field(default=None, max_length=1000)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TopologyDiscoveryTaskCreate(SQLModel):
    target_subnet: str
    scan_type: str = 'discovery'


class TopologyDiscoveryTaskRead(TopologyDiscoveryTaskBase):
    id: int
    celery_task_id: Optional[str]
    status: str
    progress: int
    nodes_discovered: int
    edges_inferred: int
    result_json: Optional[str]
    error_message: Optional[str]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    created_at: datetime
