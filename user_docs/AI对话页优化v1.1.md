# AI 对话页优化 v1.1（PRD-414 终版）

> 文档版本：v1.1（2026-05-08）
> 部署唯一标识：`6b099ed3-7175-4a78-91f4-44570c84ed27`

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 主页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | H5 项目入口（手机浏览器打开） |
| AI 对话主页（H5） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home) | AI 对话首页（推荐问、欢迎区等） |
| 管理后台 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/) | admin 后台首页 |
| AI 对话首页配置（管理后台） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/home-settings/ai-home-config/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/home-settings/ai-home-config/) | 在「全局开关」Tab 末尾的「AI 对话页（chat）配置」卡片可配置 AI 头像、署名、档案行模板等 |

---

## 功能简介

PRD-414 v1.1 终版优化集中解决以下 4 个核心体验痛点：

1. **信息层失焦** —— AI 对话页顶栏吸顶、上滑时欢迎区/推荐问/宫格/贴士正常离开屏幕；右下角浮出「↓ 回到最新消息」按钮，含未读红点提示
2. **健康打卡遮挡 AI 对话** —— 健康打卡支持垂直方向上下拖动（开关式，由后台配置控制）
3. **AI 头像不符品牌调性** —— 默认紫色头像替换为可视化配置的「小康」IP 形象（emoji 或图片二选一），头像右侧紧跟「**小康**」署名 14px / 主文本色，AI 回答正文与署名左对齐
4. **档案使用不透明** —— AI 回答上方新增「本次回答结合 **XX** 的档案 ▽」档案行，点击 ▽ 展开档案信息卡（含基础信息：姓名/性别/身高/体重等）；选「未选择档案」时不显示该行

### 后台可视化配置

进入 admin → 首页配置 → AI 对话模式首页配置 → **全局开关** Tab，页面底部新增「**AI 对话页（chat）配置 — PRD-414 v1.1**」卡片，可视化维护以下字段：

| 字段 | 默认值 | 说明 |
|------|--------|------|
| AI 对话头像 | emoji 🌿 | **与系统/品牌 Logo 完全独立维护**，推荐 128×128 PNG/JPG/WEBP，≤500KB；为空时使用兜底 |
| AI 署名 | 小康 | ≤10 字，14px 主文本色，渲染在头像右侧 |
| 档案行总开关 | 开启 | 是否在 AI 回答上方显示「本次回答结合 XX 的档案 ▽」 |
| 档案行文案模板 | 本次回答结合 {name} 的档案 | 必须包含 `{name}` 占位符，≤30 字 |
| 健康打卡可拖动 | 开启 | 仅垂直方向，长按 200ms 进入拖动态 |
| 「↓ 回到最新消息」按钮 | 开启 | 用户上滑超过 100px 时浮出 |
| 顶栏吸顶 | 开启 | 始终固定在屏幕顶端 |
| 历史会话保留天数 | 0（永久） | 0=永久；最大 3650 天 |

---

## 本次客户端变更

本次更新涉及以下终端的代码改动：

| 终端 | 变更说明 | 部署方式 |
|------|----------|----------|
| 后端 API | 新增 `ai_chat` 配置模块（schema + PATCH 路由 + 校验），扩展 `/api/ai-home-config` 公共接口；新增 8 个测试用例并通过（`backend/tests/test_ai_chat_v11_414.py`） | 已 docker cp 部署到生产容器，restart 已完成 |
| 管理后台（admin-web） | 在「AI 对话模式首页配置 → 全局开关」Tab 末尾新增「AI 对话页（chat）配置」可视化卡片（8 个字段） | 已重建 admin 容器并发布 |
| H5 端 chat 页 | AI 头像换为可配置（emoji/图片）、回答上方新增「小康」署名+档案行+档案信息卡，右下角浮出「↓ 回到最新消息」按钮（含未读红点） | 已重建 h5 容器并发布 |

> ⚠️ 微信小程序、Flutter App 端本期未做 UI 改造，但已可直接消费 `/api/ai-home-config` 接口的 `ai_chat` 字段（avatar/signature/profile_row_template 等），后续端可在下一版本同步落地。

