'use client';
/**
 * [PRD-AI-DRUG-CARD-MEDPLAN-V1 2026-05-18] 加入用药计划抽屉
 *
 * 复用 MedicationFormPanel 的全部字段，在抽屉内就地完成新增，不再跳转新页面。
 * 抽屉支持：
 *   - 自动预填药品名 / 通用名
 *   - 关联当前 AI 对话页咨询人（family_member_id）
 *   - 保存成功 → onSaved 回调（识药卡片立即变为「已加入」+ Toast）
 *   - 保存失败 → 抽屉不关闭，Toast 提示错误
 */
import React from 'react';
import MedicationFormPanel from '@/components/medication/MedicationFormPanel';
import type { DrugCardFields } from './DrugIdentifyCard';

export interface AddMedicationDrawerProps {
  open: boolean;
  card: DrugCardFields;
  /** 当前 AI 对话页选中咨询人 family_member.id；本人态传 null/0 */
  familyMemberId?: number | null;
  /** 咨询人昵称（用于抽屉标题）；本人态传空 */
  consultantName?: string | null;
  /** 是否本人态（隐藏咨询人姓名前缀） */
  isSelf?: boolean;
  onClose: () => void;
  /** 保存成功回调 */
  onSaved?: (newId: number | null) => void;
}

export default function AddMedicationDrawer({
  open,
  card,
  familyMemberId,
  consultantName,
  isSelf,
  onClose,
  onSaved,
}: AddMedicationDrawerProps) {
  if (!open) return null;

  const title = isSelf || !consultantName
    ? '加入用药计划'
    : `为 ${consultantName} 加入用药计划`;

  const prefillName =
    card.drug_name ||
    card.generic_name ||
    card.brand_name ||
    '';
  const prefillGeneric = card.generic_name || undefined;

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.45)',
        zIndex: 9998,
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'center',
      }}
      data-testid="add-medication-drawer"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: '#fff',
          width: '100%',
          maxWidth: 600,
          borderTopLeftRadius: 16,
          borderTopRightRadius: 16,
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <div
          style={{
            padding: '14px 16px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            borderBottom: '1px solid #F0F0F0',
            flexShrink: 0,
          }}
        >
          <div style={{ fontSize: 17, fontWeight: 700, color: '#111827' }} data-testid="add-med-drawer-title">
            {title}
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{ border: 'none', background: 'transparent', fontSize: 22, cursor: 'pointer', color: '#6B7280' }}
            aria-label="close"
            data-testid="add-med-drawer-close"
          >
            ✕
          </button>
        </div>
        <div style={{ flex: 1, overflowY: 'auto' }}>
          <MedicationFormPanel
            key={`add-${prefillName}`}
            mode="drawer"
            prefillName={prefillName}
            prefillGenericName={prefillGeneric}
            familyMemberId={familyMemberId ?? null}
            hideDelete
            onSaved={(id) => {
              onSaved?.(id);
              onClose();
            }}
            onCancel={onClose}
          />
        </div>
      </div>
    </div>
  );
}
