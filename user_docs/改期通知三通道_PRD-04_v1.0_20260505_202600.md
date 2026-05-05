# 改期通知三通道（小程序订阅 + APP push + 短信）使用手册

> 文档版本：v1.0  &nbsp;&nbsp; 撰写时间：2026-05-05  &nbsp;&nbsp; 适用 PRD：PRD-04 改期通知三通道

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 用户端首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 顾客在此发起改期 |
| H5 商家端预约日历 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/calendar/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/calendar/) | 店长在 PC 端浏览所有改期记录 |
| H5 商家手机端首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/m/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/m/) | 店长在手机端进入订单详情查看「通知状态」 |
| Admin 登录 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/) | 平台运营后台，可配置通知凭证 |

---

## 功能简介

本次发布完整落地 PRD-04「改期通知三通道」，确保**顾客改期成功后能真正知道新预约时段**，避免「客户按原时段到店、商家按新时段安排」的事故。

核心特性：

1. **三通道并行下发**：改期成功后**同时**触发微信小程序订阅消息、APP push、短信，**互不阻塞、任一成功即视为可触达**
2. **失败重试**：短信通道自带 1 次重试（间隔 0.5 秒）
3. **接口同步返回 `notify_result`**：客户端改期接口返回值中携带三通道下发结果，前端可即时反馈
4. **商家详情页通知状态**：店长在订单详情页可一眼看到「已通知 / 通知发送异常，请联系客户」状态及各通道明细
5. **三通道全失败 → 企业微信群机器人告警**：自动通知运营，运营人工电话联系客户兜底，杜绝「无通知失误」
6. **统一文案**：三通道发出同一份「【XX 健康】您预约的「{服务项目名}」已改期：原 {原时段}，现 {新时段}…」

---

## 使用说明

### 顾客端：发起改期

1. 在 [H5 用户端首页](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) 登录后，进入「我的订单」打开任一已预约订单
2. 点击「修改预约」按钮（仅顾客端可见，商家端无此入口——改期权已收归客户端）
3. 选择新的预约日期（明天起 90 天内）和时段，点击确认
4. 改期成功后，页面会展示三通道下发结果（小程序订阅 / APP push / 短信，每个通道独立提示）
5. 同时，您会**几乎同时收到**：
   - 微信小程序「服务通知」中的订阅消息推送（前提：改期当下已点击「同意接收订阅消息」）
   - APP 推送通知（前提：APP 已安装并允许通知）
   - 短信（前提：账号绑定了正确的手机号）
6. 三个渠道任一收到即可放心，到点凭新时段到店即可

> 即使三个渠道都没收到（例如同时未授权小程序订阅、未装 APP、手机号填错），运营会通过企业微信群机器人告警**主动电话联系您**确认改期信息，无需担心信息遗漏。

### 商家端：在订单详情查看通知状态

1. 在 [H5 商家手机端首页](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/m/) 登录后，进入「订单」列表
2. 点开任一**最近被顾客改过期**的订单，进入「订单详情」页
3. 在订单基本信息卡片之下，可看到独立的**通知状态卡片**：
   - 绿色 ✓「已通知」：三通道至少有一个下发成功，无需操作
   - 红色 ⚠️「通知发送异常，请联系客户」：三通道全部失败，需要店长**主动电话联系顾客**确认改期信息
4. 卡片中按通道（微信订阅消息 / APP push / 短信）逐一展示「✓ 成功 / ✗ 失败」状态以及失败原因摘要
5. 红色异常状态下还会提示：「运营已收到企业微信告警，请人工电话联系客户兜底」

### 运营端：配置通知凭证

所有凭证从环境变量 / 配置中心读取（不写死代码）：

| 通道 | 必填环境变量 | 说明 |
|------|--------------|------|
| 微信小程序订阅消息 | `WECHAT_MINI_APP_ID` / `WECHAT_MINI_APP_SECRET` / `WECHAT_RESCHEDULE_TEMPLATE_ID` | 小程序「服务通知」改期模板 |
| APP push（极光为例） | `APP_PUSH_PROVIDER=jpush` / `JPUSH_APP_KEY` / `JPUSH_MASTER_SECRET` | 留空则该通道直接跳过，不阻塞其他 |
| 短信 | `RESCHEDULE_SMS_TEMPLATE_ID` | 复用现有腾讯云 / 阿里云短信通道 |
| 企业微信告警 | `WECHAT_WORK_ALERT_WEBHOOK` | 群机器人 webhook URL，三通道全失败时触发 |
| 通知抬头（可选） | `NOTIFY_BRAND_NAME` | 例如 `XX 健康` |

