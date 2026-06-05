# Noob Deploy 部署报告

**部署时间**: 2026-06-05
**项目名称**: 宾尼健康 (Bini Health)
**DEPLOY_ID**: `6b099ed3-7175-4a78-91f4-44570c84ed27`
**部署类型**: BUG FIX — 修复健康档案家庭成员"邀请记录"弹窗空白问题

---

## 一、部署状态总览

| 阶段 | 状态 | 说明 |
|------|------|------|
| 阶段 0: 服务器信息 | ✅ 完成 | `deploy/deploy_msg.txt` 已包含完整的服务器、Git、ACR、数据库信息 |
| 阶段 1: 项目分析 | ✅ 完成 | DEPLOY_ID 已提取，容器清单已确认（3 容器: backend + h5-web + admin-web） |
| 阶段 1.5: 服务器预检 | ❌ 阻塞 | 目标服务器 SSH 服务无响应（详见下方诊断） |
| 阶段 2: 容器化配置 | ✅ 完成 | 所有配置文件已存在且验证通过 |
| 阶段 3: 远程部署 | ❌ 阻塞 | 因阶段 1.5 SSH 不可用，无法执行远程操作 |

---

## 二、SSH 连接故障诊断

### 目标服务器信息
- **域名**: `newbb.test.bangbangvip.com`
- **解析 IP**: `134.175.97.26`
- **SSH 端口**: `22`
- **SSH 用户**: `ubuntu`

### 诊断结果
| 检测项 | 结果 |
|--------|------|
| DNS 解析 | ✅ `newbb.test.bangbangvip.com` → `134.175.97.26` |
| ICMP Ping | ✅ 165ms 延迟，网络可达 |
| TCP 端口 22 | ✅ 端口开放（SYN-ACK 正常） |
| TCP 端口 80 | ✅ 端口开放 |
| TCP 端口 443 | ✅ 端口开放 |
| SSH Banner 接收 | ❌ **超时** — TCP 连接建立后，服务器端未发送 SSH 协议 Banner |
| HTTP 响应 | ❌ 超时 — 端口 80/443 同样无应用层响应 |

### 尝试过的连接方式
1. OpenSSH (Windows) + 密码认证 → `Connection timed out during banner exchange`
2. OpenSSH + SSH Key (id_rsa / id_rsa_deploy / id_ed25519_new) → 同上
3. paramiko (Python) → `Error reading SSH protocol banner`
4. ssh2 (Node.js) → 握手超时
5. plink (PuTTY) → 超时

### 根本原因分析
服务器 `134.175.97.26` 的 TCP 22/80/443 端口均接受连接但无应用层响应，这表明：
- 服务器可能处于崩溃/挂起状态
- Docker 服务和所有容器可能已停止
- 或存在负载均衡器/代理层在转发，但后端实例全部宕机

### 建议恢复操作
1. 通过云控制台（腾讯云）直接重启服务器实例
2. 或使用 VNC/串口控制台登录服务器
3. 重启后检查 Docker 服务：`systemctl status docker`
4. 手动启动项目容器：`cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && docker compose -f docker-compose.prod.yml up -d`

---

## 三、项目配置验证（阶段 0~2）

### 3.1 阶段 0：服务器信息 (`deploy/deploy_msg.txt`)

所有必需信息已完整记录：
- 项目域名：`6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com`
- 泛域名基础：`noob-ai.test.bangbangvip.com`
- 服务器：`newbb.test.bangbangvip.com:22`
- Git 仓库：`codeup.aliyun.com/.../6b099ed3-...84ed27.git`
- ACR 仓库：`crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com`
- 数据库：MySQL (腾讯云 RDS: `gz-cdb-nniq1lmp.sql.tencentcdb.com:27082`)

### 3.2 阶段 1：项目分析

| 项目 | 详情 |
|------|------|
| **DEPLOY_ID** | `6b099ed3-7175-4a78-91f4-44570c84ed27` |
| **技术栈** | Backend: Python FastAPI (port 8000) + H5: Next.js 14 (port 3001) + Admin: Next.js 14 (port 3000) |
| **数据库** | MySQL 8.0 (腾讯云 RDS) |
| **容器清单** | `6b099ed3-...-backend`, `6b099ed3-...-h5`, `6b099ed3-...-admin` |
| **Docker 网络** | `6b099ed3-...-network` |

### 3.3 阶段 2：容器化配置验证

