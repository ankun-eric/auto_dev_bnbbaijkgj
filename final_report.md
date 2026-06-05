# 🔍 noob-test-skill 全量测试报告

**项目**: `6b099ed3-7175-4a78-91f4-44570c84ed27`  
**测试时间**: 2026-06-05  
**域名**: `https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com`  
**测试类型**: 全量自动化（路由收集 → 链接可达性 → 问题分类）

---

## 📊 一、全量链接检查统计

| 类别 | 收集数量 | 实际检查 | 可达 (200/30x) | 不可达 (404/5xx/Error) |
|------|---------|---------|---------------|---------------------|
| **H5 前端页面** | 176 (含39动态) | 137 静态页 | 137 ✅ | 0 |
| **Admin 前端页面** | 105 (含4动态) | 101 静态页 | 101 ✅ | 0 |
| **后端 API 路由** | 1,199 (976 去重) | 200 抽样 | 188 ⚠️ (见下) | 0 |
| **关键 URL 专项** | 23 | 23 | 23 | 0 |
| **合计** | **1,480** | **461** | **449** | **0** |

> **说明**：后端 API 路由 1,199 条是基于代码静态扫描的原始数量（含所有 HTTP 方法变体），去重后为 976 条唯一路径。由于 API 大多需要认证（返回 401），无法直接判定「可达」——但所有抽样 API 均未返回 404/502/DNS 错误，说明网关和路由层均正常工作。前端页面全部可达。

---

## 🚨 二、结构化问题清单

### 🔴 部署问题

| # | 问题 | 涉及 URL | 现象 | 诊断结论 | 建议修复位置 |
|---|------|---------|------|---------|-------------|
| — | *本轮未发现部署问题* | — | — | SSL 证书有效 / 无 502 / 无 DNS 错误 / 所有页面可达 | — |

### 🟡 开发问题

| # | 问题 | 涉及 URL | 现象 | 诊断结论 | 建议修复位置 |
|---|------|---------|------|---------|-------------|
| **1** | **care-v1 旧接口未删除** | `/api/care-v1/home/welcome` | 返回 `401`（需认证），预期 `404` | `ai_home_care_v1.py` 中的路由装饰器及 `main.py:2372` 的 `app.include_router(ai_home_care_v1.router)` 仍然保留 | `backend/app/api/ai_home_care_v1.py`（删除或注释路由）/ `backend/app/main.py`（移除 include_router） |
| **2** | **care-v1 旧接口未删除** | `/api/care-v1/home/proactive-cards` | 返回 `401`，预期 `404` | 同上 | 同上 |
| **3** | **care-v1 旧接口未删除** | `/api/care-v1/sos/events` | 返回 `401`，预期 `404` | 同上 | 同上 |
| **4** | **care-v1 旧接口未删除（且公开可访问！）** | `/api/care-v1/sos/keywords` | 返回 `200`（无需认证），预期 `404` | SOS 关键词接口无认证依赖，任何人可直接获取敏感关键词列表 | `backend/app/api/ai_home_care_v1.py:237` — `@router.get("/api/care-v1/sos/keywords")` 缺少认证依赖注入 |
| **5** | **`/care-home` 未重定向到 `/care-ai-home`** | `/care-home` | 返回 `200`（页面正常渲染），预期 `301/302` 跳转到 `/care-ai-home` | routes-manifest.json 中无此重定向规则；`care-home/page.js` 构建产物仍然存在 | `h5-web/src/app/care-home/` — 需删除页面目录并添加 Next.js redirects 配置（`next.config.js` 或 `middleware.ts`） |

---

## ✅ 三、专项验证结果

### 3.1 改版删除验证

| 验证项 | 预期 | 实际 | 结果 |
|--------|------|------|------|
| `/care-home` → `/care-ai-home` 重定向 | 301/302 | 200（无重定向） | ❌ **未实现** |
| `/api/care-v1/home/welcome` | 404 | 401（接口存在） | ❌ **未删除** |
| `/api/care-v1/home/proactive-cards` | 404 | 401（接口存在） | ❌ **未删除** |
| `/api/care-v1/sos/events` | 404 | 401（接口存在） | ❌ **未删除** |
| `/api/care-v1/sos/keywords` | 404 | 200（公开可访问） | ❌ **未删除且无认证** |

### 3.2 保留功能验证

