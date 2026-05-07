# AI 对话模式首页配置 - 用户体验使用手册

> 版本 V1.0 · PRD-405 · 2026-05-07

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
| --- | --- | --- |
| H5 用户端首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 配置生效后用户看到的 AI 对话首页 |
| 管理后台首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/) | 平台运营人员登录入口 |
| AI 对话模式首页配置 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/home-settings/ai-home-config/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/home-settings/ai-home-config/) | 本次新增的 admin 配置入口 |
| 操作日志 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/home-settings/ai-home-config/logs/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/home-settings/ai-home-config/logs/) | 配置变更操作日志（保留 90 天） |

---

## 功能简介

PRD-405「AI 对话模式首页配置」把 H5 用户端 AI 对话首页（`ai-home`）的所有视觉与文案元素从代码中抽离，集中纳入管理后台进行可视化配置：

- **欢迎区**：头像（emoji/图片）、3 段问候语（早/午/晚）多条随机、副标题多条随机、是否拼接昵称
- **顶栏与品牌**：标题、Logo（emoji/图片）、☰ 侧边栏 / ··· 更多菜单 / 分享按钮三个入口可控
- **推荐问列表**："试着问我"卡片增删改、拖拽排序、启用/禁用，最多 20 条
- **浮动健康打卡按钮**：是否显示、图标、文字、跳转路径、左下/右下两选位
- **输入栏**：占位符、是否启用语音、是否启用 TTS、默认 TTS 提供方（auto/cloud/browser）
- **空闲超时与会话策略**：空闲多少分钟自动新会话、空会话引导（H5 端首次新增的能力，进入空会话时自动播放 AI 欢迎语）
- **Banner / 功能宫格 / 底部快捷标签条 显隐配置**：仅控显隐与显示规模，内容仍由原有模块管理
- **操作日志**：所有配置变更留痕 90 天，支持按时间/操作人/模块筛选，支持查看变更前后 JSON diff

配置保存后**立即对所有 H5 用户端生效**（用户端有 5 分钟本地缓存，下次进入页面或会话刷新时拉取最新）。

> **本期交付范围说明**：本次首版完整落地了「后端配置 API + 操作日志 + admin 后台可视化配置 + H5 用户端接入」。微信小程序、Flutter App、桌面端的 AI 对话首页全端 1:1 对齐，受工作量约束未在本期同步落地，后端的 `/api/ai-home-config` 接口已为各端预留好统一消费入口，后续端可直接读取这套配置完成对齐。

---

## 操作步骤

### 1. 进入配置页面

1. 打开管理后台 [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/) 并使用 admin 账号登录
2. 在左侧菜单依次点击「**首页配置 → AI 对话模式首页配置**」
3. 页面右上角的 **「操作日志」** 按钮可进入日志列表，查看所有变更记录与 JSON diff

页面采用纵向分组卡片布局，从上到下共 7 张卡片：

| 卡片 | 内容 |
| --- | --- |
| 1. 欢迎区配置 | 头像、3 段问候语、副标题、是否拼接昵称 |
| 2. 顶栏与品牌配置 | 标题、Logo、3 个入口的显隐 |
| 3. 推荐问列表配置 | 卡片列表 + 上下移动 + 启用/禁用 + 增删 |
| 4. 浮动健康打卡按钮配置 | 显隐 / 图标 / 文字 / 跳转路径 / 显示位置 |
| 5. 输入栏配置 | 占位符 / 语音 / TTS / TTS 提供方 |
| 6. 空闲超时与会话策略 | 超时分钟 / 自动新会话 / 空会话欢迎语 |
| 7. Banner / 宫格 / 标签条 显隐配置 | 显隐 + 数量约束 |

### 2. 修改配置

每张卡片右上角都有 **「保存本节」** 按钮，仅保存该卡片的内容。如果同时改动了多张卡片，可以滚动到底部点击 **「全部保存」** 一次性保存。

#### 修改头像 / Logo

1. 在「欢迎区配置」或「顶栏与品牌配置」中找到「头像」「Logo」字段
2. 选择 **「使用 Emoji」** 或 **「使用图片」**
3. 选 Emoji 时直接在输入框输入 emoji 字符（如 🌿 🩺）
4. 选图片时点击「**上传图片**」按钮，从本地选择 PNG / JPG / WebP 文件（≤1MB），系统会上传到平台对象存储并自动回填 URL
5. 点击「保存本节」，前端会立即看到新头像

#### 编辑问候语 / 副标题（多条随机）

每段问候语和副标题都是数组，支持「**新增一条**」按钮添加，点击右侧红色垃圾桶按钮删除。
- 每段至少 1 条，最多 20 条
- 用户进入页面时会从该段随机抽 1 条，**同一会话期内不再切换**（避免文案频繁切换造成困扰）

#### 编辑推荐问

1. 在「3. 推荐问列表配置」点击「**新增推荐问**」按钮
2. 在新出现的卡片中填写：
   - 图标（emoji，例如 💚）
   - 主标题（卡片显示的小字标签，例如 健康咨询）
   - 实际提问文本（点击该卡片时实际发送的问题文本）
