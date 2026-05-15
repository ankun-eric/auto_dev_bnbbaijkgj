# 健康自查功能 3 Bug 修复 — 用户体验使用手册

> **修复版本**：2026-05-16 一期上线
> **覆盖端**：H5、微信小程序、Flutter APP（安卓 + iOS）
> **核心改动**：修复"宫格【健康自查】点击无反应"、"抽屉提交后分析失败"、"首页 404"三个问题

---

## 访问链接

以下是本项目最新版本的访问/下载入口，点击即可使用：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），不涉及 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 前端（已修复上线） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | AI 对话首页入口（修复后） |
| 微信小程序下载 | [miniprogram_20260516_005816_6964.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_20260516_005816_6964.zip) | 微信小程序源码压缩包（导入微信开发者工具） |
| 安卓 APK 下载 | [app_20260516-005842_f5c3.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/app_20260516-005842_f5c3.apk) | Flutter 安卓客户端最新安装包 |
| iOS 端下载 | [iOS Build ios-v20260516-005759-de96](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-v20260516-005759-de96) | iOS 客户端构建 Release 页面（含 IPA 资产） |

---

## 功能简介

bini-health（必念健康）AI 对话首页的【健康自查】功能让用户通过"选部位 + 选症状 + 选持续时间"三步问卷，由 AI 给出针对性的健康参考分析。

本次更新一次性修复了 3 个影响主流程的 Bug：

1. **Bug 1（H5 端）**：AI 对话首页顶部"功能宫格"中的【健康自查】方形按钮点击后，弹出引导卡片但卡片里的"健康自查"按钮**毫无反应**。
2. **Bug 2（三端通杀：H5 / 小程序 / Flutter APP）**：填完健康自查抽屉后点【开始 AI 分析】，对话流出现卡片气泡，但 AI 侧的"正在分析中…"很快变成 **"分析失败，请点击重试"**。
3. **Bug 3（H5 端）**：首页加载时控制台报 `api/health-plan/today-tasks` 404 红字。

修复后：

- 宫格【健康自查】与胶囊【健康自查】两个入口行为**完全一致**——都是直接弹出健康自查抽屉。
- 三端抽屉提交后均能**稳定**返回 AI 健康参考回答（连续 5 次以上无"分析失败"）。
- 首页加载控制台**零 404 红字**。

---

## 本次客户端变更

本次更新涉及以下终端的代码改动，请下载最新版本体验：

| 终端 | 变更说明 | 新版本下载 |
|------|----------|------------|
| H5 前端 | 1）AI 对话首页【宫格分发函数】新增 `health_self_check` 分支：与胶囊入口行为一致，直接弹出健康自查抽屉。2）健康自查抽屉提交后，请求 `/api/health-self-check/start` 的 payload 改为 schema 要求的 `body_part_id`。3）首页加载的"今日任务"接口路径由 `today-tasks` 改为 `today-todos`。 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/)（已部署生效） |
| 微信小程序 | 聊天页健康自查抽屉提交 payload 改为 schema 要求的 `body_part_id`，并将展示模型与接口请求模型分离。 | [miniprogram_20260516_005816_6964.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_20260516_005816_6964.zip) |
| Flutter APP（安卓） | `HealthSelfCheckResult.toJson()` 与 `chat_screen._submitHealthSelfCheck` 一并改造为发送 `body_part_id`；卡片气泡 metadata 仍保留 `body_part` 对象（展示用）。 | [app_20260516-005842_f5c3.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/app_20260516-005842_f5c3.apk) |
| Flutter APP（iOS） | 同上（Flutter 共享代码改动覆盖 iOS） | [GitHub Release iOS-v20260516-005759-de96](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-v20260516-005759-de96) |

> ⚠️ 以上终端的代码在本次更新中均有改动，请务必下载最新版本体验。

---

## 使用说明

### 步骤一：进入 AI 对话首页

打开 H5 / 小程序 / APP 的首页（AI 对话首页 `ai-home`），登录后进入即可。

### 步骤二：触发"健康自查"

可以通过以下任一入口触发：

- **入口 A：顶部"功能宫格"**：点击【健康自查】方形按钮（图标 + 名称）。修复后**会直接弹出健康自查抽屉**。
- **入口 B：输入框上方"胶囊条"**：点击【健康自查】胶囊。同样直接弹出健康自查抽屉。
- 两种入口行为**完全一致**。

### 步骤三：在抽屉中完成三项选择

1. **选部位**：点击如"头部 🧠""眼部 👁""胸部 🫁""腹部 🍑"等图标卡片。
2. **选症状**：勾选 1 项及以上症状（如头部 → 头痛、头晕、偏头痛 …）。
3. **选持续时间**：选择 `<1天 / 1-3天 / 3-7天 / >1周 / >1月` 等档位。

> 三项必须全部选择，否则会高亮提示。

### 步骤四：开始 AI 分析

点击底部【开始 AI 分析】按钮后：

- 对话流即刻出现"健康自查卡片气泡"（用户侧，含部位名 / 图标 / 症状 / 持续时间 / 咨询人信息）。
- AI 侧短暂显示"正在分析中…"占位，随后被替换为针对所选部位 / 症状 / 持续时间的健康参考回答（医生口吻 + 免责声明）。
- **不会**出现"分析失败，请点击重试"。

---

## 微信小程序体验

### 下载小程序代码

点击下方链接下载微信小程序源码压缩包：

