# OCR 识别多图上传功能 - 用户体验使用手册

**版本**：v1.0  
**发布日期**：2026-04-08  

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 前端页面 | [https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/](https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/) | H5 用户端主页面入口 |
| 安卓 APK 下载 | [bini_health_android-v20260408-114940-zqrf.apk](https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/uploads/bini_health_android-v20260408-114940-zqrf.apk) | 安卓客户端安装包，点击下载后安装体验 |
| iOS 端下载 | [iOS Build ios-v20260408-115950-retry1](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-v20260408-115950-retry1) | iOS 客户端安装包，点击前往 GitHub Release 页面下载 |
| 微信小程序下载 | [miniprogram_20260408_114910_809c.zip](https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/uploads/miniprogram_20260408_114910_809c.zip) | 微信小程序代码包，导入微信开发者工具体验 |

---

## 微信小程序体验

### 下载小程序代码

点击以下链接下载微信小程序代码压缩包：

> 📦 下载地址：[miniprogram_20260408_114910_809c.zip](https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/uploads/miniprogram_20260408_114910_809c.zip)

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

> 📱 下载地址：[bini_health_android-v20260408-114940-zqrf.apk](https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/uploads/bini_health_android-v20260408-114940-zqrf.apk)

### 安装与体验步骤

1. **下载 APK**：点击上方链接，将 APK 安装包下载到手机（或先下载到电脑再传输到手机）
2. **允许安装**：如果手机提示「不允许安装未知来源应用」，请在手机设置中开启「允许安装未知来源应用」（不同手机品牌设置路径可能不同，一般在「设置 → 安全」或「设置 → 隐私」中）
3. **安装应用**：点击下载的 APK 文件，按照提示完成安装
4. **打开体验**：安装完成后，在手机桌面找到应用图标，点击打开即可体验

---

## iOS 端体验

### 下载安装包

点击以下链接前往 GitHub Release 页面下载 iOS 客户端安装包：

> 🍎 GitHub Release 页面：[iOS Build ios-v20260408-115950-retry1](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-v20260408-115950-retry1)
>
> 📦 IPA 直接下载：[bini_health_ios.ipa](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/download/ios-v20260408-115950-retry1/bini_health_ios.ipa)

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
3. **信任开发者证书**（如安装后无法打开）：前往「设置 → 通用 → VPN 与设备管理」，找到对应的开发者证书并点击「信任」
4. **打开体验**：安装完成后，在手机桌面找到应用图标，点击打开即可体验

---

## 功能简介

本次更新为 bini-health 系统的所有 OCR 识别场景（体检报告解读、拍照识药）升级为支持**多图上传**功能，覆盖微信小程序、H5、iOS/Android APP 四端及后台管理端。

### 主要新功能

1. **多图上传**：所有 OCR 场景支持一次上传最多 5 张图片（可在后台配置）
2. **图片预览管理**：上传前可预览已选图片，支持删除或替换单张图片
3. **上传进度提示**：实时显示"正在上传 X/N 张..."进度
4. **智能合并识别**：多张图片的识别结果由 AI 智能合并，输出一份完整报告
5. **历史记录标注**：历史记录中显示"共 N 张"，让用户知晓该记录包含多图
6. **管理端多图测试**：后台 OCR 配置页面支持多图上传测试

---

## 本次客户端变更

本次更新涉及以下客户端平台的代码改动，请下载最新版本体验：

| 平台 | 变更说明 | 新版本下载 |
|------|----------|------------|
| 微信小程序 | 体检报告和拍照识药页面支持多图选择、预览、删除，新增"开始识别"按钮 | [miniprogram_20260408_114910_809c.zip](https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/uploads/miniprogram_20260408_114910_809c.zip) |
| 安卓端 | 体检报告和拍照识药页面支持多图选择、预览、删除，新增"开始识别"按钮 | [bini_health_android-v20260408-114940-zqrf.apk](https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/uploads/bini_health_android-v20260408-114940-zqrf.apk) |
| iOS 端 | 体检报告和拍照识药页面支持多图选择、预览、删除，新增"开始识别"按钮 | [iOS Build ios-v20260408-115950-retry1](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-v20260408-115950-retry1) |

> ⚠️ 以上平台的代码在本次更新中有改动，请务必下载最新版本。未列出的平台表示本次无变更，可继续使用当前版本。

---

## 使用说明

### 体检报告多图上传（H5/小程序/APP 通用流程）

#### 步骤一：进入体检报告页面

