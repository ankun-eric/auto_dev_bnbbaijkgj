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
      {/* [PRD-HEALTH-ARCHIVE-FAMILY-MEMBER-V1 2026-06-02 改动点2]
          标题改为居中 + 主题蓝色 #1677FF，与 App 标准页面标题样式对齐。
          采用与 GreenNavBar 一致的视觉规范：白底导航条 + 主题蓝标题 + 主题蓝返回箭头。 */}
      <div
        style={{
          position: 'relative',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '12px 16px',
          background: '#fff',
          boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
          minHeight: 46,
        }}
      >
        <span
          onClick={() => router.back()}
          style={{
            position: 'absolute',
            left: 12,
            top: '50%',
            transform: 'translateY(-50%)',
            fontSize: 22,
            color: '#1677FF',
            cursor: 'pointer',
            padding: 4,
            lineHeight: 1,
          }}
          data-testid="med-plans-new-back"
        >
          ‹
        </span>
        <span
          style={{
            fontSize: 17,
            fontWeight: 600,
            color: '#1677FF',
            textAlign: 'center',
          }}
        >
          新增用药计划
        </span>
      </div>
      <MedicationFormPanel />
    </div>
  );
}
