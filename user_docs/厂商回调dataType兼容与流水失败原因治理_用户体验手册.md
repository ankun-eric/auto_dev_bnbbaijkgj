# 厂商回调 `new-call-msg` 兼容 & 回调原始流水"失败原因"治理 · 用户体验使用手册

> 适用版本：2026-05-29 修复发布
> 关联 Bug 修复：紧急呼叫器厂商回调 `dataType` 升级兼容 + 回调原始流水"失败原因"被心跳报文污染问题

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| 管理后台 · 居家安全设备 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/home-safety](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/home-safety) | 进入「回调原始记录」Tab 查看新版列与筛选 |
| 管理后台 · 登录页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/login](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/login) | 用您的管理员账号登录后跳转到上面的页面 |
| H5 前端主页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/h5/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/h5/) | C 端用户主入口（本次修复不影响 C 端） |

---

## 功能简介

本次修复解决了**紧急呼叫器厂商回调升级**带来的两个核心问题：

1. **新版告警报文无法识别**：厂商把 `dataType` 由旧值 `call-msg` 升级为 `new-call-msg`，旧后端只认 `call-msg`，导致新版告警直接被当成"未识别类型"，**告警链路断裂**。修复后，后端**同时认 `new-call-msg` 与 `call-msg`**，两者都走告警分发流程。
2. **回调原始流水"失败原因"被心跳污染**：厂商持续推送的 `smb-real-time-msg` 心跳/实时状态报文，旧后端一刀切标为"解析失败"，导致管理后台的「回调原始流水」失败原因列里塞满心跳噪声，真实的业务失败被淹没。修复后，**心跳类报文统一标记为 ⏸️ 已忽略**，失败原因留空，并且行底色用浅灰与失败的红色徽标做视觉区分；同时**新增独立 `data_type` 报文类型列**和**报文类型筛选下拉框**，让运维一眼看清谁是谁。

> ✅ 本次修复**仅作用于后端 + 管理后台 Web**，对 H5、小程序、安卓 APP、iOS APP、桌面端**零侵入**，无需重新下载客户端。

---

## 使用说明

### 一、登录管理后台

1. 打开 [管理后台登录页](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/login)
2. 输入您的管理员账号和密码登录
3. 登录成功后，在左侧导航中点击「居家安全设备」

### 二、查看「回调原始记录」Tab

1. 在「居家安全设备」页面顶部切换到 **回调原始记录** Tab
2. 您会看到**焕然一新的列表**：

#### 1. 新增「报文类型」列（位于"接收时间"之后）

- 列内容为厂商回调报文中的 `dataType` 原值，用**等宽字体**展示，例如 `new-call-msg`、`call-msg`、`smb-real-time-msg`
- 没有 dataType 字段（极端情况）会显示 `-`

#### 2. 新增「报文类型」筛选下拉框（与"解析状态"筛选并排）

固定 5 个选项：

| 选项 | 说明 |
|------|------|
| 全部报文类型 | 不做筛选 |
| `new-call-msg`（新版告警） | 新厂商主流告警报文 |
| `call-msg`（旧版告警） | 老厂商兼容告警报文 |
| `smb-real-time-msg`（心跳） | 心跳/实时状态报文（已忽略类） |
| 其它 | 既不在上述四类、也不为空的其它 dataType |

#### 3. 解析状态新增 ⏸️ 已忽略 选项

| 状态徽标 | 含义 | 颜色 |
|----------|------|------|
| ✅ 成功 | 告警业务处理成功 | 绿色 |
| ⏸️ 已忽略 | 心跳/实时状态报文，不需要业务处理 | 灰色（行底色浅灰）|
| ⏳ pending | 处理中（极短暂） | 蓝 |
| 🔁 duplicate | 厂商 msgId 重复 | 青 |
| 🚫 unbound | 设备未绑定 | 金 |
| ⚠️ unsupported_type | 未识别 dataType | 橙 |
| ⚠️ unknown_devtype | devType 不在 {1,2,7} | 橙 |
| ⚠️ missing_field | 关键字段缺失 | 橙 |
| ❌ failed | 真实业务失败（签名/解析等） | 红 |
| 💥 internal_error | 内部异常 | 红 |

