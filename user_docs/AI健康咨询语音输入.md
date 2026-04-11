# AI 健康咨询 — 语音输入功能使用手册

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 前端页面 | [https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/) | H5 移动端主页面入口 |
| 安卓 APK 下载 | [bini_health_android-v20260410-123302-2xm7.apk](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/bini_health_android-v20260410-123302-2xm7.apk) | 安卓客户端安装包，点击下载后安装体验 |
| iOS 端下载 | [iOS Build ios-v20260410-123303-4088](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-v20260410-123303-4088) | iOS 客户端安装包，前往 GitHub Release 页面下载 |
| 微信小程序代码包 | [miniprogram_20260410_123240_a5a5.zip](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/miniprogram_20260410_123240_a5a5.zip) | 小程序代码包，下载后导入微信开发者工具 |

---

## 功能简介

本次更新在 **AI 健康咨询对话页面** 新增了 **语音输入** 功能，覆盖 **H5 移动端**、**微信小程序**、**Flutter App（iOS & Android）** 三端。

用户在与 AI 健康助手对话时，除了传统的键盘文字输入外，现在可以通过 **"按住说话"** 的方式用语音描述健康问题，系统会自动将语音识别为文字并发送给 AI，获得健康建议。

**核心特性：**
- 语音/键盘一键切换
- 类微信"按住说话"交互
- 支持上滑取消录音
- 30秒最大录音时长
- 语音自动识别为文字发送
- 完善的权限引导和异常处理

---

## 本次客户端变更

本次更新涉及以下客户端平台的代码改动，请下载最新版本体验：

| 平台 | 变更说明 | 新版本下载 |
|------|----------|------------|
| H5 移动端 | AI健康咨询对话页面新增语音/键盘切换、按住说话录音、声波动画遮罩、ASR识别自动发送 | [H5 在线体验](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/) |
| 微信小程序 | AI健康咨询对话页面新增语音输入，使用WechatSI插件进行端侧语音识别 | [miniprogram_20260410_123240_a5a5.zip](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/miniprogram_20260410_123240_a5a5.zip) |
| 安卓端 | AI健康咨询对话页面新增语音输入，使用record包录音+后端ASR识别 | [bini_health_android-v20260410-123302-2xm7.apk](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/bini_health_android-v20260410-123302-2xm7.apk) |
| iOS 端 | AI健康咨询对话页面新增语音输入，使用record包录音+后端ASR识别 | [iOS Build ios-v20260410-123303-4088](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-v20260410-123303-4088) |

> ⚠️ 以上平台的代码在本次更新中有改动，请务必下载最新版本。

---

## 使用说明

### 第一步：进入 AI 健康咨询页面

打开比尼健康 App 或 H5 页面，进入 **AI 健康咨询** 对话界面。

### 第二步：切换到语音模式

在对话输入栏中，您会看到输入框右侧有一个 **🎤 麦克风图标**，点击它即可切换到语音输入模式。

- **键盘模式**（默认）：显示文字输入框 "发信息..."，右侧有麦克风图标
- **语音模式**：输入框变为绿色的 **"按住说话"** 按钮，右侧图标变为键盘图标

> 💡 想切换回键盘输入？点击右侧的 ⌨️ 键盘图标即可。

### 第三步：按住说话

切换到语音模式后：

1. **长按** "按住说话" 按钮开始录音
2. 屏幕会弹出半透明遮罩，显示 **声波动画** 和提示 "松开发送，上滑取消"
3. 对着手机说出您的健康问题，例如："最近经常头疼怎么办"
4. **松开手指** 即可自动识别并发送

### 第四步：取消录音（可选）

如果说错了想重新录：
- 录音过程中 **手指向上滑动** 超过一定距离
- 遮罩会变为红色，提示 "松开取消"
- 此时松开手指，录音会被丢弃，不会发送

### 第五步：查看 AI 回复

语音识别的文字会作为普通文字消息自动发送给 AI，AI 将根据您的描述给出健康建议。语音输入和键盘输入的消息外观完全一致。

