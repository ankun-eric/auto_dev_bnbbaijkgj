# AI健康咨询改版 — 用户体验使用手册

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5用户端 | [https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/) | H5移动端入口 |
| 管理后台 | [https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/admin/](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/admin/) | 管理后台入口 |
| 安卓APK下载 | [bini_health_android-v20260406-200031-4d73.apk](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/uploads/bini_health_android-v20260406-200031-4d73.apk) | 安卓客户端安装包 |
| iOS端下载 | [iOS Build ios-v20260406-200126-d0b4](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-v20260406-200126-d0b4) | iOS客户端安装包（GitHub Release） |

---

## 功能简介

本次更新将原"AI问诊"模块全面升级为"AI健康咨询"，明确产品定位为健康咨询服务，同时新增后台AI配置中心、敏感词过滤、免责提示等合规保障功能。主要改动包括：

1. **全端文案升级**：所有端（H5、小程序、Flutter App、管理后台）中的"AI问诊"统一替换为"AI健康咨询"
2. **会话类型名称优化**：症状分析→健康自查、中医→中医养生、用药查询→用药参考
3. **AI回复风格调整**：AI回复去除诊断性表述，每条回复末尾自动附加免责提示
4. **管理后台新增AI配置中心**：支持敏感词管理、提示词配置、免责提示配置
5. **历史聊天记录清理**：所有旧AI问诊聊天记录已物理删除

---

## 本次客户端变更

本次更新涉及以下客户端平台的代码改动，请下载最新版本体验：

| 平台 | 变更说明 | 新版本下载 |
|------|----------|------------|
| 微信小程序 | 全面替换"AI问诊"为"AI健康咨询"，更新会话类型名称，新增免责提示渲染 | [miniprogram_20260406_195919_vhob.zip](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/uploads/miniprogram_20260406_195919_vhob.zip) |
| 安卓端 | 全面替换"AI问诊"为"AI健康咨询"，更新会话类型，新增免责提示渲染 | [bini_health_android-v20260406-200031-4d73.apk](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/uploads/bini_health_android-v20260406-200031-4d73.apk) |
| iOS端 | 全面替换"AI问诊"为"AI健康咨询"，更新会话类型，新增免责提示渲染 | [iOS Build ios-v20260406-200126-d0b4](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-v20260406-200126-d0b4) |

> ⚠️ 以上平台的代码在本次更新中有改动，请务必下载最新版本。未列出的平台表示本次无变更，可继续使用当前版本。

---

## 使用说明

### 一、用户端（H5/小程序/Flutter App）

#### 1. AI健康咨询入口

- 打开应用后，在底部导航栏点击 **"AI健康咨询"**（原"AI问诊"）
- 进入AI健康咨询首页，可看到四种咨询类型

#### 2. 选择咨询类型

| 类型 | 说明 |
|------|------|
| 健康问答 | AI健康顾问在线解答各类健康问题 |
| 健康自查 | 智能健康自查参考，描述症状获取分析 |
| 中医养生 | 中医养生体质调理建议 |
| 用药参考 | 用药参考与注意事项查询 |

#### 3. 开始对话

- 点击任一咨询类型，即可进入AI对话界面
- 在输入框中描述您的健康问题，AI健康顾问将为您提供专业参考建议
- **每条AI回复末尾会附带免责提示**（灰色小字），提醒您仅供参考

#### 4. 免责提示说明

AI回复末尾会自动附加对应类型的免责提示，例如：
- 健康问答："以上内容仅供健康参考，不构成任何医疗诊断或治疗建议，如有不适请及时就医。"
- 中医养生："以上中医养生建议仅供参考，个人体质不同，建议在专业中医师指导下调理。"

这些提示以虚线分隔、灰色斜体小字显示，与正文内容视觉上有明确区分。

---

### 二、管理后台

#### 1. 登录管理后台

访问 [管理后台](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/admin/)，使用管理员账号登录。

#### 2. AI配置中心

在左侧菜单中找到 **"AI配置中心"**，包含三个子功能：

##### 2.1 敏感词管理