3. 通过「⬆/⬇」按钮调整顺序
4. 通过「启用/禁用」开关控制是否显示给用户
5. 点击「保存本节」生效

> 启用条数为 0 时，前端会隐藏整个「试着问我」区域。

#### 配置浮动健康打卡按钮

1. 在「4. 浮动健康打卡按钮配置」开关「是否显示」
2. 输入图标（emoji）和按钮文字（最长 10 字）
3. 选择是否在按钮上同时显示文字
4. 输入跳转路径，**必须以 `/` 开头**（项目内路径），后端会拒绝外链
5. 选择「右下」或「左下」显示位置

#### 配置空会话引导（H5 端本次新增能力）

1. 在「6. 空闲超时与会话策略 → 空会话引导」中开启开关
2. 在「欢迎语内容」编辑器中添加一条或多条欢迎语（最多 20 条）
3. 用户进入空会话（无任何消息）时，前端会自动以 AI 身份插入一条欢迎语（**不入库、不参与上下文**，仅作为引导提示）

### 3. 查看操作日志

1. 在「AI 对话模式首页配置」页面右上角点击「**操作日志**」按钮
2. 列表展示所有变更（保留 90 天，超期自动清理）
3. 顶部筛选区可按「日期范围 / 模块」过滤
4. 点击行右侧「**查看 diff**」按钮，弹出抽屉对比变更前后 JSON

> **保存内容与原内容完全相同时，不会重复写日志**，避免无意义的"刷屏"。

---

## 注意事项

1. **配置生效时机**：admin 点保存后立即对所有 H5 用户端生效；用户端 5 分钟本地缓存，下次进入页面或会话刷新时拉取最新
2. **图片要求**：≤1MB，PNG/JPG/WebP，前端强制裁剪 1:1 正方形；建议头像 256×256，Logo 128×128。后端会校验文件头与 MIME，防止伪装图片
3. **跳转路径白名单**：浮动按钮 `target_path` 仅允许项目内路径（必须以 `/` 开头），禁止外链
4. **昵称拼接规则**：未登录或昵称为空时，问候语不拼昵称，直接展示如"早上好"
5. **头像/Logo 优先级**：选了图片但 image_url 失效（404）时，前端会自动降级到 emoji
6. **多条随机一致性**：同一会话期内只随机一次，避免文案频繁切换
7. **空闲超时**：与现有 `chat-idle-timeout` 接口共用同一存储，本页 `idle_timeout_minutes` 字段与原接口数据互通
8. **操作日志保留期**：90 天，超期由后端定时清理；查询单次最多返回 1000 条
9. **不支持回滚**：本期只读不回滚，但日志保留 90 天供人工对照恢复
10. **多端落地**：本期 H5 端已完整接入；微信小程序 / Flutter App / 桌面端可在后续迭代中通过同一份 `/api/ai-home-config` 接口直接消费这套配置完成对齐

---

## 技术细节（开发者参考）

### 后端 API

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/ai-home-config` | 公开 | 用户端读取（含未登录） |
| GET | `/api/admin/ai-home-config` | admin | 后台读取（同上数据） |
| PUT | `/api/admin/ai-home-config` | admin | 整体保存（全部字段） |
| PATCH | `/api/admin/ai-home-config/{module}` | admin | 按模块保存（welcome/topbar/input/session/floating_button/banner/func_grid/quick_tags/recommended_questions） |
| POST | `/api/admin/ai-home-config/upload-image` | admin | 上传头像/Logo，返回 URL |
| GET | `/api/admin/ai-home-config/logs` | admin | 列表查询 |
| GET | `/api/admin/ai-home-config/logs/{id}` | admin | 日志详情（before / after） |

### 数据存储

- 主配置：`app_settings` 表中 `key='ai_home_config'` 单条 JSON
- 操作日志：`ai_home_config_logs` 表（保留 90 天）

### 兼容性

- 现有 `/api/app-settings/page-style` 接口保持不变
- 现有 `/api/app-settings/chat-idle-timeout` 接口保持不变；本页 `session.idle_timeout_minutes` 字段会双向同步到该接口的存储
- H5 现有 `ai-home` 页面在新配置上线前的旧客户端，可继续用兜底默认值正常运行

### 自动化测试

- 容器内 `pytest tests/test_ai_home_config.py` → **10 passed**
- 远程冒烟：`/api/health=200`、`/api/ai-home-config=200`、`/=200`、`/admin/=200`、`/admin/home-settings/ai-home-config/=200`、`/admin/home-settings/ai-home-config/logs/=200`

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
| --- | --- | --- |
| H5 用户端首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 配置生效后用户看到的 AI 对话首页 |
| 管理后台首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/) | 平台运营人员登录入口 |
| AI 对话模式首页配置 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/home-settings/ai-home-config/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/home-settings/ai-home-config/) | 本次新增的 admin 配置入口 |
| 操作日志 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/home-settings/ai-home-config/logs/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/home-settings/ai-home-config/logs/) | 配置变更操作日志（保留 90 天） |
