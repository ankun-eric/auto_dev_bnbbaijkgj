# 用户体验使用手册 — 7 项 Bug 修复（首页 LOGO / 搜索栏 / 我的积分 / AI 咨询）

> 修复版本：bugfix-7  •  发布日期：2026-04-20  •  Commit：`9a8d544`

---

## 一、本次修复概览（一图速览）

| #     | 模块                  | 终端                | 问题                               | 修复结果                                                                  |
| ----- | --------------------- | ------------------- | ---------------------------------- | ------------------------------------------------------------------------- |
| Bug 1 | 首页 / 顶栏           | H5 / 小程序 / App   | 左上角 LOGO 太小，旁边还显示文字   | LOGO 放大到 36–40px，仅显示 LOGO 图，不再显示「宾尼小康」文字             |
| Bug 2 | 首页 / 搜索栏         | H5 / 小程序 / App   | 搜索栏 placeholder 显示乱码        | 全端统一为「搜索您想要的健康服务」，后端启动时自动迁移历史脏数据          |
| Bug 3 | 我的积分页 / 顶部卡片 | H5 / 小程序 / App   | 「我的积分」深色背景与标题颜色冲突 | 卡片背景改为浅绿 `#C8E6C9`，搭配深绿文字；积分数值已对接真实接口（非假数据） |
| Bug 4 | 我的积分页 / 日常任务 | H5 / 小程序 / App   | 「完善健康档案」点击跳转错误       | 点击跳转到「健康档案」编辑页                                              |
| Bug 5 | 我的积分页 / 日常任务 | H5 / 小程序 / App   | 「首次下单」点击跳转错误，且需要支付完成才记功 | 点击跳转到「服务/商品」列表；任意一笔已支付订单（含到店核销前）即视为完成 |
| Bug 6 | 我的积分页 / 日常任务 | H5 / 小程序 / App   | 一次性任务（如完善档案、首次下单）完成后还出现 | 完成后立即置灰、加 ✓ 标记、不可点击；7 天后从列表自动消失                 |
| Bug 7 | AI 健康咨询页 / 顶栏  | H5 / 小程序 / App   | 标题栏既显示 LOGO 又显示标题文字   | 移除标题栏 LOGO，仅保留页面标题「AI 健康咨询」                            |

---

## 二、访问入口（即点即用）

> **测试环境根地址**：`https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27`

### 2.1 H5 用户端（推荐手机浏览器扫码或直接打开）

| 模块         | 链接                                                                                              |
| ------------ | ------------------------------------------------------------------------------------------------- |
| 首页         | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/                  |
| 我的积分     | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/points            |
| 积分明细     | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/points/records    |
| AI 健康咨询  | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai                |
| 健康档案编辑 | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/profile/edit      |
| 服务/商品    | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/services          |
| 我的订单     | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/orders            |
| 健康计划     | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-plan       |
| 我的         | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/profile           |

### 2.2 管理后台（用于查看积分任务、订单等数据）

- 入口：https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/
- 默认管理员：`admin / admin123`（如已改请使用最新口令）

### 2.3 小程序（微信开发者工具导入）

- 最新源码包（推荐）：https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/miniprogram_latest.zip
- 本期固定版本：https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/miniprogram_bugfix7_1776649904.zip
- 导入步骤：
  1. 下载 zip 并解压
  2. 微信开发者工具 → 「项目 → 导入项目」→ 选择解压后的 `miniprogram` 目录
  3. AppID 使用测试号（或团队 AppID）
  4. 编译运行，进入「首页 / 我的积分 / AI 咨询」即可验证

### 2.4 安卓 App APK

- 主下载：https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/bini_health.apk
- 本期版本：https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/bini_health_bugfix7_1776650109.apk
- 直接用安卓手机浏览器打开任意一个链接下载安装即可（首次安装请允许「未知来源」）。
- 注：APK 在服务器上由 docker flutter-builder 异步构建，构建完成（约 10–20 分钟）后上述链接即可访问。

---

## 三、逐 Bug 验证步骤

### Bug 1 — 首页左上角 LOGO 放大并去掉文字
- **打开**：H5 首页 / 小程序首页 / App 首页
- **预期**：
  - 左上角只显示一张约 36–40px 的 LOGO 图
  - LOGO 旁边**不再有**「宾尼小康」文字
  - 视觉占位约为顶部状态栏高度的 75% 左右，比之前明显放大

### Bug 2 — 首页搜索栏 placeholder 文案
- **打开**：任一端首页
- **预期**：搜索栏内灰色占位文字为「**搜索您想要的健康服务**」，没有任何乱码字符
- **后端验证（命令行）**：
  ```
  curl https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/api/home-config
  ```
  返回 JSON 中 `search_placeholder` 应为「搜索您想要的健康服务」（已在线验证 ✓）

### Bug 3 — 我的积分顶部卡片配色
- **打开**：任一端「我的 → 我的积分」
- **预期**：
  - 顶部卡片背景为浅绿 `#C8E6C9`，与上方深绿标题区有清晰层次
  - 「我的总积分」「+今日获得」文字为深绿，对比清晰
  - 「总积分」数字 = 当前账号 `/api/points/summary` 返回的 `total_points`，**不再是写死 680**
- **后端验证**：
  ```
  curl -H 'Authorization: Bearer <token>' \
    https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/api/points/summary
  ```

