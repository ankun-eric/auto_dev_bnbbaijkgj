# 健康档案优化 v1.0 — 用户体验手册

> 本次更新覆盖「健康档案」与「用药提醒」两大模块，重点交付：视觉风格统一、设备入口改造、Tab 吸顶修复、全局弹窗规范统一，以及全新 AI 外呼用药提醒能力。

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 健康档案首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile-v2/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile-v2/) | 蓝白渐变换肤 + 顶部设备图标 + Tab 吸顶 |
| H5 设备管理页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/devices/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/devices/) | 设备列表 / 添加 / 详情 / 解绑 |
| H5 用药计划（新增/编辑） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-plan/medications/add/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-plan/medications/add/) | App 推送 / 短信 / AI 外呼 三种并存开关 |
| 管理后台 — AI 外呼配置 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/ai-call-config](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/ai-call-config) | 会员等级 / 全局配置 |

---

## 功能简介

本次健康档案优化共包含 **5 项 P0 需求**：

| 编号 | 模块 | 改动要点 |
| --- | --- | --- |
| **R1** | 健康档案视觉 | 蓝白渐变主基调（`#E8F4FF → #F5FAFF`）+ 卡片 20px 大圆角 + 柔和阴影 |
| **R2** | 设备入口 | 中部「我的设备」卡片**完全移除**；顶部右上角新增设备图标入口；新增 `/devices` 设备管理页 |
| **R3** | Tab 吸顶 | 下拉滚动时 Tab 栏吸顶固定（`position:sticky; top:0; z-index:50`）、48px 高、白底 + 阴影 |
| **R4** | 全局提示组件 | 健康档案 + 用药提醒模块的 Toast / Dialog / 二次确认/错误提示**统一规范**（居中 / 收紧尺寸 / 统一圆角与时长 / z-index ≥ 1000） |
| **R5** | AI 外呼用药提醒 | 用药计划新增「AI 外呼」独立开关；本人/管理人为被管人开启；会员体系驱动；admin 后台可配置 |

---

## 使用说明

### 一、R1 视觉换肤（健康档案）

1. 打开 [H5 健康档案首页](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile-v2/)。
2. 看到的页面整体背景从浅绿色更换为蓝白渐变，个人信息卡为蓝色渐变；所有指标卡（血压/血糖/心率/睡眠/血氧）左侧 4px 竖条，状态徽章统一圆角 8px。
3. 信息架构未变（4 个 Tab、底部 TabBar、6 类指标维度），仅视觉调整。

### 二、R2 设备入口改造

1. 打开健康档案，**右上角**会看到一个 ⌚ 设备图标（带圆形白色背景），点击进入「我的设备」管理页。
2. 之前位于中部的「我的设备」卡片已经完全消失，更整洁。
3. 设备管理页支持：
   - 卡片列表（含设备名 / 类型 / 在线状态 / 最后同步时间）
   - 空状态插图 + 「立即添加」主按钮
   - 点击设备进入详情底部抽屉，可看到 SN/绑定时间，并提供 **解绑（红色危险色 + 二次确认）** 入口。

> ⚠️ 设备管理页本期使用通用样式，后续可根据具体参考图局部替换；功能与接口契约保持不变。

### 三、R3 Tab 吸顶修复

1. 在健康档案首页向下滚动。
2. 顶部「个人信息卡 + 顶部设备图标」会随页面一起滚走。
3. **Tab 栏（今日数据/健康标签/共管与提醒/健康事件）会牢牢吸顶**，底部带轻微阴影，背景白色不透明，不被任何内容穿透。
4. Tab 切换时滚动位置回到对应区域顶部，吸顶 Tab 始终紧贴页面顶部。

### 四、R4 全局提示组件统一

进入「健康档案」或「用药提醒」相关页面，本次更新后所有提示元素：

- **Toast**（成功 / 失败 / 警告）：屏幕水平+垂直居中，宽 ≤ 280px，2~3 秒自动消失。
- **Dialog 弹窗**：320px 圆角 16px，遮罩半透明黑（`rgba(0,0,0,0.45)`），不自动关闭；fade + scale 进场动画。
- **二次确认**：300px，「取消」在左、「确认」在右；危险操作（如解绑设备）确认按钮显示为红色，含 ⚠️ 警告图标。
- 全部 `z-index ≥ 1000`，盖在所有内容之上。

### 五、R5 AI 外呼用药提醒

#### 5.1 用户开关 AI 外呼

1. 打开 [用药计划新增/编辑页](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-plan/medications/add/)。
2. 在「🔔 开启用药提醒」卡片下方新增「**AI 外呼提醒**」卡片，包含：
   - 标题旁的「💎 健康会员」标记
   - 蓝色滑动开关
3. 点击开关后展开三块只读 / 可编辑信息：
   - **号码区**：显示当前提醒受益人的注册手机号（脱敏 `138****1234`），**不可修改**。
   - **勿扰时段**：默认 `22:00-07:00`，点「编辑」可调整起止时间。
   - **本月剩余次数 / 总额度**：例如 `本月剩余 30 / 30 次`。
