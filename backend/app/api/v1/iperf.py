from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from app.core.database import get_session
from app.core.auth import get_current_org, get_current_user, check_org_access
from app.models.user import User
from app.models.organization import Organization
from app.models.iperf_task import IperfTask, IperfTaskCreate, IperfTaskRead, IperfTaskResult

router = APIRouter()


def _resolve_org_id(session: Session, current_user: User, requested_org_id: Optional[int]) -> int:
    """确定任务归属的组织：
    - 普通用户：强制使用自己的 org_id，忽略请求参数
    - admin：必须显式指定 org_id（方案 A：admin 跨组织下发任务）"""
    if current_user.role == 'admin':
        if not requested_org_id:
            raise HTTPException(400, '管理员请选择目标组织')
        org = session.get(Organization, requested_org_id)
        if not org or not org.is_active:
            raise HTTPException(400, '目标组织不存在或已禁用')
        return requested_org_id
    if current_user.org_id is None:
        raise HTTPException(400, '当前用户未隶属任何组织')
    return current_user.org_id


def _ensure_probe_ready(session: Session, org_id: int):
    """探针守卫：无探针则拒绝创建任务（ADR-0003 第 5 条：无探针则拒绝）"""
    org = session.get(Organization, org_id)
    if not org or not org.probe_key:
        raise HTTPException(400, '该组织未配置探针，请先在组织管理生成探针')


@router.post('/start', response_model=IperfTaskRead, status_code=201)
def start_iperf(
    task_in: IperfTaskCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    org_id = _resolve_org_id(session, current_user, task_in.org_id)
    _ensure_probe_ready(session, org_id)
    task = IperfTask.model_validate(task_in)
    task.org_id = org_id
    task.status = 'pending'  # 等待探针拉取，不再调用 Celery
    session.add(task); session.commit(); session.refresh(task)
    return IperfTaskRead.model_validate(task)


@router.get('/tasks', response_model=dict)
def list_tasks(page: int=Query(1,ge=1), size: int=Query(20,ge=1,le=100), status: Optional[str]=None, org_id: Optional[int]=Depends(get_current_org), session: Session=Depends(get_session)):
    q = select(IperfTask).order_by(IperfTask.created_at.desc())
    if org_id is not None: q = q.where(IperfTask.org_id == org_id)
    if status: q = q.where(IperfTask.status==status)
    total = len(session.exec(q).all())
    tasks = session.exec(q.offset((page-1)*size).limit(size)).all()
    return {'total': total, 'page': page, 'size': size, 'items': [IperfTaskRead.model_validate(t) for t in tasks]}

@router.get('/tasks/{task_id}', response_model=IperfTaskResult)
def get_task(task_id: int, session: Session=Depends(get_session), current_user: User=Depends(get_current_user)):
    task = session.get(IperfTask, task_id)
    if not task or not check_org_access(task, current_user): raise HTTPException(404, '任务不存在')
    return IperfTaskResult.model_validate(task)

@router.delete('/tasks/{task_id}', status_code=204)
def delete_task(task_id: int, session: Session=Depends(get_session), current_user: User=Depends(get_current_user)):
    task = session.get(IperfTask, task_id)
    if not task or not check_org_access(task, current_user): raise HTTPException(404, '任务不存在')
    # 探针模式：任务由探针执行，删除时无需撤销 Celery
    session.delete(task); session.commit()
