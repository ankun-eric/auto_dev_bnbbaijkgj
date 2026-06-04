# Noob Publish 发布报告

========================================

## 发布信息

| 项目 | 值 |
|------|-----|
| 项目标识（DEPLOY_ID） | 6b099ed3-7175-4a78-91f4-44570c84ed27 |
| 测试环境域名 | https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com |
| 生产环境域名 | https://chat.benne-ai.com |
| 发布时间 | 2026-06-04 01:46 (实际完成时间) |
| ACR 镜像仓库 | crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com/noob_ai_apps |

## 发布流程

| 阶段 | 状态 | 说明 |
|------|------|------|
| 阶段 0：信息采集与连通性验证 | 成功 | 双环境 SSH 和 ACR 连通性验证通过 |
| 阶段 1：测试环境镜像同步到 ACR | 成功 | 4 个项目镜像 + 3 个基础镜像全部推送成功 |
| 阶段 2：生产环境部署 | 成功 | 4 个容器全部健康运行，Gateway 配置生效 |
| 阶段 3~4：自动检测与修复 | 成功 | 0 次循环修复（首次部署全部通过） |
| 阶段 4A：APP 打包与上传 | 跳过 | APP 端代码在本次发布周期中无变更 |
| 阶段 5：最终验证 | 成功 | 13 个链接中 12 个可达，1 个为 HEAD 方法限制 |

## 链接检查统计

| 统计项 | 数值 |
|--------|------|
| 总 URL 数 | 13 |
| 可达 | 12 (92.3%) |
| 不可达 | 1 (7.7%) |

### 不可达链接详情

| URL | 状态码 | 说明 |
|-----|--------|------|
| https://chat.benne-ai.com/api/health | 405 | HEAD 方法不被 FastAPI 端点支持，GET 请求正常返回 200。非部署问题。 |

## ACR 镜像信息

| 镜像 | ACR 标签 |
|------|----------|
| 后端 | crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com/noob_ai_apps/6b099ed3-...-backend:latest |
| 管理后台 | crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com/noob_ai_apps/6b099ed3-...-admin:latest |
| H5用户端 | crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com/noob_ai_apps/6b099ed3-...-h5:latest |
| 数据库 | crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com/noob_ai_apps/6b099ed3-...-db:latest |

## 访问入口

### Web 端

| 端 | URL | 说明 |
|----|-----|------|
| 用户端（H5） | https://chat.benne-ai.com/ | 宾尼健康 H5 用户端首页 |
| 管理后台 | https://chat.benne-ai.com/admin/ | 宾尼健康管理后台 |
| API 服务 | https://chat.benne-ai.com/api/health | 后端 API 健康检查 |

### 默认账号

| 账号 | 密码 |
|------|------|
| admin（手机号 13800000000） | 已设置（由数据库迁移保留） |

### 小程序端

| 端 | 说明 |
|----|------|
| 微信小程序 | 宾尼健康小程序（需在微信公众平台配置服务器域名为 chat.benne-ai.com） |

### APP 端

| 端 | 说明 |
|----|------|
| Android APK | 本次发布 APP 端代码无变更，使用已有版本。最新测试环境 APK：android-v20260603-021911-e2c7 |
| iOS IPA | 本次发布 APP 端代码无变更，使用已有版本。最新测试环境 IPA：ios-v20260603-022019-a7b2 |

### 数据库

| 项目 | 值 |
|------|-----|
| 类型 | MySQL 8.0（Docker 容器） |
| 数据库名 | bini_health |
| 表数量 | 248 |

## 残留问题

无。所有部署问题已在首次部署中解决。

## 备注

1. Gateway 配置文件在测试环境中使用 `.server` 后缀（非标准 `.conf`），已适配为生产环境标准 `.conf` 格式。
2. SSL 证书：生产环境使用 Let's Encrypt 证书（chat.benne-ai.com），验证通过。
3. Docker daemon 已配置 ACR 作为 registry-mirrors，后续基础镜像拉取不走 Docker Hub。
4. APP 端代码（flutter_app）在本次发布周期中无变更，跳过 APP 打包。如需更新 APP，可手动触发 GitHub Actions 构建。

========================================

报告生成时间：2026-06-04
