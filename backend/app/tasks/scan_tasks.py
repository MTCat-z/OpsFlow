import json
import re
import ipaddress
from datetime import datetime
from typing import Optional
from sqlmodel import Session
from app.tasks.worker import celery_app
from app.core.config import settings
from app.core.database import engine
from app.models.scan_task import ScanTask


def _is_rfc1918(target: str) -> bool:
    allowed = [ipaddress.ip_network(n, strict=False) for n in settings.ALLOWED_SCAN_NETWORKS]
    try:
        net = ipaddress.ip_network(target, strict=False)
        return any(net.subnet_of(a) or net.overlaps(a) for a in allowed)
    except ValueError:
        try:
            addr = ipaddress.ip_address(target.split('/')[0])
            return any(addr in a for a in allowed)
        except ValueError:
            return False


@celery_app.task(bind=True, name='app.tasks.scan_tasks.run_nmap_scan')
def run_nmap_scan(self, task_id: int):
    import nmap
    # 在 Session 内读取任务数据并提取到局部变量
    with Session(engine) as session:
        task = session.get(ScanTask, task_id)
        if not task:
            return {'error': f'Task {task_id} not found'}
        target = task.target
        scan_type = task.scan_type
        ports = task.ports
        if not _is_rfc1918(target):
            task.status = 'failed'
            task.error_message = f'目标 {target} 不在允许的内网范围内'
            task.finished_at = datetime.utcnow()
            session.add(task); session.commit()
            return {'error': task.error_message}
        task.status = 'running'
        task.started_at = datetime.utcnow()
        task.celery_task_id = self.request.id
        session.add(task); session.commit()
    try:
        nm = nmap.PortScanner()
        if ports and not re.match(r'^[\d,\-]+$', ports):
            with Session(engine) as session:
                task = session.get(ScanTask, task_id)
                if task:
                    task.status = 'failed'
                    task.error_message = f'ports 字段格式非法: {ports}'
                    task.finished_at = datetime.utcnow()
                    session.add(task); session.commit()
            return {'error': f'ports 字段格式非法: {ports}'}
        scan_args = _build_nmap_args(scan_type, ports)
        nm.scan(hosts=target, arguments=scan_args)
        result = _parse_nmap_result(nm)
        with Session(engine) as session:
            task = session.get(ScanTask, task_id)
            task.status = 'completed'; task.progress = 100
            task.result_json = json.dumps(result, ensure_ascii=False)
            task.host_count = result.get('host_count', 0)
            task.port_count = result.get('port_count', 0)
            task.finished_at = datetime.utcnow()
            session.add(task); session.commit()
        return {'status': 'completed'}
    except Exception as e:
        with Session(engine) as session:
            task = session.get(ScanTask, task_id)
            if task:
                task.status = 'failed'; task.error_message = str(e)[:500]
                task.finished_at = datetime.utcnow()
                session.add(task); session.commit()
        raise


def _build_nmap_args(scan_type, ports):
    args_map = {'ping': '-sn', 'port': '-sS --open', 'service': '-sV --open', 'full': '-sV -O --open'}
    base = args_map.get(scan_type, '-sn')
    if ports and scan_type != 'ping': base += f' -p {ports}'
    return base


def _parse_nmap_result(nm):
    hosts = []; port_count = 0
    for host in nm.all_hosts():
        hi = {'ip': host, 'hostname': nm[host].hostname(), 'state': nm[host].state(), 'ports': []}
        for proto in nm[host].all_protocols():
            for port in sorted(nm[host][proto].keys()):
                pi = nm[host][proto][port]
                if pi['state'] == 'open':
                    hi['ports'].append({'port': port, 'protocol': proto, 'state': pi['state'], 'service': pi.get('name',''), 'version': pi.get('version','')})
                    port_count += 1
        hosts.append(hi)
    return {'hosts': hosts, 'host_count': len([h for h in hosts if h['state']=='up']), 'port_count': port_count}
