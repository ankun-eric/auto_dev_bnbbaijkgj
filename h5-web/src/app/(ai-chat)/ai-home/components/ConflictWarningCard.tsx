'use client';
/**
 * [PRD-DRUG-CARD-V3 2026-05-16] 独立冲突警示卡（L4）
 *
 * 仅当存在 high 级冲突时渲染。提供「联系医生咨询」按钮。
 */
import React, { useEffect, useState } from 'react';
import type { ConflictInfo } from './DrugIdentifyCard';

export interface ConflictWarningCardProps {
  conflicts: ConflictInfo[];
  apiBase?: string;
}

export default function ConflictWarningCard({ conflicts, apiBase = '' }: ConflictWarningCardProps) {
  const highOnes = conflicts.filter((c) => c.severity === 'high');
  const [showHotline, setShowHotline] = useState(false);
  const [hotline, setHotline] = useState({
    hotline: '400-000-0000',
    label: '用药咨询专线',
    hours: '7×24h',
  });

  useEffect(() => {
    if (!showHotline) return;
    const url = `${apiBase}/api/v5/system-config/doctor-consult`;
    fetch(url)
      .then((r) => r.json())
      .then((data) => {
        if (data && data.code === 0 && data.data) {
          setHotline(data.data);
        }
      })
      .catch(() => {});
  }, [showHotline, apiBase]);

  if (highOnes.length === 0) return null;

  return (
    <div
      style={{
        background: '#FEF2F2',
        border: '2px solid #DC2626',
        borderRadius: 12,
        padding: 16,
        margin: '8px 0',
        maxWidth: 520,
      }}
      data-testid="conflict-warning-card"
    >
      <div style={{ fontSize: 18, fontWeight: 700, color: '#B91C1C', marginBottom: 10 }}>
        ⚠ 用药冲突警示
      </div>
      {highOnes.map((c, idx) => (
        <div key={idx} style={{ marginBottom: 10, lineHeight: 1.7 }}>
          <div style={{ fontSize: 16, fontWeight: 600, color: '#B91C1C' }}>{c.title}</div>
          <div style={{ fontSize: 15, color: '#7F1D1D' }}>{c.detail}</div>
          <div style={{ fontSize: 14, color: '#991B1B', marginTop: 4 }}>
            风险等级：{c.severity === 'high' ? '高' : c.severity === 'medium' ? '中' : '低'}
          </div>
        </div>
      ))}
      <button
        type="button"
        onClick={() => setShowHotline(true)}
        data-testid="btn-contact-doctor"
        style={{
          marginTop: 8,
          height: 48,
          width: '100%',
          borderRadius: 8,
          border: 'none',
          background: '#DC2626',
          color: '#fff',
          fontSize: 16,
          fontWeight: 600,
          cursor: 'pointer',
        }}
      >
        📞 联系医生咨询
      </button>

      {showHotline && (
        <div
          onClick={() => setShowHotline(false)}
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.4)',
            zIndex: 9999,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 20,
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: '#fff',
              borderRadius: 12,
              padding: 20,
              maxWidth: 360,
              width: '100%',
            }}
          >
            <div style={{ fontSize: 16, color: '#888', marginBottom: 8 }}>{hotline.label}</div>
            <a
              href={`tel:${hotline.hotline}`}
              style={{ fontSize: 24, fontWeight: 700, color: '#1677FF', textDecoration: 'none' }}
            >
              {hotline.hotline}
            </a>
            <div style={{ fontSize: 14, color: '#888', marginTop: 8 }}>服务时间：{hotline.hours}</div>
            <button
              type="button"
              onClick={() => {
                setShowHotline(false);
                window.location.href = '/experts';
              }}
              style={{
                marginTop: 16,
                height: 44,
                width: '100%',
                borderRadius: 8,
                border: '1px solid #1677FF',
                background: '#fff',
                color: '#1677FF',
                fontSize: 15,
                cursor: 'pointer',
              }}
            >
              前往专家咨询 →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
