"""
组织管理 API - 多租户场地隔离
"""
import io
import zipfile
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.auth import get_current_user, require_admin, audit
from app.models.user import User
from app.models.organization import (
    Organization, OrganizationCreate, OrganizationUpdate, OrganizationRead,
)
from app.services.wireguard_service import (
    generate_probe_key, generate_wireguard_keypair,
    allocate_tunnel_ip, add_peer, remove_peer,
    get_server_public_key, get_central_public_ip,
    WG_TUNNEL_NETWORK, WG_LISTEN_PORT,
)

router = APIRouter(prefix='/organizations', tags=['组织管理'])


@router.get('', summary='组织列表')
def list_organizations(
    keyword: Optional[str] = None,
    session: Session = Depends(get_session),
    user: User = Depends(require_admin),
):
    q = select(Organization)
    if keyword:
        q = q.where(Organization.name.contains(keyword) | Organization.code.contains(keyword))
    orgs = session.exec(q.order_by(Organization.id)).all()
    # 附带用户数和资产数
    from app.models.asset import Asset
    result = []
    now = datetime.utcnow()
    for org in orgs:
        user_count = len(session.exec(select(User).where(User.org_id == org.id)).all())
        asset_count = len(session.exec(select(Asset).where(Asset.org_id == org.id)).all())
        probe_online = bool(
            org.probe_last_heartbeat
            and (now - org.probe_last_heartbeat).total_seconds() <= 300
        )
        result.append({
            **OrganizationRead.model_validate(org).model_dump(),
            'user_count': user_count,
            'asset_count': asset_count,
            'probe_online': probe_online,
            'probe_last_heartbeat': org.probe_last_heartbeat,
        })
    return {'items': result, 'total': len(result)}


@router.post('', summary='创建组织')
def create_organization(
    data: OrganizationCreate,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_admin),
):
    existing = session.exec(select(Organization).where(Organization.code == data.code)).first()
    if existing:
        raise HTTPException(400, f'组织编码 {data.code} 已存在')
    org = Organization(**data.model_dump())
    session.add(org)
    session.commit()
    session.refresh(org)
    audit(request, 'create', 'organization', org.id, f'创建组织: {org.name}', session)
    return OrganizationRead.model_validate(org).model_dump()


@router.put('/{org_id}', summary='更新组织')
def update_organization(
    org_id: int,
    data: OrganizationUpdate,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_admin),
):
    org = session.get(Organization, org_id)
    if not org:
        raise HTTPException(404, '组织不存在')
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(org, k, v)
    org.updated_at = datetime.utcnow()
    session.add(org)
    session.commit()
    session.refresh(org)
    audit(request, 'update', 'organization', org.id, f'更新组织: {org.name}', session)
    return OrganizationRead.model_validate(org).model_dump()


@router.delete('/{org_id}', summary='删除组织')
def delete_organization(
    org_id: int,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_admin),
):
    org = session.get(Organization, org_id)
    if not org:
        raise HTTPException(404, '组织不存在')
    # 检查是否有关联用户
    users = session.exec(select(User).where(User.org_id == org_id)).all()
    if users:
        raise HTTPException(400, f'组织下还有 {len(users)} 个用户，请先转移或删除用户')
    audit(request, 'delete', 'organization', org.id, f'删除组织: {org.name}', session)
    session.delete(org)
    session.commit()
    return {'success': True}


@router.get('/all', summary='获取所有可用组织（下拉选择用）')
def list_all_organizations(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """获取所有活跃组织列表，用于创建用户/资产时选择"""
    orgs = session.exec(select(Organization).where(Organization.is_active == True).order_by(Organization.name)).all()
    return [{'id': o.id, 'name': o.name, 'code': o.code} for o in orgs]


@router.post('/{org_id}/generate-probe', summary='生成探针配置')
def generate_probe(
    org_id: int,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_admin),
):
    """生成 probe_key、WireGuard 密钥对，分配隧道 IP 并注册到 WireGuard server"""
    org = session.get(Organization, org_id)
    if not org:
        raise HTTPException(404, '组织不存在')
    try:
        # 生成 probe_key（如果没有）
        if not org.probe_key:
            org.probe_key = generate_probe_key()
        # 生成 WireGuard 密钥对
        private_key, public_key = generate_wireguard_keypair()
        org.wg_private_key = private_key
        org.wg_public_key = public_key
        # 分配隧道 IP（查询所有已用的 wg_tunnel_ip，分配下一个可用的）
        used_rows = session.exec(
            select(Organization.wg_tunnel_ip).where(Organization.wg_tunnel_ip.isnot(None))
        ).all()
        used_ips = [ip for ip in used_rows if ip]
        tunnel_ip = allocate_tunnel_ip(used_ips)
        if not tunnel_ip:
            raise HTTPException(500, '隧道 IP 地址池已耗尽')
        org.wg_tunnel_ip = tunnel_ip
        # 添加到 WireGuard server
        if not add_peer(public_key, tunnel_ip):
            raise HTTPException(500, '添加 WireGuard peer 失败，请检查服务端 wg 服务')
        org.updated_at = datetime.utcnow()
        session.add(org)
        session.commit()
        session.refresh(org)
        audit(request, 'generate', 'organization', org.id, f'生成探针配置: {org.name}', session)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f'生成探针配置失败: {e}')
    return {
        'org_id': org.id,
        'org_code': org.code,
        'probe_key': org.probe_key,
        'wg_private_key': org.wg_private_key,
        'wg_public_key': org.wg_public_key,
        'wg_tunnel_ip': org.wg_tunnel_ip,
        'wg_server_public_key': get_server_public_key(),
        'wg_endpoint': f'{get_central_public_ip()}:{WG_LISTEN_PORT}',
    }


