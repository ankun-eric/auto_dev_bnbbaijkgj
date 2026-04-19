# 本期需求开干交接卡 — 用户体验使用手册

> **版本**：V2.x（2026-04-19 上线）
> **部署 ID**：`6b099ed3-7175-4a78-91f4-44570c84ed27`
> **测试环境基础 URL**：`https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27`
> **链接验证**：727 / 727 全部可达 ✅

---

## 一、本期改动总览

| 模块 | 类型 | 说明 |
|------|------|------|
| H5 体质测评 `/submit` 报错 | Bug 修复 | 后端真实错误透传到 Toast；幂等防重复点击 |
| 商品收藏状态回显 + Toast 文案统一 | Bug 修复 | H5/小程序/Flutter 三端，进入商品页自动显示已收藏；统一文案"收藏成功，可在「我的-收藏」中查看" |
| 优惠券有效期重构 | 重大变更 | 从"日期范围"改为"领取后 N 天" (3/7/15/30/60/90/180/365)；旧券与已领取记录已 TRUNCATE 清零 |
| 优惠券发放记录 | 新功能 | 列出 7 个字段（用户/手机号/发放时间/方式/订单号/操作人/兑换码）+ 单个/批量回收 + 4 维筛选 + 导出 Excel |
| 4 种发放方式 | 新功能 | A 自助领取 / B 定向发放 / D 新人券 / F 兑换码（一码通用 + 一次性唯一码） |
| 资金安全审核体系 | 新功能 | 短信验证码（6位/5分钟/3次锁10分钟）+ 审核手机号配置 + 风险分级 + 退回流程 |
| 第三方合作方 + 5 个 OpenAPI + 一次性唯一码 | 新功能 | C+ 模式：API Key/Secret + HMAC-SHA256 签名 + 兑换码批量获取/售出回传/状态查询/作废/核销回调 |

---

## 二、Part 1 · BUG 修复

### Bug 1：H5 体质测评 `/submit` 报错可见 + 幂等

- **入口**：`https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/tcm`
- **改动**：
  - 提交前如果上一次请求未完成，新点击会被忽略（防止重复提交导致同一用户产生多份测评结果）
  - 后端任何报错（含 401/403/422/500 + `detail` 文本/数组）会以 `[状态码] 详细信息` 形式显示在 Toast 中，便于用户与客服直接定位
- **验证步骤**：
  1. 进入"中医测评"完成所有题目 → 点击"提交"
  2. 弱网/失败时 Toast 会展示真实错误而非"提交失败请重试"
  3. 连续点击 5 次，只有 1 次会发起请求

### Bug 2：商品收藏状态回显 + Toast 文案统一

- **三端均已修复**：
  - **H5**：`https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/product/{商品ID}`
  - **小程序**：`pages/product-detail/index`
  - **Flutter App**：`product/product_detail_screen`
- **改动**：
  - 进入商品详情页时立即调用 `GET /api/favorites/status?content_type=product&content_id={id}` 拿到当前用户的收藏状态，红心填充态正确回显
  - 收藏成功后 Toast 文案统一为：`收藏成功，可在「我的-收藏」中查看`（取消收藏沿用"已取消收藏"）
- **验证步骤**：
  1. 登录后进入任意商品 → 点击红心 → 离开页面再进入 → 红心仍为已填充状态
  2. 同一商品在不同端（H5/小程序/App）登录同账号后，红心状态保持一致

### Bug 3：优惠券有效期重构（重大变更）

- **入口（管理后台）**：`https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/product-system/coupons`
- **改动**：
  - 删除原 `valid_start` / `valid_end` 日期段、删除"长期有效"
  - 新增"有效期 (天)"下拉，固定 8 个选项：`3 / 7 / 15 / 30 / 60 / 90 / 180 / 365`
  - 用户领取时刻 `granted_at + N 天` 自动写入 `user_coupons.expire_at`
  - 上线时一次性 TRUNCATE 旧 `coupons` 与 `user_coupons` 表（已确认未上线，数据可清零）
- **验证步骤（管理后台）**：
  1. 进入"商品体系 → 优惠券管理" → 点击"新增优惠券" → "有效期"下拉只显示 8 个选项 → 保存
  2. 列表"有效期"列显示蓝色徽标 `领取后 N 天`
