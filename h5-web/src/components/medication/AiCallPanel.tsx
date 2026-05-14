'use client';
/**
 * [PRD-HEALTH-OPT-V1 2026-05-14 R5] 用药计划编辑页 — AI 外呼提醒开关面板。
 *
 * 入口形态见 PRD §5.2：
 *  - 开关 + 「💎 健康会员」标记
 *  - 号码区只读脱敏
 *  - 勿扰时段可编辑
 *  - 底部展示当月剩余次数 / 总额度
 *  - 额度用尽时弹「升级会员」Dialog（按 R4 规范）
 */
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import { BH_TOKENS } from '@/lib/health-tokens';
import { ToastUnified } from '@/lib/toast-unified';
import { showUnifiedDialog } from '@/lib/dialog-unified';

interface Props {
  planId?: number | null;
  // 当尚未创建计划（add 模式）时，仅本地保存，等保存计划成功后再提交配置
  draftMode?: boolean;
  onDraftChange?: (draft: AiCallDraft) => void;
  initialDraft?: AiCallDraft;
}

export interface AiCallDraft {
  ai_call_enabled: boolean;
  ai_call_dnd_start: string;
  ai_call_dnd_end: string;
}

interface QuotaState {
  level_code: string;
  level_display_name: string;
  monthly_quota: number;
  used: number;
  remaining: number;
}

interface RemoteState {
  ai_call_enabled: boolean;
  ai_call_dnd_start: string;
  ai_call_dnd_end: string;
  target_phone_masked?: string | null;
  quota_used: number;
  quota_total: number;
  quota_remaining: number;
  membership_level_code: string;
  membership_display_name: string;
}

