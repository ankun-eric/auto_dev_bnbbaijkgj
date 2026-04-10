# Bini Health — AI 咨询对话与健康档案 Bug 修复用户手册

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 前端页面 | [https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/](https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/) | H5 网页端入口（经 Nginx 代理） |
| 安卓 APK 下载 | [bini_health_android-v20260410-143948-iy52.apk](https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/bini_health_android-v20260410-143948-iy52.apk) | 安卓客户端安装包，点击下载后安装体验 |
| iOS 端下载 | [iOS Build ios-v20260410-144013-y1jl](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-v20260410-144013-y1jl) | iOS 客户端安装包，前往 GitHub Release 页面下载 |

---

## 功能简介

本次更新修复了 Bini Health 应用中 **AI 咨询对话** 和 **健康档案** 两大模块的 9 个 Bug，覆盖 H5 网页端、微信小程序端和 Flutter App 端（Android/iOS）。主要修复内容包括：

1. **麦克风权限优化**：不再重复弹出权限请求弹窗，已授权时直接进入语音模式
2. **发送按钮优化**：发送按钮嵌入输入框内部，在所有屏幕尺寸下始终可见
3. **咨询对象标识**：切换咨询对象按钮现在显示关系文字（如"本人"、"爸爸"），不同关系用不同颜色区分
4. **关系选择修复**：添加家庭成员时不再显示"本人"选项
5. **添加成员修复**：填写信息后点击"确认添加"可正常保存
6. **健康档案 Tab 切换**：成员切换改为直观的圆形图标 Tab 方式
7. **表单校验优化**：后端不再强制要求姓名/性别/出生日期，前端负责友好提示
8. **存量用户补数据**：所有老用户自动补齐"本人"家庭成员记录
9. **关系列表修复**：添加成员弹窗正常显示关系选择网格

---

## 本次客户端变更

本次更新涉及以下客户端平台的代码改动，请下载最新版本体验：

| 平台 | 变更说明 | 新版本下载 |
|------|----------|------------|
| 微信小程序 | 麦克风权限优化、发送按钮内嵌、咨询对象关系文字+颜色、动态加载关系类型、Grid关系选择、Tab圆形图标切换 | [miniprogram_20260410_144018_0b00.zip](https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/miniprogram_20260410_144018_0b00.zip) |
| 安卓端 | 麦克风权限缓存、输入栏紧凑布局、咨询对象圆形图标、动态加载关系类型、StatefulBuilder弹窗修复、Tab圆形图标切换 | [bini_health_android-v20260410-143948-iy52.apk](https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/bini_health_android-v20260410-143948-iy52.apk) |
| iOS 端 | 同安卓端修复内容（Flutter 跨平台共享代码） | [iOS Build ios-v20260410-144013-y1jl](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-v20260410-144013-y1jl) |

> ⚠️ 以上平台的代码在本次更新中有改动，请务必下载最新版本。

---

## 使用说明

### 一、AI 咨询对话

#### 1. 进入对话页面

登录应用后，在首页点击 **"AI 健康咨询"** 进入对话页面。

#### 2. 语音输入（已优化）

- 点击输入框右侧的 **🎤 麦克风按钮** 切换到语音模式
- **首次使用**：系统会弹出一次授权请求，请点击"去授权"并允许麦克风权限
- **后续使用**：已授权后将直接进入语音模式，**不会再次弹窗**
- 长按"按住说话"按钮开始录音，松开结束并发送

#### 3. 文字输入与发送（已优化）

- 在输入框中输入文字后，输入框**右侧内部**会出现绿色圆形发送按钮
- 点击发送按钮即可发送消息
- 在任何屏幕尺寸的手机上，发送按钮都**始终可见、可点击**

#### 4. 切换咨询对象（已优化）

- 输入栏**左侧**有一个圆形图标按钮，显示当前咨询对象的关系文字
- 不同关系类型用不同颜色区分：
  - 🟢 **本人**：绿色
  - 🔵 **爸爸/妈妈**：蓝色
  - 🩷 **儿子/女儿**：粉色
  - 🟠 **爷爷/奶奶**：橙色
  - ⚪ **其他关系**：灰色
- 点击该按钮可弹出家庭成员选择列表，选择后即可为对应成员进行健康咨询

### 二、健康档案

#### 1. 成员切换（已优化为 Tab 圆形图标）

