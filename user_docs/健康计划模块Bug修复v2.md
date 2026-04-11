# 健康计划模块 Bug 修复（第二轮）

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 端页面 | [https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/) | H5 端主页面入口 |
| 管理后台 | [https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/admin/](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/admin/) | 管理后台入口 |
| 安卓 APK 下载 | [app_20260411_011933_fce6.apk](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/app_20260411_011933_fce6.apk) | 安卓客户端安装包，点击下载安装体验 |
| iOS 端下载 | [iOS Build ios-v20260411-011940-89b4](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-v20260411-011940-89b4) | iOS 客户端，前往 GitHub Release 下载 |

---

## 功能简介

本次更新修复了健康计划模块的 4 个 Bug，涉及今日待办、自定义计划、健康打卡、用药提醒等核心功能，全面提升了用户体验：

1. **今日待办简化**：移除「健康计划」分组下多余的分类层级，直接平铺显示所有计划任务
2. **删除功能修复**：自定义计划删除后不再残留在列表中
3. **健康打卡编辑修复**：点击编辑按钮后，已有数据能正确加载到表单中
4. **用药提醒编辑修复**：点击编辑按钮后，已有数据能正确加载，不再提示"加载失败"

---

## 本次客户端变更

本次更新涉及以下客户端平台的代码改动，请下载最新版本体验：

| 平台 | 变更说明 | 新版本下载 |
|------|----------|------------|
| 微信小程序 | 移除今日待办 sub_groups 层级；修复打卡编辑字段映射；修复用药提醒编辑字段映射 | [miniprogram_20260411_012037_801f.zip](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/miniprogram_20260411_012037_801f.zip) |
| 安卓端 | 移除今日待办和首页的 sub_groups 分类层级，健康计划任务平铺显示 | [app_20260411_011933_fce6.apk](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/app_20260411_011933_fce6.apk) |
| iOS 端 | 移除今日待办和首页的 sub_groups 分类层级，健康计划任务平铺显示 | [iOS Build ios-v20260411-011940-89b4](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-v20260411-011940-89b4) |

> ⚠️ 以上平台的代码在本次更新中有改动，请务必下载最新版本。未列出的平台表示本次无变更，可继续使用当前版本。

---

## 使用说明

### Bug 1 修复验证：今日待办简化

1. 登录后进入首页，查看「今日待办」区域
2. 找到「健康计划」分组
3. **预期效果**：健康计划分组下直接平铺显示所有计划任务，不再按"运动类"、"饮食类"等分类拆分子分组
4. 所有计划任务以统一的列表形式展示，层级清晰

### Bug 2 修复验证：自定义计划删除

1. 进入「健康计划」→「自定义计划」
2. 在计划列表中点击某个计划的删除按钮（🗑️ 图标）
3. 确认删除
4. **预期效果**：删除成功后，该计划立即从列表中消失
5. 刷新页面后，被删除的计划不再出现

### Bug 3 修复验证：健康打卡编辑

1. 进入「健康计划」→「健康打卡」
2. 在打卡项列表中点击某条记录的编辑按钮（✏️ 图标）
3. **预期效果**：进入编辑页面后，打卡项的名称、提醒时间、重复频率等已有数据自动填充到表单中
4. 修改数据后点击保存，修改成功

### Bug 4 修复验证：用药提醒编辑

1. 进入「健康计划」→「用药提醒」
2. 在用药提醒列表中点击某条记录的编辑按钮（✏️ 图标）
3. **预期效果**：进入编辑页面后，药品名称、剂量、用药时段、提醒时间等已有数据自动填充到表单中
4. 修改数据后点击保存，修改成功

---

## 微信小程序体验

### 下载小程序代码

点击以下链接下载微信小程序代码压缩包：

> 📦 下载地址：[miniprogram_20260411_012037_801f.zip](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/miniprogram_20260411_012037_801f.zip)

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

> 📱 下载地址：[app_20260411_011933_fce6.apk](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/app_20260411_011933_fce6.apk)

### 安装与体验步骤

1. **下载 APK**：点击上方链接，将 APK 安装包下载到手机（或先下载到电脑再传输到手机）
2. **允许安装**：如果手机提示「不允许安装未知来源应用」，请在手机设置中开启「允许安装未知来源应用」（不同手机品牌设置路径可能不同，一般在「设置 → 安全」或「设置 → 隐私」中）
3. **安装应用**：点击下载的 APK 文件，按照提示完成安装
4. **打开体验**：安装完成后，在手机桌面找到应用图标，点击打开即可体验

---

## iOS 端体验

### 下载安装包

点击以下链接前往 GitHub Release 页面下载 iOS 客户端安装包：

> 🍎 GitHub Release 页面：[iOS Build ios-v20260411-011940-89b4](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-v20260411-011940-89b4)
>
> 📦 IPA 直接下载：[bini_health_ios.ipa](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/download/ios-v20260411-011940-89b4/bini_health_ios.ipa)

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

1. **全端一致**：本次修复覆盖了 H5 端、微信小程序、Flutter App（安卓+iOS）和管理后台，所有端的行为保持一致
2. **数据兼容**：已删除的自定义计划不会被恢复，修复仅影响列表展示
3. **编辑功能**：健康打卡和用药提醒的编辑功能已恢复正常，请重新下载最新版本客户端体验
4. **今日待办**：健康计划分组不再显示"运动类"、"饮食类"等子分类，所有任务直接平铺展示

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 端页面 | [https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/) | H5 端主页面入口 |
| 管理后台 | [https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/admin/](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/admin/) | 管理后台入口 |
| 安卓 APK 下载 | [app_20260411_011933_fce6.apk](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/app_20260411_011933_fce6.apk) | 安卓客户端安装包，点击下载安装体验 |
| iOS 端下载 | [iOS Build ios-v20260411-011940-89b4](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-v20260411-011940-89b4) | iOS 客户端，前往 GitHub Release 下载 |

## 微信小程序体验

### 下载小程序代码

点击以下链接下载微信小程序代码压缩包：

> 📦 下载地址：[miniprogram_20260411_012037_801f.zip](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/miniprogram_20260411_012037_801f.zip)

### 体验步骤

1. **下载压缩包**：点击上方链接，将 zip 压缩包下载到本地电脑
2. **解压文件**：将下载的 zip 文件解压到任意目录
3. **打开微信开发者工具**：启动开发者工具，使用微信扫码登录
4. **导入项目**：点击「导入项目」，选择解压后的文件夹，填入 AppID 或选择「测试号」
5. **预览体验**：导入成功后即可在模拟器中操作

## 安卓端体验

> 📱 下载地址：[app_20260411_011933_fce6.apk](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/app_20260411_011933_fce6.apk)

## iOS 端体验

> 🍎 GitHub Release：[iOS Build ios-v20260411-011940-89b4](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-v20260411-011940-89b4)
>
> 📦 IPA 直接下载：[bini_health_ios.ipa](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/download/ios-v20260411-011940-89b4/bini_health_ios.ipa)
