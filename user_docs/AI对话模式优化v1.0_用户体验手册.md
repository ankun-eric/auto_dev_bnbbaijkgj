# AI 对话模式优化 v1.0 用户体验使用手册

> 文档版本：v1.0（2026-05-14 全自动化部署 12/12 PASS）
>
> 本次升级聚焦"AI 对话模式"的卡片体系、Toast 规范、积分入口修复、拍照识药一站式接口等核心能力。

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 主页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | AI 对话模式主入口（移动端 H5，建议在手机浏览器打开） |
| H5 AI 对话首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home) | 进入 AI 对话首页（功能宫格 + 对话流） |
| H5 积分主页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/points](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/points) | 修复后的积分主页入口（不再 404） |
| 后台管理 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/) | 运营后台（需登录），「功能按钮管理」Tab 已升级为 7 类型 + 8 字段 |

---

## 功能简介

本次更新围绕 PRD v1.0「AI 对话模式优化」终稿做最小可验证落地，聚焦如下几个核心增强：

1. **「功能按钮管理」全新升级（运营侧）**：按钮类型从 6 种扩展到 **7 种**（新增 `quick_ask` 快捷提问），每个按钮新增 8 个配置字段（关联 Prompt 模板、外部链接 URL、预设话术、自动用户消息、卡片标题、卡片副标题、卡片封面图、按钮副说明文字），并按按钮类型条件展示对应字段。
2. **拍照识药「一站式」接口（用户侧+开发侧）**：新增 `POST /api/prd469/medication-library/recognize`，前端只需调用一次即可同时拿到药品候选 + AI 解读，告别原来的"前端先 OCR、再调匹配、再调 AI"多次往返。本期保留 OCR 单路径，预留条码识别扩展点。
3. **「积分」入口 404 修复**：左上角"三"菜单中的积分入口由 `/points-center`（旧路由 404）修正为 `/points`（新版积分主页）。
4. **Toast 全局规范升级**：删除历史记录等场景的 Toast 现在统一走「水平居中 + 上方 1/3、3 种类型差异化配色（成功-绿/失败-红/警告-橙）」的规范。
5. **AI 对话模式 4 种卡片组件**：新增 `upload / navigate / sdk_call / quick_ask` 四种卡片组件文件，覆盖 PRD §5 全部卡片场景，可用于配置驱动的对话流卡片渲染。
6. **8 个新增埋点事件白名单**：`menu_exposure / menu_click / capsule_exposure / capsule_click / card_exposure / card_button_click / form_submit / card_fail`，便于运营/数据团队按 PRD §10 进行行为分析。
7. **数据库结构演进（自动迁移）**：`chat_function_buttons` 表自动新增 8 个字段，`medication_library` 表新增 `barcode` 字段（条码识别预留）。所有迁移幂等可重入，**用户原有数据 0 丢失**。

---

## 使用说明

### 1. 运营后台：配置功能按钮（含 4 种卡片体系）

1. 打开 [后台管理](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/) 并登录
2. 进入【AI 咨询配置 → 功能按钮管理】Tab
3. 点击「新增按钮」或编辑已有按钮，按钮类型可在下面 7 种中任选：
   - `digital_human_call` 数字人通话
   - `photo_upload` 拍照上传
   - `file_upload` 文件上传
   - `ai_chat_trigger` AI 对话触发
   - `external_link` 外部链接
   - `photo_recognize_drug` 拍照识药
   - `quick_ask` 快捷提问（**本次新增**）
4. 选择按钮类型后，下方会**条件展示**对应字段：
   - `ai_chat_trigger / file_upload / photo_recognize_drug / photo_upload` → 显示「关联 Prompt 模板」下拉，数据源来自【AI 配置中心 → Prompt 模板配置】
   - `external_link` → 显示「外部链接 URL」输入框
   - `quick_ask` → 显示「预设话术」文本域
5. 通用 8 字段（每种类型都需要填写）：
   - **自动用户消息**（必填）：点击按钮后插入对话流的用户气泡文案，例：`我想做体质测评`
   - **卡片标题**（必填）：卡片头部主标题
   - **卡片副标题**：卡片头部副标题（可选）
   - **卡片封面图 URL**：任意尺寸图片 URL
   - **按钮副说明文字**：显示在卡片主按钮下方，例：`约 6 道题，2 分钟完成`
6. 保存后立即生效，无需重启

### 2. H5 用户侧：体验"积分"入口修复

1. 在手机浏览器打开 [H5 AI 对话首页](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home) 并登录
2. 点击左上角"三"菜单展开侧边栏
3. 在资产 4 格区域点击「积分」一栏 → **直接进入新版积分主页**（旧路由 `/points-center` 404 已修复）

### 3. H5 用户侧：体验"删除历史记录" Toast 新规范

