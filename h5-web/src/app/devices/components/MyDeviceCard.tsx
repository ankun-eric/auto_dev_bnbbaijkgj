'use client';
/**
 * [PRD-MY-DEVICES-V1 2026-05-21] 「我的设备」已绑定设备卡片。
 */
import { DV_COLOR } from './theme';
import type { MyDeviceItem } from '@/lib/api/devices';

interface Props {
  item: MyDeviceItem;
  onEdit: (item: MyDeviceItem) => void;
  onUnbind: (item: MyDeviceItem) => void;
}

export default function MyDeviceCard({ item, onEdit, onUnbind }: Props) {
  const memberLabel = item.member_is_self
    ? '本人'
    : `${item.member_relation || ''}${item.member_relation && item.member_nickname ? '·' : ''}${item.member_nickname || ''}` || '—';
  return (
    <div
      data-testid={`bh-my-device-card-${item.id}`}
      style={{
        background: DV_COLOR.cardBg,
        borderRadius: 16,
        padding: 16,
        boxShadow: '0 2px 12px rgba(2,132,199,0.08)',
        border: `1px solid ${DV_COLOR.brand100}`,
        position: 'relative',
      }}
    >
      <button
        onClick={() => onEdit(item)}
        aria-label="编辑设备"
        data-testid={`bh-my-device-edit-${item.id}`}
        style={{
          position: 'absolute',
          top: 10,
          right: 10,
          width: 28,
          height: 28,
          borderRadius: 14,
          border: 'none',
          background: DV_COLOR.brand100,
          color: DV_COLOR.brand600,
          fontSize: 14,
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        ✎
      </button>
      <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
        <div
          style={{
            width: 44,
            height: 44,
            borderRadius: 12,
            background: DV_COLOR.brand100,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 24,
            flexShrink: 0,
          }}
        >
          {item.icon || '📱'}
        </div>
        <div style={{ flex: 1, minWidth: 0, paddingRight: 32 }}>
          <div
            style={{
              fontSize: 15,
              fontWeight: 600,
              color: DV_COLOR.textPrimary,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {item.device_name}
            {item.alias ? `（${item.alias}）` : ''}
          </div>
          <div style={{ fontSize: 12, color: DV_COLOR.textSecondary, marginTop: 4 }}>
            SN：{item.sn_masked || '—'}
          </div>
          <div style={{ fontSize: 12, color: DV_COLOR.textSecondary, marginTop: 2 }}>
            👤 使用人：{memberLabel}
          </div>
          <div style={{ fontSize: 12, color: DV_COLOR.textSecondary, marginTop: 2 }}>
            绑定时间：{item.bound_at || '—'}
          </div>
        </div>
      </div>
      <div style={{ marginTop: 12, display: 'flex', justifyContent: 'flex-end' }}>
        <button
          onClick={() => onUnbind(item)}
          data-testid={`bh-my-device-unbind-${item.id}`}
          style={{
            padding: '6px 16px',
            borderRadius: 16,
            border: `1px solid ${DV_COLOR.danger}`,
            background: '#fff',
            color: DV_COLOR.danger,
            fontSize: 13,
            fontWeight: 500,
            cursor: 'pointer',
          }}
        >
          解绑
        </button>
      </div>
    </div>
  );
}
