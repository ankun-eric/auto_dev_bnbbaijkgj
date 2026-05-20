'use client';
/**
 * [PRD-MY-DEVICES-V1 2026-05-21] 绑定设备抽屉（底部弹起）。
 *
 * 字段：
 * - 设备名（只读）
 * - SN（必填，含扫码图标）
 * - 别名（可选，最长 20 字）
 * - 使用人（必选，默认本人）
 *
 * 扫码：复用 ScanQRButton（微信内 wx.scanQRCode / H5 调用摄像头）
 */
import { useEffect, useMemo, useState } from 'react';
import { Popup, Toast } from 'antd-mobile';
import api from '@/lib/api';
import type { CatalogItem, BindPayload } from '@/lib/api/devices';
import ConsultTargetPicker, { type FamilyMemberItem } from '@/components/ai-chat/ConsultTargetPicker';
import ScanQRButton from './ScanQRButton';
import { DV_COLOR } from './theme';

interface Props {
  visible: boolean;
  catalog: CatalogItem | null;
  onClose: () => void;
  onSubmit: (payload: BindPayload) => Promise<void>;
}

interface SelfInfo {
  member_id: number | null;
  nickname: string;
}

export default function BindDeviceDrawer({ visible, catalog, onClose, onSubmit }: Props) {
  const [sn, setSn] = useState('');
  const [alias, setAlias] = useState('');
  const [memberId, setMemberId] = useState<number | null>(null);
  const [memberLabel, setMemberLabel] = useState('我自己');
  const [picking, setPicking] = useState(false);
  const [selfMemberId, setSelfMemberId] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!visible) return;
    setSn('');
    setAlias('');
    setMemberLabel('我自己');
    // 拉取家庭成员，默认本人
    (async () => {
      try {
        const res: any = await api.get('/api/family/members');
        const data = res?.data || res;
        const list: FamilyMemberItem[] = Array.isArray(data?.items) ? data.items : Array.isArray(data) ? data : [];
        const self = list.find((m) => m.is_self);
        if (self) {
          setSelfMemberId(self.id);
          setMemberId(self.id);
          setMemberLabel(`本人 · ${self.nickname || '我自己'}`);
        } else {
          setSelfMemberId(null);
          setMemberId(null);
        }
      } catch {
        setSelfMemberId(null);
        setMemberId(null);
      }
    })();
  }, [visible, catalog?.id]);

  const title = useMemo(() => (catalog ? `绑定 ${catalog.device_name}` : '绑定设备'), [catalog]);

  const handleSubmit = async () => {
    if (!catalog) return;
    if (!sn.trim()) {
      Toast.show({ icon: 'fail', content: '请填写 SN 码' });
      return;
    }
    if (alias.length > 20) {
      Toast.show({ icon: 'fail', content: '别名不超过 20 字' });
      return;
    }
    setSubmitting(true);
    try {
      await onSubmit({
        catalog_id: catalog.id,
        sn: sn.trim(),
        alias: alias.trim() || null,
        member_id: memberId,
      });
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
        data-testid="bh-bind-device-drawer"
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
            <button
              onClick={onClose}
              aria-label="关闭"
              style={{ border: 'none', background: 'transparent', fontSize: 22, color: DV_COLOR.gray, cursor: 'pointer' }}
            >×</button>
          </div>

          {/* SN */}
          <div style={{ marginBottom: 16 }}>
            <label style={{ fontSize: 13, fontWeight: 500, color: DV_COLOR.textPrimary, display: 'block', marginBottom: 6 }}>
              SN 码 <span style={{ color: DV_COLOR.danger }}>*</span>
            </label>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input
                value={sn}
                onChange={(e) => setSn(e.target.value)}
                placeholder="请输入或扫码获取 SN"
                data-testid="bh-bind-sn-input"
                style={{
                  flex: 1,
                  height: 40,
                  borderRadius: 10,
                  border: `1px solid ${DV_COLOR.border}`,
                  padding: '0 12px',
                  fontSize: 14,
                  background: '#FAFAFA',
                  color: DV_COLOR.textPrimary,
                }}
              />
              <ScanQRButton onResult={(code) => setSn(code)} />
            </div>
          </div>

          {/* 别名 */}
          <div style={{ marginBottom: 16 }}>
            <label style={{ fontSize: 13, fontWeight: 500, color: DV_COLOR.textPrimary, display: 'block', marginBottom: 6 }}>
              别名（选填）
            </label>
            <input
              value={alias}
              onChange={(e) => setAlias(e.target.value.slice(0, 20))}
              placeholder="如 爸爸的手表（最多 20 字）"
              data-testid="bh-bind-alias-input"
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

          {/* 使用人 */}
          <div style={{ marginBottom: 20 }}>
            <label style={{ fontSize: 13, fontWeight: 500, color: DV_COLOR.textPrimary, display: 'block', marginBottom: 6 }}>
              使用人 <span style={{ color: DV_COLOR.danger }}>*</span>
            </label>
            <button
              type="button"
              onClick={() => setPicking(true)}
              data-testid="bh-bind-member-picker"
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

          <div style={{ display: 'flex', gap: 12, marginTop: 8 }}>
            <button
              onClick={onClose}
              style={{
                flex: 1,
                height: 44,
                borderRadius: 22,
                border: `1px solid ${DV_COLOR.border}`,
                background: '#fff',
                color: DV_COLOR.textPrimary,
                fontSize: 15,
                fontWeight: 500,
                cursor: 'pointer',
              }}
            >取消</button>
            <button
              onClick={handleSubmit}
              disabled={submitting}
              data-testid="bh-bind-submit"
              style={{
                flex: 1,
                height: 44,
                borderRadius: 22,
                border: 'none',
                background: DV_COLOR.gradient,
                color: '#fff',
                fontSize: 15,
                fontWeight: 600,
                cursor: submitting ? 'not-allowed' : 'pointer',
                opacity: submitting ? 0.7 : 1,
              }}
            >{submitting ? '提交中…' : '确认绑定'}</button>
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
            setMemberLabel('本人' + (selfMemberId ? '' : ''));
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
