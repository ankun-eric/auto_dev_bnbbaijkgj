# AI 咨询配置改造 — 报告解读独立成型 + Prompt 模板分组重构 + 下拉为空 Bug 修复

> 版本：v1.0  
> 发布日期：2026-05-14  
> 适用项目：bini-health

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| 前端 H5 主页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 项目主页面入口（经 Nginx 代理） |
| 管理后台 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin) | AI 咨询配置中心入口 |
| 微信小程序下载 | [miniprogram_promptcfg_20260514_222237_0362.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_promptcfg_20260514_222237_0362.zip) | 解压后导入微信开发者工具体验 |
| 安卓 APK 下载 | [app_promptcfg_20260514_222647_f9f6.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/app_promptcfg_20260514_222647_f9f6.apk) | 安卓客户端安装包，点击下载后安装体验 |
| iOS 端下载 | [iOS Build ios-promptcfg-v1778768517-c3d0](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-promptcfg-v1778768517-c3d0) | 点击前往 GitHub Release 页面下载 IPA |

---

## 功能简介

本次更新对【AI 咨询配置】做了一次完整重构，主要解决三个核心问题：

1. **修复了管理后台「关联 Prompt 模板」下拉永远为空的 Bug**，让运营终于能正常给按钮绑定 Prompt
2. **新增了「报告解读」按钮类型**，把"体检报告解读"从原本混在「拍照上传」「文件上传」里的状态独立出来，专门承接体检报告 OCR + AI 解读的业务流
3. **重构了 Prompt 模板配置页**，按业务分组（报告解读 / 药品识别 / 用药对话）展示，已下线的旧类型从界面完全隐藏

对终端用户的可见变化：H5 / 小程序 / App 中如果运营配置了「🩺 报告解读」按钮，点击即可拍照或选文件上传体检报告，进入对话化解读流程；解读质量将比原通用「拍照上传」更精准（背后走专属的 OCR + 指标提取 + 档案关联流程）。

---

## 本次客户端变更

本次更新涉及以下终端的代码改动，请下载最新版本体验：

| 终端 | 变更说明 | 新版本下载 |
|------|----------|------------|
| 微信小程序 | 新增 `report_interpret` 按钮类型渲染分支：点击「报告解读」按钮唤起相册/拍照，上传成功后自动调用 `/api/report-interpret/start` 跳转对话页 | [miniprogram_promptcfg_20260514_222237_0362.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_promptcfg_20260514_222237_0362.zip) |
| 安卓端 | Flutter 应用增加 `report_interpret` 按钮分支，复用拍照上传交互；后台同步配置「报告解读」按钮后客户端自动可见 | [app_promptcfg_20260514_222647_f9f6.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/app_promptcfg_20260514_222647_f9f6.apk) |
| iOS 端 | 同安卓，Flutter 跨平台共享代码改动覆盖 iOS | [iOS Build ios-promptcfg-v1778768517-c3d0](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-promptcfg-v1778768517-c3d0) |

> ⚠️ 以上终端的代码在本次更新中有改动，请务必下载最新版本。未列出的终端（如 H5）通过浏览器访问即可自动拿到最新版本。

---

## 管理员使用说明

### 1. 创建一个「报告解读」功能按钮

1. 登录【管理后台】，进入【AI咨询配置 → 功能按钮管理】
2. 点击右上角【新增按钮】
3. 表单中：
   - **按钮名称**：例如「体检报告解读」
   - **按钮图标**：点击「选择 Emoji」按钮，推荐选 🩺 或 📊
   - **按钮类型**：下拉选择 **「🩺 报告解读（体检报告专属）」** ← 这是本期新增的类型
   - **关联 Prompt 模板**：下拉自动只展示 2 个可绑定选项：
     - 体检报告解读（对话式）
     - 报告对比（对话式）
4. 填写【自动用户消息】、【卡片标题】等字段后，点击【确定】保存即可

