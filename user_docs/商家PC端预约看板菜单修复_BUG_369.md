# 商家 PC 端「预约看板」菜单修复 — 用户体验使用手册

> 文档编号：BUG_FIX_预约看板_20260507
> 修复版本：基于 PRD-365「预约看板」替换升级 v1.0 之上的菜单可见性与旧路径下线修复
> 适用对象：商家后台所有角色（老板 / 店长 / 财务 / 店员）

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| 商家 PC 端登录 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/login/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/login/) | 商家工作台登录入口 |
| 商家工作台首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/dashboard/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/dashboard/) | 登录后的工作台主页 |
| 预约看板（新版） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/order-dashboard/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/order-dashboard/) | 九宫格驾驶舱样式的新版预约看板 |
| H5 / 客户端首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 项目主页面入口 |

---

## 功能简介

PRD-365 升级后，商家后台原有的「预约日历」页面已整体替换为新版「**预约看板**」（九宫格驾驶舱），路由从 `/merchant/calendar/` 升级为 `/merchant/order-dashboard/`。

但因升级时**菜单权限矩阵未同步更新**，导致出现两个用户可感知的问题：

1. **左侧菜单看不到「预约看板」入口**：所有角色（老板、店长、财务、店员）登录后，左侧菜单都没有「预约看板」这一项，必须靠手输 URL 才能进入；
2. **同一功能两个入口（链接重复）**：访问旧路径 `/merchant/calendar/` 仍能进入页面（自动跳转到新路径），造成"系统有两个看板"的错觉。

本次修复一次性解决以上两个问题：

- ✅ **菜单回归**：所有 4 大类共 9 个角色 key（owner / boss / store_manager / manager / finance / verifier / clerk / staff）的左侧菜单均会显示「**预约看板**」；
- ✅ **链接统一**：旧路径 `/merchant/calendar/` 与移动端 `/merchant/m/calendar/` **彻底下线**，访问直接返回 404；全局只保留 `/merchant/order-dashboard/` 一个入口；
- ✅ **菜单顺序不变**：「预约看板」依然位于「订单管理」之后、「核销记录」之前，与升级前位置完全一致；
- ✅ **页面内容零改动**：预约看板内部的九宫格 UI、KPI 计算、视图切换（日/周/月）等功能逻辑保持不变。

---

## 使用说明

### 步骤 1：登录商家 PC 端

打开浏览器访问 [商家 PC 端登录页](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/login/)，使用您的商家账号登录。

> 💡 任意角色（老板 / 店长 / 财务 / 店员）登录均可看到本次修复效果。

### 步骤 2：在左侧菜单中找到「预约看板」

登录后，浏览器会进入 [商家工作台](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/dashboard/)。请观察左侧菜单：

```
工作台
订单管理
预约看板        ← ✅ 现在能看到了！
核销记录
报表分析
对账结算
...
```

「**预约看板**」菜单项位于「订单管理」之后、「核销记录」之前，图标为日历样式。

### 步骤 3：点击「预约看板」打开新版页面

点击菜单项「**预约看板**」，浏览器会跳转到 [预约看板页面](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/order-dashboard/)，展示 PRD-365 升级后的九宫格驾驶舱：

- 顶部 4 个 Tab：预约看板 / 服务分组日视图 / 资源视图 / 列表视图
- 中间日期切换条：前一天 / 今天 / 后一天 / 日期选择 / 刷新；右侧手机号精确搜索
- 主体九宫格：按时段（06-08 / 08-10 / ... / 22-24）展示当日各时段预约数；4 色状态（待到店 / 已到店 / 已核销 / 已取消）
- 点击任意时段卡片，右侧弹出抽屉展示该时段的全部订单详情，可执行：取消预约 / 联系客户 / 去订单详情

### 步骤 4：验证旧路径已下线

直接在地址栏输入 [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/calendar/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/calendar/)，浏览器应返回 **404 页面**（而不是再跳到新版看板）。

> 这意味着系统中只剩 `/merchant/order-dashboard/` 一个唯一入口，链接重复问题已彻底解决。

---

## 不同角色的可见效果

下表汇总本次修复后，各角色登录商家 PC 端后左侧菜单中「预约看板」的可见性：