> 📦 下载地址：[miniprogram_20260516_005816_6964.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_20260516_005816_6964.zip)
> 大小约 **0.41 MB**

### 体验步骤

1. **下载压缩包**：点击上方链接，将 zip 下载到本地电脑。
2. **解压文件**：解压到任意目录（记住解压后的文件夹路径）。
3. **下载微信开发者工具**：如尚未安装，请前往 [微信开发者工具官方下载页面](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html)。
4. **打开微信开发者工具**并使用微信扫码登录。
5. **导入项目**：点击首页的「导入项目」，目录选择第 2 步解压后的文件夹，AppID 选择「测试号」或填入项目 AppID，点击「导入」。
6. **预览体验**：开发者工具会自动编译并在模拟器中展示小程序界面，进入聊天页 → 触发健康自查抽屉 → 完成三项选择 → 点【开始 AI 分析】，可观测到 AI 给出健康参考回答。

---

## 安卓端体验

### 下载安装包

> 📱 下载地址：[app_20260516-005842_f5c3.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/app_20260516-005842_f5c3.apk)
> 大小约 **80.87 MB**

### 安装与体验步骤

1. **下载 APK**：点击上方链接（可在手机浏览器直接打开）。
2. **允许安装**：手机若提示"不允许安装未知来源应用"，请前往「设置 → 安全 / 隐私」开启"允许此来源安装应用"。
3. **安装应用**：点击下载的 APK 文件，按照提示完成安装。
4. **打开体验**：桌面找到 bini-health 应用图标 → 登录 → 进入聊天屏 → 触发健康自查抽屉 → 选择三项 → 点【开始 AI 分析】，观测 AI 健康参考回答。

---

## iOS 端体验

### 下载安装包

> 🍎 GitHub Release 页面：[iOS Build ios-v20260516-005759-de96](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-v20260516-005759-de96)
>
> 📦 IPA 直接下载：[bini_health_ios.ipa](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/download/ios-v20260516-005759-de96/bini_health_ios.ipa)

### 安装与体验步骤

1. **下载 IPA 文件**：点击上方"IPA 直接下载"链接，将 IPA 下载到电脑。
2. **安装到设备**（IPA 未经 App Store 签名，需选择以下任一方式）：
   - **方式一：AltStore / Sideloadly / SideStore 侧载**
     - 电脑安装 [AltStore](https://altstore.io/) / [Sideloadly](https://sideloadly.io/) / [SideStore](https://sidestore.io/)
     - iPhone/iPad 通过数据线连接电脑
     - 用工具将 IPA 安装到设备（使用个人 Apple ID 自签）
   - **方式二：Apple Configurator 2（Mac 电脑）**
     - Mac 打开 Apple Configurator 2 → 连接 iPhone/iPad → 将 IPA 拖到设备安装
   - **方式三：TrollStore**（仅限特定 iOS 版本的越狱设备）
   - **方式四：企业证书重签**后通过 MDM 分发
3. **信任开发者证书**（如安装后无法打开）：「设置 → 通用 → VPN 与设备管理 → 信任开发者证书」。
4. **打开体验**：桌面找到 bini-health 应用图标 → 登录 → 进入聊天屏 → 触发健康自查抽屉 → 选择三项 → 点【开始 AI 分析】。

---

## 注意事项

- **AI 回答仅供参考**：所有健康参考分析末尾都会附带"本回答仅供健康参考，不构成诊疗依据，如不适请及时就医。"免责声明。请勿将其作为诊疗依据。
- **网络要求**：AI 推理需要良好的网络连接，单次提交后端约耗时 20~30 秒。
- **iOS 安装限制**：本次 iOS 包未经 App Store 签名，仅供测试体验。如设备没有越狱也没有 AltStore 等工具，可使用 Apple Configurator + Mac 电脑安装。
- **小程序 AppID**：体验时可使用"测试号"，无需正式 AppID。
- **测试登录账号**：H5 / 小程序 / APP 都支持测试号 `13800138000`，验证码固定为 `123456`。

---

## 自动化验证已通过

本次修复在服务器侧执行了如下非 UI 自动化测试，**全部通过**：

| 测试类型 | 测试条目 | 结果 |
|----------|----------|------|
| 后端冒烟 | `/api/health`、字典、模板、`/api/health-plan/today-todos`、`/api/health-self-check/start` | 8 / 8 PASS |
| 端到端（含真实登录） | 登录 → 字典 → 按钮 → 模板 → today-todos → start（新 payload）→ 反例（旧 payload 应被 schema 拒绝） | 8 / 8 PASS |
| 稳定性（连续 5 次） | 5 次不同部位 / 症状 / 持续时间组合提交 → AI 均成功返回 | 5 / 5 PASS（每次 20~28 秒） |

---

## 访问链接

以下是本项目最新版本的访问/下载入口，点击即可使用：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），不涉及 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 前端（已修复上线） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | AI 对话首页入口（修复后） |
| 微信小程序下载 | [miniprogram_20260516_005816_6964.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_20260516_005816_6964.zip) | 微信小程序源码压缩包（导入微信开发者工具） |
| 安卓 APK 下载 | [app_20260516-005842_f5c3.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/app_20260516-005842_f5c3.apk) | Flutter 安卓客户端最新安装包 |
| iOS 端下载 | [iOS Build ios-v20260516-005759-de96](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-v20260516-005759-de96) | iOS 客户端构建 Release 页面（含 IPA 资产） |
