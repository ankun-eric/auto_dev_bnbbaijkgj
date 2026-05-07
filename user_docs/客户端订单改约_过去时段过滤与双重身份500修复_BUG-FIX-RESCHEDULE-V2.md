# 客户端订单改约｜过去时段过滤 + 双重身份 500 修复 用户体验使用手册

> 版本：BUG-FIX-RESCHEDULE-V2 · 2026-05-07
>
> 本次修复一次性覆盖三端：H5 顾客端、微信小程序顾客端、Flutter 安卓 / iOS APP 顾客端，
> 并强化后端鉴权与异常兜底，让"改约"从此不再出现「改约失败（500）」之类的通用兜底。

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| 顾客端 H5 主页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 项目主页面入口（经 Nginx 代理，端口 80） |
| 顾客端 H5 登录 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/login](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/login) | 顾客手机号登录入口 |
| 顾客端 H5 我的订单 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/unified-orders](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/unified-orders) | 在订单列表 / 详情页发起【改约】 |
| 微信小程序 zip 下载 | [miniprogram_bug403_20260507_171804_c6c0.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_bug403_20260507_171804_c6c0.zip) | 小程序源码包，导入【微信开发者工具】体验 |

---

## 功能简介

本次更新一次性解决了顾客端订单【改约】的两个互相耦合的 Bug：

1. **过去时段过滤**：在改约弹窗中切换到「今天」时，**已经过去的整段时段会自动隐藏**，而不是依然出现在 9 段时段池里被错点。例如当前是 14:30，13:00–14:00 这段已结束的时段会从列表中消失，14:00–15:00 起才显示。
2. **双重身份用户改约 500 失败**：如果同一个手机号既绑定了顾客账号、也绑定了商家账号（"双重身份用户"，例如门店店长 / 加盟商业主），过去在客户端点【改约】会弹出「改约失败（500）」。本次彻底修好——双重身份用户在客户端给自己的订单改约现在与纯顾客一样能用，**且不卡改约次数**。

此外还做了几项相关增强：

- **服务器时间接口**：新增 `GET /api/system/server-time`，三端改约弹窗在打开时会请求一次该接口，按"服务器时间"决定哪些时段算"已过去"，避免本地时间被人为调快/调慢绕过过滤。
- **结构化错误兜底**：改约接口任何分支抛出的未知异常（数据库错误、空指针等）都会被统一包成 `RESCHEDULE_INTERNAL_ERROR` 结构化响应。三端不再展示「改约失败（500）」字样，改为「改约处理异常，请稍后重试或联系客服」。
- **请求头透传强化**：H5 / 小程序 / Flutter 三端的全局请求拦截器都会强制注入 `X-Client-Source` 顾客端入口标识，token 刷新重试时也保持透传，**列表入口和详情入口收口走同一改约模块**，杜绝任何漏头。
- **UA 兜底放行**：万一某个客户端入口漏写了 `X-Client-Source` 头（如旧版本 App），后端按 User-Agent 推断为移动端时也按顾客侧入口放行，避免硬性 403。
- **后端二次过期校验**：即便前端时间被人为篡改提交"今天的过去时段"到后端，后端会按服务器时间再校验一次，返回 `RESCHEDULE_TIME_EXPIRED`，与前端隐藏过去时段构成"双保险"。

---

## 本次客户端变更

本次更新涉及以下终端的代码改动，请下载/刷新最新版本体验：

| 终端 | 变更说明 | 新版本下载 / 刷新方式 |
|------|----------|------------------------|
| H5 顾客端 | 改约弹窗按服务器时间过滤已过去时段 + 今天空状态文案与一键跳明天按钮 + 错误码映射文案 | [访问 H5 我的订单](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/unified-orders)（已自动更新，浏览器强制刷新即可） |
| 微信小程序顾客端 | 改约弹窗时段过滤 + `request.js` 已注入 `X-Client-Source: miniprogram-customer` + 错误码映射 | [miniprogram_bug403_20260507_171804_c6c0.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_bug403_20260507_171804_c6c0.zip) |
| Flutter 安卓 APP（如需重新打包） | `Dio` 已注入 `X-Client-Source: flutter-customer`、新增 `ServerTimeService`、改约弹窗时段过滤 | 通过 [GitHub Actions android-build](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/actions/workflows/android-build.yml) 手动触发构建（远程 GitHub 网络受限期间，可在网络恢复后再触发） |
| Flutter iOS APP（如需重新打包） | 同上 | 通过 [GitHub Actions ios-build](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/actions/workflows/ios-build.yml) 手动触发构建 |

