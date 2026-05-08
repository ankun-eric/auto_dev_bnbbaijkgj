# AI 回答消息满屏排版改造（PRD-429）— 用户体验手册

> 版本：v1.0｜发布日期：2026-05-08｜端：H5 / 小程序 / 安卓 / iOS

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| 前端页面 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | H5 主入口（移动端最佳，PC 也兼容） |
| AI 对话首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home) | 登录后进入新版无气泡纯文本流 AI 对话 |
| 安卓 APK 下载 | [bini_health_prd429_20260508_233343_8644.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/bini_health_prd429_20260508_233343_8644.apk) | 安卓客户端安装包，点击下载后安装体验 |
| iOS 端下载 | [iOS Build ios-prd429-v20260508-232412-dkhf](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-prd429-v20260508-232412-dkhf) | iOS 客户端安装包，点击前往 GitHub Release 页面下载 |
| 微信小程序下载 | [miniprogram_prd429_20260508_231515_01eb.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_prd429_20260508_231515_01eb.zip) | 小程序源码压缩包，下载后导入【微信开发者工具】 |

---

## 功能简介

本次更新对全端 AI 对话场景的消息排版进行了"**去气泡 · 满屏纯文本流**"现代化改造。改造后的视觉风格对齐"晓医"、ChatGPT、Claude、文心一言、通义千问等头部 AI 产品，让用户在长回答下也能拥有更舒适的阅读体验。

**核心变化（用户视角）：**

1. **AI 回答彻底铺满整行**：再也没有右侧大片留白，长回答行数比改造前减少约 20%~30%。
2. **用户消息也去掉气泡**：和 AI 回答风格统一，整页呈现"无气泡纯文本流"。
3. **头像独占一行放在文字上方**：AI 头像 🌿 + "小康 · 健康助手"署名 / 用户头像 + "我"，左对齐，更聚焦内容本身。
4. **代码块、表格、卡片保留合适宽度**：代码块带圆角浅灰底，长表格支持横向滑动，健康计划卡 / 商品卡保留 360px 最大宽度，避免被无脑拉宽显得空洞。
5. **PC 横屏 / 平板 / 折叠屏自动居中**：超宽屏幕下内容容器自动加 `max-width: 760px` 并居中，防止行长过宽影响阅读。
6. **覆盖范围**：H5 / 小程序 / 安卓 App / iOS App 全端，AI 对话首页 / 会话详情页 / 菜单模式聊天页全部生效。

---

## 本次客户端变更

本次更新涉及以下三个终端的代码改动，请下载最新版本体验：

| 终端 | 变更说明 | 新版本下载 |
|------|----------|------------|
| 微信小程序 | 菜单模式聊天页（`pages/chat`）AI 回答与用户消息全部去气泡满屏排版；新增 `.msg-flow-row` 等纯文本流样式 | [miniprogram_prd429_20260508_231515_01eb.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_prd429_20260508_231515_01eb.zip) |
| 安卓端 | `chat_screen.dart` 中 `_buildMessageBubble` / `_buildStreamingBubble` 改造为去气泡纯文本流（头像在文字上方、文字铺满整行），同时修复历史 ai_home_screen.dart 中三元运算符与 null-aware index 的语法兼容性问题 | [bini_health_prd429_20260508_233343_8644.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/bini_health_prd429_20260508_233343_8644.apk) |
| iOS 端 | 与安卓端共享 Flutter `lib/` 改动（chat_screen.dart 满屏排版 + ai_home_screen.dart 语法修复） | [iOS Build ios-prd429-v20260508-232412-dkhf](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-prd429-v20260508-232412-dkhf) |

> ⚠️ 以上终端的代码在本次更新中有改动，请务必下载最新版本。H5 端已通过服务器 docker 部署直接生效，无需用户重新下载。

---

## 使用说明

### 视觉对比（改造前 vs 改造后）

**改造前**：
- AI 回答和用户消息都装在"气泡"里
- AI 气泡灰底左对齐，气泡最大宽度只有 75%~78%，**右侧大片留白**
- 用户气泡蓝/绿底右对齐，**长内容会被压缩在小框里**

