"""追加 PRD-HEALTH-METRIC-CARD-UNIFY-V1 章节到 project-context.mdc。"""
APPEND = """


## PRD-HEALTH-METRIC-CARD-UNIFY-V1（2026-05-31）健康指标卡片统一改造（血压/血糖/心率/血氧）

**目标**：建立通用的"健康指标详情页"模板，统一血压/血糖/心率/血氧四指标的卡片样式、历史交互（最近 5 条 + 全部入口）、修改/删除（左滑 + 二次确认）、AI 解读（本次/趋势），并新增**血氧（SpO₂）**模块。

**后端核心交付**：
- 新增 `backend/app/api/health_metric_card_v1.py` —— 路由前缀 `/api/health-metric-v1`：
  - `GET /{profile_id}/{metric_type}/history`：四指标通用历史接口，支持 4 个筛选项（日期范围/状态档位/测量场景/数据来源）+ 分页（page_size 默认 20）+ `editable` 字段（仅 manual 可改可删）+ `status`（key/label/color 三元组）
  - `POST /{profile_id}/{metric_type}/ai-explain-single` —— 四指标统一"本次解读"接口（规则降级文案，可后续接入 LLM）
  - `POST /{profile_id}/{metric_type}/ai-explain-trend` —— 四指标统一"趋势解读"接口（支持 7d/30d/90d）
  - `GET /{profile_id}/{metric_type}/{record_id}/can-delete` —— 删除前权限校验（PRD §4.3 设备同步记录禁删 + §4.5 信息回显）
  - `GET /meta` —— 元数据接口（四指标 label/unit/scene_options/状态色板）
- 复用现有 `health_metric_record` 表（已支持 5 种 metric_type 含 spo2）+ `health-profile-v3` 的 POST/PUT/DELETE 接口

**H5 核心交付**：
- 新增 `h5-web/src/app/health-metric/[type]/history/page.tsx` —— 全部历史页（四指标通用），含 4 项筛选、无限滚动、左滑删除、二次确认弹窗（信息完整版）、设备同步只读弹窗
- 调整 `h5-web/src/app/health-metric/[type]/page.tsx`：
  - 历史记录卡片改为只显示最近 5 条 + 右上角"全部 ›"入口
  - 新增 `MetricAiBlock` 可复用 AI 解读组件（🤖 解读本次 + 📈 解读 N 天趋势）
  - 血压/血糖详情页统一加入"全部 ›"入口

**测试**：`backend/tests/test_health_metric_card_unify_v1_20260531.py` —— 12 个测试用例（元数据、历史筛选、分页、排序、AI 解读 × 四指标、can-delete 权限、血氧全生命周期、未知类型拒绝、跨用户访问拒绝），**本地 + 远程容器 12/12 全通过**。

**远程冒烟**：`_smoke_card_unify_v1.py` 6/6 通过（meta 接口 + 四个全部历史页 + AI 接口路由）。

**部署**：`docker cp` backend + `docker compose build h5-web && up -d`。新页面直达：`/health-metric/{type}/history?profileId=1`（type ∈ blood_pressure/blood_glucose/heart_rate/spo2）。

**用户手册**：`user_docs/manual_20260531_013100_a7b2.md`
"""

with open(".cursor/rules/project-context.mdc", "a", encoding="utf-8") as f:
    f.write(APPEND)
print("OK, appended", len(APPEND), "chars.")
