# 健康自查功能优化 · AI 解读真接入大模型 — 用户体验使用手册

> 版本：v1.0  日期：2026-05-21  作者：小白

## 访问链接

以下是本次更新涉及的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 首页（AI 健康首页） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home) | 健康自查入口在此页面，点击「自查」按钮即可进入答题流程 |
| 健康自查结果页（动态路由示例） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-self-check/result/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-self-check/result/) | 答题完成后系统会跳转到 `/health-self-check/result/{答卷ID}` 展示结果 |
| 后台·通用问卷模板管理 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/) | 运营 / 医生可在「通用问卷模板」中编辑健康自查的 AI Prompt |

---

## 功能简介

本次更新针对「健康自查」功能做了 5 处用户可感知的优化，全部围绕「**结果页要够实用、够个性化**」这件事：

1. **删除「答题记录」整块区域** — 几十个问题都列出来意义不大，结果页瘦身后核心信息一目了然。
2. **AI 解读真接入大模型** — 以前结果页的「AI 解读」是写死的，**所有用户都看到一样的话**；本次起会基于用户填写的部位、症状、持续时间，以及健康档案中的既往病史、过敏史、在用药物、家族病史，**真正调用大模型生成个性化解读**。
3. **「居家处理建议」与「出现以下情况请立即就医」也由 AI 个性化生成**，不再是固定模板。
4. **新增「档案已更新」黄色提示条** — 当您改完健康档案里的关键信息（既往病史 / 过敏史 / 在用药物 / 家族史 / 年龄 / 性别）后，再打开旧的自查结果，顶部会温和地提醒您「档案已更新」，并提供「刷新 AI 解读」按钮一键重新生成；改头像、改昵称等非健康字段则**不会打扰**。
5. **AI 失败兜底** — 万一 AI 服务暂时不可用，结果页仍会展示「基于您填写的部位/症状的兜底建议」，并允许用户手动重试 AI 解读。

---

## 本次客户端变更

本次更新涉及以下终端的代码改动，请刷新页面即可体验最新版本：

| 终端 | 变更说明 | 新版本访问 |
|------|----------|------------|
| 后端 API | 健康自查异步任务真接入大模型；新增 `profile_outdated` 字段与档案快照比对；新增 `POST /api/questionnaire/answers/{id}/retry-ai` 重试接口（已存在的接口语义已升级） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/api/health](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/api/health) |
| H5 端（健康自查结果页） | 删除「答题记录」整块区域；新增「档案已更新」提示条；AI 解读以 Markdown 风格保留段落显示 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home) |

> ⚠️ 本次更新**不涉及**安卓、iOS、Windows、小程序、Flutter 等其他终端的代码改动，无需重新下载安装包。

---

## 使用说明

### 体验路径 A：首次完成健康自查

1. 用手机浏览器打开 [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home) 进入 AI 健康首页。
2. 登录账号；如未注册，请先注册并补全【健康档案】中至少：年龄 / 性别 / 既往病史 / 过敏史 / 在用药物 / 家族病史 六项（建议都填，才能获得最个性化的 AI 解读）。
3. 点击「健康自查」按钮，按引导依次选择：**身体部位 → 症状 → 性质 → 严重程度 → 持续时间 → 备注**。
4. 提交答卷后，系统会跳转到「健康自查结果」页。
5. 此时页面顶部摘要条会显示：「🩺 健康自查报告 · 已完成本次健康自查 · 本次回答结合 本人 的健康档案」。
6. **AI 解读** / **居家处理建议** / **出现以下情况请立即就医** 三块均由大模型根据您填写的内容个性化生成。
7. 如 AI 正在生成（pending 状态），页面顶部会出现一个蓝色的「AI 正在分析中…」横条，结果生成后会自动刷新。

### 体验路径 B：档案更新后刷新 AI 解读

