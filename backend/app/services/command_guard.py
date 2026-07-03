"""
危险命令拦截服务 — 正则匹配黑名单命令，防止误操作
"""
import re
import logging

logger = logging.getLogger(__name__)

# 危险命令正则模式列表（不区分大小写）
DANGEROUS_PATTERNS = [
    (r'\berase\b', '擦除命令 (erase)'),
    (r'\bformat\b', '格式化命令 (format)'),
    (r'\bdelete\s+/\b', '强制删除命令 (delete /)'),
    (r'\breload\b', '设备重启命令 (reload)'),
    (r'\breboot\b', '设备重启命令 (reboot)'),
    (r'\bwrite\s+erase\b', '清除配置命令 (write erase)'),
    (r'\bfactory-reset\b', '恢复出厂设置 (factory-reset)'),
    (r'\bno\s+shutdown\b.*\binterface\b', '关闭接口命令'),
    (r'\bshutdown\b.*\binterface\b', '关闭接口命令'),
    (r'\bcopy\s+.*\s+running-config\b', '覆盖运行配置'),
    (r'\breset\s+saved-configuration\b', '清除保存配置'),
    (r'\bdelete\s+flash:', '删除闪存文件'),
]

_compiled_patterns = [(re.compile(p, re.IGNORECASE), desc) for p, desc in DANGEROUS_PATTERNS]


def check_dangerous_commands(commands_text: str) -> dict:
    """
    检查命令文本中是否包含危险命令。
    
    返回:
        {
            "safe": bool,          # True 表示安全
            "blocked": [str],      # 被拦截的危险命令行
            "reasons": [str],      # 拦截原因
        }
    """
    if not commands_text or not commands_text.strip():
        return {'safe': True, 'blocked': [], 'reasons': []}

    blocked = []
    reasons = []

    lines = [line.strip() for line in commands_text.strip().splitlines() if line.strip() and not line.strip().startswith('#')]

    for line in lines:
        for pattern, description in _compiled_patterns:
            if pattern.search(line):
                if line not in blocked:
                    blocked.append(line)
                    reasons.append(f'"{line}" — {description}')
                break

    return {
        'safe': len(blocked) == 0,
        'blocked': blocked,
        'reasons': reasons,
    }
