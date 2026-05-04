# 用户端下单页 — 时段网格化展示与满额置灰 · 用户体验使用手册

> 文档版本：v1.0  ·  更新时间：2026-05-04
> 对应 PRD：用户端下单页 — 时段网格化展示与满额置灰 v1.0

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（443/80），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 用户端首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 浏览器直接访问，进入商品/卡项详情页 → 立即预约 → 体验本次新版下单页 |
| H5 下单页直达 | [/checkout](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/checkout) | 需先登录、并通过商品详情页跳转，单独打开会要求带 productId |
| Admin 后台 | [/admin/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/) | 用于配置商品的预约方式、时段容量、门店容量（无 UI 改动） |
| 微信小程序代码包 | [miniprogram_slot_grid_20260504_152919_cf2b.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_slot_grid_20260504_152919_cf2b.zip) | 下载后用微信开发者工具导入体验 |
| 安卓 APK 下载 | [bini_health_slotgrid_20260504_152955_d26d.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/bini_health_slotgrid_20260504_152955_d26d.apk) | 安卓手机直接下载安装（约 80 MB） |
| iOS IPA 下载 | [bini_health_slotgrid_20260504_153018_a6f7.ipa](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ipa/bini_health_slotgrid_20260504_153018_a6f7.ipa) | 未签名 IPA，需配合 AltStore / Sideloadly 安装（约 32 MB） |
| iOS GitHub Release | [iOS Build ios-slotgrid-v20260504-153018-a6f7](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-slotgrid-v20260504-153018-a6f7) | 也可从 GitHub Release 页直接下载 |

---

## 功能简介

本次更新解决了用户端下单页两个体验断层：

1. **时段一目了然**：以前下单页时段是横向滚动列表，用户要左右滑动才能看到全部，且**满档时段直接被隐藏**，容易误以为"没那个时段"。现在改为**固定 3 列网格**，所有时段都显示出来，与"订单详情 → 修改预约"页保持一致的视觉风格。
2. **满档预先置灰**：以前用户要等到"提交订单"那一刻才会被服务端"该时段已满"打回去。现在进入下单页就能看到：
   - 已被约满的时段 → **灰底 + 灰字 + 右上角红色"已约满"角标**，不可点击。
   - 已经过去的时段 → 灰底灰字，不可点击。
   - **日期模式（无时段）**的商品也一样：日历选择器中**整天约满的日期被禁用**，picker 旁会出现红字"（已约满）"提示。

支持端：**H5、微信小程序、安卓 App、iOS App**。后端容量判定逻辑 100% 沿用旧逻辑（含商品级 `capacity` + 门店级 `slot_capacity` 双层 + 15 分钟内待支付订单计入占用），只是把状态对外暴露而已，**不会改变现有约满判定结果**。

---

## 本次客户端变更

| 终端 | 变更说明 | 新版本下载 |
|------|----------|------------|
| 后端（已部署到测试服务器） | 新增 `GET /api/h5/checkout/info`（统一返回 `available_slots` / `available_dates` 含 `is_available` + `unavailable_reason`）；改造 `GET /api/h5/slots`，满档时段不再过滤而是返回 `is_available=false` | 已部署生效，无需用户操作 |
| H5（已部署到测试服务器） | 下单页时段改 3 列网格 + 满额置灰 + 角标；日期模式日历整天约满置灰 | [H5 首页](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) |
| 微信小程序 | `pages/checkout/index` 同上，wxss 改 grid 3 列 + 角标样式 | [miniprogram_slot_grid_20260504_152919_cf2b.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_slot_grid_20260504_152919_cf2b.zip) |
| 安卓 App | `lib/screens/product/checkout_screen.dart` 时段改 `GridView.count(crossAxisCount: 3)`，已约满 `Stack`+`Positioned` 红角标，日历用 `selectableDayPredicate` 置灰满档日期 | [bini_health_slotgrid_20260504_152955_d26d.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/bini_health_slotgrid_20260504_152955_d26d.apk) |
| iOS App | 同安卓，Dart 代码全平台共享 | [bini_health_slotgrid_20260504_153018_a6f7.ipa](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ipa/bini_health_slotgrid_20260504_153018_a6f7.ipa) |

> Admin 端本次**没有任何 UI / 接口改动**，可继续使用现有版本。

---

## 使用说明

### 场景 1：时段模式（appointment_mode = time_slot）

1. 进入用户端首页 → 任选一个**预约方式为「时段」**的商品 → 进入详情页 → 点击「立即预约」进入下单页。
2. 选好门店、选好预约日期后，**「预约时段」**区域即刻渲染：
   - **3 列等宽网格**，按时间从早到晚排列，所有时段全部展示出来（不再隐藏满档项）。
   - **正常可约时段**：白底黑字 + 圆角边框；点击后变蓝边蓝字（选中态）。
   - **已约满时段**：浅灰底 `#F5F5F5` + 灰字 `#999999`，**右上角红色"已约满"角标**，**点击无任何反应**（不弹 Toast、不跳转、不变色）。
   - **已过期时段**（仅当日选择今天且当前时间已超过该时段开始）：灰底灰字，不可点击。