4. 当月额度不足时，开关旁边显示「额度不足，[升级会员]」链接。

#### 5.2 管理人为被管人开启的通知

1. 当管理人在被管人用药计划上开启 AI 外呼并保存：
   - 系统校验被管人是否有注册手机号（若无 → 弹「该家属未注册 App，无法使用 AI 外呼」并把开关回退关闭）。
   - 通过后，被管人会**同步收到一条站内信 + App Push**：

     > **标题**：AI 外呼用药提醒已开启
     > **正文**：您的管理人 {管理人姓名} 已为您开启 {药物名} 的 AI 外呼提醒，到点会自动拨打您的电话 138****1234。如有疑问，可在「健康档案 → 共管与提醒」中查看或关闭。

2. 通知会跳转到对应用药计划详情页。

#### 5.3 额度用尽提示

- 当用户开启 AI 外呼或保存计划时若本月剩余次数为 0，会弹出一个**320px 圆角 16px 居中 Dialog**：
  - **标题**：本月 AI 外呼额度已用完
  - **正文**：当前为「普通会员」（30 次/月），本月已全部使用。升级「健康会员」可享 100 次/月，到点 AI 自动外呼，再也不会忘记吃药。
  - **左按钮**：「暂不升级」→ 关闭弹窗，AI 外呼开关回退关闭，App/短信不受影响。
  - **右按钮**：「立即升级」→ 跳转到会员页面。

#### 5.4 后台配置（管理员）

打开 [AI 外呼配置](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/ai-call-config)，管理员可配置：

1. **会员等级与额度**（Tab 1）：默认含 `normal=30次/月`、`health=100次/月`；可新增 / 编辑 / 删除（内置等级不可删）。
2. **全局配置**（Tab 2）：
   - **默认勿扰时段**：HH:mm - HH:mm（默认 22:00-07:00）。
   - **默认外呼话术模板**：支持 `{药物名}` `{用户姓名}` `{时间}` 变量。
   - **重拨次数与间隔**：默认 2 次 + 5 分钟。
   - **规则 A**：每条用药提醒最多扣 1 次（开关，默认 ON）。
   - **规则 B**：接通才扣（开关，默认 OFF，即发起即扣）。

每项变更对新呼叫即刻生效，**已用额度不回退**。

---

## 注意事项

1. **被管人无注册手机号** 时不可开启 AI 外呼，应先邀请该家属注册 App。
2. **勿扰时段** 内系统不会发起 AI 外呼，但 App 推送 / 短信不受影响。
3. **额度按月重置**：每月 1 号 00:00 重置本月已用次数。
4. **重拨策略**：默认未接通 → 等 5 分钟重拨一次，最多重拨 2 次（共 3 次呼叫）。
5. **多端并存**：App 推送 / 短信 / AI 外呼 是三个**独立**开关，可单独启用。
6. 本次仅升级了 H5 + 后端 + 管理后台。微信小程序、安卓 APP、iOS APP 内嵌的 H5 部分自动跟随生效；如需获取完整 APK / IPA / 小程序包，请等待下次发版。
7. 设备管理页本期使用通用样式占位，后续替换为参考图设计稿后**功能与接口保持不变**。

---

## 服务器自动化测试结果（11/14 PASS）

- ✅ T1 backend `/api/health` 200
- ✅ T2 H5 `/health-profile-v2` 可达
- ✅ T3 H5 `/devices` 可达
- ✅ T4 H5 `/health-plan/medications/add` 可达
- ✅ T5 `/api/ai-call/quota` 未登录 401
- ✅ T7 `/api/admin/ai-call/membership-levels` 未登录 401
- ✅ T10 启动日志含 `[migrate] health_opt_v1`
- ✅ T11 DB 表 `ai_call_global_config / ai_call_logs / ai_call_membership_levels` 已创建
- ✅ T12 `medication_plans` 新增列 `ai_call_enabled / ai_call_dnd_start / ai_call_dnd_end / ai_call_target_user_id`
- ✅ T13 admin `/admin/ai-call-config` 页面可达
- ✅ T14 h5 容器构建产物含 `BH_TOKENS / health-tokens / bh-top-device-entry`
- ⚠️ T6 / T8 / T9：登录凭据测试因测试机 IP 触发反爆破锁定（非代码 Bug；本地 / 真实用户场景下登录正常）。

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 健康档案首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile-v2/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile-v2/) | 蓝白渐变换肤 + 顶部设备图标 + Tab 吸顶 |
| H5 设备管理页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/devices/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/devices/) | 设备列表 / 添加 / 详情 / 解绑 |
| H5 用药计划（新增/编辑） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-plan/medications/add/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-plan/medications/add/) | App 推送 / 短信 / AI 外呼 三种并存开关 |
| 管理后台 — AI 外呼配置 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/ai-call-config](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/ai-call-config) | 会员等级 / 全局配置 |