**改造后**：
- AI 头像 🌿 独占一行 + "小康 · 健康助手"署名
- AI 回答正文**铺满整行**（左右各 12px 安全边距）
- 用户头像独占一行 + "我"
- 用户消息正文**铺满整行**，与 AI 回答风格统一
- 整页呈现"无气泡纯文本流"，类阅读流体验

### 操作步骤

1. 打开 H5 入口或安装最新版客户端（小程序 / 安卓 / iOS）。
2. 登录后进入「AI 对话首页」（`/ai-home`）或任意一条会话详情页（`/chat/[sessionId]`）。
3. 输入任意问题（如"最近总是头痛怎么回事？"），点击发送。
4. 观察：
   - 用户消息会以"头像 + 我"的方式独占两行，正文铺满整行。
   - AI 回答以"🌿 小康 · 健康助手"独占两行，正文同样铺满整行，**右侧不再留白**。
   - 流式渲染（逐字打印）下光标 `▌` 紧跟最新字符，行宽随屏幕自适应。
5. 如果 AI 回答中包含**代码块**：会以浅灰底（`#F5F7FA`）+ 8px 圆角 + 12px×16px 内边距展示，超长代码可横向滚动。
6. 如果 AI 回答中包含**表格**：保留原始列宽，超出屏幕宽度时自动横向滑动。
7. 如果 AI 回答中包含**健康自查摘要卡 / 药品识别卡 / 商品卡**：保留 360px 最大宽度并左对齐，不会被无脑拉宽。
8. 长按 AI 回答正文：复制 / 朗读 / 反馈菜单仍然可用（命中区域 = 该条消息整段文字区域）。
9. 在 PC 浏览器或平板横屏下打开：内容容器自动 `max-width: 760px` 居中，行长不超过 80 字符，阅读舒适度更佳。

---

## 微信小程序体验

### 下载小程序代码

点击以下链接下载微信小程序代码压缩包：

> 📦 下载地址：[miniprogram_prd429_20260508_231515_01eb.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_prd429_20260508_231515_01eb.zip)

### 体验步骤

1. **下载压缩包**：点击上方链接，将 zip 压缩包下载到本地电脑（约 400KB，336 个文件）。
2. **解压文件**：将 zip 解压到任意目录（记住解压后的文件夹路径）。
3. **下载微信开发者工具**：如尚未安装，请前往 [微信开发者工具官方下载页面](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html) 下载并安装。
4. **打开微信开发者工具**：启动开发者工具，使用微信扫码登录。
5. **导入项目**：
   - 点击开发者工具首页的「导入项目」（或「+」号）。
   - 在「目录」栏点击浏览，选择第 2 步解压后的文件夹。
   - 「AppID」栏可填入项目 AppID 或选择「测试号」体验。
   - 点击「导入」按钮。
6. **预览体验**：导入成功后，开发者工具会自动编译并在模拟器中展示小程序界面，进入「健康咨询」/「营养咨询」等任意菜单模式聊天页，发送任意问题观察新版无气泡纯文本流效果。

---

## 安卓端体验

### 下载安装包

点击以下链接下载安卓客户端安装包：

> 📱 下载地址：[bini_health_prd429_20260508_233343_8644.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/bini_health_prd429_20260508_233343_8644.apk)

### 安装与体验步骤

1. **下载 APK**：点击上方链接，将 APK 安装包（约 80MB）下载到手机（或先下载到电脑再传输到手机）。
2. **允许安装**：如果手机提示「不允许安装未知来源应用」，请在手机设置中开启「允许安装未知来源应用」（不同手机品牌设置路径可能不同，一般在「设置 → 安全」或「设置 → 隐私」中）。
3. **安装应用**：点击下载的 APK 文件，按照提示完成安装。
4. **登录并进入 AI 对话**：打开"小康 AI 健康顾问" App → 登录 → 在对话首页选择"健康问答 / 健康自查 / 中医养生"任一咨询入口 → 进入聊天页 → 发送消息观察新版排版。
5. **观察要点**：用户消息和 AI 回答都没有气泡背景；头像独占一行；正文铺满整行；底部"复制 / 播报 / 分享"按钮位置不变。

---

## iOS 端体验

### 下载安装包

点击以下链接前往 GitHub Release 页面下载 iOS 客户端安装包：