3. 选中可用时段后，「提交订单」按钮可用；如果选中过满档时段（不会发生，因不可点），后端最后一道兜底也会拦截。

### 场景 2：日期模式（appointment_mode = date）

1. 同样进入下单页，选择门店后进入「预约日期」区域。
2. 打开日历选择器：
   - 整天**已约满的日期** → 显示为**禁用灰色**，无法选中（H5 / 小程序 / Flutter 三端均一致）。
   - 已过去的日期 → 同样置灰禁用。
3. 已选中的日期如果**整天约满**，picker 旁会出现红色文案 **"（已约满）"** 作为提示，**「提交订单」会被前端拦截**（弹 Toast：「该日期已约满，请重选」）。

### 场景 3：管理员配置容量（Admin 端，无 UI 改动）

为了让"约满置灰"生效，需要管理员事先在后台配置容量：

1. **商品级容量**：进入 Admin → 商品管理 → 编辑商品 → 在时段配置中给每个时段填写 `capacity`（>0 表示该商品在该时段最多多少人，0 或留空表示不限）。
2. **门店级容量（跨商品累计）**：进入 Admin → 门店管理 → 编辑门店 → 设置 `slot_capacity`（每个时段全店所有商品累计上限）。
   - 例：A 商品时段 09:00 容量 3 + B 商品时段 09:00 容量 5，门店 `slot_capacity = 4`，那么哪怕 A 还剩 2 个 B 还剩 5 个，**门店 09:00 已经被订满 4 单时所有商品的 09:00 都会显示已约满**。
3. **15 分钟保护**：用户下单 15 分钟内未支付仍计入占用，超过 15 分钟自动释放。

---

## 微信小程序体验

### 下载小程序代码

> 📦 下载地址：[miniprogram_slot_grid_20260504_152919_cf2b.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_slot_grid_20260504_152919_cf2b.zip)

### 体验步骤

1. **下载压缩包**：点击上方链接，将 zip 下载到本地电脑。
2. **解压文件**：解压到任意目录，记住路径（解压后里面会有一个 `miniprogram` 文件夹）。
3. **下载微信开发者工具**：如尚未安装，请前往 [微信开发者工具官方下载页面](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html)。
4. **打开微信开发者工具**：使用微信扫码登录。
5. **导入项目**：
   - 点击「导入项目」（或左上角 "+"）。
   - 在「目录」栏选择第 2 步解压后的 `miniprogram` 文件夹。
   - AppID 可填项目实际 AppID 或选择「测试号」。
   - 点击「导入」。
6. **预览体验**：
   - 进入"商品"页 → 任选一个**时段预约**商品 → 立即预约。
   - 在下单页选择门店与日期，**预约时段**区域以 3 列网格方式呈现，满档时段灰底 + 红角标"已约满"。
   - 也可挑一个**日期预约**商品验证整天满档场景。

---

## 安卓端体验

### 下载安装包

> 📱 下载地址：[bini_health_slotgrid_20260504_152955_d26d.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/bini_health_slotgrid_20260504_152955_d26d.apk)（约 80 MB）

### 安装与体验步骤

1. **下载 APK**：用安卓手机浏览器打开上方链接下载。
2. **允许安装**：如手机提示「不允许安装未知来源应用」，请在「设置 → 安全」或「设置 → 应用管理」中开启「允许安装未知来源应用」。
3. **安装应用**：点击下载好的 APK 文件，按提示完成安装。
4. **打开体验**：登录后从首页 → 商品详情 → 立即预约进入下单页，验证：
   - 时段以 3 列网格展示。
   - 满档时段灰底 + 右上角红色"已约满"角标，点击无响应。
   - 日期模式下日历约满天置灰。

---

## iOS 端体验

### 下载安装包

> 🍎 GitHub Release 页面：[iOS Build ios-slotgrid-v20260504-153018-a6f7](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-slotgrid-v20260504-153018-a6f7)
>
> 📦 IPA 直接下载：[bini_health_slotgrid_20260504_153018_a6f7.ipa](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ipa/bini_health_slotgrid_20260504_153018_a6f7.ipa)（约 32 MB）

### 安装与体验步骤

