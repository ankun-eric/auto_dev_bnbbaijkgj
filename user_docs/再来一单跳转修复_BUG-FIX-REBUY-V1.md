# 「再来一单」跳转页面错误 Bug 修复 — 用户体验手册

> 版本：V1.0  
> 修复编号：BUG-FIX-REBUY-V1  
> 修复时间：2026-05-07  
> 优先级：P0 高优 / 紧急

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 项目主页面入口（经 Nginx 代理，端口 80） |
| H5 我的订单 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/unified-orders/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/unified-orders/) | 订单列表页（已完成 / 已过期订单可见「再来一单」） |
| H5 登录 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/login/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/login/) | 用户登录入口 |
| 微信小程序代码下载 | [miniprogram_rebuy_20260507_154249_5fbd.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_rebuy_20260507_154249_5fbd.zip) | 微信小程序代码包，导入【微信开发者工具】体验 |

---

## 功能简介

本次修复了**全平台「再来一单」入口跳转错误**的 P0 级 Bug，覆盖 H5、Android APP、iOS APP、微信小程序三端及后端：

1. **修正跳转目的地**：点击「再来一单」由「跳到原订单详情页」改为「跳到新单支付/结算页」（旧 `?action=rebuy` 参数从未被处理）。
2. **商品自动带入**：原订单的商品 + SKU + 数量自动复用，门店/日期/时段/联系人/优惠券一律清空待选。
3. **新增后端 reorder 接口**：`POST /api/orders/unified/{order_id}/reorder` 统一校验商品状态，三端调用同一接口避免逻辑漂移。
4. **完善异常分支**：商品全部下架 / 部分下架 / 登录态过期 / SKU 已停用 全部有兜底处理与 Toast 提示。
5. **入口齐备**：列表页 + 详情页双入口，行为完全一致。
6. **支付页轻提示**："已为您带入原订单商品，请确认信息" 一次性 Toast。

---

## 本次客户端变更

本次更新涉及以下终端的代码改动，请下载最新版本体验：

| 终端 | 变更说明 | 新版本下载 |
|------|----------|------------|
| H5 网页端 | 列表页「再来一单」按钮重写跳转逻辑 → 新增详情页「再来一单」按钮（completed/expired）→ 调 reorder 接口校验后跳 `/checkout` | 已部署到测试环境，无需下载，刷新即体验 |
| 微信小程序 | 列表页/详情页新增「再来一单」按钮 + `onRebuy` 方法（完成/过期状态显示） | [miniprogram_rebuy_20260507_154249_5fbd.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_rebuy_20260507_154249_5fbd.zip) |
| Android APP | `unified_orders_screen.dart` + `unified_order_detail_screen.dart` 新增「再来一单」按钮 + `_onRebuy` 方法；`api_service.dart` 新增 `reorderUnifiedOrder` | 代码已对齐，本次未触发远程构建（服务器到 GitHub 网络受限）；可前往 [GitHub Actions android-build.yml](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/actions/workflows/android-build.yml) 手动触发 |
| iOS APP | 同上（Flutter 共享 `lib/`） | 代码已对齐，本次未触发远程构建；可前往 [GitHub Actions ios-build.yml](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/actions/workflows/ios-build.yml) 手动触发 |

> ⚠️ 以上终端的代码在本次更新中均有改动。H5 已直接部署，刷新即可体验；微信小程序请下载 zip 重新导入开发者工具；Android/iOS 端代码已合并到主干，等待你触发 GitHub Actions 远程构建获得新安装包。

---

## 使用说明

### 场景一：从订单列表点击「再来一单」（推荐）

1. 任一端登录后，进入「我的订单」
2. 找到一笔状态为「已完成」或「已过期」的订单
3. 点击订单卡片右下角的「再来一单」按钮
4. 系统弹出 Toast：
   - **正常情况**：直接跳到支付/结算页，商品已带入
   - **部分商品下架**：「部分商品已下架，已为您过滤」+ 跳支付页（仅在售商品）
   - **全部下架**：「商品已全部下架，无法再来一单」+ 停留原页（不跳转）
5. 在支付页选择「门店 / 日期 / 时段 / 联系人」（这些字段为空，需重新选择），然后立即支付即可

### 场景二：从订单详情点击「再来一单」

1. 在订单列表点击某笔已完成/已过期订单进入详情
2. 详情页底部出现「再来一单」按钮（绿色填充）
3. 后续流程与场景一完全一致

### 字段复用规则

| 字段 | 是否复用原订单 |
|------|----------------|
| 商品（spu） | ✅ 复用（仅在售商品） |
| SKU 规格 | ✅ 复用（已停用 SKU 自动过滤） |
| 数量 | ✅ 完全复用 |
| 门店 / 日期 / 时段 | ❌ 清空，需重新选 |
| 联系人 / 手机号 / 备注 | ❌ 清空，需重新填 |
| 优惠券 | ❌ 清空，由支付页根据新数据重新匹配 |

### 异常场景处理

| 异常 | 处理方式 | 文案 |
|------|----------|------|
| 全部商品已下架 | Toast + 停留原页 | 商品已全部下架，无法再来一单 |
| 部分商品下架 | Toast + 过滤后跳支付页 | 部分商品已下架，已为您过滤 |
| SKU 已停用 | 同"部分商品下架"处理 | 同上 |
| 登录态过期 | 跳登录页（H5）/ Toast 提示（小程序、APP） | 请先登录 |
| 网络异常 | Toast | 网络异常，请稍后重试 |

---

## 微信小程序体验

### 下载小程序代码