- **验证步骤（H5 用户端）**：
  - 路径：`/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-coupons`
  - "未使用"卡片显示 `有效期至 YYYY-MM-DD`，距今 ≤ 7 天显示红色"即将到期"标签

---

## 三、Part 2 · 优惠券管理增强

### 3.1 发放记录入口

- **入口**：管理后台"优惠券管理"列表 → 每行操作列点击 **"发放记录"** 按钮
- **抽屉支持**：
  - **7 个字段**：用户/手机号、发放时间、方式、状态、使用时间、订单号、操作人 + 兑换码 + 回收原因
  - **4 维筛选**：手机号 / 状态（已发放·已使用·已回收·已过期） / 发放方式 / 时间范围
  - **导出 Excel**：右上角"导出 Excel"，调用 `GET /api/admin/coupons/{coupon_id}/grants/export` → CSV
  - **批量回收**：勾选多行 → 点"批量回收" → 必填回收原因 → 已发放/已使用券会被标记为已过期（已使用券不会冲账，仅断后续核销）

### 3.2 4 种发放方式

管理后台"优惠券管理"行的"发放"按钮下拉式选择以下任一方式：

| 方式 | 编号 | 说明 |
|------|------|------|
| **自助领取** | A | 该券处于 `active` 时自动出现在 H5 "领券中心"，每人每券限领 1 张 |
| **定向发放** | B | 支持 `用户ID` + `手机号` + `标签筛选`（用户等级、注册时长 ≤ N 天） |
| **新人券** | D | 加入"新人券池"后，用户注册成功立即自动获得（每人每券 1 张） |
| **兑换码** | F | 自动跳转到"兑换码批次"创建窗口；支持 *一码通用* 与 *一次性唯一码（16 位）* |

#### 新人券池
- **入口**：`/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/product-system/new-user-coupons`
- **使用**：点击"选择券" → 在 Transfer 控件中将候选券拖入"已选" → 保存即生效

#### 兑换码批次
- **管理后台调用**：`POST /api/admin/coupons/redeem-code-batches`
- **一码通用**：可填自定义码（如 `NEW2026`），留空自动生成；支持每用户限兑次数
- **一次性唯一码（C+）**：单批最多 100,000 个；可关联第三方合作方批量分发

#### 用户兑换码兑换 (H5)
- **入口**：`/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-coupons` → 右上角"兑换码"
- **使用**：弹窗输入码 → 兑换成功后立即出现在"未使用"列表
- **限流**：单用户 10 次/分钟

---

## 四、Part 3 · 资金安全审核体系

### 4.1 审核手机号配置

- **入口**：`/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/audit/phones`
- **能力**：
  - 添加多个审核手机号（财务总监/老板等）+ 备注 + 启用/停用开关
  - 仅"启用"的手机号才会出现在审核中心的下拉中接收短信

### 4.2 审核中心

- **入口**：`/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/audit/center`
- **状态**：待审核 / 已通过 / 已驳回 / 已退回 / 已重新提交
- **审批流程**：
  1. 在列表中点行的"审批"按钮
  2. 选择审核手机号 → 点"发送验证码"（SMS：6 位，5 分钟有效）
  3. 输入收到的 6 位数字 → "确认通过"
  4. 后端实际执行 `payload` 中的业务（券发放/回收/兑换码批次等）

### 4.3 风险分级与审批模式

| 风险等级 | 触发条件 | 审批模式 |
|---------|---------|---------|
| **低风险** | 估算金额 ≤ 10 元 **且** 数量 ≤ 100 张 | 任一审核员通过即可 |
| **高风险** | 金额 > 50 元 **或** 数量 > 1000 张 **或** 一次性唯一码 > 500 个 **或** 全员发放 | 联合审批（≥ 2 人独立通过） |

### 4.4 锁定与退回

- **失败锁定**：连续 3 次输入错误验证码 → 锁定该审核手机号 10 分钟
- **退回流程**：审批人在详情中点"退回" → 必填修改说明 → 申请人可在"我提交的"中重新编辑提交

---

## 五、Part 4 · 第三方合作方（C+ 模式）

### 5.1 合作方管理