1. **下载 IPA 文件**：点击上方"IPA 直接下载"链接，将 IPA 下载到电脑。
2. **安装到 iPhone / iPad**（本 IPA 为**未签名**版本，请按以下方式之一安装）：
   - **方式一：AltStore / Sideloadly 侧载**（推荐）
     - 在电脑上安装 [AltStore](https://altstore.io/) 或 [Sideloadly](https://sideloadly.io/)。
     - 用数据线连接 iPhone/iPad 到电脑。
     - 在工具中选择 IPA，使用 Apple ID 自签后安装。
   - **方式二：Apple Configurator 2（需 Mac）**
     - 在 Mac 启动 Apple Configurator 2，连接设备后将 IPA 拖入即可安装。
   - **方式三：TrollStore**（仅适用于支持的旧版 iOS）。
3. **信任开发者**：如安装后无法打开，在 iPhone「设置 → 通用 → VPN 与设备管理」中找到对应描述文件并点击「信任」。
4. **打开体验**：登录后下单页同安卓端，验证 3 列网格 + 已约满角标 + 日期置灰。

---

## 验证点（建议自测清单）

| # | 端 | 步骤 | 预期 |
|---|----|------|------|
| 1 | H5 / 小程序 / App | 进入时段商品下单页 | 时段以 3 列等宽网格展示，所有时段全部可见 |
| 2 | 同上 | 选择已被订满的时段 | 灰底 `#F5F5F5` + 灰字 `#999999` + 右上红色 `#FF4D4F` "已约满"角标 |
| 3 | 同上 | 点击已约满时段 | **完全无反应**（不弹 Toast、不变色、不跳转） |
| 4 | 同上 | 选今天 + 早上已过去的时段 | 灰底灰字，不可点击 |
| 5 | 同上 | 选满档时段后切换日期 | 列表立即重新加载，满档/可约状态实时同步 |
| 6 | 同上 | 选可用时段并提交 | 正常进入支付页（兜底：若被并发抢光，后端 409 拦截） |
| 7 | 日期模式商品 | 打开日历选择器 | 整天满档/已过期日期不可选 |
| 8 | 日期模式商品 | 选中满档日提交（理论不会发生） | 前端 Toast「该日期已约满，请重选」拦截 |
| 9 | 视觉一致性 | 「订单详情 → 修改预约」页与下单页对比 | 两个页面时段网格视觉一致（3 列、间距、角标） |

---

## 注意事项

1. **逻辑零变更**：本次只改 UI 与 API 暴露字段，**约满判定逻辑 100% 沿用旧逻辑**（商品级 capacity + 门店级 slot_capacity + 15 min 保护），不会出现"以前能下，现在不能下"或反之的差异。
2. **再次进入页面会重新拉取**：`is_available` 在用户**进入下单页**和**切换日期/门店**时各拉取 1 次，**不轮询**。如想刷新，下拉或重新进入页面即可。
3. **极端并发兜底**：用户 A 看到"可约"、A 提交前用户 B 抢占了最后一个名额，A 提交时后端会以 409 / 业务错误码兜底返回，前端弹 Toast 提示并刷新数据。
4. **iOS 未签名 IPA 的限制**：使用 AltStore 自签的 App 有 7 天有效期，过期后需重新签名（如续 Apple Developer 账号则可延长）。
5. **小程序 AppID**：导入开发者工具时如选「测试号」，部分需要正式 AppID 的能力（如订阅消息）会无法测试，但本次新功能不依赖这些能力，可正常体验。

---

## 常见问题排查

| 现象 | 可能原因 | 处理建议 |
|------|---------|---------|
| 下单页所有时段都正常，没出现灰色"已约满" | 当前商品/门店未约满；或未配置容量 | 正常：当前还未约满。可在 Admin 把 `capacity` 调小到 1 后下一单测试 |
| 日历每一天都能选 | 日期模式商品未配置容量；或确实没有满档日 | 正常。可调小容量并下单一次后再测试 |
| 网格变成 1 列 | 浏览器缓存了旧版 H5 | 强制刷新（Ctrl+F5 / 清缓存）或重新部署后访问 |
| 小程序导入失败 | 选错了文件夹 | 应选解压后的 `miniprogram` 文件夹（里面应有 `app.json`），不是外层目录 |
| iOS App 打不开 | 未信任开发者 | 设置 → 通用 → VPN 与设备管理 → 信任对应配置文件 |
| 点击满档时段没置灰，但能进入下一步 | 客户端未升级到本次新版本 | 重新下载安装最新 APK / IPA / 小程序代码包 |

---

## 服务端测试结果（参考）

本次后端共 9 个用例全部通过：

```
backend/tests/test_checkout_info_slot_grid.py
  test_checkout_info_basic_structure                       PASSED
  test_checkout_info_capacity_full_per_product             PASSED
  test_checkout_info_store_capacity_full_cross_products    PASSED
  test_checkout_info_pending_within_15min_counts           PASSED
  test_checkout_info_pending_over_15min_does_not_count     PASSED
  test_checkout_info_cancelled_does_not_count              PASSED
  test_h5_slots_returns_full_with_marker                   PASSED
  test_h5_slots_unauthorized_returns_401                   PASSED
  test_checkout_info_unknown_product_404                   PASSED
========================== 9 passed in 4.28s ==========================
```

外部 URL 验证：根页 200、`/api/health` 200、`/checkout` 308（rewrites OK）、`/api/h5/checkout/info?productId=1` 401（未登录正确拒绝）、`/api/h5/slots?storeId=1&date=2026-05-10&productId=1` 401（同）。