1. 进入 H5 AI 对话首页 → 左上角"三"菜单展开侧边栏
2. 长按或选中任意一条历史会话 → 删除
3. 删除成功的 Toast 现在 **水平居中 + 屏幕上方 1/3 + 绿底白字 + 对勾图标**（与 PRD §7 规范一致）；删除失败时为红底白字 + 叉号图标

### 4. 开发侧：调用一站式拍照识药接口

```bash
# 方式一：仅传 image_text（前端先调通用 /api/ocr/recognize 拿到 OCR 文字）
curl -X POST "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/api/prd469/medication-library/recognize" \
  -F "image_text=感冒灵颗粒" \
  -F "prompt_template_id=1"

# 返回结构：
# {
#   "code": 0,
#   "data": {
#     "recognized": true,
#     "method": "ocr",                     // 本期固定 ocr，未来扩展 barcode
#     "drug_candidates": [ {...}, {...} ], // 最多 5 条匹配候选
#     "ai_response": "<AI 解读文本>",
#     "matched_tokens": [...]              // OCR 抽取的关键词
#   }
# }
```

### 5. 开发侧：上报 8 个新埋点事件

```javascript
// 在前端任意位置：
fetch('/api/analytics/track', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    event: 'card_button_click',
    params: { button_key: '看报告', card_type: 'upload', sub_action: 'camera' },
    ts: Date.now()
  })
});
```

支持 8 个事件：`menu_exposure / menu_click / capsule_exposure / capsule_click / card_exposure / card_button_click / form_submit / card_fail`，全部已加入服务端白名单。

---

## 注意事项

1. **数据库迁移自动执行**：本次新增的 9 个字段（chat_function_buttons 8 个 + medication_library 1 个）都会在 backend 容器启动时自动 ALTER TABLE，无需手动操作。
2. **本期暂不做条码识别**：`/recognize` 接口的 `method` 字段本期固定返回 `"ocr"`，`MedicationLibrary.barcode` 字段仅建结构、不入库数据。等条码数据源谈下来后会增量发布。
3. **本期视频客服不改造**：保留现有 `VideoConsultConfig.seat_url` webview 方案，前端只把入口接通即可。
4. **本期积分页 6 页 UI 不重绘**：业务逻辑与现有积分模块完全保持一致，仅修复入口 404；UI 全量重绘列入下个迭代。
5. **4 种卡片组件**为基础版本（蓝紫渐变色调 + 标准布局），具体业务交互在后续迭代持续完善。
6. **全程零数据丢失**：本次升级**未删除任何数据库表/字段**、**未修改既有接口的请求/响应结构**，所有改动都是新增和兼容性扩展。
7. **历史按钮自动兼容**：旧的 `ai_dialog_trigger` / `drug_identify` 类型在前端会以"(旧)"标签兜底显示，建议运营在后台逐条修正为新枚举值（`ai_chat_trigger` / `photo_recognize_drug`）。

---

## 变更接口清单

| 类别 | 路径 | 方法 | 说明 |
|------|------|------|------|
| 新增 | `/api/prd469/medication-library/recognize` | POST | 一站式识药（OCR + 模糊匹配 + AI 解读） |
| 新增 | `/api/analytics/track` | POST | 8 个事件加入白名单（menu/capsule/card 全套） |
| 增强 | `/api/admin/function-buttons` | POST/PUT | 8 个新字段 + button_type 7 类枚举校验 |
| 增强 | `/api/chat/function-buttons` | GET | 公开接口响应自动包含 8 个新字段 |
| 兼容 | `/api/prd469/medication-library/ocr` | POST | 旧接口保留，新前端推荐使用 `/recognize` |

---

## 服务器自动化测试结果（2026-05-14）

```
=== 测试报告 ===
  [PASS] T1  /api/health 返回 200/ok
  [PASS] T2  H5 主页可达
  [PASS] T3  Admin 主页可达
  [PASS] T4  公开 function-buttons 200 + 列表
  [PASS] T5  admin function-buttons 未授权 401
  [PASS] T6  /medication-library/recognize 200 + 完整结构（含 drug_candidates / ai_response / method）
  [PASS] T7  analytics capsule_exposure 200
  [PASS] T8  analytics card_button_click 200
  [PASS] T9  medication-library/search 200
  [PASS] T10 medication-library/stats 200
  [PASS] T11 admin button_type 校验/鉴权返回 401
  [PASS] T12 H5 主页 HTML 长度 > 1000

总计：12/12 通过
```

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 主页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | AI 对话模式主入口（移动端 H5，建议在手机浏览器打开） |
| H5 AI 对话首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home) | 进入 AI 对话首页（功能宫格 + 对话流） |
| H5 积分主页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/points](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/points) | 修复后的积分主页入口（不再 404） |
| 后台管理 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/) | 运营后台（需登录），「功能按钮管理」Tab 已升级为 7 类型 + 8 字段 |