export default function AiCallPanel({ planId, draftMode, onDraftChange, initialDraft }: Props) {
  const router = useRouter();
  const [remote, setRemote] = useState<RemoteState | null>(null);
  const [quota, setQuota] = useState<QuotaState | null>(null);
  const [draft, setDraft] = useState<AiCallDraft>(
    initialDraft || { ai_call_enabled: false, ai_call_dnd_start: '22:00', ai_call_dnd_end: '07:00' },
  );
  const [editingDnd, setEditingDnd] = useState(false);
  const [phoneMasked, setPhoneMasked] = useState<string>('');

  const refresh = async () => {
    try {
      const q: any = await api.get('/api/ai-call/quota');
      const qd = q?.data || q;
      setQuota(qd as QuotaState);
    } catch {
      setQuota(null);
    }
    if (planId) {
      try {
        const r: any = await api.get(`/api/medication-reminder/plans/${planId}/ai-call`);
        const rd = (r?.data || r) as RemoteState;
        setRemote(rd);
        setDraft({
          ai_call_enabled: !!rd.ai_call_enabled,
          ai_call_dnd_start: rd.ai_call_dnd_start || '22:00',
          ai_call_dnd_end: rd.ai_call_dnd_end || '07:00',
        });
        setPhoneMasked(rd.target_phone_masked || '');
      } catch {
        setRemote(null);
      }
    } else {
      try {
        // 在新建态尝试取当前用户脱敏手机号
        const u: any = await api.get('/api/account/profile').catch(() => null);
        const ud: any = u?.data || u || {};
        const phone: string = ud?.phone || '';
        if (phone && phone.length >= 7) {
          setPhoneMasked(`${phone.slice(0, 3)}****${phone.slice(-4)}`);
        }
      } catch {}
    }
  };

  useEffect(() => { refresh(); }, [planId]);

  useEffect(() => {
    onDraftChange?.(draft);
  }, [draft, onDraftChange]);

  const persistRemote = async (next: AiCallDraft) => {
    if (!planId) return;
    try {
      await api.put(`/api/medication-reminder/plans/${planId}/ai-call`, next);
      await refresh();
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || '保存失败';
      if (typeof msg === 'string' && msg.includes('额度已用完')) {
        showQuotaExhaustedDialog();
      } else if (typeof msg === 'string' && msg.includes('未注册')) {
        ToastUnified.fail('该家属未注册 App，无法使用 AI 外呼');
        setDraft({ ...next, ai_call_enabled: false });
      } else {
        ToastUnified.fail(typeof msg === 'string' ? msg : '保存失败');
        setDraft({ ...next, ai_call_enabled: false });
      }
    }
  };

  const showQuotaExhaustedDialog = () => {
    const levelName = quota?.level_display_name || '普通会员';
    const total = quota?.monthly_quota ?? 30;
    showUnifiedDialog({
      title: '本月 AI 外呼额度已用完',
      content: `当前为 ${levelName}（${total} 次/月），本月已全部使用。升级 健康会员 可享 100 次/月，到点 AI 自动外呼，再也不会忘记吃药。`,
      buttons: [
        { text: '暂不升级' },
        {
          text: '立即升级',
          primary: true,
          onClick: () => router.push('/membership'),
        },
      ],
    });
    // 回退开关
    setDraft({ ...draft, ai_call_enabled: false });
  };

  const handleToggle = (checked: boolean) => {
    if (checked) {
      const remaining = quota?.remaining ?? 0;
      if (remaining <= 0) {
        showQuotaExhaustedDialog();
        return;
      }
    }
    const next = { ...draft, ai_call_enabled: checked };
    setDraft(next);
    if (!draftMode && planId) {
      persistRemote(next);
    }
  };

  const updateDnd = (key: 'ai_call_dnd_start' | 'ai_call_dnd_end', value: string) => {
    const next = { ...draft, [key]: value };
    setDraft(next);
    if (!draftMode && planId && draft.ai_call_enabled) {
      persistRemote(next);
    }
  };

  const remaining = quota ? Math.max(0, quota.remaining) : 0;
  const total = quota?.monthly_quota ?? 30;
  const isHealthMember = quota?.level_code === 'health';

  return (
    <div
      data-testid="bh-ai-call-panel"
      style={{
        background: BH_TOKENS.cardSurface,
        borderRadius: BH_TOKENS.cardRadius,
        boxShadow: BH_TOKENS.cardShadow,
        padding: 16,
        margin: '12px 0',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 15, fontWeight: 600, color: BH_TOKENS.textPrimary }}>AI 外呼提醒</span>
          <span
            style={{
              fontSize: 11,
              padding: '2px 8px',
              borderRadius: 10,
              background: isHealthMember ? '#FEF3C7' : '#E0F2FE',
              color: isHealthMember ? '#B45309' : '#0369A1',
              fontWeight: 600,
            }}
          >💎 健康会员</span>
        </div>
        <label style={{ position: 'relative', display: 'inline-block', width: 44, height: 24 }}>
          <input
            type="checkbox"
            checked={draft.ai_call_enabled}
            onChange={(e) => handleToggle(e.target.checked)}
            data-testid="bh-ai-call-switch"
            style={{ opacity: 0, width: 0, height: 0 }}
          />
          <span
            style={{
              position: 'absolute', cursor: 'pointer', inset: 0,
              background: draft.ai_call_enabled ? BH_TOKENS.accentBlue : '#cbd5e1',
              borderRadius: 24, transition: '0.2s',
            }}
          >
            <span
              style={{
                position: 'absolute', height: 20, width: 20, left: draft.ai_call_enabled ? 22 : 2,
                bottom: 2, background: 'white', borderRadius: '50%', transition: '0.2s',
              }}
            />
          </span>
        </label>
      </div>

      {draft.ai_call_enabled && (
        <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div
            data-testid="bh-ai-call-phone"
            style={{
              padding: '10px 12px',
              background: '#F8FAFC',
              borderRadius: 10,
              fontSize: 13,
              color: BH_TOKENS.textSecondary,
              display: 'flex', justifyContent: 'space-between',
            }}
          >
            <span>外呼号码（不可改）</span>
            <span style={{ color: BH_TOKENS.textPrimary, fontWeight: 600 }}>{phoneMasked || '—'}</span>
          </div>

          <div
            style={{
              padding: '10px 12px', background: '#F8FAFC', borderRadius: 10,
              fontSize: 13, color: BH_TOKENS.textSecondary,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>勿扰时段</span>
              <button
                data-testid="bh-ai-call-dnd-edit"
                onClick={() => setEditingDnd((v) => !v)}
                style={{
                  background: 'none', border: 'none', cursor: 'pointer',
                  color: BH_TOKENS.accentBlue, fontSize: 13,
                }}
              >{editingDnd ? '完成' : '编辑'}</button>
            </div>
            {editingDnd ? (
              <div style={{ marginTop: 8, display: 'flex', gap: 8, alignItems: 'center' }}>
                <input
                  type="time"
                  value={draft.ai_call_dnd_start}
                  data-testid="bh-ai-call-dnd-start"
                  onChange={(e) => updateDnd('ai_call_dnd_start', e.target.value)}
                  style={{ flex: 1, padding: '6px 8px', borderRadius: 6, border: '1px solid #cbd5e1' }}
                />
                <span>—</span>
                <input
                  type="time"
                  value={draft.ai_call_dnd_end}
                  data-testid="bh-ai-call-dnd-end"
                  onChange={(e) => updateDnd('ai_call_dnd_end', e.target.value)}
                  style={{ flex: 1, padding: '6px 8px', borderRadius: 6, border: '1px solid #cbd5e1' }}
                />
              </div>
            ) : (
              <div style={{ marginTop: 4, color: BH_TOKENS.textPrimary, fontWeight: 600 }}>
                {draft.ai_call_dnd_start} - {draft.ai_call_dnd_end}（默认 22:00-07:00 不外呼）
              </div>
            )}
          </div>

          <div
            data-testid="bh-ai-call-quota"
            style={{
              padding: '10px 12px',
              background: 'rgba(74,158,224,0.08)', borderRadius: 10,
              fontSize: 13, color: BH_TOKENS.textSecondary,
              display: 'flex', justifyContent: 'space-between',
            }}
          >
            <span>本月剩余</span>
            <span>
              <span style={{ color: BH_TOKENS.accentBlue, fontWeight: 700 }}>{remaining}</span>
              <span> / {total} 次</span>
            </span>
          </div>
        </div>
      )}

      {!draft.ai_call_enabled && remaining <= 0 && (
        <div style={{ marginTop: 8, fontSize: 12, color: BH_TOKENS.statusDanger }}>
          额度不足，
          <span
            onClick={() => router.push('/membership')}
            style={{ color: BH_TOKENS.accentBlue, textDecoration: 'underline', cursor: 'pointer' }}
          >升级会员</span>
        </div>
      )}
    </div>
  );
}