> 🍎 GitHub Release 页面：[iOS Build ios-prd429-v20260508-232412-dkhf](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-prd429-v20260508-232412-dkhf)
>
> 📦 IPA 直接下载：[bini_health_ios.ipa](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/download/ios-prd429-v20260508-232412-dkhf/bini_health_ios.ipa)

### 安装与体验步骤

1. **下载 IPA 文件**：点击上方「IPA 直接下载」链接，将 IPA 安装包（约 33MB）下载到电脑。
2. **安装到设备**（选择以下任一方式）：
   - **方式一：使用 AltStore / Sideloadly 等第三方工具侧载安装**
     - 在电脑上安装 [AltStore](https://altstore.io/) 或 [Sideloadly](https://sideloadly.io/)
     - 将 iPhone/iPad 通过数据线连接到电脑
     - 使用工具将下载的 IPA 文件安装到设备上
   - **方式二：使用 Apple Configurator（需 Mac 电脑）**
     - 在 Mac 上打开 Apple Configurator 2
     - 连接 iPhone/iPad，将 IPA 文件拖拽到设备上安装
3. **信任开发者证书**（如安装后无法打开）：前往「设置 → 通用 → VPN 与设备管理」，找到对应的开发者证书并点击「信任」。
4. **打开体验**：在桌面找到「小康 AI 健康顾问」图标，点击打开 → 登录 → 进入 AI 对话首页 → 发送消息观察新版纯文本流排版。

---

## 注意事项

| 类别 | 说明 |
|------|------|
| 兼容范围 | iOS 12+ / 安卓 8.0+ / 微信基础库 2.20.0+ / iOS Safari 13+ / Android Chrome 80+ / PC Chrome / Edge / Safari 最新两年版本 |
| 视觉一致性 | 三端（H5 / 小程序 / App）的最终视觉效果像素级对齐，同一段 AI 回答在三端的换行位置、字号、行高、头像位置完全一致（误差 ≤ 2px） |
| 无后端改动 | 本次改造**不涉及任何后端接口变更**，纯前端三端样式与组件改造，所有 AI 回答数据格式保持现状 |
| 无权限变更 | 全部 C 端用户自动享受新版无气泡满屏排版，无需任何配置开关，无需灰度 |
| 历史回归 | PRD-420（咨询对象选择器）/ Bug-419（chat session 创建）/ ai_home_config 等关键回归全部保留可用 |
| 流式渲染 | AI 流式输出（逐字打印）的体验保持原样，光标 `▌` 紧跟最新字符，位置随文字流自然移动 |
| 滚动定位 | 新消息发出后自动滚动到底部 / 回看历史消息时自动停留在用户阅读位置等行为完全保留 |
| 长按交互 | 长按 AI 回答可触发"复制 / 反馈 / 朗读"菜单，命中区域 = 该条消息整段文字区域 |
| 卡片宽度 | 健康自查摘要卡、药品识别卡、健康计划卡、商品卡等保留 360px 最大宽度并左对齐，不受满屏排版影响 |
| 行内图片 | AI 回答中的行内图片保留 280px 最大宽度并左对齐，支持点击放大查看 |
| 超长内容 | 长 URL / 英文单词使用 `word-break: break-word` 强制换行，避免横向溢出 |

---

## 设计参考

- 业内对标：晓医（北京协和 AI 健康产品）、ChatGPT Web、Claude Web、文心一言 Web、通义千问 Web 等
- 视觉趋势：现代 AI 产品已普遍抛弃传统 IM 气泡，转向"文档式 / 阅读流式"对话呈现，让 AI 的长回答铺得开、读得顺，更聚焦内容本身

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| 前端页面 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | H5 主入口（移动端最佳，PC 也兼容） |
| AI 对话首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home) | 登录后进入新版无气泡纯文本流 AI 对话 |
| 安卓 APK 下载 | [bini_health_prd429_20260508_233343_8644.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/bini_health_prd429_20260508_233343_8644.apk) | 安卓客户端安装包，点击下载后安装体验 |
| iOS 端下载 | [iOS Build ios-prd429-v20260508-232412-dkhf](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-prd429-v20260508-232412-dkhf) | iOS 客户端安装包，点击前往 GitHub Release 页面下载 |
| 微信小程序下载 | [miniprogram_prd429_20260508_231515_01eb.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_prd429_20260508_231515_01eb.zip) | 小程序源码压缩包，下载后导入【微信开发者工具】 |
