# 九项 Bug 修复 · 用户体验使用手册

> 本次版本修复了 9 项 Bug，覆盖 PC 端、H5、微信小程序、安卓 APP、iOS APP 共 5 个终端。本手册面向终端用户与体验测试人员。

---

## 访问链接

以下是当前项目的体验链接，点击即可打开。所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 移动端/H5 Web 入口 |
| PC 后台首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/) | PC 后台 Web 入口（本次 Header 改版） |
| PC 登录页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/login](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/login) | PC 登录入口 |
| 我的优惠券 (H5) | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-coupons](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-coupons) | 本次重点 P0 修复 |
| 我的积分 (H5) | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/points](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/points) | 本次重点 P0 修复 |
| 积分商城 (H5) | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/points/mall](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/points/mall) | 本次 UI 合版（可用积分金色） |
| 我的 (H5) | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/profile](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/profile) | 本次 UI 合版（删除字号入口） |
| 小程序 zip 下载 | [miniprogram_9bugs_20260421_004124_041b.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/miniprogram_9bugs_20260421_004124_041b.zip) | 微信小程序最新版压缩包 |
| 安卓 APK 下载 | [bini_health_9bugs_20260421004913_1d69.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/bini_health_9bugs_20260421004913_1d69.apk) | 安卓客户端安装包 |
| iOS IPA 下载 | [iOS Build ios-9bugs-v20260421-004139-3c26](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-9bugs-v20260421-004139-3c26) | iOS 客户端（GitHub Release） |

---

## 功能简介

本次修复覆盖「PC 登录页」「PC 首页顶部 Header」「我的 - 优惠券合计」「我的 - 积分 · 可用积分」「我的首页 · 字体入口」「会员码规则」「积分日常任务 · 完善健康档案链接」「积分日常任务 · 首次下单任务下线」「积分商城 · 可用积分配色」9 项问题。

| 编号 | 模块 | 问题概述 | 修复后效果 |
|------|------|----------|-----------|
| 1 | PC 登录页 | 固定显示"未注册手机号"提示 | 删除永久提示，保留正常校验（经核查该版本登录页无此提示，自动归零） |
| 2 | PC 首页顶部 | 布局杂乱无统一搜索入口 | 方案 A：左 LOGO ｜ 中 大搜索栏（40–50%，圆角） ｜ 右 扫码 + 消息（红点）+ 头像 |
| 3 | 我的 - 优惠券 | 顶部"合计"数值与"可用"Tab 不一致 | 合计=未使用 AND 未过期，两处数值强一致，已用/已过期/未生效均不计入 |
| 4 | 我的 - 积分 | "可用积分"与账户实际不符 | 口径统一为 `累计获得 − 已消耗 − 已过期 − 已冻结`，所有积分展示入口同源 |
| 5 | 我的 - 首页 | 头像下方"字体大小调整"入口干扰 | 删除该入口，间距重新调整，无空白断层；设置内的字体功能继续保留 |
| 6 | 会员码 | 含易混淆字符、规则零散 | 字符集 `23456789ABCDEFGHJKLMNPQRSTUVWXYZ`，长度 6 位，全量刷码脚本 + `member_card_no_old` 回滚字段 |
| 7 | 积分日常任务 | "完善健康档案"跳转错误 | 统一跳转到 `/health-profile`（查看页，页内自带编辑入口），不再区分"已/未完善" |
| 8 | 积分日常任务 | "首次下单"任务已失去意义 | 后端 `enabled=false` + 接口层过滤，列表不再展示；已发放积分保留不回收 |
| 9 | 积分商城首页 | "可用积分"区块配色不统一 | 背景 `#FFF8E1→#FFE7A8` 渐变，数字暗金 `#B8860B` 加粗，文案 `#8C6D1F`，右侧加金色星徽章 |

---

## 本次客户端变更

本次更新涉及以下客户端平台的代码改动，请下载最新版本体验：

