# 双重身份用户 H5 顾客端改约失败修复 — 用户体验手册

- 版本：BUG-FIX-RESCHEDULE-DUAL-IDENTITY-V1
- 修复日期：2026-05-07
- 部署环境：测试环境
- 访问入口：
  - **H5 顾客端**：https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/
  - **管理后台**：https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/
  - **API 文档**：https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/api/docs

---

## 一、修复目标

修复"同一手机号既是顾客又是商家"（双重身份用户）在 H5 顾客端、微信小程序、Flutter App 等顾客侧入口对自己的订单发起改约时，被错误拦截、统一兜底显示"预约失败"的问题；同时把后端所有改约失败响应改造为结构化错误码，前端根据错误码展示具体业务提示。

---

## 二、问题现象（修复前）

| 现象 | 影响范围 |
| --- | --- |
| 双重身份用户在 H5 顾客端订单详情页点"改约"，无论选什么时段都报"预约失败" | H5 顾客端、小程序、Flutter App |
| 不论是"超时段"、"超 90 天"、"超改约次数"、"商品不允许改约"，前端均统一兜底"预约失败"，无法定位 | H5 顾客端、小程序、Flutter App |
| 商家在自己手机的顾客端入口给自己下的订单改约，被识别成商家身份而被拒 | 全部顾客侧入口 |

---

## 三、修复方案概览

### 后端
- 新增请求头 `X-Client-Source`，值为 `h5-customer` / `miniprogram-customer` / `flutter-customer` 时，明确表示"顾客侧入口"。
- 改约接口 `POST /api/orders/unified/{id}/appointment` 内部判定：
  - 来自顾客侧入口 → 完全按顾客身份放行；
  - 是双重身份用户从顾客侧入口操作自己订单时，**改约次数不再受 `reschedule_limit` 限制**；
  - 既无 `X-Client-Source` 也无顾客侧 `Client-Type` → 返回结构化 `RESCHEDULE_NO_PERMISSION (403)`。
- 改约失败一律返回结构化错误：
  ```json
  {
    "detail": {
      "code": "RESCHEDULE_TIME_OUT_OF_RANGE",
      "message": "改约时间不在可预约范围内",
      "detail": "最多可预约 90 天内的时段"
    }
  }
  ```
- 错误码清单：`RESCHEDULE_NO_PERMISSION` / `RESCHEDULE_ORDER_NOT_FOUND` / `RESCHEDULE_ORDER_STATUS_INVALID` / `RESCHEDULE_LIMIT_EXCEEDED` / `RESCHEDULE_NOT_ALLOWED` / `RESCHEDULE_TIME_EXPIRED` / `RESCHEDULE_TIME_OUT_OF_RANGE` / `RESCHEDULE_TIME_CONFLICT` / `RESCHEDULE_REFUND_IN_PROGRESS` / `RESCHEDULE_PARTIALLY_USED` / `RESCHEDULE_INTERNAL_ERROR`。

### H5 顾客端（Next.js）
- Axios 请求拦截器自动追加 `X-Client-Source: h5-customer`（仅顾客域，不影响商家域）；
- 改约失败按错误码映射展示具体提示，例如：
  - `RESCHEDULE_LIMIT_EXCEEDED` → "您已达到本订单的改约次数上限"
  - `RESCHEDULE_TIME_OUT_OF_RANGE` → "所选时段不在可预约范围内（90 天内）"

### 微信小程序
- `wx.request` 全局追加 `X-Client-Source: miniprogram-customer`；
- 文件上传 `wx.uploadFile` 同步追加；
- 错误格式化统一从 `detail.code` 映射本地提示。

### Flutter App
- Dio 全局 `BaseOptions.headers` 添加 `X-Client-Source: flutter-customer`；
- 刷新 token 的兜底请求也带上该头；
- 新增 `lib/utils/reschedule_error.dart`，从 `DioException` 中提取结构化错误并映射为 SnackBar 文案。

---

## 四、自动化测试结果

后端 pytest 套件 `backend/tests/test_reschedule_dual_identity.py` 共 11 个用例，**全部通过**：

```
tests/test_reschedule_dual_identity.py ...........   [100%]
11 passed in 14.56s
```

覆盖：
- T01 双重身份用户 H5 顾客端首次改约成功
- T02 双重身份用户连续改约 6 次仍成功（不卡 reschedule_limit）
- T03 纯顾客身份保持原 reschedule_limit=3 限制
- T05 过期时段返回 `RESCHEDULE_TIME_EXPIRED`
- T06 超 90 天范围返回 `RESCHEDULE_TIME_OUT_OF_RANGE`
- T07 纯顾客超限返回 `RESCHEDULE_LIMIT_EXCEEDED`
- T08 顾客无法改他人订单（`RESCHEDULE_ORDER_NOT_FOUND`）
- T09 所有失败响应均含 `code` + `message` 结构化字段
- T_MINIPROGRAM 小程序入口同样放行双重身份
- T_FLUTTER Flutter 入口同样放行双重身份
- T_NO_SOURCE 无顾客标识返回 403 `RESCHEDULE_NO_PERMISSION`

---

## 五、用户体验验证步骤

1. 登录 H5 顾客端：`https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/`
2. 用同一手机号在管理后台开通"商家身份"（admin 后台 → 商家管理 → 添加商家，使用同一手机号）。
3. H5 顾客端下单（任意可改约商品），完成支付，进入订单详情页。
4. 点击"修改预约"，多次切换不同时段提交：
   - **修复前**：均提示"预约失败"。
   - **修复后**：
     - 选合法时段 → 改约成功，无次数上限；
     - 选过去时段 → 提示"改约时段已过期"；
     - 选超 90 天的时段 → 提示"所选时段不在可预约范围内（最多 90 天）"；
     - 商家在 admin 配置 `allow_reschedule=false` → 提示"该商品不允许改约"。

---

## 六、回滚与影响面

- 仅新增字段、不修改既有字段语义；
- 旧版前端不发 `X-Client-Source` 时仍可通过 `Client-Type=h5-user/miniprogram-user/app-user` 走老路径；
- 商家 PC 后台改约链路未受影响（仍走 admin 鉴权 + Client-Type=pc-web）。

---

## 七、变更文件清单

后端：
- `backend/app/utils/client_source.py`：新增 `X-Client-Source` 解析与 `is_customer_entry`
- `backend/app/api/unified_orders.py`：改约接口结构化错误 + 双重身份放行
- `backend/tests/test_reschedule_dual_identity.py`：11 个新增 pytest 用例

H5：
- `h5-web/src/lib/api.ts`：拦截器追加 `X-Client-Source: h5-customer`
- `h5-web/src/lib/reschedule-error.ts`：错误码映射工具（新增）
- `h5-web/src/app/unified-order/[id]/page.tsx`：改约失败 Toast 改用映射

小程序：
- `miniprogram/utils/request.js`：全局头 + 错误格式化
- `miniprogram/pages/unified-order-detail/index.js`：改约错误展示

Flutter：
- `flutter_app/lib/services/api_service.dart`：Dio 全局头
- `flutter_app/lib/utils/reschedule_error.dart`：错误码映射工具（新增）
- `flutter_app/lib/screens/order/unified_order_detail_screen.dart`：SnackBar 改用映射