#### docker-compose.prod.yml ✅
- 3 个 service：backend (8000)、admin-web (3000)、h5-web (3001)
- 所有 container_name 以 `{DEPLOY_ID}-` 开头
- 网络名：`6b099ed3-7175-4a78-91f4-44570c84ed27-network`
- healthcheck 已配置（python3/node 原生 + wget + curl 三重兜底）
- 数据库连接指向腾讯云 RDS

#### Dockerfile 验证 ✅

| 服务 | 基础镜像 | 端口 | 构建方式 |
|------|---------|------|---------|
| backend | `crpi.../noob_doker_base/python:3.12-slim` | 8000 | 单阶段 (pip + uvicorn) |
| h5-web | `crpi.../noob_doker_base/node:20-alpine` | 3001 | 多阶段 (Next.js standalone) |
| admin-web | `crpi.../noob_doker_base/node:20-alpine` | 3000 | 多阶段 (Next.js standalone) |

- ✅ ACR 镜像优先
- ✅ 国内镜像源 (npm: npmmirror.com, pip: mirrors.cloud.tencent.com)
- ✅ BUILD_INFO 层已配置
- ✅ 多阶段构建 (前端：builder → runner)

#### Gateway 路由配置 ✅
- 文件：`deploy/6b099ed3-7175-4a78-91f4-44570c84ed27.server`
- 完整 `server` 块配置（标准模式）
- 路由规则：
  - `/api/` → `{DEPLOY_ID}-backend:8000`
  - `/uploads/` → `{DEPLOY_ID}-backend:8000`
  - `/admin/` → `{DEPLOY_ID}-admin:3000`
  - `/` → `{DEPLOY_ID}-h5:3001`
- ✅ `resolver 127.0.0.11` 已配置
- ✅ SSL 证书引用通配符证书
- ⚠️ 服务器端文件名需为 `.conf`（当前本地为 `.server`）

---

## 四、本次变更内容

### BUG FIX: 修复"邀请记录"弹窗空白

**文件**: `h5-web/src/app/health-profile/archive-list/page.tsx`

**变更**: 修改 `InvitationHistoryDrawer` 组件中的 `endpoints` 数组，前端接口路径对齐后端：

```typescript
// 修复后的接口路径
const endpoints = [
  `/api/guardian/v13/family/invite-history?managed_member_id=${member.member_id}`,
];
```

---

## 五、部署后续步骤（SSH 恢复后执行）

当服务器 SSH 恢复后，执行以下命令完成部署：

```bash
# 1. SSH 连接
ssh ubuntu@newbb.test.bangbangvip.com

# 2. 进入项目目录并拉取最新代码
cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27
git fetch codeup master --depth 1
git reset --hard codeup/master
git clean -fd

# 3. 设置 BUILD_COMMIT 并重新构建 h5-web
export BUILD_COMMIT=$(git log -1 --format="%H")
docker compose -f docker-compose.prod.yml build --no-cache h5-web

# 4. 重启 h5-web 容器
docker compose -f docker-compose.prod.yml up -d h5-web

# 5. 验证
docker ps --filter name=6b099ed3
curl -sk https://localhost/ -H 'Host: 6b099ed3-....noob-ai.test.bangbangvip.com' | head -20
```

---

## 六、关键信息汇总

| 项目 | 值 |
|------|-----|
| **项目域名** | `https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com` |
| **DEPLOY_ID** | `6b099ed3-7175-4a78-91f4-44570c84ed27` |
| **服务器** | `newbb.test.bangbangvip.com` (134.175.97.26) |
| **SSH** | `ubuntu@newbb.test.bangbangvip.com:22` (密码: Newbang888) |
| **项目目录** | `/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27` |
| **Gateway 配置** | `/home/ubuntu/gateway/conf.d/6b099ed3-7175-4a78-91f4-44570c84ed27.conf` |
| **默认账号** | `admin / admin123` |
| **数据库** | MySQL RDS `gz-cdb-nniq1lmp.sql.tencentcdb.com:27082` (库: bini_health) |
| **容器端口** | backend:8000, h5-web:3001, admin-web:3000 |

---

## 七、最终结论

**部署状态**: ⚠️ **部分完成（阻塞于服务器 SSH 不可用）**

- ✅ 阶段 0~2 已全部完成，所有配置文件验证通过
- ❌ 阶段 3 无法执行：目标服务器 `134.175.97.26:22` SSH 服务无响应
- 📋 本次 BUG FIX 内容为前端代码变更（1 个文件），不涉及 Docker 配置修改
- 🔧 服务器恢复后，仅需 `git pull + docker compose build h5-web + up -d h5-web` 即可完成部署

