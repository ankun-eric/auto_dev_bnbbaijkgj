'use client';

/**
 * [PRD-469 M7] 共管与提醒 Tab —— v2 优化：共管列表内嵌 + 权限管理
 */

import { useCallback, useEffect, useState } from 'react';
import { Toast, Mask } from 'antd-mobile';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';

interface ReminderSetting {
  miss_threshold_days: number;
  push_inapp: boolean;
  push_wechat: boolean;
  silent_start?: string | null;
  silent_end?: string | null;
  notify_caregivers: boolean;
}

interface CarePartner {
  id: number;
  managed_member_id: number;
  name: string;
  relation: string;
  avatar: string;
  status: string;
  can_edit: boolean;
  can_view: boolean;
}

interface Props {
  profileId?: number;
  token: any;
  isLinked: boolean;
}

const THRESHOLD_OPTIONS = [1, 2, 3, 5, 7];

export default function CareReminderBlock({ token: T, isLinked, profileId }: Props) {
  const router = useRouter();
  const [setting, setSetting] = useState<ReminderSetting | null>(null);
  const [partners, setPartners] = useState<CarePartner[]>([]);
  const [showPermissionModal, setShowPermissionModal] = useState<CarePartner | null>(null);
  const [permDraft, setPermDraft] = useState<{ can_edit: boolean; can_view: boolean }>({ can_edit: true, can_view: true });

  const fetchSetting = useCallback(async () => {
    try {
      const res: any = await api.get('/api/prd469/reminder-setting');
      const data = res.data || res;
      setSetting(data);
    } catch {
      setSetting(null);
    }
  }, []);

  const fetchPartners = useCallback(async () => {
    if (!profileId) return;
    try {
      const res: any = await api.get(`/api/prd469/care-partners?profile_id=${profileId}`);
      const data = res.data || res;
      setPartners(Array.isArray(data.items) ? data.items : []);
    } catch {
      setPartners([]);
    }
  }, [profileId]);

  useEffect(() => { fetchSetting(); }, [fetchSetting]);
  useEffect(() => { fetchPartners(); }, [fetchPartners]);

  const update = async (patch: Partial<ReminderSetting>) => {
    try {
      await api.put('/api/prd469/reminder-setting', patch);
      setSetting((s) => ({ ...(s || {}), ...patch } as ReminderSetting));
      Toast.show({ content: '已保存', icon: 'success', duration: 800 });
    } catch {
      Toast.show({ content: '保存失败', icon: 'fail' });
    }
  };

  const openPermissionModal = (p: CarePartner) => {
    setPermDraft({ can_edit: p.can_edit, can_view: p.can_view });
    setShowPermissionModal(p);
  };

  const savePermissions = async () => {
    if (!showPermissionModal) return;
    try {
      await api.put(`/api/prd469/care-partners/${showPermissionModal.id}/permissions`, permDraft);
      setPartners((prev) =>
        prev.map((p) =>
          p.id === showPermissionModal.id ? { ...p, ...permDraft } : p
        )
      );
      setShowPermissionModal(null);
      Toast.show({ content: '权限已更新', icon: 'success' });
    } catch {
      Toast.show({ content: '保存失败', icon: 'fail' });
    }
  };

  return (
    <div id="care-reminder" data-testid="prd469-care-reminder" style={{ padding: '12px 16px' }}>
      <h3 style={{ fontSize: 18, fontWeight: 600, color: T.brand700, margin: '8px 0 12px' }}>共管与提醒</h3>

      {/* 共管家人列表 —— Tab内直接展示 [PRD-469 v2 P1] */}
      <div
        data-testid="prd469-care-partners"
        style={{
          background: '#fff', borderRadius: 12, padding: 16,
          boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
          borderLeft: '3px solid #22c55e', marginBottom: 12,
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: T.brand700 }}>👥 共管家人</span>
          <span
            onClick={() => router.push('/family-invite')}
            style={{ fontSize: 13, color: T.brand600, cursor: 'pointer' }}
          >+ 邀请共管 ›</span>
        </div>
        {partners.length === 0 ? (
          <div style={{ textAlign: 'center', color: '#9ca3af', fontSize: 13, padding: '12px 0' }}>
            暂无共管家人，点击「邀请共管」添加
          </div>
        ) : (
          partners.map((p) => (
            <div
              key={p.id}
              data-testid={`prd469-partner-${p.id}`}
              onClick={() => openPermissionModal(p)}
              style={{
                display: 'flex', alignItems: 'center', padding: '10px 0',
                borderBottom: '1px solid #f3f4f6', cursor: 'pointer',
              }}
            >
              <span style={{ fontSize: 24, marginRight: 12 }}>{p.avatar}</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#1f2937' }}>{p.name}</div>
                <div style={{ fontSize: 12, color: '#6b7280' }}>
                  {p.relation} · {p.can_edit ? '可编辑' : '仅查看'}
                </div>
              </div>
              <span style={{ fontSize: 14, color: T.brand500 }}>管理 ›</span>
            </div>
          ))
        )}
        {partners.length > 0 && (
          <div
            onClick={() => router.push('/family-bindlist')}
            style={{ textAlign: 'center', padding: '10px 0 0', fontSize: 13, color: T.brand500, cursor: 'pointer' }}
          >查看全部共管列表 ›</div>
        )}
      </div>

      {/* 漏打卡提醒 */}
      <div
        style={{
          background: '#fff', borderRadius: 12, padding: 16, marginBottom: 12,
          boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
          borderLeft: '3px solid #22c55e',
        }}
      >
        <div style={{ fontSize: 14, fontWeight: 600, color: T.brand700, marginBottom: 12 }}>🔔 漏打卡提醒</div>
        <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 8 }}>漏打卡阈值（连续 N 天未打卡时通知）</div>
        <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
          {THRESHOLD_OPTIONS.map((n) => {
            const active = setting?.miss_threshold_days === n;
            return (
              <button
                key={n}
                onClick={() => update({ miss_threshold_days: n })}
                data-testid={`prd469-threshold-${n}`}
                style={{
                  flex: 1, padding: '8px 0', borderRadius: 8,
                  background: active ? T.brand500 : '#f3f4f6',
                  color: active ? '#fff' : '#374151',
                  border: 'none', fontSize: 13, fontWeight: 600, cursor: 'pointer',
                }}
              >{n} 天</button>
            );
          })}
        </div>

        <ToggleRow label="站内消息" checked={!!setting?.push_inapp}
          onChange={(v) => update({ push_inapp: v })} T={T} />
        <ToggleRow label="微信小程序订阅消息" checked={!!setting?.push_wechat}
          onChange={(v) => update({ push_wechat: v })} T={T} />
        <ToggleRow label="同时通知共管家人" checked={!!setting?.notify_caregivers}
          onChange={(v) => update({ notify_caregivers: v })} T={T} />

        <div style={{ display: 'flex', alignItems: 'center', padding: '12px 0' }}>
          <span style={{ flex: 1, fontSize: 14, color: '#374151' }}>静默时段</span>
          <input
            type="time"
            value={setting?.silent_start || ''}
            onChange={(e) => update({ silent_start: e.target.value })}
            style={{ padding: '4px 8px', border: '1px solid #d1d5db', borderRadius: 6 }}
          />
          <span style={{ margin: '0 6px', color: '#9ca3af' }}>~</span>
          <input
            type="time"
            value={setting?.silent_end || ''}
            onChange={(e) => update({ silent_end: e.target.value })}
            style={{ padding: '4px 8px', border: '1px solid #d1d5db', borderRadius: 6 }}
          />
        </div>
        <div style={{ fontSize: 12, color: '#9ca3af', marginTop: -6 }}>静默时段内不推送提醒（默认建议 22:00–07:00）</div>
      </div>

      {/* 权限管理弹层 [PRD-469 v2 P1] */}
      {showPermissionModal && (
        <Mask visible color="rgba(0,0,0,0.5)">
          <div
            data-testid="prd469-permission-modal"
            style={{
              position: 'fixed', left: 0, right: 0, bottom: 0,
              background: '#fff', borderTopLeftRadius: 16, borderTopRightRadius: 16,
            }}
          >
            <div style={{ padding: '14px 16px', display: 'flex', justifyContent: 'space-between', borderBottom: `1px solid ${T.brand100}` }}>
              <span style={{ fontSize: 17, fontWeight: 700 }}>权限管理</span>
              <span onClick={() => setShowPermissionModal(null)} style={{ fontSize: 22, color: '#9ca3af', cursor: 'pointer' }}>×</span>
            </div>
            <div style={{ padding: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', marginBottom: 16 }}>
                <span style={{ fontSize: 24, marginRight: 12 }}>{showPermissionModal.avatar}</span>
                <div>
                  <div style={{ fontSize: 16, fontWeight: 600 }}>{showPermissionModal.name}</div>
                  <div style={{ fontSize: 13, color: '#6b7280' }}>{showPermissionModal.relation}</div>
                </div>
              </div>
              <ToggleRow label="允许编辑健康信息" checked={permDraft.can_edit}
                onChange={(v) => setPermDraft((d) => ({ ...d, can_edit: v }))} T={T} />
              <ToggleRow label="允许查看健康档案" checked={permDraft.can_view}
                onChange={(v) => setPermDraft((d) => ({ ...d, can_view: v }))} T={T} />
              <div style={{ marginTop: 16, display: 'flex', gap: 12 }}>
                <button onClick={() => setShowPermissionModal(null)}
                  style={{ flex: 1, padding: '12px 0', borderRadius: 24, background: '#fff', border: `1px solid ${T.brand200}`, fontSize: 15, fontWeight: 600 }}>取消</button>
                <button onClick={savePermissions}
                  style={{ flex: 1, padding: '12px 0', borderRadius: 24, background: T.brand500, color: '#fff', border: 'none', fontSize: 15, fontWeight: 600 }}>保存</button>
              </div>
            </div>
          </div>
        </Mask>
      )}
    </div>
  );
}

function ToggleRow({ label, checked, onChange, T }: {
  label: string; checked: boolean; onChange: (v: boolean) => void; T: any;
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid #f3f4f6' }}>
      <span style={{ flex: 1, fontSize: 14, color: '#374151' }}>{label}</span>
      <div
        onClick={() => onChange(!checked)}
        style={{
          width: 40, height: 22, borderRadius: 11,
          background: checked ? T.brand500 : '#d1d5db',
          position: 'relative', cursor: 'pointer', transition: 'background 0.2s',
        }}
      >
        <div
          style={{
            width: 18, height: 18, borderRadius: '50%', background: '#fff',
            position: 'absolute', top: 2, left: checked ? 20 : 2,
            transition: 'left 0.2s',
          }}
        />
      </div>
    </div>
  );
}
