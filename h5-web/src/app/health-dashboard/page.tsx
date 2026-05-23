'use client';

import { Suspense, useCallback, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import api from '@/lib/api';

// ─── Types (aligned with backend HealthDashboardResponse / HealthTrendsResponse) ──

interface VitalItem {
  systolic?: number | null;
  diastolic?: number | null;
  fasting?: number | null;
  postprandial?: number | null;
  value?: number | null;
  is_abnormal: boolean;
  recorded_at?: string | null;
}

interface TodayEvent {
  time: string;
  type: string;
  title: string;
  is_abnormal?: boolean;
  completed?: boolean;
}

interface MedicationPeriodItem {
  name: string;
  completed: boolean;
}

interface MedicationPeriod {
  period: string;
  label: string;
  items: MedicationPeriodItem[];
}

interface MedicationSummary {
  completion_rate: number;
  periods: MedicationPeriod[];
}

interface CheckupSummary {
  latest_date: string | null;
  abnormal_items: string[];
  next_checkup_days: number | null;
  next_followup_days: number | null;
}

interface DashboardSummary {
  member_id: number;
  member_name: string;
  health_score: number;
  health_score_details: Record<string, number>;
  latest_vitals: {
    blood_pressure: VitalItem | null;
    blood_sugar: VitalItem | null;
    heart_rate: VitalItem | null;
  };
  today_events: TodayEvent[];
  medication_summary: MedicationSummary;
  checkup_summary: CheckupSummary;
}

interface TrendPoint {
  date: string;
  systolic?: number | null;
  diastolic?: number | null;
  glucose?: number | null;
  heart_rate?: number | null;
}

// ─── SVG Trend Chart ─────────────────────────────────────────────

function TrendChart({ data, days }: { data: TrendPoint[]; days: number }) {
  if (!data || data.length === 0) {
    return (
      <div style={{ padding: '32px 0', textAlign: 'center', color: '#9CA3AF', fontSize: 14 }}>
        暂无趋势数据
      </div>
    );
  }

  const W = 320;
  const H = 180;
  const PAD = { top: 20, right: 16, bottom: 30, left: 40 };
  const cw = W - PAD.left - PAD.right;
  const ch = H - PAD.top - PAD.bottom;

  const allSys = data.map(d => d.systolic).filter((v): v is number => v != null);
  const allDia = data.map(d => d.diastolic).filter((v): v is number => v != null);
  const allGlu = data.map(d => d.glucose).filter((v): v is number => v != null);
  const allHr = data.map(d => d.heart_rate).filter((v): v is number => v != null);

  const allVals = [...allSys, ...allDia, ...allGlu.map(v => v * 10), ...allHr];
  if (allVals.length === 0) {
    return (
      <div style={{ padding: '32px 0', textAlign: 'center', color: '#9CA3AF', fontSize: 14 }}>
        暂无趋势数据
      </div>
    );
  }

  const minV = Math.min(...allVals) * 0.85;
  const maxV = Math.max(...allVals) * 1.1;
  const range = maxV - minV || 1;

  const xScale = (i: number) => PAD.left + (data.length > 1 ? (i / (data.length - 1)) * cw : cw / 2);
  const yScale = (v: number) => PAD.top + ch - ((v - minV) / range) * ch;

  const buildPath = (values: (number | null | undefined)[]) => {
    const pts: [number, number][] = [];
    values.forEach((v, i) => {
      if (v != null) pts.push([xScale(i), yScale(v)]);
    });
    if (pts.length < 2) return '';
    return pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
  };

  const sysPath = buildPath(data.map(d => d.systolic));
  const diaPath = buildPath(data.map(d => d.diastolic));
  const gluPath = buildPath(data.map(d => d.glucose != null ? d.glucose * 10 : null));
  const hrPath = buildPath(data.map(d => d.heart_rate));

  const labelInterval = Math.max(1, Math.floor(data.length / 5));

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 'auto' }}>
      {[0, 0.25, 0.5, 0.75, 1].map(f => {
        const y = PAD.top + ch * (1 - f);
        const val = Math.round(minV + range * f);
        return (
          <g key={f}>
            <line x1={PAD.left} y1={y} x2={W - PAD.right} y2={y} stroke="#E5E7EB" strokeWidth={0.5} />
            <text x={PAD.left - 4} y={y + 3} textAnchor="end" fill="#9CA3AF" fontSize={9}>{val}</text>
          </g>
        );
      })}
      {data.map((d, i) => {
        if (i % labelInterval !== 0 && i !== data.length - 1) return null;
        const label = d.date.length >= 10 ? d.date.slice(5, 10) : d.date;
        return (
          <text key={i} x={xScale(i)} y={H - 6} textAnchor="middle" fill="#9CA3AF" fontSize={9}>{label}</text>
        );
      })}
      {sysPath && <path d={sysPath} fill="none" stroke="#EF4444" strokeWidth={2} strokeLinecap="round" />}
      {diaPath && <path d={diaPath} fill="none" stroke="#3B82F6" strokeWidth={2} strokeLinecap="round" />}
      {gluPath && <path d={gluPath} fill="none" stroke="#F59E0B" strokeWidth={2} strokeLinecap="round" strokeDasharray="4 2" />}
      {hrPath && <path d={hrPath} fill="none" stroke="#10B981" strokeWidth={2} strokeLinecap="round" />}
    </svg>
  );
}

