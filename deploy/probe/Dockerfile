FROM python:3.12-slim

# 使用阿里云 Debian 镜像加速 apt 安装
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || true

# 安装网络工具
RUN apt-get update && apt-get install -y --no-install-recommends \
    nmap \
    iperf3 \
    iputils-ping \
    wireguard-tools \
    wireguard-go \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
RUN pip install --no-cache-dir httpx python-nmap -i https://pypi.tuna.tsinghua.edu.cn/simple

WORKDIR /app

# 复制探针代码（build context 为项目根目录）
COPY backend/app/probe/agent.py /app/agent.py
COPY deploy/probe/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