@router.post('/{org_id}/reset-probe', summary='重置探针密钥')
def reset_probe(
    org_id: int,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_admin),
):
    """移除旧 Peer，重新生成密钥对和 probe_key 并注册新 Peer"""
    org = session.get(Organization, org_id)
    if not org:
        raise HTTPException(404, '组织不存在')
    try:
        # 如果有旧的 wg_public_key，先 remove_peer
        if org.wg_public_key:
            remove_peer(org.wg_public_key)
        # 生成新的密钥对和 probe_key
        private_key, public_key = generate_wireguard_keypair()
        org.wg_private_key = private_key
        org.wg_public_key = public_key
        org.probe_key = generate_probe_key()
        # add_peer 新的（复用原有隧道 IP）
        if org.wg_tunnel_ip:
            if not add_peer(public_key, org.wg_tunnel_ip):
                raise HTTPException(500, '添加 WireGuard peer 失败')
        org.updated_at = datetime.utcnow()
        session.add(org)
        session.commit()
        session.refresh(org)
        audit(request, 'reset', 'organization', org.id, f'重置探针密钥: {org.name}', session)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f'重置探针密钥失败: {e}')
    return {
        'org_id': org.id,
        'probe_key': org.probe_key,
        'wg_public_key': org.wg_public_key,
        'wg_tunnel_ip': org.wg_tunnel_ip,
    }


@router.get('/{org_id}/probe-config', summary='下载探针配置包')
def download_probe_config(
    org_id: int,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_admin),
):
    """打包下载探针部署配置（docker-compose.yml / .env / wg0.conf / README.md）"""
    org = session.get(Organization, org_id)
    if not org:
        raise HTTPException(404, '组织不存在')
    if not org.probe_key or not org.wg_private_key:
        raise HTTPException(400, '请先生成探针配置')

    opsflow_url = f'{request.url.scheme}://{request.url.netloc}/api/v1'
    server_public_key = get_server_public_key() or '<SERVER_PUBLIC_KEY>'
    server_public_ip = get_central_public_ip() or '<SERVER_PUBLIC_IP>'
    tunnel_ip = org.wg_tunnel_ip or ''

    docker_compose = '''version: "3.8"
services:
  opsflow-probe:
    image: opsflow/probe:latest
    container_name: opsflow-probe
    restart: unless-stopped
    env_file: .env
    network_mode: "host"
    cap_add:
      - NET_ADMIN
    sysctls:
      - net.ipv4.ip_forward=1
    volumes:
      - ./wg0.conf:/etc/wireguard/wg0.conf
'''

    env_content = f'''# OpsFlow 探针配置
OPSFLOW_URL={opsflow_url}
PROBE_KEY={org.probe_key}
ORG_CODE={org.code}
WG_INTERFACE=wg0
WG_TUNNEL_IP={tunnel_ip}
WG_SERVER_PUBLIC_KEY={server_public_key}
WG_SERVER_ENDPOINT={server_public_ip}:{WG_LISTEN_PORT}
'''

    wg0_conf = f'''[Interface]
PrivateKey = {org.wg_private_key}
Address = {tunnel_ip}/32

[Peer]
PublicKey = {server_public_key}
Endpoint = {server_public_ip}:{WG_LISTEN_PORT}
AllowedIPs = {WG_TUNNEL_NETWORK}
PersistentKeepalive = 25
'''

    readme = '''# OpsFlow 探针

## 部署步骤

1. 安装 Docker 和 Docker Compose
2. 将本目录下所有文件放到探针服务器
3. 启动探针：
   ```
   docker-compose up -d
   ```
4. 查看日志：
   ```
   docker-compose logs -f
   ```

## 文件说明

- `docker-compose.yml` - 探针容器编排
- `.env` - 探针环境变量配置
- `wg0.conf` - WireGuard 客户端配置
'''

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('docker-compose.yml', docker_compose)
        zf.writestr('.env', env_content)
        zf.writestr('wg0.conf', wg0_conf)
        zf.writestr('README.md', readme)
    buf.seek(0)

    return Response(
        content=buf.getvalue(),
        media_type='application/zip',
        headers={'Content-Disposition': f'attachment; filename=probe-{org.code}.zip'},
    )
