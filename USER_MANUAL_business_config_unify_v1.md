# 门店「营业管理」入口收敛与字段统一 — 用户体验手册

> 版本：v1.0  发布日期：2026-05-05  
> 适用：门店运营管理员、商家管理员
>
> 本次升级目标：把"门店营业相关的运营字段"全部收敛到**一个入口**，并补齐"提前 N 天预约""当日 N 分钟截止"两条预约规则。

---

## 一、访问地址与登录

| 用途 | 地址 |
|---|---|
| 项目基础 URL | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27 |
| Admin 后台首页 | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/ |
| Admin 登录页 | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/login |
| H5 前端 | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ |
| API 根 | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/api/ |

测试账号：`13800000000` / `admin123`（管理员）

---

## 二、本次升级亮点

1. **入口收敛**：原顶级菜单 **"商家管理 → 营业时间&并发上限"** 已下线，统一改为门店列表行内的 **「营业管理」** 按钮。  
2. **字段去重**：删除了与"门店总接待名额"含义重复的"门店级（默认值）"并发字段，前后端字段唯一以 `merchant_stores.slot_capacity` 为准。  
3. **职责分离**：
   - **「编辑门店」**：只编辑门店档案/资料字段（名称、地址、电话、营业状态…）。
   - **「营业管理」**：编辑所有运营/经营字段（营业时间、并发上限、预约提前规则）。
4. **能力补齐**：门店级新增 **最早可提前 N 天预约** 与 **当日最晚提前 N 分钟截止**；商品级也支持配置同名字段；
   生效优先级：**商品级 > 门店级 > 系统默认（30 分钟 / 不限制天数）**。
5. **空态指引**：服务级覆盖表为空时，给出"前往商品管理"按钮，一键跳转。

---

## 三、操作步骤

### 3.1 进入门店「营业管理」

1. 登录 Admin 后台。
2. 左侧菜单：**商家管理 → 门店管理** → [门店列表](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/merchant/stores)
3. 在目标门店行的「操作」列点击 **「营业管理」** 按钮，进入：
   `…/admin/merchant/stores/{id}/business-config`

> 旧入口 [营业时间&并发上限](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/merchant/business-config) 已变为提示页，3 秒后自动跳转到门店列表。

### 3.2 营业管理页四大模块

| 模块 | 字段 | 说明 |
|---|---|---|
| 按周营业时间 | 周一~周日的多时段 | 与原页一致 |
| 日期例外 | 节假日/特殊日 | 与原页一致 |
| 同时段并发上限（双层） | **门店总接待名额** + 服务级覆盖表 | 门店级唯一字段；空态会给"前往商品管理"按钮 |
| 预约提前规则（门店级） | **最早可提前 N 天**（0=不限制）<br>**当日最晚提前 N 分钟截止**（枚举：0/15/30/60/120/720/1440 分钟，留空=系统默认 30） | 商品级未填则继承门店级 |

> 点击页面底部 **「保存全部配置」** 一次性提交。系统会自动调用 3 个后端接口：
> - `POST /api/merchant/business-hours`（营业时间）
> - `POST /api/merchant/concurrency-limit`（服务级覆盖；门店级字段在此请求中将被后端**忽略**）
> - `PUT /api/merchant/stores/{id}/booking-config`（门店级 slot_capacity / advance_days / booking_cutoff_minutes）

### 3.3 商品级覆盖

1. 进入：[商品管理](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/product-system/products)
2. 编辑某商品 → **预约设置** 选项卡：
   - 「最早可提前 N 天预约」（已存在）
   - 「当日最晚提前 N 分钟截止」（**本次新增**，留空=继承门店级）

### 3.4 编辑门店（瘦身后）

进入门店列表点击「编辑」，**不再包含** "默认接待名额（slot_capacity）" 字段；如需修改请去「营业管理」。

---

## 四、生效逻辑与边界

### 4.1 双层兜底

| 字段 | 取值优先级 |
|---|---|
| `advance_days`（提前 N 天） | 商品 > 0 → 用商品；否则 门店 > 0 → 用门店；否则 0=不限制 |
| `booking_cutoff_minutes`（截止 N 分钟） | 商品非空 → 用商品；否则 门店非空 → 用门店；否则 30 分钟 |

### 4.2 边界

- 截止判定使用 **严格小于** `<`：当前时间到时段开始的剩余分钟 **必须 > 截止值** 才能预约。
- `booking_cutoff_minutes = 0` 表示"无截止限制"。
- 老接口 `POST /api/merchant/concurrency-limit` 中的 `store_max_concurrent` 字段已被后端**忽略**（仅保留 schema 兼容老前端）。

---

## 五、自助验证清单

| 场景 | 预期 |
|---|---|
| 旧入口"营业时间&并发上限"是否还在左侧菜单？ | ❌ 不在 |
| 旧 URL 直接访问 | 进入提示页，自动跳转门店列表 |
| 门店列表是否有「营业管理」按钮？ | ✅ 有 |
| 编辑门店弹窗是否还有"默认接待名额"输入框？ | ❌ 没有 |
| 营业管理页保存后刷新，3 类配置是否都持久化？ | ✅ 是 |
| 商品级填了截止 60 分钟，门店级 15 分钟，下单计算用哪个？ | 商品级 60 分钟 |
| 商品级未填，门店级 15 分钟，下单计算用哪个？ | 门店级 15 分钟 |
| 商品级、门店级均未填，下单计算用哪个？ | 系统默认 30 分钟 |

---

## 六、API 速查

```
GET  /api/merchant/stores/{store_id}/booking-config
PUT  /api/merchant/stores/{store_id}/booking-config
     body: { slot_capacity, advance_days?, booking_cutoff_minutes? }
```

`booking_cutoff_minutes` 合法枚举：`null | 0 | 15 | 30 | 60 | 120 | 720 | 1440`，其他取值返回 422。

---

## 七、问题反馈

如发现异常，请提供：
- 浏览器地址栏 URL
- 截图（含报错信息）
- 操作账号手机号 + 操作时间

发送至工程团队即可。