#### 4. 失败原因列治理

- **「已忽略」行的失败原因列严格留空**，不再显示任何心跳相关文字
- **「成功」行同样留空**
- 只有**真正失败**的行才会展示具体的失败原因（如"签名失败:..."、"未识别 dataType: xxx"）

### 三、常见验证场景

| 想验证什么 | 操作 |
|------------|------|
| 新厂商告警是否进来 | 报文类型选 `new-call-msg`，看是否有 ✅ 成功的记录 |
| 老厂商兼容是否生效 | 报文类型选 `call-msg`，确认仍能走告警链路 |
| 心跳是否被正确归类 | 报文类型选 `smb-real-time-msg`，所有记录都应是 ⏸️ 已忽略、失败原因为空、行底色浅灰 |
| 真实失败 | 解析状态选 `❌ 失败`，失败原因列展示具体原因，不再混入心跳 |
| 排查"未识别 dataType" | 解析状态选 `⚠️ 类型不支持`，失败原因展示 `未识别 dataType: xxx` |

---

## 注意事项

### 1. 历史数据不回刷（重要）

> ⚠️ 本次修复**只对升级上线后的新数据生效**，**历史脏数据保持原样**。

- 上线**之前**已落库的心跳类报文仍会显示为 `failed`，失败原因仍可能有心跳污染
- 上线**之后**的新数据会按新规则干净落库
- 如需清洗历史数据，请单独提报"历史数据治理"需求

### 2. 字段语义提示

- `devType` 设备类型枚举**不变**（`1`=紧急呼叫器、`2`=烟雾报警器、`7`=水位报警器）
- 厂商新增的 `alertState`（告警状态）、`voltageState`（电压状态）字段**不入库、不参与业务**，仅保留在 `raw_body` 原文中，可在「查看详情」中的「请求 Body（原始）」区域看到

### 3. 厂商重试与响应

- 心跳报文、已忽略类型、未识别类型均**返回 HTTP 200**，避免厂商无效重试导致雪崩
- 真实业务失败（签名、绑定等）也返回 HTTP 200（厂商不应重试业务级失败）
- 内部数据库异常会返回 HTTP 500（厂商可重试）

### 4. 后端 dataType 兼容矩阵速查

| dataType 取值 | 处理动作 | 流水状态 | 失败原因 |
|---|---|---|---|
| `new-call-msg` | 走告警链路 | `ok` / `failed` | 仅失败时填真实原因 |
| `call-msg` | 走告警链路 | `ok` / `failed` | 仅失败时填真实原因 |
| `smb-real-time-msg` | 直接落流水 | `ignored` | **空** |
| 其它已知非告警类型 | 直接落流水 | `ignored` | **空** |
| 完全未识别类型 | 不处理 | `unsupported_type` | "未识别 dataType: xxx" |

### 5. 测试验证

后端共 **83 个自动化测试用例**（含本次新增的 7 个）全部通过：

- TC-01 新版告警 `new-call-msg` → 走告警链路、`data_type=new-call-msg`、`parse_status=ok` ✅
- TC-02 旧版告警 `call-msg` 兼容 → 同 TC-01 ✅
- TC-03 心跳 `smb-real-time-msg` → `parse_status=ignored`、失败原因空 ✅
- TC-04 未知 `foo-bar` → `parse_status=unsupported_type`、原因含"未识别 dataType" ✅
- TC-05 管理后台支持 `data_type` 筛选（4 选项 + `__other__`）✅
- TC-06 `alertState/voltageState` 不入业务、保留在 raw_body ✅
- TC-07 详情接口返回 `data_type` 字段 ✅

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| 管理后台 · 居家安全设备 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/home-safety](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/home-safety) | 进入「回调原始记录」Tab 查看新版列与筛选 |
| 管理后台 · 登录页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/login](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/login) | 用您的管理员账号登录后跳转到上面的页面 |
| H5 前端主页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/h5/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/h5/) | C 端用户主入口（本次修复不影响 C 端） |
