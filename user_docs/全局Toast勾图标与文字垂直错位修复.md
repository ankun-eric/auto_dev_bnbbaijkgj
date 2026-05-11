# 全局 Toast 勾图标与文字垂直错位修复 — 用户体验手册

> 修复编号：BUG-464  
> 修复日期：2026-05-11  
> 影响端：手机端 H5（在微信 / 手机浏览器中打开）  
> 修复范围：全 App 所有使用同款黑色半透明 Toast 的入口（约 20+ 个典型场景）  
> 部署状态：✅ 已部署到测试服务器并通过 11/11 项自动化验证

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | H5 项目主入口（经 Nginx 代理） |
| AI 对话首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home) | 进入 AI 对话主界面（左上角抽屉删除会话即可触发 Toast） |
| 我的优惠券 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-coupons](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-coupons) | 领取优惠券页面（领取成功 Toast） |
| 统一订单 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/unified-orders](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/unified-orders) | 订单中心（订单操作 Toast） |
| 健康档案 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile) | 保存档案（保存成功 Toast） |
| 登录页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/login](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/login) | 登录页面（登录成功 Toast） |

---

## 功能简介

本次修复了 H5 端 **全局黑色半透明 Toast 轻提示**（如：删除成功、复制成功、保存成功、收藏成功、置顶成功、登录成功、支付成功、领取成功等）的视觉错位问题。

修复前：在 Toast 内部，**对勾图标偏上、提示文字偏下**，二者垂直方向明显错位，看起来像两块独立的元素叠在一起，缺乏视觉重心。

修复后：图标和文字作为一个整体，**上下两行紧凑居中**、视觉重心统一地对齐在 Toast 几何中心，整体观感专业、一致。

修复策略：**在 H5 全局样式（`h5-web/src/app/globals.css`）一次性覆盖 antd-mobile Toast 的内部布局**，所有调用 `Toast.show({ icon, content })` 的位置自动获得新样式，无需逐页修改。

---

## 修复后的视觉规范

| 元素 | 规范 |
|------|------|
| Toast 背景 | 黑色半透明 `rgba(0, 0, 0, 0.75)` + 圆角 12px |
| 内容布局 | flex 列向居中（图标在上、文字在下）、上下两行紧凑居中 |
| 内边距 | 上下、左右内边距对称（20px × 16px） |
| 最小尺寸 | 宽度 ≥ 120px，高度 ≥ 100px，自适应内容 |
| 行间距 | 图标与文字之间 8px |
| 成功图标 | 绿色对勾 ✓（antd-mobile `CheckOutline`） |
| 失败图标 | 红色叉号 ✗（antd-mobile `CloseOutline`） |
| 加载图标 | 白色旋转加载圈 |
| 文字 | 白色、14px、水平居中 |
| 出现位置 | 屏幕正中央（保持不变） |
| 停留时长 | 约 2 秒（保持不变） |
| 动画 | 淡入淡出（保持不变） |

---

## 操作步骤（如何在 H5 端体验修复效果）

下面以 **AI 对话模式删除聊天记录** 为典型入口演示，其他模块同款 Toast 全部自动生效。

### 入口 1：AI 对话模式 - 删除单条聊天记录

1. 用手机浏览器（或微信内置浏览器）打开 [AI 对话首页](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home)
2. 完成登录后，进入 AI 对话首页
3. 点击页面**左上角的"三横线"图标**，从左侧滑出抽屉菜单
4. 在抽屉的"历史对话"区域，任选一条聊天记录
5. **长按该记录**（或点击 ⋯ 菜单 / 左滑出现红色删除按钮）
6. 点击**"删除"**
7. 观察弹出的"删除成功"Toast：
   - ✅ 绿色对勾 ✓ 居中在第一行
   - ✅ "删除成功"文字居中在第二行
   - ✅ 两行整体居中在 Toast 几何中心，视觉重心统一

### 入口 2：AI 对话模式 - 批量删除

1. 进入抽屉的"历史对话"区域
2. 点击"管理"进入多选模式
3. 勾选若干条会话
4. 点击底部"删除"
5. 弹出"已删除"Toast，效果同上

### 入口 3：复制 AI 回复内容

1. 进入任意 AI 对话页面
2. 长按 AI 回复气泡，弹出操作菜单
3. 点击"复制"
4. 弹出"复制成功"Toast，效果同上

### 入口 4：保存健康档案

1. 进入[健康档案页](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile)
2. 修改任意字段后点击"保存"
3. 弹出"保存成功"Toast，效果同上

### 入口 5：领取优惠券

1. 进入[我的优惠券页](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-coupons)
2. 点击"领取"按钮
3. 弹出"领取成功"Toast，效果同上

### 入口 6：登录成功 / 退出登录

1. 进入[登录页](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/login)
2. 输入账号密码后登录
3. 弹出"登录成功"Toast，效果同上

### 入口 7：失败场景（红色叉号）

