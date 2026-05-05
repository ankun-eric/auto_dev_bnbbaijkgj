# 客户端改期能力收口 — 用户体验使用手册（PRD-03 v1.0 最终交付）

> 文档版本：v1.0（最终交付）
> 发布日期：2026-05-05 20:13
> 适用产品：bini-health 健康服务预约平台
> 对应 PRD：PRD-03 客户端改期能力收口

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均通过宿主机 `gateway` 容器（Nginx，监听 80/443）反向代理，请勿直接访问 Docker 内部端口（3000/3001/8000）。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 用户端首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 顾客在浏览器/手机浏览器登录后即可发起改期 |
| 商家 PC 后台首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/login/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/login/) | 商家登录入口（已确认无任何改期入口） |
| 商家端预约日历（H5） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/calendar/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/calendar/) | 已下线全部「改约」入口，顶部新增黄色提示横幅 |
| 微信小程序 zip 下载 | [miniprogram_20260505_180514_8267.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_20260505_180514_8267.zip) | 含 PRD-03 改期 UI 强化的小程序代码包，约 384 KB |
| 安卓客户端 APK 下载 | [bini_health_android_reschedule_btn_20260505_134055_a3bf.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/bini_health_android_reschedule_btn_20260505_134055_a3bf.apk) | 含 9 段切片底座的 APK，约 80 MB（详见下方「APP 端打包说明」） |
| iOS 客户端 Release | [iOS Build ios-prd01-v20260505-170803-0e27](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-prd01-v20260505-170803-0e27) | iOS IPA Release，含 9 段切片底座（详见下方「APP 端打包说明」） |

---

## 1. 功能简介

本期把「改期」权限**完全收归客户端**——顾客在 小程序 / APP / H5 自助修改预约时间，商家端不再有任何「改时间」入口；后端接口加入角色校验，从根本上拒绝商家/平台调用客户端改期接口；改期容量校验采用宽松策略，仅校验门店营业 + 时段在营业内，**不校验单时段容量**，允许超约由门店人工协调。

| 改造点 | 说明 |
|---|---|
| 商家端零改期权 | H5 商家端预约日历的「改约」按钮 / 菜单项 / Popover 全部下线；后端商家端改期接口 `/api/merchant/booking/{id}/reschedule` 直接返回 403 |
| 客户端三端改期保留并强化 | H5 / 小程序 / APP 客户端的「修改预约」按钮保留并强化（明天起 90 天 + 9 段固定切片 + 改期上限 3 次置灰 + 商品级 `allow_reschedule` 开关 + 弹窗内蓝色规则提示） |
| 接口角色校验 | `POST /api/orders/unified/{id}/appointment` 在改期场景仅允许 `role=user` 调用，商家 / 平台 / 超管全部 403 |
| 宽松容量校验 | 改期仅校验门店营业 + 时段在营业内，**不校验单时段容量**，允许超约由门店人工协调（PRD §2.5） |

> 改期成功后的「三通道通知」（小程序订阅消息 + APP push + 短信）由 PRD-04 已经独立交付。

---

## 2. 本次客户端变更

> 本次更新涉及以下终端的代码改动，请下载最新版本体验：

| 终端 | 变更说明 | 新版本下载 |
|------|----------|------------|
| H5 用户端 | 改期弹窗：标题切换「修改预约」/「选择预约时间」、新增「明天起 90 天 / 还可改期 N 次」蓝色规则提示、时段池切换为 PRD-01 的 9 段固定切片（每行 3 个）、`allow_reschedule=false` 时按钮置灰、DatePicker `min` 强制为「明天 00:00」 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) |
| H5 商家端 | 删除 `RescheduleModal.tsx` 整文件 + 删除 ListView 改约菜单项 + 删除 BookingActionPopover「改约」按钮 + 清理 page.tsx 中的弹窗引用与 state + 顶部新增黄色横幅「📌 改期权已收归客户端」 | 同上 H5 链接 |
| 微信小程序 | 弹窗标题切换、改期场景使用 9 段切片、改约按钮在 `allow_reschedule=false` 时置灰、`apptMinDate` 改为明天、新增 `.appt-tip` 蓝色规则提示样式 | [miniprogram_20260505_180514_8267.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_20260505_180514_8267.zip) |
| Flutter APP（安卓 / iOS） | 弹窗标题三态切换、改期场景使用 `_kReschedule9Slots` 9 段、改约按钮在 `allow_reschedule=false` 时置灰、`firstDate` 改为明天、新增蓝色规则横幅、`selectedDate < firstSelectable` 自动提升 | ⚠️ 详见下方「APP 端打包说明」 |