点击以下链接下载微信小程序代码压缩包：

> 📦 下载地址：[miniprogram_rebuy_20260507_154249_5fbd.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_rebuy_20260507_154249_5fbd.zip)

### 体验步骤

1. **下载压缩包**：点击上方链接，将 zip 压缩包下载到本地电脑（约 389 KB / 335 个文件）
2. **解压文件**：将下载的 zip 文件解压到任意目录（记住解压后的文件夹路径）
3. **下载微信开发者工具**：如尚未安装，请前往 [微信开发者工具官方下载页面](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html) 下载并安装
4. **打开微信开发者工具**：启动开发者工具，使用微信扫码登录
5. **导入项目**：
   - 点击开发者工具首页的「导入项目」（或「+」号）
   - 在「目录」栏点击浏览，选择第 2 步解压后的文件夹
   - 「AppID」栏可填入项目的 AppID，或选择「测试号」进行体验
   - 点击「导入」按钮
6. **预览体验**：导入成功后，开发者工具会自动编译并在模拟器中展示小程序界面
7. **重点验证**：
   - 进入「我的 → 订单」 → 已完成 Tab → 点击订单卡片右下角的「再来一单」按钮
   - 期望：弹 Toast「已为您带入原订单商品，请确认信息」 + 跳到 `/pages/checkout/index?product_id=xxx&from_rebuy=1`
   - 也可点击订单卡片进入详情页，底部应有绿色「再来一单」按钮

---

## 注意事项

1. **支付页字段需重新选择**：由于不复用门店/日期/时段/联系人/优惠券（避免老数据污染），用户进入支付页后需要重新选择这些字段才能下单。
2. **商品下架场景**：若商品已下架但订单仍是已完成/已过期状态，点击「再来一单」会 Toast 提示并停留原页，不会跳转。
3. **多商品订单**：若原订单含多个商品（多个 OrderItem），本次实现按 checkout 单品下单的产品现状，**取首个在售商品**带入支付页；后续若 checkout 升级为多品下单将自动支持。
4. **登录态过期**：H5 端会自动跳转登录页并在登录后回到订单列表；小程序与 APP 端会提示"请先登录"，需手动重新登录。
5. **iOS 端安装**：Apple 应用未上架商店时需要使用 AltStore / Sideloadly / Apple Configurator 等侧载工具，并在「设置 → 通用 → VPN 与设备管理」信任开发者证书。
6. **回滚预案**：如需回滚，仅需将 `unified_orders.py` 中 `reorder` 接口删除并恢复 H5 / 小程序 / Flutter 三端「再来一单」按钮跳转回原详情页即可（不影响其它订单功能）。
7. **后端无破坏性变更**：本次仅新增 `POST /api/orders/unified/{order_id}/reorder` 一个端点，未修改任何已有接口；不涉及订单数据模型变更；旧版客户端的「再来一单」按钮（跳详情页 + ?action=rebuy）仍可访问，只是不会触发任何效果（与修复前行为一致）。

---

## 自动化验收结果

部署后在服务器容器内运行 pytest 8 用例，**8/8 全部通过**：

| 编号 | 用例 | 结果 |
|------|------|------|
| case_01 | 全部商品在售 → status=all_available, 完整带入 | ✅ |
| case_02 | 商品已下架 → status=all_unavailable, reason=offline | ✅ |
| case_03 | 部分商品下架 → status=partial_filtered, 过滤下架项 | ✅ |
| case_04 | 商品在售但 SKU 停用 → reason=sku_offline | ✅ |
| case_05 | 订单不存在 → 404 | ✅ |
| case_06 | 未携带 token → 401/403 | ✅ |
| case_07 | 访问他人订单 → 404（按所有者过滤） | ✅ |
| case_08 | 商品被物理删除 → reason=deleted | ✅ |

HTTPS smoke 全部通过（H5 列表页 200 / 订单详情 chunks 含 `/reorder` 与 `from_rebuy`）。

---

## 修复后效果对照表

| 维度 | 修复前 | 修复后 |
|------|--------|--------|
| 跳转目的地 | 原订单详情页（错） | 新单支付页（对） |
| 商品是否带入 | ❌ 完全没有 | ✅ 商品 + SKU + 数量自动带入 |
| 字段清理 | N/A | ✅ 门店/日期/时段/联系人/备注/优惠券全部清空 |
| 全部商品下架 | ❌ 无兜底，照样跳详情 | ✅ Toast 提示 + 停留原页 |
| 部分商品下架 | ❌ 无兜底 | ✅ Toast 提示 + 自动过滤 + 跳支付页 |
| SKU 已停用 | ❌ 无兜底 | ✅ 自动过滤该项 |
| 登录态过期 | ❌ 无兜底 | ✅ 跳登录页 / Toast 提示 |
| 三端一致性 | ❌ 三端统一错 | ✅ 三端调用统一接口 |
| 入口完整性 | ⚠️ 仅订单列表有 | ✅ 列表 + 详情双入口 |
| 支付页轻提示 | ❌ 无 | ✅ Toast「已为您带入原订单商品」 |

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 项目主页面入口（经 Nginx 代理，端口 80） |
| H5 我的订单 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/unified-orders/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/unified-orders/) | 订单列表页（已完成 / 已过期订单可见「再来一单」） |
| H5 登录 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/login/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/login/) | 用户登录入口 |
| 微信小程序代码下载 | [miniprogram_rebuy_20260507_154249_5fbd.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_rebuy_20260507_154249_5fbd.zip) | 微信小程序代码包，导入【微信开发者工具】体验 |
