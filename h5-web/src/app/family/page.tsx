'use client';

/**
 * [PRD-HEALTH-ARCHIVE-OPTIM-V2 2026-05-18] /family 家庭成员列表页（激活版）
 * - 去掉自动跳转回 /health-profile
 * - 每张成员卡显示守护状态 Pill（已守护蓝 / 未守护橙 / 本人无标签）
 * - 卡片底部 2/3 按钮：本人(编辑|提醒设置) / 已守护(编辑|解绑|提醒设置) / 未守护(编辑|邀请|提醒设置)
 * - 右上角 + 按钮调起 NewFamilyMemberModal（编辑模式）
 * - 提醒设置抽屉 / 解绑抽屉 / 提醒历史抽屉
 */

export const dynamic = 'force-dynamic';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button, Input, Popup, Switch } from 'antd-mobile';
import { showToast } from '@/lib/toast-unified';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';
import NewFamilyMemberModal from '@/components/health-profile-v5/NewFamilyMemberModal';

interface MemberItem {
  id: number;
  is_self: boolean;
  nickname: string;
  relationship_type: string;
  member_user_id: number | null;
  avatar_color_index: number;
  relation_badge_char: string;
  guard_status: 'self' | 'guarded' | 'unguarded';
  gender?: string;
  birthday?: string;
}

function calcAge(birthday: string): number | null {
  try {
    const b = new Date(birthday);
    if (isNaN(b.getTime())) return null;
    const now = new Date();
    let age = now.getFullYear() - b.getFullYear();
    const m = now.getMonth() - b.getMonth();
    if (m < 0 || (m === 0 && now.getDate() < b.getDate())) age--;
    return age;
  } catch { return null; }
}

const COLOR_PALETTE = [
  { bg: '#FFE8D6', fg: '#E66A1F' },
  { bg: '#E0EFFF', fg: '#1F6FE6' },
  { bg: '#E8F7EE', fg: '#1FA168' },
  { bg: '#EFE4FF', fg: '#7E3FE6' },
  { bg: '#FFE4EE', fg: '#E63F86' },
];

function GuardPill({ status }: { status: 'self' | 'guarded' | 'unguarded' }) {
  if (status === 'self') return null;
  const isGuarded = status === 'guarded';
  return (
    <span
      style={{
        background: isGuarded ? '#E0EFFF' : '#FFE8D6',
        color: isGuarded ? '#1F6FE6' : '#E66A1F',
        padding: '2px 10px',
        borderRadius: 12,
        fontSize: 12,
        fontWeight: 600,
      }}
    >
      {isGuarded ? '已守护' : '未守护'}
    </span>
  );
}

function MemberBadgeBig({ ch, colorIndex }: { ch: string; colorIndex: number }) {
  const c = COLOR_PALETTE[(colorIndex ?? 0) % COLOR_PALETTE.length];
  return (
    <div
      style={{
        width: 48,
        height: 48,
        borderRadius: '50%',
        background: c.bg,
        color: c.fg,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontWeight: 700,
        fontSize: 20,
        flexShrink: 0,
      }}
    >
      {ch}
    </div>
  );
}

