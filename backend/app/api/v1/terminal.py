"""
WebSocket 终端代理 — 通过 paramiko SSH / telnetlib3 Telnet 连接资产
"""
import asyncio
import io
import logging
from fastapi import WebSocket, WebSocketDisconnect

from app.core.database import Session, engine
from app.core.security import decrypt
from app.models.asset import Asset

logger = logging.getLogger(__name__)


async def terminal_ws_handler(websocket: WebSocket, asset_id: int):
    """WebSocket 终端会话入口"""
    from app.core.auth import verify_ws_token, check_org_access

    # 认证：从查询参数提取 token 并验证
    token = websocket.query_params.get('token')
    with Session(engine) as session:
        user = verify_ws_token(token, session)
        if not user:
            await websocket.close(code=4001)
            return

        # 从 DB 加载资产
        asset = session.get(Asset, asset_id)
        if not asset:
            await websocket.close(code=4004)
            return

        # 检查 org_id 归属
        if not check_org_access(asset, user):
            await websocket.close(code=4033)
            return

        # 解密凭据
        ip = asset.ip_address
        port = asset.ssh_port
        protocol = asset.protocol
        auth_type = asset.auth_type
        username = decrypt(asset.username_encrypted) if asset.username_encrypted else None
        password = decrypt(asset.password_encrypted) if asset.password_encrypted else None
        ssh_key_text = decrypt(asset.ssh_private_key_encrypted) if asset.ssh_private_key_encrypted else None

    await websocket.accept()

    cols = int(websocket.query_params.get('cols', 120))
    rows = int(websocket.query_params.get('rows', 40))

    if protocol == 'ssh':
        await _handle_ssh(websocket, ip, port, username, password, ssh_key_text, auth_type, cols, rows)
    elif protocol == 'telnet':
        await _handle_telnet(websocket, ip, port, username, password)
    else:
        await websocket.send_text(f'\r\n[错误] 不支持的协议: {protocol}\r\n')
        await websocket.close(code=4000)


async def _handle_ssh(websocket, ip, port, username, password, ssh_key_text, auth_type, cols, rows):
    """SSH 终端处理"""
    try:
        import paramiko
    except ImportError:
        await websocket.send_text('\r\n[错误] paramiko 未安装\r\n')
        await websocket.close(code=4500)
        return

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    channel = None

    try:
        # 构建连接参数
        connect_kwargs = {
            'hostname': ip,
            'port': port,
            'username': username,
            'timeout': 15,
            'allow_agent': False,
            'look_for_keys': False,
        }

        if auth_type == 'key' and ssh_key_text:
            try:
                pkey = paramiko.RSAKey.from_private_key(io.StringIO(ssh_key_text))
            except Exception:
                try:
                    pkey = paramiko.Ed25519Key.from_private_key(io.StringIO(ssh_key_text))
                except Exception:
                    pkey = paramiko.ECDSAKey.from_private_key(io.StringIO(ssh_key_text))
            connect_kwargs['pkey'] = pkey
            if password:
                connect_kwargs['passphrase'] = password
        elif auth_type == 'both':
            connect_kwargs['password'] = password
            if ssh_key_text:
                try:
                    pkey = paramiko.RSAKey.from_private_key(io.StringIO(ssh_key_text))
                    connect_kwargs['pkey'] = pkey
                except Exception:
                    pass
        else:
            connect_kwargs['password'] = password

        # 在线程中执行阻塞的 SSH 连接
        await asyncio.to_thread(client.connect, **connect_kwargs)
        channel = client.invoke_shell(width=cols, height=rows)
        channel.setblocking(0)

        await websocket.send_text(f'\x1b[32m已连接到 {ip}:{port}\x1b[0m\r\n')

        # 双向转发
        ws_to_ssh = asyncio.create_task(_ws_to_ssh(websocket, channel))
        ssh_to_ws = asyncio.create_task(_ssh_to_ws(channel, websocket))

        done, pending = await asyncio.wait(
            [ws_to_ssh, ssh_to_ws],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_text(f'\r\n\x1b[31m连接错误: {e}\x1b[0m\r\n')
        except Exception:
            pass
    finally:
        if channel:
            try:
                channel.close()
            except Exception:
                pass
        try:
            client.close()
        except Exception:
            pass
        try:
            await websocket.close()
        except Exception:
            pass


async def _ws_to_ssh(websocket, channel):
    """WebSocket -> SSH"""
    while True:
        data = await websocket.receive_text()
        if not data:
            break
        # 处理 resize 消息
        if data.startswith('\x00'):
            try:
                import json
                msg = json.loads(data[1:])
                if msg.get('type') == 'resize':
                    channel.resize_pty(width=msg['cols'], height=msg['rows'])
                    continue
            except Exception:
                pass
        while channel.send_ready():
            sent = channel.send(data.encode('utf-8'))
            if sent < len(data):
                data = data[sent:]
            else:
                break


async def _ssh_to_ws(channel, websocket):
    """SSH -> WebSocket"""
    while True:
        if channel.recv_ready():
            data = channel.recv(4096)
            if not data:
                break
            await websocket.send_text(data.decode('utf-8', errors='replace'))
        elif channel.exit_status_ready():
            # 读取剩余数据
            while channel.recv_ready():
                data = channel.recv(4096)
                if data:
                    await websocket.send_text(data.decode('utf-8', errors='replace'))
            break
        else:
            await asyncio.sleep(0.05)


async def _handle_telnet(websocket, ip, port, username, password):
    """Telnet 终端处理"""
    try:
        import telnetlib3
    except ImportError:
        await websocket.send_text('\r\n[错误] telnetlib3 未安装\r\n')
        await websocket.close(code=4500)
        return

    reader = None
    writer = None
    try:
        reader, writer = await asyncio.wait_for(
            telnetlib3.open_connection(ip, port),
            timeout=15,
        )
        await websocket.send_text(f'\x1b[32m已连接到 {ip}:{port} (Telnet)\x1b[0m\r\n')

        # 自动登录
        if username:
            await asyncio.sleep(1)
            data = await asyncio.wait_for(reader.read(4096), timeout=5)
            await websocket.send_text(data)
            if 'login' in data.lower() or 'username' in data.lower():
                writer.write(username + '\n')
                await writer.drain()
                await asyncio.sleep(0.5)
                data = await asyncio.wait_for(reader.read(4096), timeout=5)
                await websocket.send_text(data)
            if password and ('password' in data.lower() or 'pass' in data.lower()):
                writer.write(password + '\n')
                await writer.drain()

        # 双向转发
        async def telnet_to_ws():
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                await websocket.send_text(data)

        async def ws_to_telnet():
            while True:
                data = await websocket.receive_text()
                writer.write(data)
                await writer.drain()

        done, pending = await asyncio.wait(
            [asyncio.create_task(telnet_to_ws()), asyncio.create_task(ws_to_telnet())],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_text(f'\r\n\x1b[31mTelnet 错误: {e}\x1b[0m\r\n')
        except Exception:
            pass
    finally:
        if writer:
            try:
                writer.close()
            except Exception:
                pass
        try:
            await websocket.close()
        except Exception:
            pass
