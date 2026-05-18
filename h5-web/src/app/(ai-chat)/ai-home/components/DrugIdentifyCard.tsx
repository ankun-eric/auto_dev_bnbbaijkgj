'use client';

/**
 * [BUG_FIX_AI_HOME_DRUG_IDENTIFY_OPTIM_20260517 · Bug-2] 识药结果卡片 V4
 *
 * 相对 V3 的改动（依据本次 PRD）：
 * - 内容结构改为 4 大模块（自上而下）：
 *   ① 药品基础信息（A）：通用名 / 商品名 / 规格 / 剂型 / 厂家 / 批准文号
 *   ② 用法用量（B）：成人 / 儿童 用法用量、服药时机
 *   ③ 安全提示（C）：禁忌 / 不良反应 / 相互作用 / 特殊人群
 *   ④ 个性化风险提示（D）：风险等级标签 + 一句话结论 + 详细原因
 * - 操作按钮区固定在卡片最底部，内容超长时内容可滚动，按钮不被挤出
 * - 主按钮"加入用药计划"在 added=true 时变灰显示「已加入用药计划」，不可重复点击
 * - 历史 V3 的"识别成功徽章 / 红色横幅"逻辑保留兼容（向后兼容）
 *
 * 合规口径（沿用 V3）：
 * - 按字段是否有值动态渲染，未识别字段整行不渲染
 * - 严禁"未在权威库"等技术词
 * - 未命中库时不渲染"用药提醒"高风险红框（避免编造禁忌）
 */
import React from 'react';

export type DrugCardFields = {
  library_id?: number | null;
  drug_name?: string | null;
  generic_name?: string | null;
  brand_name?: string | null;
  spec?: string | null;
  dosage_form?: string | null;
  manufacturer?: string | null;
  approval_no?: string | null;
  category?: string | null;
  rx_type?: string | null;
  disease_tags?: string[] | null;
  indications?: string | null;
  // 用法用量
  usage?: string | null;
  usage_adult?: string | null;
  usage_children?: string | null;
  timing?: string | null;
  // 安全提示
  contraindications?: string | null;
  adverse_reactions?: string | null;
  interactions?: string | null;
  special_population?: string | null;
};

export type ConflictInfo = {
  type: string;
  severity: 'high' | 'medium' | 'low';
  title: string;
  detail: string;
  block_add: boolean;
  matched_key?: string;
};

/** [BUG_FIX_AI_HOME_DRUG_IDENTIFY_OPTIM_20260517] 个性化风险结论（来自 engine.meta.personalized_risk） */
export type PersonalizedRisk = {
  level: 'safe' | 'caution' | 'danger';
  label: string; // 例如 "⚠️ 不建议服用"
  conclusion: string;
  reasons?: string[];
};

export interface DrugIdentifyCardProps {
  card: DrugCardFields;
  libraryMatched: boolean;
  conflicts?: ConflictInfo[];
  /** [BUG_FIX_AI_HOME_DRUG_IDENTIFY_OPTIM_20260517 · Bug-2] 个性化风险结论 */
  personalizedRisk?: PersonalizedRisk | null;
  /** [BUG_FIX_AI_HOME_DRUG_IDENTIFY_OPTIM_20260517 · Bug-2] 当前选中咨询人姓名 */
  memberName?: string | null;
  /** [BUG_FIX_AI_HOME_DRUG_IDENTIFY_OPTIM_20260517 · Bug-3] 是否已加入用药计划 */
  added?: boolean;
  onAddPlan?: () => void;
  onViewDetail?: () => void;
  onRetake?: () => void;
  onViewAllPlans?: () => void;
}

const row = (label: string, value: any) => {
  if (value === null || value === undefined || value === '' || (Array.isArray(value) && value.length === 0)) {
    return null;
  }
  return (
    <div style={{ display: 'flex', gap: 8, marginBottom: 6, lineHeight: 1.7 }}>
      <span style={{ color: '#888', fontSize: 16, minWidth: 64, flexShrink: 0 }}>{label}</span>
      <span style={{ color: '#333', fontSize: 16, wordBreak: 'break-word' }}>
        {Array.isArray(value) ? value.join('、') : String(value)}
      </span>
    </div>
  );
};