> ⚠️ 后端改动随容器热更新，前端 H5 已重建上线，浏览器强制刷新（Ctrl+F5 / Cmd+Shift+R）即可获得新版。

---

## 使用说明

### 场景 A：在 H5 顾客端改约

1. 在浏览器打开 [H5 我的订单页](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/unified-orders)，用顾客手机号登录。
2. 找到一笔已支付且已选时段的预约订单，点击列表中的【改约】按钮，或点击订单进入详情页后再点底部的【改约】按钮——两种入口走同一弹窗。
3. 在弹窗里：
   - 选「明天」：所有 9 段时段都会显示，可任意挑选。
   - 选「今天」：**只会显示当前时间还没结束的时段**。例如当前 14:30，13:00–14:00 不再显示，14:00–15:00 起才显示。
   - 如果"今天剩余时段已过"，弹窗会显示空状态文案「今日剩余时段已过，请选择明天起的日期」+ 一个【一键切到明天】按钮，点击立即帮你把日期切到明天。
4. 选好「明天起 90 天内的某一天 + 9 段时段中的某一段」后，点击【确认改期】。
5. 改约成功 Toast 提示「预约成功」，订单详情自动刷新。

### 场景 B：在微信小程序改约

1. 用【微信开发者工具】导入上方下载的小程序代码包，编译后用顾客手机号登录。
2. 进入【我的订单】，点击列表里某笔订单，进入详情页底部的【改约】按钮。
3. 弹窗交互与 H5 一致：今天只显示未过去的时段、剩余时段已过则显示空状态 + 一键跳明天按钮、错误统一展示具体业务文案。
4. 选好后点【确认改期】，吐司「预约成功」。

### 场景 C：在 Flutter App 改约

1. 安装最新的 Android APK 或 iOS IPA（如尚未触发 GitHub Actions 构建，可继续使用上一版本——本次后端兼容旧版前端的 `X-Client-Source` 缺失场景，UA 兜底会放行）。
2. 进入【我的订单】，找到一笔已支付订单，点击【改约】。
3. 弹窗交互与 H5 / 小程序一致。

### 改约错误文案对照（不再有「改约失败（500）」）

| 后端错误码 | 用户看到的文案 |
|-------------|----------------|
| `RESCHEDULE_NO_PERMISSION` | 无权操作此订单 |
| `RESCHEDULE_ORDER_NOT_FOUND` | 订单不存在或无权操作此订单 |
| `RESCHEDULE_ORDER_STATUS_INVALID` | 当前订单状态不允许改约 |
| `RESCHEDULE_LIMIT_EXCEEDED` | 该订单已达改约次数上限，无法继续改约 |
| `RESCHEDULE_NOT_ALLOWED` | 该商品不支持改约 |
| `RESCHEDULE_TIME_EXPIRED` | 所选时段已过期，请选择未来时间 |
| `RESCHEDULE_TIME_OUT_OF_RANGE` | 所选日期超出可改约范围 |
| `RESCHEDULE_TIME_CONFLICT` | 所选时段已被预约满，请选其他时段 |
| `RESCHEDULE_REFUND_IN_PROGRESS` | 该订单退款处理中，暂不允许调整预约时间 |
| `RESCHEDULE_PARTIALLY_USED` | 该订单已部分核销，无法修改预约时间 |
| `RESCHEDULE_INTERNAL_ERROR` | 改约处理异常，请稍后重试或联系客服（**取代旧版「改约失败（500）」**） |

---

## 微信小程序体验

### 下载小程序代码

点击以下链接下载微信小程序代码压缩包：