- **H5**：登录后点击底部导航「健康」→「体检报告」
- **小程序**：进入小程序后点击「体检报告」入口
- **APP**：登录后点击底部导航「健康」→「体检报告」

#### 步骤二：选择图片

1. 点击「相册」按钮，从手机相册**多选**图片（最多 5 张）
2. 或点击「拍照」按钮，逐张拍摄图片（可多次拍摄后累积）
3. 选择图片后，页面会显示已选图片的**缩略图列表**

#### 步骤三：管理已选图片

- 查看"已选 X/5 张"提示，了解当前已选数量
- 如需删除某张图片，点击缩略图右上角的 **×** 按钮
- 如需继续添加图片，再次点击「相册」或「拍照」按钮

#### 步骤四：开始识别

1. 确认图片无误后，点击**「开始识别」**按钮
2. 页面显示上传进度："正在上传 X/N 张..."
3. 上传完成后显示"识别中，请稍候..."
4. 识别完成后自动跳转到结果页面

#### 步骤五：查看结果

- 结果页面展示 AI 对所有图片的**综合解读报告**
- 多张图片的内容已智能合并，去除重复信息

---

### 拍照识药多图上传（H5/小程序/APP 通用流程）

#### 步骤一：进入拍照识药页面

- **H5**：登录后点击「拍照识药」入口
- **小程序**：进入小程序后点击「拍照识药」
- **APP**：登录后找到「拍照识药」功能入口

#### 步骤二：选择/拍摄药品图片

1. 点击「拍照识药」按钮，拍摄药品包装照片
2. 或点击「从相册选择」按钮，从相册多选图片
3. 可以拍摄药品的正面、背面、说明书等多张图片

#### 步骤三：管理已选图片

- 查看已选图片缩略图列表
- 点击 **×** 删除不需要的图片
- 最多可选 5 张图片

#### 步骤四：开始识别

1. 点击**「开始识别」**按钮
2. 等待 AI 识别完成
3. 自动跳转到药品信息对话页面

---

### 后台管理端 OCR 测试（多图）

#### 步骤一：进入 OCR 全局设置

登录管理后台 → 左侧菜单「OCR全局设置」

#### 步骤二：切换到"OCR测试"标签

点击页面顶部的「OCR测试」Tab

#### 步骤三：上传测试图片

1. 点击上传区域或拖拽图片到上传框
2. 可上传多张图片（最多受上传限制配置约束）
3. 选择 OCR 提供商（必填）
4. 选择场景模板（可选，用于完整测试）

#### 步骤四：执行测试

- 点击**「仅OCR测试」**：仅测试 OCR 文字识别，不调用 AI
- 点击**「完整测试（含AI）」**：OCR 识别后调用 AI 处理

#### 步骤五：查看测试结果

- **每张图片结果**：可折叠展示每张图的识别文本
- **合并OCR文本**：所有图片识别文本的合并结果
- **合并AI结果**：AI 对合并文本的整体处理结果（JSON 格式）

---

## 注意事项

1. **图片数量限制**：默认最多上传 5 张图片，管理员可在「OCR全局设置 → 上传限制」中调整
2. **图片大小限制**：单张图片大小限制由全局设置配置，默认 5MB
3. **图片格式**：支持 JPG、PNG 等常见图片格式
4. **识别超时**：如果识别时间超过 30 秒，建议在历史记录中查看结果
5. **部分失败处理**：
   - 如果部分图片识别失败（图片模糊等），系统会提示哪张图片失败
   - 可以删除失败的图片后重新提交识别
   - 已成功识别的图片结果不会丢失
6. **历史记录**：历史列表中显示第一张图的缩略图，并标注"共 N 张"
7. **向下兼容**：原有单图识别历史记录正常展示，不受影响

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 前端页面 | [https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/](https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/) | H5 用户端主页面入口 |
| 安卓 APK 下载 | [bini_health_android-v20260408-114940-zqrf.apk](https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/uploads/bini_health_android-v20260408-114940-zqrf.apk) | 安卓客户端安装包，点击下载后安装体验 |
| iOS 端下载 | [iOS Build ios-v20260408-115950-retry1](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-v20260408-115950-retry1) | iOS 客户端安装包，点击前往 GitHub Release 页面下载 |
| 微信小程序下载 | [miniprogram_20260408_114910_809c.zip](https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/uploads/miniprogram_20260408_114910_809c.zip) | 微信小程序代码包，导入微信开发者工具体验 |