- **功能**：管理AI回复中需要被过滤替换的敏感词
- **操作步骤**：
  1. 点击"AI配置中心" → "敏感词管理"
  2. 查看已有的敏感词列表（支持关键字搜索和分页）
  3. 点击"新增"按钮添加新的敏感词替换规则
  4. 在弹窗中填写"敏感词"和"替换词"，点击确定保存
  5. 可对已有规则进行编辑或删除操作

- **效果**：AI回复中出现敏感词时，系统会自动替换为对应的替换词后再展示给用户

##### 2.2 提示词配置

- **功能**：按会话类型分别配置AI的系统提示词（System Prompt）
- **操作步骤**：
  1. 点击"AI配置中心" → "提示词配置"
  2. 页面顶部有5个Tab标签：健康问答、健康自查、中医养生、用药参考、在线客服
  3. 切换到需要修改的类型Tab
  4. 在文本编辑器中修改系统提示词内容
  5. 点击"保存"按钮，修改立即生效（无需重启服务）

- **注意**：提示词决定了AI回复的风格和角色定位，修改时请确保符合健康咨询定位

##### 2.3 免责提示配置

- **功能**：按会话类型配置每条AI回复末尾的免责提示文案
- **操作步骤**：
  1. 点击"AI配置中心" → "免责提示配置"
  2. 切换到需要修改的类型Tab
  3. 修改免责提示文案内容
  4. 通过"是否启用"开关控制该类型是否附加免责提示
  5. 点击"保存"按钮，修改立即生效

- **默认配置**："在线客服"类型默认关闭免责提示，其他类型默认开启

---

## 微信小程序体验

### 下载小程序代码

点击以下链接下载微信小程序代码压缩包：

> 📦 下载地址：[miniprogram_20260406_195919_vhob.zip](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/uploads/miniprogram_20260406_195919_vhob.zip)

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

> 📱 下载地址：[bini_health_android-v20260406-200031-4d73.apk](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/uploads/bini_health_android-v20260406-200031-4d73.apk)

### 安装与体验步骤

1. **下载 APK**：点击上方链接，将 APK 安装包下载到手机（或先下载到电脑再传输到手机）
2. **允许安装**：如果手机提示「不允许安装未知来源应用」，请在手机设置中开启「允许安装未知来源应用」（不同手机品牌设置路径可能不同，一般在「设置 → 安全」或「设置 → 隐私」中）
3. **安装应用**：点击下载的 APK 文件，按照提示完成安装
4. **打开体验**：安装完成后，在手机桌面找到应用图标，点击打开即可体验

---

## iOS端体验

### 下载安装包

点击以下链接前往 GitHub Release 页面下载 iOS 客户端安装包：

> 🍎 GitHub Release 页面：[iOS Build ios-v20260406-200126-d0b4](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-v20260406-200126-d0b4)
>
> 📦 IPA 直接下载：[bini_health_ios-v20260406-200126-d0b4.ipa](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/download/ios-v20260406-200126-d0b4/bini_health_ios-v20260406-200126-d0b4.ipa)

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

1. **AI健康咨询仅供参考**：所有AI回复内容均为健康参考信息，不构成医疗诊断或治疗建议。如有身体不适，请及时就医。
2. **历史记录已清空**：本次更新已清除所有旧的AI问诊聊天记录，用户需重新开始对话。
3. **管理员权限**：AI配置中心（敏感词管理、提示词配置、免责提示配置）仅管理员可访问。
4. **实时生效**：管理员修改提示词或免责提示后，无需重启服务即可立即生效。
5. **敏感词过滤**：系统会自动过滤AI回复中的敏感词，所有端统一生效。

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5用户端 | [https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/) | H5移动端入口 |
| 管理后台 | [https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/admin/](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/admin/) | 管理后台入口 |
| 安卓APK下载 | [bini_health_android-v20260406-200031-4d73.apk](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/uploads/bini_health_android-v20260406-200031-4d73.apk) | 安卓客户端安装包 |
| iOS端下载 | [iOS Build ios-v20260406-200126-d0b4](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-v20260406-200126-d0b4) | iOS客户端安装包（GitHub Release） |