> **关键约束**：未配置任何凭证时，对应通道会返回 `ok=false, detail="凭证未配置"`，但**不抛异常、不阻塞改期主流程**。改期接口仍然 200 返回，订单时间已写入数据库。

---

## 通知文案模板

三通道统一发出以下文案（变量自动替换）：

> 【XX 健康】您预约的「{服务项目名}」已改期：原 {原时段}，现 {新时段}，门店：{门店名}。如有疑问请联系门店：{门店电话}。

变量来源：
- `{服务项目名}` ← `unified_orders.product_name`
- `{原时段}` ← 改期前的 `appointment_time` 格式化（如 `05月06日 10:00-12:00`）
- `{新时段}` ← 改期后的 `appointment_time` 格式化
- `{门店名}` ← `stores.name`
- `{门店电话}` ← `stores.phone`

---

## 接口返回示例

客户端改期接口 `PUT /api/orders/{id}/reschedule`（即 `POST /api/orders/unified/{id}/appointment` 的改期分支）成功后，返回值的 `notify_result` 字段：

```json
{
  "message": "预约已确认",
  "status": "pending_use",
  "appointment_time": "2026-05-07T14:00:00",
  "reschedule_count": 1,
  "reschedule_limit": 3,
  "notify_result": {
    "channels": [
      { "name": "wechat_subscribe", "ok": true,  "detail": "订阅消息已下发" },
      { "name": "app_push",         "ok": false, "detail": "APP push 服务商未配置" },
      { "name": "sms",              "ok": true,  "detail": "短信已下发" }
    ],
    "any_ok": true,
    "all_failed": false
  }
}
```

三通道全部失败时，返回值还会带上企业微信告警结果：

```json
{
  "notify_result": {
    "channels": [
      { "name": "wechat_subscribe", "ok": false, "detail": "凭证未配置" },
      { "name": "app_push",         "ok": false, "detail": "服务商未配置" },
      { "name": "sms",              "ok": false, "detail": "短信发送失败（已重试 1 次）" }
    ],
    "any_ok": false,
    "all_failed": true,
    "wechat_work_alert": { "ok": true, "detail": "企业微信告警已发送" }
  }
}
```

---

## 异常处理矩阵

| 场景 | 系统行为 |
|------|----------|
| 三通道全部失败 | 订单详情页红色「通知发送异常，请联系客户」+ 企业微信群机器人告警 + 运营电话兜底 |
| 客户未授权小程序订阅 | 该通道直接 `ok=false`（detail：用户未授权小程序），其他两通道继续下发 |
| 客户未安装 APP | APP push 通道返回 `ok=false`（detail：服务商未配置 / 用户无 token），其他两通道正常下发 |
| 客户手机号格式错误 | 短信通道重试 1 次仍失败 → `ok=false`，记录日志；其他两通道继续下发 |
| `APP_PUSH_PROVIDER` 为空 | APP push 通道直接跳过（detail：服务商未配置），其他两通道正常 |
| 微信 access_token 拉取失败 | 该通道 `ok=false`（detail：access_token 获取失败），不影响其他通道 |
| 企业微信 webhook 网络异常 | 仅记录日志（`logger.warning`），不影响主流程，订单仍按 200 返回 |

---

## 自动化测试结果（2026-05-05 部署后实测）

服务器容器内执行：

```bash
docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend python -m pytest \
  tests/test_prd04_reschedule_notify_v1.py \
  tests/test_reschedule_notification_v1.py \
  -v --noconftest -p no:cacheprovider
```

结果：**29 / 29 PASS in 1.08s** ✅

测试分布：
- **PRD-04 新增 11 个 case**：
  - `test_wechat_work_alert_no_webhook`：未配置 webhook 直接 `ok=false`
  - `test_wechat_work_alert_explicit_webhook_phone_masked`：手机号中间四位被遮蔽（`139****4321`）
  - `test_wechat_work_alert_http_error_returns_ok_false`：webhook HTTP 500 → `ok=false`
  - `test_wechat_work_alert_errcode_nonzero_returns_ok_false`：webhook 返回 errcode≠0 → `ok=false`
  - `test_all_failed_triggers_wechat_work_alert`：三通道全失败时**确实调用**企业微信告警一次
  - `test_partial_success_does_NOT_trigger_alert`：任一通道成功即**不**触发告警
  - `test_all_failed_alert_exception_is_swallowed`：告警自身异常不阻塞主流程
  - `test_to_dict_no_alert_when_no_failure` / `test_to_dict_includes_alert_when_attached`：`to_dict()` 字段输出
  - `test_alert_short_phone_no_mask_crash` / `test_alert_empty_phone_no_crash`：手机号边界数据不崩