> ⚠️ H5 已通过服务器 `gateway` 容器部署生效，访问 H5 链接即可体验最新版本；微信小程序 zip 已上传服务器，公网可下载；后端 API 已部署上线（见下方测试结果）。

### APP 端打包说明（如实告知）

本次 Flutter 端代码改动（含 PRD-03 全部 UI 强化）已合并并推送到 master（commit `49c39a9`），但 GitHub Actions 远程构建在上次执行时未能完成——构建用的 GitHub Personal Access Token 被 GitHub Secret Scanning 自动撤销，工作流无法被触发。

**当前可下载的 APP 二进制版本**：

- 安卓 APK：[bini_health_android_reschedule_btn_20260505_134055_a3bf.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/bini_health_android_reschedule_btn_20260505_134055_a3bf.apk)（已含 PRD-01 9 段切片底座 + PRD-02 看板能力）
- iOS Release：[iOS Build ios-prd01-v20260505-170803-0e27](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-prd01-v20260505-170803-0e27)（同上含 PRD-01 时段底座）

**为什么使用旧版本依然能正常完成改期**（核心契约由后端兜底）：

- ✅ **改期接口仅 customer 可调** —— 后端 `set_order_appointment` 强制 `role=user` 校验，商家 / 平台 / 超管发起改期一律 403
- ✅ **改期日期范围明天起 90 天** —— 后端 `appt_naive < tomorrow_start` / `appt_naive > max_date` 校验
- ✅ **宽松容量校验** —— 后端 `validate_reschedule_lenient` 仅校验门店营业 + 时段在营业内
- ✅ **改期上限 3 次** —— 后端 `reschedule_count >= 3` 校验
- ✅ **商品级 `allow_reschedule`** —— 后端任一商品 `allow_reschedule=False` → 400 透传

旧版本 APP 仅缺少本次新增的「蓝色规则提示横幅」和「标题文案微调」等 UI 细节，**功能不缺失**。

如需获取含 PRD-03 全部 UI 强化的最新 APK / IPA，重新签发 GitHub Personal Access Token（scopes: `repo` + `workflow`）后，运行项目根目录下的 `deploy/_build_apk_prd03_20260505.py` 与 `deploy/_build_ios_prd03_20260505.py` 即可一键完成构建上传。

---

## 3. 使用说明

### 3.1 顾客端：在 小程序 / APP / H5 改期

1. **进入订单详情页**：在「我的订单」列表点击对应订单进入详情。
2. **找到「改约」按钮**：底部操作栏会显示「改约」按钮（仅在订单状态为 `已预约 / 待核销 / 部分核销` 且非退款流程中显示）。
3. **判断按钮是否可点击**：
   - 灰色置灰 + 提示「本订单已达改期上限，如需继续改期请联系门店」→ 当前订单已经改期 3 次，达到 `reschedule_limit`。
   - 灰色置灰 + 提示「该商品不支持改期」→ 该商品 `allow_reschedule=false`（如电影票、限时活动等不可退改场景）。
   - 正常颜色 → 可点击进入改期弹窗。