> 📦 下载地址：[miniprogram_bug403_20260507_171804_c6c0.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_bug403_20260507_171804_c6c0.zip)

### 体验步骤

1. **下载压缩包**：点击上方链接，将 zip 压缩包下载到本地电脑。
2. **解压文件**：将 zip 解压到任意目录（记住解压后的文件夹路径）。
3. **安装微信开发者工具**：如尚未安装，前往 [微信开发者工具官方下载页面](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html)。
4. **打开微信开发者工具**：使用微信扫码登录开发者工具。
5. **导入项目**：
   - 点击工具首页的【导入项目】（或【+】号）。
   - 「目录」选择第 2 步解压后的文件夹（注意：要选到 `miniprogram/` 这一层）。
   - 「AppID」填写项目的真实 AppID 或选择「测试号」。
   - 点击【导入】。
6. **预览体验**：导入后会自动编译。在模拟器中按提示登录顾客手机号，进入【我的订单】，对一笔已支付的订单点【改约】，验证：
   - 改约弹窗打开后，切到「今天」时已过去的时段不再出现；
   - 「今天」剩余时段都过去时显示空状态 + 一键跳明天；
   - 双重身份用户（同时是商家与顾客）改约能成功。

---

## 注意事项

1. **服务器时间是改约的"权威时间"**：弹窗里能选哪些时段以服务器时间为准；如果你的手机/电脑时间被人为调快了几小时甚至几天，改约弹窗仍然按服务器时间隐藏过去时段。
2. **网络异常时的降级**：如果服务器时间接口偶发不可达，弹窗顶部会出现红字「网络异常，时段以服务器为准；如改约失败请重试」。此时弹窗会临时降级为本地时间过滤，提交时由后端再次校验，必要时会返回 `RESCHEDULE_TIME_EXPIRED`，请刷新弹窗重试。
3. **「一键切到明天」是引导，不是强制**：点击后日期会自动切到明天，但你仍可继续选其他更晚的日期。
4. **改约范围还是「明天起 90 天」**：本次修复**不更改** PRD-03 既定的"明天起 90 天"改期日期范围。「今日空状态文案」只是为了在用户不小心点了"今天"时给出友好引导。
5. **双重身份用户在客户端为自己改约不再卡次数**：本规则沿袭上一轮 BUG-FIX-RESCHEDULE-DUAL-IDENTITY-V1 的承诺，纯顾客仍受 `reschedule_limit` 限制。
6. **越权防护仍然在**：双重身份用户改不到他人订单，会返回 `RESCHEDULE_ORDER_NOT_FOUND`。
7. **建议刷新 / 重新打包**：H5 已自动上线，浏览器强制刷新即可；小程序请下载上方 zip 重新导入；Flutter App 端如需重打包请通过 GitHub Actions 手动触发。

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| 顾客端 H5 主页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 项目主页面入口（经 Nginx 代理，端口 80） |
| 顾客端 H5 登录 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/login](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/login) | 顾客手机号登录入口 |
| 顾客端 H5 我的订单 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/unified-orders](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/unified-orders) | 在订单列表 / 详情页发起【改约】 |
| 微信小程序 zip 下载 | [miniprogram_bug403_20260507_171804_c6c0.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_bug403_20260507_171804_c6c0.zip) | 小程序源码包，导入【微信开发者工具】体验 |

## 微信小程序体验

### 下载小程序代码

点击以下链接下载微信小程序代码压缩包：

> 📦 下载地址：[miniprogram_bug403_20260507_171804_c6c0.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_bug403_20260507_171804_c6c0.zip)

### 体验步骤

1. 下载压缩包并解压到任意目录。
2. 打开【微信开发者工具】，点击【导入项目】，选择解压后的 `miniprogram/` 目录。
3. AppID 选填（可用「测试号」），点击【导入】完成。
4. 自动编译后，模拟器中登录顾客手机号 → 进入【我的订单】 → 选一笔订单点【改约】 → 验证今天过去时段不显示、空状态 + 一键跳明天、双重身份用户改约成功。
