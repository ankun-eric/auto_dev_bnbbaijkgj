# 老健康自查 (PRD-HEALTH-SELF-CHECK-V1) 代码备份

> 备份时间：2026-05-19
> 触发 PRD：PRD-QUESTIONNAIRE-DRAWER-V1（健康自查抽屉化 + 新版问卷模板体系融合）

## 备份原因

PRD-QUESTIONNAIRE-DRAWER-V1 将健康自查、体质测评等问卷类业务统一收敛到「通用问卷
模板（questionnaire_template）+ AI 功能按钮（chat_function_buttons）」一套架构。
本目录是改造前老实现的快照副本，方便回滚或对照参考。

**注意**：仓库主目录里的同名文件 **未删除**，只是已标记为
`@Deprecated` / 老接口路径保留 410 Gone 兼容期。

## 文件清单

| 备份路径 | 原路径 |
|---|---|
| `backend/api/health_self_check.py` | `backend/app/api/health_self_check.py` |
| `backend/schemas/health_self_check.py` | `backend/app/schemas/health_self_check.py` |
| `h5-web/components/HealthSelfCheckDrawer.tsx` | `h5-web/src/components/ai-chat/HealthSelfCheckDrawer.tsx` |
| `h5-web/components/HealthSelfCheckCard.tsx` | `h5-web/src/components/ai-chat/HealthSelfCheckCard.tsx` |

## 数据迁移

老数据资产迁移到新架构的位置如下：

| 老数据 | 新位置 |
|---|---|
| `body_part_dict.name / icon` | `questionnaire_question`（"部位"题）→ `options[].label / icon` |
| `body_part_dict.symptoms[]` | `questionnaire_question`（"症状"题）→ `option_filter_json.filter_map` |
| `health_check_templates.duration_options[]` | `questionnaire_question`（"持续时间"题）→ `options` |
| `health_check_templates.default_prompt` | `questionnaire_template.ai_prompt_template` |
| 部位↔症状关联 | `questionnaire_question.option_filter_json` |
| AI Prompt 覆盖 | `chat_function_buttons.prompt_override_text`（保留） |

迁移脚本：`backend/app/services/prd_questionnaire_drawer_v1_migration.py`

## 还原方法

如需还原：
1. 把本目录下 `backend/*` 和 `h5-web/*` 的文件复制回原路径覆盖
2. 在数据库中执行：
   - `UPDATE chat_function_buttons SET ai_function_type='health_self_check', questionnaire_template_id=NULL, questionnaire_display_form=NULL WHERE ai_function_type='questionnaire' AND questionnaire_template_id={健康自查模板ID};`
3. 重启后端
