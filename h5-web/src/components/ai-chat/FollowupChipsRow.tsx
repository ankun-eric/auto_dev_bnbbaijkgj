'use client';

/**
 * [PRD-TCM-CARD-MSG-PROTOCOL-V1 2026-05-20] AI 追问 chips 行（AI 侧）
 *
 * 渲染 3 个可点击的快捷 chip，作为本轮对话的最后一条 AI 消息。
 * - chips 本身**不带**「本次回答结合 XX 的档案」开场白
 * - 用户点击某个 chip → 触发后端 /api/questionnaire/followup-chip，
 *   后端返回的二轮回答**重新带上**开场白
 * - 点击后 chips 行整体置灰
 */

import React from 'react';

export interface FollowupChipItem {
  code: string;
  label: string;
}

interface Props {
  chips: FollowupChipItem[];
  disabled?: boolean;
  onClickChip: (chip: FollowupChipItem) => void;
}

export default function FollowupChipsRow({ chips, disabled, onClickChip }: Props) {
  if (!chips || chips.length === 0) return null;
  return (
    <div
      data-testid="followup-chips-row"
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: 8,
        marginTop: 4,
        maxWidth: 360,
      }}
    >
      {chips.map((chip) => (
        <button
          key={chip.code}
          type="button"
          data-testid={`followup-chip-${chip.code}`}
          disabled={!!disabled}
          onClick={() => !disabled && onClickChip(chip)}
          style={{
            padding: '6px 14px',
            background: disabled ? '#F1F5F9' : '#F0F9FF',
            color: disabled ? '#94A3B8' : '#0284C7',
            border: `1px solid ${disabled ? '#E2E8F0' : '#BAE6FD'}`,
            borderRadius: 20,
            fontSize: 13,
            fontWeight: 500,
            cursor: disabled ? 'not-allowed' : 'pointer',
            transition: 'all 0.15s',
          }}
        >
          {chip.label}
        </button>
      ))}
    </div>
  );
}
