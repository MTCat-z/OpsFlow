import json
import threading
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, col
from app.core.database import get_session
from app.core.auth import get_current_org
from app.models.topology import (
    TopologyNode, TopologyNodeCreate, TopologyNodeUpdate, TopologyNodeRead,
    TopologyEdge, TopologyEdgeCreate, TopologyEdgeRead,
    TopologyDiscoveryTask, TopologyDiscoveryTaskCreate, TopologyDiscoveryTaskRead,
)
from app.models.asset import Asset

router = APIRouter()


# ---------- 拓扑图数据 ----------

@router.get('/graph', summary='获取完整拓扑图')
def get_graph(
    subnet: Optional[str] = None,
    org_id: Optional[int] = Depends(get_current_org),
    session: Session = Depends(get_session),
):
    q_nodes = select(TopologyNode)
    q_edges = select(TopologyEdge)
    if org_id is not None:
        q_nodes = q_nodes.where(TopologyNode.org_id == org_id)
        q_edges = q_edges.where(TopologyEdge.org_id == org_id)
    if subnet:
        q_nodes = q_nodes.where(TopologyNode.subnet == subnet)
        node_ids = [n.id for n in session.exec(q_nodes).all()]
        if node_ids:
            q_edges = q_edges.where(
                col(TopologyEdge.source_node_id).in_(node_ids)
                | col(TopologyEdge.target_node_id).in_(node_ids)
            )
        else:
            return {'nodes': [], 'edges': []}
    nodes = session.exec(q_nodes).all()
    edges = session.exec(q_edges).all()
    return {'nodes': nodes, 'edges': edges}


# ---------- 节点管理 ----------

@router.post('/nodes', response_model=TopologyNodeRead, status_code=201)
def create_node(data: TopologyNodeCreate, session: Session = Depends(get_session), org_id: Optional[int] = Depends(get_current_org)):
    node = TopologyNode.model_validate(data, update={'is_manual': True})
    node.org_id = org_id
    session.add(node)
    session.commit()
    session.refresh(node)
    return node


@router.put('/nodes/{node_id}', response_model=TopologyNodeRead)
def update_node(node_id: int, data: TopologyNodeUpdate, session: Session = Depends(get_session)):
    node = session.get(TopologyNode, node_id)
    if not node:
        raise HTTPException(404, '节点不存在')
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(node, k, v)
    node.updated_at = datetime.utcnow()
    session.add(node)
    session.commit()
    session.refresh(node)
    return node


@router.patch('/nodes/{node_id}/position', response_model=TopologyNodeRead)
def update_node_position(node_id: int, data: dict, session: Session = Depends(get_session)):
    node = session.get(TopologyNode, node_id)
    if not node:
        raise HTTPException(404, '节点不存在')
    if 'position_x' in data:
        node.position_x = float(data['position_x'])
    if 'position_y' in data:
        node.position_y = float(data['position_y'])
    node.updated_at = datetime.utcnow()
    session.add(node)
    session.commit()
    session.refresh(node)
    return node


@router.delete('/nodes/{node_id}', status_code=204)
def delete_node(node_id: int, session: Session = Depends(get_session)):
    node = session.get(TopologyNode, node_id)
    if not node:
        raise HTTPException(404, '节点不存在')
    # 删除关联的边
    edges = session.exec(
        select(TopologyEdge).where(
            (TopologyEdge.source_node_id == node_id) | (TopologyEdge.target_node_id == node_id)
        )
    ).all()
    for edge in edges:
        session.delete(edge)
    session.delete(node)
    session.commit()


# ---------- 连线管理 ----------

@router.post('/edges', response_model=TopologyEdgeRead, status_code=201)
def create_edge(data: TopologyEdgeCreate, session: Session = Depends(get_session)):
    # 验证节点存在
    src = session.get(TopologyNode, data.source_node_id)
    tgt = session.get(TopologyNode, data.target_node_id)
    if not src or not tgt:
        raise HTTPException(400, '源节点或目标节点不存在')
    edge = TopologyEdge.model_validate(data, update={'is_manual': True})
    session.add(edge)
    session.commit()
    session.refresh(edge)
    return edge


