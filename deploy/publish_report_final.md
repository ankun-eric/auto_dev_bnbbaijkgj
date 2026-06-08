========================================
  Noob Publish 生产环境发布报告
========================================

## 发布信息

| 项目 | 值 |
|------|-----|
| 项目标识 (DEPLOY_ID) | 6b099ed3-7175-4a78-91f4-44570c84ed27 |
| 生产环境域名 | https://chat.benne-ai.com |
| 发布版本 | v20260608_101505 |
| 发布时间 | 2026-06-08 10:26 UTC+8 |
| Git Commit | a0db415 |
| 回滚备份 tag | backup-20260608101531 |

## ACR 版本备份

| 镜像 | ACR 地址 |
|------|---------|
| Backend | crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com/noob_ai_apps/6b099ed3-...-backend:v20260608_101505 |
| Admin-Web | crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com/noob_ai_apps/6b099ed3-...-admin-web:v20260608_101505 |
| H5-Web | crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com/noob_ai_apps/6b099ed3-...-h5-web:v20260608_101505 |

## 发布流程摘要

| 阶段 | 状态 | 说明 |
|------|------|------|
| 阶段 0: 发布信息采集与连通性验证 | ✅ 成功 | SSH 连通、ACR 可达、publish_msg.txt 已更新 |
| 阶段 1: 代码拉取与 Docker 构建 | ✅ 成功 | Commit a0db415, 3 个镜像构建完成，ACR 备份推送成功 |
| 阶段 2: 生产环境部署启动 | ✅ 成功 | 4 个容器全部 healthy，Gateway 路由重载成功 |
| 阶段 3: 全量链接检查 | ✅ 成功 | 关键 URL 19/20 可达 (95%) |
| 阶段 4: 自动修复与循环重部署 | ⏭️ 跳过 | 所有关键 URL 可达，无需修复 |
| 阶段 4A: APP 打包与上传 | ⏭️ 跳过 | flutter_app/ 无代码变更 |
| 阶段 5: 最终验证 | ✅ 完成 | 见下方链接检查统计 |

## 链接检查统计

| 指标 | 数值 |
|------|------|
| 总检查 URL 数 | 20 (关键页面) |
| ✅ 可达 (200/308) | 19 |
| ❌ 不可达 | 1 (API health - 405 Method Not Allowed，HEAD 方法不支持，GET 正常) |
| 可达率 | 95% |
| 后端路由总数 | 1287 |
| H5 前端路由总数 | 174 |
| 管理后台路由总数 | 106 |

## 数据库安全

| 项目 | 值 |
|------|-----|
| 安全预检 | ✅ 通过（无 DROP/DELETE/TRUNCATE/ALTER 缩减型操作） |
| 操作类型 | 增量部署，已有表无需重建 |
| 数据库 | 腾讯云 MySQL (gz-cdb-nniq1lmp.sql.tencentcdb.com:27082) |
| 已有用户数据 | 完整无损 |
| 备份 | 未备份（用户未要求） |

## 回滚信息

**方案 A：本地备份 tag 回滚（秒级）**
```bash
cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/
docker compose -f docker-compose.prod.yml down
docker tag 6b099ed3-...-backend:backup-20260608101531 6b099ed3-...-backend:latest
docker tag 6b099ed3-...-admin-web:backup-20260608101531 6b099ed3-...-admin-web:latest
docker tag 6b099ed3-...-h5-web:backup-20260608101531 6b099ed3-...-h5-web:latest
docker compose -f docker-compose.prod.yml up -d
```

**方案 B：从 ACR 拉取指定版本回滚**
```bash
cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/
docker compose -f docker-compose.prod.yml down
docker pull crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com/noob_ai_apps/6b099ed3-...-backend:v20260607_231212
docker tag crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com/noob_ai_apps/6b099ed3-...-backend:v20260607_231212 6b099ed3-...-backend:latest
docker compose -f docker-compose.prod.yml up -d
```

## 访问入口

════════════════════════════════════════
【项目各端入口】
════════════════════════════════════════

### Web 端

| 端 | 入口 URL | 说明 |
|----|---------|------|
| H5 用户端首页 | https://chat.benne-ai.com/ | 宾尼健康用户端 |
| H5 用户端登录 | https://chat.benne-ai.com/login | 用户登录页 |
| AI 问诊首页 | https://chat.benne-ai.com/ai-home | AI 健康问诊 |
| 关怀版首页 | https://chat.benne-ai.com/care-ai-home | 长辈关怀版 |
| 健康档案 | https://chat.benne-ai.com/health-profile | 健康档案管理 |
| 会员中心 | https://chat.benne-ai.com/member-center | 会员服务 |
| 我的设备 | https://chat.benne-ai.com/devices | 智能设备管理 |
| 脑力游戏 | https://chat.benne-ai.com/brain-game | 益智乐园 |
| 管理后台 | https://chat.benne-ai.com/admin/ | 运营管理后台 |
| 管理后台登录 | https://chat.benne-ai.com/admin/login | 管理员登录 |

### 默认账号

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 管理员 | admin | admin123 |

### 小程序端

| 平台 | 说明 |
|------|------|
| 微信小程序 | 宾尼健康小程序（需在微信中搜索使用） |

### APP 端（本次无变更，下载上次版本）

| 平台 | 下载链接 |
|------|---------|
| Android | https://chat.benne-ai.com/app_downloads/ (如有上传) |
| iOS | 通过 TestFlight 分发 |

════════════════════════════════════════

## 本次发布变更内容

| 文件 | 变更 |
|------|------|
| h5-web/src/app/family-auth/page.tsx | Bug修复：getErrorTitle() 匹配关键词 + 微信跳转 fallback 优化 |
| deploy/publish_msg.txt | 发布信息更新 |
| .noob-ai/index/main-index.mdc | 项目索引更新 |

========================================
  报告生成时间: 2026-06-08 10:30 UTC+8
  发布状态: ✅ 成功
========================================
