from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from app.core.database import get_session
from app.core.auth import get_current_org
from app.models.iperf_task import IperfTask, IperfTaskCreate, IperfTaskRead, IperfTaskResult
from app.tasks.iperf_tasks import run_iperf_test

router = APIRouter()

@router.post('/start', response_model=IperfTaskRead, status_code=201)
def start_iperf(task_in: IperfTaskCreate, session: Session=Depends(get_session), org_id: Optional[int]=Depends(get_current_org)):
    task = IperfTask.model_validate(task_in)
    task.org_id = org_id
    session.add(task); session.commit(); session.refresh(task)
    def _send_task():
        try:
            from app.tasks.worker import celery_app
            celery_app.send_task('app.tasks.iperf_tasks.run_iperf_test', args=[task.id], countdown=2)
        except Exception:
            pass
    import threading
    threading.Thread(target=_send_task, daemon=True).start()
    task.status = 'pending'
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
def get_task(task_id: int, session: Session=Depends(get_session)):
    task = session.get(IperfTask, task_id)
    if not task: raise HTTPException(404, '任务不存在')
    return IperfTaskResult.model_validate(task)

@router.delete('/tasks/{task_id}', status_code=204)
def delete_task(task_id: int, session: Session=Depends(get_session)):
    task = session.get(IperfTask, task_id)
    if not task: raise HTTPException(404, '任务不存在')
    if task.celery_task_id and task.status in ('pending','running'):
        try:
            from app.tasks.worker import celery_app
            celery_app.control.revoke(task.celery_task_id, terminate=True)
        except: pass
    session.delete(task); session.commit()