- **入口**：`/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/product-system/partners`
- **能力**：
  - 新增合作方 → 系统自动生成 `API Key` 与 `API Secret`（**Secret 仅本次显示，请立即复制保存**）
  - 重置 Key（旧 Secret 立即失效）
  - 对账抽屉：展示该合作方所有兑换码批次的"生成总数 / 已售出 / 已核销 / 作废 / 待售 / 批次数量"

### 5.2 5 个 OpenAPI 接口（HMAC-SHA256 签名）

> 所有接口都通过基础 URL 暴露：`https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/api/openapi/`
>
> 公共请求头：
> - `X-Api-Key`: 合作方 API Key
> - `X-Timestamp`: 当前 Unix 秒（5 分钟内有效）
> - `X-Nonce`: 一次性随机串
> - `X-Signature`: `HMAC_SHA256(secret, "{METHOD}\n{PATH}\n{TIMESTAMP}\n{NONCE}\n{BODY}")`，hex lower

| # | Method | Path | 说明 |
|---|--------|------|------|
| ① | POST | `/api/openapi/redeem-codes/batch-fetch` | 批量获取本合作方批次的可售卖唯一码（请求体: `{"batch_id": <int>, "limit": <int>}`） |
| ② | POST | `/api/openapi/redeem-codes/mark-sold` | 上传售出状态（请求体: `{"codes": ["xxx", ...], "buyer_phone": "1380000..."}`） |
| ③ | GET | `/api/openapi/redeem-codes/{code}/status` | 查询单个码的当前状态（available/sold/used/disabled） |
| ④ | POST | `/api/openapi/redeem-codes/disable` | 退款时作废码（请求体: `{"codes": [...], "reason": "..."}`） |
| ⑤ | POST | `/api/openapi/redeem-codes/redeem-callback` | 线下核销结果回调（请求体: `{"code": "...", "verified_at": "...", "store_id": <int>}`） |

### 5.3 一次性唯一码

- **生成规则**：16 位字母数字，去除易混淆字符（O/0/I/1/L），单批最多 100,000 个
- **导出**：管理后台"兑换码批次列表" → "导出 CSV"
- **限流**：单用户兑换 10 次/分钟，逾期/作废/已用码立即拦截

---

## 六、关键链接快查

| 名称 | 链接 |
|------|------|
| H5 用户首页 | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ |
| H5 我的优惠券 | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/my-coupons |
| H5 中医测评 | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/tcm |
| 管理后台首页 | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/ |
| 优惠券管理 | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/product-system/coupons |
| 新人券池 | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/product-system/new-user-coupons |
| 合作方管理 | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/product-system/partners |
| 审核手机号 | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/audit/phones |
| 审核中心 | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/audit/center |
| Swagger 接口文档 | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/docs |

---

## 七、回归测试建议

1. **优惠券完整链路**：新建券（30 天） → 用户领取 → 在"我的优惠券"看到"有效期至" → 后台"发放记录" → 批量回收 → 用户列表自动消失
2. **新人券**：将一张券加入新人券池 → 用任意新手机号注册 → 立即在"我的优惠券"看到该券
3. **兑换码（一码通用）**：后台创建 universal 批次 `NEW2026` → 用户在"我的优惠券 → 兑换码"输入 → 收到券
4. **兑换码（一次性唯一码）**：后台创建 unique 批次 100 个 → 导出 CSV → 选 1 个码给用户兑换 → 该码状态变为 used，再次兑换报错
5. **审核**：手动 POST `/api/admin/audit/requests` 一笔高风险申请 → 在审核中心选择手机号 → 发送验证码 → 通过 → 业务实际执行
6. **第三方 OpenAPI**：用任意合作方的 Key/Secret 按文档构造签名 → batch-fetch → mark-sold → status → 完整闭环

---

## 八、上线注意事项

> ⚠️ **首次启动后端会自动 TRUNCATE 旧 `coupons` 与 `user_coupons` 表**（已配置 `coupons_v2_truncated` 标志位防止重复执行）。生产环境如需保留旧数据，请在部署前先注释 `backend/app/main.py` 中的 `_migrate_coupons_v2()` 内的 `DELETE` 语句。

> ⚠️ 第三方 API Secret **只在创建时显示一次**，请合作方立即妥善保存；遗失只能"重置 Key"重新生成。
