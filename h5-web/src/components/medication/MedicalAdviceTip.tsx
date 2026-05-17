'use client';

/**
 * [PRD-MED-PLAN-OPTIM-V1 2026-05-17] 顶部医嘱提示条（Tip-B 黄底警示）
 *
 * - 常驻不可关闭
 * - 文案固定："用药请遵循医嘱"
 * - 背景 #FFFBEB / 边框 #FDE68A / 字色 #92400E / 图标 #F59E0B
 */

export default function MedicalAdviceTip() {
  return (
    <div
      data-testid="med-advice-tip"
      style={{
        margin: '12px 14px 8px',
        padding: '10px 12px',
        background: '#FFFBEB',
        border: '1px solid #FDE68A',
        borderRadius: 10,
        display: 'flex',
        alignItems: 'center',
        gap: 10,
      }}
    >
      <span
        aria-hidden
        style={{
          width: 18,
          height: 18,
          borderRadius: 9,
          background: '#F59E0B',
          color: '#fff',
          fontSize: 13,
          lineHeight: '18px',
          textAlign: 'center',
          fontWeight: 700,
          flexShrink: 0,
        }}
      >
        !
      </span>
      <span style={{ color: '#92400E', fontSize: 13, fontWeight: 500 }}>
        用药请遵循医嘱
      </span>
    </div>
  );
}
