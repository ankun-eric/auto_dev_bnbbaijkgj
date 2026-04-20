# 用户端首页与"我的-积分"模块｜7 项 Bug 修复 体验手册

> 项目：bini-health
> 版本：v7 + v7.2（2026-04-20）
> 覆盖范围：**H5 + 微信小程序 + 安卓 App**（用户端三端）
> 本次修复 Bug 总数：**7**（本手册开头"访问链接"表可直接体验）

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|---|---|---|
| 用户端首页（H5） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | H5 主页面入口，包含首页 LOGO、搜索栏、底部 Tab |
| 我的-积分页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/points](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/points) | 本次重点修复页（配色、真实积分、任务跳转、一次性任务置灰） |
| AI 健康咨询页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai) | 标题栏已移除 LOGO |
| 健康档案编辑页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/profile/edit](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/profile/edit) | 积分任务「完善健康档案」直达页 |
| 服务列表页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/services](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/services) | 积分任务「首次下单」直达页 |
| 安卓 APK 下载 | [bini_health.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/bini_health.apk) | 安卓客户端安装包（含本次 7 项 Bug 修复） |
| 微信小程序 zip 下载 | [miniprogram_latest.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/miniprogram_latest.zip) | 小程序代码压缩包，导入微信开发者工具体验（含本次 7 项 Bug 修复） |

---

## 一、功能简介

本次针对「用户端首页」与「我的-积分」两个核心模块的用户反馈，系统性修复了 7 项视觉/数据/跳转 Bug，覆盖 H5 + 微信小程序 + 安卓 App 三端；并随手修正了 AI 健康咨询页标题栏冗余 LOGO 的问题。目标是：让用户进入首页一眼看清品牌 LOGO、一读就懂的搜索提示；进入积分页看到真实可用积分、清晰的配色、正确跳转的任务、及时收拢完成的一次性任务。

### 本次修复一览

| # | 模块 | 修复后体验 |
|---|---|---|
| 1 | 首页顶栏 | LOGO 由过小升级为**顶栏高度 75%**，去掉冗余文字，品牌识别度显著提升 |
| 2 | 首页搜索栏 | 默认 placeholder 统一为**"搜索您想要的健康服务"**（本次 v7.2 强制重置服务器脏数据） |
| 3 | 我的-积分页 | 顶部卡片背景色改为**柔和浅绿 `#C8E6C9`**，与深绿标题形成清晰层次；"可用积分"**接入真实 `/api/points/summary` 接口**，不再是写死的 680 |
| 4 | 积分任务 | 「完善健康档案」点击**直达健康档案编辑页**（`/profile/edit`） |
| 5 | 积分任务 | 「首次下单」点击**直达服务列表页**（`/services`），支付任意一笔订单即视为完成 |
| 6 | 积分任务 | 一次性任务完成后**立即置灰、标注"✓ 已完成"、不可再点击**；**7 天后自动从列表消失** |
| 7 | AI 健康咨询页 | 顶部标题栏**移除 LOGO**，仅保留"AI 健康咨询"页面标题 |

---

## 二、使用说明（分步骤体验）

下面以 H5 为例，微信小程序与安卓 App 的交互**完全一致**。

### 体验 Bug 1：首页 LOGO 放大

1. 打开 [H5 首页](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/)
2. 查看页面左上角，可以看到 LOGO **明显放大**（占据顶栏约 75% 高度）
3. LOGO 右侧已**不再有"宾尼小康"等文字**，画面更清爽

### 体验 Bug 2：首页搜索栏文案修正

1. 停留在 H5 首页，查看中间的搜索框
2. 当搜索框未输入时，应显示**"搜索您想要的健康服务"**
3. 不再是之前的乱码或错误文案

### 体验 Bug 3：我的-积分页配色 + 真实积分

1. 点击底部 Tab **"我的"**，进入个人中心
2. 点击进入 **"我的积分"** 页（或直接访问 [积分页链接](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/points)）
3. 页面顶部"我的积分"卡片呈现**浅绿色 `#C8E6C9`**，上方深绿标题区层次分明，**不再撞色**
4. 卡片中显示的"可用积分"为**后台接口真实返回值**（不同用户账户的积分会不同，登录后对账一致）；未登录/接口异常时显示骨架屏或 "--"

### 体验 Bug 4：任务「完善健康档案」跳转正确

1. 在积分页下滑到"日常任务"列表
2. 点击卡片 **"完善健康档案"**
3. 应立即跳转到[健康档案编辑页](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/profile/edit)
4. 填写并保存档案后返回积分页，任务状态会正确更新（见 Bug 6）