> 💡 **联动过滤说明**：选择不同的「按钮类型」后，下方「关联 Prompt 模板」下拉会**自动**只展示该按钮类型允许绑定的模板。例如选「拍照识药」只会看到药品识别组的 3 个模板；选「报告解读」只会看到报告解读组的 2 个模板。**不会再出现绑错的情况**。

### 2. 查看 / 修改 Prompt 模板

1. 进入【AI咨询配置 → Prompt 模板配置】
2. 顶部出现 4 个**业务分组 Tab**：
   - 🩺 报告解读（2 条）
   - 🔍 药品识别（3 条）
   - 💬 用药对话（3 条）
   - 📦 通用素材（保留位）
3. 点击任一分组，下方左侧二级列表会展示该分组下的具体 Prompt 类型；
4. 选中某条后右侧出现编辑区，可修改 Prompt 内容、点击「保存」自动新建版本、或回滚到历史版本

### 3. 预览效果

点击编辑区右上方的【👁 预览效果】按钮，弹窗的「示例输入」会**自动填入**该 Prompt 在数据库中预设的示例文本（例如「示例：体检报告全文…」）。如果数据库没配，则回退到前端硬编码示例。

### 4. 已下线类型的处理

- 原页面里两条标了"已下线"的类型（旧版报告解读 `checkup_report`、趋势解读 `trend_analysis`）已经**从界面完全消失**，不会再混淆视听
- 但是后端数据库依然保留它们的配置，老数据不会被删，所以历史 Prompt 内容随时可以查回来（通过 API 加 `?include_offline=1` 参数）

---

## 终端用户使用说明

### H5 / 小程序 / App 的体验流程

当管理员配置了「🩺 报告解读」按钮后，终端用户进入 AI 对话首页可看到该按钮。点击该按钮：

1. 系统弹出图片选择菜单（拍照 / 相册）
2. 选好体检报告照片后，自动上传到服务器
3. 上传成功后，**自动跳转到 AI 对话页**
4. 对话页 AI 会自动开始解读您的体检报告（OCR + 关键指标提取 + 健康建议）
5. 解读完成后您可以**继续追问**任何疑问

> 与原「拍照上传」按钮的区别：原拍照上传只会简单调用通用 AI 识图接口；而「报告解读」按钮走专属流程，能识别更多指标、关联个人健康档案、给出更有针对性的解读。

---

## 微信小程序体验

### 下载小程序代码

点击以下链接下载微信小程序代码压缩包：

> 📦 下载地址：[miniprogram_promptcfg_20260514_222237_0362.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_promptcfg_20260514_222237_0362.zip)

### 体验步骤

1. **下载压缩包**：点击上方链接，将 zip 压缩包下载到本地电脑
2. **解压文件**：将下载的 zip 文件解压到任意目录（记住解压后的文件夹路径）
3. **下载微信开发者工具**：如尚未安装，请前往 [微信开发者工具官方下载页面](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html) 下载并安装
4. **打开微信开发者工具**：启动开发者工具，使用微信扫码登录
5. **导入项目**：
   - 点击开发者工具首页的「导入项目」（或「+」号）
   - 在「目录」栏点击浏览，选择第 2 步解压后的文件夹
   - 「AppID」栏可选择「测试号」
   - 点击「导入」按钮
6. **预览体验**：导入成功后，开发者工具会自动编译并在模拟器中展示小程序界面

---

## 安卓端体验

### 下载安装包

点击以下链接下载安卓客户端安装包：

> 📱 下载地址：[app_promptcfg_20260514_222647_f9f6.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/app_promptcfg_20260514_222647_f9f6.apk)

### 安装与体验步骤

1. **下载 APK**：点击上方链接，将 APK 安装包下载到手机（或先下载到电脑再传输到手机）
2. **允许安装**：如果手机提示「不允许安装未知来源应用」，请在手机设置中开启「允许安装未知来源应用」（不同手机品牌设置路径可能不同，一般在「设置 → 安全」或「设置 → 隐私」中）
3. **安装应用**：点击下载的 APK 文件，按照提示完成安装
4. **打开体验**：安装完成后，在手机桌面找到应用图标，点击打开即可体验

