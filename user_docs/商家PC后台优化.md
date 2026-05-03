# 商家 PC 后台优化使用手册（v1.1）

> 本次为「商家 PC 后台」用户体验优化版本，重点解决：订单状态展示与用户端不一致、订单列表字段拥挤、附件上传体验差、预约日历英文化、日历详情遮挡日历等问题。

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| 项目主页面（用户端 H5） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 用户端 H5 入口 |
| 商家 PC 后台 - 订单管理 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/orders](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/orders) | 本次优化主战场之一 |
| 商家 PC 后台 - 预约日历 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/calendar](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/calendar) | 本次优化主战场之二 |
| 商家手机端 H5 - 订单 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/m/orders](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/m/orders) | 移动端同步状态映射 |
| 平台后台 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/) | 平台运营管理 |

---

## 功能简介

本次主要优化了商家 PC 后台的「订单管理」与「预约日历」两个模块，并同步修复了商家手机端 H5 的状态展示不一致问题：

1. **订单状态展示完全对齐用户端**：商家端原本只显示 5 个状态（很多英文裸值漏出），现已补齐为系统真实使用的 14 个状态，文案与颜色与用户端 H5、小程序、APP 完全一致。
2. **订单列表新布局**：左侧固定订单号/下单时间/商品名，右侧固定状态/操作，中间字段（用户、手机号、金额、支付方式、核销码、门店、预约时间、附件数）支持横向滚动，每行加高 8px，告别拥挤。
3. **附件上传焕然一新**：把简陋的 URL 输入框改成 Antd 上传组件，支持 jpg/png/pdf 三种格式，单文件 ≤ 5MB，单订单最多 9 个附件，图片可预览、PDF 可下载。
4. **预约日历完全中文化**：去掉年份选择器，月份名改为「一月/二月…十二月」，星期改为「周一/周二/周三/周四/周五/周六/周日」。
5. **日历详情面板从下方挪到右侧**：点击日历中的预约后，详情以右侧 400px 侧滑面板的形式展示，不再遮挡日历视图，支持 ESC、点击空白、点击 × 关闭。
6. **历史数据自动迁移**：后端在启动时自动把所有 `redeemed` 状态的旧订单合并到 `completed`（已完成）状态；筛选器中已不再暴露 `redeemed`、`paid` 等历史值。

> 全程仅修改了「商家 PC 后台」「商家手机端 H5」「后端 API + 启动迁移」三处代码，用户端（小程序/H5/APP）无需任何更新。

---

## 使用说明

### 一、商家 PC 后台 - 订单管理

1. 访问 [商家 PC 后台 - 订单管理](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/orders) ，使用商家账号登录。
2. **筛选器（顶栏）**：
   - 关键字搜索（订单号 / 商品名）
   - 状态下拉：仅展示 6 个常用项 — 待付款 / 待发货 / 待核销 / 已完成 / 已退款 / 已取消（不再出现 `redeemed`、`paid` 等英文混乱值）
   - 日期范围筛选
3. **订单列表**：
   - **左侧固定**：订单号、下单时间、商品名称（保证横滚时关键信息不丢失）
   - **中间横滚区**：用户、手机号、金额、支付方式（如「微信支付（小程序）」）、核销码、门店、预约时间、附件数
   - **右侧固定**：状态（彩色 Tag）、操作（详情 / 附件）
   - 行高已加大，字段间不再拥挤
4. **状态文案**：和用户端完全一致 —— 待付款 / 待发货 / 待收货 / 待预约 / 待核销 / 部分核销 / 待评价 / 已完成 / 已过期 / 退款中 / 已退款 / 已取消，全部中文，无英文裸值。
5. **订单详情**：点击「详情」按钮 → 右侧抽屉展示完整信息 + 备注列表 + 添加备注 + 调整预约时间。

### 二、商家 PC 后台 - 附件上传（新版）

1. 在订单列表点击某行的「附件」按钮 → 弹出附件管理弹窗。
2. **附件列表**：
   - 图片附件：左侧缩略图，可点击预览
   - PDF 附件：左侧 PDF 图标，可点击下载
   - 每条都可删除（带二次确认）
3. **上传新附件**：
   - 点击「选择文件上传」按钮，从本地选择 jpg、png 或 pdf 文件
   - **限制**：单文件不超过 5MB；单订单最多 9 个附件；超出会前端立即提示并拦截
   - 上传成功后会立即刷新列表，订单列表中的附件计数也同步更新
4. **不再需要外部 OSS**：服务器内置静态文件存储，文件直接通过浏览器可下载/预览。

### 三、商家 PC 后台 - 预约日历（中文化 + 右侧面板）

1. 访问 [商家 PC 后台 - 预约日历](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/calendar) 。
2. **日历顶栏**（已优化）：
   - 左：「← 上月」按钮
   - 中：「2026 年 五月」（中文月份名）
   - 右：「下月 →」按钮
   - **不再有年份下拉**
