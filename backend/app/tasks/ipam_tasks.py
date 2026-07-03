import logging
from datetime import datetime

from sqlmodel import Session, select

from app.tasks.worker import celery_app
from app.core.database import engine
from app.models.ipam import IpamSubnet, IpamAddress
from app.models.asset import Asset

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name='app.tasks.ipam_tasks.discover_ipam_subnet')
def discover_ipam_subnet(self, subnet_id: int):
    """对指定子网执行 Nmap ping scan，发现存活 IP 并 upsert 到 IpamAddress"""
    import nmap

    with Session(engine) as session:
        subnet = session.get(IpamSubnet, subnet_id)
        if not subnet:
            return {'error': f'Subnet {subnet_id} not found'}
        cidr = subnet.cidr
        dhcp_enabled = subnet.dhcp_enabled

    try:
        nm = nmap.PortScanner()
        # ping scan 发现存活主机
        nm.scan(hosts=cidr, arguments='-sn -PE')

        discovered = []
        for host in nm.all_hosts():
            mac = nm[host].addresses.get('mac', '') if hasattr(nm[host], 'addresses') else ''
            hostname = nm[host].hostname() or ''
            discovered.append({
                'ip': host,
                'mac': mac,
                'hostname': hostname,
            })

        # upsert 到数据库
        with Session(engine) as session:
            subnet = session.get(IpamSubnet, subnet_id)
            if not subnet:
                return {'error': f'Subnet {subnet_id} not found'}

            new_count = 0
            updated_count = 0
            conflict_count = 0
            now = datetime.utcnow()

            for item in discovered:
                existing = session.exec(
                    select(IpamAddress).where(
                        IpamAddress.subnet_id == subnet_id,
                        IpamAddress.ip_address == item['ip'],
                    )
                ).first()

                if existing:
                    # 更新已有记录
                    old_mac = existing.mac_address
                    if item['mac'] and old_mac and item['mac'] != old_mac:
                        # MAC 变更 → 标记为冲突
                        existing.status = 'conflict'
                        conflict_count += 1
                    else:
                        existing.status = 'used'
                    existing.mac_address = item['mac'] or existing.mac_address
                    existing.hostname = item['hostname'] or existing.hostname
                    existing.last_seen_at = now
                    existing.updated_at = now
                    session.add(existing)
                    updated_count += 1
                else:
                    # 新发现
                    addr = IpamAddress(
                        subnet_id=subnet_id,
                        ip_address=item['ip'],
                        mac_address=item['mac'] or None,
                        hostname=item['hostname'] or None,
                        status='used',
                        source='nmap',
                        last_seen_at=now,
                    )
                    session.add(addr)
                    new_count += 1

            # 标记长时间未见的 IP 为 offline（超过 24 小时未发现）
            stale_addrs = session.exec(
                select(IpamAddress).where(
                    IpamAddress.subnet_id == subnet_id,
                    IpamAddress.status == 'used',
                    IpamAddress.source == 'nmap',
                )
            ).all()
            offline_count = 0
            for addr in stale_addrs:
                if addr.last_seen_at and (now - addr.last_seen_at).total_seconds() > 86400 * 3:
                    addr.status = 'offline'
                    session.add(addr)
                    offline_count += 1

            # 尝试关联资产
            _associate_assets(session, subnet_id)

            session.commit()

        logger.info(
            'IPAM discovery completed for %s: new=%d, updated=%d, conflicts=%d, offline=%d',
            cidr, new_count, updated_count, conflict_count, offline_count,
        )
        return {
            'subnet_id': subnet_id,
            'cidr': cidr,
            'discovered': len(discovered),
            'new': new_count,
            'updated': updated_count,
            'conflicts': conflict_count,
            'offline': offline_count,
        }

    except Exception as e:
        logger.error('IPAM discovery failed for subnet %s: %s', subnet_id, e)
        return {'error': str(e)}


def _associate_assets(session: Session, subnet_id: int):
    """将发现的 IP 与资产表关联"""
    addrs = session.exec(
        select(IpamAddress).where(
            IpamAddress.subnet_id == subnet_id,
            IpamAddress.asset_id == None,
        )
    ).all()

    for addr in addrs:
        asset = session.exec(
            select(Asset).where(Asset.ip_address == addr.ip_address)
        ).first()
        if asset:
            addr.asset_id = asset.id
            session.add(addr)


@celery_app.task(name='app.tasks.ipam_tasks.discover_all_subnets')
def discover_all_subnets():
    """遍历所有启用的子网并触发发现任务"""
    with Session(engine) as session:
        subnets = session.exec(select(IpamSubnet)).all()

    triggered = 0
    for subnet in subnets:
        try:
            discover_ipam_subnet.delay(subnet.id)
            triggered += 1
        except Exception as e:
            logger.error('Failed to trigger discovery for subnet %s: %s', subnet.id, e)

    return {'triggered': triggered, 'total': len(subnets)}