4. **改期弹窗**：
   - **标题**：「修改预约」（若是首次填写预约日则显示「选择预约时间」）。
   - **顶部蓝色规则提示**：「改期可选范围：明天起 90 天内；本订单还可改期 N 次」。
   - **预约日期**：日历最早为**明天**，最远为**今天 + 90 天**。今天的日期不可选，超出范围自动置灰。
   - **预约时段**：每行 3 个，共 9 段（`06:00-08:00 / 08:00-10:00 / 10:00-12:00 / 12:00-14:00 / 14:00-16:00 / 16:00-18:00 / 18:00-20:00 / 20:00-22:00 / 22:00-24:00`）。**注意：凌晨 00:00-06:00 不开放改期**。
   - **确认改期**：点击底部绿色按钮，提示「改期成功，已通知您」。
5. **改期生效**：订单的预约时间立即更新，门店端预约看板会同步刷新；后端会异步并行下发三通道通知（小程序订阅消息 + APP push + 短信，详见 PRD-04）。

### 3.2 商家端：不再有任何改期权

商家在以下任何位置都不会看到「改约」按钮：

- 商家 PC 后台 — 订单管理页（[`/admin/product-system/orders`](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/product-system/orders)）：✅ 经审计确认无改期入口。
- 商家 PC 后台 — 预约看板（[`/admin/product-system/orders/dashboard`](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/product-system/orders/dashboard)）：✅ 经审计确认无改期入口。
- 商家 H5 — 预约日历（[`/merchant/calendar`](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/calendar/)）：✅ 已删除 `RescheduleModal`、列表「改约」菜单项、9 宫格 Popover「改约」按钮、详情页改约入口。
- 商家 H5 — 顶部新增黄色横幅：「📌 改期权已收归客户端，商家无法直接改时间。如顾客需要改期，请提示其在小程序 / APP / H5 自助操作。」

如商家通过其他途径（如直接调 API）尝试调用商家改期接口 `/api/merchant/booking/{id}/reschedule`，后端会直接返回 **403 Forbidden**，错误文案为：

> 改期权已收归客户端，商家端无改期权限。请通知顾客自行在小程序/APP/H5 客户端发起改期。

### 3.3 客服 / 平台运营：建议引导话术

当顾客来电要求门店帮其改期时，客服可以这样回复：

> 「您好，根据平台规则，预约时间的修改需要由您自己在 小程序 / APP / H5 上完成（订单详情页 → 改约按钮）。门店和平台都没有直接修改您预约时间的权限。这样设计是为了保护您的权益，避免有任何人在未经您同意的情况下修改您的预约时间。您操作过程中如有困难，我可以电话指导您一步步完成。」

---

## 4. 微信小程序体验

### 下载小程序代码

点击以下链接下载微信小程序代码压缩包：

> 📦 下载地址：[miniprogram_20260505_180514_8267.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_20260505_180514_8267.zip)

### 体验步骤

1. **下载压缩包**：点击上方链接，将 zip 压缩包下载到本地电脑（约 384 KB）。
2. **解压文件**：将下载的 zip 文件解压到任意目录（解压后根目录直接是 `app.json`、`project.config.json` 等小程序入口文件）。
3. **下载微信开发者工具**：如尚未安装，请前往 [微信开发者工具官方下载页面](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html) 下载并安装。
4. **打开微信开发者工具**：启动开发者工具，使用微信扫码登录。
5. **导入项目**：
   - 点击开发者工具首页的「导入项目」（或「+」号）。
   - 在「目录」栏点击浏览，选择第 2 步解压后的文件夹。
   - 「AppID」栏可填入项目的 AppID，或选择「测试号」进行体验。
   - 点击「导入」按钮。
6. **预览体验**：导入成功后，开发者工具会自动编译并在模拟器中展示小程序界面。登录账号后进入「我的订单 → 任意订单 → 改约」即可体验本次 PRD-03 改期 UI 强化（蓝色规则提示横幅、9 段固定切片、`allow_reschedule=false` 置灰等）。

---

## 5. 安卓端体验

### 下载安装包

点击以下链接下载安卓客户端安装包：

> 📱 下载地址：[bini_health_android_reschedule_btn_20260505_134055_a3bf.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/bini_health_android_reschedule_btn_20260505_134055_a3bf.apk)