export default function FamilyListPage() {
  const router = useRouter();
  const [members, setMembers] = useState<MemberItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [alertMember, setAlertMember] = useState<MemberItem | null>(null);
  const [unbindMember, setUnbindMember] = useState<MemberItem | null>(null);
  const [editMember, setEditMember] = useState<MemberItem | null>(null);
  const [editDraft, setEditDraft] = useState<{ name: string; gender: string; birthday: string; height: string; weight: string; relationship_type: string }>({ name: '', gender: '', birthday: '', height: '', weight: '', relationship_type: '' });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r: any = await api.get('/api/family-archive-v2/members');
      const data = r.data || r;
      setMembers(Array.isArray(data.items) ? data.items : []);
    } catch (e) {
      setMembers([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const onEdit = (m: MemberItem) => {
    setEditDraft({
      name: m.nickname || '',
      gender: m.gender || '',
      birthday: m.birthday || '',
      height: '',
      weight: '',
      relationship_type: m.relationship_type || '',
    });
    setEditMember(m);
  };

  const onInvite = (m: MemberItem) => {
    router.push(`/family-invite?member_id=${m.id}`);
  };

  return (
    <div style={{ minHeight: '100vh', background: '#F5F7FB', paddingBottom: 80 }}>
      <GreenNavBar
        right={
          <span
            onClick={() => setShowAdd(true)}
            style={{
              color: '#fff',
              fontSize: 22,
              fontWeight: 600,
              padding: '0 6px',
              cursor: 'pointer',
            }}
            data-testid="family-add-btn"
          >
            +
          </span>
        }
      >
        家庭成员
      </GreenNavBar>

      <div style={{ padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {loading && <div style={{ color: '#999', textAlign: 'center', padding: 24 }}>加载中...</div>}
        {!loading && members.length === 0 && (
          <div style={{ color: '#999', textAlign: 'center', padding: 24 }}>暂无家庭成员</div>
        )}
        {members.map((m) => (
          <div
            key={m.id}
            style={{
              background: '#FFFFFF',
              borderRadius: 12,
              padding: 14,
              boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
              border: m.is_self ? '1px solid #BFE0FF' : '1px solid transparent',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <MemberBadgeBig ch={m.relation_badge_char || (m.is_self ? '我' : '人')} colorIndex={m.avatar_color_index} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 16, fontWeight: 600, color: '#222' }}>
                    {m.nickname || (m.is_self ? '本人' : '未命名')}
                  </span>
                  <GuardPill status={m.guard_status} />
                </div>
                <div style={{ marginTop: 4, color: '#666', fontSize: 13 }}>
                  {m.is_self ? '本人' : m.relationship_type || '未设置关系'}
                </div>
                <div style={{ marginTop: 2, color: '#999', fontSize: 12 }}>
                  {(() => {
                    const g = m.gender || '未填写';
                    const age = m.birthday ? calcAge(m.birthday) : null;
                    const ageStr = age != null ? `${age}岁` : '未填写';
                    return `${g} · ${ageStr}`;
                  })()}
                </div>
              </div>
            </div>
            <div style={{ height: 1, background: '#F0F2F5', margin: '12px 0 8px' }} />
            <div style={{ display: 'flex', justifyContent: 'space-around', color: '#1F6FE6', fontSize: 14 }}>
              <span onClick={() => onEdit(m)} style={{ cursor: 'pointer', padding: '4px 8px' }}>编辑</span>
              {!m.is_self && m.guard_status === 'guarded' && (
                <>
                  <span style={{ color: '#E0E0E0' }}>|</span>
                  <span onClick={() => setUnbindMember(m)} style={{ cursor: 'pointer', padding: '4px 8px', color: '#E66A1F' }}>解绑</span>
                </>
              )}
              {!m.is_self && m.guard_status === 'unguarded' && (
                <>
                  <span style={{ color: '#E0E0E0' }}>|</span>
                  <span onClick={() => onInvite(m)} style={{ cursor: 'pointer', padding: '4px 8px' }}>邀请</span>
                </>
              )}
              <span style={{ color: '#E0E0E0' }}>|</span>
              <span onClick={() => setAlertMember(m)} style={{ cursor: 'pointer', padding: '4px 8px' }}>提醒设置</span>
            </div>
          </div>
        ))}
      </div>

      {showAdd && (
        <NewFamilyMemberModal
          onClose={() => setShowAdd(false)}
          onSuccess={() => {
            setShowAdd(false);
            load();
          }}
        />
      )}

      <AlertSettingsDrawer
        member={alertMember}
        onClose={() => setAlertMember(null)}
      />

      <UnbindDrawer
        member={unbindMember}
        onClose={() => setUnbindMember(null)}
        onUnbound={() => {
          setUnbindMember(null);
          load();
        }}
      />

      <EditMemberDrawer
        member={editMember}
        draft={editDraft}
        onDraftChange={setEditDraft}
        onClose={() => setEditMember(null)}
        onSaved={() => {
          setEditMember(null);
          load();
        }}
      />
    </div>
  );
}

// ───────────────── 编辑成员抽屉 ─────────────────

interface EditDraft {
  name: string;
  gender: string;
  birthday: string;
  height: string;
  weight: string;
  relationship_type: string;
}

const GENDER_OPTIONS = ['男', '女', '其他'];

function EditMemberDrawer({
  member,
  draft,
  onDraftChange,
  onClose,
  onSaved,
}: {
  member: MemberItem | null;
  draft: EditDraft;
  onDraftChange: (d: EditDraft) => void;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [saving, setSaving] = useState(false);

  const onSave = async () => {
    if (!member) return;
    setSaving(true);
    try {
      const body: Record<string, any> = {
        name: draft.name || undefined,
        gender: draft.gender || undefined,
        birthday: draft.birthday || undefined,
        height: draft.height ? Number(draft.height) : undefined,
        weight: draft.weight ? Number(draft.weight) : undefined,
      };
      if (!member.is_self) {
        body.relationship_type = draft.relationship_type || undefined;
      }
      await api.put(`/api/health/profile/member/${member.id}`, body);
      showToast('已保存');
      onSaved();
    } catch (e: any) {
      showToast(e?.message || '保存失败', 'fail');
    } finally {
      setSaving(false);
    }
  };

  const fieldLabel = (text: string) => (
    <div style={{ fontSize: 13, color: '#666', marginBottom: 6 }}>{text}</div>
  );

  return (
    <Popup
      visible={!!member}
      onMaskClick={onClose}
      bodyStyle={{ borderTopLeftRadius: 16, borderTopRightRadius: 16, padding: 16, maxHeight: '85vh', overflowY: 'auto' }}
    >
      {member && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <strong style={{ fontSize: 18 }}>编辑个人信息</strong>
            <span onClick={onClose} style={{ fontSize: 22, color: '#999', cursor: 'pointer', padding: '0 8px' }}>×</span>
          </div>

          <div style={{ marginBottom: 14 }}>
            {fieldLabel('姓名')}
            <Input
              placeholder="请输入姓名"
              value={draft.name}
              onChange={(v) => onDraftChange({ ...draft, name: v })}
              style={{ background: '#F8F9FC', borderRadius: 8, padding: '0 12px', height: 40, '--font-size': '15px' } as any}
            />
          </div>

          <div style={{ marginBottom: 14 }}>
            {fieldLabel('性别')}
            <div style={{ display: 'flex', gap: 10 }}>
              {GENDER_OPTIONS.map((g) => (
                <div
                  key={g}
                  onClick={() => onDraftChange({ ...draft, gender: g })}
                  style={{
                    padding: '6px 20px',
                    borderRadius: 20,
                    fontSize: 14,
                    cursor: 'pointer',
                    fontWeight: 500,
                    background: draft.gender === g ? '#1F6FE6' : '#F1F5F9',
                    color: draft.gender === g ? '#fff' : '#64748B',
                    transition: 'all 0.2s',
                  }}
                >
                  {g}
                </div>
              ))}
            </div>
          </div>

          <div style={{ marginBottom: 14 }}>
            {fieldLabel('生日')}
            <input
              type="date"
              value={draft.birthday}
              onChange={(e) => onDraftChange({ ...draft, birthday: e.target.value })}
              style={{
                width: '100%',
                background: '#F8F9FC',
                borderRadius: 8,
                padding: '0 12px',
                height: 40,
                border: 'none',
                fontSize: 15,
                color: '#333',
                outline: 'none',
                boxSizing: 'border-box',
              }}
            />
          </div>

          <div style={{ display: 'flex', gap: 12, marginBottom: 14 }}>
            <div style={{ flex: 1 }}>
              {fieldLabel('身高 (cm)')}
              <Input
                type="number"
                placeholder="如 170"
                value={draft.height}
                onChange={(v) => onDraftChange({ ...draft, height: v })}
                style={{ background: '#F8F9FC', borderRadius: 8, padding: '0 12px', height: 40, '--font-size': '15px' } as any}
              />
            </div>
            <div style={{ flex: 1 }}>
              {fieldLabel('体重 (kg)')}
              <Input
                type="number"
                placeholder="如 65"
                value={draft.weight}
                onChange={(v) => onDraftChange({ ...draft, weight: v })}
                style={{ background: '#F8F9FC', borderRadius: 8, padding: '0 12px', height: 40, '--font-size': '15px' } as any}
              />
            </div>
          </div>

          {!member.is_self && (
            <div style={{ marginBottom: 14 }}>
              {fieldLabel('关系')}
              <Input
                placeholder="如 父亲、母亲"
                value={draft.relationship_type}
                onChange={(v) => onDraftChange({ ...draft, relationship_type: v })}
                style={{ background: '#F8F9FC', borderRadius: 8, padding: '0 12px', height: 40, '--font-size': '15px' } as any}
              />
            </div>
          )}

          <Button block color="primary" loading={saving} onClick={onSave} style={{ marginTop: 8 }}>
            保存
          </Button>
        </div>
      )}
    </Popup>
  );
}

// ───────────────── 提醒设置抽屉 ─────────────────

interface AlertSettings {
  member_id: number;
  is_self: boolean;
  guard_status: string;
  masked_phone: string | null;
  ai_call_enabled: boolean;
  ai_call_timing: string;
  guardian_alert_minutes: number;
  show_guardian_alert: boolean;
}

function CapsuleTag({
  label,
  selected,
  onTap,
}: {
  label: string;
  selected: boolean;
  onTap: () => void;
}) {
  const [pressed, setPressed] = useState(false);
  return (
    <div
      onClick={() => {
        setPressed(true);
        onTap();
        setTimeout(() => setPressed(false), 200);
      }}
      style={{
        padding: '6px 14px',
        borderRadius: 20,
        fontSize: 13,
        fontWeight: 500,
        cursor: 'pointer',
        background: selected ? '#0EA5E9' : '#F1F5F9',
        color: selected ? '#fff' : '#64748B',
        transform: pressed ? 'scale(0.95)' : 'scale(1)',
        transition: 'all 0.2s',
        userSelect: 'none',
      }}
    >
      {label}
    </div>
  );
}

function AlertSettingsDrawer({ member, onClose }: { member: MemberItem | null; onClose: () => void }) {
  const [settings, setSettings] = useState<AlertSettings | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!member) {
      setSettings(null);
      return;
    }
    (async () => {
      try {
        const r: any = await api.get(`/api/family-archive-v2/member/${member.id}/alert-settings`);
        setSettings(r.data || r);
      } catch (e) {
        showToast('加载提醒设置失败', 'fail');
      }
    })();
  }, [member]);

  const onSave = async () => {
    if (!settings || !member) return;
    setSaving(true);
    try {
      await api.put(`/api/family-archive-v2/member/${member.id}/alert-settings`, {
        ai_call_enabled: settings.ai_call_enabled,
        ai_call_timing: settings.ai_call_timing,
        guardian_alert_minutes: settings.guardian_alert_minutes,
      });
      showToast('已保存');
      onClose();
    } catch (e: any) {
      showToast(e?.message || '保存失败', 'fail');
    } finally {
      setSaving(false);
    }
  };

  const TIMING_OPTIONS: { value: string; label: string }[] = [
    { value: 'on_time', label: '准时拨打' },
    { value: 'delay_5', label: '延迟5分钟' },
    { value: 'delay_10', label: '延迟10分钟' },
    { value: 'delay_15', label: '延迟15分钟' },
  ];

  const GUARDIAN_MINUTES: { value: number; label: string }[] = [
    { value: 5, label: '5分钟' },
    { value: 10, label: '10分钟' },
    { value: 15, label: '15分钟' },
  ];

  return (
    <Popup
      visible={!!member}
      onMaskClick={onClose}
      bodyStyle={{
        borderTopLeftRadius: 16,
        borderTopRightRadius: 16,
        maxHeight: '90vh',
        overflowY: 'auto',
        background: '#fff',
      }}
    >
      {settings && (
        <div style={{ padding: '16px 16px 24px' }}>
          {/* Header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <strong style={{ fontSize: 18, color: '#1E293B' }}>提醒设置</strong>
            <span onClick={onClose} style={{ fontSize: 22, color: '#94A3B8', cursor: 'pointer', padding: '0 8px' }}>×</span>
          </div>

          {/* 顶部状态卡片 */}
          <div
            style={{
              background: 'linear-gradient(135deg, #0EA5E9, #38BDF8)',
              borderRadius: 14,
              padding: '18px 16px',
              marginBottom: 16,
              color: '#fff',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: 28 }}>📱</span>
              <div>
                <div style={{ fontSize: 16, fontWeight: 700 }}>
                  {settings.ai_call_enabled ? 'AI外呼已开启' : 'AI外呼未开启'}
                </div>
                <div style={{ fontSize: 13, opacity: 0.85, marginTop: 2 }}>
                  {settings.masked_phone ? `通知号码 ${settings.masked_phone}` : '暂未绑定号码'}
                </div>
              </div>
            </div>
          </div>

          {/* AI 外呼提醒 */}
          <div
            style={{
              background: '#fff',
              borderRadius: 14,
              padding: 16,
              marginBottom: 12,
              boxShadow: '0 1px 6px rgba(0,0,0,0.06)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: 10,
                    background: '#E0F2FE',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 18,
                    flexShrink: 0,
                  }}
                >
                  📞
                </span>
                <div>
                  <div style={{ fontSize: 15, fontWeight: 600, color: '#1E293B' }}>AI 外呼提醒</div>
                  <div style={{ fontSize: 12, color: '#94A3B8', marginTop: 1 }}>到点提醒 TA 打卡</div>
                </div>
              </div>
              <Switch
                checked={settings.ai_call_enabled}
                onChange={(checked) => setSettings({ ...settings, ai_call_enabled: checked })}
                style={{ '--checked-color': '#0EA5E9' } as any}
              />
            </div>
            <div
              style={{
                opacity: settings.ai_call_enabled ? 1 : 0.4,
                pointerEvents: settings.ai_call_enabled ? 'auto' : 'none',
                transition: 'opacity 0.25s',
              }}
            >
              <div style={{ fontSize: 13, color: '#64748B', marginBottom: 8 }}>呼叫时机</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {TIMING_OPTIONS.map((opt) => (
                  <CapsuleTag
                    key={opt.value}
                    label={opt.label}
                    selected={settings.ai_call_timing === opt.value}
                    onTap={() => setSettings({ ...settings, ai_call_timing: opt.value })}
                  />
                ))}
              </div>
            </div>
          </div>

          {/* 超时通知守护者 */}
          {settings.show_guardian_alert && (
            <div
              style={{
                background: '#fff',
                borderRadius: 14,
                padding: 16,
                marginBottom: 12,
                boxShadow: '0 1px 6px rgba(0,0,0,0.06)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
                <span
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: 10,
                    background: '#FFF7ED',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 18,
                    flexShrink: 0,
                  }}
                >
                  🔔
                </span>
                <div>
                  <div style={{ fontSize: 15, fontWeight: 600, color: '#1E293B' }}>超时通知守护者</div>
                  <div style={{ fontSize: 12, color: '#94A3B8', marginTop: 1 }}>若 TA 到点未打卡，将推送通知您</div>
                </div>
              </div>
              <div style={{ fontSize: 13, color: '#64748B', marginBottom: 8 }}>触发时长</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {GUARDIAN_MINUTES.map((opt) => (
                  <CapsuleTag
                    key={opt.value}
                    label={opt.label}
                    selected={settings.guardian_alert_minutes === opt.value}
                    onTap={() => setSettings({ ...settings, guardian_alert_minutes: opt.value })}
                  />
                ))}
              </div>
            </div>
          )}

          {/* 查看提醒历史 */}
          <div
            onClick={() => setHistoryOpen(true)}
            style={{
              background: '#fff',
              borderRadius: 14,
              padding: 16,
              marginBottom: 20,
              boxShadow: '0 1px 6px rgba(0,0,0,0.06)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              cursor: 'pointer',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: 10,
                  background: '#F3E8FF',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 18,
                  flexShrink: 0,
                }}
              >
                📋
              </span>
              <span style={{ fontSize: 15, fontWeight: 600, color: '#1E293B' }}>查看提醒历史</span>
            </div>
            <span style={{ color: '#94A3B8', fontSize: 18, fontWeight: 600 }}>›</span>
          </div>

          {/* 保存按钮 */}
          <div
            onClick={saving ? undefined : onSave}
            style={{
              background: saving ? '#94A3B8' : 'linear-gradient(135deg, #0EA5E9, #38BDF8)',
              borderRadius: 24,
              padding: '14px 0',
              textAlign: 'center',
              color: '#fff',
              fontSize: 16,
              fontWeight: 600,
              cursor: saving ? 'not-allowed' : 'pointer',
              userSelect: 'none',
            }}
          >
            {saving ? '保存中...' : '保存设置'}
          </div>
        </div>
      )}

      {/* 提醒历史抽屉 */}
      <Popup
        visible={historyOpen}
        onMaskClick={() => setHistoryOpen(false)}
        bodyStyle={{ borderTopLeftRadius: 16, borderTopRightRadius: 16, padding: 16, maxHeight: '85vh', overflowY: 'auto', background: '#fff' }}
      >
        {member && historyOpen && <AlertHistoryList memberId={member.id} onBack={() => setHistoryOpen(false)} />}
      </Popup>
    </Popup>
  );
}

function AlertHistoryList({ memberId, onBack }: { memberId: number; onBack: () => void }) {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    (async () => {
      try {
        const r: any = await api.get(`/api/family-archive-v2/member/${memberId}/alert-history`);
        const data = r.data || r;
        setItems(Array.isArray(data.items) ? data.items : []);
      } catch {
        setItems([]);
      } finally {
        setLoading(false);
      }
    })();
  }, [memberId]);

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 16 }}>
        <span onClick={onBack} style={{ cursor: 'pointer', fontSize: 20, marginRight: 8, color: '#0EA5E9', fontWeight: 600 }}>‹</span>
        <strong style={{ fontSize: 18, color: '#1E293B' }}>提醒历史</strong>
      </div>
      {loading && <div style={{ color: '#94A3B8', textAlign: 'center', padding: 24 }}>加载中...</div>}
      {!loading && items.length === 0 && (
        <div style={{ color: '#94A3B8', textAlign: 'center', padding: 24 }}>暂无提醒记录</div>
      )}
      {items.map((it) => (
        <div
          key={it.id}
          style={{
            background: '#fff',
            borderRadius: 12,
            padding: 14,
            marginBottom: 10,
            boxShadow: '0 1px 4px rgba(0,0,0,0.05)',
            display: 'flex',
            alignItems: 'center',
            gap: 12,
          }}
        >
          <span
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              background: it.type === 'guardian_alert' ? '#FFF7ED' : '#E0F2FE',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 16,
              flexShrink: 0,
            }}
          >
            {it.type === 'guardian_alert' ? '🔔' : '📞'}
          </span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 14, fontWeight: 500, color: '#1E293B' }}>
              {it.type === 'guardian_alert' ? '超时通知' : 'AI 外呼'}
            </div>
            <div style={{ fontSize: 12, color: '#94A3B8', marginTop: 2 }}>{it.pushed_at}</div>
          </div>
          <span style={{ fontSize: 12, color: '#64748B', flexShrink: 0 }}>{it.delivery_status}</span>
        </div>
      ))}
    </div>
  );
}

