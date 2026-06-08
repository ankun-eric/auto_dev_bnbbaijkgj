# Noob Test 全量链接检查报告

## 部署信息

| 参数 | 值 |
|------|-----|
| 项目域名 | `6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com` |
| 解析 IP | `134.175.97.26` |
| DEPLOY_ID | `6b099ed3-7175-4a78-91f4-44570c84ed27` |
| 服务器 | `newbb.test.bangbangvip.com:22` |
| 检查时间 | 2026-06-07 18:08 UTC |
| 需求描述 | 修复解绑后重新邀请"无法处理邀请"Bug |

---

## 阶段 4.1：路由收集汇总

| 项目 | 路由数 |
|------|--------|
| 后端 API (FastAPI) | 1212 条 |
| h5-web 前端 (Next.js) | 175 条 |
| admin-web 前端 (Next.js) | 108 条 |
| **总计** | **1495 条** |


## 阶段 4.2：链接可达性检查

### 增量检查（需求相关 16 条 URL）

| # | 类型 | URL | 状态码 | 结果 | 备注 |
|---|------|-----|--------|------|------|
| A1 | API GET | /api/family/members | 401 | ✅ | 端点存在需认证 |
| A2 | API GET | /api/family/invitation/test | 404 | ❌ | 业务层"邀请不存在" |
| A3 | API GET | /api/family/management | 401 | ✅ | 端点存在需认证 |
| A4 | API GET | /api/family/managed-by | 401 | ✅ | 端点存在需认证 |
| A5 | API POST | /api/family/invitation | 401 | ✅ | 端点存在需认证 |
| A6 | API POST | /api/family/invitation/test/accept | 401 | ✅ | 端点存在需认证 |
| A7 | API POST | /api/family/member/1/invite | 401 | ✅ | 端点存在需认证 |
| A8 | API POST | /api/family/member/1/unbind | 401 | ✅ | 端点存在需认证 |
| A9 | API GET | /api/health | 200 | ✅ | `{"status":"ok"}` |
| P1 | PAGE | /family-auth | 200 | ✅ | 308→200，CSR |
| P2 | PAGE | /family-invite | 200 | ✅ | 308→200，CSR |
| P3 | PAGE | /family-guardian-list | 200 | ✅ | 308→200，CSR |
| P4 | PAGE | /family-bindlist | 200 | ✅ | 308→200，CSR |
| P5 | PAGE | /family-alert | 200 | ✅ | 308→200，CSR |
| P6 | PAGE | /invite | 200 | ✅ | 308→200，CSR |
| P7 | PAGE | / | 200 | ✅ | SSR，冒烟通过 |

**增量统计**：✅ 15/16 (93.75%) | ❌ 1/16 (6.25%)


### 代表性抽样检查（24 条 URL，覆盖多模块）

| 分类 | 抽样数 | ✅ | ❌ | 成功率 |
|------|--------|----|----|--------|
| 后端 API（auth/users/health/report/products/coupons/merchant/messages/points/settings/admin） | 12 | 12 | 0 | 100% |
| h5-web 前端（首页/登录/健康档案/AI/产品/会员/设置/扫码） | 8 | 8 | 0 | 100% |
| admin-web（/admin 前缀，含登录/仪表盘/用户管理） | 4 | 4 | 0 | 100% |

**SSH 状态**：❌ `newbb.test.bangbangvip.com:22` 连接超时，无法执行服务器内部诊断（gateway/容器层）。

### 关键发现

1. **所有 HTTPS 外部链路正常**：DNS 解析、SSL 证书、nginx gateway 全部工作正常
2. **SSL 证书**：✅ 通过（Schannel TLS 握手成功）
3. **前端路由**：H5 和 Admin 均 Next.js 14 App Router，无尾斜杠路径 308 重定向到 `/` 版本
4. **CSR 冒烟限制**：h5-web 中大部分页面为客户端渲染（CSR），curl 只能获取 `"加载中..."` 占位 HTML，关键词需 JS 执行后才能验证
5. **admin-web 路由前缀**：`/admin/` 和 `/admin-web/` 两种前缀均可达（均 308 重定向），实际有效路由为 `/admin/`


---

## 阶段 4.3：问题收集与分类报告

> ⚠️ 遵循"不修复原则"，以下问题仅做结构化记录，未执行任何自动修复。

### 部署问题（共 1 项）

| # | 问题类型 | 涉及资源 | 现象 | 诊断结论 | 建议修复位置 |
|---|---------|---------|------|---------|-------------|
| D1 | SSH 不可达 | `newbb.test.bangbangvip.com:22` | SSH 连接超时（60s），无法执行服务器内部诊断及容器层检查 | 防火墙/安全组可能未开放 22 端口，或 SSH 服务未启动 | 服务器安全组/防火墙规则 |

### 开发问题（共 2 项）

