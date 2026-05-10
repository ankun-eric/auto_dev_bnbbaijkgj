# AI 对话模式页面修复（晴空诊室主色调一致性）使用手册

> 本次为 H5 端 AI 对话模式相关页面（共 20 屏）的视觉一致性修复，统一对齐到「小康 AI · 晴空诊室」最终主色调（PRD-442 v1.0）。

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 主入口（首页） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 项目主页面入口（经 Nginx 代理） |
| AI 主聊天 | [/chat/<sessionId>](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/chat/demo) | 小康 AI 健康咨询主对话窗 |
| 用药聊天 | [/drug/chat/<sessionId>](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/drug/chat/demo) | 用药识别 AI 解读对话窗 |
| 客服聊天 | [/customer-service](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/customer-service) | 在线客服 AI 应答页 |
| AI 主页 | [/ai-home](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home) | 小康 AI 主页（功能聚合） |
| 用药方案管理 | [/medication-plans](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/medication-plans) | 用药提醒方案 |
| 历史会话 | [/chat-history](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/chat-history) | AI 对话历史记录 |
| 健康档案 | [/health-archive](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-archive) | 个人/家庭健康档案 |
| 体检解读 | [/checkup](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/checkup) | 体检报告 AI 解读列表 |
| 数字人通话 | [/digital-human-call](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/digital-human-call) | 数字人语音通话页 |
| AI 设置 | [/ai-settings](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-settings) | AI 个性化设置 |
| 反馈 | [/feedback](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/feedback) | 用户反馈通道 |
| 账户安全 | [/account-security](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/account-security) | 账户与安全 |

---

## 功能简介

本次更新对 H5 端涉及 AI 对话与 AI 内容呈现的 **20 屏页面**进行视觉一致性修复，统一到「小康 AI · 晴空诊室」最终主色调，让用户在所有 AI 入口、AI 对话、AI 解读相关页面感受到一致的「天蓝晴空」沉浸式品牌体验。

### 视觉变化要点

| 元素 | 修复前可能样式 | 修复后统一样式 |
|------|-------------|--------------|
| 页面底色 | 灰白 / 浅灰（#F5F7FA / #F9FAFB / #F6F7F9 等不一致） | 晴空浅蓝 `#F0F9FF`（brand-50） |
| 顶栏 | 纯蓝 / 主色实心 | 135° 斜向渐变 `#F0F9FF → #DBEAFE`，深蓝 `#0C4A6E` 文字 |
| AI 气泡 | `#f5f5f5` 浅灰底 / 白底 | 晴空浅蓝 `#E0F2FE`（brand-100），文字 `#0C4A6E`（深蓝），左上角 4px 小尖角 |
| 用户气泡 | 纯蓝 `#1890ff` / `#0EA5E9` | 蓝色渐变 `#7DD3FC → #38BDF8`，白色文字，右上角 4px 小尖角 |
| 输入框 | 灰底 `bg-gray-50` | 白底 `#FFFFFF` + 1px `#BAE6FD` 描边 + 22px 圆角 |
| 发送按钮 | 主色单色 | 蓝色渐变 `#38BDF8 → #0284C7` |

---

## 使用说明

无需用户手动操作。打开手册中提供的任意 AI 相关页面，即可看到全新视觉效果：

1. **打开 AI 主页**：进入 [AI 主页](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home)，可看到底色统一为晴空浅蓝。
2. **AI 对话**：进入 [AI 主聊天](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/chat/demo) 与小康对话；用户消息显示为蓝色渐变气泡（白字），AI 解读以 PRD-429 满屏排版呈现，整体融入晴空底色。
3. **用药聊天**：进入 [用药聊天](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/drug/chat/demo) 上传药盒照片或文字咨询，AI 气泡为浅蓝底深蓝字，明显有别于灰底风格。
4. **客服聊天**：进入 [/customer-service](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/customer-service)，气泡颜色与主对话保持一致。
5. **报告/对话分享页**：通过分享链接（如 `/shared/chat/<token>`、`/shared/drug/<token>`、`/shared/report/<token>`）查看，顶栏与气泡均与新规范一致。
6. **(ai-chat) 路由组**：包括 [AI 设置](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-settings)、[反馈](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/feedback)、[历史会话](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/chat-history)、[账户安全](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/account-security)、[健康档案](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-archive)、[用药方案](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/medication-plans) 等 7 个子页面，统一通过路由组 `layout.tsx` 包裹的 `bh-ai-page` 容器获得晴空浅蓝底色。

---

## 注意事项

- **缓存**：如果本次打开页面仍是旧色，请在浏览器中下拉刷新或强制刷新（PC: `Ctrl+F5` / Mac: `Cmd+Shift+R`），以加载最新构建产物。
- **会话依赖**：部分对话页面需要登录态（如 `/chat/<sessionId>`、`/medication-plans` 等），未登录会先跳转 `/login`。
- **覆盖范围**：本次仅修改 H5 前端视觉。后端、Admin Web、小程序、移动 APP 端代码未变更，无需更新。
- **回滚**：如果需要回滚，仅需 `git revert` 本次合并提交，前端容器重新 build 即可在 2 分钟内恢复。

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 主入口（首页） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 项目主页面入口（经 Nginx 代理） |
| AI 主聊天 | [/chat/<sessionId>](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/chat/demo) | 小康 AI 健康咨询主对话窗 |
| 用药聊天 | [/drug/chat/<sessionId>](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/drug/chat/demo) | 用药识别 AI 解读对话窗 |
| 客服聊天 | [/customer-service](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/customer-service) | 在线客服 AI 应答页 |
| AI 主页 | [/ai-home](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home) | 小康 AI 主页（功能聚合） |
| 用药方案管理 | [/medication-plans](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/medication-plans) | 用药提醒方案 |
| 历史会话 | [/chat-history](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/chat-history) | AI 对话历史记录 |
| 健康档案 | [/health-archive](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-archive) | 个人/家庭健康档案 |
| 体检解读 | [/checkup](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/checkup) | 体检报告 AI 解读列表 |
| 数字人通话 | [/digital-human-call](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/digital-human-call) | 数字人语音通话页 |
| AI 设置 | [/ai-settings](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-settings) | AI 个性化设置 |
| 反馈 | [/feedback](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/feedback) | 用户反馈通道 |
| 账户安全 | [/account-security](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/account-security) | 账户与安全 |
