'use client';
/**
 * [PRD-MY-DEVICES-V1 2026-05-21] 「支持设备列表」按品牌分区展示。
 */
import type { CatalogGroup, CatalogItem } from '@/lib/api/devices';
import { BRAND_BADGE, DV_COLOR } from './theme';

interface Props {
  group: CatalogGroup;
  onBind: (item: CatalogItem) => void;
}

function buttonState(item: CatalogItem): {
  text: string;
  bg: string;
  color: string;
  border?: string;
  disabled: boolean;
  testid: string;
} {
  if (!item.is_active) {
    return {
      text: '敬请期待',
      bg: DV_COLOR.grayBg,
      color: DV_COLOR.gray,
      disabled: true,
      testid: 'btn-soon',
    };
  }
  if (item.is_unique && item.bound_count >= 1) {
    return {
      text: '已绑定',
      bg: DV_COLOR.grayBg,
      color: DV_COLOR.gray,
      disabled: true,
      testid: 'btn-bound',
    };
  }
  if (!item.is_unique && item.bound_count >= 1) {
    return {
      text: '继续绑定',
      bg: '#FFFFFF',
      color: DV_COLOR.brand600,
      border: `1px solid ${DV_COLOR.brand500}`,
      disabled: false,
      testid: 'btn-bind-more',
    };
  }
  return {
    text: '绑定',
    bg: DV_COLOR.brand500,
    color: '#FFFFFF',
    disabled: false,
    testid: 'btn-bind',
  };
}

export default function BrandSection({ group, onBind }: Props) {
  const badge = BRAND_BADGE[group.brand_code] || BRAND_BADGE.other;
  return (
    <div
      data-testid={`bh-brand-section-${group.brand_code}`}
      style={{
        background: DV_COLOR.cardBg,
        borderRadius: 16,
        padding: 16,
        boxShadow: '0 2px 12px rgba(2,132,199,0.06)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '4px 12px',
            borderRadius: 12,
            background: badge.bg,
            color: badge.color,
            fontSize: 13,
            fontWeight: 600,
          }}
        >
          {group.brand_name}
        </span>
        <span style={{ fontSize: 12, color: DV_COLOR.textSecondary }}>
          {group.items.length} 项
        </span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {group.items.map((item) => {
          const st = buttonState(item);
          return (
            <div
              key={item.id}
              data-testid={`bh-catalog-item-${item.id}`}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                padding: 10,
                background: DV_COLOR.brand50,
                borderRadius: 12,
              }}
            >
              <div
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: 10,
                  background: '#FFFFFF',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 20,
                  flexShrink: 0,
                }}
              >
                {item.icon || '📱'}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    fontSize: 14,
                    fontWeight: 600,
                    color: DV_COLOR.textPrimary,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {item.device_name}
                </div>
                <div style={{ fontSize: 11, color: DV_COLOR.textSecondary, marginTop: 2 }}>
                  {group.brand_name} · {item.is_unique ? '唯一绑定' : '支持多台'}
                </div>
              </div>
              <button
                data-testid={`bh-catalog-btn-${item.id}`}
                data-state={st.testid}
                disabled={st.disabled}
                onClick={() => !st.disabled && onBind(item)}
                style={{
                  padding: '6px 14px',
                  borderRadius: 16,
                  border: st.border || 'none',
                  background: st.bg,
                  color: st.color,
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: st.disabled ? 'not-allowed' : 'pointer',
                  flexShrink: 0,
                  minWidth: 78,
                }}
              >
                {st.text}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
