# AI 对话首页 · 左侧抽屉页优化（V7）使用手册

> 版本：PRD-455 V7（最终版）
> 端：H5（`h5-web`）
> 模块：AI 对话首页 → 左上角「☰」按钮 → 左侧抽屉

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 主页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 项目主入口（经 Nginx 代理） |
| AI 对话首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home) | 本次抽屉优化生效页面（左上角 ☰ 触发） |
| 健康档案 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-archive](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-archive) | 抽屉「健康档案」入口 |
| 我的设备 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-devices](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-devices) | 抽屉「我的设备」入口 |
| 统一订单 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/unified-orders](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/unified-orders) | 抽屉「订单」入口 |
| 优惠券 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-coupons](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-coupons) | 抽屉「优惠券」入口 |
| 我的收藏 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-favorites](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-favorites) | 抽屉「收藏」入口 |
| 通知中心 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/notifications](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/notifications) | 抽屉「🔔 铃铛」点击跳转 |
| 设置 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-settings](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-settings) | 抽屉「⚙ 齿轮」点击跳转 |

---

## 功能简介

本次更新对 **AI 对话首页 → 左上角「☰」按钮触发的左侧抽屉页**进行全量重写，整体对齐 PRD V7 最终版，包含以下重点改造：

1. **抽屉宽度从 70% 调整为 85%**，遮罩占右侧 15%（深色半透明，可点击关闭）。
2. **顶栏全新布局**：左侧用户头像 + 右侧三图标（🔔 消息 / ⊞ 会员码 / ⚙ 设置），**取消左上角 × 关闭键**，整体上移消除留白。
3. **用户身份信息升级**：将原「VIP 会员号」文案替换为浅灰底 **ID 胶囊**（`ID: xxxx` + 复制图标），点击即可复制并 Toast 提示「ID 已复制」。
4. **资产行四并列**：积分（数字）/ 优惠券（图标 + 角标）/ 订单（图标 + 角标）/ 收藏（数字），徽标≥99 显示「99+」，0 不显示。
5. **新增两个高频入口**：「🏥 健康档案 · 家人健康管理」与「📱 我的设备 · 硬件设备管理」，替代原「待付款 / 待使用 / 待评价 / 推荐」四列订单状态。
6. **历史对话三态共存**：
   - **⋯ 按钮**点击呼出菜单（置顶 / 删除）。
   - **左滑手势**露出「橙色置顶 + 红色删除」两色块按钮。
   - **管理态**点击右上「管理」进入批量勾选，吸底操作条「全选 / 已选 N 项 / 删除」。
7. **历史对话 4 组弱化分组**：「置顶 / 最近 7 天 / 最近 30 天 / 更早」，11px 浅灰色标题，无背景无分割线，空组隐藏。
8. **咨询人 6 色识别**：每条历史对话底部显示 6px 实心圆点 + 角色文字（本人 / 配偶 / 爸爸 / 妈妈 / 孩子 / 老人），同一角色色值固定。
9. **置顶上限 10 条**，超出时 Toast 提示「最多置顶 10 条对话」；已置顶对话右上角带橙色「置顶」标签。
10. **删除二次确认**：单条删除「确认删除该对话？」，批量删除「确认删除已选 N 条对话？」。
11. **整页配色对齐 ai-home 天蓝色板**：背景 `#F0F9FF → #DBEAFE` 整页竖向渐变，卡片纯白扁平（无描边、无阴影），主色 `#0EA5E9`（方案 A · 通透天空）。
12. **空态体验**：无历史对话时显示「💬 还没有对话记录，开始你的第一次咨询吧 + 返回首页」按钮。

> 本次仅 H5 端改动，安卓 / iOS / 微信小程序端无变更，**无需重新下载安装包**。

---

## 使用说明

### 1. 打开抽屉

