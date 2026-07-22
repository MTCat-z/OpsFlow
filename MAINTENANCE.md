# OpsFlow 维护指南

> 本文档记录项目维护经验、部署流程、常见问题与解决方案，供后续对话和维护参考。

---

## 项目概览

- **技术栈**：FastAPI + Vue3 + Element Plus + Celery + Redis + Docker + Nginx
- **部署方式**：Docker Compose（Linux host 网络模式），服务器 `192.168.40.183`
- **代码仓库**：GitHub `MTCat-z/OpsFlow`（public）
- **本地开发**：Windows，`d:\OpsFlow`
- **服务器路径**：`/opt/ops-platform`

---

## 一、开发工作流

### 标准流程（重要）

```
本地修改 → npm run lint → npm run build → git commit → git push → 服务器 git pull + upgrade.sh
```

### 关键规则

1. **不要在服务器上直接改代码**，所有修改在本地完成后通过 Git 推送
2. **commit message 用 conventional commits**，但注意：
   - subject 不能用 sentence-case（首字母大写），用全小写或中文
   - body 每行不超过 100 字符
   - 示例：`feat(broadband): 新增导出 Excel 功能`
3. **push 前先验证**：`npm run lint`（前端）+ `python -m py_compile`（后端语法）
4. **本地有 lint-staged 钩子**（commit 时自动跑 eslint），会阻止有错误的提交

### 服务器更新流程

```bash
cd /opt/ops-platform

# 方式一：直接跑升级脚本（推荐，不要先手动 git pull）
bash deploy/upgrade.sh

# 方式二：如果脚本出问题，手动构建
git pull origin main
docker compose -f deploy/docker-compose.linux.yml build --no-cache nginx
docker compose -f deploy/docker-compose.linux.yml up -d nginx
docker compose -f deploy/docker-compose.linux.yml restart backend celery_worker celery_beat
```

### 升级脚本（deploy/upgrade.sh）机制

- 脚本自动完成：备份数据库 → pull 代码 → 分析变更类型 → 按需重建/重启 → 健康检查
- 用 `.last_built_commit` 文件记录上次构建的 commit，支持"手动 pull 后再跑脚本"的场景
- 变更检测：对比 pull 前后的 HEAD（或上次构建版本与当前 HEAD）获取变更文件列表
- 按变更类型最小化操作：
  - 仅后端 Python 变更 → 重启容器（卷挂载生效）
  - 前端/Nginx 变更 → 重建 nginx 镜像
  - 依赖/Dockerfile 变更 → 重建后端镜像
  - Compose 配置变更 → 全量重建

---

## 二、项目结构

```
OpsFlow/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # API 路由（broadband.py, dashboard.py, users.py 等）
│   │   ├── core/            # 认证(auth.py)、配置(config.py)、数据库(database.py)
│   │   ├── models/          # SQLModel 数据模型
│   │   ├── services/        # 业务服务（broadband_renewal.py, dingtalk.py, ssh_executor.py 等）
│   │   └── tasks/           # Celery 异步任务（broadband_tasks.py, worker.py）
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env                 # 环境变量（不提交，从 .env.example 复制）
├── frontend/
│   ├── src/
│   │   ├── api/index.js     # 所有 API 调用集中在这里
│   │   ├── components/common/ # 公共组件（StatCards, StatusTag, OutputBlock）
│   │   ├── composables/     # 组合式函数（useTheme, useDialog, useTableData 等）
│   │   ├── styles/          # tokens.css（设计系统）+ global.css（全局样式+EP主题覆盖）
│   │   ├── stores/          # Pinia store（auth.js）
│   │   └── views/           # 14 个业务页面
│   ├── index.html           # 入口（含 Google Fonts 引入）
│   └── Dockerfile           # 前端无独立 Dockerfile，由 deploy/Dockerfile.nginx 多阶段构建
├── deploy/
│   ├── Dockerfile.nginx     # Nginx + 前端多阶段构建（node:20-alpine → nginx:alpine）
│   ├── docker-compose.linux.yml  # Linux 服务器部署配置（host 网络模式）
│   ├── nginx.linux.conf     # Nginx 配置（index.html 不缓存，带 hash 资源长缓存）
│   └── upgrade.sh           # 一键升级脚本
├── docker-compose.yml       # 本地开发用（非 host 网络，端口映射）
├── nginx/nginx.conf         # 本地开发用 Nginx 配置
└── .gitignore
```

---

## 三、设计系统

### 设计 Token（frontend/src/styles/tokens.css）

- **主色**：`--ops-primary: #2563EB`（亮蓝）
- **侧栏**：`--ops-sidebar-bg: #0F172A`（深蓝黑）
- **字体**：Fira Sans（正文）+ Fira Code（数字/终端）
- **暗色模式**：`[data-theme='dark']`，通过 `useTheme` composable 管理，localStorage 持久化
- **Element Plus 主题**：在 global.css 用 CSS 变量覆盖 `--el-color-primary` 等，让 EP 跟随 token

### 规则

