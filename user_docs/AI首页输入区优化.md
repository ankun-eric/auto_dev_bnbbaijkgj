# AI 首页输入区优化 · 用户体验使用手册

> 版本：2026-06-02　｜　涉及端：H5 网页端、微信小程序、安卓 App、iOS App

本次对「AI 首页（智能问答首页）」的底部输入区做了两处体验优化：① 输入框上方的「已结合健康档案」提示文字显示更完整；② 语音「按住说话」增加了完整的按压反馈效果。

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| 前端页面（AI 首页） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home) | AI 智能问答首页，本次优化页面 |
| 项目主页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 项目入口 |
| 微信小程序代码包下载 | [miniprogram_aihome_input_hint_20260602_131319_789a.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/miniprogram_aihome_input_hint_20260602_131319_789a.zip) | 导入微信开发者工具体验 |
| 安卓 APK 下载 | [app_aihome_input_hint_20260602_131356_0v79.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/app_aihome_input_hint_20260602_131356_0v79.apk) | 安卓客户端安装包 |
| iOS 端下载 | [iOS Build ios-v20260602-131352-y2i7](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-v20260602-131352-y2i7) | 前往 GitHub Release 下载 IPA |

---

## 功能简介

### 优化一：输入框上方提示文字显示更完整

- **位置**：AI 首页底部输入框**上方**那一行灰色小字提示。
- **变化**：
  - 文案精简：由原来的 `问答已结合【XX】的健康档案` 改为 `问答已结合【XX】健康档案`（去掉「的」字）。
  - 字号缩小：提示文字改用更小的字号并保证单行显示，常规长度的名字下整行可完整展示，不再被右侧发送按钮挤断、不再显示不全。
  - 样式保持小灰字风格不变。
- 其中 `XX` 为当前选中的咨询对象（如「本人」「母亲」「父亲」等关系或姓名）。

### 优化二：语音「按住说话」按压效果

切换到语音输入模式后，长按「按住说话」按钮录音时，新增以下 5 项反馈，操作有没有按上、有没有在录音一目了然：

1. **按钮按下反馈**：按住时按钮变色并轻微下沉缩小，一眼看出「已按住」。
2. **录音浮层 + 声波动画**：屏幕上方弹出**天蓝半透明**录音浮层，浮层内有跳动的白色声波动画（H5 端声波随说话音量实时起伏）。
3. **文字提示切换**：按钮文字由「按住说话」切换为「松开发送」。
4. **震动反馈**：按下瞬间手机轻震一下（H5 网页端依赖浏览器/设备支持振动能力）。
5. **上滑取消**：录音时手指上滑可取消本次发送，浮层提示「松开取消」。

---

## 本次客户端变更

本次更新涉及以下终端的代码改动，请下载最新版本体验：

| 终端 | 变更说明 | 新版本下载 |
|------|----------|------------|
| 微信小程序 | AI 对话「按住说话」按压效果优化：新增按下震动、按下缩小、录音浮层改为天蓝半透明 + 白色声波 | [miniprogram_aihome_input_hint_20260602_131319_789a.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/miniprogram_aihome_input_hint_20260602_131319_789a.zip) |
| 安卓端 | AI 对话「按住说话」按压效果优化：按下震动（HapticFeedback）、按下缩小、录音浮层天蓝半透明、文字「松开发送」 | [app_aihome_input_hint_20260602_131356_0v79.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/app_aihome_input_hint_20260602_131356_0v79.apk) |
| iOS 端 | AI 对话「按住说话」按压效果优化：同安卓端 | [iOS Build ios-v20260602-131352-y2i7](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-v20260602-131352-y2i7) |

> ⚠️ 以上终端的代码在本次更新中有改动，请务必下载最新版本。H5 网页端已直接更新部署，打开网页即为最新版，无需另行下载。

---

## 使用说明

### 一、查看输入框上方提示文字（优化一）

1. 打开 [AI 首页](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home)。
2. 看页面底部输入框，**正上方**有一行灰色小字：`问答已结合【XX】健康档案`。
3. 切换咨询对象（点击底部「为(XX)咨询 ⇄」胶囊）后，提示中的 `XX` 会随之更新；常规长度的名字下整行可完整显示。

### 二、体验「按住说话」按压效果（优化二）

1. 在 AI 首页底部输入区，点击左侧的**麦克风图标**，切换到语音输入模式，此时出现「按住说话」按钮。
2. **长按**「按住说话」按钮：
   - 按钮立即变色并轻微下沉缩小；
   - 手机轻震一下（取决于设备支持）；
   - 屏幕上方弹出天蓝半透明录音浮层，内有跳动的白色声波；
   - 按钮文字变为「松开发送」。
3. 说话完毕后**松开手指**，即自动完成语音识别并发送。
4. 若想取消本次录音：按住状态下**手指上滑**，浮层会提示「松开取消」，此时松手即取消，不会发送。
5. 想切回文字输入：点击麦克风旁的**键盘图标**即可。