3. **星期行**：周一 / 周二 / 周三 / 周四 / 周五 / 周六 / 周日（替换默认的 Mo/Tu/We…）
4. **日历单元格**：
   - 显示「共 N 个预约」
   - 三色块（绿/橙/红）分别对应上午/下午/晚间的密度
5. **当日预约列表**：点击某天后，下方卡片改为「卡片栅格」展示每个预约（更醒目），点击任意预约卡片即弹出右侧侧滑面板。
6. **右侧侧滑面板（新）**：
   - 宽度 400px，从右侧滑入，**不遮挡日历**
   - 内容：预约人、电话、预约项目、预约时间、备注、订单号、预约状态
   - 底部仅一个主按钮「**查看订单详情**」，点击跳转到订单管理页（`/merchant/orders?highlight=<订单ID>`）
   - **三种关闭方式**：① 点击右上角 × ② 按 ESC 键 ③ 点击面板外的灰色蒙层
   - 不放置核销 / 取消 / 呼叫等敏感操作（避免误触）

### 四、商家手机端 H5（同步状态映射）

1. 访问 [商家手机端订单](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/m/orders) （建议在手机浏览器中打开）。
2. **顶部 Tab**已改为：全部 / 待付款 / 待发货 / 待核销 / 已完成 / 已退款（与 PC 端 6 个常用状态对齐）。
3. **状态色块** 颜色与文案与用户端 H5 完全一致，避免商家与用户对话时鸡同鸭讲。
4. 点击单条订单进入详情页，状态徽章/操作按钮与新映射对齐。

---

## 注意事项

1. **首次部署后会自动执行一次性数据迁移**：把所有历史 `redeemed` 状态的订单刷为 `completed`。该迁移**幂等可重入**，无需手动触发，也不会重复处理。
2. **历史 `paid` 状态保留兼容映射**：旧的、个别仍处于 `paid` 状态的订单在详情/列表中显示为「待核销」，但筛选下拉中不再暴露此选项。
3. **附件上传当前使用宿主静态目录**：服务器重建容器时不会丢失（已挂载到宿主磁盘）。如未来要切换到 OSS / S3，只需替换 `/api/merchant/orders/{id}/attachments/upload` 接口的存储实现，前端无须改动。
4. **前端 URL 路径**：商家 PC 路径统一在 `/merchant/*`，商家手机端在 `/merchant/m/*`，二者已分别采用 PC 与移动端样式。
5. **登录态隔离**：商家手机端使用独立 token；如同时在 PC 与手机两端使用，请分别登录。
6. **状态文案与颜色统一规范**：

| 英文枚举 | 中文文案 | 颜色 |
|---|---|---|
| pending_payment | 待付款 | #fa8c16 |
| pending_shipment | 待发货 | #1890ff |
| pending_receipt | 待收货 | #13c2c2 |
| pending_appointment | 待预约 | #722ed1 |
| appointed | 待核销 | #13c2c2 |
| pending_use | 待核销 | #13c2c2 |
| partial_used | 部分核销 | #faad14 |
| pending_review | 待评价 | #eb2f96 |
| completed | 已完成 | #52c41a |
| expired | 已过期 | #8c8c8c |
| refunding | 退款中 | #f5222d |
| refunded | 已退款 | #8c8c8c |
| cancelled | 已取消 | #8c8c8c |

> 商家与用户端打开同一订单，看到的状态文字与颜色**完全一致**。

---

## 验证清单（验收时可参照）

- ✅ 商家 PC 任意订单状态展示均为中文，无英文裸值
- ✅ 同一订单在商家 PC、商家手机、用户端的状态文案一致
- ✅ 商家 PC 订单列表无横向挤压，订单号/下单时间/商品名 左固定，状态/操作 右固定
- ✅ 附件上传支持 jpg/png/pdf，单文件 5MB 超限有提示，最多 9 个附件
- ✅ 日历顶部无年份选择器，月份「一月/二月…十二月」、星期「周一/周二…周日」中文化
- ✅ 点击日历预约后右侧 400px 侧滑面板弹出，不遮挡日历，支持 ESC / × / 点击空白关闭
- ✅ 数据库无 `redeemed` 状态残留（启动迁移自动清理），筛选器不再出现 `redeemed`/`paid`
- ✅ 服务器容器内 `pytest tests/test_merchant_pc_optim_v1_1.py`：**11/11 全通过**
- ✅ 全量回归（含支付配置 + 状态简化）：**34/34 全通过**

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| 项目主页面（用户端 H5） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 用户端 H5 入口 |
| 商家 PC 后台 - 订单管理 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/orders](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/orders) | 本次优化主战场之一 |
| 商家 PC 后台 - 预约日历 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/calendar](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/calendar) | 本次优化主战场之二 |
| 商家手机端 H5 - 订单 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/m/orders](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/m/orders) | 移动端同步状态映射 |
| 平台后台 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/) | 平台运营管理 |