const riskColor = (level: PersonalizedRisk['level']) => {
  if (level === 'danger') return { bg: '#FEF2F2', border: '#FCA5A5', text: '#B91C1C', tag: '#DC2626' };
  if (level === 'caution') return { bg: '#FFFBEB', border: '#FCD34D', text: '#92400E', tag: '#D97706' };
  return { bg: '#F0FDF4', border: '#86EFAC', text: '#166534', tag: '#16A34A' };
};

export default function DrugIdentifyCard(props: DrugIdentifyCardProps) {
  const {
    card,
    libraryMatched,
    conflicts = [],
    personalizedRisk,
    memberName,
    added = false,
    onAddPlan,
    onViewDetail,
    onRetake,
    onViewAllPlans,
  } = props;

  const blockAdd = conflicts.some((c) => c.block_add) || personalizedRisk?.level === 'danger';
  const highConflict = conflicts.find((c) => c.severity === 'high');

  return (
    <div
      data-testid="drug-identify-card"
      style={{
        background: '#fff',
        borderRadius: 12,
        boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
        margin: '8px 0',
        maxWidth: 520,
        display: 'flex',
        flexDirection: 'column',
        // [BUG_FIX_AI_HOME_DRUG_IDENTIFY_OPTIM_20260517 · Bug-2] 卡片整体最高 70vh，
        // 内容区可滚，按钮区固定在卡片最底部，永远不被挤出
        maxHeight: '70vh',
      }}
    >
      {/* —— 内容滚动区 —— */}
      <div
        data-testid="drug-card-scroll"
        style={{
          overflowY: 'auto',
          padding: '16px 16px 0 16px',
          flex: '1 1 auto',
          minHeight: 0,
        }}
      >
        {/* 顶部识别成功徽章 */}
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 12 }}>
          <span
            style={{
              background: '#52C41A',
              color: '#fff',
              fontSize: 14,
              padding: '4px 10px',
              borderRadius: 999,
              fontWeight: 600,
            }}
          >
            ✓ 识别成功
          </span>
          {memberName ? (
            <span style={{ marginLeft: 8, fontSize: 13, color: '#666' }}>
              · 已结合「{memberName}」档案
            </span>
          ) : null}
        </div>

        {/* 高危冲突横幅（V3 兼容） */}
        {highConflict && (
          <div
            style={{
              background: '#DC2626',
              color: '#fff',
              padding: '10px 12px',
              borderRadius: 8,
              fontSize: 16,
              fontWeight: 600,
              marginBottom: 12,
              lineHeight: 1.7,
            }}
            data-testid="conflict-banner"
          >
            ⚠ {highConflict.title}
          </div>
        )}

        {/* 药品名 */}
        {card.drug_name && (
          <div style={{ fontSize: 22, fontWeight: 700, color: '#111', marginBottom: 10, lineHeight: 1.5 }}>
            {card.drug_name}
          </div>
        )}

        {/* ① 药品基础信息 */}
        <div data-testid="drug-card-section-basic" style={{ marginTop: 4, marginBottom: 12 }}>
          <div style={{ fontSize: 14, color: '#1677FF', fontWeight: 600, marginBottom: 6 }}>① 药品基础信息</div>
          {row('通用名', card.generic_name)}
          {row('商品名', card.brand_name)}
          {row('规格', card.spec)}
          {row('剂型', card.dosage_form)}
          {row('厂家', card.manufacturer)}
          {row('批准文号', card.approval_no)}
          {row('分类', card.category)}
          {row('类型', card.rx_type)}
        </div>

        {/* ② 用法用量 —— 仅在命中库或字段有值时渲染（合规） */}
        {libraryMatched && (card.usage || card.usage_adult || card.usage_children || card.timing) && (
          <div
            data-testid="drug-card-section-usage"
            style={{ padding: 12, background: '#F0F9FF', borderRadius: 8, marginBottom: 12 }}
          >
            <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 6, color: '#0369A1' }}>
              ② 用法用量
            </div>
            {row('成人用法', card.usage_adult || card.usage)}
            {row('儿童用法', card.usage_children)}
            {row('服药时机', card.timing)}
          </div>
        )}

        {/* ③ 安全提示 —— 仅在命中库时才渲染（避免编造禁忌） */}
        {libraryMatched && (card.contraindications || card.adverse_reactions || card.interactions || card.special_population) && (
          <div
            data-testid="drug-card-section-safety"
            style={{
              padding: 12,
              background: '#FEF2F2',
              borderRadius: 8,
              border: '1px solid #FCA5A5',
              marginBottom: 12,
            }}
          >
            <div
              style={{
                display: 'inline-block',
                background: '#DC2626',
                color: '#fff',
                fontSize: 14,
                padding: '2px 8px',
                borderRadius: 4,
                marginBottom: 6,
                fontWeight: 600,
              }}
            >
              ③ 安全提示
            </div>
            {row('禁忌人群', card.contraindications)}
            {row('不良反应', card.adverse_reactions)}
            {row('相互作用', card.interactions)}
            {row('特殊人群', card.special_population)}
          </div>
        )}

        {/* ④ 个性化风险提示（基于当前选中成员档案） */}
        {personalizedRisk && (
          <div
            data-testid="drug-card-section-personalized"
            style={{
              padding: 12,
              background: riskColor(personalizedRisk.level).bg,
              borderRadius: 8,
              border: `1px solid ${riskColor(personalizedRisk.level).border}`,
              marginBottom: 16,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <span
                style={{
                  background: riskColor(personalizedRisk.level).tag,
                  color: '#fff',
                  fontSize: 13,
                  padding: '2px 8px',
                  borderRadius: 999,
                  fontWeight: 600,
                }}
              >
                {personalizedRisk.label}
              </span>
              <span style={{ fontSize: 13, color: '#666' }}>④ 个性化风险提示</span>
            </div>
            <div style={{ fontSize: 16, color: riskColor(personalizedRisk.level).text, fontWeight: 600, lineHeight: 1.7 }}>
              {personalizedRisk.conclusion}
            </div>
            {personalizedRisk.reasons && personalizedRisk.reasons.length > 0 && (
              <ul style={{ margin: '6px 0 0 0', paddingLeft: 18, fontSize: 14, color: '#555', lineHeight: 1.7 }}>
                {personalizedRisk.reasons.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      {/* —— ⑤ 操作按钮区（固定底部） ——
       * [PRD-AI-DRUG-CARD-MEDPLAN-V1 2026-05-18]
       *   - 「加入用药计划」/「已加入用药计划」 + 「查看用药计划」并列
       *   - 「已加入」态：灰色描边按钮 + 对勾，仍可点击
       *   - 空咨询人态：置灰不可点击 + Toast「请先选择咨询人」
       */}
      <div
        data-testid="drug-card-actions"
        style={{
          padding: 12,
          borderTop: '1px solid #F0F0F0',
          background: '#fff',
          borderBottomLeftRadius: 12,
          borderBottomRightRadius: 12,
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
          flexShrink: 0,
        }}
      >
        {/* 主按钮行：加入用药计划 + 查看用药计划 */}
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            type="button"
            onClick={blockAdd ? undefined : onAddPlan}
            disabled={blockAdd}
            data-testid="btn-add-plan"
            style={{
              flex: 1,
              height: 44,
              borderRadius: 8,
              border: added ? '1px solid #9CA3AF' : 'none',
              background: blockAdd ? '#D1D5DB' : added ? '#F3F4F6' : '#0EA5E9',
              color: added ? '#4B5563' : '#fff',
              fontSize: 15,
              fontWeight: 600,
              cursor: blockAdd ? 'not-allowed' : 'pointer',
            }}
          >
            {blockAdd
              ? '存在用药风险，无法加入'
              : added
              ? '✓ 已加入用药计划'
              : '+ 加入用药计划'}
          </button>
          <button
            type="button"
            onClick={onViewAllPlans}
            data-testid="btn-view-plans"
            style={{
              flex: 1,
              height: 44,
              borderRadius: 8,
              border: '1px solid #0EA5E9',
              background: '#fff',
              color: '#0EA5E9',
              fontSize: 15,
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            📋 查看用药计划
          </button>
        </div>
        {/* 次按钮行：药品详情 / 重新拍照 */}
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            type="button"
            onClick={onViewDetail}
            data-testid="btn-view-detail"
            style={{
              flex: 1,
              height: 36,
              borderRadius: 8,
              border: '1px solid #D1D5DB',
              background: '#fff',
              color: '#374151',
              fontSize: 13,
              cursor: 'pointer',
            }}
          >
            🔍 药品详情
          </button>
          <button
            type="button"
            onClick={onRetake}
            data-testid="btn-retake"
            style={{
              flex: 1,
              height: 36,
              borderRadius: 8,
              border: '1px solid #D1D5DB',
              background: '#fff',
              color: '#374151',
              fontSize: 13,
              cursor: 'pointer',
            }}
          >
            📷 重新拍照
          </button>
        </div>
      </div>
    </div>
  );
}