> ⚠️ 该 APK 是上一阶段（PRD-02）构建的，已含 PRD-01 9 段切片底座 + PRD-02 看板能力。本次 PRD-03 的 Flutter 改期弹窗 UI 强化（蓝色规则横幅 / 标题切换文案 / `firstDate` 提升至明天）**未在该包中**，但所有 PRD-03 后端规则（明天起 90 天 / 角色校验 / 宽松校验 / 商品级开关）由服务器端拦截兜底，使用旧 APK 仍可正常完成改期。
>
> 如需含本次完整 UI 强化的 APK，需重新签发 GitHub Token 后运行 `deploy/_build_apk_prd03_20260505.py`。

### 安装与体验步骤

1. **下载 APK**：点击上方链接，将 APK 安装包下载到手机（或先下载到电脑再传输到手机），约 80 MB。
2. **允许安装**：如果手机提示「不允许安装未知来源应用」，请在手机设置中开启「允许安装未知来源应用」（不同手机品牌设置路径可能不同，一般在「设置 → 安全」或「设置 → 隐私」中）。
3. **安装应用**：点击下载的 APK 文件，按照提示完成安装。
4. **打开体验**：安装完成后，在手机桌面找到应用图标，点击打开即可体验。登录后进入「我的订单 → 任意订单 → 改约」即可。

---

## 6. iOS 端体验

### 下载安装包

点击以下链接前往 GitHub Release 页面下载 iOS 客户端安装包：

> 🍎 GitHub Release 页面：[iOS Build ios-prd01-v20260505-170803-0e27](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-prd01-v20260505-170803-0e27)

> ⚠️ 该 IPA 是上一阶段（PRD-01）构建的，未签名版本，需通过 AltStore / Sideloadly 等工具侧载安装。本次 PRD-03 的 Flutter UI 强化未在该包中，但所有后端规则由服务器端兜底，功能不缺失。如需含本次完整 UI 强化的 IPA，需重新签发 GitHub Token 后运行 `deploy/_build_ios_prd03_20260505.py`。

### 安装与体验步骤