---

## 微信小程序体验

### 下载小程序代码

点击以下链接下载微信小程序代码压缩包：

> 📦 下载地址：[miniprogram_aihome_input_hint_20260602_131319_789a.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/miniprogram_aihome_input_hint_20260602_131319_789a.zip)

### 体验步骤

1. **下载压缩包**：点击上方链接，将 zip 压缩包下载到本地电脑。
2. **解压文件**：将下载的 zip 文件解压到任意目录（记住解压后的文件夹路径）。
3. **下载微信开发者工具**：如尚未安装，请前往 [微信开发者工具官方下载页面](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html) 下载并安装。
4. **打开微信开发者工具**：启动开发者工具，使用微信扫码登录。
5. **导入项目**：
   - 点击开发者工具首页的「导入项目」（或「+」号）；
   - 在「目录」栏点击浏览，选择第 2 步解压后的文件夹；
   - 「AppID」栏可填入项目的 AppID，或选择「测试号」进行体验；
   - 点击「导入」按钮。
6. **预览体验**：导入成功后，进入「AI 对话」页，切换到语音模式长按「按住说话」即可体验本次优化。

---

## 安卓端体验

### 下载安装包

点击以下链接下载安卓客户端安装包：

> 📱 下载地址：[app_aihome_input_hint_20260602_131356_0v79.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/app_aihome_input_hint_20260602_131356_0v79.apk)

### 安装与体验步骤

1. **下载 APK**：点击上方链接，将 APK 安装包下载到手机（或先下载到电脑再传输到手机）。
2. **允许安装**：如果手机提示「不允许安装未知来源应用」，请在手机设置中开启「允许安装未知来源应用」（一般在「设置 → 安全」或「设置 → 隐私」中）。
3. **安装应用**：点击下载的 APK 文件，按照提示完成安装。
4. **打开体验**：安装完成后，在手机桌面找到应用图标，进入 AI 对话页，切换语音模式长按「按住说话」即可体验。

---

## iOS 端体验

### 下载安装包

点击以下链接前往 GitHub Release 页面下载 iOS 客户端安装包：

> 🍎 GitHub Release 页面：[iOS Build ios-v20260602-131352-y2i7](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-v20260602-131352-y2i7)
>
> 📦 IPA 直接下载：[bini_health_ios.ipa](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/download/ios-v20260602-131352-y2i7/bini_health_ios.ipa)

### 安装与体验步骤

1. **下载 IPA 文件**：点击上方「IPA 直接下载」链接，将 IPA 安装包下载到电脑。
2. **安装到设备**（该包未做代码签名，需自签安装，选择以下任一方式）：
   - **方式一：使用 AltStore / Sideloadly 等工具侧载**
     - 在电脑上安装 [AltStore](https://altstore.io/) 或 [Sideloadly](https://sideloadly.io/)；
     - 将 iPhone/iPad 通过数据线连接到电脑；
     - 使用工具将下载的 IPA 文件自签并安装到设备上。
   - **方式二：使用 Apple Configurator（需 Mac）**
     - 在 Mac 上打开 Apple Configurator 2，连接设备后将 IPA 拖入安装。
3. **信任开发者证书**（如安装后无法打开）：前往「设置 → 通用 → VPN 与设备管理」，找到对应证书并点击「信任」。
4. **打开体验**：安装完成后，进入 AI 对话页，切换语音模式长按「按住说话」即可体验。

---

## 注意事项

- **H5 网页端**已直接部署最新版，打开网页即为最新效果，无需下载。
- **震动反馈**取决于设备能力：部分浏览器/设备可能不支持网页振动；小程序、安卓、iOS 原生端支持更稳定。
- **录音权限**：首次使用语音输入需授权麦克风权限，未授权时无法录音。
- **上滑取消**判定为手指向上滑动一段距离（约半屏内），松手即取消，不会发送语音。
- **超长用户名提示**：若个别用户名特别长，提示文字在精简和缩小字号后仍可能放不下，此为已知遗留项，后续再行优化。

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| 前端页面（AI 首页） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home) | AI 智能问答首页，本次优化页面 |
| 项目主页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 项目入口 |
| 微信小程序代码包下载 | [miniprogram_aihome_input_hint_20260602_131319_789a.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/miniprogram_aihome_input_hint_20260602_131319_789a.zip) | 导入微信开发者工具体验 |
| 安卓 APK 下载 | [app_aihome_input_hint_20260602_131356_0v79.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/app_aihome_input_hint_20260602_131356_0v79.apk) | 安卓客户端安装包 |
| iOS 端下载 | [iOS Build ios-v20260602-131352-y2i7](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-v20260602-131352-y2i7) | 前往 GitHub Release 下载 IPA |