@router.delete('/edges/{edge_id}', status_code=204)
def delete_edge(edge_id: int, session: Session = Depends(get_session)):
    edge = session.get(TopologyEdge, edge_id)
    if not edge:
        raise HTTPException(404, '连线不存在')
    session.delete(edge)
    session.commit()


# ---------- 自动发现 ----------

@router.post('/discover', response_model=TopologyDiscoveryTaskRead, status_code=201)
def start_discovery(data: TopologyDiscoveryTaskCreate, session: Session = Depends(get_session)):
    task = TopologyDiscoveryTask.model_validate(data)
    session.add(task)
    session.commit()
    session.refresh(task)

    def _dispatch():
        from app.tasks.worker import celery_app
        celery_app.send_task(
            'app.tasks.topology_tasks.run_topology_discovery',
            args=[task.id],
            countdown=2,
        )

    threading.Thread(target=_dispatch, daemon=True).start()
    task.status = 'pending'
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@router.get('/discover/tasks', response_model=dict, summary='发现任务列表')
def list_discovery_tasks(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
):
    q = select(TopologyDiscoveryTask)
    total = len(session.exec(q).all())
    items = session.exec(q.offset((page - 1) * size).limit(size)).all()
    return {'total': total, 'page': page, 'size': size, 'items': items}


@router.get('/discover/tasks/{task_id}', response_model=TopologyDiscoveryTaskRead)
def get_discovery_task(task_id: int, session: Session = Depends(get_session)):
    task = session.get(TopologyDiscoveryTask, task_id)
    if not task:
        raise HTTPException(404, '任务不存在')
    return task


@router.delete('/discover/tasks/{task_id}', status_code=204)
def delete_discovery_task(task_id: int, session: Session = Depends(get_session)):
    task = session.get(TopologyDiscoveryTask, task_id)
    if not task:
        raise HTTPException(404, '任务不存在')
    if task.status == 'running':
        raise HTTPException(400, '运行中的任务不能删除')
    # 删除该任务产生的节点和边
    nodes = session.exec(
        select(TopologyNode).where(TopologyNode.discovery_task_id == task_id)
    ).all()
    node_ids = [n.id for n in nodes]
    if node_ids:
        related_edges = session.exec(
            select(TopologyEdge).where(
                col(TopologyEdge.source_node_id).in_(node_ids)
                | col(TopologyEdge.target_node_id).in_(node_ids)
            )
        ).all()
        for edge in related_edges:
            session.delete(edge)
    for node in nodes:
        session.delete(node)
    session.delete(task)
    session.commit()


# ---------- 导入到资产管理 ----------

@router.post('/import/{node_id}', summary='将节点导入资产管理')
def import_node_to_asset(node_id: int, data: Optional[dict] = None, session: Session = Depends(get_session)):
    node = session.get(TopologyNode, node_id)
    if not node:
        raise HTTPException(404, '节点不存在')
    if node.asset_id:
        raise HTTPException(400, '该节点已关联资产')

    extra = data or {}
    asset = Asset(
        name=extra.get('name', node.name),
        ip_address=node.ip_address or '0.0.0.0',
        device_type=extra.get('device_type', node.device_type),
        location=extra.get('location', ''),
        status='active',
    )
    session.add(asset)
    session.flush()

    node.asset_id = asset.id
    node.updated_at = datetime.utcnow()
    session.add(node)
    session.commit()
    session.refresh(asset)
    return {
        'id': asset.id,
        'name': asset.name,
        'ip_address': asset.ip_address,
        'device_type': asset.device_type,
    }


@router.post('/import/batch', summary='批量导入节点到资产')
def import_batch(data: dict, session: Session = Depends(get_session)):
    node_ids = data.get('node_ids', [])
    defaults = data.get('defaults', {})
    imported = 0
    skipped = 0
    for nid in node_ids:
        node = session.get(TopologyNode, nid)
        if not node or node.asset_id or not node.ip_address:
            skipped += 1
            continue
        asset = Asset(
            name=defaults.get('name_prefix', '') + node.name,
            ip_address=node.ip_address,
            device_type=defaults.get('device_type', node.device_type),
            location=defaults.get('location', ''),
            status='active',
        )
        session.add(asset)
        session.flush()
        node.asset_id = asset.id
        node.updated_at = datetime.utcnow()
        session.add(node)
        imported += 1
    session.commit()
    return {'imported': imported, 'skipped': skipped}
