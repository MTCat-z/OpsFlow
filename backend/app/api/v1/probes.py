"""
探针 API - 探针拉取任务、回传结果、心跳上报
"""
import os
import zipfile
import io
import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Request, Response
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.auth import get_current_user
from app.models.user import User
from app.models.organization import Organization
from app.models.scan_task import ScanTask
from app.models.iperf_task import IperfTask
from app.services.wireguard_service import (
    generate_probe_key, generate_wireguard_keypair,
    allocate_tunnel_ip, add_peer, remove_peer, get_server_public_key,
    WG_SERVER_TUNNEL_IP,
)

router = APIRouter(prefix='/probes', tags=['探针'])


def verify_probe_key(
    x_probe_key: str = Header(...),
    x_org_code: str = Header(...),
    session: Session = Depends(get_session),
) -> Organization:
    """验证探针密钥"""
    org = session.exec(
        select(Organization).where(
            Organization.code == x_org_code,
            Organization.probe_key == x_probe_key,
            Organization.is_active == True,
        )
    ).first()
    if not org:
        raise HTTPException(401, '探针认证失败')
    return org


@router.get('/tasks', summary='探针拉取待执行任务')
def get_probe_tasks(
    org: Organization = Depends(verify_probe_key),
    session: Session = Depends(get_session),
):
    """探针拉取该组织待执行的扫描和测速任务"""
    tasks = []
    # 拉取 pending 的扫描任务
    scan_tasks = session.exec(
        select(ScanTask).where(
            ScanTask.org_id == org.id,
            ScanTask.status == 'pending',
        )
    ).all()
    for t in scan_tasks:
        t.status = 'running'
        t.started_at = datetime.utcnow()
        tasks.append({
            'id': f'scan_{t.id}',
            'type': 'scan',
            'task_id': t.id,
            'target': t.target,
            'scan_type': t.scan_type,
            'ports': t.ports,
        })

    # 拉取 pending 的测速任务
    iperf_tasks = session.exec(
        select(IperfTask).where(
            IperfTask.org_id == org.id,
            IperfTask.status == 'pending',
        )
    ).all()
    for t in iperf_tasks:
        t.status = 'running'
        t.started_at = datetime.utcnow()
        tasks.append({
            'id': f'iperf_{t.id}',
            'type': 'iperf',
            'task_id': t.id,
            'server_host': t.server_host,
            'server_port': t.server_port,
            'protocol': t.protocol,
            'duration': t.duration,
            'parallel': t.parallel,
            'reverse': t.reverse,
        })

    session.commit()
    return {'tasks': tasks}


@router.post('/tasks/{task_type}/{task_id}/result', summary='探针回传结果')
def submit_task_result(
    task_type: str,
    task_id: int,
    result: dict,
    org: Organization = Depends(verify_probe_key),
    session: Session = Depends(get_session),
):
    """探针回传扫描/测速结果"""
    if task_type == 'scan':
        task = session.get(ScanTask, task_id)
        if not task or task.org_id != org.id:
            raise HTTPException(404, '任务不存在')
        task.status = 'completed' if result.get('success') else 'failed'
        task.result_json = result.get('result_json', '')
        task.host_count = result.get('host_count', 0)
        task.port_count = result.get('port_count', 0)
        task.error_message = result.get('error_message', '')
        task.progress = 100
        task.finished_at = datetime.utcnow()
    elif task_type == 'iperf':
        task = session.get(IperfTask, task_id)
        if not task or task.org_id != org.id:
            raise HTTPException(404, '任务不存在')
        task.status = 'completed' if result.get('success') else 'failed'
        task.bandwidth_mbps = result.get('bandwidth_mbps')
        task.jitter_ms = result.get('jitter_ms')
        task.lost_percent = result.get('lost_percent')
        task.retransmits = result.get('retransmits')
        task.result_json = result.get('result_json', '')
        task.error_message = result.get('error_message', '')
        task.finished_at = datetime.utcnow()
    else:
        raise HTTPException(400, '未知任务类型')

    session.add(task)
    session.commit()
    return {'success': True}


@router.post('/heartbeat', summary='探针心跳上报')
def probe_heartbeat(
    org: Organization = Depends(verify_probe_key),
    session: Session = Depends(get_session),
):
    """探针定时心跳，更新最后心跳时间"""
    org.probe_last_heartbeat = datetime.utcnow()
    session.add(org)
    session.commit()
    return {'success': True, 'server_time': datetime.utcnow().isoformat()}


@router.get('/targets', summary='可用测速目标（中心 + 各在线探针）')
def list_iperf_targets(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """供前端创建测速任务时选择 iperf3 服务端目标：
    - 中心服务器（隧道 IP，常驻 iperf3 服务端）
    - 各在线探针（兼作 iperf3 服务端，仅在线时可测）"""
    now = datetime.utcnow()
    targets = [{
        'type': 'central',
        'name': '中心服务器',
        'host': WG_SERVER_TUNNEL_IP,
        'port': 5201,
        'online': True,
    }]
    orgs = session.exec(
        select(Organization).where(Organization.probe_key.isnot(None))
    ).all()
    for o in orgs:
        if not o.wg_tunnel_ip:
            continue
        online = bool(
            o.probe_last_heartbeat
            and (now - o.probe_last_heartbeat).total_seconds() <= 300
        )
        targets.append({
            'type': 'probe',
            'org_id': o.id,
            'name': o.name,
            'code': o.code,
            'host': o.wg_tunnel_ip,
            'port': 5201,
            'online': online,
        })
    return {'targets': targets}