- **历史 18 个 case 回归**（`test_reschedule_notification_v1.py`）：时段格式化、文案构造、三通道凭证缺失、聚合行为、端到端 mock，全部 PASS

部署后 8 个核心 URL HTTPS 健康检查：
- `/`（H5 用户端）→ 200
- `/admin/`（Admin 登录）→ 200
- `/merchant/calendar/`（商家 PC 日历）→ 200
- `/merchant/m/`（商家手机端首页）→ 200
- `/api/health` → 200
- `/api/docs`（Swagger）→ 200
- `/api/admin/payment-channels` → 401（接口存活、鉴权拦截）
- `/api/merchant/orders/1/detail?store_id=1` → 401（接口存活、鉴权拦截）

---

## 注意事项

1. **首次填写预约日不触发改期通知**：仅当订单已有预约时间、再次修改时才视为「改期」并触发三通道。这避免了下单后第一次填日期就误发「您的预约已改期」消息。
2. **改期权 100% 收归客户端**：商家端无改期入口（PRD-03 落地）。商家在订单详情页**仅能查看**通知状态，不能直接发起或重发通知。
3. **手机号脱敏**：企业微信告警中的客户手机号中间 4 位会被替换为 `****`，避免在群聊里完全暴露客户隐私。
4. **凭证从配置中心读，不写死代码**：所有 SDK Key/Secret/Template ID 通过环境变量传入，源码中没有任何明文凭证。
5. **整体下发延迟 ≤ 3 秒**：三通道并发执行，整体耗时 ≈ 单通道最慢耗时（受限于微信 API 与短信运营商响应速度）。
6. **APP push 当前为占位接入**：本期已就绪极光（JPush）模板，运营在配置中心写入 `APP_PUSH_PROVIDER=jpush` + `JPUSH_APP_KEY` + `JPUSH_MASTER_SECRET` 后立即生效，无需重新发版。
7. **企业微信告警内容**：包含订单号、客户姓名、客户手机号（脱敏）、原时段、新时段、门店名、失败明细前 200 字符。
8. **顾客无需安装 APP / 关注小程序**：只要绑定了正确的手机号，短信通道就能触达，是兜底首选。
9. **本次代码改动**：仅涉及 `backend/`（服务实现 + 商家详情接口）和 `h5-web/`（商家手机端订单详情页 UI），均通过 Docker 部署到服务器后立即生效，**无需重新打包小程序、APK、IPA、exe**。
10. **支持的渠道扩展**：未来若接入个推 / FCM，只需在 `_send_app_push` 中按 `provider` 分支扩展，不影响其他通道。

---

## FAQ

**Q1：顾客没有看到任何通知，但订单显示已改期，怎么办？**
A：进入商家端订单详情页查看「通知状态」，若为红色异常，运营已通过企业微信告警群收到通知；店长可主动电话联系顾客确认。若状态为绿色「已通知」但顾客未感知，常见原因：① 顾客未授权小程序订阅消息（一次性授权后才能收到下一次）；② 顾客 APP 通知权限关闭；③ 短信被运营商屏蔽。建议电话兜底。

**Q2：能否禁用某个通道？**
A：可以。**只需把对应的环境变量留空即可**——例如不再使用 APP push，把 `APP_PUSH_PROVIDER` 删除，该通道会自动返回 `ok=false, detail=未配置`，不影响其他通道与主流程。

**Q3：企业微信告警如何关闭？**
A：把环境变量 `WECHAT_WORK_ALERT_WEBHOOK` 留空即可。三通道全失败时只会记录服务器日志，不发企业微信。

**Q4：通知是否会影响改期接口性能？**
A：通知是**异步并行**调用，整体耗时 ≈ 单通道最慢耗时（一般 < 3 秒）。改期接口在通知下发完毕后才返回 `notify_result`，方便客户端即时反馈；若希望接口立即返回（不等通知），需要把 `notify_order_rescheduled` 包装为 `asyncio.create_task`。本期保持「同步等待 + 立即反馈」，便于商家页面立即看到通知状态。

**Q5：notify_result 字段以前没有？**
A：`notify_result` 字段已在历史版本（"门店预约看板与改期能力升级 v1.0 · F-11"）就位。本期 PRD-04 新增的是企业微信告警结果挂载到 `notify_result.wechat_work_alert`、以及商家订单详情页的通知状态卡片展示。

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 用户端首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 顾客在此发起改期 |
| H5 商家端预约日历 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/calendar/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/calendar/) | 店长在 PC 端浏览所有改期记录 |
| H5 商家手机端首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/m/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/m/) | 店长在手机端进入订单详情查看「通知状态」 |
| Admin 登录 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/) | 平台运营后台，可配置通知凭证 |

文档结束。
