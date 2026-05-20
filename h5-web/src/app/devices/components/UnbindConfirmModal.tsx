'use client';
/**
 * [PRD-MY-DEVICES-V1 2026-05-21] 解绑二次确认 Modal。
 */
import { DV_COLOR } from './theme';
import type { MyDeviceItem } from '@/lib/api/devices';

interface Props {
  visible: boolean;
  item: MyDeviceItem | null;
  onCancel: () => void;
  onConfirm: () => void;
  submitting?: boolean;
}

export default function UnbindConfirmModal({ visible, item, onCancel, onConfirm, submitting }: Props) {
  if (!visible) return null;
  return (
    <div
      data-testid="bh-unbind-confirm-modal"
      onClick={onCancel}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.45)',
        zIndex: 200,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: '#fff',
          width: '100%',
          maxWidth: 360,
          borderRadius: 16,
          padding: 20,
          boxShadow: '0 20px 40px rgba(0,0,0,0.18)',
        }}
      >
        <div style={{ fontSize: 17, fontWeight: 600, color: DV_COLOR.textPrimary, marginBottom: 12 }}>
          确认解绑此设备？
        </div>
        <div
          style={{
            fontSize: 14,
            color: DV_COLOR.textSecondary,
            lineHeight: 1.6,
            background: DV_COLOR.brand50,
            borderRadius: 10,
            padding: 12,
            marginBottom: 18,
          }}
        >
          <div style={{ marginBottom: 6 }}>
            解绑后，<strong style={{ color: DV_COLOR.danger }}>该设备将不再上传新数据</strong>到你的健康档案。
          </div>
          <div>
            已上传的<strong style={{ color: DV_COLOR.textPrimary }}>历史数据将保留</strong>，可在健康档案中查看。
          </div>
          {item ? (
            <div style={{ marginTop: 8, fontSize: 12, color: DV_COLOR.gray }}>
              设备：{item.device_name}
              {item.alias ? `（${item.alias}）` : ''} · SN：{item.sn_masked || '—'}
            </div>
          ) : null}
        </div>
        <div style={{ display: 'flex', gap: 12 }}>
          <button
            onClick={onCancel}
            style={{
              flex: 1, height: 42, borderRadius: 21,
              border: `1px solid ${DV_COLOR.border}`,
              background: '#fff', color: DV_COLOR.textPrimary,
              fontSize: 14, fontWeight: 500, cursor: 'pointer',
            }}
          >取消</button>
          <button
            onClick={onConfirm}
            disabled={submitting}
            data-testid="bh-unbind-confirm-ok"
            style={{
              flex: 1, height: 42, borderRadius: 21, border: 'none',
              background: DV_COLOR.danger, color: '#fff',
              fontSize: 14, fontWeight: 600,
              cursor: submitting ? 'not-allowed' : 'pointer',
              opacity: submitting ? 0.7 : 1,
            }}
          >{submitting ? '解绑中…' : '确认解绑'}</button>
        </div>
      </div>
    </div>
  );
}