1. 在浏览器中访问 [AI 对话首页](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home)（请先登录）。
2. 点击页面顶部左上角的 **「☰」按钮**，左侧抽屉将以 250ms 滑入动画展开，占屏幕宽度 **85%**，右侧 15% 为深色半透明遮罩。
3. **关闭抽屉**：点击右侧遮罩区域、或在抽屉内左滑、或按系统返回键即可关闭。

### 2. 顶栏入口

抽屉顶部从左到右依次为：

- **用户头像**（48×48 圆形）：展示当前登录用户头像。
- **🔔 铃铛**（消息）：右上角红点提示有未读通知（仅红点，无数字），点击进入「通知中心」。
- **⊞ 二维码**（会员码）：点击跳转「会员码」页面（如未配置则进入对应路由）。
- **⚙ 齿轮**（设置）：点击跳转「设置」页面。

### 3. 用户身份信息

- 顶栏下方第一行显示**用户昵称**（16px 加粗）。
- 第二行 **ID 胶囊**：浅灰底圆角胶囊，文字为 `ID: 2025013579`，点击右侧 📋 复制图标后会自动复制 ID 到剪贴板，并提示「ID 已复制」。

### 4. 资产行四并列

白底卡片下，四项等宽并列：

| 项 | 上方 | 下方 | 点击跳转 |
|----|------|------|----------|
| 1 | 积分余额（数字） | 积分 | 积分中心 |
| 2 | 🎫 + 角标（≥1 显示） | 优惠券 | 优惠券列表 |
| 3 | 📦 + 角标（≥1 显示） | 订单 | 统一订单中心 |
| 4 | 收藏数（数字） | 收藏 | 我的收藏 |

> 角标 ≥ 99 显示 `99+`；为 0 不显示角标。

### 5. 高频入口

资产行下方两个并列中等矩形按钮：

- **🏥 健康档案**：主标题「健康档案」，副标题「家人健康管理」 → 跳转家庭健康档案页。
- **📱 我的设备**：主标题「我的设备」，副标题「硬件设备管理」 → 跳转设备管理页。

### 6. 历史对话

#### 6.1 浏览

- 标题行「历史对话」+ 右侧「管理」入口。
- 列表按 4 组弱化分组：**置顶 → 最近 7 天 → 最近 30 天 → 更早**。
- 空组**自动隐藏**，无背景色无分割线。
- 每条历史显示：标题（单行省略）+ 摘要（单行省略，灰色）+ 右侧时间。
- 条目底部左侧 6px 实心圆点 + 咨询人角色文字，6 色预设：
  - 本人（蓝）/ 配偶（粉）/ 爸爸（深蓝）/ 妈妈（玫红）/ 孩子（橙黄）/ 老人（紫）。
- 已置顶条目右上角带橙色「置顶」小标签。

#### 6.2 单条操作（三种方式都可）

- **方式 A · ⋯ 按钮**：点击条目右侧「⋯」图标，弹出菜单（**置顶 / 取消置顶**、**删除**）。
- **方式 B · 左滑**：在条目上向左滑动约 50px，露出橙色「置顶」+ 红色「删除」两色块按钮。
- **方式 C · 管理态**：详见 6.3。

> 删除时会弹出确认弹窗「确认删除该对话？」，点击「确认」才会真正删除。

#### 6.3 批量管理（管理态）

1. 点击「历史对话」标题右侧的「**管理**」按钮，进入管理态。
2. 每条历史左侧出现 ⭕ 圆圈勾选框，**点击条目即切换勾选**（已选 = 实心 ✅ 主色）。
3. 屏幕底部出现吸底操作条：
   - 左：「**全选**」按钮（再次点击为「全不选」）。
   - 中：「**已选 N 项**」灰色文案。
   - 右：「**删除**」红字按钮，N=0 时置灰禁用。
4. 点击「删除」会弹出确认弹窗「确认删除已选 N 条对话？」。
5. 点击右上角「完成」即可退出管理态。
6. 管理态下：⋯ 按钮和左滑手势均自动禁用。

### 7. 置顶规则

