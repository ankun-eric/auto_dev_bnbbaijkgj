# 部署报告

**部署时间**: 2026-06-06 13:45 UTC  
**部署状态**: ✅ 成功  
**DEPLOY_ID**: `6b099ed3-7175-4a78-91f4-44570c84ed27`

---

## 1. 项目域名

- **主域名**: https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com
- **管理后台**: https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/admin/
- **API 端点**: https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/

---

## 2. 容器运行状态

| 容器名称 | 状态 | 健康检查 |
|---------|------|---------|
| `6b099ed3-...-db` | Up ~1h | healthy |
| `6b099ed3-...-backend` | Up ~30m | healthy |
| `6b099ed3-...-h5` | Up ~30m | healthy |
| `6b099ed3-...-admin` | Up ~30m | healthy |

所有 4 个容器均正常运行并通过健康检查。

---

## 3. 外部验证

| 端点 | HTTP 状态 | 响应 |
|------|----------|------|
| `/api/health` | 200 | `{"status":"ok","service":"bini-health-api"}` |
| `/` (H5) | 200 | ✅ |
| `/admin/` | 200 | ✅ |

---

## 4. 数据库状态

- **数据库类型**: MySQL 8.0 (Docker 容器)
- **数据库名**: `bini_health`
- **数据表数量**: 258 张
- **初始化状态**: ✅ 已完成（SQLAlchemy create_all）

## 5. 默认管理员账号

| 字段 | 值 |
|------|-----|
| ID | 1 |
| 手机号 | 13800000000 |
| 角色 | admin |
| 超级管理员 | 是 (is_superuser=1) |
| 状态 | active |

**其他管理员**:
- ID 16: 13800050505 (admin, superuser)
- ID 36: 13800013800 (admin)
- ID 216: admin (admin, 使用"admin"作为手机号)

> 注：本系统使用手机号+密码登录，无传统 username 字段。如需创建 admin/admin123 经典账号，可通过后台或 API 操作。

---

## 6. Gateway 配置

- **配置文件**: `/home/ubuntu/gateway/conf.d/6b099ed3-7175-4a78-91f4-44570c84ed27.server`
- **Nginx 语法测试**: ✅ 通过
- **Nginx 重载**: ✅ 成功
- **Gateway 容器**: `gateway-nginx` 已接入项目 Docker 网络
- **路由规则**:
  - `/api/` → backend:8000
  - `/uploads/` → backend:8000
  - `/admin/` → admin:3000
  - `/` → h5:3001

---

## 7. 执行步骤回顾

### 阶段 0：deploy_msg.txt
✅ 部署配置已存在于 `deploy/deploy_msg.txt`

### 阶段 1：项目分析
✅ 确认项目结构：backend (8000) + h5-web (3001) + admin-web (3000) + MySQL

### 阶段 1.5：服务器环境预检（6项）
✅ 1. Gateway nginx 配置结构 - 正常，conf.d 使用 .server 扩展名  
✅ 2. 路由占用检查 - 端口 8000/3000/3001 未占用，Gateway 配置已由 .server 文件提供  
✅ 3. ACR 基础镜像 - python:3.12-slim 已存在，node:20-alpine 需拉取  
✅ 4. Docker 网络拓扑 - 项目网络已存在，gateway-nginx 已接入  
✅ 5. 基础镜像内置工具 - Python 3.12.13 + pip 25.0.1  
✅ 6. 磁盘空间 - 217G 总量，117G 可用（44%）

### 阶段 2：容器化配置
✅ 更新 deploy/Dockerfile.h5 - 添加 BUILD_COMMIT arg + BUILD_INFO  
✅ 更新 deploy/Dockerfile.admin - 添加 BUILD_COMMIT arg + BUILD_INFO  
✅ 更新 deploy/docker-compose.prod.yml - 添加 BUILD_COMMIT args + 修正 DATABASE_URL + 修正域名 URL

### 阶段 3：远程部署
✅ Git 拉取最新代码（commit: 1b1f915e）  
✅ ACR 登录成功  
✅ Docker Compose 服务确认运行中（4个容器均 healthy）  
✅ Gateway 配置更新（.server 文件已生效，修复重复 .conf 文件冲突）  
✅ Nginx 语法测试通过 + 重载成功  
✅ 数据库已初始化（258 张表）  
✅ 管理员账号已存在

---

## 8. 遇到的问题及解决方案

### 问题 1：Gateway 配置重复冲突
**现象**: 写入 .conf 文件后 nginx -t 报 "server directive is not allowed here"  
**原因**: 项目 Gateway 使用 `.server` 扩展名（在 nginx.conf 主配置中独立 include），同时写入 `.conf` 文件导致重复加载且在错误的上下文中  
**解决**: 将重复的 .conf 文件重命名为 .conf.dup_disabled，保留已有的 .server 配置

### 问题 2：docker cp 失败（只读卷）
**现象**: `docker cp` 到 gateway-nginx 容器报 "mounted volume is marked read-only"  
**原因**: Gateway 容器的 conf.d 目录通过 bind mount 挂载宿主目录，非容器内可写  
**解决**: 直接写入宿主目录 `/home/ubuntu/gateway/conf.d/`，nginx 自动通过 bind mount 读取

### 问题 3：数据库连接方式差异
**现象**: deploy/docker-compose.prod.yml 原 DATABASE_URL 指向腾讯云外网 MySQL  
**解决**: 修正为连接本地 Docker 网络内的 MySQL 容器：`mysql+aiomysql://root:bini_health_2026@6b099ed3-...-db:3306/bini_health`

---

## 9. 总结

部署已成功完成。所有服务正常运行，Gateway 路由生效，数据库已初始化，管理员账号可用。

**项目访问**: https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com