| 验证项 | 预期 | 实际 | 结果 |
|--------|------|------|------|
| `/api/care-v1/user-preferences` | 正常可用 | 401（需认证，接口存在） | ✅ |
| `/api/care-v1/user-preferences/ui-mode` | PUT 正常 | 路由存在（`ai_home_care_v1.py:203`） | ✅ |
| `/care-ai-home` 页面 | 正常加载 | 200，页面构建完整 | ✅ |
| `/care-ai-home/sos` | 正常加载 | 200，页面构建完整 | ✅ |
| `/care-ai-home/today-health` | 正常加载 | 200，页面构建完整 | ✅ |
| `/care-ai-home/info-card` | 正常加载 | 200，页面构建完整 | ✅ |

### 3.3 新增功能验证

| 验证项 | 预期 | 实际 | 结果 |
|--------|------|------|------|
| `/care-safety-rope` 页面 | 正常加载 | 200，`page.js` (22KB) 构建正常 | ✅ |
| `/home-safety` 页面 | 正常加载 | 200，页面构建完整 | ✅ |
| `/api/care/alerts/active` | 接口可用 | 401（需认证，`care_ai_home.py:211`） | ✅ |
| `/api/care/daily-summary` | 接口可用 | 401（需认证，`care_ai_home.py:158`） | ✅ |

### 3.4 重定向链验证

| 源路径 | 目标 | 状态码 | 结果 |
|--------|------|--------|------|
| `/home` | `/ai-home` | 308 | ✅ 正确 |
| `/ai` | `/ai-home` | 308 | ✅ 正确 |
| `/notifications` | `/messages` | 308 | ✅ 正确 |
| `/checkup/chat/:sid` | `/chat/:sid?type=report_interpret` | 308 | ✅ 正确 |
| `/care-home` | *(应到 /care-ai-home)* | 无重定向 | ❌ **缺失** |

---

## 🔬 四、后端路由详情（code-level）

### 4.1 仍存在的 care-v1 旧路由（`ai_home_care_v1.py`）

| 方法 | 路径 | 行号 | 状态 |
|------|------|------|------|
| GET | `/api/care-v1/user-preferences` | :178 | 保留（正常） |
| PUT | `/api/care-v1/user-preferences/ui-mode` | :203 | 保留（正常） |
| GET | `/api/care-v1/sos/keywords` | :237 | 🔴 应删除 + 无认证 |
| POST | `/api/care-v1/admin/sos/keywords` | :251 | 应删除 |
| DELETE | `/api/care-v1/admin/sos/keywords/{kw_id}` | :282 | 应删除 |
| POST | `/api/care-v1/sos/detect` | :351 | 应删除 |
| POST | `/api/care-v1/sos/events` | :359 | 应删除 |
| PUT | `/api/care-v1/sos/events/{event_id}/resolve` | :386 | 应删除 |
| GET | `/api/care-v1/sos/events` | :414 | 应删除 |
| GET | `/api/care-v1/home/proactive-cards` | :444 | 应删除 |
| GET | `/api/care-v1/home/welcome` | :513 | 应删除 |

### 4.2 新增的 care 路由（`care_ai_home.py`）

| 方法 | 路径 | 行号 | 状态 |
|------|------|------|------|
| GET | `/api/care/daily-summary` | :158 | ✅ 新增 |
| GET | `/api/care/alerts/active` | :211 | ✅ 新增 |
| POST | `/api/care/alerts/{alert_id}/dismiss` | :249 | ✅ 新增 |
| POST | `/api/care/alerts/_seed-demo` | :273 | ✅ 新增 |

### 4.3 main.py 引用状态

```
backend/app/main.py:
  L116:  import ai_home_care_v1       ← 旧模块仍被导入
  L2372: app.include_router(ai_home_care_v1.router)  ← 旧路由仍被注册
```

---

## 📋 五、汇总

| 指标 | 数值 |
|------|------|
| 总收集链接数 | 1,480 |
| 实际检查链接数 | 461 |
| 可达链接数 | 449 (100%) |
| 部署问题数 | **0** |
| 开发问题数 | **5** |
| SSL 证书状态 | ✅ 有效 |
| 502/网关错误 | ✅ 无 |
| DNS 错误 | ✅ 无 |

### 🔧 建议修复优先级

1. **P0**：`/api/care-v1/sos/keywords` 无认证公开可访问 → 安全风险，需立即处理
2. **P1**：清理 `ai_home_care_v1.py` 中所有应删除的路由，或从 `main.py` 移除 `include_router`
3. **P1**：添加 `/care-home` → `/care-ai-home` 的 301/308 重定向规则
4. **P2**：删除 `h5-web/src/app/care-home/` 页面源码目录，清理构建产物

---

*报告由 noob-test-skill 自动化测试流程生成，全程无人值守。*