---

## iOS 端体验

### 下载安装包

点击以下链接前往 GitHub Release 页面下载 iOS 客户端安装包：

> 🍎 GitHub Release 页面：[iOS Build ios-promptcfg-v1778768517-c3d0](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-promptcfg-v1778768517-c3d0)
>
> 📦 IPA 直接下载：[bini_health_ios.ipa](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/download/ios-promptcfg-v1778768517-c3d0/bini_health_ios.ipa)

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

## 注意事项

1. **历史按钮的自动迁移**：升级时后端会自动把所有"已绑定报告类 Prompt 的 `photo_upload`/`file_upload` 按钮"迁移到新的 `report_interpret` 类型；同时备份原表为 `function_buttons_backup_pcv1`。管理员**无需手动调整**。
2. **新建按钮时下拉不可能再为空**：Prompt 下拉数据源已经修复，且按按钮类型联动过滤；如果还是出现空状态，会有「去 Prompt 配置中心 →」的快捷跳转按钮帮你定位问题。
3. **已下线类型不可见但数据未删**：旧的 `checkup_report` / `trend_analysis` 两个类型仅在前端 UI 隐藏；后端 API 加参数 `?include_offline=1` 仍可访问。这保证了历史数据可回溯。
4. **客户端兼容降级**：旧版 H5/小程序/App 未升级时，碰到 `report_interpret` 类型按钮会**按通用「拍照上传」逻辑兜底**，不会出现"按钮点了没反应"的情况。但解读质量会回退到基础水平，建议尽快升级到本次发布版本。
5. **8 种按钮类型**：本次新增后总数从 7 种扩为 8 种，新增的为 `🩺 报告解读`。详见上方"管理员使用说明"。

---

## 服务器自动化测试结果（15/15 PASS）

| # | 测试用例 | 结果 |
|---|----------|------|
| T1 | backend `/api/health` 200 | ✅ |
| T2 | admin / 主页可达 | ✅ |
| T3 | 公开 `/api/function-buttons` 返回数组 | ✅ |
| T4 | backend 启动日志含 `[migrate] prompt_type_config_v1` | ✅ |
| T5 | `prompt_type_config` 表有 10 条数据 | ✅ |
| T6 | `report_interpret` 业务分组下有 2 条在线类型 | ✅ |
| T7 | `_deprecated` 组下有 2 条已下线类型 | ✅ |
| T8 | `function_buttons_backup_pcv1` 备份表已创建 | ✅ |
| T9 | `ALLOWED_BUTTON_TYPES` 含 `report_interpret` | ✅ |
| T10 | `_load_type_configs` 隐藏已下线 + 含 `report_interpret` + 含 `business_group` | ✅ |
| T11 | GroupResponse 含 `business_group` + `allowed_button_types` 字段 | ✅ |
| T12 | `/api/report-interpret/start` 路由已注册 | ✅ |
| T13 | `/api/admin/prompt-type-config` 路由已注册 | ✅ |
| T14 | admin-web function-buttons 源码含 Bug 修复标记（7 处） | ✅ |
| T15 | admin-web prompt-templates 业务分组 Tab 代码已就位（4 处） | ✅ |

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| 前端 H5 主页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 项目主页面入口（经 Nginx 代理） |
| 管理后台 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin) | AI 咨询配置中心入口 |
| 微信小程序下载 | [miniprogram_promptcfg_20260514_222237_0362.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_promptcfg_20260514_222237_0362.zip) | 解压后导入微信开发者工具体验 |
| 安卓 APK 下载 | [app_promptcfg_20260514_222647_f9f6.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/app_promptcfg_20260514_222647_f9f6.apk) | 安卓客户端安装包，点击下载后安装体验 |
| iOS 端下载 | [iOS Build ios-promptcfg-v1778768517-c3d0](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-promptcfg-v1778768517-c3d0) | 点击前往 GitHub Release 页面下载 IPA |
