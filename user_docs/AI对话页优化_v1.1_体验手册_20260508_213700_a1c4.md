# AI 对话页优化（PRD v1.1）— 用户体验使用手册

> 版本：v1.1（PRD-423 增量交付）
> 上线时间：2026-05-08
> 涉及端：H5（前端）+ Backend（后端）
> 关联 PRD：`PRD_AI对话页优化_v1.1.md`

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 主页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | H5 项目入口（经 Nginx 代理） |
| AI 对话首页（ai-home） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home) | 本次优化的主战场之一 |
| 历史会话页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/chat-history](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/chat-history) | 查看已归档的会话列表 |
| 健康档案 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-archive](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-archive) | 完善「本人」档案的入口 |

---

## 功能简介

本次更新围绕「AI 对话页优化（PRD v1.1）」交付以下增量能力：

1. **冷启动「未完善本人档案」轻提示**：进入 AI 对话首页时，若用户尚未建立「本人」档案，顶部出现 36px 浅蓝（`#EAF4FF`）轻提示横条，引导用户先去完善档案。点击横条直接跳转到健康档案完善页。
2. **切换咨询对象的提示横条规范化**：切换家庭成员/本人 等咨询对象时，弹出的提示横条（38px 浅蓝、13px 字号、带"返回上一会话"按钮）严格对齐 PRD §5 设计规范，文案统一为"已切换为 XX 咨询，已为您开启新对话"。
3. **埋点全量打通（EVT-01 ~ EVT-10 共 10 个事件）**：包括进入对话页、切换咨询对象、归档历史会话、档案行渲染/展开/收起、回到最新消息、健康打卡卡片拖动、未完善本人档案提示点击、发送消息等 10 类用户行为埋点；前端通过统一的 `aiChatTrack` API 上报，后端落入应用日志，便于运营/数据团队后续做转化漏斗分析。
4. **后端新增轻量埋点接收接口**：`POST /api/analytics/track`（单条）与 `POST /api/analytics/track/batch`（批量），支持失败重试时由前端的本地队列恢复回传。

---

## 使用说明

### 一、 体验「冷启动轻提示」

> **触发条件**：当前账号下尚未建立「本人」档案。

1. 打开浏览器，访问 [AI 对话首页](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home) 并登录账号。
2. 如果未建本人档案，页面顶部会出现一条 **浅蓝色的提示条**（高度 36px，背景色 `#EAF4FF`）：
   - 文案：`建议先完善本人档案，让小康给您更精准的建议 →`
   - 右侧带 `×` 关闭按钮
3. 点击提示条任意位置（除关闭按钮外）→ 自动跳转到 `/health-archive?target=self&from=ai-chat`，引导完成本人档案录入。
4. 不想被提示打扰：点击右侧 `×` 暂时关闭（本次会话内不再出现）。

### 二、 体验「切换咨询对象提示横条」

1. 打开 [AI 对话首页](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home)。
2. 与小康展开一段对话（至少发送 1 条消息）。
3. 点击底部输入框上方的「**为本人咨询**」（或当前咨询对象）按钮，打开「切换咨询对象」抽屉。
4. 选择另一位家庭成员（如「妈妈」），抽屉关闭后：
   - 顶部立即出现一条 **浅蓝色提示横条**（高度 36px、背景色 `#EAF4FF`、文字 13px）。
   - 文案为：`已切换为 妈妈 · 妈妈 咨询，已为您开启新对话`
   - 横条右侧带「**返回上一会话**」蓝色边框按钮。
5. **5 秒内**：点击「返回上一会话」可立刻恢复到原会话与原咨询对象，原会话内容完整保留。
6. **5 秒后**：横条自动消失，新会话开启完成。

### 三、 验证埋点上报

> 面向运营/数据/QA 同学

1. 打开浏览器开发者工具的 **Network** 面板。
2. 浏览 [AI 对话首页](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home) 并进行以下操作：
   - 进入页面 → 触发 `ai_chat_page_view`（EVT-01）
   - 发送消息 → 触发 `ai_chat_send`（EVT-10）
   - 切换咨询对象 → 触发 `ai_chat_target_switch`（EVT-02）+ `ai_chat_archive_history`（EVT-03）
   - 拖动右下角「健康打卡」卡片 → 触发 `ai_chat_punchcard_drag`（EVT-08）
   - 点击「先完善本人档案」轻提示 → 触发 `ai_chat_no_self_profile_tip_click`（EVT-09）
3. 在 Network 中筛选 `analytics/track`，应看到对应的 POST 请求，状态 `200`，请求体含完整的 `event` 与 `params` 字段。

---

## 注意事项

1. **新接口启用**：`/api/analytics/track` 与 `/api/analytics/track/batch` 仅做最小落库（写入应用日志），不依赖任何新表。如果未来需要做严格 ETL，可以从应用日志直接抽取 `track` 关键字行 → JSON 反序列化即可。
2. **失败容忍**：埋点采用「失败静默 + 本地队列」模式 —— 网络异常时事件先压入 `localStorage.__track_event_queue__`，恢复联网后批量回传，**永远不会**因埋点失败影响主对话/打卡/切换业务流。
3. **跨端一致性**：本期以 H5 为锚点产出实现，事件 `key` 与参数已固定（详见 `h5-web/src/lib/analytics.ts` 中的 `AI_CHAT_EVENTS` 常量）。后续小程序端 / APP 端若需要补埋，**务必使用相同的 event key 与参数字段名**，以免出现数据口径不一致。
4. **冷启动提示去重**：关闭按钮当前是「本次会话内不再出现」，下次刷新页面如果仍未建本人档案，会再次出现。
5. **本期不变更范围**：本期 `chat/[sessionId]` 单独会话页只补了「进入页面」一个埋点（EVT-01），其余 9 个事件的接入暂未在该入口落地，原因是该页面体量大且 PRD §3.3/§3.4 抽公共组件改造未在本期同步进行。后续 PRD v1.2 会把双入口对齐补齐。

---

## 涉及到的关键文件（开发同学查阅）

| 文件 | 变更说明 |
|------|----------|
| `h5-web/src/lib/analytics.ts` | 新增 `AI_CHAT_EVENTS` 常量与 `aiChatTrack` API |
| `h5-web/src/app/(ai-chat)/ai-home/page.tsx` | 接入冷启动提示 + 提示横条规范 + 6 个事件埋点 |
| `h5-web/src/app/chat/[sessionId]/page.tsx` | 引入 `aiChatTrack` + 接入 EVT-01 进入对话页埋点 |
| `backend/app/api/analytics.py` | 新增轻量埋点接收接口（含批量上报） |
| `backend/app/main.py` | 注册 `analytics` 路由 |

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 主页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | H5 项目入口（经 Nginx 代理） |
| AI 对话首页（ai-home） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home) | 本次优化的主战场之一 |
| 历史会话页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/chat-history](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/chat-history) | 查看已归档的会话列表 |
| 健康档案 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-archive](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-archive) | 完善「本人」档案的入口 |