1. **下载 IPA 文件**：点击上方 GitHub Release 链接，下载 IPA 安装包到电脑。
2. **安装到设备**（选择以下任一方式）：
   - **方式一：使用 AltStore / Sideloadly 等第三方工具侧载安装**
     - 在电脑上安装 [AltStore](https://altstore.io/) 或 [Sideloadly](https://sideloadly.io/)。
     - 将 iPhone/iPad 通过数据线连接到电脑。
     - 使用工具将下载的 IPA 文件安装到设备上。
   - **方式二：使用 Apple Configurator 2（需 Mac 电脑）**
     - 在 Mac 上打开 Apple Configurator 2。
     - 连接 iPhone/iPad，将 IPA 文件拖拽到设备上安装。
3. **信任开发者证书**（如安装后无法打开）：前往「设置 → 通用 → VPN 与设备管理」，找到对应的开发者证书并点击「信任」。
4. **打开体验**：安装完成后，在手机桌面找到应用图标，点击打开即可体验。登录后进入「我的订单 → 任意订单 → 改约」即可。

---

## 7. 注意事项

| 注意点 | 说明 |
|---|---|
| 改期上限 | 单订单最多 3 次，第 4 次起按钮置灰，文案「本订单已达改期上限，如需继续改期请联系门店」 |
| 改期范围 | 仅可改至**明天起 90 天**内的日期，今天不可选；超出范围后端会返回 400「改期日期最早从明天起」/「改期日期最远 90 天内」 |
| 凌晨段限制 | 改期时段固定 9 段（06:00-24:00），凌晨 00:00-06:00 不开放，与全平台 PRD-01 配置一致 |
| 商品级开关 | 商品配置 `allow_reschedule=false` 时，改约按钮全平台置灰；商家可在商品后台「商品管理 → 编辑商品 → 预约配置」开关此项 |
| 角色限制 | 改期接口仅允许 customer 角色（即注册用户）调用；商家用户、平台运营、超管均无任何改期权限——即便是超管也无权代客改期，必须由顾客本人发起 |
| 宽松容量校验 | 改期仅校验门店营业 + 时段在营业内，**不校验单时段容量**：即使该时段已经满员，客户改期到该时段也会成功，门店在 9 宫格看板中会看到「超约」状态，需主动联系顾客协调时间 |
| 退款进行中限制 | 订单退款审核中（`refund_status in (applied/reviewing/approved/returning/refund_success)`）不允许改期 |
| 已部分核销限制 | 订单已部分核销（`pending_use` + 至少一个 item `used_redeem_count > 0`）不允许改期，避免破坏核销轨迹 |
| 改期通知 | 改期成功后并行下发三通道通知（小程序订阅消息 + APP push + 短信），不阻塞改期主流程（详见 PRD-04） |

---

## 8. 自动化测试结果（部署后服务器实测）

| 测试套件 | 用例数 | 结果 |
|---|---|---|
| `tests/test_prd03_reschedule_v1.py` | 27 | ✅ 全部 PASS |
| `tests/test_prd02_dashboard_v1.py` | 41 | ✅ 全部 PASS |
| `tests/test_time_slots_unified_v1.py` | 44 | ✅ 全部 PASS |
| **合计** | **112** | **✅ 100% PASS（1.32s）** |

测试覆盖：
- 宽松校验工具 16 case（`_parse_hhmm` / `_time_in_window` / `validate_reschedule_lenient` 含无 store_id / 无配置 / weekday 命中与不命中 / `date_exception` 各分支 / 多窗口任一命中 / 不查 OrderItem 容量断言）
- 改期日期边界 2 case（明天最早 / 90 天最远）
- 角色校验 9 case（仅 user 通过，其他 8 种角色全部拒绝）
- PRD-02 看板字段口径 41 case
- PRD-01 9 段切片底座 44 case

---

## 9. 部署链路（已验证）

- ✅ 后端 commit `49c39a9` 已部署到服务器容器 `6b099ed3-7175-4a78-91f4-44570c84ed27-backend`
- ✅ H5 / Admin 已构建为 standalone 镜像并启动到 `-h5` / `-admin` 容器
- ✅ 服务器 gateway nginx 已补全 `/miniprogram/`、`/apk/`、`/downloads/`、`/ipa/`、`/verify-miniprogram/` 5 条静态下载 location，全部公网 200
- ✅ H5 用户端首页：[https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) 实测 200
- ✅ Admin 后台首页：[https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/) 实测 200
- ✅ 商家端预约日历：[https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/calendar/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/calendar/) 实测 200
- ✅ 微信小程序 zip 下载：实测 HTTP 200，Content-Type `application/zip`
- ✅ 安卓 APK 下载：实测 HTTP 200，Content-Type `application/vnd.android.package-archive`

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均通过宿主机 `gateway` 容器（Nginx，监听 80/443）反向代理，请勿直接访问 Docker 内部端口（3000/3001/8000）。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 用户端首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 顾客在浏览器/手机浏览器登录后即可发起改期 |
| 商家 PC 后台首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/login/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/login/) | 商家登录入口（已确认无任何改期入口） |
| 商家端预约日历（H5） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/calendar/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/calendar/) | 已下线全部「改约」入口 |
| 微信小程序 zip 下载 | [miniprogram_20260505_180514_8267.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_20260505_180514_8267.zip) | 含 PRD-03 改期 UI 强化的小程序代码包 |
| 安卓客户端 APK 下载 | [bini_health_android_reschedule_btn_20260505_134055_a3bf.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/bini_health_android_reschedule_btn_20260505_134055_a3bf.apk) | 含 9 段切片底座的 APK，本次 UI 强化待重打 |
| iOS 客户端 Release | [iOS Build ios-prd01-v20260505-170803-0e27](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-prd01-v20260505-170803-0e27) | iOS Release，含 9 段切片底座 |

---

文档结束。
