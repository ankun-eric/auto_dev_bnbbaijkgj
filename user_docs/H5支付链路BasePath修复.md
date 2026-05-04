# H5 支付链路 BasePath 修复 — 用户体验使用手册

> 修复日期：2026-05-04
> 修复范围：H5 端 + 后端（无小程序 / 安卓 / iOS 端代码改动）

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），并保留 `/autodev/<uuid>/` 子路径前缀。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 主页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 项目主页面入口 |
| H5 下单页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/checkout](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/checkout) | 下单结算页（修复后跳转支付不再丢前缀） |
| 支付宝沙盒收银台 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/sandbox-pay/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/sandbox-pay/) | 支付宝沙盒收银台（自测桩，需带 order_no/channel 查询参数） |
| H5 支付成功页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/pay/success](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/pay/success) | 支付完成回跳页（防伪造重定向） |
| H5 订单列表 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/unified-orders](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/unified-orders) | 我的订单列表 |
| H5 登录页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/login](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/login) | 用户登录入口 |

## 功能简介

本次修复彻底解决了 H5 项目部署在 `/autodev/<uuid>/` **临时体验链接**子路径下时，**支付链路整体错乱**的问题：

**原 Bug 现象**：
- 在 H5 内点击「立即支付」跳支付宝沙盒收银台 → 浏览器把 `pay_url` 拼成根域 URL（如 `https://newbb.test.bangbangvip.com/sandbox-pay`），**丢掉了 `/autodev/<uuid>` 前缀**
- 落到了 **同域名下另一个项目** 的页面，看到 "路由 OK" 等无关文案
- 支付完成后回跳同样错位，订单状态展示丢失

**修复后效果**：
- 所有内部跳转、静态资源、API 请求、支付跳转、支付回跳 **全部正确保留 `/autodev/<uuid>` 前缀**
- 支付宝沙盒收银台正常访问，支付完成后回跳到本项目的「支付成功页」
- **前向兼容**：未来切换为根域名 / 独立子域名（如 `h5.xxx.com`），只需改一个配置项 `PROJECT_BASE_URL` + `NEXT_PUBLIC_BASE_PATH`，业务代码零改动

## 本次客户端变更

本次更新仅涉及 **H5 端 + 后端容器** 的代码改动，**微信小程序 / 安卓 APP / 苹果 APP 本期零改动**，可继续使用上一版本（[小程序 zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_slot_badge_20260504_162603_bea2.zip) / [APK](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/bini_health_slotbadge_20260504_162352_25e8.apk) / [IPA](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ipa/bini_health_slotbadge_20260504_162337_0e07.ipa)）。

| 终端 | 变更说明 | 新版本下载 |
|------|----------|------------|
| H5 端（Web） | 新增 `withBasePath` / `redirectToPayUrl` 工具函数；checkout、unified-order、auth 三处统一使用安全跳转工具，`/sandbox-pay` 不再丢前缀 | 直接刷新 H5 链接即可（[https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/)） |
| 后端 API | `_build_sandbox_pay_url` 强化兼容三级 base 取值；docker-compose 新增 `PROJECT_BASE_URL` 环境变量；pay_url 现在带完整域名+basePath | 已随容器自动更新 |

> ⚠️ H5 端无需安装包，直接刷新浏览器即可使用最新版本（建议清浏览器缓存）。

## 使用说明

### 步骤 1：进入 H5 主页
浏览器打开 [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/)，正常进入首页（地址栏保持 `/autodev/<uuid>/` 前缀）。

### 步骤 2：登录账号
点击「我的」或任何需登录的入口，跳转到 [/login](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/login)，使用手机号 + 验证码登录。

### 步骤 3：选择商品下单
1. 浏览首页或点击「服务」、「商品」入口选择商品
2. 进入下单页 [/checkout](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/checkout)，选择门店 / 时段 / 联系方式
3. 选择支付方式（**支付宝（H5）**），点击「立即支付」

### 步骤 4：支付（关键修复点）
1. 点击「立即支付」后，H5 自动调用后端 `/api/orders/unified/{id}/pay`
2. 后端返回的 `pay_url` 现在是完整 URL：
   `https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/sandbox-pay?order_no=...&channel=alipay_h5`
