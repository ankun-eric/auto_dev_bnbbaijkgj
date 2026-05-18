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
import { Button, Input, Popup, Toast } from 'antd-mobile';
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

  const onEdit = (_m: MemberItem) => {
    // [PRD-HEALTH-ARCHIVE-OPTIM-V2] NewFamilyMemberModal 当前仅支持新增；编辑暂走相同 Modal 让用户完善
    setShowAdd(true);
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
    </div>
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
        Toast.show('加载提醒设置失败');
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
      Toast.show({ icon: 'success', content: '已保存' });
      onClose();
    } catch (e: any) {
      Toast.show(e?.message || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Popup visible={!!member} onMaskClick={onClose} bodyStyle={{ borderTopLeftRadius: 16, borderTopRightRadius: 16, padding: 16, maxHeight: '85vh', overflowY: 'auto' }}>
      {settings && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <strong style={{ fontSize: 18 }}>提醒设置</strong>
            <span onClick={onClose} style={{ fontSize: 22, color: '#999', cursor: 'pointer', padding: '0 8px' }}>×</span>
          </div>

          {/* 手机号 */}
          <div style={{ background: '#F8F9FC', borderRadius: 8, padding: 12, marginBottom: 12 }}>
            <div style={{ fontSize: 13, color: '#666', marginBottom: 4 }}>对方手机号</div>
            <div style={{ fontSize: 16, fontWeight: 600, color: '#222' }}>{settings.masked_phone || '未填写'}</div>
            <div style={{ marginTop: 6, fontSize: 12, color: '#888' }}>
              💡 这里显示的是对方的注册手机号，若需换号码，请联系对方修改
            </div>
          </div>

          {/* AI 外呼 */}
          <div style={{ background: '#F8F9FC', borderRadius: 8, padding: 12, marginBottom: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <div>
                <div style={{ fontSize: 15, fontWeight: 600 }}>AI 外呼提醒</div>
                <div style={{ fontSize: 12, color: '#888' }}>提醒 TA 打卡</div>
              </div>
              <label style={{ cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={settings.ai_call_enabled}
                  onChange={(e) => setSettings({ ...settings, ai_call_enabled: e.target.checked })}
                />
                <span style={{ marginLeft: 4 }}>{settings.ai_call_enabled ? '开' : '关'}</span>
              </label>
            </div>
            <div style={{ opacity: settings.ai_call_enabled ? 1 : 0.45, pointerEvents: settings.ai_call_enabled ? 'auto' : 'none' }}>
              <div style={{ fontSize: 13, color: '#666', marginBottom: 6 }}>呼叫时机</div>
              {(['on_time', 'delay_5', 'delay_10', 'delay_15'] as const).map((opt) => (
                <label key={opt} style={{ display: 'block', padding: '6px 0', cursor: 'pointer' }}>
                  <input
                    type="radio"
                    name="ai_call_timing"
                    checked={settings.ai_call_timing === opt}
                    onChange={() => setSettings({ ...settings, ai_call_timing: opt })}
                  />
                  <span style={{ marginLeft: 8 }}>
                    {opt === 'on_time' ? '准时拨打' : opt === 'delay_5' ? '延迟 5 分钟' : opt === 'delay_10' ? '延迟 10 分钟' : '延迟 15 分钟'}
                  </span>
                </label>
              ))}
            </div>
          </div>

          {/* 超时通知守护者（本人不显示） */}
          {settings.show_guardian_alert && (
            <div style={{ background: '#F8F9FC', borderRadius: 8, padding: 12, marginBottom: 12 }}>
              <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 4 }}>超时通知守护者</div>
              <div style={{ fontSize: 12, color: '#888', marginBottom: 8 }}>
                📩 若 TA 到点未打卡，将以站内推送方式通知您
              </div>
              <div style={{ fontSize: 13, color: '#666', marginBottom: 6 }}>触发时长</div>
              {([5, 10, 15] as const).map((opt) => (
                <label key={opt} style={{ display: 'block', padding: '6px 0', cursor: 'pointer' }}>
                  <input
                    type="radio"
                    name="guardian_alert_minutes"
                    checked={settings.guardian_alert_minutes === opt}
                    onChange={() => setSettings({ ...settings, guardian_alert_minutes: opt })}
                  />
                  <span style={{ marginLeft: 8 }}>{opt} 分钟{opt === 5 ? '（默认）' : ''}</span>
                </label>
              ))}
            </div>
          )}

          <div
            onClick={() => setHistoryOpen(true)}
            style={{
              background: '#F8F9FC',
              borderRadius: 8,
              padding: 14,
              marginBottom: 16,
              display: 'flex',
              justifyContent: 'space-between',
              cursor: 'pointer',
            }}
          >
            <span>查看提醒历史</span>
            <span style={{ color: '#999' }}>›</span>
          </div>

          <Button block color="primary" loading={saving} onClick={onSave}>
            保存
          </Button>
        </div>
      )}

      {/* 提醒历史抽屉 */}
      <Popup
        visible={historyOpen}
        onMaskClick={() => setHistoryOpen(false)}
        bodyStyle={{ borderTopLeftRadius: 16, borderTopRightRadius: 16, padding: 16, maxHeight: '85vh', overflowY: 'auto' }}
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
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 12 }}>
        <span onClick={onBack} style={{ cursor: 'pointer', fontSize: 18, marginRight: 8 }}>‹</span>
        <strong style={{ fontSize: 18 }}>提醒历史</strong>
      </div>
      {loading && <div style={{ color: '#999', textAlign: 'center', padding: 24 }}>加载中...</div>}
      {!loading && items.length === 0 && (
        <div style={{ color: '#999', textAlign: 'center', padding: 24 }}>暂无提醒记录</div>
      )}
      {items.map((it) => (
        <div key={it.id} style={{ background: '#F8F9FC', borderRadius: 8, padding: 12, marginBottom: 8 }}>
          <div style={{ fontSize: 13, color: '#666' }}>{it.pushed_at}</div>
          <div style={{ fontSize: 14, marginTop: 4 }}>
            类型：{it.type === 'guardian_alert' ? '超时通知' : 'AI 外呼'} · 结果：{it.delivery_status}
          </div>
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
        Toast.show(`验证码已发送（开发环境：${data.debug_code}）`);
        setCode(data.debug_code);
      } else {
        Toast.show('验证码已发送');
      }
      setCountdown(60);
    } catch (e: any) {
      Toast.show(e?.message || '发送失败');
    } finally {
      setSending(false);
    }
  };

  const onConfirm = async () => {
    if (!member) return;
    if (!code || code.length < 4) {
      Toast.show('请输入验证码');
      return;
    }
    setConfirming(true);
    try {
      await api.post(`/api/family-archive-v2/member/${member.id}/unbind/confirm`, { code });
      Toast.show({ icon: 'success', content: `已解除与 ${member.nickname || member.relationship_type} 的守护关系` });
      onUnbound();
    } catch (e: any) {
      Toast.show(e?.message || '验证码无效');
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
