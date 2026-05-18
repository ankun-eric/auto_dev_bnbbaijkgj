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
  // [PRD-MED-PLAN-V1 2026-05-16] 用药 AI 外呼提醒全局开关
  medication_ai_call_enabled?: boolean;
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
  /** [BUG-HEALTH-ARCHIVE-V2 2026-05-16] 当前选中成员的 member_id（用于「邀请共管」跳转参数） */
  memberId?: number;
  /** [BUG-HEALTH-ARCHIVE-V2 2026-05-16] 当前选中是否为本人 —— 本人不展示「邀请共管」按钮 */
  isSelf?: boolean;
}

const THRESHOLD_OPTIONS = [1, 2, 3, 5, 7];

export default function CareReminderBlock({ token: T, isLinked, profileId, memberId, isSelf }: Props) {
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

      {/* [PRD-HEALTH-ARCHIVE-OPTIM-V1 F7] 用药 AI 外呼提醒整体迁移至「家庭守护列表」/被守护人详情，
          此处不再提供独立开关，改为入口跳转。 */}
      <div
        data-testid="bh-aicall-entry-card"
        onClick={() => router.push('/family-guardian-list?reminder=self')}
        style={{
          background: '#fff', borderRadius: 12, padding: 14, marginBottom: 12,
          boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
          borderLeft: '3px solid #0284C7',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer',
        }}
      >
        <div>
          <div style={{ fontSize: 14, fontWeight: 600, color: T.brand700 }}>📞 用药 AI 外呼提醒</div>
          <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>
            到家庭守护列表中按被守护人配置 AI 外呼提醒（包含本人对自己）
          </div>
        </div>
        <span style={{ fontSize: 18, color: '#9ca3af' }}>›</span>
      </div>

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
          {/* [BUG-HEALTH-ARCHIVE-V2 2026-05-16] B4：本人卡片不显示「邀请共管」按钮；B5：跳转携带 member_id */}
          {!isSelf && (
            <span
              data-testid="prd469-invite-co-management"
              onClick={() => {
                if (memberId) {
                  router.push(`/family-invite?member_id=${memberId}`);
                } else {
                  router.push('/family-invite');
                }
              }}
              style={{ fontSize: 13, color: T.brand600, cursor: 'pointer' }}
            >+ 邀请共管 ›</span>
          )}
        </div>
        {partners.length === 0 ? (
          <div style={{ textAlign: 'center', color: '#9ca3af', fontSize: 13, padding: '12px 0' }}>
            {isSelf
              ? '本人无需邀请共管，可在家庭成员卡片中邀请其他成员'
              : '暂无共管家人，点击「邀请共管」添加'}
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

      {/* [PRD-HEALTH-ARCHIVE-OPTIM-V1 F6] 漏打卡提醒区块整块移除（站内/微信/AI 外呼开关全部移除，
          站内/微信通知作为系统默认通道，永远开启，不再向用户暴露配置）。
          仅保留入口，点击跳转家庭守护列表。 */}
      <div
        data-testid="bh-checkin-reminder-entry"
        onClick={() => router.push('/family-guardian-list?reminder=self')}
        style={{
          background: '#fff', borderRadius: 12, padding: 14, marginBottom: 12,
          boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
          borderLeft: '3px solid #22c55e',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer',
        }}
      >
        <span style={{ fontSize: 14, fontWeight: 600, color: T.brand700 }}>🔔 打卡提醒设置</span>
        <span style={{ fontSize: 18, color: '#9ca3af' }}>›</span>
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