| 平台 | 变更说明 | 新版本下载 |
|------|----------|------------|
| 微信小程序 | 我的优惠券合计、可用积分显示、积分商城配色、删除字号入口 | [miniprogram_9bugs_20260421_004124_041b.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/miniprogram_9bugs_20260421_004124_041b.zip) |
| 安卓端 | 同上 + 会员码大写展示、日常任务跳转修正 | [bini_health_9bugs_20260421004913_1d69.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/bini_health_9bugs_20260421004913_1d69.apk) |
| iOS 端 | 同安卓端（Flutter 共享源码） | [iOS Build ios-9bugs-v20260421-004139-3c26](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-9bugs-v20260421-004139-3c26) |

> ⚠️ 以上平台的代码在本次更新中有改动，请务必下载最新版本。PC 端 / H5 直接访问线上地址即可，无需下载。

---

## 使用说明

### 一、PC 端

#### 1. 登录页（Bug #1）
- 访问 [PC 登录页](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/login)
- 页面不再出现"未注册手机号"的常驻灰色提示文字
- 手机号格式校验、密码必填校验等常规校验保持原有行为

#### 2. PC 首页顶部新 Header（Bug #2）
- 登录后进入 [PC 首页](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/)
- 顶栏从左到右依次是：
  1. 左：**折叠按钮 + 圆形渐变 LOGO + "宾尼小康"品牌字**
  2. 中：**大搜索栏**（宽度约屏幕 45%，最大 50%，圆角 24px），提示词为 **"搜索健康商品/服务/文章"**
  3. 右：**扫码图标**（hover 提示"扫一扫"）→ **消息图标**（右上角有红点未读提示，hover 提示"消息"）→ **用户头像**（点击下拉退出登录）
- 将鼠标悬停到扫码/消息图标上可以看到 tooltip 文字；红点出现在消息图标右上角，醒目提示有未读

#### 3. 积分商城（PC 管理）
- PC 后台的"积分商城"是商品与兑换记录管理页，本次**配色变更不适用于后台管理页**，仅 H5/小程序/APP 的 C 端积分商城应用新配色

### 二、H5（移动网页）

#### 1. 我的 - 优惠券（Bug #3）
- 访问 [我的优惠券](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-coupons)
- **顶部"合计 N 张可用"**与**下方 Tab "可用(N)"**的数字完全一致
- 切换到"已使用"/"已过期"Tab，顶部合计数**不受影响**（只反映"可用"）
- 已过期的券、已使用的券、"未到生效时间"的券都**不计入合计**

#### 2. 我的 - 积分（Bug #4）
- 访问 [我的积分](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/points)
- 顶部"可用积分"数值来自后端统一接口 `/api/points/summary.available_points`
- 所有积分展示入口（我的页面的小卡片 / 积分页 / 积分商城 / APP 首页入口）数据同源
- 口径：**累计获得 − 已消耗 − 已过期 − 已冻结**，不会出现"看到 A 数字，兑换时系统说不够" 的错配

#### 3. 我的首页 - 字号入口（Bug #5）
- 访问 [我的页面](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/profile)
- 头像下方原来那一行"🔍 字号偏小？点这里调大"的快捷入口**已删除**
- **字体功能并未去掉**，用户仍可通过"设置菜单 → 字体大小"调整，系统默认字号逻辑未变
- 删除后上下卡片间距重新校准，无空白断层

#### 4. 积分商城 - 可用积分区块（Bug #9）
- 访问 [积分商城](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/points/mall)
- 顶部卡片背景：淡金渐变 `#FFF8E1 → #FFE7A8`（左上 → 右下）
- 积分数字：暗金 `#B8860B`，加粗，字号比普通正文大
- "可用积分"文字：`#8C6D1F`（金棕）
- 卡片右侧有金色星形徽章 ⭐，烘托会员尊贵感
- "积分记录"等跳转按钮交互**未变**

#### 5. 任务 - 完善健康档案（Bug #7）
- 在[我的积分](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/points)页的"日常任务"列表里点击"完善健康档案"
- 统一跳转到 [健康档案查看页](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile)（已完善/未完善一视同仁，页内提供编辑入口）

#### 6. 任务 - 首次下单（Bug #8）
- 日常任务列表**不再展示"首次下单"任务**
- 历史上已经通过首次下单领取的积分**不会被回收**

### 三、微信小程序

