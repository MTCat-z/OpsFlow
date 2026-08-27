"""
WireGuard VPN 管理服务 - 管理探针的 VPN 密钥和 Peer
"""
import subprocess
import secrets
import ipaddress
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# WireGuard 隧道网段
WG_TUNNEL_NETWORK = "10.99.0.0/24"
WG_SERVER_TUNNEL_IP = "10.99.0.1"
WG_LISTEN_PORT = 51820
WG_INTERFACE = "wg0"


def generate_wireguard_keypair() -> Tuple[str, str]:
    """生成 WireGuard 密钥对，返回 (private_key, public_key)"""
    result = subprocess.run(
        ["wg", "genkey"],
        capture_output=True, text=True, check=True
    )
    private_key = result.stdout.strip()
    result = subprocess.run(
        ["wg", "pubkey"],
        input=private_key, capture_output=True, text=True, check=True
    )
    public_key = result.stdout.strip()
    return private_key, public_key


def generate_probe_key() -> str:
    """生成探针认证密钥"""
    return f"pk_{secrets.token_hex(16)}"


def allocate_tunnel_ip(used_ips: list[str]) -> Optional[str]:
    """分配隧道 IP，从 10.99.0.2 开始，跳过已用的"""
    network = ipaddress.ip_network(WG_TUNNEL_NETWORK)
    used_set = set(used_ips) | {WG_SERVER_TUNNEL_IP}
    for ip in network.hosts():
        ip_str = str(ip)
        if ip_str not in used_set:
            return ip_str
    return None


def add_peer(public_key: str, tunnel_ip: str) -> bool:
    """向 WireGuard server 添加一个 Peer"""
    try:
        subprocess.run(
            ["wg", "set", WG_INTERFACE, "peer", public_key,
             "allowed-ips", f"{tunnel_ip}/32"],
            check=True, capture_output=True
        )
        logger.info("WireGuard peer 已添加: %s -> %s", public_key[:8], tunnel_ip)
        return True
    except subprocess.CalledProcessError as e:
        logger.error("添加 WireGuard peer 失败: %s", e.stderr)
        return False
    except FileNotFoundError as e:
        logger.error("wg 命令未找到: %s", e)
        return False


def remove_peer(public_key: str) -> bool:
    """从 WireGuard server 移除一个 Peer"""
    try:
        subprocess.run(
            ["wg", "set", WG_INTERFACE, "peer", public_key, "remove"],
            check=True, capture_output=True
        )
        logger.info("WireGuard peer 已移除: %s", public_key[:8])
        return True
    except subprocess.CalledProcessError as e:
        logger.error("移除 WireGuard peer 失败: %s", e.stderr)
        return False
    except FileNotFoundError as e:
        logger.error("wg 命令未找到: %s", e)
        return False


def get_peers() -> Optional[dict[str, str]]:
    """获取 wg0 当前所有 peer，返回 {公钥: allowed-ips}；接口不可用时返回 None"""
    try:
        result = subprocess.run(
            ["wg", "show", WG_INTERFACE, "allowed-ips"],
            capture_output=True, text=True, check=True
        )
        peers = {}
        for line in result.stdout.strip().splitlines():
            parts = line.split()
            if parts:
                peers[parts[0]] = parts[1] if len(parts) > 1 else ""
        return peers
    except Exception:
        return None


def get_server_public_key() -> Optional[str]:
    """获取中心服务器的 WireGuard 公钥"""
    try:
        result = subprocess.run(
            ["wg", "show", WG_INTERFACE, "public-key"],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except Exception:
        return None


def get_central_public_ip() -> Optional[str]:
    """获取中心服务器的公网 IP"""
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", "5", "ifconfig.me"],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except Exception:
        return None
