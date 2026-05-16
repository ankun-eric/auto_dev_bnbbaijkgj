'use client';

/**
 * [PRD-DRUG-CARD-V3 2026-05-16] 适老化识药结果卡片
 *
 * 关键合规口径：
 * - 卡片按字段是否有值动态渲染，未识别字段整行不渲染
 * - **严禁** 出现「未收录」「未在权威库」「仅供参考」等技术词
 * - 未命中库时不渲染「用药提醒」区块（避免编造禁忌）
 * - 字号、按钮高度严格遵循适老化参数表（药品名 22px、按钮 44px）
 */
import React from 'react';

export type DrugCardFields = {
  library_id?: number | null;
  drug_name?: string | null;
  generic_name?: string | null;
  spec?: string | null;
  manufacturer?: string | null;
  approval_no?: string | null;
  category?: string | null;
  rx_type?: string | null;
  disease_tags?: string[] | null;
  indications?: string | null;
  usage?: string | null;
  contraindications?: string | null;
  adverse_reactions?: string | null;
};

export type ConflictInfo = {
  type: string;
  severity: 'high' | 'medium' | 'low';
  title: string;
  detail: string;
  block_add: boolean;
  matched_key?: string;
};

export interface DrugIdentifyCardProps {
  card: DrugCardFields;
  libraryMatched: boolean;
  conflicts?: ConflictInfo[];
  onAddPlan?: () => void;
  onViewAllPlans?: () => void;
}

const row = (label: string, value: any) => {
  if (value === null || value === undefined || value === '' || (Array.isArray(value) && value.length === 0)) {
    return null;
  }
  return (
    <div style={{ display: 'flex', gap: 8, marginBottom: 6, lineHeight: 1.7 }}>
      <span style={{ color: '#888', fontSize: 16, minWidth: 56 }}>{label}</span>
      <span style={{ color: '#333', fontSize: 16 }}>{Array.isArray(value) ? value.join('、') : String(value)}</span>
    </div>
  );
};

export default function DrugIdentifyCard(props: DrugIdentifyCardProps) {
  const { card, libraryMatched, conflicts = [], onAddPlan, onViewAllPlans } = props;
  const blockAdd = conflicts.some((c) => c.block_add);
  const highConflict = conflicts.find((c) => c.severity === 'high');

  return (
    <div
      data-testid="drug-identify-card"
      style={{
        background: '#fff',
        borderRadius: 12,
        padding: 16,
        boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
        margin: '8px 0',
        maxWidth: 520,
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
      </div>

      {/* 高危冲突横幅（L1） */}
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

      {/* 药品名（22px 加粗黑色） */}
      {card.drug_name && (
        <div style={{ fontSize: 22, fontWeight: 700, color: '#111', marginBottom: 10, lineHeight: 1.5 }}>
          {card.drug_name}
        </div>
      )}

      {row('通用名', card.generic_name)}
      {row('规格', card.spec)}
      {row('厂家', card.manufacturer)}
      {row('分类', card.category)}
      {row('类型', card.rx_type)}

      {/* 仅当命中权威库且有用法用量时才渲染（合规） */}
      {libraryMatched && card.usage && (
        <div style={{ marginTop: 12, padding: 12, background: '#F0F9FF', borderRadius: 8 }}>
          <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 6, color: '#0369A1' }}>💊 用法用量</div>
          <div style={{ fontSize: 16, color: '#333', lineHeight: 1.7 }}>{card.usage}</div>
        </div>
      )}

      {/* 仅当命中权威库且有禁忌时才渲染（合规） */}
      {libraryMatched && card.contraindications && (
        <div
          style={{
            marginTop: 12,
            padding: 12,
            background: '#FEF2F2',
            borderRadius: 8,
            border: '1px solid #FCA5A5',
          }}
          data-testid="warn-box"
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
            ⚠ 用药提醒
          </div>
          <div style={{ fontSize: 16, color: '#B91C1C', fontWeight: 600, lineHeight: 1.7 }}>
            {card.contraindications}
          </div>
        </div>
      )}

      {/* 按钮组 */}
      <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
        <button
          type="button"
          onClick={blockAdd ? undefined : onAddPlan}
          disabled={blockAdd}
          data-testid="btn-add-plan"
          style={{
            height: 48,
            borderRadius: 8,
            border: 'none',
            background: blockAdd ? '#D1D5DB' : '#1677FF',
            color: '#fff',
            fontSize: 16,
            fontWeight: 600,
            cursor: blockAdd ? 'not-allowed' : 'pointer',
          }}
        >
          {blockAdd ? '存在用药风险，无法加入' : '+ 加入用药计划'}
        </button>
        <button
          type="button"
          onClick={onViewAllPlans}
          data-testid="btn-view-plans"
          style={{
            height: 48,
            borderRadius: 8,
            border: '1px solid #D1D5DB',
            background: '#fff',
            color: '#333',
            fontSize: 16,
            cursor: 'pointer',
          }}
        >
          📋 查看全部用药计划
        </button>
      </div>
    </div>
  );
}