- **禁止在业务页面硬编码十六进制颜色**，统一用 `var(--ops-*)`
- 唯一例外：xterm.js canvas 渲染的主题色（`fillStyle` 无法解析 CSS 变量）

---

## 四、经验教训与常见问题

### 1. Docker 构建缓存导致 UI 不更新

**现象**：服务器 `docker compose build` 后 UI 没变化，查看日志发现 `COPY frontend/ .` 和 `RUN npm run build` 都命中了 CACHED。

**原因**：Docker 构建缓存机制，如果 `COPY` 的文件内容没变（或 Docker 认为没变），就用缓存层。

**解决**：用 `--no-cache` 强制重建。
```bash
docker compose -f deploy/docker-compose.linux.yml build --no-cache nginx
```

### 2. 浏览器缓存导致看到老界面

**现象**：服务器已更新，但浏览器还是显示旧 UI，必须用无痕模式才能看到新版。

**原因**：Nginx 对所有 `.js/.css` 设了 `expires 30d`，浏览器缓存了旧的 JS/CSS 文件。`index.html` 也被缓存，导致浏览器不知道有新的 hash 文件。

**解决**：Nginx 配置中 `index.html` 设为不缓存（`Cache-Control: no-cache`），带 hash 的资源保持长缓存。Vite 产物文件名含 hash，更新后 hash 变化，浏览器会自动请求新文件。已在 `deploy/nginx.linux.conf` 中修复。

**用户侧操作**：更新后第一次访问按 `Ctrl+Shift+R` 强刷一次，之后不再需要。

### 3. Dockerfile 反引号 Bug

**现象**：`npm ci` 构建失败，URL 被破坏成 `https://registry.npmmirror.com:`（末尾多了冒号）。

**原因**：Dockerfile 中 `--registry=\`https://...\`` 用了反引号，shell 将其当作命令替换执行。

**解决**：去掉反引号，改为 `--registry=https://registry.npmmirror.com`。同时 `npm ci` 改为 `npm install`（lock 文件与 package.json 不同步时 `npm ci` 会失败），`node:18` 升级到 `node:20`（部分依赖要求 node 20+）。

### 4. 升级脚本"已是最新"误判

**现象**：手动 `git pull` 后再跑 `upgrade.sh`，脚本提示"已是最新，无需升级"跳过了构建。

**原因**：脚本只看"本次 pull 有没有拉到新代码"，不看"代码是否已更新但还没构建"。

**解决**：用 `.last_built_commit` 文件记录上次构建的 commit。pull 无新代码时，对比当前 HEAD 与 `.last_built_commit`，不同则继续构建。构建完成后更新该文件。

### 5. GitHub Token 泄露自动撤销

**现象**：push 时 token 出现在 remote URL 中（`https://oauth2:github_pat_xxx@github.com/...`），GitHub 检测到后自动撤销 token，后续 push 返回 401。

**原因**：token 内嵌在 URL 中，GitHub 的扫描机制会检测并撤销泄露的 token。

**解决**：
- 不要把 token 内嵌在 remote URL 中
- 用 `git credential` 存储凭据：`git config credential.helper store`，然后 `echo "protocol=https\nhost=github.com\nusername=xxx\npassword=xxx" | git credential approve`
- 检查是否有 `insteadOf` 重写规则：`git config --get-regexp "url\..*\.(insteadOf|pushInsteadOf)"`，有则删除

### 6. Fine-grained Token 权限

**现象**：token 能读 API（`/user`、`/repos` 返回 200），但 `git push` 返回 403/401。

**原因**：fine-grained token 的 Contents 权限默认是只读，API 的 `permissions.push: true` 反映的是用户身份权限而非 token 实际权限。

**解决**：生成 token 时 Repository permissions → Contents → 选 **Read and Write**。

### 7. PowerShell 与 Bash 差异

本地环境是 Windows PowerShell，注意：
- `&&` / `||` 不是有效的语句分隔符，用 `;` + `if ($LASTEXITCODE)` 代替
- heredoc（`<<'EOF'`）不支持，git commit 用多个 `-m` 参数
- `bash -n` 验证脚本语法需用 Git 自带的 bash：`& "C:\Program Files\Git\bin\bash.exe" -n file.sh`
- Docker 卷挂载用 PowerShell 变量：`-v "${PWD}\path:/container/path"`

### 8. 本地验证清单（push 前必做）

```
前端：
  cd d:\OpsFlow\frontend
  npm run lint          # 必须 0 errors（warnings 可接受）
  npm run build         # 必须成功

后端：
  cd d:\OpsFlow\backend
  python -m py_compile app/api/v1/xxx.py  # 语法检查
  python -c "from app.api.v1 import xxx"  # import 检查（注意 .env 配置问题可能导致 Settings 报错，这不代表代码有问题）
```

---

## 五、宽带管理模块要点

### 续费周期告警

- 后端定时任务（`broadband_tasks.py`）按续费周期算截止日
- **所有 UI/仪表盘/测试通知都已对齐续费周期**（不再用合同到期日）
- 核心计算函数：`backend/app/services/broadband_renewal.py` 的 `get_next_renewal(contract)`
- 返回 `{next_deadline, days_remaining, deadline_type}`，deadline_type 为 `cycle` 或 `contract_end`