#### 体验步骤见下方「微信小程序体验」章节。功能体验等同于 H5：
- 我的 - 优惠券：顶部"合计 N 张可用" 条 + Tab `可用(N)` 同步一致
- 我的 - 积分：顶部"我的可用积分"数字来自 `/api/points/summary`，无硬编码
- 积分商城：可用积分金色配色 + 右侧 ⭐ 徽章
- 我的首页：删除了"字号偏小？点这里调大"入口

### 四、安卓 / iOS APP（Flutter）

#### 同 H5 的修复均已落地，此外还包括：
- **会员码展示大写化**：在"我的 → 会员卡"页的 QR token 文本展示统一为大写
- 积分商城首页"可用积分"卡片：背景金色渐变 + 数字暗金 + 右侧金色 `stars_rounded` 图标
- 日常任务跳转映射：`/health-profile` 直达健康档案页，`first_order` 任务不展示

---

## 微信小程序体验

### 下载小程序代码

点击以下链接下载微信小程序代码压缩包：

> 📦 下载地址：[miniprogram_9bugs_20260421_004124_041b.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/miniprogram_9bugs_20260421_004124_041b.zip)

### 体验步骤

1. **下载压缩包**：点击上方链接，将 zip 压缩包下载到本地电脑
2. **解压文件**：将 zip 文件解压到任意目录（记住解压后的文件夹路径，根目录应含 `app.json` `app.js` `project.config.json`）
3. **下载微信开发者工具**：如未安装，请前往 [微信开发者工具官方下载页面](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html) 下载并安装
4. **打开微信开发者工具**：启动开发者工具，使用微信扫码登录
5. **导入项目**：
   - 点击首页的「导入项目」（或「+」号）
   - 在「目录」栏浏览，选择第 2 步解压后的文件夹
   - 「AppID」栏可填入项目的 AppID 或选择「测试号」
   - 点击「导入」按钮
6. **预览体验**：导入成功后，开发者工具会自动编译并在模拟器中展示小程序界面

---

## 安卓端体验

### 下载安装包

点击以下链接下载安卓客户端安装包：

> 📱 下载地址：[bini_health_9bugs_20260421004913_1d69.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/bini_health_9bugs_20260421004913_1d69.apk)

### 安装与体验步骤

1. **下载 APK**：点击上方链接，将 APK 安装包下载到手机（或先下载到电脑再传输到手机）
2. **允许安装**：如果手机提示「不允许安装未知来源应用」，请在手机设置中开启「允许安装未知来源应用」（不同手机品牌设置路径不同，一般在「设置 → 安全」或「设置 → 应用管理」中）
3. **安装应用**：点击下载的 APK 文件，按提示完成安装
4. **打开体验**：安装完成后，在手机桌面找到"宾尼小康"图标点击打开

---

## iOS 端体验

### 下载安装包

点击以下链接前往 GitHub Release 页面下载 iOS 客户端安装包：

> 🍎 GitHub Release 页面：[iOS Build ios-9bugs-v20260421-004139-3c26](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-9bugs-v20260421-004139-3c26)
>
> 📦 IPA 直接下载：[bini_health_ios.ipa](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/download/ios-9bugs-v20260421-004139-3c26/bini_health_ios.ipa)

### 安装与体验步骤

