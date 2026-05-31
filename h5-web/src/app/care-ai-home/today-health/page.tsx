'use client';

// [PRD-CARE-MODE-OPTIM-V1 2026-05-31] 关怀模式 → 健康记录 → 今日健康数据页
// - 5 张卡片：血压 / 血糖 / 心率 / 血氧 / 睡眠（顺序固定）
// - 复用健康档案本人 Tab 的「今日健康数据」数据源 /api/health-profile-v3/{profileId}/today-metrics
// - 点击任一卡片 → 跳转 /health-metric/{type}?profileId=xxx（与健康档案完全一致的详情页）
// - 不另起一套数据与逻辑，健康档案改动本页自动跟随

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';

interface Snapshot {
  metric_type?: string;
  value?: any;
  measured_at?: string | null;
  source?: string | null;
  is_abnormal?: boolean;
}

interface TodayMetrics {
  profile_id?: number;
  blood_pressure?: Snapshot;
  blood_glucose?: Snapshot;
  heart_rate?: Snapshot;
  sleep?: Snapshot;
  spo2?: Snapshot;
}

const CARD_DEFS = [
  { type: 'blood_pressure', label: '血压', unit: 'mmHg', icon: '💓', bg: 'linear-gradient(135deg, #EF5350 0%, #E53935 100%)' },
  { type: 'blood_glucose', label: '血糖', unit: 'mmol/L', icon: '🩸', bg: 'linear-gradient(135deg, #EC407A 0%, #D81B60 100%)' },
  { type: 'heart_rate', label: '心率', unit: 'bpm', icon: '❤️', bg: 'linear-gradient(135deg, #FF7043 0%, #F4511E 100%)' },
  { type: 'spo2', label: '血氧', unit: '%', icon: '🫁', bg: 'linear-gradient(135deg, #42A5F5 0%, #1E88E5 100%)' },
  { type: 'sleep', label: '睡眠', unit: 'h', icon: '🌙', bg: 'linear-gradient(135deg, #7E57C2 0%, #5E35B1 100%)' },
];

function readValue(type: string, snap?: Snapshot): string {
  const v = snap?.value;
  if (!v) return '—';
  if (type === 'blood_pressure') {
    if (v.systolic || v.diastolic) return `${v.systolic ?? '-'}/${v.diastolic ?? '-'}`;
    return '—';
  }
  if (type === 'sleep') return v.duration_h ?? v.value ?? '—';
  return v.value ?? '—';
}

export default function CareTodayHealthPage() {
  const router = useRouter();

  const [profileId, setProfileId] = useState<number | null>(null);
  const [metrics, setMetrics] = useState<TodayMetrics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const selfRes: any = await api.get('/api/health-profile/self');
        const pid = selfRes?.data?.profile_id ?? selfRes?.profile_id ?? null;
        setProfileId(pid);
        if (pid) {
          const tmRes: any = await api.get(`/api/health-profile-v3/${pid}/today-metrics`);
          setMetrics(tmRes?.data ?? tmRes ?? null);
        }
      } catch {
        /* 静默：无数据时卡片显示 — */
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const goDetail = (type: string) => {
    router.push(`/health-metric/${type}?profileId=${profileId || ''}`);
  };

  const snapOf = (type: string): Snapshot | undefined => {
    if (!metrics) return undefined;
    return (metrics as any)[type];
  };

  return (
    <div
      style={{ minHeight: '100vh', background: '#F5F7FA', paddingBottom: 32, color: '#212121' }}
      data-testid="care-today-health-page"
    >
      {/* 顶栏 */}
      <div
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 50,
          background: '#FFFFFF',
          borderBottom: '1px solid #EEF1F4',
          height: 52,
          display: 'flex',
          alignItems: 'center',
          padding: '0 12px',
        }}
      >
        <button
          aria-label="返回"
          onClick={() => router.back()}
          style={{ background: 'transparent', border: 'none', fontSize: 22, cursor: 'pointer', width: 40, height: 40 }}
        >
          ‹
        </button>
        <div style={{ flex: 1, textAlign: 'center', fontSize: 18, fontWeight: 700, marginRight: 40 }}>
          今日健康数据
        </div>
      </div>

      <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 14 }} data-testid="care-today-health-cards">
        {CARD_DEFS.map((c) => {
          const snap = snapOf(c.type);
          const value = readValue(c.type, snap);
          const abnormal = !!snap?.is_abnormal;
          return (
            <button
              key={c.type}
              onClick={() => goDetail(c.type)}
              data-testid={`care-today-card-${c.type}`}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 16,
                width: '100%',
                background: '#FFFFFF',
                border: abnormal ? '1px solid #FDE2C8' : '1px solid #EEF1F4',
                borderLeft: abnormal ? '4px solid #F5B544' : '1px solid #EEF1F4',
                borderRadius: 18,
                padding: '18px 16px',
                cursor: 'pointer',
                textAlign: 'left',
                boxShadow: '0 2px 10px rgba(0,0,0,0.04)',
              }}
            >
              <div
                style={{
                  flexShrink: 0,
                  width: 52,
                  height: 52,
                  borderRadius: 14,
                  background: c.bg,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 26,
                }}
                aria-hidden="true"
              >
                {c.icon}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 18, fontWeight: 700, color: '#1F2937' }}>{c.label}</div>
                <div style={{ marginTop: 4 }}>
                  <span style={{ fontSize: 24, fontWeight: 700, color: '#0C4A6E' }}>
                    {loading ? '…' : value}
                  </span>
                  <span style={{ fontSize: 13, color: '#9CA3AF', marginLeft: 4 }}>{c.unit}</span>
                </div>
              </div>
              <span style={{ flexShrink: 0, fontSize: 24, color: '#C4CDD5' }} aria-hidden="true">›</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
