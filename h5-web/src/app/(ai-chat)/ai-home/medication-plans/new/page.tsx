'use client';

/**
 * [PRD-MED-PLAN-ENTRY-V1 2026-05-17] 用药计划新增表单页
 * 路由：/ai-home/medication-plans/new
 */

import { useRouter } from 'next/navigation';
import MedicationFormPanel from '@/components/medication/MedicationFormPanel';

export default function MedicationPlanNewPage() {
  const router = useRouter();
  return (
    <div data-testid="med-plans-new" style={{ minHeight: '100vh', background: '#F4F6F9', paddingBottom: 80 }}>
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
          onClick={() => router.back()}
          style={{ fontSize: 24, color: '#111827', cursor: 'pointer', padding: 4 }}
          data-testid="med-plans-new-back"
        >
          ←
        </span>
        <span style={{ flex: 1, textAlign: 'center', fontSize: 16, fontWeight: 600 }}>新增用药计划</span>
        <span style={{ width: 32 }} />
      </div>
      <MedicationFormPanel />
    </div>
  );
}