- 进入健康档案页面后，顶部显示**圆形图标 Tab 栏**
- 第一个 Tab 固定为 **"本人"**（绿色），其他 Tab 为已添加的家庭成员
- 选中的 Tab 高亮显示对应颜色背景 + 白色文字
- 未选中的 Tab 显示浅灰色背景 + 深色文字
- 点击不同 Tab 即可切换查看对应成员的健康信息

#### 2. 添加家庭成员（已修复）

- 点击 Tab 栏最右侧的 **"+"** 按钮
- 弹出添加家庭成员弹窗，关系选择区域正常显示**网格布局的关系按钮**
- 关系列表中**不会出现"本人"**选项（"本人"是自动创建的）
- 选择关系后填写姓名、性别、出生日期等信息
- 点击 **"确认添加"** 按钮即可成功保存

#### 3. 表单填写说明

- **姓名**：建议填写，方便识别家庭成员
- **性别**：建议选择，有助于 AI 提供更精准的健康建议
- **出生日期**：建议填写，有助于年龄相关的健康分析
- 以上字段在页面层面会提示必填，但如果暂时不方便填写，可以先创建成员后续补充

---

## 微信小程序体验

### 下载小程序代码

点击以下链接下载微信小程序代码压缩包：

> 📦 下载地址：[miniprogram_20260410_144018_0b00.zip](https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/miniprogram_20260410_144018_0b00.zip)

### 体验步骤

1. **下载压缩包**：点击上方链接，将 zip 压缩包下载到本地电脑
2. **解压文件**：将下载的 zip 文件解压到任意目录（记住解压后的文件夹路径）
3. **下载微信开发者工具**：如尚未安装，请前往 [微信开发者工具官方下载页面](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html) 下载并安装
4. **打开微信开发者工具**：启动开发者工具，使用微信扫码登录
5. **导入项目**：
   - 点击开发者工具首页的「导入项目」（或「+」号）
   - 在「目录」栏点击浏览，选择第 2 步解压后的文件夹
   - 「AppID」栏可填入项目的 AppID，或选择「测试号」进行体验
   - 点击「导入」按钮
6. **预览体验**：导入成功后，开发者工具会自动编译并在模拟器中展示小程序界面，您可以直接在模拟器中操作体验

---

## 安卓端体验

### 下载安装包

点击以下链接下载安卓客户端安装包：

> 📱 下载地址：[bini_health_android-v20260410-143948-iy52.apk](https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/bini_health_android-v20260410-143948-iy52.apk)

### 安装与体验步骤

1. **下载 APK**：点击上方链接，将 APK 安装包下载到手机（或先下载到电脑再传输到手机）
2. **允许安装**：如果手机提示「不允许安装未知来源应用」，请在手机设置中开启「允许安装未知来源应用」（不同手机品牌设置路径可能不同，一般在「设置 → 安全」或「设置 → 隐私」中）
3. **安装应用**：点击下载的 APK 文件，按照提示完成安装
4. **打开体验**：安装完成后，在手机桌面找到应用图标，点击打开即可体验

---

## iOS 端体验

### 下载安装包

点击以下链接前往 GitHub Release 页面下载 iOS 客户端安装包：

> 🍎 GitHub Release 页面：[iOS Build ios-v20260410-144013-y1jl](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-v20260410-144013-y1jl)
>
> 📦 IPA 直接下载：[bini_health_ios.ipa](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/download/ios-v20260410-144013-y1jl/bini_health_ios.ipa)

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
4. **打开体验**：安装完成后，在手机桌面找到应用图标，点击打开即可体验

---

## 注意事项

1. **麦克风权限**：首次使用语音输入功能时需要授权麦克风权限，授权一次后不会重复弹窗
2. **"本人"记录**：每个用户自动拥有一条"本人"家庭成员记录，无需手动添加，不可删除
3. **添加家庭成员**：关系选择列表中不包含"本人"选项，因为"本人"是系统自动创建的
4. **网络要求**：使用 AI 咨询功能需要网络连接，请确保手机网络正常
5. **浏览器兼容性**（H5 端）：推荐使用 Chrome、Safari 等主流浏览器访问

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 前端页面 | [https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/](https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/) | H5 网页端入口（经 Nginx 代理） |
| 安卓 APK 下载 | [bini_health_android-v20260410-143948-iy52.apk](https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/bini_health_android-v20260410-143948-iy52.apk) | 安卓客户端安装包，点击下载后安装体验 |
| iOS 端下载 | [iOS Build ios-v20260410-144013-y1jl](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-v20260410-144013-y1jl) | iOS 客户端安装包，前往 GitHub Release 页面下载 |
