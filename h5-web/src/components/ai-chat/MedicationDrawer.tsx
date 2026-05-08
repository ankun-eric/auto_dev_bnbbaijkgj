'use client';

/**
 * [PRD-432 2026-05-09] 长期用药半屏抽屉
 *
 * 由 ProfileCard 中"长期用药"行点击触发：在当前 AI 对话页内弹出底部抽屉
 * - 标题栏：长期用药 / 去管理 ›
 * - 列表项：药品名 + 剂量/频次/已服用天数（只读）
 * - 空状态：插画 + "暂无长期用药，点击添加 ›" → 跳转到用药管理设置页新增态
 */

import { useEffect, useState } from 'react';
import api from '@/lib/api';

interface MedicationItem {
  id: number;
  medicine_name: string;
  dosage: string;
  frequency: string;
  used_days: number;
}

interface MedicationsPayload {
  consultant_id: number;
  nickname: string;
  items: MedicationItem[];
  is_none: boolean;
  total: number;
}

interface MedicationDrawerProps {
  consultantId: number;
  consultantName: string;
  onClose: () => void;
  onGoManage: () => void;
  onGoCreate: () => void;
}

export default function MedicationDrawer({
  consultantId,
  consultantName,
  onClose,
  onGoManage,
  onGoCreate,
}: MedicationDrawerProps) {
  const [data, setData] = useState<MedicationsPayload | null>(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .get(`/api/v1/consultant/${consultantId}/medications`)
      .then((res) => {
        if (cancelled) return;
        setData(res.data);
        setError(false);
      })
      .catch(() => {
        if (cancelled) return;
        setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [consultantId]);

  const items = data?.items || [];
  const isEmpty = items.length === 0 && !data?.is_none;

  return (
    <div
      data-testid="ai-medication-drawer-mask"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'rgba(0,0,0,0.4)',
        zIndex: 200,
        display: 'flex',
        alignItems: 'flex-end',
      }}
    >
      <div
        data-testid="ai-medication-drawer"
        style={{
          width: '100%',
          maxHeight: '50vh',
          background: '#fff',
          borderTopLeftRadius: 16,
          borderTopRightRadius: 16,
          padding: '8px 0 12px',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <div style={{ width: 36, height: 4, background: '#E5E7EB', borderRadius: 2, margin: '4px auto 8px' }} />
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '0 16px 10px',
            borderBottom: '1px solid #F3F4F6',
          }}
        >
          <div style={{ fontSize: 16, fontWeight: 600 }}>长期用药</div>
          <div
            data-testid="ai-medication-drawer-go-manage"
            onClick={onGoManage}
            style={{ color: '#2563EB', fontSize: 14, cursor: 'pointer' }}
          >
            去管理 ›
          </div>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '8px 16px' }}>
          {loading && (
            <div style={{ textAlign: 'center', color: '#9CA3AF', padding: 20 }}>加载中...</div>
          )}
          {!loading && error && (
            <div style={{ textAlign: 'center', color: '#EF4444', padding: 20 }}>
              加载失败，请稍后再试
            </div>
          )}
          {!loading && !error && data?.is_none && (
            <div style={{ textAlign: 'center', color: '#6B7280', padding: 30 }}>
              {consultantName} 当前无长期用药
            </div>
          )}
          {!loading && !error && isEmpty && (
            <div data-testid="ai-medication-drawer-empty" style={{ textAlign: 'center', padding: 30 }}>
              <div style={{ fontSize: 56, marginBottom: 12 }}>💊</div>
              <div
                onClick={onGoCreate}
                style={{
                  color: '#2563EB',
                  fontSize: 14,
                  cursor: 'pointer',
                  fontWeight: 500,
                }}
              >
                暂无长期用药，点击添加 ›
              </div>
            </div>
          )}
          {!loading && !error && items.length > 0 && (
            <div>
              {items.map((it, idx) => (
                <div
                  key={it.id}
                  data-testid={`ai-medication-drawer-item-${idx}`}
                  style={{
                    padding: '10px 0',
                    borderBottom: idx === items.length - 1 ? 'none' : '1px solid #F3F4F6',
                  }}
                >
                  <div style={{ fontSize: 15, fontWeight: 500, color: '#111827' }}>
                    💊 {it.medicine_name}
                  </div>
                  <div style={{ fontSize: 12, color: '#6B7280', marginTop: 4 }}>
                    {[it.dosage, it.frequency, it.used_days > 0 ? `已服用 ${it.used_days} 天` : null]
                      .filter(Boolean)
                      .join(' / ')}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
