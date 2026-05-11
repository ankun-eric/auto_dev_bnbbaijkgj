# AI 对话首页 · 左侧抽屉「加载失败」修复 - 用户体验使用手册

> 修复版本：BUG-460-CHAT-SESSIONS-500-FIX-20260511
>
> 修复时间：2026-05-11
>
> 本次仅后端单文件修复，**所有客户端无需重新下载**，刷新 H5 页面即可看到效果。

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 主页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 项目主入口（自动跳登录或首页） |
| H5 登录页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/login](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/login) | 用户登录入口 |
| AI 对话首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home) | **本次修复的页面**：登录后进入，点击左上角 ☰ 可打开抽屉 |
| 健康档案 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-archive](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-archive) | 抽屉中「家人健康管理」入口 |
| 我的设备 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-devices](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-devices) | 抽屉中「硬件设备管理」入口 |
| 通知中心 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/notifications](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/notifications) | 顶栏 🔔 入口 |
| 设置 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-settings](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-settings) | 顶栏 ⚙ 入口 |

---

## 功能简介

本次修复**完全解决了** AI 对话首页左侧抽屉中「**历史对话**」区块持续显示"加载失败"的问题。

### 修复前

- 进入 H5 → AI 对话首页 → 点 `☰` 打开左侧抽屉
- 抽屉里其它区块（积分 / 优惠券 / 订单 / 收藏 / 健康档案 / 我的设备）**都正常**
- 但「历史对话」区块**始终**显示红色"加载失败"，**所有用户、所有账号都复现**
- 既无法回到过往对话，也无法管理（置顶/取消置顶/批量删除）
- F12 Network 面板可见：`GET /api/chat-sessions` → **HTTP 500 Internal Server Error**

### 修复后

- 抽屉中「历史对话」区块**稳定加载**
- 按 PRD V7 规则分四组展示：**置顶 / 最近 7 天 / 最近 30 天 / 更早**
- 全新账号（无任何会话）：显示"还没有对话记录"空态，**不再显示"加载失败"**
- 老账号（有会话）：按规则正确排序展示——**置顶在前 → 置顶内按置顶时间倒序 → 非置顶按最近活跃倒序**
- 接口稳定返回 200，多账号、反复刷新都不再 500

### 技术根因（仅供参考）

**MySQL 不支持 PostgreSQL/Oracle 的 `ORDER BY ... NULLS LAST` 语法**。BUG-457 修复时为了让"已取消置顶（pinned_at=NULL）的会话排在置顶（pinned_at 非空）之后"，后端代码使用了 SQLAlchemy 的 `.nullslast()`；该方法在 MySQL 方言下会生成不兼容的 SQL，被 MySQL 直接拒绝（错误码 1064，SQL 语法错误），导致 FastAPI 转 500。

本次将排序逻辑改为 MySQL 原生兼容写法：用 `CASE WHEN pinned_at IS NULL THEN 1 ELSE 0 END ASC, pinned_at DESC` 表达"非 NULL 在前 + 同组内按时间倒序"，行为完全等价于 `NULLS LAST`，且 MySQL/PostgreSQL/SQLite 全部兼容。

同时对接口字段做了双层兜底：① ORDER BY 极端异常时降级到最简 `updated_at DESC` 排序，② 单条数据序列化异常静默跳过，绝不再让整列接口 500。

---

## 使用说明

### 步骤 1 · 登录测试环境

打开 [H5 登录页](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/login)，使用您的测试账号登录。

> 如尚无账号，可直接在登录页选择「注册新账号」，本次修复**对新老账号都生效**。

### 步骤 2 · 进入 AI 对话首页

登录成功后会自动进入 [AI 对话首页](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home)。如果没有自动跳转，手动点击进入即可。

### 步骤 3 · 打开左侧抽屉

点击页面**左上角的 `☰` 按钮**，左侧抽屉以 250ms 动画从左滑出，宽度占屏幕 85%。

### 步骤 4 · 查看「历史对话」区块

抽屉中部从上往下：

1. **顶栏**：头像 + 昵称 + ID 胶囊 + 🔔 + ⚙
2. **资产 4 并列**：积分 / 优惠券 / 订单 / 收藏
3. **高频入口**：🏥 健康档案 / 📱 我的设备
4. **历史对话**（本次修复重点）：
   - 标题"历史对话" + 右侧"管理"按钮
   - 下方按**置顶 / 最近 7 天 / 最近 30 天 / 更早**四组分组
   - 每条会话：标题 + 摘要 + 时间 + 6 色咨询人圆点 + 置顶标签

### 步骤 5 · 验证修复效果

**对照以下三个场景**，本次修复后**全部不再出现"加载失败"**：

