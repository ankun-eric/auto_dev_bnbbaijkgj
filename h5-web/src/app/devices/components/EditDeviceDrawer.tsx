'use client';
/**
 * [PRD-MY-DEVICES-V1 2026-05-21] 编辑设备抽屉。
 *
 * - SN / 品类不可改
 * - 可改：别名 / 使用人
 */
import { useEffect, useMemo, useState } from 'react';
import { Popup } from 'antd-mobile';
import { showToast } from '@/lib/toast-unified';
import type { MyDeviceItem, EditBindingPayload } from '@/lib/api/devices';
import ConsultTargetPicker, { type FamilyMemberItem } from '@/components/ai-chat/ConsultTargetPicker';
import api from '@/lib/api';
import { DV_COLOR } from './theme';

interface Props {
  visible: boolean;
  item: MyDeviceItem | null;
  onClose: () => void;
  onSubmit: (payload: EditBindingPayload) => Promise<void>;
}

export default function EditDeviceDrawer({ visible, item, onClose, onSubmit }: Props) {
  const [alias, setAlias] = useState('');
  const [memberId, setMemberId] = useState<number | null>(null);
  const [memberLabel, setMemberLabel] = useState('本人');
  const [picking, setPicking] = useState(false);
  const [selfMemberId, setSelfMemberId] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!visible || !item) return;
    setAlias(item.alias || '');
    setMemberId(item.member_id ?? null);
    const lbl = item.member_is_self
      ? `本人${item.member_nickname ? ' · ' + item.member_nickname : ''}`
      : `${item.member_relation || ''}${item.member_relation && item.member_nickname ? ' · ' : ''}${item.member_nickname || ''}` || '本人';
    setMemberLabel(lbl);
    (async () => {
      try {
        const res: any = await api.get('/api/family/members');
        const data = res?.data || res;
        const list: FamilyMemberItem[] = Array.isArray(data?.items) ? data.items : Array.isArray(data) ? data : [];
        const self = list.find((m) => m.is_self);
        setSelfMemberId(self ? self.id : null);
      } catch {
        setSelfMemberId(null);
      }
    })();
  }, [visible, item]);

  const title = useMemo(() => (item ? `编辑 ${item.device_name}` : '编辑设备'), [item]);

  const handleSubmit = async () => {
    if (!item) return;
    if (alias.length > 20) {
      showToast('别名不超过 20 字', 'fail');
      return;
    }
    setSubmitting(true);
    try {
      await onSubmit({ alias: alias.trim() || null, member_id: memberId });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <Popup
        visible={visible}
        onMaskClick={onClose}
        position="bottom"
        bodyStyle={{ borderRadius: '16px 16px 0 0', maxHeight: '80vh', overflow: 'auto' }}
        data-testid="bh-edit-device-drawer"
      >
        <div style={{ padding: 20 }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: 16,
              paddingBottom: 12,
              borderBottom: `1px solid ${DV_COLOR.brand100}`,
            }}
          >
            <span style={{ fontSize: 17, fontWeight: 600, color: DV_COLOR.textPrimary }}>{title}</span>
            <button onClick={onClose} style={{ border: 'none', background: 'transparent', fontSize: 22, color: DV_COLOR.gray, cursor: 'pointer' }}>×</button>
          </div>

          <div style={{ marginBottom: 14, fontSize: 12, color: DV_COLOR.textSecondary }}>
            SN：{item?.sn_masked || '—'}（SN 与设备品类不可修改，需要更换请先解绑）
          </div>

          <div style={{ marginBottom: 16 }}>
            <label style={{ fontSize: 13, fontWeight: 500, color: DV_COLOR.textPrimary, display: 'block', marginBottom: 6 }}>
              别名（选填）
            </label>
            <input
              value={alias}
              onChange={(e) => setAlias(e.target.value.slice(0, 20))}
              placeholder="如 爸爸的手表（最多 20 字）"
              data-testid="bh-edit-alias-input"
              style={{
                width: '100%',
                height: 40,
                borderRadius: 10,
                border: `1px solid ${DV_COLOR.border}`,
                padding: '0 12px',
                fontSize: 14,
                background: '#FAFAFA',
                color: DV_COLOR.textPrimary,
              }}
            />
          </div>

          <div style={{ marginBottom: 20 }}>
            <label style={{ fontSize: 13, fontWeight: 500, color: DV_COLOR.textPrimary, display: 'block', marginBottom: 6 }}>
              使用人
            </label>
            <button
              type="button"
              onClick={() => setPicking(true)}
              data-testid="bh-edit-member-picker"
              style={{
                width: '100%',
                height: 44,
                borderRadius: 10,
                border: `1px solid ${DV_COLOR.border}`,
                background: '#FAFAFA',
                padding: '0 12px',
                fontSize: 14,
                color: DV_COLOR.textPrimary,
                textAlign: 'left',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <span>👤 {memberLabel}</span>
              <span style={{ color: DV_COLOR.gray, fontSize: 16 }}>›</span>
            </button>
          </div>

          <div style={{ display: 'flex', gap: 12 }}>
            <button
              onClick={onClose}
              style={{
                flex: 1, height: 44, borderRadius: 22,
                border: `1px solid ${DV_COLOR.border}`, background: '#fff',
                color: DV_COLOR.textPrimary, fontSize: 15, fontWeight: 500, cursor: 'pointer',
              }}
            >取消</button>
            <button
              onClick={handleSubmit}
              disabled={submitting}
              data-testid="bh-edit-submit"
              style={{
                flex: 1, height: 44, borderRadius: 22, border: 'none',
                background: DV_COLOR.gradient, color: '#fff', fontSize: 15, fontWeight: 600,
                cursor: submitting ? 'not-allowed' : 'pointer', opacity: submitting ? 0.7 : 1,
              }}
            >{submitting ? '保存中…' : '保存'}</button>
          </div>
        </div>
      </Popup>

      <ConsultTargetPicker
        visible={picking}
        currentMemberId={memberId === selfMemberId ? null : memberId}
        onClose={() => setPicking(false)}
        onSelect={(member) => {
          if (member == null) {
            setMemberId(selfMemberId);
            setMemberLabel('本人');
          } else {
            setMemberId(member.id);
            const relation = member.relation_type_name || member.relationship_type || '家人';
            setMemberLabel(`${relation} · ${member.nickname || ''}`);
          }
          setPicking(false);
        }}
      />
    </>
  );
}