function ChartLegend() {
  const items = [
    { label: '收缩压', color: '#EF4444' },
    { label: '舒张压', color: '#3B82F6' },
    { label: '血糖×10', color: '#F59E0B' },
    { label: '心率', color: '#10B981' },
  ];
  return (
    <div style={{ display: 'flex', justifyContent: 'center', gap: 12, marginTop: 8, flexWrap: 'wrap' }}>
      {items.map(it => (
        <div key={it.label} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <div style={{ width: 12, height: 3, borderRadius: 2, background: it.color }} />
          <span style={{ fontSize: 11, color: '#6B7280' }}>{it.label}</span>
        </div>
      ))}
    </div>
  );
}

// ─── Score Ring ───────────────────────────────────────────────────

function ScoreRing({ score }: { score: number | null }) {
  const s = score ?? 0;
  const color = s >= 80 ? '#10B981' : s >= 60 ? '#F59E0B' : '#EF4444';
  const r = 50;
  const circ = 2 * Math.PI * r;
  const offset = circ * (1 - s / 100);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '16px 0' }}>
      <div style={{ position: 'relative', width: 120, height: 120 }}>
        <svg width={120} height={120} style={{ transform: 'rotate(-90deg)' }}>
          <circle cx={60} cy={60} r={r} fill="none" stroke="#E5E7EB" strokeWidth={10} />
          <circle cx={60} cy={60} r={r} fill="none" stroke={color} strokeWidth={10}
            strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round" />
        </svg>
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        }}>
          <span style={{ fontSize: 32, fontWeight: 800, color }}>{score != null ? score : '—'}</span>
          <span style={{ fontSize: 12, color: '#6B7280' }}>健康评分</span>
        </div>
      </div>
      <span style={{ fontSize: 13, color, fontWeight: 600, marginTop: 8 }}>
        {score == null ? '暂无评分' : score >= 80 ? '健康状态良好' : score >= 60 ? '需要关注' : '建议及时就医'}
      </span>
    </div>
  );
}

// ─── Slot Label ──────────────────────────────────────────────────

const SLOT_LABELS: Record<string, string> = {
  morning: '🌅 早上',
  noon: '☀️ 中午',
  evening: '🌆 晚上',
  bedtime: '🌙 睡前',
};

// ─── Main Inner Component ────────────────────────────────────────

function HealthDashboardInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const memberId = searchParams?.get('member_id') || '';

  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [trends, setTrends] = useState<TrendPoint[]>([]);
  const [trendDays, setTrendDays] = useState<number>(7);
  const [loading, setLoading] = useState(true);

  const fetchSummary = useCallback(async () => {
    if (!memberId) return;
    try {
      const res: any = await api.get(`/api/health-dashboard/${memberId}`);
      const data = res?.data || res;
      setSummary(data);
    } catch {
      setSummary(null);
    }
  }, [memberId]);

  const fetchTrends = useCallback(async (days: number) => {
    if (!memberId) return;
    try {
      const res: any = await api.get(`/api/health-dashboard/${memberId}/trends?days=${days}`);
      const data = res?.data || res;
      const dateMap = new Map<string, TrendPoint>();
      const ensurePoint = (d: string) => {
        if (!dateMap.has(d)) dateMap.set(d, { date: d });
        return dateMap.get(d)!;
      };
      (data.blood_pressure || []).forEach((r: any) => {
        const p = ensurePoint(r.date);
        p.systolic = r.systolic ?? p.systolic;
        p.diastolic = r.diastolic ?? p.diastolic;
      });
      (data.blood_sugar || []).forEach((r: any) => {
        const p = ensurePoint(r.date);
        p.glucose = r.fasting ?? r.postprandial ?? p.glucose;
      });
      (data.heart_rate || []).forEach((r: any) => {
        const p = ensurePoint(r.date);
        p.heart_rate = r.value ?? p.heart_rate;
      });
      const merged = Array.from(dateMap.values()).sort((a, b) => a.date.localeCompare(b.date));
      setTrends(merged);
    } catch {
      setTrends([]);
    }
  }, [memberId]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      await Promise.all([fetchSummary(), fetchTrends(trendDays)]);
      setLoading(false);
    })();
  }, [fetchSummary, fetchTrends, trendDays]);

  const handleTrendTab = (days: number) => {
    setTrendDays(days);
    fetchTrends(days);
  };

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', background: '#F0F5FF', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ color: '#9CA3AF', fontSize: 16 }}>加载中…</span>
      </div>
    );
  }

  const bp = summary?.latest_vitals?.blood_pressure;
  const bg = summary?.latest_vitals?.blood_sugar;
  const hr = summary?.latest_vitals?.heart_rate;
  const memberName = summary?.member_name || '家人';

  return (
    <div style={{ background: '#F0F5FF', minHeight: '100vh', paddingBottom: 80 }}>
      {/* 顶部导航栏 */}
      <div style={{
        position: 'sticky', top: 0, zIndex: 50,
        background: 'linear-gradient(135deg, #0EA5E9, #38BDF8)',
        padding: '12px 16px',
        display: 'flex', alignItems: 'center', gap: 12,
        color: '#fff',
        boxShadow: '0 2px 8px rgba(14,165,233,0.3)',
      }}>
        <button
          onClick={() => router.back()}
          style={{ background: 'rgba(255,255,255,0.2)', border: 'none', borderRadius: '50%', width: 36, height: 36, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: '#fff', fontSize: 18 }}
        >←</button>
        <span style={{ flex: 1, fontSize: 18, fontWeight: 700 }}>{memberName} 的健康看板</span>
        <span style={{ width: 32 }} />
      </div>

      {/* M4: 仪表盘卡片区 — 3 张小卡片横排 */}
      <div data-testid="dashboard-vitals" style={{ padding: '16px 16px 0', display: 'flex', gap: 10 }}>
        {/* 血压 */}
        <div style={{
          flex: 1, background: '#fff', borderRadius: 16, padding: '14px 12px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.06)', textAlign: 'center',
          border: bp?.is_abnormal ? '2px solid #EF4444' : '2px solid transparent',
        }}>
          <div style={{ fontSize: 13, color: '#6B7280', marginBottom: 6 }}>💓 血压</div>
          <div style={{
            fontSize: 22, fontWeight: 800,
            color: bp?.is_abnormal ? '#EF4444' : '#10B981',
          }}>
            {bp?.systolic != null ? `${bp.systolic}/${bp.diastolic ?? '-'}` : '—'}
          </div>
          <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 4 }}>mmHg</div>
          {bp?.is_abnormal && (
            <div style={{ marginTop: 6, padding: '2px 8px', borderRadius: 8, background: '#EF4444', color: '#fff', fontSize: 11, fontWeight: 600, display: 'inline-block' }}>偏高</div>
          )}
        </div>
        {/* 血糖 */}
        <div style={{
          flex: 1, background: '#fff', borderRadius: 16, padding: '14px 12px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.06)', textAlign: 'center',
          border: bg?.is_abnormal ? '2px solid #EF4444' : '2px solid transparent',
        }}>
          <div style={{ fontSize: 13, color: '#6B7280', marginBottom: 6 }}>🩸 血糖</div>
          <div style={{
            fontSize: 22, fontWeight: 800,
            color: bg?.is_abnormal ? '#EF4444' : '#10B981',
          }}>
            {bg?.fasting != null ? bg.fasting : bg?.postprandial != null ? bg.postprandial : '—'}
          </div>
          <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 4 }}>mmol/L</div>
          {bg?.is_abnormal && (
            <div style={{ marginTop: 6, padding: '2px 8px', borderRadius: 8, background: '#EF4444', color: '#fff', fontSize: 11, fontWeight: 600, display: 'inline-block' }}>异常</div>
          )}
        </div>
        {/* 心率 */}
        <div style={{
          flex: 1, background: '#fff', borderRadius: 16, padding: '14px 12px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.06)', textAlign: 'center',
          border: hr?.is_abnormal ? '2px solid #EF4444' : '2px solid transparent',
        }}>
          <div style={{ fontSize: 13, color: '#6B7280', marginBottom: 6 }}>❤️ 心率</div>
          <div style={{
            fontSize: 22, fontWeight: 800,
            color: hr?.is_abnormal ? '#EF4444' : '#10B981',
          }}>
            {hr?.value != null ? hr.value : '—'}
          </div>

          <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 4 }}>bpm</div>
          {hr?.is_abnormal && (
            <div style={{ marginTop: 6, padding: '2px 8px', borderRadius: 8, background: '#EF4444', color: '#fff', fontSize: 11, fontWeight: 600, display: 'inline-block' }}>异常</div>
          )}
        </div>
      </div>

      {/* M5: 趋势曲线区 */}
      <div data-testid="dashboard-trends" style={{ padding: '12px 16px 0' }}>
        <div style={{ background: '#fff', borderRadius: 16, padding: 16, boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
            <span style={{ fontSize: 16, fontWeight: 700, color: '#1E293B' }}>📈 趋势曲线</span>
            <div style={{ display: 'flex', gap: 6 }}>
              {[7, 30, 90].map(d => (
                <button
                  key={d}
                  onClick={() => handleTrendTab(d)}
                  style={{
                    padding: '4px 12px', borderRadius: 14, border: 'none',
                    background: trendDays === d ? '#0EA5E9' : '#F1F5F9',
                    color: trendDays === d ? '#fff' : '#64748B',
                    fontSize: 12, fontWeight: 600, cursor: 'pointer',
                  }}
                >{d}天</button>
              ))}
            </div>
          </div>
          <TrendChart data={trends} days={trendDays} />
          <ChartLegend />
        </div>
      </div>

      {/* M6: 今日动态时间线 */}
      <div data-testid="dashboard-timeline" style={{ padding: '12px 16px 0' }}>
        <div style={{ background: '#fff', borderRadius: 16, padding: 16, boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
          <div style={{ fontSize: 16, fontWeight: 700, color: '#1E293B', marginBottom: 12 }}>📋 今日动态</div>
          {!summary?.today_events || summary.today_events.length === 0 ? (
            <div style={{ padding: '20px 0', textAlign: 'center', color: '#9CA3AF', fontSize: 14 }}>暂无数据</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
              {summary.today_events.map((item, idx) => (
                <div key={idx} style={{ display: 'flex', gap: 12, position: 'relative', paddingBottom: 16 }}>
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: 20 }}>
                    <div style={{
                      width: 12, height: 12, borderRadius: '50%', flexShrink: 0,
                      background: item.is_abnormal ? '#EF4444' : item.completed === false ? '#F59E0B' : '#10B981',
                      border: '2px solid #fff',
                      boxShadow: `0 0 0 2px ${item.is_abnormal ? '#FEE2E2' : '#D1FAE5'}`,
                    }} />
                    {idx < summary.today_events.length - 1 && (
                      <div style={{ width: 2, flex: 1, background: '#E5E7EB', marginTop: 4 }} />
                    )}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{
                        fontSize: 14, fontWeight: 600,
                        color: item.is_abnormal ? '#EF4444' : '#1E293B',
                      }}>{item.title}</span>
                      <span style={{ fontSize: 12, color: '#9CA3AF', flexShrink: 0 }}>{item.time}</span>
                    </div>
                    <div style={{ fontSize: 13, color: '#6B7280', marginTop: 2 }}>
                      {item.type === 'medication' ? (item.completed ? '已服用' : '待服用') : ''}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* M7: 用药打卡清单 */}
      <div data-testid="dashboard-medications" style={{ padding: '12px 16px 0' }}>
        <div style={{ background: '#fff', borderRadius: 16, padding: 16, boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <span style={{ fontSize: 16, fontWeight: 700, color: '#1E293B' }}>💊 用药打卡</span>
            {summary?.medication_summary && summary.medication_summary.completion_rate > 0 && (
              <span style={{
                fontSize: 13, fontWeight: 700,
                color: summary.medication_summary.completion_rate >= 100 ? '#10B981' : '#F59E0B',
              }}>{summary.medication_summary.completion_rate}%</span>
            )}
          </div>
          {!summary?.medication_summary || summary.medication_summary.periods.every(p => p.items.length === 0) ? (
            <div style={{ padding: '20px 0', textAlign: 'center', color: '#9CA3AF', fontSize: 14 }}>暂无用药计划</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {summary.medication_summary.periods.filter(p => p.items.length > 0).map((slot, idx) => (
                <div key={slot.period || idx}>
                  <div style={{ fontSize: 14, fontWeight: 600, color: '#374151', marginBottom: 8 }}>
                    {SLOT_LABELS[slot.period] || slot.label}
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {slot.items.map((med, midx) => (
                      <div key={midx} style={{
                        display: 'flex', alignItems: 'center', gap: 10,
                        padding: '8px 12px', borderRadius: 10,
                        background: med.completed ? '#F0FDF4' : '#FEF2F2',
                      }}>
                        <span style={{ fontSize: 18 }}>{med.completed ? '✅' : '⬜'}</span>
                        <div style={{ flex: 1 }}>
                          <span style={{ fontSize: 14, fontWeight: 600, color: '#1E293B' }}>{med.name}</span>
                        </div>
                        <span style={{
                          fontSize: 12, fontWeight: 600,
                          color: med.completed ? '#10B981' : '#EF4444',
                        }}>{med.completed ? '已服' : '未服'}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* M8: 体检报告摘要 */}
      <div data-testid="dashboard-checkup" style={{ padding: '12px 16px 0' }}>
        <div style={{ background: '#fff', borderRadius: 16, padding: 16, boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
          <div style={{ fontSize: 16, fontWeight: 700, color: '#1E293B', marginBottom: 12 }}>🔬 体检报告</div>
          {!summary?.checkup_summary ? (
            <div style={{ padding: '20px 0', textAlign: 'center', color: '#9CA3AF', fontSize: 14 }}>暂无体检报告</div>
          ) : (
            <div>
              {summary.checkup_summary.latest_date && (
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                  <span style={{ fontSize: 14, color: '#374151' }}>最近体检</span>
                  <span style={{ fontSize: 14, fontWeight: 600, color: '#1E293B' }}>{summary.checkup_summary.latest_date}</span>
                </div>
              )}
              {summary.checkup_summary.abnormal_items.length > 0 && (
                <div style={{ marginBottom: 10 }}>
                  <div style={{ fontSize: 13, color: '#6B7280', marginBottom: 6 }}>异常项目</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {summary.checkup_summary.abnormal_items.map((item, i) => (
                      <span key={i} style={{
                        padding: '3px 10px', borderRadius: 10,
                        background: '#FEE2E2', color: '#EF4444',
                        fontSize: 12, fontWeight: 600,
                      }}>{item}</span>
                    ))}
                  </div>
                </div>
              )}
              <div style={{ display: 'flex', gap: 10 }}>
                {summary.checkup_summary.next_followup_days != null && (
                  <div style={{
                    flex: 1, padding: '10px 12px', borderRadius: 10,
                    background: summary.checkup_summary.next_followup_days <= 7 ? '#FEF2F2' : '#F0F9FF',
                    textAlign: 'center',
                  }}>
                    <div style={{ fontSize: 24, fontWeight: 800, color: summary.checkup_summary.next_followup_days <= 7 ? '#EF4444' : '#0EA5E9' }}>
                      {summary.checkup_summary.next_followup_days}
                    </div>
                    <div style={{ fontSize: 12, color: '#6B7280' }}>天后复诊</div>
                  </div>
                )}
                {summary.checkup_summary.next_checkup_days != null && (
                  <div style={{
                    flex: 1, padding: '10px 12px', borderRadius: 10,
                    background: summary.checkup_summary.next_checkup_days <= 30 ? '#FFFBEB' : '#F0F9FF',
                    textAlign: 'center',
                  }}>
                    <div style={{ fontSize: 24, fontWeight: 800, color: summary.checkup_summary.next_checkup_days <= 30 ? '#F59E0B' : '#0EA5E9' }}>
                      {summary.checkup_summary.next_checkup_days}
                    </div>
                    <div style={{ fontSize: 12, color: '#6B7280' }}>天后体检</div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 底部入口 */}
      <div style={{ padding: '16px 16px 24px', display: 'flex', gap: 10 }}>
        <button
          onClick={() => router.push(`/health-reminders?member_id=${memberId}`)}
          style={{
            flex: 1, padding: '14px 0', borderRadius: 22,
            background: 'linear-gradient(135deg, #F59E0B, #FBBF24)',
            color: '#fff', border: 'none', fontSize: 15, fontWeight: 700,
            cursor: 'pointer', boxShadow: '0 4px 12px rgba(245,158,11,0.35)',
          }}
        >🔔 查看提醒</button>
        <button
          onClick={() => router.push(`/health-profile?member_id=${memberId}`)}
          style={{
            flex: 1, padding: '14px 0', borderRadius: 22,
            background: 'linear-gradient(135deg, #0EA5E9, #38BDF8)',
            color: '#fff', border: 'none', fontSize: 15, fontWeight: 700,
            cursor: 'pointer', boxShadow: '0 4px 12px rgba(14,165,233,0.35)',
          }}
        >📋 健康档案</button>
      </div>
    </div>
  );
}

// ─── Default Export with Suspense ─────────────────────────────────

export default function HealthDashboardPage() {
  return (
    <Suspense fallback={<div style={{ minHeight: '100vh', background: '#F0F5FF', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><span style={{ color: '#9CA3AF' }}>加载中…</span></div>}>
      <HealthDashboardInner />
    </Suspense>
  );
}