---

## 微信小程序体验

### 下载小程序代码

点击以下链接下载微信小程序代码压缩包：

> 📦 下载地址：[miniprogram_20260410_123240_a5a5.zip](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/miniprogram_20260410_123240_a5a5.zip)

### 体验步骤

1. **下载压缩包**：点击上方链接，将 zip 压缩包下载到本地电脑
2. **解压文件**：将下载的 zip 文件解压到任意目录（记住解压后的文件夹路径）
3. **下载微信开发者工具**：如尚未安装，请前往 [微信开发者工具官方下载页面](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html) 下载并安装
4. **打开微信开发者工具**：启动开发者工具，使用微信扫码登录
5. **导入项目**：
   - 点击开发者工具首页的「导入项目」（或「+」号）
   - 在「目录」栏点击浏览，选择第 2 步解压后的 `miniprogram` 文件夹
   - 「AppID」栏可填入项目的 AppID，或选择「测试号」进行体验
   - 点击「导入」按钮
6. **预览体验**：导入成功后，开发者工具会自动编译并在模拟器中展示小程序界面，进入 AI 健康咨询页面即可体验语音输入功能

---

## 安卓端体验

### 下载安装包

点击以下链接下载安卓客户端安装包：

> 📱 下载地址：[bini_health_android-v20260410-123302-2xm7.apk](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/bini_health_android-v20260410-123302-2xm7.apk)

### 安装与体验步骤

1. **下载 APK**：点击上方链接，将 APK 安装包下载到手机（或先下载到电脑再传输到手机）
2. **允许安装**：如果手机提示「不允许安装未知来源应用」，请在手机设置中开启「允许安装未知来源应用」（不同手机品牌设置路径可能不同，一般在「设置 → 安全」或「设置 → 隐私」中）
3. **安装应用**：点击下载的 APK 文件，按照提示完成安装
4. **打开体验**：安装完成后，在手机桌面找到「宾尼小康」应用图标，点击打开，进入 AI 健康咨询页面即可体验语音输入

---

## iOS 端体验

### 下载安装包

点击以下链接前往 GitHub Release 页面下载 iOS 客户端安装包：

> 🍎 GitHub Release 页面：[iOS Build ios-v20260410-123303-4088](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-v20260410-123303-4088)
>
> 📦 IPA 直接下载：[bini_health_ios.ipa](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/download/ios-v20260410-123303-4088/bini_health_ios.ipa)

### 安装与体验步骤

