"""仪表盘面板模型 — Grafana 风格可配置面板

按 org_id 隔离存储面板配置，支持拖拽布局和多种数据源。
"""
from datetime import datetime
from typing import Optional, Dict, Any
from sqlmodel import Field, SQLModel, Column, JSON


class DashboardPanel(SQLModel, table=True):
    __tablename__ = 'dashboard_panels'
    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: Optional[int] = Field(default=None, index=True)
    title: str = Field(max_length=100)
    # 数据源类型: zabbix_item | iperf_recent | scan_recent | zabbix_problems | probe_status
    source_type: str = Field(max_length=30)
    # 数据源配置 JSON，结构随 source_type 而变：
    #   zabbix_item:     {host_id, item_key, period}
    #   iperf_recent:    {}
    #   scan_recent:     {}
    #   zabbix_problems: {}
    #   probe_status:    {}
    source_config: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    # 图表类型: line | stat | table
    chart_type: str = Field(default='stat', max_length=20)
    # 网格位置 JSON: {x, y, w, h}（vue-grid-layout 坐标系）
    grid_position: Dict[str, Any] = Field(
        default_factory=lambda: {'x': 0, 'y': 0, 'w': 6, 'h': 4},
        sa_column=Column(JSON),
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DashboardPanelCreate(SQLModel):
    title: str
    source_type: str
    source_config: Dict[str, Any] = Field(default_factory=dict)
    chart_type: str = 'stat'
    grid_position: Dict[str, Any] = Field(
        default_factory=lambda: {'x': 0, 'y': 0, 'w': 6, 'h': 4}
    )


class DashboardPanelUpdate(SQLModel):
    title: Optional[str] = None
    source_type: Optional[str] = None
    source_config: Optional[Dict[str, Any]] = None
    chart_type: Optional[str] = None
    grid_position: Optional[Dict[str, Any]] = None


class DashboardPanelRead(SQLModel):
    id: int
    org_id: Optional[int]
    title: str
    source_type: str
    source_config: Dict[str, Any]
    chart_type: str
    grid_position: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