1. 完成一次健康自查（记下结果页 URL，如 `/health-self-check/result/123`）。
2. 进入「我的 / 健康档案」页面，修改任意一项**关键字段**（既往病史 / 过敏史 / 在用药物 / 家族病史 / 年龄 / 性别）。
3. 再次打开第 1 步记下的结果页 URL，您会看到顶部多了一条**黄色提示**：
   > 您的健康档案已更新，AI 解读基于旧档案生成 [刷新 AI 解读]
4. 点击「刷新 AI 解读」按钮，系统会立即重新调用大模型；按钮变灰、弹出「已重新触发 AI 解读」Toast；几秒后页面自动刷新，呈现基于新档案的解读。
5. 提示条消失，提示已被消除。

> 💡 仅修改昵称 / 头像 / 邮箱等非健康字段不会出现提示条 —— 这是 A+++ 缓存失效策略：**只在与诊断真正相关的字段变动时打扰用户**。

### 体验路径 C：AI 失败时的兜底体验

1. 当 AI 服务暂时不可用（如网络抖动、模型限流），结果页仍会展示「**基于您填写的部位/症状的兜底建议**」，确保用户拿到可用内容。
2. 若状态条变红「AI 解读暂时失败」，可点击右侧「重试解读」按钮重新触发；正常情况下系统会自动重试并恢复。

---

## 注意事项

1. **AI 解读仅供参考**：所有 AI 输出均为初步分析，**不构成医疗诊断**；若症状持续或加重，请尽快前往正规医疗机构就诊。
2. **首次进入会有几秒等待**：AI 接 LLM 生成结果一般 3~8 秒，期间页面顶部会展示「AI 正在为您生成个性化解读…」骨架文案。
3. **缓存策略友好**：首次生成完成后再次进入同一答卷，**不会重复消耗 Token**，秒开。只有当您手动点「刷新 AI 解读」或改了健康档案关键字段才会重新生成。
4. **运营 / 医生可配置 Prompt**：后台「通用问卷模板管理」中的「健康自查」模板，可编辑其 `AI Prompt Template`，所有占位符均**统一为中文**（`{部位}` / `{症状列表}` / `{档案既往病史}` 等），与"占位符速查表"保持一致；不会再出现「正文中文、速查表英文」造成 AI 看不懂占位符的旧 Bug。
5. **结果页不再有「答题记录」区块**：精简为 AI 解读 / 居家建议 / 就医警示 / 推荐商品 / 底部 CTA 五大区块，体验更聚焦。

---

## 验收要点（运营 / 测试可参考）

- [x] 提交答卷后，详情接口 `GET /api/questionnaire/answers/{id}` 返回值新增 `profile_outdated` 与 `ai_generated_at`。
- [x] 详情接口仍返回 `ai_full_interpretation` / `home_care_tips` / `red_flag_signals` 三大字段；当 LLM 返回非合法 JSON 时，自动降级使用兜底模板。
- [x] 结果页**不再显示**「您的答题记录」整块区域。
- [x] 修改健康档案的关键字段后再次打开旧答卷，顶部出现黄色「档案已更新」提示条 + 「刷新 AI 解读」按钮。
- [x] 通用问卷模板管理后台的 `health_self_check` 模板，`ai_prompt_template` 不再包含旧版错误占位符 `{scores}` / `{main_type}` / `{body_parts}`。
- [x] 后端 pytest 用例 `tests/test_hsc_ai_real_v1_20260521.py` 全 7 个用例通过。

---

## 访问链接

以下是本次更新涉及的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 首页（AI 健康首页） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home) | 健康自查入口在此页面，点击「自查」按钮即可进入答题流程 |
| 健康自查结果页（动态路由示例） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-self-check/result/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-self-check/result/) | 答题完成后系统会跳转到 `/health-self-check/result/{答卷ID}` 展示结果 |
| 后台·通用问卷模板管理 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/) | 运营 / 医生可在「通用问卷模板」中编辑健康自查的 AI Prompt |