| # | 问题类型 | 涉及 URL | 现象 | 诊断结论 | 建议修复位置 |
|---|---------|---------|------|---------|-------------|
| C1 | 业务层 404 | `GET /api/family/invitation/test` | 返回 JSON `{"detail":"邀请不存在"}` (HTTP 404) | 端点路由正常（HEAD 返回 405 allow:GET），404 为业务层返回。无有效邀请码 `test`，属预期行为。前端 `getErrorTitle()`（family-auth/page.tsx:391-393）已添加对"不存在"/"邀请不存在"的匹配，修复到位 | 需有效测试数据验证 |
| C2 | Pytest 无法执行 | `backend/tests/test_reinvite_after_unbind_v1_20260607.py` | SSH 不可达（服务器端无法执行），本地 Python 环境异常（import 超时） | 测试文件存在且语法正确，但执行环境未就绪。SSH 端口不可达导致无法在容器内执行 | 开放 SSH 端口后重新执行，或配置本地测试环境 |


---

## 阶段 4.4：业务断言验证与冒烟测试

### 4.4.1 后端业务断言验证

| 项目 | 状态 |
|------|------|
| 测试文件 | `backend/tests/test_reinvite_after_unbind_v1_20260607.py` ✅ 存在 |
| 测试用例数 | 7 个（TC-01 ~ TC-07，含 1 个 skip 的集成测试） |
| 执行环境 | ❌ SSH 不可达 → 无法在服务器容器执行；本地 Python 环境异常 |
| 代码级验证 | ✅ 所有 4 个修复点已在源码中确认存在 |

**源码修复确认**：

| 修复编号 | 描述 | 源码位置 | 状态 |
|---------|------|---------|------|
| 修复一-a | create_invitation 后更新 sub_status="applying" | `family_management.py:226-231` | ✅ |
| 修复一-b | reinvite_member 后更新 sub_status="applying" | `family_member_v2.py:1226-1230` | ✅ |
| 修复二 | create_invitation 前清理旧 inactive mgmt→removed | `family_management.py:179-189` | ✅ |
| 修复三 | 前端 getErrorTitle() 匹配"邀请不存在" | `family-auth/page.tsx:391-393` | ✅ |
| 修复四 | accept_invitation 复用旧 inactive mgmt 记录 | `family_management.py:624-648` | ✅ |


### 4.4.2 前端单元测试

| 项目 | 状态 |
|------|------|
| 测试框架 | 未在 h5-web 或 admin-web 容器中检测到配置（SSH 不可达） |
| 结论 | ⚠️ 前端单元测试环境无法验证（SSH 不可达），跳过 |

### 4.4.3 前端冒烟测试

| 页面 | URL | 渲染模式 | 冒烟结果 | 说明 |
|------|-----|---------|---------|------|
| h5-web 首页 | / | SSR | ✅ 通过 | HTML 含"宾尼小康""AI健康管家" |
| family-auth | /family-auth | CSR | ⚠️ 无法验证 | curl 仅获"加载中..."占位 HTML |
| family-invite | /family-invite | CSR | ⚠️ 无法验证 | 同上 |
| family-guardian-list | /family-guardian-list | CSR | ⚠️ 无法验证 | 同上 |
| family-bindlist | /family-bindlist | CSR | ⚠️ 无法验证 | 同上 |
| family-alert | /family-alert | CSR | ⚠️ 无法验证 | 同上 |
| login (h5) | /login | CSR | ⚠️ 无法验证 | 同上 |
| health-profile | /health-profile | CSR | ⚠️ 无法验证 | 同上 |
| admin 登录 | /admin/login | CSR | ⚠️ 无法验证 | 同上 |
| admin 仪表盘 | /admin/dashboard | CSR | ⚠️ 无法验证 | 同上 |

> **冒烟测试说明**：h5-web 和 admin-web 均使用 Next.js 14 App Router 的客户端渲染模式（CSR）。SSR 阶段仅输出 `<template data-dgst="BAILOUT_TO_CLIENT_SIDE_RENDERING">` 及"加载中..."占位符。业务关键词（按钮文案、表单标签等）需 JS 执行后渲染，curl 无法获取。建议使用 Playwright/Puppeteer 等无头浏览器进行端到端冒烟测试。


---

## 最终汇总

```
========================================
  Noob Test 全量链接检查报告
========================================

部署信息：
  - 项目域名：https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com
  - DEPLOY_ID：6b099ed3-7175-4a78-91f4-44570c84ed27
  - 检查时间：2026-06-07 18:08 UTC

链接检查统计：
  - 总路由数：1495（1212 API + 283 PAGE）
  - 增量检查：16 条
  - 抽样检查：24 条
  - ✅ 外部可达成：39/40 (97.5%)
  - ❌ 不可达：1 条（A2 业务层 404，属预期行为）

问题清单：
  - 部署问题：1 项（SSH 不可达）
  - 开发问题：2 项（业务层 404 + Pytest 无法执行）

需求修复验证（源码级）：
  - ✅ 修复一：create_invitation → sub_status="applying" （family_management.py:226-231）
  - ✅ 修复一：reinvite_member → sub_status="applying" （family_member_v2.py:1226-1230）
  - ✅ 修复二：清理旧 inactive mgmt → removed （family_management.py:179-189）
  - ✅ 修复三：前端 getErrorTitle() 匹配"邀请不存在" （family-auth/page.tsx:391-393）
  - ✅ 修复四：accept 复用旧 inactive mgmt → active （family_management.py:624-648）

========================================
```