3. 浏览器跳转到支付宝沙盒收银台（**注意 URL 中 `/autodev/<uuid>/` 前缀完整保留**）
4. 在沙盒收银台点「确认支付」即可模拟完成支付

### 步骤 5：支付完成
1. 沙盒收银台确认成功后，自动跳转到 [/pay/success?orderId=xxx](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/pay/success)
2. 显示绿色对勾、实付金额、订单信息卡
3. 可点击「查看订单详情」或「返回首页」继续操作

### 步骤 6：浏览器后退测试（防伪造）
- 在支付成功页按浏览器后退键 → 应直接跳到 H5 首页（不会回到下单页或沙盒页）
- 直接 URL 访问 `/pay/success`（不带参数） → 自动重定向到订单列表
- 直接 URL 访问 `/pay/success?orderId=不存在的id` → Toast 提示后重定向

## 注意事项

1. **临时体验链接说明**：本项目目前部署在 `https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/` 这个 **临时体验链接**下；未来切换为根域名 / 独立子域名（如 `h5.xxx.com`）时，业务代码零改动，只需修改部署配置中的 `NEXT_PUBLIC_BASE_PATH` 和 `PROJECT_BASE_URL` 两个环境变量。

2. **支付环境**：本次使用的是 **支付宝沙盒桩 URL**（开发自测），不是真实生产支付宝；接入真实商户证书后，`pay_url` 会替换为支付宝官方收银台，**本次修复对真实支付宝同样有效**（真实 `pay_url` 是完整跨域 URL，`redirectToPayUrl` 工具会原样跳转）。

3. **浏览器缓存**：如果之前已经打开过 H5，建议**强制刷新**（Ctrl+F5 / Cmd+Shift+R）以加载最新前端代码。

4. **正常 401 跳登录**：未登录访问需要登录的接口，H5 会自动跳到 [/login](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/login)（带 `/autodev/<uuid>/` 前缀）；修复前可能错误跳到根域 `/login`。

5. **不影响小程序 / APP**：本次仅 H5 + 后端容器变更，微信小程序、安卓、苹果 App 端**完全不受影响**，无需重新下载安装。

## 修复验证清单（已通过）

| 序号 | 验证项 | 实际结果 |
|------|--------|----------|
| 1 | 直接打开临时体验链接根路径 | ✅ 200，地址栏保持 `/autodev/<uuid>/` 前缀 |
| 2 | F12 看 `_next` 静态资源请求 | ✅ 全部带 `/autodev/<uuid>/_next/...` 前缀 |
| 3 | 进入 checkout 下单 | ✅ 留在 `/autodev/<uuid>/checkout`，308 trailing slash |
| 4 | 后端构造 pay_url（PROJECT_BASE_URL 已配置） | ✅ `https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/sandbox-pay?...` |
| 5 | 沙盒收银台页面访问 | ✅ 200，资源带正确前缀 |
| 6 | 支付完成自动回跳 | ✅ 落到 `/autodev/<uuid>/pay/success`，**不再** 看到根域"路由 OK"页 |
| 7 | H5 内 router.push / Link / 401 跳 login | ✅ 全部留在 `/autodev/<uuid>/...` 子路径下 |
| 8 | 模拟把 `BASE_PATH` 配成空串 | ✅ 工具函数逻辑测试通过，前向兼容 OK |

## 访问链接

以下是当前项目的体验链接，点击即可打开：

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 主页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 项目主页面入口 |
| H5 下单页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/checkout](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/checkout) | 下单结算页（修复后跳转支付不再丢前缀） |
| 支付宝沙盒收银台 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/sandbox-pay/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/sandbox-pay/) | 支付宝沙盒收银台（自测桩，需带 order_no/channel 查询参数） |
| H5 支付成功页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/pay/success](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/pay/success) | 支付完成回跳页（防伪造重定向） |
| H5 订单列表 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/unified-orders](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/unified-orders) | 我的订单列表 |
| H5 登录页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/login](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/login) | 用户登录入口 |
