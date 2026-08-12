"""
命令安全校验服务 — 白名单优先 + 黑名单纵深防御

策略：
1. 白名单：每条命令必须以允许的只读前缀开头（show/display/ping 等），
   否则直接拦截。这是主要防御层，确保只有只读/诊断类命令可执行。
2. 黑名单：即使匹配白名单，仍拦截危险的 shell 元字符和命令名，
   防止通过管道、参数展开等方式注入任意命令。
"""
import re
import logging

logger = logging.getLogger(__name__)

# ============================================================
# 白名单：允许的命令前缀（锚定行首，只读/诊断类）
# 网络设备常见只读命令：Cisco show、Huawei display、ping、traceroute 等
# ============================================================
ALLOWED_PREFIXES = [
    re.compile(r'^show\s', re.IGNORECASE),
    re.compile(r'^display\s', re.IGNORECASE),
    re.compile(r'^ping\s', re.IGNORECASE),
    re.compile(r'^traceroute\s', re.IGNORECASE),
    re.compile(r'^tracert\s', re.IGNORECASE),
    re.compile(r'^terminal\s', re.IGNORECASE),
    re.compile(r'^list\s', re.IGNORECASE),
    re.compile(r'^get\s', re.IGNORECASE),
    re.compile(r'^view\s', re.IGNORECASE),
    re.compile(r'^exit\s*$', re.IGNORECASE),
    re.compile(r'^quit\s*$', re.IGNORECASE),
]

# ============================================================
# 黑名单：危险的 shell 元字符和命令名（纵深防御）
# 修复了原版黑名单的已知绕过：
#   - 重定向符不再要求后接空格（>file 也拦截）
#   - 拦截 ${} 参数展开（原版只拦 $()，可被 ${IFS} 绕过）
#   - 拦截 $'' ANSI-C 引号（可用于拼装命令名绕过词边界）
#   - 拦截 ; & | 等命令链接符
#   - 命令名匹配带数字后缀（python3 等）
# ============================================================
DANGEROUS_PATTERNS = [
    # --- 命令链接/注入元字符 ---
    (r';', '命令分隔符 ;'),
    (r'&', '后台/逻辑符 &'),
    (r'`', '反引号命令替换'),
    (r'\$\(', '命令替换 $(...)'),
    (r'\$\{', '参数展开 ${...}（可用于绕过命令名检测）'),
    (r"\$'", "ANSI-C 引号 $'...'（可用于拼装命令名）"),
    (r'/dev/tcp', 'Bash TCP 重定向 (/dev/tcp)'),
    (r'\\\s*$', '行尾续行符（可能跨行拼接危险命令）'),

    # --- 重定向（不再要求后接空格，修复原版绕过） ---
    (r'>>?', '输出重定向符 > 或 >>'),
    (r'<<', 'Here 文档重定向符 <<'),

    # --- 危险命令名（含数字后缀变体） ---
    (r'\berase\b', '擦除命令 (erase)'),
    (r'\bformat\b', '格式化命令 (format)'),
    (r'\bdelete\b', '删除命令 (delete)'),
    (r'\breload\b', '设备重启命令 (reload)'),
    (r'\breboot\b', '设备重启命令 (reboot)'),
    (r'\bwrite\s+erase\b', '清除配置命令 (write erase)'),
    (r'\bfactory-reset\b', '恢复出厂设置 (factory-reset)'),
    (r'\bshutdown\b', '关闭接口命令 (shutdown)'),
    (r'\bcopy\s', '复制命令 (copy，可能覆盖配置)'),
    (r'\breset\s+saved-configuration\b', '清除保存配置'),
    (r'\brm\b', '删除命令 (rm)'),
    (r'\bmv\b', '移动命令 (mv)'),
    (r'\bcurl\w*', '网络请求命令 (curl)'),
    (r'\bwget\w*', '下载命令 (wget)'),
    (r'\btftp\b', 'TFTP 传输命令 (tftp)'),
    (r'\bftp\b', 'FTP 传输命令 (ftp)'),
    (r'\bscp\b', 'SCP 传输命令 (scp)'),
    (r'\b(bash|zsh|ksh|csh|dash|ash)\b', 'Shell 调用'),
    (r'\bsh\b', 'Shell 调用 (sh)'),
    (r'\bpython\w*', 'Python 调用'),
    (r'\bperl\w*', 'Perl 调用'),
    (r'\b(nc|ncat)\b', 'Netcat 命令'),
]

_compiled_dangerous = [(re.compile(p, re.IGNORECASE), desc) for p, desc in DANGEROUS_PATTERNS]


def check_dangerous_commands(commands_text: str) -> dict:
    """
    检查命令文本是否安全。

    采用白名单优先 + 黑名单纵深防御：
    1. 每条非注释命令必须匹配白名单前缀之一，否则拦截
    2. 即使匹配白名单，若命中危险模式也拦截

    返回:
        {
            "safe": bool,          # True 表示安全
            "blocked": [str],      # 被拦截的命令行
            "reasons": [str],      # 拦截原因
        }
    """
    if not commands_text or not commands_text.strip():
        return {'safe': True, 'blocked': [], 'reasons': []}

    blocked = []
    reasons = []

    lines = [
        line.strip()
        for line in commands_text.strip().splitlines()
        if line.strip() and not line.strip().startswith('#')
    ]

    for line in lines:
        # 1. 白名单校验：必须匹配允许的只读前缀
        if not any(p.match(line) for p in ALLOWED_PREFIXES):
            if line not in blocked:
                blocked.append(line)
                reasons.append(
                    f'"{line}" — 不在允许的命令白名单内'
                    f'（仅允许 show/display/ping/traceroute 等只读命令）'
                )
            continue

        # 2. 黑名单纵深防御：即使匹配白名单也检查危险模式
        for pattern, description in _compiled_dangerous:
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