| 角色分类 | 角色 key（代码层面） | 是否可见预约看板 | 点击后效果 |
|----------|----------------------|-------------------|-------------|
| 老板 | `owner` / `boss` | ✅ 可见 | 进入新版预约看板 |
| 店长 | `store_manager` / `manager` | ✅ 可见 | 进入新版预约看板 |
| 财务 | `finance` | ✅ 可见 | 进入新版预约看板 |
| 店员 | `verifier` / `clerk` / `staff` | ✅ 可见 | 进入新版预约看板 |

> 💡 您可以使用不同角色账号分别登录验证。

---

## 注意事项

### 历史链接 / 历史书签处理

如果您在浏览器收藏夹、聊天记录、纸质二维码等位置保存了 `/merchant/calendar/` 链接，**这些旧链接现在会显示 404**，请按以下方式处理：

1. **修改书签**：将旧地址中的 `/merchant/calendar` 替换为 `/merchant/order-dashboard`，例如：
   - 旧：`.../merchant/calendar/`
   - 新：`.../merchant/order-dashboard/`
2. **直接通过菜单进入**：登录后点击左侧菜单「预约看板」即可，无需手动输入链接
3. **重新生成的二维码 / 通知模板**会自动指向新地址，无需用户操作

### 移动端入口

商家移动端的工作台首页（`/merchant/m/dashboard/`）原有 4 个快捷入口：核销 / 订单 / 预约日历 / 报表 / 员工 / 对账 / 门店。本次修复一并移除了快捷入口中已失效的「预约日历」一项，避免点击后 404。

> ⚠️ 商家移动端「预约看板」对应的入口 UX 重新设计**不在本次修复范围**，将由后续版本统一规划。

### 后端接口未受影响

本次修复仅涉及商家 PC 端前端页面与菜单显示，后端 API 路径（`/api/merchant/dashboard/*` 与 `/api/merchant/calendar/*`）均未改动，不会影响：

- 已部署的小程序 / APP / H5 端通过后端 API 进行的预约 / 核销操作
- 商家移动端 H5（`/merchant/m/...`）的核销、订单、对账等功能
- 任何依赖 `/api/...` 后端接口的外部对接

### 浏览器缓存

如果您在登录后仍未看到「预约看板」菜单，请尝试：

1. **强制刷新**：按 `Ctrl + F5`（Windows）或 `Cmd + Shift + R`（macOS）
2. **清除缓存**：浏览器开发者工具 → Application → Clear storage → 重新登录
3. **重新登录**：退出当前账号后重新登录一次（确保读取到最新的菜单权限矩阵）

---

## 修复点速览

| 修复点 | 文件 / 范围 | 修改类型 |
|--------|-------------|----------|
| 权限矩阵 9 个角色 key 中 `'calendar'` → `'order-dashboard'` | `h5-web/src/app/merchant/lib.ts` | 代码替换 |
| 删除商家 PC 端旧 calendar 目录 | `h5-web/src/app/merchant/calendar/`（共 12 个文件） | 删除文件 |
| 删除商家移动端旧 calendar 目录 | `h5-web/src/app/merchant/m/calendar/`（共 2 个文件） | 删除文件 |
| 移动端工作台移除已失效的「预约日历」快捷入口 | `h5-web/src/app/merchant/m/dashboard/page.tsx` | 代码删除 |

---

## 验证清单

| 序号 | 验证项 | 预期结果 | 实际结果 |
|------|--------|----------|----------|
| 1 | 商家 PC 端登录页可达 | HTTP 200 | ✅ 通过 |
| 2 | 商家工作台首页可达 | HTTP 200 | ✅ 通过 |
| 3 | 新版预约看板 `/merchant/order-dashboard/` 可达 | HTTP 200 | ✅ 通过 |
| 4 | 旧路径 `/merchant/calendar/` | HTTP 404 | ✅ 通过 |
| 5 | 旧路径 `/merchant/m/calendar/` | HTTP 404 | ✅ 通过 |
| 6 | 商家移动端首页 `/merchant/m/dashboard/` | HTTP 200 | ✅ 通过 |
| 7 | 后端 API `/api/openapi.json` | HTTP 200 | ✅ 通过 |

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| 商家 PC 端登录 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/login/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/login/) | 商家工作台登录入口 |
| 商家工作台首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/dashboard/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/dashboard/) | 登录后的工作台主页 |
| 预约看板（新版） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/order-dashboard/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/order-dashboard/) | 九宫格驾驶舱样式的新版预约看板 |
| H5 / 客户端首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 项目主页面入口 |
