'use client';

/**
 * [PRD-468 2026-05-12] 健康档案改版 v2 主页面
 *
 * 信息架构：
 *   家庭成员条 → Hero 卡（基本信息）→ 粘性 Tab（5 个）→ Tab 内容
 *
 * 视觉基线：PRD-441/442（11 级天蓝 + 病历卡左竖线 + 天蓝阴影 + 中老年友好字号）
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Toast } from 'antd-mobile';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';

// ─── 设计 Token（PRD-441/442 11 级天蓝） ─────────────────────────────────
const T = {
  brand50: '#f0f9ff',
  brand100: '#e0f2fe',
  brand200: '#bae6fd',
  brand300: '#7dd3fc',
  brand400: '#38bdf8',
  brand500: '#0ea5e9',
  brand600: '#0284c7',
  brand700: '#0369a1',
  brand800: '#075985',
  yellow: '#f59e0b',
  green: '#10b981',
  danger: '#ef4444',
  cardLineBlue: '3px solid #38bdf8',
  cardLineYellow: '3px solid #f59e0b',
  shadow: '0 4px 16px rgba(56, 189, 248, 0.08)',
  gradient: 'linear-gradient(135deg, #7dd3fc 0%, #0284c7 100%)',
};

const TAB_LIST = [
  { id: 'today-data', label: '今日数据' },
  { id: 'health-tags', label: '健康标签' },
  { id: 'medication-plan', label: '用药计划' },
  { id: 'management', label: '共管' },
  { id: 'events', label: '事件' },
];

const METRIC_LABEL: Record<string, string> = {
  blood_pressure: '血压',
  blood_glucose: '血糖',
  heart_rate: '心率',
  sleep: '睡眠',
  spo2: '血氧',
};

// ─── 类型 ─────────────────────────────────────────────────────────────────
interface FamilyMember {
  id: number;
  user_id: number;
  is_self: boolean;
  nickname: string;
  relationship_type?: string;
  relation_type_name?: string;
  birthday?: string;
  gender?: string;
  height?: number;
  weight?: number;
  member_user_id?: number | null;
}

interface HealthProfileBasic {
  id: number;
  name?: string;
  gender?: string;
  birthday?: string;
  height?: number | null;
  weight?: number | null;
  blood_type?: string;
}

interface MetricSnapshot {
  metric_type: string;
  value: Record<string, any> | null;
  measured_at: string | null;
  source: string | null;
  is_abnormal: boolean;
}

interface TodayMetricsResponse {
  profile_id: number;
  blood_pressure: MetricSnapshot;
  blood_glucose: MetricSnapshot;
  heart_rate: MetricSnapshot;
  sleep: MetricSnapshot;
  spo2: MetricSnapshot;
  medication: {
    checked: number;
    total: number;
    has_overdue: boolean;
  };
}

interface MedicationPlanCard {
  plan_id: number;
  drug_name: string;
  dosage?: string;
  schedule: string[];
  time_chips: { scheduled_time: string; checked: boolean }[];
  weekly_completed: number;
  weekly_total: number;
  weekly_rate: number;
}

// ─── 病历卡组件 ───────────────────────────────────────────────────────────
function MedicalCard({
  children,
  abnormal = false,
  onClick,
  testid,
  style,
}: {
  children: React.ReactNode;
  abnormal?: boolean;
  onClick?: () => void;
  testid?: string;
  style?: React.CSSProperties;
}) {
  return (
    <div
      data-testid={testid}
      onClick={onClick}
      style={{
        background: '#FFFFFF',
        borderLeft: abnormal ? T.cardLineYellow : T.cardLineBlue,
        borderRadius: 16,
        padding: 16,
        boxShadow: T.shadow,
        cursor: onClick ? 'pointer' : 'default',
        position: 'relative',
        ...style,
      }}
    >
      {children}
    </div>
  );
}

// ─── 主页 ─────────────────────────────────────────────────────────────────
export default function HealthProfileV2Page() {
  const router = useRouter();

  // 成员条
  const [members, setMembers] = useState<FamilyMember[]>([]);
  const [selectedMemberId, setSelectedMemberId] = useState<number | null>(null);

  // 当前成员的 profile
  const [profile, setProfile] = useState<HealthProfileBasic | null>(null);

  // 今日 6 项
  const [todayMetrics, setTodayMetrics] = useState<TodayMetricsResponse | null>(null);

  // 用药计划
  const [medications, setMedications] = useState<MedicationPlanCard[]>([]);

  // 当前激活的 Tab
  const [activeTab, setActiveTab] = useState<string>('today-data');
  const isScrollingRef = useRef(false);

  // 关联状态
  const [isLinked, setIsLinked] = useState(false);

  // ─── 拉成员列表 ───
  const fetchMembers = useCallback(async () => {
    try {
      const res: any = await api.get('/api/family/members');
      const data = res.data || res;
      const items: FamilyMember[] = Array.isArray(data.items) ? data.items : [];
      setMembers(items);
      if (items.length > 0 && selectedMemberId == null) {
        const self = items.find((m) => m.is_self) || items[0];
        setSelectedMemberId(self.id);
      }
    } catch {
      setMembers([]);
    }
  }, [selectedMemberId]);

  // ─── 拉 profile (member id) → 取得 profile_id ───
  const fetchProfile = useCallback(async (memberId: number) => {
    try {
      const res: any = await api.get(`/api/health/profile/member/${memberId}`);
      const data = res.data || res;
      setProfile(data);
      return data?.id as number | undefined;
    } catch {
      setProfile(null);
      return undefined;
    }
  }, []);

  // ─── 拉今日 6 项 ───
  const fetchTodayMetrics = useCallback(async (profileId: number) => {
    try {
      const res: any = await api.get(`/api/health-profile-v3/${profileId}/today-metrics`);
      const data = res.data || res;
      setTodayMetrics(data);
    } catch {
      setTodayMetrics(null);
    }
  }, []);

  // ─── 拉用药计划 ───
  const fetchMedication = useCallback(async (profileId: number) => {
    try {
      const res: any = await api.get(`/api/health-profile-v3/${profileId}/medication-plan`);
      const data = res.data || res;
      setMedications(Array.isArray(data.items) ? data.items : []);
    } catch {
      setMedications([]);
    }
  }, []);

  // ─── 拉共管关联状态 ───
  const fetchLinkStatus = useCallback(async (memberId: number) => {
    try {
      const res: any = await api.get('/api/family/management');
      const data = res.data || res;
      const items = Array.isArray(data.items) ? data.items : [];
      setIsLinked(items.some((it: any) => it.managed_member_id === memberId && it.status === 'active'));
    } catch {
      setIsLinked(false);
    }
  }, []);

  useEffect(() => {
    fetchMembers();
  }, [fetchMembers]);

  useEffect(() => {
    if (selectedMemberId == null) return;
    (async () => {
      const profileId = await fetchProfile(selectedMemberId);
      if (profileId != null) {
        await Promise.all([
          fetchTodayMetrics(profileId),
          fetchMedication(profileId),
          fetchLinkStatus(selectedMemberId),
        ]);
      }
    })();
  }, [selectedMemberId, fetchProfile, fetchTodayMetrics, fetchMedication, fetchLinkStatus]);

  // ─── 滚动联动 Tab ───
  useEffect(() => {
    const onScroll = () => {
      if (isScrollingRef.current) return;
      const trigger = window.innerHeight / 3 + 60;
      for (const tab of TAB_LIST) {
        const el = document.getElementById(tab.id);
        if (!el) continue;
        const rect = el.getBoundingClientRect();
        if (rect.top <= trigger && rect.bottom >= trigger) {
          setActiveTab(tab.id);
          break;
        }
      }
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const handleTabClick = useCallback((id: string) => {
    setActiveTab(id);
    isScrollingRef.current = true;
    const el = document.getElementById(id);
    if (el) {
      const top = el.getBoundingClientRect().top + window.scrollY - 100;
      window.scrollTo({ top, behavior: 'smooth' });
    }
    setTimeout(() => { isScrollingRef.current = false; }, 800);
  }, []);

  // ─── 渲染：成员条 ───
  const renderMemberBar = () => (
    <div
      data-testid="prd468-member-bar"
      style={{ background: T.brand50, padding: '12px 16px', display: 'flex', gap: 12, overflowX: 'auto' }}
    >
      {members.map((m) => {
        const active = m.id === selectedMemberId;
        const hasLink = !!m.member_user_id;
        return (
          <div
            key={m.id}
            onClick={() => setSelectedMemberId(m.id)}
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              minWidth: 64,
              cursor: 'pointer',
              position: 'relative',
            }}
          >
            <div
              style={{
                width: 48,
                height: 48,
                borderRadius: '50%',
                background: active ? T.brand500 : T.brand100,
                color: active ? '#fff' : T.brand700,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 20,
                fontWeight: 600,
                border: active ? `2px solid ${T.brand300}` : 'none',
              }}
            >
              {m.is_self ? '我' : (m.nickname || '?').slice(0, 1)}
            </div>
            {hasLink && (
              <div
                style={{
                  width: 10, height: 10, borderRadius: '50%', background: T.brand500,
                  position: 'absolute', top: 0, right: 6, border: '2px solid #fff',
                }}
              />
            )}
            <span style={{ fontSize: 13, color: T.brand800, marginTop: 4 }}>
              {m.is_self ? '本人' : (m.relation_type_name || m.nickname)}
            </span>
          </div>
        );
      })}
      <div
        onClick={() => router.push('/health-profile')}
        style={{
          minWidth: 64, display: 'flex', flexDirection: 'column',
          alignItems: 'center', cursor: 'pointer',
        }}
      >
        <div
          style={{
            width: 48, height: 48, borderRadius: '50%',
            background: '#fff', border: `2px dashed ${T.brand300}`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 24, color: T.brand500,
          }}
        >+</div>
        <span style={{ fontSize: 13, color: T.brand800, marginTop: 4 }}>添加</span>
      </div>
    </div>
  );

  // ─── Hero 卡 ───
  const renderHero = () => {
    if (!profile) return null;
    const fields = [
      { label: '性别', value: profile.gender || '未填' },
      { label: '生日', value: profile.birthday || '未填' },
      { label: '身高', value: profile.height ? `${profile.height} cm` : '未填' },
      { label: '体重', value: profile.weight ? `${profile.weight} kg` : '未填' },
      { label: '血型', value: profile.blood_type || '未填' },
    ];
    return (
      <div style={{ padding: '12px 16px' }}>
        <div
          data-testid="prd468-hero-card"
          style={{
            background: T.gradient, color: '#fff', borderRadius: 16, padding: 20,
            boxShadow: T.shadow,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <div
              style={{
                width: 64, height: 64, borderRadius: '50%',
                background: 'rgba(255,255,255,0.2)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 28, fontWeight: 700,
              }}
            >{(profile.name || '我').slice(0, 1)}</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>{profile.name || '我'}</div>
              {isLinked && (
                <div
                  style={{
                    display: 'inline-block', padding: '2px 8px', borderRadius: 10,
                    background: 'rgba(16, 185, 129, 0.9)', fontSize: 12, fontWeight: 600,
                  }}
                >✓ 已关联本人</div>
              )}
            </div>
            <button
              onClick={() => router.push('/health-profile')}
              style={{
                background: 'rgba(255,255,255,0.25)', color: '#fff',
                border: 'none', borderRadius: 20, padding: '8px 14px',
                fontSize: 14, cursor: 'pointer', fontWeight: 600,
              }}
            >✎ 编辑</button>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 8, marginTop: 16 }}>
            {fields.map((f) => (
              <div key={f.label} style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 12, opacity: 0.85 }}>{f.label}</div>
                <div style={{ fontSize: 14, fontWeight: 600, marginTop: 2 }}>{f.value}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  };

  // ─── 粘性 Tab ───
  const renderStickyTabs = () => (
    <div
      data-testid="prd468-sticky-tabs"
      style={{
        position: 'sticky', top: 56, zIndex: 10, background: '#fff',
        borderBottom: `1px solid ${T.brand200}`,
      }}
    >
      <div style={{ display: 'flex', overflowX: 'auto' }}>
        {TAB_LIST.map((t) => {
          const active = activeTab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => handleTabClick(t.id)}
              style={{
                flex: '0 0 auto', padding: '12px 16px',
                background: 'none', border: 'none',
                fontSize: 16, fontWeight: active ? 700 : 500,
                color: active ? T.brand500 : T.brand800,
                borderBottom: active ? `2px solid ${T.brand500}` : '2px solid transparent',
                cursor: 'pointer',
              }}
            >{t.label}</button>
          );
        })}
      </div>
    </div>
  );

  // ─── Tab 1：今日 6 宫格 ───
  const renderTodayMetrics = () => {
    const tm = todayMetrics;
    const cells = [
      {
        id: 'blood_pressure',
        label: '血压',
        unit: 'mmHg',
        value: tm?.blood_pressure.value ? `${tm.blood_pressure.value.systolic || '-'}/${tm.blood_pressure.value.diastolic || '-'}` : '—',
        abnormal: tm?.blood_pressure.is_abnormal,
      },
      {
        id: 'blood_glucose',
        label: '血糖',
        unit: 'mmol/L',
        value: tm?.blood_glucose.value?.value ?? '—',
        abnormal: tm?.blood_glucose.is_abnormal,
      },
      {
        id: 'heart_rate',
        label: '心率',
        unit: 'bpm',
        value: tm?.heart_rate.value?.value ?? '—',
        abnormal: tm?.heart_rate.is_abnormal,
      },
      {
        id: 'sleep',
        label: '睡眠',
        unit: 'h',
        value: tm?.sleep.value?.duration_h ?? '—',
        abnormal: tm?.sleep.is_abnormal,
      },
      {
        id: 'spo2',
        label: '血氧',
        unit: '%',
        value: tm?.spo2.value?.value ?? '—',
        abnormal: tm?.spo2.is_abnormal,
      },
    ];

    return (
      <div id="today-data" data-testid="prd468-today-data" style={{ padding: '12px 16px' }}>
        <h3 style={{ fontSize: 18, fontWeight: 600, color: T.brand700, margin: '8px 0 12px' }}>今日数据</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12 }}>
          {cells.map((c) => (
            <MedicalCard
              key={c.id}
              abnormal={!!c.abnormal}
              testid={`prd468-metric-${c.id}`}
              onClick={() => router.push(`/health-metric/${c.id}?profileId=${profile?.id || ''}`)}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                <span style={{ fontSize: 13, color: T.brand800 }}>{c.label}</span>
                {c.abnormal && (
                  <span
                    style={{
                      fontSize: 11, fontWeight: 600, color: '#fff', background: T.yellow,
                      padding: '2px 6px', borderRadius: 6,
                    }}
                  >偏高</span>
                )}
              </div>
              <div style={{ marginTop: 8 }}>
                <span style={{ fontSize: 22, fontWeight: 700, color: T.brand700 }}>{c.value}</span>
                <span style={{ fontSize: 13, color: T.brand800, marginLeft: 4 }}>{c.unit}</span>
              </div>
            </MedicalCard>
          ))}
          {/* 第 6 格：用药 X/Y */}
          <MedicalCard
            abnormal={!!tm?.medication.has_overdue}
            testid="prd468-metric-medication"
            onClick={() => handleTabClick('medication-plan')}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
              <span style={{ fontSize: 13, color: T.brand800 }}>用药打卡</span>
              {tm?.medication.has_overdue && (
                <span
                  style={{
                    fontSize: 11, fontWeight: 600, color: '#fff', background: T.yellow,
                    padding: '2px 6px', borderRadius: 6,
                  }}
                >待打卡</span>
              )}
            </div>
            <div style={{ marginTop: 8 }}>
              <span style={{ fontSize: 22, fontWeight: 700, color: T.brand700 }}>
                {tm?.medication.checked ?? 0}/{tm?.medication.total ?? 0}
              </span>
              <span style={{ fontSize: 13, color: T.brand800, marginLeft: 4 }}>已打卡</span>
            </div>
            <div style={{ height: 6, background: T.brand100, borderRadius: 3, marginTop: 8 }}>
              <div
                style={{
                  width: `${tm?.medication.total ? (tm.medication.checked / tm.medication.total) * 100 : 0}%`,
                  height: '100%', background: T.brand500, borderRadius: 3,
                }}
              />
            </div>
          </MedicalCard>
        </div>
      </div>
    );
  };

  // ─── Tab 2：健康标签 ───
  const renderHealthTags = () => (
    <div id="health-tags" data-testid="prd468-health-tags" style={{ padding: '12px 16px' }}>
      <h3 style={{ fontSize: 18, fontWeight: 600, color: T.brand700, margin: '8px 0 12px' }}>健康标签速览</h3>
      <MedicalCard testid="prd468-tags-card">
        <div
          onClick={() => router.push('/health-profile')}
          style={{ display: 'flex', flexWrap: 'wrap', gap: 8, fontSize: 14, cursor: 'pointer' }}
        >
          <span style={{ color: T.brand800 }}>点击进入档案详情查看完整标签列表</span>
        </div>
      </MedicalCard>
    </div>
  );

  // ─── Tab 3：用药计划 ───
  const renderMedicationPlan = () => (
    <div id="medication-plan" data-testid="prd468-medication-plan" style={{ padding: '12px 16px' }}>
      <h3 style={{ fontSize: 18, fontWeight: 600, color: T.brand700, margin: '8px 0 12px' }}>用药计划</h3>
      {medications.length === 0 ? (
        <MedicalCard>
          <div style={{ textAlign: 'center', color: T.brand800, padding: '24px 0', fontSize: 14 }}>
            暂无用药计划
            <div
              onClick={() => router.push('/health-plan/medications/add')}
              style={{
                marginTop: 12, padding: '10px 20px', background: T.brand500, color: '#fff',
                borderRadius: 22, display: 'inline-block', cursor: 'pointer', fontSize: 14,
              }}
            >+ 添加用药</div>
          </div>
        </MedicalCard>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {medications.map((m) => (
            <MedicalCard key={m.plan_id} testid={`prd468-med-${m.plan_id}`}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 18, fontWeight: 600, color: T.brand700 }}>
                  {m.drug_name} {m.dosage}
                </span>
                <span style={{ fontSize: 13, color: T.brand800 }}>{`每日 ${m.schedule.length} 次`}</span>
              </div>
              <div style={{ display: 'flex', gap: 10, marginTop: 12, flexWrap: 'wrap' }}>
                {m.time_chips.map((c) => (
                  <div
                    key={c.scheduled_time}
                    style={{
                      padding: '8px 12px', borderRadius: 8,
                      background: c.checked ? '#d1fae5' : '#fee2e2',
                      color: c.checked ? '#065f46' : '#991b1b',
                      fontSize: 14, fontWeight: 600,
                    }}
                  >
                    {c.checked ? '✓ ' : '⏰ '}{c.scheduled_time}
                  </div>
                ))}
              </div>
              <div style={{ marginTop: 12 }}>
                <div style={{ fontSize: 13, color: T.brand800, marginBottom: 4 }}>
                  本周完成率 {m.weekly_rate}%（{m.weekly_completed}/{m.weekly_total}）
                </div>
                <div style={{ height: 6, background: T.brand100, borderRadius: 3 }}>
                  <div style={{ width: `${m.weekly_rate}%`, height: '100%', background: T.brand500, borderRadius: 3 }} />
                </div>
              </div>
              <div style={{ marginTop: 10, fontSize: 13, color: T.brand600 }}>
                ⓘ 漏打卡超 15 分钟将通知共管者
              </div>
            </MedicalCard>
          ))}
        </div>
      )}
    </div>
  );

  // ─── Tab 4：共管与提醒 ───
  const renderManagement = () => (
    <div id="management" data-testid="prd468-management" style={{ padding: '12px 16px' }}>
      <h3 style={{ fontSize: 18, fontWeight: 600, color: T.brand700, margin: '8px 0 12px' }}>共管与提醒</h3>
      <MedicalCard>
        <div
          onClick={() => router.push('/health-profile')}
          style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '12px 0', borderBottom: `1px solid ${T.brand100}`, cursor: 'pointer',
          }}
        >
          <span style={{ fontSize: 15, color: T.brand800 }}>👥 共同管理者</span>
          <span style={{ fontSize: 13, color: T.brand600 }}>查看 ▶</span>
        </div>
        <div
          onClick={() => router.push('/health-profile')}
          style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '12px 0', borderBottom: `1px solid ${T.brand100}`, cursor: 'pointer',
          }}
        >
          <span style={{ fontSize: 15, color: T.brand800 }}>📨 邀请本人关联</span>
          <span style={{ fontSize: 13, color: isLinked ? T.green : T.brand600 }}>
            {isLinked ? '✓ 已关联 ▶' : '邀请 ▶'}
          </span>
        </div>
        <div
          style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '12px 0',
          }}
        >
          <span style={{ fontSize: 15, color: T.brand800 }}>🔔 漏打卡代为提醒</span>
          <span style={{ fontSize: 13, color: T.green, fontWeight: 600 }}>开启（15min 宽限）</span>
        </div>
        <div
          style={{
            background: T.brand50, padding: '10px 12px', borderRadius: 8,
            fontSize: 13, color: T.brand800, marginTop: 8, lineHeight: 1.6,
          }}
        >
          系统级固定开启。当本人漏打卡超过 15 分钟时，全部共管者将收到通知，提醒联系本人。
        </div>
      </MedicalCard>
    </div>
  );

  // ─── Tab 5：事件流 ───
  const renderEvents = () => (
    <div id="events" data-testid="prd468-events" style={{ padding: '12px 16px 80px' }}>
      <h3 style={{ fontSize: 18, fontWeight: 600, color: T.brand700, margin: '8px 0 12px' }}>健康事件流</h3>
      <MedicalCard>
        <div style={{ fontSize: 14, color: T.brand800, lineHeight: 1.8 }}>
          事件流将聚合您的指标录入、用药打卡、报告上传等关键事件。
          <br />
          请在「今日数据」录入一项指标，事件流将自动展示。
        </div>
      </MedicalCard>
    </div>
  );

  return (
    <div style={{ background: '#F0F9FF', minHeight: '100vh', paddingBottom: 80 }}>
      <GreenNavBar>我的健康档案</GreenNavBar>
      {renderMemberBar()}
      {renderHero()}
      {renderStickyTabs()}
      {renderTodayMetrics()}
      {renderHealthTags()}
      {renderMedicationPlan()}
      {renderManagement()}
      {renderEvents()}
    </div>
  );
}
