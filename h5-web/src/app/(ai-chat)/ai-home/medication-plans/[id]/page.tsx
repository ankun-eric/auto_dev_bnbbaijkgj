'use client';

/**
 * [PRD-MED-PLAN-ENTRY-V1 2026-05-17] 用药计划详情/编辑页
 * 路由：/ai-home/medication-plans/:id
 */

import { useParams, useRouter } from 'next/navigation';
import MedicationFormPanel from '@/components/medication/MedicationFormPanel';

export default function MedicationPlanDetailPage() {
  const router = useRouter();
  const params = useParams() as { id?: string };
  const planId = params?.id ? Number(params.id) : undefined;
  if (!planId || Number.isNaN(planId)) {
    return (
      <div style={{ padding: 40, textAlign: 'center', color: '#6B7280' }}>
        无效的用药计划 ID
      </div>
    );
  }
  return (
    <div data-testid="med-plans-detail" style={{ minHeight: '100vh', background: '#F4F6F9', paddingBottom: 80 }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          padding: '12px 16px',
          background: '#fff',
          boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
        }}
      >
        <span
          onClick={() => router.push('/ai-home/medication-plans')}
          style={{ fontSize: 24, color: '#111827', cursor: 'pointer', padding: 4 }}
          data-testid="med-plans-detail-back"
        >
          ←
        </span>
        <span style={{ flex: 1, textAlign: 'center', fontSize: 16, fontWeight: 600 }}>用药计划详情</span>
        <span style={{ width: 32 }} />
      </div>
      <MedicationFormPanel planId={planId} />
    </div>
  );
}