1. **下载 IPA 文件**：点击上方「IPA 直接下载」链接，将 IPA 安装包下载到电脑
2. **安装到设备**（选择以下任一方式）：
   - **方式一：使用 AltStore / Sideloadly 侧载**
     - 在电脑上安装 [AltStore](https://altstore.io/) 或 [Sideloadly](https://sideloadly.io/)
     - 将 iPhone/iPad 通过数据线连接到电脑
     - 使用工具将下载的 IPA 文件安装到设备
   - **方式二：Apple Configurator（需 Mac）**
     - 在 Mac 上打开 Apple Configurator 2
     - 连接 iPhone/iPad，拖拽 IPA 文件到设备上安装
   - **方式三：TrollStore（iOS 14.0 – 16.x 越狱/半越狱设备）**
3. **信任开发者证书**（如安装后无法打开）：前往「设置 → 通用 → VPN 与设备管理」，找到对应的开发者证书并点击「信任」
4. **打开体验**：安装完成后在手机桌面找到应用图标点击打开

> ⚠️ 本次 IPA 为**未签名构建**（无 Apple Developer 账号代签），仅供内部体验测试，无法上架 App Store。首次运行可能需要在设备上信任开发者证书。

---

## 注意事项

1. **会员码全量刷码**：Bug #6 的数据库刷码脚本 (`backend/scripts/reissue_member_codes.py`) 尚未在生产库执行，建议在**凌晨低峰期**运行；脚本内置数据库整表备份（`users_backup_YYYYMMDD`）与 `member_card_no_old` 兜底字段，30 天内可回滚
2. **积分对账脚本仅出报表**：`backend/scripts/audit_points.py` 扫描用户余额与流水差异并输出 CSV，**严禁自动修正**，需由运营人工确认后批量处理
3. **"已过期/已冻结"积分占位**：目前 `PointsRecord` 表没有 `expire` 枚举值和 `status` 字段，`expired / frozen` 两项临时为 0；规则与计算层已就位，一旦业务上线相关机制，无需改代码即可生效
4. **iOS 安装限制**：未签名 IPA 需要侧载工具，且 Apple 证书有效期有限（普通 Apple ID 证书 7 天、付费开发者证书 1 年）；过期后需重新侧载
5. **APK 国内来源**：APK 从 GitHub Release 走镜像上传，非 GitHub 原链接。如下载失败可尝试刷新、换网络
6. **任务"首次下单"下线后的恢复路径**：后端配置保留 `enabled=false`，随时可上线；历史数据未触动

---

## 访问链接

以下是当前项目的体验链接，点击即可打开。所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 移动端/H5 Web 入口 |
| PC 后台首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/) | PC 后台 Web 入口（本次 Header 改版） |
| PC 登录页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/login](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/login) | PC 登录入口 |
| 我的优惠券 (H5) | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-coupons](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-coupons) | 本次重点 P0 修复 |
| 我的积分 (H5) | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/points](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/points) | 本次重点 P0 修复 |
| 积分商城 (H5) | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/points/mall](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/points/mall) | 本次 UI 合版（可用积分金色） |
| 我的 (H5) | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/profile](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/profile) | 本次 UI 合版（删除字号入口） |
| 小程序 zip 下载 | [miniprogram_9bugs_20260421_004124_041b.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/miniprogram_9bugs_20260421_004124_041b.zip) | 微信小程序最新版压缩包 |
| 安卓 APK 下载 | [bini_health_9bugs_20260421004913_1d69.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/bini_health_9bugs_20260421004913_1d69.apk) | 安卓客户端安装包 |
| iOS IPA 下载 | [iOS Build ios-9bugs-v20260421-004139-3c26](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-9bugs-v20260421-004139-3c26) | iOS 客户端（GitHub Release） |

---

## 微信小程序体验

### 下载小程序代码

点击以下链接下载微信小程序代码压缩包：

> 📦 下载地址：[miniprogram_9bugs_20260421_004124_041b.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/miniprogram_9bugs_20260421_004124_041b.zip)

### 体验步骤

1. 下载压缩包并解压；根目录包含 `app.json`
2. 打开微信开发者工具 → 导入项目 → 选择解压后的目录
3. 选择项目 AppID 或使用测试号，导入后在模拟器中预览

---

## 安卓端体验

### 下载安装包

> 📱 下载地址：[bini_health_9bugs_20260421004913_1d69.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/bini_health_9bugs_20260421004913_1d69.apk)

### 安装步骤

1. 下载 APK 到手机
2. 允许安装未知来源应用
3. 点击安装 → 打开应用

---

## iOS 端体验

### 下载安装包

> 🍎 GitHub Release 页面：[iOS Build ios-9bugs-v20260421-004139-3c26](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-9bugs-v20260421-004139-3c26)
>
> 📦 IPA 直接下载：[bini_health_ios.ipa](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/download/ios-9bugs-v20260421-004139-3c26/bini_health_ios.ipa)

### 安装步骤

1. 下载 IPA 到电脑
2. 使用 AltStore / Sideloadly / Apple Configurator 侧载到设备
3. 前往「设置 → 通用 → VPN 与设备管理」信任开发者证书
4. 打开应用体验