// ───────────────── 解绑抽屉 ─────────────────

function UnbindDrawer({ member, onClose, onUnbound }: { member: MemberItem | null; onClose: () => void; onUnbound: () => void }) {
  const [code, setCode] = useState('');
  const [sending, setSending] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const [masked, setMasked] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    if (!member) {
      setCode('');
      setCountdown(0);
      setMasked(null);
      return;
    }
  }, [member]);

  useEffect(() => {
    if (countdown <= 0) return;
    const t = setTimeout(() => setCountdown((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [countdown]);

  const onSendCode = async () => {
    if (!member) return;
    setSending(true);
    try {
      const r: any = await api.post(`/api/family-archive-v2/member/${member.id}/unbind/send-code`, {});
      const data = r.data || r;
      setMasked(data.masked_phone);
      if (data.debug_code) {
        // 开发环境兜底
        showToast(`验证码已发送（开发环境：${data.debug_code}）`);
        setCode(data.debug_code);
      } else {
        showToast('验证码已发送');
      }
      setCountdown(60);
    } catch (e: any) {
      showToast(e?.message || '发送失败', 'fail');
    } finally {
      setSending(false);
    }
  };

  const onConfirm = async () => {
    if (!member) return;
    if (!code || code.length < 4) {
      showToast('请输入验证码', 'warning');
      return;
    }
    setConfirming(true);
    try {
      await api.post(`/api/family-archive-v2/member/${member.id}/unbind/confirm`, { code });
      showToast(`已解除与 ${member.nickname || member.relationship_type} 的守护关系`);
      onUnbound();
    } catch (e: any) {
      showToast(e?.message || '验证码无效', 'fail');
    } finally {
      setConfirming(false);
    }
  };

  return (
    <Popup visible={!!member} onMaskClick={onClose} bodyStyle={{ borderTopLeftRadius: 16, borderTopRightRadius: 16, padding: 16, maxHeight: '70vh', overflowY: 'auto' }}>
      {member && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <strong style={{ fontSize: 18 }}>解除守护关系</strong>
            <span onClick={onClose} style={{ fontSize: 22, color: '#999', cursor: 'pointer', padding: '0 8px' }}>×</span>
          </div>

          <div
            style={{
              background: '#FFF4ED',
              border: '1px solid #FFD8B8',
              color: '#9A4500',
              borderRadius: 8,
              padding: 12,
              fontSize: 13,
              lineHeight: '20px',
              marginBottom: 16,
            }}
          >
            ⚠️ 解绑后将停止所有健康守护与提醒，且 TA 的健康数据您将无法继续查看。此操作不可恢复，请谨慎操作。
          </div>

          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 13, color: '#666', marginBottom: 6 }}>
              短信验证码{masked ? `已发送至：${masked}（守护者）` : '将发送至您的手机'}
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <Input
                placeholder="输入验证码"
                value={code}
                onChange={(v) => setCode(v.replace(/\D/g, '').slice(0, 6))}
                style={{ flex: 1, background: '#F8F9FC', borderRadius: 8, padding: '0 12px', height: 40 }}
              />
              <Button
                size="small"
                disabled={countdown > 0 || sending}
                onClick={onSendCode}
                style={{ width: 140 }}
              >
                {countdown > 0 ? `${countdown}s 后重发` : sending ? '发送中...' : '获取验证码'}
              </Button>
            </div>
          </div>

          <Button block color="danger" loading={confirming} onClick={onConfirm}>
            确认解绑
          </Button>
        </div>
      )}
    </Popup>
  );
}