### 体验 Bug 5：任务「首次下单」跳转正确

1. 在积分页"日常任务"列表中，点击卡片 **"首次下单"**
2. 应立即跳转到[服务列表页](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/services)
3. 在服务列表中下单并支付任意一笔订单（**到店核销前的已支付状态也算**），下次进入积分页会看到任务自动变为"✓ 已完成"

### 体验 Bug 6：一次性任务完成后的置灰与自动消失

1. 完成"完善健康档案"或"首次下单"其中一个一次性任务
2. 返回积分页，对应任务卡片会立即进入以下状态：
   - 图标和文字灰度化
   - 标题右侧出现 **"✓ 已完成"** 绿色小标签
   - 积分数字变灰
   - **卡片不可点击**（多次点击不会重复发放积分）
3. 完成后 **7 天内** 仍然可见（方便用户确认），**超过 7 天将自动从任务列表中消失**，避免长期占位

### 体验 Bug 7：AI 咨询页标题栏去 LOGO

1. 访问 [AI 健康咨询页](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai)
2. 查看顶部标题栏，应**仅显示"AI 健康咨询"文字**
3. 不再有多余的 LOGO 图标；右侧功能按钮（如有）位置保持不变

---

## 三、微信小程序体验

### 下载小程序代码

点击以下链接下载微信小程序代码压缩包：

> 📦 下载地址：[miniprogram_latest.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/miniprogram_latest.zip)

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
6. **预览体验**：导入成功后，开发者工具会自动编译并在模拟器中展示小程序界面
7. **逐项验证**：在首页查看 LOGO 大小、搜索栏文案；点击"我的-积分"查看卡片配色和积分数值；点击任务卡片验证跳转；AI 咨询页查看标题栏

---

## 四、安卓端体验

### 下载安装包

点击以下链接下载安卓客户端安装包：

> 📱 下载地址：[bini_health.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/bini_health.apk)

### 安装与体验步骤

1. **下载 APK**：点击上方链接，将 APK 安装包下载到手机（或先下载到电脑再传输到手机）
2. **允许安装**：如果手机提示「不允许安装未知来源应用」，请在手机设置中开启「允许安装未知来源应用」（不同手机品牌设置路径可能不同，一般在「设置 → 安全」或「设置 → 隐私」中）
3. **安装应用**：点击下载的 APK 文件，按照提示完成安装
4. **打开体验**：安装完成后，在手机桌面找到应用图标，点击打开
5. **登录后验证**：登录任意测试账号后，按第二节"使用说明"逐项验证首页、积分页、AI 咨询页的 7 项修复点

---

## 五、注意事项

- **登录状态**：Bug 3（真实积分）和 Bug 6（任务完成状态）依赖登录态，请确保先登录再体验。
- **积分值对账**：不同账户的积分不同；如果长期未变化，可对照管理后台同一用户的积分账户值核对。
- **首单完成判定**：本次修复后，支付成功的订单（不论是否到店核销）即被视为"首次下单"已完成，下次刷新积分页即可看到任务变为"已完成"。
- **任务 7 天消失**：一次性任务完成后**前 7 天仍在列表中显示为"已完成"**，超过 7 天才自动隐藏；这是为了让用户确认任务奖励已发放。
- **浏览器缓存**：如果首页 LOGO/搜索文案看起来仍是旧版，可在手机浏览器或微信中下拉刷新一次；H5 已通过 Next.js 热更。
- **v7.2 关键修复**：服务器侧搜索栏文案曾被误改为 "搜索健康服务/商品"，本次部署通过 `placeholder_v7_2_normalized` 幂等迁移标志**强制重置为"搜索您想要的健康服务"**。

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|---|---|---|
| 用户端首页（H5） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | H5 主页面入口，包含首页 LOGO、搜索栏、底部 Tab |
| 我的-积分页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/points](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/points) | 本次重点修复页（配色、真实积分、任务跳转、一次性任务置灰） |
| AI 健康咨询页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai) | 标题栏已移除 LOGO |
| 健康档案编辑页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/profile/edit](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/profile/edit) | 积分任务「完善健康档案」直达页 |
| 服务列表页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/services](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/services) | 积分任务「首次下单」直达页 |
| 安卓 APK 下载 | [bini_health.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/bini_health.apk) | 安卓客户端安装包（含本次 7 项 Bug 修复） |
| 微信小程序 zip 下载 | [miniprogram_latest.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/miniprogram_latest.zip) | 小程序代码压缩包，导入微信开发者工具体验（含本次 7 项 Bug 修复） |
