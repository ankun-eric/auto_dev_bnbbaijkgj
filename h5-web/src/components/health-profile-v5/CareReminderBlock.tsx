'use client';

/**
 * [PRD-469 M7] 共管与提醒 Tab —— 简化版（保留入口跳到共管列表 + 漏打卡阈值/静默时段配置）
 */

import { useCallback, useEffect, useState } from 'react';
import { Toast } from 'antd-mobile';
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

interface Props {
  profileId?: number;
  token: any;
  isLinked: boolean;
}

const THRESHOLD_OPTIONS = [1, 2, 3, 5, 7];

export default function CareReminderBlock({ token: T, isLinked }: Props) {
  const router = useRouter();
  const [setting, setSetting] = useState<ReminderSetting | null>(null);

  const fetchSetting = useCallback(async () => {
    try {
      const res: any = await api.get('/api/prd469/reminder-setting');
      const data = res.data || res;
      setSetting(data);
    } catch {
      setSetting(null);
    }
  }, []);

  useEffect(() => { fetchSetting(); }, [fetchSetting]);

  const update = async (patch: Partial<ReminderSetting>) => {
    try {
      await api.put('/api/prd469/reminder-setting', patch);
      setSetting((s) => ({ ...(s || {}), ...patch } as ReminderSetting));
      Toast.show({ content: '已保存', icon: 'success', duration: 800 });
    } catch {
      Toast.show({ content: '保存失败', icon: 'fail' });
    }
  };

  return (
    <div id="care-reminder" data-testid="prd469-care-reminder" style={{ padding: '12px 16px' }}>
      <h3 style={{ fontSize: 18, fontWeight: 600, color: T.brand700, margin: '8px 0 12px' }}>共管与提醒</h3>
      <div
        style={{
          background: '#fff', borderRadius: 12, padding: 16,
          boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
          borderLeft: '3px solid #22c55e',
        }}
      >
        <Row label="👥 共管家人列表" onClick={() => router.push('/family-bindlist')} value="查看 ›" T={T} />
        <Row label="📨 邀请共管人" onClick={() => router.push('/family-invite')} value={isLinked ? '✓ 已关联 ›' : '邀请 ›'} T={T} />
      </div>

      <div
        style={{
          background: '#fff', borderRadius: 12, padding: 16, marginTop: 12,
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
    </div>
  );
}

function Row({ label, value, onClick, T }: { label: string; value: string; onClick: () => void; T: any }) {
  return (
    <div
      onClick={onClick}
      style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '12px 0', borderBottom: `1px solid ${T.brand100}`, cursor: 'pointer',
      }}
    >
      <span style={{ fontSize: 15, color: '#374151' }}>{label}</span>
      <span style={{ fontSize: 13, color: T.brand600 }}>{value}</span>
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
