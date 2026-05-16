'use client';
/**
 * [PRD-DRUG-CARD-V3 2026-05-16] 加入用药计划抽屉（最小可用版）
 *
 * 字段 1:1 复用 /ai-home/medication-plans/new 页面。
 * 完整字段在该页已实现，本抽屉提供快捷预填后跳转。
 */
import React from 'react';
import type { DrugCardFields } from './DrugIdentifyCard';

export interface AddMedicationDrawerProps {
  open: boolean;
  card: DrugCardFields;
  onClose: () => void;
}

export default function AddMedicationDrawer({ open, card, onClose }: AddMedicationDrawerProps) {
  if (!open) return null;
  const handleGoFull = () => {
    const params = new URLSearchParams();
    if (card.drug_name) params.set('drug_name', card.drug_name);
    if (card.generic_name) params.set('generic_name', card.generic_name);
    if (card.spec) params.set('spec', card.spec);
    if (card.manufacturer) params.set('manufacturer', card.manufacturer);
    if (card.disease_tags && card.disease_tags.length) {
      params.set('disease_tags', card.disease_tags.join(','));
    }
    window.location.href = `/ai-home/medication-plans/new?${params.toString()}`;
  };
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
          padding: 20,
          maxHeight: '90vh',
          overflowY: 'auto',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div style={{ fontSize: 18, fontWeight: 700 }}>加入用药计划</div>
          <button
            type="button"
            onClick={onClose}
            style={{ border: 'none', background: 'transparent', fontSize: 20, cursor: 'pointer' }}
            aria-label="close"
          >
            ✕
          </button>
        </div>
        <div style={{ fontSize: 16, color: '#333', marginBottom: 8, lineHeight: 1.7 }}>
          药品名：<b>{card.drug_name || '-'}</b>
        </div>
        {card.generic_name && (
          <div style={{ fontSize: 15, color: '#666', marginBottom: 6 }}>通用名：{card.generic_name}</div>
        )}
        {card.spec && <div style={{ fontSize: 15, color: '#666', marginBottom: 6 }}>规格：{card.spec}</div>}
        {card.manufacturer && (
          <div style={{ fontSize: 15, color: '#666', marginBottom: 6 }}>厂家：{card.manufacturer}</div>
        )}
        <div style={{ fontSize: 14, color: '#888', margin: '12px 0', lineHeight: 1.7 }}>
          完整字段（用药人、剂量、频次、起止日期、提醒、AI 外呼等）请进入用药计划新增页编辑。
        </div>
        <button
          type="button"
          onClick={handleGoFull}
          data-testid="btn-go-add-full"
          style={{
            height: 48,
            width: '100%',
            borderRadius: 8,
            border: 'none',
            background: '#1677FF',
            color: '#fff',
            fontSize: 16,
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          继续填写用药信息
        </button>
      </div>
    </div>
  );
}