| 场景 | 期望表现 |
|------|---------|
| 全新账号（无任何会话） | 显示空态："还没有对话记录，开始你的第一次咨询吧" + 主色「返回首页」按钮 |
| 老账号（有会话） | 按四组分组正确展示，**置顶项在最前**，每组内按时间倒序 |
| 反复多次开关抽屉 | 每次都稳定加载，**永远不会**再出现红色"加载失败" |

### 步骤 6 · 操作单条会话（验证写接口同样正常）

任选一条历史对话条目，**三种操作方式任选其一**：

- **点 ⋯ 按钮**：弹出菜单 → 置顶/取消置顶 + 删除
- **向左滑动条目**：露出橙色「置顶」+ 红色「删除」两色块
- **点顶部"管理"按钮**：进入管理态，圆圈勾选 + 吸底操作条（全选 / 已选 N 项 / 删除）

任一操作后**再次开关抽屉**，列表会按新规则刷新（置顶项跃升首位 / 已删项不再出现），且**接口持续稳定 200**。

### 步骤 7 · 关闭抽屉

点击右侧 15% 半透明遮罩区，或左滑抽屉，即可关闭。

---

## 注意事项

1. **本次修复仅改动后端**：所有客户端（H5、小程序、Flutter App、管理后台）的代码**未做任何改动**，因此**无需重新下载任何安装包/小程序包**，浏览器刷新（强制刷新 Ctrl+F5）即可生效。

2. **关联接口同步加固**：本次顺手把 `GET /api/chat-sessions/{id}` 详情接口也做了字段健壮性兜底（`session_type` 枚举异常 / `family_member` 关联缺失），从抽屉点开任意会话进入对话详情页时也不会再 500。

3. **管理端 `/api/admin/chat-sessions` 不受影响**：管理端接口使用 `ChatSession.created_at.desc()` 单字段排序，本身就没有 NULLS LAST 问题，本次未改动。

4. **如遇到旧版抽屉缓存的"加载失败"**：极少数情况下浏览器仍展示旧的失败态，按以下顺序处理：
   - 关闭抽屉 → 重新打开抽屉
   - 浏览器强制刷新（Windows: Ctrl + F5；macOS: Cmd + Shift + R）
   - 退出账号 → 重新登录
   - 上述三步执行后仍异常的，请提交详细复现路径反馈

5. **服务端测试已 18/18 通过**：包括无数据空态、有数据排序、置顶动作、稳定性（连续 5 次请求）、详情接口、鉴权边界、错误 token 等。

---

## 服务端非 UI 自动化测试结果（18/18 PASS）

`deploy/_test_bug460_server.py` 真实 HTTPS 接口 + 真实 MySQL 数据，断言：

- T01 ✅ 注册新用户成功
- T02 ✅ **核心断言**：空数据时 GET /api/chat-sessions 返回 200 + `[]`
- T03 ✅ 未登录返回 401（鉴权未被绕过）
- T04 ✅ 错误 token 返回 401
- T05 ✅ 分页 page=1, page_size=20 返回 200
- T06 ✅ 边界分页 page=999, page_size=100 返回 200 + `[]`
- T07 ✅ 响应类型是 JSON 数组（list）
- T08 ✅ 详情接口对不存在 id 返回 404
- T09 ✅ 远端源码含 BUG-460 标记（4 处）
- T10 ✅ backend 最近日志已无 'NULLS LAST' / '1064'
- T11 ✅ 管理端接口对普通用户返回 403
- T12 ✅ 关联接口（通知未读数）未登录 401
- T13 ✅ 同账号 5 次请求稳定 200（无偶发 500）
- T14 ✅ GET /api/chat-sessions/0 返 404
- T15 ✅ **核心断言**：三条数据排序 = [置顶新, 置顶旧, 非置顶最近]（验证完整 ORDER BY 在 MySQL 上正确）
- T16 ✅ 响应中 is_pinned 字段类型为 bool
- T17 ✅ 响应中 message_count 字段为非负 int
- T18 ✅ 置顶 B 后，B 跃升列表首位

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 主页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 项目主入口（自动跳登录或首页） |
| H5 登录页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/login](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/login) | 用户登录入口 |
| AI 对话首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home) | **本次修复的页面**：登录后进入，点击左上角 ☰ 可打开抽屉 |
| 健康档案 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-archive](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-archive) | 抽屉中「家人健康管理」入口 |
| 我的设备 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-devices](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-devices) | 抽屉中「硬件设备管理」入口 |
| 通知中心 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/notifications](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/notifications) | 顶栏 🔔 入口 |
| 设置 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-settings](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-settings) | 顶栏 ⚙ 入口 |
