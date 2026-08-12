"""
SSH 命令执行服务 — 同步执行单条/多条命令，供配置备份和批量命令复用
"""
import io
import logging
from typing import Optional

import paramiko

from app.core.database import Session, engine
from app.core.security import decrypt
from app.models.asset import Asset
from app.services.command_guard import check_dangerous_commands

logger = logging.getLogger(__name__)


def _build_client(asset: Asset) -> paramiko.SSHClient:
    """根据资产凭据构建已连接的 SSHClient"""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    username = decrypt(asset.username_encrypted) if asset.username_encrypted else None
    password = decrypt(asset.password_encrypted) if asset.password_encrypted else None
    ssh_key_text = decrypt(asset.ssh_private_key_encrypted) if asset.ssh_private_key_encrypted else None
    auth_type = asset.auth_type or 'password'

    connect_kwargs = {
        'hostname': asset.ip_address,
        'port': asset.ssh_port or 22,
        'username': username,
        'timeout': 15,
        'allow_agent': False,
        'look_for_keys': False,
    }

    if auth_type == 'key' and ssh_key_text:
        pkey = _parse_private_key(ssh_key_text)
        connect_kwargs['pkey'] = pkey
        if password:
            connect_kwargs['passphrase'] = password
    elif auth_type == 'both':
        connect_kwargs['password'] = password
        if ssh_key_text:
            pkey = _parse_private_key(ssh_key_text)
            if pkey:
                connect_kwargs['pkey'] = pkey
    else:
        connect_kwargs['password'] = password

    client.connect(**connect_kwargs)
    return client


def _parse_private_key(key_text: str) -> Optional[paramiko.PKey]:
    """尝试多种格式解析私钥"""
    for key_class in (paramiko.RSAKey, paramiko.Ed25519Key, paramiko.ECDSAKey):
        try:
            return key_class.from_private_key(io.StringIO(key_text))
        except Exception:
            continue
    return None


def execute_ssh_command(asset_id: int, command: str, timeout: int = 30) -> dict:
    """
    SSH 连接到资产并执行命令，返回 {success, output, error}
    
    支持多行命令（按换行拆分逐条执行），收集所有输出。
    """
    with Session(engine) as session:
        asset = session.get(Asset, asset_id)
        if not asset:
            return {'success': False, 'output': '', 'error': f'资产 {asset_id} 不存在'}
        if not asset.ip_address:
            return {'success': False, 'output': '', 'error': '资产未配置 IP 地址'}
        # 提取到局部变量
        asset_name = asset.name
        ip = asset.ip_address

    # 安全校验（纵深防御：即使调用方绕过了 API 层检查，此处仍拦截）
    guard = check_dangerous_commands(command)
    if not guard['safe']:
        logger.warning('命令被安全策略拦截: %s', guard['reasons'])
        return {'success': False, 'output': '', 'error': f'命令被安全策略拦截: {"; ".join(guard["reasons"][:3])}'}

    client = None
    try:
        client = _build_client(asset)

        commands = [c.strip() for c in command.strip().splitlines() if c.strip()]
        if not commands:
            return {'success': False, 'output': '', 'error': '未提供有效命令'}

        outputs = []
        for cmd in commands:
            stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
            out = stdout.read().decode('utf-8', errors='replace')
            err = stderr.read().decode('utf-8', errors='replace')
            outputs.append(out)
            if err:
                outputs.append(err)

        full_output = ''.join(outputs)
        return {'success': True, 'output': full_output, 'error': ''}

    except paramiko.AuthenticationException:
        return {'success': False, 'output': '', 'error': f'{ip}: SSH 认证失败'}
    except paramiko.SSHException as e:
        return {'success': False, 'output': '', 'error': f'{ip}: SSH 错误: {e}'}
    except Exception as e:
        return {'success': False, 'output': '', 'error': f'{ip}: {e}'}
    finally:
        if client:
            try:
                client.close()
            except Exception:
                pass


def execute_ssh_command_with_asset(asset: Asset, command: str, timeout: int = 30) -> dict:
    """
    直接传入 Asset 对象执行命令（避免重复查询 DB）。
    用于批量场景中已加载资产列表的情况。
    """
    if not asset.ip_address:
        return {'success': False, 'output': '', 'error': '资产未配置 IP 地址'}

    # 安全校验（纵深防御：即使调用方绕过了 API 层检查，此处仍拦截）
    guard = check_dangerous_commands(command)
    if not guard['safe']:
        logger.warning('命令被安全策略拦截: %s', guard['reasons'])
        return {'success': False, 'output': '', 'error': f'命令被安全策略拦截: {"; ".join(guard["reasons"][:3])}'}

    client = None
    try:
        client = _build_client(asset)

        commands = [c.strip() for c in command.strip().splitlines() if c.strip()]
        if not commands:
            return {'success': False, 'output': '', 'error': '未提供有效命令'}

        outputs = []
        for cmd in commands:
            stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
            out = stdout.read().decode('utf-8', errors='replace')
            err = stderr.read().decode('utf-8', errors='replace')
            outputs.append(out)
            if err:
                outputs.append(err)

        full_output = ''.join(outputs)
        return {'success': True, 'output': full_output, 'error': ''}

    except paramiko.AuthenticationException:
        return {'success': False, 'output': '', 'error': f'{asset.ip_address}: SSH 认证失败'}
    except paramiko.SSHException as e:
        return {'success': False, 'output': '', 'error': f'{asset.ip_address}: SSH 错误: {e}'}
    except Exception as e:
        return {'success': False, 'output': '', 'error': f'{asset.ip_address}: {e}'}
    finally:
        if client:
            try:
                client.close()
            except Exception:
                pass