### 导入导出

- **导入模板**：`GET /broadband/export/template`，16 列固定格式
- **导出 Excel**：`GET /broadband/export/excel?keyword=xx&status=xx`，格式与导入模板一致，可编辑后重新导入
- **导入 Excel**：`POST /broadband/import/excel`，支持中英文周期标签（每月/monthly 等）

### 续费周期映射

| 代码值 | 中文 | 月数 |
|--------|------|------|
| monthly | 每月 | 1 |
| quarterly | 每季度 | 3 |
| semi_annual | 每半年 | 6 |
| annual | 每年 | 12 |

---

## 六、用户/密码管理

- 默认管理员：`admin / admin123`（首次登录强制改密码）
- 重置密码：在服务器上用 docker exec 执行 Python 脚本（见下）
- 用户表：`users`，密码用 bcrypt 哈希，`must_change_password` 标记是否需要改密

```bash
# 服务器重置 admin 密码
cd /opt/ops-platform
docker compose -f deploy/docker-compose.linux.yml exec backend python -c "
from sqlmodel import Session, select
from app.core.database import engine
from app.models.user import User
from app.core.auth import hash_password
with Session(engine) as s:
    u = s.exec(select(User).where(User.username=='admin')).first()
    if u:
        u.password_hash = hash_password('admin123')
        u.must_change_password = True
        s.add(u); s.commit()
        print('admin 密码已重置为 admin123')
"
```

---

## 七、关键配置

### 后端 .env（从 .env.example 复制）

- `DATABASE_URL`：SQLite，`sqlite:///./data/ops_platform.db`
- `FERNET_KEY`：SSH 密钥加密用，生成方式 `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- `SECRET_KEY`：JWT 签名密钥
- `DEBUG`：注意 pydantic-settings 对大小写敏感，`.env` 中写 `DEBUG=false`（小写）

### Nginx 缓存策略

- `index.html`：不缓存（`Cache-Control: no-cache, no-store, must-revalidate`）
- 带 hash 的 JS/CSS/图片等：30 天长缓存（Vite 产物 hash 变化自动失效）
- API/WebSocket：反代到 `127.0.0.1:8000`

### Docker Compose（Linux）

- 所有服务用 `network_mode: host`（直接用宿主机网络，nmap/iperf3 可访问物理网卡）
- 后端代码通过卷挂载（`../backend:/app`），Python 代码变更只需重启容器
- 前端在 Docker 内构建（多阶段：node:20 build → nginx:alpine serve）

---

## 八、Git 凭据配置

服务器上推荐配置（避免 token 泄露）：

```bash
# 检查是否有 insteadOf 重写规则（会导致 token 泄露）
git config --get-regexp "url\..*\.(insteadOf|pushInsteadOf)"

# 清除重写规则
git config --global --unset-all "url.https://oauth2:xxx@github.com.insteadof"

# 设置干净的 remote URL
git remote set-url origin https://github.com/MTCat-z/OpsFlow.git

# 用 credential store 存储凭据
git config --local credential.helper store
echo "protocol=https
host=github.com
username=MTCat-z
password=github_pat_xxx" | git credential approve
```

---

## 九、页面清单（14 个）

| 路径 | 页面 | 备注 |
|------|------|------|
| /dashboard | 运维数据大屏 | 统计卡片 + ECharts + 到期倒计时 |
| /assets | 资产管理 | 设备台账 + SSH 凭据 |
| /scan | Nmap 扫描 | 异步扫描任务 |
| /iperf | 性能测试 | Iperf3 带宽测试 |
| /broadband | 宽带管理 | 合同管理 + 续费告警 + 导入导出 |
| /topology | 网络拓扑 | AntV G6 可视化 |
| /diagnostics | 网络诊断 | Ping/Traceroute/DNS/Port/MTR |
| /zabbix | Zabbix 监控 | 仪表盘 + 主机详情 |
| /inspection | 自动化巡检 | 巡检方案 + 运行记录 |
| /config-backup | 配置备份 | 网络设备配置快照 + Diff |
| /commands | 批量命令执行 | 多设备批量命令 |
| /ipam | IPAM | IP 地址管理 |
| /users | 用户管理 | 管理员可见 |
| /audit | 审计日志 | 管理员可见 |

---

## 十、后续维护建议

1. **每次改动后更新本文档**，记录新踩的坑和解决方案
2. **push 前必须本地验证**：lint + build + 语法检查
3. **服务器更新优先用 `bash deploy/upgrade.sh`**，不要先手动 pull
4. **如果脚本出问题**：手动 `git pull` + `docker compose build --no-cache` + `up -d`
5. **网络不稳定时**：commit 不丢，多试几次 push 即可
6. **改 Nginx 配置后**：需要重建 nginx 容器（`docker compose up -d --force-recreate nginx`），因为配置是构建时 COPY 的
7. **改后端 .env 后**：需要重启后端容器（`docker compose restart backend celery_worker celery_beat`）