任意"删除失败,请稍后重试"、"操作失败"等失败提示场景，红色叉号 ✗ 同样在第一行居中，提示文字在第二行居中，整体视觉重心统一。

---

## 验收清单（用户验证用）

请按以下 20 条入口逐项验证，**修复后**全部 Toast 必须符合统一规范：

### AI 对话模式相关

| 序号 | 入口 | 预期 Toast |
|------|------|------------|
| 1 | 抽屉历史对话 → 长按单条 → 删除 | "已删除" / "删除成功"（绿勾 + 文字两行居中） |
| 2 | 抽屉历史对话 → 多选 → 批量删除 | "已删除"（同上） |
| 3 | 抽屉历史对话 → 左滑 → 删除 | "已删除"（同上） |
| 4 | 抽屉历史对话 → 置顶 | "已置顶"（同上） |
| 5 | 抽屉历史对话 → 取消置顶 | "已取消置顶"（同上） |
| 6 | AI 对话内 → 复制回复 | "复制成功"（同上） |
| 7 | AI 对话内 → 操作失败 | "操作失败"（红叉 + 文字两行居中） |

### 健康 / 问诊 / 订单等其他模块

| 序号 | 模块 | 操作 | 预期 Toast |
|------|------|------|------------|
| 8 | 健康首页 / 健康计划 | 保存 / 更新计划 | "保存成功" |
| 9 | 体检报告 | 保存 / 删除报告 | "操作成功" |
| 10 | 用药计划 | 添加 / 修改用药 | "保存成功" |
| 11 | 中医 / 问诊结果 | 收藏 / 保存结果 | "收藏成功" |
| 12 | 订单页 | 联系商家 / 操作订单 | 各类成功提示 |
| 13 | 支付成功页 | 完成支付 | "支付成功" |
| 14 | 优惠券 | 领取优惠券 | "领取成功" |
| 15 | 登录页 / 退出登录 | 登录 / 退出 | "登录成功" / "已退出登录" |
| 16 | 个人资料 / 健康档案 | 保存信息 | "保存成功" |
| 17 | 家庭成员邀请 | 邀请家人 | "邀请已发送" |
| 18 | 搜索 / 商品收藏 | 收藏商品 | "收藏成功" |
| 19 | 商家端登录 / 订单 | 各类操作 | 各类提示 |
| 20 | 任何 `Toast.show({...})` 调用点 | 任意成功/失败 | 全部统一新样式 |

✅ **验收通过标准**：

- 图标 + 文字上下两行紧凑居中
- 整体视觉重心位于 Toast 几何中心
- 成功类用绿色对勾，失败类用红色叉号
- 文字白色清晰，背景黑色半透明
- 没有任何一处出现"图标偏上、文字偏下、整体失衡"

---

## 注意事项

1. **如未看到修复效果**：请清除浏览器缓存或硬刷新页面（Ctrl + Shift + R / Cmd + Shift + R），确保加载最新的 CSS 资源
2. **微信内置浏览器**：如在微信中体验，可在右上角菜单选择"刷新"，或退出页面重新进入即可加载最新样式
3. **本次修复不影响**：
   - Toast 的出现位置（仍为屏幕正中央）
   - Toast 停留时长（仍约 2 秒）
   - Toast 淡入淡出动画（沿用原节奏）
   - 业务逻辑、接口、数据均未变动
4. **后续保障**：本次为全局组件层统一修复，**后续新增的任何调用 Toast 的功能都会自动获得正确的样式**，无需重复维护

---

## 技术实现说明（供开发参考）

- 修改文件：`h5-web/src/app/globals.css`（仅追加一段全局样式块，不修改任何业务代码）
- 修复目标选择器：`.adm-toast-mask .adm-toast-main-icon`、`.adm-toast-icon`、`.adm-auto-center`
- 核心策略：将默认的"块级 + padding 35px"布局改为 **flex 列向居中** + 对称 padding（20px × 16px） + gap 8px
- 服务器自动化测试：`deploy/_test_bug464_server.py` 共 **11 项 PASS（11/11）**
  - 容器 running ✅
  - 源码 `BUG-464` 标记存在 ✅
  - 源码 `.adm-toast-main-icon` 选择器命中 9 次 ✅
  - 源码 `flex-direction: column` 命中 2 次 ✅
  - 构建产物（minified CSS）包含 `adm-toast-main-icon` ✅
  - 构建产物包含 `flex` 规则 ✅
  - 6 个主要 H5 页面 URL 全部可达（200/308） ✅

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | H5 项目主入口（经 Nginx 代理） |
| AI 对话首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home) | 进入 AI 对话主界面（左上角抽屉删除会话即可触发 Toast） |
| 我的优惠券 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-coupons](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-coupons) | 领取优惠券页面（领取成功 Toast） |
| 统一订单 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/unified-orders](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/unified-orders) | 订单中心（订单操作 Toast） |
| 健康档案 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile) | 保存档案（保存成功 Toast） |
| 登录页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/login](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/login) | 登录页面（登录成功 Toast） |