- **上限 10 条**，超出时再次点击「置顶」会 Toast 提示「最多置顶 10 条对话」。
- 已置顶条目按置顶时间倒序排列，自动出现在「置顶」分组顶部。
- 已置顶条目的 ⋯ 菜单中显示「**取消置顶**」选项，点击后该条记录回归到原时间分组。

### 8. 空态与异常态

| 场景 | 表现 |
|------|------|
| 无历史对话 | 居中显示 💬 + 文案「还没有对话记录，开始你的第一次咨询吧」+「返回首页」主色按钮 |
| 网络异常加载失败 | 显示「加载失败，点击重试」链接，再次拉取数据 |
| 优惠券/订单数为 0 | 不显示角标 |
| 积分/收藏为 0 | 显示数字「0」 |
| 消息无未读 | 不显示红点 |
| 用户未登录 | 抽屉不可打开（保持原有逻辑） |

---

## 注意事项

1. **本次仅 H5 端**改动，安卓 APP / iOS APP / 微信小程序端**无任何变更**，无需更新或重新安装。
2. 抽屉打开后**关闭抽屉**有三种方式：① 点击右侧遮罩；② 抽屉内向左滑；③ 系统返回键。
3. 历史对话区是**仅有的可滚动区域**，顶部用户卡片 + 资产行 + 高频入口固定不滚动。
4. 复制 ID 在 HTTPS 站点下走 `navigator.clipboard`，HTTP 或老浏览器走 `document.execCommand('copy')` 兜底。
5. 咨询人 6 色映射基于角色英文枚举（`self/spouse/father/mother/child/elder`）；超出预设的角色名会基于 hash 自动分配色值，**保证同一角色色值固定**。
6. 置顶 / 删除接口（`POST /api/chat/history/pin` / `POST /api/chat/history/delete`）若返回失败，前端采用乐观更新策略，本地仍显示更新后状态，建议刷新页面重新拉取。
7. 数据接口：抽屉打开时会触发 3 个请求 —— 历史对话列表（`/api/chat-sessions`）、用户资产（`/api/h5/user-assets`，含旧接口降级兜底）、消息未读总数（`/api/v1/notifications/unread-count`）。

---

## 验收要点（自查清单）

- [x] 抽屉打开比例严格为 **85% / 15%**
- [x] 顶部三图标（🔔/⊞/⚙）与左侧用户头像水平居中对齐，无 × 关闭键
- [x] ID 胶囊正确显示 `ID: xxxx`，点击复制图标可用
- [x] 资产行四项徽标按差异化规则呈现
- [x] 历史对话 4 组分组标题以 11px `#9CA3AF` 弱化呈现，无背景无分割线
- [x] 每条历史尾部显示 6 色咨询人圆点 + 角色文字
- [x] 单条历史支持「⋯ 按钮 + 左滑」两种方式呼出「置顶 / 删除」
- [x] 管理态底部操作条「全选 / 已选 N 项 / 删除」三段布局，N=0 时删除按钮置灰
- [x] 整页背景为 `#F0F9FF → #DBEAFE` 整页竖向渐变，卡片纯白扁平
- [x] 服务器自动化测试 30/30 PASS（30 个 PRD 关键标识全部出现在 Next.js 静态产物中）

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 主页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 项目主入口 |
| AI 对话首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home) | 本次抽屉优化生效页面 |
| 健康档案 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-archive](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-archive) | 抽屉「健康档案」入口 |
| 我的设备 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-devices](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-devices) | 抽屉「我的设备」入口 |
| 统一订单 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/unified-orders](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/unified-orders) | 抽屉「订单」入口 |
| 优惠券 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-coupons](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-coupons) | 抽屉「优惠券」入口 |
| 我的收藏 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-favorites](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-favorites) | 抽屉「收藏」入口 |
| 通知中心 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/notifications](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/notifications) | 抽屉「🔔 铃铛」点击跳转 |
| 设置 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-settings](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-settings) | 抽屉「⚙ 齿轮」点击跳转 |
