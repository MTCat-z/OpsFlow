FROM python:3.11-slim

# 使用阿里云 Debian 镜像加速 apt 安装
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || true


WORKDIR /app

# 安装系统依赖（nmap & iperf3 由宿主机提供，这里安装调用所需的基础工具）
RUN apt-get update && apt-get install -y --no-install-recommends \
    nmap \
    iperf3 \
    iputils-ping \
    traceroute \
    mtr-tiny \
    dnsutils \
    openssh-client \
    curl \
    wireguard-tools \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制应用代码
COPY . .

# 创建数据目录
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