1. **下载 IPA 文件**：点击上方「IPA 直接下载」链接，将 IPA 安装包下载到电脑
2. **安装到设备**（选择以下任一方式）：
   - **方式一：使用 AltStore / Sideloadly 等第三方工具侧载安装**
     - 在电脑上安装 [AltStore](https://altstore.io/) 或 [Sideloadly](https://sideloadly.io/)
     - 将 iPhone/iPad 通过数据线连接到电脑
     - 使用工具将下载的 IPA 文件安装到设备上
   - **方式二：使用 Apple Configurator（需 Mac 电脑）**
     - 在 Mac 上打开 Apple Configurator 2
     - 连接 iPhone/iPad，将 IPA 文件拖拽到设备上安装
   - **方式三：通过 TestFlight（如项目已配置 TestFlight 分发）**
     - 在 iPhone/iPad 上安装 [TestFlight](https://apps.apple.com/app/testflight/id899247664) App
     - 根据项目提供的 TestFlight 邀请链接加入测试
3. **信任开发者证书**（如安装后无法打开）：前往「设置 → 通用 → VPN 与设备管理」，找到对应的开发者证书并点击「信任」
4. **打开体验**：安装完成后，在手机桌面找到应用图标，点击打开，进入 AI 健康咨询页面即可体验语音输入

---

## 注意事项

### 权限说明
- **首次使用语音功能**时，系统会请求麦克风权限，请点击「允许」以正常使用
- 如果之前拒绝了权限，可以在手机的系统设置中重新开启麦克风权限

### 录音规则
- 最大录音时长为 **30 秒**，到达上限后会自动识别并发送
- 录音时间过短（< 0.5 秒）不会触发录音，会提示"录音时间太短"
- 录音过程中可以随时 **上滑取消**

### 网络要求
- 语音识别需要网络连接（使用腾讯云 ASR 服务）
- 网络异常时会自动切换回键盘输入模式，并提示"语音服务暂不可用"

### 语言支持
- 目前仅支持 **中文** 语音识别

### 消息展示
- 通过语音输入的文字消息与手动打字发送的消息 **外观完全一致**
- 在对话界面中无法区分消息是语音输入还是键盘输入

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 前端页面 | [https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/) | H5 移动端主页面入口 |
| 安卓 APK 下载 | [bini_health_android-v20260410-123302-2xm7.apk](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/bini_health_android-v20260410-123302-2xm7.apk) | 安卓客户端安装包，点击下载后安装体验 |
| iOS 端下载 | [iOS Build ios-v20260410-123303-4088](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-v20260410-123303-4088) | iOS 客户端安装包，前往 GitHub Release 页面下载 |
| 微信小程序代码包 | [miniprogram_20260410_123240_a5a5.zip](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/miniprogram_20260410_123240_a5a5.zip) | 小程序代码包，下载后导入微信开发者工具 |

## 微信小程序体验

### 下载小程序代码

点击以下链接下载微信小程序代码压缩包：

> 📦 下载地址：[miniprogram_20260410_123240_a5a5.zip](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/miniprogram_20260410_123240_a5a5.zip)

### 体验步骤

1. **下载压缩包**：点击上方链接，将 zip 压缩包下载到本地电脑
2. **解压文件**：将下载的 zip 文件解压到任意目录（记住解压后的文件夹路径）
3. **下载微信开发者工具**：如尚未安装，请前往 [微信开发者工具官方下载页面](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html) 下载并安装
4. **打开微信开发者工具**：启动开发者工具，使用微信扫码登录
5. **导入项目**：
   - 点击开发者工具首页的「导入项目」（或「+」号）
   - 在「目录」栏点击浏览，选择第 2 步解压后的 `miniprogram` 文件夹
   - 「AppID」栏可填入项目的 AppID，或选择「测试号」进行体验
   - 点击「导入」按钮
6. **预览体验**：导入成功后，开发者工具会自动编译并在模拟器中展示小程序界面，进入 AI 健康咨询页面即可体验语音输入功能

## 安卓端体验

### 下载安装包

点击以下链接下载安卓客户端安装包：

> 📱 下载地址：[bini_health_android-v20260410-123302-2xm7.apk](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/bini_health_android-v20260410-123302-2xm7.apk)

### 安装与体验步骤

1. **下载 APK**：点击上方链接，将 APK 安装包下载到手机（或先下载到电脑再传输到手机）
2. **允许安装**：如果手机提示「不允许安装未知来源应用」，请在手机设置中开启「允许安装未知来源应用」
3. **安装应用**：点击下载的 APK 文件，按照提示完成安装
4. **打开体验**：安装完成后，在手机桌面找到「宾尼小康」应用图标，点击打开即可体验

## iOS 端体验

### 下载安装包

点击以下链接前往 GitHub Release 页面下载 iOS 客户端安装包：

> 🍎 GitHub Release 页面：[iOS Build ios-v20260410-123303-4088](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-v20260410-123303-4088)
>
> 📦 IPA 直接下载：[bini_health_ios.ipa](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/download/ios-v20260410-123303-4088/bini_health_ios.ipa)

### 安装与体验步骤

1. **下载 IPA 文件**：点击上方「IPA 直接下载」链接，将 IPA 安装包下载到电脑
2. **安装到设备**：使用 AltStore、Sideloadly 等第三方工具侧载安装到 iPhone/iPad
3. **信任开发者证书**：前往「设置 → 通用 → VPN 与设备管理」，找到对应证书并信任
4. **打开体验**：在手机桌面找到应用图标，点击打开即可体验
