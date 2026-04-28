# 服务页分类栏固定与二级Tab联动优化 — 用户体验使用手册

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> 所有链接均使用宿主机 Nginx 代理端口（80），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 前端页面 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 项目主页面入口（经 Nginx 代理，端口 80） |
| 安卓 APK 下载 | [bini_health_android-v20260428-143835-94d9.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/bini_health_android-v20260428-143835-94d9.apk) | 安卓客户端安装包，点击下载后安装体验 |
| iOS 端下载 | [iOS Build ios-v20260428-143818-b06d](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-v20260428-143818-b06d) | iOS 客户端安装包，前往 GitHub Release 页面下载 |
| 小程序 zip 下载 | [miniprogram_20260428_143751_4082.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_20260428_143751_4082.zip) | 微信小程序代码包，下载后导入开发者工具体验 |

## 功能简介

本次更新对用户端「首页 → 服务」页面进行了全面的交互优化，覆盖 **H5 网页端**、**Flutter APP 端（iOS / Android）** 和 **微信小程序端** 三端，主要提升包括：

1. **左侧分类栏固定**：浏览商品时左侧一级分类栏始终可见，任意位置一键切换分类
2. **二级子类Tab固定**：二级子类横向Tab始终固定在商品列表上方，滑动商品时不会消失
3. **Tab与商品滚动联动**：滑动商品列表时Tab自动高亮当前所在子类，点击Tab自动定位到对应商品区域
4. **履约角标位置优化**：到店/快递/虚拟角标从商品名称右侧移至价格行右侧，释放名称显示空间
5. **商品名称完整显示**：取消名称单行截断限制，服务全称完整展示

## 本次客户端变更

本次更新涉及以下客户端平台的代码改动，请下载最新版本体验：

| 平台 | 变更说明 | 新版本下载 |
|------|----------|------------|
| H5 网页端 | 服务页布局重构：左侧分类栏固定、二级Tab固定+联动高亮、商品名完整显示、履约角标下移 | [H5 前端页面](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) |
| 微信小程序 | 服务页布局重构：左侧分类栏+右侧Tab联动布局、履约角标、商品分组渲染 | [miniprogram_20260428_143751_4082.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_20260428_143751_4082.zip) |
| 安卓端 | 服务页布局重构：左侧分类栏+右侧Tab联动布局、履约角标、商品名完整显示 | [bini_health_android-v20260428-143835-94d9.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/bini_health_android-v20260428-143835-94d9.apk) |
| iOS 端 | 服务页布局重构：左侧分类栏+右侧Tab联动布局、履约角标、商品名完整显示 | [iOS Build ios-v20260428-143818-b06d](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-v20260428-143818-b06d) |

> 以上平台的代码在本次更新中有改动，请务必下载最新版本。

## 使用说明

### 1. 打开服务页

- **H5 端**：在浏览器中访问 [项目主页](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/)，点击底部导航栏的「服务」Tab
- **APP 端**：打开 bini-health APP，点击底部导航栏的「服务」
- **小程序端**：在微信开发者工具中导入小程序代码，点击底部导航栏的「服务」

### 2. 使用左侧分类栏切换分类

进入服务页后，您会看到左侧有一列分类菜单（如推荐、美容、养生、居家等）：

- 点击任意分类名称，右侧内容区立即切换到对应分类的商品
- 当前选中的分类会以**绿色文字 + 左侧绿色竖线**标识
- 如果分类数量较多，左侧栏可以**独立上下滑动**查看全部分类
- 无论右侧商品滚动到哪里，左侧分类栏**始终固定在屏幕左侧**

### 3. 使用二级子类Tab筛选

当某个一级分类下有子分类时，右侧顶部会显示横向的子类Tab：

- 默认显示「全部」，展示该分类下所有子类的商品
- 点击某个子类Tab（如"推拿"、"艾灸"），商品列表会**平滑滚动**到该子类的商品区域
- 如果子类较多（横向放不下），可以**左右滑动**Tab栏查看更多子类
- Tab栏底部有**轻微阴影**，视觉上与下方滚动的商品列表区分

### 4. 滚动联动自动切换

当您上下滑动商品列表时：

- 二级子类Tab会**自动高亮**当前正在浏览的子类
- 如果高亮的Tab已经滑出可视范围，Tab栏会**自动横向滚动**将其带入可视区域
- Tab的高亮切换有**平滑过渡动效**，不会生硬跳变

### 5. 查看商品信息

商品卡片展示了完整的服务信息：

- **商品名称**：完整显示，不再被截断，即使名称很长也会完整展示多行
- **卖点描述**：名称下方灰色小字展示
- **价格**：绿色醒目显示（多规格商品显示「¥最低价起」）
- **履约角标**：在价格行右侧显示到店服务（橙色）、快递配送（蓝色）、虚拟商品（紫色）等标签

### 6. 搜索商品

在页面顶部的搜索框中输入关键词，即可全分类搜索商品。搜索功能与之前保持一致，不受本次布局优化影响。

## 微信小程序体验

### 下载小程序代码

点击以下链接下载微信小程序代码压缩包：

> 下载地址：[miniprogram_20260428_143751_4082.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_20260428_143751_4082.zip)

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

## 安卓端体验

### 下载安装包

点击以下链接下载安卓客户端安装包：

> 下载地址：[bini_health_android-v20260428-143835-94d9.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/bini_health_android-v20260428-143835-94d9.apk)

### 安装与体验步骤

1. **下载 APK**：点击上方链接，将 APK 安装包下载到手机（或先下载到电脑再传输到手机）
2. **允许安装**：如果手机提示「不允许安装未知来源应用」，请在手机设置中开启「允许安装未知来源应用」（不同手机品牌设置路径可能不同，一般在「设置 → 安全」或「设置 → 隐私」中）
3. **安装应用**：点击下载的 APK 文件，按照提示完成安装
4. **打开体验**：安装完成后，在手机桌面找到应用图标，点击打开即可体验

## iOS 端体验

### 下载安装包

点击以下链接前往 GitHub Release 页面下载 iOS 客户端安装包：

> GitHub Release 页面：[iOS Build ios-v20260428-143818-b06d](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-v20260428-143818-b06d)
>
> IPA 直接下载：[bini_health_ios.ipa](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/download/ios-v20260428-143818-b06d/bini_health_ios.ipa)

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

## 注意事项

1. **三端一致体验**：H5、APP、小程序三端的服务页布局和交互效果保持一致
2. **搜索功能不受影响**：搜索页面的商品卡片布局暂不调整，保持原有样式
3. **管理后台不涉及**：本次为用户端优化，管理后台页面无任何改动
4. **后端 API 不变**：本次为纯前端 UI 调整，不涉及数据结构和后端 API 变更
5. **分类数据来源不变**：一级分类和二级子类数据均从后端 API 获取，与之前保持一致

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> 所有链接均使用宿主机 Nginx 代理端口（80），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 前端页面 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 项目主页面入口（经 Nginx 代理，端口 80） |
| 安卓 APK 下载 | [bini_health_android-v20260428-143835-94d9.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/bini_health_android-v20260428-143835-94d9.apk) | 安卓客户端安装包，点击下载后安装体验 |
| iOS 端下载 | [iOS Build ios-v20260428-143818-b06d](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-v20260428-143818-b06d) | iOS 客户端安装包，前往 GitHub Release 页面下载 |
| 小程序 zip 下载 | [miniprogram_20260428_143751_4082.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_20260428_143751_4082.zip) | 微信小程序代码包，下载后导入开发者工具体验 |