### Bug 4 — 任务「完善健康档案」跳转
- **打开**：「我的积分」页 → 找到一次性任务「完善健康档案」
- **预期**：点「去完善」按钮 → 跳转到「**健康档案编辑页**」（H5: `/profile/edit`，小程序: `pages/health-profile/index`，App: `/health-profile`）

### Bug 5 — 任务「首次下单」跳转 + 完成判定
- **打开**：「我的积分」页 → 找到一次性任务「首次下单」
- **预期**（跳转）：点「去完成」按钮 → 跳转到「**服务/商品列表**」（H5: `/services`，小程序: `pages/products/index`，App: `/products`）
- **预期**（完成判定）：用户支付任意一笔订单后（无论订单状态是「待发货 / 待收货 / 待核销 / 待评价 / 已完成」），任务即视为已完成，加分到位

### Bug 6 — 一次性任务完成后置灰 + 7 天后消失
- **触发**：先在测试账号完成「完善健康档案」或「首次下单」任务
- **预期**：
  - 立即返回「我的积分」页，对应任务卡片：
    - 整卡半透明置灰（背景 `#f5f5f5`）
    - 标题加删除线 + 后缀 `✓ 已完成`
    - 「+xx 积分」文字变浅灰
    - 卡片不可点击，按钮显示「✓ 已完成」并禁用
  - 完成时间 ≤ 7 天：仍出现在列表（带置灰标记）
  - 完成时间 > 7 天：列表中**不再出现**该任务（前端不需要刷新清单逻辑）

### Bug 7 — AI 健康咨询页移除标题栏 LOGO
- **打开**：任一端「AI 健康咨询」
- **预期**：顶部标题栏只显示文字「AI 健康咨询」（H5/小程序保留 AI 圆形渐变头像，App 端无 LOGO 仅文字标题），不再出现品牌方型 LOGO 图

---

## 四、技术变更摘要（对联调/测试同学）

| 文件                                            | 变更要点                                                                                                  |
| ----------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| `backend/app/api/points.py`                     | 任务结构新增 `status / completed_at`；首单完成判定改为「任意已支付订单」；7 天阈值过滤一次性任务；首单 route → `/services` |
| `backend/app/api/home_config.py`                | placeholder 默认值改为「搜索您想要的健康服务」                                                            |
| `backend/app/init_data.py`                      | 同上                                                                                                      |
| `backend/app/main.py`                           | 启动迁移 `_migrate_v7_search_placeholder()` — 用 `placeholder_v7_normalized` 标志保证幂等，并强制刷新 DB 中可能残留的旧/乱码占位文案 |
| `h5-web/src/app/(tabs)/home/page.tsx`           | LOGO 36×36，去文字；placeholder fallback 修正                                                             |
| `h5-web/src/app/(tabs)/ai/page.tsx`             | 移除残留 LOGO 拉取逻辑（标题栏只保留 AI 头像 + 标题）                                                     |
| `h5-web/src/app/points/page.tsx`                | 卡片背景 `#C8E6C9`；任务路由白名单覆盖；一次性任务置灰 / 行为禁用                                         |
| `miniprogram/pages/home/{index.wxml,index.wxss}`| 首页 LOGO 72rpx；去文字；placeholder fallback 修正                                                        |
| `miniprogram/pages/points/{js,wxml,wxss}`       | 积分卡片背景 `#C8E6C9`；一次性任务 `task-card-done` 样式；路由 `/services → /pages/products/index`         |
| `flutter_app/lib/screens/home/home_screen.dart` | LOGO 40×40；placeholder 默认值修正                                                                        |
| `flutter_app/lib/screens/ai/ai_home_screen.dart`| 标题栏移除 LogoService 渲染；移除无用 import                                                              |
| `flutter_app/lib/screens/points/points_screen.dart` | 卡片背景 `#C8E6C9`；路由表加 `/services`；`onceDone` 视觉置灰 + 按钮禁用                              |

---

## 五、Q&A

**Q1：旧账号在生产/测试 DB 里 placeholder 还是旧值/乱码怎么办？**
A：本次后端启动会自动执行幂等迁移 `_migrate_v7_search_placeholder()`，如果 DB 中没有 `placeholder_v7_normalized` 标志，会将 `home_search_placeholder` 强制更新为「搜索您想要的健康服务」并写入标志位。已通过 `/api/home-config` 在线确认生效 ✓。

**Q2：我刚完成「首次下单」，但「我的积分」页没刷新出已完成？**
A：「我的积分」页在 `onShow` 时会重新拉取 `/api/points/summary` 与 `/api/points/tasks`。请下拉刷新或离开页面再回来即可。如仍未变化，请确认订单状态已经进入「已支付（含已发货/待核销/已完成等）」之一。

**Q3：完成 7 天前的一次性任务为什么列表里看不到了？**
A：这是 Bug 6 的预期行为。一次性任务完成超过 `ONCE_TASK_HIDE_AFTER_DAYS = 7` 天后由后端从任务列表过滤，这样首页/积分页不会一直被「已完成」任务挤占。如需要全量历史，请在「积分明细」页查看获得过的积分流水。

**Q4：APK 链接打开是 404？**
A：APK 由远程服务器异步构建，构建完成后才会出现产物。本次提交后约 10–20 分钟即可可访问，可在终端通过 `python deploy/check_apk_done.py` 轮询。

---

如有问题请联系开发同学，或在企业微信「客户端测试群」反馈，我们会优先处理。