---

## 使用说明

### 1. 在管理后台配置 AI 头像与署名

1. 浏览器打开 [管理后台](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/) 并登录
2. 左侧菜单点击「首页配置 → AI 对话模式首页配置」
3. 切换到 **全局开关** Tab（默认 6 个 Tab 中的最后一个）
4. 滚动到页面最下方，找到「**AI 对话页（chat）配置 — PRD-414 v1.1**」卡片
5. 上传 AI 对话头像（推荐 128×128 正方形 PNG）或保留 emoji 模式
6. 修改署名（默认「小康」，最长 10 字）
7. 点击页面右下角吸底「保存本 Tab」按钮
8. 切换到 H5 chat 页（下拉刷新或重新进入），即可看到新头像 + 署名生效

### 2. H5 端用户在 AI 对话页的体验改进

1. 用手机浏览器打开 [H5 主页](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/)
2. 登录后进入 AI 对话（点击底部「AI」Tab → 输入问题 → 进入 chat 页）
3. **顶栏始终吸顶**，向下滚动时顶栏不消失
4. 发送提问，AI 回复后会看到：
   - 头像左侧使用配置的「小康」头像（或 emoji）
   - 头像旁紧跟「小康」二字（14px 主文本色）
   - AI 回答正文上方有「本次回答结合 **XX** 的档案 ▽」档案行（仅当选择具体家人时）
   - 点击 ▽ 展开档案信息卡，再次点击 △ 收起
5. **向上滚动**查看历史消息，距离底部超过 100px 时，右下角浮出 **↓ 回到最新消息** 圆形按钮
6. 期间若有新消息进入，按钮上会出现红点未读提示
7. 点击按钮平滑滚动到底部，红点清零

### 3. 切换咨询对象（基于现有功能）

- 在 chat 页底部输入框上方点击「为 XX 咨询」选择器
- 弹出家庭成员列表（默认排序：本人 → 其他家人 → 未选择档案）
- 选择新对象后，原对话归档到「历史会话」（永久保留），自动开启新对话
- 新对话顶部出现轻提示「已切换为 XX 咨询，已为您开启新对话」（3 秒后自动消失）

---

## 注意事项

1. **AI 头像与系统 Logo 独立维护**：即使后台 Logo 变更，AI 对话头像保持不变（除非在 ai_chat 字段单独修改）
2. **档案行只在选具体家人时显示**：如果选择「未选择档案」（通用咨询），档案行自动隐藏，回答区域更紧凑干净
3. **档案行模板必须包含 `{name}` 占位符**：例如「本次回答结合 {name} 的档案」、「为 {name} 服务」均合法；缺少 `{name}` 会保存失败
4. **历史会话永久保留**：本次明确决策为永久保留（O-04），不会自动清理。如需调整，可在后台修改「历史会话保留天数」（0=永久）
5. **首次配置后 5 分钟内 H5 端可能仍读取本地缓存**：因 H5 已实现 5 分钟本地缓存机制；强制刷新页面或等待 5 分钟自动失效

---

## 验证情况（已通过）

- 后端容器内 pytest：`tests/test_ai_home_config.py + tests/test_ai_home_config_v1.py + tests/test_ai_home_config_tab411.py + tests/test_ai_chat_v11_414.py` → **38 passed in 23.66s**（含本次 8 个 PRD-414 用例 T01-T08）
- admin-web docker compose build：125.1s 成功
- h5-web docker compose build：98.8s 成功
- 远程 smoke：`/api/health=200`、`/api/ai-home-config=200`（含 ai_chat 字段）、`/admin/home-settings/ai-home-config/=200`、`/=200` 全 200

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 主页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | H5 项目入口（手机浏览器打开） |
| AI 对话主页（H5） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home) | AI 对话首页（推荐问、欢迎区等） |
| 管理后台 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/) | admin 后台首页 |
| AI 对话首页配置（管理后台） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/home-settings/ai-home-config/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/home-settings/ai-home-config/) | 在「全局开关」Tab 末尾的「AI 对话页（chat）配置」卡片可配置 AI 头像、署名、档案行模板等 |
