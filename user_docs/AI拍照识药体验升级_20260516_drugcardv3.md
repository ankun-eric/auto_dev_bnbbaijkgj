# AI 对话模式拍照识药体验升级 · 用户体验使用手册

> 版本 v1.0 · 2026-05-16
> 关联 PRD：AI 对话模式 · 拍照识药体验升级与权威药品库建设

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| 前端 AI 对话主页（H5） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home) | 进入 AI 对话模式 ai-home，主入口 |
| 项目主页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | bini-health 项目入口页 |
| 健康档案 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile) | 维护过敏史、慢病等档案（用于冲突防护） |
| 用药计划 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-plan/medications/add](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-plan/medications/add) | 新增用药计划完整表单页 |

---

## 功能简介

本次升级聚焦**「AI 对话模式 · 拍照识药」**两个必现 Bug 的根治，并同步落地权威药品库匹配 + 档案冲突防护的核心能力。面向 40-60 岁中老年主力用户，给出清晰、安全、易懂的用药指导。

### 本次解决的问题

1. **Bug 修复 #1**：上传药品图片时，对话流中**不再出现**形如
   `[用户上传的图片1张] 1. https://xxx/xxx.jpg` 的冗余文本气泡；只保留干净的「图片小图墙气泡」+「AI 回复气泡」。
2. **Bug 修复 #2**：识药时不再出现「AI 服务调用失败：400 Bad Request」错误。后端识药链路改为显式多模态开关（`enable_vision`），默认锁定纯文本，杜绝因纯文本模型 deepseek-v3-2-251201 收到多模态结构而 400。

### 本次新增的能力

1. **权威药品库匹配**：识药结果回来后，系统会自动按药品名 / 通用名 / 批准文号去权威库做精确 + 模糊匹配，命中后用权威字段更新识药卡片。
2. **档案冲突 4 级防护**：基于档案里的过敏史、慢病、在用药物，自动判定三类冲突（药物过敏、慢病冲突、重复用药）。命中时弹出红底警示横幅、按钮置灰、独立警示卡，并提供「📞 联系医生咨询」入口。
3. **联系医生咨询热线**：可由后台动态配置咨询电话号码 / 名称 / 服务时间，前端实时读取。
4. **待审池**：未命中权威库的药品，后端会**完全静默**写入「医生药品库待审池」（用户完全感知不到），运营可在后台手动审核入库。
5. **AI 对话气泡显示优化**：对话流中上传图片后只看到一条图片墙气泡，符合 PRD 5.1 验收。

---

## 操作步骤

### 1. 拍照识药主流程

1. 打开 AI 对话主页：[https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home)
2. 在底部胶囊功能区找到「拍照识药」按钮（也叫「药品识别」「识药」等）
3. 选择「从相册」或「拍一张」上传药品图片
4. **预期表现**：
   - 对话流中**仅出现**一条图片小图墙气泡（**不再有** `[用户上传的图片N张] + URL` 文本）
   - 紧接着 AI 流式打字输出识药结果与解读
   - **不会出现** `AI服务调用失败: 400 Bad Request` 报错

### 2. 看懂识药结果卡片

识药成功后，对话流中会展示识药结果卡片，结构如下：

- 顶部绿色徽章「✓ 识别成功」
- 药品名（22px 加粗黑色）
- 通用名 / 规格 / 厂家 / 分类（按字段是否有值动态渲染，未识别字段整行不显示）
- 命中权威库时：额外渲染「💊 用法用量」与「⚠ 用药提醒」（红底高对比）
- 底部两个大按钮（高度 ≥ 48px）：
  - 「+ 加入用药计划」（蓝色主按钮）
  - 「📋 查看全部用药计划」

> ⚠ **合规提醒**：未命中权威库时，卡片**不会**显示「未收录」「仅供参考」等技术词；也**不会**编造禁忌信息，避免误导用户用药。

### 3. 加入用药计划

1. 点击「+ 加入用药计划」按钮
2. 底部弹出抽屉，已自动预填药品名、通用名、规格、厂家等字段
3. 点击「继续填写用药信息」按钮，跳转到完整的「新增用药计划」页（剂量、频次、起止日期、提醒等）
4. 填完保存即完成。

### 4. 档案冲突防护演示

1. 先打开「健康档案」页，在「药物过敏」一栏添加例如「青霉素」
2. 回到 AI 对话主页，上传一张阿莫西林（青霉素类药）的图片
3. **预期表现**：
   - 识药卡片顶部出现红底白字横幅「⚠ 本药与您档案中【青霉素过敏】可能存在冲突」
   - AI 解读对相关段落加粗红字强调
   - 「+ 加入用药计划」按钮置灰，文案改为「存在用药风险，无法加入」
   - 对话流下方出现独立「⚠ 用药冲突警示」卡，含「📞 联系医生咨询」按钮

### 5. 联系医生咨询

1. 在冲突警示卡上点击「📞 联系医生咨询」
2. 弹出浮层，显示后台配置的热线（默认 `400-000-0000`，可点击直接拨打）
3. 浮层底部「前往专家咨询 →」可跳转 `/experts` 列表

---

## 注意事项

1. **图片要求**：药盒平放、光线充足、距离 20-30cm 拍正面，识别成功率最高。
2. **冲突误报**：本期为安全考虑采用**从严判定**（宁可误报不漏报）。如对识别有疑问，请咨询医生或药师。
3. **未命中库不输出禁忌**：当权威库未收录该药时，AI 会基于通用药品知识做解读，**不会**编造特定禁忌，请以药品说明书为准。
4. **40-60 岁适老化**：药品名 22px、按钮 48px、行高 1.7-1.8，对比度满足红底白字 #DC2626/#FFFFFF。
5. **隐私安全**：上传图片走 COS / 后端 OCR，URL 仅在后端 AI 上下文使用，不在 UI 中暴露给用户。

---

## 本次接口说明

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v5/medication-library/match` | POST | 权威库匹配 + 三类冲突判定 |
| `/api/v5/system-config/doctor-consult` | GET | 公开读取医疗咨询热线（无需鉴权） |
| `/api/admin/medication-library-pending` | GET | 后台待审池列表 |
| `/api/admin/medication-library-pending/{id}/accept` | POST | 后台一键采纳入主库 |
| `/api/admin/medication-library-pending/{id}/reject` | POST | 后台驳回 |

后端启动时会自动通过 SQLAlchemy 建表创建 `medication_library_pending`，无需手动建表。

---

## 已知限制 / 后续计划

- **NMPA 全量药品库**（15-18 万条）抓取脚本本期作为骨架交付，未跑全量入库；后续按 PRD F8 安排夜间任务跑全量 + 月度增量。
- **小程序端 / Flutter 端 UI**：本期共用同一套后端接口契约，UI 组件先在 H5 落地，后续按 PRD §9 完成三端 UI 对齐。
- **抽屉表单字段完整版**：本期为「最小预填 + 跳转完整页」方案，后续将完整字段嵌入抽屉（参考 `health-plan/medications/add` 页）。

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| 前端 AI 对话主页（H5） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home) | 进入 AI 对话模式 ai-home，主入口 |
| 项目主页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | bini-health 项目入口页 |
| 健康档案 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile) | 维护过敏史、慢病等档案（用于冲突防护） |
| 用药计划 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-plan/medications/add](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-plan/medications/add) | 新增用药计划完整表单页 |
